"""The four authority-precedence baselines. Items 33-39.

    B0  SPEC_FIRST            always trust the protocol/schema declaration
    B1  IMPLEMENTATION_FIRST   always trust the executable producer
    B2  OBSERVATION_FIRST      treat runtime behaviour as effective truth
    B3  SET_VALUED             keep every source-supported interpretation

The question item 38 asks is not which is nicest. It is whether B3 exposes
uncertainty the others conceal, or whether it just makes everything
ambiguous. Both answers are reportable and one of them kills the direction.

A baseline can also FAIL TO APPLY, and that turns out to matter more than any
of them succeeding: a precedence rule cannot resolve a case where the
authority it privileges says nothing. `SILENT` is not a tie to be broken, it
is a gap in the standard.

  python research/semantic_authority_conflict/baselines.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import authorities as A                                        # noqa: E402

SILENT = A.SILENT
LEVELS = ("VALUE", "STATE", "EVIDENCE", "DIAGNOSIS", "ASSURANCE", "ACTION")


def _in_scope(v):
    """An authority tagged with a different raw state is context, not a
    competing interpretation of THIS one. Pooling them made
    IMPLEMENTATION_FIRST read as self-inconsistent on GNSS when it is not."""
    return not str(v.get("scope", "")).startswith("different_raw_state")


def spec_authorities(case):
    return {k: v for k, v in case["authorities"].items()
            if k.startswith("C_spec") and _in_scope(v)}


def producer_authorities(case):
    return {k: v for k, v in case["authorities"].items()
            if k.startswith("C_producer") and _in_scope(v)}


def consumer_authorities(case):
    return {k: v for k, v in case["authorities"].items()
            if k.startswith("C_consumer") and _in_scope(v)}


def resolves(auths):
    """A precedence rule resolves a case iff the privileged authority speaks
    AND speaks with one voice."""
    spoken = {v["interpretation"] for v in auths.values()
              if v["interpretation"] != SILENT}
    if not spoken:
        return "SILENT", None
    if len(spoken) > 1:
        return "SELF_INCONSISTENT", sorted(spoken)
    return "RESOLVES", sorted(spoken)[0]


def main() -> int:
    sens = {}
    p = os.path.join(_HERE, "DECISION_SENSITIVITY.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            sens.setdefault(r["case"], {})[r["level"]] = r

    rows = []
    for case in A.CASES:
        name = case["case"]
        cons = consumer_authorities(case)
        cons_set = {v["interpretation"] for v in cons.values()}

        s_status, s_val = resolves(spec_authorities(case))
        p_status, p_val = resolves(producer_authorities(case))

        # does the privileged authority actually settle what the consumers
        # should do -- i.e. would following it collapse the consumer set?
        b0 = ("RESOLVES" if s_status == "RESOLVES" else s_status)
        b1 = ("RESOLVES" if p_status == "RESOLVES" else p_status)
        # OBSERVATION_FIRST privileges runtime behaviour, and there are three
        # runtimes. It cannot be unique unless the consumers already agree.
        b2 = "RESOLVES" if len(cons_set) == 1 else "SELF_INCONSISTENT"

        amb = {L: (sens.get(name, {}).get(L, {}).get("verdict", "")
                   == "SEMANTICALLY_AMBIGUOUS") for L in LEVELS}
        attributable_levels = [L for L in LEVELS if amb[L]]

        rows.append({
            "case": name,
            "raw_state": case["raw_state"],
            "n_consumer_interpretations": len(cons_set),
            "consumer_interpretations": " | ".join(sorted(cons_set)),
            "B0_SPEC_FIRST": b0,
            "B0_value": (s_val if isinstance(s_val, str) else
                         (" | ".join(s_val) if s_val else "")),
            "B1_IMPLEMENTATION_FIRST": b1,
            "B1_value": (p_val if isinstance(p_val, str) else
                         (" | ".join(p_val) if p_val else "")),
            "B2_OBSERVATION_FIRST": b2,
            "B3_SET_VALUED_ambiguous_levels": " | ".join(attributable_levels),
            "B3_ambiguity_reaches_ACTION": amb["ACTION"],
            "spec_and_producer_agree": (s_status == "RESOLVES"
                                        and p_status == "RESOLVES"
                                        and s_val == p_val),
        })

    # ---- item 38's summary question ------------------------------------
    n = len(rows)
    lvl_cells = [(r["case"], L) for r in rows for L in LEVELS]
    ambiguous_cells = sum(
        1 for r in rows for L in LEVELS
        if sens.get(r["case"], {}).get(L, {}).get("verdict", "")
        == "SEMANTICALLY_AMBIGUOUS")
    robust_cells = sum(
        1 for r in rows for L in LEVELS
        if sens.get(r["case"], {}).get(L, {}).get("verdict", "") == "ROBUST")
    confounded_cells = sum(
        1 for r in rows for L in LEVELS
        if sens.get(r["case"], {}).get(L, {}).get("verdict", "")
        == "CONFOUNDED_BY_CONTROL")

    summary = {
        "artifact": "BASELINE_COMPARISON_SUMMARY",
        "cases": n,
        "level_cells": len(lvl_cells),
        "ambiguity_rate": round(ambiguous_cells / len(lvl_cells), 3),
        "robust_decision_rate": round(robust_cells / len(lvl_cells), 3),
        "confounded_rate": round(confounded_cells / len(lvl_cells), 3),
        "cases_where_B0_resolves": sum(
            1 for r in rows if r["B0_SPEC_FIRST"] == "RESOLVES"),
        "cases_where_B1_resolves": sum(
            1 for r in rows if r["B1_IMPLEMENTATION_FIRST"] == "RESOLVES"),
        "cases_where_B2_resolves": sum(
            1 for r in rows if r["B2_OBSERVATION_FIRST"] == "RESOLVES"),
        "cases_where_spec_and_producer_agree": sum(
            1 for r in rows if r["spec_and_producer_agree"]),
        "cases_where_B3_ambiguity_reaches_ACTION": sum(
            1 for r in rows if r["B3_ambiguity_reaches_ACTION"]),
        "item_38_answer": None,
    }
    summary["item_38_answer"] = (
        "B3 flags ambiguity at upstream levels that B0/B1/B2 would each "
        "silently resolve, but in "
        f"{summary['cases_where_B3_ambiguity_reaches_ACTION']} of {n} cases "
        "does that ambiguity reach the ACTION level. Where it does not, the "
        "extra information B3 carries changes nothing the vehicle would do.")

    with open(os.path.join(_HERE, "BASELINE_COMPARISON.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(_HERE, "results", "BASELINE_SUMMARY.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    for r in rows:
        print(f"\n  {r['case']}")
        print(f"    consumers disagree {r['n_consumer_interpretations']} ways:"
              f" {r['consumer_interpretations']}")
        print(f"    B0 SPEC_FIRST           {r['B0_SPEC_FIRST']:<18} "
              f"{r['B0_value']}")
        print(f"    B1 IMPLEMENTATION_FIRST {r['B1_IMPLEMENTATION_FIRST']:<18} "
              f"{r['B1_value']}")
        print(f"    B2 OBSERVATION_FIRST    {r['B2_OBSERVATION_FIRST']}")
        print(f"    spec and producer agree: {r['spec_and_producer_agree']}")
        print(f"    B3 ambiguous levels: "
              f"{r['B3_SET_VALUED_ambiguous_levels'] or '(none)'}")
    print(f"\n  ambiguity rate {summary['ambiguity_rate']}  "
          f"robust rate {summary['robust_decision_rate']}  "
          f"confounded {summary['confounded_rate']}")
    print(f"  B0 resolves {summary['cases_where_B0_resolves']}/{n}   "
          f"B1 resolves {summary['cases_where_B1_resolves']}/{n}   "
          f"B2 resolves {summary['cases_where_B2_resolves']}/{n}")
    print(f"  B3 ambiguity reaching ACTION: "
          f"{summary['cases_where_B3_ambiguity_reaches_ACTION']}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
