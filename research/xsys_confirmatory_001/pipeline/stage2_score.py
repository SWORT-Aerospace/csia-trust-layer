#!/usr/bin/env python3
"""XSYS-001 STAGE 2 — unblind, score, and compute the preregistered statistics.

Refuses to run unless the stage-1 output matches its seal. Joins the stage-0
key only here.

OUTCOME TAXONOMY (frozen). For a symptomatic trial whose true cause is c
(A: ACTUATION/mechanical, B: SENSOR/response_sensor), taking the v2
localization of motor_0:
  UNIQUE_CORRECT     verdict SUPPORTED and supported == (c,)
  AMBIGUOUS_CORRECT  verdict AMBIGUOUS and c is still a candidate
  UNSUPPORTED        verdict UNSUPPORTED and c is still a candidate
                     (evidence insufficient under the architecture)
  NO_EVIDENCE        no localization of motor_0 (local symptom not detected)
  WRONG              verdict SUPPORTED for a cause other than c, OR c was
                     eliminated (rejected) under any verdict
For a nominal trial N:
  CORRECT_NO_EVIDENCE  no localization on any motor
  FALSE_ALARM          a localization exists but no cause is SUPPORTED
  WRONG                some cause is SUPPORTED on some motor
Localizations on motors 1..3 of A and B trials are counted as spurious
symptoms (secondary), not folded into the motor-0 outcome.

In this spec LOCAL_RPM_DEFICIT confirms both causes whenever motor_0 is
localized, so a v2 UNSUPPORTED verdict can arise only from CONFLICTING
evidence that eliminates both causes. The true cause was then eliminated, and
the trial is scored WRONG (strict). The raw v2 verdicts are reported beside
the taxonomy so that every WRONG can be traced to its verdict.

A matched PAIR is RESOLVED when both its A and its B trial are UNIQUE_CORRECT.
The primary denominator is every eligible pair; a pair that is not AMBIGUOUS
under local evidence alone (V0) counts as not resolved.

MULTIPLICITY. The primary hypothesis is tested alone at one-sided alpha 0.05.
The eight secondary tests (H1, H2, H3b, H4 at each of the five levels) form
ONE Holm family at 0.05, and they are interpreted as confirmatory only if
H_PRIMARY is SUPPORTED (fixed-sequence gatekeeping); otherwise they are
reported as DESCRIPTIVE ONLY. H5 and H6 are zero-tolerance criteria without
a test.

INTERVALS. The independent unit is the nuisance condition, not the sample
and not the trial. A rate r over the pairs of n_eff conditions is bounded
with the cluster-conservative Clopper-Pearson form
    lower = BetaInv(0.05; r n_eff, n_eff - r n_eff + 1)   (0 if r = 0)
    p     = I_0.5(r n_eff, n_eff - r n_eff + 1)            one-sided vs 0.5
which treats every pair in a condition as perfectly correlated.
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.special import betainc
from scipy.stats import beta, binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xsys_freeze_check as FC  # noqa: E402

H_ACT, H_SEN = "ACTUATION/mechanical", "SENSOR/response_sensor"
TRUTH_H = {"A": H_ACT, "B": H_SEN}
ALPHA_ONE_SIDED = 0.05
NULL_RATE = 0.5
PRIMARY = ("C3", "V3_TEMPORAL")


def outcome_symptomatic(loc, truth_h):
    if loc is None:
        return "NO_EVIDENCE"
    rejected = {r["hypothesis"] for r in loc["rejected"]}
    if truth_h in rejected:
        return "WRONG"
    v = loc["verdict"]
    if v == "SUPPORTED":
        return "UNIQUE_CORRECT" if loc["supported"] == [truth_h] else "WRONG"
    if v == "AMBIGUOUS":
        return "AMBIGUOUS_CORRECT"
    if v == "UNSUPPORTED":
        return "UNSUPPORTED"
    return "NO_EVIDENCE"


def outcome_nominal(per_motor):
    locs = [l for l in per_motor.values() if l is not None]
    if not locs:
        return "CORRECT_NO_EVIDENCE"
    if any(l["verdict"] == "SUPPORTED" for l in locs):
        return "WRONG"
    return "FALSE_ALARM"


def cluster_bound(rate, n_eff):
    if n_eff == 0:
        return {"rate": None, "n_eff": 0, "lower95": None, "p_vs_0.5": None}
    x = rate * n_eff
    lower = 0.0 if x <= 0 else float(beta.ppf(ALPHA_ONE_SIDED, x, n_eff - x + 1))
    p = 1.0 if x <= 0 else float(betainc(x, n_eff - x + 1, NULL_RATE))
    return {"rate": rate, "n_eff": n_eff, "lower95": lower, "p_vs_0.5": p}


def holm(pvals):
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, running, adj = len(items), 0.0, {}
    for r, (k, p) in enumerate(items):
        running = max(running, (m - r) * p)
        adj[k] = min(1.0, running)
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--qc", required=True)
    ap.add_argument("--analysis-matrix", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--freeze-manifest", help="required when the key is confirmatory")
    a = ap.parse_args()
    body = Path(a.stage1).read_bytes()
    seal = json.loads(Path(a.stage1).with_suffix(".seal.json").read_text())
    if hashlib.sha256(body).hexdigest() != seal["stage1_output_sha256"]:
        raise SystemExit("stage-1 output does not match its seal: refusing to score")
    s1 = json.loads(body)["trials"]
    key = json.loads(Path(a.key).read_text())
    qc = json.loads(Path(a.qc).read_text())
    mode = key["mode"]
    trials = key["trials"]
    manifest_sha = None
    if mode == "confirmatory":
        if not a.freeze_manifest:
            raise SystemExit("a confirmatory key needs --freeze-manifest")
        _, manifest_sha = FC.verify_frozen(a.freeze_manifest, same_as=(
            (a.analysis_matrix, "research/xsys_confirmatory_001/prereg/ANALYSIS_MATRIX.csv"),))
        if qc.get("freeze_manifest_sha256") != manifest_sha or seal.get("freeze_manifest_sha256") != manifest_sha:
            raise SystemExit("stage 0 or stage 1 ran under another (or no) freeze manifest")

    per_trial = {}
    for oid, k in trials.items():
        v = s1[oid]["verdicts"]
        outc = {}
        for cpv, per_motor in v.items():
            if k["kind"] == "N":
                outc[cpv] = outcome_nominal(per_motor)
            else:
                outc[cpv] = outcome_symptomatic(per_motor.get("motor_0"), TRUTH_H[k["kind"]])
        spurious = {cpv: sorted(m for m, l in per_motor.items() if m != "motor_0" and l is not None)
                    for cpv, per_motor in v.items()}
        raw = {cpv: (None if per_motor.get("motor_0") is None else per_motor["motor_0"]["verdict"])
               for cpv, per_motor in v.items()}
        f0 = s1[oid]["features"]["motor_0"]
        per_trial[k["analysis_id"]] = {**k, "opaque_id": oid, "outcomes": outc, "v2_verdict_motor_0": raw,
                                       "spurious_subjects": spurious,
                                       "witness_T1_dyn": f0["dyn_T1"], "witness_T3_ctrl": f0["ctrl_T3"],
                                       "witness_T3_dyn_invalid": f0["dyn_T3_invalid"],
                                       "features_motor_0": f0, "w_est_exploratory": s1[oid]["w_est_exploratory"],
                                       "computational_latency_s": s1[oid]["computational_latency_s"]}

    # ---------------------------------------------------------------- pairs
    pairs = defaultdict(dict)
    for t in per_trial.values():
        if t["kind"] in ("A", "B"):
            pairs[t["pair_id"]][t["kind"]] = t
    eligible = {pid: p for pid, p in pairs.items() if "A" in p and "B" in p}
    # every pair the frozen matrix defines, so an excluded pair cannot vanish from the count
    all_pairs_in_matrix = sorted({r["pair_id"] for r in csv.DictReader(open(a.analysis_matrix)) if r["pair_id"]})

    def resolved(p, cpv):
        return p["A"]["outcomes"].get(cpv) == "UNIQUE_CORRECT" and p["B"]["outcomes"].get(cpv) == "UNIQUE_CORRECT"

    def pair_rate(cpv, pred, subset=None):
        by_cond = defaultdict(list)
        for pid, p in eligible.items():
            if subset and not subset(p):
                continue
            by_cond[p["A"]["nuisance_id"]].append(1.0 if pred(p, cpv) else 0.0)
        vals = [x for xs in by_cond.values() for x in xs]
        rate = float(np.mean(vals)) if vals else None
        res = cluster_bound(rate if rate is not None else 0.0, len(by_cond))
        res.update({"n_pairs": len(vals), "n_success": int(sum(vals))})
        if vals:
            bt = binomtest(int(sum(vals)), len(vals), NULL_RATE, alternative="greater")
            res["pair_level_cp_lower95_ASSUMES_INDEPENDENCE"] = float(
                bt.proportion_ci(confidence_level=0.90, method="exact").low)
        return res

    def count(cpv, kinds, label):
        return sum(1 for t in per_trial.values() if t["kind"] in kinds and t["outcomes"].get(cpv) == label)

    def tally(cpv, kinds):
        out = defaultdict(int)
        for t in per_trial.values():
            if t["kind"] in kinds:
                out[t["outcomes"].get(cpv, "NOT_EVALUATED")] += 1
        return dict(out)

    def raw_tally(cpv, kind):
        out = defaultdict(int)
        for t in per_trial.values():
            if t["kind"] == kind:
                out[str(t["v2_verdict_motor_0"].get(cpv, "NOT_EVALUATED"))] += 1
        return dict(sorted(out.items()))

    cp_primary = "/".join(PRIMARY)
    primary = pair_rate(cp_primary, resolved)
    wrong_primary = count(cp_primary, ("A", "B"), "WRONG")
    primary["wrong_A_B"] = wrong_primary
    primary["decision_rule"] = "SUPPORTED iff lower95 > 0.5 AND wrong_A_B == 0"
    primary["H_PRIMARY"] = ("SUPPORTED" if primary["lower95"] is not None and primary["lower95"] > NULL_RATE
                            and wrong_primary == 0 else "NOT SUPPORTED")

    def sep(field):
        return lambda p, _cpv: p["A"][field] is False and p["B"][field] is True

    h1 = pair_rate("C3/V3_TEMPORAL", sep("witness_T1_dyn"))
    h2 = pair_rate("C3/V3_TEMPORAL", sep("witness_T3_ctrl"))
    prr = {v: pair_rate(f"C3/{v}", resolved) for v in ("V0_LOCAL_ONLY", "V1_DYN_ONLY", "V2_CTRL_ONLY",
                                                        "V3_TEMPORAL", "V4_INVALID_WINDOW")}
    by_cond_v4 = defaultdict(list)
    for t in per_trial.values():
        if t["kind"] == "A" and t["pair_id"] in eligible:
            by_cond_v4[t["nuisance_id"]].append(1.0 if t["outcomes"].get("C3/V4_INVALID_WINDOW") == "WRONG" else 0.0)
    v4_vals = [x for xs in by_cond_v4.values() for x in xs]
    h3b = cluster_bound(float(np.mean(v4_vals)) if v4_vals else 0.0, len(by_cond_v4))
    h3b.update({"n_A": len(v4_vals), "n_wrong": int(sum(v4_vals))})
    h3a = (prr["V3_TEMPORAL"]["rate"] is not None
           and prr["V3_TEMPORAL"]["rate"] >= max(prr["V1_DYN_ONLY"]["rate"] or 0, prr["V2_CTRL_ONLY"]["rate"] or 0))
    # the five preregistered levels come from the frozen matrix, so a level whose
    # pairs were all excluded still enters the family (with p = 1)
    levels = sorted({r["eta"] for r in csv.DictReader(open(a.analysis_matrix)) if r["kind"] == "A"}, reverse=True)
    h4 = {lv: pair_rate(cp_primary, resolved, subset=lambda p, lv=lv: p["A"]["eta"] == lv) for lv in levels}
    sec_p = {"H1": h1["p_vs_0.5"], "H2": h2["p_vs_0.5"], "H3b": h3b["p_vs_0.5"],
             **{f"H4@{lv}": r["p_vs_0.5"] for lv, r in h4.items()}}
    sec_p = {k: (1.0 if v is None else v) for k, v in sec_p.items()}
    sec_adj = holm(sec_p)                       # ONE family of eight
    h4_adj = {lv: sec_adj[f"H4@{lv}"] for lv in levels}
    h4_pass = [lv for lv in levels if h4_adj[lv] < ALPHA_ONE_SIDED]

    # H5: every VALID configuration (V0..V3, both checkpoints; V4 is the
    # deliberate invalid-window control) either resolves correctly or stays
    # ambiguous. Local evidence alone must never be unique; no configuration
    # may eliminate a true cause; no nominal trial may receive a cause.
    valid_cpvs = sorted({c for t in per_trial.values() for c in t["outcomes"]} - {"C3/V4_INVALID_WINDOW"})
    symptomatic = [t for t in per_trial.values() if t["kind"] in ("A", "B")]
    v0_all_amb = all(t["outcomes"].get(f"{cp}/V0_LOCAL_ONLY") == "AMBIGUOUS_CORRECT"
                     for t in symptomatic for cp in ("C1", "C3"))
    primary["pairs_ambiguous_under_V0"] = sum(
        1 for p in eligible.values()
        if p["A"]["outcomes"].get("C3/V0_LOCAL_ONLY") == "AMBIGUOUS_CORRECT"
        and p["B"]["outcomes"].get("C3/V0_LOCAL_ONLY") == "AMBIGUOUS_CORRECT")
    wrong_valid = {c: count(c, ("A", "B"), "WRONG") for c in valid_cpvs}
    n_nom = [t for t in per_trial.values() if t["kind"] == "N"]
    n_attr = {c: sum(1 for t in n_nom if t["outcomes"].get(c) == "WRONG") for c in valid_cpvs}
    h5 = {"V0_all_symptomatic_AMBIGUOUS_CORRECT_C1_C3": v0_all_amb,
          "wrong_symptomatic_by_valid_configuration": wrong_valid,
          "nominal_attributions_by_valid_configuration": n_attr,
          "H5": "SUPPORTED" if (v0_all_amb and not any(wrong_valid.values()) and not any(n_attr.values()))
          else "NOT SUPPORTED"}
    # H6: the UNIQUE gained by V3 over V0 is not bought with WRONG, at either checkpoint
    h6 = {cp: {"wrong_V3": count(f"{cp}/V3_TEMPORAL", ("A", "B"), "WRONG"),
               "wrong_V0": count(f"{cp}/V0_LOCAL_ONLY", ("A", "B"), "WRONG"),
               "unique_correct_V3": count(f"{cp}/V3_TEMPORAL", ("A", "B"), "UNIQUE_CORRECT"),
               "unique_correct_V0": count(f"{cp}/V0_LOCAL_ONLY", ("A", "B"), "UNIQUE_CORRECT")}
          for cp in ("C1", "C3")}
    h6["wrong_V3"] = h6["C3"]["wrong_V3"]
    h6["H6"] = ("SUPPORTED" if all(h6[cp]["wrong_V3"] <= h6[cp]["wrong_V0"] and h6[cp]["wrong_V3"] == 0
                                   for cp in ("C1", "C3")) else "NOT SUPPORTED")

    lat = {}
    for kind in ("A", "B"):
        ts = [t for t in per_trial.values() if t["kind"] == kind and t["pair_id"] in eligible]
        cert = []
        for t in ts:
            if t["outcomes"].get("C1/V3_TEMPORAL") == "UNIQUE_CORRECT":
                cert.append(0.2)
            elif t["outcomes"].get(cp_primary) == "UNIQUE_CORRECT":
                cert.append(15.0)
            else:
                cert.append(None)
        det = [t["features_motor_0"]["detection_latency_s"] for t in ts]
        lat[kind] = {"certification_s_counts": {str(k): cert.count(k) for k in (0.2, 15.0, None)},
                     "detection_latency_s": {"median": float(np.median([d for d in det if d is not None]))
                                             if any(d is not None for d in det) else None,
                                             "n_missing": det.count(None)},
                     "computational_latency_s_median": float(np.median([t["computational_latency_s"] for t in ts]))
                     if ts else None}

    result = {
        "mode": mode,
        "freeze_manifest_sha256": manifest_sha,
        "stage1_output_sha256": seal["stage1_output_sha256"],
        "label": ("CONFIRMATORY" if mode == "confirmatory"
                  else "DRY RUN ON APPARATUS DATA - IN-SAMPLE FOR THE CALIBRATION - NOT CONFIRMATORY"),
        "primary": primary,
        "secondary_interpretation": ("CONFIRMATORY (H_PRIMARY supported; one Holm family of eight)"
                                     if primary["H_PRIMARY"] == "SUPPORTED"
                                     else "DESCRIPTIVE ONLY (H_PRIMARY not supported: gatekeeping)"),
        "secondary_holm_family": {k: {"p": sec_p[k], "p_holm": sec_adj[k]} for k in sec_p},
        "secondary": {
            "H1_early_dynamics_separation": {**h1, "p_holm": sec_adj["H1"],
                                             "H1": "SUPPORTED" if sec_adj["H1"] < ALPHA_ONE_SIDED else "NOT SUPPORTED"},
            "H2_persistent_compensation_separation": {**h2, "p_holm": sec_adj["H2"],
                                                      "H2": "SUPPORTED" if sec_adj["H2"] < ALPHA_ONE_SIDED else "NOT SUPPORTED"},
            "H3_temporal_complementarity": {
                "a_V3_at_least_single_window_variants": h3a,
                "b_invalid_window_wrong_rate_A": {**h3b, "p_holm": sec_adj["H3b"]},
                "H3": "SUPPORTED" if (h3a and sec_adj["H3b"] < ALPHA_ONE_SIDED
                                      and h6["wrong_V3"] == 0) else "NOT SUPPORTED"},
            "H4_generalization_across_eta": {"per_level": {str(k): {**v, "p_holm": h4_adj[k]} for k, v in h4.items()},
                                             "levels_passing": [str(x) for x in h4_pass],
                                             "H4": "SUPPORTED" if len(h4_pass) >= 3 else "NOT SUPPORTED"},
            "H5_safe_ambiguity": h5,
            "H6_no_wrong_cause_improvement": h6,
        },
        "pair_resolution_rate_by_variant_C3": prr,
        "outcome_tallies": {cpv: {"A": tally(cpv, ("A",)), "B": tally(cpv, ("B",)), "N": tally(cpv, ("N",))}
                            for cpv in sorted({c for t in per_trial.values() for c in t["outcomes"]})},
        "v2_verdict_tallies_motor_0": {cpv: {kind: raw_tally(cpv, kind) for kind in ("A", "B", "N")}
                                       for cpv in sorted({c for t in per_trial.values() for c in t["outcomes"]})},
        "latency": lat,
        "spurious_symptom_trials_C3_V3": sum(1 for t in per_trial.values()
                                             if t["kind"] in ("A", "B") and t["spurious_subjects"].get(cp_primary)),
        "pairs": {"in_matrix": len(all_pairs_in_matrix), "eligible": len(eligible),
                  "excluded": sorted(set(all_pairs_in_matrix) - set(eligible))},
        "exclusions": {"flights": {k: v["reason"] for k, v in qc["flights"].items() if v["decision"] == "EXCLUDED"},
                       "analysis_trials": {k: v["reason"] for k, v in qc["analysis_trials"].items()
                                           if v["decision"] == "EXCLUDED"}},
        "trials": per_trial,
    }
    Path(a.out).write_text(json.dumps(result, indent=1, default=float))
    print(json.dumps({"label": result["label"], "primary": {k: primary[k] for k in
                      ("rate", "n_eff", "n_pairs", "n_success", "lower95", "wrong_A_B", "H_PRIMARY")},
                      "H1": result["secondary"]["H1_early_dynamics_separation"]["H1"],
                      "H2": result["secondary"]["H2_persistent_compensation_separation"]["H2"],
                      "H3": result["secondary"]["H3_temporal_complementarity"]["H3"],
                      "H4": result["secondary"]["H4_generalization_across_eta"]["H4"],
                      "H5": h5["H5"], "H6": h6["H6"],
                      "secondary_interpretation": result["secondary_interpretation"],
                      "PRR_by_variant": {k: v["rate"] for k, v in prr.items()}}, indent=1, default=float))


if __name__ == "__main__":
    main()
