"""Dual-channel admissibility: the arms are what they claim to be.

NON_SCORED_TEST_FIXTURE. Synthetic inputs and static source reads only; no
simulator is launched and no campaign scenario is replayed here.

The claims these tests exist to protect are all of the form "the comparison is
causal because the arms differ in exactly one thing". That is not something to
assert in prose.
"""

from __future__ import annotations

import importlib.util
import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "dual_admissibility")
RES = os.path.join(PKG, "results")


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PKG, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def A():
    return _load("_dual_arms", "dual_arms.py")


GOOD = {"fix_type": 6, "h_acc": 300, "eph": 121, "satellites_visible": 10}
DEGRADED = {"fix_type": 6, "h_acc": 250000, "eph": 121,
            "satellites_visible": 8}
NOFIX = {"fix_type": 1, "h_acc": 0, "eph": 65535, "satellites_visible": 0}


def _feats(a_gps):
    return {"phys_gps": (1.0, a_gps),
            "altitude_baro": (1.0, a_gps),
            "redundant_imu": (1.0, 1.0)}


# ---------------------------------------------- frozen core untouched
def test_the_frozen_core_is_not_modified():
    """The v1 freeze guard is the real check; this asserts the intent."""
    import subprocess
    r = subprocess.run(
        ["git", "diff", "--stat", "csia/trust_engine", "csia/diagnosis",
         "csia/runtime/online.py", "csia/runtime/failsafe.py"],
        capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0
    assert r.stdout.strip() == "", r.stdout


def test_no_arm_touches_the_production_diagnosis_defaults(A):
    from csia.diagnosis.bayes import CAUSES
    stock = {k: list(v) for k, v in CAUSES.items()}
    for arm in A.ARMS:
        A.causes_for(arm)
    assert {k: list(v) for k, v in CAUSES.items()} == stock


# ---------------------------------------------- one-factor arms
@pytest.mark.parametrize("split,coupled",
                         [("S2a", "S1Da"), ("S2b", "S1Db"), ("S2c", "S1D")])
def test_each_split_arm_differs_from_its_control_in_exactly_one_field(
        A, split, coupled):
    a, b = A.arm_config(split), A.arm_config(coupled)
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert diff == {"arm", "d_coupled_to_a"}, diff
    assert a["d_coupled_to_a"] is False and b["d_coupled_to_a"] is True


@pytest.mark.parametrize("split,coupled",
                         [("S2a", "S1Da"), ("S2b", "S1Db"), ("S2c", "S1D")])
def test_matched_arms_carry_identical_hypothesis_maps(A, split, coupled):
    assert A.causes_for(split) == A.causes_for(coupled)


def test_s0_and_s1_add_no_features_at_all(A):
    from csia.diagnosis.bayes import CAUSES
    for arm in ("S0", "S1"):
        assert A.causes_for(arm) == {k: list(v) for k, v in CAUSES.items()}


def test_s0_and_s1_differ_only_in_the_adapter_policy(A):
    a, b = A.arm_config("S0"), A.arm_config("S1")
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert diff == {"arm", "adapter_policy"}


# ---------------------------------------------- value vs status
def test_no_arm_can_make_an_invalid_navigation_value_admissible(A):
    """Item 14. The arms may add STATUS features; none may add a value one."""
    for arm in A.ARMS:
        added = set(A.causes_for(arm)["gps_fault"]) - {"phys_gps"}
        assert added <= {A.STATUS_FEATURE, A.HACC_FEATURE}, (arm, added)


def test_the_adapter_policy_is_what_closes_the_value_gate(A):
    """Under every propagating arm the frozen core sees valid=False, so it --
    not the research wrapper -- is what gates the value relations off."""
    for arm in A.ARMS:
        if arm in ("S0",):
            assert A.policy_for(arm) == "DROP"
        else:
            assert A.policy_for(arm) == "PROPAGATE_INVALID_HOLD"


def test_status_evidence_survives_a_closed_operational_gate(A):
    """The property S2 exists to have."""
    w = A.DiagArm("S2a")
    w.sidecar.observe(NOFIX, 1.0)
    w.set_time(1.1)
    w.step(_feats(0.0))
    row = w.rows[-1]
    assert row["a_gps"] == 0.0
    assert row["d_status"] == 1.0, "status must survive A = 0"
    assert row["c_status"] == 0.0


def test_the_coupled_control_discards_exactly_that_evidence(A):
    w = A.DiagArm("S1Da")
    w.sidecar.observe(NOFIX, 1.0)
    w.set_time(1.1)
    w.step(_feats(0.0))
    row = w.rows[-1]
    assert row["a_gps"] == 0.0
    assert row["d_status"] == 0.0, "D = A must gate the status off"


def test_on_an_open_gate_the_two_are_indistinguishable(A):
    a, b = A.DiagArm("S2a"), A.DiagArm("S1Da")
    for w in (a, b):
        w.sidecar.observe(NOFIX, 1.0)
        w.set_time(1.1)
        w.step(_feats(1.0))
    assert a.rows[-1] == b.rows[-1]


# ---------------------------------------------- the sidecar
def test_the_sidecar_answers_as_of_the_queried_time(A):
    """The ordering bug this fixes made IV and VV indistinguishable."""
    s = A.GnssStatusSidecar()
    s.observe(GOOD, 1.0)
    s.observe(NOFIX, 2.0)
    assert s.status_contribution(1.5)[0] == 1.0, "must not see the future"
    assert s.status_contribution(2.0)[0] == 0.0


def test_status_evidence_expires_when_no_message_arrives(A):
    """Item 22: transport starvation must NOT read as 'the receiver said no'."""
    s = A.GnssStatusSidecar()
    s.observe(NOFIX, 1.0)
    assert s.status_contribution(1.4) is not None
    assert s.status_contribution(1.0 + A.MSG_FRESH_S + 0.01) is None


def test_an_unusable_h_acc_never_enters_the_smoother(A):
    s = A.GnssStatusSidecar()
    s.observe(GOOD, 1.0)
    settled = s.hacc_contribution(1.0)
    s.observe(NOFIX, 1.1)
    assert s.hacc_contribution(1.1) == settled, \
        "a message with no usable h_acc must not move the estimate"


def test_the_two_hacc_freshness_modes_differ_only_after_the_window(A):
    a = A.GnssStatusSidecar("message")
    b = A.GnssStatusSidecar("valid_hacc")
    for s in (a, b):
        s.observe(GOOD, 1.0)
        s.observe(NOFIX, 1.2)
    assert a.hacc_contribution(1.3) == b.hacc_contribution(1.3)
    for s in (a, b):
        s.observe(NOFIX, 1.6)
    # the message keeps arriving, so "message" mode still serves the stale
    # healthy h_acc; "valid_hacc" mode has correctly let it expire
    assert a.hacc_contribution(1.7) is not None
    assert b.hacc_contribution(1.7) is None


def test_the_hacc_transform_is_the_frozen_one(A):
    """No new scale was chosen: the recursion must match lam_stream exactly."""
    import importlib.util as iu
    spec = iu.spec_from_file_location("_h", os.path.join(
        ROOT, "research", "maer", "maer_hacc_transform.py"))
    HH = iu.module_from_spec(spec)
    spec.loader.exec_module(HH)
    msgs = [dict(GOOD), dict(DEGRADED), dict(DEGRADED), dict(GOOD)]
    want = [c for _m, _l, c, ok in HH.lam_stream(msgs) if ok]
    s = A.GnssStatusSidecar()
    got = []
    for i, m in enumerate(msgs):
        s.observe(m, float(i))
        got.append(s.hacc_contribution(float(i))[0])
    assert got == pytest.approx(want, rel=1e-12)


# ---------------------------------------------- no label leakage
def test_no_arm_config_mentions_a_scenario_or_fault_label(A):
    banned = ("jam", "m1", "clean", "scenario", "sim_gps", "fault_label",
              "ground_truth", "onset")
    for arm in A.ARMS:
        blob = json.dumps(A.arm_config(arm)).lower()
        for w in banned:
            assert w not in blob, (arm, w)


def test_the_sidecar_signature_takes_no_label(A):
    import inspect
    assert list(inspect.signature(
        A.GnssStatusSidecar.observe).parameters) == ["self", "msg", "t"]
    assert list(inspect.signature(
        A.GnssStatusSidecar.status_contribution).parameters) == ["self", "tau"]


def test_a_gps_is_read_from_the_frozen_gate_not_re_derived(A):
    w = A.DiagArm("S2c")
    w.set_time(1.0)
    w.step(_feats(0.0))
    assert w.rows[-1]["a_gps"] == 0.0
    w.step(_feats(1.0))
    assert w.rows[-1]["a_gps"] == 1.0


# ---------------------------------------------- committed results
@pytest.mark.skipif(not os.path.exists(
    os.path.join(RES, "S0_S1_REPRODUCTION.json")), reason="not built")
def test_the_motivating_tradeoff_reproduced_exactly():
    d = json.load(open(os.path.join(RES, "S0_S1_REPRODUCTION.json"),
                       encoding="utf-8"))
    assert d["exact_reproduction"] is True
    assert all(c["exact_match"] for c in d["checks"])


@pytest.mark.skipif(not os.path.exists(
    os.path.join(RES, "FORMAL_RESULTS.json")), reason="not built")
def test_the_closed_form_predicts_the_measured_replay():
    d = json.load(open(os.path.join(RES, "FORMAL_RESULTS.json"),
                       encoding="utf-8"))
    for c in d["prediction_vs_measurement"]:
        assert c["abs_difference"] < 1e-3, c


@pytest.mark.skipif(not os.path.exists(
    os.path.join(RES, "PARETO_RESULTS.json")), reason="not built")
def test_the_clean_control_is_reported_whatever_it_says():
    """Item 19 is a control, not a hurdle: the result is recorded either way."""
    d = json.load(open(os.path.join(RES, "PARETO_RESULTS.json"),
                       encoding="utf-8"))
    for tag, v in d["clean_control_equivalence"].items():
        assert "arms_equal_on_D" in v and "final_post_gps_fault" in v, tag
        # no arm may lead with gps_fault on clean data
        assert all(x == 0.0 for x in v["D_top_share"].values()), (tag, v)
