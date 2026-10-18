"""Phase 3 — closed-loop consequence measurement.

Three groups of test, and the third is the one that matters most.

1. The seed partitions and the preregistered constants, pinned so a later
   edit cannot quietly retune the experiment.
2. The policy boundary: P2 emits a typed support value and nothing else, and
   exactly one function in the codebase turns that into a response.
3. The independent evaluator, against hand-built traces with a known correct
   classification -- one for EVERY outcome class. An evaluator that bucketed
   everything the same way would pass a happy-path test and fail these.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASE3 = ROOT / "research" / "consequence" / "phase3"
sys.path.insert(0, str(PHASE3))

import independent_consequence_evaluator as ice        # noqa: E402

from csia_consequence import action_adapter as aa      # noqa: E402
from csia_consequence import consequence_model as cm   # noqa: E402
from csia_consequence import phase3_partitions as parts  # noqa: E402
from csia_consequence import support as production_support  # noqa: E402

PREREG = PHASE3 / "PREREGISTRATION_PHASE3.md"


# --- 1. partitions and preregistered constants ----------------------------

def test_the_phase3_partition_manifest_is_pinned():
    assert parts.manifest_hash() == (
        "6fda17fac860a55cff5434af41e0c5f60045a7014ece1583951db06a871c8ecf")


def test_the_locked_partition_refuses_casual_access():
    with pytest.raises(PermissionError, match="locked"):
        parts.seeds("locked")
    assert len(parts.seeds(
        "locked", i_am_opening_the_locked_partition=True)) == 24


def test_phase3_seeds_are_disjoint_from_every_earlier_partition():
    parts.assert_disjoint()
    parts.assert_disjoint_from_earlier_phases()


def test_every_model_constant_is_stated_in_the_preregistration():
    """The numbers that decide the outcome must be the numbers that were
    declared before the locked partition was opened. A drift between the two
    is exactly the failure this check exists for."""
    text = PREREG.read_text(encoding="utf-8")
    for name, value in sorted(cm.CONSTANTS.items()):
        row = re.search(rf"`{re.escape(name)}`\s*\|\s*([0-9.]+)", text)
        assert row, f"{name} is not in the preregistration's constant table"
        assert float(row.group(1)) == pytest.approx(value), (
            name, row.group(1), value)


def test_the_preregistration_declares_the_partition_hash_it_used():
    assert parts.manifest_hash() in PREREG.read_text(encoding="utf-8")


# --- 2. the policy boundary -----------------------------------------------

def test_the_decision_pair_is_separated_only_by_the_armed_gated_features():
    """The whole Phase-3 prediction, checked against the frozen core rather
    than restated from it."""
    a, b = aa.DECISION_PAIR
    assert aa.LOW_SETS[a] ^ aa.LOW_SETS[b] == {"accel_motor_current",
                                               "accel_esc_rpm"}
    assert "redundant_imu" in aa.LOW_SETS[a] & aa.LOW_SETS[b]


def test_the_low_sets_are_the_frozen_cores_and_not_a_copy():
    from csia.diagnosis.causal import SOURCE_INDICATORS
    assert set(aa.LOW_SETS) == set(SOURCE_INDICATORS)
    for source, features in SOURCE_INDICATORS.items():
        assert aa.LOW_SETS[source] == frozenset(features)


def test_p2_holds_no_actuator_authority():
    assert aa.HAS_ACTUATOR_AUTHORITY is False
    assert production_support.SupportReport.HAS_ACTUATOR_AUTHORITY is False


def test_only_one_function_turns_support_into_a_response():
    """Structural, not stylistic. If a second place learns to name a response
    from a support value, P2 has grown an action path."""
    import inspect
    source = inspect.getsource(aa)
    namers = [name for name in ("adapt", "p0_decide", "p1_decide",
                                "p2_support", "decision_pair_support")
              if re.search(rf"def {name}\b", source)]
    assert set(namers) == {"adapt", "p0_decide", "p1_decide", "p2_support",
                           "decision_pair_support"}
    p2 = inspect.getsource(aa.p2_support) + inspect.getsource(
        aa.decision_pair_support)
    for response in aa.RESPONSES:
        assert response not in p2, (
            f"p2_support can name {response}; it must emit a typed support "
            f"value only")


class _Report:
    def __init__(self, status, reason="R"):
        self.status = status
        self.reason = reason


class _State:
    t = 20.0
    edges = {}
    fresh = {}


class _Action:
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}


@pytest.mark.parametrize("support_state,expected", [
    ("IDENTIFIABLE", aa.R_SELECT_IMU0),
    ("AMBIGUOUS", aa.R_ABSTAIN),
    ("NON_IDENTIFIABLE", aa.R_ABSTAIN),
])
def test_the_adapter_withdraws_an_attribution_only_when_unsupported(
        support_state, expected):
    actions = [_Action("SELECT_IMU", {"use": "imu0"})]
    decision = aa.adapt(_State(), 1, actions, _Report("IDENTIFIABLE"),
                        _Report(support_state))
    assert decision.response == expected


@pytest.mark.parametrize("support_state", ["AMBIGUOUS", "NON_IDENTIFIABLE"])
def test_the_adapter_never_withdraws_a_response_that_asserts_no_attribution(
        support_state):
    """Withdrawing a controlled descent because attribution is ambiguous
    would be a false refusal with a real cost. The adapter must not."""
    actions = [_Action("CONTROLLED_DESCENT", {"rate_mps": 1.5})]
    decision = aa.adapt(_State(), 3, actions, _Report("IDENTIFIABLE"),
                        _Report(support_state))
    assert decision.response == aa.R_CONTROLLED_DESCENT


def test_an_unknown_response_is_refused_at_construction():
    with pytest.raises(ValueError, match="unknown response"):
        aa.Decision("DO_A_BARREL_ROLL", 0, None, None, "")


# --- the consequence model ------------------------------------------------

def _ticks(response, *, n=1200, takeoff=5.0, switch_at=12.0):
    return [{"t": i * 0.04, "airborne": i * 0.04 >= takeoff,
             "response": response if i * 0.04 >= switch_at else aa.R_NONE}
            for i in range(n)]


def test_choosing_the_faulty_unit_is_worse_than_choosing_nothing():
    """The assumption H2's falsifiability rests on, checked as arithmetic."""
    nothing = cm.simulate(_ticks(aa.R_NONE), fault_family="imu_bias",
                          faulty_source="imu0", correct=aa.R_SELECT_IMU1)
    wrong = cm.simulate(_ticks(aa.R_SELECT_IMU0), fault_family="imu_bias",
                        faulty_source="imu0", correct=aa.R_SELECT_IMU1)
    right = cm.simulate(_ticks(aa.R_SELECT_IMU1), fault_family="imu_bias",
                        faulty_source="imu0", correct=aa.R_SELECT_IMU1)
    assert right.position_error_m < nothing.position_error_m
    assert wrong.position_error_m > nothing.position_error_m


def test_a_grounded_vehicle_accrues_no_position_error():
    ticks = [{"t": i * 0.04, "airborne": False, "response": aa.R_NONE}
             for i in range(500)]
    out = cm.simulate(ticks, fault_family="imu_bias", faulty_source="imu0",
                      correct=aa.R_SELECT_IMU1)
    assert out.position_error_m == 0.0
    assert out.airborne_s == 0.0


def test_the_correct_response_under_latent_truth_is_ground_truth_not_policy():
    assert cm.correct_response("imu_bias", "imu0") == aa.R_SELECT_IMU1
    assert cm.correct_response("imu_bias", "imu1") == aa.R_SELECT_IMU0
    assert cm.correct_response("dual_imu_bias", None) == aa.R_CONTROLLED_DESCENT
    assert cm.correct_response("none", None) == aa.R_NONE
    with pytest.raises(ValueError, match="no declared correct response"):
        cm.correct_response("gremlins", None)


# --- 3. the independent evaluator -----------------------------------------

def test_the_evaluator_imports_nothing_from_csia():
    code = (
        "import sys; sys.path.insert(0, %r);"
        "import independent_consequence_evaluator;"
        "print(sorted(m for m in sys.modules"
        " if m.split('.')[0].startswith('csia')))" % str(PHASE3))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


def _seg(t0, t1, response, *, airborne=True, pair="IDENTIFIABLE",
         gates_open=True, level=0):
    return {"t_start": t0, "t_end": t1, "airborne": airborne, "level": level,
            "response": response, "support": pair, "pair_support": pair,
            "any_stale": False, "gates_open": {"g": gates_open},
            "gates_at_start": {"g": 1.0 if gates_open else 0.0}, "ticks": 1}


#: One hand-built trace per outcome class, with the classification a human
#: would give it. An evaluator that always answered the same way fails here.
CONTROLS = [
    ("positive: the correct attribution is issued",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "SELECT_IMU1")],
     "SELECT_IMU1", ice.CORRECT_ACTIONABLE),
    ("positive: the FAULTY unit is selected, with support present",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "SELECT_IMU0")],
     "SELECT_IMU1", ice.INCORRECT_ACTIONABLE),
    ("positive: an attribution issued while the pair is not identifiable",
     [_seg(0, 5, "NONE", airborne=False),
      _seg(5, 60, "SELECT_IMU1", pair="NON_IDENTIFIABLE", gates_open=False)],
     "SELECT_IMU1", ice.UNSUPPORTED_CONFIDENCE),
    ("positive: an explicit abstention",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "ABSTAIN")],
     "SELECT_IMU1", ice.ABSTENTION),
    ("positive: a conservative response short of the correct one",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "CAUTION_GENERIC")],
     "SELECT_IMU1", ice.SAFE_FALLBACK),
    ("positive: nothing issued while a fault demanded a response",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "NONE")],
     "SELECT_IMU1", ice.MISSED_ESCALATION),
    ("positive: an escalation on a nominal flight",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "CONTROLLED_DESCENT")],
     "NONE", ice.FALSE_ESCALATION),
    ("negative: a nominal flight with nothing issued",
     [_seg(0, 5, "NONE", airborne=False), _seg(5, 60, "NONE")],
     "NONE", ice.CORRECT_ACTIONABLE),
]


@pytest.mark.parametrize("label,segments,correct,expected",
                         CONTROLS, ids=[c[0] for c in CONTROLS])
def test_the_evaluator_on_hand_built_controls(label, segments, correct,
                                              expected):
    assert ice.classify(segments, correct_response=correct)["outcome"] == \
        expected, label


def test_every_outcome_class_has_a_control():
    covered = {expected for _l, _s, _c, expected in CONTROLS}
    assert covered == set(ice.OUTCOME_CLASSES), \
        sorted(set(ice.OUTCOME_CLASSES) - covered)


def test_materiality_is_about_response_class_not_about_the_model():
    assert ice.materially_different("SELECT_IMU0", "SELECT_IMU1")
    assert ice.materially_different("NONE", "CAUTION_GENERIC")
    assert not ice.materially_different("CAUTION_GENERIC", "ABSTAIN")
    assert not ice.materially_different("PREPARE_LANDING",
                                        "CONTROLLED_DESCENT")


def test_a_response_the_evaluator_was_not_told_about_is_refused():
    with pytest.raises(ice.TraceError, match="unknown response"):
        ice.classify([_seg(0, 10, "ENGAGE_WARP")],
                     correct_response="SELECT_IMU1")


def test_occlusion_overlap_counts_only_airborne_closed_time():
    segments = [_seg(0, 5, "NONE", airborne=False, gates_open=False),
                _seg(5, 20, "NONE", gates_open=False),
                _seg(20, 60, "NONE", gates_open=True)]
    assert ice.occlusion_overlap_s(segments) == 15.0


def test_the_evaluator_agrees_with_the_campaigns_own_response_vocabulary():
    """If the campaign grows a response the evaluator cannot class, the
    campaign is emitting something nobody has decided the meaning of."""
    assert set(ice.RESPONSE_CLASS) == set(aa.RESPONSES)


def test_occlusion_during_a_fault_is_not_occlusion_over_a_whole_flight():
    """The distinction that a development-phase confound forced.

    A hovering vehicle keeps its speed gate shut for most of a mission, so two
    conditions can match on total airborne occlusion and differ completely on
    whether the gate was shut WHEN THE FAULT WAS RUNNING.
    """
    segments = [_seg(0, 5, "NONE", airborne=False, gates_open=False),
                _seg(5, 20, "NONE", gates_open=False),
                _seg(20, 40, "NONE", gates_open=True),
                _seg(40, 60, "NONE", gates_open=False)]
    assert ice.occlusion_overlap_s(segments) == 35.0
    assert ice.occlusion_during_fault_s(segments, [25.0, 30.0]) == 0.0
    assert ice.occlusion_during_fault_s(segments, [45.0, 50.0]) == 5.0
    assert ice.occlusion_during_fault_s(segments, [10.0, 30.0]) == 10.0
    assert ice.occlusion_during_fault_s(segments, None) == 0.0


# --- 4. the analysis, where the p-value decides the verdict ---------------

import analyze as an                                     # noqa: E402


@pytest.mark.parametrize("b,c,expected", [
    (0, 0, 1.0),
    (1, 1, 1.0),
    (3, 1, 0.625),        # the locked heading_course F-vs-G pair
    (5, 0, 0.0625),       # the classic near-miss: NOT significant at 0.05
    (6, 0, 0.03125),
    (10, 0, 0.001953125),
])
def test_the_exact_mcnemar_p_value(b, c, expected):
    """Pinned to exact values, because this number decides H2.

    A one-sided version, or an off-by-one in the tail, would move 3-versus-1
    from p=0.625 to something that could be mistaken for a finding.
    """
    assert an.mcnemar_exact(b, c) == pytest.approx(expected)


def test_the_mcnemar_p_value_matches_a_direct_enumeration():
    """Independent of the formula: enumerate the binomial outright."""
    import itertools
    for b, c in [(3, 1), (4, 2), (2, 5), (0, 3)]:
        n = b + c
        k = min(b, c)
        outcomes = list(itertools.product([0, 1], repeat=n))
        extreme = sum(1 for o in outcomes
                      if min(sum(o), n - sum(o)) <= k)
        assert an.mcnemar_exact(b, c) == pytest.approx(
            min(1.0, extreme / len(outcomes)))


def test_mcnemar_is_symmetric_in_its_arguments():
    for b, c in [(3, 1), (7, 2), (0, 5)]:
        assert an.mcnemar_exact(b, c) == an.mcnemar_exact(c, b)


def _fake_evaluation(outcomes_by_condition, *, group="heading_course"):
    """A minimal evaluation document with hand-chosen outcomes."""
    rows = []
    for seed, per_condition in enumerate(zip(*outcomes_by_condition.values())):
        for condition, outcome in zip(outcomes_by_condition, per_condition):
            rows.append({
                "seed": 1000 + seed, "gate_group": group,
                "condition": condition, "correct_response": "CAUTION_GENERIC",
                "policies": {p: {
                    "outcome": outcome, "responses_issued": [],
                    "first_response_s": None, "correct_response_s": None,
                    "unsupported_confidence_s": 0.0, "ambiguity_s": 0.0,
                    "abstention_s": 0.0, "idle_while_fault_s": 0.0,
                    "airborne_s": 55.0, "coverage_loss_frac": 0.0,
                    "materially_different_from_correct": [],
                    "occlusion_overlap_s": 0.0,
                    "occlusion_during_fault_s": 4.0 if condition == "F" else 0.0,
                    "fault_window_s": [45.5, 49.5],
                    "time_to_safe_state_s": None, "position_error_m": 0.0,
                    "min_geofence_margin_m": 120.0,
                    "energy_margin_frac": 1.0,
                } for p in ("P0", "P1", "P2")},
            })
    return {"per_scenario": rows, "by_policy": {
        p: {"scenarios": len(rows), "by_outcome": {},
            "incorrect_actionable": 0, "correct_actionable": 0,
            "abstentions": 0, "ambiguous_outputs": 0, "safe_fallbacks": 0,
            "false_escalations": 0, "missed_escalations": 0,
            "unsupported_confidence_scenarios": 0, "total_ambiguity_s": 0.0,
            "total_abstention_s": 0.0, "total_position_error_m": 0.0,
            "mean_coverage_loss_frac": 0.0, "mean_position_error_m": 0.0,
            "safe_state_reached": 0}
        for p in ("P0", "P1", "P2")}}


def test_the_paired_test_is_paired_and_not_two_proportions():
    """Same marginal counts, different pairing, different answer.

    Both cases below have 3 misses under F and 1 under G. In the first the
    misses are on different seeds; in the second G's miss is on a seed F also
    missed. An unpaired comparison cannot tell them apart. This one must.
    """
    ok = "CORRECT_ACTIONABLE"
    miss = ice.MISSED_ESCALATION
    disjoint = _fake_evaluation({
        "F": [miss, miss, miss, ok, ok, ok],
        "G": [ok, ok, ok, miss, ok, ok]})
    nested = _fake_evaluation({
        "F": [miss, miss, miss, ok, ok, ok],
        "G": [miss, ok, ok, ok, ok, ok]})
    a = an.paired_condition_test(disjoint, group="heading_course",
                                 policy="P0", left="F", right="G")
    b = an.paired_condition_test(nested, group="heading_course",
                                 policy="P0", left="F", right="G")
    assert a["missed_left"] == b["missed_left"] == 3
    assert a["missed_right"] == b["missed_right"] == 1
    assert (a["discordant_left_only"], a["discordant_right_only"]) == (3, 1)
    assert (b["discordant_left_only"], b["discordant_right_only"]) == (2, 0)
    assert a["mcnemar_exact_two_sided_p"] != b["mcnemar_exact_two_sided_p"]


def test_h2_is_not_supported_without_an_attributable_difference():
    """A conflict that the matched control also produces is not a finding."""
    ok = "CORRECT_ACTIONABLE"
    miss = ice.MISSED_ESCALATION
    evaluation = _fake_evaluation({
        "F": [miss, ok, ok, ok], "G": [ok, ok, ok, ok]})
    tests = [an.paired_condition_test(evaluation, group="heading_course",
                                      policy="P0", left="F", right="G")]
    verdict = an.verdicts(evaluation, tests, {})["H2"]
    assert verdict["decision_conflicts_total"] == 1
    assert verdict["verdict"] == "NOT SUPPORTED"
    assert "attributable" in verdict["why"].lower()


def test_h2_is_supported_when_the_paired_control_separates_them():
    """The other direction, so the verdict is not a constant."""
    ok = "CORRECT_ACTIONABLE"
    miss = ice.MISSED_ESCALATION
    evaluation = _fake_evaluation({
        "F": [miss] * 8 + [ok] * 2, "G": [ok] * 10})
    tests = [an.paired_condition_test(evaluation, group="heading_course",
                                      policy="P0", left="F", right="G")]
    assert tests[0]["distinguishable_from_chance"] is True
    assert an.verdicts(evaluation, tests, {})["H2"]["verdict"] == "SUPPORTED"


def test_a_conflict_only_in_the_physically_inconsistent_control_does_not_count():
    ok = "CORRECT_ACTIONABLE"
    miss = ice.MISSED_ESCALATION
    evaluation = _fake_evaluation({"F": [miss] * 6, "G": [ok] * 6},
                                  group="armed_gate_pair")
    tests = [an.paired_condition_test(evaluation, group="armed_gate_pair",
                                      policy="P0", left="F", right="G")]
    verdict = an.verdicts(evaluation, tests, {})["H2"]
    assert verdict["decision_conflicts_total"] == 6
    assert verdict["decision_conflicts_in_physically_consistent_conditions"] == 0
    assert verdict["verdict"] == "NOT SUPPORTED"


def test_the_locked_results_artifact_is_what_the_analyzer_produces():
    """No number in the write-up may be typed by hand."""
    results = json.loads(
        (PHASE3 / "results" / "PHASE3_RESULTS_LOCKED.json").read_text(
            encoding="utf-8"))
    evaluation = json.loads(
        (PHASE3 / "results" / "PHASE3_EVALUATION_LOCKED.json").read_text(
            encoding="utf-8"))
    assert an.build(evaluation) == results


def test_the_locked_run_declares_it_executed_nothing():
    traces = json.loads(
        (PHASE3 / "results" / "PHASE3_TRACES_LOCKED.json").read_text(
            encoding="utf-8"))
    assert traces["executed_an_autopilot"] is False
    assert traces["armed_a_vehicle"] is False
    assert traces["touched_hardware"] is False
    assert traces["evidence_level"] == "MODEL_BASED_ACTION_CONSEQUENCE"
    assert traces["partition"] == "locked"
    assert len(traces["seeds"]) == 24


# --- 5. the write-up may not drift from the artifact ----------------------

RESULTS_MD = PHASE3 / "PHASE3_RESULTS.md"
MANIFEST = PHASE3 / "SHA256_MANIFEST.json"


def test_the_write_up_quotes_the_artifacts_numbers():
    """Every figure the results document states, re-derived and matched.

    Prose drifts from artifacts silently. This is the only thing that stops
    it: the document must still be true of the JSON it was written from.
    """
    text = RESULTS_MD.read_text(encoding="utf-8")
    results = json.loads(
        (PHASE3 / "results" / "PHASE3_RESULTS_LOCKED.json").read_text(
            encoding="utf-8"))
    fvg = next(t for t in results["paired_tests"]
               if t["group"] == "heading_course"
               and t["left_condition"] == "F")
    p0 = results["policy_table"]["P0"]

    for quoted in (
        f"p = {fvg['mcnemar_exact_two_sided_p']}",
        f"{fvg['missed_left']} / {fvg['pairs']}",
        f"{fvg['missed_right']} / {fvg['pairs']}",
        f"{p0['scenarios']} locked scenarios",
        f"| correct actionable | {p0['correct_actionable']} |",
        f"| missed escalations | {p0['missed_escalations']} |",
    ):
        assert quoted in text, quoted

    assert results["hypotheses"]["H2"]["verdict"] == "NOT SUPPORTED"
    assert results["hypotheses"]["H3"]["verdict"] == "NOT SUPPORTED"
    assert "## H2 RESULT — **NOT SUPPORTED**" in text
    assert "## H3 RESULT — **NOT SUPPORTED**" in text


def test_the_write_up_claims_no_level_above_the_one_measured():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert "`MODEL_BASED_ACTION_CONSEQUENCE`" in text
    for forbidden in ("SITL_CLOSED_LOOP_EXECUTION`.", "HIL_EXECUTION`.",
                      "flight-validated", "hardware-validated"):
        assert forbidden not in text, forbidden
    for denial in ("Nothing flew.", "No autopilot executed anything.",
                   "not a safety guarantee"):
        assert denial.lower() in text.lower(), denial


def test_the_manifest_matches_every_file_it_lists():
    import hashlib
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = []
    for rel, want in manifest["files"].items():
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        if got != want:
            bad.append(rel)
    assert bad == [], bad
    assert manifest["frozen_core"]["mismatches"] == []
    assert manifest["frozen_core"]["files_checked"] == 12


def test_the_manifest_covers_the_artifacts_the_write_up_depends_on():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for required in (
            "research/consequence/phase3/PREREGISTRATION_PHASE3.md",
            "research/consequence/phase3/PHASE3_RESULTS.md",
            "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json",
            "research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json",
            "research/consequence/phase3/analyze.py",
            "research/consequence/phase3/independent_consequence_evaluator.py",
            "csia_consequence/consequence_model.py"):
        assert required in manifest["files"], required
