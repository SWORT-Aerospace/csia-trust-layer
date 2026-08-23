"""map_mavlink unit tests: armed heartbeat, GPS vz validity, FC-reboot
re-anchoring. Pure-function tests — no pymavlink required."""

import numpy as np

from csia.runtime.plugins import map_mavlink


class _Msg:
    def __init__(self, mtype, **kw):
        self._mtype = mtype
        self.__dict__.update(kw)

    def get_type(self):
        return self._mtype


def _imu(t_ms):
    return _Msg("SCALED_IMU", time_boot_ms=t_ms,
                xacc=0, yacc=0, zacc=-1000, xgyro=0, ygyro=0, zgyro=0,
                xmag=0, ymag=0, zmag=0)


def test_heartbeat_armed_flag_and_gcs_ignored():
    ctx = {"t0": None}
    map_mavlink(_imu(1000), ctx)   # establish the time epoch
    out = map_mavlink(_Msg("HEARTBEAT", type=2, base_mode=128 | 16), ctx)
    assert out == [("vehicle_status", 0.0, {"armed": True})]
    out = map_mavlink(_Msg("HEARTBEAT", type=2, base_mode=16), ctx)
    assert out == [("vehicle_status", 0.0, {"armed": False})]
    # GCS heartbeats (MAV_TYPE_GCS=6) must not masquerade as vehicle state
    assert map_mavlink(_Msg("HEARTBEAT", type=6, base_mode=0), ctx) == []


def test_heartbeat_before_any_timestamp_is_dropped():
    ctx = {"t0": None}
    assert map_mavlink(_Msg("HEARTBEAT", type=2, base_mode=128), ctx) == []


def test_gps_raw_int_marks_vz_invalid():
    ctx = {"t0": None}
    map_mavlink(_imu(1000), ctx)
    out = map_mavlink(_Msg("GPS_RAW_INT", time_usec=1_100_000, fix_type=3,
                           lat=400000000, lon=-750000000, alt=50_000,
                           vel=500, cog=9000), ctx)
    (name, _t, ch), = out
    assert name == "gps"
    assert ch["valid"] is True
    assert ch["vz_valid"] is False, \
        "GPS_RAW_INT has no vertical rate; the mapping must say so"
    assert ch["vel"][2] == 0.0


def test_reboot_reanchors_epoch_monotonic():
    """An FC reboot restarts boot time; downstream time must stay
    monotonic (previously every post-reboot sample was dropped forever)."""
    ctx = {"t0": None}
    ts = []
    for t_ms in (1000, 2000, 5000, 10_000):
        out = map_mavlink(_imu(t_ms), ctx)
        ts.append(out[0][1])
    for t_ms in (500, 1500, 2500):    # reboot: boot clock restarted
        out = map_mavlink(_imu(t_ms), ctx)
        assert out, "post-reboot samples must not be dropped"
        ts.append(out[0][1])
    assert all(b > a for a, b in zip(ts, ts[1:])), \
        f"stream time not monotonic across reboot: {ts}"
