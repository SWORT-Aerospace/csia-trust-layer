"""§36 BASELINE TEST — the v1.1 wrapper must reproduce v1.1 exactly.

    v1.1 wrapper must reproduce original v1.1 API meaning exactly.
    The plugin layer may not alter: assurance state, function eligibility,
    support, diagnosis.

WHY THIS FILE IS LONGER THAN "compare two dicts"
------------------------------------------------
Comparing outputs proves the wrapper did not alter v1.1 ON THESE PAYLOADS. It
does not prove the wrapper CANNOT. The difference matters, because the way a
wrapper silently starts altering the thing it wraps is not a wrong number — it
is someone adding a plausible-looking input six months later.

So the guarantees here are argued structurally as well as empirically:

  1. the wrapper imports no v1.1 producer, so it cannot compute a v1.1
     quantity to substitute (checked by parsing the import graph)
  2. the state map is a bijection, so nothing is lost or merged in transit
  3. per-node health carries `affected_functions = ()`, so no source reading
     can move a v1.1 function verdict
  4. the profile lists SENSOR as REQUIRED and not no-degradation, so the
     roll-up can neither soften nor harden what v1.1 said
  5. and then, empirically, the outputs match on the real payloads
"""

import ast
import json
import os

import pytest

from csia.v2.domain import Snapshot
from csia.v2.domains.navigation import _STATE, NavigationAssuranceDomain
from csia.v2.evidence import ObservationState
from csia.v2.functions import RANK
from csia.v2.profiles.aircraft import (AIRCRAFT_FUNCTIONS, V1_1_FUNCTIONS,
                                       build_aircraft_engine,
                                       build_v1_1_baseline_engine)
from csia.v2.profiles.aircraft_scenarios import load_v1_1_example

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAV = os.path.join(ROOT, "csia", "v2", "domains", "navigation.py")

#: Every real v1.1 payload committed to the repository. Real, because a
#: synthetic payload would make this whole file circular.
VARIANTS = ("clean", "fixloss")


@pytest.fixture(params=VARIANTS)
def payload(request):
    return load_v1_1_example(request.param)


def v1_1_states(payload):
    return {k: v["state"] for k, v in payload["function_eligibility"].items()}


# --------------------------------------------------------- 1. structural
def _imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            out.add(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
    return out


def test_the_wrapper_imports_no_v1_1_producer():
    """It consumes the published payload and nothing else. It cannot alter a
    v1.1 verdict because it has no way to compute one.

    Phase C moved the ingest behind `csia/v2/ingest.py`, so the check follows
    the indirection: neither module may reach a producer, and the strict
    parser must still be what the EXTERNAL path uses.
    """
    ingest = os.path.join(ROOT, "csia", "v2", "ingest.py")
    producers = ("trust_engine", "diagnosis", "eligibility", "ledger",
                 "runtime", "scenarios", "profiles", "advisory", "trust_mode")
    for path in (NAV, ingest):
        for mod in _imports(path):
            for p in producers:
                assert p not in mod, (
                    f"{os.path.basename(path)} imports {mod!r}, which reaches "
                    f"a v1.1 producer; the wrapper consumes output only")
    # The external path must still go through the strict parser, and the
    # navigation domain must reach it only through the ingest module.
    assert any("monitor" in m for m in _imports(ingest)), (
        "the external path should consume the payload through the same "
        "strict parser the external monitor uses")
    assert not any("monitor" in m for m in _imports(NAV)), (
        "the domain should not parse payloads itself; ingest owns the "
        "boundary so there is exactly one place to audit")
    # `sequential` appears in ingest only to CHECK the frozen detector
    # constants a payload declares -- it reads two module constants and
    # computes nothing, which is the opposite of using a producer.
    from csia.v2 import ingest as I
    src = open(ingest, encoding="utf-8").read()
    assert "CusumBank" not in src and "step(" not in src
    assert I.SUPPORTED_MAJOR_MINOR == ("1.1",)


def test_the_state_map_is_a_bijection():
    """Four states in, four states out, nothing merged. A many-to-one map
    would lose a distinction v1.1 makes."""
    assert len(set(_STATE.values())) == len(_STATE) == 4
    assert set(_STATE) == {"ELIGIBLE", "DEGRADED", "INELIGIBLE", "UNKNOWN"}


def test_per_source_health_can_never_move_a_v1_1_function():
    """§36's sharpest edge. A source reading attached to a v1.1 function
    could degrade a function v1.1 called eligible -- exactly the alteration
    that is forbidden -- so those records name no function at all."""
    p = load_v1_1_example("fixloss")
    result = NavigationAssuranceDomain().evaluate(
        Snapshot(t=p["timestamp"], signals={}, v1_1_payload=p))
    health = [r for r in result.records
              if r.relation == "v1_1.source_health"]
    assert health, "the wrapper should still EMIT source health as evidence"
    assert any(r.is_adverse for r in health), "fixloss has an unfresh source"
    for r in health:
        assert r.affected_functions == ()


def test_derived_v1_1_statements_are_evidence_but_not_cause_candidates():
    p = load_v1_1_example("fixloss")
    result = NavigationAssuranceDomain().evaluate(
        Snapshot(t=p["timestamp"], signals={}, v1_1_payload=p))
    for r in result.records:
        if r.relation in ("v1_1.function_eligibility", "v1_1.support",
                          "sensor.aggregate"):
            assert not r.attributable
        if r.relation == "v1_1.source_health":
            assert r.attributable


def test_the_profile_cannot_soften_or_harden_a_v1_1_verdict():
    """A SUPPORTING domain's INELIGIBLE is softened to DEGRADED, and a
    no-degradation domain's DEGRADED is hardened to INELIGIBLE. Either would
    be an alteration, so SENSOR must be REQUIRED and must not be listed as
    no-degradation on any v1.1-named function."""
    for fn in AIRCRAFT_FUNCTIONS:
        if fn.name not in V1_1_FUNCTIONS:
            continue
        assert "SENSOR" in fn.required_domains, fn.name
        assert "SENSOR" not in fn.supporting_domains, fn.name
        assert "SENSOR" not in fn.no_degradation_domains, fn.name


def test_precision_landing_stays_omitted_because_v1_1_omitted_it():
    """v1.1 declined to specify it for want of a landing reference; v2 adds
    power, compute, timing, communication and actuation, and no landing
    reference. Listing it would reinstate a function nobody can evaluate."""
    assert "PRECISION_LANDING" not in V1_1_FUNCTIONS
    assert "PRECISION_LANDING" not in {f.name for f in AIRCRAFT_FUNCTIONS}
    req = json.load(open(os.path.join(
        ROOT, "engineering", "v1_1", "csia_output_example.json"),
        encoding="utf-8"))
    assert "PRECISION_LANDING" not in req["function_eligibility"]


# --------------------------------------------------------- 2. empirical
def test_the_baseline_engine_reproduces_v1_1_eligibility_exactly(payload):
    """With only the SENSOR domain registered, a v2 function's only evidence
    is the v1.1 verdict. Any difference is an alteration by the plugin layer,
    because there is nowhere else it could have come from."""
    engine = build_v1_1_baseline_engine()
    result = engine.evaluate(Snapshot(t=payload["timestamp"], signals={},
                                      v1_1_payload=payload))
    got = {k: v.state for k, v in result.functions.items()}
    assert got == v1_1_states(payload)


def test_the_sensor_domain_state_is_the_v1_1_verdict_in_the_full_profile(
        payload):
    """§17 wants a v2 function to be limited by TIMING or COMPUTE. §36 wants
    v1.1's verdict intact. Both hold because they are different statements,
    and `domain_states["SENSOR"]` is where v1.1's survives untouched."""
    inverse = {v.value: k for k, v in _STATE.items()}
    engine = build_aircraft_engine()
    result = engine.evaluate(Snapshot(
        t=payload["timestamp"],
        signals=_nominal_but_broken_everywhere_else(),
        v1_1_payload=payload))
    for name, state in v1_1_states(payload).items():
        verdict = result.functions[name]
        assert inverse[verdict.domain_states["SENSOR"]] == state, (
            f"{name}: the SENSOR column must still read exactly what v1.1 "
            f"said, whatever else is failing")


def test_adding_domains_can_only_restrict_a_function_never_relax_it(payload):
    """Monotonicity. v2 must never call something eligible that v1.1 called
    ineligible: with the worst-state roll-up and an order-preserving map it
    structurally cannot, and this checks the profile has not broken that."""
    base = build_v1_1_baseline_engine().evaluate(
        Snapshot(t=payload["timestamp"], signals={}, v1_1_payload=payload))
    full = build_aircraft_engine().evaluate(Snapshot(
        t=payload["timestamp"], signals=_nominal_but_broken_everywhere_else(),
        v1_1_payload=payload))
    for name in V1_1_FUNCTIONS:
        assert RANK[full.functions[name].state] >= \
            RANK[base.functions[name].state], name


def test_the_support_and_diagnosis_are_transcribed_not_recomputed(payload):
    result = NavigationAssuranceDomain().evaluate(
        Snapshot(t=payload["timestamp"], signals={}, v1_1_payload=payload))
    diag = [r for r in result.records if r.relation == "v1_1.support"][0]
    assert diag.detail["leader"] == payload["diagnosis"]["leader"]
    assert diag.detail["support_state"] == payload["diagnosis"]["support_state"]
    assert diag.detail["ambiguity"] == payload["diagnosis"]["ambiguity"]
    assert diag.measured_value == pytest.approx(
        payload["diagnosis"]["posterior"])


def test_a_missing_payload_is_unavailable_not_healthy():
    result = NavigationAssuranceDomain().evaluate(Snapshot(t=0.0, signals={}))
    assert result.records[0].observation_state is ObservationState.UNAVAILABLE
    assert "V1_1_PAYLOAD_MISSING" in result.records[0].reason_codes


def test_a_payload_from_another_schema_is_refused_not_reinterpreted():
    """§16's strictness is inherited: the wrapper uses the same parser, so a
    version it does not understand is refused rather than coerced."""
    bad = dict(load_v1_1_example("clean"), schema_version="9.9.9")
    result = NavigationAssuranceDomain().evaluate(
        Snapshot(t=0.0, signals={}, v1_1_payload=bad))
    assert result.records[0].observation_state is ObservationState.UNAVAILABLE
    assert "V1_1_PAYLOAD_REJECTED" in result.records[0].reason_codes
    assert result.unevaluated


def _nominal_but_broken_everywhere_else():
    """Every non-SENSOR domain in its worst state, so the test above is a
    real test: if anything outside v1.1 could reach the SENSOR column, this
    is the input that would show it."""
    return {
        "POWER": {"battery": {}, "rail_5v": {}, "rail_3v3": {}},
        "COMPUTE": {"state_estimator": {"alive": False}, "csia": {},
                    "logger": {}, "cpu": {"cpu_load": 1.0}},
        "TIMING": {}, "COMMUNICATION": {}, "ACTUATION": {},
    }
