"""Ceiling-invariant evidence and the P7a/P7b/P7c comparison.

Development partition. Runs the invariant over every admissible action, every
plant, every magnitude on the frozen grid and several seeds, on both the change
loss and the point loss. A single violation invalidates the oracle
implementation and stops the phase.

Also measures what the prior phase asserted and this one has to re-earn: that
maximising current second moment is not the same objective as diagnosing well.
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_independent_validation import ceilings                # noqa: E402
from csia_independent_validation import partitions as pt        # noqa: E402
from csia_independent_validation.actions import energy_class    # noqa: E402

OUT = ROOT / ("research/active_evidence/independent_validation/results/"
              "ORACLE_TAXONOMY.json")

PLANTS = ("Q0", "Q1", "Q2")
MAGNITUDES = (0.002, 0.004, 0.006, 0.010, 0.020, 0.040)
LOSSES = ("change", "point")
N_SEEDS = 6


def main() -> int:
    seeds = pt.seeds("development")[:N_SEEDS]
    arena = ceilings.Arena()
    space = ceilings.candidates()

    invariant_reports: List[Dict] = []
    violations: List[Dict] = []
    for loss in LOSSES:
        for plant in PLANTS:
            for seed in seeds:
                for delta in MAGNITUDES:
                    report = ceilings.ceiling_invariant(
                        arena, plant, seed, delta, deployable=space,
                        loss=loss)
                    invariant_reports.append(
                        {k: report[k] for k in
                         ("plant", "seed", "delta", "loss", "oracle_action",
                          "oracle_loss", "holds")})
                    violations.extend(report["violations"])

    # P7a against P7b: is maximum excitation the same objective as good
    # diagnosis? The prior phase said no; this re-measures it independently.
    benchmark_rows: List[Dict] = []
    for plant in PLANTS:
        for seed in seeds:
            benchmark = ceilings.p7a_select(arena, plant, seed)
            for delta in MAGNITUDES:
                oracle_action, oracle_outcome = ceilings.p7b_select(
                    arena, plant, seed, delta, loss="change")
                benchmark_outcome = arena.run(benchmark, plant, seed, delta)
                benchmark_rows.append({
                    "plant": plant, "seed": seed, "delta": delta,
                    "p7a_action": benchmark.name,
                    "p7b_action": oracle_action.name,
                    "same_action": benchmark.name == oracle_action.name,
                    "p7a_loss": benchmark_outcome.loss("change"),
                    "p7b_loss": oracle_outcome.loss("change"),
                    "p7a_regret": ceilings.regret(
                        benchmark_outcome, oracle_outcome.loss("change")),
                    "p7a_energy_as": benchmark_outcome.energy_as,
                    "p7b_energy_as": oracle_outcome.energy_as,
                    "p7a_energy_class": energy_class(benchmark),
                    "p7b_energy_class": energy_class(oracle_action),
                })

    # P7c: chosen once per seed over the whole declared envelope.
    robust_rows: List[Dict] = []
    for seed in seeds:
        for loss in LOSSES:
            action, worst = ceilings.p7c_select(
                arena, seed, plants_in_envelope=PLANTS,
                magnitudes=MAGNITUDES, loss=loss)
            robust_rows.append({"seed": seed, "loss": loss,
                                "action": action.name, "worst_case_loss": worst,
                                "energy_as": action.energy_as})

    doc = {
        "schema": "csia.independent_validation.oracle_taxonomy/1",
        "partition": "development",
        "seeds": list(seeds),
        "partition_manifest_sha256": pt.manifest_hash(),
        "action_space_size": len(space),
        "ceiling_invariant": {
            "checks": len(invariant_reports),
            "violations": violations,
            "holds": not violations,
        },
        "p7a_versus_p7b": {
            "rows": benchmark_rows,
            "same_action_fraction":
                sum(r["same_action"] for r in benchmark_rows)
                / len(benchmark_rows),
            "median_p7a_regret_ohm":
                statistics.median(r["p7a_regret"] for r in benchmark_rows),
            "worst_p7a_regret_ohm":
                max(r["p7a_regret"] for r in benchmark_rows),
            "median_p7a_loss_over_p7b_loss": statistics.median(
                r["p7a_loss"] / r["p7b_loss"] for r in benchmark_rows
                if r["p7b_loss"] > 0),
        },
        "p7c": robust_rows,
        "reports": invariant_reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")

    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"ceiling invariant: {len(invariant_reports)} checks over "
          f"{len(space)} actions each, violations "
          f"{len(violations)}")
    comparison = doc["p7a_versus_p7b"]
    print(f"P7a agrees with P7b in "
          f"{comparison['same_action_fraction']:.1%} of cells")
    print(f"P7a median regret {comparison['median_p7a_regret_ohm']:.3e} ohm, "
          f"worst {comparison['worst_p7a_regret_ohm']:.3e} ohm")
    print("P7a loss / P7b loss, median: "
          f"{comparison['median_p7a_loss_over_p7b_loss']:.1f}x")
    for row in robust_rows:
        print(f"  P7c seed {row['seed']} loss {row['loss']}: "
              f"{row['action']} worst {row['worst_case_loss']:.3e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
