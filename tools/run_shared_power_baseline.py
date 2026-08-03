"""Run the pre-registered shared-power baseline benchmark (slice 3D).

    python tools/run_shared_power_baseline.py \
      --campaign campaigns/shared_power_generalization_v1.json \
      --output campaigns/results/shared_power_baseline_v1.json

Evaluation only. All five systems consume identical inputs.
"""

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402

from csia.diagnosis import run_shadow  # noqa: E402
from csia.diagnosis.baselines import (observability_qualified,  # noqa: E402
                                      system_a_legacy, system_b_majority_vote,
                                      system_c_per_source,
                                      system_d_shared_rule)
from csia.diagnosis.bayes import CausalDiagnosis  # noqa: E402
from csia.diagnosis.shadow import features_over_time  # noqa: E402
from csia.experiments import EvidenceEnvironment, build  # noqa: E402
from csia.prediction import PredictionComparator  # noqa: E402
from csia.scenarios import sample_streams  # noqa: E402
from csia.sensors import Fault, generate_flight  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
RESOURCE = "MAIN_POWER_PACK"
SYSTEMS = ("A_LEGACY_SINGLE_SOURCE", "B_MAJORITY_VOTE",
           "C_PER_SOURCE_THRESHOLD", "D_SHARED_RESOURCE_RULE", "E_CSIA")


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def rate(k, n):
    lo, hi = wilson(k, n)
    return {"num": k, "den": n,
            "rate": None if n == 0 else round(k / n, 4),
            "ci95": [lo, hi]}


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


def set_metrics(pred, truth):
    pred, truth = set(pred), set(truth)
    tp = len(pred & truth)
    prec = tp / len(pred) if pred else (1.0 if not truth else 0.0)
    rec = tp / len(truth) if truth else (1.0 if not pred else 0.0)
    f1 = 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)
    union = pred | truth
    jac = 1.0 if not union else len(pred & truth) / len(union)
    if pred == truth:
        outcome = "EXACT"
    elif not pred:
        outcome = "NONE"
    elif pred < truth:
        outcome = "PARTIAL"
    elif pred > truth:
        outcome = "OVER"
    elif pred & truth:
        outcome = "UNDER"
    else:
        outcome = "INCORRECT"
    return {"outcome": outcome, "precision": round(prec, 4),
            "recall": round(rec, 4), "f1": round(f1, 4),
            "jaccard": round(jac, 4),
            "incorrect_blame": sorted(pred - truth)}


def evaluate(row, truth_flight):
    faults = faults_for(row)
    td = PredictionComparator(tick_hz=25.0).build(
        sample_streams(truth_flight, faults), 60.0)
    feats = features_over_time(td)
    t = td.t
    truth_set = tuple(row["expected_affected_sources"])
    is_shared = row["family"] == "POSITIVE_SHARED_POWER"

    obs = observability_qualified(t, feats, truth_set)

    verdicts, costs = {}, {}
    t0 = time.perf_counter()
    diag = CausalDiagnosis().run(td)
    va = system_a_legacy(t, diag.posterior, diag.causes, truth_set)
    costs["A_LEGACY_SINGLE_SOURCE"] = (time.perf_counter() - t0) / len(t) * 1e6
    verdicts["A_LEGACY_SINGLE_SOURCE"] = va

    for name, fn in (("B_MAJORITY_VOTE", system_b_majority_vote),
                     ("C_PER_SOURCE_THRESHOLD", system_c_per_source),
                     ("D_SHARED_RESOURCE_RULE", system_d_shared_rule)):
        t0 = time.perf_counter()
        verdicts[name] = fn(t, feats, truth_set)
        costs[name] = (time.perf_counter() - t0) / len(t) * 1e6

    t0 = time.perf_counter()
    run = run_shadow(faults, truth=truth_flight)
    costs["E_CSIA"] = (time.perf_counter() - t0) / len(t) * 1e6
    from csia.diagnosis.baselines import BaselineVerdict
    ve = BaselineVerdict("E_CSIA")
    if run.first_root is not None:
        ve.fault_detected, ve.abstained = True, False
        ve.affected_sources = tuple(sorted(run.first_root[2]))
        ve.t_root_cause = run.first_root[0]
        ve.t_first_detection = run.first_root[0]
        if run.first_root[1] == "H_SHARED_POWER_DEGRADATION":
            ve.shared_resource = RESOURCE
            ve.shared_vs_independent = "SHARED"
        elif run.first_root[1] == "H_MULTI_INDEPENDENT_IMU":
            ve.shared_vs_independent = "INDEPENDENT"
        if set(ve.affected_sources) == set(truth_set):
            ve.t_exact_set = run.first_root[0]
    verdicts["E_CSIA"] = ve

    onset = row["params"].get("onset", row["params"].get("imu0_onset", 0.0))
    out = {"scenario_id": row["scenario_id"], "family": row["family"],
           "partition": row["dataset_partition"],
           "adversarial": row["adversarial"],
           "truth_affected": list(truth_set),
           "truth_shared": is_shared,
           "configured_onset_s": onset,
           "observability": obs,
           "detectability_floor": is_shared and not obs["qualified"],
           "systems": {}}
    for name, v in verdicts.items():
        sm = set_metrics(v.affected_sources, truth_set)
        claimed_shared = v.shared_vs_independent == "SHARED"
        out["systems"][name] = {
            **v.to_dict(), **{"set_" + k: val for k, val in sm.items()},
            "root_cause_correct": bool(is_shared and claimed_shared),
            "incorrectly_claimed_shared": bool(not is_shared and claimed_shared),
            "latency_root_s": None if v.t_root_cause is None
            else round(v.t_root_cause - onset, 2),
            "latency_set_s": None if v.t_exact_set is None
            else round(v.t_exact_set - onset, 2),
            "tick_cost_us": round(costs[name], 1),
        }
    return out


def summarize(rows, system):
    pos = [r for r in rows if r["truth_shared"]]
    neg = [r for r in rows if not r["truth_shared"]]
    healthy = [r for r in rows if r["family"] == "NEGATIVE_HEALTHY"]
    obs_pos = [r for r in pos if r["observability"]["qualified"]]
    floor = [r for r in pos if r["detectability_floor"]]

    def g(r):
        return r["systems"][system]

    lat = sorted(g(r)["latency_root_s"] for r in pos
                 if g(r)["latency_root_s"] is not None)
    f1s = [g(r)["set_f1"] for r in rows]
    costs = sorted(g(r)["tick_cost_us"] for r in rows)

    def pct(xs, q):
        return None if not xs else xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]

    return {
        "root_cause_correct": rate(sum(1 for r in pos if g(r)["root_cause_correct"]),
                                   len(pos)),
        "root_cause_correct_observable":
            rate(sum(1 for r in obs_pos if g(r)["root_cause_correct"]),
                 len(obs_pos)),
        "incorrect_shared_on_negatives":
            rate(sum(1 for r in neg if g(r)["incorrectly_claimed_shared"]),
                 len(neg)),
        "clean_shared_activations":
            sum(1 for r in healthy if g(r)["incorrectly_claimed_shared"]),
        "exact_set": rate(sum(1 for r in rows if g(r)["set_outcome"] == "EXACT"),
                          len(rows)),
        "exact_set_positives":
            rate(sum(1 for r in pos if g(r)["set_outcome"] == "EXACT"), len(pos)),
        "exact_set_observable":
            rate(sum(1 for r in obs_pos if g(r)["set_outcome"] == "EXACT"),
                 len(obs_pos)),
        "set_outcome_counts": {
            o: sum(1 for r in rows if g(r)["set_outcome"] == o)
            for o in ("EXACT", "PARTIAL", "OVER", "UNDER", "INCORRECT", "NONE")},
        "incorrect_source_blame":
            rate(sum(1 for r in rows if g(r)["set_incorrect_blame"]), len(rows)),
        "abstention": rate(sum(1 for r in rows if g(r)["abstained"]), len(rows)),
        "source_f1_mean": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "source_jaccard_mean": round(
            sum(g(r)["set_jaccard"] for r in rows) / len(rows), 4) if rows else None,
        "detectability_floor_n": len(floor),
        "detectability_floor_correct":
            sum(1 for r in floor if g(r)["root_cause_correct"]),
        "latency_root": {"n": len(lat), "p50": pct(lat, 0.5),
                         "p90": pct(lat, 0.9), "p95": pct(lat, 0.95),
                         "max": lat[-1] if lat else None,
                         "censored": len(pos) - len(lat)},
        "tick_cost_us": {"median": pct(costs, 0.5), "p95": pct(costs, 0.95),
                         "p99": pct(costs, 0.99),
                         "max": costs[-1] if costs else None},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default=os.path.join(
        ROOT, "campaigns", "shared_power_generalization_v1.json"))
    ap.add_argument("--output", default=os.path.join(
        ROOT, "campaigns", "results", "shared_power_baseline_v1.json"))
    args = ap.parse_args()

    with open(args.campaign) as fh:
        campaign = json.load(fh)
    truth_flight = generate_flight()

    rows = [evaluate(r, truth_flight) for r in campaign["scenarios"]]

    strata = {"ALL": rows}
    for part in ("DEVELOPMENT", "VALIDATION", "BLIND_SYNTHETIC", "ADVERSARIAL"):
        strata[part] = [r for r in rows if r["partition"] == part]
    strata["DETECTABILITY_FLOOR"] = [r for r in rows if r["detectability_floor"]]
    strata["OBSERVABLE_POSITIVE"] = [
        r for r in rows if r["truth_shared"] and r["observability"]["qualified"]]
    for fam in ("NEGATIVE_INDEPENDENT", "NEGATIVE_SINGLE_SOURCE",
                "NEGATIVE_HEALTHY"):
        strata[fam] = [r for r in rows if r["family"] == fam]

    summary = {s: {sys_: summarize(v, sys_) for sys_ in SYSTEMS}
               for s, v in strata.items() if v}

    man = build("shared_power_baseline", EvidenceEnvironment.SIMULATION,
                dataset_id=campaign["campaign_id"],
                dataset_aggregate_hash=campaign["campaign_aggregate_hash"],
                output_paths=[args.output])
    doc = {"result_schema_version": "1.0.0", "result_type": "BASELINE_COMPARISON",
           "evidence_environment": EvidenceEnvironment.SIMULATION.value,
           "experiment_manifest": man.to_dict(),
           "payload": {"protocol": "docs/validation/SHARED_POWER_BASELINE_PROTOCOL.md",
                       "campaign_id": campaign["campaign_id"],
                       "campaign_aggregate_hash": campaign["campaign_aggregate_hash"],
                       "authorization": "SHADOW_ONLY",
                       "systems": list(SYSTEMS),
                       "stratum_sizes": {k: len(v) for k, v in strata.items()},
                       "summary": summary, "scenarios": rows}}
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    with open(args.output.replace(".json", "_manifest.json"), "w") as fh:
        json.dump(man.to_dict(), fh, indent=1, sort_keys=True)

    for stratum in ("BLIND_SYNTHETIC", "VALIDATION", "ADVERSARIAL",
                    "OBSERVABLE_POSITIVE", "DETECTABILITY_FLOOR"):
        if stratum not in summary:
            continue
        print(f"\n=== {stratum}  n={len(strata[stratum])} ===")
        print(f"  {'system':26s} {'root':>12s} {'exactSet':>12s} "
              f"{'F1':>6s} {'badShared':>10s} {'blame':>7s}")
        for sysname in SYSTEMS:
            s = summary[stratum][sysname]
            print(f"  {sysname:26s} "
                  f"{str(s['root_cause_correct']['rate']):>12s} "
                  f"{str(s['exact_set_positives']['rate']):>12s} "
                  f"{s['source_f1_mean']:>6} "
                  f"{str(s['incorrect_shared_on_negatives']['rate']):>10s} "
                  f"{str(s['incorrect_source_blame']['rate']):>7s}")
    print(f"\n-> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
