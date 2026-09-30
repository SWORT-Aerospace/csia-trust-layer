#!/usr/bin/env python3
"""Shadow validation of Semantic Core 2.1 against frozen v2.0. RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/shadow_validation.py

Frozen v2.0 is authoritative throughout; `csia_semantic_core.shadow.ShadowRunner`
observes each tick and returns nothing to it.

Datasets:
    A  the 44 shipped scenarios x 60 ticks (2,640 ticks), classified against
       ground truth (ground_truth.py)
    B  XSYS-001: the 3,872 sealed slots, reusing the 2.1 package's replay
       (research/csia_semantic_core_2_1/semantic_core_2_1_differential.py
       section F), re-executed here
Counterfactual profile test (Part 7): every candidate successor-profile
declaration in profile_candidates.json, alone, together and left out one at
a time, plus the deliberately wrong R-BAD, run in shadow over dataset A.

Writes SHADOW_RESULTS.json, SHADOW_DIFFERENCES.csv and SHADOW_LOG.jsonl.
Reads frozen code and sealed files only; writes nothing else.
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
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"),
          str(REPO / "research/csia_semantic_core_2_1"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ground_truth as GT  # noqa: E402
import semantic_probe as P  # noqa: E402

from csia.v2 import signatures as SIG  # noqa: E402
from csia.v2.attribution import UNIQUE  # noqa: E402
from csia.v2.localization import EvidenceIndex  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia.v2.profiles.matched_scenarios import (MATCHED_SETS,  # noqa: E402
                                                SET_SYMPTOM)
from csia_semantic_core import (SemanticCore21, SuccessorIndex,  # noqa: E402
                                declared_scope)
from csia_semantic_core.profile_overlay import (Declaration,  # noqa: E402
                                                ProfileOverlay,
                                                load_successor)
from csia_semantic_core.shadow import ShadowRunner  # noqa: E402

OUT = HERE / "SHADOW_RESULTS.json"
DIFFS = HERE / "SHADOW_DIFFERENCES.csv"
LOG = HERE / "SHADOW_LOG.jsonl"
CANDIDATES = json.loads((HERE / "profile_candidates.json").read_text())["candidates"]
NAV_FUNCS = ("COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION",
             "GEOFENCE_SUPPORT", "INERTIAL_CONTINUATION")


def overlay(*ids, version=None) -> ProfileOverlay:
    decls = tuple(Declaration(**{k: (tuple(v) if isinstance(v, list) else v)
                                 for k, v in CANDIDATES[i].items()}) for i in ids)
    return ProfileOverlay("aircraft-successor", version or "+".join(ids) or "none",
                          "csia/v2/profiles/aircraft.py", decls)


# ================================================================ grading
def _grade_loc(p, truth_h):
    if p is None:
        return "ABSENT"
    if truth_h == GT.UNSPECIFIED:
        return "UNGRADED"
    surv = set(p["supported"]) | set(p["unresolved"])
    if truth_h is None:
        if p["verdict"] == "UNSUPPORTED" and not surv:
            return "CORRECT_CERTAIN"
        return "WRONG" if p["verdict"] == "SUPPORTED" else "CORRECT_UNCERTAIN"
    if truth_h in p["rejected"]:
        return "WRONG"
    if p["verdict"] == "SUPPORTED":
        return "CORRECT_CERTAIN" if p["supported"] == [truth_h] else "WRONG"
    if truth_h in surv:
        return "CORRECT_UNCERTAIN"
    return "UNGRADED"


def _grade_attr(a, truth_dom):
    if truth_dom is None or truth_dom == GT.UNSPECIFIED:
        return "UNGRADED"
    if a["verdict"] == UNIQUE:
        return ("CORRECT_CERTAIN" if a["candidates"][0].split("/", 1)[0] == truth_dom
                else "WRONG")
    if a["verdict"] == "AMBIGUOUS":
        doms = {c.split("/", 1)[0] for c in a["candidates"]}
        return "CORRECT_UNCERTAIN" if truth_dom in doms else "UNGRADED"
    return "UNGRADED"


def classify(scenario, d, gaps_new, rec21):
    """One difference -> (category, grade_old, grade_new, basis).

    `rec21` carries, besides the shadow record, `truth_domain` (this tick's
    attribution truth, `GT.attribution_domain`) and `scope` (each navigation
    function's declared C3 scope under the profile in use)."""
    if d["stage"] == "ATTRIBUTION":
        dom = rec21.get("truth_domain", GT.truth(scenario)["domain"])
        go, gn = _grade_attr(d["old"], dom), _grade_attr(d["new"], dom)
        if gn == "WRONG" and go != "WRONG":
            return "POSSIBLE_REGRESSION", go, gn, "new attribution names a wrong domain uniquely"
        if go == "WRONG":
            return "CORRECTNESS_FIX", go, gn, "the withheld UNIQUE named the wrong domain"
        if go == "CORRECT_CERTAIN" and gn in ("CORRECT_UNCERTAIN", "UNGRADED"):
            gapped = [x for x in d.get("localization_disagreement", [])
                      if gaps_new.get(f"{x['symptom']}|{d['old']['candidates'][0].split('/', 1)[1]}")]
            if gapped:
                return ("PROFILE_GAP", go, gn,
                        "UNIQUE withheld because a localization with a scope gap keeps "
                        + ",".join(sorted({h for x in gapped for h in x['retains']})))
            return ("CONSERVATIVE_WITHHOLD", go, gn,
                    "UNIQUE withheld; the same tick's localization keeps "
                    + ",".join(sorted({h for x in d.get('localization_disagreement', [])
                                       for h in x['retains']})))
        return "UNKNOWN", go, gn, "no ground truth for the attribution"
    sym, subject = d["unit"].split("|", 1)
    th = GT.true_hypothesis(scenario, sym)
    should = GT.symptom_should_exist(scenario, sym, subject)
    go, gn = _grade_loc(d["old"], th), _grade_loc(d["new"], th)
    gap = bool(gaps_new.get(d["unit"])) or any(r.startswith("SCOPE_GAP") for r in d["reasons"])
    if d["new"] is None:
        if should is False:
            return "CORRECTNESS_FIX", go, "ABSENT", "false symptom on an unaffected function removed"
        if should is True:
            undeclared = not rec21.get("declared_serving", {}).get(subject, True)
            if undeclared:
                return ("PROFILE_GAP", go, "ABSENT",
                        "real symptom not raised: nothing is declared to serve the subject")
            if not cause_in_scope(scenario, subject, rec21):
                return ("PROFILE_GAP", go, "ABSENT",
                        "real symptom not raised: the subject has declared serving "
                        "components, but the injected cause is outside its declared scope "
                        "(partial declaration)")
            return ("POSSIBLE_REGRESSION", go, "ABSENT",
                    "real symptom not raised although the injected cause is inside "
                    "the subject's declared scope")
        return "UNKNOWN", go, "ABSENT", "presence not graded for this subject"
    if d["old"] is None:
        if should is True:
            return "CORRECTNESS_FIX", "ABSENT", gn, "real symptom now raised"
        if should is False:
            return "POSSIBLE_REGRESSION", "ABSENT", gn, "symptom raised on an unaffected function"
        return "UNKNOWN", "ABSENT", gn, "presence not graded"
    if gn == "WRONG" and go != "WRONG":
        return "POSSIBLE_REGRESSION", go, gn, "the true hypothesis is rejected or another is SUPPORTED"
    if go == "WRONG" and gn != "WRONG":
        return "CORRECTNESS_FIX", go, gn, "a wrong localization is no longer wrong"
    if go == "WRONG" and gn == "WRONG":
        return "UNKNOWN", go, gn, "wrong under both"
    if "UNGRADED" in (go, gn):
        return "UNKNOWN", go, gn, "no ground truth for this symptom"
    so = set(d["old"]["supported"]) | set(d["old"]["unresolved"])
    sn = set(d["new"]["supported"]) | set(d["new"]["unresolved"])
    if go == "CORRECT_UNCERTAIN" and gn == "CORRECT_CERTAIN":
        return "CORRECTNESS_FIX", go, gn, "the true hypothesis is now the only confirmed survivor"
    if len(sn) > len(so) or (go == "CORRECT_CERTAIN" and gn == "CORRECT_UNCERTAIN"):
        return (("PROFILE_GAP", go, gn, "wider because a scoped predicate had nothing declared to read")
                if gap else
                ("CONSERVATIVE_WITHHOLD", go, gn, "wider; the evidence does not exclude the added survivors"))
    if len(sn) < len(so):
        return "CORRECTNESS_FIX", go, gn, "narrower, still containing the true hypothesis"
    return "SEMANTIC_CLARIFICATION", go, gn, "same survivors, different verdict wording"


def cause_in_scope(scenario, subject, rec21):
    """Is the injected cause inside the subject's declared C3 scope? With no
    single injected component, any adverse record of the injected domain
    inside the scope counts."""
    scope = set(rec21.get("scope", {}).get(subject, ()))
    t = GT.truth(scenario)
    comp = t.get("component")
    if comp not in (None, GT.UNSPECIFIED):
        return comp in scope
    return any(c in scope for c in rec21.get("adverse_in_truth_domain", ()))


# ================================================================ dataset A
def runs_A():
    out = {}
    for name in sorted(SCENARIOS):
        engine, res = P.run_scenario(SCENARIOS[name])
        out[name] = (engine, res)
    return out


def declared_serving(records, funcs=NAV_FUNCS):
    ix = SuccessorIndex(records, tracing=False)
    return {f: bool(declared_scope(ix, f) - {f}) for f in funcs}


def scopes(records, funcs=NAV_FUNCS):
    ix = SuccessorIndex(records, tracing=False)
    return {f: sorted(declared_scope(ix, f) - {f}) for f in funcs}


def _verdicts(loc_map):
    return {k: v["verdict"] for k, v in loc_map.items()}


def shadow_A(runs, ov=None, keep_rows=True, time_v2=False):
    rows, log, per_cat = [], [], {}
    wrong_unique, stats = [], {"ticks": 0, "ticks_differing": 0,
                               "ticks_label_change_only": 0, "ticks_trace_only": 0,
                               "units": 0, "shadow_faults": 0}
    for name, (engine, res) in runs.items():
        runner = ShadowRunner(engine, overlay=ov, trace=True, time_v2=time_v2)
        t = GT.truth(name)
        for tick, sa in enumerate(res):
            rec = runner.observe(sa)
            stats["ticks"] += 1
            if "shadow_fault" in rec:
                stats["shadow_faults"] += 1
                continue
            recs21 = ov.apply(sa.records) if ov else sa.records
            rec["declared_serving"] = declared_serving(recs21)
            rec["scope"] = scopes(recs21)
            rec["truth_domain"] = GT.attribution_domain(name, sa.records)
            rec["adverse_in_truth_domain"] = sorted(
                {r.component for r in sa.records
                 if r.domain == t["domain"] and r.is_adverse})
            a21 = rec["v2_1"]["attribution"]
            dom = rec["truth_domain"]
            if a21["verdict"] == UNIQUE and dom not in (None, GT.UNSPECIFIED) \
                    and a21["candidates"][0].split("/", 1)[0] != dom:
                a20 = rec["v2_0"]["attribution"]
                wrong_unique.append({
                    "scenario": name, "tick": tick, "candidate": a21["candidates"][0],
                    "v2_0_same": a20 == {k: a21[k] for k in ("verdict", "candidates")},
                    "label": GT.onset_label(name, sa.records, a21["candidates"][0])})
            cats = []
            for d in rec["differences"]:
                cat, go, gn, basis = classify(name, d, rec["profile_gap_effects"], rec)
                cats.append(cat)
                per_cat[cat] = per_cat.get(cat, 0) + 1
                stats["units"] += 1
                if keep_rows:
                    rows.append({"scenario": name, "tick": tick, "unit": d["unit"],
                                 "stage": d["stage"],
                                 "v2_0": json.dumps(d["old"], sort_keys=True),
                                 "v2_1": json.dumps(d["new"], sort_keys=True),
                                 "verdict_change": "->".join(map(str, d["verdict_change"])),
                                 "candidates_added": "|".join(d["candidates_added"]),
                                 "candidates_removed": "|".join(d["candidates_removed"]),
                                 "reasons": "|".join(d["reasons"])[:400],
                                 "grade_v2_0": go, "grade_v2_1": gn,
                                 "category": cat, "basis": basis})
            if rec["differences"]:
                stats["ticks_differing"] += 1
            elif rec["label_changes"]:
                stats["ticks_label_change_only"] += 1
            elif rec["unknown_evidence_effects"] or rec["profile_gap_effects"]:
                stats["ticks_trace_only"] += 1
            if keep_rows:
                log.append({"scenario": name, "tick": tick,
                            "input_hash": rec["input_hash"], "identical": rec["identical"],
                            "differences": len(rec["differences"]),
                            "categories": sorted(set(cats)),
                            "predicate_faults": len(rec["predicate_faults"]),
                            "unknown_evidence_effects": len(rec["unknown_evidence_effects"]),
                            "profile_gap_units": sorted(rec["profile_gap_effects"]),
                            "label_changes": len(rec["label_changes"]),
                            "v2_0": {"attribution": rec["v2_0"]["attribution"],
                                     "localization": _verdicts(rec["v2_0"]["localization"])},
                            "v2_1": {"attribution": {k: rec["v2_1"]["attribution"][k]
                                                     for k in ("verdict", "candidates")},
                                     "localization": _verdicts(rec["v2_1"]["localization"])},
                            "runtime_ns": rec["runtime_ns"],
                            "overlay": rec["overlay"]})
    return {"stats": stats, "categories": dict(sorted(per_cat.items())),
            "wrong_unique_under_2_1": wrong_unique}, rows, log


# ======================================================= Phase C headline
def _phase_c_runner():
    path = REPO / "engineering/v2/run_phase_c.py"
    spec = importlib.util.spec_from_file_location("frozen_run_phase_c", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gate_under(runs, ov):
    import semantic_core_2_1_differential as D
    RP = _phase_c_runner()
    rows = []
    for set_name, members in MATCHED_SETS.items():
        want = SET_SYMPTOM[set_name]
        for name in members:
            engine, res = runs[name]
            final = res[-1]
            recs = ov.apply(final.records) if ov else final.records
            blind = "|".join(SIG.uncovered_common_cause_domains(EvidenceIndex(final.records)))
            tr = SemanticCore21.from_engine(engine, trace=False).reason(recs)
            locs = [x.v2 for x in tr.localizations if x.symptom == want]
            if not locs:
                rows.append(D._missing(set_name, name, want, ""))
            for loc in locs:
                rows.append(D._row(set_name, name, want, loc, blind, ""))
    g = RP.decision_gate(rows)
    return {"verdict": g["verdict"],
            "qualifying": {q["set"]: q["answers"] for q in g["qualifying_sets"]},
            "non_qualifying": {q["set"]: q.get("why") for q in g["non_qualifying_sets"]}}


# ================================================== counterfactual profiles
def compare(base_rows, rows):
    """Per unit (scenario, tick, unit) keyed comparison of two shadow runs."""
    key = lambda r: (r["scenario"], r["tick"], r["unit"])  # noqa: E731
    b = {key(r): r for r in base_rows}
    n = {key(r): r for r in rows}
    out = {"restored_to_v2_0": 0, "newly_different_from_v2_0": 0,
           "category_moves": {}}
    for k in set(b) | set(n):
        if k in b and k not in n:
            out["restored_to_v2_0"] += 1
            c = b[k]["category"]
            out["category_moves"][c + "->RESTORED"] = out["category_moves"].get(c + "->RESTORED", 0) + 1
        elif k in n and k not in b:
            out["newly_different_from_v2_0"] += 1
            c = n[k]["category"]
            out["category_moves"]["NEW->" + c] = out["category_moves"].get("NEW->" + c, 0) + 1
        elif b[k]["category"] != n[k]["category"] or b[k]["v2_1"] != n[k]["v2_1"]:
            c = b[k]["category"] + "->" + n[k]["category"]
            out["category_moves"][c] = out["category_moves"].get(c, 0) + 1
    out["category_moves"] = dict(sorted(out["category_moves"].items()))
    return out


def candidate_set_changes(runs, ov):
    """Against 2.1 without the overlay: localizations whose survivor set
    shrinks or expands, and new UNIQUE verdicts, all ticks."""
    shrink = expand = new_unique = 0
    for name, (engine, res) in runs.items():
        core = SemanticCore21.from_engine(engine, trace=False)
        for sa in res:
            a = core.reason(sa.records)
            b = core.reason(ov.apply(sa.records))
            la = {x.key: set(x.supported) | set(x.unresolved) for x in a.localizations}
            lb = {x.key: set(x.supported) | set(x.unresolved) for x in b.localizations}
            for k in set(la) & set(lb):
                shrink += int(lb[k] < la[k])
                expand += int(lb[k] > la[k])
            new_unique += int(b.attribution.verdict == UNIQUE and a.attribution.verdict != UNIQUE)
    return {"survivor_sets_shrink": shrink, "survivor_sets_expand": expand,
            "new_unique_vs_2_1_base": new_unique}


def p16_under(runs, ov):
    """POSITION_UNAVAILABLE on a function the frozen function graph, fed the
    SAME (overlaid) records, calls ELIGIBLE."""
    contra = total = 0
    for name, (engine, res) in runs.items():
        core = SemanticCore21.from_engine(engine, trace=False)
        for sa in res:
            recs = ov.apply(sa.records) if ov else sa.records
            states = engine.functions.evaluate(recs)
            for x in core.reason(recs).localizations:
                if x.symptom == "POSITION_UNAVAILABLE":
                    total += 1
                    contra += int(states.get(x.subject) is not None
                                  and states[x.subject].state == "ELIGIBLE")
    return {"position_unavailable_localizations": total,
            "on_a_function_the_graph_calls_ELIGIBLE": contra}


def wrong_unique_summary(entries):
    out: dict = {}
    for e in entries:
        k = f'{e["scenario"]}|{e["candidate"]}|{e["label"]}|v2_0_same={e["v2_0_same"]}'
        out.setdefault(k, []).append(e["tick"])
    return {k: [min(v), max(v), len(v)] for k, v in sorted(out.items())}


def main():
    runs = runs_A()
    results = {"harness": "semantic_core_2_1_shadow_validation",
               "candidates_sha256": hashlib.sha256(
                   (HERE / "profile_candidates.json").read_bytes()).hexdigest()}
    base, rows, log = shadow_A(runs, time_v2=True)
    results["A_base_profile"] = base
    results["A_base_wrong_unique_summary"] = wrong_unique_summary(
        base["wrong_unique_under_2_1"])
    results["A_base_p16"] = p16_under(runs, None)
    import semantic_core_2_1_differential as D
    F = D.section_F()
    results["B_xsys"] = {k: F[k] for k in (
        "slots", "decision_differences_2_1_vs_sealed",
        "outcome_differences_2_1_vs_recorded_results",
        "full_v2_0_view_differences_2_1_vs_sealed", "XSYS_HARD_GATE",
        "primary_recomputed_under_2_1")}
    results["phase_c_gate_base"] = gate_under(runs, None)
    configs = {"ALL_ACCEPT_CANDIDATES": ("R1", "R2", "R3", "R4", "R5"),
               "G1_ONLY": ("R1", "R2", "R3"), "G2_ONLY": ("R5",),
               "G3_ONLY": ("R4",), "R1": ("R1",), "R2": ("R2",), "R3": ("R3",),
               "R2_R3_R5": ("R2", "R3", "R5"),
               "R1_R2_R3_R5": ("R1", "R2", "R3", "R5"),
               "PLUS_R6": ("R1", "R2", "R3", "R4", "R5", "R6"),
               "WITH_R_BAD": ("R1", "R2", "R3", "R4", "R5", "R-BAD")}
    succ = load_successor("aircraft_successor_r1")
    configs["SUCCESSOR_R1"] = succ
    configs["SUCCESSOR_R1_PLUS_R5"] = ProfileOverlay(
        succ.name, "r1+R5", succ.base_profile,
        succ.declarations + overlay("R5").declarations)
    cf = {}
    for label, ids in configs.items():
        ov = ids if isinstance(ids, ProfileOverlay) else overlay(*ids, version=label)
        summ, orows, _ = shadow_A(runs, ov)
        cf[label] = {"declarations": ([f"{d.domain}/{d.component}" for d in ov.declarations]
                                      if isinstance(ids, ProfileOverlay) else list(ids)),
                     "overlay_sha256": ov.digest(),
                     "vs_v2_0": summ,
                     "wrong_unique_summary": wrong_unique_summary(
                         summ["wrong_unique_under_2_1"]),
                     "vs_2_1_base": compare(rows, orows),
                     "candidate_sets": candidate_set_changes(runs, ov),
                     "p16": p16_under(runs, ov),
                     "phase_c_gate": gate_under(runs, ov)}
    results["counterfactual_profiles"] = cf
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True, default=str) + "\n")
    with open(DIFFS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(LOG, "w", encoding="utf-8") as fh:
        for r in log:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(json.dumps({"A": base["stats"], "categories": base["categories"],
                      "wrong_unique": wrong_unique_summary(base["wrong_unique_under_2_1"]),
                      "cf": {k: {"cats": v["vs_v2_0"]["categories"],
                                 "wrong_unique": len(v["vs_v2_0"]["wrong_unique_under_2_1"]),
                                 "restored": v["vs_2_1_base"]["restored_to_v2_0"],
                                 "new": v["vs_2_1_base"]["newly_different_from_v2_0"],
                                 "sets": v["candidate_sets"], "p16": v["p16"],
                                 "gate": v["phase_c_gate"]["verdict"]}
                             for k, v in cf.items()}}, indent=1, default=str))


if __name__ == "__main__":
    main()
