#!/usr/bin/env python3
"""Dataset A three ways (Phases 4, 5, 6, 13 and part of 12). RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/dataset_a_three_way.py

The 44 shipped scenarios x 60 ticks (2,640 ticks), under:

    V2_0       frozen v2.0, the authoritative output
    PRE_BASE   2.1.0, frozen profile
    PRE_R1     2.1.0 + successor r1 (the configuration the shadow study accepted)
    REV_BASE   2.1.1, frozen profile (no pacing declarations)
    REV_R2     2.1.1 + successor r2 (the promotion candidate)

Ground truth, grading and the v2.0 difference classifier are the shadow
study's own (`ground_truth.py`, `shadow_validation.py`), imported.

Phase 4. Every unit (symptom|subject localization, or the tick's
attribution) where REV_R2 differs from PRE_R1, and where REV_BASE differs
from PRE_BASE, is classified:

  - the cause is found by ablation: REV with one revision switched off; a
    difference that disappears when R-k is off is caused by R-k;
  - the grade is the shadow study's, old and new;
  - POSSIBLE_REGRESSION if the new answer is graded WRONG and the old one is
    not; UNKNOWN if a unit cannot be graded; otherwise EXPECTED_R1 / R2 / R3
    (cause), with the effect named: CORRECTNESS_FIX (wrong to not wrong),
    CERTAINTY_RESTORED (correct uncertain to correct certain),
    CONSERVATIVE_WITHHOLD (correct certain to correct uncertain); a
    difference no single revision explains is PROFILE_EFFECT if it needs the
    profile, else UNKNOWN.
  The REV_R2-vs-V2_0 differences are also classified with the shadow
  study's own classifier, for continuity with its 1,275-unit table.

Phase 5. The seven weakened-UNIQUE scenarios and TS_STALLED (the shadow
study's list, `unique_review.WEAKENED`): UNIQUE per tick under every
configuration, and why it is withheld.

Phase 6. MS_B5 and MS_TS_B5: wrong UNIQUE ticks under 2.1.1 with every
profile variant (none, r1, r2, r2 plus each shadow candidate, every
candidate together, R-BAD).

Phase 13. Decision-quality counts per configuration.

Writes DATASET_A_THREE_WAY.json and REVISION_DIFFERENCES.csv.
"""
from __future__ import annotations

import csv
import functools
import json
import sys
import time

import revision_common as RC

import ground_truth as GT  # noqa: E402
import shadow_validation as S  # noqa: E402
import unique_review as U  # noqa: E402

from csia.v2.attribution import UNIQUE  # noqa: E402
from csia.v2.localization import AMBIGUOUS, SUPPORTED  # noqa: E402
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import (ProfileOverlay,  # noqa: E402
                                                load_successor)
from csia_semantic_core.shadow import ShadowRunner  # noqa: E402

OUT = RC.HERE / "DATASET_A_THREE_WAY.json"
CSV_OUT = RC.HERE / "REVISION_DIFFERENCES.csv"
REVISED = Corrections.revised()
ABLATIONS = {"R1": "fault_policy_b", "R2": "pacing_inputs", "R3": "config_epoch"}


def without(flag):
    from dataclasses import replace
    return replace(REVISED, **{flag: False})


def lp(x, frozen=False):
    v = x if frozen else x.v2
    return {"verdict": v.verdict, "supported": list(v.supported),
            "unresolved": list(v.unresolved),
            "rejected": sorted(h for h, _ in v.rejected),
            "outcome": None if frozen else x.outcome}


def ap(a, frozen=False):
    if frozen:
        return {"verdict": a.verdict, "candidates": [c.id for c in a.candidates],
                "withheld": []}
    return {"verdict": a.verdict, "candidates": list(a.candidates),
            "withheld": list(a.withheld_unique_because)}


def tick_view(tr=None, sa=None):
    if sa is not None:
        return ({f"{x.symptom}|{x.subject}": lp(x, True) for x in sa.localizations},
                ap(sa.attribution, True))
    return ({x.key: lp(x) for x in tr.localizations}, ap(tr.attribution))


RANK = {"WRONG": 0, "ABSENT": 1, "UNGRADED": 1, "CORRECT_UNCERTAIN": 2, "CORRECT_CERTAIN": 3}


def grade_unit(name, unit, p, truth_dom):
    if unit == "ATTRIBUTION":
        return S._grade_attr(p, truth_dom)
    sym, subject = unit.split("|", 1)
    if p is None:
        should = GT.symptom_should_exist(name, sym, subject)
        return {True: "MISSED", False: "CORRECT_ABSENT"}.get(should, "UNGRADED")
    should = GT.symptom_should_exist(name, sym, subject)
    if should is False:
        return "FALSE_SYMPTOM"
    return S._grade_loc(p, GT.true_hypothesis(name, sym))


def classify_rev(name, unit, old, new, truth_dom, causes, profile_needed):
    go, gn = grade_unit(name, unit, old, truth_dom), grade_unit(name, unit, new, truth_dom)
    bad = ("WRONG", "MISSED", "FALSE_SYMPTOM")
    if gn in bad and go not in bad:
        return "POSSIBLE_REGRESSION", go, gn, "the new answer is graded wrong"
    if "UNGRADED" in (go, gn):
        return "UNKNOWN", go, gn, "no ground truth for this unit"
    if go in bad and gn not in bad:
        effect = "CORRECTNESS_FIX"
    elif RANK.get(gn, 1) > RANK.get(go, 1):
        effect = "CERTAINTY_RESTORED"
    elif RANK.get(gn, 1) < RANK.get(go, 1):
        effect = "CONSERVATIVE_WITHHOLD"
    elif go == gn:
        effect = "SAME_GRADE"
    else:
        effect = "OTHER"
    if len(causes) == 1:
        return f"EXPECTED_{causes[0]}", go, gn, effect
    if profile_needed:
        return "PROFILE_EFFECT", go, gn, effect
    return "UNKNOWN", go, gn, "no single revision explains it: " + ",".join(causes)


def _q():
    return {"ticks": 0, "unique": 0, "correct_unique": 0, "wrong_unique": 0,
            "attr_ambiguous": 0, "correct_attr_ambiguous": 0, "false_attr_ambiguous": 0,
            "supported": 0, "correct_supported": 0, "wrong_supported": 0,
            "ambiguous_loc": 0, "correct_ambiguous_loc": 0, "false_ambiguous_loc": 0,
            "withheld_predicate_fault": 0, "no_consistent": 0,
            "correct_no_consistent": 0, "insufficient": 0,
            "true_hypothesis_eliminated": 0, "false_symptoms": 0, "missed_symptoms": 0,
            "ungraded_units": 0, "predicate_fault_units": 0, "scope_gap_units": 0,
            "localizations": 0}


def quality(q, name, locs, attr, truth_dom, outcomes=None, gaps=None, faults=None):
    q["ticks"] += 1
    ga = S._grade_attr(attr, truth_dom)
    if attr["verdict"] == UNIQUE:
        q["unique"] += 1
        q["correct_unique"] += int(ga == "CORRECT_CERTAIN")
        q["wrong_unique"] += int(ga == "WRONG")
    elif attr["verdict"] == AMBIGUOUS:
        q["attr_ambiguous"] += 1
        q["correct_attr_ambiguous"] += int(ga == "CORRECT_UNCERTAIN")
        q["false_attr_ambiguous"] += int(ga == "UNGRADED" and truth_dom not in (None, GT.UNSPECIFIED))
    for k, p in locs.items():
        q["localizations"] += 1
        sym, subject = k.split("|", 1)
        should = GT.symptom_should_exist(name, sym, subject)
        if should is False:
            q["false_symptoms"] += 1
            continue
        th = GT.true_hypothesis(name, sym)
        g = S._grade_loc(p, th)
        if g == "UNGRADED":
            q["ungraded_units"] += 1
        oc = (outcomes or {}).get(k)
        if oc == "WITHHELD_PREDICATE_FAULT":
            q["withheld_predicate_fault"] += 1
        elif p["verdict"] == SUPPORTED:
            q["supported"] += 1
            q["correct_supported"] += int(g == "CORRECT_CERTAIN")
            q["wrong_supported"] += int(g == "WRONG")
        elif p["verdict"] == AMBIGUOUS:
            q["ambiguous_loc"] += 1
            q["correct_ambiguous_loc"] += int(g == "CORRECT_UNCERTAIN")
            q["false_ambiguous_loc"] += int(g == "WRONG")
        elif not p["supported"] and not p["unresolved"]:
            q["no_consistent"] += 1
            q["correct_no_consistent"] += int(g == "CORRECT_CERTAIN")
        else:
            q["insufficient"] += 1
        if th not in (None, GT.UNSPECIFIED) and th in p["rejected"]:
            q["true_hypothesis_eliminated"] += 1
        q["scope_gap_units"] += int(bool((gaps or {}).get(k)))
        q["predicate_fault_units"] += int(bool((faults or {}).get(k)))


def missed(q, name, locs, all_subjects):
    for sym, subject in all_subjects:
        if GT.symptom_should_exist(name, sym, subject) is True and f"{sym}|{subject}" not in locs:
            q["missed_symptoms"] += 1


def main():
    t0 = time.perf_counter()
    runs = S.runs_A()
    r1 = load_successor("aircraft_successor_r1")
    r2 = load_successor("aircraft_successor_r2")
    cfg = {"PRE_BASE": (Corrections(), None), "PRE_R1": (Corrections(), r1),
           "REV_BASE": (REVISED, None), "REV_R2": (REVISED, r2)}
    for k, flag in ABLATIONS.items():
        cfg[f"REV_R2_no{k}"] = (without(flag), r2)
        cfg[f"REV_BASE_no{k}"] = (without(flag), None)
    quality_rows = {c: _q() for c in ("V2_0", "PRE_BASE", "PRE_R1", "REV_BASE", "REV_R2")}
    diffs, cats, effects = [], {}, {}
    weak = {n: {c: {"unique_ticks": 0, "correct_unique_ticks": 0, "withheld": {}}
                for c in ("V2_0", "PRE_BASE", "PRE_R1", "REV_BASE", "REV_R2")}
            for n in U.WEAKENED}
    w_new = {"wrong_unique_vs_v2_0": [], "wrong_unique_vs_pre": [],
             "true_eliminated_vs_pre": [], "wrong_supported_vs_pre": [],
             "missed_vs_pre": [], "false_symptom_vs_pre": []}
    for name, (engine, res) in runs.items():
        cores = {c: SemanticCore21.from_engine(engine, corr, trace=True,
                                               pacing=(ov.pacing_map() if ov else None))
                 for c, (corr, ov) in cfg.items()}
        for tick, sa in enumerate(res):
            truth_dom = GT.attribution_domain(name, sa.records)
            views, trs = {"V2_0": tick_view(sa=sa)}, {}
            for c, (corr, ov) in cfg.items():
                tr = cores[c].reason(ov.apply(sa.records) if ov else sa.records)
                trs[c] = tr
                views[c] = tick_view(tr)
            for c in quality_rows:
                locs, attr = views[c]
                tr = trs.get(c)
                quality(quality_rows[c], name, locs, attr, truth_dom,
                        outcomes=None if tr is None else {x.key: x.outcome for x in tr.localizations},
                        gaps=None if tr is None else {x.key: x.trace.get("scope_gaps") for x in tr.localizations},
                        faults=None if tr is None else {x.key: x.predicate_errors for x in tr.localizations})
            all_subj = {tuple(k.split("|", 1)) for c in quality_rows for k in views[c][0]}
            for c in quality_rows:
                missed(quality_rows[c], name, views[c][0], all_subj)
            if name in weak:
                for c in weak[name]:
                    a = views[c][1]
                    w = weak[name][c]
                    if a["verdict"] == UNIQUE:
                        w["unique_ticks"] += 1
                        w["correct_unique_ticks"] += int(S._grade_attr(a, truth_dom) == "CORRECT_CERTAIN")
                    for why in a["withheld"]:
                        w["withheld"][why] = w["withheld"].get(why, 0) + 1
            for new_c, old_c, ab in (("REV_R2", "PRE_R1", "REV_R2_no"),
                                     ("REV_BASE", "PRE_BASE", "REV_BASE_no")):
                (nl, na), (ol, oa) = views[new_c], views[old_c]
                units = sorted(set(nl) | set(ol)) + ["ATTRIBUTION"]
                for u in units:
                    if u == "ATTRIBUTION":
                        old = {k: oa[k] for k in ("verdict", "candidates")}
                        new = {k: na[k] for k in ("verdict", "candidates")}
                    else:
                        old, new = ol.get(u), nl.get(u)
                    if old == new:
                        continue
                    causes = []
                    for k in ABLATIONS:
                        al, aa = views[ab + k]
                        got = ({kk: aa[kk] for kk in ("verdict", "candidates")}
                               if u == "ATTRIBUTION" else al.get(u))
                        if got == old:
                            causes.append(k)
                    cat, go, gn, effect = classify_rev(
                        name, u, old, new, truth_dom, causes, new_c == "REV_R2")
                    key = f"{new_c}_vs_{old_c}"
                    cats.setdefault(key, {})
                    cats[key][cat] = cats[key].get(cat, 0) + 1
                    effects.setdefault(key, {})
                    effects[key][f"{cat}:{effect}"] = effects[key].get(f"{cat}:{effect}", 0) + 1
                    diffs.append({"comparison": key, "scenario": name, "tick": tick,
                                  "unit": u, "old": json.dumps(old, sort_keys=True),
                                  "new": json.dumps(new, sort_keys=True),
                                  "causes": "|".join(causes), "grade_old": go,
                                  "grade_new": gn, "category": cat, "effect": effect})
                    if new_c == "REV_R2":
                        if u == "ATTRIBUTION" and gn == "WRONG" and go != "WRONG":
                            w_new["wrong_unique_vs_pre"].append((name, tick))
                        elif u != "ATTRIBUTION":
                            if gn == "WRONG" and go != "WRONG":
                                th = GT.true_hypothesis(name, u.split("|")[0])
                                (w_new["true_eliminated_vs_pre"] if new and th in new["rejected"]
                                 else w_new["wrong_supported_vs_pre"]).append((name, tick, u))
                            if gn == "MISSED" and go != "MISSED":
                                w_new["missed_vs_pre"].append((name, tick, u))
                            if gn == "FALSE_SYMPTOM" and go != "FALSE_SYMPTOM":
                                w_new["false_symptom_vs_pre"].append((name, tick, u))
            a20, a21 = views["V2_0"][1], views["REV_R2"][1]
            if (S._grade_attr(a21, truth_dom) == "WRONG"
                    and S._grade_attr(a20, truth_dom) != "WRONG"):
                w_new["wrong_unique_vs_v2_0"].append((name, tick))
    # REV_R2 against frozen v2.0, with the shadow study's own classifier.
    orig = S.ShadowRunner
    S.ShadowRunner = functools.partial(ShadowRunner, corrections=REVISED)
    try:
        vs_v20, _rows, _log = S.shadow_A(runs, r2, keep_rows=True)
        vs_v20_base, _r, _l = S.shadow_A(runs, None, keep_rows=False)
    finally:
        S.ShadowRunner = orig
    # Phase 6: the two wrong-cause UNIQUE scenarios under every variant.
    variants = {"none": None, "successor_r1": r1, "successor_r2": r2}
    for cid in ("R1", "R2", "R3", "R4", "R5", "R5a", "R5b", "R6", "R-BAD"):
        variants[f"r2+{cid}"] = ProfileOverlay(r2.name, f"r2+{cid}", r2.base_profile,
                                               r2.declarations + S.overlay(cid).declarations)
    variants["r2+all_candidates"] = ProfileOverlay(
        r2.name, "r2+all", r2.base_profile,
        r2.declarations + S.overlay("R1", "R2", "R3", "R4", "R5", "R5a", "R5b", "R6").declarations)
    wrong = {}
    for name in U.WRONG:
        engine, res = runs[name]
        wrong[name] = {}
        for vname, ov in variants.items():
            core = SemanticCore21.from_engine(engine, REVISED, trace=False,
                                              pacing=ov.pacing_map() if ov else None)
            n = 0
            for sa in res:
                a = core.reason(ov.apply(sa.records) if ov else sa.records).attribution
                n += int(a.verdict == UNIQUE and S._grade_attr(
                    {"verdict": a.verdict, "candidates": list(a.candidates)},
                    GT.attribution_domain(name, sa.records)) == "WRONG")
            wrong[name][vname] = n
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(diffs[0]) if diffs else ["comparison"])
        w.writeheader()
        w.writerows(diffs)
    out = {"harness": "semantic_core_2_1_revision_dataset_a_three_way",
           "ticks": sum(len(r) for _e, r in runs.values()),
           "successor_r1_digest": r1.digest(), "successor_r2_digest": r2.digest(),
           "phase4_revision_differences": {"categories": cats, "category_effects": effects,
                                           "units": len(diffs)},
           "phase4_rev_r2_vs_v2_0_shadow_classifier": {
               "stats": vs_v20["stats"], "categories": vs_v20["categories"],
               "wrong_unique": S.wrong_unique_summary(vs_v20["wrong_unique_under_2_1"])},
           "phase4_rev_base_vs_v2_0_shadow_classifier": {
               "stats": vs_v20_base["stats"], "categories": vs_v20_base["categories"],
               "wrong_unique": S.wrong_unique_summary(vs_v20_base["wrong_unique_under_2_1"])},
           "phase5_weakened": weak,
           "phase6_wrong_unique_ticks": wrong,
           "phase6_variant_digests": {k: (v.digest() if v else None) for k, v in variants.items()},
           "phase12_dataset_a": {k: {"count": len(v), "examples": v[:10]} for k, v in w_new.items()},
           "phase13_quality": quality_rows,
           "seconds": round(time.perf_counter() - t0, 1)}
    RC.write_json(OUT, out)
    print(json.dumps({k: out[k] for k in ("phase4_revision_differences", "phase6_wrong_unique_ticks",
                                          "phase12_dataset_a", "seconds")}, indent=1, default=str)[:6000])
    print(json.dumps(out["phase4_rev_r2_vs_v2_0_shadow_classifier"], indent=1, default=str))
    print(json.dumps(out["phase13_quality"], indent=1))


if __name__ == "__main__":
    sys.exit(main())
