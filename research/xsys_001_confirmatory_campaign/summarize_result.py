#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign: descriptive breakdown of the frozen stage-2
result. Written and committed BEFORE unblinding.

It decides nothing. Every decision (primary, H1-H6, Holm, gating) is copied
unchanged from RESULTS.json, which the frozen stage 2 wrote. This script
only arranges what the report must show separately, as the grant requires:
  - the outcome taxonomy, with AMBIGUOUS_CORRECT never merged into WRONG;
  - results by eta level, with every level kept;
  - every WRONG as its own entry: primary configuration first, then the
    other valid configurations, then the V4 invalid-window negative control
    (where WRONG on A trials is the preregistered expectation);
  - what remains ambiguous: by eta, checkpoint, evidence and remaining
    hypotheses;
  - the latency kinds separately: detection, isolation/certification,
    action (not measurable) and computational;
  - spurious localizations on motors 1-3, nominal outcomes, and W_EST
    (EXPLORATORY, no inference).
The raw v2 localizations come from the sealed STAGE1.json, joined through
the opaque id already recorded in RESULTS.json.

Usage: summarize_result.py --results RESULTS.json --stage1 STAGE1.json
                           --stage1-record STAGE1_SEAL_RECORD.json --out RESULT_SUMMARY.json
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
A1 = REPO / "research" / "xsys_confirmatory_001" / "amendment_a1"
PRIMARY = "C3/V3_TEMPORAL"
V4 = "C3/V4_INVALID_WINDOW"
SYMPTOMATIC_LABELS = ("UNIQUE_CORRECT", "AMBIGUOUS_CORRECT", "WRONG", "UNSUPPORTED", "NO_EVIDENCE")
NOMINAL_LABELS = ("CORRECT_NO_EVIDENCE", "FALSE_ALARM", "WRONG")
H = {"A": "ACTUATION/mechanical", "B": "SENSOR/response_sensor"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dist(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "median": None, "min": None, "max": None, "p95": None, "mean": None}
    a = np.asarray(xs, float)
    return {"n": len(xs), "median": float(np.median(a)), "min": float(a.min()), "max": float(a.max()),
            "p95": float(np.percentile(a, 95)), "mean": float(a.mean())}


def tally(ts, cpv, labels):
    c = Counter(t["outcomes"].get(cpv, "NOT_EVALUATED") for t in ts)
    return {**{k: c.get(k, 0) for k in labels}, **{k: v for k, v in c.items() if k not in labels}}


def evidence_used(cpv, f):
    """The witnesses stage 1 gave v2 for this configuration (mirrors the frozen stage-1 plan)."""
    cp, v = cpv.split("/")
    rpm = f["rpm_T1"] if cp == "C1" else f["rpm_T3"]
    dyn, ctrl = "withheld", "withheld"
    if v in ("V1_DYN_ONLY", "V3_TEMPORAL"):
        dyn = f["dyn_T1"]
    if v in ("V2_CTRL_ONLY", "V3_TEMPORAL") and cp == "C3":
        ctrl = f["ctrl_T3"]
    if v == "V4_INVALID_WINDOW" and cp == "C3":
        dyn = f["dyn_T3_invalid"]
    stats = {"L": f["L_T1"] if cp == "C1" else f["L_T3"], "D": f["D_T3"] if v == "V4_INVALID_WINDOW" else f["D_T1"],
             "C": f["C_T3"]}
    return {"rpm_deficit_witness": rpm, "dyn_nominal_witness": dyn, "ctrl_nominal_witness": ctrl, "statistics": stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--stage1", required=True)
    ap.add_argument("--stage1-record", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--analysis-matrix", default=str(A1 / "ANALYSIS_MATRIX_A1.csv"))
    ap.add_argument("--flight-matrix", default=str(A1 / "FLIGHT_MATRIX_A1.csv"))
    a = ap.parse_args()
    res = json.loads(Path(a.results).read_text())
    s1 = json.loads(Path(a.stage1).read_text())["trials"]
    rec = json.loads(Path(a.stage1_record).read_text())
    fm = {r["flight_id"]: r for r in csv.DictReader(open(a.flight_matrix))}
    am = list(csv.DictReader(open(a.analysis_matrix)))
    levels = sorted({r["eta"] for r in am if r["kind"] == "A"}, reverse=True)
    trials = res["trials"]
    cpvs = sorted({c for t in trials.values() for c in t["outcomes"]})
    by_kind = {k: [t for t in trials.values() if t["kind"] == k] for k in ("A", "B", "N")}

    def nuis(t):
        r = fm[t["source_flight_id"]]
        return {"heading_deg": r.get("heading_deg"), "noise_segment_id": r.get("noise_segment_id"),
                "noise_segment_sim_s": r.get("noise_segment_sim_s"), "t_onset_s": r.get("t_onset_s")}

    def loc(t, cpv, motor="motor_0"):
        return s1[t["opaque_id"]]["verdicts"][cpv].get(motor)

    # ---- taxonomy
    taxonomy = {cpv: {"A": tally(by_kind["A"], cpv, SYMPTOMATIC_LABELS), "B": tally(by_kind["B"], cpv, SYMPTOMATIC_LABELS),
                      "A_plus_B": tally(by_kind["A"] + by_kind["B"], cpv, SYMPTOMATIC_LABELS),
                      "N": tally(by_kind["N"], cpv, NOMINAL_LABELS)} for cpv in cpvs}

    # ---- by eta (B trials carry the eta of their matched A flight)
    h4 = res["secondary"]["H4_generalization_across_eta"]["per_level"]
    eligible_pairs = defaultdict(dict)
    for t in trials.values():
        if t["kind"] in ("A", "B"):
            eligible_pairs[t["pair_id"]][t["kind"]] = t
    eligible_pairs = {p: v for p, v in eligible_pairs.items() if "A" in v and "B" in v}
    by_eta = {}
    for lv in levels:
        ta = [t for t in by_kind["A"] if t["eta"] == lv]
        tb = [t for t in by_kind["B"] if t["eta"] == lv]
        pr = [p for p in eligible_pairs.values() if p["A"]["eta"] == lv]
        wp = Counter((t["kind"], str(t["features_motor_0"]["rpm_T3"]), str(t["witness_T1_dyn"]), str(t["witness_T3_ctrl"]))
                     for t in ta + tb)
        by_eta[lv] = {
            "eligible_pairs": len(pr),
            "pairs_resolved_primary": sum(1 for p in pr if p["A"]["outcomes"].get(PRIMARY) == "UNIQUE_CORRECT"
                                          and p["B"]["outcomes"].get(PRIMARY) == "UNIQUE_CORRECT"),
            "H4_frozen_statistics": h4.get(lv) or h4.get(str(lv)),
            "outcomes": {cpv: {"A": tally(ta, cpv, SYMPTOMATIC_LABELS), "B": tally(tb, cpv, SYMPTOMATIC_LABELS)}
                         for cpv in cpvs},
            "wrong_primary": sum(1 for t in ta + tb if t["outcomes"].get(PRIMARY) == "WRONG"),
            "witness_patterns_kind_rpmT3_dynT1_ctrlT3": {"|".join(k): v for k, v in sorted(wp.items())},
            "detection_latency_s": {"A": dist([t["features_motor_0"]["detection_latency_s"] for t in ta]),
                                    "B": dist([t["features_motor_0"]["detection_latency_s"] for t in tb])},
            "certification_s_counts": {k: dict(Counter(
                "0.2" if t["outcomes"].get("C1/V3_TEMPORAL") == "UNIQUE_CORRECT" else
                "15.0" if t["outcomes"].get(PRIMARY) == "UNIQUE_CORRECT" else "not certified" for t in ts))
                for k, ts in (("A", ta), ("B", tb))},
        }

    # ---- every WRONG, individually
    def wrong_entry(t, cpv):
        cp, v = cpv.split("/")
        base = {"analysis_id": t["analysis_id"], "opaque_id": t["opaque_id"], "kind": t["kind"],
                "source_flight_id": t["source_flight_id"], "matched_a_flight_id": t["matched_a_flight_id"],
                "pair_id": t["pair_id"], "eta": t["eta"], "nuisance_id": t["nuisance_id"], **nuis(t),
                "checkpoint": cp, "variant": v}
        if t["kind"] == "N":
            per = s1[t["opaque_id"]]["verdicts"][cpv]
            return {**base, "true_cause": "NOMINAL (no fault)",
                    "motors_with_supported_cause": {m: l["supported"] for m, l in per.items()
                                                    if l is not None and l["verdict"] == "SUPPORTED"},
                    "localizations": {m: l for m, l in per.items() if l is not None}}
        lz = loc(t, cpv)
        return {**base, "true_cause": H[t["kind"]],
                "predicted_cause": lz["supported"] if lz else None,
                "v2_verdict": lz["verdict"] if lz else None,
                "candidate_set_initial": lz["initial_candidates"] if lz else None,
                "candidates_remaining": sorted(set(lz["supported"]) | set(lz["unresolved"])) if lz else None,
                "rejected": lz["rejected"] if lz else None,
                "evidence": lz["evidence"] if lz else None, "refuting_evidence": lz["refuting_evidence"] if lz else None,
                "unmeasurable": lz["unmeasurable"] if lz else None,
                "evidence_state": evidence_used(cpv, t["features_motor_0"]),
                "why_wrong": ("true cause rejected" if lz and H[t["kind"]] in {r["hypothesis"] for r in lz["rejected"]}
                              else "another cause SUPPORTED")}

    wrong = {"primary_configuration": [], "other_valid_configurations": [], "V4_invalid_window_negative_control": []}
    for cpv in cpvs:
        for t in sorted(trials.values(), key=lambda t: t["analysis_id"]):
            if t["outcomes"].get(cpv) == "WRONG":
                grp = ("primary_configuration" if cpv == PRIMARY else
                       "V4_invalid_window_negative_control" if cpv == V4 else "other_valid_configurations")
                wrong[grp].append(wrong_entry(t, cpv))
    wrong_counts = {g: len(v) for g, v in wrong.items()}

    # ---- remaining ambiguity
    amb = {}
    for cpv in cpvs:
        ts = [t for t in by_kind["A"] + by_kind["B"] if t["outcomes"].get(cpv) == "AMBIGUOUS_CORRECT"]
        pat = Counter()
        remaining = Counter()
        for t in ts:
            e = evidence_used(cpv, t["features_motor_0"])
            pat["|".join((t["kind"], t["eta"], str(e["dyn_nominal_witness"]), str(e["ctrl_nominal_witness"])))] += 1
            lz = loc(t, cpv)
            remaining[" + ".join(sorted(set(lz["supported"]) | set(lz["unresolved"])))] += 1
        amb[cpv] = {"count": len(ts),
                    "by_eta_kind": {lv: {k: sum(1 for t in ts if t["eta"] == lv and t["kind"] == k) for k in ("A", "B")}
                                    for lv in levels},
                    "evidence_patterns_kind_eta_dyn_ctrl": dict(sorted(pat.items())),
                    "hypotheses_remaining": dict(remaining)}
    amb_primary_trials = [{"analysis_id": t["analysis_id"], "kind": t["kind"], "eta": t["eta"],
                           "nuisance_id": t["nuisance_id"], **evidence_used(PRIMARY, t["features_motor_0"]),
                           "unmeasurable": loc(t, PRIMARY)["unmeasurable"]}
                          for t in sorted(by_kind["A"] + by_kind["B"], key=lambda t: t["analysis_id"])
                          if t["outcomes"].get(PRIMARY) == "AMBIGUOUS_CORRECT"]
    other_primary = {lab: [{"analysis_id": t["analysis_id"], "kind": t["kind"], "eta": t["eta"],
                            "nuisance_id": t["nuisance_id"], **evidence_used(PRIMARY, t["features_motor_0"]),
                            "v2_verdict": t["v2_verdict_motor_0"].get(PRIMARY)}
                           for t in sorted(by_kind["A"] + by_kind["B"], key=lambda t: t["analysis_id"])
                           if t["outcomes"].get(PRIMARY) == lab] for lab in ("UNSUPPORTED", "NO_EVIDENCE")}

    # ---- latency
    comp = [t["computational_latency_s"] for t in trials.values()]
    latency = {
        "detection_s_motor0_post_onset": {k: dist([t["features_motor_0"]["detection_latency_s"] for t in by_kind[k]])
                                          for k in ("A", "B")},
        "detection_missing_motor0": {k: sum(1 for t in by_kind[k] if t["features_motor_0"]["detection_latency_s"] is None)
                                     for k in ("A", "B")},
        "nominal_trials_with_any_motor_detection": sum(
            1 for t in by_kind["N"] if any(f["detection_latency_s"] is not None
                                           for f in s1[t["opaque_id"]]["features"].values())),
        "isolation_and_certification": {
            "rule": ("frozen: certified at C1 (t0 + 0.2 s) if C1/V3 is UNIQUE_CORRECT, else at C3 (t0 + 15 s) if "
                     "C3/V3 is UNIQUE_CORRECT, else not certified. v2 isolates and certifies in the same call, so "
                     "isolation latency equals certification latency here; both are resolved only to the two "
                     "preregistered checkpoints, not continuously"),
            "frozen_stage2_counts": res["latency"]},
        "action_latency": "NOT MEASURABLE: XSYS-001 takes no mitigating action; nothing was commanded after attribution",
        "computational_s_per_trial_stage1": dist(comp),
        "computational_s_total_stage1_sum_per_trial": float(np.sum(comp)),
        "stage1_process_wall_s_including_strace_and_freeze_verification": rec.get("wall_s_including_strace"),
    }

    # ---- spurious, nominal, W_EST
    spurious = {cpv: sorted({t["analysis_id"]: t["spurious_subjects"][cpv] for t in by_kind["A"] + by_kind["B"]
                             if t["spurious_subjects"].get(cpv)}.items()) for cpv in cpvs}
    nominal = {cpv: {t["analysis_id"]: t["outcomes"][cpv] for t in by_kind["N"]
                     if t["outcomes"].get(cpv) != "CORRECT_NO_EVIDENCE"} for cpv in cpvs}
    west_keys = sorted({k for t in trials.values() for k in t["w_est_exploratory"]})
    west = {"label": "EXPLORATORY - W_EST is not a preregistered hypothesis; descriptive only, no inference",
            "by_kind": {k: {w: dist([t["w_est_exploratory"][w] for t in by_kind[k]]) for w in west_keys}
                        for k in ("A", "B", "N")},
            "by_eta_A": {lv: {w: dist([t["w_est_exploratory"][w] for t in by_kind["A"] if t["eta"] == lv])
                              for w in west_keys} for lv in levels}}

    compact = [{"analysis_id": t["analysis_id"], "kind": t["kind"], "eta": t["eta"], "nuisance_id": t["nuisance_id"],
                "C1/V3": t["outcomes"].get("C1/V3_TEMPORAL"), "C3/V3": t["outcomes"].get(PRIMARY),
                "C3/V0": t["outcomes"].get("C3/V0_LOCAL_ONLY"), "C3/V4": t["outcomes"].get(V4),
                "v2_C3/V3": t["v2_verdict_motor_0"].get(PRIMARY),
                "rpm_T3": t["features_motor_0"]["rpm_T3"], "dyn_T1": t["witness_T1_dyn"], "ctrl_T3": t["witness_T3_ctrl"],
                "detection_s": t["features_motor_0"]["detection_latency_s"]}
               for t in sorted(trials.values(), key=lambda t: t["analysis_id"])]

    out = {
        "campaign_id": "XSYS-001-CONFIRMATORY",
        "label": "DESCRIPTIVE BREAKDOWN of the frozen stage-2 result; decides nothing",
        "inputs": {"results_sha256": sha256(a.results), "stage1_sha256": sha256(a.stage1),
                   "stage1_seal_record_sha256": sha256(a.stage1_record)},
        "decisions_copied_from_stage2": {
            "H_PRIMARY": res["primary"]["H_PRIMARY"], "primary": res["primary"],
            "secondary_interpretation": res["secondary_interpretation"],
            "H1": res["secondary"]["H1_early_dynamics_separation"]["H1"],
            "H2": res["secondary"]["H2_persistent_compensation_separation"]["H2"],
            "H3": res["secondary"]["H3_temporal_complementarity"]["H3"],
            "H4": res["secondary"]["H4_generalization_across_eta"]["H4"],
            "H4_levels_passing": res["secondary"]["H4_generalization_across_eta"]["levels_passing"],
            "H5": res["secondary"]["H5_safe_ambiguity"]["H5"], "H6": res["secondary"]["H6_no_wrong_cause_improvement"]["H6"],
            "holm_family": res["secondary_holm_family"]},
        "taxonomy": taxonomy,
        "by_eta": by_eta,
        "wrong_counts": wrong_counts,
        "wrong_individual": wrong,
        "ambiguity": amb, "ambiguous_primary_trials": amb_primary_trials,
        "unsupported_and_no_evidence_primary": other_primary,
        "latency": latency,
        "spurious_localizations_motors_1_3": spurious,
        "nominal_non_correct": nominal,
        "w_est_exploratory": west,
        "per_trial_compact": compact,
    }
    Path(a.out).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({"H_PRIMARY": out["decisions_copied_from_stage2"]["H_PRIMARY"], "wrong_counts": wrong_counts,
                      "taxonomy_primary": taxonomy.get(PRIMARY), "summary_sha256": sha256(a.out)}, indent=1))


if __name__ == "__main__":
    main()
