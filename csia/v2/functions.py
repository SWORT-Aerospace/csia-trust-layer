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
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"function": self.function, "state": self.state,
                "limiting_domain": self.limiting_domain,
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

        watched = tuple(fn.required_domains) + tuple(fn.supporting_domains)
        for domain in watched:
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

        # -- decide, and remember WHICH domain decided it -----------------
        worst_state, limiting = ELIGIBLE, None
        for domain in watched:
            state = ObservationState(per_domain[domain])
            verdict = _MAP[state]
            if (domain in fn.no_degradation_domains
                    and verdict == DEGRADED):
                # This function does not tolerate degradation here.
                verdict = INELIGIBLE
            if domain in fn.supporting_domains and verdict in (INELIGIBLE,
                                                               UNKNOWN):
                # A supporting domain cannot remove a function, only degrade
                # it -- that is what makes it supporting rather than required.
                verdict = DEGRADED
            if RANK[verdict] > RANK[worst_state]:
                worst_state, limiting = verdict, domain

        if worst_state == ELIGIBLE:
            codes = ["ALL_REQUIREMENTS_MET"]
        return FunctionVerdict(
            function=fn.name, state=worst_state, limiting_domain=limiting,
            domain_states=per_domain,
            reason_codes=tuple(dict.fromkeys(codes)),
            evidence_count=len(mine), fallback=fn.fallback,
            detail={"acceptable_degradation": fn.acceptable_degradation}
            if fn.acceptable_degradation else {})


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
