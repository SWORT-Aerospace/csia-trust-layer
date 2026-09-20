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
