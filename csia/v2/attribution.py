"""Cross-domain cause attribution — §§14, 29.

Spec: `engineering/v2/CROSS_DOMAIN_RELATION_SPEC.md`.

§29 CARRIES THE v1.1 DISCIPLINE ACROSS DOMAINS
----------------------------------------------
    UNIQUE       one candidate has adverse evidence, and something
                 affirmatively excludes the others
    AMBIGUOUS    several candidates carry adverse evidence and nothing
                 separates them
    UNSUPPORTED  a candidate is implicated by a cross-domain relation but has
                 no adverse evidence of its own
    NO_EVIDENCE  nothing adverse anywhere

**Do not invent certainty.** This is the same rule Phase 2 established for the
sensor domain, where a leader at posterior 0.9998 with zero discriminating
evidence is `NON_IDENTIFIABLE`. The mechanism here is structural rather than
Bayesian — §18 forbids forcing heterogeneous evidence through the
eight-hypothesis core — but the standard is identical: **a cause is named only
when something rules the alternatives out.**

WHAT MAKES A CANDIDATE UNIQUE
-----------------------------
Not "it is the only one we noticed". A candidate is unique when every other
domain that *would* have shown adverse evidence under a competing explanation
is affirmatively `NOMINAL`. That affirmative nominal reading is the
discriminator, and it is recorded by name — so a reader can check what
actually did the excluding rather than trusting that something did.

COMMON CAUSE — §14, Scenario E
------------------------------
When two components carry adverse evidence and both declare a dependency on a
third that is *also* adverse, the third is retained as a **common-cause
alternative** rather than discarded. Two sensors sagging together on one 5 V
rail are not two faults; but nor is "it must be the rail" a unique
attribution, because a rail fault and two coincident sensor faults produce the
same evidence here. The honest output is AMBIGUOUS with the common cause
named.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import ObservationState

UNIQUE = "UNIQUE"
AMBIGUOUS = "AMBIGUOUS"
UNSUPPORTED = "UNSUPPORTED"
NO_EVIDENCE = "NO_EVIDENCE"

VERDICTS = (UNIQUE, AMBIGUOUS, UNSUPPORTED, NO_EVIDENCE)


@dataclass(frozen=True)
class Candidate:
    """A component that could explain what is being observed."""

    domain: str
    component: str
    supporting: tuple = ()          # relation ids carrying adverse evidence
    reason_codes: tuple = ()

    @property
    def id(self) -> str:
        return f"{self.domain}/{self.component}"


@dataclass(frozen=True)
class Attribution:
    verdict: str
    candidates: tuple
    #: Records that affirmatively excluded a competing explanation. Named, so
    #: a reader can check what did the excluding.
    discriminators: tuple = ()
    #: A shared dependency that would explain several candidates at once.
    common_cause: str | None = None
    #: Implicated by a relation but carrying no adverse evidence of its own.
    unsupported: tuple = ()
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"verdict": self.verdict,
                "candidates": [c.id for c in self.candidates],
                "candidate_detail": [
                    {"id": c.id, "domain": c.domain,
                     "component": c.component,
                     "supporting_relations": list(c.supporting),
                     "reason_codes": list(c.reason_codes)}
                    for c in self.candidates],
                "discriminators": list(self.discriminators),
                "common_cause": self.common_cause,
                "unsupported": list(self.unsupported),
                "detail": dict(self.detail)}


@dataclass(frozen=True)
class CrossDomainRelation:
    """A check that spans domains. §14.

    `implicates` names the components this relation can point at. A component
    named here but carrying no adverse evidence of its own comes out
    UNSUPPORTED rather than being promoted on the strength of the relation
    alone.
    """

    relation_id: str
    domains: tuple
    implicates: tuple
    description: str


def attribute(records, relations=()) -> Attribution:
    """Structural attribution over one tick of evidence. Deterministic."""
    # Derived statements — roll-ups, aggregates, transcribed verdicts — are
    # evidence but not candidates. See `EvidenceRecord.attributable`.
    adverse = [r for r in records if r.is_adverse and r.attributable]
    nominal = [r for r in records
               if r.observation_state is ObservationState.NOMINAL
               and r.attributable]

    if not adverse:
        return Attribution(verdict=NO_EVIDENCE, candidates=())

    # -- candidates: distinct components carrying adverse evidence --------
    grouped: dict = {}
    for r in adverse:
        key = (r.domain, r.component)
        entry = grouped.setdefault(key, {"relations": [], "codes": []})
        entry["relations"].append(r.relation)
        entry["codes"].extend(r.reason_codes)
    candidates = tuple(
        Candidate(domain=d, component=c,
                  supporting=tuple(dict.fromkeys(v["relations"])),
                  reason_codes=tuple(dict.fromkeys(v["codes"])))
        for (d, c), v in sorted(grouped.items()))

    # -- §14/E: a shared dependency that is ITSELF adverse ----------------
    # Reachability, not adjacency. A rail feeds a converter feeds a bus feeds
    # a sensor; the sensor declares the bus and nothing declares the rail
    # twice, so counting DIRECT dependencies would miss the very case §28/E
    # is about. The graph is declared by the host, walking it is deterministic
    # and this is emphatically NOT an independence score (§22) -- it names a
    # node, and only a node that carries adverse evidence of its own.
    adverse_ids = {c.id for c in candidates}
    graph: dict = {}
    for r in records:
        # Union, not overwrite: one component emits several relations and
        # they need not all repeat the same dependency list.
        graph.setdefault(f"{r.domain}/{r.component}", set()).update(
            r.dependencies)
    reach_counts: dict = {}
    for cid in sorted(adverse_ids):
        for node in _ancestors(cid, graph):
            if node in adverse_ids and node != cid:
                reach_counts[node] = reach_counts.get(node, 0) + 1
    shared = sorted(k for k, n in reach_counts.items() if n >= 2)
    common = None
    if shared:
        common = max(shared, key=lambda k: (reach_counts[k], k))

    # -- implicated but unsupported ---------------------------------------
    implicated = set()
    for rel in relations:
        if any(r.domain in rel.domains for r in adverse):
            implicated.update(rel.implicates)
    unsupported = tuple(sorted(implicated - adverse_ids))

    if len(candidates) == 1:
        # UNIQUE requires an affirmative exclusion, not merely the absence of
        # a competitor. The discriminators are the nominal readings from OTHER
        # domains that would have gone adverse under a competing explanation.
        only = candidates[0]
        discriminators = tuple(sorted(
            f"{r.domain}/{r.component}:{r.relation}"
            for r in nominal if r.domain != only.domain))
        # Affirmative nominal readings inside the candidate's own domain also
        # exclude alternatives -- a healthy battery is what exonerates the
        # battery when a rail fails. They are recorded, but they do not by
        # themselves make a CROSS-DOMAIN attribution unique: a deployment
        # running one domain could otherwise claim system-level uniqueness on
        # single-domain evidence.
        same_domain = tuple(sorted(
            f"{r.domain}/{r.component}:{r.relation}"
            for r in nominal
            if r.domain == only.domain and r.component != only.component))
        if discriminators:
            return Attribution(verdict=UNIQUE, candidates=candidates,
                               discriminators=discriminators,
                               unsupported=unsupported,
                               detail={"same_domain_discriminators":
                                       list(same_domain)}
                               if same_domain else {})
        # One candidate and nothing affirmatively nominal elsewhere: we have
        # not ruled anything out, so we do not claim to have.
        return Attribution(
            verdict=AMBIGUOUS, candidates=candidates, unsupported=unsupported,
            detail={"why": "single candidate, but no affirmatively nominal "
                           "evidence from another domain to exclude an "
                           "alternative"})

    detail = {"why": "several components carry adverse evidence and nothing "
                     "separates them"}
    if shared:
        detail["shared_adverse_dependencies"] = list(shared)
        detail["common_cause_note"] = (
            "a shared dependency that is itself adverse is RETAINED as an "
            "alternative explanation, not adopted as the answer: one rail "
            "fault and two coincident faults downstream of it produce the "
            "same evidence here")
    return Attribution(verdict=AMBIGUOUS, candidates=candidates,
                       common_cause=common, unsupported=unsupported,
                       detail=detail)


def _ancestors(node: str, graph: dict) -> set:
    """Everything `node` transitively depends on. Cycle-safe."""
    seen, stack = set(), list(graph.get(node, ()))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur, ()))
    return seen


def attribute_unsupported(implicated, records) -> Attribution:
    """A relation points at something with no adverse evidence of its own."""
    ids = {f"{r.domain}/{r.component}" for r in records if r.is_adverse}
    missing = tuple(sorted(set(implicated) - ids))
    if not missing:
        return Attribution(verdict=NO_EVIDENCE, candidates=())
    return Attribution(verdict=UNSUPPORTED, candidates=(),
                       unsupported=missing)
