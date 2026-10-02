#!/usr/bin/env python3
"""Calibrate the stock propulsion thresholds from APPARATUS data only.
RESEARCH ONLY. Run once, then frozen (CALIBRATION_2_3.json is committed
before any XSYS-001 evaluation).

    .venv/bin/python research/csia_2_3_stock_bridge/calibrate_23.py

**Data.** The actuator-effectiveness apparatus logs
(`research/px4_actuator_effectiveness/raw_ulog/`, decompressed outside git):
- 32 nominal flights (`nominal_batch1`, `nominal_batch2`: unpatched and
  patched builds);
- 27 sweep flights (eta 0, 0.25, ..., 1.0 on motor 1, three repeats).

None of them is an XSYS-001 flight. All are decimated to PX4 547e2ca's
default logging intervals first.

**Rule (XSYS-001's own calibration rule):** every threshold is 2 x the
largest absolute value of the same statistic under the null, over
pseudo-onsets every 0.5 s in hover. The factor 2 is a specificity margin.

| threshold | null statistic |
|---|---|
| theta_tel | L_tel over the AFTER window |
| theta_ctrl | C over the AFTER window |
| theta_dyn | D over [t0, t0 + 0.2 s) |
| k_tel, k_ctrl (CUSUM drift) | the trailing-reference deviation d at every hover sample |

The CUSUM decision interval is h = 3k: a deviation of 2k is flagged after
3 samples (0.3 s at 10 Hz).

**Validation, not fitting.** The sweep flights report detection, delay and
onset error. They set nothing.

**THE LIMIT.** SIH's rotor and command signals carry almost no noise, so
these thresholds are very small. They say nothing about a real vehicle,
which needs its own nominal calibration (`STOCK_PRODUCERS.md`).
"""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import common_23 as C

from csia_evidence_assurance import stock_stats as SS  # noqa: E402
from csia_evidence_assurance.stock_log import StockLog  # noqa: E402

APP = C.OUT_RAW / "apparatus"


def load(path):
    return StockLog.from_ulog(path).decimate()


def hover_span(log):
    t = log.topics["actuator_motors"]["t"]
    fl = log.in_flight(t)
    if not fl.any():
        return None
    return float(t[fl][0]) + 10.0, float(t[fl][-1]) - 1.0


def null_stats(path):
    log = load(path)
    ms = SS.motor_series(log)
    span = hover_span(log)
    if ms is None or span is None:
        return None
    a, b = span
    out = {"flight": Path(path).stem, "L": [], "C": [], "D": [], "d_tel": 0.0, "d_ctrl": 0.0}
    for dv in SS.deviations(ms):
        mt = (dv["t_tel"] >= a) & (dv["t_tel"] <= b) & np.isfinite(dv["d_tel"])
        mc = (dv["t_ctrl"] >= a) & (dv["t_ctrl"] <= b) & np.isfinite(dv["d_ctrl"])
        if mt.any():
            out["d_tel"] = max(out["d_tel"], float(np.max(np.abs(dv["d_tel"][mt]))))
        if mc.any():
            out["d_ctrl"] = max(out["d_ctrl"], float(np.max(np.abs(dv["d_ctrl"][mc]))))
    t0 = a + 5.0
    while t0 + 15.0 <= b:
        ch = SS.event_changes(ms, t0)
        out["L"] += [abs(x) for x in ch["L_tel_AFTER"] if np.isfinite(x)]
        out["C"] += [abs(x) for x in ch["C_AFTER"] if np.isfinite(x)]
        for m in range(ms.n_motors):
            d, n = SS.rate_transient(log, t0, m)
            if n and np.isfinite(d):
                out["D"].append(abs(d))
        t0 += 0.5
    out["pseudo_onsets"] = len(out["L"]) // max(ms.n_motors, 1)
    out["L"] = max(out["L"], default=0.0)
    out["C"] = max(out["C"], default=0.0)
    out["D"] = max(out["D"], default=0.0)
    return out


def sweep_stats(path, cal):
    log = load(path)
    rec = json.loads(Path(path).with_suffix(".json").read_text())
    m = int(rec["motor"]) - 1
    eta = float(rec["eta"])
    # the injection time from the run record (the apparatus has no blinding)
    t_on = float(rec["events_ms"]["eta_set"][0]) * 1e-3
    from pyulog import ULog
    u = ULog(str(path), ["vehicle_status"], False)
    # events_ms is wall time since the run start; align on the arm command
    arm_cmd = float(rec["events_ms"]["arm_sent"]) * 1e-3
    vs = log.topics["vehicle_status"]
    armed = vs["t"][vs["arming_state"] == 2]
    t_onset = float(armed[0]) + (t_on - arm_cmd) if armed.size else float("nan")
    del u
    ms = SS.motor_series(log)
    out = {"flight": Path(path).stem, "eta": eta, "motor": m, "t_onset_est": round(t_onset, 3)}
    if ms is None:
        return out
    ch = SS.event_changes(ms, t_onset)
    out["L_tel_AFTER"] = ch["L_tel_AFTER"][m]
    out["C_AFTER"] = ch["C_AFTER"][m]
    out["L_tel_EARLY"] = ch["L_tel_EARLY"][m]
    dv = SS.deviations(ms)[m]
    first = None
    for kind, tt, dd, k in (("tel", dv["t_tel"], dv["d_tel"], cal["k_tel"]),
                            ("ctrl", dv["t_ctrl"], dv["d_ctrl"], cal["k_ctrl"])):
        alarms, _ = SS.cusum(tt, dd, k, 3 * k)
        hit = [a for a in alarms if a[1] >= t_onset - 1.0]
        out[f"alarm_{kind}"] = hit[0] if hit else None
        if hit and (first is None or hit[0][1] < first[1]):
            first = hit[0]
    out["detected"] = first is not None
    if first:
        out["delay_s"] = round(first[1] - t_onset, 3)
        out["onset_error_s"] = round(first[0] - t_onset, 3)
    return out


def main():
    nominal = sorted(str(p) for d in ("nominal_batch1", "nominal_batch2")
                     for p in (APP / d).glob("*.ulg"))
    sweep = sorted(str(p) for p in (APP / "sweep").glob("*.ulg"))
    with ProcessPoolExecutor(4) as ex:
        nul = [r for r in ex.map(null_stats, nominal) if r]
    mx = {k: max(r[k] for r in nul) for k in ("L", "C", "D", "d_tel", "d_ctrl")}
    cal = {"theta_tel": 2 * mx["L"], "theta_ctrl": 2 * mx["C"], "theta_dyn": 2 * mx["D"],
           "k_tel": 2 * mx["d_tel"], "k_ctrl": 2 * mx["d_ctrl"]}
    cal["h_tel"], cal["h_ctrl"] = 3 * cal["k_tel"], 3 * cal["k_ctrl"]
    with ProcessPoolExecutor(4) as ex:
        sw = list(ex.map(sweep_stats, sweep, [cal] * len(sweep)))
    by_eta = {}
    for r in sw:
        by_eta.setdefault(r["eta"], []).append(r)
    out = {
        "label": "CSIA 2.3 stock calibration; apparatus data only; frozen before XSYS-001 evaluation",
        "rule": "threshold = 2 x the largest |value| of the statistic under the null (pseudo-onsets every 0.5 s in hover); CUSUM h = 3k",
        "rates": "PX4 547e2ca default logging intervals (stock_log.STOCK_INTERVAL_MS)",
        "null_flights": len(nul),
        "null_pseudo_onsets": sum(r["pseudo_onsets"] for r in nul),
        "null_max_abs": mx,
        "calibration": cal,
        "sweep_validation": {str(e): {"n": len(v), "detected": sum(1 for r in v if r.get("detected")),
                                      "median_delay_s": (float(np.median([r["delay_s"] for r in v if r.get("detected")]))
                                                         if any(r.get("detected") for r in v) else None),
                                      "median_onset_error_s": (float(np.median([r["onset_error_s"] for r in v if r.get("detected")]))
                                                               if any(r.get("detected") for r in v) else None),
                                      "L_tel_AFTER": [round(r.get("L_tel_AFTER", float("nan")), 4) for r in v],
                                      "C_AFTER": [round(r.get("C_AFTER", float("nan")), 4) for r in v]}
                             for e, v in sorted(by_eta.items())},
        "limit": "SIH carries almost no noise on these signals; the thresholds do not transfer to hardware",
    }
    C.write_json(C.HERE / "CALIBRATION_2_3.json", out)
    print(json.dumps(out, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main()
