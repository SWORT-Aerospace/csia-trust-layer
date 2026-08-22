"""The IMU repair, measured in WP-C2 and PROMOTED TO DEFAULT in WP-C3.

`attitude_gravity_mag` is now in `imu0_bias_drift`'s production LOW signature
(`csia/diagnosis/bayes.py`). These tests pinned the flag OFF while it was an
experiment; they now pin the promotion, so a silent revert fails the build.
The flag itself is retained as a no-op so the WP-C2 before/after experiment
stays re-runnable.

The research module lives under `research/`, which is NOT an installed package
— CI runs `pip install -e .`, which ships `csia` only. Importing it at module
scope would make this file fail to collect on a clean runner, so the
research-side checks use `pytest.importorskip` and the production-side checks
stand alone. (`tests/test_ci_env.py` caught exactly this defect.)
"""

import os

import pytest

from csia.diagnosis import CausalDiagnosis

FLAG = "CSIA_WP_C2_IMU_REPAIR"
REPAIR_FEATURE = "attitude_gravity_mag"
REPAIR_TARGET = "imu0_bias_drift"


def _experiment():
    """The research module, or skip. Needs `research/` on the path."""
    return pytest.importorskip(
        "research.wp_c2.repair_experiment",
        reason="research/ is not an installed package; run with PYTHONPATH=.")


# --- production-path guards: these must hold on any runner -----------------

def test_production_signature_now_carries_the_repair():
    """PROMOTED 2026-08-22. The repair was measured behind a flag in WP-C2 and
    promoted to default in WP-C3 on the user's authorization.

    This assertion is inverted from its original form, which pinned the flag
    OFF. It now pins the promotion, so a silent revert fails the build.
    """
    causes = CausalDiagnosis().causes
    assert REPAIR_FEATURE in causes[REPAIR_TARGET], (
        f"{REPAIR_FEATURE} is missing from the production {REPAIR_TARGET} "
        f"signature; the WP-C3 promotion has been reverted")
    assert REPAIR_FEATURE not in causes["imu1_bias_drift"], (
        "the repair must remain asymmetric between the two IMUs")


def test_nominal_signature_is_empty():
    """`nominal`'s LOW set is definitionally empty: healthy flight predicts no
    anomaly. Any edit to it would invert the model's meaning."""
    assert list(CausalDiagnosis().causes["nominal"]) == []


def test_flag_is_not_set_in_the_ambient_environment():
    """A stray export would silently turn the experiment on for a whole run."""
    assert os.environ.get(FLAG, "0") != "1", (
        f"{FLAG} is set in this environment; production behaviour is not "
        f"being exercised")


# --- research-side guards: skipped when research/ is not importable --------

def test_flag_is_off_by_default(monkeypatch):
    exp = _experiment()
    monkeypatch.delenv(FLAG, raising=False)
    assert exp.repair_enabled() is False


@pytest.mark.parametrize("value", ["0", "", "false", "no", "true", "yes"])
def test_only_the_exact_opt_in_enables_it(monkeypatch, value):
    """Anything other than the literal "1" leaves production behaviour."""
    exp = _experiment()
    monkeypatch.setenv(FLAG, value)
    assert exp.repair_enabled() is False


def test_explicit_opt_in_enables_it(monkeypatch):
    exp = _experiment()
    monkeypatch.setenv(FLAG, "1")
    assert exp.repair_enabled() is True


def test_default_diagnosis_is_unmodified(monkeypatch):
    exp = _experiment()
    monkeypatch.delenv(FLAG, raising=False)
    assert exp.make_diagnosis(repair=False).causes == CausalDiagnosis().causes


def test_flag_is_now_a_no_op_after_promotion():
    """Post-promotion the flag adds nothing: the feature is already in the
    production table, so repaired == default. Kept so the WP-C2 experiment
    remains re-runnable and its before/after record stays reproducible."""
    exp = _experiment()
    base = CausalDiagnosis().causes
    repaired = exp.repaired_causes(base)
    # Compare as sets: repaired_causes sorts only the entry it touches, so
    # list order differs for the others without any content change.
    assert {h: set(v) for h, v in repaired.items()} \
        == {h: set(v) for h, v in base.items()}


def test_repair_changes_exactly_one_signature():
    """A repair that touches more than its target is not the repair we
    measured."""
    exp = _experiment()
    base = CausalDiagnosis().causes
    repaired = exp.repaired_causes(base)
    assert set(repaired) == set(base), "hypothesis set must not change"
    differing = [h for h in base if sorted(repaired[h]) != sorted(base[h])]
    assert differing == [], (
        f"post-promotion the repair is a no-op; unexpected changes: "
        f"{differing}")


def test_repair_never_touches_nominal():
    exp = _experiment()
    assert list(exp.repaired_causes(CausalDiagnosis().causes)["nominal"]) == []


def test_pipeline_gets_the_production_table_when_flag_absent(monkeypatch):
    """End-to-end guard: with the flag unset, the object handed to the
    pipeline is the production one — which now carries the repair."""
    exp = _experiment()
    monkeypatch.delenv(FLAG, raising=False)
    diag = exp.make_diagnosis(repair=exp.repair_enabled())
    assert diag.causes == CausalDiagnosis().causes
    assert REPAIR_FEATURE in diag.causes[REPAIR_TARGET]
