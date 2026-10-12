#!/usr/bin/env python3
"""POST-HOC / EXPLORATORY. Written AFTER criterion C4 failed on the design
pilots; it does not replace C4 and cannot change the frozen decision.

Question: is the C4 failure (true pitch-rate correlation up to 0.27 between
design conditions) evidence of shared state/noise, or is |r| <= 0.1 simply
not attainable for these signals even between spans known to be independent?

Reference null: the long hover Q1 cut into 20 s spans [t0 - 5, t0 + 15) with
t0 every 25 s. Their noise draws are disjoint segments of one stream (the
same construction the design uses), so their pairwise correlations are what
INDEPENDENT spans produce. The design pairs are compared with that reference.

Usage: explore_c4_posthoc.py <Q1 ulg> <DESIGN_CHECK.json> <out C4_POSTHOC_EXPLORATORY.json>
"""
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

import independence_diagnostics as ID


def main():
    q1 = ID.Flight(Path(sys.argv[1]))
    design = json.loads(Path(sys.argv[2]).read_text())
    arm, dis = q1.t_arm_us * 1e-6, q1.t_disarm_us * 1e-6
    t0s = [t for t in np.arange(arm + 22.0, dis - 15.5, 25.0)]
    t0_us = [int(round(t * 1e6 / ID.STEP_US)) * ID.STEP_US for t in t0s]
    sig = ("gyro_loss_axis_m0", "kappa_m0", "rho_m0", "w_true_roll", "w_true_pitch")
    null = {s: [] for s in sig}
    for a, b in combinations(t0_us, 2):
        r = ID.trajectory_corr(q1, a, q1, b)
        for s in sig:
            null[s].append(r[s])
    # effective number of independent samples in a 20 s span (Bartlett, from Q1)
    ob, tr = q1.full()
    g = ob["t_abs_us"]
    m = (g >= (arm + 17) * 1e6) & (g < (dis - 0.5) * 1e6)
    neff = {}
    for name, x in (("w_true_roll", tr["w_true"][m, 0]), ("w_true_pitch", tr["w_true"][m, 1]),
                    ("gyro_roll", ob["gyro"][m, 0])):
        ac = ID.acf(x, int(round(10.0 / 0.004)))
        tau_int = 1 + 2 * float(np.sum(ac[1:] * (ac[1:] > 0)))
        neff[name] = {"integral_time_s": tau_int * 0.004, "n_eff_in_20s": 5000 / (tau_int * tau_int ** 0)}
        neff[name]["n_eff_in_20s"] = 5000 / tau_int
    obs = design["C4_trajectory_correlation"]["pairs"]
    out = {"label": "POST-HOC / EXPLORATORY - does not replace C4 or change the frozen decision",
           "reference": f"{len(t0s)} disjoint 20 s spans of Q1, t0 every 25 s: {len(null['w_true_pitch'])} independent pairs",
           "reference_abs_r": {s: {"median": float(np.median(np.abs(v))), "p95": float(np.quantile(np.abs(v), 0.95)),
                                   "max": float(np.max(np.abs(v))), "fraction_above_0.1": float(np.mean(np.abs(v) > 0.1))}
                               for s, v in null.items()},
           "design_pairs_abs_r": {s: sorted(round(abs(p[s]), 3) for p in obs.values()) for s in sig},
           "design_pairs_percentile_in_reference": {
               s: [float(np.mean(np.abs(null[s]) <= abs(p[s]))) for p in obs.values()] for s in sig},
           "effective_samples": neff}
    Path(sys.argv[3]).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: out[k] for k in ("reference", "reference_abs_r", "design_pairs_abs_r", "effective_samples")},
                     indent=1, default=float))


if __name__ == "__main__":
    main()
