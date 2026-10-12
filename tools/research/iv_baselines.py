"""Closest prior-art baselines, run over the same action space and plants.

Textbook reconstructions, not reproductions of any paper: no scholarly full
text is reachable from this host and the access check is recorded in
``BASELINE_MAPPING.md``. Novelty status stays ``BLOCKED_EXTERNAL_ACCESS``.

Development partition.
"""
from __future__ import annotations

import json
import math
import pathlib
import statistics
import sys
from typing import Dict, List

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_independent_validation import baselines as bl                # noqa: E402
from csia_independent_validation import ceilings, partitions as pt     # noqa: E402
from csia_independent_validation.plants import (SYNTHETIC_SENSING,     # noqa: E402
                                                simulate)

OUT = ROOT / ("research/active_evidence/independent_validation/results/"
              "BASELINES.json")

SIGMA_V = SYNTHETIC_SENSING["sigma_v"]
DURATION_S = 8.0
MAGNITUDES = (0.0, 0.010, 0.020, 0.040)


def invalidation_threshold(plant: str, seed: int, *, action_name: str,
                           low: float = 0.001, high: float = 0.50,
                           steps: int = 40) -> float:
    """Smallest bounded-noise budget for which the two-parameter model survives.

    Bisection on the consistency bound. Below the returned value the feasible
    set is empty, which is the classical set-membership statement that the
    model is invalidated by the data.
    """
    from csia_independent_validation.actions import by_name
    action = by_name(action_name)
    observation, _ = simulate(action.command(), plant=plant,
                              duration=action.duration_s or DURATION_S,
                              seed=seed)
    current = np.asarray(observation.i_meas)[::8]
    voltage = np.asarray(observation.v_meas)[::8]
    for _ in range(steps):
        middle = 0.5 * (low + high)
        if bl.feasible_set(current, voltage, middle).empty:
            low = middle
        else:
            high = middle
    return high


def design_rankings(seed: int) -> Dict:
    """Does classical optimal design pick the same action as P7a?"""
    arena = ceilings.Arena()
    rows: List[Dict] = []
    for action in ceilings.candidates():
        observation, _ = arena.nominal(action, "Q1", seed)[0], None
        current = np.asarray(observation.i_meas)
        rows.append({
            "action": action.name,
            "s_ii": float(np.sum((current - current.mean()) ** 2)),
            "det_fisher": bl.d_optimal_score(current, SIGMA_V),
            "var_r_crb": bl.variance_of_r(current, SIGMA_V),
            "pe_level_order4": bl.persistent_excitation_level(current, 4),
            "energy_as": action.energy_as,
        })
    by_s_ii = max(rows, key=lambda r: r["s_ii"])["action"]
    by_var_r = min(rows, key=lambda r: r["var_r_crb"])["action"]
    by_det = max(rows, key=lambda r: r["det_fisher"])["action"]
    by_pe = max(rows, key=lambda r: r["pe_level_order4"])["action"]
    p7a = ceilings.p7a_select(arena, "Q1", seed).name
    return {
        "rows": rows,
        "argmax_s_ii": by_s_ii,
        "argmin_cramer_rao_var_r": by_var_r,
        "argmax_det_fisher": by_det,
        "argmax_persistent_excitation_order4": by_pe,
        "p7a_selection": p7a,
        "a_optimal_for_r_equals_p7a": by_var_r == p7a == by_s_ii,
    }


def discrimination(seed: int) -> Dict:
    """Finite-model active discrimination over the same action space."""
    from csia_independent_validation.actions import by_name
    rows: List[Dict] = []
    for action in ceilings.candidates():
        predictions = {}
        for magnitude in MAGNITUDES:
            observation, _ = simulate(
                action.command(), plant="Q1",
                duration=action.duration_s or DURATION_S, seed=seed,
                r0_delta=magnitude)
            predictions[f"{magnitude}"] = np.asarray(observation.v_meas)
        rows.append({"action": action.name,
                     "min_pairwise_separation_sigmas":
                         bl.pairwise_separation(predictions, SIGMA_V)})
    best = max(rows, key=lambda r: r["min_pairwise_separation_sigmas"])
    return {"rows": rows, "best_action": best["action"],
            "best_separation_sigmas":
                best["min_pairwise_separation_sigmas"]}


def staleness_gap(seed: int) -> Dict:
    """What the conventional fit reports on a window that was cut short.

    The RCEC routes a truncated execution to ``ABORTED_INCOMPLETE``. A
    classical post-execution fit has no such concept: it reports an interval
    with a t-statistic and no indication that the window it was computed on is
    not the window that was certified.
    """
    from csia_independent_validation.actions import by_name
    action = by_name("cosine3_10A_8s")
    observation, truth = simulate(action.command(), plant="Q1",
                                  duration=DURATION_S, seed=seed,
                                  r0_delta=0.020)
    full = bl.classical_fit(observation.i_meas, observation.v_meas)
    keep = int(observation.n * 0.25)
    cut = bl.classical_fit(observation.i_meas[:keep],
                           observation.v_meas[:keep])
    return {
        "true_r0": truth.r0_realized,
        "full_window": full.to_dict(),
        "truncated_to_25_percent": cut.to_dict(),
        "full_covers_truth": full.ci_low <= truth.r0_realized <= full.ci_high,
        "truncated_covers_truth":
            cut.ci_low <= truth.r0_realized <= cut.ci_high,
        "note": ("both intervals are reported with the same confidence "
                 "language; neither carries any signal that the second was "
                 "computed on a window that was cut short"),
    }


def main() -> int:
    seeds = pt.seeds("development")[:4]
    seed = seeds[0]
    doc = {
        "schema": "csia.independent_validation.baselines/1",
        "provenance": bl.PROVENANCE,
        "partition": "development",
        "seeds": list(seeds),
        "partition_manifest_sha256": pt.manifest_hash(),
        "implemented": list(bl.IMPLEMENTED),
        "not_implemented": bl.NOT_IMPLEMENTED,
        "design_rankings": design_rankings(seed),
        "discrimination": discrimination(seed),
        "set_membership_invalidation_threshold_volts": {
            plant: statistics.median(
                invalidation_threshold(plant, s,
                                       action_name="cosine3_10A_8s")
                for s in seeds)
            for plant in ("Q0", "Q1", "Q2")},
        "sensor_noise_sigma_v": SIGMA_V,
        "staleness_gap": staleness_gap(seed),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    rankings = doc["design_rankings"]
    print("optimal design:")
    print(f"  argmax S_II                 {rankings['argmax_s_ii']}")
    print(f"  argmin Cramer-Rao var(R)    "
          f"{rankings['argmin_cramer_rao_var_r']}")
    print(f"  argmax det Fisher           {rankings['argmax_det_fisher']}")
    print(f"  argmax PE level (order 4)   "
          f"{rankings['argmax_persistent_excitation_order4']}")
    print(f"  P7a benchmark               {rankings['p7a_selection']}")
    print(f"  A-optimal for R == P7a?     "
          f"{rankings['a_optimal_for_r_equals_p7a']}")
    print("finite-model discrimination best: "
          f"{doc['discrimination']['best_action']} at "
          f"{doc['discrimination']['best_separation_sigmas']:.3f} sigmas")
    print("set-membership invalidation threshold (V), sigma_V = "
          f"{SIGMA_V}:")
    for plant, value in doc[
            "set_membership_invalidation_threshold_volts"].items():
        print(f"  {plant}: {value:.4f}  ({value / SIGMA_V:.2f} sigma)")
    gap = doc["staleness_gap"]
    print("staleness gap: full covers truth "
          f"{gap['full_covers_truth']}, truncated covers truth "
          f"{gap['truncated_covers_truth']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
