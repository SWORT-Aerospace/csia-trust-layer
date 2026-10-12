#!/usr/bin/env python3
"""Condense a run_dry_run.sh output directory into DRY_RUN_RESULTS.json.

Keeps every decision, tally, manipulation-check value and failure-path
result; drops opaque ids (random per run) and local paths. Timing values
(computational latency) vary between runs; nothing else should.

Usage: summarize_dry_run.py <run_dry_run output dir> <out.json>
"""
import json
import sys
from pathlib import Path


def qc_summary(qc):
    def span(key, kinds):
        vals = [f["checks"][key] for f in qc["flights"].values()
                if key in f.get("checks", {}) and f["checks"].get("MC_onset_event") is not None
                and any(k in kinds for k in [kind_of(f)])]
        return [min(vals), max(vals)] if vals else None

    def kind_of(f):
        return "A" if "MC_eta_reached" in f.get("checks", {}) else "NB"

    b = [t["checks"] for t in qc["analysis_trials"].values() if "ratio_match_max_abs" in t.get("checks", {})]
    onset = [f["meta"]["t0_us"] - f["meta"]["t_param_update_us"] for f in qc["flights"].values() if "meta" in f]
    return {
        "flights": len(qc["flights"]),
        "flights_included": sum(f["decision"] == "INCLUDED" for f in qc["flights"].values()),
        "analysis_trials_included": sum(t["decision"] == "INCLUDED" for t in qc["analysis_trials"].values()),
        "A_eta_hat_post_minus_eta_range": [
            min(f["checks"]["eta_hat_post"] - float(n.split("eta")[1][:3]) / 100 for n, f in qc["flights"].items()
                if kind_of(f) == "A"),
            max(f["checks"]["eta_hat_post"] - float(n.split("eta")[1][:3]) / 100 for n, f in qc["flights"].items()
                if kind_of(f) == "A")],
        "A_rotor_equation_rms_range": span("rotor_equation_rms", ("A",)),
        "A_max_tilt_deg_range": span("max_tilt_deg_after_onset", ("A",)),
        "NB_max_tilt_deg_range": span("max_tilt_deg_after_onset", ("NB",)),
        "heading_error_deg_range": span("heading_error_deg", ("A", "NB")),
        "B_ratio_match_max_abs": max(x["ratio_match_max_abs"] for x in b) if b else None,
        "B_only_motor0_rpm_changed": all(x["MC_B_only_motor0_rpm_changed"] for x in b),
        "t0_minus_param_update_us_range": [min(onset), max(onset)] if onset else None,
        "failed_checks": {n: f["reason"] for n, f in qc["flights"].items() if f["decision"] == "EXCLUDED"},
    }


def results_summary(r):
    keep = ("label", "primary", "secondary_interpretation", "secondary_holm_family", "secondary",
            "pair_resolution_rate_by_variant_C3", "outcome_tallies", "v2_verdict_tallies_motor_0",
            "latency", "spurious_symptom_trials_C3_V3", "pairs", "exclusions")
    return {k: r[k] for k in keep}


def main():
    d, out = Path(sys.argv[1]), Path(sys.argv[2])
    full = json.loads((d / "full" / "RESULTS.json").read_text())
    excl = json.loads((d / "excl" / "RESULTS.json").read_text())
    res = {
        "label": "DRY RUN ON APPARATUS DATA - IN-SAMPLE FOR THE CALIBRATION - NOT CONFIRMATORY",
        "data": "apparatus sweep, eta 0.90..0.50 x 3 repeats (A) and eta 1.00 x 3 (NB); "
                "research/px4_actuator_effectiveness/raw_ulog/sweep/",
        "full_run": {"qc": qc_summary(json.loads((d / "full" / "QC.json").read_text())),
                     "results": results_summary(full)},
        "exclusion_path": {"withheld_flight": "sweep_eta070_r2", "pairs": excl["pairs"],
                           "exclusions": excl["exclusions"], "primary": excl["primary"]},
        "seal_path": {"stage2_refused": (d / "tamper.err").exists() and "refusing" in (d / "tamper.err").read_text(),
                      "message": (d / "tamper.err").read_text().strip() if (d / "tamper.err").exists() else None},
    }
    out.write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({"primary": full["primary"]["H_PRIMARY"], "qc": res["full_run"]["qc"]}, indent=1))


if __name__ == "__main__":
    main()
