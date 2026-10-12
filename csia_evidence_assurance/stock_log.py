"""Stock PX4 log access for the 2.3 evidence bridge. OFFBOARD ONLY.

`StockLog.from_ulog(path)` reads the topics and fields the stock producers
and the event-discovery layer may use, and nothing else. It is data access,
not evidence: no claim is made here.

WHAT IS READ
------------
| topic | fields | used for |
|---|---|---|
| `actuator_motors` | `control[i]` | the allocator's per-motor command (COMMAND) |
| `esc_status` | `esc[i].esc_rpm`, `esc_current`, `esc_voltage`, `esc_errorcount`, `failures`; `esc_count`, `esc_online_flags` | the ESC's reported response (TELEMETRY RESPONSE) |
| `control_allocator_status` | `unallocated_torque[3]`, `unallocated_thrust[3]`, `actuator_saturation[i]`, `torque_setpoint_achieved`, `thrust_setpoint_achieved`, `handled_motor_failure_mask` | allocation |
| `rate_ctrl_status` | roll, pitch and yaw rate integrators | controller compensation (context) |
| `vehicle_angular_velocity` | `xyz` | vehicle physical response |
| `battery_status` (instance 0) | `voltage_v`, `current_a`, `current_average_a`, `remaining`, `warning`, `faults`, `connected` | power |
| `failure_detector_status` | flags, `motor_failure_mask`, `imbalanced_prop_metric` | PX4's own failure detector |
| `vehicle_land_detected` | `landed` | flight segments |
| `vehicle_status` | `arming_state` | flight segments |
| `cpuload` | `load` | compute (context) |

**Also read:** the initial parameters the producers declare as configuration
dependencies, and the PX4 log messages of level WARNING and above.

**Also read: the logger's own dropouts** (`dropouts`: start and length of
each gap the logger recorded), for log completeness (claim
LOG_COMPLETENESS): an output whose window overlaps a dropout, or a gap of
more than GAP_FACTOR times its topic's logging interval, is reported with
producer health UNAVAILABLE (`gap_in`).

**In-flight parameter changes are NOT read.** In a SITL campaign they are
how faults are injected (XSYS-001 sets `SIH_MOT_EFF1` at onset), so reading
them would hand the onset to the analysis.

DEFAULT-RATE EMULATION
----------------------
**The XSYS-001 logs are richer than an ordinary log.** They were recorded
with a custom topic list on top of the default profile:
- `esc_status` and `actuator_motors` at 250 Hz, where PX4 547e2ca's
  `add_default_topics` logs them at 10 Hz;
- `control_allocator_status` at 125 Hz, against 5 Hz.

`decimate(STOCK_INTERVAL_MS)` keeps, per topic, the first sample at or
after each interval boundary, as the logger's interval subscription does.
The stock evidence is evaluated at the default rates.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MAX_MOTORS = 8
#: A gap longer than this many logging intervals is a log gap (claim LOG_COMPLETENESS).
GAP_FACTOR = 3.0
_WARN_LEVELS = ("EMERGENCY", "ALERT", "CRITICAL", "ERROR", "WARNING")

#: PX4 547e2ca `add_default_topics()` intervals, ms, for a real board.
STOCK_INTERVAL_MS = {
    "actuator_motors": 100, "esc_status": 100, "control_allocator_status": 200,
    "rate_ctrl_status": 200, "vehicle_angular_velocity": 20, "battery_status": 200,
    "failure_detector_status": 100, "vehicle_land_detected": 0, "vehicle_status": 0,
    "cpuload": 0,
}

PARAMS = ("THR_MDL_FAC", "CA_ROTOR_COUNT", "IMU_GYRO_DNF_EN", "MPC_THR_HOVER",
          "BAT1_N_CELLS", "BAT1_V_EMPTY", "BAT1_V_CHARGED", "BAT_LOW_THR", "BAT_CRIT_THR",
          "FD_ACT_EN", "FD_FAIL_P", "FD_FAIL_R", "FD_IMB_PROP_THR", "SYS_HITL",
          "SENS_IMU_MODE", "MC_ROLLRATE_I", "MC_PITCHRATE_I") + tuple(
    f"CA_ROTOR{i}_{k}" for i in range(MAX_MOTORS) for k in ("PX", "PY", "CT", "KM"))


def _topic_fields(n_motors: int) -> dict:
    esc = []
    for i in range(n_motors):
        esc += [f"esc[{i}].esc_rpm", f"esc[{i}].esc_current", f"esc[{i}].esc_voltage",
                f"esc[{i}].esc_errorcount", f"esc[{i}].failures"]
    return {
        "actuator_motors": [f"control[{i}]" for i in range(n_motors)],
        "esc_status": ["esc_count", "esc_online_flags"] + esc,
        "control_allocator_status": (
            [f"unallocated_torque[{i}]" for i in range(3)]
            + [f"unallocated_thrust[{i}]" for i in range(3)]
            + [f"actuator_saturation[{i}]" for i in range(n_motors)]
            + ["torque_setpoint_achieved", "thrust_setpoint_achieved",
               "handled_motor_failure_mask"]),
        "rate_ctrl_status": ["rollspeed_integ", "pitchspeed_integ", "yawspeed_integ"],
        "vehicle_angular_velocity": ["xyz[0]", "xyz[1]", "xyz[2]"],
        "battery_status": ["voltage_v", "current_a", "current_average_a", "remaining",
                           "warning", "faults", "connected"],
        "failure_detector_status": ["fd_roll", "fd_pitch", "fd_alt", "fd_ext", "fd_arm_escs",
                                    "fd_battery", "fd_imbalanced_prop", "fd_motor",
                                    "motor_failure_mask", "imbalanced_prop_metric"],
        "vehicle_land_detected": ["landed"],
        "vehicle_status": ["arming_state", "failsafe", "nav_state"],
        "cpuload": ["load"],
    }


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class StockLog:
    origin: dict
    t0_us: int
    #: topic -> field -> array; every topic has "t" (seconds from log start)
    topics: dict
    params: dict
    #: PX4 log messages of level WARNING and above: (t, level, text)
    messages: list = field(default_factory=list)
    #: per topic: the sampling the arrays reflect ("as logged" or an interval)
    sampling: dict = field(default_factory=dict)
    #: the logger's recorded dropouts: (start s from log start, length s)
    dropouts: list = field(default_factory=list)

    @property
    def n_motors(self) -> int:
        n = self.params.get("CA_ROTOR_COUNT")
        return int(n) if n is not None else 0

    def has(self, topic: str) -> bool:
        return topic in self.topics and len(self.topics[topic]["t"]) > 0

    # ------------------------------------------------------------ reading
    @classmethod
    def from_ulog(cls, path) -> "StockLog":
        from pyulog import ULog
        path = Path(path)
        names = list(STOCK_INTERVAL_MS)
        u = ULog(str(path), names, False)
        t0 = int(u.start_timestamp)
        params = {k: u.initial_parameters.get(k) for k in PARAMS}
        n = int(params["CA_ROTOR_COUNT"] or 0)
        want = _topic_fields(max(n, 1))
        topics = {}
        for d in u.data_list:
            if d.multi_id != 0 or d.name not in want or d.name in topics:
                continue
            out = {"t": (d.data["timestamp"].astype(np.int64) - t0) * 1e-6}
            for f in want[d.name]:
                if f in d.data:
                    out[f] = np.asarray(d.data[f], dtype=float)
            topics[d.name] = out
        msgs = [(round((int(m.timestamp) - t0) * 1e-6, 3), m.log_level_str(), m.message.strip())
                for m in u.logged_messages if m.log_level_str() in _WARN_LEVELS]
        drops = [(round((int(d.timestamp) - t0) * 1e-6, 6), round(int(d.duration) * 1e-3, 6))
                 for d in u.dropouts]
        return cls({"file": path.name, "sha256": _sha(path)}, t0, topics, params, msgs,
                   {k: "as logged" for k in topics}, drops)

    # ------------------------------------------------------------ rates
    def decimate(self, intervals_ms=None) -> "StockLog":
        """Keep the first sample at or after each interval boundary (0 =
        every sample), as the PX4 logger's interval subscription does."""
        intervals_ms = STOCK_INTERVAL_MS if intervals_ms is None else intervals_ms
        topics, sampling = {}, {}
        for name, d in self.topics.items():
            iv = intervals_ms.get(name)
            if not iv:
                topics[name], sampling[name] = d, self.sampling.get(name, "as logged")
                continue
            t = d["t"]
            keep, nxt = [], -np.inf
            for k in range(len(t)):
                if t[k] >= nxt:
                    keep.append(k)
                    nxt = t[k] + iv * 1e-3
            idx = np.asarray(keep, dtype=int)
            topics[name] = {f: v[idx] for f, v in d.items()}
            sampling[name] = f"decimated to {iv} ms"
        return StockLog(dict(self.origin), self.t0_us, topics, dict(self.params),
                        list(self.messages), sampling, list(self.dropouts))

    # ------------------------------------------------------------ cache
    def to_npz(self, path) -> None:
        flat = {f"{t}|{f}": v for t, d in self.topics.items() for f, v in d.items()}
        meta = {"origin": self.origin, "t0_us": self.t0_us, "params": self.params,
                "messages": self.messages, "sampling": self.sampling,
                "dropouts": self.dropouts}
        import json
        np.savez_compressed(path, __meta__=np.frombuffer(json.dumps(meta).encode(), np.uint8),
                            **flat)

    @classmethod
    def from_npz(cls, path) -> "StockLog":
        import json
        z = np.load(path)
        meta = json.loads(bytes(z["__meta__"]).decode())
        topics: dict = {}
        for k in z.files:
            if k == "__meta__":
                continue
            t, f = k.split("|", 1)
            topics.setdefault(t, {})[f] = z[k]
        origin = dict(meta["origin"], extract=Path(path).name)
        return cls(origin, meta["t0_us"], topics, meta["params"],
                   [tuple(m) for m in meta["messages"]], meta["sampling"],
                   [tuple(d) for d in meta.get("dropouts", [])])

    # ------------------------------------------------------------ helpers
    def gap_in(self, topic: str, a: float, b: float):
        """The first log gap touching [a, b) on `topic`, as a short text, or
        None. A gap is a logger dropout overlapping the span, or two
        consecutive samples further apart than GAP_FACTOR times the topic's
        logging interval (its stock interval, or the median spacing when the
        topic is logged on every publication)."""
        for s0, dur in self.dropouts:
            if s0 < b and s0 + dur > a:
                return f"logger dropout of {dur:.3f} s at {s0:.3f} s"
        d = self.topics.get(topic)
        if d is None or len(d["t"]) < 2:
            return None
        t = d["t"]
        iv = STOCK_INTERVAL_MS.get(topic) or 0
        step = iv * 1e-3 if iv else float(np.median(np.diff(t)))
        lo = max(int(np.searchsorted(t, a, side="right")) - 1, 0)
        hi = min(int(np.searchsorted(t, b, side="left")), len(t) - 1)
        if hi <= lo:
            return None
        gaps = np.diff(t[lo:hi + 1])
        k = int(np.argmax(gaps))
        if gaps[k] > GAP_FACTOR * step:
            return f"{topic}: no sample for {gaps[k]:.3f} s from {t[lo + k]:.3f} s"
        return None

    def in_flight(self, t: np.ndarray) -> np.ndarray:
        """True where the vehicle is armed and not landed (zero-order hold of
        `vehicle_status` and `vehicle_land_detected`). False where unknown."""
        out = np.zeros(len(t), dtype=bool)
        if not (self.has("vehicle_status") and self.has("vehicle_land_detected")):
            return out
        vs, ld = self.topics["vehicle_status"], self.topics["vehicle_land_detected"]
        ia = np.searchsorted(vs["t"], t, side="right") - 1
        il = np.searchsorted(ld["t"], t, side="right") - 1
        ok = (ia >= 0) & (il >= 0)
        armed = np.zeros(len(t), dtype=bool)
        landed = np.ones(len(t), dtype=bool)
        armed[ok] = vs["arming_state"][ia[ok]] == 2          # vehicle_status ARMING_STATE_ARMED
        landed[ok] = ld["landed"][il[ok]] > 0.5
        return armed & ~landed

    # ------------------------------------------------------------ coverage
    def coverage(self) -> dict:
        """Per topic the stock bridge reads: present, samples, median rate,
        the default logging interval, and which fields never vary (all
        zero, constant or all NaN) and so carry no evidence."""
        out = {}
        for name in sorted(STOCK_INTERVAL_MS):
            d = self.topics.get(name)
            if d is None or len(d["t"]) == 0:
                out[name] = {"present": False, "default_interval_ms": STOCK_INTERVAL_MS[name]}
                continue
            t = d["t"]
            dt = np.diff(t)
            silent = {}
            for f, v in sorted(d.items()):
                if f == "t":
                    continue
                v = np.asarray(v, float)
                if np.all(np.isnan(v)):
                    silent[f] = "all_nan"
                elif np.all(v[~np.isnan(v)] == 0):
                    silent[f] = "all_zero"
                elif np.all(v[~np.isnan(v)] == v[~np.isnan(v)][0]):
                    silent[f] = "constant"
            out[name] = {"present": True, "samples": int(len(t)),
                         "rate_hz": round(1.0 / float(np.median(dt)), 2) if dt.size else None,
                         "default_interval_ms": STOCK_INTERVAL_MS[name],
                         "sampling": self.sampling.get(name, "as logged"),
                         "fields_read": len(d) - 1, "fields_without_information": silent}
        return out
