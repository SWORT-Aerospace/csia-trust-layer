"""The primary experiment: six arms, one raw stream, two objectives.

Endpoints are defined HERE, in code, and the Pareto classification is computed
by rule rather than read off a plot. The definitions were written before any
S2 arm had been run; the S0/S1 numbers they are calibrated against were already
committed from the previous work package.

  Objective O  operational correctness
               O = 1 - (ticks with raw OBSERVED_INVALID and A_gps == 1)
                       / (ticks with raw OBSERVED_INVALID)
               A_gps is the frozen core's fresh['gps'], the same value
               FailsafePolicy reads. Higher is better; 1.0 means the
               operational gate was never open on an invalid observation.

  Objective D  diagnostic preservation
               D = (post-onset ticks where gps_fault is the leading cause)
                   / (post-onset ticks)
               Higher is better. Secondary: the final gps_fault posterior.

Writes THREE_ARM_IMPLEMENTATION_AUDIT.json, THREE_ARM_REPLAY_RESULTS.csv,
OPERATIONAL_CORRECTNESS_RESULTS.json, DIAGNOSTIC_PRESERVATION_RESULTS.json,
PARETO_RESULTS.json and the clean-control results.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
OUT = os.path.join(_HERE, "results")
EPS_EQ = 1e-9


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
R = _load("_dual_replay", os.path.join(_HERE, "dual_replay.py"))
A = _load("_dual_arms", os.path.join(_HERE, "dual_arms.py"))


def objective_O(s):
    f = s["O_admissible_while_invalid_frac"]
    return None if f is None else round(1.0 - f, 6)


def objective_D(s):
    return s["D_top_share"]


def classify_pareto(pts, focus="S2c"):
    """Rule-based, on the two axes defined at the top of this file."""
    def ge(a, b):
        return a >= b - EPS_EQ

    def gt(a, b):
        return a > b + EPS_EQ

    fx, fy = pts[focus]
    out = {}
    for other in ("S0", "S1"):
        ox, oy = pts[other]
        if ge(fx, ox) and ge(fy, oy) and (gt(fx, ox) or gt(fy, oy)):
            out[other] = "DOMINATES"
        elif ge(ox, fx) and ge(oy, fy) and (gt(ox, fx) or gt(oy, fy)):
            out[other] = "IS_DOMINATED_BY"
        elif abs(fx - ox) <= EPS_EQ and abs(fy - oy) <= EPS_EQ:
            out[other] = "EQUAL"
        else:
            out[other] = "TRADEOFF"
    if out["S0"] == "DOMINATES" and out["S1"] == "DOMINATES":
        verdict = "PARETO_DOMINANT"
    elif out["S1"] == "DOMINATES":
        verdict = "PARETO_IMPROVING"
    elif "TRADEOFF" in out.values():
        verdict = "TRADEOFF_ONLY"
    else:
        verdict = "NO_IMPROVEMENT"
    return {"focus": focus, "pairwise": out, "verdict": verdict}


def run_set(messages, onset, arms=A.ARMS, tag=""):
    outs, summaries = {}, {}
    for arm in arms:
        out = R.replay(messages, arm)
        outs[arm] = out
        summaries[arm] = R.summarise(out, t_from=onset)
        s = summaries[arm]
        print(f"  {tag}{arm:<4} O={objective_O(s)}  D={objective_D(s)}  "
              f"post={s['D_final_post_gps_fault']}  "
              f"navdeg={s['O_nav_degraded_ticks']}  "
              f"evid_while_invalid={s['D_ticks_with_any_gps_evidence_while_invalid']}"
              f"/{s['n_ticks_obs_invalid']}")
    return outs, summaries


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    with open(FIXTURE, "rb") as fh:
        fixture_sha = hashlib.sha256(fh.read()).hexdigest()
    cap = H.load_fixture(FIXTURE)
    msgs, meta = cap["messages"], cap["meta"]
    onset = float(meta["t_inject_rel_s"])

    # ---- item 7: prove every arm consumed the same bytes ----------------
    stream_sha = hashlib.sha256(
        json.dumps(msgs, sort_keys=True, default=str).encode()).hexdigest()
    gps_sig = hashlib.sha256(repr([
        (m.get("fix_type"), m.get("satellites_visible"), m.get("h_acc"),
         m.get("_t_recv"))
        for m in msgs if m.get("mavpackettype") == "GPS_RAW_INT"
    ]).encode()).hexdigest()

    print("FAULT CONDITION (ArduPilot SIM_GPS1_JAM, N = 1 recording)")
    outs, summaries = run_set(msgs, onset)

    # ---- implementation audit -------------------------------------------
    audit = {
        "artifact": "THREE_ARM_IMPLEMENTATION_AUDIT",
        "fixture": meta["tag"],
        "fixture_sha256": fixture_sha,
        "message_stream_sha256": stream_sha,
        "gnss_stream_signature_sha256": gps_sig,
        "same_input_for_every_arm": True,
        "same_input_proof": "every arm is replayed from the identical decoded "
                            "message list in one process; the hash above is "
                            "taken once, before any arm runs",
        "frozen_constants_shared": {
            "EPS": __import__("csia.diagnosis.bayes",
                              fromlist=["EPS"]).EPS,
            "SMOOTH_ALPHA": __import__("csia.diagnosis.bayes",
                                       fromlist=["SMOOTH_ALPHA"]).SMOOTH_ALPHA,
            "EVIDENCE_MULT": __import__("csia.diagnosis.bayes",
                                        fromlist=["EVIDENCE_MULT"]).EVIDENCE_MULT,
            "PRIOR_NOMINAL": __import__("csia.diagnosis.bayes",
                                        fromlist=["PRIOR_NOMINAL"]).PRIOR_NOMINAL,
            "STALE_TIMEOUT_S_gps": H.GPS_STALE_TIMEOUT_S,
        },
        "arms": {arm: {"config": A.arm_config(arm),
                       "config_sha256": A.arm_config_hash(arm),
                       "causes_gps_fault": A.causes_for(arm)["gps_fault"]}
                 for arm in A.ARMS},
        "s1d_and_s2c_differ_only_in_d_coupling": (
            {k: v for k, v in A.arm_config("S1D").items()
             if A.arm_config("S2c").get(k) != v}),
    }
    with open(os.path.join(OUT, "THREE_ARM_IMPLEMENTATION_AUDIT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(audit, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # ---- per-arm summary table ------------------------------------------
    rows = []
    for arm in A.ARMS:
        s = dict(summaries[arm])
        s["objective_O"] = objective_O(s)
        s["objective_D"] = objective_D(s)
        s["condition"] = "M1_JAM"
        rows.append(s)
    cols = ["condition", "arm", "objective_O", "objective_D"] + \
        [k for k in rows[0] if k not in ("condition", "arm", "objective_O",
                                         "objective_D")]

    # ---- clean controls (item 19) ---------------------------------------
    print("\nCLEAN CONTROL A: real pre-onset segment of the same recording")
    clean_real = [m for m in msgs if float(m["_t_recv"]) < onset]
    _, clean_real_s = run_set(clean_real, 3.0, tag="clean-real ")

    print("\nCLEAN CONTROL B: synthetic all-valid schedule, full duration")
    carrier, gps = H.carrier_and_gps(msgs)
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)
    clean_synth = H.synth_stream(carrier, template, lambda k, t: False, hz=5.0)
    _, clean_synth_s = run_set(clean_synth, 12.0, tag="clean-synth ")

    for tag, sm in (("CLEAN_REAL_PRE_ONSET", clean_real_s),
                    ("CLEAN_SYNTH_ALL_VALID", clean_synth_s)):
        for arm in A.ARMS:
            s = dict(sm[arm])
            s["objective_O"] = objective_O(s)
            s["objective_D"] = objective_D(s)
            s["condition"] = tag
            rows.append(s)

    with open(os.path.join(OUT, "THREE_ARM_REPLAY_RESULTS.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ---- operational correctness (H1) -----------------------------------
    op = {
        "artifact": "OPERATIONAL_CORRECTNESS_RESULTS",
        "hypothesis": "H1: S1 and S2 represent explicit raw invalidity more "
                      "faithfully at the operational-admissibility boundary "
                      "than S0",
        "endpoint": "overlap between raw OBSERVED_INVALID and A_gps == 1; "
                    "lower overlap is better",
        "fixture": meta["tag"], "n_realisations": 1,
        "per_arm": {arm: {
            "ticks_obs_invalid": summaries[arm]["n_ticks_obs_invalid"],
            "admissible_while_invalid":
                summaries[arm]["O_admissible_while_invalid"],
            "admissible_while_invalid_frac":
                summaries[arm]["O_admissible_while_invalid_frac"],
            "objective_O": objective_O(summaries[arm]),
            "failsafe_nav_degraded_ticks":
                summaries[arm]["O_nav_degraded_ticks"],
            "failsafe_nav_degraded_while_valid":
                summaries[arm]["O_nav_degraded_while_valid"],
            "max_failsafe_level": summaries[arm]["O_max_failsafe_level"],
        } for arm in A.ARMS},
    }
    op["H1_supported"] = bool(
        objective_O(summaries["S1"]) > objective_O(summaries["S0"])
        and objective_O(summaries["S2c"]) > objective_O(summaries["S0"]))
    with open(os.path.join(OUT, "OPERATIONAL_CORRECTNESS_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(op, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # ---- diagnostic preservation (H2) + ablations (item 18) -------------
    dg = {
        "artifact": "DIAGNOSTIC_PRESERVATION_RESULTS",
        "hypothesis": "H2: S2 preserves more fault-relevant diagnostic "
                      "evidence than S1 during explicit invalidity",
        "fixture": meta["tag"], "n_realisations": 1,
        "per_arm": {arm: {
            k: summaries[arm][k] for k in summaries[arm]
            if k.startswith("D_") or k in ("min_trust_gps", "final_trust_gps")
        } for arm in A.ARMS},
        "ablations": {
            "S2a_status_only": summaries["S2a"]["D_top_share"],
            "S2b_hacc_only": summaries["S2b"]["D_top_share"],
            "S2c_both": summaries["S2c"]["D_top_share"],
            "S1D_same_terms_but_D_coupled_to_A":
                summaries["S1D"]["D_top_share"],
            "S1_no_terms": summaries["S1"]["D_top_share"],
        },
        "detector_dominance_test": {
            "question": "does the improvement come from ADDING the evidence "
                        "terms, or from DECOUPLING D from A?",
            "S1D_minus_S1": round(summaries["S1D"]["D_top_share"]
                                  - summaries["S1"]["D_top_share"], 6),
            "S2c_minus_S1D": round(summaries["S2c"]["D_top_share"]
                                   - summaries["S1D"]["D_top_share"], 6),
            "reading": "S1D carries exactly the same two evidence terms as "
                       "S2c and differs only in gating them by A. A large "
                       "S1D-S1 gap would mean the terms leak past the coupled "
                       "gate; a large S2c-S1D gap means the decoupling is "
                       "what does the work.",
        },
    }
    dg["H2_supported"] = bool(
        summaries["S2c"]["D_top_share"] > summaries["S1"]["D_top_share"])
    with open(os.path.join(OUT, "DIAGNOSTIC_PRESERVATION_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(dg, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # ---- Pareto (H3) -----------------------------------------------------
    pts = {arm: (objective_O(summaries[arm]), objective_D(summaries[arm]))
           for arm in A.ARMS}
    clean_equiv = {
        tag: {
            "arms_equal_on_O": len({sm[a]["O_admissible_while_invalid_frac"]
                                    for a in A.ARMS}) <= 1,
            "arms_equal_on_D": len({sm[a]["D_top_share"]
                                    for a in A.ARMS}) == 1,
            "D_top_share": {a: sm[a]["D_top_share"] for a in A.ARMS},
            "final_post_gps_fault": {a: sm[a]["D_final_post_gps_fault"]
                                     for a in A.ARMS},
            "n_ticks_obs_invalid": {a: sm[a]["n_ticks_obs_invalid"]
                                    for a in A.ARMS},
        }
        for tag, sm in (("CLEAN_REAL_PRE_ONSET", clean_real_s),
                        ("CLEAN_SYNTH_ALL_VALID", clean_synth_s))
    }
    par = {
        "artifact": "PARETO_RESULTS",
        "axes": {
            "X_objective_O": "1 - (ticks obs-invalid with A_gps==1) / "
                             "(ticks obs-invalid); higher better",
            "Y_objective_D": "share of post-onset ticks with gps_fault "
                             "leading; higher better",
        },
        "defined_before_running_S2": True,
        "points": {arm: {"O": pts[arm][0], "D": pts[arm][1]}
                   for arm in A.ARMS},
        "classification": classify_pareto(pts, "S2c"),
        "classification_S2a": classify_pareto(pts, "S2a"),
        "classification_S2b": classify_pareto(pts, "S2b"),
        "classification_S1D": classify_pareto(pts, "S1D"),
        "clean_control_equivalence": clean_equiv,
        "H3_pattern_expected": {"S0": "O low, D high", "S1": "O high, D low",
                                "S2": "O high, D high"},
    }
    with open(os.path.join(OUT, "PARETO_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(par, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("\nPARETO")
    for arm in A.ARMS:
        print(f"  {arm:<4} O={pts[arm][0]}  D={pts[arm][1]}")
    print(f"  S2c verdict: {par['classification']['verdict']}  "
          f"{par['classification']['pairwise']}")
    print(f"  detector-dominance: S1D-S1="
          f"{dg['detector_dominance_test']['S1D_minus_S1']}  "
          f"S2c-S1D={dg['detector_dominance_test']['S2c_minus_S1D']}")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
