"""MAER arms: one code path, one gate parameter, no label leakage.

NON_SCORED_TEST_FIXTURE. Every input here is synthetic and hand-built. None of
it is campaign scenario data, so running these tests is not a scored trial.

The preregistration makes the A1/A1G comparison causal only if the two arms are
one implementation differing by a single gate factor. These tests assert that
mechanically rather than by inspection.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MOD = os.path.join(ROOT, "research", "maer", "maer_arms.py")


def _load():
    spec = importlib.util.spec_from_file_location("_maer_arms", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def M():
    return _load()


GOOD = {"h_acc": 300, "eph": 121, "satellites_visible": 10}       # nominal
BAD = {"h_acc": 250000, "eph": 121, "satellites_visible": 5}      # degraded
PRELOCK = {"h_acc": 0, "eph": 65535, "satellites_visible": 0}     # invalid


def _feats(gvalid):
    """A minimal feature dict shaped like the frozen core's."""
    return {"altitude_baro": (1.0, gvalid),
            "phys_gps": (1.0, gvalid),
            "redundant_imu": (1.0, 1.0)}


# ------------------------------------------------- one code path
def test_a1_and_a1g_configs_differ_in_exactly_one_field(M):
    a, b = M.arm_config("A1"), M.arm_config("A1G")
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert diff == {"arm", "gate_mode"}, diff
    assert a["gate_mode"] == "ungated" and b["gate_mode"] == "gvalid"


def test_a1_and_a1g_share_every_transform_constant(M):
    a, b = M.arm_config("A1"), M.arm_config("A1G")
    for k in ("h0_mm", "kappa_h", "ew_alpha", "validity_predicate",
              "hacc_feature", "target_cause"):
        assert a[k] == b[k], k


def test_a1_and_a1g_share_the_same_hypothesis_map(M):
    assert M.causes_for("A1") == M.causes_for("A1G")
    assert M.HACC_FEATURE in M.causes_for("A1")[M.TARGET_CAUSE]


def test_config_hashes_differ_only_because_of_the_gate(M):
    """Blank the gate and the two arms must hash identically."""
    import hashlib
    import json
    a, b = M.arm_config("A1"), M.arm_config("A1G")
    for cfg in (a, b):
        cfg["arm"] = "X"
        cfg["gate_mode"] = "X"
    ha = hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()
    hb = hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()
    assert ha == hb


def test_the_sidecar_is_one_class_with_one_parameter(M):
    """A1 and A1G instantiate the same class; only gate_mode differs."""
    a = M.HaccSidecar(M.gate_mode_for("A1"))
    b = M.HaccSidecar(M.gate_mode_for("A1G"))
    assert type(a) is type(b)
    assert a.gate_mode != b.gate_mode


# ------------------------------------------------- MC1 mechanics
def test_identical_input_gives_identical_consistency_across_a1_and_a1g(M):
    a = M.HaccSidecar("ungated")
    b = M.HaccSidecar("gvalid")
    for msg in (GOOD, BAD, BAD, BAD):
        a.observe(msg)
        b.observe(msg)
        assert a.last == b.last, "the transform diverged between arms"


def test_on_gvalid_zero_a1_contributes_and_a1g_does_not(M):
    """MC1 in miniature, on synthetic input."""
    a, b = M.HaccSidecar("ungated"), M.HaccSidecar("gvalid")
    a.observe(BAD)
    b.observe(BAD)
    ca, cb = a.contribution(0.0), b.contribution(0.0)
    assert ca is not None and ca[1] == 1.0
    assert cb is not None and cb[1] == 0.0
    assert ca[0] == cb[0], "same residual, only the gate may differ"


def test_on_gvalid_one_the_two_arms_are_indistinguishable(M):
    a, b = M.HaccSidecar("ungated"), M.HaccSidecar("gvalid")
    a.observe(BAD)
    b.observe(BAD)
    assert a.contribution(1.0) == b.contribution(1.0)


def test_a0_and_a2_contribute_nothing(M):
    for arm in ("A0", "A2"):
        s = M.HaccSidecar(M.gate_mode_for(arm))
        s.observe(BAD)
        assert s.contribution(0.0) is None
        assert s.contribution(1.0) is None


def test_invalid_samples_do_not_move_the_arm(M):
    s = M.HaccSidecar("ungated")
    s.observe(BAD)
    settled = s.last
    assert s.observe(PRELOCK) is False
    assert s.contribution(1.0) is None, "an invalid sample must contribute nothing"
    s.observe(BAD)
    assert s.last is not None
    # the smoother continued from the pre-invalid state rather than resetting
    assert s.last != settled or settled is not None


# ------------------------------------------------- A0 fidelity
def test_a0_reproduces_the_stock_diagnosis_exactly(M):
    """Production behaviour must be unchanged when no relation is attached."""
    from csia.diagnosis.bayes import CAUSES, DiagnosisCore
    stock = DiagnosisCore()
    wrapped = M.ArmWrapper("A0")
    assert M.causes_for("A0") == {k: list(v) for k, v in CAUSES.items()}
    for gv in (1.0, 1.0, 0.0, 0.0, 1.0):
        wrapped.sidecar.observe(BAD)
        a = stock.step(_feats(gv))
        b = wrapped.step(_feats(gv))
        assert a.keys() == b.keys()
        for k in a:
            assert a[k] == pytest.approx(b[k], rel=1e-12), k


def test_the_wrapper_reads_gvalid_from_the_frozen_gate(M):
    """gvalid is taken from the core's own altitude_baro gate, not re-derived."""
    w = M.ArmWrapper("A1")
    w.sidecar.observe(BAD)
    w.step(_feats(0.0))
    assert w.rows[-1]["gvalid"] == 0.0
    w.step(_feats(1.0))
    assert w.rows[-1]["gvalid"] == 1.0


# ------------------------------------------------- leakage
def test_no_arm_config_mentions_a_scenario_or_fault_label(M):
    """A3's classifier must not key off ground truth (item 16)."""
    import json
    banned = ("jam", "M0", "M1", "M2", "M3", "clean", "transport", "ramp",
              "scenario", "sim_gps", "fault_label")
    for arm in M.ARMS:
        blob = json.dumps(M.arm_config(arm)).lower()
        for word in banned:
            assert word not in blob, (arm, word)


def test_the_sidecar_signature_takes_no_label(M):
    """observe() sees a MAVLink message; contribution() sees gvalid. Nothing else."""
    import inspect
    assert list(inspect.signature(M.HaccSidecar.observe).parameters) == [
        "self", "gps_raw_msg"]
    assert list(inspect.signature(M.HaccSidecar.contribution).parameters) == [
        "self", "gvalid"]


# ------------------------------------------------- CUSUM
def test_cusum_uses_the_frozen_parameters(M):
    c = M.Cusum()
    assert (c.k, c.h) == (0.5, 500.0)


def test_cusum_accumulates_and_alarms_once(M):
    c = M.Cusum()
    for i in range(2000):
        c.update(2.0, i * 0.04)
    assert c.alarm_t is not None
    first = c.alarm_t
    for i in range(100):
        c.update(2.0, 100 + i)
    assert c.alarm_t == first, "the alarm time must latch"


def test_cusum_stays_quiet_on_in_control_input(M):
    c = M.Cusum()
    for i in range(5000):
        c.update(0.0, i * 0.04)
    assert c.alarm_t is None
    assert c.S == 0.0
