#!/usr/bin/env python3
"""Calibrate the maneuver-study candidates on the CALIBRATION set only. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/calibrate_maneuver.py

**Data:** CAL1-CAL5 (MANEUVER_FLIGHTS_DESIGN.md), nominal only. No
development flight (2.3 V1-V13) and no evaluation flight is read.

**Model:** `maneuver.fit_model` on all five (torque-to-acceleration gains and
biases, the allocator's mixing and its pseudo-inverse, the heteroscedastic
residual noise).

**Pseudo-onsets:** every 0.5 s where both the BEFORE window [t0-5, t0-0.5)
and the AFTER window [t0+10, t0+15) lie in flight; saturated windows are
left out (every candidate refuses them).

**Rule (2.3's, unchanged):** threshold = 2 x the largest value of the
statistic under the null.

| threshold | candidate | null statistic |
|---|---|---|
| theta_steady_r3, theta_ctrl_r3 | B0 | not re-derived: 2.3 calibration r3, as the product ships |
| theta_steady_B1 | B1 | R, the larger peak body rate of the two windows |
| theta_C_by_bin | B2 | per R bin, the largest abs(C) over all motors; a bin with fewer than 20 pseudo-onsets is not calibrated |
| theta_delta | B3 | the largest abs(delta_m) over all motors |
| h_glr | B4 | the largest GLR_m over all motors |

Writes MANEUVER_CALIBRATION.json.
"""
from __future__ import annotations

import json
import math


import common_rb as C
import maneuver as M

from csia_evidence_assurance.adapters import px4_stock as PS

CAL = ("CAL1", "CAL2", "CAL3", "CAL4", "CAL5")
MIN_BIN = 20


def pseudo_onsets(f):
    t = f.t[f.in_flight]
    if not len(t):
        return []
    out, t0 = [], float(t[0]) + 5.5
    while t0 + 15.0 <= float(t[-1]):
        ok = True
        for w in ("BEFORE", "AFTER"):
            m = M._mask(f.t, t0, w)
            if not m.any() or f.in_flight[m].mean() < 0.95:
                ok = False
        if ok:
            out.append(t0)
        t0 += 0.5
    return out


def main():
    flights = [M.load(C.OUT_RAW / "sitl" / f"{r}.ulg", r) for r in CAL]
    mdl = M.fit_model(flights)
    rows = []
    for f in flights:
        d = M.residual(f, mdl)
        for t0 in pseudo_onsets(f):
            s = M.statistics_at(f, mdl, d, t0)
            if s["saturated"]:
                continue
            s["flight"] = f.name
            rows.append(s)
    fin = lambda xs: [x for x in xs if math.isfinite(x)]  # noqa: E731
    R = fin([r["R"] for r in rows])
    by_bin = {}
    for r in rows:
        b = M._bin(r["R"]) if math.isfinite(r["R"]) else None
        if b is not None:
            by_bin.setdefault(b, []).extend(abs(c) for c in fin(r["C"]))
    counts = {}
    for r in rows:
        b = M._bin(r["R"]) if math.isfinite(r["R"]) else None
        if b is not None:
            counts[b] = counts.get(b, 0) + 1
    theta_bins = [(2 * max(by_bin[b]) if counts.get(b, 0) >= MIN_BIN and by_bin.get(b) else None)
                  for b in range(len(M.R_BINS) - 1)]
    dmax = max(abs(x) for r in rows for x in fin(r["delta"]))
    gmax = max(x for r in rows for x in fin([g for g, _e in r["glr"]]))
    stock = PS.load_calibration()["calibration"]
    cal = {"theta_steady_r3": stock["theta_steady"], "theta_ctrl_r3": stock["theta_ctrl"],
           "theta_steady_B1": 2 * max(R), "theta_C_by_bin": theta_bins,
           "theta_delta": 2 * dmax, "h_glr": 2 * gmax}
    C.write_json(C.HERE / "MANEUVER_CALIBRATION.json", {
        "label": "RB-001 maneuver study: calibration on CAL1-CAL5 only (nominal)",
        "rule": "threshold = 2 x the largest null value; B2 bins need >= 20 pseudo-onsets",
        "flights": {f.name: C.sha(C.OUT_RAW / "sitl" / f"{f.name}.ulg") for f in flights},
        "pseudo_onsets": len(rows), "pseudo_onsets_by_R_bin": {str(M.R_BINS[b]): n for b, n in sorted(counts.items())},
        "R_bins": [str(x) for x in M.R_BINS],
        "null_max": {"R": max(R), "C_by_bin": {str(M.R_BINS[b]): max(v) for b, v in sorted(by_bin.items())},
                     "delta": dmax, "glr": gmax},
        "calibration": cal, "model": mdl.to_dict()})
    print(json.dumps({"pseudo_onsets": len(rows), "counts": counts, "cal": cal}, indent=1, default=str))


if __name__ == "__main__":
    main()
