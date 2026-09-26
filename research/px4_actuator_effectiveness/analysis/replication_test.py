#!/usr/bin/env python3
"""Replication test for the hover-yaw cluster seen in nominal batch 1.

Stated before batch 2 was flown: in batch 1 the four lowest-p metrics were all
hover-yaw metrics, all LOWER in the patched build (none survived Holm over the
172 metrics). Batch 2 repeats the batch-1 protocol exactly. Each of the four
is tested one-sided in batch 1's direction (patched < base) with an exact
permutation test, Holm-adjusted over the four.

  any Holm-adjusted p < 0.05  -> the patch materially changes nominal yaw: STOP
  otherwise                   -> the batch-1 cluster is not reproduced
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np

import sihlog
from nominal_equivalence import holm, run_metrics

HYPOTHESES = [  # (metric, direction of batch-1 effect)
    ("hover|estimate/attitude_yaw|std", "patched_lower"),
    ("hover|response/angular_velocity_true_z|std", "patched_lower"),
    ("hover|response/attitude_true_yaw|std", "patched_lower"),
    ("hover|response/angular_velocity_true_z|mean", "patched_lower"),
]


def one_sided_p(base, patched):
    v = np.concatenate([base, patched])
    n, k = len(v), len(patched)
    obs = base.mean() - patched.mean()          # large when patched is lower
    hits = total = 0
    for comb in itertools.combinations(range(n), k):
        lab = np.zeros(n, bool)
        lab[list(comb)] = True
        hits += (v[~lab].mean() - v[lab].mean()) >= obs - 1e-12
        total += 1
    return float(obs), hits / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = Path(a.runs)
    base = [run_metrics(sihlog.load(p)) for p in sorted(runs.glob("nom_base_*.ulg"))]
    patched = [run_metrics(sihlog.load(p)) for p in sorted(runs.glob("nom_patched_*.ulg"))]
    rows = []
    for metric, _ in HYPOTHESES:
        b = np.array([r[metric] for r in base])
        p_ = np.array([r[metric] for r in patched])
        obs, p = one_sided_p(b, p_)
        sd = np.sqrt(0.5 * (b.var(ddof=1) + p_.var(ddof=1)))
        rows.append({"metric": metric, "base_mean": b.mean(), "patched_mean": p_.mean(),
                     "base_minus_patched": obs, "effect_in_sd": obs / sd, "p_one_sided": p})
    for r, q in zip(rows, holm([r["p_one_sided"] for r in rows])):
        r["p_holm"] = float(q)
    verdict = "STOP" if min(r["p_holm"] for r in rows) < 0.05 else "NOT_REPLICATED"
    out = {"hypotheses": HYPOTHESES, "n_base": len(base), "n_patched": len(patched),
           "results": rows, "verdict": verdict}
    Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
