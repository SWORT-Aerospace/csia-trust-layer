"""The independent-validation campaign runner.

Implements the design fixed in ``PREREGISTRATION_AMENDMENT_1.md`` and adds
nothing to it. One main block, five ablation blocks, and a reduction that
reports both the preregistered change metric and the point metric side by side
with the predicate always named.

    python tools/research/iv_campaign.py --partition development
    python tools/research/iv_campaign.py --partition validation
    python tools/research/iv_campaign.py --partition final --open-the-seal

The sealed partition needs the flag spelled out, and the flag is one grep away
from anybody auditing this.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import statistics
import sys
import time
from dataclasses import replace
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_independent_validation import evaluator as ev            # noqa: E402
from csia_independent_validation import partitions as pt           # noqa: E402
from csia_independent_validation import strategies as st           # noqa: E402
from csia_independent_validation.plants import (SYNTHETIC_SENSING,  # noqa: E402
                                                Sensing)
from csia_independent_validation.runner import (ARMS, Campaign,     # noqa: E402
                                                Cell, DRIFT_STATES,
                                                MAGNITUDES, PLANTS,
                                                frontier,
                                                resolution_area, slice_rows)

RESULTS = ROOT / "research/active_evidence/independent_validation/results"

#: Ablation blocks, each varying one thing against the main configuration.
LAG_RATIOS = (0.5, 1.0, 2.0)
RINGING_V = (0.05, 0.20, 0.60)          # below, near and above the boundary
SENSING_ABLATIONS = {
    "scale_i_2pct": {"scale_i": 0.02},
    "sigma_i_0p2A": {"sigma_i": 0.2},
    "quantum_i_0p05A": {"quantum_i": 0.05},
    "delay_i_40ms": {"delay_i_s": 0.04},
    "quantum_v_10mV": {"quantum_v": 0.01},
    "delay_v_40ms": {"delay_v_s": 0.04},
}
TELEMETRY_ABLATIONS = {
    "dropout_20pct": {"dropout": 0.2},
    "jitter_2ms": {"timestamp_jitter_s": 0.002},
    "sample_phase_half": {"sample_phase": 0.5},
}
EXECUTIONS = ("full", "clipped", "aborted")

#: Ablations run on deployable arms and selectors only; P7b is omitted, as the
#: amendment says, because an exhaustive ceiling in every ablation cell is not
#: affordable and quoting the main-block value is the honest alternative.
ABLATION_ARMS = tuple(st.STRATEGIES) + tuple(st.SELECTORS)


def main_block(campaign: Campaign, seeds) -> List[Dict]:
    rows: List[Dict] = []
    for plant in PLANTS:
        for drift in DRIFT_STATES:
            for seed in seeds:
                for magnitude in MAGNITUDES:
                    cell = Cell(plant=plant, drift_state=drift,
                                magnitude=magnitude, seed=seed)
                    for arm in ARMS:
                        rows.append({**campaign.row(arm, cell),
                                     "block": "main"})
    return rows


def ablation_block(campaign: Campaign, seeds, *, name: str, cells) -> List:
    rows: List[Dict] = []
    for cell in cells:
        for arm in ABLATION_ARMS:
            rows.append({**campaign.row(arm, cell), "block": name})
    return rows


def ablation_cells(seeds) -> Dict[str, List[Cell]]:
    base = Sensing(**SYNTHETIC_SENSING)
    out: Dict[str, List[Cell]] = {}
    out["lag_error"] = [
        Cell(plant="Q1", drift_state="nominal", magnitude=magnitude,
             seed=seed, lag_ratio=ratio)
        for ratio in LAG_RATIOS for magnitude in MAGNITUDES for seed in seeds]
    out["unknown_ringing"] = [
        Cell(plant="Q1", drift_state="nominal", magnitude=magnitude,
             seed=seed, ringing_v=amplitude)
        for amplitude in RINGING_V for magnitude in MAGNITUDES
        for seed in seeds]
    out["sensing"] = [
        Cell(plant="Q1", drift_state="nominal", magnitude=magnitude,
             seed=seed, sensing=replace(base, **overrides))
        for overrides in SENSING_ABLATIONS.values()
        for magnitude in MAGNITUDES for seed in seeds]
    out["telemetry"] = [
        Cell(plant="Q1", drift_state="nominal", magnitude=magnitude,
             seed=seed, sensing=replace(base, **overrides))
        for overrides in TELEMETRY_ABLATIONS.values()
        for magnitude in MAGNITUDES for seed in seeds]
    out["execution"] = [
        Cell(plant="Q1", drift_state="nominal", magnitude=magnitude,
             seed=seed, execution=execution)
        for execution in EXECUTIONS for magnitude in MAGNITUDES
        for seed in seeds]
    return out


def reduce_rows(rows: List[Dict]) -> Dict:
    """Everything the report needs, computed once, with predicates named."""
    main = [r for r in rows if r["block"] == "main"]

    def per_arm(metric: str) -> Dict:
        out: Dict[str, Dict] = {}
        for arm in ARMS:
            for drift in DRIFT_STATES:
                subset = slice_rows(main, arm=arm, drift_state=drift)
                if not subset:
                    continue
                margins = [r["m_r_out"] for r in subset
                           if r["m_r_out"] is not None]
                errors = [r["ae_r"] for r in subset if r["ae_r"] is not None]
                out[f"{arm}/{drift}"] = {
                    "n": len(subset),
                    "A_s": resolution_area(subset, metric=metric),
                    "frontier": frontier(subset, metric=metric),
                    "median_m_r_out": (statistics.median(margins)
                                       if margins else None),
                    "median_ae_r": (statistics.median(errors)
                                    if errors else None),
                    "mean_energy_as": statistics.mean(
                        r["energy_as"] for r in subset),
                    "abstentions": sum(1 for r in subset
                                       if r["abstention"] is not None),
                }
        return out

    calibration: Dict[str, Dict] = {}
    by_state: Dict[str, List[Dict]] = collections.defaultdict(list)
    for row in main:
        if row["state"] is not None:
            by_state[row["state"]].append(row)
    for state, group in sorted(by_state.items()):
        resolved = [r for r in group if r["resolved"]]
        point_ok = [r for r in group if r["ae_r"] is not None
                    and r["ae_r"] < ev.TAU_R_RELATIVE * r["magnitude"]]
        calibration[state] = {
            "n": len(group),
            "resolved_fraction_change_metric": len(resolved) / len(group),
            "resolved_fraction_point_metric": len(point_ok) / len(group),
            "median_ae_r": statistics.median(
                r["ae_r"] for r in group if r["ae_r"] is not None),
            "meets_coverage_target_change":
                len(resolved) / len(group) >= ev.COVERAGE_TARGET,
            "meets_coverage_target_point":
                len(point_ok) / len(group) >= ev.COVERAGE_TARGET,
        }

    false_certificates = [
        {k: r[k] for k in ("arm", "plant", "drift_state", "magnitude", "seed",
                           "action", "m_r_out", "ae_r", "e_delta_r")}
        for r in main
        if r["state"] == "CERTIFIED_IN_MODEL" and not r["resolved"]]
    false_certificates_point = [
        {k: r[k] for k in ("arm", "plant", "drift_state", "magnitude", "seed",
                           "action", "ae_r")}
        for r in main
        if r["state"] == "CERTIFIED_IN_MODEL" and r["ae_r"] is not None
        and r["ae_r"] >= ev.TAU_R_RELATIVE * r["magnitude"]]

    interaction: Dict[str, Dict] = {}
    for metric in ("change", "point"):
        passive_with = resolution_area(
            slice_rows(main, arm="P0_passive", drift_state="elevated"),
            metric=metric)
        passive_without = resolution_area(
            slice_rows(main, arm="P0_passive", drift_state="nominal"),
            metric=metric)
        for arm in ARMS:
            with_drift = resolution_area(
                slice_rows(main, arm=arm, drift_state="elevated"),
                metric=metric)
            without = resolution_area(
                slice_rows(main, arm=arm, drift_state="nominal"),
                metric=metric)
            try:
                value = ev.drift_interaction(with_drift, without,
                                             passive_with, passive_without)
            except ValueError as error:
                value = f"undefined: {error}"
            interaction.setdefault(metric, {})[arm] = value

    plants: Dict[str, Dict] = {}
    for plant in PLANTS:
        subset = slice_rows(main, plant=plant)
        errors = [r["ae_r"] for r in subset if r["ae_r"] is not None]
        changes = [abs(r["e_delta_r"]) for r in subset
                   if r["e_delta_r"] is not None]
        plants[plant] = {
            "n": len(subset),
            "median_ae_r": statistics.median(errors) if errors else None,
            "median_abs_e_delta_r": (statistics.median(changes)
                                     if changes else None),
            "A_s_change": resolution_area(subset, metric="change"),
            "A_s_point": resolution_area(subset, metric="point"),
        }

    return {
        "per_arm_change_metric": per_arm("change"),
        "per_arm_point_metric": per_arm("point"),
        "resolve_predicates": {
            "change": "M_R_out > 0 with tau_R = 0.5 * |target change|",
            "point": "AE_R < 0.5 * |target change|"},
        "calibration_by_certificate_state": calibration,
        "false_certificates_change_metric": false_certificates,
        "false_certificates_point_metric": false_certificates_point,
        "drift_interaction_I_s": interaction,
        "by_plant": plants,
        "state_counts": dict(collections.Counter(
            r["state"] for r in main if r["state"] is not None)),
        "abstention_counts": dict(collections.Counter(
            r["abstention"] for r in rows if r["abstention"] is not None)),
    }


def run(partition: str, *, open_the_seal: bool) -> int:
    seeds = pt.seeds(partition,
                     i_am_opening_the_sealed_partition=open_the_seal)
    campaign = Campaign()
    started = time.time()

    rows = main_block(campaign, seeds)
    for name, cells in ablation_cells(seeds).items():
        rows.extend(ablation_block(campaign, seeds, name=name, cells=cells))
    elapsed = time.time() - started

    document = {
        "schema": "csia.independent_validation.campaign/1",
        "partition": partition,
        "seeds": list(seeds),
        "partition_manifest_sha256": pt.manifest_hash(),
        "preregistration": "PREREGISTRATION.md + PREREGISTRATION_AMENDMENT_1.md",
        "arms": list(ARMS),
        "plants": list(PLANTS),
        "magnitudes": list(MAGNITUDES),
        "drift_states": dict(DRIFT_STATES),
        "n_rows": len(rows),
        "plant_simulations": campaign.simulations,
        "elapsed_s": elapsed,
        "what_this_is_not": (
            "Simulator only. Synthetic pack, no chemistry, no hardware "
            "representativeness. Not a certified safety artifact. Nothing "
            "here promotes anything."),
        "reduction": reduce_rows(rows),
        "rows": rows,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"CAMPAIGN_{partition.upper()}.json"
    out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    print(f"wrote {out.relative_to(ROOT)}")
    print(f"{len(rows)} rows, {campaign.simulations} plant runs, "
          f"{elapsed:.1f} s")
    reduction = document["reduction"]
    print(f"false certificates (change metric): "
          f"{len(reduction['false_certificates_change_metric'])}")
    print(f"false certificates (point metric):  "
          f"{len(reduction['false_certificates_point_metric'])}")
    print("state counts:", reduction["state_counts"])
    print("abstentions:", reduction["abstention_counts"])
    print("A_s (point metric), nominal drift:")
    for key, stats in sorted(reduction["per_arm_point_metric"].items()):
        if key.endswith("/nominal"):
            print(f"  {key:28s} A_s {stats['A_s']:.3f}  "
                  f"frontier {stats['frontier']}  "
                  f"energy {stats['mean_energy_as']:.1f} A.s")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", required=True,
                        choices=("development", "calibration", "validation",
                                 "final"))
    parser.add_argument("--open-the-seal", action="store_true",
                        help="required for the sealed final partition")
    args = parser.parse_args()
    raise SystemExit(run(args.partition, open_the_seal=args.open_the_seal))
