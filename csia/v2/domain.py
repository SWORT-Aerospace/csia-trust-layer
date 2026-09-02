"""The `AssuranceDomain` plugin contract — §§1, 2, 21.

Spec: `engineering/v2/DOMAIN_PLUGIN_SPEC.md`.

WHY A PLUGIN AND NOT MORE NODES
-------------------------------
§1: do NOT grow the existing 8-node sensor structure into a 50-node monolith.
A power rail is not a sensor with a different name — it has different
evidence, different relations, different failure semantics and a different
notion of what "healthy" even means. Modelling it as another node in the
trust graph would force it through a Beta recursion designed for sensor
consistency, which is the mistake §18 exists to prevent.

So a domain is a plugin: it owns its own relations, emits the common
`EvidenceRecord`, and meets the other domains only at the function graph.

DETERMINISM IS PART OF THE CONTRACT
-----------------------------------
Same snapshot in, same evidence out. No clock reads, no randomness, no
network, no global state. `observe()` takes the snapshot it is given and
`evaluate()` returns records computed from it — a domain that consulted the
wall clock could not be replayed, and replay is what the ledger is for.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from .evidence import EvidenceRecord

#: §25: the core framework is not aircraft-specific. These names describe
#: what a subsystem IS, not what vehicle it is bolted to, so the same set
#: covers an aircraft, a UGV, a robot arm, a boat and a motor test stand.
DOMAIN_IDS = (
    "SENSOR", "POWER", "COMPUTE", "TIMING", "COMMUNICATION", "ACTUATION",
    "FIRMWARE_CONFIGURATION", "THERMAL", "ESTIMATOR", "STORAGE",
    "SECURITY_INTEGRITY",
)


@dataclass(frozen=True)
class Snapshot:
    """One instant of raw system state, as the host hands it over.

    Deliberately a plain nested mapping rather than a typed vehicle object:
    §25 requires the core to serve aircraft, ground robots, boats, arms and
    test stands, and a typed `Aircraft` here would have decided that question
    the wrong way on line one.

        signals[domain_id][component][signal] = value
    """

    t: float
    signals: dict = field(default_factory=dict)
    #: The v1.1 output payload, when a navigation domain is present. v2
    #: INGESTS v1.1 output (§24); it never reaches inside the frozen runtime.
    v1_1_payload: dict | None = None

    def get(self, domain: str, component: str, signal: str, default=None):
        return (self.signals.get(domain, {})
                .get(component, {})
                .get(signal, default))

    def component(self, domain: str, component: str) -> dict:
        return self.signals.get(domain, {}).get(component, {})

    def components(self, domain: str) -> dict:
        return self.signals.get(domain, {})

    def has(self, domain: str, component: str, *signals) -> bool:
        c = self.component(domain, component)
        return all(s in c and c[s] is not None for s in signals)


@dataclass(frozen=True)
class DomainResult:
    """What a domain concluded this tick."""

    domain: str
    records: tuple
    #: Components the domain could not evaluate at all, and why. Reported
    #: rather than dropped: a domain that silently skips a component looks
    #: identical to one that found it healthy.
    unevaluated: dict = field(default_factory=dict)

    @property
    def adverse(self) -> tuple:
        return tuple(r for r in self.records if r.is_adverse)


class AssuranceDomain(abc.ABC):
    """One subsystem's assurance plugin.

    Subclasses declare four things and implement one method. The four
    declarations are what the registry validates; `evaluate` is what runs.
    """

    #: Stable identifier. Must be in `DOMAIN_IDS`.
    domain_id: str = ""
    #: Schema version of THIS plugin's evidence, independent of the core.
    schema_version: str = "2.0.0"
    #: Signals the domain needs to do anything at all.
    required_inputs: tuple = ()
    #: Signals it will use if present and work without if absent.
    optional_inputs: tuple = ()
    #: Relations it can emit, as stable ids.
    relations: tuple = ()
    #: System functions its evidence can bear on.
    affected_functions: tuple = ()
    #: Reason codes it can emit.
    reason_codes: tuple = ()

    # -- the one method a plugin must implement ------------------------
    @abc.abstractmethod
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        """Deterministic. Same snapshot in, same records out."""

    # -- shared helper -------------------------------------------------
    def _record(self, **kw) -> EvidenceRecord:
        kw.setdefault("domain", self.domain_id)
        kw.setdefault("source", self.domain_id.lower())
        return EvidenceRecord(**kw)

    def declaration(self) -> dict:
        """§21: what the registry stores and validates."""
        return {
            "domain_id": self.domain_id,
            "schema_version": self.schema_version,
            "required_inputs": list(self.required_inputs),
            "optional_inputs": list(self.optional_inputs),
            "relations": list(self.relations),
            "affected_functions": list(self.affected_functions),
            "reason_codes": list(self.reason_codes),
            "implementation": type(self).__name__,
        }
