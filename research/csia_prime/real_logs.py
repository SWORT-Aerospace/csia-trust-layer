#!/usr/bin/env python3
"""PRIME Track B1: the unchanged product on every real log reachable. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/real_logs.py

**The logs** (`REAL_DATA_ACQUISITION.md`):
- the four real-board pyulog test logs RB-001 used (and its two SITL ones,
  labelled);
- the PX4 documentation asset found in the PX4-Autopilot checkout at
  547e2ca: a real Pixhawk FMUv5 on a boat, PlotJuggler's sample log.

**Per log:**
- what recorded it: board, PX4 version, airframe (`SYS_AUTOSTART`),
  `vehicle_status.vehicle_type`, `CA_ROTOR_COUNT`, armed time;
- the product, unchanged (`runs.stock_flight` + `machine_report`):
  crash or not, events, every symptom raised at any time, final
  attribution, profile gate, records observed, coverage notices;
- **real timing against the product's own data-access rules (RR-04/05):**
  for each stock topic, the as-logged interval (median, p99, max), and the
  share of 15 s windows the 2.3 gap rule refuses
  - as the product does it (default-rate re-decimation, gap > 3 x the
    547e2ca default interval);
  - with RB-001's specified fix (no re-decimation of a topic already at or
    below its default rate; gap > 3 x the topic's own median interval);
- **PX4 warnings as events:** how many events one persistent condition
  makes (the battery warning's transitions).

Nothing is calibrated on these logs. Writes REAL_LOG_RESULTS.json.
"""
from __future__ import annotations

import traceback

import numpy as np

import common_prime as C
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from csia_evidence_assurance.stock_log import GAP_FACTOR, STOCK_INTERVAL_MS, StockLog

WINDOW_S = 15.0


def logs():
    out = []
    for p in sorted(C.REAL_PYULOG.glob("*.ulg")):
        out.append((p, "pyulog test corpus (PX4/pyulog, BSD-3)"))
    if C.REAL_PX4_DOCS.exists() and C.sha(C.REAL_PX4_DOCS) == C.REAL_PX4_DOCS_SHA:
        out.append((C.REAL_PX4_DOCS, "PX4-Autopilot docs asset at 547e2ca (PX4 docs, CC-BY-4.0)"))
    return out


def identity(path):
    from pyulog import ULog
    u = ULog(str(path), ["vehicle_status", "actuator_armed"], False)
    info = u.msg_info_dict
    D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
    vs = D.get("vehicle_status")
    vt, armed_s = None, 0.0
    if vs is not None and len(vs["timestamp"]) > 1:
        if "vehicle_type" in vs:
            vt = int(np.bincount(vs["vehicle_type"].astype(int)).argmax())
        t = (vs["timestamp"].astype(np.int64) - u.start_timestamp) * 1e-6
        a = vs["arming_state"] == 2
        armed_s = float(np.sum(np.diff(t)[a[:-1]]))
    hw = info.get("ver_hw", "")
    return {"hardware": hw, "real_hardware": not hw.startswith("PX4_SITL"),
            "px4_git": info.get("ver_sw", "")[:12], "release": info.get("ver_sw_release"),
            "sys_autostart": u.initial_parameters.get("SYS_AUTOSTART"),
            "mav_type": u.initial_parameters.get("MAV_TYPE"),
            "vehicle_status_vehicle_type": vt,
            "ca_rotor_count": u.initial_parameters.get("CA_ROTOR_COUNT"),
            "armed_s": round(armed_s, 1),
            "duration_s": round((u.last_timestamp - u.start_timestamp) * 1e-6, 1)}


def gap_rule_own_median(t, a, b):
    """RB-001's specified (unapplied) fix: gap > 3 x the topic's own median interval."""
    if len(t) < 3:
        return None
    step = float(np.median(np.diff(t)))
    lo = max(int(np.searchsorted(t, a, side="right")) - 1, 0)
    hi = min(int(np.searchsorted(t, b, side="left")), len(t) - 1)
    if hi <= lo:
        return None
    g = np.diff(t[lo:hi + 1])
    return float(g.max()) if g.max() > GAP_FACTOR * step else None


def timing(raw: StockLog, dec: StockLog):
    out = {}
    for topic, iv in STOCK_INTERVAL_MS.items():
        if not iv or not raw.has(topic):
            continue
        t = raw.topics[topic]["t"]
        if len(t) < 3:
            continue
        d = np.diff(t)
        span = (float(t[0]), float(t[-1]))
        starts = np.arange(span[0], span[1] - WINDOW_S, 1.0)
        refused_product = sum(dec.gap_in(topic, s, s + WINDOW_S) is not None for s in starts)
        own = t if np.median(d) * 1e3 >= iv else dec.topics[topic]["t"]
        refused_fix = sum(gap_rule_own_median(own, s, s + WINDOW_S) is not None for s in starts)
        out[topic] = {"default_interval_ms": iv,
                      "as_logged_interval_ms": {"median": round(float(np.median(d)) * 1e3, 2),
                                                "p99": round(float(np.percentile(d, 99)) * 1e3, 2),
                                                "max": round(float(d.max()) * 1e3, 2)},
                      "windows": len(starts),
                      "refused_by_product_gap_rule": int(refused_product),
                      "refused_with_rb001_fix": int(refused_fix)}
    return out


def warnings(raw: StockLog):
    """Battery-warning transitions: how often one condition is re-raised."""
    b = raw.topics.get("battery_status")
    if b is None or "warning" not in b:
        return None
    w = b["warning"].astype(int)
    rises = int(np.sum((w[1:] > 0) & (w[:-1] == 0)))
    return {"samples_in_warning": int(np.sum(w > 0)), "warning_rises": rises,
            "max_level": int(w.max()) if len(w) else 0,
            "voltage_range_v": [round(float(np.min(b["voltage_v"])), 2),
                                round(float(np.max(b["voltage_v"])), 2)] if "voltage_v" in b else None}


def product(path):
    run = R.stock_flight(path)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    any_time = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                       if c["what"] != "attribution" and c["to"]})
    kinds = {}
    for e in m["events"]:
        for k in e["trigger_kinds"]:
            kinds[k] = kinds.get(k, 0) + 1
    return {"events": len(m["events"]), "event_trigger_kinds": kinds,
            "symptoms_any_time": any_time,
            "attribution": m["summary"]["attribution"]["verdict"],
            "profile_gate": m["profile_gate"]["status"],
            "profile_records_observed": m["coverage_report"]["profile_records_observed"],
            "coverage_notices": [n["why"] for n in m["coverage_report"]["coverage_notices"]],
            "topics_absent": m["coverage_report"]["topics_absent"]}


def main():
    rows = {}
    for path, source in logs():
        row = {"file": path.name, "sha256": C.sha(path), "source": source}
        row.update(identity(path))
        try:
            row["product"] = product(path)
        except Exception as exc:  # noqa: BLE001 - a crash on a real log is itself a finding
            row["product"] = {"error": f"{type(exc).__name__}: {exc}",
                              "trace": traceback.format_exc()[-800:]}
        raw = StockLog.from_ulog(path)
        row["timing"] = timing(raw, raw.decimate())
        row["battery_warnings"] = warnings(raw)
        p = row["product"]
        if row["armed_s"] > 0 and "events" in p:
            row["events_per_armed_hour"] = round(p["events"] / (row["armed_s"] / 3600.0), 1)
        rows[path.name] = row
        print(path.name, row["hardware"], row["sys_autostart"], row["armed_s"],
              p.get("events", p.get("error")), p.get("symptoms_any_time"), flush=True)
    C.write_json(C.HERE / "REAL_LOG_RESULTS.json", {
        "label": "PRIME B1: the unchanged product on every real log reachable; nothing calibrated on them",
        "window_s": WINDOW_S, "logs": rows})


if __name__ == "__main__":
    main()
