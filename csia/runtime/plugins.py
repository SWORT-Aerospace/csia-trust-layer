"""Source plugins: where samples come from.

A source yields ``(sensor, t, channels)`` tuples in timestamp order — the
contract documented in ``online.OnlineTrustLayer``. Ship one plugin per data
origin; the trust layer neither knows nor cares which one is attached:

  SimulatedFlightSource — the phase-1 simulator as a bench source (any
                          scenario from the catalog); deterministic.
  MavlinkSource         — real vehicle / SITL over MAVLink (SOW001 stack:
                          Pi 5 companion listening to the STM32H743 FC).
                          Requires pymavlink (optional extra, not installed
                          by default): pip install "csia-trust-layer[mavlink]"
"""

import logging
from abc import ABC, abstractmethod
from typing import Iterator

import numpy as np

log = logging.getLogger(__name__)

Sample = tuple  # (sensor: str, t: float, channels: dict)


class SourcePlugin(ABC):
    """Yield samples in non-decreasing timestamp order."""

    @abstractmethod
    def samples(self) -> Iterator[Sample]:
        ...

    def stop(self):
        pass


class SimulatedFlightSource(SourcePlugin):
    """Bench source: any scenario from csia.scenarios, replayed as a
    time-ordered event stream exactly as the sensors would deliver it."""

    def __init__(self, scenario: str = "clean", truth=None):
        from ..scenarios import SCENARIOS, sample_streams
        from ..sensors import generate_flight
        if scenario not in SCENARIOS:
            raise KeyError(f"unknown scenario {scenario!r}; "
                           f"available: {list(SCENARIOS)}")
        self.scenario = scenario
        _, self.faults = SCENARIOS[scenario]
        self.truth = truth if truth is not None else generate_flight()
        self.streams = sample_streams(self.truth, self.faults)
        self.duration = float(self.truth.t[-1])

    def samples(self) -> Iterator[Sample]:
        events = []
        for name, s in self.streams.items():
            if name == "vibration":
                # the online layer consumes the 10 Hz RMS envelope channel
                for i, t in enumerate(np.asarray(s["t_rms"])):
                    events.append((float(t), name,
                                   {"rms": float(s["rms"][i]), "valid": True}))
                continue
            t_arr = np.asarray(s["t"])
            keys = [k for k in s if k not in ("t",)]
            for i, t in enumerate(t_arr):
                ch = {}
                for k in keys:
                    v = np.asarray(s[k])
                    ch[k] = bool(v[i]) if k == "valid" else v[i]
                events.append((float(t), name, ch))
        events.sort(key=lambda e: e[0])
        for t, name, ch in events:
            yield name, t, ch




def _frd(v):
    """Body FRD -> z-up body (180-deg rotation about x)."""
    import numpy as _np
    return _np.array([v[0], -v[1], -v[2]], dtype=float)


def map_mavlink(msg, ctx: dict) -> list:
    """MAVLink message -> CSIA samples. Handles PX4 (HIGHRES_IMU) and
    ArduPilot (SCALED_IMU*) dialects; frames converted FRD/NED -> z-up
    (body (x,-y,-z), world (n,-e,-d)). ctx persists origin/time state.
    Validated against ArduPilot SITL (tools/sitl_validate.py)."""
    k = msg.get_type()
    t_us = getattr(msg, "time_usec", None)
    t = (t_us / 1e6) if t_us else getattr(msg, "time_boot_ms", 0) / 1e3
    if ctx.get("t0") is None and t > 0:
        ctx["t0"] = t
    if ctx.get("t0") is None:
        return []
    t = t - ctx["t0"]
    if t < 0:
        return []
    out = []
    if k == "HIGHRES_IMU":  # PX4 primary IMU, SI units
        out.append(("imu0", t, {
            "accel": _frd([msg.xacc, msg.yacc, msg.zacc]),
            "gyro": _frd([msg.xgyro, msg.ygyro, msg.zgyro]), "valid": True}))
        if getattr(msg, "xmag", 0.0) or getattr(msg, "ymag", 0.0):
            out.append(("mag", t, {   # gauss -> uT
                "field_ut": _frd([msg.xmag, msg.ymag, msg.zmag]) * 100.0,
                "valid": True}))
    elif k in ("SCALED_IMU", "SCALED_IMU2"):  # ArduPilot, mG / mrad/s / mgauss
        sensor = "imu0" if k == "SCALED_IMU" else "imu1"
        out.append((sensor, t, {
            "accel": _frd([msg.xacc, msg.yacc, msg.zacc]) * 9.80665e-3,
            "gyro": _frd([msg.xgyro, msg.ygyro, msg.zgyro]) * 1e-3,
            "valid": True}))
        if sensor == "imu0" and (msg.xmag or msg.ymag or msg.zmag):
            out.append(("mag", t, {
                "field_ut": _frd([msg.xmag, msg.ymag, msg.zmag]) * 0.1,
                "valid": True}))
    elif k == "SCALED_PRESSURE":
        from ..sensors.barometer import pressure_to_altitude
        import numpy as _np
        out.append(("baro", t, {
            "altitude": float(pressure_to_altitude(
                _np.array([msg.press_abs]))[0]),
            "temp_c": msg.temperature / 100.0, "valid": True}))
    elif k == "GPS_RAW_INT":
        # RAW receiver output — the correct thing for an integrity monitor
        # to watch. The EKF innovation-gates faults out of its fused output
        # (GLOBAL_POSITION_INT), hiding exactly what we exist to detect.
        import numpy as _np
        ctx["has_raw_gps"] = True
        if msg.fix_type < 3:
            out.append(("gps", t, {"pos": _np.zeros(3), "vel": _np.zeros(3),
                                   "valid": False}))
            return out
        if "origin" not in ctx:
            ctx["origin"] = (msg.lat, msg.lon, msg.alt / 10)
        o = ctx["origin"]
        coslat = _np.cos(_np.deg2rad(o[0] * 1e-7))
        cog = _np.deg2rad(msg.cog / 100.0)
        spd = msg.vel / 100.0
        out.append(("gps", t, {
            "pos": _np.array([(msg.lat - o[0]) * 1e-7 * 111_320.0,
                              -(msg.lon - o[1]) * 1e-7 * 111_320.0 * coslat,
                              (msg.alt / 10 - o[2]) / 1e2]),
            "vel": _np.array([spd * _np.cos(cog), -spd * _np.sin(cog), 0.0]),
            "valid": True}))
    elif k == "GLOBAL_POSITION_INT" and not ctx.get("has_raw_gps"):
        # fallback when the raw stream is unavailable (fused EKF output;
        # weaker for integrity monitoring — documented limitation)
        import numpy as _np
        if "origin" not in ctx:
            ctx["origin"] = (msg.lat, msg.lon, msg.alt)
        o = ctx["origin"]
        coslat = _np.cos(_np.deg2rad(o[0] * 1e-7))
        out.append(("gps", t, {
            "pos": _np.array([(msg.lat - o[0]) * 1e-7 * 111_320.0,
                              -(msg.lon - o[1]) * 1e-7 * 111_320.0 * coslat,
                              (msg.alt - o[2]) / 1e3]),
            "vel": _np.array([msg.vx, -msg.vy, -msg.vz]) / 100.0,
            "valid": True}))
    elif k == "BATTERY_STATUS":
        v = sum(x for x in msg.voltages if 0 < x < 65535) / 1e3
        out.append(("battery", t, {"voltage": v,
                                   "current": max(msg.current_battery, 0) / 100.0,
                                   "valid": True}))
    elif k == "VIBRATION":
        import numpy as _np
        rms = float(_np.linalg.norm([msg.vibration_x, msg.vibration_y,
                                     msg.vibration_z]) / _np.sqrt(3.0))
        out.append(("vibration", t, {"rms": rms, "valid": True}))
    elif k in ("ESC_TELEMETRY_1_TO_4", "ESC_STATUS"):
        import numpy as _np
        rpm = _np.array(list(msg.rpm)[:4], dtype=float)
        cur = _np.array(list(getattr(msg, "current", [0] * 4))[:4],
                        dtype=float)
        if k == "ESC_TELEMETRY_1_TO_4":
            cur = cur / 100.0  # cA -> A
        out.append(("motor_esc", t, {"rpm": rpm, "current": cur,
                                     "valid": True}))
    return out


# MAVLink message -> (sensor, channels) mapping for the SOW001 stack.
# Documented here even when pymavlink is absent, so the integration
# contract is reviewable without installing it.
MAVLINK_MESSAGE_MAP = {
    "HIGHRES_IMU":   "imu0 (accel m/s^2, gyro rad/s)",
    "SCALED_IMU2":   "imu1 (accel mG -> m/s^2, gyro mrad/s -> rad/s)",
    "SCALED_PRESSURE": "baro (press_abs hPa -> ISA altitude, temperature)",
    "SCALED_IMU3/MAG": "mag (xmag/ymag/zmag mgauss -> uT)",
    "GLOBAL_POSITION_INT": "gps pos (lat/lon/alt -> local m), vel (vx/vy/vz cm/s)",
    "ESC_STATUS":    "motor_esc (rpm, current A)",
    "BATTERY_STATUS": "battery (voltages mV, current_battery cA)",
    "VIBRATION":     "vibration (vibration_x/y/z -> rms m/s^2)",
}


class MavlinkSource(SourcePlugin):
    """Live vehicle / SITL source. EXPERIMENTAL: field mapping is written
    against MAVLink common.xml; validate against the actual FC stream
    (units and frames!) before trusting the numbers."""

    def __init__(self, conn: str = "udp:0.0.0.0:14550", timeout_s: float = 5.0):
        try:
            from pymavlink import mavutil
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "MavlinkSource requires pymavlink: "
                'pip install "csia-trust-layer[mavlink]"') from exc
        self._mavutil = mavutil
        self.conn_str = conn
        self.timeout_s = timeout_s
        self._running = False

    def samples(self) -> Iterator[Sample]:  # pragma: no cover - needs hardware
        m = self._mavutil.mavlink_connection(self.conn_str)
        log.info("MAVLink: waiting for heartbeat on %s", self.conn_str)
        m.wait_heartbeat(timeout=self.timeout_s)
        self._running = True
        ctx = {"t0": None}
        while self._running:
            msg = m.recv_match(blocking=True, timeout=self.timeout_s)
            if msg is None:
                log.warning("MAVLink: stream timed out")
                return
            yield from map_mavlink(msg, ctx)

    def stop(self):
        self._running = False
