"""ArduPilot adapter.

Verified against **ArduCopter V4.8.0-dev @ 01a504b**. Field names, units and
sentinel semantics come from `docs/simulation/CHANNEL_SEMANTICS.yaml`, which
cites the ArduPilot source line for each.

ArduPilot-specific traps this adapter handles, each of which cost us a run at
some point:

* `SCALED_IMU*` is milli-g and milli-rad/s and milli-gauss. PX4's `HIGHRES_IMU`
  is SI. Mixing them silently scales accelerations by ~1000.
* `GPS_RAW_INT.fix_type < 3` is **not** a position of zero. Encoding it as one
  injects a fictitious jump of ~5000 km from the local origin.
* `BATTERY_STATUS.current_battery == -1` means "not measured", not 0 A.
* `voltages[i] == 65535` means "cell not present" and must be excluded from
  the pack sum, not added as 65 V.
* A `HEARTBEAT` from `MAV_TYPE_GCS` (6) is the ground station's, not the
  vehicle's. Reading its `base_mode` asserts an armed state the aircraft never
  reported.
"""

from __future__ import annotations

import numpy as np

from ..sample import SensorFrame
from .base import PlatformAdapter, finite

MAV_MODE_FLAG_SAFETY_ARMED = 128
MAV_TYPE_GCS = 6
CELL_ABSENT = 65535
CURRENT_NOT_MEASURED = -1

# ArduCopter custom_mode -> name. Only the modes that matter for reading a
# shadow log; anything else is reported by number rather than guessed at.
COPTER_MODES = {
    0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED",
    5: "LOITER", 6: "RTL", 7: "CIRCLE", 9: "LAND", 11: "DRIFT",
    13: "SPORT", 14: "FLIP", 15: "AUTOTUNE", 16: "POSHOLD", 17: "BRAKE",
    18: "THROW", 19: "AVOID_ADSB", 20: "GUIDED_NOGPS", 21: "SMART_RTL",
    22: "FLOWHOLD", 23: "FOLLOW", 24: "ZIGZAG", 25: "SYSTEMID",
    26: "AUTOROTATE", 27: "AUTO_RTL",
}


def _frd_to_zup(v) -> np.ndarray:
    """MAVLink body FRD -> CSIA body z-up: (x, -y, -z)."""
    a = np.asarray(v, dtype=float)
    return np.array([a[0], -a[1], -a[2]])


class ArduPilotAdapter(PlatformAdapter):
    platform = "ardupilot"
    verified_against = "ArduCopter V4.8.0-dev @ 01a504b"

    # Every message type this adapter converts. Checked FIRST so an unwanted
    # type costs one set lookup instead of a walk down the dispatch chain.
    #
    # Measured need: a live SITL feed at 3,529 msg/s delivered 105,972
    # messages in 30 s of which 68,001 -- 64% -- were types CSIA does not
    # consume (AHRS, ATTITUDE, GLOBAL_POSITION_INT, MEMINFO, PARAM_VALUE,
    # NAV_CONTROLLER_OUTPUT and friends). Each one was paying for the full
    # if-chain before falling through.
    # Fast-path dispatch. THIS SET MUST MATCH THE BRANCHES BELOW.
    #
    # It did not. "RAW_IMU" was omitted when this set was introduced as a
    # performance optimization, so every RAW_IMU was counted unmapped and
    # discarded BEFORE reaching the handler written to process it -- 7,538 of
    # them in a 30 s live run. On ArduCopter 4.8 that message carries
    # inertial instance 0 AND compass instance 0, so the optimization silently
    # took imu0 and the magnetometer out of an 8-node trust graph, disabling
    # the dual-IMU cross-check and the heading_course relation.
    #
    # 631 tests passed throughout. `test_contract_producers_are_all_handled`
    # now ties this set to CHANNEL_SEMANTICS.yaml so the two cannot drift
    # again in either direction.
    HANDLED_TYPES = frozenset({
        "HEARTBEAT", "RAW_IMU", "SCALED_IMU", "SCALED_IMU2", "SCALED_IMU3",
        "SCALED_PRESSURE", "GPS_RAW_INT", "BATTERY_STATUS", "VIBRATION",
        "ESC_TELEMETRY_1_TO_4", "ESC_STATUS", "EKF_STATUS_REPORT",
    })

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
        if k not in self.HANDLED_TYPES:
            self._note_unmapped(k)
            return
        g = (lambda n, d=None: getattr(msg, n, d)) if hasattr(msg, "get_type") \
            else (lambda n, d=None: msg.get(n, d))
        t_src = self._source_time(g)

        if k == "HEARTBEAT":
            if g("type", MAV_TYPE_GCS) == MAV_TYPE_GCS:
                return                       # ground station, not the vehicle
            armed = bool(g("base_mode", 0) & MAV_MODE_FLAG_SAFETY_ARMED)
            self._put("vehicle_status.armed", armed, t_source=t_src)
            cm = g("custom_mode", None)
            if cm is not None:
                self._flight_mode = COPTER_MODES.get(int(cm), f"MODE_{cm}")
                self._put("estimator.flight_mode", self._flight_mode,
                          t_source=t_src)
            return

        # RAW_IMU and SCALED_IMU both carry inertial instance 0; SCALED_IMU2
        # is instance 1 and SCALED_IMU3 instance 2 (GCS_Common.cpp:6851-6861,
        # send_scaled_imu(0|1|2, ...)). Scaling is identical across all four:
        # accel * 1000 / GRAVITY_MSS, gyro * 1000, mag straight from
        # Compass::get_field() in milligauss.
        #
        # RAW_IMU was missing from the first version of this adapter, and a
        # live qualification run against ArduCopter 4.8 found it: imu0 and the
        # magnetometer never arrived at all, because the RAW_SENSORS stream
        # publishes RAW_IMU rather than SCALED_IMU. Reading the source rather
        # than assuming the name is why the units are right.
        if k in ("RAW_IMU", "SCALED_IMU", "SCALED_IMU2", "SCALED_IMU3"):
            node = {"RAW_IMU": "imu0", "SCALED_IMU": "imu0",
                    "SCALED_IMU2": "imu1", "SCALED_IMU3": "imu2"}[k]
            if node == "imu2":
                self._note_unmapped(k)       # third IMU is not a CSIA node
                return
            acc = [g("xacc", 0), g("yacc", 0), g("zacc", 0)]
            gyr = [g("xgyro", 0), g("ygyro", 0), g("zgyro", 0)]
            if all(finite(x) for x in acc):
                self._put(f"{node}.accel",
                          _frd_to_zup(acc) * 9.80665e-3,      # mG -> m/s^2
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="m/s^2")
            if all(finite(x) for x in gyr):
                self._put(f"{node}.gyro",
                          _frd_to_zup(gyr) * 1e-3,            # mrad/s -> rad/s
                          t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                          unit="rad/s")
            if node == "imu0":
                mag = [g("xmag", 0), g("ymag", 0), g("zmag", 0)]
                # An all-zero triple is ABSENT, not a zero field. A real
                # magnetometer never reads exactly zero on all three axes.
                if any(mag) and all(finite(x) for x in mag):
                    self._put("mag.field_ut",
                              _frd_to_zup(mag) * 0.1,          # mgauss -> uT
                              t_source=t_src, frame=SensorFrame.BODY_Z_UP,
                              unit="uT")
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
                self._put("baro.temp_c", float(temp) / 100.0, t_source=t_src,
                          unit="degC")
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

        if k in ("ESC_TELEMETRY_1_TO_4", "ESC_STATUS"):
            rpm = np.asarray(list(g("rpm", []))[:4], dtype=float)
            cur = np.asarray(list(g("current", [0] * 4))[:4], dtype=float)
            if k == "ESC_TELEMETRY_1_TO_4":
                cur = cur / 100.0                              # cA -> A
            if rpm.size:
                self._put("esc.rpm", rpm, t_source=t_src, unit="rpm")
            if cur.size:
                self._put("esc.current", cur, t_source=t_src, unit="A")
            return

        if k == "EKF_STATUS_REPORT":
            self._put("estimator.variances", {
                "velocity_variance": g("velocity_variance", None),
                "pos_horiz_variance": g("pos_horiz_variance", None),
                "pos_vert_variance": g("pos_vert_variance", None),
                "compass_variance": g("compass_variance", None),
                "terrain_alt_variance": g("terrain_alt_variance", None),
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
            # Explicitly forget the previous fix rather than let it age out
            # slowly: a lost fix is information, and a stale position that
            # keeps looking fresh for a second is a lie about the present.
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
            # No vertical rate exists in GPS_RAW_INT. The third component is
            # padding; gnss.velocity_z is UNAVAILABLE in the contract and the
            # core is told vz_valid=False.
            vel = np.array([spd * np.cos(cog), -spd * np.sin(cog), 0.0])
            if all(finite(x) for x in vel):
                self._put("gnss.velocity", vel, t_source=t_src,
                          frame=SensorFrame.WORLD_Z_UP, unit="m/s")
