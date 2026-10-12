#!/usr/bin/env python3
"""Why run-to-run repeatability of PX4 SIH is clustered.

SIH seeds rand() once with a fixed seed (sih.cpp:61), and the GPS, baro and
mag simulators draw from the same process-global generator on other threads.
Runs therefore replay one of a few noise realizations, and branch only when a
thread-interleaving event reorders the draws. This script measures, for every
pair of runs, the fraction of pre-arm accelerometer samples (vehicle at rest,
so the signal is gravity plus SIH noise) that are bit-identical, and the time
at which the full-rate physical signals first differ.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sihlog

FULL_RATE = ["rpm_true", "accel_meas", "gyro_meas", "w_true", "q_true", "cmd_sim"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ulogs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = {}
    for p in a.ulogs:
        tr = sihlog.load(p)
        runs[Path(p).stem] = (tr.t_us, tr.t, np.column_stack([tr.s[k] for k in FULL_RATE]),
                              tr.s["accel_meas"][:, 0], sihlog.arm_time_us(tr))
    names = list(runs)
    same_pre = np.zeros((len(names), len(names)))
    first_div = np.full((len(names), len(names)), np.nan)
    for i, x in enumerate(names):
        for j, y in enumerate(names):
            tx, sx, X, ax, _ = runs[x]
            ty, sy, Y, ay, _ = runs[y]
            common, ix, iy = np.intersect1d(tx, ty, return_indices=True)
            pre = (common > 1.0e6) & (common < 9.5e6)
            same_pre[i, j] = np.mean(ax[ix][pre] == ay[iy][pre])
            eq = np.all((X[ix] == Y[iy]) | (np.isnan(X[ix]) & np.isnan(Y[iy])), axis=1)
            bad = np.nonzero(~eq)[0]
            first_div[i, j] = common[bad[0]] / 1e6 if len(bad) else np.nan
    out = {"runs": names, "arm_us": [int(runs[n][4]) for n in names],
           "identical_pre_arm_accel_fraction": same_pre.round(3).tolist(),
           "first_divergence_s_full_rate_physical": np.round(first_div, 3).tolist()}
    Path(a.out).write_text(json.dumps(out, indent=1))
    lab = [n.replace("nom_base_", "B").replace("nom_patched_", "P") for n in names]
    print("identical pre-arm accelerometer samples, fraction")
    print("     " + " ".join(f"{s:>4s}" for s in lab))
    for s, row in zip(lab, same_pre):
        print(f"{s:>4s} " + " ".join(f"{v:4.2f}" for v in row))


if __name__ == "__main__":
    main()
