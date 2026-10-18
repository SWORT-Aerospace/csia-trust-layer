#!/usr/bin/env python3
"""CSIA semantic correctness audit: executable probe. RESEARCH ONLY.

This file is not production CSIA, and nothing in `csia/` imports it. It
imports the frozen v2 Phase C code and calls it. It never writes to that code,
never monkey-patches it and never registers anything with it. It reads the
sealed XSYS-001 stage-1 and stage-2 files and never writes them.

Run from the repository root:

    .venv/bin/python research/csia_semantic_correctness/semantic_probe.py

It writes `semantic_probe_results.json` next to this file. The package
documents cite the result ids used below.

    R    minimal reproductions at record level
    E    engine-level runs of every shipped scenario, plus variants
    P    metamorphic properties over the shipped-scenario corpus
    N    exhaustive small-state enumeration
    X    XSYS-001 replay from the sealed stage-1 output
    SH   a SHADOW successor semantics

SH exists only to MEASURE what a proposed correction would change. It is not
the correction, it is not wired into anything, and nothing outside this file
calls it.

Deterministic: fixed seeds, sorted iteration, no clock in any output.
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from csia.v2 import scenarios as SC  # noqa: E402
from csia.v2 import signatures as SIG  # noqa: E402
from csia.v2.attribution import AMBIGUOUS as A_AMBIGUOUS  # noqa: E402
from csia.v2.attribution import UNIQUE as A_UNIQUE  # noqa: E402
from csia.v2.attribution import Attribution, attribute  # noqa: E402
from csia.v2.evidence import Applicability as AP  # noqa: E402
from csia.v2.evidence import EvidenceRecord as ER  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import (AMBIGUOUS, SUPPORTED, UNSUPPORTED,  # noqa: E402
                                  EvidenceIndex, Hypothesis, Predicate,
                                  SymptomSpec, localize, localize_all)
from csia.v2.profiles import SCENARIOS, build_engine_for  # noqa: E402
from csia.v2.profiles.aircraft import AIRCRAFT_RELATIONS  # noqa: E402
from csia.v2.profiles.aircraft_scenarios import example_payload_feed  # noqa: E402

TICKS = 60                      # the tick count the v2 localization tests use
SEED = 20260929
OUT = HERE / "semantic_probe_results.json"
XSYS_STAGE1 = REPO / "research/xsys_001_confirmatory_campaign/stage1/STAGE1.json"
XSYS_STAGE1_SHA = "ccbc10f5aecde43bbfe7297e2073907089ece1562190383c57e0682c11a0e8e3"
XSYS_RESULTS = REPO / "research/xsys_001_confirmatory_campaign/stage2/RESULTS.json"
XSYS_PIPELINE = REPO / "research/xsys_confirmatory_001/pipeline"
UNKNOWN_STATES = (OS.UNAVAILABLE, OS.NOT_APPLICABLE)
ADVERSE = (OS.DEGRADED, OS.VIOLATED)


# ============================================================== helpers
def rec(domain, component, relation, state=OS.NOMINAL, deps=(), codes=(),
        app=None, attributable=True, fns=()):
    if app is None:
        app = {OS.UNAVAILABLE: AP.INPUTS_MISSING,
               OS.NOT_APPLICABLE: AP.NOT_APPLICABLE}.get(state, AP.APPLICABLE)
    return ER(domain=domain, component=component, relation=relation,
              source="semantic-probe", observation_state=state,
              applicability=app, dependencies=tuple(deps),
              reason_codes=tuple(codes), attributable=attributable,
              affected_functions=tuple(fns))


def rid(r):
    return f"{r.domain}/{r.component}:{r.relation}"


def rshow(r):
    """The fields reasoning reads, for the written record of a reproduction."""
    return {"domain": r.domain, "component": r.component,
            "relation": r.relation, "state": r.observation_state.value,
            "applicability": r.applicability.value,
            "dependencies": list(r.dependencies) if r.dependencies is not None else None,
            "reason_codes": list(r.reason_codes) if r.reason_codes is not None else None,
            "affected_functions": list(r.affected_functions),
            "attributable": r.attributable}


def twin(r, state):
    """The same statement, but 'could not look' (UNAVAILABLE) or 'nothing to
    look at' (NOT_APPLICABLE). Dependencies are declared structure, not
    evidence, so they are kept."""
    app = AP.INPUTS_MISSING if state is OS.UNAVAILABLE else AP.NOT_APPLICABLE
    return replace(r, observation_state=state, applicability=app,
                   reason_codes=())


def lproj(loc):
    return {"verdict": loc.verdict, "supported": list(loc.supported),
            "unresolved": list(loc.unresolved),
            "rejected": sorted(h for h, _ in loc.rejected)}


def aproj(a):
    return {"verdict": a.verdict, "candidates": [c.id for c in a.candidates],
            "common_cause": a.common_cause}


def atrace(a):
    return {"discriminators": list(a.discriminators),
            "unsupported": list(a.unsupported),
            "domains_excluded": list(a.detail.get("domains_excluded", []))}


def ltrace(loc):
    return {"evidence": list(loc.evidence),
            "refuting": list(loc.refuting_evidence),
            "unmeasurable": list(loc.unmeasurable),
            "rejected_by": [list(x) for x in loc.rejected]}


class Cfg:
    """What an engine reasons with, beside the records."""

    def __init__(self, symptoms, predicates, relations):
        self.symptoms = tuple(symptoms)
        self.predicates = dict(predicates)
        self.relations = tuple(relations)


def cfg_of(engine):
    return Cfg(engine.symptoms, engine.predicates, engine.relations)


AIR = Cfg(SIG.SYMPTOMS, SIG.PREDICATES, AIRCRAFT_RELATIONS)


def frozen(records, cfg):
    """Exactly what `AssuranceEngine.evaluate` does with one tick's records."""
    records = tuple(records)
    locs = (localize_all(cfg.symptoms, records, cfg.predicates)
            if cfg.symptoms else ())
    return locs, attribute(records, cfg.relations)


def decision(out):
    locs, a = out
    return {"loc": {f"{x.symptom}|{x.subject}": lproj(x) for x in locs},
            "attr": aproj(a)}


def trace(out):
    locs, a = out
    return {"loc": {f"{x.symptom}|{x.subject}": ltrace(x) for x in locs},
            "attr": atrace(a)}


def changed_units(d0, d1, skip_subjects=()):
    out = []
    for k in sorted(set(d0["loc"]) | set(d1["loc"])):
        if k.split("|", 1)[1] in skip_subjects:
            continue
        if d0["loc"].get(k) != d1["loc"].get(k):
            out.append(k)
    if d0["attr"] != d1["attr"]:
        out.append("ATTR")
    return out


def feed(sc):
    if sc.system != "aircraft":
        return None
    return example_payload_feed(getattr(sc, "v1_1_variant", "clean"))


def run_scenario(sc, ticks=TICKS):
    engine = build_engine_for(sc)
    return engine, SC.run(engine, sc, ticks=ticks, payload_for=feed(sc))


def variant(sc, name, drop=(), mutate=None):
    inner = sc.inject

    def inj(sig, frac, t):
        if inner is not None:
            inner(sig, frac, t)
        for d, c in drop:
            sig.get(d, {}).pop(c, None)
        if mutate is not None:
            mutate(sig, frac, t)
    return replace(sc, inject=inj, name=name)


def _nominal_ids(records):
    return {f"{r.domain}/{r.component}" for r in records
            if r.observation_state is OS.NOMINAL and r.attributable}


def _excluded_ids(records):
    """C1: affirmatively NOMINAL means at least one NOMINAL attributable record
    and no record of the same component that could not look or was adverse."""
    blocked = {f"{r.domain}/{r.component}" for r in records
               if r.observation_state is OS.UNAVAILABLE or r.is_adverse}
    return _nominal_ids(records) - blocked


def _graph(records):
    g = {}
    for r in records:
        g.setdefault(f"{r.domain}/{r.component}", set()).update(r.dependencies or ())
    return g


def _ancestors(node, graph):
    seen, stack = set(), list(graph.get(node, ()))
    while stack:
        cur = stack.pop()
        if cur not in seen:
            seen.add(cur)
            stack.extend(graph.get(cur, ()))
    return seen


def declared_alternatives(cid, records, relations):
    """Every component the CURRENT declared structure names as a possible
    other explanation for `cid`: what it transitively depends on, plus what
    any relation spanning its domain implicates. Nothing is invented; these
    are the two structures `attribute()` already walks."""
    alts = _ancestors(cid, _graph(records))
    dom = cid.split("/", 1)[0]
    for rel in relations:
        if dom in rel.domains:
            alts.update(rel.implicates)
    alts.discard(cid)
    return sorted(alts)


# ============================================================ SHADOW (SH)
class ShadowIndex(EvidenceIndex):
    """SHADOW ONLY. C6: an exact duplicate counts once, and two different
    records about one (relation, component) answer neither; the disagreement
    is kept. With c6=False it is the frozen index, unchanged."""

    def __init__(self, records, c6=True):
        recs = list(records)
        self.all_records = tuple(recs)
        self.conflicts = set()
        if c6:
            seen, uniq = set(), []
            for r in recs:
                key = _rkey(r)
                if key not in seen:
                    seen.add(key)
                    uniq.append(r)
            recs = uniq
            states = {}
            for r in recs:
                states.setdefault((r.relation, r.component), set()).add(
                    (r.observation_state, tuple(sorted(r.reason_codes or ()))))
            self.conflicts = {k for k, v in states.items() if len(v) > 1}
        super().__init__(recs)

    def by_relation(self, relation, component=None, prefix=None):
        if component is not None and (relation, component) in self.conflicts:
            return []
        return super().by_relation(relation, component, prefix)


def _rkey(r):
    try:
        return json.dumps(r.to_dict(), sort_keys=True, default=str)
    except TypeError:
        return repr(r)


def _agg(rows, k3):
    """'Every row is fine'. Frozen form: None if no rows, else no row adverse.
    C2 (Kleene strong conjunction): a NOT_APPLICABLE row says nothing; any
    adverse row makes it False; otherwise any UNAVAILABLE row makes it None."""
    rows = list(rows)
    if k3:
        rows = [r for r in rows if r.observation_state is not OS.NOT_APPLICABLE]
    if not rows:
        return None
    if any(r.observation_state in ADVERSE for r in rows):
        return False
    if k3 and any(r.observation_state is OS.UNAVAILABLE for r in rows):
        return None
    return True


def _scope(index, subject):
    """C3: the components DECLARED to serve `subject`. For a function: the
    timing channels, processes and links whose `affected_functions` name it.
    For a component: itself. Then everything those declare as dependencies,
    transitively. Uses only fields the records already carry."""
    serving = ("timing.end_to_end", "compute.process_alive",
               "compute.process_producing", "compute.deadline_met",
               "comm.link_state")
    comps = {subject}
    for r in getattr(index, "all_records", index.records):
        if r.relation in serving and subject in r.affected_functions:
            comps.add(r.component)
    frontier = list(comps)
    while frontier:
        c = frontier.pop()
        for d in index.dependencies_of(c):
            name = d.split("/", 1)[1]
            if name not in comps:
                comps.add(name)
                frontier.append(name)
    return comps


def shadow_tests(c2, c3):
    """Replacement test functions for exactly the predicates the audit found
    reading 'could not look' as an answer (C2) or ignoring their subject (C3).
    With both flags off every one of them reproduces the frozen predicate."""
    def scoped(index, s, rows):
        if not c3:
            return list(rows)
        sc = _scope(index, s)
        return [r for r in rows if r.component in sc]

    def any_adverse_id(index, node_ids):
        """True if any named node is adverse. Frozen: False once any node has
        any row. C2: None unless EVERY named node has looked and none could
        not look, which is the only case 'not adverse' is known."""
        rows_by = {nid: index.find_id(nid) for nid in node_ids}
        rows = [r for v in rows_by.values() for r in v]
        if not rows:
            return None
        if any(r.observation_state in ADVERSE for r in rows):
            return True
        if c2:
            for v in rows_by.values():
                looked = [r for r in v if r.observation_state is not OS.NOT_APPLICABLE]
                if not looked or any(r.observation_state is OS.UNAVAILABLE for r in looked):
                    return None
        return False

    def dep_ok(domain):
        def test(index, subject):
            got = any_adverse_id(index, SIG._deps_in(index, subject, domain))
            return None if got is None else (not got)
        return test

    def producer(relations):
        def test(index, channel):
            rows = []
            for proc in SIG._producer_processes(index, channel):
                for rel in relations:
                    rec_ = index.one(rel, component=proc)
                    if rec_ is not None:
                        rows.append(rec_)
            return _agg(rows, c2)
        return test

    def process_alive(index, process):
        rows = [index.one("compute.process_alive", component=process),
                index.one("compute.process_producing", component=process)]
        return _agg([r for r in rows if r is not None], c2)

    def single(relation, fn):
        def test(index, subject):
            rec_ = index.one(relation, component=subject)
            if rec_ is None or rec_.observation_state is OS.NOT_APPLICABLE:
                return None
            if c2 and rec_.observation_state is OS.UNAVAILABLE:
                return None
            return fn(rec_)
        return test

    def judged(rows):
        # frozen: APPLICABLE only (which silently drops UNAVAILABLE rows);
        # C2: drop only rows the domain declared not judged
        if c2:
            return [r for r in rows if r.applicability is not AP.NOT_APPLICABLE]
        return [r for r in rows if r.applicability.value == "APPLICABLE"]

    def estimator_ok(index, s):
        rows = [r for r in index.records if r.domain == "COMPUTE" and r.relation in
                ("compute.process_alive", "compute.process_producing", "compute.deadline_met")]
        return _agg(scoped(index, s, rows), c2)

    def timing_ok(index, s):
        return _agg(scoped(index, s, judged(index.by_relation("timing.end_to_end"))), c2)

    def no_segment_over(index, s):
        rows = judged(index.by_relation("timing.segment_budget")) + list(index.by_relation("timing.rate"))
        if c3:
            chans = {r.component for r in index.by_relation("timing.end_to_end")} & _scope(index, s)
            rows = [r for r in rows if r.component.split(".", 1)[0] in chans]
        return _agg(rows, c2)

    def links_ok(index, s):
        return _agg(scoped(index, s, index.by_relation("comm.link_state")), c2)

    def cpu_ok(index, s):
        return _agg(scoped(index, s, index.by_relation("compute.resource_headroom")), c2)

    def shared_status(index, domain):
        """Structure exactly as SIG._shared_adverse_dependency finds it; the
        status of each shared node read in Kleene form, so a node nobody
        reported, or that could not be looked at, is unknown, not healthy."""
        srcs = SIG._adverse_sources(index)
        counts = {}
        for r in srcs:
            for dep in set(r.dependencies):
                if dep.startswith(f"{domain}/"):
                    counts[dep] = counts.get(dep, 0) + 1
        shared = sorted(k for k, n in counts.items() if n >= 2)
        if not shared:
            reach = {}
            for r in srcs:
                for dep in set(r.dependencies):
                    for up in index.dependencies_of(dep.split("/", 1)[1]):
                        if up.startswith(f"{domain}/"):
                            reach[up] = reach.get(up, 0) + 1
            shared = sorted(k for k, n in reach.items() if n >= 2)
        if not shared:
            return False
        st = [any_adverse_id(index, [x]) for x in shared]
        if any(v is True for v in st):
            return True
        if any(v is None for v in st):
            return None
        return False

    def shared_in(domain):
        def test(index, _subject):
            if len(SIG._adverse_sources(index)) < 2:
                return None
            st = shared_status(index, domain)
            if st is True or st is None:
                return st
            return False if SIG._covered(index, domain) else None
        return test

    def no_shared(index, _subject):
        if len(SIG._adverse_sources(index)) < 2:
            return None
        st = [shared_status(index, d) for d in SIG._COMMON_CAUSE_DOMAINS]
        if any(v is True for v in st):
            return False
        if any(v is None for v in st):
            return None
        if any(not SIG._covered(index, d) for d in SIG._COMMON_CAUSE_DOMAINS):
            return None
        return True

    k3 = {"SHARED_ADVERSE_POWER_DEPENDENCY": shared_in("POWER"),
          "SHARED_ADVERSE_COMM_DEPENDENCY": shared_in("COMMUNICATION"),
          "SHARED_ADVERSE_COMPUTE_DEPENDENCY": shared_in("COMPUTE"),
          "NO_SHARED_ADVERSE_DEPENDENCY": no_shared,
          "CHANNEL_LINK_NOMINAL": dep_ok("COMMUNICATION"),
          "ACTUATOR_LINK_NOMINAL": dep_ok("COMMUNICATION"),
          "ACTUATOR_POWER_NOMINAL": dep_ok("POWER"),
          "PRODUCER_PROCESS_HEALTHY": producer(("compute.process_alive", "compute.process_producing")),
          "PRODUCER_DEADLINE_MET": producer(("compute.deadline_met",)),
          "PROCESS_ALIVE_AND_PRODUCING": process_alive,
          "CURRENT_PRESENT": single("actuation.electrical_response",
                                    lambda r: "ACT_NO_ELECTRICAL_RESPONSE" not in r.reason_codes),
          "STALL_SIGNATURE": single("actuation.mechanical_response",
                                    lambda r: "ACT_STALLED" in r.reason_codes),
          "PHYSICAL_RESPONSE_NOMINAL": single("actuation.physical_response",
                                              lambda r: r.observation_state is OS.NOMINAL)}
    scope = {"ESTIMATOR_PROCESS_HEALTHY": estimator_ok,
             "FUNCTION_TIMING_WITHIN_DEADLINE": timing_ok,
             "NO_TIMING_SEGMENT_OVER_BUDGET": no_segment_over,
             "FUNCTION_LINKS_NOMINAL": links_ok,
             "CPU_HEADROOM_NOMINAL": cpu_ok}
    out = {}
    if c2:
        out.update(k3)
    if c2 or c3:
        out.update(scope)
    return out


C2_PREDICATES = ("SHARED_ADVERSE_POWER_DEPENDENCY", "SHARED_ADVERSE_COMM_DEPENDENCY",
                 "SHARED_ADVERSE_COMPUTE_DEPENDENCY", "NO_SHARED_ADVERSE_DEPENDENCY",
                 "CHANNEL_LINK_NOMINAL", "ACTUATOR_LINK_NOMINAL", "ACTUATOR_POWER_NOMINAL",
                 "PRODUCER_PROCESS_HEALTHY", "PRODUCER_DEADLINE_MET", "PROCESS_ALIVE_AND_PRODUCING",
                 "CURRENT_PRESENT", "STALL_SIGNATURE", "PHYSICAL_RESPONSE_NOMINAL",
                 "ESTIMATOR_PROCESS_HEALTHY", "FUNCTION_TIMING_WITHIN_DEADLINE",
                 "NO_TIMING_SEGMENT_OVER_BUDGET", "FUNCTION_LINKS_NOMINAL", "CPU_HEADROOM_NOMINAL")
C3_PREDICATES = ("ESTIMATOR_PROCESS_HEALTHY", "FUNCTION_TIMING_WITHIN_DEADLINE",
                 "NO_TIMING_SEGMENT_OVER_BUDGET", "FUNCTION_LINKS_NOMINAL", "CPU_HEADROOM_NOMINAL")


def _sc_degraded_position_functions(c2):
    tests = shadow_tests(c2, True)

    def detect(index):
        out = set()
        for r in index.by_relation("v1_1.function_eligibility"):
            _, _, name = r.component.partition(".")
            if not name or ("NAVIGATION" not in name and "POSITION" not in name):
                continue
            if (r.observation_state in ADVERSE
                    or tests["ESTIMATOR_PROCESS_HEALTHY"](index, name) is False
                    or tests["FUNCTION_TIMING_WITHIN_DEADLINE"](index, name) is False
                    or tests["FUNCTION_LINKS_NOMINAL"](index, name) is False):
                out.add(name)
        return tuple(sorted(out))
    return detect


class ShadowPredicate(Predicate):
    """C4: an exception or a return that is not True/False/None is still
    unmeasurable for elimination, and it is also REPORTED."""

    def __call__(self, index, subject):
        log = getattr(index, "predicate_errors", None)
        try:
            got = self.test(index, subject)
        except Exception as exc:  # noqa: BLE001
            if log is not None:
                log.append([self.predicate_id, subject, f"RAISED:{type(exc).__name__}"])
            return None
        if got is not None and type(got) is not bool:
            if log is not None:
                log.append([self.predicate_id, subject,
                            f"NON_BOOL:{type(got).__module__}.{type(got).__name__}"])
            return None
        return got


def shadow_predicates(preds, c2=True, c3=True, c4=True):
    repl = shadow_tests(c2, c3)
    cls = ShadowPredicate if c4 else Predicate
    base = {}
    for pid, p in preds.items():
        if pid.endswith("_FALSE") and pid[:-6] in preds:
            continue
        base[pid] = cls(pid, p.description, p.evidence_domain, repl.get(pid, p.test))
    out = dict(base)
    for pid, b in base.items():
        if pid + "_FALSE" in preds:
            def neg(index, subject, _b=b):
                got = _b(index, subject)
                return None if got is None else (not got)
            out[pid + "_FALSE"] = cls(pid + "_FALSE", "NOT (" + b.description + ")",
                                      b.evidence_domain, neg)
    return out


def shadow_symptoms(symptoms, c2=True, c3=True):
    if not c3:
        return tuple(symptoms)
    return tuple(replace(s, detect=_sc_degraded_position_functions(c2))
                 if s.symptom_id == "POSITION_UNAVAILABLE" else s
                 for s in symptoms)


def split_unsupported(loc):
    """C5: the two things localization UNSUPPORTED means today."""
    if loc.verdict != UNSUPPORTED:
        return loc.verdict
    return ("NO_CONSISTENT_HYPOTHESIS" if not loc.unresolved
            else "INSUFFICIENT_EVIDENCE")


def collisions(spec, loc):
    """C7: hypotheses rejected although a predicate that confirms ONLY them
    was True. Trace only; the rejection stands."""
    vals = loc.detail.get("predicate_values", {})
    confirms = {}
    for h in spec.hypotheses:
        for p in h.confirmed_by:
            confirms.setdefault(p, set()).add(h.hypothesis_id)
    out = []
    for h, by in loc.rejected:
        hyp = next(x for x in spec.hypotheses if x.hypothesis_id == h)
        specific = [p for p in hyp.confirmed_by
                    if vals.get(p) is True and confirms[p] == {h}]
        shared = [p for p in hyp.confirmed_by
                  if vals.get(p) is True and confirms[p] != {h}]
        if specific or shared:
            out.append({"hypothesis": h, "refuted_by": by,
                        "specific_confirmers": specific,
                        "shared_confirmers": shared})
    return out


def split_implicated(a, records):
    """C5 for attribution: `unsupported` today mixes three states."""
    nominal = _nominal_ids(records)
    seen = {f"{r.domain}/{r.component}" for r in records}
    unavailable = {f"{r.domain}/{r.component}" for r in records
                   if r.observation_state in UNKNOWN_STATES} - nominal
    return {"implicated_nominal": [c for c in a.unsupported if c in nominal],
            "implicated_unavailable": [c for c in a.unsupported if c in unavailable],
            "implicated_unobserved": [c for c in a.unsupported if c not in seen]}


def shadow_attribute(records, relations, locs=(), c1=True, f2=True):
    """C1: a discriminator must be RELEVANT, meaning a record about a declared
    alternative of the candidate, and every declared alternative must be
    affirmatively NOMINAL. F2: UNIQUE is withheld while a same-tick
    localization of the candidate still keeps an explanation in another
    domain. Both only ever turn UNIQUE into AMBIGUOUS."""
    a = attribute(records, relations)
    meta = {"split_unsupported": split_implicated(a, records)}
    if a.verdict != A_UNIQUE:
        return a, meta
    only = a.candidates[0]
    reasons = []
    if c1:
        alts = declared_alternatives(only.id, records, relations)
        nominal = _excluded_ids(records)
        relevant = sorted(d for d in a.discriminators
                          if d.split(":", 1)[0] in alts)
        unexcluded = [x for x in alts if x not in nominal]
        cross = [d for d in relevant if not d.startswith(only.domain + "/")]
        meta.update(declared_alternatives=alts, relevant_discriminators=relevant,
                    unexcluded_alternatives=unexcluded)
        if not alts:
            reasons.append("NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED")
        elif unexcluded:
            reasons.append("DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL")
        elif not cross:
            reasons.append("NO_RELEVANT_DISCRIMINATOR_FROM_ANOTHER_DOMAIN")
    if f2:
        keep = []
        for x in locs:
            if x.subject != only.component:
                continue
            other = [h for h in x.supported + x.unresolved
                     if h.split("/", 1)[0] != only.domain]
            if other:
                keep.append({"symptom": x.symptom, "retains": other})
        if keep:
            reasons.append("SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN")
            meta["localization_disagreement"] = keep
    if not reasons:
        return a, meta
    meta["withheld_unique_because"] = reasons
    return Attribution(verdict=A_AMBIGUOUS, candidates=a.candidates,
                       discriminators=a.discriminators,
                       common_cause=a.common_cause, unsupported=a.unsupported,
                       detail=dict(a.detail, why="successor gate: " + ", ".join(reasons))), meta


ALL_FIXES = ("C1", "F2", "C2", "C3", "C4", "C6")


def shadow(records, cfg, fixes=ALL_FIXES):
    """The whole successor, or any subset of its fixes, over one tick."""
    fx = set(fixes)
    records = tuple(records)
    index = ShadowIndex(records, c6="C6" in fx)
    index.predicate_errors = []
    preds = shadow_predicates(cfg.predicates, c2="C2" in fx, c3="C3" in fx, c4="C4" in fx)
    specs = shadow_symptoms(cfg.symptoms, c2="C2" in fx, c3="C3" in fx)
    locs, meta = [], {}
    for spec in specs:
        for subject in spec.detect(index):
            before = len(index.predicate_errors)
            loc = localize(spec, index, subject, preds)
            locs.append(loc)
            meta[f"{loc.symptom}|{loc.subject}"] = {
                "successor_verdict": split_unsupported(loc),
                "collisions": collisions(spec, loc),
                "predicate_errors": index.predicate_errors[before:]}
    arecs = records
    if "C6" in fx:
        seen, arecs = set(), []
        for r in records:
            k = _rkey(r)
            if k not in seen:
                seen.add(k)
                arecs.append(r)
    a, ameta = shadow_attribute(tuple(arecs), cfg.relations, locs,
                                c1="C1" in fx, f2="F2" in fx)
    return (tuple(locs), a), {"loc": meta, "attr": ameta,
                              "disagreements": sorted(map(list, index.conflicts))}


# ============================================================== R section
def section_R():
    R = {}

    def case(cid, title, records, cfg=AIR, note=""):
        out = frozen(records, cfg)
        sh, meta = shadow(records, cfg)
        R[cid] = {"title": title, "records": [rshow(r) for r in records],
                  "frozen": decision(out), "frozen_trace": trace(out),
                  "shadow": decision(sh), "shadow_meta": meta["attr"],
                  "note": note}
        return out

    rail = rec("POWER", "rail_5v", "power.rail_tolerance", OS.VIOLATED)
    cpu = rec("COMPUTE", "cpu", "compute.resource_headroom")
    case("R1A", "one adverse record, nothing else", [rail])
    case("R1B", "the same plus ONE unrelated NOMINAL record from another domain",
         [rail, cpu])

    gps = rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED,
              deps=("POWER/rail_5v", "COMMUNICATION/gnss_serial"))
    motor = rec("ACTUATION", "motor_0", "actuation.command_path")
    link_u = rec("COMMUNICATION", "gnss_serial", "comm.link_state", OS.UNAVAILABLE)
    rail_u = rec("POWER", "rail_5v", "power.rail_tolerance", OS.UNAVAILABLE)
    link_n = rec("COMMUNICATION", "gnss_serial", "comm.link_state")
    rail_n = rec("POWER", "rail_5v", "power.rail_tolerance")
    case("R2", "adverse GNSS source; its declared link and rail never observed; "
         "an unrelated motor record is NOMINAL", [gps, motor])
    case("R3", "as R2, but the link and rail are UNAVAILABLE (could not look)",
         [gps, link_u, rail_u, motor])
    case("R4", "control: the declared link and rail are affirmatively NOMINAL",
         [gps, link_n, rail_n])

    # R6: container order decides between SUPPORTED and UNSUPPORTED.
    base6 = [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                 deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial")),
             rec("TIMING", "nav_solution.sensor_slow", "timing.rate"),
             rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget"),
             rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget"),
             link_n,
             rec("COMPUTE", "state_estimator", "compute.process_alive"),
             rec("COMPUTE", "state_estimator", "compute.process_producing")]
    clk_ok = rec("TIMING", "nav_solution", "timing.clock_consistency")
    clk_bad = rec("TIMING", "nav_solution", "timing.clock_consistency", OS.VIOLATED)
    case("R6A", "two clock records disagree; the NOMINAL one is listed first",
         base6 + [clk_ok, clk_bad])
    case("R6B", "identical set; the VIOLATED clock record is listed first",
         base6 + [clk_bad, clk_ok])

    src = rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED,
              deps=("POWER/rail_5v",))
    case("R7A", "one adverse source on an adverse rail", [src, rail])
    case("R7B", "the same adverse source record, twice", [src, src, rail])
    case("R7C", "an unrelated NOMINAL record, twice (attribution trace)",
         [rail, cpu, cpu])

    # R8: 'could not look' used as a refutation.
    stale = [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                 deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial")),
             rec("TIMING", "nav_solution", "timing.clock_consistency"),
             rec("TIMING", "nav_solution.sensor_slow", "timing.rate")]
    proc_ok = [rec("COMPUTE", "state_estimator", "compute.process_alive"),
               rec("COMPUTE", "state_estimator", "compute.process_producing")]
    tr_bad = rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget", OS.VIOLATED)
    pr_ok = rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget")
    case("R8A", "transport over budget; the link is not reported at all",
         stale + [tr_bad, pr_ok] + proc_ok)
    case("R8B", "transport over budget; the link is UNAVAILABLE (telemetry missing)",
         stale + [tr_bad, pr_ok, link_u] + proc_ok)
    tr_ok = rec("TIMING", "nav_solution.transport_delay", "timing.segment_budget")
    pr_bad = rec("TIMING", "nav_solution.processing_delay", "timing.segment_budget", OS.VIOLATED)
    alive = lambda st: rec("COMPUTE", "state_estimator", "compute.process_alive", st)  # noqa: E731
    case("R8C", "processing over budget; the producing process is STALLED (true cause)",
         stale + [tr_ok, pr_bad, link_n, alive(OS.VIOLATED)])
    case("R8D", "the same, but the process is not reported at all",
         stale + [tr_ok, pr_bad, link_n])
    case("R8E", "the same, but the process telemetry is UNAVAILABLE",
         stale + [tr_ok, pr_bad, link_n, alive(OS.UNAVAILABLE)])
    m_adv = rec("ACTUATION", "motor_0", "actuation.electrical_response", OS.VIOLATED,
                codes=("ACT_NO_ELECTRICAL_RESPONSE",),
                deps=("POWER/battery", "COMMUNICATION/esc_can"))
    bat = lambda st: rec("POWER", "battery", "power.source_health", st)  # noqa: E731
    case("R8F", "motor has no current; battery source VIOLATED; one unrelated NOMINAL",
         [m_adv, bat(OS.VIOLATED), cpu])
    case("R8G", "the same, but the battery telemetry is UNAVAILABLE",
         [m_adv, bat(OS.UNAVAILABLE), cpu])

    # R17: two adverse sources declare the same four shared nodes; nobody
    # reports those nodes at all.
    shared4 = ("POWER/rail_3v3", "COMMUNICATION/bus_a", "COMPUTE/proc_a", "TIMING/clk_a")
    s1 = rec("SENSOR", "source.imu0", "v1_1.source_health", OS.VIOLATED, deps=shared4)
    s2 = rec("SENSOR", "source.mag", "v1_1.source_health", OS.VIOLATED, deps=shared4)
    node = lambda st: rec("POWER", "rail_3v3", "power.rail_tolerance", st)  # noqa: E731
    case("R17A", "two adverse sources share four declared nodes; no node is reported", [s1, s2])
    case("R17B", "the same, and the shared rail is reported VIOLATED", [s1, s2, node(OS.VIOLATED)])
    case("R17C", "the same, and the shared rail is UNAVAILABLE", [s1, s2, node(OS.UNAVAILABLE)])

    # R18: Part 7, three detectors reading ONE physical source.
    views = [("cusum", "detector.cusum"), ("threshold", "detector.threshold"),
             ("kalman", "detector.kalman_residual")]
    same_comp = [replace(rec("SENSOR", "source.imu1", f"imu1.{n}", OS.VIOLATED), source=src)
                 for n, src in views]
    split_comp = [replace(rec("SENSOR", f"imu1.{n}", "imu1.check", OS.VIOLATED,
                              deps=("SENSOR/source.imu1",)), source=src) for n, src in views]
    as_sources = [replace(rec("SENSOR", "source.imu1", "v1_1.source_health", OS.VIOLATED,
                              deps=("POWER/rail_3v3",)), source=src) for _n, src in views]
    one_source = [as_sources[0], rec("POWER", "rail_3v3", "power.rail_tolerance")]
    case("R18A", "three detectors on IMU1, reported as three relations of one component",
         same_comp + [cpu])
    case("R18B", "the same three detectors, reported as three components that each "
         "declare IMU1 as their dependency", split_comp + [cpu])
    case("R18C", "one adverse IMU1 source-health reading, rail NOMINAL", one_source)
    case("R18D", "the same reading from three detectors (source field differs; "
         "nothing else does)", as_sources + one_source[1:])
    R["R18_source_field_read"] = {
        "title": "does any reasoning path read EvidenceRecord.source?",
        "same_output_when_only_source_differs": (
            decision(frozen([replace(x, source="a") for x in same_comp] + [cpu], AIR))
            == decision(frozen([replace(x, source="b") for x in same_comp] + [cpu], AIR)))}

    # R12: VOLTAGE_RAIL_LOW asks for the source by the RAIL's name.
    case("R12", "rail_5v VIOLATED, battery affirmatively NOMINAL",
         [rec("POWER", "rail_5v", "power.rail_tolerance", OS.VIOLATED,
              deps=("POWER/battery",)), bat(OS.NOMINAL)])
    # R14: a second, unrelated fault.
    case("R14", "R1B plus an unrelated VIOLATED telemetry radio",
         [rail, cpu, rec("COMMUNICATION", "telemetry_radio", "comm.link_state", OS.VIOLATED)])
    # R16: an unrelated process makes the navigation functions a symptom.
    nav = [rec("SENSOR", "v1_1.PRECISION_NAVIGATION", "v1_1.function_eligibility",
               attributable=False),
           rec("TIMING", "nav_solution", "timing.end_to_end",
               deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial"),
               fns=("PRECISION_NAVIGATION",)),
           rec("COMMUNICATION", "gnss_serial", "comm.link_state"),
           rec("COMPUTE", "state_estimator", "compute.deadline_met",
               fns=("PRECISION_NAVIGATION",))]
    logger_late = rec("COMPUTE", "logger", "compute.deadline_met", OS.VIOLATED,
                      fns=("LOGGING",))
    case("R16A", "navigation evidence all NOMINAL", nav)
    case("R16B", "the same plus an unrelated late LOGGER process", nav + [logger_late])

    # R9-R11, R15: exceptions and return types.
    spec = SymptomSpec("S", "synthetic", detect=lambda ix: ("x",), hypotheses=(
        Hypothesis("D1/h1", "D1", "m", confirmed_by=("P",), refuted_by=("Q",)),
        Hypothesis("D2/h2", "D2", "m", confirmed_by=("P",), refuted_by=("R",))))

    def preds(q):
        return {"P": Predicate("P", "", "D", lambda i, s: True),
                "Q": Predicate("Q", "", "D", q),
                "R": Predicate("R", "", "D", lambda i, s: False)}

    def boom_key(i, s):
        raise KeyError("defect")

    def boom_zero(i, s):
        raise ZeroDivisionError("defect")

    rows = []
    import numpy as np  # present in the repository environment
    for label, q in [("True", lambda i, s: True), ("False", lambda i, s: False),
                     ("None", lambda i, s: None),
                     ("raises KeyError", boom_key),
                     ("raises ZeroDivisionError", boom_zero),
                     ("numpy.True_", lambda i, s: np.True_),
                     ("numpy.False_", lambda i, s: np.False_),
                     ("int 1", lambda i, s: 1), ("str 'yes'", lambda i, s: "yes"),
                     ("float nan", lambda i, s: float("nan"))]:
        got = localize(spec, EvidenceIndex(()), "x", preds(q))
        sidx = ShadowIndex(())
        sidx.predicate_errors = []
        sp = {k: ShadowPredicate(v.predicate_id, "", "D", v.test) for k, v in preds(q).items()}
        sgot = localize(spec, sidx, "x", sp)
        rows.append({"Q": label, "frozen": lproj(got),
                     "frozen_unmeasurable": list(got.unmeasurable),
                     "frozen_value_recorded": repr(got.detail["predicate_values"]["Q"]),
                     "shadow": lproj(sgot), "shadow_errors": sidx.predicate_errors})
    R["R9_R10"] = {"title": "one predicate's return or exception, all else fixed "
                            "(P True confirms both; Q refutes h1; R refutes h2 and is False)",
                   "rows": rows}
    rows2 = []
    for label, q in [("True", lambda i, s: True), ("None", lambda i, s: None),
                     ("raises KeyError", boom_key)]:
        pr = preds(q)
        pr["R"] = Predicate("R", "", "D", lambda i, s: True)
        got = localize(spec, EvidenceIndex(()), "x", pr)
        rows2.append({"Q": label, "frozen": lproj(got),
                      "frozen_unmeasurable": list(got.unmeasurable)})
    R["R9B"] = {"title": "as R9 but R is True: a raising refuter turns 'every "
                          "explanation ruled out' into SUPPORTED", "rows": rows2}

    malformed = rec("ACTUATION", "motor_0", "actuation.electrical_response", OS.VIOLATED)
    malformed = replace(malformed, reason_codes=None)
    locs = localize_all(SIG.SYMPTOMS, [malformed], SIG.PREDICATES)
    try:
        attribute([malformed])
        attr_raises = None
    except Exception as exc:  # noqa: BLE001
        attr_raises = f"{type(exc).__name__}: {exc}"
    sidx = ShadowIndex([malformed])
    sidx.predicate_errors = []
    sp = shadow_predicates(SIG.PREDICATES)
    for spec_ in SIG.SYMPTOMS:
        for subj in spec_.detect(sidx):
            localize(spec_, sidx, subj, sp)
    R["R11A"] = {"title": "a record with reason_codes=None reaches localization and attribution",
                 "frozen_localization": [lproj(x) | {"unmeasurable": list(x.unmeasurable)} for x in locs],
                 "frozen_attribution_raises": attr_raises,
                 "shadow_predicate_errors": sidx.predicate_errors}
    bad = replace(rec("SENSOR", "source.gps", "v1_1.source_health", OS.VIOLATED),
                  dependencies=None)
    try:
        attribute([bad])
        R["R11B"] = {"title": "dependencies=None reaches attribution", "raises": None}
    except Exception as exc:  # noqa: BLE001
        R["R11B"] = {"title": "dependencies=None reaches attribution",
                     "raises": f"{type(exc).__name__}: {exc}"}
    try:
        localize(spec, EvidenceIndex(()), "x", {"P": preds(None)["P"], "Q": preds(None)["Q"]})
        R["R15A"] = {"title": "a hypothesis names a predicate the table lacks", "raises": None}
    except Exception as exc:  # noqa: BLE001
        R["R15A"] = {"title": "a hypothesis names a predicate the table lacks",
                     "raises": f"{type(exc).__name__}: {exc}"}

    def bad_detect(ix):
        raise RuntimeError("detector defect")
    try:
        localize_all((replace(spec, detect=bad_detect),), [], {})
        R["R15B"] = {"title": "a symptom detector raises", "raises": None}
    except Exception as exc:  # noqa: BLE001
        R["R15B"] = {"title": "a symptom detector raises",
                     "raises": f"{type(exc).__name__}: {exc}"}

    # R13: static facts, read from source.
    callers = []
    for p in sorted(REPO.rglob("*.py")):
        if ".venv" in p.parts or "node_modules" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "attribute_unsupported") or \
               (isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "attribute_unsupported"):
                callers.append(str(p.relative_to(REPO)))
    used = {p for s in SIG.SYMPTOMS for h in s.hypotheses
            for p in tuple(h.confirmed_by) + tuple(h.refuted_by)}
    R["R13"] = {"title": "static: callers of attribute_unsupported; declared "
                         "predicates no hypothesis uses",
                "attribute_unsupported_callers": sorted(set(callers)),
                "unused_predicates": sorted(p for p in SIG.PREDICATES
                                            if not p.endswith("_FALSE") and p not in used
                                            and p + "_FALSE" not in used)}
    return R


# ============================================================== E section
def section_E():
    E = {"baseline": {}, "tick_census": {}, "variants": {}}
    runs = {}
    for name in sorted(SCENARIOS):
        sc = SCENARIOS[name]
        engine, res = run_scenario(sc)
        runs[name] = (sc, engine, res)
        fin = res[-1]
        cfg = cfg_of(engine)
        a = fin.attribution
        _sh, meta = shadow(fin.records, cfg)
        E["baseline"][name] = {
            "system": sc.system,
            "attribution": aproj(a) | {"n_discriminators": len(a.discriminators)},
            "relevant_discriminators": meta["attr"].get("relevant_discriminators"),
            "declared_alternatives": meta["attr"].get("declared_alternatives"),
            "localizations": {f"{x.symptom}|{x.subject}": lproj(x) for x in fin.localizations},
            "nav_function_states": {k: v.state for k, v in fin.functions.items()}}
    # every tick: is a single candidate ever AMBIGUOUS in a shipped profile?
    single = {"UNIQUE": 0, "AMBIGUOUS": 0}
    ticks = 0
    for name, (_sc, _e, res) in runs.items():
        for t in res:
            ticks += 1
            if len(t.attribution.candidates) == 1:
                single[t.attribution.verdict] = single.get(t.attribution.verdict, 0) + 1
    E["tick_census"] = {"ticks": ticks, "single_candidate_ticks_by_verdict": single}
    E["loc_attr_matrix"] = loc_attr_matrix(runs)
    # A symptom that says a function is not fully available, on a tick where
    # the function graph calls that same function ELIGIBLE.
    contra, total, by = 0, 0, {}
    sh_contra = sh_total = 0
    for name, (_sc, engine, res) in sorted(runs.items()):
        cfg = cfg_of(engine)
        for t in res:
            for x in shadow(t.records, cfg)[0][0]:
                if x.symptom == "POSITION_UNAVAILABLE":
                    sh_total += 1
                    fv = t.functions.get(x.subject)
                    sh_contra += int(fv is not None and fv.state == "ELIGIBLE")
            for x in t.localizations:
                if x.symptom != "POSITION_UNAVAILABLE":
                    continue
                total += 1
                fv = t.functions.get(x.subject)
                if fv is not None and fv.state == "ELIGIBLE":
                    contra += 1
                    k = f"{x.subject}|{x.verdict}"
                    by[k] = by.get(k, 0) + 1
    E["symptom_vs_function_state"] = {"position_unavailable_localizations": total,
                                      "on_a_function_the_graph_calls_ELIGIBLE": contra,
                                      "by_subject_and_verdict": dict(sorted(by.items())),
                                      "shadow_position_unavailable_localizations": sh_total,
                                      "shadow_on_a_function_the_graph_calls_ELIGIBLE": sh_contra}

    A = {n: s for n, s in SCENARIOS.items()}

    def logger_late(sig, frac, t):
        sig["COMPUTE"]["logger"]["runtime_s"] = 0.5

    def radio_down(sig, frac, t):
        sig["COMMUNICATION"]["telemetry_radio"]["link_up"] = False

    specs = [
        ("V_IRR_1", "NOMINAL", dict(mutate=logger_late), "unrelated logger misses its deadline"),
        ("V_IRR_2", "MS_D1_NAV_SOURCE", dict(mutate=logger_late), "true GNSS source fault, plus the unrelated late logger"),
        ("V_IRR_3", "NOMINAL", dict(mutate=radio_down), "unrelated telemetry radio link down"),
        ("V_MIS_1", "MS_A2_COMMUNICATION_DELAY", dict(drop=[("COMMUNICATION", "gnss_serial")]), "true transport delay; GNSS link telemetry absent"),
        ("V_MIS_2", "MS_A4_PROCESS_STALL", dict(drop=[("COMPUTE", "state_estimator")]), "true process stall; estimator telemetry absent"),
        ("V_MIS_3", "MS_C4_CPU_SATURATED_NOT_SHARED", dict(drop=[("COMPUTE", "cpu")]), "true CPU saturation; resource telemetry absent"),
        ("V_MIS_4", "MS_B2_POWER_PATH", dict(drop=[("POWER", "battery")]), "true power-path fault; battery telemetry absent"),
        ("V_MIS_5", "MS_D3_COMM_STARVATION", dict(drop=[("COMMUNICATION", "gnss_serial")]), "true link starvation; the link's own telemetry absent"),
    ]
    for vid, base, kw, desc in specs:
        sc = A[base]
        _e0, r0 = runs[base][1], runs[base][2]
        v = variant(sc, f"{base}+{vid}", **kw)
        engine, res = run_scenario(v)
        b, f = r0[-1], res[-1]
        cfg = cfg_of(engine)
        d0 = decision((b.localizations, b.attribution))
        d1 = decision((f.localizations, f.attribution))
        sh0, _ = shadow(b.records, cfg)
        sh1, _ = shadow(f.records, cfg)
        s0, s1 = decision(sh0), decision(sh1)
        E["variants"][vid] = {
            "base": base, "description": desc,
            "frozen_changed": {k: [d0["loc"].get(k) if k != "ATTR" else d0["attr"],
                                   d1["loc"].get(k) if k != "ATTR" else d1["attr"]]
                               for k in changed_units(d0, d1)},
            "shadow_changed": {k: [s0["loc"].get(k) if k != "ATTR" else s0["attr"],
                                   s1["loc"].get(k) if k != "ATTR" else s1["attr"]]
                               for k in changed_units(s0, s1)},
            "nav_function_states_after": {k: v2.state for k, v2 in f.functions.items()
                                          if "NAV" in k or "POSITION" in k}}
    # Part 8, producer unavailable: the POWER plugin raises from tick 2 on,
    # during the true power-path fault. Same wrapper the v2 tests use.
    from csia.v2.plugin_runtime import FailingDomain
    pf = {}
    for base, dom in (("MS_B2_POWER_PATH", "POWER"), ("MS_A4_PROCESS_STALL", "COMPUTE"),
                      ("MS_D3_COMM_STARVATION", "COMMUNICATION")):
        sc = SCENARIOS[base]
        engine = build_engine_for(sc)
        engine.registry.replace(FailingDomain(engine.registry.get(dom), mode="raise", after_tick=1))
        res = SC.run(engine, sc, ticks=TICKS, payload_for=feed(sc))
        f, b = res[-1], runs[base][2][-1]
        sh0 = decision(shadow(b.records, cfg_of(engine))[0])
        sh1 = decision(shadow(f.records, cfg_of(engine))[0])
        d0 = decision((b.localizations, b.attribution))
        d1 = decision((f.localizations, f.attribution))
        pf[f"{base}+{dom}_PLUGIN_RAISES"] = {
            "frozen_attribution": [d0["attr"], d1["attr"]],
            "frozen_changed": {k: [d0["loc"].get(k), d1["loc"].get(k)]
                               for k in changed_units(d0, d1) if k != "ATTR"},
            "shadow_attribution": [sh0["attr"], sh1["attr"]],
            "plugin_state": f.plugins.get(dom, {}).get("state"),
            "function_states_after": {k: v.state for k, v in sorted(f.functions.items())}}
    E["producer_unavailable"] = pf
    b5 = runs["MS_B5_RESPONSE_SENSOR"][2][-1]
    E["B5_contradiction"] = {
        "attribution": aproj(b5.attribution),
        "domains_excluded": b5.attribution.detail.get("domains_excluded"),
        "sensor_discriminators": [d for d in b5.attribution.discriminators if d.startswith("SENSOR/")],
        "localization": {f"{x.symptom}|{x.subject}": lproj(x) for x in b5.localizations}}
    return E, runs


def loc_attr_matrix(runs):
    """Every tick of every shipped scenario: attribution verdict against the
    verdict of each localization whose subject is an attribution candidate's
    component. Also the cross-domain retention that makes a UNIQUE
    contradict its own tick."""
    cells, examples = {}, {}
    for name, (_sc, _e, res) in sorted(runs.items()):
        for k, t in enumerate(res):
            comps = {c.component: c.domain for c in t.attribution.candidates}
            for x in t.localizations:
                if x.subject not in comps:
                    continue
                other = [h for h in x.supported + x.unresolved
                         if h.split("/", 1)[0] != comps[x.subject]]
                key = f"{t.attribution.verdict}|{x.verdict}|{'OTHER_DOMAIN_RETAINED' if other else 'SAME_DOMAIN_ONLY'}"
                cells[key] = cells.get(key, 0) + 1
                examples.setdefault(key, set()).add(name)
            for x in t.localizations:
                if x.subject in comps:
                    continue
                key = f"{t.attribution.verdict}|{x.verdict}|SUBJECT_NOT_A_CANDIDATE"
                cells[key] = cells.get(key, 0) + 1
                examples.setdefault(key, set()).add(name)
    return {"cells": dict(sorted(cells.items())),
            "scenarios": {k: sorted(v) for k, v in sorted(examples.items())}}


#: The reason code an adverse completion of a record must carry for the
#: predicates that read codes rather than states.
ADVERSE_CODE = {"actuation.electrical_response": ("ACT_NO_ELECTRICAL_RESPONSE",),
                "actuation.mechanical_response": ("ACT_STALLED",),
                "actuation.command_path": ("ACT_COMMAND_NOT_TRANSMITTED",),
                "timing.end_to_end": ("TIMING_DEADLINE_MISSED",)}


def completions(r):
    """The two things an unknown record could have been, structure unchanged."""
    codes = tuple(r.reason_codes or ()) if r.is_adverse else ADVERSE_CODE.get(r.relation, ())
    return (replace(r, observation_state=OS.NOMINAL, applicability=AP.APPLICABLE, reason_codes=()),
            replace(r, observation_state=OS.VIOLATED, applicability=AP.APPLICABLE, reason_codes=codes))


def _confirmed(hyp, values):
    got = [values.get(p) is True for p in hyp.confirmed_by]
    return bool(hyp.confirmed_by) and (all(got) if hyp.confirm_requires_all else any(got))


def k3_check(spec, loc_u, locs_c):
    """Kleene-consistency of one localization computed with an unknown record,
    against the same localization under every completion of that record.

    UNKNOWN_REFUTES   a hypothesis is rejected, though some completion does
                      not reject it: 'could not look' was used as a refutation
    UNKNOWN_CONFIRMS  a hypothesis is confirmed, though some completion does
                      not confirm it: 'could not look' was used as support
    UNKNOWN_SUPPORTED the verdict is SUPPORTED and rests on either of those
    A hypothesis that merely SURVIVES because its refuter is unknown is not a
    violation: that is what 'unmeasurable eliminates nothing' means."""
    out = {"UNKNOWN_REFUTES": False, "UNKNOWN_CONFIRMS": False, "UNKNOWN_SUPPORTED": False}
    cs = [c for c in locs_c if c is not None]
    if loc_u is None or not cs:
        return out
    hyps = {h.hypothesis_id: h for h in spec.hypotheses}
    rej_u = {h for h, _ in loc_u.rejected}
    bad = set()
    for h in rej_u:
        if any(h not in {x for x, _ in c.rejected} for c in cs):
            out["UNKNOWN_REFUTES"] = True
            bad.add(h)
    vu = loc_u.detail["predicate_values"]
    for hid, hyp in hyps.items():
        if _confirmed(hyp, vu) and any(not _confirmed(hyp, c.detail["predicate_values"]) for c in cs):
            out["UNKNOWN_CONFIRMS"] = True
            bad.add(hid)
    if loc_u.verdict == SUPPORTED and bad:
        out["UNKNOWN_SUPPORTED"] = True
    return out


# ============================================================== P section
AUX = [("COMPUTE", "aux_process", "compute.deadline_met"),
       ("COMMUNICATION", "aux_link", "comm.link_state"),
       ("TIMING", "aux_channel", "timing.end_to_end"),
       ("POWER", "aux_rail", "power.rail_tolerance"),
       ("ACTUATION", "aux_actuator", "actuation.command_path"),
       ("SENSOR", "source.aux", "v1_1.source_health")]
STATES = (OS.NOMINAL, OS.DEGRADED, OS.VIOLATED, OS.UNAVAILABLE, OS.NOT_APPLICABLE)


def corpus_from(runs):
    return [(n, cfg_of(e), tuple(res[-1].records)) for n, (_s, e, res) in sorted(runs.items())]


def section_P(runs):
    corpus = corpus_from(runs)
    P = {}
    P["P1"] = p1_irrelevant_addition(corpus)
    P["P2"] = p2_removal(corpus)
    P["P3"] = p3_order(corpus)
    P["P4"] = p4_duplicates(corpus)
    P["P5"] = p5_exceptions(corpus)
    P["P6"] = p6_missing(corpus)
    P["P8"] = p8_replay()
    P["P9"] = p9_consistency(runs)
    P["P10"] = p10_trace(corpus)
    P["P11"] = p11_unsupported(runs)
    P["P12"] = p12_kleene(corpus)
    return P


def _run_both(records, cfg):
    return decision(frozen(records, cfg)), decision(shadow(records, cfg)[0])


def p1_irrelevant_addition(corpus):
    """Add one record about a component nothing declares, in every state.
    Invariant: no localization on any OTHER subject changes, no new
    localization appears on another subject, the attribution does not
    become more certain, and (for NOMINAL) does not change at all."""
    res = {t: {"cases": 0, "violations": 0, "localization_violations": 0,
               "attribution_changed_on_nominal": 0, "attribution_more_certain": 0,
               "attribution_candidates_lost": 0, "by_state": {}, "examples": []}
           for t in ("frozen", "shadow")}
    for name, cfg, records in corpus:
        base_f, base_s = _run_both(records, cfg)
        for (d, c, rel), st in itertools.product(AUX, STATES):
            extra = rec(d, c, rel, st, fns=("AUX_FUNCTION",))
            f1, s1 = _run_both(records + (extra,), cfg)
            skip = (c, "sources") if rel == "v1_1.source_health" else (c,)
            for tag, b, a in (("frozen", base_f, f1), ("shadow", base_s, s1)):
                bad = [k for k in changed_units(b, a, skip_subjects=skip) if k != "ATTR"]
                ab, aa = b["attr"], a["attr"]
                r = res[tag]
                r["localization_violations"] += int(bool(bad))
                if st is OS.NOMINAL and ab != aa:
                    bad.append("ATTR")
                    r["attribution_changed_on_nominal"] += 1
                if ab["verdict"] == A_AMBIGUOUS and aa["verdict"] == A_UNIQUE:
                    bad.append("ATTR")
                    r["attribution_more_certain"] += 1
                if not set(ab["candidates"]) <= set(aa["candidates"]):
                    bad.append("ATTR")
                    r["attribution_candidates_lost"] += 1
                r["cases"] += 1
                if bad:
                    r["violations"] += 1
                    r["by_state"][st.value] = r["by_state"].get(st.value, 0) + 1
                    if len(r["examples"]) < 12:
                        r["examples"].append({"scenario": name, "added": rid(extra) + "=" + st.value,
                                              "changed": bad[:4]})
    return res


def _declared_scope_for_unit(unit, records, attr_alts):
    """What the CURRENT declared structure says a result may depend on.
    For attribution: candidates, their declared alternatives and the
    dependency chain. For a localization: its subject, the components
    declared to serve it, their dependencies, and a channel's segments."""
    if unit == "ATTR":
        return attr_alts
    _sym, subject = unit.split("|", 1)
    idx = ShadowIndex(records, c6=False)
    if subject == "sources":
        comps = {r.component for r in records if r.relation == "v1_1.source_health"}
        for r in records:
            if r.relation == "v1_1.source_health":
                comps.update(d.split("/", 1)[1] for d in (r.dependencies or ()))
        return {"components": comps, "declares_domains": {"SENSOR", "POWER", "COMMUNICATION", "COMPUTE"}}
    comps = _scope(idx, subject) | {f"v1_1.{subject}"}
    comps |= {r.component for r in records
              if r.component.split(".", 1)[0] in comps}
    doms = {r.domain for r in records if r.component in comps}
    return {"components": comps, "declares_domains": doms}


def p2_removal(corpus):
    """Part 4. Remove each record in turn and classify it against each result
    it could touch, using the declared structure, not the change alone."""
    out = {}
    for tag in ("frozen", "shadow"):
        out[tag] = _p2(corpus, (lambda rr, c: frozen(rr, c)) if tag == "frozen"
                       else (lambda rr, c: shadow(rr, c)[0]))
    return out


def _p2(corpus, fn):
    tally = {}
    examples = {}
    for name, cfg, records in corpus:
        base = decision(fn(records, cfg))
        a = attribute(records, cfg.relations)
        alts = set()
        for cnd in a.candidates:
            alts.add(cnd.id)
            alts.update(declared_alternatives(cnd.id, records, cfg.relations))
        attr_scope = {"components": {x.split("/", 1)[1] for x in alts},
                      "declares_domains": {x.split("/", 1)[0] for x in alts}}
        scopes = {u: _declared_scope_for_unit(u, records, attr_scope)
                  for u in list(base["loc"]) + ["ATTR"]}
        for i, r in enumerate(records):
            rest = records[:i] + records[i + 1:]
            after = decision(fn(rest, cfg))
            for unit in list(base["loc"]) + ["ATTR"]:
                b = base["attr"] if unit == "ATTR" else base["loc"].get(unit)
                af = after["attr"] if unit == "ATTR" else after["loc"].get(unit)
                sc = scopes[unit]
                in_scope = r.component in sc["components"] or (
                    unit == "ATTR" and r.is_adverse and r.attributable)
                verdict_changed = (af is None) or (b["verdict"] != af["verdict"])
                any_changed = b != af
                if in_scope:
                    cls = "ESSENTIAL" if verdict_changed else "RELEVANT"
                elif any_changed:
                    cls = ("IRRELEVANT_BUT_DECISION_CHANGING"
                           if r.domain in sc["declares_domains"] else "UNKNOWN")
                else:
                    cls = "IRRELEVANT_AND_INVARIANT"
                tally[cls] = tally.get(cls, 0) + 1
                if cls in ("IRRELEVANT_BUT_DECISION_CHANGING", "UNKNOWN"):
                    ex = examples.setdefault(cls, [])
                    if len(ex) < 15:
                        ex.append({"scenario": name, "removed": rid(r) + "=" + r.observation_state.value,
                                   "unit": unit, "before": b, "after": af})
    return {"tally": dict(sorted(tally.items())), "examples": examples}


def p3_order(corpus):
    rng = random.Random(SEED)
    out = {"frozen": {"cases": 0, "violations": 0, "trace_only": 0},
           "shadow": {"cases": 0, "violations": 0, "trace_only": 0}}
    for name, cfg, records in corpus:
        f0 = frozen(records, cfg)
        s0 = shadow(records, cfg)[0]
        orders = [tuple(reversed(records))]
        for _ in range(5):
            o = list(records)
            rng.shuffle(o)
            orders.append(tuple(o))
        for o in orders:
            for tag, base, fn in (("frozen", f0, lambda rr: frozen(rr, cfg)),
                                  ("shadow", s0, lambda rr: shadow(rr, cfg)[0])):
                got = fn(o)
                out[tag]["cases"] += 1
                if decision(got) != decision(base):
                    out[tag]["violations"] += 1
                elif trace(got) != trace(base):
                    out[tag]["trace_only"] += 1
    return out


def p4_duplicates(corpus):
    out = {"frozen": {"single": 0, "decision": 0, "trace_only": 0, "group_decision": 0, "examples": []},
           "shadow": {"single": 0, "decision": 0, "trace_only": 0, "group_decision": 0, "examples": []}}
    for name, cfg, records in corpus:
        for tag, fn in (("frozen", lambda rr: frozen(rr, cfg)),
                        ("shadow", lambda rr: shadow(rr, cfg)[0])):
            base = fn(records)
            if decision(fn(records + records)) != decision(base):
                out[tag]["group_decision"] += 1
            for r in records:
                got = fn(records + (r,))
                out[tag]["single"] += 1
                if decision(got) != decision(base):
                    out[tag]["decision"] += 1
                    if len(out[tag]["examples"]) < 10:
                        out[tag]["examples"].append({"scenario": name, "duplicated": rid(r) + "=" + r.observation_state.value,
                                                     "changed": changed_units(decision(base), decision(got))[:4]})
                elif trace(got) != trace(base):
                    out[tag]["trace_only"] += 1
    return out


def p5_exceptions(corpus):
    """Make each predicate raise, one at a time, on every corpus tick. Does
    the failure show anywhere in the output other than as 'not measurable',
    and does it change a conclusion?"""
    pids = sorted({p for _n, cfg, _r in corpus for p in cfg.predicates
                   if not p.endswith("_FALSE")})
    rows = {}
    for pid in pids:
        row = {"ticks_evaluated": 0, "frozen_visible": 0, "shadow_visible": 0,
               "frozen_decision_changed": 0, "examples": []}
        for name, cfg, records in corpus:
            if pid not in cfg.predicates:
                continue

            def boom(i, s):
                raise RuntimeError("injected predicate defect")
            preds = dict(cfg.predicates)
            preds[pid] = Predicate(pid, "", "X", boom)
            if pid + "_FALSE" in preds:
                b = preds[pid]
                preds[pid + "_FALSE"] = Predicate(
                    pid + "_FALSE", "", "X",
                    lambda i, s, _b=b: (None if _b(i, s) is None else not _b(i, s)))
            c2 = Cfg(cfg.symptoms, preds, cfg.relations)
            base = frozen(records, cfg)
            got = frozen(records, c2)
            used = any(pid in x.detail["predicate_values"] or pid + "_FALSE" in x.detail["predicate_values"]
                       for x in got[0])
            row["ticks_evaluated"] += int(used)
            blob = json.dumps([x.to_dict() for x in got[0]] + [got[1].to_dict()], default=str)
            row["frozen_visible"] += int("injected predicate defect" in blob or "RuntimeError" in blob)
            if decision(got) != decision(base):
                row["frozen_decision_changed"] += 1
                gb, ga = decision(base)["loc"], decision(got)["loc"]
                row["became_supported"] = row.get("became_supported", 0) + sum(
                    1 for k, v in ga.items() if v["verdict"] == SUPPORTED
                    and (gb.get(k) is None or gb[k]["verdict"] != SUPPORTED))
                if len(row["examples"]) < 3:
                    u = changed_units(decision(base), decision(got))
                    row["examples"].append({"scenario": name, "unit": u[0],
                                            "before": decision(base)["loc"].get(u[0]),
                                            "after": decision(got)["loc"].get(u[0])})
            _sh, meta = shadow(records, c2, fixes=("C4",))
            row["shadow_visible"] += int(any(m["predicate_errors"] for m in meta["loc"].values()))
        rows[pid] = row
    return {"per_predicate": rows,
            "predicates": len(pids),
            "predicates_whose_failure_changed_a_decision": sorted(
                p for p, r in rows.items() if r["frozen_decision_changed"]),
            "frozen_visible_total": sum(r["frozen_visible"] for r in rows.values()),
            "became_supported_total": sum(r.get("became_supported", 0) for r in rows.values()),
            "decision_changes_total": sum(r["frozen_decision_changed"] for r in rows.values())}


def p6_missing(corpus):
    """Part 8. Replace a record by its 'could not look' (UNAVAILABLE) or
    'nothing to look at' (NOT_APPLICABLE) twin, and check every localization
    against both completions of that record (k3_check). Attribution: count
    UNIQUE verdicts that stand while the unknown record is a declared
    alternative of the candidate."""
    out = {}
    for tag in ("frozen", "shadow"):
        r = {"cases": 0, "same_unit_differences": 0, "examples": []}
        for name, cfg, records in corpus:
            for i, rr in enumerate(records):
                if rr.observation_state in UNKNOWN_STATES or rr.dependencies:
                    continue
                t = records[:i] + (twin(rr, OS.NOT_APPLICABLE),) + records[i + 1:]
                gone = records[:i] + records[i + 1:]
                fn = (lambda x: frozen(x, cfg)) if tag == "frozen" else (lambda x: shadow(x, cfg)[0])
                a, b = decision(fn(t)), decision(fn(gone))
                r["cases"] += 1
                common = sorted(set(a["loc"]) & set(b["loc"]))
                diff = [k for k in common if a["loc"][k] != b["loc"][k]]
                if diff or a["attr"] != b["attr"]:
                    r["same_unit_differences"] += 1
                    if len(r["examples"]) < 8:
                        k = diff[0] if diff else "ATTR"
                        r["examples"].append({"scenario": name, "record": rid(rr), "unit": k,
                                              "record_removed": b["loc"].get(k, b["attr"]),
                                              "record_not_applicable": a["loc"].get(k, a["attr"])})
        out[f"{tag}_NOT_APPLICABLE_vs_absent"] = r
    for label, st in (("UNAVAILABLE", OS.UNAVAILABLE),):
        for tag in ("frozen", "shadow"):
            r = {"cases": 0, "cases_with_violation": 0, "UNKNOWN_REFUTES": 0,
                 "UNKNOWN_CONFIRMS": 0, "UNKNOWN_SUPPORTED": 0,
                 "unique_despite_unknown_alternative": 0, "examples": []}
            for name, cfg, records in corpus:
                specs = {x.symptom_id: x for x in cfg.symptoms}
                for i, rr in enumerate(records):
                    if rr.observation_state in UNKNOWN_STATES:
                        continue
                    def run(rec_):
                        rs = records[:i] + (rec_,) + records[i + 1:]
                        return frozen(rs, cfg) if tag == "frozen" else shadow(rs, cfg)[0]
                    u = run(twin(rr, st))
                    cs = [run(c) for c in completions(rr)]
                    r["cases"] += 1
                    hit = False
                    for loc in u[0]:
                        same = [next((x for x in c[0] if x.symptom == loc.symptom
                                      and x.subject == loc.subject), None) for c in cs]
                        f = k3_check(specs[loc.symptom], loc, same)
                        for k, v in f.items():
                            r[k] += int(v)
                        if any(f.values()):
                            hit = True
                            if len(r["examples"]) < 10:
                                r["examples"].append({"scenario": name, "unknown": rid(rr) + "=" + st.value,
                                                      "unit": f"{loc.symptom}|{loc.subject}",
                                                      "flags": [k for k, v in f.items() if v],
                                                      "with_unknown": lproj(loc),
                                                      "completions": [lproj(x) if x else None for x in same]})
                    a = u[1]
                    if a.verdict == A_UNIQUE:
                        alts = declared_alternatives(a.candidates[0].id, records, cfg.relations)
                        if f"{rr.domain}/{rr.component}" in alts:
                            r["unique_despite_unknown_alternative"] += 1
                            hit = True
                    r["cases_with_violation"] += int(hit)
            out[f"{tag}_{label}"] = r
    return out


def p8_replay():
    names = ["MS_B5_RESPONSE_SENSOR", "MS_A2_COMMUNICATION_DELAY", "SHARED_RAIL", "TS_STALLED"]
    same = 0
    for n in names:
        _e, a = run_scenario(SCENARIOS[n])
        _e, b = run_scenario(SCENARIOS[n])
        same += int([t.to_dict() for t in a] == [t.to_dict() for t in b])
    return {"scenarios": names, "identical": same}


def p9_consistency(runs):
    tot = viol = 0
    sh_viol = 0
    examples = []
    for name, (_sc, engine, res) in sorted(runs.items()):
        cfg = cfg_of(engine)
        for k, t in enumerate(res):
            if t.attribution.verdict != A_UNIQUE:
                continue
            tot += 1
            only = t.attribution.candidates[0]
            bad = [x for x in t.localizations if x.subject == only.component and
                   any(h.split("/", 1)[0] != only.domain for h in x.supported + x.unresolved)]
            if bad:
                viol += 1
                if len(examples) < 10 and (not examples or examples[-1]["scenario"] != name):
                    examples.append({"scenario": name, "tick": k, "unique": only.id,
                                     "localization": {f"{x.symptom}|{x.subject}": lproj(x) for x in bad}})
                sa = shadow(t.records, cfg)[0][1]
                if sa.verdict == A_UNIQUE:
                    sh_viol += 1
    return {"unique_ticks": tot, "frozen_violations": viol,
            "shadow_violations": sh_viol, "examples": examples}


def p10_trace(corpus):
    """The trace must be what the predicate values imply, and no hypothesis
    may be both confirmed and refuted without the output saying so."""
    inconsistent = 0
    coll = {"shared_confirmer_only": 0, "specific_confirmer": 0}
    examples = []
    for name, cfg, records in corpus:
        index = EvidenceIndex(records)
        for spec in cfg.symptoms:
            for subject in spec.detect(index):
                loc = localize(spec, index, subject, cfg.predicates)
                vals = loc.detail["predicate_values"]
                if tuple(sorted(p for p, v in vals.items() if v is True)) != loc.evidence:
                    inconsistent += 1
                if tuple(sorted(p for p, v in vals.items() if v is None)) != loc.unmeasurable:
                    inconsistent += 1
                for c in collisions(spec, loc):
                    k = "specific_confirmer" if c["specific_confirmers"] else "shared_confirmer_only"
                    coll[k] += 1
                    if len(examples) < 8:
                        examples.append({"scenario": name, "symptom": spec.symptom_id,
                                         "subject": subject} | c)
    return {"trace_inconsistencies": inconsistent,
            "silent_confirm_and_refute": coll, "examples": examples}


def p11_unsupported(runs):
    loc = {"NO_CONSISTENT_HYPOTHESIS": 0, "INSUFFICIENT_EVIDENCE": 0}
    attr_unsupported_field = {"implicated_nominal": 0, "implicated_unavailable": 0,
                              "implicated_unobserved": 0}
    attr_verdict_unsupported = 0
    scen = {"NO_CONSISTENT_HYPOTHESIS": set(), "INSUFFICIENT_EVIDENCE": set()}
    with_conflict = 0
    for name, (_sc, engine, res) in sorted(runs.items()):
        specs = {x.symptom_id: x for x in engine.symptoms}
        for t in res:
            for x in t.localizations:
                if x.verdict == UNSUPPORTED:
                    k = split_unsupported(x)
                    loc[k] += 1
                    scen[k].add(name)
                    if k == "NO_CONSISTENT_HYPOTHESIS" and any(
                            c["specific_confirmers"] for c in collisions(specs[x.symptom], x)):
                        with_conflict += 1
            if t.attribution.verdict == "UNSUPPORTED":
                attr_verdict_unsupported += 1
            for k, v in split_implicated(t.attribution, t.records).items():
                attr_unsupported_field[k] += len(v)
    return {"localization_UNSUPPORTED_ticks_by_meaning": loc,
            "no_consistent_hypothesis_that_absorbed_a_specific_confirmation": with_conflict,
            "scenarios": {k: sorted(v) for k, v in scen.items()},
            "attribution_UNSUPPORTED_verdict_ticks": attr_verdict_unsupported,
            "attribution_unsupported_field_entries_by_meaning": attr_unsupported_field}


def p12_kleene(corpus):
    """Which PREDICATES turn 'could not look' into an answer? A predicate is
    Kleene-consistent if, with one record UNAVAILABLE, it returns None or the
    value it returns under BOTH completions of that record."""
    offenders = {}
    shadow_off = {}
    for name, cfg, records in corpus:
        base_subjects = set()
        for spec in cfg.symptoms:
            base_subjects.update(spec.detect(EvidenceIndex(records)))
        for i, r in enumerate(records):
            if r.observation_state in UNKNOWN_STATES:
                continue
            idx = lambda x: EvidenceIndex(records[:i] + (x,) + records[i + 1:])  # noqa: E731
            u_idx = idx(twin(r, OS.UNAVAILABLE))
            n_idx, v_idx = (idx(c) for c in completions(r))
            me = f"{r.domain}/{r.component}"
            dependents = {x.component for x in records if me in (x.dependencies or ())}
            subjects = sorted(base_subjects | {r.component} | dependents)
            spreds = shadow_predicates(cfg.predicates, c2=True, c3=False, c4=True)
            for pid, p in cfg.predicates.items():
                if pid.endswith("_FALSE"):
                    continue
                for s_ in subjects:
                    su, sn, sv = spreds[pid](u_idx, s_), spreds[pid](n_idx, s_), spreds[pid](v_idx, s_)
                    if su is not None and not (su == sn == sv):
                        shadow_off[pid] = shadow_off.get(pid, 0) + 1
                    u, n, v = p(u_idx, s_), p(n_idx, s_), p(v_idx, s_)
                    if u is None or (u == n == v):
                        continue
                    o = offenders.setdefault(pid, {"cases": 0, "example": None})
                    o["cases"] += 1
                    if o["example"] is None:
                        o["example"] = {"scenario": name, "record": rid(r), "subject": s_,
                                        "with_unavailable": u, "if_nominal": n, "if_violated": v}
    return {"offending_predicates": dict(sorted(offenders.items())),
            "shadow_offending_predicates": dict(sorted(shadow_off.items())),
            "predicates_checked": len({p for _n, c, _r in corpus for p in c.predicates
                                       if not p.endswith("_FALSE")})}


# ============================================================== N section
def section_N():
    return {"N1": n1_abstract(), "N2": n2_attribution(),
            "N3": n3_command_no_response(), "N4": n4_output_stale(),
            "N5": n5_position_irrelevance(), "N6": n6_shared_nodes()}


def n6_shared_nodes():
    """Two adverse sources that declare the same four shared nodes; each node
    is absent, NOMINAL, VIOLATED or UNAVAILABLE. An absent node is checked
    against both completions too: 'nobody reported it' is not 'it is fine'."""
    S4 = (None, OS.NOMINAL, OS.VIOLATED, OS.UNAVAILABLE)
    nodes = (("POWER", "rail_3v3", "power.rail_tolerance"),
             ("COMMUNICATION", "bus_a", "comm.link_state"),
             ("COMPUTE", "proc_a", "compute.process_alive"),
             ("TIMING", "clk_a", "timing.clock_consistency"))
    deps = tuple(f"{d}/{c}" for d, c, _ in nodes)
    spec = SIG.SYMPTOMS_BY_ID["MULTIPLE_SENSORS_DEGRADED"]

    def build(states):
        out = [rec("SENSOR", "source.imu0", "v1_1.source_health", OS.VIOLATED, deps=deps),
               rec("SENSOR", "source.mag", "v1_1.source_health", OS.VIOLATED, deps=deps)]
        for (d, c, rel), st in zip(nodes, states):
            if st is not None:
                out.append(rec(d, c, rel, st))
        return out

    def pick(tag, recs):
        out = frozen(recs, AIR) if tag == "frozen" else shadow(recs, AIR)[0]
        return next((x for x in out[0] if x.symptom == "MULTIPLE_SENSORS_DEGRADED"), None)

    res = {"configs": 0}
    for tag in ("frozen", "shadow"):
        for k in ("UNKNOWN_REFUTES", "UNKNOWN_CONFIRMS", "UNKNOWN_SUPPORTED"):
            res[f"{tag}_{k}"] = 0
        res[f"{tag}_independent_faults_supported"] = 0
    res["examples"] = []
    res["configs_with_unknown"] = 0
    for states in itertools.product(S4, repeat=4):
        res["configs"] += 1
        unk = [i for i, st in enumerate(states) if st is None or st is OS.UNAVAILABLE]
        res["configs_with_unknown"] += int(bool(unk))
        comps = []
        for fill in itertools.product((OS.NOMINAL, OS.VIOLATED), repeat=len(unk)):
            st2 = list(states)
            for i, f in zip(unk, fill):
                st2[i] = f
            comps.append(build(st2))
        for tag in ("frozen", "shadow"):
            base = pick(tag, build(states))
            if base is not None and "SENSOR/independent_faults" in base.supported:
                res[f"{tag}_independent_faults_supported"] += 1
            if not unk:
                continue
            flags = k3_check(spec, base, [pick(tag, c) for c in comps])
            for k, v in flags.items():
                res[f"{tag}_{k}"] += int(v)
            if tag == "frozen" and any(flags.values()) and len(res["examples"]) < 4:
                res["examples"].append({"nodes": [getattr(x, "value", x) for x in states],
                                        "flags": [k for k, v in flags.items() if v],
                                        "result": lproj(base) if base else None})
    return res


def _mk(fn):
    return Predicate(fn.__name__, "", "X", fn)


def n1_abstract():
    """Set elimination itself, on two shapes, over every K3 valuation.
    Shape XSYS: the shared-symptom pair XSYS-001 used. Shape SPECIFIC: three
    hypotheses, each with its own confirmer and its own refuter."""
    V = (True, False, None)
    out = {}

    def run_shape(spec, base_ids, derived):
        census, trans = {}, {}
        mono = {"confirm_added_rejects_hypothesis": 0, "refuter_added_supports_hypothesis": 0}
        unsup = {"NO_CONSISTENT_HYPOTHESIS": 0, "INSUFFICIENT_EVIDENCE": 0}
        silent = 0
        results = {}
        for vals in itertools.product(V, repeat=len(base_ids)):
            env = dict(zip(base_ids, vals))
            full = derived(env)
            preds = {k: Predicate(k, "", "X", (lambda v: (lambda i, s: v))(v)) for k, v in full.items()}
            loc = localize(spec, EvidenceIndex(()), "x", preds)
            results[vals] = (env, full, loc)
            census[loc.verdict] = census.get(loc.verdict, 0) + 1
            if loc.verdict == UNSUPPORTED:
                unsup[split_unsupported(loc)] += 1
            silent += int(bool([c for c in collisions(spec, loc) if c["specific_confirmers"]]))
        for vals, (env, full, loc) in results.items():
            for j, v in enumerate(vals):
                if v is not None:
                    continue
                for nv in (True, False):
                    nvals = vals[:j] + (nv,) + vals[j + 1:]
                    _e2, full2, loc2 = results[nvals]
                    key = f"{loc.verdict}->{loc2.verdict}"
                    trans[key] = trans.get(key, 0) + 1
                    newly_true = {p for p in full2 if full2[p] is True and full[p] is not True}
                    for h in spec.hypotheses:
                        hid = h.hypothesis_id
                        if newly_true & set(h.confirmed_by) and not newly_true & set(h.refuted_by):
                            if hid not in [x for x, _ in loc.rejected] and hid in [x for x, _ in loc2.rejected]:
                                mono["confirm_added_rejects_hypothesis"] += 1
                        if newly_true & set(h.refuted_by):
                            if hid in loc2.supported:
                                mono["refuter_added_supports_hypothesis"] += 1
        return {"valuations": len(results), "verdicts": census, "unsupported_meanings": unsup,
                "valuations_with_silent_specific_conflict": silent,
                "transitions_on_adding_one_predicate_value": dict(sorted(trans.items())),
                "monotonicity_violations": mono}

    xs = SymptomSpec("X", "xsys shape", detect=lambda i: ("x",), hypotheses=(
        Hypothesis("ACTUATION/mechanical", "ACTUATION", "", confirmed_by=("S",),
                   refuted_by=("S_FALSE", "D", "C")),
        Hypothesis("SENSOR/response_sensor", "SENSOR", "", confirmed_by=("S", "D", "C"),
                   refuted_by=("D_FALSE", "C_FALSE"))))

    def neg(env):
        out = dict(env)
        for k, v in env.items():
            out[k + "_FALSE"] = None if v is None else (not v)
        return out
    out["XSYS_SHAPE"] = run_shape(xs, ("S", "D", "C"), neg)
    sp = SymptomSpec("Y", "specific", detect=lambda i: ("x",), hypotheses=tuple(
        Hypothesis(f"D{i}/h{i}", f"D{i}", "", confirmed_by=(f"C{i}",), refuted_by=(f"R{i}",))
        for i in (1, 2, 3)))
    out["SPECIFIC_SHAPE"] = run_shape(sp, ("C1", "R1", "C2", "R2", "C3", "R3"), lambda e: dict(e))
    return out


def n2_attribution():
    """Components A (D1, depends on B), B (D2), C (D3, unrelated to both).
    Each is absent, NOMINAL, DEGRADED, UNAVAILABLE or NOT_APPLICABLE."""
    opts = (None, OS.NOMINAL, OS.DEGRADED, OS.UNAVAILABLE, OS.NOT_APPLICABLE)
    mk = {"A": lambda st: rec("D1", "a", "d1.rel", st, deps=("D2/b",)),
          "B": lambda st: rec("D2", "b", "d2.rel", st),
          "C": lambda st: rec("D3", "c", "d3.rel", st)}
    counts = {"configs": 0, "unique_frozen": 0, "unique_shadow": 0,
              "irrelevant_C_changes_verdict": 0, "irrelevant_C_creates_unique": 0,
              "unavailable_differs_from_absent": 0, "unavailable_creates_unique": 0,
              "order_changes_anything": 0, "duplicate_changes_decision": 0,
              "duplicate_changes_trace": 0,
              "shadow_irrelevant_C_creates_unique": 0,
              "shadow_unavailable_creates_unique": 0}
    unique_when = []
    for sa, sb, sc in itertools.product(opts, repeat=3):
        recs = [mk[k](s) for k, s in zip("ABC", (sa, sb, sc)) if s is not None]
        counts["configs"] += 1
        a = attribute(recs)
        s = shadow_attribute(recs, ())[0]
        counts["unique_frozen"] += a.verdict == A_UNIQUE
        counts["unique_shadow"] += s.verdict == A_UNIQUE
        if a.verdict == A_UNIQUE:
            unique_when.append({"A": getattr(sa, "value", None), "B": getattr(sb, "value", None),
                                "C": getattr(sc, "value", None), "shadow": s.verdict})
        if sc is not None:
            no_c = [r for r in recs if r.domain != "D3"]
            a2 = attribute(no_c)
            if sc is OS.NOMINAL and a2.verdict != a.verdict:
                counts["irrelevant_C_changes_verdict"] += 1
                if a.verdict == A_UNIQUE:
                    counts["irrelevant_C_creates_unique"] += 1
            if sc is OS.NOMINAL and shadow_attribute(recs, ())[0].verdict == A_UNIQUE and \
                    shadow_attribute(no_c, ())[0].verdict != A_UNIQUE:
                counts["shadow_irrelevant_C_creates_unique"] += 1
        for k, st in zip("ABC", (sa, sb, sc)):
            if st is OS.UNAVAILABLE:
                gone = [r for r in recs if not r.domain.endswith(str("ABC".index(k) + 1))]
                if aproj(attribute(gone)) != aproj(a):
                    counts["unavailable_differs_from_absent"] += 1
                if a.verdict == A_UNIQUE and attribute(gone).verdict != A_UNIQUE:
                    counts["unavailable_creates_unique"] += 1
                if s.verdict == A_UNIQUE and shadow_attribute(gone, ())[0].verdict != A_UNIQUE:
                    counts["shadow_unavailable_creates_unique"] += 1
        base = a.to_dict()
        for perm in itertools.permutations(recs):
            if attribute(list(perm)).to_dict() != base:
                counts["order_changes_anything"] += 1
        for r in recs:
            d = attribute(recs + [r])
            if aproj(d) != aproj(a):
                counts["duplicate_changes_decision"] += 1
            elif d.to_dict() != base:
                counts["duplicate_changes_trace"] += 1
    counts["frozen_unique_configurations"] = unique_when
    return counts


def _enum_generic(name, dims, build, symptom, subject, cfg=AIR):
    """Every combination of `dims`. Each record set is reasoned on as given,
    reversed, and with each record duplicated; every UNAVAILABLE record is
    checked against both of its completions (k3_check)."""
    spec = next(x for x in cfg.symptoms if x.symptom_id == symptom)
    keys = [k for k, _v in dims]
    c = {"configs": 0, "symptom_present": 0, "configs_with_unavailable": 0,
         "reverse_order_changes": 0, "duplicate_changes": 0,
         "shadow_reverse_order_changes": 0, "shadow_duplicate_changes": 0,
         "verdicts_frozen": {}, "verdicts_shadow": {}, "examples": []}
    for tag in ("frozen", "shadow"):
        for k in ("UNKNOWN_REFUTES", "UNKNOWN_CONFIRMS", "UNKNOWN_SUPPORTED"):
            c[f"{tag}_{k}"] = 0

    def pick(out):
        return next((x for x in out[0] if x.symptom == symptom and x.subject == subject), None)

    def run(tag, recs):
        return pick(frozen(recs, cfg) if tag == "frozen" else shadow(recs, cfg)[0])

    for combo in itertools.product(*[v for _k, v in dims]):
        d = dict(zip(keys, combo))
        recs = build(d)
        c["configs"] += 1
        f, s_ = run("frozen", recs), run("shadow", recs)
        c["symptom_present"] += f is not None
        vf = f.verdict if f else "NONE"
        vs = s_.verdict if s_ else "NONE"
        c["verdicts_frozen"][vf] = c["verdicts_frozen"].get(vf, 0) + 1
        c["verdicts_shadow"][vs] = c["verdicts_shadow"].get(vs, 0) + 1
        fp = lproj(f) if f else None
        sp = lproj(s_) if s_ else None
        rv = run("frozen", list(reversed(recs)))
        c["reverse_order_changes"] += int((lproj(rv) if rv else None) != fp)
        rv = run("shadow", list(reversed(recs)))
        c["shadow_reverse_order_changes"] += int((lproj(rv) if rv else None) != sp)
        for r in recs:
            g = run("frozen", recs + [r])
            c["duplicate_changes"] += int((lproj(g) if g else None) != fp)
            g = run("shadow", recs + [r])
            c["shadow_duplicate_changes"] += int((lproj(g) if g else None) != sp)
        unk = [k for k in keys if d[k] is OS.UNAVAILABLE]
        if not unk:
            continue
        c["configs_with_unavailable"] += 1
        comps = []
        for fill in itertools.product((OS.NOMINAL, OS.VIOLATED), repeat=len(unk)):
            comps.append(build(d | dict(zip(unk, fill))))
        for tag, base in (("frozen", f), ("shadow", s_)):
            flags = k3_check(spec, base, [run(tag, cr) for cr in comps])
            for k, v in flags.items():
                c[f"{tag}_{k}"] += int(v)
            if tag == "frozen" and any(flags.values()) and len(c["examples"]) < 6:
                c["examples"].append({"config": {k: getattr(v, "value", v) for k, v in d.items()},
                                      "flags": [k for k, v in flags.items() if v],
                                      "with_unavailable": lproj(base) if base else None})
    c["name"] = name
    return c


def n3_command_no_response():
    S3 = (None, OS.NOMINAL, OS.VIOLATED, OS.UNAVAILABLE)
    dims = [("command_path", (None, OS.NOMINAL, OS.VIOLATED)),
            ("electrical", S3), ("mechanical", S3), ("physical", S3),
            ("battery", S3), ("esc_can", S3)]
    deps = ("POWER/battery", "COMMUNICATION/esc_can")

    def build(d):
        out = []
        code = {"command_path": "ACT_COMMAND_NOT_TRANSMITTED",
                "electrical": "ACT_NO_ELECTRICAL_RESPONSE", "mechanical": "ACT_STALLED",
                "physical": "ACT_NO_PHYSICAL_RESPONSE"}
        rel = {"command_path": "actuation.command_path", "electrical": "actuation.electrical_response",
               "mechanical": "actuation.mechanical_response", "physical": "actuation.physical_response"}
        for k in ("command_path", "electrical", "mechanical", "physical"):
            st = d[k]
            if st is not None:
                out.append(rec("ACTUATION", "motor_0", rel[k], st, deps=deps,
                               codes=(code[k],) if st is OS.VIOLATED else ()))
        if d["battery"] is not None:
            out.append(rec("POWER", "battery", "power.source_health", d["battery"]))
        if d["esc_can"] is not None:
            out.append(rec("COMMUNICATION", "esc_can", "comm.link_state", d["esc_can"]))
        return out
    return _enum_generic("COMMAND_NO_RESPONSE", dims, build, "COMMAND_NO_RESPONSE", "motor_0")


def n4_output_stale():
    S4 = (None, OS.NOMINAL, OS.VIOLATED, OS.UNAVAILABLE)
    S3 = (None, OS.NOMINAL, OS.VIOLATED)
    dims = [("link", S4), ("process", S4), ("transport", S3), ("processing", S3),
            ("rate", S3), ("clock", S3)]

    def build(d):
        out = [rec("TIMING", "nav_solution", "timing.end_to_end", OS.VIOLATED,
                   deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial"))]
        if d["link"] is not None:
            out.append(rec("COMMUNICATION", "gnss_serial", "comm.link_state", d["link"]))
        if d["process"] is not None:
            out.append(rec("COMPUTE", "state_estimator", "compute.process_alive", d["process"]))
        for k, comp, rel in (("transport", "nav_solution.transport_delay", "timing.segment_budget"),
                             ("processing", "nav_solution.processing_delay", "timing.segment_budget"),
                             ("rate", "nav_solution.sensor_slow", "timing.rate"),
                             ("clock", "nav_solution", "timing.clock_consistency")):
            if d[k] is not None:
                out.append(rec("TIMING", comp, rel, d[k]))
        return out
    return _enum_generic("OUTPUT_STALE", dims, build, "OUTPUT_STALE", "nav_solution")


def n5_position_irrelevance():
    """PRECISION_NAVIGATION with every combination of its declared evidence,
    against every combination of three components it does not use."""
    S4 = (None, OS.NOMINAL, OS.VIOLATED, OS.UNAVAILABLE)
    rel_dims = [("v1_1", (OS.NOMINAL, OS.VIOLATED)), ("nav_channel", (None, OS.NOMINAL, OS.VIOLATED)),
                ("gnss_link", S4), ("estimator", S4)]
    irr_dims = [("logger", S4), ("radio", S4), ("tlm_channel", (None, OS.NOMINAL, OS.VIOLATED))]
    nav_fns = ("PRECISION_NAVIGATION",)

    def build(d):
        out = [rec("SENSOR", "v1_1.PRECISION_NAVIGATION", "v1_1.function_eligibility",
                   d["v1_1"], attributable=False)]
        if d["nav_channel"] is not None:
            out.append(rec("TIMING", "nav_solution", "timing.end_to_end", d["nav_channel"],
                           deps=("COMPUTE/state_estimator", "COMMUNICATION/gnss_serial"), fns=nav_fns))
        if d["gnss_link"] is not None:
            out.append(rec("COMMUNICATION", "gnss_serial", "comm.link_state", d["gnss_link"], fns=("SENSING",)))
        if d["estimator"] is not None:
            out.append(rec("COMPUTE", "state_estimator", "compute.deadline_met", d["estimator"], fns=nav_fns))
        if d["logger"] is not None:
            out.append(rec("COMPUTE", "logger", "compute.deadline_met", d["logger"], fns=("LOGGING",)))
        if d["radio"] is not None:
            out.append(rec("COMMUNICATION", "telemetry_radio", "comm.link_state", d["radio"], fns=("TELEMETRY",)))
        if d["tlm_channel"] is not None:
            out.append(rec("TIMING", "telemetry_downlink", "timing.end_to_end", d["tlm_channel"],
                           deps=("COMMUNICATION/telemetry_radio",), fns=("TELEMETRY",)))
        return out

    def pick(out):
        for x in out[0]:
            if x.symptom == "POSITION_UNAVAILABLE" and x.subject == "PRECISION_NAVIGATION":
                return lproj(x)
        return None
    res = {"relevant_configs": 0, "irrelevant_variants_per_config": 0,
           "frozen_configs_where_irrelevant_evidence_changes_result": 0,
           "frozen_irrelevant_creates_supported": 0,
           "shadow_configs_where_irrelevant_evidence_changes_result": 0,
           "examples": []}
    rk = [k for k, _ in rel_dims]
    ik = [k for k, _ in irr_dims]
    for rcombo in itertools.product(*[v for _k, v in rel_dims]):
        res["relevant_configs"] += 1
        rd = dict(zip(rk, rcombo))
        f0 = pick(frozen(build(rd | {k: None for k in ik}), AIR))
        s0 = pick(shadow(build(rd | {k: None for k in ik}), AIR)[0])
        fchg = schg = False
        for icombo in itertools.product(*[v for _k, v in irr_dims]):
            d = rd | dict(zip(ik, icombo))
            f1 = pick(frozen(build(d), AIR))
            s1 = pick(shadow(build(d), AIR)[0])
            if f1 != f0:
                if not fchg and len(res["examples"]) < 6:
                    res["examples"].append({"relevant": {k: getattr(v, "value", v) for k, v in rd.items()},
                                            "irrelevant": {k: getattr(v, "value", v) for k, v in zip(ik, icombo)},
                                            "without_irrelevant": f0, "with_irrelevant": f1})
                fchg = True
                if f1 and f1["verdict"] == SUPPORTED and (f0 is None or f0["verdict"] != SUPPORTED):
                    res["frozen_irrelevant_creates_supported"] += 1
            schg = schg or (s1 != s0)
        res["irrelevant_variants_per_config"] = 4 * 4 * 3
        res["frozen_configs_where_irrelevant_evidence_changes_result"] += fchg
        res["shadow_configs_where_irrelevant_evidence_changes_result"] += schg
    return res


# ============================================================== X section
def section_X():
    raw = XSYS_STAGE1.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    X = {"stage1_sha256": sha, "stage1_sha256_matches_seal": sha == XSYS_STAGE1_SHA}
    if str(XSYS_PIPELINE) not in sys.path:
        sys.path.insert(0, str(XSYS_PIPELINE))
    import stage1_evidence as S1  # noqa: E402
    import stage2_score as S2  # noqa: E402
    import xsys_v2_adapter as XA  # noqa: E402
    data = json.loads(raw)
    results = json.loads(XSYS_RESULTS.read_text())
    by_opaque = {t["opaque_id"]: t for t in results["trials"].values()}
    cfg = Cfg((XA.SPEC,), XA.PREDICATES, ())
    fixes = {"C2": ("C2",), "C4": ("C4",), "C6": ("C6",), "ALL_LOCALIZATION_FIXES": ("C2", "C4", "C6")}
    n = equal = 0
    diffs = {k: 0 for k in fixes}
    outcome_diffs = {k: 0 for k in fixes}
    raised = nonbool = 0
    states = {}
    coll = {"shared_confirmer_only": 0, "specific_confirmer": 0}
    coll_primary = {"shared_confirmer_only": 0, "specific_confirmer": 0}
    cf = {"slots_changed": 0, "primary_cell_slots_changed": 0, "primary_outcomes_changed": 0}
    for oid, t in sorted(data["trials"].items()):
        truth = by_opaque[oid]
        for vc in sorted(t["verdicts"]):
            cp, v = vc.split("/")
            for subj in sorted(t["features"]):
                f = t["features"][subj]
                rpm, dyn, ctrl, w = S1.plan(v, cp, f)
                stats = {"L": f["L_T1"] if cp == "C1" else f["L_T3"],
                         "D": f["D_T3"] if v == "V4_INVALID_WINDOW" else f["D_T1"], "C": f["C_T3"]}
                recs = XA.records_for(subj, rpm, dyn, ctrl, stats, w)
                for r in recs:
                    states[r.observation_state.value] = states.get(r.observation_state.value, 0) + 1
                loc = XA.localize_subject(recs, subj)
                got = None if loc is None else json.loads(json.dumps(loc.to_dict(), default=float))
                n += 1
                equal += int(got == t["verdicts"][vc][subj])
                index = EvidenceIndex(recs)
                for pid, p in XA.PREDICATES.items():
                    try:
                        val = p.test(index, subj)
                    except Exception:  # noqa: BLE001
                        raised += 1
                        continue
                    if val is not None and type(val) is not bool:
                        nonbool += 1
                if loc is not None:
                    for c in collisions(XA.SPEC, loc):
                        k = "specific_confirmer" if c["specific_confirmers"] else "shared_confirmer_only"
                        coll[k] += 1
                        if vc == "C3/V3_TEMPORAL" and subj == "motor_0":
                            coll_primary[k] += 1
                for fx, fl in fixes.items():
                    sh = shadow(recs, cfg, fixes=fl)[0][0]
                    sh = [x for x in sh if x.subject == subj]
                    sp = lproj(sh[0]) if sh else None
                    fp = lproj(loc) if loc else None
                    if sp != fp:
                        diffs[fx] += 1
                    if subj == "motor_0" and truth["kind"] in ("A", "B"):
                        th = S2.TRUTH_H[truth["kind"]]
                        o_frozen = S2.outcome_symptomatic(None if loc is None else loc.to_dict(), th)
                        o_shadow = S2.outcome_symptomatic(None if not sh else sh[0].to_dict(), th)
                        outcome_diffs[fx] += int(o_frozen != o_shadow)
                # counterfactual, NOT proposed: keep a hypothesis that a
                # SPECIFIC confirmer supports instead of eliminating it
                if loc is not None and subj == "motor_0":
                    cfl = counterfactual_disagreement(XA.SPEC, loc)
                    if cfl != lproj(loc):
                        cf["slots_changed"] += 1
                        if vc == "C3/V3_TEMPORAL":
                            cf["primary_cell_slots_changed"] += 1
                            if truth["kind"] in ("A", "B"):
                                th = S2.TRUTH_H[truth["kind"]]
                                o1 = S2.outcome_symptomatic(loc.to_dict(), th)
                                o2 = outcome_from_proj(cfl, th)
                                cf["primary_outcomes_changed"] += int(o1 != o2)
    X.update({"slots": n, "frozen_replay_identical_to_sealed": equal,
              "record_states_seen": states,
              "predicate_raises": raised, "predicate_non_bool_returns": nonbool,
              "shadow_decision_diffs_by_fix": diffs,
              "shadow_motor0_outcome_diffs_by_fix": outcome_diffs,
              "confirm_and_refute_all_slots": coll,
              "confirm_and_refute_primary_cell_motor0": coll_primary,
              "counterfactual_disagreement_preserving_successor": cf,
              "primary_record": json.loads((XSYS_RESULTS.parent / "PRIMARY_RESULT_RECORD.json").read_text())})
    return X


def counterfactual_disagreement(spec, loc):
    """NOT A PROPOSAL. A successor that refuses to eliminate a hypothesis a
    SPECIFIC confirmer supports, and calls the result a disagreement."""
    keep = {c["hypothesis"] for c in collisions(spec, loc) if c["specific_confirmers"]}
    if not keep:
        return lproj(loc)
    rej = sorted(h for h, _ in loc.rejected if h not in keep)
    sup = sorted(set(loc.supported) | keep)
    return {"verdict": "EVIDENCE_DISAGREEMENT", "supported": sup,
            "unresolved": list(loc.unresolved), "rejected": rej}


def outcome_from_proj(p, truth_h):
    if truth_h in p["rejected"]:
        return "WRONG"
    if p["verdict"] == SUPPORTED:
        return "UNIQUE_CORRECT" if p["supported"] == [truth_h] else "WRONG"
    if p["verdict"] in (AMBIGUOUS, "EVIDENCE_DISAGREEMENT"):
        return "AMBIGUOUS_CORRECT"
    return p["verdict"]


# ======================================================== shipped effects
def section_SH(runs):
    """What each proposed fix, alone and together, changes on the final tick
    of every shipped scenario. First, the instrument check: with no fix
    switched on, the shadow must reproduce the frozen output on every tick."""
    ticks = mism = 0
    for name, (_sc, engine, res) in sorted(runs.items()):
        cfg = cfg_of(engine)
        for t in res:
            ticks += 1
            got = shadow(t.records, cfg, fixes=())[0]
            ref = (t.localizations, t.attribution)
            if decision(got) != decision(ref) or trace(got) != trace(ref):
                mism += 1
    out = {"IDENTITY_CHECK": {"ticks": ticks, "mismatches_with_no_fix": mism}}
    all_ticks = {}
    for fx in ALL_FIXES + ("ALL",):
        fl = ALL_FIXES if fx == "ALL" else (fx,)
        n_loc = n_attr = n_trace_only = 0
        for name, (_sc, engine, res) in sorted(runs.items()):
            cfg = cfg_of(engine)
            for t in res:
                got = shadow(t.records, cfg, fixes=fl)[0]
                d0, d1 = decision((t.localizations, t.attribution)), decision(got)
                n_loc += int(d0["loc"] != d1["loc"])
                n_attr += int(d0["attr"] != d1["attr"])
                n_trace_only += int(d0 == d1 and trace((t.localizations, t.attribution)) != trace(got))
        all_ticks[fx] = {"ticks_with_localization_change": n_loc,
                         "ticks_with_attribution_change": n_attr,
                         "ticks_with_trace_only_change": n_trace_only}
    out["ALL_TICKS"] = {"ticks": ticks, "by_fix": all_ticks}
    for fx in ALL_FIXES + ("ALL",):
        fl = ALL_FIXES if fx == "ALL" else (fx,)
        changed = {}
        for name, (_sc, engine, res) in sorted(runs.items()):
            fin = res[-1]
            cfg = cfg_of(engine)
            d0 = decision((fin.localizations, fin.attribution))
            d1 = decision(shadow(fin.records, cfg, fixes=fl)[0])
            units = changed_units(d0, d1)
            if units:
                changed[name] = {u: [d0["attr"] if u == "ATTR" else d0["loc"].get(u),
                                     d1["attr"] if u == "ATTR" else d1["loc"].get(u)] for u in units}
        out[fx] = {"scenarios_changed": len(changed), "changes": changed}
    return out


def main():
    results = {"probe": "csia_semantic_correctness", "seed": SEED, "ticks": TICKS}
    results["R"] = section_R()
    E, runs = section_E()
    results["E"] = E
    results["P"] = section_P(runs)
    results["N"] = section_N()
    results["X"] = section_X()
    results["SH"] = section_SH(runs)
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({"wrote": str(OUT.relative_to(REPO)),
                      "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
