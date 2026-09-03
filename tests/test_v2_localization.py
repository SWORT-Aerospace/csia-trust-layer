"""Phase C §41 -- the thirteen required test properties.

Each of §41's properties gets at least one test here, and the test name says
which property it is. Four of them (10-13) already had coverage from the v2
Phase A/B work; they are restated against the Phase C code path rather than
assumed to still hold, because Phase C added a plugin supervisor between the
engine and every domain and that is exactly the kind of change that quietly
breaks a genericity or determinism claim.

WHAT THESE TESTS ARE FOR
------------------------
Not "does localization run". Every property below is a way the layer could
LOOK right and BE wrong:

    a scenario label leaking into the evidence index would let the framework
    recognise the answer instead of deriving it

    a hypothesis confirmed by nothing would still be reported as a cause if
    the verdict logic counted survivors

    a plugin that raised and was swallowed would leave the function reading
    healthy, which is the failure mode §21 names in so many words

    a common cause counted once per downstream symptom would turn one fault
    into three and the operator would chase all three
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

from csia.v2 import signatures as SIG
from csia.v2 import scenarios as SC
from csia.v2.evidence import EvidenceRecord, ObservationState
from csia.v2.explanation import explain_all
from csia.v2.ingest import NavigationDomainInput
from csia.v2.ledger import V2AssuranceLedger, V2LedgerContext
from csia.v2.localization import (AMBIGUOUS, EvidenceIndex, SUPPORTED,
                                  UNSUPPORTED, localize, localize_all,
                                  minimum_resolving_subsets)
from csia.v2.plugin_runtime import (AVAILABLE, DEGRADED, FAILED,
                                    NOT_CONFIGURED, FailingDomain)
from csia.v2.profiles import build_engine_for
from csia.v2.profiles.matched_scenarios import (MATCHED_BY_NAME, MATCHED_SETS,
                                                SET_SYMPTOM)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TICKS = 60


def _feed(sc):
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed
    if sc.system != "aircraft":
        return None
    return example_payload_feed(getattr(sc, "v1_1_variant", "clean"))


def _run(name, ticks=_TICKS, engine=None):
    sc = MATCHED_BY_NAME[name]
    engine = engine or build_engine_for(sc)
    return engine, SC.run(engine, sc, ticks=ticks, payload_for=_feed(sc))


def _final(name, **kw):
    return _run(name, **kw)[1][-1]


def _loc(name, symptom=None, **kw):
    """The localizations for one scenario's matched symptom."""
    sc = MATCHED_BY_NAME[name]
    want = symptom or next(SET_SYMPTOM[s] for s, m in MATCHED_SETS.items()
                           if sc.name in m)
    return [x for x in _final(name, **kw).localizations if x.symptom == want]


# ===================================================================== §41.1
def test_1_v1_1_semantics_are_unchanged_by_everything_phase_c_added():
    """The v1.1 verdicts under the full Phase C engine are identical to the
    ones v1.1 produces on its own, payload for payload."""
    from csia.v1_1.monitor import parse
    from csia.v2.profiles.aircraft_scenarios import load_v1_1_example

    variants = sorted({getattr(sc, "v1_1_variant", "clean")
                       for sc in MATCHED_BY_NAME.values()
                       if sc.system == "aircraft"})
    assert variants
    for variant in variants:
        payload = load_v1_1_example(variant)
        own = parse(payload)
        inp = NavigationDomainInput.from_external_payload(payload)
        assert inp.function_eligibility == own.function_eligibility
        assert inp.function_reasons == own.function_reasons
        assert inp.assurance_level == own.assurance
        assert inp.diagnosis.leader == own.leader
        assert inp.diagnosis.posterior == own.posterior
        assert inp.diagnosis.support_state == own.support_state
        assert inp.diagnosis.ambiguity == own.ambiguity
        assert inp.sequential_alarming == own.sequential_alarms


def test_1b_the_frozen_v1_1_output_schema_version_is_still_the_only_one():
    from csia.v2.ingest import SUPPORTED_MAJOR_MINOR
    assert SUPPORTED_MAJOR_MINOR == ("1.1",)


# ===================================================================== §41.2
@pytest.mark.parametrize("name", ["MS_A1_SENSOR_DELAY", "MS_D1_NAV_SOURCE",
                                  "MS_C1_INDEPENDENT"])
def test_2_the_internal_and_external_interfaces_localize_identically(name):
    """§20's typed path must not be a second, weaker semantics."""
    from csia.v2.profiles.aircraft_scenarios import load_v1_1_example

    sc = MATCHED_BY_NAME[name]
    payload = load_v1_1_example(getattr(sc, "v1_1_variant", "clean"))
    ext = NavigationDomainInput.from_external_payload(payload)
    itl = NavigationDomainInput.from_trusted_payload(payload)
    assert ext.semantic_key() == itl.semantic_key()
    assert ext.provenance_path == "external"
    assert itl.provenance_path == "internal"


# ===================================================================== §41.3
@pytest.mark.parametrize("name", sorted(MATCHED_BY_NAME))
def test_3_localization_is_deterministic_for_the_same_evidence(name):
    once = [x.to_dict() for x in _loc(name)]
    twice = [x.to_dict() for x in _loc(name)]
    assert once == twice


def test_3b_localization_does_not_depend_on_record_order():
    final = _final("MS_A2_COMMUNICATION_DELAY")
    forward = localize_all(SIG.SYMPTOMS, final.records, SIG.PREDICATES)
    backward = localize_all(SIG.SYMPTOMS, tuple(reversed(final.records)),
                            SIG.PREDICATES)
    assert [x.to_dict() for x in forward] == [x.to_dict() for x in backward]


# ===================================================================== §41.4
def test_4_no_scenario_label_or_ground_truth_reaches_the_evidence_index():
    """THE PROPERTY THAT MAKES EVERY OTHER RESULT MEAN ANYTHING.

    If the scenario name, its tags, its expectation string or the injected
    ground truth appeared anywhere in the records, the framework could
    recognise the answer instead of deriving it, and the whole of §§7-10
    would be a lookup table wearing a diagnosis costume.
    """
    # The scenario NAMES, and the tags that identify a scenario rather than
    # describe a subsystem. "position" and "actuator" are ordinary vocabulary
    # a records document is entitled to contain -- the first version of this
    # test banned them and failed on a legitimate function name, which would
    # have taught me to weaken the test rather than trust it.
    generic = {"matched", "position", "actuator", "multi_sensor", "set_a",
               "set_b", "set_c", "set_d", "model_gap", "irreducible"}
    forbidden = set()
    for sc in MATCHED_BY_NAME.values():
        forbidden.add(sc.name.lower())
        forbidden.update(t.lower() for t in sc.tags if t.lower() not in generic)
    for name in sorted(MATCHED_BY_NAME):
        sc = MATCHED_BY_NAME[name]
        final = _final(name)
        blob = json.dumps([r.to_dict() for r in final.records],
                          sort_keys=True, default=str).lower()
        for token in forbidden:
            assert token not in blob, f"{name}: leaked {token!r}"
        # The expectation text is the answer key. Not one word of it that is
        # longer than a preposition may appear either.
        for word in sc.expectation.lower().split():
            word = word.strip(".,:;()\"'")
            if len(word) > 9 and word.isalpha() and word not in (
                    "hypothesis", "hypotheses", "supported", "unresolved",
                    "eligibility", "communication", "independent",
                    "dependency", "measurable", "estimator", "refuted",
                    "localizes", "mechanical", "actuation", "signature"):
                assert word not in blob, f"{name}: leaked {word!r}"


def test_4b_localize_receives_an_index_and_a_subject_and_nothing_else():
    """A signature check, so no future edit can smuggle the scenario in."""
    src = ast.parse(open(os.path.join(_ROOT, "csia", "v2", "localization.py"),
                         encoding="utf-8").read())
    fn = next(n for n in src.body
              if isinstance(n, ast.FunctionDef) and n.name == "localize")
    assert [a.arg for a in fn.args.args] == ["spec", "index", "subject",
                                             "predicates"]
    assert fn.args.vararg is None and fn.args.kwarg is None


# ===================================================================== §41.5
def test_5_the_minimum_resolving_subset_really_does_resolve_it():
    """And a smaller one really does not -- otherwise 'minimum' is a word."""
    from itertools import combinations

    sc = MATCHED_BY_NAME["MS_A2_COMMUNICATION_DELAY"]
    final = _final(sc.name)
    index = EvidenceIndex(final.records)
    spec = SIG.SYMPTOMS_BY_ID["OUTPUT_STALE"]
    subject = spec.detect(index)[0]
    got = minimum_resolving_subsets(spec, index, subject, SIG.PREDICATES)

    full = localize(spec, index, subject, SIG.PREDICATES)
    assert got["verdict"] == full.verdict
    assert got["minimum_subset"] is not None, got["note"]
    best = tuple(got["minimum_subset"])

    def limited_to(subset):
        allowed = set(subset)
        from csia.v2.localization import Predicate
        table = {pid: (SIG.PREDICATES[pid] if pid in allowed
                       else Predicate(pid, "withheld", "", lambda *_: None))
                 for pid in SIG.PREDICATES}
        return localize(spec, index, subject, table)

    assert limited_to(best).verdict == full.verdict
    assert limited_to(best).supported == full.supported
    for smaller in combinations(best, max(len(best) - 1, 0)):
        if len(smaller) == len(best):
            continue
        got_small = limited_to(smaller)
        assert not (got_small.verdict == full.verdict
                    and got_small.supported == full.supported), (
            f"{smaller} already resolves it, so {best} is not minimal")


def test_5b_unmeasurable_predicates_are_never_enumerated_as_evidence():
    final = _final("MS_B4_MECHANICAL")
    index = EvidenceIndex(final.records)
    spec = SIG.SYMPTOMS_BY_ID["COMMAND_NO_RESPONSE"]
    subject = spec.detect(index)[0]
    got = minimum_resolving_subsets(spec, index, subject, SIG.PREDICATES)
    assert got["measurable_predicates"]
    for pid in got["measurable_predicates"]:
        assert SIG.PREDICATES[pid](index, subject) is not None
    # And the ones this platform cannot measure really are excluded.
    assert "PHYSICAL_RESPONSE_NOMINAL" not in got["measurable_predicates"]


# ===================================================================== §41.6
def test_6_a_surviving_hypothesis_nobody_confirmed_is_not_a_cause():
    """§2. Presence in the candidate set is not evidence."""
    for name in sorted(MATCHED_BY_NAME):
        for loc in _loc(name):
            for h in loc.unresolved:
                assert h not in loc.supported
            if loc.verdict == SUPPORTED:
                assert len(loc.supported) == 1 and not loc.unresolved
            if loc.verdict == AMBIGUOUS:
                assert len(loc.supported) + len(loc.unresolved) > 1


def test_6b_a_lone_survivor_that_nothing_confirms_is_unsupported_not_supported():
    spec = SIG.SYMPTOMS_BY_ID["VOLTAGE_RAIL_LOW"]
    index = EvidenceIndex(())
    fake = {p: SIG.PREDICATES[p] for p in SIG.PREDICATES}
    got = localize(spec, index, "nothing", fake)
    assert got.verdict in (UNSUPPORTED, AMBIGUOUS)
    assert got.supported == ()


def test_6c_the_matched_sets_never_produce_a_supported_hypothesis_twice_over():
    """No localization may report two supported hypotheses AND call it
    SUPPORTED -- that would be a unique cause claim with a rival."""
    for name in sorted(MATCHED_BY_NAME):
        for loc in _loc(name):
            if len(loc.supported) > 1:
                assert loc.verdict == AMBIGUOUS


# ===================================================================== §41.7
def test_7_a_common_cause_is_reported_once_not_once_per_downstream_symptom():
    """§13. Two sources on one adverse rail is ONE finding."""
    locs = _loc("MS_C2_SHARED_POWER")
    assert locs
    for loc in locs:
        assert loc.supported == ("POWER/shared_node",)
        assert "SENSOR/independent_faults" not in loc.supported


def test_7b_an_uncovered_domain_is_not_evidence_of_independence():
    """The C-set finding: 'no dependency recorded here' must not read as
    'they do not share one here'."""
    final = _final("MS_C4_CPU_SATURATED_NOT_SHARED")
    index = EvidenceIndex(final.records)
    blind = SIG.uncovered_common_cause_domains(index)
    assert "COMPUTE" in blind
    assert SIG.PREDICATES["SHARED_ADVERSE_COMPUTE_DEPENDENCY"](
        index, "any") is None
    assert SIG.PREDICATES["NO_SHARED_ADVERSE_DEPENDENCY"](index, "any") is None
    for loc in _loc("MS_C4_CPU_SATURATED_NOT_SHARED"):
        assert loc.verdict == AMBIGUOUS
        assert "SENSOR/independent_faults" not in loc.supported


def test_7c_one_deadline_overrun_is_not_counted_as_two_faults():
    """§27. A segment over its own budget is that segment's fault, and
    TIMING/deadline_violation must be refuted rather than co-reported."""
    for loc in _loc("MS_D4_COMPUTE_DEADLINE"):
        rejected = dict(loc.rejected)
        assert "TIMING/deadline_violation" in rejected
        assert rejected["TIMING/deadline_violation"] == \
            "NO_TIMING_SEGMENT_OVER_BUDGET_FALSE"
        assert loc.supported == ("COMPUTE/estimator_stale",)


# ===================================================================== §41.8
def _break(engine, domain_id, mode, deadline=None):
    """Swap one registered domain for a wrapper that fails the given way."""
    victim = engine.registry.get(domain_id)
    assert victim is not None, domain_id
    engine.registry.replace(FailingDomain(victim, mode=mode, after_tick=1))
    if deadline is not None:
        engine.supervisor.statuses[domain_id].deadline_s = deadline
        engine.supervisor.emit_deadline_evidence = True
    return victim


def test_8_a_plugin_that_raises_is_failed_and_never_healthy():
    """§21 in its own words: do not catch errors and continue as healthy."""
    sc = MATCHED_BY_NAME["MS_A1_SENSOR_DELAY"]
    engine = build_engine_for(sc)
    _break(engine, "POWER", "raise")
    _e, results = _run(sc.name, ticks=6, engine=engine)
    status = results[-1].plugins["POWER"]
    assert status["state"] == FAILED
    for verdict in results[-1].functions.values():
        assert verdict.domain_states.get("POWER") != "NOMINAL"


def test_8b_a_plugin_that_says_nothing_is_not_configured_not_believed():
    sc = MATCHED_BY_NAME["MS_A1_SENSOR_DELAY"]
    engine = build_engine_for(sc)
    _break(engine, "POWER", "silent")
    _e, results = _run(sc.name, ticks=6, engine=engine)
    assert results[-1].plugins["POWER"]["state"] in (NOT_CONFIGURED, DEGRADED,
                                                     FAILED)


def test_8c_a_failed_plugin_marks_every_function_it_declared():
    sc = MATCHED_BY_NAME["MS_A1_SENSOR_DELAY"]
    engine = build_engine_for(sc)
    _break(engine, "POWER", "raise")
    _e, results = _run(sc.name, ticks=6, engine=engine)
    touched = [f for f, v in results[-1].functions.items()
               if "POWER" in v.domain_states]
    assert touched
    for f in touched:
        assert results[-1].functions[f].domain_states["POWER"] == "UNAVAILABLE"


# ===================================================================== §41.9
def test_9_a_plugin_that_overruns_its_deadline_is_reported_not_absorbed():
    """The COUNT is wall-clock and stays out of the replayable document; the
    STATE it produces is derived and belongs in it. Both halves are checked,
    because reporting neither would also 'pass' a test that only looked at
    one of them."""
    sc = MATCHED_BY_NAME["MS_A1_SENSOR_DELAY"]
    engine = build_engine_for(sc)
    _break(engine, "POWER", "hang", deadline=0.0)
    _e, results = _run(sc.name, ticks=6, engine=engine)
    assert engine.supervisor.statuses["POWER"].deadline_misses >= 1
    assert results[-1].plugins["POWER"]["state"] != AVAILABLE
    assert "deadline_misses" not in results[-1].plugins["POWER"]


def test_9b_the_watchdog_state_is_in_the_ledger_but_the_stopwatch_is_not():
    """A wall-clock reading in the replayed document would make the ledger
    non-deterministic, so the timing is observability only."""
    sc = MATCHED_BY_NAME["MS_A1_SENSOR_DELAY"]
    _e, results = _run(sc.name, ticks=4)
    for status in results[-1].plugins.values():
        assert "state" in status
        assert "last_execution_s" not in status
        assert "max_execution_s" not in status


# ==================================================================== §41.10
def test_10_the_motor_test_stand_imports_no_aircraft_stack():
    code = (
        "import sys\n"
        "from csia.v2.profiles.test_stand import build_test_stand_engine\n"
        "from csia.v2.profiles.test_stand_scenarios import "
        "TEST_STAND_SCENARIOS\n"
        "from csia.v2 import scenarios as SC\n"
        "e = build_test_stand_engine()\n"
        "SC.run(e, TEST_STAND_SCENARIOS[0], ticks=5)\n"
        "bad = [m for m in sys.modules if 'v1_1' in m or 'aircraft' in m]\n"
        "print(repr(sorted(bad)))\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=_ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


# ==================================================================== §41.11
def test_11_the_second_generic_profile_imports_no_aircraft_stack():
    code = (
        "import sys\n"
        "from csia.v2.profiles.pump_skid import (build_pump_skid_engine, "
        "PUMP_SKID_SCENARIOS)\n"
        "from csia.v2 import scenarios as SC\n"
        "e = build_pump_skid_engine()\n"
        "SC.run(e, PUMP_SKID_SCENARIOS[0], ticks=5)\n"
        "bad = [m for m in sys.modules if 'v1_1' in m or 'aircraft' in m]\n"
        "print(repr(sorted(bad)))\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=_ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


def test_11b_the_pump_skid_is_structurally_different_not_a_renamed_bench():
    """§30 asks for a SECOND STRUCTURALLY DIFFERENT profile. The thing that
    makes it different is one-of-N redundancy and a fallback requirement set,
    neither of which the bench or the aircraft has."""
    from csia.v2.profiles.pump_skid import PUMP_SKID_FUNCTIONS
    from csia.v2.profiles.test_stand import TEST_STAND_FUNCTIONS
    assert any(f.redundant_groups for f in PUMP_SKID_FUNCTIONS)
    assert any(f.fallback_requirements for f in PUMP_SKID_FUNCTIONS)
    assert not any(f.redundant_groups for f in TEST_STAND_FUNCTIONS)


# ==================================================================== §41.12
def test_12_no_profile_field_appears_in_the_framework_core():
    """Thresholds, rail names, function names and platform vocabulary live in
    the profile. §28: not in framework source."""
    core = ("attribution.py", "domain.py", "engine.py", "evidence.py",
            "functions.py", "ledger.py", "localization.py", "registry.py",
            "plugin_runtime.py", "explanation.py", "scenarios.py")
    banned = {"aircraft", "flight", "drone", "multirotor", "gnss", "imu",
              "airspeed", "altitude", "geofence", "pump", "dyno", "esc",
              "battery", "rail", "motor", "rpm", "torque", "attitude"}

    def parts(identifier):
        """`snake_case` and `CamelCase` split into WORDS.

        Substring matching is what made the first version of this test fail
        on `description` (it contains "esc"), and a test that fails on the
        wrong thing gets weakened until it passes. Words, not substrings.
        """
        out, buf = [], ""
        for ch in identifier.replace("_", " ") + " ":
            if ch.isupper() and buf and not buf[-1].isupper():
                out.append(buf)
                buf = ch
            elif ch == " ":
                if buf:
                    out.append(buf)
                buf = ""
            else:
                buf += ch
        return {w.lower() for w in out if w}

    for fname in core:
        path = os.path.join(_ROOT, "csia", "v2", fname)
        tree = ast.parse(open(path, encoding="utf-8").read())
        # Docstrings and messages may discuss the platforms; code may not
        # name them. Only identifiers are inspected.
        for node in ast.walk(tree):
            names = ()
            if isinstance(node, ast.Name):
                names = (node.id,)
            elif isinstance(node, ast.Attribute):
                names = (node.attr,)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names = (node.name,)
            elif isinstance(node, ast.arg):
                names = (node.arg,)
            for ident in names:
                hit = parts(ident) & banned
                assert not hit, f"{fname}: {ident} contains {sorted(hit)}"


# ==================================================================== §41.13
@pytest.mark.parametrize("name", ["MS_A2_COMMUNICATION_DELAY",
                                  "MS_B4_MECHANICAL",
                                  "MS_D3_COMM_STARVATION"])
def test_13_the_localization_ledger_replays_bit_for_bit(name):
    def once():
        sc = MATCHED_BY_NAME[name]
        engine, results = _run(name, ticks=30)
        led = V2AssuranceLedger(V2LedgerContext(
            profile=sc.system, software_sha="test",
            configuration_hash="test", plugin_manifest_hash="test"))
        for a in results:
            led.observe(a)
        return led

    first, second = once(), once()
    assert [e.to_dict() for e in first.events] == \
           [e.to_dict() for e in second.events]
    ok, problems = first.verify_chain()
    assert ok, problems


def test_13b_a_symptom_appearing_is_itself_a_ledger_event():
    sc = MATCHED_BY_NAME["MS_A2_COMMUNICATION_DELAY"]
    _e, results = _run(sc.name, ticks=30)
    led = V2AssuranceLedger(V2LedgerContext(
        profile=sc.system, software_sha="test", configuration_hash="test",
        plugin_manifest_hash="test"))
    for a in results:
        led.observe(a)
    loc_events = [e for e in led.events
                  if e.event_type == "LOCALIZATION_CHANGED"]
    assert loc_events
    assert loc_events[0].localization["symptom"] == "OUTPUT_STALE"


# ================================================ the signature matrix (§4)
def test_every_can_explain_cell_names_a_mechanism_and_its_evidence():
    """§4's rule. A domain that 'might be involved' with no stated mechanism
    is how a candidate set becomes a list of everything."""
    rows = SIG.matrix_rows()
    assert rows
    explaining = [r for r in rows if r["cell"] == SIG.CAN_EXPLAIN]
    assert explaining
    for r in explaining:
        assert r["mechanism"].strip(), r
        assert r["confirming_evidence"].strip(), r


def test_the_matrix_is_generated_from_the_declarations_the_runtime_uses():
    """A hand-maintained matrix drifts from behaviour and stops being
    evidence of anything. Every cell must be reachable from SYMPTOMS."""
    declared = {(s.symptom_id, h.domain)
                for s in SIG.SYMPTOMS for h in s.hypotheses}
    for r in SIG.matrix_rows():
        if r["cell"] == SIG.CAN_EXPLAIN:
            assert (r["symptom"], r["domain"]) in declared, r
    for symptom, domain in declared:
        assert any(r["symptom"] == symptom and r["domain"] == domain
                   for r in SIG.matrix_rows()), (symptom, domain)


def test_the_written_matrix_matches_the_declarations(tmp_path):
    import csv as _csv
    path = SIG.write_matrix_csv(str(tmp_path / "m.csv"))
    written = list(_csv.DictReader(open(path, encoding="utf-8")))
    assert len(written) == len(SIG.matrix_rows())


# ============================================== the explanation object (§1)
def test_the_explanation_separates_limiting_possible_and_cleared():
    engine, results = _run("MS_D1_NAV_SOURCE", ticks=30)
    explanations = explain_all(results[-1], engine.functions)
    assert explanations
    for ex in explanations:
        assert not (set(ex.limiting_domains) & set(ex.possible_domains))
        assert not (set(ex.limiting_domains) & set(ex.cleared_domains))
        if ex.state == "ELIGIBLE":
            assert not ex.limiting_domains
