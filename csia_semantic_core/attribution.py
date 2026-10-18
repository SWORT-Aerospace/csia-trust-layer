"""Successor attribution: the frozen `attribute()`, gated and traced.

Frozen `csia.v2.attribution.attribute()` runs unchanged. Under C6 it runs on
the de-duplicated records. The successor adds two gates, C1 and F2. **Each
can only turn UNIQUE into AMBIGUOUS.** Neither creates a UNIQUE, names a
different candidate or removes one.

C1: RELEVANCE-GATED DISCRIMINATOR (fixes SC-01)
-----------------------------------------------
In 2.0.0 any NOMINAL record from another domain licensed UNIQUE. In 2.1.0,
UNIQUE for the single adverse attributable component *c* also requires:

1. *c* has at least one **declared alternative**. These are the nodes *c*
   transitively depends on, plus the components implicated by a relation
   spanning *c*'s domain. Both are structures `attribute()` already walks.
2. Every declared alternative is **affirmatively NOMINAL**: at least one
   NOMINAL attributable record, and no UNAVAILABLE or adverse record.
3. At least one relevant discriminator comes from a domain other than *c*'s.
   That keeps the frozen cross-domain rule.

Otherwise the outcome is AMBIGUOUS, with one of these reasons:

- NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED;
- DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL;
- NO_RELEVANT_DISCRIMINATOR_FROM_ANOTHER_DOMAIN.

Relevance is never "a different domain", and it is never inferred from a
record being nominal. Adding or removing a record about a component that is
not a declared alternative cannot change the outcome.

F2: LOCALIZATION AGREEMENT (fixes SC-02)
----------------------------------------
UNIQUE is withheld while a localization in the same tick, on the
candidate's own component, still keeps a hypothesis from another domain,
whether supported or unresolved. The reason is
SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN, and the retained hypotheses
are listed. The two stages stay separate: localization is not merged into
attribution, and attribution does not rewrite a localization.

C5: IMPLICATED COMPONENTS (fixes SC-11 and SC-20)
-------------------------------------------------
The 2.0.0 `unsupported` list mixed three states. 2.1.0 splits it into:

- `implicated_nominal`;
- `implicated_unavailable`;
- `implicated_unobserved`;
- `implicated_other`, which holds anything left, such as a component with
  only non-attributable records.

`components_not_observed` lists declared components that no record looked
at. The verdict UNSUPPORTED stays reserved and unreachable, as in 2.0.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csia.v2.attribution import (AMBIGUOUS, NO_EVIDENCE, UNIQUE, Attribution,
                                 attribute)
from csia.v2.evidence import ObservationState

OS = ObservationState

NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED = "NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED"
DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL = \
    "DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL"
NO_RELEVANT_DISCRIMINATOR_FROM_ANOTHER_DOMAIN = \
    "NO_RELEVANT_DISCRIMINATOR_FROM_ANOTHER_DOMAIN"
SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN = \
    "SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN"
NOT_A_DECLARED_ALTERNATIVE = "NOT_A_DECLARED_ALTERNATIVE"
NOT_ATTRIBUTABLE = "NOT_ATTRIBUTABLE"
LOOKED = (OS.NOMINAL, OS.DEGRADED, OS.VIOLATED)


def _cid(r) -> str:
    return f"{r.domain}/{r.component}"


def _graph(records) -> dict:
    g: dict = {}
    for r in records:
        g.setdefault(_cid(r), set()).update(r.dependencies)
    return g


def _ancestors(node, graph) -> set:
    seen, stack = set(), list(graph.get(node, ()))
    while stack:
        cur = stack.pop()
        if cur not in seen:
            seen.add(cur)
            stack.extend(graph.get(cur, ()))
    return seen


def declared_alternatives(cid, records, relations) -> list:
    """Every component the declared structure names as another possible
    explanation for `cid`. Nothing is invented."""
    alts = _ancestors(cid, _graph(records))
    dom = cid.split("/", 1)[0]
    for rel in relations:
        if dom in rel.domains:
            alts.update(rel.implicates)
    alts.discard(cid)
    return sorted(alts)


def nominal_ids(records) -> set:
    return {_cid(r) for r in records
            if r.observation_state is OS.NOMINAL and r.attributable}


def affirmatively_nominal_ids(records) -> set:
    """At least one NOMINAL attributable record, and no record of the same
    component that could not look or was adverse."""
    blocked = {_cid(r) for r in records
               if r.observation_state is OS.UNAVAILABLE or r.is_adverse}
    return nominal_ids(records) - blocked


def split_implicated(unsupported, records) -> dict:
    nominal = nominal_ids(records)
    seen = {_cid(r) for r in records}
    looked = {_cid(r) for r in records if r.observation_state in LOOKED}
    unavailable = seen - looked
    out = {"implicated_nominal": [], "implicated_unavailable": [],
           "implicated_unobserved": [], "implicated_other": []}
    for c in unsupported:
        if c in nominal:
            out["implicated_nominal"].append(c)
        elif c not in seen:
            out["implicated_unobserved"].append(c)
        elif c in unavailable:
            out["implicated_unavailable"].append(c)
        else:
            out["implicated_other"].append(c)
    return out


def components_not_observed(records, relations) -> list:
    declared = set()
    for rel in relations:
        declared.update(rel.implicates)
    for r in records:
        declared.update(r.dependencies)
    looked = {_cid(r) for r in records if r.observation_state in LOOKED}
    return sorted(declared - looked)


@dataclass(frozen=True)
class AttributionResult:
    #: The successor's decision in the 2.0.0 schema. Identical to frozen
    #: `attribute()` whenever no gate withheld UNIQUE.
    v2: Attribution
    #: What frozen `attribute()` said on the same records, before the gates.
    frozen_verdict: str
    withheld_unique_because: tuple
    implicated: dict
    components_not_observed: tuple
    trace: dict = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        return self.v2.verdict

    @property
    def candidates(self) -> tuple:
        return tuple(c.id for c in self.v2.candidates)

    def to_dict(self) -> dict:
        a = self.v2
        return {"verdict": a.verdict,
                "candidates": [c.id for c in a.candidates],
                "common_cause": a.common_cause,
                "withheld_unique_because": list(self.withheld_unique_because),
                **{k: list(v) for k, v in self.implicated.items()},
                "components_not_observed": list(self.components_not_observed),
                "trace": self.trace}

    def to_v2_0_dict(self) -> dict:
        return self.v2.to_dict()


def attribute_2_1(records, relations, localizations=(), c1=True,
                  f2=True) -> AttributionResult:
    """`records` are the tick's records as the successor index holds them
    (de-duplicated under C6). `localizations` are the same tick's
    `LocalizationResult`s, for F2."""
    records = tuple(records)
    a = attribute(records, relations)
    implicated = split_implicated(a.unsupported, records)
    not_observed = tuple(components_not_observed(records, relations))
    trace: dict = {
        "candidates": [c.id for c in a.candidates],
        "non_attributable_ignored": sorted(
            {f"{_cid(r)}:{r.relation}" for r in records
             if not r.attributable and (r.is_adverse
                                        or r.observation_state is OS.NOMINAL)}),
    }
    if a.verdict == NO_EVIDENCE:
        trace["why"] = "NOTHING_ADVERSE"
    elif len(a.candidates) > 1:
        trace["why"] = "SEVERAL_CANDIDATES"
        trace["discriminators"] = list(a.discriminators)
    reasons: list = []
    if len(a.candidates) == 1:
        only = a.candidates[0]
        alts = declared_alternatives(only.id, records, relations)
        excluded = affirmatively_nominal_ids(records)
        relevant = sorted(d for d in a.discriminators
                          if d.split(":", 1)[0] in alts)
        other = sorted(d for d in a.discriminators if d not in relevant)
        unexcluded = [x for x in alts if x not in excluded]
        cross = [d for d in relevant if not d.startswith(only.domain + "/")]
        trace.update(declared_alternatives=alts,
                     unexcluded_alternatives=unexcluded,
                     relevant_discriminators=relevant,
                     other_nominal={d: NOT_A_DECLARED_ALTERNATIVE
                                    for d in other})
        if a.verdict == UNIQUE and c1:
            if not alts:
                reasons.append(NO_DECLARED_ALTERNATIVE_WAS_EXCLUDED)
            elif unexcluded:
                reasons.append(DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL)
            elif not cross:
                reasons.append(NO_RELEVANT_DISCRIMINATOR_FROM_ANOTHER_DOMAIN)
        keep = []
        for x in localizations:
            if x.subject != only.component:
                continue
            retained = [h for h in tuple(x.supported) + tuple(x.unresolved)
                        if h.split("/", 1)[0] != only.domain]
            if retained:
                keep.append({"symptom": x.symptom, "retains": retained})
        if keep:
            trace["localization_disagreement"] = keep
            if a.verdict == UNIQUE and f2:
                reasons.append(SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN)
        if a.verdict == UNIQUE and not reasons:
            trace["why"] = "EVERY_DECLARED_ALTERNATIVE_AFFIRMATIVELY_NOMINAL"
        elif a.verdict == UNIQUE:
            trace["why"] = "UNIQUE_WITHHELD"
        else:
            trace["why"] = "SINGLE_CANDIDATE_NOTHING_NOMINAL_IN_ANOTHER_DOMAIN"
    out = a
    if reasons:
        out = Attribution(verdict=AMBIGUOUS, candidates=a.candidates,
                          discriminators=a.discriminators,
                          common_cause=a.common_cause,
                          unsupported=a.unsupported,
                          detail=dict(a.detail, why="successor gate: "
                                      + ", ".join(reasons)))
    return AttributionResult(out, a.verdict, tuple(reasons), implicated,
                             not_observed, trace)
