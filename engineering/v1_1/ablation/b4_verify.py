"""Section 23 gate: are the frozen B4 constants still valid under v1.1?

The brief says reuse k = 0.5, h = 500 "ONLY if those values are still
semantically valid under v1.1 residual construction. Verify this from
historical artifacts. If not: do not silently reuse them."

This script performs that verification. It does NOT run the Phase 3B
comparison; it decides whether Phase 3B may use those constants at all.

    python engineering/v1_1/ablation/b4_verify.py

THE HISTORICAL RECORD (research/phase2/p1_offline_baselines.py, and
research/phase2/results/baseline_comparison.json):

  B4_K = 0.5                      textbook, set by design, not tuned
  B4_H_TEXTBOOK = 5.0             FAILED: 4 alarms on the clean nominal arm,
                                  retained as a committed negative result
  B4_H_GRID = (5, 10, 20, 50, 100, 200, 500, 1000)
  selection rule                  smallest h on the grid for which the CLEAN
                                  NOMINAL arm produces ZERO alarms, evaluated
                                  only on the clean arm, never on a fault
  h = 500                         first grid value with R10_nominal_alarms = 0

  residual                        z_t = (lam_t - mu0) / sigma0 on the
                                  PRE-TRANSFORM smoothed chi-square, with
                                  mu0/sigma0 from the clean arm.
                                  NOT the rejected z = max(0, 1-c) * 10.

The statistic:  S_t = max(0, S_{t-1} + z_t - k),  alarm when S_t > h
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
for p in (ROOT, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.scenarios import run_scenario                          # noqa: E402

B4_K = 0.5
B4_H_GRID = (5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0)
B4_H_HISTORICAL = 500.0

# The clean DEVELOPMENT arm. mu0/sigma0 come from here and from nowhere else.
CLEAN_ARM = "clean"
FAULT_ARMS = ["gps_dropout", "gps_spoof", "imu0_bias_drift", "mag_emi",
              "power_sag", "vibration_anomaly", "dual_imu_failure"]


def lam_streams(td) -> dict:
    """Pre-transform smoothed chi-square per node, gated as production gates.

    This is the quantity B4 was defined on. `td.physics[n] = (lam, gate)` and
    online.py multiplies the gate by freshness, so a gated-out sample is not
    evidence and must not enter the statistic.
    """
    out = {}
    for n, (lam, gate) in td.physics.items():
        lam = np.asarray(lam, dtype=float)
        g = np.asarray(gate, dtype=float) * np.ones(len(lam))
        fresh = np.asarray(td.fresh[n], dtype=bool) if n in td.fresh \
            else np.ones(len(lam), dtype=bool)
        out[n] = (lam, (g > 1e-9) & fresh)
    return out


def cusum_alarms(z, active, k=B4_K, h=B4_H_HISTORICAL):
    """One-sided CUSUM. Returns (first_alarm_index or None, n_alarm_ticks)."""
    s, first, n = 0.0, None, 0
    for i in range(len(z)):
        if not active[i]:
            continue                      # gated out is NOT evidence
        s = max(0.0, s + z[i] - k)
        if s > h:
            n += 1
            if first is None:
                first = i
    return first, n


def main() -> int:
    _t, _f, td_clean, _h, _d = run_scenario(CLEAN_ARM)
    clean = lam_streams(td_clean)

    # mu0/sigma0 from the CLEAN arm only.
    stats = {}
    for n, (lam, act) in clean.items():
        vals = lam[act]
        if vals.size < 2:
            stats[n] = None
            continue
        stats[n] = (float(vals.mean()), float(vals.std(ddof=1)))

    usable = {n: s for n, s in stats.items() if s and s[1] > 1e-12}
    degenerate = sorted(n for n, s in stats.items()
                        if not s or s[1] <= 1e-12)

    def z_of(streams, n):
        lam, act = streams[n]
        mu0, sd0 = usable[n]
        return (lam - mu0) / sd0, act

    # --- the gate: does the CLEAN arm still give zero alarms at h = 500? ---
    grid = {}
    for h in B4_H_GRID:
        total = 0
        per_node = {}
        for n in usable:
            z, act = z_of(clean, n)
            _first, cnt = cusum_alarms(z, act, h=h)
            per_node[n] = cnt
            total += cnt
        grid[h] = {"clean_alarm_ticks": total, "per_node": per_node,
                   "satisfies_zero_clean_alarms": total == 0}

    smallest_ok = next((h for h in B4_H_GRID
                        if grid[h]["satisfies_zero_clean_alarms"]), None)
    still_valid = (grid[B4_H_HISTORICAL]["satisfies_zero_clean_alarms"]
                   and smallest_ok == B4_H_HISTORICAL)

    # --- does it still respond on the fault arms? -------------------------
    responses = {}
    for scen in FAULT_ARMS:
        _t, _f, td, _h2, _d2 = run_scenario(scen)
        st = lam_streams(td)
        hits = {}
        for n in usable:
            if n not in st:
                continue
            z, act = z_of(st, n)
            first, cnt = cusum_alarms(z, act, h=B4_H_HISTORICAL)
            if cnt:
                hits[n] = {"first_t": round(float(td.t[first]), 3),
                           "alarm_ticks": cnt}
        responses[scen] = hits

    verdict = ("REUSABLE" if still_valid else
               "NOT_REUSABLE_RE_DERIVATION_REQUIRED")

    out = {
        "artifact": "B4_CONSTANT_VERIFICATION",
        "section": "23",
        "historical_source": "research/phase2/p1_offline_baselines.py "
                             "(B4_K, B4_H_GRID) and "
                             "research/phase2/results/baseline_comparison.json",
        "historical_k": B4_K,
        "historical_h": B4_H_HISTORICAL,
        "historical_h_textbook_rejected": {
            "h": 5.0,
            "why": "4 alarms on the clean nominal arm; failed R10. Retained "
                   "in the historical record as a committed negative result.",
        },
        "selection_rule": "smallest h on the fixed grid for which the CLEAN "
                          "NOMINAL arm produces zero alarms; evaluated only "
                          "on the clean arm, never on a fault outcome",
        "residual": "z_t = (lam_t - mu0)/sigma0 on the PRE-TRANSFORM smoothed "
                    "chi-square, gated as production gates it. NOT the "
                    "rejected z = max(0, 1-c)*10.",
        "clean_arm": CLEAN_ARM,
        "in_control_stats": {n: {"mu0": round(v[0], 6),
                                 "sigma0": round(v[1], 6)}
                             for n, v in usable.items()},
        "degenerate_nodes_excluded": degenerate,
        "grid": {str(h): grid[h] for h in B4_H_GRID},
        "smallest_h_with_zero_clean_alarms": smallest_ok,
        "historical_h_still_valid": still_valid,
        "fault_arm_response_at_historical_h": responses,
        "verdict": verdict,
    }
    p = os.path.join(ENG, "B4_CONSTANT_VERIFICATION.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  in-control nodes: {sorted(usable)}")
    print(f"  excluded (sigma0 = 0 or too few samples): {degenerate}")
    print("\n  h      clean alarm ticks   zero?")
    for h in B4_H_GRID:
        print(f"    {h:<7.0f} {grid[h]['clean_alarm_ticks']:<18d} "
              f"{grid[h]['satisfies_zero_clean_alarms']}")
    print(f"\n  smallest h with zero clean alarms: {smallest_ok}")
    print(f"  historical h = {B4_H_HISTORICAL} still valid: {still_valid}")
    print(f"\n  VERDICT: {verdict}")
    print("\n  fault-arm response at historical h:")
    for s, hits in responses.items():
        print(f"    {s:<20} {hits if hits else 'NO ALARM'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
