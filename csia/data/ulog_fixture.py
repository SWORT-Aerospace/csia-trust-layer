"""Synthetic ULog fixture writer — TEST INFRASTRUCTURE ONLY.

Writes a minimal, pyulog-parseable ULog so PX4 ingestion can be VALIDATED
locally while real corpora are network-blocked. The fixture is clearly
synthetic (ver_sw declares it); it must never be counted as flight data,
exposure, or evidence. Format per the public ULog spec (header, B flag bits,
F formats, I info, A subscriptions, D data).
"""

import io
import struct


def _msg(buf, mtype, payload):
    buf.write(struct.pack("<HB", len(payload), ord(mtype)) + payload)


def write_fixture(path: str, n_imu: int = 250, rate_hz: float = 250.0,
                  n_estimators: int = 2, drop_system_power: bool = False,
                  inject_gap_at: int | None = None) -> str:
    """Two vehicle_imu instances, N estimator_status instances, battery,
    system_power (optional — its absence tests missing-topic handling),
    vehicle_status. Returns path."""
    buf = io.BytesIO()
    buf.write(b"ULog\x01\x12\x35" + bytes([1]) + struct.pack("<Q", 0))
    _msg(buf, "B", bytes(16) + struct.pack("<3Q", 0, 0, 0))

    fmts = [
        b"vehicle_imu:uint64_t timestamp;float[3] delta_velocity;"
        b"float[3] delta_angle;uint32_t accel_device_id;"
        b"uint32_t gyro_device_id;uint8_t delta_velocity_clipping;",
        b"estimator_status:uint64_t timestamp;float[3] test_ratio;"
        b"float pos_horiz_accuracy;uint16_t filter_fault_flags;"
        b"uint8_t reset_count_vel_ne;",
        b"estimator_innovations:uint64_t timestamp;float[2] gps_hvel;"
        b"float gps_vvel;float[2] gps_hpos;float gps_vpos;",
        b"battery_status:uint64_t timestamp;float voltage_v;float current_a;"
        b"uint8_t warning;",
        b"system_power:uint64_t timestamp;float voltage5v_v;"
        b"uint8_t brick_valid;uint8_t usb_connected;",
        b"vehicle_status:uint64_t timestamp;uint8_t arming_state;"
        b"uint8_t nav_state;",
    ]
    for f in fmts:
        _msg(buf, "F", f)

    val = b"v1.14.0-CSIA-SYNTHETIC-FIXTURE"
    key = f"char[{len(val)}] ver_sw".encode()
    _msg(buf, "I", bytes([len(key)]) + key + val)
    val2 = b"csia_fixture"
    key2 = f"char[{len(val2)}] sys_name".encode()
    _msg(buf, "I", bytes([len(key2)]) + key2 + val2)

    msgid = 0
    subs = []
    for inst in range(2):
        subs.append((inst, msgid, b"vehicle_imu")); msgid += 1
    for inst in range(n_estimators):
        subs.append((inst, msgid, b"estimator_status")); msgid += 1
    for inst in range(n_estimators):
        subs.append((inst, msgid, b"estimator_innovations")); msgid += 1
    subs.append((0, msgid, b"battery_status")); bat_id = msgid; msgid += 1
    if not drop_system_power:
        subs.append((0, msgid, b"system_power")); pwr_id = msgid; msgid += 1
    subs.append((0, msgid, b"vehicle_status")); vs_id = msgid; msgid += 1
    for mid, mi, name in subs:
        _msg(buf, "A", struct.pack("<BH", mid, mi) + name)

    dt_us = int(1e6 / rate_hz)
    for k in range(n_imu):
        if inject_gap_at is not None and inject_gap_at <= k < inject_gap_at + 25:
            continue                       # 25-sample gap: quality-report food
        ts = 1_000_000 + k * dt_us
        for inst in range(2):
            _msg(buf, "D", struct.pack("<H", inst) + struct.pack("<Q", ts)
                 + struct.pack("<6f", 0.0, 0.0, 9.81 * dt_us * 1e-6 * (1 + 0.001 * inst),
                               0.0, 0.0, 0.0)
                 + struct.pack("<II", 1310988 + inst, 1310996 + inst)
                 + bytes([0]))
        if k % 10 == 0:
            for e in range(n_estimators):
                _msg(buf, "D", struct.pack("<H", 2 + e) + struct.pack("<Q", ts)
                     + struct.pack("<3f", 0.3, 0.25, 0.2 + 0.05 * e)
                     + struct.pack("<f", 0.8) + struct.pack("<H", 0) + bytes([0]))
                _msg(buf, "D", struct.pack("<H", 2 + n_estimators + e)
                     + struct.pack("<Q", ts)
                     + struct.pack("<6f", 0.1, -0.1, 0.05, 0.2, -0.2, 0.1))
            _msg(buf, "D", struct.pack("<H", bat_id) + struct.pack("<Q", ts)
                 + struct.pack("<2f", 15.9, 12.0) + bytes([0]))
            if not drop_system_power:
                _msg(buf, "D", struct.pack("<H", pwr_id) + struct.pack("<Q", ts)
                     + struct.pack("<f", 5.02) + bytes([1, 0]))
            _msg(buf, "D", struct.pack("<H", vs_id) + struct.pack("<Q", ts)
                 + bytes([2, 4]))
    with open(path, "wb") as fh:
        fh.write(buf.getvalue())
    return path
