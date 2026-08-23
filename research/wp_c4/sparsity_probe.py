"""WP-C4 Part 2.4 — is the effective-signature gap an artifact of sparsity?

The live objection: CSIA's signature matrix has 19 entries over 8 hypotheses,
about 2.4 features each, and SOI(gps_fault) = 1 holds precisely because
`phys_gps` is its SOLE feature. If the gap kappa(S_eff) - kappa(S) vanishes
as density rises, the defensible claim narrows from "design-time analysis
overstates isolability" to "SPARSE signature matrices are fragile to
self-occlusion" — a smaller and different statement.

Controlled synthesis over the SAME gate structure:
  * one designated hypothesis h* closes `gvalid` (the gps_fault role); no
    other hypothesis closes anything, matching the source-derived CLOSES.
  * ARM A "uniform": every hypothesis, h* included, draws features uniformly
    from the whole feature pool.
  * ARM B "physically forced": h* draws ONLY from features that gvalid gates,
    because a GPS fault's evidence is necessarily GPS evidence. Others draw
    uniformly. This is the arm that matches reality.

The distinction between the arms is the crux: if the gap survives at density
in ARM B but not ARM A, the result is not about sparsity at all — it is about
a hypothesis whose evidence lives entirely behind a gate it closes.

Run:  PYTHONPATH=. python research/wp_c4/sparsity_probe.py
Out:  research/wp_c4/results/sparsity_probe.json
"""

import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c1.lattice import REQ, load_signatures         # noqa: E402
from research.wp_c3.effective_signature import (                # noqa: E402
    kappa_of, partition_of)
from research.wp_e1.gate_map import GATE_FEATURES               # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
SEED = 20260822
N_DRAWS = 400
N_HYPS = 8                      # 1 nominal + 7 faults, matching CSIA

FEATURES = sorted(REQ)
GVALID_GATED = sorted(GATE_FEATURES["gvalid"])


def synth(density, arm, rng):
    """One synthetic signature matrix. h1 is `nominal` (empty by definition);
    h2 is h*, the hypothesis that closes gvalid."""
    sig = {"h1_nominal": []}
    pool_star = GVALID_GATED if arm == "physically_forced" else FEATURES
    k_star = min(density, len(pool_star))
    sig["h2_star"] = sorted(rng.sample(pool_star, k_star))
    for i in range(3, N_HYPS + 1):
        sig[f"h{i}"] = sorted(rng.sample(FEATURES, min(density,
                                                       len(FEATURES))))
    return sig


def effective(sig):
    """h* silences everything gvalid gates; nobody else silences anything."""
    out = {}
    for h, feats in sig.items():
        if h == "h2_star":
            out[h] = sorted(f for f in feats if f not in GVALID_GATED)
        else:
            out[h] = sorted(feats)
    return out


def measure(sig):
    eff = effective(sig)
    k_s, k_eff = kappa_of(sig), kappa_of(eff)
    star_emptied = (bool(sig["h2_star"]) and not eff["h2_star"])
    # is h* absorbed into nominal specifically?
    pi = partition_of(eff)
    nom_class = next(m for s, m in pi.items() if "h1_nominal" in m)
    return {
        "kappa_S": k_s,
        "kappa_S_eff": k_eff,
        "gap": k_eff - k_s,
        "star_evidence_fully_silenced": star_emptied,
        "star_absorbed_into_nominal": "h2_star" in nom_class,
    }


def main() -> int:
    rng = random.Random(SEED)
    arms = {}
    for arm in ("uniform", "physically_forced"):
        rows = []
        for density in range(1, 9):
            draws = [measure(synth(density, arm, rng))
                     for _ in range(N_DRAWS)]
            gaps = [d["gap"] for d in draws]
            rows.append({
                "density_features_per_hypothesis": density,
                "n_draws": N_DRAWS,
                "mean_gap": round(sum(gaps) / len(gaps), 6),
                "max_gap": round(max(gaps), 6),
                "frac_gap_positive": round(
                    sum(1 for g in gaps if g > 1e-12) / len(gaps), 4),
                "frac_star_fully_silenced": round(
                    sum(1 for d in draws
                        if d["star_evidence_fully_silenced"]) / len(draws), 4),
                "frac_star_absorbed_into_nominal": round(
                    sum(1 for d in draws
                        if d["star_absorbed_into_nominal"]) / len(draws), 4),
                "mean_kappa_S": round(
                    sum(d["kappa_S"] for d in draws) / len(draws), 6),
            })
        arms[arm] = rows

    # The real system, for reference.
    real = load_signatures()
    real_density = round(sum(len(v) for v in real.values()) / len(real), 4)

    report = {
        "purpose": "does the effective-signature gap survive at density, or "
                   "is it an artifact of a sparse signature matrix?",
        "seed": SEED, "n_draws_per_cell": N_DRAWS,
        "feature_pool_size": len(FEATURES),
        "gvalid_gated_features": GVALID_GATED,
        "real_system": {
            "n_entries": sum(len(v) for v in real.values()),
            "mean_features_per_hypothesis": real_density,
            "gps_fault_features": sorted(real["gps_fault"]),
            "all_of_which_are_gvalid_gated": all(
                f in GVALID_GATED for f in real["gps_fault"]),
        },
        "arms": arms,
        "arm_definitions": {
            "uniform": "h* draws features uniformly from the whole pool",
            "physically_forced": "h* draws ONLY from gvalid-gated features, "
                                 "because a GPS fault's evidence is "
                                 "necessarily GPS evidence — this is the arm "
                                 "that matches the real system",
        },
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "sparsity_probe.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"real system: {report['real_system']['n_entries']} entries, "
          f"{real_density} features/hypothesis; gps_fault features "
          f"{report['real_system']['gps_fault_features']}, all gvalid-gated: "
          f"{report['real_system']['all_of_which_are_gvalid_gated']}\n")
    for arm, rows in arms.items():
        print(f"--- ARM: {arm} ---")
        print(f"{'density':>8s} {'mean gap':>10s} {'P(gap>0)':>10s} "
              f"{'P(h* silenced)':>15s} {'P(h*->nominal)':>15s}")
        for r in rows:
            print(f"{r['density_features_per_hypothesis']:>8d} "
                  f"{r['mean_gap']:>10.5f} {r['frac_gap_positive']:>10.3f} "
                  f"{r['frac_star_fully_silenced']:>15.3f} "
                  f"{r['frac_star_absorbed_into_nominal']:>15.3f}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
