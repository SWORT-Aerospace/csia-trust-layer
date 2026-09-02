"""Phase 3B section-23 gate: the frozen B4 constants.

Section 23 permits reusing k = 0.5, h = 500 ONLY if they remain valid under
v1.1 residual construction. These tests protect the verification and the two
facts that shape the architecture decision.
"""

from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")
VER = os.path.join(ENG, "B4_CONSTANT_VERIFICATION.json")


def _v():
    if not os.path.exists(VER):
        pytest.skip("B4 verification not built")
    return json.load(open(VER, encoding="utf-8"))


def test_the_historical_constants_are_recovered_not_reinvented():
    d = _v()
    assert d["historical_k"] == 0.5
    assert d["historical_h"] == 500.0
    assert "p1_offline_baselines.py" in d["historical_source"]


def test_the_rejected_textbook_h_stays_recorded_as_a_failure():
    """h = 5.0 failed with 4 clean-arm alarms and is a committed negative
    result. If it quietly became the selected value, the selection rule has
    been abandoned."""
    d = _v()
    assert d["historical_h_textbook_rejected"]["h"] == 5.0
    assert d["grid"]["5.0"]["satisfies_zero_clean_alarms"] is False


def test_h_500_is_still_the_smallest_h_with_zero_clean_alarms():
    """The section-23 gate itself."""
    d = _v()
    assert d["smallest_h_with_zero_clean_alarms"] == 500.0
    assert d["grid"]["500.0"]["clean_alarm_ticks"] == 0
    assert d["historical_h_still_valid"] is True
    assert d["verdict"] == "REUSABLE"


def test_h_was_selected_on_the_clean_arm_only():
    d = _v()
    rule = d["selection_rule"].lower()
    assert "clean" in rule
    assert "never on a fault" in rule
    assert d["clean_arm"] == "clean"


def test_the_rejected_invented_residual_is_not_used():
    """Section 24 names it explicitly."""
    src = open(os.path.join(ENG, "ablation", "b4_verify.py"),
               encoding="utf-8").read()
    assert "max(0.0, 1" not in src.replace(" ", "")
    d = _v()
    assert "PRE-TRANSFORM" in d["residual"]
    assert "rejected" in d["residual"]


def test_the_imu_blindness_is_recorded():
    """The finding that stops 'replace trust with the standard method'.

    B4 has no per-IMU residual, so it cannot alarm on the IMU scenarios --
    which are exactly where Phase 3A found the trust arm acting.
    """
    d = _v()
    resp = d["fault_arm_response_at_historical_h"]
    assert resp["imu0_bias_drift"] == {}, resp["imu0_bias_drift"]
    assert resp["dual_imu_failure"] == {}, resp["dual_imu_failure"]
    # and it DOES respond where it applies
    assert "gps" in resp["gps_spoof"]
    assert "mag" in resp["mag_emi"]
    assert "vibration" in resp["vibration_anomaly"]


def test_a_gnss_dropout_does_not_alarm():
    """Absence is not evidence. A gated-out sample must not enter the CUSUM."""
    d = _v()
    assert d["fault_arm_response_at_historical_h"]["gps_dropout"] == {}


def test_no_algorithmic_novelty_is_claimed():
    t = open(os.path.join(ENG, "SEQUENTIAL_DETECTOR_SPEC.md"),
             encoding="utf-8").read()
    assert "No algorithmic novelty is claimed" in t
    assert "Page's 1954" in t or "Page 1954" in t


def test_phase_3b_is_recorded_as_not_run():
    """The arm comparison T0-T4 has NOT been executed. If a later edit claims
    a sequential result without running it, this fails."""
    t = open(os.path.join(ENG, "SEQUENTIAL_DETECTOR_SPEC.md"),
             encoding="utf-8").read()
    assert "NOT RUN" in t
    a = open(os.path.join(ENG, "ARCHITECTURE_DECISION.md"),
             encoding="utf-8").read()
    assert "NOT MEASURED" in a
    assert not os.path.exists(os.path.join(ENG, "SEQUENTIAL_RESULTS.csv")), (
        "SEQUENTIAL_RESULTS.csv exists but the spec says the arms were not run")
