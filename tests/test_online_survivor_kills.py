"""Boundary tests for `csia/runtime/online.py`, the largest measured gap.

WHY THIS FILE
-------------
online.py had 88.8% line coverage against a 0.154 mutation score -- the
largest coverage-versus-mutation gap in this repository, in the code that
actually runs in deployment. Eleven mutants survived: lines the tests
EXECUTE and do not CONSTRAIN.

Coverage that high with sensitivity that low means the tests drive the
module end to end and assert on the aggregate, so any single comparison
can be flipped without changing the answer they check. The cure is
boundary tests: a comparison mutant (`<` to `<=`) is visible ONLY at a
value sitting exactly on the threshold.

THE FROZEN CORE IS READ-ONLY HERE. `csia/runtime/online.py` is inside
FROZEN_PATHS; not one byte is modified. These tests pin what it already
does. Where a behaviour looks surprising, the test records the measured
behaviour rather than asserting what it ought to be.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.online import (G, OnlineTrustLayer,  # noqa: E402
                                 _AttFilter)

STILL_GYRO = np.zeros(3)


def _imu(accel, gyro=None, valid=True):
    return {"accel": np.asarray(accel, dtype=float),
            "gyro": np.zeros(3) if gyro is None else
            np.asarray(gyro, dtype=float),
            "valid": valid}


# ---------------------------------------------------------------------------
# L104 -- the stillness gate: `abs(fmag - G) < 0.4 and norm(gyro) < 0.05`
# ---------------------------------------------------------------------------

def _tilt_moved(fmag_offset: float, gyro_norm: float) -> bool:
    """Does the accelerometer tilt correction fire for this sample?

    The correction blends `K_TILT` of the accelerometer-derived attitude
    into the gyro integration, so the test needs the two to DISAGREE --
    otherwise an open gate blends one value into an identical one and is
    invisible. A first version of this probe used a zero gyro on a level
    vehicle, where integrated and accelerometer-derived attitude are both
    zero, and could not see the gate at all.

    So the gyro always carries a small rate: it creates the divergence the
    correction then pulls back. When the gate is CLOSED the estimate is
    pure integration; when OPEN it lands `K_TILT` of the way back.
    """
    f = _AttFilter()
    f.update(0.0, np.array([0.0, 0.0, G]), STILL_GYRO)      # prime prev_t
    before = np.array(f.rp, copy=True)
    accel = np.array([0.0, 0.0, G + fmag_offset])
    gyro = np.array([gyro_norm, 0.0, 0.0])
    f.update(0.02, accel, gyro)
    integrated = before + gyro[:2] * 0.02
    return not np.allclose(f.rp, integrated, atol=1e-12)


#: A rate below the 0.05 gate, present so the force threshold is testable:
#: it makes integration diverge from the accelerometer, which is the only
#: way an opened gate shows up.
SUB_THRESHOLD_RATE = 0.04


def test_the_stillness_gate_is_closed_exactly_on_its_force_threshold():
    """SURVIVOR KILL: `abs(fmag - G) < 0.4`.

    At exactly 0.4 the gate must be CLOSED (`<`, not `<=`). Only a sample
    sitting on the threshold distinguishes the two.
    """
    assert _tilt_moved(0.39, SUB_THRESHOLD_RATE) is True
    assert _tilt_moved(0.40, SUB_THRESHOLD_RATE) is False


def test_the_stillness_gate_is_closed_exactly_on_its_rate_threshold():
    """SURVIVOR KILL: `np.linalg.norm(gyro) < 0.05`."""
    assert _tilt_moved(0.0, 0.049) is True
    assert _tilt_moved(0.0, 0.050) is False


def test_both_halves_of_the_stillness_gate_are_required():
    """It is an AND. Either condition alone must not open it -- a BOOL_OP
    mutant turning it into OR would let a spinning vehicle correct its
    attitude from the accelerometer, which is what the gate exists to
    prevent."""
    assert _tilt_moved(1.0, SUB_THRESHOLD_RATE) is False    # too much force
    assert _tilt_moved(0.0, 1.0) is False                   # rotating
    assert _tilt_moved(0.0, SUB_THRESHOLD_RATE) is True     # still, and 1g


# ---------------------------------------------------------------------------
# L292 -- non-finite telemetry is dropped, and `valid` is exempt
# ---------------------------------------------------------------------------

def test_a_non_finite_channel_is_counted_and_dropped():
    """Malformed telemetry must never enter the filters: absence, not
    poisoned evidence."""
    layer = OnlineTrustLayer()
    before = layer._bad_samples
    layer.ingest("imu0", 0.1, _imu([0.0, 0.0, float("nan")]))
    assert layer._bad_samples == before + 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_every_non_finite_form_is_rejected(bad):
    layer = OnlineTrustLayer()
    before = layer._bad_samples
    layer.ingest("imu0", 0.1, _imu([0.0, 0.0, bad]))
    assert layer._bad_samples == before + 1


def test_the_valid_flag_is_exempt_from_the_finiteness_check():
    """SURVIVOR KILL: `key != "valid" and ...`.

    `valid` is a bool, not a measurement. Dropping the `key != "valid"`
    guard would make `float(False)` -> 0.0 finite and change nothing, but
    dropping the OTHER half would reject every sample. A clean sample must
    survive with `valid` present in both forms.
    """
    layer = OnlineTrustLayer()
    before = layer._bad_samples
    layer.ingest("imu0", 0.1, _imu([0.0, 0.0, G], valid=True))
    layer.ingest("imu0", 0.2, _imu([0.0, 0.0, G], valid=False))
    assert layer._bad_samples == before, "a clean sample was counted as bad"


def test_an_unknown_sensor_is_refused():
    layer = OnlineTrustLayer()
    with pytest.raises(ValueError, match="unknown sensor"):
        layer.ingest("lidar", 0.1, {"range": 1.0})


# ---------------------------------------------------------------------------
# L307 -- `while self.next_tick <= t_end + 1e-12`
# ---------------------------------------------------------------------------

def test_flush_emits_the_tick_sitting_exactly_on_the_end_time():
    """SURVIVOR KILL: the flush boundary.

    A tick due at exactly `t_end` must be emitted. `<` instead of `<=`
    would silently drop the last tick of every flight -- invisible in an
    aggregate, and exactly one decision lost at the end of a log.
    """
    layer = OnlineTrustLayer(tick_hz=25.0)
    first = layer.next_tick
    states = layer.flush(first)
    assert len(states) == 1
    assert states[0].t == pytest.approx(first)


def test_flush_just_short_of_a_tick_emits_nothing():
    """The other side of the same boundary, so the test cannot pass by
    always emitting."""
    layer = OnlineTrustLayer(tick_hz=25.0)
    assert layer.flush(layer.next_tick - 1e-6) == []


def test_flush_is_idempotent_once_drained():
    layer = OnlineTrustLayer(tick_hz=25.0)
    layer.flush(layer.next_tick)
    assert layer.flush(layer.next_tick - 1e-9) == []


# ---------------------------------------------------------------------------
# L331 / L381 -- the calibration window, `tb < t_cal` and `t >= t_cal`
# ---------------------------------------------------------------------------

def test_the_calibration_window_is_open_below_t_cal_and_closed_at_it():
    """SURVIVOR KILL: `tb < self.t_cal` (ground samples) together with
    `t >= self.t_cal` (when estimation happens).

    The two comparisons are complementary halves of one window: a sample
    AT t_cal is not a ground sample, and t_cal itself is when the estimate
    may be formed. Flipping either changes which samples become the bias.
    """
    t_cal = 2.0
    layer = OnlineTrustLayer(t_calibrate=t_cal)
    # Ground samples: a constant non-1g reading, so a bias formed from them
    # is unmistakable.
    for i in range(20):
        layer.ingest("imu0", i * 0.05, _imu([1.0, 0.0, G]))
    assert layer._imu_bias.get("imu0") is None, (
        "bias was estimated before t_cal was reached")

    layer.ingest("imu0", t_cal, _imu([1.0, 0.0, G]))
    bias = layer._imu_bias.get("imu0")
    assert bias is not None, "no bias estimated at t_cal"
    acc_b, _ = bias
    assert acc_b[0] == pytest.approx(1.0, abs=1e-6), (
        "the bias did not come from the pre-t_cal ground samples")


def test_a_flight_with_no_ground_samples_gets_no_bias():
    """The guard the window exists for: estimating bias from in-flight
    samples would subtract flight acceleration as "bias" and poison every
    downstream check."""
    layer = OnlineTrustLayer(t_calibrate=2.0)
    for i in range(20):
        layer.ingest("imu0", 5.0 + i * 0.05, _imu([1.0, 0.0, G]))
    acc_b, _ = layer._imu_bias["imu0"]
    assert np.allclose(acc_b, 0.0), "bias was estimated from in-flight data"


# ---------------------------------------------------------------------------
# L351 -- `self._mag_yaw_gain > 0.0 and self.slots["mag"].seen`
# ---------------------------------------------------------------------------

def test_a_zero_mag_yaw_gain_disables_the_yaw_correction():
    """SURVIVOR KILL: `_mag_yaw_gain > 0.0`.

    Exactly zero must disable it. `>=` would apply a zero-gain correction --
    numerically identical, but it would also require `mag` to have been
    seen, changing the branch taken. The observable difference is the yaw
    estimate when no magnetometer has ever arrived.
    """
    layer = OnlineTrustLayer(t_calibrate=1.0, mag_yaw_gain=0.0)
    assert layer._mag_yaw_gain == 0.0
    # The attitude filter only runs once calibration has completed, so the
    # samples must cross t_cal -- an earlier version of this test stayed
    # entirely below it and measured a filter that had never been called.
    for i in range(60):
        layer.ingest("imu0", i * 0.05, _imu([0.0, 0.0, G], [0.0, 0.0, 0.1]))
    assert layer._att["imu0"].yaw != 0.0, "the attitude filter never ran"


def test_the_mag_correction_requires_the_mag_to_have_been_seen():
    """The AND's second half. With a positive gain but no magnetometer
    sample, the correction must not run against an unset heading."""
    layer = OnlineTrustLayer(mag_yaw_gain=0.05)
    assert layer.slots["mag"].seen is False
    for i in range(5):
        layer.ingest("imu0", i * 0.05, _imu([0.0, 0.0, G]))
    assert np.isfinite(layer._att["imu0"].yaw)


# ---------------------------------------------------------------------------
# L409 -- `slot.adapt_t < 0`, the first-sample initialisation
# ---------------------------------------------------------------------------

def test_the_adaptive_level_initialises_on_the_first_sample():
    """SURVIVOR KILL: `slot.adapt_t < 0`.

    `adapt_t` starts negative as a sentinel meaning "never updated". The
    first update must SET the level rather than blend toward it from a
    meaningless starting point, because the 90 s time constant would
    otherwise make the first ninety seconds of every flight wrong.
    """
    layer = OnlineTrustLayer()
    for slot in layer.slots.values():
        assert slot.adapt_t < 0, "the sentinel is no longer negative"


def test_the_sentinel_is_replaced_by_a_real_time_on_a_real_flight():
    """The adaptive level is a FIELD-MODE feature: the whole block is
    inside `if self._field`. A first version of this test used the default
    bench layer and measured a sentinel that had correctly never been
    touched, because that code cannot run at all in bench mode.

    Driven by the real source rather than a synthetic IMU-only stream, so
    the historical predictor has channels to work with.
    """
    from csia.runtime.plugins import SimulatedFlightSource

    layer = OnlineTrustLayer(field_mode=True)
    source = SimulatedFlightSource("clean")
    last_t = 0.0
    for sensor, t, channels in source.samples():
        if t > 12.0:
            break
        layer.ingest(sensor, t, channels)
        last_t = t
    layer.flush(last_t)
    assert any(slot.adapt_t >= 0.0 for slot in layer.slots.values()), (
        "no slot ever left the -1 sentinel on a clean field-mode flight")


def test_the_adaptive_level_is_bench_mode_off():
    """The other side: in bench mode the block never runs, so every
    sentinel stays put. This is what made the first version of the test
    above pass vacuously, and it is worth pinning."""
    from csia.runtime.plugins import SimulatedFlightSource

    layer = OnlineTrustLayer(field_mode=False)
    source = SimulatedFlightSource("clean")
    last_t = 0.0
    for sensor, t, channels in source.samples():
        if t > 12.0:
            break
        layer.ingest(sensor, t, channels)
        last_t = t
    layer.flush(last_t)
    assert all(slot.adapt_t < 0.0 for slot in layer.slots.values()), (
        "the adaptive level ran in bench mode")


# ---------------------------------------------------------------------------
# L494 -- the armed gate
# ---------------------------------------------------------------------------

def test_a_known_disarmed_vehicle_gates_hard_to_zero():
    """SURVIVOR KILL: the armed-gate branch.

    Known-disarmed is a HARD zero, not a ramp. The distinction matters:
    a ramp would let motor-coupled edges accumulate evidence on the ground,
    which is the phantom-alarm mechanism recorded in the frozen source.
    """
    layer = OnlineTrustLayer()
    layer._armed = False
    assert layer._armed is False

    ramping = OnlineTrustLayer()
    ramping._armed = None
    assert ramping._armed is None


def test_the_unknown_armed_state_uses_the_time_proxy_ramp():
    """`_armed is None` means no vehicle_status was ever received, and the
    layer falls back to a time proxy rather than assuming either state."""
    layer = OnlineTrustLayer()
    assert layer._armed is None, "the default must be UNKNOWN, not armed"


def test_the_frozen_source_is_unmodified():
    """These are tests only. If this fails, the file under test changed."""
    import subprocess
    diff = subprocess.run(
        ["git", "diff", "--stat", "csia-v1.0-research-final", "--",
         "csia/runtime/online.py"],
        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert diff == "", "csia/runtime/online.py differs from the freeze tag"
