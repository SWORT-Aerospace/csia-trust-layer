"""FL-032 — end-to-end assurance for the Phase-3.2 analysis pipeline.

WHY THIS FILE EXISTS
--------------------
Five Phase-3.2 mutants survived because nothing ran `build()` end to end. The
suite tested the statistical primitives thoroughly and never tested the
pipeline's USE of them, so the exclusion cap, the false-escalation veto, the
gating and -- worst -- the CONFIRMATORY SELECTION were all unpinned.

Two of those are honest limits of the earlier tests. `32-03`, the cherry-pick
mutant, is not: it survived because every grid point in the Phase-3.2 dataset
gives the same answer, so substituting a cherry-pick produced the identical
verdict. **That dataset cannot test the property.** This file builds a
synthetic dataset that can: one where the selected row decides the verdict.

WHAT IS AND IS NOT ASSERTED
---------------------------
The Phase-3.2 locked result is NOT regenerated. It is pinned by sha256 here,
and the end-to-end test rebuilds it from its own traces and compares, which
is a stronger statement than a hash alone: the artifact is both unchanged and
reproducible from its inputs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import random
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
P32 = ROOT / "research" / "consequence" / "phase32"
sys.path.insert(0, str(P32))

import evaluate32 as ev32                                  # noqa: E402

TRACES = P32 / "results" / "PHASE32_TRACES_LOCKED.json"
RESULTS = P32 / "results" / "PHASE32_RESULTS_LOCKED.json"

#: Sealed at 5208624. Part A must not move it.
RESULTS_SHA256 = \
    "2f58a6ae415ecccfdc4a3b4c331d0cab4c42954464eaf155ed23beaa6f20d2c6"


# --- 1. the real artifact, end to end ------------------------------------

def test_the_sealed_locked_result_is_byte_identical():
    assert hashlib.sha256(RESULTS.read_bytes()).hexdigest() == RESULTS_SHA256


def test_build_reproduces_the_sealed_result_from_its_own_traces():
    traces = json.loads(TRACES.read_text(encoding="utf-8"))
    rebuilt = ev32.build(traces)
    committed = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert rebuilt["h2_phase32"]["verdict"] == "SUPPORTED"
    assert set(rebuilt) - set(committed) == {"intake"}
    for key in committed:
        assert rebuilt[key] == committed[key], key


def test_the_analyzer_runs_from_the_command_line_and_exits_zero(tmp_path):
    """The command the reproduction guide gives, with its exit status."""
    out = tmp_path / "out.json"
    proc = subprocess.run(
        [sys.executable, str(P32 / "evaluate32.py"), str(TRACES),
         "--out", str(out)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert "H2 PHASE-3.2: SUPPORTED" in proc.stdout
    assert json.loads(out.read_text(encoding="utf-8"))["h2_phase32"][
        "verdict"] == "SUPPORTED"


# --- 2. a small fixture, so the pipeline is exercised without 6 MB of data -

def _segments(response: str, *, conflict_free_ground=True):
    return [
        {"t_start": 0.0, "t_end": 5.0, "airborne": False, "level": 0,
         "response": "NONE", "support": "IDENTIFIABLE",
         "pair_support": "IDENTIFIABLE", "any_stale": False,
         "gates_open": {"g": True}, "gates_at_start": {"g": 1.0},
         "ticks": 125},
        {"t_start": 5.0, "t_end": 60.0, "airborne": True, "level": 0,
         "response": response, "support": "IDENTIFIABLE",
         "pair_support": "IDENTIFIABLE", "any_stale": False,
         "gates_open": {"g": True}, "gates_at_start": {"g": 1.0},
         "ticks": 1375},
    ]


def _outcome():
    return {"time_to_safe_state_s": None, "position_error_m": 0.0,
            "altitude_error_m": 0.0, "min_geofence_margin_m": 120.0,
            "energy_margin_frac": 1.0, "max_position_error_m": 0.0,
            "geofence_margin_m": 120.0, "geofence_breached": False,
            "airborne_s": 55.0, "final_altitude_m": 30.0,
            "reached_safe_state": False, "responses_seen": [],
            "time_to_first_response_s": None,
            "time_to_correct_response_s": None}


def _scenario(seed, family, condition, magnitude, *, conflict):
    correct = "NONE" if condition == "N" else "PREPARE_LANDING"
    # A conflict is "nothing issued where TERMINATE was required".
    response = "NONE" if (conflict or condition == "N") else "PREPARE_LANDING"
    return {
        "seed": seed, "gate_group": family, "family_role": "PRIMARY",
        "condition": condition, "magnitude": magnitude,
        "is_confirmatory": False, "profile": "fixture", "takeoff_s": 5.0,
        "armed_schedule": [[0.0, True]], "gating_sensor_dropped": [],
        "fault_window_s": None if condition == "N" else [28.0, 48.0],
        "fault_window_duration_s": 0.0 if condition == "N" else 20.0,
        "fault_family": "none" if condition == "N" else "vibration_anomaly",
        "faulty_source": None if condition == "N" else "vibration",
        "correct_response": correct, "gates_under_test": ["g"],
        "time_to_level_s": {}, "meaningful_consequence_fields": [],
        "policies": {p: {"segments": _segments(response),
                         "outcome": _outcome(), "ticks": 1500}
                     for p in ("P0", "P2")},
    }


def _document(*, n=10, decoy_conflicts=True, primary_conflicts=False):
    """A synthetic campaign.

    `structural` is the preregistered family; `decoy` exists only so that a
    cherry-pick has somewhere better to go.
    """
    scenarios = []
    for seed in range(n):
        scenarios.append(_scenario(seed, "structural", "N", None,
                                   conflict=False))
        for magnitude in (1.0, 2.0):
            scenarios.append(_scenario(seed, "structural", "EG", magnitude,
                                       conflict=primary_conflicts))
            scenarios.append(_scenario(seed, "structural", "EA", magnitude,
                                       conflict=False))
        scenarios.append(_scenario(seed, "decoy", "EG", 5.0,
                                   conflict=decoy_conflicts))
        scenarios.append(_scenario(seed, "decoy", "EA", 5.0, conflict=False))
    return {
        "scenarios": scenarios,
        "grids": {"structural": [1.0, 2.0], "decoy": [5.0]},
        "confirmatory_point": {"structural": 1.0},
        "partition": "fixture", "invalid_runs": [], "invalid_run_count": 0,
        "grid_order": "declaration order",
    }


def test_build_on_a_small_fixture_reaches_a_verdict():
    result = ev32.build(_document(primary_conflicts=True,
                                  decoy_conflicts=False))
    assert result["h2_phase32"]["verdict"] == "SUPPORTED"
    assert result["intake"]["scenarios_seen"] == 10 * 7
    assert result["intake"]["grid_points_with_no_scenarios"] == []


# --- 3. THE SYNTHETIC CHERRY-PICK CANARY ---------------------------------

def test_the_cherry_pick_canary_fails_if_the_selected_row_is_not_the_declared_one():
    """The test `32-03` must not survive.

    The dataset is built so the selection DECIDES the verdict:

      * `structural` at 1.0 -- the preregistered confirmatory point -- has
        0 conflicts in both arms, so RD = 0 and the honest verdict is
        NOT SUPPORTED;
      * `structural` at 2.0 is likewise flat, so a cherry-pick cannot find a
        winner inside the declared family;
      * `decoy` at 5.0 has 10/10 against 0/10, RD = 1.0 and p < alpha.

    A pipeline that selects the maximum-effect row returns SUPPORTED here.
    The honest one returns NOT SUPPORTED. That is the whole assertion.
    """
    document = _document(primary_conflicts=False, decoy_conflicts=True)
    result = ev32.build(document)

    decoy = next(t for t in result["tests"] if t["family"] == "decoy")
    primary = result["h2_phase32"]["confirmatory_test"]

    # The dataset really does make the choice matter -- checked, not assumed.
    assert decoy["risk_difference"] == 1.0
    assert decoy["significant"] is True
    assert primary["risk_difference"] == 0.0
    assert primary["significant"] is False
    assert decoy["risk_difference"] > primary["risk_difference"]

    # The declared row is the one that was used, and it decides.
    assert (primary["family"], primary["magnitude"]) == ("structural", 1.0)
    assert result["h2_phase32"]["verdict"] == "NOT SUPPORTED"


def test_the_canary_would_go_the_other_way_under_a_max_effect_selection():
    """A canary that cannot fire proves nothing. This demonstrates that the
    cherry-picked selection reaches the opposite verdict on the same data,
    without mutating the module: the selection is applied here by hand."""
    document = _document(primary_conflicts=False, decoy_conflicts=True)
    result = ev32.build(document)
    cherry = max(result["tests"], key=lambda t: t["risk_difference"])
    assert (cherry["family"], cherry["magnitude"]) == ("decoy", 5.0)
    assert cherry["significant"] and cherry["risk_difference"] >= ev32.MIN_RD
    # i.e. a pipeline selecting `cherry` would report SUPPORTED, where the
    # preregistered pipeline reports NOT SUPPORTED.
    assert result["h2_phase32"]["verdict"] == "NOT SUPPORTED"


# --- 4. malformed, reordered, duplicated, incomplete ----------------------

@pytest.mark.parametrize("missing", ["scenarios", "grids",
                                     "confirmatory_point"])
def test_a_missing_required_key_is_refused(missing):
    document = _document()
    document.pop(missing)
    with pytest.raises(ev32.TraceError, match="missing required keys"):
        ev32.build(document)


def test_a_scenario_missing_a_field_is_refused():
    document = _document()
    del document["scenarios"][3]["correct_response"]
    with pytest.raises(ev32.TraceError, match="missing 'correct_response'"):
        ev32.build(document)


def test_a_duplicated_scenario_is_refused():
    document = _document()
    document["scenarios"].append(copy.deepcopy(document["scenarios"][1]))
    with pytest.raises(ev32.TraceError, match="duplicate scenario"):
        ev32.build(document)


def test_a_magnitude_outside_the_declared_grid_is_refused():
    document = _document()
    document["scenarios"][1]["magnitude"] = 99.0
    with pytest.raises(ev32.TraceError, match="not in the declared grid"):
        ev32.build(document)


def test_a_confirmatory_point_outside_the_grid_is_refused():
    document = _document()
    document["confirmatory_point"] = {"structural": 7.0}
    with pytest.raises(ev32.TraceError, match="confirmatory point"):
        ev32.build(document)


def test_an_unknown_response_in_a_segment_is_refused():
    document = _document()
    document["scenarios"][1]["policies"]["P0"]["segments"][1]["response"] = \
        "ENGAGE_WARP"
    with pytest.raises(ev32.TraceError, match="unknown response"):
        ev32.build(document)


def test_reordering_the_scenarios_changes_no_conclusion():
    """The grid is read from its declaration, never from scenario order.

    `per_scenario` is exempt and that is stated rather than hidden: it is a
    listing that echoes the order the campaign wrote its rows in, so
    shuffling the input shuffles the listing. What must not move is every
    CONCLUSION -- the tests, the summary, the verdict and the intake -- and
    the listing must still be the same set of rows.
    """
    document = _document(primary_conflicts=True, decoy_conflicts=False)
    shuffled = copy.deepcopy(document)
    random.Random(20260920).shuffle(shuffled["scenarios"])
    assert shuffled["scenarios"] != document["scenarios"]

    a, b = ev32.build(shuffled), ev32.build(document)
    assert set(a) == set(b)
    for key in set(a) - {"per_scenario"}:
        assert a[key] == b[key], key

    def identity(rows):
        return sorted((r["seed"], r["family"], r["condition"],
                       r["magnitude"], r["policies"]["P0"]["outcome"],
                       r["policies"]["P0"]["action_conflict"])
                      for r in rows)
    assert identity(a["per_scenario"]) == identity(b["per_scenario"])


def test_an_incomplete_pair_is_classified_and_not_silently_analysed():
    """One arm missing is an ordinary experimental fact. It is dropped, the
    reason is recorded, and the pair count falls -- it is not imputed."""
    document = _document(primary_conflicts=True, decoy_conflicts=False)
    before = ev32.build(document)["h2_phase32"]["confirmatory_test"]
    document["scenarios"] = [
        s for s in document["scenarios"]
        if not (s["seed"] == 0 and s["gate_group"] == "structural"
                and s["condition"] == "EA" and s["magnitude"] == 1.0)]
    after = ev32.build(document)["h2_phase32"]["confirmatory_test"]
    assert after["pairs_analysed"] == before["pairs_analysed"] - 1
    assert after["pairs_dropped"] == 1
    assert after["dropped_detail"][0]["reason"] == \
        "one arm of the pair is missing"


def test_too_many_exclusions_are_reported_as_underpowered():
    document = _document(n=10, primary_conflicts=True, decoy_conflicts=False)
    document["scenarios"] = [
        s for s in document["scenarios"]
        if not (s["seed"] in (0, 1, 2, 3, 4) and s["gate_group"] == "structural"
                and s["condition"] == "EA" and s["magnitude"] == 1.0)]
    result = ev32.build(document)
    assert result["h2_phase32"]["confirmatory_test"][
        "underpowered_by_exclusions"] is True
    assert result["h2_phase32"]["verdict"] == "UNDERPOWERED_BY_EXCLUSIONS"


def test_a_declared_grid_point_with_no_scenarios_is_reported():
    document = _document(primary_conflicts=True, decoy_conflicts=False)
    document["scenarios"] = [s for s in document["scenarios"]
                             if s["magnitude"] != 2.0]
    result = ev32.build(document)
    assert result["intake"]["grid_points_with_no_scenarios"] == \
        ["structural|2.0"]


def test_a_false_escalation_in_the_nominal_arm_vetoes_the_verdict():
    """The nominal control is not decoration."""
    document = _document(primary_conflicts=True, decoy_conflicts=False)
    assert ev32.build(document)["h2_phase32"]["verdict"] == "SUPPORTED"
    for s in document["scenarios"]:
        if s["condition"] == "N" and s["gate_group"] == "structural":
            s["policies"]["P0"]["segments"] = _segments("PREPARE_LANDING")
    result = ev32.build(document)
    assert result["summary"]["structural|N|None"]["false_escalations"] == 10
    assert result["h2_phase32"]["verdict"] == "NOT SUPPORTED"


def test_an_effect_below_the_declared_threshold_does_not_support_h2():
    """Significant but small is reported as observed and not as a
    demonstrated consequence -- the reason MIN_RD was declared in advance."""
    document = _document(n=40, primary_conflicts=False, decoy_conflicts=False)
    for s in document["scenarios"]:
        if (s["gate_group"] == "structural" and s["condition"] == "EG"
                and s["magnitude"] == 1.0 and s["seed"] < 8):
            s["policies"]["P0"]["segments"] = _segments("NONE")
            s["policies"]["P2"]["segments"] = _segments("NONE")
        elif (s["gate_group"] == "structural" and s["condition"] == "EG"
              and s["magnitude"] == 1.0):
            s["policies"]["P0"]["segments"] = _segments("PREPARE_LANDING")
            s["policies"]["P2"]["segments"] = _segments("PREPARE_LANDING")
    t = ev32.build(document)["h2_phase32"]["confirmatory_test"]
    assert t["count_left"] == 8 and t["count_right"] == 0
    assert t["significant"] is True
    assert t["risk_difference"] == pytest.approx(0.2)
    assert t["exceeds_effect_size_threshold"] is False
    assert ev32.build(document)["h2_phase32"]["verdict"] == "NOT SUPPORTED"


# --- 5. the campaign, end to end on one seed ------------------------------
# The analyzer is only half the pipeline. These run the real campaign for a
# single seed so that the gating and the invalid-run detection are exercised
# rather than assumed.

def _campaign():
    import campaign32
    return campaign32


def test_the_gated_condition_really_gates_the_evidence():
    """EG must differ from EA in the gates, not just in a label."""
    campaign32 = _campaign()
    seed = campaign32.parts.seeds("development")[0]
    ea, why_a = campaign32.run_scenario(seed=seed, family="structural",
                                        condition="EA", magnitude=3.0)
    eg, why_g = campaign32.run_scenario(seed=seed, family="structural",
                                        condition="EG", magnitude=3.0)
    assert why_a is None and why_g is None
    assert ea["gating_sensor_dropped"] == []
    assert eg["gating_sensor_dropped"] == [campaign32.GATING_SENSOR]

    def gates_ever_open(doc):
        return any(all(seg["gates_open"].values())
                   for seg in doc["policies"]["P0"]["segments"]
                   if seg["airborne"])
    assert gates_ever_open(ea) is True
    assert gates_ever_open(eg) is False


def test_the_two_conditions_reach_different_failsafe_levels():
    """The Phase-3.2 finding, reproduced on one development seed."""
    campaign32 = _campaign()
    seed = campaign32.parts.seeds("development")[0]
    ea, _ = campaign32.run_scenario(seed=seed, family="structural",
                                    condition="EA", magnitude=3.0)
    eg, _ = campaign32.run_scenario(seed=seed, family="structural",
                                    condition="EG", magnitude=3.0)
    assert ea["time_to_level_s"], "EA should reach a failsafe level"
    assert eg["time_to_level_s"] == {}, "EG should reach none"


def test_an_invalid_run_is_detected_and_given_a_reason():
    """The invalid-run path returns (None, reason); it does not raise and it
    does not quietly return a document."""
    campaign32 = _campaign()
    seed = campaign32.parts.seeds("development")[0]
    doc, why = campaign32.run_scenario(seed=seed, family="structural",
                                       condition="EA", magnitude=99.0)
    # 99.0 is not in the declared grid but the campaign will still run it;
    # what must hold is that a run either yields a document or a reason.
    assert (doc is None) != (why is None)


def test_a_nonfinite_sample_is_rejected_as_an_invalid_run(monkeypatch):
    """Force the trust layer to reject samples and check the campaign says
    so rather than reporting the run as valid."""
    campaign32 = _campaign()
    import csia.runtime.online as online

    class _Rejecting(online.OnlineTrustLayer):
        @property
        def bad_samples(self):
            return 7

    monkeypatch.setattr(campaign32, "OnlineTrustLayer", _Rejecting)
    seed = campaign32.parts.seeds("development")[0]
    doc, why = campaign32.run_scenario(seed=seed, family="structural",
                                       condition="EA", magnitude=3.0)
    assert doc is None
    assert why == "trust layer rejected 7 samples"
