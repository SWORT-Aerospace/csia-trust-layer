#!/usr/bin/env python3
"""Calibration revision 3: theta_steady, from APPARATUS data only. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/calibrate_steady.py

**Why.** The claim register (CLAIMS.json, ALLOCATOR_COMPENSATION) assumes
"near-steady flight in both windows" and lists "maneuvering or wind in a
window" as a failure mode. Revision 2 did not implement that assumption.
Validation flights V5 and V6 (nominal, maneuvering) showed the cost: every
reposition and yaw turn raised a false COMMAND_NO_RESPONSE.

**Statistic.** R_w(t0) = the largest body-rate magnitude |omega| (rad/s,
`vehicle_angular_velocity` at its default interval) in the BEFORE and
AFTER windows of a pseudo-onset t0 (`stock_stats.peak_rate`).

**Rule (unchanged):** theta_steady = 2 x the largest R under the null, over
the same 32 apparatus nominal flights and pseudo-onsets every 0.5 s in
hover as revision 2. No XSYS-001 flight and no validation flight sets it.

**Every revision-2 threshold is carried over unchanged.** Revision 2 is
kept as CALIBRATION_2_3_r2_superseded.json.
"""
from __future__ import annotations

import json
import shutil
from concurrent.futures import ProcessPoolExecutor

import common_23 as C
from calibrate_23 import APP, hover_span, load

from csia_evidence_assurance import stock_stats as SS


def null_peak(path):
    log = load(path)
    span = hover_span(log)
    if span is None:
        return None
    a, b = span
    t0, mx, n = a + 5.0, 0.0, 0
    while t0 + 15.0 <= b:
        mx = max(mx, SS.peak_rate(log, t0, "BEFORE"), SS.peak_rate(log, t0, "AFTER"))
        n += 1
        t0 += 0.5
    return mx, n


def main():
    nominal = sorted(str(p) for d in ("nominal_batch1", "nominal_batch2")
                     for p in (APP / d).glob("*.ulg"))
    with ProcessPoolExecutor(4) as ex:
        res = [r for r in ex.map(null_peak, nominal) if r]
    mx = max(r[0] for r in res)
    path = C.HERE / "CALIBRATION_2_3.json"
    cal = json.loads(path.read_text())
    if cal["revision"] == 2:
        shutil.copy(path, C.HERE / "CALIBRATION_2_3_r2_superseded.json")
    cal["revision"] = 3
    cal["calibration"]["theta_steady"] = 2 * mx
    cal["null_max_abs"]["R_steady"] = mx
    cal["null_steady"] = {"flights": len(res), "pseudo_onsets": sum(r[1] for r in res),
                          "statistic": "largest |omega| (rad/s) in the BEFORE and AFTER windows"}
    hist = [h for h in cal["revision_history"] if not h.startswith("r3")]
    hist.append("r3: adds theta_steady for the compensation claim's assumption 'near-steady "
                "flight in both windows' (claim register), which r2 did not implement; found "
                "missing by validation flights V5 and V6, whose maneuvers raised false "
                "COMMAND_NO_RESPONSE symptoms. Same rule, same 32 apparatus nominal flights; "
                "every r2 threshold unchanged; no XSYS-001 or validation flight sets it")
    cal["revision_history"] = hist
    C.write_json(path, cal)
    pk = C.REPO / "csia_evidence_assurance/stock_calibration.json"
    packaged = json.loads(pk.read_text())
    packaged["calibration"] = cal["calibration"]
    packaged["revision"] = 3
    C.write_json(pk, packaged)
    print(json.dumps({"theta_steady": 2 * mx, "null_max": mx, "flights": len(res)}))


if __name__ == "__main__":
    main()
