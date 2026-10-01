#!/usr/bin/env python3
"""Predicate-fault replay (Phase 0 B1 and Phase 3). RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/fault_replay.py

The shadow study's dataset D, re-run: on every tick of dataset A, every base
predicate of the tick's table raises in turn (`X` and `X_FALSE` together).
The injection, the roles and the grading are the shadow study's own,
imported from `predicate_fault_study.py` and not re-implemented. What is
new is the configuration under test:

    PRE       2.1.0 as committed, with the shadow study's reference policies
              A, B, C, D applied after the fact (`apply_policy`). This must
              reproduce the shadow result exactly (B1: 168 under A).
    R1_ONLY   2.1.1 with only FAULT_POLICY_B on, base profile. Its verdicts
              are the core's own, not a post-hoc policy. The same 68,640
              injections, so it is compared one for one with PRE.
    REVISED   2.1.1 with all three revisions on and successor profile r2.
              Its table has one more base predicate (PACING_INPUTS_NOMINAL),
              so its injection count is larger; the 26 shared bases are
              reported separately for a like-for-like comparison.

Writes FAULT_REPLAY_RESULTS.json and FAULT_REPLAY_RESULTS.csv.
"""
from __future__ import annotations

import csv
import sys
import time

import revision_common as RC

import ground_truth as GT  # noqa: E402
import predicate_fault_study as F  # noqa: E402
import semantic_probe as P  # noqa: E402

from csia.v2.localization import SUPPORTED  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402

OUT_JSON = RC.HERE / "FAULT_REPLAY_RESULTS.json"
OUT_CSV = RC.HERE / "FAULT_REPLAY_RESULTS.csv"
REF_POLICIES = ("A", "B", "C", "D")


def implemented_verdicts(tr):
    """The revised core's own decision, in the study's vocabulary: a
    localization the core withheld is WITHHELD; everything else is its 2.0
    view verdict. Attribution is the core's own."""
    from csia_semantic_core.localization import WITHHELD_PREDICATE_FAULT
    locs = {x.key: (F.WITHHELD if x.outcome == WITHHELD_PREDICATE_FAULT
                    else x.v2.verdict) for x in tr.localizations}
    return locs, tr.attribution.verdict


def _blank():
    b = F._blank()
    b.update(trace_material_withheld=0, trace_fault_impact_entries=0,
             withheld_without_material_refuter=0)
    return b


def replay(make_core, policies, records_of=None, bases_filter=None,
           label=""):
    """`make_core(engine)` -> a SemanticCore21. `policies` maps a policy
    name to a function (tr) -> (loc verdicts, attribution verdict).
    `records_of(sa)` -> the records reasoned over (default: the tick's)."""
    t0 = time.perf_counter()
    roles_all = F.ROLES + ("ALL",)
    agg = {(r, p): _blank() for r in roles_all for p in policies}
    lost_ticks = {p: 0 for p in policies}
    created: dict = {p: [] for p in policies}
    injections = 0
    bases_seen = set()
    for name in sorted(SCENARIOS):
        engine, res = P.run_scenario(SCENARIOS[name])
        core = make_core(engine)
        for s in core.symptoms:
            F._SPEC_BY_SYMPTOM[s.symptom_id] = {h.hypothesis_id: h
                                                for h in s.hypotheses}
        specs = {s.symptom_id: s for s in core.symptoms}
        bases = [b for b in F.base_ids(core.predicates)
                 if bases_filter is None or bases_filter(b)]
        bases_seen.update(bases)
        faulted = {b: F.faulted_core(core, b) for b in bases}
        for tick, sa in enumerate(res):
            recs = records_of(sa) if records_of else sa.records
            clean = core.reason(recs)
            truth_dom = GT.attribution_domain(name, sa.records)
            clean_loc = {x.key: x for x in clean.localizations}
            clean_v, clean_a = policies[next(iter(policies))](clean)
            clean_grade = {k: F.grade_loc(name, x, clean_v[k])
                           for k, x in clean_loc.items()}
            clean_attr = F.grade_attr(truth_dom, clean, clean_a)
            for b in bases:
                ids = F.ids_of(b, core.predicates)
                tr = faulted[b].reason(recs)
                injections += 1
                inj = {x.key: x for x in tr.localizations}
                assert set(inj) == set(clean_loc), "a fault changed detection"
                proles = {k: F.roles_for(name, clean_loc[k],
                                         specs[clean_loc[k].symptom], ids)
                          for k in clean_loc}
                troles = (set().union(*proles.values()) if proles
                          else {"IRRELEVANT"})
                for pol, fn in policies.items():
                    locv, av = fn(tr)
                    lost = False
                    for k, x in inj.items():
                        g = F.grade_loc(name, x, locv[k])
                        oc = F.outcome_class(x, locv[k])
                        failed = {i for e in x.predicate_errors
                                  for i in e.evaluated_as}
                        was = clean_v[k]
                        is_created = locv[k] == SUPPORTED and (
                            was != SUPPORTED
                            or tuple(x.supported) != tuple(clean_loc[k].supported))
                        resting = locv[k] == SUPPORTED and bool(
                            failed & set(F.spec_h(x)[x.supported[0]].refuted_by))
                        impact = getattr(x, "fault_impact", ())
                        mat_w = any(e.get("action") == "SUPPORTED_WITHHELD"
                                    for e in impact)
                        withheld_wo = (locv[k] == F.WITHHELD and not (
                            x.supported and failed & set(
                                F.spec_h(x)[x.supported[0]].refuted_by)))
                        for role in proles[k] | {"ALL"}:
                            a = agg[(role, pol)]
                            a["pairs"] += 1
                            a[oc] = a.get(oc, 0) + 1
                            a["fault_evaluated"] += int(bool(x.predicate_errors))
                            a["fault_visible"] += int(bool(x.predicate_errors)
                                                      and (pol != "D" or locv[k] == F.INVALID))
                            a["fault_created_supported"] += int(is_created)
                            a["supported_resting_on_failed_refuter"] += int(resting)
                            a["trace_material_withheld"] += int(mat_w)
                            a["trace_fault_impact_entries"] += len(impact)
                            a["withheld_without_material_refuter"] += int(withheld_wo)
                            if g != "UNGRADED":
                                a["graded"] += 1
                                a["wrong"] += int(g == "WRONG")
                                a["new_wrong"] += int(g == "WRONG" and clean_grade[k] != "WRONG")
                                if clean_grade[k] == "CORRECT_CERTAIN":
                                    a["correct_supported_clean"] += 1
                                    kept = g == "CORRECT_CERTAIN"
                                    a["correct_supported_retained"] += int(kept)
                                    a["correct_supported_lost"] += int(not kept)
                                    lost |= not kept
                        if is_created:
                            created[pol].append({
                                "scenario": name, "tick": tick, "failed": b,
                                "unit": k, "grade": g,
                                "faulted_supported": list(x.supported)})
                    ag = F.grade_attr(truth_dom, tr, av)
                    for role in troles | {"ALL"}:
                        a = agg[(role, pol)]
                        a["injections"] += 1
                        a["attr_wrong_unique"] += int(ag == "WRONG_UNIQUE")
                        a["attr_new_wrong_unique"] += int(
                            ag == "WRONG_UNIQUE" and clean_attr != "WRONG_UNIQUE")
                        if clean_attr == "CORRECT_UNIQUE":
                            a["attr_correct_unique_clean"] += 1
                            a["attr_correct_unique_retained"] += int(ag == "CORRECT_UNIQUE")
                            a["attr_correct_unique_lost"] += int(ag != "CORRECT_UNIQUE")
                            lost |= ag != "CORRECT_UNIQUE"
                    lost_ticks[pol] += int(lost)
    return {"label": label, "injections": injections,
            "bases": sorted(bases_seen),
            "per_policy": {p: dict(agg[("ALL", p)],
                                   ticks_with_any_conclusion_lost=lost_ticks[p])
                           for p in policies},
            "per_role": {f"{r}|{p}": agg[(r, p)] for r in roles_all
                         for p in policies},
            "fault_created_supported": {p: {"count": len(v), "examples": v[:6]}
                                        for p, v in created.items()},
            "seconds": round(time.perf_counter() - t0, 1)}


def pre_policies():
    return {p: (lambda tr, p=p: F.apply_policy(p, tr)) for p in REF_POLICIES}


def run_pre():
    return replay(lambda e: SemanticCore21.from_engine(e, trace=False),
                  pre_policies(), label="PRE: 2.1.0, reference policies")


HEADLINE = ("pairs", "graded", "wrong", "new_wrong", "fault_created_supported",
            "supported_resting_on_failed_refuter", "fault_evaluated",
            "fault_visible", "correct_supported_clean",
            "correct_supported_lost", "attr_new_wrong_unique",
            "attr_correct_unique_clean", "attr_correct_unique_lost",
            "ticks_with_any_conclusion_lost", "WITHHELD", "INVALID",
            "trace_material_withheld", "withheld_without_material_refuter")


def main():
    from csia_semantic_core.profile_overlay import load_successor
    out = {"harness": "semantic_core_2_1_revision_fault_replay",
           "dataset": "D: every base predicate failed in turn on every tick of dataset A"}
    out["PRE"] = run_pre()
    r1 = Corrections(fault_policy_b=True)
    out["R1_ONLY"] = replay(
        lambda e: SemanticCore21.from_engine(e, r1, trace=True),
        {"B_IMPLEMENTED": implemented_verdicts},
        label="2.1.1 FAULT_POLICY_B only, base profile")
    succ = load_successor("aircraft_successor_r2")
    rev = Corrections.revised()

    def make_rev(e):
        return SemanticCore21.from_engine(e, rev, trace=True,
                                          pacing=succ.pacing_map())
    out["REVISED_SHARED_BASES"] = replay(
        make_rev, {"B_IMPLEMENTED": implemented_verdicts},
        records_of=lambda sa: succ.apply(sa.records),
        bases_filter=lambda b: b != "PACING_INPUTS_NOMINAL",
        label="2.1.1 all revisions, successor r2, the 26 shared bases")
    out["REVISED_PACING_BASE"] = replay(
        make_rev, {"B_IMPLEMENTED": implemented_verdicts},
        records_of=lambda sa: succ.apply(sa.records),
        bases_filter=lambda b: b == "PACING_INPUTS_NOMINAL",
        label="2.1.1 all revisions, successor r2, PACING_INPUTS_NOMINAL only")
    RC.write_json(OUT_JSON, out)
    rows = []
    for cfg in ("PRE", "R1_ONLY", "REVISED_SHARED_BASES", "REVISED_PACING_BASE"):
        for pol, a in out[cfg]["per_policy"].items():
            rows.append({"configuration": cfg, "policy": pol,
                         "injections": out[cfg]["injections"],
                         **{k: a.get(k, 0) for k in HEADLINE}})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    sys.exit(main())
