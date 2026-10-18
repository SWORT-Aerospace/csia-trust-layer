"""The v1.1 adapter must feed the frozen core what the v1 path fed it.

Why this test exists. v1.1 added a SECOND way into `OnlineTrustLayer`:

    v1.0   MAVLink msg -> csia.runtime.plugins.map_mavlink -> core
    v1.1   MAVLink msg -> PlatformAdapter -> AircraftSample -> core

The core is frozen at `csia-v1.0-research-final`. If the two paths hand it
different numbers, then every measurement taken through the new stack is
silently incomparable with the tagged baseline -- and the freeze would be
worthless, because the thing that changed would be the input rather than the
algorithm.

Nothing else in the repository checks this. The adapter unit tests assert the
adapter matches *my understanding* of the MAVLink spec; the same understanding
wrote the adapter, so those tests cannot catch a shared misreading. This test
compares against independently written code that has been used for every v1
result, which can.

Where the paths DIFFER, the difference is asserted explicitly and named. A
silent divergence is a bug; a listed one is a decision.
"""

import numpy as np
import pytest

from csia.aircraft.adapters import get_adapter
from csia.runtime.plugins import map_mavlink

G = 9.80665


class Msg:
    """Attribute-style MAVLink message, as pymavlink delivers it.

    `map_mavlink` uses attribute access and `get_type()`; the adapter accepts
    either that or a dict. Driving both from ONE object removes any chance of
    the two paths seeing different inputs.
    """

    def __init__(self, type_, **fields):
        self._type = type_
        for k, v in fields.items():
            setattr(self, k, v)

    def get_type(self):
        return self._type


def _stream():
    """One second of representative telemetry, deliberately not round numbers.

    Values are chosen so a scale error of 10x, 100x or 1000x cannot coincide
    with a correct answer, and so no axis is zero (a sign flip would hide).
    """
    return [
        Msg("HEARTBEAT", type=2, base_mode=128 | 64, custom_mode=5,
            autopilot=3, system_status=4),
        Msg("SCALED_IMU", time_boot_ms=1000,
            xacc=137, yacc=-241, zacc=-993,
            xgyro=53, ygyro=-27, zgyro=11,
            xmag=421, ymag=-133, zmag=377),
        Msg("SCALED_IMU2", time_boot_ms=1000,
            xacc=141, yacc=-238, zacc=-991,
            xgyro=49, ygyro=-31, zgyro=14,
            xmag=0, ymag=0, zmag=0),
        Msg("SCALED_PRESSURE", time_boot_ms=1000,
            press_abs=978.31, press_diff=0.0, temperature=2317),
        Msg("GPS_RAW_INT", time_usec=1_000_000, fix_type=3,
            lat=473_977_419, lon=85_455_936, alt=488_231,
            eph=121, epv=178, vel=643, cog=13_742, satellites_visible=11),
        Msg("BATTERY_STATUS", time_boot_ms=1000,
            voltages=[3821, 3817, 3833, 3809] + [65535] * 6,
            current_battery=1731, battery_remaining=76),
        Msg("VIBRATION", time_usec=1_000_000,
            vibration_x=3.17, vibration_y=2.84, vibration_z=4.02,
            clipping_0=0, clipping_1=0, clipping_2=0),
    ]


def _legacy_channels():
    """Run the v1 path and collapse to {sensor: channels}."""
    ctx = {"t0": None}
    out = {}
    for m in _stream():
        for sensor, _t, ch in map_mavlink(m, ctx):
            out[sensor] = ch
    return out


def _adapter_channels():
    """Run the v1.1 path and collapse to {sensor: channels}."""
    ad = get_adapter("ardupilot")
    for m in _stream():
        ad.ingest(m)
    s = ad.sample(t_mono=1.0)
    return {sensor: ch for sensor, _t, ch in ad.to_core_samples(s)}, ad


# Sensors the new path deliberately withholds, with the reason. Anything that
# disappears WITHOUT being on this list is a regression.
INTENTIONALLY_WITHHELD = {
    "motor_esc": "ESC channels are STUB_OR_NONINFORMATIVE in SITL (W-5); "
                 "the constant 0.8 A drove a spurious CRITICAL on every "
                 "clean flight",
}

# Sensors the v1.1 path delivers that the v1 path drops. Found by this test on
# its first run -- see test_v1_drops_the_first_heartbeat for the mechanism.
INTENTIONALLY_ADDED = {
    "vehicle_status": "v1 stamps HEARTBEAT with the last stream time and "
                      "drops it when none exists yet, so the first armed "
                      "report is discarded on every connection (W-7). The "
                      "v1.1 path uses the monotonic deployment clock and has "
                      "no such dependency.",
}


def test_same_sensor_set_except_documented_exclusions():
    legacy = _legacy_channels()
    new, _ = _adapter_channels()
    missing = set(legacy) - set(new)
    assert missing <= set(INTENTIONALLY_WITHHELD), (
        f"the v1.1 path dropped sensors nobody decided to drop: "
        f"{sorted(missing - set(INTENTIONALLY_WITHHELD))}")
    added = set(new) - set(legacy)
    assert added <= set(INTENTIONALLY_ADDED), (
        f"the v1.1 path invented sensors: "
        f"{sorted(added - set(INTENTIONALLY_ADDED))}")


def test_v1_drops_the_first_heartbeat():
    """W-7, pinned. A v1 defect the v1.1 path does not inherit.

    `map_mavlink` has no clock of its own: it stamps an untimestamped message
    with `ctx["t_last"]`, and returns nothing when that is unset. HEARTBEAT is
    untimestamped, and on a real link it is the FIRST message -- pymavlink's
    own `wait_heartbeat()` guarantees it. So the first armed report is thrown
    away on every connection, and `armed` stays None until the next heartbeat
    a second later.

    `armed` gates the motor edges and the failsafe, so this is a real if brief
    startup gap. It is recorded, not fixed: the v1 core is frozen at
    `csia-v1.0-research-final` and this test exists to keep the behaviour
    visible, not to license changing it.
    """
    hb = Msg("HEARTBEAT", type=2, base_mode=128 | 64, custom_mode=5)
    imu = Msg("SCALED_IMU", time_boot_ms=1000, xacc=1, yacc=1, zacc=-1000,
              xgyro=0, ygyro=0, zgyro=0, xmag=1, ymag=1, zmag=1)

    ctx = {"t0": None}
    assert map_mavlink(hb, ctx) == [], "v1 no longer drops the first heartbeat"

    ctx = {"t0": None}
    map_mavlink(imu, ctx)
    assert [s for s, _t, _c in map_mavlink(hb, ctx)] == ["vehicle_status"]

    # The v1.1 path reports it from the first heartbeat, in any order.
    ad = get_adapter("ardupilot")
    ad.ingest(hb)
    cv = ad.sample(t_mono=0.0).get("vehicle_status.armed")
    assert cv.usable and cv.value is True


@pytest.mark.parametrize("sensor,key", [
    ("imu0", "accel"), ("imu0", "gyro"),
    ("imu1", "accel"), ("imu1", "gyro"),
    ("mag", "field_ut"),
    ("baro", "altitude"),
    ("gps", "pos"), ("gps", "vel"),
    ("battery", "voltage"),
    ("vibration", "rms"),
])
def test_numeric_agreement_with_the_v1_path(sensor, key):
    """Every quantity the frozen core reads must be bit-comparable.

    Tolerance is 1e-9 relative, not 1e-3: these are the same arithmetic on the
    same inputs, so anything beyond floating-point noise is a real difference
    in how a field was interpreted.
    """
    legacy = _legacy_channels()
    new, _ = _adapter_channels()
    assert sensor in legacy and sensor in new, sensor
    a = np.asarray(legacy[sensor][key], dtype=float)
    b = np.asarray(new[sensor][key], dtype=float)
    assert a.shape == b.shape, f"{sensor}.{key} shape differs"
    np.testing.assert_allclose(
        b, a, rtol=1e-9, atol=1e-12,
        err_msg=f"{sensor}.{key} differs between the v1 and v1.1 paths")


def test_gps_vz_valid_flag_is_preserved():
    """The core changes behaviour on this flag; it must survive the rewrite."""
    legacy = _legacy_channels()
    new, _ = _adapter_channels()
    assert legacy["gps"]["vz_valid"] is False
    assert new["gps"]["vz_valid"] is False


def test_esc_is_the_only_intentional_exclusion():
    """Pin the exclusion list so silently growing it fails the build."""
    stream = _stream() + [Msg("ESC_TELEMETRY_1_TO_4", time_usec=1_000_000,
                              rpm=[0, 0, 0, 0], current=[80, 80, 80, 80],
                              voltage=[1600] * 4, temperature=[20] * 4)]
    ctx = {"t0": None}
    legacy = {}
    for m in stream:
        for sensor, _t, ch in map_mavlink(m, ctx):
            legacy[sensor] = ch
    ad = get_adapter("ardupilot")
    for m in stream:
        ad.ingest(m)
    new = {s for s, _t, _c in ad.to_core_samples(ad.sample(t_mono=1.0))}
    assert "motor_esc" in legacy, "the v1 path used to accept the ESC stub"
    assert "motor_esc" not in new, "the ESC stub reached the frozen core again"
    assert set(legacy) - new == set(INTENTIONALLY_WITHHELD)


def test_battery_current_sentinel_is_refused_by_both_paths():
    """`current_battery == -1` means the vehicle is not measuring current.

    HISTORY, because this test used to assert the opposite of half of what it
    now asserts. Until the v1.1 ingestion pass this was the one place the two
    paths disagreed on a VALUE rather than on presence: `map_mavlink` computed
    `max(-1, 0) / 100 = 0.0` and handed the core a confident reading of zero
    amps, while the adapter refused. The test asserted both, and called the
    disagreement a deliberate improvement.

    It was half an improvement. Zero amps is a claim about the aircraft and
    "not measured" is a claim about the sensor, and the legacy path was making
    the first when the producer had made the second. v1.1 fixes the legacy
    path too, so the paths now AGREE and the agreement is the thing worth
    protecting. The pre-fix behaviour is preserved, with its hash, in
    `engineering/v1_1/KNOWN_DEFECTS_PRE_FIX.json` (case D4).
    """
    m = Msg("BATTERY_STATUS", time_boot_ms=1000,
            voltages=[3800, 3800, 3800, 3800] + [65535] * 6,
            current_battery=-1)
    ctx = {"t0": None, "t_last": 1.0}
    legacy = {s: ch for s, _t, ch in map_mavlink(m, ctx)}
    assert legacy["battery"]["current"] is None      # was 0.0 before v1.1
    assert legacy["battery"]["current_valid"] is False
    assert legacy["battery"]["valid"] is False

    ad = get_adapter("ardupilot")
    ad.ingest(m)
    cv = ad.sample(t_mono=1.0).get("battery.current")
    assert cv.value is None
    assert not cv.usable
    # and the sensor is withheld rather than fed a fabricated zero
    assert "battery" not in {s for s, _t, _c in
                             ad.to_core_samples(ad.sample(t_mono=1.0))}


def test_adapter_reports_no_unmapped_message_it_should_have_handled():
    _new, ad = _adapter_channels()
    unmapped = ad.unmapped_types()
    assert unmapped == {}, f"adapter ignored messages it maps: {unmapped}"


# --------------------------------------------------------------------------
# Sequence equivalence.
#
# Everything above compares ONE conversion. That is not enough, and this
# section exists because the single-shot tests passed while the adapter was
# re-feeding the frozen core nine sensors every tick regardless of whether
# any new data had arrived.
#
# The v1 path hands the core one sample per MEASUREMENT
# (csia/runtime/service.py:120 iterates the source stream). An adapter that
# hands it one sample per TICK per sensor is not equivalent, even though every
# individual value is identical -- it changes how many times a filter is
# updated, and therefore the effective time constants of a FROZEN core.

def _stream_at_rates(seconds=1.0, imu_hz=25, gps_hz=5):
    """Interleaved messages at DIFFERENT rates, which is the whole point."""
    msgs = []
    for i in range(int(seconds * imu_hz)):
        t = i / imu_hz
        msgs.append((t, Msg("SCALED_IMU", time_boot_ms=int(t * 1000),
                            xacc=100 + i, yacc=-200, zacc=-1000,
                            xgyro=10, ygyro=-5, zgyro=2,
                            xmag=400, ymag=-100, zmag=300)))
    for i in range(int(seconds * gps_hz)):
        t = i / gps_hz
        msgs.append((t, Msg("GPS_RAW_INT", time_usec=int(t * 1e6), fix_type=3,
                            lat=473_000_000 + i * 100, lon=85_000_000,
                            alt=500_000, vel=100, cog=9000)))
    return sorted(msgs, key=lambda p: p[0])


def test_core_receives_one_sample_per_measurement_not_per_tick():
    """A slow sensor must not be re-fed at the tick rate.

    GPS arrives at 5 Hz while the layer ticks at 25 Hz. The core must see the
    GPS sample 5 times, not 25 -- otherwise one fix is presented to the Holt
    filters as five agreeing measurements.
    """
    ad = get_adapter("ardupilot")
    clock = {"t": 0.0}
    ad._clock = lambda: clock["t"]

    handed = {}
    stream = _stream_at_rates()
    tick_dt = 1.0 / 25.0
    next_tick, idx = 0.0, 0
    while next_tick <= 1.0:
        while idx < len(stream) and stream[idx][0] <= next_tick:
            clock["t"] = stream[idx][0]
            ad.ingest(stream[idx][1])
            idx += 1
        clock["t"] = next_tick
        for sensor, _t, _ch in ad.to_core_samples(ad.sample(t_mono=next_tick)):
            handed[sensor] = handed.get(sensor, 0) + 1
        next_tick += tick_dt

    assert handed.get("imu0", 0) >= 20, handed
    # The assertion that was missing: 5 Hz data handed over ~5 times, not 25.
    assert handed.get("gps", 0) <= 8, (
        f"GPS was handed to the core {handed.get('gps')} times for 5 "
        f"measurements -- the adapter is re-feeding stale samples")


def test_an_unchanged_sensor_is_not_handed_over_twice():
    """The minimal case, stated directly."""
    ad = get_adapter("ardupilot")
    ad.ingest(Msg("SCALED_IMU", time_boot_ms=1000, xacc=137, yacc=-241,
                  zacc=-993, xgyro=53, ygyro=-27, zgyro=11,
                  xmag=421, ymag=-133, zmag=377))
    first = {s for s, _t, _c in ad.to_core_samples(ad.sample(t_mono=1.0))}
    assert "imu0" in first
    # Nothing new arrived. The core must not be told again.
    second = {s for s, _t, _c in ad.to_core_samples(ad.sample(t_mono=1.04))}
    assert "imu0" not in second, "stale sensor re-fed to the frozen core"

    ad.ingest(Msg("SCALED_IMU", time_boot_ms=1040, xacc=140, yacc=-240,
                  zacc=-990, xgyro=50, ygyro=-25, zgyro=10,
                  xmag=420, ymag=-130, zmag=375))
    third = {s for s, _t, _c in ad.to_core_samples(ad.sample(t_mono=1.08))}
    assert "imu0" in third, "a genuinely new sample was withheld"
