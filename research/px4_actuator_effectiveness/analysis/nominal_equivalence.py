#!/usr/bin/env python3
"""Nominal-equivalence gate: is patched SIH at SIH_MOT_EFF1..4 = 1.0 the same
simulator as unmodified SIH?

PX4 SIH is not bit-reproducible: its noise generator is a process-global rand()
drawn from several threads, so two identical unmodified runs diverge at noise
level from boot. The tolerance is therefore the simulator's own run-to-run
repeatability, measured on the unmodified build, and the question is whether
the patched build's runs are distinguishable from another batch of unmodified
runs.

Decision rule, fixed before the equivalence data were analysed:

  STOP if any of
    (1) a per-metric exact permutation test, Holm-adjusted over all metrics, p < 0.05
    (2) the multivariate energy-distance exact permutation test, p < 0.05
    (3) the takeoff-trajectory exact permutation test, p < 0.05
  otherwise PASS, reporting every effect in units of the unmodified build's
  run-to-run standard deviation.

Permutation: all C(n, k) relabellings when there are at most 200000 of them
(C(16, 8) = 12870 for one batch); otherwise 20000 seeded random relabellings.
"""
import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np

import sihlog

WINDOWS = {"climb": (10.5, 20.0), "hover": (22.0, 44.5)}


def signal_table(tr):
    s = tr.s
    innov_idx = {n: i for i, n in enumerate(tr.raw["innov_fields"])}
    cols = {}
    for i in range(4):
        cols[f"command/actuator_motors[{i}]"] = s["cmd_alloc"][:, i]
        cols[f"command/actuator_outputs_sim[{i}]"] = s["cmd_sim"][:, i]
        cols[f"rotor/esc_rpm[{i}]"] = s["rpm_true"][:, i]
    for i, ax in enumerate("xyz"):
        cols[f"response/angular_velocity_true_{ax}"] = s["w_true"][:, i]
        cols[f"response/specific_force_meas_{ax}"] = s["accel_meas"][:, i]
        cols[f"response/position_true_{ax}"] = s["pos_true"][:, i]
    for i, ax in enumerate(("roll", "pitch", "yaw")):
        cols[f"response/attitude_true_{ax}"] = s["euler_true"][:, i]
        cols[f"estimate/attitude_{ax}"] = s["euler_est"][:, i]
    for i, n in enumerate(("x", "y", "z", "vx", "vy", "vz")):
        cols[f"estimate/local_position_{n}"] = s["pos_est"][:, i]
    for n in ("gps_hpos[0]", "gps_hpos[1]", "gps_vpos", "gps_hvel[0]", "gps_vvel", "baro_vpos",
              "heading", "mag_field[0]", "mag_field[2]"):
        cols[f"estimate/innovation_{n}"] = s["innov"][:, innov_idx[n]]
    cols["estimate/hover_thrust"] = s["hover_thrust"][:, 0]
    return cols


def run_metrics(tr):
    t = tr.t
    cols = signal_table(tr)
    m = {}
    for w, (a, b) in WINDOWS.items():
        sel = (t >= a) & (t < b)
        for name, v in cols.items():
            x = v[sel]
            m[f"{w}|{name}|mean"] = float(np.nanmean(x))
            m[f"{w}|{name}|std"] = float(np.nanstd(x))
    return m


def climb_trajectory(tr, grid):
    """Altitude and motor-1 command through the climb, on a common time grid."""
    t = tr.t
    z = np.interp(grid, t, tr.s["pos_true"][:, 2])
    c = np.interp(grid, t, tr.s["cmd_alloc"][:, 0])
    return np.concatenate([z, c * 10.0])  # command scaled so both carry comparable weight


MAX_EXACT, N_RANDOM, SEED = 200_000, 20_000, 547


def relabellings(n, k):
    if math.comb(n, k) <= MAX_EXACT:
        for comb in itertools.combinations(range(n), k):
            lab = np.zeros(n, bool)
            lab[list(comb)] = True
            yield lab
    else:
        rng = np.random.default_rng(SEED)
        for _ in range(N_RANDOM):
            lab = np.zeros(n, bool)
            lab[rng.choice(n, k, replace=False)] = True
            yield lab


def exact_perm_pvalue(values, labels, stat):
    n = len(labels)
    k = int(labels.sum())
    obs = stat(values, labels)
    count = total = 0
    for lab in relabellings(n, k):
        count += stat(values, lab) >= obs - 1e-12
        total += 1
    return obs, count / total


def energy_stat(D):
    def f(_, lab):
        a, b = np.nonzero(lab)[0], np.nonzero(~lab)[0]
        return 2 * D[np.ix_(a, b)].mean() - D[np.ix_(a, a)].mean() - D[np.ix_(b, b)].mean()
    return f


def mean_cross_distance(D):
    def f(_, lab):
        a, b = np.nonzero(lab)[0], np.nonzero(~lab)[0]
        return D[np.ix_(a, b)].mean() - 0.5 * (D[np.ix_(a, a)][np.triu_indices(len(a), 1)].mean()
                                               + D[np.ix_(b, b)][np.triu_indices(len(b), 1)].mean())
    return f


def holm(p):
    p = np.asarray(p)
    order = np.argsort(p)
    adj = np.empty_like(p)
    m = len(p)
    running = 0.0
    for r, i in enumerate(order):
        running = max(running, (m - r) * p[i])
        adj[i] = min(1.0, running)
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", help="directory holding nom_base_XX.ulg and nom_patched_XX.ulg")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = Path(a.runs)
    base = sorted(runs.glob("nom_base_*.ulg"))
    patched = sorted(runs.glob("nom_patched_*.ulg"))
    names = [p.stem for p in base + patched]
    labels = np.array([False] * len(base) + [True] * len(patched))
    trials = [sihlog.load(p) for p in base + patched]

    per_run = [run_metrics(tr) for tr in trials]
    keys = sorted(per_run[0])
    M = np.array([[r[k] for k in keys] for r in per_run])

    # every relabelling at once: (n_perm x n_runs) @ (n_runs x n_metrics)
    n, k_p = len(labels), int(labels.sum())
    L = np.array(list(relabellings(n, k_p)))
    diffs = np.abs(L.astype(float) @ M / k_p - (~L).astype(float) @ M / (n - k_p))
    obs = np.abs(M[labels].mean(0) - M[~labels].mean(0))
    p_all = (diffs >= obs[None, :] - 1e-12 * np.maximum(1.0, np.abs(obs[None, :]))).mean(0)

    rows = []
    for j, k in enumerate(keys):
        v = M[:, j]
        sd_base = v[~labels].std(ddof=1)
        sd_pool = np.sqrt(0.5 * (v[~labels].var(ddof=1) + v[labels].var(ddof=1)))
        delta = v[labels].mean() - v[~labels].mean()
        p = float(p_all[j])
        rows.append({"metric": k, "base_mean": v[~labels].mean(), "patched_mean": v[labels].mean(),
                     "delta": delta, "sd_base_run_to_run": sd_base,
                     "delta_in_sd": float(delta / sd_pool) if sd_pool > 0 else 0.0,
                     "base_range": [v[~labels].min(), v[~labels].max()],
                     "patched_range": [v[labels].min(), v[labels].max()],
                     "p_perm": p})
    adj = holm([r["p_perm"] for r in rows])
    for r, q in zip(rows, adj):
        r["p_holm"] = float(q)

    Z = (M - M.mean(0)) / np.where(M.std(0) > 0, M.std(0), 1.0)
    D = np.sqrt(((Z[:, None, :] - Z[None, :, :]) ** 2).sum(-1))
    e_obs, e_p = exact_perm_pvalue(None, labels, energy_stat(D))

    grid = np.arange(10.5, 20.0, 0.004)
    T = np.array([climb_trajectory(tr, grid) for tr in trials])
    DT = np.sqrt(((T[:, None, :] - T[None, :, :]) ** 2).mean(-1))
    iu = np.triu_indices(len(trials), 1)
    pair_kind = np.where(labels[iu[0]] == labels[iu[1]], np.where(labels[iu[0]], "PP", "BB"), "BP")
    c_obs, c_p = exact_perm_pvalue(None, labels, mean_cross_distance(DT))

    meta = []
    for p, tr in zip(base + patched, trials):
        j = json.loads(p.with_suffix(".json").read_text())
        meta.append({"name": p.stem, "px4_sha256": j["px4_sha256"], "ulog_sha256": j["ulog_sha256"],
                     "arm_us": sihlog.arm_time_us(tr), "dropouts": tr.dropouts,
                     "SIH_MOT_EFF1": tr.params.get("SIH_MOT_EFF1")})

    worst = sorted(rows, key=lambda r: r["p_holm"])[:10]
    stop = (min(r["p_holm"] for r in rows) < 0.05) or e_p < 0.05 or c_p < 0.05
    result = {
        "decision_rule": __doc__.split("Decision rule")[1].split("Exact permutation")[0].strip(),
        "n_base": int((~labels).sum()), "n_patched": int(labels.sum()), "n_metrics": len(keys),
        "windows_s": WINDOWS,
        "per_metric_min_p_holm": min(r["p_holm"] for r in rows),
        "per_metric_min_p_raw": min(r["p_perm"] for r in rows),
        "per_metric_max_abs_delta_in_sd": max(abs(r["delta_in_sd"]) for r in rows),
        "n_metrics_raw_p_below_0.05": int(sum(r["p_perm"] < 0.05 for r in rows)),
        "expected_raw_p_below_0.05_under_null": round(0.05 * len(keys), 1),
        "energy_statistic": e_obs, "energy_p": e_p,
        "climb_trajectory": {"stat_cross_minus_within": c_obs, "p": c_p,
                             "rms_distance_BB": [float(DT[iu][pair_kind == "BB"].min()), float(DT[iu][pair_kind == "BB"].mean()), float(DT[iu][pair_kind == "BB"].max())],
                             "rms_distance_PP": [float(DT[iu][pair_kind == "PP"].min()), float(DT[iu][pair_kind == "PP"].mean()), float(DT[iu][pair_kind == "PP"].max())],
                             "rms_distance_BP": [float(DT[iu][pair_kind == "BP"].min()), float(DT[iu][pair_kind == "BP"].mean()), float(DT[iu][pair_kind == "BP"].max())]},
        "verdict": "STOP" if stop else "PASS",
        "lowest_p_metrics": worst,
        "runs": meta,
        "metrics": rows,
    }
    Path(a.out).write_text(json.dumps(result, indent=1, default=float))
    print(json.dumps({k: result[k] for k in ("n_base", "n_patched", "n_metrics", "per_metric_min_p_holm",
                                             "per_metric_min_p_raw", "per_metric_max_abs_delta_in_sd",
                                             "n_metrics_raw_p_below_0.05", "expected_raw_p_below_0.05_under_null",
                                             "energy_p", "climb_trajectory", "verdict")}, indent=1, default=float))


if __name__ == "__main__":
    main()
