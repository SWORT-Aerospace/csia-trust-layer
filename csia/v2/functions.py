"""The system function graph — §§15, 16.

Spec: `engineering/v2/FUNCTION_DEPENDENCY_SPEC.md`.

THE SEPARATION THAT MAKES v2 WORTH BUILDING — §15
-------------------------------------------------
Component domains and functions are different things. A domain says "the 5 V
rail is out of tolerance". A function says "precision navigation is no longer
justified". v1.1 already made that distinction inside one domain; v2's whole
contribution is making it hold across domains, so the product answer is

    which functions are still justified, by what evidence,
    and WHAT DOMAIN IS LIMITING THEM

The last clause is the one a component-oriented tool cannot answer at all.

The states are v1.1's, unchanged and for the same reasons: `UNKNOWN` means the
policy could not determine eligibility, and is not the unmodeled-fault
hypothesis, which v2 does not implement either.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import ObservationState

ELIGIBLE = "ELIGIBLE"
DEGRADED = "DEGRADED"
INELIGIBLE = "INELIGIBLE"
UNKNOWN = "UNKNOWN"

STATES = (ELIGIBLE, DEGRADED, INELIGIBLE, UNKNOWN)

#: More restrictive is higher. `UNKNOWN` outranks `INELIGIBLE` because
#: "cannot determine" must not be acted on as though it were "available".
RANK = {ELIGIBLE: 0, DEGRADED: 1, INELIGIBLE: 2, UNKNOWN: 3}


@dataclass(frozen=True)
class SystemFunction:
    """What a function needs, declared rather than inferred. §15."""

    name: str
    summary: str
    #: Every one of these domains must have evidence for the function.
    required_domains: tuple
    #: Domains that improve the function but whose absence only degrades it.
    supporting_domains: tuple = ()
    #: Domains where DEGRADED is not tolerated — the function stops instead.
    #: Named per function because "degraded timing" means something different
    #: to logging than it does to closed-loop control.
    no_degradation_domains: tuple = ()
    #: What the host may fall back to. Recorded, never actioned: CSIA does
    #: not switch anything (§33).
    fallback: str | None = None
    acceptable_degradation: str = ""

    # ---------------------------------------------- Phase C §11 additions
    #: ONE-OF-N groups over COMPONENTS, as `"DOMAIN/component"` ids. At
    #: least one member must be healthy.
    #:
    #: Components rather than domains, because that is where redundancy
    #: actually lives: two pumps in parallel are both in ACTUATION, and a
    #: domain-level group would be a group of one whose state is the WORST
    #: pump -- which reports a fully-capable skid as failed the moment either
    #: pump stops. That was the first implementation, and the pump-skid
    #: profile is what exposed it.
    redundant_groups: tuple = ()
    #: ALTERNATE requirement sets. If the primary requirements are not met
    #: but one of these is, the function is DEGRADED rather than INELIGIBLE
    #: -- it is running on its fallback. Each entry is
    #: `(name, (domains...))`, and the name is reported so the consumer
    #: knows WHICH fallback is carrying it.
    fallback_requirements: tuple = ()
    #: Domains that improve quality and are not required at all. Their state
    #: is reported and never changes the verdict.
    optional_domains: tuple = ()


@dataclass(frozen=True)
class FunctionVerdict:
    function: str
    state: str
    #: §17's product output: which domain set this outcome.
    limiting_domain: str | None
    domain_states: dict
    reason_codes: tuple
    evidence_count: int
    fallback: str | None = None
    #: Phase C §1. Which declared fallback set, if any, is carrying it.
    active_fallback: str | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"function": self.function, "state": self.state,
                "limiting_domain": self.limiting_domain,
                "active_fallback": self.active_fallback,
                "domain_states": dict(sorted(self.domain_states.items())),
                "reason_codes": list(self.reason_codes),
                "evidence_count": self.evidence_count,
                "fallback": self.fallback, "detail": dict(self.detail)}


#: Domain observation state -> what it does to a function that requires it.
_MAP = {
    ObservationState.NOMINAL: ELIGIBLE,
    ObservationState.NOT_APPLICABLE: ELIGIBLE,
    ObservationState.DEGRADED: DEGRADED,
    ObservationState.VIOLATED: INELIGIBLE,
    #: A required domain that could not be evaluated leaves eligibility
    #: undetermined. It is NOT treated as healthy.
    ObservationState.UNAVAILABLE: UNKNOWN,
}


class FunctionGraph:
    """Rolls domain evidence up into per-function eligibility."""

    def __init__(self, functions):
        self.functions = {f.name: f for f in functions}
        if len(self.functions) != len(list(functions)):
            raise ValueError("duplicate function name")

    def names(self) -> tuple:
        return tuple(sorted(self.functions))

    def evaluate(self, records) -> dict:
        """`{function: FunctionVerdict}`. Deterministic and total."""
        out = {}
        for name in sorted(self.functions):
            out[name] = self._one(self.functions[name], records)
        return out

    def _one(self, fn: SystemFunction, records) -> FunctionVerdict:
        mine = [r for r in records if fn.name in r.affected_functions]
        per_domain, codes = {}, []

        watched = (tuple(fn.required_domains) + tuple(fn.supporting_domains)
                   + tuple(d for g in fn.redundant_groups for d in g)
                   + tuple(fn.optional_domains)
                   + tuple(d for _n, ds in fn.fallback_requirements
                           for d in ds))
        for domain in dict.fromkeys(watched):
            rows = [r for r in mine if r.domain == domain]
            if not rows:
                # No evidence is not good news. A required domain that said
                # nothing has not shown the function to be fine.
                per_domain[domain] = (ObservationState.UNAVAILABLE.value
                                      if domain in fn.required_domains
                                      else ObservationState.NOT_APPLICABLE
                                      .value)
                continue
            state = max((r.observation_state for r in rows),
                        key=lambda s: {ObservationState.NOMINAL: 0,
                                       ObservationState.NOT_APPLICABLE: 0,
                                       ObservationState.DEGRADED: 1,
                                       ObservationState.VIOLATED: 2,
                                       ObservationState.UNAVAILABLE: 3}[s])
            per_domain[domain] = state.value
            for r in rows:
                if r.is_adverse or r.observation_state is \
                        ObservationState.UNAVAILABLE:
                    codes.extend(r.reason_codes)

        def verdict_for(domain, softening=True):
            state = ObservationState(per_domain[domain])
            got = _MAP[state]
            if domain in fn.no_degradation_domains and got == DEGRADED:
                got = INELIGIBLE
            if softening and domain in fn.supporting_domains \
                    and got in (INELIGIBLE, UNKNOWN):
                # A supporting domain cannot remove a function, only degrade
                # it -- that is what makes it supporting rather than required.
                got = DEGRADED
            return got

        # -- decide, and remember WHICH domain decided it -----------------
        worst_state, limiting, redundancy = ELIGIBLE, None, []
        for domain in tuple(fn.required_domains) + tuple(fn.supporting_domains):
            got = verdict_for(domain)
            if RANK[got] > RANK[worst_state]:
                worst_state, limiting = got, domain

        # -- §11 REDUNDANT: one-of-N over COMPONENTS. The group costs
        #    nothing while ONE member is healthy, and costs what its BEST
        #    member costs once none is.
        for group in fn.redundant_groups:
            per = {}
            for member in group:
                dom, _, comp = member.partition("/")
                rows = [r for r in mine
                        if r.domain == dom and (not comp
                                                or r.component == comp)]
                if not rows:
                    per[member] = UNKNOWN
                    continue
                st = max((r.observation_state for r in rows),
                         key=lambda s: {ObservationState.NOMINAL: 0,
                                        ObservationState.NOT_APPLICABLE: 0,
                                        ObservationState.DEGRADED: 1,
                                        ObservationState.VIOLATED: 2,
                                        ObservationState.UNAVAILABLE: 3}[s])
                per[member] = _MAP[st]
            best = min(per.values(), key=lambda v: RANK[v]) if per else UNKNOWN
            healthy = [m for m, v in per.items() if v == ELIGIBLE]
            redundancy.append({"group": list(group),
                               "member_states": dict(sorted(per.items())),
                               "healthy_members": sorted(healthy),
                               "exhausted": not healthy})
            if RANK[best] > RANK[worst_state]:
                worst_state = best
                limiting = min((m.split("/")[0] for m, v in per.items()
                                if v == best), default=None)
            if not healthy:
                codes.append("REDUNDANT_GROUP_EXHAUSTED")
            elif len(healthy) < len(group):
                codes.append("REDUNDANCY_REDUCED")

        # -- §11 FALLBACK: an alternate requirement set that IS met turns
        #    "gone" into "running on the fallback". The function is DEGRADED,
        #    never ELIGIBLE: a function on its reserve is not a function at
        #    full capability, and reporting it as one is how a fallback stops
        #    being visible.
        active_fallback = None
        if worst_state in (INELIGIBLE, UNKNOWN):
            for name, domains in fn.fallback_requirements:
                if all(verdict_for(d, softening=False) == ELIGIBLE
                       for d in domains):
                    active_fallback = name
                    worst_state = DEGRADED
                    codes.append("RUNNING_ON_FALLBACK")
                    break

        if worst_state == ELIGIBLE:
            # A function still eligible on its last redundant member is
            # eligible with NO MARGIN, and saying only "all requirements met"
            # would hide the one fact an operator would act on.
            kept = [c for c in codes if c == "REDUNDANCY_REDUCED"]
            codes = ["ALL_REQUIREMENTS_MET"] + kept
        detail = {}
        if fn.acceptable_degradation:
            detail["acceptable_degradation"] = fn.acceptable_degradation
        if fn.redundant_groups:
            detail["redundancy"] = redundancy
        if fn.optional_domains:
            detail["optional_domains"] = {
                d: per_domain.get(d) for d in fn.optional_domains}
        if fn.fallback_requirements:
            detail["declared_fallbacks"] = [n for n, _ in
                                            fn.fallback_requirements]
        return FunctionVerdict(
            function=fn.name, state=worst_state, limiting_domain=limiting,
            domain_states=per_domain,
            reason_codes=tuple(dict.fromkeys(codes)),
            evidence_count=len(mine), fallback=fn.fallback,
            active_fallback=active_fallback, detail=detail)


def system_state(verdicts) -> str:
    """§16's single top-level word, derived from the functions.

    NORMAL      every function eligible
    DEGRADED    something is degraded, nothing is lost
    RESTRICTED  at least one function is unavailable, but not all
    UNAVAILABLE every function is ineligible or undetermined
    """
    states = [v.state for v in verdicts.values()]
    if not states:
        return "UNAVAILABLE"
    if all(s == ELIGIBLE for s in states):
        return "NORMAL"
    if all(s in (INELIGIBLE, UNKNOWN) for s in states):
        return "UNAVAILABLE"
    if any(s in (INELIGIBLE, UNKNOWN) for s in states):
        return "RESTRICTED"
    return "DEGRADED"
