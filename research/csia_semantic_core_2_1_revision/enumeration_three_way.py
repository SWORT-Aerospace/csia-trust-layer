#!/usr/bin/env python3
"""Phase 2: the small-state enumeration, frozen v2.0 vs 2.1.0 vs 2.1.1.
RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/enumeration_three_way.py

The 2.1 package's own harness (`semantic_core_2_1_differential.py`) runs the
audit's probe with 2.1 in the successor slot: section D (enumeration,
metamorphic perturbations, property measures) and R21 (the Phase A targets).
It is imported and run twice, unmodified:

    PRE      as committed: `Corrections.only(...)` / `Corrections()` = 2.1.0
    REVISED  the module's `Corrections` name is bound, for this process
             only, to a factory that adds the three revision switches, so
             every core the harness builds is 2.1.1. No pacing map is given
             (the enumeration is about semantics, not the aircraft profile),
             so R-2's starvation predicate answers None everywhere.

The frozen column is the same in both runs (it is frozen v2). Per measure
the output names what is NEW (a violation 2.1.1 has that 2.1.0 had not),
REMOVED, UNCHANGED or DEFERRED.

Writes ENUMERATION_THREE_WAY.json.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace

import revision_common as RC

import semantic_core_2_1_differential as D  # noqa: E402

from csia_semantic_core import Corrections  # noqa: E402

OUT = RC.HERE / "ENUMERATION_THREE_WAY.json"
REVISIONS = dict(fault_policy_b=True, pacing_inputs=True, config_epoch=True)


class RevisedCorrections:
    """Stands in for `Corrections` inside the differential module: the same
    constructors, with the three revisions switched on."""

    def __new__(cls, *a, **kw):
        return replace(Corrections(*a, **kw), **REVISIONS)

    @staticmethod
    def only(*ids):
        return replace(Corrections.only(*ids), **REVISIONS)

    @staticmethod
    def none():
        return Corrections.none()


def r9b(corrections):
    """The Phase A target R9B, built as `section_R21` builds it, but with the
    core's corrections passed explicitly (`section_R21` builds this one core
    with the package default, so binding the module name cannot reach it)."""
    P = D.P
    spec = P.SymptomSpec("S", "synthetic", detect=lambda ix: ("x",), hypotheses=(
        P.Hypothesis("D1/h1", "D1", "m", confirmed_by=("P",), refuted_by=("Q",)),
        P.Hypothesis("D2/h2", "D2", "m", confirmed_by=("P",), refuted_by=("R",))))

    def boom(i, s):
        raise KeyError("defect")
    tbl = {"P": P.Predicate("P", "", "D", lambda i, s: True),
           "Q": P.Predicate("Q", "", "D", boom),
           "R": P.Predicate("R", "", "D", lambda i, s: True)}
    from csia_semantic_core import SemanticCore21
    x = SemanticCore21((spec,), tbl, (), corrections).reason([]).localizations[0]
    return {"verdict_2_0_view": x.v2.verdict, "outcome": x.outcome,
            "evaluation": x.evaluation, "fault_impact": list(x.fault_impact),
            "supported_left_standing": x.outcome == "SUPPORTED"}


def run(label):
    committed = json.loads(D.P.OUT.read_text())
    audit, comparison, _runs = D.section_audit(committed)
    d = D.norm(D.section_D(audit))
    r21 = D.norm(D.section_R21())
    sh = D.diff_paths(committed["SH"], audit["SH"], limit=10000)
    return {"label": label, "D": d, "R21": r21,
            "SH_differing_paths_all": sh,
            "SH_scenarios_named": sorted({x.split("/")[3] for x in sh
                                          if x.count("/") >= 3 and x.split("/")[2] == "changes"}),
            "audit_sections_identical_to_audit": {
                k: v["identical_to_audit"] for k, v in comparison.items()},
            "audit_differing_paths": {k: v["differing_paths"][:12]
                                      for k, v in comparison.items()
                                      if v["differing_paths"]}}


def main():
    pre = run("PRE 2.1.0")
    original = D.Corrections
    D.Corrections = RevisedCorrections
    try:
        rev = run("REVISED 2.1.1 (no pacing map)")
    finally:
        D.Corrections = original
    accepted = json.loads((RC.PREV / "SEMANTIC_CORE_2_1_RESULTS.json").read_text())["D"]
    rows = []
    pm = {r["id"]: r for r in pre["D"]["measures"]}
    for r in rev["D"]["measures"]:
        p = pm[r["id"]]
        f, s0, s1 = r["frozen_v2"], p["semantic_core_2_1"], r["semantic_core_2_1"]
        if s1 == s0:
            change = "UNCHANGED"
        elif s1 > s0:
            change = "NEW_VIOLATIONS"
        else:
            change = "REMOVED_VIOLATIONS"
        rows.append({"id": r["id"], "measure": r["measure"], "frozen_v2": f,
                     "semantic_core_2_1_0": s0, "semantic_core_2_1_1": s1,
                     "classification_2_1_0": p["classification"],
                     "classification_2_1_1": r["classification"],
                     "change_2_1_0_to_2_1_1": change})
    r9b_pre = r9b(Corrections())
    r9b_rev = r9b(Corrections.revised())
    deferred = []
    for item in rev["D"]["not_measured_here"]:
        row = dict(item)
        if item["id"] == "R9B":
            row["status_2_1_1"] = ("FIXED: the raising refuter no longer leaves a SUPPORTED "
                                   "standing" if not r9b_rev["supported_left_standing"]
                                   else "STILL_PRESENT")
        else:
            row["status_2_1_1"] = "STILL_DEFERRED (outside R-1/R-2/R-3)"
        deferred.append(row)
    counts: dict = {}
    for r in rows:
        counts[r["change_2_1_0_to_2_1_1"]] = counts.get(r["change_2_1_0_to_2_1_1"], 0) + 1
    out = {"harness": "semantic_core_2_1_revision_enumeration_three_way",
           "pre_identical_to_accepted_section_D": not D.diff_paths(accepted, pre["D"]),
           "revised_identical_to_accepted_section_D": not D.diff_paths(accepted, rev["D"]),
           "revised_differing_paths_vs_accepted": D.diff_paths(accepted, rev["D"]),
           "measures": rows, "change_counts": counts,
           "classification_counts": {"2_1_0": pre["D"]["classification_counts"],
                                     "2_1_1": rev["D"]["classification_counts"]},
           "deferred": deferred,
           "R21": {"2_1_0": pre["R21"], "2_1_1": rev["R21"]},
           "R9B": {"2_1_0": r9b_pre, "2_1_1": r9b_rev},
           "SH_differing_paths": {"2_1_0": pre["SH_differing_paths_all"],
                                  "2_1_1": rev["SH_differing_paths_all"]},
           "SH_scenarios_named": {"2_1_0": pre["SH_scenarios_named"],
                                  "2_1_1": rev["SH_scenarios_named"]},
           "audit_sections_identical_to_audit": {
               "2_1_0": pre["audit_sections_identical_to_audit"],
               "2_1_1": rev["audit_sections_identical_to_audit"]},
           "audit_differing_paths": {"2_1_0": pre["audit_differing_paths"],
                                     "2_1_1": rev["audit_differing_paths"]}}
    RC.write_json(OUT, out)
    print(json.dumps({k: out[k] for k in ("pre_identical_to_accepted_section_D",
                                          "revised_identical_to_accepted_section_D",
                                          "revised_differing_paths_vs_accepted",
                                          "change_counts", "classification_counts",
                                          "R9B", "audit_sections_identical_to_audit",
                                          "SH_scenarios_named")},
                     indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
