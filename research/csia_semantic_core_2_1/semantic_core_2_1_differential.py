#!/usr/bin/env python3
"""Semantic Core 2.1 against frozen v2: the differential. RESEARCH ONLY.

Run from the repository root:

    .venv/bin/python research/csia_semantic_core_2_1/semantic_core_2_1_differential.py

It writes, next to this file:

    SEMANTIC_CORE_2_1_RESULTS.json   every number the package documents cite
    PHASE_E_CHANGE_RECEIPTS.jsonl    one receipt per changed shipped tick

Sections, named after the phases of the Semantic Core 2.1 brief:

    PRE / POST  hashes of the frozen code and every historical artifact,
                before and after. The run fails if any of them changed
    AUDIT       the semantic correctness audit's own probe, re-run with its
                shadow successor replaced by csia_semantic_core
    D           small-state enumeration and properties, frozen v2 against
                2.1: FIXED / STILL_PRESENT / NOT_APPLICABLE /
                INTENTIONALLY_DEFERRED
    E           all 44 shipped scenarios x 60 ticks: every changed decision,
                with the rule and the evidence responsible, clustered by root
                cause
    F           XSYS-001: all 3,872 sealed slots through 2.1, and the primary
                matched-pair scoring recomputed. THE HARD GATE
    G           the recorded Phase C artifacts, recomputed under 2.1: the
                scenario results, localization rows, evidence subsets and the
                decision gate, using the frozen gate function

HOW THE AUDIT PROBE IS REUSED. `research/csia_semantic_correctness/
semantic_probe.py` measured a shadow successor through three functions:
`shadow`, `shadow_attribute` and `shadow_predicates`. Here those three names
are rebound IN MEMORY, in this process only, to adapters over
`csia_semantic_core`. Every enumeration, perturbation and replay the audit ran
then runs through the real successor. The probe file is not modified, and
nothing is written into the audit package.

WHAT IT TOUCHES. It imports frozen v2, the audit probe, the XSYS-001 pipeline
modules and the frozen Phase C runner (by path, for `decision_gate`). It only
reads sealed and historical files. Deterministic: fixed seeds, sorted
iteration, no clock in any output.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AUDIT = REPO / "research/csia_semantic_correctness"
for p in (str(REPO), str(AUDIT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import semantic_probe as P  # noqa: E402

from csia.v2 import scenarios as SC  # noqa: E402
from csia.v2 import signatures as SIG  # noqa: E402
from csia.v2.attribution import UNIQUE  # noqa: E402
from csia.v2.localization import (SUPPORTED, UNSUPPORTED,  # noqa: E402
                                  EvidenceIndex, minimum_resolving_subsets)
from csia.v2.profiles import SCENARIOS, build_engine_for  # noqa: E402
from csia.v2.profiles.matched_scenarios import (MATCHED_BY_NAME,  # noqa: E402
                                                MATCHED_SETS, SET_SYMPTOM)
from csia_semantic_core import (INSUFFICIENT_EVIDENCE,  # noqa: E402
                                NO_CONSISTENT_HYPOTHESIS, Corrections,
                                SemanticCore21, SuccessorIndex,
                                attribute_2_1, declared_scope,
                                successor_predicate_table,
                                successor_symptoms)
from csia_semantic_core.predicates import successor_tests  # noqa: E402

OUT = HERE / "SEMANTIC_CORE_2_1_RESULTS.json"
RECEIPTS = HERE / "PHASE_E_CHANGE_RECEIPTS.jsonl"
LOCK = HERE / "PHASE_A_CHARACTERIZATION_LOCK.json"
FIXES = P.ALL_FIXES                 # ("C1", "F2", "C2", "C3", "C4", "C6")
OS = P.OS

#: Frozen reasoning code (Phase A lock) and every historical artifact the
#: brief lists. Hashed before and after the run.
PROTECTED = (
    "csia/v2/localization.py", "csia/v2/attribution.py",
    "csia/v2/signatures.py", "csia/v2/evidence.py", "csia/v2/engine.py",
    "engineering/v2/V2_SCENARIO_RESULTS.json",
    "engineering/v2/LOCALIZATION_RESULTS.csv",
    "engineering/v2/EVIDENCE_SUBSET_RESULTS.csv",
    "engineering/v2/LOCALIZATION_LEDGER.json",
    "engineering/v2/V2_PHASEC_GATE.json",
    "engineering/v2/V2_PHASEC_FREEZE.md",
    "engineering/v2/V2_CHATGPT_REVIEW_REPORT.md",
    "engineering/v2/run_phase_c.py",
    "research/xsys_001_confirmatory_campaign/stage1/STAGE1.json",
    "research/xsys_001_confirmatory_campaign/stage1/STAGE1.seal.json",
    "research/xsys_001_confirmatory_campaign/stage2/RESULTS.json",
    "research/xsys_001_confirmatory_campaign/stage2/PRIMARY_RESULT_RECORD.json",
    "research/xsys_001_confirmatory_campaign/CONFIRMATORY_RESULT_MANIFEST.json",
    "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py",
    "research/xsys_confirmatory_001/pipeline/stage2_score.py",
    "research/csia_semantic_correctness/semantic_probe.py",
    "research/csia_semantic_correctness/semantic_probe_results.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes() -> dict:
    return {p: sha(REPO / p) for p in PROTECTED}


def norm(x):
    return json.loads(json.dumps(x, sort_keys=True, default=str))


def diff_paths(a, b, path="", out=None, limit=40):
    """JSON paths where two documents differ."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}")
            else:
                diff_paths(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(path or "/")
    return out


# ================================================================ adapters
def core_for(cfg, fixes=FIXES, trace=False):
    return SemanticCore21(cfg.symptoms, cfg.predicates, cfg.relations,
                          Corrections.only(*fixes), trace=trace)


def _attr_meta(res, c1, f2):
    """The shadow's meta shape, from a 2.1 AttributionResult."""
    m = {"split_unsupported": {k: list(res.implicated[k]) for k in
                               ("implicated_nominal", "implicated_unavailable",
                                "implicated_unobserved")}}
    if res.implicated["implicated_other"]:
        m["split_unsupported"]["implicated_other"] = list(
            res.implicated["implicated_other"])
    if res.frozen_verdict == UNIQUE:
        t = res.trace
        if c1:
            m.update(declared_alternatives=t["declared_alternatives"],
                     relevant_discriminators=t["relevant_discriminators"],
                     unexcluded_alternatives=t["unexcluded_alternatives"])
        if f2 and "localization_disagreement" in t:
            m["localization_disagreement"] = t["localization_disagreement"]
        if res.withheld_unique_because:
            m["withheld_unique_because"] = list(res.withheld_unique_because)
    return m


def shadow21(records, cfg, fixes=FIXES):
    tr = core_for(cfg, fixes).reason(records)
    locs = tuple(x.v2 for x in tr.localizations)
    meta = {x.key: {"successor_verdict": x.outcome,
                    "collisions": x.trace["confirmed_and_refuted"],
                    "predicate_errors": [[e.predicate, e.subject, e.error_class]
                                         for e in x.predicate_errors]}
            for x in tr.localizations}
    return (locs, tr.attribution.v2), {
        "loc": meta, "attr": _attr_meta(tr.attribution, "C1" in fixes,
                                        "F2" in fixes),
        "disagreements": [k.split(":", 1)[::-1] for k in tr.conflicting_keys]}


def shadow_attribute21(records, relations, locs=(), c1=True, f2=True):
    res = attribute_2_1(records, relations, locs, c1=c1, f2=f2)
    return res.v2, _attr_meta(res, c1, f2)


def shadow_predicates21(preds, c2=True, c3=True, c4=True):
    return successor_predicate_table(preds, c2=c2, c3=c3, c4=c4)


def install_adapters():
    P.shadow = shadow21
    P.shadow_attribute = shadow_attribute21
    P.shadow_predicates = shadow_predicates21


# ================================================================== AUDIT
def section_audit(committed):
    """The audit's probe, with 2.1 in the successor slot."""
    install_adapters()
    got = {"R": P.section_R()}
    got["E"], runs = P.section_E()
    got["P"] = P.section_P(runs)
    got["N"] = P.section_N()
    got["X"] = P.section_X()
    got["SH"] = P.section_SH(runs)
    got = norm(got)
    comparison = {}
    for sec, val in got.items():
        paths = diff_paths(committed[sec], val)
        comparison[sec] = {"identical_to_audit": not paths,
                           "differing_paths": paths}
    return got, comparison, runs


# ====================================================================== D
def _at(doc, path):
    for k in path.split("."):
        doc = doc[k]
    return doc


def _sum(x):
    if isinstance(x, dict):
        return sum(_sum(v) for v in x.values())
    return x


#: (id, property or defect, frozen measure, 2.1 measure, correction,
#:  deferred?). Each measure is a path into the AUDIT section's results,
#:  where the audit's "shadow" slot now holds 2.1.
MEASURES = (
    ("N2.irrelevant", "P1/P19 irrelevant NOMINAL creates UNIQUE (N2)",
     "N.N2.irrelevant_C_creates_unique", "N.N2.shadow_irrelevant_C_creates_unique", "C1", False),
    ("N2.unique", "P19 UNIQUE configurations of 125 (N2); 4 remain, each with its declared alternative NOMINAL",
     "N.N2.unique_frozen", "N.N2.unique_shadow", "C1", None),
    ("N2.unavailable", "UNAVAILABLE creates UNIQUE (N2)",
     "N.N2.unavailable_creates_unique", "N.N2.shadow_unavailable_creates_unique", "C1", False),
    ("N2.duplicate", "P15 duplicate changes an attribution decision (N2)",
     "N.N2.duplicate_changes_decision", None, "C6", False),
    ("N2.order", "P3 order changes anything (N2)",
     "N.N2.order_changes_anything", None, "C6", False),
    ("N3.unknown_refutes", "P6 unknown record refutes (N3 COMMAND_NO_RESPONSE)",
     "N.N3.frozen_UNKNOWN_REFUTES", "N.N3.shadow_UNKNOWN_REFUTES", "C2", False),
    ("N3.unknown_supported", "P6 SUPPORTED resting on an unknown (N3)",
     "N.N3.frozen_UNKNOWN_SUPPORTED", "N.N3.shadow_UNKNOWN_SUPPORTED", "C2", False),
    ("N3.order", "P3 order (N3)", "N.N3.reverse_order_changes",
     "N.N3.shadow_reverse_order_changes", "C6", False),
    ("N3.duplicate", "P4 duplicate (N3)", "N.N3.duplicate_changes",
     "N.N3.shadow_duplicate_changes", "C6", False),
    ("N4.unknown_refutes", "P6 unknown record refutes (N4 OUTPUT_STALE)",
     "N.N4.frozen_UNKNOWN_REFUTES", "N.N4.shadow_UNKNOWN_REFUTES", "C2", False),
    ("N4.unknown_supported", "P6 SUPPORTED resting on an unknown (N4)",
     "N.N4.frozen_UNKNOWN_SUPPORTED", "N.N4.shadow_UNKNOWN_SUPPORTED", "C2", False),
    ("N4.order", "P3 order (N4)", "N.N4.reverse_order_changes",
     "N.N4.shadow_reverse_order_changes", "C6", False),
    ("N4.duplicate", "P4 duplicate (N4)", "N.N4.duplicate_changes",
     "N.N4.shadow_duplicate_changes", "C6", False),
    ("N5.irrelevant", "P1 irrelevant evidence changes a POSITION result (N5)",
     "N.N5.frozen_configs_where_irrelevant_evidence_changes_result",
     "N.N5.shadow_configs_where_irrelevant_evidence_changes_result", "C3", False),
    ("N6.unknown_refutes", "P6 unreported shared node refutes (N6)",
     "N.N6.frozen_UNKNOWN_REFUTES", "N.N6.shadow_UNKNOWN_REFUTES", "C2", False),
    ("N6.unknown_confirms", "P6 unreported shared node confirms (N6)",
     "N.N6.frozen_UNKNOWN_CONFIRMS", "N.N6.shadow_UNKNOWN_CONFIRMS", "C2", False),
    ("N6.unknown_supported", "P6 SUPPORTED resting on an unreported node (N6)",
     "N.N6.frozen_UNKNOWN_SUPPORTED", "N.N6.shadow_UNKNOWN_SUPPORTED", "C2", False),
    ("N1.monotone", "P14 monotone information (N1, both shapes)",
     "N1_violations", None, "none", False),
    ("P1", "P1 irrelevant addition changes another subject's localization (corpus)",
     "P.P1.frozen.violations", "P.P1.shadow.violations", "C3", False),
    ("P2", "P2 irrelevant removal changes a decision (corpus)",
     "P2_irrelevant_frozen", "P2_irrelevant_2_1", "C3", False),
    ("P2.unknown", "P2 removal whose relevance the declared scope cannot settle",
     "P2_unknown_frozen", "P2_unknown_2_1", "C3", False),
    ("P3", "P3 order (corpus)", "P.P3.frozen.violations",
     "P.P3.shadow.violations", "C6", False),
    ("P4", "P4 duplicate changes a decision (corpus)", "P.P4.frozen.decision",
     "P.P4.shadow.decision", "C6", False),
    ("P5", "P5 injected predicate faults NOT visible (corpus evaluations)",
     "P5_invisible_frozen", "P5_invisible_2_1", "C4", False),
    ("P6", "P6 Kleene violations under UNAVAILABLE (corpus)",
     "P.P6.frozen_UNAVAILABLE.cases_with_violation",
     "P.P6.shadow_UNAVAILABLE.cases_with_violation", "C2", False),
    ("P7", "P7 attribution candidates lost (corpus)",
     "P.P7_frozen", "P.P7_2_1", "none", False),
    ("P9", "P9 UNIQUE contradicting its own tick's localization (corpus)",
     "P.P9.frozen_violations", "P.P9.shadow_violations", "F2", False),
    ("P12", "P12 predicates inconsistent under UNAVAILABLE (corpus)",
     "P12_frozen", "P12_2_1", "C2", False),
    ("P16", "P16 POSITION_UNAVAILABLE on a function the graph calls ELIGIBLE",
     "P16_frozen", "P16_2_1", "C3", True),
)


def section_D(audit):
    a = dict(audit)
    a["P5_invisible_frozen"] = sum(
        r["ticks_evaluated"] - r["frozen_visible"]
        for r in audit["P"]["P5"]["per_predicate"].values())
    a["P5_invisible_2_1"] = sum(
        r["ticks_evaluated"] - r["shadow_visible"]
        for r in audit["P"]["P5"]["per_predicate"].values())
    a["P"] = dict(audit["P"], P7_frozen=audit["P"]["P1"]["frozen"][
        "attribution_candidates_lost"], P7_2_1=audit["P"]["P1"]["shadow"][
        "attribution_candidates_lost"])
    a["N1_violations"] = sum(
        v for shape in audit["N"]["N1"].values()
        for v in shape["monotonicity_violations"].values())
    for tag, key in (("frozen", "frozen"), ("2_1", "shadow")):
        tally = audit["P"]["P2"][key]["tally"]
        a[f"P2_irrelevant_{tag}"] = tally.get("IRRELEVANT_BUT_DECISION_CHANGING", 0)
        a[f"P2_unknown_{tag}"] = tally.get("UNKNOWN", 0)
    a["P12_frozen"] = len(audit["P"]["P12"]["offending_predicates"])
    a["P12_2_1"] = len(audit["P"]["P12"]["shadow_offending_predicates"])
    sv = audit["E"]["symptom_vs_function_state"]
    a["P16_frozen"] = sv["on_a_function_the_graph_calls_ELIGIBLE"]
    a["P16_2_1"] = sv["shadow_on_a_function_the_graph_calls_ELIGIBLE"]
    rows = []
    for mid, label, fpath, spath, corr, deferred in MEASURES:
        f = _sum(_at(a, fpath))
        s = f if spath is None else _sum(_at(a, spath))
        if isinstance(f, dict) or isinstance(s, dict):
            f, s = _sum(f), _sum(s)
        if mid == "N2.unique":
            cls = ("FIXED" if s < f else "STILL_PRESENT")
            note = ("the remaining UNIQUE configurations are the legitimate "
                    "form: A adverse, its declared alternative B NOMINAL")
        elif spath is None:
            cls = "NOT_APPLICABLE" if f == 0 else "STILL_PRESENT"
            note = ("no violation in frozen v2; the successor leaves this "
                    "path unchanged" if f == 0 else "")
        elif f == 0 and s == 0:
            cls, note = "NOT_APPLICABLE", "no violation under either"
        elif s == 0:
            cls, note = "FIXED", ""
        elif deferred:
            cls, note = "INTENTIONALLY_DEFERRED", (
                "residual is profile gap G-3 (SC-18), owner decision")
        else:
            cls = "STILL_PRESENT"
            note = "REGRESSION" if s > f else ""
        rows.append({"id": mid, "measure": label, "frozen_v2": f,
                     "semantic_core_2_1": s, "correction": corr,
                     "classification": cls, "note": note})
    deferred = [
        {"id": "P17", "measure": "uniform exception handling across stages",
         "classification": "INTENTIONALLY_DEFERRED",
         "note": "predicate faults are reported (C4). Attribution, detectors "
                 "and a missing table id still raise, as in 2.0.0; intake "
                 "validation (G5) is not approved"},
        {"id": "P18", "measure": "source-identity awareness (SC-14)",
         "classification": "INTENTIONALLY_DEFERRED",
         "note": "correlated evidence is outside the approved scope"},
        {"id": "P20", "measure": "predicate subject correctness (SC-15, C8)",
         "classification": "INTENTIONALLY_DEFERRED",
         "note": "rail source lookup (C8) is not approved"},
        {"id": "R9B", "measure": "a raising refuter creates SUPPORTED",
         "classification": "INTENTIONALLY_DEFERRED",
         "note": "the fault is now reported (evaluation PREDICATE_FAULT); "
                 "withholding the SUPPORTED verdict is governance option G5, "
                 "not approved"},
    ]
    counts: dict = {}
    for r in rows + deferred:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    return {"measures": rows, "not_measured_here": deferred,
            "classification_counts": dict(sorted(counts.items()))}


# ====================================================================== E
def _survivors(p):
    return None if p is None else set(p["supported"]) | set(p["unresolved"])


def _certainty(old, new):
    if old is None or new is None:
        return "UNIT_REMOVED" if new is None else "UNIT_ADDED"
    so, sn = _survivors(old), _survivors(new)
    if old["verdict"] == SUPPORTED and new["verdict"] != SUPPORTED:
        return "LESS_CERTAIN"
    if new["verdict"] == SUPPORTED and old["verdict"] != SUPPORTED:
        return "MORE_CERTAIN"
    if len(sn) > len(so):
        return "LESS_CERTAIN"
    if len(sn) < len(so):
        return "MORE_CERTAIN"
    return "SAME_SIZE"


def _detector_evidence(records, name):
    """Why the frozen POSITION_UNAVAILABLE detector fired on `name` and the
    2.1 detector did not: the adverse rows it read outside the declared
    scope."""
    fx = EvidenceIndex(records)
    six = SuccessorIndex(records, tracing=False)
    scope = declared_scope(six, name)
    t21 = successor_tests(True, True)
    fams = (("ESTIMATOR_PROCESS_HEALTHY", SIG._estimator_ok,
             lambda r: r.domain == "COMPUTE" and r.relation in (
                 "compute.process_alive", "compute.process_producing",
                 "compute.deadline_met")),
            ("FUNCTION_TIMING_WITHIN_DEADLINE", SIG._nav_timing_ok,
             lambda r: r.relation == "timing.end_to_end"),
            ("FUNCTION_LINKS_NOMINAL", SIG._nav_link_ok,
             lambda r: r.relation == "comm.link_state"))
    out = []
    for pid, frozen_fn, sel in fams:
        if frozen_fn(fx, name) is False and t21[pid](six, name) is not False:
            out.append({"predicate": pid,
                        "value_2_0": False, "value_2_1": t21[pid](six, name),
                        "adverse_out_of_scope": sorted(
                            P.rid(r) for r in records if sel(r) and
                            r.observation_state in P.ADVERSE
                            and r.component not in scope)})
    return out


def _loc_change(unit, old, new, loc_old, loc_new, records, functions):
    """Evidence and reason for one changed localization unit (rule C3).

    `assessment` says what the change does to the answer, judged by the
    repository's own function graph (P16), not by the successor being more
    conservative:
      CONSISTENT_WITH_FUNCTION_GRAPH
                                    a symptom on a function the same tick's
                                    frozen function graph calls ELIGIBLE,
                                    raised only by evidence outside its
                                    declared scope, is no longer raised
                                    (SC-05, P16)
      WEAKENED_BY_PROFILE_GAP       the profile declares nothing serving the
                                    subject, so a scoped predicate cannot
                                    look (SC-18); the frozen answer may have
                                    been right
      REVIEW                        anything else
    """
    rec = {"certainty": _certainty(old, new)}
    subject = unit.split("|", 1)[1]
    if new is None:
        ev = _detector_evidence(records, subject)
        six = SuccessorIndex(records, tracing=False)
        serving = sorted(declared_scope(six, subject) - {subject})
        fn = functions.get(subject)
        state = None if fn is None else fn.state
        rec["evidence_responsible"] = ev
        rec["function_graph_state"] = state
        rec["declared_serving_components"] = len(serving)
        ok = bool(ev) and all(e["adverse_out_of_scope"] for e in ev)
        rec["expected"] = ok
        if not ok:
            rec.update(reason="UNCLASSIFIED_REMOVAL", assessment="REVIEW")
        elif state == "ELIGIBLE":
            rec.update(reason="SYMPTOM_ON_A_FUNCTION_THE_GRAPH_CALLS_ELIGIBLE_REMOVED",
                       assessment="CONSISTENT_WITH_FUNCTION_GRAPH")
        elif not serving:
            rec.update(reason="SYMPTOM_LOST:PROFILE_DECLARES_NOTHING_SERVING_SUBJECT",
                       assessment="WEAKENED_BY_PROFILE_GAP")
        else:
            rec.update(reason="SYMPTOM_RAISED_ONLY_BY_EVIDENCE_OUTSIDE_DECLARED_SCOPE",
                       assessment="REVIEW")
        return rec
    if old is None:
        rec.update(expected=False, reason="UNCLASSIFIED_ADDITION",
                   evidence_responsible=[], assessment="REVIEW")
        return rec
    v0 = loc_old.detail["predicate_values"]
    v1 = loc_new.v2.detail["predicate_values"]
    per = loc_new.trace.get("predicates", {})
    changed = {}
    for pid in sorted(set(v0) | set(v1)):
        if v0.get(pid) != v1.get(pid):
            tr = per.get(pid, {})
            changed[pid] = {"value_2_0": v0.get(pid), "value_2_1": v1.get(pid),
                            "ignored_out_of_scope": sorted(
                                k for k, v in tr.get("ignored", {}).items()
                                if v == "OUT_OF_DECLARED_SCOPE"),
                            "scope_gaps": tr.get("scope_gaps", [])}
    rec["evidence_responsible"] = changed
    gaps = {g for c in changed.values() for g in c["scope_gaps"]}
    to_none = all(c["value_2_1"] is None for c in changed.values())
    oos = all(c["ignored_out_of_scope"] or c["scope_gaps"]
              for c in changed.values())
    if changed and to_none and gaps and rec["certainty"] != "MORE_CERTAIN":
        rec.update(expected=True, reason="PROFILE_DECLARES_NOTHING_SERVING_SUBJECT:"
                   + "|".join(sorted(gaps)), assessment="WEAKENED_BY_PROFILE_GAP")
    elif changed and oos and rec["certainty"] != "MORE_CERTAIN":
        rec.update(expected=True, assessment="REVIEW",
                   reason="OUT_OF_SCOPE_EVIDENCE_NO_LONGER_DECIDES")
    else:
        rec.update(expected=False, reason="UNCLASSIFIED_CHANGE_REVIEW",
                   assessment="REVIEW")
    return rec


def _rule_for(unit, new_val, per_fix):
    singles = [fx for fx in FIXES if per_fix[fx].get(unit, "ABSENT") == new_val]
    if singles:
        return "+".join(singles)
    if per_fix["C3+F2"].get(unit, "ABSENT") == new_val:
        return "C3+F2"
    return "UNATTRIBUTED"


def _dec(tr):
    locs = {x.key: P.lproj(x.v2) for x in tr.localizations}
    return locs, P.aproj(tr.attribution.v2)


def section_E(runs):
    receipts, clusters = [], {}
    totals = {"ticks": 0, "ticks_changed": 0, "ticks_localization_changed": 0,
              "ticks_attribution_changed": 0, "units_changed": 0,
              "unexpected_units": 0, "more_certain_units": 0}
    by_rule: dict = {}
    assess: dict = {}
    final_changes = {}
    for name, (_sc, engine, res) in sorted(runs.items()):
        core_all = SemanticCore21.from_engine(engine, Corrections(), trace=True)
        cores = {fx: SemanticCore21.from_engine(engine, Corrections.only(fx),
                                                trace=False) for fx in FIXES}
        cores["C3+F2"] = SemanticCore21.from_engine(
            engine, Corrections.only("C3", "F2"), trace=False)
        for tick, t in enumerate(res):
            totals["ticks"] += 1
            old_locs = {f"{x.symptom}|{x.subject}": x for x in t.localizations}
            old = ({k: P.lproj(v) for k, v in old_locs.items()},
                   P.aproj(t.attribution))
            tr = core_all.reason(t.records)
            new = _dec(tr)
            if old == new:
                continue
            new_locs = {x.key: x for x in tr.localizations}
            per_fix = {}
            for fx, c in cores.items():
                d = _dec(c.reason(t.records))
                per_fix[fx] = dict(d[0], ATTR=d[1])
            units = []
            for u in sorted(set(old[0]) | set(new[0])):
                o, n = old[0].get(u), new[0].get(u)
                if o == n:
                    continue
                ch = _loc_change(u, o, n, old_locs.get(u), new_locs.get(u),
                                 t.records, t.functions)
                units.append({"unit": u, "stage": "LOCALIZATION",
                              "old": o, "new": n,
                              "rule": _rule_for(u, n if n is not None
                                                else "ABSENT", per_fix), **ch})
            if old[1] != new[1]:
                a = tr.attribution
                expected = (old[1]["verdict"] == UNIQUE
                            and new[1]["verdict"] == "AMBIGUOUS"
                            and old[1]["candidates"] == new[1]["candidates"]
                            and bool(a.withheld_unique_because))
                units.append({
                    "unit": "ATTRIBUTION", "stage": "ATTRIBUTION",
                    "old": old[1], "new": new[1],
                    "rule": _rule_for("ATTR", new[1], per_fix),
                    "certainty": "LESS_CERTAIN" if expected else "REVIEW",
                    "evidence_responsible": {
                        "withheld_unique_because": list(a.withheld_unique_because),
                        "localization_disagreement":
                            a.trace.get("localization_disagreement", []),
                        "unexcluded_alternatives":
                            a.trace.get("unexcluded_alternatives", [])},
                    "expected": expected,
                    "true_domain_from_description": TRUE_DOMAIN.get(name),
                    "assessment": (
                        "REVIEW" if not expected or name not in TRUE_DOMAIN
                        else "WRONG_UNIQUE_CORRECTED"
                        if old[1]["candidates"][0].split("/", 1)[0] != TRUE_DOMAIN[name]
                        else "RIGHT_UNIQUE_WEAKENED"),
                    "reason": ("UNIQUE_WITHHELD:" + "|".join(
                        a.withheld_unique_because)) if expected
                    else "UNCLASSIFIED_ATTRIBUTION_CHANGE"})
            totals["ticks_changed"] += 1
            totals["ticks_localization_changed"] += int(old[0] != new[0])
            totals["ticks_attribution_changed"] += int(old[1] != new[1])
            for un in units:
                totals["units_changed"] += 1
                totals["unexpected_units"] += int(not un["expected"])
                totals["more_certain_units"] += int(
                    un["certainty"] == "MORE_CERTAIN")
                by_rule[un["rule"]] = by_rule.get(un["rule"], 0) + 1
                sym = un["unit"].split("|", 1)[0]
                assess[un["assessment"]] = assess.get(un["assessment"], 0) + 1
                key = "|".join((un["rule"], un["stage"], sym, un["reason"],
                                un["assessment"],
                                str((un["old"] or {}).get("verdict")) + "->"
                                + str((un["new"] or {}).get("verdict"))))
                c = clusters.setdefault(key, {
                    "rule": un["rule"], "stage": un["stage"], "symptom": sym,
                    "reason": un["reason"], "expected": un["expected"],
                    "assessment": un["assessment"],
                    "transition": key.rsplit("|", 1)[1], "units": 0,
                    "scenarios": {}})
                c["units"] += 1
                c["scenarios"].setdefault(name, []).append(tick)
                un["cluster"] = key
            receipts.append({
                "receipt": f"SC21-E-{name}-{tick:03d}", "scenario": name,
                "tick": tick, "t": round(float(t.t), 6),
                "semantics_old": "2.0.0", "semantics_new": "2.1.0",
                "HISTORICAL_RESULT_MODIFIED": "NO", "units": units})
            if tick == len(res) - 1:
                final_changes[name] = [
                    {k: u[k] for k in ("unit", "old", "new", "rule", "reason",
                                       "expected", "assessment")} for u in units]
    for c in clusters.values():
        c["scenarios"] = {k: {"ticks": len(v), "first": v[0], "last": v[-1]}
                          for k, v in sorted(c["scenarios"].items())}
    return {"totals": totals, "units_by_rule": dict(sorted(by_rule.items())),
            "units_by_assessment": dict(sorted(assess.items())),
            "clusters": dict(sorted(clusters.items())),
            "final_tick_changes": final_changes,
            "final_tick_scenarios_changed": len(final_changes)}, receipts


# ====================================================================== F
def section_F():
    pipe = REPO / "research/xsys_confirmatory_001/pipeline"
    if str(pipe) not in sys.path:
        sys.path.insert(0, str(pipe))
    import stage1_evidence as S1  # noqa: E402
    import stage2_score as S2  # noqa: E402
    import xsys_v2_adapter as XA  # noqa: E402
    import numpy as np  # noqa: E402
    raw = P.XSYS_STAGE1.read_bytes()
    seal = json.loads((P.XSYS_STAGE1.parent / "STAGE1.seal.json").read_text())
    s1_sha = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    results = json.loads(P.XSYS_RESULTS.read_text())
    primary_record = json.loads(
        (P.XSYS_RESULTS.parent / "PRIMARY_RESULT_RECORD.json").read_text())
    core = SemanticCore21((XA.SPEC,), XA.PREDICATES, (), Corrections(),
                          trace=False)
    new_verdicts, n = {}, 0
    dec_diff = dict_diff = frozen_diff = 0
    labels, evaluations = {}, {}
    errors = dups = conflicts = 0
    for oid, t in sorted(data["trials"].items()):
        nv = new_verdicts.setdefault(oid, {})
        for vc in sorted(t["verdicts"]):
            cp, v = vc.split("/")
            per = nv.setdefault(vc, {})
            for subj in sorted(t["features"]):
                f = t["features"][subj]
                rpm, dyn, ctrl, w = S1.plan(v, cp, f)
                stats = {"L": f["L_T1"] if cp == "C1" else f["L_T3"],
                         "D": f["D_T3"] if v == "V4_INVALID_WINDOW" else f["D_T1"],
                         "C": f["C_T3"]}
                recs = XA.records_for(subj, rpm, dyn, ctrl, stats, w)
                sealed = t["verdicts"][vc][subj]
                floc = XA.localize_subject(recs, subj)
                fgot = None if floc is None else norm(floc.to_dict())
                frozen_diff += int(fgot != sealed)
                tr = core.reason(recs)
                mine = [x for x in tr.localizations if x.subject == subj]
                got = None if not mine else norm(mine[0].to_v2_0_dict())
                per[subj] = got
                n += 1
                dict_diff += int(got != sealed)
                dec_diff += int((None if got is None else
                                 {k: got[k] for k in ("verdict", "supported",
                                                      "unresolved", "rejected")})
                                != (None if sealed is None else
                                    {k: sealed[k] for k in ("verdict", "supported",
                                                            "unresolved", "rejected")}))
                errors += sum(len(x.predicate_errors) for x in tr.localizations)
                dups += len(tr.duplicates_collapsed)
                conflicts += len(tr.conflicting_keys)
                for x in mine:
                    labels[x.outcome] = labels.get(x.outcome, 0) + 1
                    evaluations[x.evaluation] = evaluations.get(x.evaluation, 0) + 1

    def outcomes_from(verdicts):
        per_trial = {}
        for aid, k in results["trials"].items():
            v = verdicts[k["opaque_id"]]
            outc = {}
            for cpv, per_motor in v.items():
                if k["kind"] == "N":
                    outc[cpv] = S2.outcome_nominal(per_motor)
                else:
                    outc[cpv] = S2.outcome_symptomatic(per_motor.get("motor_0"),
                                                       S2.TRUTH_H[k["kind"]])
            per_trial[aid] = {**k, "outcomes": outc}
        return per_trial

    def primary_of(per_trial):
        """stage2_score.main's primary, from its own functions."""
        pairs: dict = {}
        for t in per_trial.values():
            if t["kind"] in ("A", "B"):
                pairs.setdefault(t["pair_id"], {})[t["kind"]] = t
        eligible = {pid: p for pid, p in pairs.items() if "A" in p and "B" in p}
        cpv = "/".join(S2.PRIMARY)
        by_cond: dict = {}
        for p in eligible.values():
            ok = (p["A"]["outcomes"].get(cpv) == "UNIQUE_CORRECT"
                  and p["B"]["outcomes"].get(cpv) == "UNIQUE_CORRECT")
            by_cond.setdefault(p["A"]["nuisance_id"], []).append(1.0 if ok else 0.0)
        vals = [x for xs in by_cond.values() for x in xs]
        rate = float(np.mean(vals)) if vals else None
        res = S2.cluster_bound(rate if rate is not None else 0.0, len(by_cond))
        wrong = sum(1 for t in per_trial.values() if t["kind"] in ("A", "B")
                    and t["outcomes"].get(cpv) == "WRONG")
        res.update({"n_pairs": len(vals), "n_success": int(sum(vals)),
                    "wrong_A_B": wrong,
                    "H_PRIMARY": ("SUPPORTED" if res["lower95"] is not None
                                  and res["lower95"] > S2.NULL_RATE and wrong == 0
                                  else "NOT SUPPORTED")})
        return res

    sealed_verdicts = {oid: t["verdicts"] for oid, t in data["trials"].items()}
    old_trials = outcomes_from(sealed_verdicts)
    new_trials = outcomes_from(new_verdicts)
    outcome_diff = sum(1 for aid in old_trials for cpv in old_trials[aid]["outcomes"]
                       if old_trials[aid]["outcomes"][cpv]
                       != new_trials[aid]["outcomes"].get(cpv))
    recorded_diff = sum(1 for aid, t in results["trials"].items()
                        for cpv, o in t["outcomes"].items()
                        if new_trials[aid]["outcomes"].get(cpv) != o)
    p_sealed = primary_of(old_trials)
    p_new = primary_of(new_trials)
    matches_record = (
        p_new["n_pairs"] == primary_record["VALID_MATCHED_PAIRS"]
        and p_new["n_success"] == primary_record["RESOLVED_MATCHED_PAIRS"]
        and p_new["lower95"] == primary_record["ONE_SIDED_95_LB"]
        and p_new["n_eff"] == primary_record["N_EFF_CONDITIONS"]
        and p_new["wrong_A_B"] == primary_record["WRONG"]
        and (p_new["H_PRIMARY"] == "SUPPORTED")
        == (primary_record["PRIMARY_SUPPORTED"] == "YES"))
    gate = ("PASS" if (dec_diff == 0 and outcome_diff == 0 and recorded_diff == 0
                       and matches_record and p_new == p_sealed
                       and s1_sha == seal["stage1_output_sha256"])
            else "SEMANTIC_2_1_XSYS_GOVERNANCE_BLOCK")
    return {"stage1_sha256": s1_sha,
            "stage1_matches_seal": s1_sha == seal["stage1_output_sha256"],
            "slots": n, "frozen_replay_differs_from_sealed": frozen_diff,
            "decision_differences_2_1_vs_sealed": dec_diff,
            "full_v2_0_view_differences_2_1_vs_sealed": dict_diff,
            "outcome_differences_2_1_vs_sealed_verdicts": outcome_diff,
            "outcome_differences_2_1_vs_recorded_results": recorded_diff,
            "predicate_errors": errors, "duplicates_collapsed": dups,
            "conflicting_keys": conflicts,
            "outcome_labels_2_1": dict(sorted(labels.items())),
            "evaluation_status_2_1": dict(sorted(evaluations.items())),
            "primary_recomputed_from_sealed_verdicts": p_sealed,
            "primary_recomputed_under_2_1": p_new,
            "primary_record": {k: primary_record[k] for k in (
                "VALID_MATCHED_PAIRS", "RESOLVED_MATCHED_PAIRS",
                "ONE_SIDED_95_LB", "N_EFF_CONDITIONS", "WRONG",
                "PRIMARY_SUPPORTED")},
            "primary_under_2_1_matches_record": matches_record,
            "XSYS_HARD_GATE": gate}


# ====================================================================== G
def _phase_c_runner():
    path = REPO / "engineering/v2/run_phase_c.py"
    spec = importlib.util.spec_from_file_location("frozen_run_phase_c", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(set_name, name, want, loc, blind, expectation, verdict=None):
    return {"set": set_name, "scenario": name, "symptom": want,
            "subject": loc.subject, "detected": True,
            "verdict": verdict or loc.verdict,
            "initial_domains": "|".join(loc.initial_domains),
            "initial_candidates": len(loc.initial_candidates),
            "supported": "|".join(loc.supported),
            "unresolved": "|".join(loc.unresolved),
            "rejected": "|".join(f"{h}<-{p}" for h, p in loc.rejected),
            "candidate_domains_after": loc.candidate_domain_count,
            "evidence": "|".join(loc.evidence),
            "unmeasurable": "|".join(loc.unmeasurable),
            "dependency_model_blind_to": blind, "expectation": expectation}


def _missing(set_name, name, want, expectation):
    return {"set": set_name, "scenario": name, "symptom": want, "subject": "",
            "detected": False, "verdict": "SYMPTOM_NOT_DETECTED",
            "initial_domains": "", "initial_candidates": 0, "supported": "",
            "unresolved": "", "rejected": "", "candidate_domains_after": 0,
            "evidence": "", "unmeasurable": "", "dependency_model_blind_to": "",
            "expectation": expectation}


def phase_c_rows(ticks=60):
    """LOCALIZATION_RESULTS rows, frozen and 2.1, from one run per member."""
    frozen_rows, rows21, subsets_f, subsets21 = [], [], [], []
    for set_name, members in MATCHED_SETS.items():
        want = SET_SYMPTOM[set_name]
        spec = SIG.SYMPTOMS_BY_ID[want]
        for name in members:
            sc = MATCHED_BY_NAME[name]
            engine = build_engine_for(sc)
            res = SC.run(engine, sc, ticks=ticks, payload_for=P.feed(sc))
            final = res[-1]
            blind = "|".join(SIG.uncovered_common_cause_domains(
                EvidenceIndex(final.records)))
            core = SemanticCore21.from_engine(engine, Corrections(), trace=False)
            tr = core.reason(final.records)
            for tag, locs, out in (("f", [x for x in final.localizations
                                          if x.symptom == want], frozen_rows),
                                   ("n", [x.v2 for x in tr.localizations
                                          if x.symptom == want], rows21)):
                if not locs:
                    out.append(_missing(set_name, name, want, sc.expectation))
                for loc in locs:
                    out.append(_row(set_name, name, want, loc, blind,
                                    sc.expectation))
            # evidence subsets (EVIDENCE_SUBSET_RESULTS.csv)
            ix = EvidenceIndex(final.records)
            six = SuccessorIndex(final.records, tracing=False)
            sspec = next(s for s in core.symptoms if s.symptom_id == want)
            for tag, index, sp, preds, out in (
                    ("f", ix, spec, SIG.PREDICATES, subsets_f),
                    ("n", six, sspec, core.predicates, subsets21)):
                for subject in sp.detect(index):
                    got = minimum_resolving_subsets(sp, index, subject, preds)
                    out.append({"scenario": name, "subject": subject,
                                "verdict": got["verdict"],
                                "minimum_size": got["minimum_size"],
                                "minimum_subset": "|".join(got["minimum_subset"] or ()),
                                "uniquely_resolved": got["uniquely_resolved"]})
    return frozen_rows, rows21, subsets_f, subsets21


def _csv(path):
    with open(REPO / path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


#: Ground truth for the scenarios whose final attribution changes, read from
#: each scenario's own `description` (csia/v2/profiles). The domain of the
#: injected cause.
TRUE_DOMAIN = {
    "ACTUATOR_NO_RESPONSE": "ACTUATION", "CLOCK_DRIFT": "TIMING",
    "MS_B3_DRIVE_NO_CURRENT": "ACTUATION", "MS_B4_MECHANICAL": "ACTUATION",
    "MS_B5_RESPONSE_SENSOR": "SENSOR", "MS_TS_B5_RESPONSE_SENSOR": "SENSOR",
    "STALLED_ACTUATOR": "ACTUATION", "PROCESS_STALL": "COMPUTE",
    "MS_D2_ESTIMATOR_STALE": "COMPUTE", "TS_STALLED": "ACTUATION",
}


def section_G(runs_60, E):
    RP = _phase_c_runner()
    out = {}
    # -- LOCALIZATION_RESULTS.csv and the decision gate (60 ticks) --------
    f_rows, n_rows, sub_f, sub_n = phase_c_rows()
    recorded = _csv("engineering/v2/LOCALIZATION_RESULTS.csv")
    cols = ("set", "scenario", "symptom", "subject", "detected", "verdict",
            "supported", "unresolved", "rejected", "evidence", "unmeasurable")
    def proj(rows):
        return [{c: str(r[c]) for c in cols} for r in rows]
    out["localization_results_frozen_replay_matches_record"] = (
        proj(f_rows) == proj(recorded))
    changed_rows = []
    rec_by = {(r["scenario"], r["subject"]): r for r in proj(recorded)}
    new_by = {(r["scenario"], r["subject"]): r for r in proj(n_rows)}
    for k in sorted(set(rec_by) | set(new_by)):
        a, b = rec_by.get(k), new_by.get(k)
        if a is None or b is None or any(a[c] != b[c] for c in (
                "detected", "verdict", "supported", "unresolved", "rejected")):
            changed_rows.append({"scenario": k[0], "subject": k[1],
                                 "recorded": a and {c: a[c] for c in (
                                     "verdict", "supported", "unresolved")},
                                 "semantic_core_2_1": b and {c: b[c] for c in (
                                     "verdict", "supported", "unresolved")}})
    out["localization_results_rows"] = len(recorded)
    out["localization_results_rows_changed"] = changed_rows
    gate_recorded = json.loads((REPO / "engineering/v2/V2_PHASEC_GATE.json").read_text())
    gate_f = RP.decision_gate(f_rows)
    gate_n = RP.decision_gate(n_rows)
    out["gate_frozen_recomputed_matches_record"] = norm(gate_f) == norm(gate_recorded)
    out["gate_2_1"] = norm(gate_n)
    out["gate_verdict"] = {"recorded": gate_recorded["verdict"],
                           "semantic_core_2_1": gate_n["verdict"]}
    out["gate_qualifying_sets"] = {
        "recorded": [q["set"] for q in gate_recorded["qualifying_sets"]],
        "semantic_core_2_1": [q["set"] for q in gate_n["qualifying_sets"]]}
    out["gate_qualifying_answers_unchanged"] = (
        norm(gate_n["qualifying_sets"]) == norm(gate_recorded["qualifying_sets"]))
    out["gate_non_qualifying_changed"] = [
        {"set": b["set"], "recorded": a, "semantic_core_2_1": b}
        for a, b in zip(norm(gate_recorded["non_qualifying_sets"]),
                        norm(gate_n["non_qualifying_sets"])) if a != b]
    rec_sub = _csv("engineering/v2/EVIDENCE_SUBSET_RESULTS.csv")
    sub_cols = ("scenario", "subject", "verdict", "minimum_size",
                "minimum_subset", "uniquely_resolved")
    out["evidence_subsets_frozen_replay_matches_record"] = (
        [{c: str(r[c]) for c in sub_cols} for r in rec_sub]
        == [{c: str(r[c]) for c in sub_cols} for r in sub_f])
    sf = {(r["scenario"], r["subject"]): r for r in sub_f}
    sn = {(r["scenario"], r["subject"]): r for r in sub_n}
    out["evidence_subset_rows"] = len(rec_sub)
    out["evidence_subset_rows_changed"] = [
        {"scenario": k[0], "subject": k[1], "recorded": sf.get(k),
         "semantic_core_2_1": sn.get(k)}
        for k in sorted(set(sf) | set(sn)) if sf.get(k) != sn.get(k)]

    # -- V2_SCENARIO_RESULTS.json and the review report (200 ticks) -------
    recorded = json.loads((REPO / "engineering/v2/V2_SCENARIO_RESULTS.json").read_text())
    ticks = recorded["ticks_per_scenario"]
    per, all_match = {}, True
    for name in sorted(recorded["scenarios"]):
        sc = SCENARIOS[name]
        engine = build_engine_for(sc)
        res = SC.run(engine, sc, ticks=ticks, payload_for=P.feed(sc))
        summ = SC.summarize(res)
        r = recorded["scenarios"][name]
        match = (summ["attribution_verdicts"] == r["attribution_verdicts"]
                 and summ["final"]["attribution"] == r["final"]["attribution"]
                 and summ["final"]["candidates"] == r["final"]["candidates"])
        all_match &= match
        core = SemanticCore21.from_engine(engine, Corrections(), trace=False)
        tally, loc_changed, fin = {}, 0, None
        for t in res:
            tr = core.reason(t.records)
            v = tr.attribution.verdict
            tally[v] = tally.get(v, 0) + 1
            loc_changed += int([P.lproj(x.v2) for x in tr.localizations]
                               != [P.lproj(x) for x in t.localizations])
            fin = tr
        per[name] = {
            "recorded_final": r["final"]["attribution"],
            "recorded_candidates": r["final"]["candidates"],
            "semantic_core_2_1_final": fin.attribution.verdict,
            "withheld_unique_because": list(fin.attribution.withheld_unique_because),
            "recorded_tally": r["attribution_verdicts"],
            "semantic_core_2_1_tally": dict(sorted(tally.items())),
            "ticks_with_localization_change": loc_changed}
    out["scenario_results_ticks"] = ticks
    out["scenario_results_frozen_replay_matches_record"] = all_match
    out["scenario_results"] = per
    out["scenario_results_final_changed"] = sorted(
        n for n, v in per.items() if v["recorded_final"] != v["semantic_core_2_1_final"])

    # -- the 44-scenario, 60-tick final ticks (the audit corpus) ----------
    final_attr = {}
    for name, units in E["final_tick_changes"].items():
        for u in units:
            if u["unit"] == "ATTRIBUTION":
                cand = u["old"]["candidates"]
                dom = cand[0].split("/", 1)[0] if len(cand) == 1 else None
                truth = TRUE_DOMAIN.get(name)
                final_attr[name] = {
                    "old": u["old"], "new": u["new"], "rule": u["rule"],
                    "true_domain_from_description": truth,
                    "old_unique_named_true_domain": (None if truth is None
                                                     else dom == truth),
                    "recorded_in_V2_SCENARIO_RESULTS": name in recorded["scenarios"]}
    out["final_tick_attribution_changes_60"] = final_attr
    out["wrong_unique_corrected"] = sorted(
        n for n, v in final_attr.items() if v["old_unique_named_true_domain"] is False)
    out["right_unique_weakened"] = sorted(
        n for n, v in final_attr.items() if v["old_unique_named_true_domain"] is True)
    out["final_attribution_changes_without_truth"] = sorted(
        n for n, v in final_attr.items() if v["true_domain_from_description"] is None)
    return out


# ============================================================ R under 2.1
def section_R21():
    """The Phase A targets, re-run through 2.1 directly."""
    AIR = P.AIR
    core = core_for(AIR, trace=True)
    rec = P.rec
    out = {}

    def run(records):
        return core.reason(records)

    rail = rec("POWER", "rail_5v", "power.rail_tolerance", OS.VIOLATED)
    cpu = rec("COMPUTE", "cpu", "compute.resource_headroom")
    a = run([rail, cpu]).attribution
    out["R1_unrelated_nominal_creates_UNIQUE"] = {
        "frozen": P.frozen([rail, cpu], AIR)[1].verdict, "2_1": a.verdict,
        "reason": list(a.withheld_unique_because),
        "fixed": a.verdict != UNIQUE}
    base6 = [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                 deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial")),
             rec("TIMING", "nav_solution.sensor_slow", "timing.rate"),
             rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget"),
             rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget"),
             rec("COMMUNICATION", "gnss_serial", "comm.link_state"),
             rec("COMPUTE", "state_estimator", "compute.process_alive"),
             rec("COMPUTE", "state_estimator", "compute.process_producing")]
    ok = rec("TIMING", "nav_solution", "timing.clock_consistency")
    bad = rec("TIMING", "nav_solution", "timing.clock_consistency", OS.VIOLATED)
    r6a, r6b = run(base6 + [ok, bad]), run(base6 + [bad, ok])
    out["R6_order_dependence"] = {
        "2_1_A": [P.lproj(x.v2) for x in r6a.localizations],
        "2_1_B": [P.lproj(x.v2) for x in r6b.localizations],
        "conflicts": list(r6a.conflicting_keys),
        "fixed": ([P.lproj(x.v2) for x in r6a.localizations]
                  == [P.lproj(x.v2) for x in r6b.localizations])}
    src = rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED,
              deps=("POWER/rail_5v",))
    r7a, r7b = run([src, rail]), run([src, src, rail])
    out["R7_duplicate_induced_symptom"] = {
        "2_1_single": [x.key for x in r7a.localizations],
        "2_1_duplicated": [x.key for x in r7b.localizations],
        "duplicates_collapsed": r7b.duplicates_collapsed,
        "fixed": ([x.key for x in r7a.localizations]
                  == [x.key for x in r7b.localizations])}
    stale = [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                 deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial")),
             rec("TIMING", "nav_solution", "timing.clock_consistency"),
             rec("TIMING", "nav_solution.sensor_slow", "timing.rate")]
    proc_ok = [rec("COMPUTE", "state_estimator", "compute.process_alive"),
               rec("COMPUTE", "state_estimator", "compute.process_producing")]
    tr_bad = rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget", OS.VIOLATED)
    pr_ok = rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget")
    link_u = rec("COMMUNICATION", "gnss_serial", "comm.link_state", OS.UNAVAILABLE)
    r8b = run(stale + [tr_bad, pr_ok, link_u] + proc_ok).localizations[0]
    out["R8B_unavailable_link_refutes_true_cause"] = {
        "2_1": P.lproj(r8b.v2), "outcome": r8b.outcome,
        "fixed": "COMMUNICATION/transport_delay" not in dict(r8b.v2.rejected)}
    tr_ok = rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget")
    pr_bad = rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget", OS.VIOLATED)
    link_n = rec("COMMUNICATION", "gnss_serial", "comm.link_state")
    alive_u = rec("COMPUTE", "state_estimator", "compute.process_alive", OS.UNAVAILABLE)
    r8e = run(stale + [tr_ok, pr_bad, link_n, alive_u]).localizations[0]
    out["R8E_unavailable_process_gives_wrong_SUPPORTED"] = {
        "2_1": P.lproj(r8e.v2), "outcome": r8e.outcome,
        "fixed": r8e.v2.supported != ("COMPUTE/processing_delay",)
        or r8e.v2.verdict != SUPPORTED}
    m_adv = rec("ACTUATION", "motor_0", "actuation.electrical_response", OS.VIOLATED,
                codes=("ACT_NO_ELECTRICAL_RESPONSE",),
                deps=("POWER/battery", "COMMUNICATION/esc_can"))
    bat_u = rec("POWER", "battery", "power.source_health", OS.UNAVAILABLE)
    a = run([m_adv, bat_u, cpu]).attribution
    out["R8G_unavailable_battery_gives_UNIQUE"] = {
        "2_1": a.verdict, "reason": list(a.withheld_unique_because),
        "fixed": a.verdict != UNIQUE}
    shared4 = ("POWER/rail_3v3", "COMMUNICATION/bus_a", "COMPUTE/proc_a", "TIMING/clk_a")
    s1 = rec("SENSOR", "source.imu0", "v1_1.source_health", OS.VIOLATED, deps=shared4)
    s2 = rec("SENSOR", "source.mag", "v1_1.source_health", OS.VIOLATED, deps=shared4)
    r17 = run([s1, s2]).localizations[0]
    out["R17_unreported_shared_nodes_support_independent_faults"] = {
        "2_1": P.lproj(r17.v2), "outcome": r17.outcome,
        "fixed": "SENSOR/independent_faults" not in r17.v2.supported}
    # R9 / R9B: the synthetic spec, through the successor table.
    spec = P.SymptomSpec("S", "synthetic", detect=lambda ix: ("x",), hypotheses=(
        P.Hypothesis("D1/h1", "D1", "m", confirmed_by=("P",), refuted_by=("Q",)),
        P.Hypothesis("D2/h2", "D2", "m", confirmed_by=("P",), refuted_by=("R",))))

    def boom(i, s):
        raise KeyError("defect")

    def tbl(q, r):
        return {"P": P.Predicate("P", "", "D", lambda i, s: True),
                "Q": P.Predicate("Q", "", "D", q),
                "R": P.Predicate("R", "", "D", r)}
    r9 = SemanticCore21((spec,), tbl(boom, lambda i, s: False)).reason([])
    x = r9.localizations[0]
    out["R9_exception_silently_unmeasurable"] = {
        "2_1": P.lproj(x.v2), "evaluation": x.evaluation,
        "predicate_errors": [e.to_dict() for e in x.predicate_errors],
        "evidence_unavailable": list(x.evidence_unavailable),
        "fixed": x.evaluation == "PREDICATE_FAULT" and bool(x.predicate_errors)}
    r9b = SemanticCore21((spec,), tbl(boom, lambda i, s: True)).reason([])
    x = r9b.localizations[0]
    out["R9B_raising_refuter_creates_SUPPORTED"] = {
        "2_1": P.lproj(x.v2), "evaluation": x.evaluation,
        "predicate_errors": [e.to_dict() for e in x.predicate_errors],
        "fault_now_observable": x.evaluation == "PREDICATE_FAULT",
        "verdict_still_SUPPORTED": x.v2.verdict == SUPPORTED,
        "fixed": "PARTLY: the fault is observable; withholding SUPPORTED is "
                 "governance option G5, not approved"}
    out["all_fixed_or_made_observable"] = all(
        v["fixed"] is True for k, v in out.items() if k != "R9B_raising_refuter_creates_SUPPORTED") \
        and out["R9B_raising_refuter_creates_SUPPORTED"]["fault_now_observable"]
    return out


# ================================================================== main
def main():
    lock = json.loads(LOCK.read_text())
    committed = json.loads(P.OUT.read_text())
    before = hashes()
    results = {"harness": "semantic_core_2_1_differential",
               "semantics": {"historical": "2.0.0", "successor": "2.1.0"},
               "phase_a_lock_sha256": sha(LOCK),
               "phase_a_head_commit": lock["head_commit"]}
    results["R21"] = section_R21()
    audit, comparison, runs = section_audit(committed)
    results["AUDIT"] = {"comparison_with_audit_shadow": comparison,
                        "R11A_values": {
                            "audit_shadow": committed["R"]["R11A"]["shadow_predicate_errors"],
                            "semantic_core_2_1": audit["R"]["R11A"]["shadow_predicate_errors"],
                            "note": "2.1 records (predicate, evaluated_as, subject, "
                                    "error_class); the audit's shadow recorded "
                                    "(predicate, subject, error_class). Same faults"},
                        "SH_2_1": audit["SH"], "X_2_1": audit["X"]}
    results["D"] = section_D(audit)
    E, receipts = section_E(runs)
    results["E"] = E
    results["F"] = section_F()
    results["G"] = section_G(runs, E)
    after = hashes()
    results["PROTECTED_FILES"] = {
        "sha256": before, "unchanged_by_this_run": before == after}
    if before != after:
        raise SystemExit("a protected file changed during the run")
    OUT.write_text(json.dumps(norm(results), indent=1, sort_keys=True) + "\n")
    with open(RECEIPTS, "w", encoding="utf-8") as fh:
        for r in receipts:
            fh.write(json.dumps(norm(r), sort_keys=True) + "\n")
    print(json.dumps({
        "wrote": [str(OUT.relative_to(REPO)), str(RECEIPTS.relative_to(REPO))],
        "sha256": {"results": sha(OUT), "receipts": sha(RECEIPTS)},
        "XSYS_HARD_GATE": results["F"]["XSYS_HARD_GATE"],
        "E_totals": E["totals"]}, indent=1))


if __name__ == "__main__":
    main()
