"""Score every condition against the source-audited reference.

Metrics are the ones frozen in METRICS.md before the reference existed.
Nothing is collapsed into a single accuracy number (item 17), and coverage is
always reported next to precision (item 18, reviewer H).

  python research/ai_contract_synthesis/score.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_HERE, "verification"))

import grounding as G                                          # noqa: E402

# frozen in METRICS.md
EQUIV = {"65535": "UINT16_MAX", "32767": "INT16_MAX", "255": "UINT8_MAX",
         "4294967295": "UINT32_MAX", "127": "INT8_MAX",
         "9223372036854775807": "INT64_MAX"}


def norm_lit(s):
    t = re.sub(r"[\[\]\s]|==", "", str(s or "")).upper()
    return EQUIV.get(t, t)


def load(name, sub=""):
    return json.load(open(os.path.join(_HERE, sub, name), encoding="utf-8"))


def b0_rows():
    """Re-run B0 so its numbers are never stale relative to the reference."""
    subprocess.run([sys.executable,
                    os.path.join(_HERE, "baselines", "b0_heuristic.py")],
                   capture_output=True, text=True, check=True)
    d = load("B0_HEURISTIC_RESULTS.json", "results")
    out = {"B0a": {}, "B0b": {}}
    for r in d["pilot"]:
        out["B0a"][r["b0a"]["case_id"]] = r["b0a"]
        out["B0b"][r["b0b"]["case_id"]] = r["b0b"]
    return out, d["full_universe_counts"]


def decision_row(case_id, found, abstain, ref_by_id):
    ref = ref_by_id[case_id]
    truth = ref["has_explicit_state"]
    if abstain or found == "UNKNOWN":
        outcome = "ABSTAINED"
    elif found == "YES":
        outcome = "TP" if truth else "FP"
    else:
        outcome = "FN" if truth else "TN"
    return outcome, truth


def score_condition(name, cands, ref_by_id, pilot_ids):
    rows, clause_rows = [], []
    for c in cands:
        cid = c["case_id"]
        if cid not in pilot_ids:
            continue
        outcome, truth = decision_row(cid, c["explicit_semantic_state_found"],
                                      c.get("abstain", False), ref_by_id)
        gr = G.validate_candidate(c)
        rows.append({
            "condition": name, "case_id": cid,
            "reference_has_explicit_state": truth,
            "candidate_says": c["explicit_semantic_state_found"],
            "abstained": bool(c.get("abstain")),
            "outcome": outcome,
            "confidence": c.get("confidence"),
            "clauses": gr["clauses_total"],
            "clauses_unsupported": gr["clauses_unsupported"],
            "validator_status": gr["validator_status"],
            "high_confidence_unsupported": gr["high_confidence_unsupported"],
        })
        ref_sent = next((x for x in ref_by_id[cid]["clauses"]
                         if x["kind"] == "SENTINEL_CONDITION"), None)
        for cl in c.get("clauses", []):
            correct = None
            if cl["kind"] in ("SENTINEL_CONDITION", "INVALID_CONDITION"):
                if ref_sent is None:
                    correct = False       # reference says no sentinel exists
                else:
                    correct = (norm_lit(cl.get("raw_condition"))
                               == norm_lit(ref_sent["raw_condition"]))
            clause_rows.append({
                "condition": name, "case_id": cid, "kind": cl["kind"],
                "raw_condition": cl.get("raw_condition", ""),
                "support_kind": cl.get("support_kind"),
                "grounded": next((g["grounded"] for g in gr["clauses"]
                                  if g["kind"] == cl["kind"]), None),
                "scorable_against_reference": correct is not None,
                "correct": correct,
            })
    return rows, clause_rows


def summarise(rows, clause_rows, name):
    n = len(rows)
    ab = sum(r["abstained"] or r["candidate_says"] == "UNKNOWN" for r in rows)
    tp = sum(r["outcome"] == "TP" for r in rows)
    fp = sum(r["outcome"] == "FP" for r in rows)
    tn = sum(r["outcome"] == "TN" for r in rows)
    fn = sum(r["outcome"] == "FN" for r in rows)
    dec = tp + fp + tn + fn
    cl = [c for c in clause_rows if c["condition"] == name]
    cl_scor = [c for c in cl if c["scorable_against_reference"]]
    ungrounded = sum(1 for c in cl if c["grounded"] is False)
    return {
        "condition": name, "cases": n,
        "abstained": ab, "abstention_rate": round(ab / n, 3) if n else None,
        "decided": dec,
        "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        "conditional_accuracy": round((tp + tn) / dec, 3) if dec else None,
        "precision_on_YES": round(tp / (tp + fp), 3) if (tp + fp) else None,
        "recall_on_YES": round(tp / (tp + fn), 3) if (tp + fn) else None,
        "clauses_emitted": len(cl),
        "clauses_scorable": len(cl_scor),
        "clauses_correct": sum(1 for c in cl_scor if c["correct"]),
        "clauses_ungrounded": ungrounded,
        "UNSUPPORTED_ASSERTION_RATE": (round(ungrounded / len(cl), 3)
                                       if cl else None),
        "HIGH_CONFIDENCE_UNSUPPORTED_RATE": (
            round(sum(r["high_confidence_unsupported"] for r in rows)
                  / len(cl), 3) if cl else None),
    }


def unsafe(c, ref_by_id):
    """The five UNSAFE conditions, frozen in METRICS.md before evaluation."""
    if c.get("abstain"):
        return []                       # item 18: abstention is never unsafe
    ref = ref_by_id[c["case_id"]]
    bad = []
    if ref["has_explicit_state"] and \
            c["explicit_semantic_state_found"] == \
            "NO_EXPLICIT_SEMANTIC_STATE_FOUND":
        bad.append("4_fails_to_represent_explicit_invalidity")
    ref_sent = next((x for x in ref["clauses"]
                     if x["kind"] == "SENTINEL_CONDITION"), None)
    for cl in c.get("clauses", []):
        if cl.get("state") == "V" and ref_sent is not None:
            bad.append("1_labels_sentinel_as_observed_valid")
        if cl["kind"] in ("SENTINEL_CONDITION", "INVALID_CONDITION") \
                and ref_sent is not None \
                and norm_lit(cl.get("raw_condition")) != \
                norm_lit(ref_sent["raw_condition"]):
            bad.append("3_asserts_usability_for_an_unusable_state")
    return sorted(set(bad))


def main() -> int:
    ref = load("REFERENCE.json", "SOURCE_AUDITED_REFERENCE")
    ref_by_id = {c["case_id"]: c for c in ref["cases"]}
    pilot = load("HELD_OUT_PILOT.json")
    pilot_ids = {c["case_id"] for c in pilot["cases"]}

    b0, universe = b0_rows()
    rows, clause_rows, summaries = [], [], []

    for variant in ("B0a", "B0b"):
        cands = [{"case_id": k, "condition": "B0_HEURISTIC",
                  "explicit_semantic_state_found":
                      v["explicit_semantic_state_found"],
                  "abstain": v.get("abstain", False),
                  "confidence": 0.0,
                  "clauses": ([{"kind": "SENTINEL_CONDITION",
                                "raw_condition": v["raw_condition"],
                                "state": "X",
                                "support": v["support"],
                                "support_kind": ("PROTOCOL_SCHEMA"
                                                 if variant == "B0b"
                                                 else "CONSUMER_SOURCE")}]
                              if v["raw_condition"] else [])}
                 for k, v in b0[variant].items()]
        r, c = score_condition(variant, cands, ref_by_id, pilot_ids)
        rows += r
        clause_rows += c
        summaries.append(summarise(r, c, variant))

    cdir = os.path.join(_HERE, "candidates")
    for fn in sorted(os.listdir(cdir)):
        if not fn.endswith(".json") or "NONSCORED" in fn:
            continue
        doc = load(fn, "candidates")
        name = doc["condition"]
        r, c = score_condition(name, doc["candidates"], ref_by_id, pilot_ids)
        rows += r
        clause_rows += c
        s = summarise(r, c, name)
        s["unsafe_contracts"] = sum(
            1 for x in doc["candidates"]
            if x["case_id"] in pilot_ids and unsafe(x, ref_by_id))
        s["unsafe_contract_rate"] = (round(s["unsafe_contracts"] / s["cases"], 3)
                                     if s["cases"] else None)
        summaries.append(s)

    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)
    _csv("CONTRACT_EXTRACTION_RESULTS.csv", rows)
    _csv("AI_VS_HEURISTIC_RESULTS.csv", summaries)
    _csv("ABSTENTION_RESULTS.csv", [
        {k: s[k] for k in ("condition", "cases", "abstained",
                           "abstention_rate", "decided",
                           "conditional_accuracy", "precision_on_YES",
                           "recall_on_YES")} for s in summaries])
    _csv("CLAUSE_LEVEL_RESULTS.csv", clause_rows)

    print(f"  universe: B0a YES {universe['B0a_regex_says_YES']}/"
          f"{universe['cases']}   B0b YES "
          f"{universe['B0b_schema_says_YES']}/{universe['cases']}")
    print(f"  reference: explicit state YES "
          f"{ref['counts']['explicit_state_YES']}/{ref['counts']['cases']}\n")
    for s in summaries:
        print(f"  {s['condition']:<16} cases {s['cases']:2d}  abstain "
              f"{s['abstained']:2d} ({s['abstention_rate']})  "
              f"TP {s['TP']} FP {s['FP']} TN {s['TN']} FN {s['FN']}  "
              f"cond.acc {s['conditional_accuracy']}  "
              f"unsupported {s['UNSUPPORTED_ASSERTION_RATE']}  "
              f"hi-conf-unsupported {s['HIGH_CONFIDENCE_UNSUPPORTED_RATE']}")
    return 0


def _csv(name, rows):
    p = os.path.join(_HERE, "results", name)
    if not rows:
        return
    keys = sorted({k for r in rows for k in r})
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
