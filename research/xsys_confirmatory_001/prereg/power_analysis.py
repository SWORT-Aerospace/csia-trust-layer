#!/usr/bin/env python3
"""XSYS-001: decision boundary and power of the preregistered primary rule.

Uses NO experimental data: only the frozen decision rule (stage2_score.py)
and binomial arithmetic. It is the basis for the number of nuisance
conditions H.

PRIMARY RULE (frozen): with n_eff = H nuisance conditions and an observed pair
resolution rate r (pooled over the 5 H pairs),
    lower95 = BetaInv(0.05; r H, H - r H + 1),   SUPPORTED iff lower95 > 0.5
(and no WRONG, which this script does not model). This bound treats the five
pairs of a condition as ONE observation: it is valid however strongly the
pairs of a condition are correlated.

DESIGN REQUIREMENT, fixed before this script was run: the smallest H for
which an observed r = 0.80 still supports H_PRIMARY. r = 0.80 is the rate
left when one of the five fault levels resolves no pair at all and the other
four resolve every pair, so the primary result may not hinge on any single
level.

Power is reported under two models of the true per-pair resolution
probability pi:
  CORRELATED   all pairs of a condition resolve together (X ~ Bin(H, pi)
               conditions resolved; exact)
  INDEPENDENT  every pair resolves on its own (Monte Carlo, frozen seed)
"""
import json
from pathlib import Path

import numpy as np
from scipy.special import betainc
from scipy.stats import beta, binom

HERE = Path(__file__).resolve().parent
LEVELS = 5
NULL = 0.5
ALPHA = 0.05
SEED = 20260926
N_MC = 200_000
N_SECONDARY = 8


def lower95(r, h):
    x = r * h
    return 0.0 if x <= 0 else float(beta.ppf(ALPHA, x, h - x + 1))


def p_value(r, h):
    x = r * h
    return 1.0 if x <= 0 else float(betainc(x, h - x + 1, NULL))


def min_passing_rate(h):
    """Smallest pooled rate on the attainable grid k / (5 H) that passes."""
    for k in range(LEVELS * h + 1):
        r = k / (LEVELS * h)
        if lower95(r, h) > NULL:
            return r
    return None


def power_correlated(pi, h):
    return float(sum(binom.pmf(x, h, pi) for x in range(h + 1) if lower95(x / h, h) > NULL))


def power_independent(pi, h, rng):
    k = rng.binomial(LEVELS * h, pi, size=N_MC)
    ok = np.array([lower95(v / (LEVELS * h), h) > NULL for v in range(LEVELS * h + 1)])
    return float(ok[k].mean())


def per_level_holm_pass(k, h):
    """H4 at one level: h pairs, one per condition; worst case of Holm, where
    the level's p-value is multiplied by the full family size of eight."""
    p = p_value(k / h, h)
    return {"p": p, "p_times_8": min(1.0, p * N_SECONDARY), "passes_worst_case": p * N_SECONDARY < ALPHA}


def main():
    rng = np.random.default_rng(SEED)
    hs = (6, 8, 10, 11, 12, 16)
    rates = (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7)
    table = {str(h): {f"{r:.2f}": round(lower95(r, h), 4) for r in rates} for h in hs}
    boundary = {str(h): min_passing_rate(h) for h in hs}
    required = min(h for h in range(2, 40) if lower95(0.80, h) > NULL)
    pis = (1.0, 0.95, 0.9, 0.85, 0.8)
    power = {str(h): {f"{pi:.2f}": {"correlated": round(power_correlated(pi, h), 4),
                                    "independent": round(power_independent(pi, h, rng), 4)} for pi in pis}
             for h in (8, 10, 11, 12)}
    out = {
        "rule": "SUPPORTED iff BetaInv(0.05; rH, H - rH + 1) > 0.5 and no WRONG",
        "design_requirement": "smallest H with lower95(r = 0.80) > 0.5",
        "smallest_H_meeting_requirement": required,
        "lower95_by_H_and_rate": table,
        "smallest_passing_rate_by_H": boundary,
        "power_by_H_and_true_rate": power,
        "H4_single_level_at_smallest_H": {f"{k}_of_{required}": per_level_holm_pass(k, required)
                                          for k in range(required, required - 4, -1)},
        "monte_carlo": {"seed": SEED, "draws": N_MC},
    }
    (HERE / "POWER.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"smallest_H": required, "smallest_passing_rate": boundary[str(required)],
                      "lower95": table[str(required)], "power": power[str(required)]}, indent=1))


if __name__ == "__main__":
    main()
