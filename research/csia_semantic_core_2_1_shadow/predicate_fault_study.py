#!/usr/bin/env python3
"""Predicate-fault policy study (Parts 10-12, 48). RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/predicate_fault_study.py

DATASET D. Over every tick of dataset A (44 scenarios x 60 ticks), every
base predicate of the tick's table is made to fail in turn: its test raises,
so under C4 it evaluates to None and the fault is recorded. `X` and
`X_FALSE` fail together, as they would if the producer behind them broke.
2.1 is run once per injection. Five policies are then applied to that one
result, so they are compared on identical faulted ticks:

    A   report the fault, keep every verdict (current 2.1)
    B   dependency-sensitive: withhold a SUPPORTED localization only when a
        failed predicate is a REFUTER of the supported hypothesis, i.e. the
        failed predicate could have rejected it. Everything else stands,
        with the fault visible.
    C   downgrade every SUPPORTED localization that saw any fault, and the
        attribution UNIQUE whenever the tick saw any fault
    D   invalidate the whole tick whenever any predicate failed
    B+U B, and also withhold SUPPORTED when a refuter of the supported
        hypothesis was merely UNMEASURED (C2 None without a fault). Shown to
        price the obvious extension, not proposed.

Roles, per (injection, localization) pair, from the UNFAULTED result of the
same tick (a pair can hold several):

    CONFIRMING            confirms a hypothesis the unfaulted result supports
    REFUTING_SUPPORTED    refutes a hypothesis the unfaulted result supports
    REFUTING_REJECTED     is the predicate that rejected a hypothesis
    ALTERNATIVE_DOMAIN    read only by hypotheses outside the true domain
    MULTI_HYPOTHESIS      read by two or more hypotheses of the symptom
    IRRELEVANT            the symptom does not read it at all

Grading uses ground_truth.py only; units without a stated true hypothesis
are counted but not graded. Writes PREDICATE_FAULT_INJECTION_RESULTS.csv and
PREDICATE_FAULT_RESULTS.json. Reads frozen code; writes nothing else.
"""
from __future__ import annotations

import copy
import csv
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ground_truth as GT  # noqa: E402
import semantic_probe as P  # noqa: E402

from csia.v2.attribution import UNIQUE  # noqa: E402
from csia.v2.localization import AMBIGUOUS, SUPPORTED, UNSUPPORTED  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import SemanticCore21  # noqa: E402

CSV_OUT = HERE / "PREDICATE_FAULT_INJECTION_RESULTS.csv"
JSON_OUT = HERE / "PREDICATE_FAULT_RESULTS.json"
POLICIES = ("A", "B", "C", "D", "B+U")
ROLES = ("CONFIRMING", "REFUTING_SUPPORTED", "REFUTING_REJECTED",
         "ALTERNATIVE_DOMAIN", "MULTI_HYPOTHESIS", "IRRELEVANT")
WITHHELD = "WITHHELD"
INVALID = "INVALID"


class InjectedFault(RuntimeError):
    pass


def _raise(index, subject):
    raise InjectedFault("injected")


def base_ids(table):
    return sorted(p for p, v in table.items() if v.negation_of is None)


def faulted_core(core, base):
    """A copy of `core` whose `base` predicate (and its negation) raises."""
    table = dict(core.predicates)
    old = table[base]
    new = replace(old, test=_raise)
    table[base] = new
    for pid, v in table.items():
        if v.negation_of is old:
            table[pid] = replace(v, negation_of=new)
    c = copy.copy(core)
    c.predicates = table
    return c


def ids_of(base, table):
    return {base} | {p for p, v in table.items() if v.negation_of is not None
                     and v.negation_of.predicate_id == base}


# ------------------------------------------------------------------ policy
def apply_policy(policy, tr):
    """-> (per-localization verdict, attribution verdict). Localization
    verdicts are the 2.0.0 verdicts, or WITHHELD / INVALID."""
    any_fault = any(x.predicate_errors for x in tr.localizations)
    locs = {}
    for x in tr.localizations:
        v = x.v2.verdict
        failed = {i for e in x.predicate_errors for i in e.evaluated_as}
        if policy == "D" and any_fault:
            v = INVALID
        elif policy == "C" and failed and v == SUPPORTED:
            v = WITHHELD
        elif policy in ("B", "B+U") and v == SUPPORTED:
            hyp = spec_h(x)[x.supported[0]]
            if failed & set(hyp.refuted_by):
                v = WITHHELD
            elif policy == "B+U" and any(
                    x.v2.detail["predicate_values"].get(p) is None
                    for p in hyp.refuted_by):
                v = WITHHELD
        locs[x.key] = v
    a = tr.attribution.verdict
    if policy == "D" and any_fault:
        a = INVALID
    elif policy == "C" and any_fault and a == UNIQUE:
        a = WITHHELD
    return locs, a


_SPEC_BY_SYMPTOM: dict = {}


def spec_h(x):
    return _SPEC_BY_SYMPTOM[x.symptom]


# ----------------------------------------------------------------- grading
def grade_loc(scenario, x, verdict):
    th = GT.true_hypothesis(scenario, x.symptom)
    if th == GT.UNSPECIFIED:
        return "UNGRADED"
    surv = set(x.supported) | set(x.unresolved)
    rejected = {h for h, _ in x.v2.rejected}
    if verdict == INVALID:
        return "INVALID"
    if th is None:
        return "WRONG" if verdict == SUPPORTED else "CORRECT"
    if th in rejected:
        return "WRONG"
    if verdict == SUPPORTED:
        return "CORRECT_CERTAIN" if list(x.supported) == [th] else "WRONG"
    return "CORRECT" if th in surv or verdict == WITHHELD else "UNGRADED"


def grade_attr(truth_dom, tr, verdict):
    if truth_dom in (None, GT.UNSPECIFIED) or verdict != UNIQUE:
        return None
    c = tr.attribution.candidates[0]
    return "CORRECT_UNIQUE" if c.split("/", 1)[0] == truth_dom else "WRONG_UNIQUE"


def outcome_class(x, verdict):
    if verdict in (WITHHELD, INVALID):
        return verdict
    if verdict == SUPPORTED:
        return "SUPPORTED"
    if verdict == AMBIGUOUS:
        return "AMBIGUOUS"
    if verdict == UNSUPPORTED:
        return "INSUFFICIENT" if (x.supported or x.unresolved) else "NO_CONSISTENT"
    return verdict


def roles_for(scenario, x_clean, spec, ids):
    hyps = spec.hypotheses
    reads = [h for h in hyps if ids & (set(h.confirmed_by) | set(h.refuted_by))]
    if not reads:
        return {"IRRELEVANT"}
    out = set()
    sup = set(x_clean.supported)
    for h in hyps:
        if h.hypothesis_id in sup:
            if ids & set(h.confirmed_by):
                out.add("CONFIRMING")
            if ids & set(h.refuted_by):
                out.add("REFUTING_SUPPORTED")
    if any(by in ids for _h, by in x_clean.v2.rejected):
        out.add("REFUTING_REJECTED")
    th = GT.true_hypothesis(scenario, x_clean.symptom)
    if th not in (None, GT.UNSPECIFIED):
        tdom = th.split("/", 1)[0]
        if all(h.hypothesis_id.split("/", 1)[0] != tdom for h in reads) \
                and not out & {"CONFIRMING", "REFUTING_SUPPORTED"}:
            out.add("ALTERNATIVE_DOMAIN")
    if len(reads) >= 2:
        out.add("MULTI_HYPOTHESIS")
    return out


def _count_by(log):
    out: dict = {}
    for e in log:
        k = (f'{e["scenario"]}|{e["unit"]}|failed={e["failed"]}|clean={e["clean"]}'
             f'->{"/".join(e["faulted_supported"])}|truth={e["true_hypothesis"]}|{e["grade_under_A"]}')
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _blank():
    return {"pairs": 0, "graded": 0, "wrong": 0, "new_wrong": 0,
            "correct_supported_clean": 0, "correct_supported_retained": 0,
            "correct_supported_lost": 0, "SUPPORTED": 0, "AMBIGUOUS": 0,
            "INSUFFICIENT": 0, "NO_CONSISTENT": 0, "WITHHELD": 0, "INVALID": 0,
            "fault_visible": 0, "fault_evaluated": 0,
            "fault_created_supported": 0, "supported_resting_on_failed_refuter": 0,
            "injections": 0, "attr_wrong_unique": 0, "attr_new_wrong_unique": 0,
            "attr_correct_unique_clean": 0, "attr_correct_unique_retained": 0,
            "attr_correct_unique_lost": 0}


def main():
    t_start = time.perf_counter()
    agg = {(r, p): _blank() for r in ROLES + ("ALL",) for p in POLICIES}
    examples: dict = {}
    per_policy_ticks = {p: {"ticks_with_any_conclusion_lost": 0} for p in POLICIES}
    unmeasured_refuter_base = {"supported_localizations": 0,
                               "with_unmeasured_refuter": 0,
                               "correct_among_them": 0}
    injections = 0
    created_log = []
    for name in sorted(SCENARIOS):
        engine, res = P.run_scenario(SCENARIOS[name])
        core = SemanticCore21.from_engine(engine, trace=False)
        for s in core.symptoms:
            _SPEC_BY_SYMPTOM[s.symptom_id] = {h.hypothesis_id: h for h in s.hypotheses}
        specs = {s.symptom_id: s for s in core.symptoms}
        bases = base_ids(core.predicates)
        faulted = {b: faulted_core(core, b) for b in bases}
        for tick, sa in enumerate(res):
            clean = core.reason(sa.records)
            truth_dom = GT.attribution_domain(name, sa.records)
            clean_loc = {x.key: x for x in clean.localizations}
            clean_grade = {k: grade_loc(name, x, x.v2.verdict) for k, x in clean_loc.items()}
            clean_attr = grade_attr(truth_dom, clean, clean.attribution.verdict)
            for x in clean.localizations:
                if x.v2.verdict == SUPPORTED:
                    unmeasured_refuter_base["supported_localizations"] += 1
                    h = spec_h(x)[x.supported[0]]
                    if any(x.v2.detail["predicate_values"].get(p) is None
                           for p in h.refuted_by):
                        unmeasured_refuter_base["with_unmeasured_refuter"] += 1
                        unmeasured_refuter_base["correct_among_them"] += int(
                            clean_grade[x.key] == "CORRECT_CERTAIN")
            for b in bases:
                ids = ids_of(b, core.predicates)
                tr = faulted[b].reason(sa.records)
                injections += 1
                inj_loc = {x.key: x for x in tr.localizations}
                assert set(inj_loc) == set(clean_loc), "a predicate fault changed detection"
                pair_roles = {k: roles_for(name, clean_loc[k], specs[clean_loc[k].symptom], ids)
                              for k in clean_loc}
                tick_roles = set().union(*pair_roles.values()) if pair_roles else {"IRRELEVANT"}
                for pol in POLICIES:
                    locv, av = apply_policy(pol, tr)
                    lost_any = False
                    for k, x in inj_loc.items():
                        g = grade_loc(name, x, locv[k])
                        oc = outcome_class(x, locv[k])
                        failed = {i for e in x.predicate_errors for i in e.evaluated_as}
                        created = locv[k] == SUPPORTED and (
                            clean_loc[k].v2.verdict != SUPPORTED
                            or tuple(x.supported) != tuple(clean_loc[k].supported))
                        resting = locv[k] == SUPPORTED and bool(
                            failed & set(spec_h(x)[x.supported[0]].refuted_by))
                        vis = bool(x.predicate_errors) if pol != "D" else (locv[k] == INVALID)
                        for role in pair_roles[k] | {"ALL"}:
                            a = agg[(role, pol)]
                            a["pairs"] += 1
                            a[oc] = a.get(oc, 0) + 1
                            a["fault_evaluated"] += int(bool(x.predicate_errors))
                            a["fault_visible"] += int(vis and bool(x.predicate_errors))
                            a["fault_created_supported"] += int(created)
                            a["supported_resting_on_failed_refuter"] += int(resting)
                            if g != "UNGRADED":
                                a["graded"] += 1
                                a["wrong"] += int(g == "WRONG")
                                a["new_wrong"] += int(g == "WRONG" and clean_grade[k] != "WRONG")
                                if clean_grade[k] == "CORRECT_CERTAIN":
                                    a["correct_supported_clean"] += 1
                                    kept = g == "CORRECT_CERTAIN"
                                    a["correct_supported_retained"] += int(kept)
                                    a["correct_supported_lost"] += int(not kept)
                                    lost_any |= not kept
                        if pol == "A" and created:
                            created_log.append({
                                "scenario": name, "tick": tick, "failed": b, "unit": k,
                                "clean": clean_loc[k].v2.verdict,
                                "clean_supported": list(clean_loc[k].supported),
                                "clean_unresolved": list(clean_loc[k].unresolved),
                                "faulted_supported": list(x.supported),
                                "grade_under_A": g, "clean_grade": clean_grade[k],
                                "true_hypothesis": GT.true_hypothesis(name, x.symptom)})
                        if g == "WRONG" and clean_grade[k] != "WRONG":
                            examples.setdefault(pol, [])
                            if len(examples[pol]) < 12:
                                examples[pol].append({
                                    "scenario": name, "tick": tick, "failed": b,
                                    "unit": k, "clean": clean_loc[k].v2.verdict,
                                    "clean_supported": list(clean_loc[k].supported),
                                    "faulted_supported": list(x.supported),
                                    "roles": sorted(pair_roles[k]),
                                    "policy_verdict": locv[k]})
                    ag = grade_attr(truth_dom, tr, av)
                    for role in tick_roles | {"ALL"}:
                        a = agg[(role, pol)]
                        a["injections"] += 1
                        a["attr_wrong_unique"] += int(ag == "WRONG_UNIQUE")
                        a["attr_new_wrong_unique"] += int(ag == "WRONG_UNIQUE"
                                                          and clean_attr != "WRONG_UNIQUE")
                        if clean_attr == "CORRECT_UNIQUE":
                            a["attr_correct_unique_clean"] += 1
                            a["attr_correct_unique_retained"] += int(ag == "CORRECT_UNIQUE")
                            a["attr_correct_unique_lost"] += int(ag != "CORRECT_UNIQUE")
                            lost_any |= ag != "CORRECT_UNIQUE"
                    per_policy_ticks[pol]["ticks_with_any_conclusion_lost"] += int(lost_any)
    rows = []
    for (role, pol), a in agg.items():
        rows.append({"role": role, "policy": pol, **a})
    rows.sort(key=lambda r: (ROLES + ("ALL",)).index(r["role"]) * 10 + POLICIES.index(r["policy"]))
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    out = {"harness": "semantic_core_2_1_predicate_fault_injection",
           "dataset": "D: every base predicate failed in turn on every tick of dataset A",
           "injections": injections,
           "policies": list(POLICIES),
           "per_policy": {p: {k: agg[("ALL", p)][k] for k in agg[("ALL", p)]}
                          | per_policy_ticks[p] for p in POLICIES},
           "new_wrong_examples": examples,
           "fault_created_supported_under_A": {
               "count": len(created_log),
               "by": _count_by(created_log),
               "examples": created_log[:15]},
           "unmeasured_refuter_base_rate_unfaulted": unmeasured_refuter_base,
           "seconds": round(time.perf_counter() - t_start, 1)}
    JSON_OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({p: {k: out["per_policy"][p][k] for k in (
        "pairs", "graded", "wrong", "new_wrong", "fault_created_supported",
        "supported_resting_on_failed_refuter", "fault_evaluated", "fault_visible",
        "correct_supported_clean",
        "correct_supported_lost", "attr_new_wrong_unique",
        "attr_correct_unique_clean", "attr_correct_unique_lost",
        "ticks_with_any_conclusion_lost")} for p in POLICIES}, indent=1))
    print("unmeasured refuter base rate", unmeasured_refuter_base)
    print("examples A", json.dumps(examples.get("A", [])[:6], indent=1))
    print("seconds", out["seconds"])


if __name__ == "__main__":
    main()
