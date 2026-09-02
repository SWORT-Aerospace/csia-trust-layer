"""The v2 assurance engine — §§16, 17.

Runs every registered domain over one snapshot, rolls the evidence up into
per-function eligibility, attributes a cause structurally, and produces the
system assurance state.

    SYSTEM:  NORMAL / DEGRADED / RESTRICTED / UNAVAILABLE
    per domain, per function, plus what is LIMITING each function

Deterministic throughout: domains run in sorted id order, records keep that
order, and nothing reads a clock. The engine holds no state between ticks
except the ledger, which is append-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import attribution as ATTR
from .domain import Snapshot
from .evidence import ObservationState, worst
from .functions import FunctionGraph, system_state
from .registry import DomainRegistry


@dataclass(frozen=True)
class SystemAssurance:
    """One tick of the product's answer."""

    t: float
    system: str
    domains: dict                 # {domain_id: ObservationState value}
    functions: dict               # {name: FunctionVerdict}
    attribution: ATTR.Attribution
    records: tuple
    unevaluated: dict = field(default_factory=dict)

    @property
    def limiting_domains(self) -> tuple:
        return tuple(sorted({v.limiting_domain
                             for v in self.functions.values()
                             if v.limiting_domain}))

    def to_dict(self) -> dict:
        return {
            "t": round(float(self.t), 6),
            "system": self.system,
            "domains": dict(sorted(self.domains.items())),
            "functions": {k: v.to_dict()
                          for k, v in sorted(self.functions.items())},
            "limiting_domains": list(self.limiting_domains),
            "attribution": self.attribution.to_dict(),
            "evidence": [r.to_dict() for r in self.records],
            "unevaluated": dict(sorted(self.unevaluated.items())),
        }

    def summary(self) -> str:
        lines = [f"SYSTEM: {self.system}"]
        for d, s in sorted(self.domains.items()):
            lines.append(f"  {d:24s} {s}")
        for name, v in sorted(self.functions.items()):
            lim = f"  <- limited by {v.limiting_domain}" \
                if v.limiting_domain else ""
            lines.append(f"  {name:24s} {v.state}{lim}")
        a = self.attribution
        lines.append(f"  CAUSE SUPPORT: {a.verdict}"
                     + (f" {[c.id for c in a.candidates]}"
                        if a.candidates else ""))
        if a.common_cause:
            lines.append(f"    common-cause alternative retained: "
                         f"{a.common_cause}")
        if a.unsupported:
            lines.append(f"    unsupported: {list(a.unsupported)}")
        return "\n".join(lines)


class AssuranceEngine:
    """Composes domains. Owns no domain logic of its own."""

    def __init__(self, registry: DomainRegistry, functions: FunctionGraph,
                 relations=()):
        self.registry = registry
        self.functions = functions
        self.relations = tuple(relations)

    def evaluate(self, snapshot: Snapshot) -> SystemAssurance:
        records, domain_states, unevaluated = [], {}, {}
        for domain in self.registry.domains():        # sorted by id
            result = domain.evaluate(snapshot)
            records.extend(result.records)
            domain_states[domain.domain_id] = worst(result.records).value
            if result.unevaluated:
                unevaluated[domain.domain_id] = dict(result.unevaluated)

        verdicts = self.functions.evaluate(records)
        return SystemAssurance(
            t=snapshot.t,
            system=system_state(verdicts),
            domains=domain_states,
            functions=verdicts,
            attribution=ATTR.attribute(records, self.relations),
            records=tuple(records),
            unevaluated=unevaluated,
        )

    def declarations(self) -> dict:
        return {
            "domains": self.registry.declarations(),
            "functions": [
                {"name": f.name, "summary": f.summary,
                 "required_domains": list(f.required_domains),
                 "supporting_domains": list(f.supporting_domains),
                 "no_degradation_domains": list(f.no_degradation_domains),
                 "fallback": f.fallback,
                 "acceptable_degradation": f.acceptable_degradation}
                for _n, f in sorted(self.functions.functions.items())],
            "cross_domain_relations": [
                {"relation_id": r.relation_id, "domains": list(r.domains),
                 "implicates": list(r.implicates),
                 "description": r.description} for r in self.relations],
        }


def coverage_report(engine: AssuranceEngine) -> dict:
    """Which functions have a required domain that nothing can serve.

    A function whose required domain has no registered plugin can only ever
    come out UNKNOWN, and finding that out at configuration time is better
    than finding it out per tick for the rest of a deployment.
    """
    have = {d.domain_id for d in engine.registry.domains()}
    gaps = {}
    for name, fn in sorted(engine.functions.functions.items()):
        missing = tuple(sorted(set(fn.required_domains) - have))
        if missing:
            gaps[name] = list(missing)
    return {"registered_domains": sorted(have),
            "functions": list(engine.functions.names()),
            "functions_with_unserved_required_domains": gaps,
            "complete": not gaps}


#: Re-exported so callers do not need three imports for one tick.
__all__ = ["AssuranceEngine", "SystemAssurance", "Snapshot",
           "ObservationState", "coverage_report"]
