"""WP-C6 Part 2.1 — the interior between ARM A and ARM B.

WP-C4's density sweep tested two endpoints: a hypothesis drawing evidence
freely (containment 0) and one drawing only from the gated set (containment
1). Those are corners. This sweeps the interior.

Let a fraction rho of the target hypothesis's features lie inside C_h and
1 - rho outside, for rho in [0, 1] at several densities. The question:

    Is effective undetectability a THRESHOLD phenomenon at rho = 1, or does
    it degrade gracefully?

If a single feature outside C_h repairs the pair entirely, irreparability is
knife-edge, and the useful engineering statement is "one ungated relation
suffices" rather than anything about containment in general.

Run:  PYTHONPATH=. python research/wp_c6/partial_containment_sweep.py
Out:  research/wp_c6/results/partial_containment_sweep.json
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.lattice import REQ                          # noqa: E402
from research.wp_c3.effective_signature import (                # noqa: E402
    kappa_of, partition_of)
from research.wp_e1.gate_map import GATE_FEATURES               # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
SEED = 20260823
N_DRAWS = 400
N_HYPS = 8

FEATURES = sorted(REQ)
INSIDE = sorted(GATE_FEATURES["gvalid"])          # C_h
OUTSIDE = sorted(set(FEATURES) - set(INSIDE))


def synth(density, n_outside, rng):
    """h2 is the star hypothesis: n_outside of its features lie outside C_h."""
    n_inside = max(0, density - n_outside)
    sig = {"h1_nominal": []}
    feats = (rng.sample(INSIDE, min(n_inside, len(INSIDE)))
             + rng.sample(OUTSIDE, min(n_outside, len(OUTSIDE))))
    sig["h2_star"] = sorted(feats)
    for i in range(3, N_HYPS + 1):
        sig[f"h{i}"] = sorted(rng.sample(FEATURES, min(density,
                                                       len(FEATURES))))
    return sig


def effective(sig):
    """The star hypothesis silences everything gvalid controls."""
    return {h: (sorted(f for f in feats if f not in INSIDE)
                if h == "h2_star" else sorted(feats))
            for h, feats in sig.items()}


def measure(sig):
    eff = effective(sig)
    pi = partition_of(eff)
    nom = next(m for s, m in pi.items() if "h1_nominal" in m)
    return {
        "gap": kappa_of(eff) - kappa_of(sig),
        "star_absorbed": "h2_star" in nom,
        "star_effective_features": len(eff["h2_star"]),
    }


def main() -> int:
    rng = random.Random(SEED)
    grid = []
    for density in (1, 2, 3, 4, 6, 8):
        for n_outside in range(0, density + 1):
            rho = 1.0 - n_outside / density        # fraction INSIDE C_h
            draws = [measure(synth(density, n_outside, rng))
                     for _ in range(N_DRAWS)]
            gaps = [d["gap"] for d in draws]
            grid.append({
                "density": density,
                "n_features_outside_C": n_outside,
                "rho_fraction_inside_C": round(rho, 4),
                "mean_gap": round(sum(gaps) / len(gaps), 6),
                "frac_gap_positive": round(
                    sum(1 for g in gaps if g > 1e-12) / len(gaps), 4),
                "frac_star_absorbed_into_nominal": round(
                    sum(1 for d in draws if d["star_absorbed"]) / len(draws),
                    4),
            })

    # Threshold test: at each density, compare rho = 1 against the next step
    # down (exactly one feature outside).
    threshold = []
    for density in (1, 2, 3, 4, 6, 8):
        full = next(r for r in grid if r["density"] == density
                    and r["n_features_outside_C"] == 0)
        one_out = next((r for r in grid if r["density"] == density
                        and r["n_features_outside_C"] == 1), None)
        if one_out is None:
            continue
        threshold.append({
            "density": density,
            "absorbed_at_rho_1": full["frac_star_absorbed_into_nominal"],
            "absorbed_with_one_feature_outside":
                one_out["frac_star_absorbed_into_nominal"],
            "drop": round(full["frac_star_absorbed_into_nominal"]
                          - one_out["frac_star_absorbed_into_nominal"], 4),
        })

    knife_edge = all(t["absorbed_with_one_feature_outside"] < 1e-9
                     for t in threshold)

    # --- COUNTEREXAMPLE SEARCH ---------------------------------------------
    # WP-C3 stated Pi(S_eff) is no finer than Pi(S), justified as "S_eff <= S
    # entrywise, so equal columns stay equal". That justification is WRONG for
    # COLUMN-DEPENDENT deletion: if two hypotheses share a column in S and only
    # one of them silences, their columns separate in S_eff and the partition
    # gets FINER. Equal columns are preserved only under UNIFORM row deletion.
    # This searches for it rather than assuming either way.
    rng2 = random.Random(SEED + 1)
    neg, trials = [], 200000
    for _ in range(trials):
        d = rng2.choice([2, 3, 4, 6, 8])
        no = rng2.randint(0, d)
        sig = synth(d, no, rng2)
        eff = effective(sig)
        g = kappa_of(eff) - kappa_of(sig)
        if g < -1e-12:
            neg.append({"density": d, "n_outside": no, "gap": round(g, 6),
                        "S": sig, "S_eff": eff})
    counterexample = {
        "trials": trials,
        "n_negative_gap": len(neg),
        "fraction": round(len(neg) / trials, 6),
        "example": neg[0] if neg else None,
        "finding": (
            "Pi(S_eff) is NOT always coarser than Pi(S). The entrywise "
            "domination argument fails for column-dependent deletion: two "
            "hypotheses sharing a column in S separate in S_eff when only one "
            "of them silences. Equal columns are preserved only under UNIFORM "
            "row deletion, which is not what per-hypothesis silencing does."
            if neg else
            "No counterexample found in this search; the ordering held "
            "throughout."),
        "does_this_affect_the_real_system": (
            "No. In the deployed signature matrix only gps_fault silences "
            "anything, and its column is unique, so no shared column can be "
            "broken. WP-C3's computational verification on the real matrix "
            "stands. What fails is the GENERAL justification, not the "
            "instance."),
    }

    report = {
        "purpose": "sweep the interior between full and zero containment",
        "seed": SEED, "n_draws_per_cell": N_DRAWS,
        "C_h_features": INSIDE,
        "outside_features": OUTSIDE,
        "threshold_test": threshold,
        "is_knife_edge_at_rho_1": knife_edge,
        "coarsening_counterexample": counterexample,
        "verdict": (
            "THRESHOLD, not graceful. A single feature outside C_h removes "
            "absorption entirely at every density tested. Effective "
            "undetectability requires FULL containment of the present support; "
            "partial containment does not partially degrade it. The useful "
            "engineering statement is therefore 'one ungated relation "
            "suffices', which is a stronger and more actionable claim than "
            "anything about containment in general."
            if knife_edge else
            "GRACEFUL. Absorption persists with some features outside C_h; "
            "see the grid."),
        "grid": grid,
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS,
                           "partial_containment_sweep.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"{'density':>8s} {'#outside':>9s} {'rho':>6s} {'mean gap':>10s} "
          f"{'P(absorbed)':>12s}")
    for r in grid:
        print(f"{r['density']:>8d} {r['n_features_outside_C']:>9d} "
              f"{r['rho_fraction_inside_C']:>6.2f} {r['mean_gap']:>10.5f} "
              f"{r['frac_star_absorbed_into_nominal']:>12.3f}")
    print(f"\nthreshold test (rho=1 vs exactly one feature outside):")
    for t in threshold:
        print(f"  density {t['density']}: {t['absorbed_at_rho_1']:.3f} -> "
              f"{t['absorbed_with_one_feature_outside']:.3f} "
              f"(drop {t['drop']:.3f})")
    print(f"\nknife-edge at rho = 1: {knife_edge}")
    ce = report["coarsening_counterexample"]
    print(f"\ncoarsening counterexample search: {ce['n_negative_gap']} of "
          f"{ce['trials']} draws gave a NEGATIVE gap "
          f"({ce['fraction']:.4%})")
    print(f"  -> {ce['finding'][:120]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
