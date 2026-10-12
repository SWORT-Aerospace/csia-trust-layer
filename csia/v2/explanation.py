"""FUNCTION ASSURANCE EXPLANATION — Phase C §§1, 12.

Spec: `engineering/v2/FUNCTION_LOCALIZATION_SPEC.md`.

§1 asks for one object per function:

    state              ELIGIBLE / DEGRADED / INELIGIBLE / UNKNOWN
    limiting_domains   SUPPORTED domains that prevent full eligibility
    possible_domains   unresolved alternatives
    cleared_domains    domains the current evidence argues AGAINST
    evidence           the exact supporting observations and relations

THE DISTINCTION THAT DOES THE WORK
-----------------------------------
`limiting`, `possible` and `cleared` are three different epistemic states and
collapsing any two of them loses the point:

    limiting   something confirms this domain and nothing refutes it
    possible   it survived elimination and nothing confirms it — it is not a
               cause, it is an alternative nobody could rule out
    cleared    a named predicate affirmatively argued against it

An operator reading `cleared: [SENSOR, COMMUNICATION]` learns that those were
**measured and found fine**, which is a stronger and more actionable statement
than their simply being absent from a list.

`possible` is never presented as a cause (§2). A function whose explanation
has an empty `limiting` and a non-empty `possible` is one where the system
knows something is wrong and honestly cannot say what — which §39 says is a
better answer than a wrong unique one.

WHY THIS IS DERIVED AND NOT COMPUTED AGAIN
-------------------------------------------
Everything here comes from the function verdict and the localizations already
produced this tick. Nothing re-decides anything, so an explanation cannot
disagree with the verdict it explains.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .localization import AMBIGUOUS, SUPPORTED, UNSUPPORTED


@dataclass(frozen=True)
class FunctionExplanation:
    """§1's object, per function."""

    function: str
    state: str
    #: Domains a SUPPORTED hypothesis places at fault, restricted to the
    #: domains this function actually depends on.
    limiting_domains: tuple
    #: Unresolved alternatives. NOT causes.
    possible_domains: tuple
    #: Domains an affirmative predicate argued against.
    cleared_domains: tuple
    #: The function-graph answer, kept beside the localization one. Where
    #: they differ, they differ for a reason worth seeing.
    graph_limiting_domain: str | None
    active_fallback: str | None
    reason_codes: tuple
    #: `(symptom, subject, verdict, supported, evidence)` per symptom that
    #: touches one of this function's domains.
    symptoms: tuple = ()
    evidence: tuple = ()
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "function": self.function, "state": self.state,
            "limiting_domains": list(self.limiting_domains),
            "possible_domains": list(self.possible_domains),
            "cleared_domains": list(self.cleared_domains),
            "graph_limiting_domain": self.graph_limiting_domain,
            "active_fallback": self.active_fallback,
            "reason_codes": list(self.reason_codes),
            "symptoms": [dict(s) for s in self.symptoms],
            "evidence": list(self.evidence),
            "detail": dict(self.detail),
        }

    def render(self) -> str:
        """One line. Prose is optional and never canonical (§32)."""
        if self.state == "ELIGIBLE":
            return f"{self.function}: ELIGIBLE"
        head = f"{self.function}: {self.state}"
        if self.limiting_domains:
            head += f" limited by {', '.join(self.limiting_domains)}"
        if self.possible_domains:
            head += f"; unresolved alternatives {', '.join(self.possible_domains)}"
        if self.cleared_domains:
            head += f"; cleared {', '.join(self.cleared_domains)}"
        if self.active_fallback:
            head += f"; running on fallback {self.active_fallback}"
        return head


def explain(verdict, localizations, function_spec=None,
            function_names=()) -> FunctionExplanation:
    """Join one function verdict to the localizations that bear on it."""
    watched = set(verdict.domain_states)
    if function_spec is not None:
        watched |= set(function_spec.required_domains)
        watched |= set(function_spec.supporting_domains)
        watched |= {d for g in function_spec.redundant_groups for d in g}
    others = set(function_names) - {verdict.function}

    limiting, possible, cleared, rows, evidence = set(), set(), set(), [], []
    for loc in localizations:
        # A symptom whose SUBJECT is another function is about that function.
        # Attaching it here by domain overlap alone reported PRECISION_
        # NAVIGATION's loss on the explanation of an unrelated function that
        # merely shares the SENSOR domain -- and did it while that function
        # was ELIGIBLE, which is a contradiction in the same object.
        if loc.subject in others:
            continue
        touches = ({h.split("/")[0] for h in loc.supported}
                   | {h.split("/")[0] for h in loc.unresolved}
                   | {h.split("/")[0] for h, _p in loc.rejected})
        if not (touches & watched):
            continue
        rows.append({"symptom": loc.symptom, "subject": loc.subject,
                     "verdict": loc.verdict,
                     "supported": list(loc.supported),
                     "unresolved": list(loc.unresolved),
                     "evidence": list(loc.evidence)})
        evidence.extend(loc.evidence)
        if loc.verdict in (SUPPORTED, AMBIGUOUS):
            limiting |= {h.split("/")[0] for h in loc.supported} & watched
        if loc.verdict in (AMBIGUOUS, UNSUPPORTED):
            possible |= {h.split("/")[0] for h in loc.unresolved} & watched
        cleared |= {h.split("/")[0] for h, _p in loc.rejected} & watched

    # A domain that is BOTH cleared for one symptom and limiting for another
    # is limiting: being fine as an explanation of X says nothing about Y.
    cleared -= limiting
    possible -= limiting

    # The function graph's own answer is kept and reconciled rather than
    # replaced. It reads the function's REQUIREMENTS; localization reads the
    # SYMPTOM's alternatives, and a domain can limit a function without
    # having produced a symptom anyone declared.
    if verdict.limiting_domain and not limiting:
        limiting = {verdict.limiting_domain}

    # §1 defines limiting_domains as the domains that PREVENT FULL
    # ELIGIBILITY. An eligible function has none by definition, so a symptom
    # that touches one of its domains without costing it anything is context,
    # not a limit -- it stays in `symptoms` and out of `limiting`.
    if verdict.state == "ELIGIBLE":
        possible |= limiting
        limiting = set()
        possible -= cleared

    return FunctionExplanation(
        function=verdict.function, state=verdict.state,
        limiting_domains=tuple(sorted(limiting)),
        possible_domains=tuple(sorted(possible)),
        cleared_domains=tuple(sorted(cleared)),
        graph_limiting_domain=verdict.limiting_domain,
        active_fallback=verdict.active_fallback,
        reason_codes=tuple(verdict.reason_codes),
        symptoms=tuple(rows),
        evidence=tuple(sorted(set(evidence))),
        detail={"domain_states": dict(sorted(verdict.domain_states.items())),
                "note": "possible_domains are alternatives nobody could rule "
                        "out. They are NOT causes (§2)."}
        if possible else
        {"domain_states": dict(sorted(verdict.domain_states.items()))})


def explain_all(assurance, function_graph=None) -> tuple:
    """One explanation per function, in a deterministic order."""
    specs = getattr(function_graph, "functions", {}) or {}
    names = tuple(assurance.functions)
    return tuple(
        explain(v, assurance.localizations, specs.get(name), names)
        for name, v in sorted(assurance.functions.items()))
