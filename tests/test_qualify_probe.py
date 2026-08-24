"""The qualification probe is an instrument, so it needs its own tests.

RULE A applied reflexively: an instrument that decides whether a channel is
trustworthy must itself be checked, or a defect in it becomes a false verdict
about an autopilot.

Every test here pins a defect that actually occurred, in the order it was
found. All three were invisible until a live PX4 run hit them.
"""

import importlib.util
import math
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.qualification import default_contract   # noqa: E402


def _probe():
    spec = importlib.util.spec_from_file_location(
        "qualify_platform",
        os.path.join(ROOT, "tools", "simulation", "qualify_platform.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


qp = _probe()


# --------------------------------------------------------------------------
# Defect 1: a NaN reached statistics.pstdev and killed a 40-second run.
#
# PX4's ESTIMATOR_STATUS publishes NaN ratios before the EKF converges;
# ArduPilot's EKF_STATUS_REPORT does not. _scalarize guarded only its numpy
# branch, so the dict branch returned NaN straight through.

@pytest.mark.parametrize("value", [
    float("nan"),
    float("inf"),
    float("-inf"),
    {"vel_ratio": float("nan"), "mag_ratio": 0.3},     # the actual crash
    {"only": float("inf")},
    [1.0, float("nan")],
    [float("inf"), 2.0],
])
def test_non_finite_never_becomes_a_sample(value):
    assert qp._scalarize(value) is None


@pytest.mark.parametrize("value,expected", [
    ({"a": 1.0, "b": 2.0}, 3.0),
    ([1.0, 2.0], 3.0),
    (2.5, 2.5),
    (True, 1.0),
])
def test_finite_values_still_scalarize(value, expected):
    """A guard that rejected everything would be safe and useless."""
    assert qp._scalarize(value) == pytest.approx(expected)


def test_every_scalarize_branch_is_guarded():
    """Regression on the SHAPE of the fix, not just one input.

    The bug was structural: five branches, one check. If someone reintroduces
    an early return, this catches it for any branch rather than only the dict
    one that happened to bite.
    """
    for value in (float("nan"), {"x": float("nan")}, [float("nan")],
                  float("inf"), {"x": float("inf")}, [float("inf")]):
        out = qp._scalarize(value)
        assert out is None or math.isfinite(out)


def test_pstdev_is_reachable_with_probe_output():
    """The end the crash came from: whatever _scalarize emits must be safe."""
    import statistics
    vals = [qp._scalarize(v) for v in
            ({"a": 1.0}, {"a": 2.0}, {"a": 3.0}, {"a": float("nan")})]
    clean = [v for v in vals if v is not None]
    assert statistics.pstdev(clean) > 0      # would raise before the fix


# --------------------------------------------------------------------------
# Defect 2: "arrived but unusable" was collapsed into "never arrived".

def test_nan_only_channel_is_not_reported_as_absent():
    c = default_contract()
    rows = qp.analyse({}, {}, c, nonfinite={"estimator.variances": 1200})
    row = next(r for r in rows if r["channel"] == "estimator.variances")
    assert row["observed"] == "AVAILABLE_UNVALIDATED"
    assert "non-finite" in row["detail"]
    assert row["nonfinite_samples"] == 1200


def test_truly_absent_channel_still_reports_absent():
    c = default_contract()
    rows = qp.analyse({}, {}, c, nonfinite={})
    row = next(r for r in rows if r["channel"] == "esc.rpm")
    assert row["observed"] == "UNAVAILABLE"
    assert row["detail"] == "never arrived"
    assert row["nonfinite_samples"] == 0


# --------------------------------------------------------------------------
# Defect 3: `spread` leaked across channels.
#
# The DECODE branch never assigned it, so a latched row reported whatever the
# previous channel left in the local variable.

def test_spread_does_not_leak_from_a_varying_channel_into_a_latched_one():
    c = default_contract()
    obs = {"baro.altitude": [1.0, 2.0, 3.0],        # VARIATION, spread 2.0
           "vehicle_status.armed": [1.0, 1.0]}      # DECODE, spread undefined
    rows = qp.analyse(obs, {}, c)
    varying = next(r for r in rows if r["channel"] == "baro.altitude")
    latched = next(r for r in rows if r["channel"] == "vehicle_status.armed")
    assert varying["spread"] == pytest.approx(2.0)
    assert latched["spread"] is None, (
        "a DECODE row inherited the previous channel's spread")


def test_latched_channel_is_informative_by_decoding_not_variation():
    c = default_contract()
    rows = qp.analyse({"vehicle_status.armed": [1.0] * 500}, {}, c)
    row = next(r for r in rows if r["channel"] == "vehicle_status.armed")
    assert row["observed"] == "INFORMATIVE"
    assert "DECODE" in row["detail"]


# --------------------------------------------------------------------------
# The verdict split: presence claims are motion-independent, constancy is not.

def test_presence_finding_survives_an_invalid_probe():
    """A run that could not fly still knows what never arrived."""
    c = default_contract()
    rows = qp.analyse({}, {}, c)
    absent = [r["channel"] for r in rows if r["observed"] == "UNAVAILABLE"]
    assert absent, "presence findings were discarded"
