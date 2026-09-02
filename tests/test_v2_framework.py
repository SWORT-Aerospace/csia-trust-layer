"""CSIA v2 — the plugin framework itself: evidence, registry, functions.

These test the CONTRACT, not any particular domain. A domain that broke one of
these would be rejected at registration or would produce evidence the function
graph could not read, and both of those are failures of the framework's
promise rather than of the domain.
"""

import ast
import os

import pytest

from csia.v2.attribution import (AMBIGUOUS, NO_EVIDENCE, UNIQUE,
                                 CrossDomainRelation, attribute)
from csia.v2.domain import DOMAIN_IDS, AssuranceDomain, DomainResult, Snapshot
from csia.v2.evidence import (Applicability, EvidenceRecord, ObservationState,
                              worst)
from csia.v2.functions import (DEGRADED, ELIGIBLE, INELIGIBLE, RANK, UNKNOWN,
                               FunctionGraph, SystemFunction, system_state)
from csia.v2.registry import CORE_SCHEMA_MAJOR, DomainRegistry, PluginRejected

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, "csia", "v2")


def rec(**kw):
    base = dict(domain="POWER", component="battery", relation="power.x",
                source="power", observation_state=ObservationState.NOMINAL,
                applicability=Applicability.APPLICABLE)
    base.update(kw)
    return EvidenceRecord(**base)


# ------------------------------------------------------------- §3 evidence
def test_the_evidence_record_has_no_scalar_health_field_anywhere():
    """§3/§18. A domain without a residual must not be able to invent one,
    and a categorical verdict must not be silently comparable with a
    Beta-distributed sensor trust. The absence is the mechanism."""
    fields = set(EvidenceRecord.__dataclass_fields__)
    for banned in ("score", "health", "confidence", "trust", "probability",
                   "likelihood", "quality", "grade"):
        assert banned not in fields, (
            f"EvidenceRecord grew a {banned!r} field; §3 says evidence may be "
            f"categorical and §18 forbids forcing it into one number")


def test_the_categorical_verdict_is_required_and_the_numbers_are_not():
    r = rec()
    assert r.observation_state is ObservationState.NOMINAL
    assert r.measured_value is None and r.residual is None
    with pytest.raises(TypeError):
        rec(observation_state="NOMINAL")
    with pytest.raises(TypeError):
        rec(applicability="APPLICABLE")
    with pytest.raises(ValueError):
        rec(component="")


def test_unavailable_and_not_applicable_are_never_collapsed():
    """"We could not look" must not become "there was nothing to look at":
    collapsing them makes a missing sensor indistinguishable from a healthy
    one, which is the whole failure mode v1.1's freshness logic exists for."""
    assert ObservationState.UNAVAILABLE != ObservationState.NOT_APPLICABLE
    assert worst([rec(observation_state=ObservationState.NOT_APPLICABLE)]) \
        is ObservationState.NOT_APPLICABLE
    assert worst([rec(observation_state=ObservationState.UNAVAILABLE)]) \
        is ObservationState.UNAVAILABLE
    # NOT_APPLICABLE is not adverse; UNAVAILABLE is not adverse either, but
    # it outranks VIOLATED when a function asks whether it may proceed.
    assert not rec(observation_state=ObservationState.NOT_APPLICABLE).is_adverse
    assert not rec(observation_state=ObservationState.UNAVAILABLE).is_adverse


def test_no_evidence_is_not_good_news():
    assert worst([]) is ObservationState.UNAVAILABLE


def test_the_three_timestamps_survive_as_three():
    """§6. One age field is the sum of four segments and identifies none."""
    r = rec(timestamp_validity=1.0, timestamp_arrival=1.010,
            timestamp_processed=1.025)
    lat = r.latencies()
    assert lat["transport_latency"] == pytest.approx(0.010)
    assert lat["processing_latency"] == pytest.approx(0.015)
    assert lat["end_to_end_latency"] == pytest.approx(0.025)


def test_dependencies_are_a_list_not_a_number():
    """§22: store dependencies as explicit structure. Do NOT yet compute
    independence scores."""
    r = rec(dependencies=("POWER/rail_5v", "COMMUNICATION/gnss_serial"))
    assert isinstance(r.dependencies, tuple)
    assert isinstance(r.to_dict()["dependencies"], list)


# ------------------------------------------------------------- §21 registry
class _Dummy(AssuranceDomain):
    domain_id = "POWER"
    schema_version = "2.0.0"
    relations = ("x",)
    affected_functions = ("F",)

    def evaluate(self, snapshot):
        return DomainResult(domain=self.domain_id, records=())


def test_the_registry_rejects_a_duplicate_id():
    reg = DomainRegistry()
    reg.register(_Dummy())
    with pytest.raises(PluginRejected, match="duplicate"):
        reg.register(_Dummy())


def test_the_registry_rejects_an_unknown_domain_id():
    class Rogue(_Dummy):
        domain_id = "VIBES"
    with pytest.raises(PluginRejected, match="unknown domain_id"):
        DomainRegistry().register(Rogue())


def test_the_registry_rejects_a_plugin_from_another_contract():
    class Old(_Dummy):
        schema_version = "1.4.0"
    with pytest.raises(PluginRejected, match="schema_version"):
        DomainRegistry().register(Old())
    assert CORE_SCHEMA_MAJOR == "2"


def test_the_registry_rejects_a_plugin_that_declares_nothing():
    class Silent(_Dummy):
        relations = ()
    with pytest.raises(PluginRejected, match="no relations"):
        DomainRegistry().register(Silent())

    class Unattached(_Dummy):
        affected_functions = ()
    with pytest.raises(PluginRejected, match="affected_functions"):
        DomainRegistry().register(Unattached())


def test_registration_order_cannot_change_the_answer():
    """§21's determinism requirement, made checkable: two hosts registering
    the same plugins in different orders must produce the same evidence
    sequence and therefore the same ledger."""
    class P(_Dummy):
        domain_id = "POWER"

    class C(_Dummy):
        domain_id = "COMPUTE"
    a, b = DomainRegistry(), DomainRegistry()
    a.register(P())
    a.register(C())
    b.register(C())
    b.register(P())
    assert ([d.domain_id for d in a.domains()]
            == [d.domain_id for d in b.domains()] == ["COMPUTE", "POWER"])


def test_every_domain_id_names_a_subsystem_not_a_vehicle():
    """§25. The core's vocabulary must serve an aircraft, a boat, an arm and
    a test stand equally."""
    for name in DOMAIN_IDS:
        assert name.isupper()
    for aviation in ("FLIGHT", "AIRCRAFT", "UAV", "DRONE", "AVIONIC",
                     "AIRFRAME", "ROTOR", "PROPELLER"):
        assert not any(aviation in d for d in DOMAIN_IDS)


# -------------------------------------------------------- §15/§16 functions
def _f(name, **kw):
    kw.setdefault("summary", "")
    kw.setdefault("required_domains", ("POWER",))
    return SystemFunction(name=name, **kw)


def test_unknown_outranks_ineligible():
    """"Cannot determine" must not be acted on as though it were
    "available", and it must not be quietly softened to "unavailable"
    either: they are different states with different remedies."""
    assert RANK[UNKNOWN] > RANK[INELIGIBLE] > RANK[DEGRADED] > RANK[ELIGIBLE]


def test_a_required_domain_that_said_nothing_leaves_the_function_unknown():
    g = FunctionGraph([_f("F")])
    v = g.evaluate([])["F"]
    assert v.state == UNKNOWN
    assert v.domain_states["POWER"] == "UNAVAILABLE"


def test_a_supporting_domain_can_degrade_a_function_but_never_remove_it():
    g = FunctionGraph([_f("F", required_domains=("POWER",),
                          supporting_domains=("COMPUTE",))])
    records = [rec(affected_functions=("F",)),
               rec(domain="COMPUTE", component="cpu",
                   observation_state=ObservationState.VIOLATED,
                   affected_functions=("F",))]
    v = g.evaluate(records)["F"]
    assert v.state == DEGRADED and v.limiting_domain == "COMPUTE"


def test_a_no_degradation_domain_stops_the_function_instead_of_degrading_it():
    """§15's whole point: the same evidence costs different functions
    different amounts, and the difference is DECLARED per function."""
    records = [rec(domain="TIMING", component="nav",
                   observation_state=ObservationState.DEGRADED,
                   affected_functions=("STRICT", "RELAXED"))]
    g = FunctionGraph([
        _f("STRICT", required_domains=("TIMING",),
           no_degradation_domains=("TIMING",)),
        _f("RELAXED", required_domains=("TIMING",))])
    out = g.evaluate(records)
    assert out["STRICT"].state == INELIGIBLE
    assert out["RELAXED"].state == DEGRADED


def test_the_verdict_names_the_domain_that_set_it():
    """§17's central column. A component-oriented monitor cannot answer
    'what is limiting this function', and that answer is the product."""
    records = [rec(affected_functions=("F",)),
               rec(domain="TIMING", component="nav",
                   observation_state=ObservationState.VIOLATED,
                   reason_codes=("TIMING_DEADLINE_MISSED",),
                   affected_functions=("F",))]
    v = FunctionGraph([_f("F", required_domains=("POWER", "TIMING"))]
                      ).evaluate(records)["F"]
    assert v.state == INELIGIBLE and v.limiting_domain == "TIMING"
    assert "TIMING_DEADLINE_MISSED" in v.reason_codes


def test_the_system_word_is_derived_from_the_functions():
    def verdicts(*states):
        return {f"F{i}": FunctionGraph([_f(f"F{i}")]).evaluate(
            [rec(domain="POWER", affected_functions=(f"F{i}",),
                 observation_state=s)])[f"F{i}"]
            for i, s in enumerate(states)}
    assert system_state(verdicts(ObservationState.NOMINAL)) == "NORMAL"
    assert system_state(verdicts(ObservationState.DEGRADED)) == "DEGRADED"
    assert system_state(verdicts(ObservationState.VIOLATED)) == "UNAVAILABLE"
    assert system_state(verdicts(ObservationState.NOMINAL,
                                 ObservationState.VIOLATED)) == "RESTRICTED"
    assert system_state({}) == "UNAVAILABLE"


# ---------------------------------------------------------- §29 attribution
def test_nothing_adverse_is_no_evidence_not_a_clean_bill_of_health():
    a = attribute([rec()])
    assert a.verdict == NO_EVIDENCE and a.candidates == ()


def test_a_lone_candidate_is_not_unique_without_something_ruling_others_out():
    """§29 carries v1.1's discipline across domains: a leader at posterior
    0.9998 with no discriminating evidence is NOT a diagnosis, and neither is
    'it is the only thing we noticed'."""
    lonely = rec(observation_state=ObservationState.VIOLATED)
    a = attribute([lonely])
    assert a.verdict == AMBIGUOUS
    assert "no affirmatively nominal" in a.detail["why"]


def test_unique_requires_an_affirmative_exclusion_and_names_it():
    adverse = rec(observation_state=ObservationState.VIOLATED)
    elsewhere = rec(domain="COMPUTE", component="cpu",
                    relation="compute.resource_headroom")
    a = attribute([adverse, elsewhere])
    assert a.verdict == UNIQUE
    assert a.discriminators == ("COMPUTE/cpu:compute.resource_headroom",)


def test_a_relation_alone_never_promotes_a_component_to_a_cause():
    """§29 UNSUPPORTED. Being named by a relation is not evidence."""
    adverse = rec(observation_state=ObservationState.VIOLATED)
    elsewhere = rec(domain="COMPUTE", component="cpu")
    rel = CrossDomainRelation(
        relation_id="r", domains=("POWER",),
        implicates=("ACTUATION/motor_0",), description="")
    a = attribute([adverse, elsewhere], (rel,))
    assert a.unsupported == ("ACTUATION/motor_0",)
    assert "ACTUATION/motor_0" not in [c.id for c in a.candidates]


def test_a_shared_adverse_dependency_is_retained_not_adopted():
    """§14/§28-E. Two things failing on one rail is not proof the rail did
    it: a rail fault and two coincident faults produce the same evidence."""
    rail = rec(component="rail_5v",
               observation_state=ObservationState.VIOLATED)
    one = rec(domain="SENSOR", component="source.gps",
              observation_state=ObservationState.VIOLATED,
              dependencies=("POWER/rail_5v",))
    two = rec(domain="COMMUNICATION", component="radio",
              observation_state=ObservationState.VIOLATED,
              dependencies=("POWER/rail_5v",))
    a = attribute([rail, one, two])
    assert a.verdict == AMBIGUOUS, "a common cause is not a unique cause"
    assert a.common_cause == "POWER/rail_5v"
    assert "POWER/rail_5v" in [c.id for c in a.candidates]


def test_a_common_cause_is_found_through_the_declared_chain_not_only_next_door():
    """A rail feeds a converter feeds a bus feeds a sensor. Counting only
    DIRECT dependencies would miss exactly the case §28-E is about."""
    rail = rec(component="rail_5v",
               observation_state=ObservationState.VIOLATED)
    conv = rec(component="rail_3v3",
               observation_state=ObservationState.VIOLATED,
               dependencies=("POWER/rail_5v",))
    sensor = rec(domain="SENSOR", component="source.imu0",
                 observation_state=ObservationState.VIOLATED,
                 dependencies=("POWER/rail_3v3",))
    link = rec(domain="COMMUNICATION", component="radio",
               observation_state=ObservationState.VIOLATED,
               dependencies=("POWER/rail_5v",))
    a = attribute([rail, conv, sensor, link])
    assert a.common_cause == "POWER/rail_5v"


def test_a_healthy_shared_dependency_is_not_offered_as_a_common_cause():
    """The battery feeds everything, so it is reachable from every candidate.
    It is only a common-cause ALTERNATIVE when it carries adverse evidence of
    its own -- otherwise the honest reading is that it has been exonerated."""
    battery = rec(component="battery")                    # NOMINAL
    one = rec(component="rail_5v",
              observation_state=ObservationState.VIOLATED,
              dependencies=("POWER/battery",))
    two = rec(component="rail_3v3",
              observation_state=ObservationState.VIOLATED,
              dependencies=("POWER/battery",))
    a = attribute([battery, one, two])
    assert a.common_cause is None


def test_a_derived_verdict_is_evidence_but_never_a_candidate():
    """A function eligibility roll-up is a conclusion computed from other
    records in the same tick. Admitting it as a candidate counts its own
    inputs twice and fills the list with things that cannot fail."""
    source = rec(domain="SENSOR", component="source.gps",
                 observation_state=ObservationState.VIOLATED)
    verdict = rec(domain="SENSOR", component="v1_1.COARSE_NAVIGATION",
                  relation="v1_1.function_eligibility",
                  observation_state=ObservationState.VIOLATED,
                  attributable=False)
    other = rec(domain="POWER", component="battery")
    a = attribute([source, verdict, other])
    assert [c.id for c in a.candidates] == ["SENSOR/source.gps"]


def test_attribution_is_deterministic_under_record_reordering():
    records = [rec(component="rail_5v",
                   observation_state=ObservationState.VIOLATED),
               rec(domain="COMPUTE", component="cpu",
                   observation_state=ObservationState.DEGRADED),
               rec(domain="TIMING", component="nav")]
    first = attribute(records).to_dict()
    assert attribute(list(reversed(records))).to_dict() == first


# --------------------------------------------------- §§1, 25 core hygiene
def test_the_core_framework_contains_no_aircraft_vocabulary():
    """§25, checked against the source rather than promised in a README.

    The profile packages may say `aircraft` as much as they like. The core
    may not: the moment it does, the framework has an opinion about what it
    is bolted to and §37's genericity test is decided in advance.
    """
    banned = ("aircraft", "flight", "uav", "drone", "avionic", "airframe",
              "autopilot", "rotor", "gnss", "airspeed", "altitude")
    offenders = []
    for name in sorted(os.listdir(V2)):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(V2, name), encoding="utf-8").read()
        tree = ast.parse(text)
        # Identifiers and string literals only. Prose in a docstring may
        # legitimately mention an aircraft while EXPLAINING why the code
        # does not depend on one, and grepping the whole file would flag
        # exactly those explanations.
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and any(
                    b in node.id.lower() for b in banned):
                offenders.append(f"{name}: name {node.id}")
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and any(
                    b in node.name.lower() for b in banned):
                offenders.append(f"{name}: def {node.name}")
            elif isinstance(node, ast.Attribute) and any(
                    b in node.attr.lower() for b in banned):
                offenders.append(f"{name}: attribute {node.attr}")
    assert not offenders, f"aircraft vocabulary in the core: {offenders}"


def test_the_core_never_imports_a_profile_or_a_domain():
    """Dependencies point one way: profiles and domains depend on the core,
    never the reverse. A core that imported a domain could not have a domain
    added without editing it, which is the monolith §1 forbids."""
    offenders = []
    for name in sorted(os.listdir(V2)):
        if not name.endswith(".py") or name == "__init__.py":
            continue
        tree = ast.parse(open(os.path.join(V2, name), encoding="utf-8").read())
        for node in ast.walk(tree):
            mod = ""
            if isinstance(node, ast.ImportFrom):
                mod = ("." * node.level) + (node.module or "")
            elif isinstance(node, ast.Import):
                mod = ",".join(a.name for a in node.names)
            if "domains" in mod or "profiles" in mod:
                offenders.append(f"{name}: imports {mod}")
    assert not offenders, offenders


def test_a_snapshot_is_a_plain_mapping_not_a_typed_vehicle():
    """§25 again, structurally. A typed `Aircraft` here would have decided
    the genericity question on line one."""
    s = Snapshot(t=0.0, signals={"POWER": {"battery": {"voltage_v": 22.0}}})
    assert s.get("POWER", "battery", "voltage_v") == 22.0
    assert s.get("POWER", "battery", "missing") is None
    assert s.get("NOPE", "nope", "nope") is None
    assert s.has("POWER", "battery", "voltage_v")
    assert not s.has("POWER", "battery", "current_a")
    assert s.v1_1_payload is None, "v1.1 is optional, not required"


def test_both_verdicts_report_what_was_ruled_out_the_same_way():
    """A consumer should not need two code paths to read "what was excluded"
    depending on whether the verdict came out UNIQUE or AMBIGUOUS."""
    one = rec(observation_state=ObservationState.VIOLATED)
    elsewhere = rec(domain="COMPUTE", component="cpu")
    unique = attribute([one, elsewhere])
    assert unique.verdict == UNIQUE
    assert unique.detail["domains_excluded"] == ["COMPUTE"]

    two = rec(domain="TIMING", component="nav",
              observation_state=ObservationState.VIOLATED)
    ambiguous = attribute([one, two, elsewhere])
    assert ambiguous.verdict == AMBIGUOUS
    assert ambiguous.detail["domains_excluded"] == ["COMPUTE"]
    assert ambiguous.discriminators == ("COMPUTE/cpu:power.x",)
