"""Build FINAL_SUMMARY.json from the committed result artifacts.

Every number in the final report comes from here rather than from a person
reading a table and typing it into prose. That is the whole reason this script
exists: the prior phase's headline numbers were arithmetically correct and
carried the wrong label, and a summary assembled by hand is exactly where that
happens.

Reads whatever is present and records what is missing rather than failing, so
a partial phase produces a partial summary that says so.
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics
import sys
from typing import Dict, List, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/active_evidence/independent_validation"
RESULTS = BASE / "results"


def _load(name: str) -> Optional[Dict]:
    path = RESULTS / name
    return json.loads(path.read_text()) if path.is_file() else None


def _campaign_summary(campaign: Optional[Dict]) -> Dict:
    if campaign is None:
        return {"status": "NOT_RUN"}
    reduction = campaign["reduction"]
    main = [r for r in campaign["rows"] if r["block"] == "main"]

    oracle: Dict[tuple, float] = {}
    for row in main:
        if row["arm"] == "P7b_oracle" and row["e_delta_r"] is not None:
            oracle[(row["plant"], row["drift_state"], row["magnitude"],
                    row["seed"])] = abs(row["e_delta_r"])

    regret: Dict[str, List[float]] = collections.defaultdict(list)
    violations: List[Dict] = []
    for row in main:
        if row["e_delta_r"] is None:
            continue
        key = (row["plant"], row["drift_state"], row["magnitude"],
               row["seed"])
        if key not in oracle:
            continue
        value = abs(row["e_delta_r"]) - oracle[key]
        regret[row["arm"]].append(value)
        if row["deployable"] and value < -1e-12:
            violations.append({k: row[k] for k in
                               ("arm", "plant", "drift_state", "magnitude",
                                "seed", "action", "e_delta_r")})

    return {
        "status": "RUN",
        "partition": campaign["partition"],
        "n_rows": campaign["n_rows"],
        "plant_simulations": campaign["plant_simulations"],
        "elapsed_s": campaign["elapsed_s"],
        "state_counts": reduction["state_counts"],
        "abstention_counts": reduction["abstention_counts"],
        "false_certificates_change_metric":
            len(reduction["false_certificates_change_metric"]),
        "false_certificates_point_metric":
            len(reduction["false_certificates_point_metric"]),
        "calibration_by_certificate_state":
            reduction["calibration_by_certificate_state"],
        "per_arm_change_metric": reduction["per_arm_change_metric"],
        "per_arm_point_metric": reduction["per_arm_point_metric"],
        "drift_interaction_I_s": reduction["drift_interaction_I_s"],
        "by_plant": reduction["by_plant"],
        "ceiling_invariant_violations": violations,
        "ceiling_invariant_holds": not violations,
        "median_regret_by_arm": {
            arm: statistics.median(values) for arm, values in regret.items()
            if values},
    }


def main() -> int:
    from csia_independent_validation import audit, partitions as pt

    provenance = json.loads((BASE / "BASE_PROVENANCE.json").read_text())
    taxonomy = _load("ORACLE_TAXONOMY.json")
    plant = _load("PLANT_INDEPENDENCE.json")
    unknown = _load("UNKNOWN_AND_SENSITIVITY.json")
    baselines = _load("BASELINES.json")

    document = {
        "schema": "csia.independent_validation.final_summary/1",
        "what_this_is_not": (
            "Simulator only. Synthetic pack, no chemistry claimed, no "
            "hardware representativeness implied. Not a certified safety "
            "artifact, not airworthy, not production-ready. Nothing here "
            "promotes anything."),
        "novelty_status": "BLOCKED_EXTERNAL_ACCESS",
        "provenance": {
            "branch": provenance["git"]["branch"],
            "base_head": provenance["git"]["head"],
            "ancestors_verified": provenance["git"]["ancestors_verified"],
            "frozen_core_digest":
                provenance["frozen_core"]["digest_of_digests"],
            "frozen_core_mismatches":
                provenance["frozen_core"]["per_file_mismatches"],
            "prior_partition_manifest":
                provenance["partitions"]["recorded_in_locked_artifact"],
            "iv_partition_manifest": pt.manifest_hash(),
        },
        "layer_separation": {
            "layer_a_modules": list(audit.LAYER_A_MODULES),
            "layer_a_leaks": audit.layer_a_leaks(),
            "truth_bearing_modules": sorted(audit.truth_bearing_modules()),
        },
        "prior_result_verification": {
            "frontier_margin_positive":
                provenance["recomputed"]["frontier_margin_positive"],
            "frontier_certified_and_positive":
                provenance["recomputed"]["frontier_certified_and_positive"],
            "paired_P2_vs_P6": provenance["recomputed"]["paired_P2_vs_P6"],
            "paired_P2_vs_P1": provenance["recomputed"]["paired_P2_vs_P1"],
            "plant_margin_identity":
                provenance["recomputed"]["plant_margin_identity"],
            "withdrawn": [
                "zero false certificates in 8640 runs, as evidence of "
                "soundness: the check was empty by construction",
                "the locked false-certificate check scored against plant "
                "truth: no row carried a true resistance",
            ],
        },
        "oracle_taxonomy": (
            None if taxonomy is None else {
                "ceiling_invariant_checks":
                    taxonomy["ceiling_invariant"]["checks"],
                "ceiling_invariant_violations":
                    len(taxonomy["ceiling_invariant"]["violations"]),
                "p7a_agreement_with_p7b":
                    taxonomy["p7a_versus_p7b"]["same_action_fraction"],
                "p7a_median_loss_ratio":
                    taxonomy["p7a_versus_p7b"][
                        "median_p7a_loss_over_p7b_loss"],
            }),
        "plant_independence": (
            None if plant is None else {
                "matched_cells":
                    plant["outcome_vs_certificate"]["matched_cells"],
                "cert_margin_identical": plant["outcome_vs_certificate"][
                    "cells_where_cert_margin_is_identical_across_plants"],
                "outcome_error_identical": plant["outcome_vs_certificate"][
                    "cells_where_outcome_error_is_identical_across_plants"],
                "by_plant": plant["outcome_vs_certificate"]["by_plant"],
            }),
        "unknown_boundary": (
            None if unknown is None else {
                "boundary": unknown["unknown"]["boundary"],
                "baseline_delta_no_fault":
                    unknown["unknown"]["baseline_delta_no_fault"],
                "by_amplitude": unknown["unknown"]["by_amplitude"],
            }),
        "sensitivity": (None if unknown is None
                        else unknown["sensitivity"]),
        "baselines": (
            None if baselines is None else {
                "provenance": baselines["provenance"],
                "a_optimal_for_r_equals_p7a":
                    baselines["design_rankings"][
                        "a_optimal_for_r_equals_p7a"],
                "set_membership_invalidation_threshold_volts":
                    baselines["set_membership_invalidation_threshold_volts"],
                "staleness_gap": {
                    "full_covers_truth":
                        baselines["staleness_gap"]["full_covers_truth"],
                    "truncated_covers_truth":
                        baselines["staleness_gap"]["truncated_covers_truth"],
                },
                "not_implemented": list(baselines["not_implemented"]),
            }),
        "campaigns": {
            name: _campaign_summary(_load(f"CAMPAIGN_{name.upper()}.json"))
            for name in ("calibration", "validation", "final")},
    }
    (BASE / "FINAL_SUMMARY.json").write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n")
    print("wrote FINAL_SUMMARY.json")
    for name, summary in document["campaigns"].items():
        print(f"  campaign {name:12s} {summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
