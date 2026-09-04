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
from .localization import localize_all
from .plugin_runtime import PluginSupervisor
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
    #: Phase C §§1-6: one entry per symptom present this tick.
    localizations: tuple = ()
    #: Phase C §§21-23: `{domain_id: PluginStatus.to_dict()}`.
    plugins: dict = field(default_factory=dict)

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
            "localization": [x.to_dict() for x in self.localizations],
            "plugins": dict(sorted(self.plugins.items())),
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
        for loc in self.localizations:
            lines.append(f"  SYMPTOM {loc.symptom} on {loc.subject}: "
                         f"{loc.verdict}"
                         + (f" -> {', '.join(loc.supported)}"
                            if loc.supported else "")
                         + (f" | unresolved {', '.join(loc.unresolved)}"
                            if loc.unresolved else ""))
        bad = [k for k, v in sorted(self.plugins.items())
               if v.get("state") not in (None, "AVAILABLE")]
        if bad:
            lines.append("  PLUGINS NOT AVAILABLE: "
                         + ", ".join(f"{k}={self.plugins[k]['state']}"
                                     for k in bad))
        a = self.attribution
        lines.append(f"  CAUSE SUPPORT: {a.verdict}"
                     + (f" {[c.id for c in a.candidates]}"
                        if a.candidates else ""))
        if a.common_cause:
            lines.append(f"    common-cause alternative retained: "
                         f"{a.common_cause}")
        if a.detail.get("domains_excluded"):
            lines.append(f"    ruled out by affirmative evidence: "
                         f"{a.detail['domains_excluded']}")
        if a.unsupported:
            lines.append(f"    implicated but unsupported: "
                         f"{list(a.unsupported)}")
        return "\n".join(lines)


class AssuranceEngine:
    """Composes domains. Owns no domain logic of its own."""

    def __init__(self, registry: DomainRegistry, functions: FunctionGraph,
                 relations=(), symptoms=(), predicates=None,
                 supervisor=None, plugin_deadlines=None,
                 emit_deadline_evidence: bool = False):
        self.registry = registry
        self.functions = functions
        self.relations = tuple(relations)
        #: Phase C. Empty by default so an engine built the Phase B way keeps
        #: behaving the Phase B way; the profiles supply the real table.
        self.symptoms = tuple(symptoms)
        self.predicates = dict(predicates or {})
        #: §21. Every plugin runs behind a boundary, always -- isolation is
        #: not opt-in, because the failure it prevents is silent.
        self.supervisor = supervisor or PluginSupervisor(
            registry.domains(), deadlines=plugin_deadlines,
            emit_deadline_evidence=emit_deadline_evidence)

    def evaluate(self, snapshot: Snapshot) -> SystemAssurance:
        records, domain_states, unevaluated = [], {}, {}
        plugins = {}
        for domain in self.registry.domains():        # sorted by id
            got, uneval, status = self.supervisor.run(domain, snapshot)
            records.extend(got)
            domain_states[domain.domain_id] = worst(got).value
            if uneval:
                unevaluated[domain.domain_id] = dict(uneval)
            # The DETERMINISTIC view only: execution times are wall-clock
            # and would make a replay of this document differ from the run.
            plugins[domain.domain_id] = status.deterministic_dict()
        self.supervisor.advance()

        verdicts = self.functions.evaluate(records)
        localizations = (localize_all(self.symptoms, records, self.predicates)
                         if self.symptoms else ())
        return SystemAssurance(
            t=snapshot.t,
            system=system_state(verdicts),
            domains=domain_states,
            functions=verdicts,
            attribution=ATTR.attribute(records, self.relations),
            records=tuple(records),
            unevaluated=unevaluated,
            localizations=localizations,
            plugins=plugins,
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
