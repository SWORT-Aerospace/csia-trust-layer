"""Phase 3.1 — the actionability-precondition study.

The tests that matter most here are the ones that stop Phase 3.1 from
quietly rewriting Phase 3: its locked artifacts must still hash to what they
hashed at `4cc60eb`, and its headline zero must survive the span rule that
Phase 3.1 changed.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P31 = ROOT / "research" / "consequence" / "phase31"
P3 = ROOT / "research" / "consequence" / "phase3"
sys.path.insert(0, str(P31))

import evaluate31 as ev31                                  # noqa: E402

from csia_consequence import consequence_model31 as cm31    # noqa: E402
from csia_consequence import phase31_partitions as parts31  # noqa: E402

AMENDMENT = P31 / "PREREGISTRATION_PHASE31.md"


# --- Phase 3 must not move ------------------------------------------------

#: Recorded at HEAD 4cc60eb, before Phase 3.1 existed.
PHASE3_FROZEN = {
    "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json":
        "d1e911ba6d770d5afa5ab542d1fe037be8a538a9a29f0a5589a77551c27dd3e3",
    "research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json":
        "78d132988a38ad9fb16c5b85ff7f91e51df78c31b27d596469a49cfdfa238b57",
    "research/consequence/phase3/results/PHASE3_EVALUATION_LOCKED.json":
        "021959060591e91e0a68f4101ffdc5c13b17126c1475d434979314d8c34b1918",
    "research/consequence/phase3/PREREGISTRATION_PHASE3.md":
        "d3fd5dc4d8a20b0f383407e91e9c55d3f6bd737fc48352cd85206a08a142b5be",
}


@pytest.mark.parametrize("rel,want", sorted(PHASE3_FROZEN.items()))
def test_phase3_locked_artifacts_are_byte_identical(rel, want):
    got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert got == want, f"{rel} changed; Phase 3 is frozen"


def test_phase3s_headline_zero_survives_the_new_span_rule():
    """Phase 3.1 changed how a segment's duration is measured. Phase 3's
    `unsupported_confidence_scenarios = 0` must not depend on that, and this
    checks it directly rather than asserting it."""
    traces = json.loads(
        (P3 / "results" / "PHASE3_TRACES_LOCKED.json").read_text(
            encoding="utf-8"))
    hits = [(s["gate_group"], s["condition"], pol, seg["t_start"])
            for s in traces["scenarios"]
            for pol, p in s["policies"].items()
            for seg in p["segments"]
            if seg["airborne"] and seg["response"] in ev31.ATTRIBUTING
            and seg["pair_support"] != ev31.IDENTIFIABLE]
    assert hits == [], hits


def test_the_phase3_mutation_score_is_still_36_of_38():
    """36/38 with two survivors, and the survivors are not to be killed."""
    doc = json.loads(
        (ROOT / "research/bus_provenance/results/E2M_MUTATION_RESULTS.json")
        .read_text(encoding="utf-8"))
    assert doc["evaluated"] == 38
    assert doc["killed"] == 36
    assert doc["survived"] == 2
    assert sorted(r["id"] for r in doc["results"]
                  if r["verdict"] == "SURVIVED") == ["P3-03", "P3-04"]
    assert doc["kills_attributed_to_a_bare_file"] == 0
    assert doc["baseline_unmutated"]["returncode"] == 0


# --- partitions and the amendment -----------------------------------------

def test_the_phase31_partition_manifest_is_pinned():
    assert parts31.manifest_hash() == (
        "713abd66227760d954435859a7fb71d352eb1dc03b444e0fc25e0b2e252433bf")


def test_the_locked_partition_refuses_casual_access():
    with pytest.raises(PermissionError, match="locked"):
        parts31.seeds("locked")
    assert len(parts31.seeds(
        "locked", i_am_opening_the_locked_partition=True)) == 40


def test_phase31_seeds_are_disjoint_from_phase3_and_everything_earlier():
    parts31.assert_disjoint()
    parts31.assert_disjoint_from_earlier_phases()
    from csia_consequence import phase3_partitions as p3
    ours = {s for v in parts31.PARTITIONS.values() for s in v}
    theirs = {s for v in p3.PARTITIONS.values() for s in v}
    assert ours & theirs == set()


def test_the_amendment_declares_the_pooling_rule_before_execution():
    text = AMENDMENT.read_text(encoding="utf-8")
    assert "Phase-3.1 results are NOT pooled with Phase-3 results." in text
    assert "3/24" in text and "1/24" in text and "p = 0.625" in text


def test_the_amendment_states_the_seed_count_and_the_stopping_rule():
    text = AMENDMENT.read_text(encoding="utf-8")
    assert parts31.manifest_hash() in text
    assert "**40** locked" in text
    assert "No interim looks, no extension" in text
    assert "0.0881" in text and "0.1425" in text


def test_every_phase31_constant_is_declared_in_the_amendment():
    text = AMENDMENT.read_text(encoding="utf-8")
    for name in ("DRIFT_POWER_MPS", "DRIFT_STRUCT_MPS"):
        assert f"`{name}" in text or name in text, name
    assert str(ev31.MIN_STATE_S) in text
    assert "MIN_CONSEQUENCE_M" in text


# --- the span rule, which is why Phase 3.1 can measure anything -----------

def _seg(t0, t1, response, *, ticks, airborne=True, pair="IDENTIFIABLE",
         gates_open=True):
    return {"t_start": t0, "t_end": t1, "airborne": airborne, "level": 0,
            "response": response, "support": pair, "pair_support": pair,
            "any_stale": False, "gates_open": {"g": gates_open},
            "gates_at_start": {"g": 1.0 if gates_open else 0.0},
            "ticks": ticks}


def test_a_single_tick_segment_has_a_nonzero_duration():
    """Phase 3 measured `t_end - t_start`, which is zero here. The frozen
    failsafe issues each action once, so every attributing action is a
    single-tick segment and would have measured zero."""
    one = _seg(30.0, 30.0, "SELECT_IMU1", ticks=1)
    assert one["t_end"] - one["t_start"] == 0.0
    assert ev31.span_s(one) == pytest.approx(1.0 / ev31.TICK_HZ)


def test_an_attribution_issued_while_unidentifiable_is_counted():
    segments = [_seg(0.0, 5.0, "NONE", ticks=125, airborne=False),
                _seg(5.0, 29.96, "NONE", ticks=625, pair="NON_IDENTIFIABLE"),
                _seg(30.0, 30.0, "SELECT_IMU1", ticks=1,
                     pair="NON_IDENTIFIABLE"),
                _seg(30.04, 60.0, "NONE", ticks=749,
                     pair="NON_IDENTIFIABLE")]
    v = ev31.classify(segments, correct_response="SELECT_IMU1")
    assert v["unsupported_confidence_s"] > 0.0
    assert v["outcome"] == "UNSUPPORTED_CONFIDENCE"
    # The attribution was nonetheless the RIGHT unit, and both are true.
    assert "SELECT_IMU1" in v["responses_issued"]
    assert v["action_conflict"] is False


def test_the_action_conflict_criterion_is_on_classes_not_labels():
    base = [_seg(0.0, 5.0, "NONE", ticks=125, airborne=False)]
    same_class = base + [_seg(5.0, 60.0, "CONTROLLED_DESCENT", ticks=1375)]
    assert ev31.classify(same_class,
                         correct_response="PREPARE_LANDING")["action_conflict"] \
        is False
    other = base + [_seg(5.0, 60.0, "CAUTION_GENERIC", ticks=1375)]
    assert ev31.classify(other,
                         correct_response="PREPARE_LANDING")["action_conflict"] \
        is True
    nothing = base + [_seg(5.0, 60.0, "NONE", ticks=1375)]
    assert ev31.classify(nothing,
                         correct_response="PREPARE_LANDING")["action_conflict"] \
        is True


def test_a_nominal_flight_with_no_action_is_not_a_conflict():
    segments = [_seg(0.0, 5.0, "NONE", ticks=125, airborne=False),
                _seg(5.0, 60.0, "NONE", ticks=1375)]
    v = ev31.classify(segments, correct_response="NONE")
    assert v["action_conflict"] is False
    assert v["outcome"] == "CORRECT_ACTIONABLE"


def test_an_unknown_response_is_refused():
    with pytest.raises(ev31.TraceError, match="unknown response"):
        ev31.classify([_seg(0.0, 1.0, "ENGAGE_WARP", ticks=25)],
                      correct_response="NONE")


# --- statistics -----------------------------------------------------------

@pytest.mark.parametrize("k,n,lo,hi", [
    (0, 40, 0.0, 0.088097),
    (0, 24, 0.0, 0.142474),
    (12, 12, 0.735352, 1.0),
    (3, 24, 0.026559, 0.323611),
])
def test_clopper_pearson_matches_the_exact_interval(k, n, lo, hi):
    got = ev31.clopper_pearson(k, n)
    assert got[0] == pytest.approx(lo, abs=1e-5)
    assert got[1] == pytest.approx(hi, abs=1e-5)


def test_clopper_pearson_agrees_with_scipy():
    """A second derivation of the same interval. The bisection here exists so
    the evaluator keeps its no-dependency property; scipy is only the check."""
    scipy_stats = pytest.importorskip("scipy.stats")
    for k, n in [(0, 40), (1, 40), (12, 40), (40, 40), (3, 24)]:
        lo, hi = ev31.clopper_pearson(k, n)
        want_lo = 0.0 if k == 0 else scipy_stats.beta.ppf(0.025, k, n - k + 1)
        want_hi = 1.0 if k == n else scipy_stats.beta.ppf(0.975, k + 1, n - k)
        assert lo == pytest.approx(want_lo, abs=1e-5), (k, n)
        assert hi == pytest.approx(want_hi, abs=1e-5), (k, n)


def test_the_mcnemar_p_value_is_phase_3s_unchanged():
    assert ev31.mcnemar_exact(3, 1) == pytest.approx(0.625)
    assert ev31.mcnemar_exact(12, 0) == pytest.approx(2 / 4096)


# --- independence ---------------------------------------------------------

def test_the_phase31_evaluator_imports_no_csia_module():
    code = ("import sys; sys.path.insert(0, %r);"
            "import evaluate31;"
            "print(sorted(m for m in sys.modules"
            " if m.split('.')[0].startswith('csia')))" % str(P31))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


def test_the_false_refusal_definition_is_on_responses_not_on_labels():
    """The defect a development run exposed.

    Where P2 fires, P0's outcome LABEL is UNSUPPORTED_CONFIDENCE, not
    CORRECT_ACTIONABLE -- P0 names the right unit while the pair is not
    identifiable. A definition keyed on the label reported zero false
    refusals while twelve were happening.
    """
    import inspect
    src = inspect.getsource(ev31.build)
    assert 'r["correct_response"] in r["policies"]["P0"]["responses_issued"]' \
        in src
    assert 'P0"]["outcome"] == "CORRECT_ACTIONABLE"' not in src


# --- the campaign's own declarations --------------------------------------

def test_phase31_uses_no_disarmed_gate_scenario():
    source = (P31 / "campaign31.py").read_text(encoding="utf-8")
    assert '"armed": bool(a)' not in source
    assert "_merge_armed(events, [(0.0, True)])" in source
    for doc in ("PHASE31_TRACES_DEVELOPMENT.json",):
        d = json.loads((P31 / "results" / doc).read_text(encoding="utf-8"))
        assert d["uses_disarmed_gate_scenarios"] is False
        assert d["pooled_with_phase3"] is False
        for s in d["scenarios"]:
            assert s["armed_schedule"] == [[0.0, True]]


def test_the_energy_column_is_declared_not_meaningful():
    assert cm31.NOT_MEANINGFUL_ANY_FAMILY == ("energy_margin_frac",)
    assert cm31.MEANINGFUL["power_sag"] == ("time_to_safe_state_s",)
    assert cm31.MEANINGFUL["vibration_anomaly"] == ("time_to_safe_state_s",)
    assert "position_error_m" in cm31.MEANINGFUL["imu_bias"]
    assert cm31.DRIFT_POWER_MPS == 0.0
    assert cm31.DRIFT_STRUCT_MPS == 0.0


def test_phase3s_consequence_model_is_not_mutated_by_the_extension():
    """The extension installs its table for a call and restores it. If that
    leaked, Phase 3's model would silently change under it."""
    from csia_consequence import consequence_model as base
    before = dict(base.FAULT_DRIFT)
    cm31.simulate_31(
        [{"t": 0.0, "airborne": False, "response": "NONE"}],
        fault_family="power_sag", faulty_source="battery",
        correct="PREPARE_LANDING")
    assert base.FAULT_DRIFT == before
    assert "power_sag" not in base.FAULT_DRIFT
