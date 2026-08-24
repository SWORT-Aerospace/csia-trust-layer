"""PX4 adapter.

Verified against **PX4-Autopilot @ 547e2ca**, `px4_sitl_default`.

PX4 is not ArduPilot with different names. The differences that matter:

* `HIGHRES_IMU` is **SI already** -- m/s^2, rad/s, gauss. Applying ArduPilot's
  milli-scaling here is a silent 1000x error, so the two adapters share no
  scaling code on purpose.
* PX4's magnetometer arrives inside `HIGHRES_IMU` in **gauss** (x100 -> uT),
  where ArduPilot's arrives inside `SCALED_IMU` in **milligauss** (x0.1 -> uT).
* Estimator health is `ESTIMATOR_STATUS` with normalised innovation *ratios*,
  not `EKF_STATUS_REPORT` variances. They are not interchangeable and are
  logged under the same channel with the source recorded.
* `HIGHRES_IMU.fields_updated` is a bitmask saying which fields in *this*
  message are fresh. A field whose bit is clear is a repeat of the last value,
  not a new measurement.
* PX4 flight modes are encoded in the upper bytes of `custom_mode` (main mode
  and sub mode), not as a flat enum.
"""

from __future__ import annotations

import numpy as np

from ..sample import SensorFrame
from .base import PlatformAdapter, finite

MAV_MODE_FLAG_SAFETY_ARMED = 128
MAV_TYPE_GCS = 6
CELL_ABSENT = 65535
CURRENT_NOT_MEASURED = -1

# HIGHRES_IMU.fields_updated bits (common.xml HIL_SENSOR/HIGHRES_IMU).
FIELD_XACC, FIELD_XGYRO, FIELD_XMAG = 0b1, 0b1000, 0b1000000

PX4_MAIN_MODES = {
    1: "MANUAL", 2: "ALTCTL", 3: "POSCTL", 4: "AUTO", 5: "ACRO",
    6: "OFFBOARD", 7: "STABILIZED", 8: "RATTITUDE",
}
PX4_SUB_MODES = {
    1: "READY", 2: "TAKEOFF", 3: "LOITER", 4: "MISSION", 5: "RTL",
    6: "LAND", 7: "RTGS", 8: "FOLLOW_TARGET", 9: "PRECLAND",
}


def _frd_to_zup(v) -> np.ndarray:
    a = np.asarray(v, dtype=float)
    return np.array([a[0], -a[1], -a[2]])


def _decode_mode(custom_mode: int) -> str:
    main = (custom_mode >> 16) & 0xFF
    sub = (custom_mode >> 24) & 0xFF
    name = PX4_MAIN_MODES.get(main, f"MAIN_{main}")
    if main == 4 and sub:
        return f"AUTO.{PX4_SUB_MODES.get(sub, sub)}"
    return name


class PX4Adapter(PlatformAdapter):
    platform = "px4"
    verified_against = "PX4-Autopilot @ 547e2ca (px4_sitl_default)"

    def __init__(self, **kw):
        super().__init__(**kw)
        self._origin = None

    # ------------------------------------------------------------------
    def ingest(self, msg) -> None:
        self.counters["messages"] += 1
        # pymavlink dicts carry the message name in "mavpackettype";
        # "type" is a real HEARTBEAT field and must not be shadowed.
        k = (msg.get_type() if hasattr(msg, "get_type")
             else msg["mavpackettype"])
        g = (lambda n, d=None: getattr(msg, n, d)) if hasattr(msg, "get_type") \
            else (lambda n, d=None: msg.get(n, d))
        t_src = self._source_time(g)

        if k == "HEARTBEAT":
            if g("type", MAV_TYPE_GCS) == MAV_TYPE_GCS:
                return
            armed = bool(g("base_mode", 0) & MAV_MODE_FLAG_SAFETY_ARMED)
            self._put("vehicle_status.armed", armed, t_source=t_src)
            cm = g("custom_mode", None)
            if cm is not None:
                self._flight_mode = _decode_mode(int(cm))
                self._put("estimator.flight_mode", self._flight_mode,
                          t_source=t_src)
            return

        if k == "HIGHRES_IMU":
            updated = g("fields_updated", None)

            def fresh(bit):
                # None means the autopilot did not populate the mask; accept
                # the value rather than discard a whole stream over it.
                return updated is None or bool(updated & bit)

            acc = [g("xacc", 0.0), g("yacc", 0.0), g("zacc", 0.0)]
            if fresh(FIELD_XACC) and all(finite(x) for x in acc):
                self._put("imu0.accel", _frd_to_zup(acc),      # already SI
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="m/s^2")
            gyr = [g("xgyro", 0.0), g("ygyro", 0.0), g("zgyro", 0.0)]
            if fresh(FIELD_XGYRO) and all(finite(x) for x in gyr):
                self._put("imu0.gyro", _frd_to_zup(gyr),       # already SI
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="rad/s")
            mag = [g("xmag", 0.0), g("ymag", 0.0), g("zmag", 0.0)]
            if fresh(FIELD_XMAG) and any(mag) and all(finite(x) for x in mag):
                self._put("mag.field_ut",
                          _frd_to_zup(mag) * 100.0,            # gauss -> uT
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="uT")
            return

        if k in ("SCALED_IMU2", "SCALED_IMU3"):
            if k == "SCALED_IMU3":
                self._note_unmapped(k)
                return
            acc = [g("xacc", 0), g("yacc", 0), g("zacc", 0)]
            gyr = [g("xgyro", 0), g("ygyro", 0), g("zgyro", 0)]
            if all(finite(x) for x in acc):
                self._put("imu1.accel", _frd_to_zup(acc) * 9.80665e-3,
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="m/s^2")
            if all(finite(x) for x in gyr):
                self._put("imu1.gyro", _frd_to_zup(gyr) * 1e-3,
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="rad/s")
            return

        if k == "SCALED_PRESSURE":
            from ...sensors.barometer import pressure_to_altitude
            p = g("press_abs", None)
            if p is not None and finite(p) and p > 0:
                alt = float(pressure_to_altitude(np.array([float(p)]))[0])
                self._put("baro.altitude", alt, t_source=t_src,
                          frame=SensorFrame.WORLD_Z_UP, unit="m")
            temp = g("temperature", None)
            if temp is not None and finite(temp):
                self._put("baro.temp_c", float(temp) / 100.0,
                          t_source=t_src, unit="degC")
            return

        if k == "GPS_RAW_INT":
            self._ingest_gps(g, t_src)
            return

        if k == "BATTERY_STATUS":
            volts = [v for v in (g("voltages", []) or [])
                     if 0 < v < CELL_ABSENT]
            if volts:
                self._put("battery.voltage", sum(volts) / 1e3,
                          t_source=t_src, unit="V")
            cur = g("current_battery", CURRENT_NOT_MEASURED)
            if cur is not None and cur != CURRENT_NOT_MEASURED and finite(cur):
                self._put("battery.current", float(cur) / 100.0,
                          t_source=t_src, unit="A")
            else:
                self.counters["rejected_sentinel"] += 1
            return

        if k == "VIBRATION":
            vx, vy, vz = (g("vibration_x", 0.0), g("vibration_y", 0.0),
                          g("vibration_z", 0.0))
            if all(finite(v) for v in (vx, vy, vz)):
                rms = float(np.linalg.norm([vx, vy, vz]) / np.sqrt(3.0))
                self._put("vibration.rms", rms, t_source=t_src, unit="m/s^2")
            return

        if k == "ESC_STATUS":
            rpm = np.asarray(list(g("rpm", []))[:4], dtype=float)
            cur = np.asarray(list(g("current", [0] * 4))[:4], dtype=float)
            if rpm.size:
                self._put("esc.rpm", rpm, t_source=t_src, unit="rpm")
            if cur.size:
                self._put("esc.current", cur, t_source=t_src, unit="A")
            return

        if k == "ESTIMATOR_STATUS":
            # Ratios, not variances. Recorded as such so a reader never
            # compares a PX4 ratio against an ArduPilot variance.
            self._put("estimator.variances", {
                "_source": "ESTIMATOR_STATUS(ratios)",
                "vel_ratio": g("vel_ratio", None),
                "pos_horiz_ratio": g("pos_horiz_ratio", None),
                "pos_vert_ratio": g("pos_vert_ratio", None),
                "mag_ratio": g("mag_ratio", None),
                "hagl_ratio": g("hagl_ratio", None),
                "flags": g("flags", None),
            }, t_source=t_src)
            return

        self._note_unmapped(k)

    # ------------------------------------------------------------------
    def _source_time(self, g):
        t_us = g("time_usec", None)
        if t_us:
            return float(t_us) / 1e6
        t_ms = g("time_boot_ms", None)
        if t_ms:
            return float(t_ms) / 1e3
        return None

    def _ingest_gps(self, g, t_src):
        fix = g("fix_type", 0)
        if fix is None or fix < 3:
            self._latest.pop("gnss.position", None)
            self._latest.pop("gnss.velocity", None)
            self.counters["rejected_sentinel"] += 1
            return
        lat, lon, alt = g("lat", None), g("lon", None), g("alt", None)
        if lat is None or lon is None or alt is None:
            return
        if self._origin is None:
            self._origin = (lat, lon, alt / 1e3)
        o = self._origin
        coslat = float(np.cos(np.deg2rad(o[0] * 1e-7)))
        pos = np.array([(lat - o[0]) * 1e-7 * 111_320.0,
                        -(lon - o[1]) * 1e-7 * 111_320.0 * coslat,
                        (alt / 1e3 - o[2])])
        if all(finite(x) for x in pos):
            self._put("gnss.position", pos, t_source=t_src,
                      frame=SensorFrame.WORLD_Z_UP, unit="m")
        vel_cms, cog_cdeg = g("vel", None), g("cog", None)
        if vel_cms is not None and cog_cdeg is not None:
            spd = float(vel_cms) / 100.0
            cog = float(np.deg2rad(float(cog_cdeg) / 100.0))
            vel = np.array([spd * np.cos(cog), -spd * np.sin(cog), 0.0])
            if all(finite(x) for x in vel):
                self._put("gnss.velocity", vel, t_source=t_src,
                          frame=SensorFrame.WORLD_Z_UP, unit="m/s")
