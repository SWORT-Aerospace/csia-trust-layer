"""The WP-C2 IMU repair is an experiment. Assert it is OFF by default.

The repair adds `attitude_gravity_mag` to `imu0_bias_drift`'s LOW signature,
which separates the IMU pair under every configuration at full instrumentation
(WP-C2 Part 2). It is authorized as a research experiment, not as a production
default, so these tests pin the production path shut.

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

def test_production_signature_does_not_carry_the_repair():
    """The committed cause table must be untouched by this work package."""
    causes = CausalDiagnosis().causes
    assert REPAIR_FEATURE not in causes[REPAIR_TARGET], (
        f"{REPAIR_FEATURE} has leaked into the production {REPAIR_TARGET} "
        f"signature; the WP-C2 repair was authorized behind a flag only")


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


def test_repair_changes_exactly_one_signature():
    """A repair that touches more than its target is not the repair we
    measured."""
    exp = _experiment()
    base = CausalDiagnosis().causes
    repaired = exp.repaired_causes(base)
    assert set(repaired) == set(base), "hypothesis set must not change"
    differing = [h for h in base if sorted(repaired[h]) != sorted(base[h])]
    assert differing == [REPAIR_TARGET], (
        f"expected only {REPAIR_TARGET} to change, got {differing}")
    assert (set(repaired[REPAIR_TARGET]) - set(base[REPAIR_TARGET])
            == {REPAIR_FEATURE})


def test_repair_never_touches_nominal():
    exp = _experiment()
    assert list(exp.repaired_causes(CausalDiagnosis().causes)["nominal"]) == []


def test_pipeline_gets_the_production_table_when_flag_absent(monkeypatch):
    """End-to-end guard: with the flag unset, the object handed to the
    pipeline is the production one."""
    exp = _experiment()
    monkeypatch.delenv(FLAG, raising=False)
    diag = exp.make_diagnosis(repair=exp.repair_enabled())
    assert REPAIR_FEATURE not in diag.causes[REPAIR_TARGET]
