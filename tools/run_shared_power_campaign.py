"""Run the frozen shared-power campaign, one partition at a time.

    python tools/run_shared_power_campaign.py DEVELOPMENT
    python tools/run_shared_power_campaign.py VALIDATION
    python tools/run_shared_power_campaign.py ADVERSARIAL
    python tools/run_shared_power_campaign.py BLIND_SYNTHETIC --reason "..."

BLIND_SYNTHETIC access is logged to datasets/reports/blind_evaluation_access.json
with the commit, campaign hash and a reason. Viewing blind results and then
changing code invalidates the campaign — the log is what makes that auditable.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.diagnosis import IsolationOutcome, run_shadow  # noqa: E402
from csia.experiments import EvidenceEnvironment, build  # noqa: E402
from csia.sensors import Fault, generate_flight  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
CAMPAIGN = os.path.join(ROOT, "campaigns", "shared_power_generalization_v1.json")
ACCESS_LOG = os.path.join(ROOT, "datasets", "reports",
                          "blind_evaluation_access.json")
RESOURCE = "MAIN_POWER_PACK"


def faults_for(row):
    p, fam = row["params"], row["family"]
    if fam == "NEGATIVE_HEALTHY":
        return []
    if fam == "NEGATIVE_INDEPENDENT":
        if p.get("mag_emi"):
            return [Fault("emi_spike", "mag", 25.0, 8.0,
                          {"amplitude": 10.0, "rate_hz": 12.0})]
        if p.get("gps_spoof"):
            return [Fault("gps_spoof", "gps", 20.0, 15.0,
                          {"drift": (3.0, 1.0, 0.0)})]
        return [Fault("bias_drift", "imu0", p["imu0_onset"], 30.0,
                      {"axis": 2, "rate": p["r0"], "channel": "accel"}),
                Fault("bias_drift", "imu1", p["imu1_onset"], 28.0,
                      {"axis": 2, "rate": p["r1"], "channel": "accel"})]
    out = []
    if p.get("depth_v", 0.0) > 0:
        out.append(Fault("power_sag", "battery", p["onset"], p["dur"],
                         {"depth_v": p["depth_v"]}))
    if p.get("rpm_loss", 0.0) > 0:
        out.append(Fault("power_sag", "motor_esc",
                         p["onset"] + p.get("delay", 0.0), p["dur"],
                         {"rpm_loss": p["rpm_loss"]}))
    return out


def evaluate(row, truth):
    truth_sources = tuple(row["expected_affected_sources"])
    shared = row["expected_shared_resource"]
    run = run_shadow(faults_for(row), truth=truth)
    outcome = run.isolation(truth_sources, shared_resource=shared) \
        if truth_sources else (
            IsolationOutcome.NONE.value if run.first_root is None
            else IsolationOutcome.INCORRECT_ISOLATION.value)

    peak = run.peak_confidence.get("H_SHARED_POWER_DEGRADATION", 0.0)
    support_ticks = sum(1 for r in run.reports for h in r.hypotheses
                        if h.hypothesis_id == "H_SHARED_POWER_DEGRADATION"
                        and h.confidence >= 0.30)
    active_ticks = sum(1 for r in run.reports for h in r.hypotheses
                       if h.hypothesis_id == "H_SHARED_POWER_DEGRADATION"
                       and h.confidence >= 0.60)
    onset = row["params"].get("onset", row["params"].get("imu0_onset", 0.0))
    shared_claimed = (run.first_root is not None
                      and run.first_root[1] == "H_SHARED_POWER_DEGRADATION")
    return {
        "scenario_id": row["scenario_id"], "family": row["family"],
        "isolation": outcome,
        "root": None if run.first_root is None else run.first_root[1],
        "affected": [] if run.first_root is None else list(run.first_root[2]),
        "shared_claimed": shared_claimed,
        "peak_shared": round(peak, 4),
        "peak_independent": round(run.peak_confidence.get(
            "H_MULTI_INDEPENDENT_IMU", 0.0), 4),
        "margin": round(peak - run.peak_confidence.get(
            "H_MULTI_INDEPENDENT_IMU", 0.0), 4),
        "ticks_above_support": support_ticks,
        "ticks_above_activation": active_ticks,
        "latency_s": None if run.latency(onset) is None
        else round(run.latency(onset), 2),
        "tick_cost_us": round(run.tick_cost_us, 1),
    }


def aggregate(rows):
    pos = [r for r in rows if r["family"] == "POSITIVE_SHARED_POWER"]
    neg = [r for r in rows if r["family"] != "POSITIVE_SHARED_POWER"]
    healthy = [r for r in rows if r["family"] == "NEGATIVE_HEALTHY"]
    indep = [r for r in rows if r["family"] == "NEGATIVE_INDEPENDENT"]

    cc = sum(1 for r in pos
             if r["isolation"] == IsolationOutcome.CORRECT_COMMON_CAUSE.value)
    bad_cc = sum(1 for r in neg if r["shared_claimed"])
    indep_ok = sum(1 for r in indep if not r["shared_claimed"])
    lat = sorted(r["latency_s"] for r in pos if r["latency_s"] is not None)

    def rate(k, n):
        return None if n == 0 else round(k / n, 4)

    counts = {}
    for r in rows:
        counts[r["isolation"]] = counts.get(r["isolation"], 0) + 1
    return {
        "n": len(rows), "n_positive": len(pos), "n_negative": len(neg),
        "correct_common_cause": cc,
        "correct_common_cause_rate": rate(cc, len(pos)),
        "incorrect_common_cause_on_negatives": bad_cc,
        "incorrect_common_cause_rate": rate(bad_cc, len(neg)),
        "correct_independent_discrimination": indep_ok,
        "independent_discrimination_rate": rate(indep_ok, len(indep)),
        "clean_flight_common_cause_activations":
            sum(1 for r in healthy if r["shared_claimed"]),
        "isolation_counts": counts,
        "latency_p50": lat[len(lat) // 2] if lat else None,
        "latency_p95": lat[int(0.95 * (len(lat) - 1))] if lat else None,
        "dwell_completion_rate": rate(
            sum(1 for r in pos if r["ticks_above_activation"] >= 25), len(pos)),
        "mean_tick_cost_us": round(
            sum(r["tick_cost_us"] for r in rows) / max(len(rows), 1), 1),
    }


def log_blind_access(reason, campaign, viewed=True):
    entry = {
        "timestamp_utc": build("blind_access").timestamp_utc,
        "git_commit": build("blind_access").git_commit,
        "campaign_id": campaign["campaign_id"],
        "campaign_aggregate_hash": campaign["campaign_aggregate_hash"],
        "initiated_by": "tools/run_shared_power_campaign.py",
        "reason": reason,
        "results_viewed": viewed,
        "code_changed_after_viewing": None,
        "note": "if code changes after this entry, this campaign becomes "
                "OBSERVED_EVALUATION and a new blind campaign is required",
    }
    log = {"accesses": []}
    if os.path.exists(ACCESS_LOG):
        with open(ACCESS_LOG) as fh:
            log = json.load(fh)
    log["accesses"].append(entry)
    os.makedirs(os.path.dirname(ACCESS_LOG), exist_ok=True)
    with open(ACCESS_LOG, "w") as fh:
        json.dump(log, fh, indent=1, sort_keys=True)
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("partition", choices=("DEVELOPMENT", "VALIDATION",
                                          "ADVERSARIAL", "BLIND_SYNTHETIC"))
    ap.add_argument("--reason", default="")
    args = ap.parse_args()

    with open(CAMPAIGN) as fh:
        campaign = json.load(fh)
    rows = [r for r in campaign["scenarios"]
            if r["dataset_partition"] == args.partition]
    if not rows:
        raise SystemExit(f"no scenarios in {args.partition}")

    if args.partition == "BLIND_SYNTHETIC":
        if not args.reason:
            raise SystemExit("--reason is required to access BLIND_SYNTHETIC")
        log_blind_access(args.reason, campaign)
        print("*** BLIND ACCESS LOGGED — implementation must now be frozen ***")

    truth = generate_flight()
    results = [evaluate(r, truth) for r in rows]
    agg = aggregate(results)

    man = build(f"shared_power_{args.partition.lower()}",
                EvidenceEnvironment.SIMULATION,
                dataset_id=campaign["campaign_id"],
                dataset_aggregate_hash=campaign["campaign_aggregate_hash"],
                dataset_partition=args.partition)
    out = os.path.join(ROOT, "experiments", "results",
                       f"shared_power_{args.partition.lower()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"result_schema_version": "1.0.0",
                   "result_type": "SCENARIO",
                   "evidence_environment": EvidenceEnvironment.SIMULATION.value,
                   "experiment_manifest": man.to_dict(),
                   "payload": {"partition": args.partition,
                               "authorization": "SHADOW_ONLY",
                               "aggregate": agg, "scenarios": results}},
                  fh, indent=1, sort_keys=True)

    print(f"=== {args.partition}  n={agg['n']} "
          f"(+{agg['n_positive']} / -{agg['n_negative']}) ===")
    print(f"  correct common cause      : {agg['correct_common_cause']}"
          f"/{agg['n_positive']}  ({agg['correct_common_cause_rate']})")
    print(f"  independent discrimination: "
          f"{agg['independent_discrimination_rate']}")
    print(f"  incorrect common cause    : "
          f"{agg['incorrect_common_cause_on_negatives']}/{agg['n_negative']} "
          f"({agg['incorrect_common_cause_rate']})")
    print(f"  clean-flight activations  : "
          f"{agg['clean_flight_common_cause_activations']}")
    print(f"  latency p50/p95           : {agg['latency_p50']} / "
          f"{agg['latency_p95']} s")
    print(f"  dwell completion          : {agg['dwell_completion_rate']}")
    print(f"  mean tick cost            : {agg['mean_tick_cost_us']} us")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
