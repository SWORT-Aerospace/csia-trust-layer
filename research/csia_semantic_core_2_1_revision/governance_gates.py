#!/usr/bin/env python3
"""Phases 9 and 10: the XSYS-001 and Phase C hard gates under 2.1.1.
RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/governance_gates.py

PHASE 9, XSYS-001. The 2.1 package's replay of the 3,872 sealed slots
(`semantic_core_2_1_differential.section_F`), imported and run unmodified,
once as committed (2.1.0) and once with the module's `Corrections` bound to
the revised factory (2.1.1). The gate: 3,872 slots; 0 decision and 0
scored-outcome differences against the sealed run; primary 55/55, lower
bound 0.7616, H_PRIMARY SUPPORTED. Anything else is
SEMANTIC_2_1_XSYS_GOVERNANCE_BLOCK.

PHASE 10, PHASE C. The frozen `decision_gate` (engineering/v2/run_phase_c.py)
over each matched-set member's final tick, reasoned by 2.1.0 and 2.1.1, with
and without the successor profile (r1 for 2.1.0, r2 for 2.1.1). The gate: the
committed headline (CROSS_DOMAIN_ASSURANCE_FUNCTIONAL) and the six answers of
engineering/v2/V2_PHASEC_GATE.json, unchanged. Anything else is
SEMANTIC_2_1_PHASE_C_GOVERNANCE_BLOCK.

Writes GOVERNANCE_GATES.json.
"""
from __future__ import annotations

import json
import sys

import revision_common as RC

import semantic_core_2_1_differential as D  # noqa: E402
import shadow_validation as S  # noqa: E402
from enumeration_three_way import RevisedCorrections  # noqa: E402

from csia.v2 import signatures as SIG  # noqa: E402
from csia.v2.localization import EvidenceIndex  # noqa: E402
from csia.v2.profiles.matched_scenarios import (MATCHED_SETS,  # noqa: E402
                                                SET_SYMPTOM)
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

OUT = RC.HERE / "GOVERNANCE_GATES.json"
KEYS = ("slots", "decision_differences_2_1_vs_sealed",
        "outcome_differences_2_1_vs_recorded_results",
        "full_v2_0_view_differences_2_1_vs_sealed", "XSYS_HARD_GATE",
        "primary_recomputed_under_2_1")


def xsys(revised):
    original = D.Corrections
    if revised:
        D.Corrections = RevisedCorrections
    try:
        F = D.section_F()
    finally:
        D.Corrections = original
    return {k: F[k] for k in KEYS}


def xsys_ok(f):
    p = f["primary_recomputed_under_2_1"]
    return (f["slots"] == 3872 and f["decision_differences_2_1_vs_sealed"] == 0
            and f["outcome_differences_2_1_vs_recorded_results"] == 0
            and f["XSYS_HARD_GATE"] == "PASS" and p["n_success"] == 55
            and p["n_pairs"] == 55 and round(p["lower95"], 4) == 0.7616
            and p["H_PRIMARY"] == "SUPPORTED")


def phase_c(runs, corrections, ov):
    RP = S._phase_c_runner()
    rows = []
    for set_name, members in MATCHED_SETS.items():
        want = SET_SYMPTOM[set_name]
        for name in members:
            engine, res = runs[name]
            final = res[-1]
            recs = ov.apply(final.records) if ov else final.records
            blind = "|".join(SIG.uncovered_common_cause_domains(EvidenceIndex(final.records)))
            core = SemanticCore21.from_engine(engine, corrections, trace=False,
                                              pacing=ov.pacing_map() if ov else None)
            locs = [x.v2 for x in core.reason(recs).localizations if x.symptom == want]
            if not locs:
                rows.append(D._missing(set_name, name, want, ""))
            for loc in locs:
                rows.append(D._row(set_name, name, want, loc, blind, ""))
    g = RP.decision_gate(rows)
    return {"verdict": g["verdict"],
            "qualifying": {q["set"]: q["answers"] for q in g["qualifying_sets"]},
            "non_qualifying": {q["set"]: q.get("why") for q in g["non_qualifying_sets"]}}


def main():
    out = {"harness": "semantic_core_2_1_revision_governance_gates"}
    out["phase9_xsys"] = {"2_1_0": xsys(False), "2_1_1": xsys(True)}
    out["phase9_xsys_gate_pass"] = {k: xsys_ok(v) for k, v in out["phase9_xsys"].items()}
    committed = json.loads((RC.REPO / "engineering/v2/V2_PHASEC_GATE.json").read_text())
    want = {"verdict": committed["verdict"],
            "qualifying": {q["set"]: q["answers"] for q in committed["qualifying_sets"]}}
    runs = {}
    import semantic_probe as P
    from csia.v2.profiles import SCENARIOS
    for members in MATCHED_SETS.values():
        for name in members:
            runs[name] = P.run_scenario(SCENARIOS[name])
    r1 = load_successor("aircraft_successor_r1")
    r2 = load_successor("aircraft_successor_r2")
    rev = Corrections.revised()
    gates = {"2_1_0_base": phase_c(runs, Corrections(), None),
             "2_1_0_successor_r1": phase_c(runs, Corrections(), r1),
             "2_1_1_base": phase_c(runs, rev, None),
             "2_1_1_successor_r2": phase_c(runs, rev, r2)}
    out["phase10_committed_headline"] = want
    out["phase10_phase_c"] = gates
    out["phase10_unchanged"] = {
        k: (g["verdict"] == want["verdict"] and g["qualifying"] == want["qualifying"])
        for k, g in gates.items()}
    out["tokens_if_failed"] = {
        "phase9": None if all(out["phase9_xsys_gate_pass"].values())
        else "SEMANTIC_2_1_XSYS_GOVERNANCE_BLOCK",
        "phase10": None if all(out["phase10_unchanged"].values())
        else "SEMANTIC_2_1_PHASE_C_GOVERNANCE_BLOCK"}
    RC.write_json(OUT, out)
    print(json.dumps({k: out[k] for k in ("phase9_xsys", "phase9_xsys_gate_pass",
                                          "phase10_unchanged", "tokens_if_failed")},
                     indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
