"""Derived tables and plots from the committed raw artifacts.

Tables are CSV: text, diffable, and readable without a viewer. Plots are PNG
and exist because the task asks for them; each one is a direct rendering of the
CSV beside it, so a reader who distrusts the image can check the numbers.

Nothing here computes a result. It reshapes results that already exist.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/active_evidence/independent_validation"
RESULTS = BASE / "results"
TABLES = RESULTS / "tables"
PLOTS = RESULTS / "plots"


def _load(name: str) -> Optional[Dict]:
    path = RESULTS / name
    return json.loads(path.read_text()) if path.is_file() else None


def _write_csv(name: str, header: List[str], rows: List[List]) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    with (TABLES / name).open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  table {name} ({len(rows)} rows)")


def certificate_margin_versus_actual_error(campaign: Dict) -> None:
    rows = [[r["arm"], r["plant"], r["drift_state"], r["magnitude"],
             r["seed"], r["m_r_cert"], r["m_r_out"], r["e_delta_r"],
             r["ae_r"], r["state"]]
            for r in campaign["rows"]
            if r["block"] == "main" and r["m_r_cert"] is not None]
    _write_csv("certificate_margin_vs_error.csv",
               ["arm", "plant", "drift", "magnitude", "seed", "m_r_cert",
                "m_r_out", "e_delta_r", "ae_r", "state"], rows)

    PLOTS.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 4.5))
    axis.scatter([r[5] for r in rows], [r[8] for r in rows], s=4, alpha=0.25)
    axis.set_xlabel("certificate margin $M_R^{cert}$ (ohm)")
    axis.set_ylabel("independent point error $AE_R$ (ohm)")
    axis.set_yscale("log")
    axis.set_title("What the certificate believes against what it achieved")
    figure.tight_layout()
    figure.savefig(PLOTS / "margin_vs_error.png", dpi=110)
    plt.close(figure)
    print("  plot margin_vs_error.png")


def calibration_table(campaign: Dict) -> None:
    calibration = campaign["reduction"]["calibration_by_certificate_state"]
    rows = [[state, stats["n"], stats["resolved_fraction_change_metric"],
             stats["resolved_fraction_point_metric"], stats["median_ae_r"],
             stats["meets_coverage_target_change"],
             stats["meets_coverage_target_point"]]
            for state, stats in sorted(calibration.items())]
    _write_csv("calibration_by_state.csv",
               ["state", "n", "resolved_change", "resolved_point",
                "median_ae_r", "meets_target_change", "meets_target_point"],
               rows)


def frontier_table(campaign: Dict) -> None:
    rows = []
    for metric in ("change", "point"):
        table = campaign["reduction"][f"per_arm_{metric}_metric"]
        for key, stats in sorted(table.items()):
            arm, drift = key.split("/")
            rows.append([metric, arm, drift, stats["n"], stats["A_s"],
                         stats["frontier"], stats["mean_energy_as"],
                         stats["median_ae_r"], stats["abstentions"]])
    _write_csv("frontiers.csv",
               ["metric", "arm", "drift", "n", "A_s", "frontier",
                "mean_energy_as", "median_ae_r", "abstentions"], rows)

    PLOTS.mkdir(parents=True, exist_ok=True)
    table = campaign["reduction"]["per_arm_point_metric"]
    arms = sorted({key.split("/")[0] for key in table})
    figure, axis = plt.subplots(figsize=(8, 4.5))
    width = 0.38
    for offset, drift in ((-width / 2, "nominal"), (width / 2, "elevated")):
        values = [table.get(f"{arm}/{drift}", {}).get("A_s", 0.0)
                  for arm in arms]
        axis.bar([i + offset for i in range(len(arms))], values, width,
                 label=drift)
    axis.set_xticks(range(len(arms)))
    axis.set_xticklabels(arms, rotation=60, ha="right", fontsize=8)
    axis.set_ylabel("$A_s$ (point metric)")
    axis.set_title("Grid resolution area by arm and drift")
    axis.legend()
    figure.tight_layout()
    figure.savefig(PLOTS / "resolution_area.png", dpi=110)
    plt.close(figure)
    print("  plot resolution_area.png")


def matched_cost_table(campaign: Dict) -> None:
    rows = []
    for row in campaign["rows"]:
        if row["block"] != "main" or row["action"] is None:
            continue
        rows.append([row["arm"], row["energy_class"], row["energy_as"],
                     row["duration_s"], row["ae_r"], row["m_r_out"],
                     row["resolved"]])
    _write_csv("matched_cost.csv",
               ["arm", "energy_class", "energy_as", "duration_s", "ae_r",
                "m_r_out", "resolved"], rows)

    PLOTS.mkdir(parents=True, exist_ok=True)
    by_arm: Dict[str, List] = {}
    for arm, _, energy, _, error, _, _ in rows:
        if error is None:
            continue
        by_arm.setdefault(arm, []).append((energy, error))
    figure, axis = plt.subplots(figsize=(6.5, 4.5))
    for arm, points in sorted(by_arm.items()):
        energies = [p[0] for p in points]
        errors = [p[1] for p in points]
        axis.scatter(sum(energies) / len(energies),
                     sorted(errors)[len(errors) // 2], label=arm, s=36)
    axis.set_xlabel("mean energy (A.s)")
    axis.set_ylabel("median $AE_R$ (ohm)")
    axis.set_yscale("log")
    axis.set_title("Cost against accuracy")
    axis.legend(fontsize=7, ncol=2)
    figure.tight_layout()
    figure.savefig(PLOTS / "cost_pareto.png", dpi=110)
    plt.close(figure)
    print("  plot cost_pareto.png")


def unknown_boundary_table(unknown: Dict) -> None:
    rows = [[amplitude, stats["median_delta"], stats["routed_fraction"],
             stats["n"]]
            for amplitude, stats in unknown["unknown"]["by_amplitude"].items()]
    _write_csv("unknown_boundary.csv",
               ["ringing_v", "median_delta_sigmas", "routed_fraction", "n"],
               rows)

    PLOTS.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 4.2))
    axis.plot([r[1] for r in rows], [r[2] for r in rows], marker="o")
    boundary = unknown["unknown"]["boundary"].get("boundary_sigmas")
    if boundary is not None:
        axis.axvline(boundary, linestyle="--", color="grey",
                     label=f"boundary {boundary:.2f} sigma")
        axis.legend()
    axis.set_xlabel(r"$\delta_{unknown}$ (sigmas of sensor noise)")
    axis.set_ylabel("routed to UNKNOWN_OR_MODEL_MISMATCH")
    axis.set_title("Unknown-fault detectability")
    figure.tight_layout()
    figure.savefig(PLOTS / "unknown_boundary.png", dpi=110)
    plt.close(figure)
    print("  plot unknown_boundary.png")


def sensitivity_table(unknown: Dict) -> None:
    rows = [[parameter, stats["step"], stats["J_q_out"], stats["J_q_cert"],
             stats["mutation_detected"]]
            for parameter, stats in unknown["sensitivity"].items()]
    _write_csv("sensitivity.csv",
               ["parameter", "step", "J_q_out", "J_q_cert", "detected"], rows)


def oracle_table(taxonomy: Dict) -> None:
    rows = [[r["plant"], r["seed"], r["delta"], r["p7a_action"],
             r["p7b_action"], r["same_action"], r["p7a_loss"], r["p7b_loss"],
             r["p7a_regret"], r["p7a_energy_as"], r["p7b_energy_as"]]
            for r in taxonomy["p7a_versus_p7b"]["rows"]]
    _write_csv("p7a_versus_p7b.csv",
               ["plant", "seed", "delta", "p7a_action", "p7b_action",
                "same_action", "p7a_loss", "p7b_loss", "p7a_regret",
                "p7a_energy_as", "p7b_energy_as"], rows)


def worst_counterexample(campaign: Dict) -> None:
    """The single worst cell, by independent point error, among certified rows."""
    certified = [r for r in campaign["rows"]
                 if r["block"] == "main"
                 and r["state"] == "CERTIFIED_IN_MODEL"
                 and r["ae_r"] is not None]
    if not certified:
        print("  no certified rows; no worst counterexample")
        return
    worst = max(certified, key=lambda r: r["ae_r"])
    (RESULTS / "WORST_COUNTEREXAMPLE.json").write_text(
        json.dumps(worst, indent=1, sort_keys=True) + "\n")
    print(f"  worst certified cell: {worst['arm']} on {worst['plant']} "
          f"at {worst['magnitude']}, AE_R {worst['ae_r']:.6f} ohm")


def main() -> int:
    taxonomy = _load("ORACLE_TAXONOMY.json")
    unknown = _load("UNKNOWN_AND_SENSITIVITY.json")
    campaign = None
    for name in ("FINAL", "VALIDATION", "CALIBRATION"):
        campaign = _load(f"CAMPAIGN_{name}.json")
        if campaign is not None:
            print(f"using CAMPAIGN_{name}.json")
            break

    if taxonomy is not None:
        oracle_table(taxonomy)
    if unknown is not None:
        unknown_boundary_table(unknown)
        sensitivity_table(unknown)
    if campaign is not None:
        certificate_margin_versus_actual_error(campaign)
        calibration_table(campaign)
        frontier_table(campaign)
        matched_cost_table(campaign)
        worst_counterexample(campaign)
    else:
        print("no campaign artifact; campaign tables skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
