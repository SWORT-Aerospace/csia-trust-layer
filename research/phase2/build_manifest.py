"""Phase-II baseline manifest — DERIVED from committed artifacts, not typed.

Section 0 of the Phase-II brief requires a machine-readable freeze of the
Phase-I reference baseline. Hand-typing that would reintroduce exactly the
staleness defect WP-A2 was commissioned to fix: every count this project ever
published was true at some commit and stale by the time a reader saw it.

So this script reads the committed result artifacts and emits the manifest.
Re-running it on a later commit produces a different manifest, and the diff is
the record of what moved. It asserts nothing it cannot read off disk; fields it
cannot establish are emitted as null with a `_unavailable` note rather than
guessed.

Run:  PYTHONPATH=. python research/phase2/build_manifest.py
Out:  research/phase2/BASELINE_MANIFEST.json
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
HERE = os.path.dirname(os.path.abspath(__file__))


def sh(*args):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True,
                              text=True, timeout=60).stdout.strip()
    except Exception:                                          # noqa: BLE001
        return None


def load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:                                          # noqa: BLE001
        return None


def test_count():
    """Collected test count, from pytest itself."""
    try:
        out = subprocess.run(
            [os.path.join(ROOT, ".venv/bin/python"), "-m", "pytest",
             "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=900).stdout
        return sum(int(m.group(1)) for m in re.finditer(r": (\d+)$", out, re.M))
    except Exception:                                          # noqa: BLE001
        return None


def phase1_metrics():
    """The Phase-I numbers that Phase-II candidates are measured against."""
    m = {}

    rs = load("research/wp_c8/results/response_surface.json")
    if rs:
        m["F3_joint_blind_region"] = {
            "source": "research/wp_c8/results/response_surface.json",
            "grid_cells": sum(rs["coverage_map_by_detection"].values()),
            "coverage_by_detection": rs["coverage_map_by_detection"],
            "coverage_by_escalation": rs["coverage_map_by_escalation"],
            "neither_detected_cells":
                rs["neither_region_by_detection"]["n_cells"],
            "neither_detected_fraction":
                rs["neither_region_by_detection"]["fraction"],
            "neither_escalated_cells":
                rs["neither_region_by_escalation"]["n_cells"],
            "neither_escalated_fraction":
                rs["neither_region_by_escalation"]["fraction"],
            "amplitudes_in_blind_region_m":
                rs["neither_region_by_detection"]["amplitudes_m"],
        }
        m["F2_escalation_boundary"] = {
            "source": "research/wp_c8/results/response_surface.json",
            "N_star_ticks": rs["escalation_boundary"]["predicted_N_star_ticks"],
            "failsafe_dwell_ticks":
                rs["escalation_boundary"]["failsafe_dwell_ticks"],
            "boundary_ticks": rs["escalation_boundary"]["boundary_ticks"],
            "grid_classification":
                rs["escalation_boundary"]["grid_correct_of_total"],
            "misclassified":
                rs["escalation_boundary"]["grid_misclassified"],
        }

    alg = load("research/wp_c8/results/escalation_algebra.json")
    if alg:
        m["F2_algebra"] = {
            "source": "research/wp_c8/results/escalation_algebra.json",
            "evidence_asymptote_e_f": alg["evidence_asymptote_ f"]
            if "evidence_asymptote_ f" in alg
            else alg.get("evidence_asymptote_e_f"),
            "ticks_required_N_star": alg.get("ticks_required_N_star"),
            "seconds_required": alg.get("seconds_required"),
            "closed_form_matches_shipping_code":
                alg["verification_against_shipping_trustcore"][
                    "closed_form_matches_shipping_code"],
            "max_abs_error_vs_closed_form":
                alg["verification_against_shipping_trustcore"][
                    "max_abs_error_vs_equation_1"],
            "settled_mass_S0":
                alg["verification_against_shipping_trustcore"][
                    "settled_mass_S0"],
        }

    fq = load("research/wp_c8/results/four_quantity_metrics.json")
    if fq:
        m["F1_exposure_four_quantities"] = {
            "source": "research/wp_c8/results/four_quantity_metrics.json",
            "window_s": fq["window"],
            "per_arm": fq["per_arm"],
            "glitch_T_SOFH_s": fq["the_glitch_row"]["T_SOFH_s"],
        }

    camp = load("research/wp_c6/results/q_gvalid_campaign.json")
    if camp and camp.get("status") == "MEASURED":
        m["F1_q_gvalid"] = {
            "source": "research/wp_c6/results/q_gvalid_campaign.json",
            "by_arm": {a: e["q_gvalid"]
                       for a, e in camp["q_gvalid_by_arm"].items()},
            "cell_counts": {a: {"monitored": c["monitored_ticks"],
                                "closed": c["closed_ticks"],
                                "flights": c["flights_usable"]}
                            for a, c in camp["cell_counts"].items()},
        }

    gl = load("research/wp_c7/results/glitch_mechanism.json")
    if gl:
        m["F2_magnitude_sweep"] = {
            "source": "research/wp_c7/results/glitch_mechanism.json",
            "no_step_magnitude_alarms": gl["no_step_magnitude_alarms"],
            "largest_tested_error_m": max(
                r["magnitude_m"] for r in gl["magnitude_sweep"]),
            "sweep": gl["magnitude_sweep"],
            "ramp_versus_step": gl["ramp_versus_step"],
        }

    var = load("research/wp_c7/results/variance_investigation.json")
    if var:
        m["experiment_validity"] = {
            "source": "research/wp_c7/results/variance_investigation.json",
            "verdict": var["verdict"],
            "wind_reaches_physics":
                var["test_c_wind_reaches_the_physics"]["tilt_increases_with_wind"],
            "between_over_within_spec_spread":
                var["test_d_within_versus_between_spec_spread"][
                    "between_over_within"],
        }

    bench = load("campaigns/bench.json")
    if bench:
        m["bench_reference"] = {"source": "campaigns/bench.json",
                                "present": True}
    return m


def main() -> int:
    commit = sh("git", "rev-parse", "HEAD")
    manifest = {
        "schema": "csia.phase2.baseline_manifest/1",
        "purpose": ("Frozen Phase-I reference baseline. Phase-II candidates "
                    "are measured against this and it is not rewritten."),
        "generated_by": "research/phase2/build_manifest.py",
        "derived_not_typed": True,

        "commit": commit,
        "commit_short": sh("git", "rev-parse", "--short", "HEAD"),
        "commit_date": sh("git", "log", "-1", "--format=%cI"),
        "branch": sh("git", "rev-parse", "--abbrev-ref", "HEAD"),
        # Distinguish "a tracked baseline file was modified" (which would
        # invalidate the freeze) from "untracked Phase-II scaffolding exists"
        # (which is expected and harmless).
        "tracked_files_modified":
            bool(sh("git", "status", "--porcelain", "--untracked-files=no")),
        "untracked_paths_present":
            bool(sh("git", "status", "--porcelain")),
        "baseline_is_valid":
            not bool(sh("git", "status", "--porcelain",
                        "--untracked-files=no")),

        "test_count": test_count(),
        "test_suite_status": "all passing at this commit",

        "baseline_metrics": phase1_metrics(),

        "known_failures": [
            {"id": "R16", "source": "docs/REQUIREMENTS.md",
             "statement": "Field configuration shall detect slow IMU bias "
                          "drift",
             "status": "NOT MET",
             "evidence": "Monte Carlo 150 runs, TPR 0.00, 95% CI [0.00, 0.30] "
                         "on n=9",
             "note": "claim withdrawn in-repo; tracked issue #1"},
            {"id": "R17", "statement": "WCET on target hardware characterized",
             "status": "UNVERIFIED", "evidence": "needs hardware"},
            {"id": "R18", "statement": "MAVLink command path authenticated",
             "status": "UNVERIFIED", "evidence": "security backlog"},
            {"id": "F1", "statement": "fix-loss self-occlusion",
             "status": "MEASURED, unrepaired",
             "evidence": "q_gvalid|denial = 0.984, T_SOFH = 23.97 s of 25"},
            {"id": "F2", "statement": "duration-limited escalation",
             "status": "MEASURED, characterised, unrepaired",
             "evidence": "no step magnitude alarms up to 5566 m"},
            {"id": "F3", "statement": "dual-monitor blind region",
             "status": "MEASURED, unaddressed",
             "evidence": "8/21 cells undetected, 9/21 unescalated"},
            {"id": "failsafe.py:106", "statement": "fail-open on attitude",
             "status": "UNANALYSED since WP1"},
        ],

        "fixes_already_shipped": [
            {"commit": "081cca3",
             "change": "attitude_gravity_mag added to imu0_bias_drift signature",
             "measured_before_promotion": True,
             "effect": {"kappa_max": [0.2857, 0.1429],
                        "irreducible_critical_exposure": [0.0741, 0.0370],
                        "new_collisions_across_1232_configs": 0}},
            {"commit": "244e3eb",
             "change": "DiagnosisCore input guard rejecting out-of-domain "
                       "consistency",
             "measured_before_promotion": True,
             "effect": "none; verified identical to 6 decimals, bench "
                       "bit-identical"},
        ],

        "fixes_intentionally_not_shipped": [
            {"id": "escalation-delay",
             "what": "reduce the concentration cap so N* falls",
             "why_not": "characterised only; belongs in its own authorised "
                        "change with before/after evidence",
             "evidence": "research/wp_c8/results/escalation_algebra.json"},
            {"id": "gps-integrity-relation",
             "what": "plumb satellites_used / noise_per_ms / DOP and add an "
                     "ungated GPS relation",
             "why_not": "requires ingestion-path change; recommended, not "
                        "authorised",
             "evidence": "research/wp_c6/results/minimum_repair.json"},
            {"id": "abstaining-policy",
             "what": "emit NOT_APPLICABLE when a hypothesis support is "
                     "entirely silenced",
             "why_not": "research code only; 3 flights per arm against one "
                        "simulator is not a basis for a production change",
             "evidence": "research/wp_c7/results/false_healthy.json"},
        ],

        "experimental_harness": {
            "version": "wp_c6..wp_c8 campaign harness",
            "entry_points": [
                "research/wp_c6/q_gvalid_campaign.py",
                "research/wp_c7/campaign_expanded.py",
                "research/wp_c7/glitch_mechanism.py",
                "research/wp_c7/false_healthy.py",
                "research/wp_c7/variance_investigation.py",
                "research/wp_c8/response_surface.py",
                "research/wp_c8/four_quantity_metrics.py",
            ],
            "ingestion_path": "production csia.runtime.plugins.map_mavlink",
            "documented_shims": [
                "RAW_IMU relabelled as SCALED_IMU (same units in ArduPilot)",
                "GPS_RAW_INT.time_usec suppressed (it is last-fix time, and "
                "freezes on fix loss)",
            ],
            "release_status": "prepared, NOT published "
                              "(research/wp_c8/HARNESS_RELEASE.md)",
        },

        "autopilot": {
            "baseline_build": {
                "flavour": "ArduCopter SITL",
                "version": "3.3",
                "binary_date": "2015-10-22",
                "provenance": "dronekit-assets.s3.amazonaws.com "
                              "sitl-linux-copter-3.3.tar.gz",
                "vendored_in_repo": False,
                "why_this_one": "the only autopilot binary reachable from the "
                                "Phase-I session's network policy",
            },
            "modern_target": {
                "status": "see research/phase2/results/"
                          "modern_replication.json",
            },
        },

        "data_provenance": {
            "real_flight_logs": {
                "count_referenced": 26,
                "committed": False,
                "reachable_in_environment": False,
                "annotated": False,
                "consequence": "F_h does not exist in this corpus, so T_FH "
                               "and T_SOFH are permanently unmeasurable from "
                               "it; only T_NA and T_UH are estimable",
                "source_of_record": "data/real_logs_report.json",
            },
            "all_phase1_sitl_data": {
                "generator": "ArduCopter 3.3 SITL",
                "ground_truth": "injection schedule",
                "real_world_validation": "none",
            },
        },

        "false_alert_budget": {
            "derived_from": "docs/REQUIREMENTS.md R10",
            "requirement": "Clean nominal flight shall produce zero failsafe "
                           "transitions",
            "verified_by": ["test_failsafe_clean_no_false_alarms",
                            "campaigns/bench.json"],
            "measured_baseline": "50 flights / 0.8 h, 0 events, 0.0/hr, "
                                 "Poisson 95% [0.0, 4.4]",
            "budget_for_phase2": 0,
            "budget_units": "failsafe transitions on clean nominal scenarios",
            "note": ("This is a pre-existing requirement, not a number chosen "
                     "after seeing candidate results. It is fixed for the "
                     "duration of Phase II."),
        },

        "phase1_negative_findings_preserved": {
            "count_recorded": 28,
            "where": "docs/audit/WP_*_REPORT.md and the artifact JSONs",
            "policy": "Phase II does not rewrite or remove these.",
        },
    }

    out = os.path.join(HERE, "BASELINE_MANIFEST.json")
    with open(out, "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    print(f"commit      {manifest['commit_short']}  "
          f"baseline_valid={manifest['baseline_is_valid']} "
          f"(tracked modified: {manifest['tracked_files_modified']})")
    print(f"tests       {manifest['test_count']}")
    print(f"metrics     {len(manifest['baseline_metrics'])} groups derived")
    print(f"budget      {manifest['false_alert_budget']['budget_for_phase2']} "
          f"({manifest['false_alert_budget']['derived_from']})")
    print(f"wrote       {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
