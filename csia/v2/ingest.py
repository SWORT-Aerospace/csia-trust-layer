"""The internal typed interface — Phase C §§15–20.

Spec: `engineering/v2/INTERNAL_INTERFACE_SPEC.md`.

    JSON Schema validation is useful at EXTERNAL TRUST BOUNDARIES. It should
    not necessarily execute every tick between two in-process, version-locked
    components. (§15)

TWO INTERFACES, ONE MEANING
---------------------------
    EXTERNAL   JSON, schema 1.1.0, strict validation, logging, any process or
               network boundary. Unchanged.
    INTERNAL   this module: a typed, frozen, in-memory record, valid by
               construction, never serialised and never schema-validated per
               tick.

`NavigationDomainInput` is the internal form. It is **not a trust boundary**
and §20 bounds where it may be used: same process, version-locked components,
construction-controlled objects. Anything arriving over a network, an IPC
channel, a file or an untrusted plugin edge goes through
`from_external_payload`, which validates exactly as before.

WHAT THE MEASUREMENT ACTUALLY SHOWED — AND A CORRECTION
--------------------------------------------------------
Phase B reported ~28 ms per tick for the v1.1 ingest and attributed it to
"the cost of ingesting schema 1.1.0 strictly". **That attribution was wrong,
and the number was not an inherent cost of validation.**

`jsonschema.validate()` re-checks and re-compiles the schema on every call.
Against a validator compiled once, the same full validation of the same
payload costs ~0.7 ms. So roughly 97% of the "validation cost" was
recompiling a constant, and it was removed in `csia/v1_1/output_api.py`
**without weakening validation at all** — a test asserts identical behaviour,
error type and error message, across the accepted payload and ten distinct
malformations.

The typed path below removes what remains: the schema walk, the strict field
re-checks, and the dict-of-dicts traversal. Both numbers are reported
separately in `V2_PHASEC_COMPUTE.json` so nobody has to take either on faith.

WHY A SEPARATE TYPE AND NOT "SKIP VALIDATION"
---------------------------------------------
"Skip validation when you trust the source" is a flag, and a flag is one
review away from being set in the wrong place. A distinct type makes the
trust boundary visible in the signature: a function taking
`NavigationDomainInput` is stating that its caller is in-process and
version-locked, and a payload from a socket cannot become one without going
through the validating constructor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

#: The v1.1 schema major.minor this internal form mirrors. A payload from any
#: other version cannot become a `NavigationDomainInput`: the internal path is
#: version-locked by construction, which is what makes skipping the schema
#: walk defensible rather than merely faster.
SUPPORTED_MAJOR_MINOR = ("1.1",)


class IngestRejected(ValueError):
    """A payload the internal path will not accept. Never downgraded."""


def _frozen(d):
    return MappingProxyType(dict(d))


@dataclass(frozen=True)
class DiagnosisInput:
    """v1.1's diagnosis, transcribed. Field names are v1.1's, deliberately.

    `posterior` is a posterior probability under a stated prior, and it is
    NOT a confidence (Phase 4 §22). Nothing in this module or downstream of
    it renders the number without its support qualifier attached.
    """

    leader: str
    posterior: float
    support_state: str
    ambiguity: str
    active_evidence_count: int
    discriminating_evidence_count: int
    identifiable: bool
    unknown_fault_model: str | None = None


@dataclass(frozen=True)
class NavigationDomainInput:
    """One v1.1 tick, typed. Valid by construction, never re-validated.

    Every mapping is wrapped in a read-only view so a domain cannot mutate a
    caller's state — the plugin contract's determinism guarantee has to
    survive the caller as well as the plugin.
    """

    schema_version: str
    trust_mode: str
    timestamp: float
    assurance_level: str
    function_eligibility: dict
    function_reasons: dict
    trust: dict
    fresh: dict
    missing_reason: dict
    sequential_alarming: tuple
    sequential_k: float
    sequential_h: float
    diagnosis: DiagnosisInput
    recommendations: tuple = ()
    ledger_event: dict | None = None
    #: How this object came to exist. Carried into the ledger so a replay can
    #: tell which interface produced a run.
    provenance_path: str = "internal"
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if ".".join(self.schema_version.split(".")[:2]) not in \
                SUPPORTED_MAJOR_MINOR:
            raise IngestRejected(
                f"unsupported schema_version {self.schema_version!r}; the "
                f"internal path is version-locked to {SUPPORTED_MAJOR_MINOR}")
        object.__setattr__(self, "function_eligibility",
                           _frozen(self.function_eligibility))
        object.__setattr__(self, "function_reasons",
                           _frozen({k: tuple(v) for k, v
                                    in self.function_reasons.items()}))
        object.__setattr__(self, "trust", _frozen(self.trust))
        object.__setattr__(self, "fresh", _frozen(self.fresh))
        object.__setattr__(self, "missing_reason",
                           _frozen(self.missing_reason))
        object.__setattr__(self, "sequential_alarming",
                           tuple(self.sequential_alarming))
        object.__setattr__(self, "recommendations",
                           tuple(self.recommendations))

    # ------------------------------------------------------------------
    @classmethod
    def from_external_payload(cls, payload: dict) -> "NavigationDomainInput":
        """THE TRUST BOUNDARY. Full strict parse, schema validation included.

        Use this for anything that crossed a process, a socket, a file or an
        untrusted edge. It is the same `csia.v1_1.monitor.parse` the external
        consumer uses, so a payload this rejects is a payload the external
        consumer would also have rejected.
        """
        from ..v1_1.monitor import PayloadRejected, parse
        try:
            view = parse(payload)
        except PayloadRejected as exc:
            raise IngestRejected(str(exc)) from exc
        return cls._from_parts(payload, view.function_reasons,
                               path="external")

    @classmethod
    def from_trusted_payload(cls, payload: dict) -> "NavigationDomainInput":
        """THE INTERNAL PATH. Same process, version-locked producer.

        Structural checks only: the version, the presence of the fields this
        type needs, and the detector constants. **No JSON Schema walk.** That
        is defensible precisely because §20 bounds where this may be called —
        it is not a validation shortcut for untrusted input, it is the
        absence of a boundary that is not there.
        """
        try:
            reasons = {name: tuple(row.get("reason_codes", ()))
                       for name, row in payload["function_eligibility"].items()}
            return cls._from_parts(payload, reasons, path="internal")
        except IngestRejected:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise IngestRejected(
                f"malformed v1.1 payload on the internal path: "
                f"{type(exc).__name__}: {exc}") from exc

    @classmethod
    def _from_parts(cls, payload, reasons, path) -> "NavigationDomainInput":
        # Two frozen CONSTANTS, read to reject a payload from a differently
        # configured detector. Nothing here steps a detector.
        from ..v1_1.sequential import CUSUM_H, CUSUM_K
        seq = payload["sequential"]
        if seq.get("k") != CUSUM_K or seq.get("h") != CUSUM_H:
            raise IngestRejected(
                f"sequential constants {seq.get('k')}/{seq.get('h')} do not "
                f"match the frozen detector {CUSUM_K}/{CUSUM_H}")
        diag = payload["diagnosis"]
        ev = payload["evidence"]
        return cls(
            schema_version=payload["schema_version"],
            trust_mode=payload["trust"]["mode"],
            timestamp=float(payload["timestamp"]),
            assurance_level=payload["assurance"]["level"],
            function_eligibility={k: v["state"] for k, v in
                                  payload["function_eligibility"].items()},
            function_reasons=reasons,
            trust={k: float(v) for k, v in payload["trust"]["nodes"].items()},
            fresh={k: bool(v) for k, v in ev["fresh"].items()},
            missing_reason=dict(ev.get("missing_reason", {})),
            sequential_alarming=tuple(seq.get("alarming", ())),
            sequential_k=float(seq["k"]), sequential_h=float(seq["h"]),
            diagnosis=DiagnosisInput(
                leader=diag["leader"], posterior=float(diag["posterior"]),
                support_state=diag["support_state"],
                ambiguity=diag["ambiguity"],
                active_evidence_count=int(diag["active_evidence_count"]),
                discriminating_evidence_count=int(
                    diag["discriminating_evidence_count"]),
                identifiable=bool(diag["identifiable"]),
                unknown_fault_model=diag.get("unknown_fault_model")),
            recommendations=tuple(payload.get("recommendations", ())),
            ledger_event=payload.get("ledger_event"),
            provenance_path=path)

    # ------------------------------------------------------------------
    def with_timestamp(self, t: float) -> "NavigationDomainInput":
        """A copy at a new tick time. Used by the scenario harness, which
        replays one real payload against a synthetic clock."""
        from dataclasses import replace
        return replace(self, timestamp=float(t))

    def semantic_key(self) -> tuple:
        """Everything a domain can read, as a comparable value.

        §18's equivalence test compares this between the external and
        internal paths. `provenance_path` is deliberately excluded: it
        records WHICH interface was used and is expected to differ, and
        including it would make the test pass for the wrong reason —
        by never being equal.
        """
        d = self.diagnosis
        return (
            self.schema_version, self.trust_mode, self.timestamp,
            self.assurance_level,
            tuple(sorted(self.function_eligibility.items())),
            tuple(sorted((k, tuple(v))
                         for k, v in self.function_reasons.items())),
            tuple(sorted(self.trust.items())),
            tuple(sorted(self.fresh.items())),
            tuple(sorted(self.missing_reason.items())),
            self.sequential_alarming, self.sequential_k, self.sequential_h,
            (d.leader, d.posterior, d.support_state, d.ambiguity,
             d.active_evidence_count, d.discriminating_evidence_count,
             d.identifiable, d.unknown_fault_model),
            self.recommendations,
        )
