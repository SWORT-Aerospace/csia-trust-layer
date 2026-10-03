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


def discover(log, est_log=None, calibration=None, mode: str = "2.3"):
    """-> (events, triggers, notices). `log` is a StockLog at stock rates.

    `mode` "2.3" is the historical discovery every 2.3 and PRIME report used;
    "prime1" is the PRIME-1 successor (`discover_prime1`)."""
    if mode == "prime1":
        events, trs, notices, _stats = discover_prime1(log, est_log, calibration)
        return events, trs, notices
    if mode != "2.3":
        raise ValueError(f"unknown discovery mode {mode!r}")
    from .adapters.px4_stock import load_calibration
    cal = (calibration or load_calibration())["calibration"]
    trs = propulsion_triggers(log, cal) + px4_triggers(log, est_log)
    notices = [V11_NOTICE]
    return cluster(trs), trs, notices


V11_NOTICE = {"producer_id": "cusum:v1_1_sequential", "source": "event discovery", "available": False,
              "why": "the frozen v1.1 CUSUM reads the v1 simulation's physics chi-square; a "
                     "PX4 log has none, so it cannot trigger here"}


# ------------------------------------------------------------------ PRIME-1 successor discovery
#: The two telemetry arms, as distinct event semantics (D-PRIME-2). The event layer says only
#: "this telemetry channel changed enough to warrant analysis"; it attributes nothing.
RPM_DEFICIT = "propulsion.rpm_deficit"
RPM_EXCESS = "propulsion.rpm_excess"
COMPENSATION = "propulsion.compensation_change"
ESC_OFFLINE = "px4.esc_offline"
#: PRIME C3's merge rule (supported by a real log, RR-10): a re-raised identical PX4 condition.
MERGE_S = 60.0
#: PX4's failure-injection manager announces a test-harness injection. That is ground truth,
#: not vehicle evidence: never a trigger, counted in a labelled debug field only.
HARNESS_PREFIX = "[failure_injection_manager]"
#: A compensation alarm opens an event only where the compensation claim itself could be
#: admitted: near-steady flight (peak body rate <= theta_steady) in its BEFORE and AFTER windows,
#: exactly the producer's validity condition (`adapters/px4_stock.py`). The change's own transient
#: lies between the two windows and does not count. PRIME C3's E2 used [onset - 5, onset + 0.5] s,
#: which includes the transient of a real loss; PRIME-1's development checks showed that drop a
#: hover loss's compensation alarm (2.3 V4).
STEADY_WINDOWS = ("BEFORE", "AFTER")
#: ...and the two windows must be the same flight condition: the net heading change from the
#: end of BEFORE to the start of AFTER (integrated body yaw rate) within this tolerance. A
#: commanded heading change between two steady holds moves the motor split in wind exactly as
#: a loss does (PRIME-1 development: 2.3/RB-001 EN4, 180 degree reversals in a 4 m/s wind).
#: DECLARED, NOT CALIBRATED: it separates commanded heading changes from the yaw transient a
#: motor loss leaves behind, which the yaw controller returns to the held heading.
HEADING_TOL_DEG = 15.0
SEMANTICS = {RPM_DEFICIT: "RPM_DEFICIT_EVENT", RPM_EXCESS: "RPM_EXCESS_EVENT",
             COMPENSATION: "COMPENSATION_CHANGE_EVENT", ESC_OFFLINE: "ESC_OFFLINE_EVENT"}


def _heading_change_deg(log, onset: float) -> float:
    """Net heading change (deg) from the end of BEFORE to the start of AFTER: the body
    yaw rate integrated over that interval (near-level flight), or NaN."""
    if not log.has("vehicle_angular_velocity"):
        return float("nan")
    av = log.topics["vehicle_angular_velocity"]
    a, b = onset + SS.WINDOWS["BEFORE"][1], onset + SS.WINDOWS["AFTER"][0]
    msk = (av["t"] >= a) & (av["t"] <= b)
    if msk.sum() < 2:
        return float("nan")
    t, wz = av["t"][msk], np.asarray(av["xyz[2]"], float)[msk]
    return float(np.degrees(np.sum(0.5 * (wz[1:] + wz[:-1]) * np.diff(t))))


def _steady_around(log, onset: float, theta) -> bool:
    if theta is None:
        return False
    peaks = [SS.peak_rate(log, onset, w) for w in STEADY_WINDOWS]
    if not all(math.isfinite(v) and v <= theta for v in peaks):
        return False
    dpsi = _heading_change_deg(log, onset)
    return math.isfinite(dpsi) and abs(dpsi) <= HEADING_TOL_DEG


def propulsion_triggers_prime1(log, cal) -> tuple:
    """-> (triggers, stats). One-sided CUSUMs (Page 1954) on the 2.3 statistics:
    RPM_DEFICIT on reference - q, RPM_EXCESS on q - reference (same k_tel, h_tel:
    the 2.3 rule calibrated them on |d|), and the compensation ratio, whose alarm
    counts only inside its own steadiness regime (its BEFORE and AFTER windows). A telemetry alarm
    counts only while the channel's own trailing reference is consistent with the
    other rotors (`releases.TELEMETRY_LEVEL_BAND`)."""
    from .releases import TELEMETRY_LEVEL_BAND as band
    ms = SS.motor_series(log)
    stats = {"compensation_alarms_outside_steadiness": 0, "telemetry_alarms_on_inconsistent_reference": 0}
    if ms is None:
        return [], stats
    out = []
    for m, dv in enumerate(SS.deviations(ms)):
        # the telemetry channel's own trailing reference (q is relative to the other rotors)
        ref = dv["d_tel"] + ms.q[:, m]
        arms = ((RPM_DEFICIT, dv["t_tel"], dv["d_tel"], cal["k_tel"], cal["h_tel"],
                 "telemetry response deficit (fraction)"),
                (RPM_EXCESS, dv["t_tel"], dv["d_tel_excess"], cal["k_tel"], cal["h_tel"],
                 "telemetry response excess (fraction)"),
                (COMPENSATION, dv["t_ctrl"], dv["d_ctrl"], cal["k_ctrl"], cal["h_ctrl"],
                 "compensation ratio rise"))
        for kind, tt, dd, k, h, unit in arms:
            alarms, S = SS.cusum(tt, dd, k, h)
            for onset, alarm, peak in alarms:
                if kind == COMPENSATION and not _steady_around(log, onset, cal.get("theta_steady")):
                    stats["compensation_alarms_outside_steadiness"] += 1
                    continue
                if kind in (RPM_DEFICIT, RPM_EXCESS):
                    # a change is only a change against a valid reference: once a channel's own
                    # reference disagrees grossly with the other rotors (a corruption already
                    # reported), its further excursions open no new telemetry event
                    j = min(int(np.searchsorted(tt, onset)), len(tt) - 1)
                    r = ref[j]
                    if not (math.isfinite(r) and 1.0 / band <= r <= band):
                        stats["telemetry_alarms_on_inconsistent_reference"] += 1
                        continue
                after = np.flatnonzero((tt > alarm) & (S == 0.0))
                cleared = float(tt[after[0]]) if after.size else None
                i = int(np.searchsorted(tt, alarm))
                mag = float(dd[i]) if i < len(dd) and math.isfinite(dd[i]) else None
                out.append(Trigger("stock_stats", kind, onset, alarm, m, mag, unit, cleared,
                                   {"cusum_peak": round(peak, 6), "k": k, "h": h,
                                    "semantics": SEMANTICS[kind]}))
    return out, stats


def esc_offline_triggers(log) -> list:
    """A rotor's bit in `esc_status.esc_online_flags` falling in flight: PX4 itself reports
    the ESC offline (its RPM is then not a measurement)."""
    es = log.topics.get("esc_status") or {}
    if "esc_online_flags" not in es or not len(es.get("t", [])):
        return []
    fl = log.in_flight(es["t"])
    flags = np.asarray(es["esc_online_flags"]).astype(np.int64)
    out = []
    for m in range(max(log.n_motors, 0)):
        off = ((flags >> m) & 1) == 0
        for t in _edges(es["t"], off, fl):
            out.append(Trigger("esc_status", ESC_OFFLINE, t, t, m,
                               detail={"semantics": SEMANTICS[ESC_OFFLINE]}))
    return out


def _condition_key(tr):
    d = tr.detail or {}
    return (tr.kind, d.get("text") or d.get("flag") or d.get("filter_fault_flags"), tr.motor)


def px4_triggers_prime1(log, est_log=None) -> tuple:
    """-> (triggers, stats): PX4's monitors as in 2.3, without test-harness messages, plus
    the ESC-offline edge, with re-raised identical conditions merged (MERGE_S)."""
    raw = px4_triggers(log, est_log) + esc_offline_triggers(log)
    stats = {"test_harness_messages_ignored": 0, "reraised_px4_conditions_merged": 0}
    out, last = [], {}
    for tr in sorted(raw, key=lambda x: (x.onset_t, x.kind, x.motor if x.motor is not None else -1)):
        if tr.kind == "px4.log_message" and str((tr.detail or {}).get("text", "")).startswith(HARNESS_PREFIX):
            stats["test_harness_messages_ignored"] += 1
            continue
        key = _condition_key(tr)
        if key in last and tr.onset_t - last[key] <= MERGE_S:
            last[key] = tr.onset_t
            stats["reraised_px4_conditions_merged"] += 1
            continue
        last[key] = tr.onset_t
        out.append(tr)
    return out, stats


def discover_prime1(log, est_log=None, calibration=None, resolution_s: float = 1e-6):
    """-> (events, triggers, notices, stats). PRIME-1's event discovery; every onset and
    alarm time on the analysis timebase (D-PRIME-1)."""
    from .adapters.px4_stock import load_calibration
    cal = (calibration or load_calibration())["calibration"]
    prop, s1 = propulsion_triggers_prime1(log, cal)
    px4, s2 = px4_triggers_prime1(log, est_log)
    scale = round(1.0 / resolution_s)
    trs = []
    for tr in prop + px4:
        tr.onset_t = round(tr.onset_t * scale) / scale
        tr.alarm_t = round(tr.alarm_t * scale) / scale
        trs.append(tr)
    stats = dict(s1, **s2, mode="prime1",
                 arms=sorted(SEMANTICS.values()), merge_s=MERGE_S, steady_windows=list(STEADY_WINDOWS),
                 heading_tolerance_deg=HEADING_TOL_DEG)
    return cluster(trs), trs, [V11_NOTICE], stats
