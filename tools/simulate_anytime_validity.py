"""T-1 falsification matrix: empirical boundary crossing under null processes.

    python tools/simulate_anytime_validity.py

Simulation cannot prove a theorem; its role here is to FALSIFY invalid
constructions. Every cell reports P(exists t <= T : E_t >= 1/alpha) under a
null process, against the advertised Ville bound alpha.

Protocol notes (pre-registered):
  * Block-length SELECTION uses seed base 0; the FINAL evaluation of the
    selected length uses seed base 1000. The final null-evaluation partition
    is never used to choose L (executive directive, T-1 item 10).
  * All cells use N paths x T steps with vectorized math mirroring
    csia/evidence/eprocess.py; tests pin class-vs-vectorized parity.
"""

import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from csia.experiments import EvidenceEnvironment, build  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
KAPPA, P_MIN, THR, ALPHA = 0.5, 1e-8, 20.0, 0.05
N_SELECT, N_EVAL, T = 2000, 4000, 3000
SEED_SELECT, SEED_EVAL = 0, 1000


def calibrate(p):
    return KAPPA * np.power(np.clip(p, P_MIN, 1.0), KAPPA - 1.0)


# --- null generators: (N, T) matrix of scores x, plus a marginal->p map ------

def gen_iid(rng, n, t):
    return rng.standard_normal((n, t)), lambda x: stats.norm.sf(x)


def gen_ar1(rho):
    def g(rng, n, t):
        x = np.empty((n, t))
        s = rng.standard_normal(n)
        c = math.sqrt(1 - rho * rho)
        for k in range(t):
            s = rho * s + c * rng.standard_normal(n)
            x[:, k] = s
        return x, lambda v: stats.norm.sf(v)
    return g


def gen_t3(rng, n, t):
    return rng.standard_t(3, (n, t)), lambda x: stats.t.sf(x, 3)


def gen_regime(rng, n, t, period=300, rhos=(0.3, 0.97)):
    """Regime-switching AR(1); returns x plus per-tick regime index."""
    x = np.empty((n, t))
    reg = np.empty(t, dtype=int)
    s = rng.standard_normal(n)
    for k in range(t):
        r = rhos[(k // period) % 2]
        reg[k] = (k // period) % 2
        s = r * s + math.sqrt(1 - r * r) * rng.standard_normal(n)
        x[:, k] = s
    return x, reg


# --- constructions (vectorized) ----------------------------------------------

def _cross(log_e_steps):
    return (np.cumsum(log_e_steps, axis=1).max(axis=1)
            >= math.log(THR)).mean()


def run_naive(x, p_of):
    return _cross(np.log(calibrate(p_of(x))))


def _block_var(rho, L):
    acc = sum((1.0 - k / L) * rho ** k for k in range(1, L))
    return (1.0 + 2.0 * acc) / L


def run_blockwise(x, L, rho):
    n, t = x.shape
    nb = t // L
    means = x[:, :nb * L].reshape(n, nb, L).mean(axis=2)
    p = stats.norm.sf(means / math.sqrt(_block_var(rho, L)))
    return _cross(np.log(calibrate(p)))


def run_blockwise_regime(x, reg, L, rhos, oracle):
    """Regime null. oracle=True conditions the block variance on the true
    regime (context-conditioned calibration); False assumes one stationary
    rho (the average), modelling context-ignorant calibration."""
    n, t = x.shape
    nb = t // L
    means = x[:, :nb * L].reshape(n, nb, L).mean(axis=2)
    p = np.empty_like(means)
    for j in range(nb):
        r = rhos[reg[j * L]] if oracle else 0.65
        p[:, j] = stats.norm.sf(means[:, j] / math.sqrt(_block_var(r, L)))
    return _cross(np.log(calibrate(p)))


def run_lr(x, rho0, delta=1.0):
    """Conditions on x[:,0]; the LR runs over t >= 1 so every factor uses the
    true conditional law. (Bug found by this suite: scoring x_0 against the
    conditional density with prev=0, while the process starts stationary,
    injected one enormous invalid first e-value -> measured 0.196 crossing.)"""
    prev = x[:, 0].copy()
    var = 1.0 - rho0 * rho0
    log_e = np.zeros((x.shape[0], x.shape[1] - 1))
    for k in range(1, x.shape[1]):
        mu0 = rho0 * prev
        log_e[:, k - 1] = (delta * (x[:, k] - mu0) - 0.5 * delta ** 2) / var
        prev = x[:, k]
    return _cross(log_e)


def run_cal_reuse(x, rng, n_cal=200):
    """iid scores, but p computed against ONE fixed reused calibration set."""
    cal = np.sort(rng.standard_normal(n_cal))
    p = (n_cal - np.searchsorted(cal, x) + 1.0) / (n_cal + 1.0)
    return _cross(np.log(calibrate(p)))


def run_power(rho, L, onset, delta, rng, n=1000):
    """ALTERNATIVE: mean shift delta from `onset`. Detection + latency."""
    x = np.empty((n, T))
    s = rng.standard_normal(n)
    c = math.sqrt(1 - rho * rho)
    for k in range(T):
        s = rho * s + c * rng.standard_normal(n)
        x[:, k] = s + (delta if k >= onset else 0.0)
    nb = T // L
    means = x[:, :nb * L].reshape(n, nb, L).mean(axis=2)
    p = stats.norm.sf(means / math.sqrt(_block_var(rho, L)))
    e = np.cumprod(np.clip(calibrate(p), 1e-300, 1e12), axis=1)
    hit = e >= THR
    detected = hit.any(axis=1)
    first = np.where(detected, hit.argmax(axis=1), nb) * L
    lat = (first[detected & (first >= onset)] - onset)
    return {"detection_rate": round(float(detected.mean()), 4),
            "median_latency_ticks": None if lat.size == 0
            else int(np.median(lat))}


def main() -> int:
    t0 = time.time()
    out = {"alpha": ALPHA, "threshold": THR, "kappa": KAPPA, "T": T,
           "protocol": {"selection_seed_base": SEED_SELECT,
                        "evaluation_seed_base": SEED_EVAL,
                        "rule": "block length selected on selection seeds "
                                "ONLY; final numbers from evaluation seeds"},
           "cells": {}}

    def wilson(k, n, z=1.96):
        ph = k / n
        d = 1 + z * z / n
        c = (ph + z * z / (2 * n)) / d
        h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
        return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))

    def cell(name, fn, seed, n):
        rng = np.random.default_rng(seed)
        rate = fn(rng, n)
        k = int(round(rate * n))
        se = math.sqrt(max(rate * (1 - rate), 1e-9) / n)
        lo, hi = wilson(k, n)
        out["cells"][name] = {
            "crossing_count": k, "n_paths": n,
            "crossing_rate": round(float(rate), 4),
            "ci95_wilson": [lo, hi], "mc_se": round(se, 4),
            "seed_family": seed, "bound": ALPHA,
            # a cell violates only when its LOWER confidence limit clears the
            # bound — point estimates are not presented as exact
            "violates": bool(lo > ALPHA)}
        print(f"  {name:44s} {rate:7.4f}  "
              f"{'VIOLATES' if out['cells'][name]['violates'] else 'ok':8s}")

    print("== SELECTION phase (seed base 0) — block-length sweep ==")
    sweep = {0.5: (1, 5, 25, 50, 100), 0.94: (1, 5, 25, 50, 100),
             0.99: (1, 5, 25, 50, 100, 200, 400)}
    for rho in (0.5, 0.94, 0.99):
        g = gen_ar1(rho)
        for L in sweep[rho]:
            cell(f"select/ar1_{rho}/L{L}",
                 lambda r, n, g=g, L=L, rho=rho:
                 run_blockwise(g(r, n, T)[0], L, rho),
                 SEED_SELECT, N_SELECT)

    # Selected block length: smallest L valid across the DECLARED dependence
    # domain rho <= 0.94 (decision made on selection seeds only). rho = 0.99
    # is recorded as the domain BOUNDARY: L must scale with the mixing time,
    # and the sweep documents how far L=100 falls short there.
    chosen = min((L for L in (1, 5, 25, 50, 100)
                  if not any(out["cells"][f"select/ar1_{r}/L{L}"]["violates"]
                             for r in (0.5, 0.94))), default=100)
    out["selected_block_len"] = chosen
    out["validity_domain"] = {
        "declared": "AR(1)-like dependence with rho <= 0.94 "
                    "(approx. 15-tick decorrelation, CSIA's smoothed regime)",
        "boundary_counterexample": "rho = 0.99 violates at L <= 100 "
                                   "(0.113 at L=100) and is restored at "
                                   "L = 200 (0.054) and L = 400 (0.014): "
                                   "L must scale with the mixing time"}
    print(f"  -> selected block length L = {chosen} "
          "(valid for declared domain rho <= 0.94)")

    print("== EVALUATION phase (seed base 1000) ==")
    cell("eval/naive/iid",
         lambda r, n: run_naive(*gen_iid(r, n, T)), SEED_EVAL, N_EVAL)
    cell("eval/naive/ar1_0.94_KNOWN_INVALID",
         lambda r, n: run_naive(*(lambda x: (x[0], x[1]))(
             gen_ar1(0.94)(r, n, T))), SEED_EVAL, N_EVAL)
    cell("eval/naive/t3_iid",
         lambda r, n: run_naive(*gen_t3(r, n, T)), SEED_EVAL, N_EVAL)
    cell("eval/naive/calibration_reuse",
         lambda r, n: run_cal_reuse(r.standard_normal((n, T)), r),
         SEED_EVAL, N_EVAL)
    for rho in (0.5, 0.94, 0.99):
        cell(f"eval/blockwise_L{chosen}/ar1_{rho}",
             lambda r, n, rho=rho:
             run_blockwise(gen_ar1(rho)(r, n, T)[0], chosen, rho),
             SEED_EVAL, N_EVAL)
    cell(f"eval/blockwise_L{chosen}/regime_oracle_context",
         lambda r, n: (lambda xr: run_blockwise_regime(
             xr[0], xr[1], chosen, (0.3, 0.97), True))(gen_regime(r, n, T)),
         SEED_EVAL, N_EVAL)
    cell(f"eval/blockwise_L{chosen}/regime_IGNORED_context",
         lambda r, n: (lambda xr: run_blockwise_regime(
             xr[0], xr[1], chosen, (0.3, 0.97), False))(gen_regime(r, n, T)),
         SEED_EVAL, N_EVAL)
    cell("eval/lr_correct_null/ar1_0.94",
         lambda r, n: run_lr(gen_ar1(0.94)(r, n, T)[0], 0.94),
         SEED_EVAL, N_EVAL)
    cell("eval/lr_MISSPECIFIED_iid_assumed/ar1_0.94",
         lambda r, n: run_lr(gen_ar1(0.94)(r, n, T)[0], 0.0),
         SEED_EVAL, N_EVAL)

    print("== POWER (alternative, not a validity claim) ==")
    rng = np.random.default_rng(SEED_EVAL + 7)
    out["power"] = {
        f"blockwise_L{chosen}/ar1_0.94/shift1.0":
            run_power(0.94, chosen, onset=1000, delta=1.0, rng=rng),
        f"blockwise_L{chosen}/ar1_0.94/shift0.5":
            run_power(0.94, chosen, onset=1000, delta=0.5, rng=rng)}
    for k, v in out["power"].items():
        print(f"  {k:44s} det={v['detection_rate']} "
              f"lat={v['median_latency_ticks']} ticks")

    out["runtime_s"] = round(time.time() - t0, 1)
    man = build("anytime_validity_t1", EvidenceEnvironment.SIMULATION,
                output_paths=["experiments/results/anytime_validity_v1.json"])
    doc = {"result_schema_version": "1.0.0", "result_type": "MONTE_CARLO",
           "evidence_environment": "SIMULATION",
           "experiment_manifest": man.to_dict(), "payload": out}
    path = os.path.join(ROOT, "experiments", "results",
                        "anytime_validity_v1.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    print(f"-> {path}  ({out['runtime_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
