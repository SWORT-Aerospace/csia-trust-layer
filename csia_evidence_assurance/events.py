"""Automatic event discovery (CSIA 2.3). OFFBOARD ONLY.

The question it answers is

    SOMETHING WORTH ANALYSING MAY HAVE STARTED HERE

and never "this motor failed". A discovered event only sets the time the
stock producers compare against (`adapters/px4_stock.py`). The diagnosis
stays with the producers, admissibility and Semantic Core 2.1.1.

TRIGGERS (mature methods only; no learned detector)
---------------------------------------------------
| source | kind | method | from |
|---|---|---|---|
| `stock_stats` telemetry response | `propulsion.telemetry_change` | one-sided CUSUM (Page 1954) per motor | `esc_status`, `actuator_motors` |
| `stock_stats` compensation ratio | `propulsion.compensation_change` | one-sided CUSUM per motor | `actuator_motors` |
| PX4 failure detector | `px4.failure_detector` | rising edge of any `fd_*` flag | `failure_detector_status` |
| PX4 battery warning | `px4.battery_warning` | rising edge of `warning` >= LOW | `battery_status` |
| PX4 control allocator | `px4.allocation_not_achieved` | setpoint not achieved or a motor saturated for >= 0.5 s | `control_allocator_status` |
| PX4 EKF2 | `px4.estimator_rejection` | a test ratio above 1.0 for >= 1 s, or a filter fault flag | `estimator_status` |
| PX4 commander | `px4.failsafe` | rising edge of `vehicle_status.failsafe` | `vehicle_status` |
| PX4 log messages | `px4.log_message` | a WARNING or worse while in flight | the ULog message log |
| frozen CUSUM (v1.1) | — | no input in a PX4 log (it reads the v1 simulation's physics chi-square); reported as NO_COVERAGE | — |

**Not triggers:**
- **In-flight parameter changes:** they are not read at all (`stock_log.py`).
- **EKF2 resets and aiding changes:** these are configuration context in
  the timeline. They happen in every flight around take-off (2.2 pilot:
  heading 3-axis fusion and height-source changes in 64/66 flights), and as
  triggers they would turn every take-off into an incident.

**Every trigger is in flight only:** armed and not landed.

CLUSTERING (Phase 14)
---------------------
Triggers are sorted by onset. A trigger joins the open cluster if its onset
is within GAP_S (3.0 s) of the cluster's latest trigger. Otherwise it opens
a new one.

The event time t0 is the earliest onset in the cluster. For a CUSUM trigger
that is the onset estimate: the last sample with S = 0 before the alarm.

**"Cleared" means something specific.** It is the time every CUSUM in the
cluster returned to zero, which happens when the trailing reference has
absorbed the new level. It means "the change is complete", not "the fault
went away".
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from . import stock_stats as SS

GAP_S = 3.0
ALLOC_HOLD_S = 0.5
EST_HOLD_S = 1.0
EST_GATE = 1.0
FAULT_MASK = 0xFFFF
EST_RATIOS = ("pos_test_ratio", "vel_test_ratio", "hgt_test_ratio", "hdg_test_ratio")


@dataclass
class Trigger:
    source: str
    kind: str
    onset_t: float
    alarm_t: float
    motor: int | None = None
    magnitude: float | None = None
    unit: str = ""
    cleared_t: float | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("onset_t", "alarm_t", "magnitude", "cleared_t"):
            if isinstance(d[k], float):
                d[k] = round(d[k], 6)
        return d


@dataclass
class Event:
    event_id: str
    t0: float
    first_alarm_t: float
    triggers: list
    cleared_t: float | None

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "t0": round(self.t0, 6),
                "first_alarm_t": round(self.first_alarm_t, 6),
                "cleared_t": None if self.cleared_t is None else round(self.cleared_t, 6),
                "trigger_kinds": sorted({t.kind for t in self.triggers}),
                "motors": sorted({t.motor for t in self.triggers if t.motor is not None}),
                "triggers": [t.to_dict() for t in self.triggers]}


def _edges(t, on, in_flight):
    """Times where `on` goes False -> True while in flight."""
    on = np.asarray(on, bool) & in_flight
    idx = np.flatnonzero(on[1:] & ~on[:-1]) + 1
    if on.size and on[0]:
        idx = np.concatenate([[0], idx])
    return [float(t[i]) for i in idx]


def _held(t, on, in_flight, hold_s):
    """(start, confirm) of runs where `on` holds for >= hold_s in flight."""
    on = np.asarray(on, bool) & in_flight
    out, start = [], None
    for i in range(len(t)):
        if on[i] and start is None:
            start = i
        if start is not None and (not on[i] or i == len(t) - 1):
            end = i if on[i] else i - 1
            if t[end] - t[start] >= hold_s:
                j = start + int(np.searchsorted(t[start:end + 1], t[start] + hold_s))
                out.append((float(t[start]), float(t[min(j, end)])))
            start = None
    return out


def propulsion_triggers(log, cal) -> list:
    ms = SS.motor_series(log)
    if ms is None:
        return []
    out = []
    for m, dv in enumerate(SS.deviations(ms)):
        for kind, tt, dd, k, h, unit in (
                ("propulsion.telemetry_change", dv["t_tel"], dv["d_tel"], cal["k_tel"], cal["h_tel"],
                 "telemetry response deficit (fraction)"),
                ("propulsion.compensation_change", dv["t_ctrl"], dv["d_ctrl"], cal["k_ctrl"],
                 cal["h_ctrl"], "compensation ratio rise")):
            alarms, S = SS.cusum(tt, dd, k, h)
            for onset, alarm, peak in alarms:
                after = np.flatnonzero((tt > alarm) & (S == 0.0))
                cleared = float(tt[after[0]]) if after.size else None
                i = int(np.searchsorted(tt, alarm))
                mag = float(dd[i]) if i < len(dd) and math.isfinite(dd[i]) else None
                out.append(Trigger("stock_stats", kind, onset, alarm, m, mag, unit, cleared,
                                   {"cusum_peak": round(peak, 6), "k": k, "h": h}))
    return out


def px4_triggers(log, est_log=None) -> list:
    out = []
    if log.has("failure_detector_status"):
        fd = log.topics["failure_detector_status"]
        fl = log.in_flight(fd["t"])
        for f in ("fd_roll", "fd_pitch", "fd_alt", "fd_ext", "fd_arm_escs", "fd_battery",
                  "fd_imbalanced_prop", "fd_motor"):
            if f in fd:
                for t in _edges(fd["t"], fd[f] != 0, fl):
                    out.append(Trigger("failure_detector_status", "px4.failure_detector", t, t,
                                       detail={"flag": f}))
    if log.has("battery_status"):
        b = log.topics["battery_status"]
        for t in _edges(b["t"], b["warning"] >= 1, log.in_flight(b["t"])):
            out.append(Trigger("battery_status", "px4.battery_warning", t, t))
    if log.has("control_allocator_status"):
        ca = log.topics["control_allocator_status"]
        bad = (ca["torque_setpoint_achieved"] == 0) | (ca["thrust_setpoint_achieved"] == 0)
        for m in range(log.n_motors):
            k = f"actuator_saturation[{m}]"
            if k in ca:
                bad = bad | (ca[k] != 0)
        for start, confirm in _held(ca["t"], bad, log.in_flight(ca["t"]), ALLOC_HOLD_S):
            out.append(Trigger("control_allocator_status", "px4.allocation_not_achieved",
                               start, confirm))
    if log.has("vehicle_status") and "failsafe" in log.topics["vehicle_status"]:
        vs = log.topics["vehicle_status"]
        for t in _edges(vs["t"], vs["failsafe"] != 0, log.in_flight(vs["t"])):
            out.append(Trigger("vehicle_status", "px4.failsafe", t, t))
    fl_t = log.topics["vehicle_status"]["t"] if log.has("vehicle_status") else None
    if fl_t is not None and len(fl_t):
        for (t, level, text) in log.messages:
            if bool(log.in_flight(np.array([t]))[0]):
                out.append(Trigger("log_message", "px4.log_message", t, t,
                                   detail={"level": level, "text": text}))
    if est_log is not None and est_log.status:
        inst = min(est_log.status)
        s = est_log.status[inst]
        t = (s["timestamp"].astype(np.int64) - est_log.t0_us) * 1e-6
        fl = log.in_flight(t)
        over = np.zeros(len(t), bool)
        for r in EST_RATIOS:
            v = np.asarray(s[r], float)
            over |= np.isfinite(v) & (v > EST_GATE)
        for start, confirm in _held(t, over, fl, EST_HOLD_S):
            out.append(Trigger("estimator_status", "px4.estimator_rejection", start, confirm,
                               detail={"gate": EST_GATE}))
        for tt in _edges(t, (s["filter_fault_flags"].astype(np.int64) & FAULT_MASK) != 0, fl):
            out.append(Trigger("estimator_status", "px4.estimator_rejection", tt, tt,
                               detail={"filter_fault_flags": True}))
    return out


def cluster(triggers, gap_s: float = GAP_S) -> list:
    trs = sorted(triggers, key=lambda x: (x.onset_t, x.alarm_t, x.kind, x.motor or -1))
    events, cur = [], []
    for tr in trs:
        if cur and tr.onset_t - max(c.onset_t for c in cur) > gap_s:
            events.append(cur)
            cur = []
        cur.append(tr)
    if cur:
        events.append(cur)
    out = []
    for i, grp in enumerate(events, 1):
        cl = [t.cleared_t for t in grp if t.source == "stock_stats"]
        cleared = None if (not cl or any(c is None for c in cl)) else max(cl)
        out.append(Event(f"E{i}", min(t.onset_t for t in grp), min(t.alarm_t for t in grp),
                         grp, cleared))
    return out


def discover(log, est_log=None, calibration=None):
    """-> (events, triggers, notices). `log` is a StockLog at stock rates."""
    from .adapters.px4_stock import load_calibration
    cal = (calibration or load_calibration())["calibration"]
    trs = propulsion_triggers(log, cal) + px4_triggers(log, est_log)
    notices = [{"producer_id": "cusum:v1_1_sequential", "source": "event discovery",
                "available": False,
                "why": "the frozen v1.1 CUSUM reads the v1 simulation's physics chi-square; a "
                       "PX4 log has none, so it cannot trigger here"}]
    return cluster(trs), trs, notices
