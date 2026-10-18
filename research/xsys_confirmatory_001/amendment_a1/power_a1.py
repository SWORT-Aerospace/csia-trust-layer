#!/usr/bin/env python3
"""XSYS-001-A1: the sample-size calculation re-run for the amended nuisance design.

Uses no experimental data. It (1) recomputes the frozen XSYS-001 requirement
with the frozen functions of prereg/power_analysis.py and checks it against the
frozen prereg/POWER.json, and (2) asks what happens to the FROZEN decision
rule if conditions are NOT independent, which is the assumption the amendment
exists to secure.

Correlated-condition model: condition j is fully resolved with probability
p_j, p_j ~ Beta with mean pi and intra-class correlation rho_b between
conditions (beta-binomial). rho_b = 0 is the independence the amendment
establishes; rho_b > 0 shows the cost of the dependence the original design
had. The frozen rule is applied unchanged: SUPPORTED iff
BetaInv(0.05; X, n - X + 1) > 0.5 with X resolved conditions of n (pairs of a
condition resolve together: the conservative case of the frozen bound).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
X = HERE.parent
sys.path.insert(0, str(X / "prereg"))
import power_analysis as P  # noqa: E402  (frozen; imported, not modified)

SEED = 202609271
DRAWS = 400_000
N = 11


def pass_table(n):
    return np.array([P.lower95(x / n, n) > P.NULL for x in range(n + 1)])


def prob_pass(pi, rho_b, n, rng):
    ok = pass_table(n)
    if rho_b == 0:
        x = rng.binomial(n, pi, DRAWS)
    else:
        a = pi * (1 - rho_b) / rho_b
        b = (1 - pi) * (1 - rho_b) / rho_b
        x = rng.binomial(n, rng.beta(a, b, DRAWS))
    return float(ok[x].mean())


def main():
    rng = np.random.default_rng(SEED)
    frozen = json.loads((X / "prereg" / "POWER.json").read_text())
    required = min(h for h in range(2, 40) if P.lower95(0.80, h) > P.NULL)
    recomputed = {"smallest_H_meeting_requirement": required,
                  "lower95_at_H11": {f"{r:.2f}": round(P.lower95(r, N), 4) for r in (1.0, 0.95, 0.9, 0.85, 0.8)}}
    same = (required == frozen["smallest_H_meeting_requirement"]
            and all(recomputed["lower95_at_H11"][k] == frozen["lower95_by_H_and_rate"]["11"][k]
                    for k in recomputed["lower95_at_H11"]))
    rhos = (0.0, 0.02, 0.05, 0.1, 0.2)
    type1 = {f"{r}": prob_pass(0.5, r, N, rng) for r in rhos}
    power = {f"{pi}": {f"{r}": prob_pass(pi, r, N, rng) for r in rhos} for pi in (0.95, 0.9, 0.85)}
    out = {
        "requirement": "smallest H with lower95(r = 0.80) > 0.5 (frozen, XSYS-001)",
        "recomputed": recomputed, "identical_to_frozen_POWER_json": same,
        "decision_N": N,
        "why_N_stays_11": ("The frozen requirement assumes independent conditions and fully correlated pairs "
                           "within a condition. The amended design makes the first assumption true "
                           "(DESIGN_CHECK.json C1-C5), so the frozen calculation applies unchanged and 11 is "
                           "still the smallest count meeting it. Nothing was re-tuned to keep 11."),
        "frozen_rule_false_positive_rate_at_true_rate_0.5_by_between_condition_rho": type1,
        "frozen_rule_power_by_true_condition_resolution_rate_and_rho": power,
        "reading": ("Between-condition correlation inflates the frozen rule's false-positive rate above its "
                    "nominal 0.05, which is why independence must hold by construction rather than be "
                    "assumed. At rho_b = 0 the rate is at most 0.05."),
        "monte_carlo": {"seed": SEED, "draws": DRAWS},
    }
    (HERE / "POWER_A1.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("recomputed", "identical_to_frozen_POWER_json",
                                          "frozen_rule_false_positive_rate_at_true_rate_0.5_by_between_condition_rho",
                                          "frozen_rule_power_by_true_condition_resolution_rate_and_rho")}, indent=1))


if __name__ == "__main__":
    main()
