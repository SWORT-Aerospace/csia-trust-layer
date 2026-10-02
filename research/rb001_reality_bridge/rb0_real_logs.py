#!/usr/bin/env python3
"""RB0: what the reachable REAL PX4 logs show. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/rb0_real_logs.py

**The data.** The only real-hardware PX4 logs this session can reach are the
test logs of PX4's own `pyulog` repository (raw.githubusercontent.com; every
other log host and dataset host is blocked by the session's network policy,
ENVIRONMENT_AND_ACCESS.md). Fetched into /home/user/rb001_raw/github/ with
their SHA-256 recorded here. Two of the six are SITL and are labelled so.

**What is measured, per log:**
- what hardware and PX4 version recorded it, and whether it flew (armed and
  not landed);
- sensor noise at rest: gyro standard deviation and the peak body rate in
  5 s windows, against 2.3's theta_steady (0.0989 rad/s, from SIH hover);
- timing (Part 17): per-topic sampling interval median, jitter and largest
  gap; `timestamp` minus `timestamp_sample` where both exist; the logger's
  own dropouts;
- log completeness (Part 18): whether StockLog sees the dropouts and flags
  windows that overlap them;
- the product on it: `runs.stock_flight` (the 2.3 default for a .ulg) and
  what its report says it could and could not observe.

Nothing is calibrated on these logs: there are too few, of unknown
conditions, and none flew a propulsion fault.
Writes RB0_REAL_LOGS.json.
"""
from __future__ import annotations


import numpy as np

import common_rb as C

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from csia_evidence_assurance.stock_log import StockLog

GITHUB = C.OUT_RAW / "github"
SOURCE = "https://raw.githubusercontent.com/PX4/pyulog/main/test/"
THETA_STEADY = 0.09889434104510486
TIMING_TOPICS = ("sensor_combined", "vehicle_angular_velocity", "vehicle_attitude",
                 "actuator_outputs", "battery_status", "vehicle_status", "vehicle_local_position",
                 "esc_status", "actuator_motors")


def flight_summary(u):
    D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
    t0 = u.start_timestamp
    vs = D.get("vehicle_status")
    armed_s = 0.0
    if vs is not None:
        t = (vs["timestamp"].astype(np.int64) - t0) * 1e-6
        a = vs["arming_state"] == 2
        armed_s = float(np.sum(np.diff(t)[a[:-1]])) if len(t) > 1 else 0.0
    ld = D.get("vehicle_land_detected")
    airborne_s = None
    if ld is not None and len(ld["timestamp"]) > 1:
        t = (ld["timestamp"].astype(np.int64) - t0) * 1e-6
        ok = t >= 0
        t, landed = t[ok], ld["landed"][ok]
        end = (u.last_timestamp - t0) * 1e-6
        tt = np.append(t, end)
        airborne_s = float(np.sum(np.diff(tt)[landed == 0]))
    return {"armed_s": round(armed_s, 1),
            "airborne_s": None if airborne_s is None else round(airborne_s, 1)}


def gyro_noise(u):
    D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
    src = "vehicle_angular_velocity" if "vehicle_angular_velocity" in D else "sensor_combined"
    d = D[src]
    keys = ["xyz[0]", "xyz[1]", "xyz[2]"] if src == "vehicle_angular_velocity" else \
        ["gyro_rad[0]", "gyro_rad[1]", "gyro_rad[2]"]
    g = np.stack([np.asarray(d[k], float) for k in keys], 1)
    t = (d["timestamp"].astype(np.int64) - u.start_timestamp) * 1e-6
    ok = t >= 0
    t, g = t[ok], g[ok]
    peaks = []
    a = t[0] if len(t) else 0.0
    while len(t) and a + 5.0 <= t[-1]:
        m = (t >= a) & (t < a + 5.0)
        if m.sum() > 10:
            peaks.append(float(np.max(np.linalg.norm(g[m] - np.median(g[m], 0), axis=1))))
            peaks.append(float(np.max(np.linalg.norm(g[m], axis=1))))
        a += 5.0
    peaks_raw = peaks[1::2]
    return {"source": src, "std_rad_s": np.round(g.std(0), 5).tolist(),
            "bias_rad_s": np.round(np.median(g, 0), 5).tolist(),
            "windows_5s": len(peaks_raw),
            "peak_rate_rad_s": {"median": round(float(np.median(peaks_raw)), 4) if peaks_raw else None,
                                "max": round(float(np.max(peaks_raw)), 4) if peaks_raw else None},
            "windows_over_theta_steady": int(sum(p > THETA_STEADY for p in peaks_raw))}


def timing(u):
    out = {}
    for d in u.data_list:
        if d.multi_id or d.name not in TIMING_TOPICS:
            continue
        t = d.data["timestamp"].astype(np.int64)
        dt = np.diff(t) * 1e-6
        dt = dt[dt > 0]
        row = {"samples": int(len(t))}
        if dt.size:
            med = float(np.median(dt))
            row.update({"interval_median_ms": round(1e3 * med, 3),
                        "interval_p99_ms": round(1e3 * float(np.percentile(dt, 99)), 3),
                        "jitter_std_ms": round(1e3 * float(np.std(dt)), 3),
                        "largest_gap_ms": round(1e3 * float(dt.max()), 1),
                        "gaps_over_3x": int(np.sum(dt > 3 * med))})
        if "timestamp_sample" in d.data:
            lat = (t - d.data["timestamp_sample"].astype(np.int64)) * 1e-3
            lat = lat[(lat >= 0) & (lat < 1e4)]
            if lat.size:
                row["publish_minus_sample_ms"] = {"median": round(float(np.median(lat)), 3),
                                                  "p99": round(float(np.percentile(lat, 99)), 3)}
        out[d.name] = row
    return out


def product_view(path):
    run = R.stock_flight(path)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    f = m["final"] or {}
    return {"events": len(m["events"]),
            "trigger_kinds": sorted({k for e in m["events"] for k in e["trigger_kinds"]}),
            "headline": f.get("state", {}).get("headline"),
            "profile_records_observed": m["coverage_report"]["profile_records_observed"],
            "not_observed": m["summary"]["not_observed"],
            "topics_absent": m["coverage_report"]["topics_absent"]}


def main():
    from pyulog import ULog
    rows = {}
    for p in sorted(GITHUB.glob("*.ulg")):
        u = ULog(str(p))
        info = u.msg_info_dict
        hw = info.get("ver_hw", "")
        row = {"file": p.name, "source": SOURCE + p.name, "sha256": C.sha(p),
               "hardware": hw, "real_hardware": not hw.startswith("PX4_SITL"),
               "px4_git": info.get("ver_sw", "")[:12], "release": info.get("ver_sw_release"),
               "duration_s": round((u.last_timestamp - u.start_timestamp) * 1e-6, 1),
               "airframe": u.initial_parameters.get("SYS_AUTOSTART"),
               "logger_dropouts": {"count": len(u.dropouts),
                                   "total_ms": int(sum(d.duration for d in u.dropouts))}}
        row.update(flight_summary(u))
        row["gyro"] = gyro_noise(u)
        row["timing"] = timing(u)
        sl = StockLog.from_ulog(p)
        row["stocklog_dropouts_seen"] = len(sl.dropouts)
        flagged = 0
        for s0, dur in sl.dropouts:
            if sl.gap_in("sensor_combined", s0 - 1.0, s0 + dur + 1.0):
                flagged += 1
        row["dropouts_flagged_by_gap_in"] = flagged
        try:
            row["product"] = product_view(p)
        except Exception as exc:  # noqa: BLE001 - a crash on a real log is itself a finding
            row["product"] = {"error": f"{type(exc).__name__}: {exc}"}
        rows[p.name] = row
        print(p.name, hw, row["armed_s"], row["airborne_s"], row["gyro"]["peak_rate_rad_s"],
              row["logger_dropouts"], row["product"].get("headline", row["product"].get("error")),
              flush=True)
    C.write_json(C.HERE / "RB0_REAL_LOGS.json", {
        "label": "RB0: the reachable real PX4 logs (pyulog test corpus); NOT a designed corpus; "
                 "nothing calibrated on it",
        "theta_steady_2_3": THETA_STEADY, "logs": rows})


if __name__ == "__main__":
    main()
