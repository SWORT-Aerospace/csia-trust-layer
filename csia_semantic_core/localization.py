"""Successor localization: the frozen `localize()`, labelled and traced.

**The elimination rule is not changed.** Every localization here is exactly
what frozen `csia.v2.localization.localize()` returns when it is given the
successor index and the successor predicate table. That object is kept
whole, as `LocalizationResult.v2`, and it is the 2.0.0 view.

What 2.1.0 adds, none of which moves a hypothesis:

C5: OUTCOME LABELS (fixes SC-09 and SC-10)
------------------------------------------
The 2.0.0 verdict UNSUPPORTED carried two meanings. It is split:

| 2.0.0 verdict | 2.1.0 outcome |
|---|---|
| UNSUPPORTED, no survivor | NO_CONSISTENT_HYPOTHESIS |
| UNSUPPORTED, one survivor nothing confirms | INSUFFICIENT_EVIDENCE, with reason UNCONFIRMED_SURVIVOR, or UNMODELLED when the survivor is a hypothesis the platform cannot decide |
| SUPPORTED, AMBIGUOUS | unchanged |

EVALUATION STATUS
-----------------
Beside the outcome, and never instead of it:

| status | meaning |
|---|---|
| PREDICATE_FAULT | a predicate raised or returned a non-bool (C4). Listed in `predicate_errors` |
| EVIDENCE_UNAVAILABLE | no fault, and some predicate could not look. Listed in `evidence_unavailable` |
| COMPLETE | every predicate the symptom names was measured |

In 2.0.0 a fault and a missing input were both just "unmeasurable". In
2.1.0 `evidence_unavailable` excludes the faulted ids.

C7: TRACE (fixes SC-16 and SC-21)
---------------------------------
- `confirmed_and_refuted`: a hypothesis rejected although a predicate
  confirming it was True. Its confirmers are split into those specific to it
  and those it shares. The rejection stands.
- `supported_with_unmeasured_refuters`: the supported hypothesis's own
  refuters that could not look.

Plus the evidence each predicate read, set aside or could not read.

R-1: DEPENDENCY-SENSITIVE PREDICATE-FAULT POLICY (2.1.1, FAULT_POLICY_B)
-----------------------------------------------------------------------
Off by default; 2.1.0 reports a fault and keeps every verdict (policy A).
With it on, every failed predicate is checked against every hypothesis of
the localization that names it, and asked one question: **could the failed
predicate have changed this conclusion?** Each answer is one `fault_impact`
entry: the failed predicate, the hypothesis, the role (REFUTER or
CONFIRMER), the dependency (MATERIAL or NOT_MATERIAL) and why, and the
action taken.

| role | hypothesis is | dependency | action |
|---|---|---|---|
| REFUTER | rejected by another refuter | NOT_MATERIAL | none |
| REFUTER | the SUPPORTED one | MATERIAL: had it been True it would have rejected it | SUPPORTED_WITHHELD |
| REFUTER | a survivor of a result that is not SUPPORTED | MATERIAL: its survival may rest on the fault | none: nothing was established |
| CONFIRMER | rejected | NOT_MATERIAL | none |
| CONFIRMER | supported, confirmed by another true confirmer (any-of) | NOT_MATERIAL | none |
| CONFIRMER | supported only through it | MATERIAL | SUPPORTED_WITHHELD |
| CONFIRMER | unresolved | MATERIAL: it may be why nothing confirmed it | none: nothing was established |
| either | unmodelled | NOT_MATERIAL: never decided by any predicate | none |

Under the frozen rule a None never rejects and never confirms, so a fault
can only widen a result, except in one way: a failed refuter of the
hypothesis that ends SUPPORTED. That SUPPORTED becomes the outcome
WITHHELD_PREDICATE_FAULT. Its survivors are unchanged. Its 2.0 view reads
AMBIGUOUS, so a downstream consumer treats it as "no conclusion", never as
NO_CONSISTENT. A failed predicate that a localization does not read leaves
that localization untouched: it cannot have changed its conclusion. The
failure stays visible in `predicate_errors` and `evaluation` either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from csia.v2.localization import (AMBIGUOUS, SUPPORTED, UNSUPPORTED,
                                  Localization, localize)

NO_CONSISTENT_HYPOTHESIS = "NO_CONSISTENT_HYPOTHESIS"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
OUTCOMES = (SUPPORTED, AMBIGUOUS, NO_CONSISTENT_HYPOTHESIS,
            INSUFFICIENT_EVIDENCE)
#: 2.1.1 (R-1): a SUPPORTED that a material predicate fault leaves
#: unestablished.
WITHHELD_PREDICATE_FAULT = "WITHHELD_PREDICATE_FAULT"
REVISED_OUTCOMES = OUTCOMES + (WITHHELD_PREDICATE_FAULT,)

REFUTER = "REFUTER"
CONFIRMER = "CONFIRMER"
MATERIAL = "MATERIAL"
NOT_MATERIAL = "NOT_MATERIAL"
SUPPORTED_WITHHELD = "SUPPORTED_WITHHELD"
NO_ACTION = "NONE"

UNCONFIRMED_SURVIVOR = "UNCONFIRMED_SURVIVOR"
UNMODELLED = "UNMODELLED"

COMPLETE = "COMPLETE"
EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
PREDICATE_FAULT = "PREDICATE_FAULT"


@dataclass(frozen=True)
class PredicateError:
    """One predicate fault, named. No traceback."""

    predicate: str
    evaluated_as: tuple
    subject: str
    error_class: str
    symptom: str
    hypotheses: tuple

    def to_dict(self) -> dict:
        return {"predicate": self.predicate,
                "evaluated_as": list(self.evaluated_as),
                "subject": self.subject, "error_class": self.error_class,
                "context": {"symptom": self.symptom,
                            "hypotheses": list(self.hypotheses)}}


@dataclass(frozen=True)
class LocalizationResult:
    v2: Localization
    outcome: str
    outcome_reason: str | None
    evaluation: str
    evidence_unavailable: tuple
    predicate_errors: tuple
    trace: dict = field(default_factory=dict)
    #: R-1 (2.1.1): one entry per (failed predicate, hypothesis naming it).
    #: Empty under 2.1.0.
    fault_impact: tuple = ()

    @property
    def key(self) -> str:
        return f"{self.v2.symptom}|{self.v2.subject}"

    @property
    def symptom(self):
        return self.v2.symptom

    @property
    def subject(self):
        return self.v2.subject

    @property
    def supported(self):
        return self.v2.supported

    @property
    def unresolved(self):
        return self.v2.unresolved

    def to_dict(self) -> dict:
        v = self.v2
        return {
            "symptom": v.symptom, "subject": v.subject,
            "outcome": self.outcome, "outcome_reason": self.outcome_reason,
            "evaluation": self.evaluation,
            "supported": list(v.supported), "unresolved": list(v.unresolved),
            "rejected": [{"hypothesis": h, "by": p} for h, p in v.rejected],
            "unmodelled": list(v.unmodelled),
            "initial_candidates": list(v.initial_candidates),
            "evidence": list(v.evidence),
            "refuting_evidence": list(v.refuting_evidence),
            "evidence_unavailable": list(self.evidence_unavailable),
            "predicate_errors": [e.to_dict() for e in self.predicate_errors],
            "common_cause": v.common_cause,
            "trace": self.trace,
        }

    def to_v2_0_dict(self) -> dict:
        return self.v2.to_dict()


def outcome_of(loc: Localization, spec) -> tuple:
    """C5. Returns (outcome, reason)."""
    if loc.verdict != UNSUPPORTED:
        return loc.verdict, None
    if not loc.unresolved:
        return NO_CONSISTENT_HYPOTHESIS, None
    only = loc.unresolved[0]
    unmodelled = any(h.hypothesis_id == only and h.unmodelled
                     for h in spec.hypotheses)
    return INSUFFICIENT_EVIDENCE, (UNMODELLED if unmodelled
                                   else UNCONFIRMED_SURVIVOR)


def _why(loc, outcome, reason):
    if outcome == SUPPORTED:
        return "ONE_CONFIRMED_SURVIVOR"
    if outcome == NO_CONSISTENT_HYPOTHESIS:
        return "EVERY_DECLARED_HYPOTHESIS_REJECTED"
    if outcome == INSUFFICIENT_EVIDENCE:
        return ("ONE_SURVIVOR_THE_PLATFORM_CANNOT_DECIDE"
                if reason == UNMODELLED else "ONE_SURVIVOR_NOTHING_CONFIRMS")
    if loc.supported:
        return "SEVERAL_SURVIVORS_SOME_CONFIRMED"
    return "SEVERAL_SURVIVORS_NONE_CONFIRMED"


def confirmed_and_refuted(spec, loc) -> list:
    """C7. Hypotheses rejected although a predicate that confirms them was
    True. `specific_confirmers` confirm only this hypothesis;
    `shared_confirmers` confirm others too. Trace only."""
    vals = loc.detail.get("predicate_values", {})
    confirms: dict = {}
    for h in spec.hypotheses:
        for p in h.confirmed_by:
            confirms.setdefault(p, set()).add(h.hypothesis_id)
    by_id = {h.hypothesis_id: h for h in spec.hypotheses}
    out = []
    for hid, by in loc.rejected:
        hyp = by_id[hid]
        true = [p for p in hyp.confirmed_by if vals.get(p) is True]
        specific = [p for p in true if confirms[p] == {hid}]
        shared = [p for p in true if confirms[p] != {hid}]
        if true:
            out.append({"hypothesis": hid, "refuted_by": by,
                        "specific_confirmers": specific,
                        "shared_confirmers": shared})
    return out


def supported_with_unmeasured_refuters(spec, loc) -> list:
    """C7. The supported hypothesis's own refuters that could not look."""
    vals = loc.detail.get("predicate_values", {})
    out = []
    for h in spec.hypotheses:
        if h.hypothesis_id in loc.supported:
            missing = [p for p in h.refuted_by if vals.get(p) is None]
            if missing:
                out.append({"hypothesis": h.hypothesis_id,
                            "unmeasured_refuters": missing})
    return out


def _errors_for(spec, subject, raw) -> tuple:
    """Collapse the raw error log of one localization: one entry per
    (predicate, subject, error class), with every id it made None."""
    grouped: dict = {}
    for pid, evaluated_as, subj, err in raw:
        grouped.setdefault((pid, subj, err), set()).add(evaluated_as)
    out = []
    for (pid, subj, err), ids in sorted(grouped.items()):
        hyps = sorted({h.hypothesis_id for h in spec.hypotheses
                       for p in tuple(h.confirmed_by) + tuple(h.refuted_by)
                       if p in ids})
        out.append(PredicateError(pid, tuple(sorted(ids)), subj, err,
                                  spec.symptom_id, tuple(hyps)))
    return tuple(out)


def _evidence_trace(evaluations, detailed) -> dict:
    per, used, unknown, ignored, conflicts, gaps = {}, set(), set(), {}, set(), set()
    for ev in evaluations:
        per[ev["predicate"]] = {k: ev[k] for k in
                                ("value", "read", "ignored", "conflicts",
                                 "scope_gaps") if ev[k] or k == "value"}
        target = used if ev["value"] is True or ev["value"] is False else unknown
        target.update(ev["read"])
        ignored.update(ev["ignored"])
        conflicts.update(ev["conflicts"])
        gaps.update(ev["scope_gaps"])
    out = {"evidence_used": sorted(used),
           "unknown_inputs": sorted(unknown - used),
           "ignored": dict(sorted((k, v) for k, v in ignored.items()
                                  if k not in used)),
           "conflicts_not_read": sorted(conflicts),
           "scope_gaps": sorted(gaps)}
    if detailed:
        out["predicates"] = dict(sorted(per.items()))
    return out


def _impact(h, role, loc, failed):
    """R-1: could a failed predicate in this `role` have changed `h`'s part in
    the conclusion? -> (dependency, why, action)."""
    hid = h.hypothesis_id
    vals = loc.detail.get("predicate_values", {})
    rejected = dict(loc.rejected)
    established = loc.verdict == SUPPORTED and hid in loc.supported
    if h.unmodelled:
        return NOT_MATERIAL, "UNMODELLED_HYPOTHESIS_IS_NEVER_DECIDED", NO_ACTION
    if hid in rejected:
        return (NOT_MATERIAL,
                f"REJECTED_BY_MEASURED_REFUTER:{rejected[hid]}", NO_ACTION)
    if role == REFUTER:
        if established:
            return (MATERIAL, "HAD_IT_BEEN_TRUE_IT_WOULD_HAVE_REJECTED_THE_"
                    "SUPPORTED_HYPOTHESIS", SUPPORTED_WITHHELD)
        return (MATERIAL, "THIS_SURVIVOR_MAY_REST_ON_THE_FAILED_REFUTER",
                NO_ACTION)
    if hid in loc.supported:
        others = [p for p in h.confirmed_by if p not in failed]
        needed = h.confirm_requires_all or not any(
            vals.get(p) is True for p in others)
        if not needed:
            return NOT_MATERIAL, "CONFIRMED_BY_ANOTHER_TRUE_CONFIRMER", NO_ACTION
        return (MATERIAL, "CONFIRMATION_DEPENDS_ON_THE_FAILED_CONFIRMER",
                SUPPORTED_WITHHELD if established else NO_ACTION)
    return MATERIAL, "MAY_BE_WHY_NOTHING_CONFIRMED_IT", NO_ACTION


def fault_impact(spec, loc, errors) -> tuple:
    """R-1: one entry per (failed predicate id, hypothesis that names it)."""
    failed = {}
    for e in errors:
        for i in e.evaluated_as:
            failed[i] = e.predicate
    out = []
    for h in spec.hypotheses:
        for role, ids in ((REFUTER, h.refuted_by), (CONFIRMER, h.confirmed_by)):
            for pid in ids:
                if pid not in failed:
                    continue
                dep, why, action = _impact(h, role, loc, failed)
                out.append({"predicate_fault": True, "predicate": failed[pid],
                            "evaluated_as": pid,
                            "hypothesis": h.hypothesis_id, "role": role,
                            "dependency": dep, "why": why, "action": action})
    return tuple(out)


def localize_2_1(spec, index, subject, predicates,
                 detailed_trace: bool = True,
                 fault_policy_b: bool = False) -> LocalizationResult:
    """One symptom on one subject. `index` is a `SuccessorIndex` and
    `predicates` a successor table (`successor_predicate_table`).
    `fault_policy_b` is R-1 (2.1.1)."""
    err0 = len(index.predicate_errors)
    ev0 = len(index.evaluations)
    loc = localize(spec, index, subject, predicates)
    errors = _errors_for(spec, subject, index.predicate_errors[err0:])
    faulted = {i for e in errors for i in e.evaluated_as}
    unavailable = tuple(p for p in loc.unmeasurable if p not in faulted)
    evaluation = (PREDICATE_FAULT if errors
                  else EVIDENCE_UNAVAILABLE if unavailable else COMPLETE)
    outcome, reason = outcome_of(loc, spec)
    impact = fault_impact(spec, loc, errors) if (fault_policy_b
                                                 and errors) else ()
    withheld = [e for e in impact if e["action"] == SUPPORTED_WITHHELD]
    trace = {"why": _why(loc, outcome, reason),
             "confirmed_and_refuted": confirmed_and_refuted(spec, loc),
             "supported_with_unmeasured_refuters":
                 supported_with_unmeasured_refuters(spec, loc)}
    if withheld:
        outcome = WITHHELD_PREDICATE_FAULT
        reason = ("FAILED_REFUTER_OF_SUPPORTED_HYPOTHESIS"
                  if any(e["role"] == REFUTER for e in withheld)
                  else "FAILED_CONFIRMER_OF_SUPPORTED_HYPOTHESIS")
        trace["why"] = "SUPPORTED_WITHHELD_A_FAILED_PREDICATE_COULD_HAVE_CHANGED_IT"
        trace["withheld_because"] = [
            {"predicate": e["predicate"], "evaluated_as": e["evaluated_as"],
             "hypothesis": e["hypothesis"], "role": e["role"]}
            for e in withheld]
        loc = replace(loc, verdict=AMBIGUOUS,
                      detail=dict(loc.detail, why="successor gate: "
                                  + WITHHELD_PREDICATE_FAULT))
    if impact:
        trace["fault_impact"] = [dict(e) for e in impact]
    if index.tracing:
        trace.update(_evidence_trace(index.evaluations[ev0:], detailed_trace))
    return LocalizationResult(loc, outcome, reason, evaluation, unavailable,
                              errors, trace, impact)


def localize_all_2_1(specs, index, predicates,
                     detailed_trace: bool = True,
                     fault_policy_b: bool = False) -> tuple:
    """Every symptom present in the tick, in the frozen order."""
    out = []
    for spec in specs:
        for subject in spec.detect(index):
            out.append(localize_2_1(spec, index, subject, predicates,
                                    detailed_trace, fault_policy_b))
    return tuple(out)
