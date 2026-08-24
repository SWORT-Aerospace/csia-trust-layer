"""Platform adapters: units, frames, sentinels, freshness, isolation.

Every test here encodes a specific way a telemetry integration goes wrong
silently. The scaling tests matter most: an ArduPilot/PX4 unit mix-up is a
1000x error that produces plausible-looking numbers.
"""

import numpy as np
import pytest

from csia.aircraft.adapters import ADAPTERS, get_adapter
from csia.aircraft.sample import MissingReason, Quality

G = 9.80665


def msg(type_, **kw):
    # pymavlink's own to_dict() convention: the message NAME lives in
    # "mavpackettype", leaving "type" free for HEARTBEAT's vehicle-type field.
    # An earlier version of this helper used "type" for both and silently
    # made every HEARTBEAT test meaningless.
    kw["mavpackettype"] = type_
    return kw


# --------------------------------------------------------------------------
# Units and frames -- the 1000x class of bug

def test_ardupilot_accel_is_milli_g():
    ad = get_adapter("ardupilot")
    ad.ingest(msg("SCALED_IMU", time_boot_ms=1000,
                  xacc=0, yacc=0, zacc=-1000))          # -1000 mG = -1 g FRD
    cv = ad.sample(t_mono=1.0).get("imu0.accel")
    assert cv.usable
    # FRD z-down -1 g -> z-up +9.81
    assert cv.value[2] == pytest.approx(G, rel=1e-6)
    assert cv.unit == "m/s^2"


def test_px4_accel_is_already_si():
    ad = get_adapter("px4")
    ad.ingest(msg("HIGHRES_IMU", time_usec=1_000_000,
                  xacc=0.0, yacc=0.0, zacc=-G, fields_updated=None))
    cv = ad.sample(t_mono=1.0).get("imu0.accel")
    assert cv.value[2] == pytest.approx(G, rel=1e-6)


def test_the_two_adapters_do_not_share_scaling():
    """Same physical acceleration, different dialects, same canonical answer."""
    ap = get_adapter("ardupilot")
    ap.ingest(msg("SCALED_IMU", time_boot_ms=1000, xacc=0, yacc=0, zacc=-1000))
    px = get_adapter("px4")
    px.ingest(msg("HIGHRES_IMU", time_usec=1_000_000,
                  xacc=0.0, yacc=0.0, zacc=-G))
    a = ap.sample(t_mono=1.0).get("imu0.accel").value
    b = px.sample(t_mono=1.0).get("imu0.accel").value
    assert np.allclose(a, b, atol=1e-6)


def test_mag_scaling_differs_by_platform():
    ap = get_adapter("ardupilot")            # milligauss -> uT is x0.1
    ap.ingest(msg("SCALED_IMU", time_boot_ms=1000, xacc=1, yacc=1, zacc=1,
                  xmag=500, ymag=0, zmag=0))
    px = get_adapter("px4")                  # gauss -> uT is x100
    px.ingest(msg("HIGHRES_IMU", time_usec=1_000_000, xmag=0.5, ymag=0.0,
                  zmag=0.0))
    assert ap.sample(t_mono=1.0).get("mag.field_ut").value[0] == \
        pytest.approx(50.0)
    assert px.sample(t_mono=1.0).get("mag.field_ut").value[0] == \
        pytest.approx(50.0)


def test_frd_to_z_up_conversion():
    ad = get_adapter("ardupilot")
    ad.ingest(msg("SCALED_IMU", time_boot_ms=1000,
                  xacc=100, yacc=200, zacc=300))
    v = ad.sample(t_mono=1.0).get("imu0.accel").value
    assert v[0] > 0 and v[1] < 0 and v[2] < 0     # (x, -y, -z)


# --------------------------------------------------------------------------
# Sentinels -- values that mean "absent" and must never be read as data

@pytest.mark.parametrize("platform", sorted(ADAPTERS))
def test_no_3d_fix_is_missing_not_a_zero_position(platform):
    ad = get_adapter(platform)
    ad.ingest(msg("GPS_RAW_INT", time_usec=1_000_000, fix_type=3,
                  lat=473_000_000, lon=85_000_000, alt=500_000,
                  vel=0, cog=0))
    assert ad.sample(t_mono=1.0).get("gnss.position").usable
    ad.ingest(msg("GPS_RAW_INT", time_usec=2_000_000, fix_type=1,
                  lat=0, lon=0, alt=0, vel=0, cog=0))
    cv = ad.sample(t_mono=2.0).get("gnss.position")
    assert not cv.usable
    assert cv.value is None
    assert cv.missing in (MissingReason.NO_3D_FIX, MissingReason.NOT_RECEIVED)


@pytest.mark.parametrize("platform", sorted(ADAPTERS))
def test_absent_battery_cells_are_excluded_from_the_sum(platform):
    ad = get_adapter(platform)
    ad.ingest(msg("BATTERY_STATUS", time_boot_ms=1000,
                  voltages=[3700, 3700, 3700, 3700, 65535, 65535,
                            65535, 65535, 65535, 65535],
                  current_battery=1500))
    cv = ad.sample(t_mono=1.0).get("battery.voltage")
    assert cv.value == pytest.approx(14.8)          # 4 cells, not 4 + 6x65 V


@pytest.mark.parametrize("platform", sorted(ADAPTERS))
def test_current_not_measured_is_missing_not_zero(platform):
    ad = get_adapter(platform)
    ad.ingest(msg("BATTERY_STATUS", time_boot_ms=1000,
                  voltages=[3700, 3700, 3700, 3700], current_battery=-1))
    cv = ad.sample(t_mono=1.0).get("battery.current")
    assert cv.value is None
    assert ad.counters["rejected_sentinel"] >= 1


@pytest.mark.parametrize("platform", sorted(ADAPTERS))
def test_gcs_heartbeat_does_not_set_armed_state(platform):
    ad = get_adapter(platform)
    ad.ingest(msg("HEARTBEAT", type=6, base_mode=128, custom_mode=0))
    assert not ad.sample(t_mono=1.0).get("vehicle_status.armed").usable
    ad.ingest(msg("HEARTBEAT", type=2, base_mode=128, custom_mode=0))
    assert ad.sample(t_mono=1.0).get("vehicle_status.armed").value is True


def test_all_zero_magnetometer_is_absent_not_a_zero_field():
    ad = get_adapter("ardupilot")
    ad.ingest(msg("SCALED_IMU", time_boot_ms=1000, xacc=1, yacc=1, zacc=1,
                  xmag=0, ymag=0, zmag=0))
    assert not ad.sample(t_mono=1.0).get("mag.field_ut").usable


@pytest.mark.parametrize("platform", sorted(ADAPTERS))
def test_nan_never_reaches_the_core(platform):
    ad = get_adapter(platform)
    ad.ingest(msg("SCALED_IMU" if platform == "ardupilot" else "HIGHRES_IMU",
                  time_usec=1_000_000,
                  xacc=float("nan"), yacc=0, zacc=0,
                  xgyro=0, ygyro=0, zgyro=0))
    s = ad.sample(t_mono=1.0)
    assert not s.get("imu0.accel").usable
    for _sensor, _t, ch in ad.to_core_samples(s):
        for v in ch.values():
            assert not np.any(np.isnan(np.asarray(v, dtype=float)))


# --------------------------------------------------------------------------
# Freshness

def test_stale_channel_becomes_missing_with_a_reason():
    clock = {"t": 0.0}
    ad = get_adapter("ardupilot", clock=lambda: clock["t"])
    ad.ingest(msg("SCALED_IMU", time_boot_ms=0, xacc=0, yacc=0, zacc=-1000))
    assert ad.sample(t_mono=0.0).get("imu0.accel").usable
    clock["t"] = 10.0
    cv = ad.sample(t_mono=10.0).get("imu0.accel")
    assert cv.missing is MissingReason.STALE
    assert "exceeds" in cv.note


def test_adapter_holds_one_value_per_channel():
    """Acceptance criterion: no unbounded queues."""
    ad = get_adapter("ardupilot")
    for i in range(5000):
        ad.ingest(msg("SCALED_IMU", time_boot_ms=i, xacc=i, yacc=0, zacc=-1000))
    assert len(ad._latest) <= 20


# --------------------------------------------------------------------------
# Isolation: platform names must not escape the adapter

def test_canonical_sample_exposes_no_platform_field_names():
    ad = get_adapter("ardupilot")
    ad.ingest(msg("SCALED_IMU", time_boot_ms=1000, xacc=0, yacc=0, zacc=-1000))
    banned = ("xacc", "SCALED_IMU", "HIGHRES_IMU", "GPS_RAW_INT",
              "press_abs", "current_battery", "vibration_x")
    blob = repr(ad.sample(t_mono=1.0).to_log_dict())
    for name in banned:
        assert name not in blob, f"platform field name {name!r} leaked"


def test_unmapped_message_types_are_counted_not_silently_dropped():
    ad = get_adapter("ardupilot")
    ad.ingest(msg("SYS_STATUS", time_boot_ms=1))
    ad.ingest(msg("SYS_STATUS", time_boot_ms=2))
    assert ad.unmapped_types()["SYS_STATUS"] == 2


def test_partial_sensor_is_withheld_from_the_core():
    """Half a GPS fix is a fabricated fix, not a degraded one."""
    ad = get_adapter("ardupilot")
    ad.ingest(msg("GPS_RAW_INT", time_usec=1_000_000, fix_type=3,
                  lat=473_000_000, lon=85_000_000, alt=500_000,
                  vel=None, cog=None))
    core = dict((s, ch) for s, _t, ch in
                ad.to_core_samples(ad.sample(t_mono=1.0)))
    assert "gps" not in core


def test_flight_mode_decoding_differs_by_platform():
    ap = get_adapter("ardupilot")
    ap.ingest(msg("HEARTBEAT", type=2, base_mode=128, custom_mode=9))
    assert ap.sample(t_mono=1.0).flight_mode == "LAND"
    px = get_adapter("px4")
    px.ingest(msg("HEARTBEAT", type=2, base_mode=128,
                  custom_mode=(4 << 16) | (6 << 24)))
    assert px.sample(t_mono=1.0).flight_mode == "AUTO.LAND"


def test_estimator_channels_never_enter_the_core():
    ad = get_adapter("ardupilot")
    ad.ingest(msg("EKF_STATUS_REPORT", time_boot_ms=1000,
                  velocity_variance=0.2, pos_horiz_variance=0.3,
                  pos_vert_variance=0.1, compass_variance=0.05))
    s = ad.sample(t_mono=1.0)
    assert s.estimator_health["estimator.variances"].missing is not None
    assert all(sensor != "_autopilot_reference"
               for sensor, _t, _ch in ad.to_core_samples(s))
