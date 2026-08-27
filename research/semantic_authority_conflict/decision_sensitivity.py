"""Does the assurance decision depend on which authority is chosen?

Items 11-13, 22-24, 32, 40, 45-46. The whole package turns on this file.

F(C_a, w) is computed by driving the REAL committed ingest path for authority
C_a through the REAL frozen core and the REAL failsafe policy, using the
stage-indexed probe from research/evidence_semantics. Six levels, kept
separate because item 13 is explicit that disagreement at VALUE may still
yield identical ACTION:

    VALUE      the numeric payload crossing into the core
    STATE      the quality token crossing, plus the core's slot history
    EVIDENCE   whether and when operational admissibility closes
    DIAGNOSIS  the sensor's trust trajectory
    ASSURANCE  failsafe level history and first escalation time
    ACTION     the set of failsafe actions actually issued

NULL CONTROL. Every comparison is repeated on V^k, an all-nominal word of the
same length. The three paths differ in sample rate, timestamp convention and
computed values even with no fault present; a level that already disagrees on
the control cannot be attributed to semantic authority and is reported
CONFOUNDED. This discipline is inherited from the previous package, where it
was what stopped a stamping convention being read as a semantic difference.

  python research/semantic_authority_conflict/decision_sensitivity.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
ES = os.path.join(ROOT, "research", "evidence_semantics")
sys.path.insert(0, ROOT)
sys.path.insert(0, ES)

import contract_checker as C                                   # noqa: E402
import probe as P                                              # noqa: E402

LEVELS = ("VALUE", "STATE", "EVIDENCE", "DIAGNOSIS", "ASSURANCE", "ACTION")

# case -> (family, word realising the raw state, the consumer authorities)
CASES = {
    "battery.current_not_measured": ("battery", "X",
                                     ["C_consumer_A", "C_consumer_B",
                                      "C_consumer_C"]),
    "gnss.no_3d_fix": ("gnss", "I",
                       ["C_consumer_A", "C_consumer_B", "C_consumer_C"]),
    "mag.all_zero_triple": ("mag", "Z",
                            ["C_consumer_A", "C_consumer_B", "C_consumer_C"]),
}

# consumer authority -> the committed ingest path that realises it
PATH_OF = {"C_consumer_A": "v1_1_adapter",
           "C_consumer_B": "plugins_py",
           "C_consumer_C": "ulog_source_py"}


def proj_action(rows):
    return tuple(sorted({a for r in rows for a in r["T9_actions"]}))


def F(level, rows):
    if level == "ACTION":
        return proj_action(rows)
    if level == "ASSURANCE":
        lv, esc, _acts = C.proj_assurance(rows)
        return (lv, esc)
    return C.PROJ[level](rows)


def _stage_first_diff(rows_a, rows_b):
    """Conflict propagation depth (item 46), over the probe's nine stages."""
    first, last = None, None
    for st in P.STAGES:
        ta, tb = C._stage_trace(rows_a, st), C._stage_trace(rows_b, st)
        if ta != tb:
            if first is None:
                first = st
            last = st
    return first, last


def main() -> int:
    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)
    sens_rows, prop_rows, xpath_rows = [], [], []
    setval = {}

    for case, (family, word, auths) in CASES.items():
        runs = {a: C.run(PATH_OF[a], word, family) for a in auths}
        ctrl = {a: C.run(PATH_OF[a], "V" * len(word), family) for a in auths}

        y_star, confounded = {}, {}
        for lvl in LEVELS:
            vals = {a: F(lvl, runs[a]) for a in auths}
            cvals = {a: F(lvl, ctrl[a]) for a in auths}
            control_agrees = len({repr(v) for v in cvals.values()}) == 1
            distinct = {repr(v) for v in vals.values()}
            y_star[lvl] = {
                "n_distinct": len(distinct),
                "robust": len(distinct) == 1,
                "control_agrees": control_agrees,
                "attributable": control_agrees and len(distinct) > 1,
                "values": {a: str(vals[a])[:200] for a in auths},
            }
            confounded[lvl] = not control_agrees
            sens_rows.append({
                "case": case, "raw_state_word": word, "level": lvl,
                "n_distinct_outcomes": len(distinct),
                "semantically_robust": len(distinct) == 1,
                "control_agrees": control_agrees,
                "decision_sensitive_attributable": (control_agrees
                                                    and len(distinct) > 1),
                "verdict": ("ROBUST" if len(distinct) == 1 else
                            ("CONFOUNDED_BY_CONTROL" if not control_agrees
                             else "SEMANTICALLY_AMBIGUOUS")),
            })

        # ---- minimal authority subset (item 32) -------------------------
        minimal = {}
        for lvl in LEVELS:
            if not y_star[lvl]["attributable"]:
                minimal[lvl] = None
                continue
            found = None
            for i, a in enumerate(auths):
                for b in auths[i + 1:]:
                    if F(lvl, runs[a]) != F(lvl, runs[b]):
                        found = [a, b]
                        break
                if found:
                    break
            minimal[lvl] = found
        setval[case] = {"family": family, "word": word,
                        "authorities": auths,
                        "Y_star": y_star,
                        "minimal_authority_subset": minimal}

        # ---- propagation depth + cross-path rows -------------------------
        for i, a in enumerate(auths):
            for b in auths[i + 1:]:
                first, last = _stage_first_diff(runs[a], runs[b])
                fc, lc = _stage_first_diff(ctrl[a], ctrl[b])
                lvl_first = next((L for L in LEVELS
                                  if F(L, runs[a]) != F(L, runs[b])), None)
                lvl_last = next((L for L in reversed(LEVELS)
                                 if F(L, runs[a]) != F(L, runs[b])), None)
                prop_rows.append({
                    "case": case, "pair": f"{a}__vs__{b}",
                    "first_stage_of_disagreement": first or "",
                    "last_stage_where_observable": last or "",
                    "first_level_of_disagreement": lvl_first or "",
                    "last_level_where_observable": lvl_last or "",
                    "control_first_stage_of_disagreement": fc or "",
                    "disagreement_reaches_ACTION":
                        F("ACTION", runs[a]) != F("ACTION", runs[b]),
                })
                xpath_rows.append({
                    "case": case, "pair": f"{a}__vs__{b}",
                    **{f"{L}_differs": F(L, runs[a]) != F(L, runs[b])
                       for L in LEVELS},
                    **{f"{L}_control_differs": F(L, ctrl[a]) != F(L, ctrl[b])
                       for L in LEVELS},
                })

    _csv("DECISION_SENSITIVITY.csv", sens_rows)
    _csv("CONFLICT_PROPAGATION.csv", prop_rows)
    _csv("CROSS_PATH_RESULTS.csv", xpath_rows)
    with open(os.path.join(_HERE, "SET_VALUED_ASSURANCE_RESULTS.json"),
              "w", encoding="utf-8") as fh:
        json.dump({"artifact": "SET_VALUED_ASSURANCE_RESULTS",
                   "levels": list(LEVELS),
                   "note": "Y* is a SET, not a distribution. No authority "
                           "carries a weight anywhere in this package "
                           "(item 10).",
                   "cases": setval}, fh, indent=2, sort_keys=True,
                  default=str)
        fh.write("\n")

    print("  decision sensitivity, by case and level:")
    for case in CASES:
        print(f"\n  {case}")
        for lvl in LEVELS:
            r = next(x for x in sens_rows
                     if x["case"] == case and x["level"] == lvl)
            print(f"    {lvl:<10} distinct={r['n_distinct_outcomes']}  "
                  f"{r['verdict']}")
    n_act = sum(1 for r in prop_rows if r["disagreement_reaches_ACTION"])
    print(f"\n  pairs whose disagreement reaches ACTION: {n_act} of "
          f"{len(prop_rows)}")
    return 0


def _csv(name, rows):
    if not rows:
        return
    with open(os.path.join(_HERE, name), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
