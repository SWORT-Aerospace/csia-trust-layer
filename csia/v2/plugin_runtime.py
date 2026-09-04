"""Plugin isolation, watchdog and identity — Phase C §§21, 22, 23.

    One failed domain plugin must not: crash all assurance, fabricate healthy
    output, or silently disappear. (§21)
    Do not catch errors and continue as healthy. (§21)

THE THREE WAYS THIS GOES WRONG, AND WHAT STOPS EACH
----------------------------------------------------
**Crashing everything.** One plugin raising must not take the tick down, so
every `evaluate()` runs inside a boundary.

**Fabricating health.** The tempting shape is `except Exception: continue`,
which produces a tick with no evidence from that domain — and "no evidence"
read as "nothing wrong" is the failure mode the whole system exists to
prevent. A FAILED plugin therefore emits an `UNAVAILABLE` record **attached
to every function it declares**, so those functions go `UNKNOWN` and say why.

**Disappearing quietly.** Every status change opens a ledger event, and the
status is carried in the API document. A domain that stopped reporting is
visible as a domain that stopped reporting.

DETERMINISM, AND THE ONE PLACE IT IS DELIBERATELY FORFEITED
------------------------------------------------------------
§22 asks for execution time and a missed assurance deadline to become
evidence. Execution time is wall-clock, and wall-clock evidence in the ledger
would make replay non-reproducible — which §41 requires and which everything
downstream of the ledger depends on.

So the two are separated:

    ALWAYS      execution time, consecutive errors and last-evaluated tick are
                measured and reported in `PluginStatus` and the runtime
                report. Observability, not evidence.
    OPT-IN      `emit_deadline_evidence=True` turns a missed plugin deadline
                into an `EvidenceRecord`. It is **off by default**, and when
                on the runtime says so in its report, because a ledger
                containing it cannot be replayed to the byte.

The deterministic half of §22 is always on: a plugin that FAILED, or that was
never configured, produces evidence without consulting a clock.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

from .evidence import Applicability, EvidenceRecord, ObservationState

# ------------------------------------------------------------------ states
AVAILABLE = "AVAILABLE"
DEGRADED = "DEGRADED"
FAILED = "FAILED"
NOT_CONFIGURED = "NOT_CONFIGURED"
PLUGIN_STATES = (AVAILABLE, DEGRADED, FAILED, NOT_CONFIGURED)

PLUGIN_FAILED = "PLUGIN_FAILED"
PLUGIN_NOT_CONFIGURED = "PLUGIN_NOT_CONFIGURED"
PLUGIN_DEADLINE_MISSED = "PLUGIN_DEADLINE_MISSED"
PLUGIN_PARTIAL = "PLUGIN_PARTIAL"

REASON_CODES = (PLUGIN_FAILED, PLUGIN_NOT_CONFIGURED, PLUGIN_DEADLINE_MISSED,
                PLUGIN_PARTIAL)


@dataclass
class PluginStatus:
    """What the supervisor knows about one plugin. §§22, 23."""

    domain_id: str
    state: str = AVAILABLE
    #: §23 identity, carried into the ledger.
    schema_version: str = ""
    configuration_hash: str = ""
    implementation: str = ""
    #: §22 watchdog.
    evaluations: int = 0
    consecutive_errors: int = 0
    total_errors: int = 0
    last_evaluated_tick: int | None = None
    last_evaluated_t: float | None = None
    last_execution_s: float | None = None
    max_execution_s: float | None = None
    last_error: str = ""
    #: Declared budget, if the host stated one.
    deadline_s: float | None = None
    deadline_misses: int = 0

    def to_dict(self) -> dict:
        return {
            "domain_id": self.domain_id, "state": self.state,
            "schema_version": self.schema_version,
            "configuration_hash": self.configuration_hash,
            "implementation": self.implementation,
            "evaluations": self.evaluations,
            "consecutive_errors": self.consecutive_errors,
            "total_errors": self.total_errors,
            "last_evaluated_tick": self.last_evaluated_tick,
            "last_execution_s": (None if self.last_execution_s is None
                                 else round(self.last_execution_s, 9)),
            "max_execution_s": (None if self.max_execution_s is None
                                else round(self.max_execution_s, 9)),
            "deadline_s": self.deadline_s,
            "deadline_misses": self.deadline_misses,
            "last_error": self.last_error[:200],
        }

    def deterministic_dict(self) -> dict:
        """The part that may appear in the PER-TICK document and the ledger.

        Execution times and deadline-miss counts are DELIBERATELY ABSENT.
        They are wall-clock, they differ between two replays of the same
        trace, and a ledger carrying them could not be verified by replay --
        which is the property everything downstream of the ledger assumes.
        They are reported by `PluginSupervisor.report()` instead.
        """
        return {"state": self.state,
                "schema_version": self.schema_version,
                "configuration_hash": self.configuration_hash,
                "implementation": self.implementation,
                "evaluations": self.evaluations,
                "consecutive_errors": self.consecutive_errors,
                "total_errors": self.total_errors,
                "last_error": self.last_error[:200]}

    def identity(self) -> dict:
        """§23: the part that goes in the ledger context."""
        return {"domain_id": self.domain_id,
                "schema_version": self.schema_version,
                "configuration_hash": self.configuration_hash,
                "implementation": self.implementation}


def configuration_hash(domain) -> str:
    """A stable digest of everything the plugin declares.

    Deterministic: the declaration is canonicalised before hashing, so the
    same configuration produces the same hash on any host and a changed
    threshold produces a different one.
    """
    try:
        decl = domain.declaration()
    except Exception as exc:               # a plugin too broken to declare
        decl = {"declaration_failed": f"{type(exc).__name__}"}
    blob = json.dumps(decl, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:32]


class PluginSupervisor:
    """Runs domains behind a boundary and keeps their status. §§21, 22.

    Holds state across ticks — deliberately. The DOMAINS are stateless by
    contract; the thing supervising them is allowed to remember that a plugin
    has failed nine times in a row, and that memory is exactly what §22 asks
    for.
    """

    def __init__(self, domains, deadlines=None,
                 emit_deadline_evidence: bool = False,
                 degrade_after_errors: int = 1,
                 clock=time.perf_counter):
        self.statuses = {}
        for d in domains:
            st = PluginStatus(
                domain_id=d.domain_id,
                schema_version=str(getattr(d, "schema_version", "")),
                configuration_hash=configuration_hash(d),
                implementation=type(d).__name__,
                deadline_s=(deadlines or {}).get(d.domain_id))
            self.statuses[d.domain_id] = st
        #: OFF by default. See the module docstring: wall-clock evidence in
        #: the ledger would make replay non-reproducible.
        self.emit_deadline_evidence = emit_deadline_evidence
        self.degrade_after_errors = degrade_after_errors
        self._clock = clock
        self.tick = 0

    # ------------------------------------------------------------------
    def run(self, domain, snapshot) -> tuple:
        """`(records, unevaluated, status)`. Never raises for a plugin fault.

        A programming error in the SUPERVISOR still raises; only the plugin's
        own `evaluate` is inside the boundary, so a bug here cannot hide
        behind a domain's failure state.
        """
        st = self.statuses[domain.domain_id]
        started = self._clock()
        try:
            result = domain.evaluate(snapshot)
            records = tuple(result.records)
            unevaluated = dict(result.unevaluated)
        except BaseException as exc:       # noqa: BLE001 -- see docstring
            elapsed = self._clock() - started
            st.consecutive_errors += 1
            st.total_errors += 1
            st.last_error = f"{type(exc).__name__}: {exc}"
            st.state = FAILED
            st.last_execution_s = elapsed
            st.max_execution_s = max(elapsed, st.max_execution_s or 0.0)
            st.last_evaluated_tick = self.tick
            st.last_evaluated_t = snapshot.t
            return (self._failure_records(domain, snapshot, st),
                    {domain.domain_id: f"plugin FAILED: {st.last_error[:120]}"},
                    st)

        elapsed = self._clock() - started
        st.evaluations += 1
        st.consecutive_errors = 0
        st.last_execution_s = elapsed
        st.max_execution_s = max(elapsed, st.max_execution_s or 0.0)
        st.last_evaluated_tick = self.tick
        st.last_evaluated_t = snapshot.t

        over = (st.deadline_s is not None and elapsed > st.deadline_s)
        if over:
            st.deadline_misses += 1
        if not records:
            # A plugin that ran and said nothing is NOT_CONFIGURED for this
            # snapshot: it is configured to watch something the platform is
            # not reporting. Distinct from FAILED, and distinct from healthy.
            st.state = NOT_CONFIGURED
            records = self._not_configured_records(domain, snapshot)
        elif over and self.emit_deadline_evidence:
            st.state = DEGRADED
            records = records + self._deadline_records(domain, snapshot, st,
                                                       elapsed)
        elif over:
            st.state = DEGRADED
        else:
            st.state = AVAILABLE
        return records, unevaluated, st

    # ------------------------------------------------------------------
    def _base(self, domain, snapshot, state, codes, detail):
        """One record per declared function, so a failed domain degrades
        exactly what it was responsible for and nothing else."""
        functions = tuple(domain.declaration().get("affected_functions", ())) \
            or tuple(getattr(domain, "affected_functions", ()))
        return (EvidenceRecord(
            domain=domain.domain_id, component="plugin",
            relation="plugin.status", source="plugin_supervisor",
            observation_state=state,
            applicability=Applicability.INPUTS_MISSING,
            affected_functions=functions, reason_codes=codes,
            timestamp_processed=snapshot.t,
            expected_relation="the domain plugin evaluated successfully",
            #: A supervisor statement is not a component that can fail.
            attributable=False, detail=detail),)

    def _failure_records(self, domain, snapshot, st):
        return self._base(
            domain, snapshot, ObservationState.UNAVAILABLE, (PLUGIN_FAILED,),
            {"error": st.last_error[:200],
             "consecutive_errors": st.consecutive_errors,
             "note": "the plugin raised. Its functions are UNKNOWN, not "
                     "healthy: an exception is the absence of an answer, "
                     "never the answer 'fine'."})

    def _not_configured_records(self, domain, snapshot):
        return self._base(
            domain, snapshot, ObservationState.UNAVAILABLE,
            (PLUGIN_NOT_CONFIGURED,),
            {"note": "the plugin ran and produced no evidence, so the "
                     "platform is not reporting what it watches. Reported "
                     "rather than treated as silence."})

    def _deadline_records(self, domain, snapshot, st, elapsed):
        return self._base(
            domain, snapshot, ObservationState.DEGRADED,
            (PLUGIN_DEADLINE_MISSED,),
            {"execution_s": round(elapsed, 9), "deadline_s": st.deadline_s,
             "note": "WALL-CLOCK EVIDENCE. A ledger containing this record "
                     "cannot be replayed to the byte; it is emitted only "
                     "because the host asked for it."})

    # ------------------------------------------------------------------
    def advance(self):
        self.tick += 1

    def report(self) -> dict:
        return {
            "plugins": {k: v.to_dict()
                        for k, v in sorted(self.statuses.items())},
            "deadline_evidence_enabled": self.emit_deadline_evidence,
            "determinism_note":
                ("execution time and deadline misses are MEASURED and "
                 "REPORTED always, and become evidence only when the host "
                 "opts in, because wall-clock evidence in the ledger would "
                 "make replay non-reproducible"),
        }

    def identities(self) -> list:
        return [self.statuses[k].identity() for k in sorted(self.statuses)]

    def manifest_hash(self) -> str:
        blob = json.dumps(self.identities(), sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()


@dataclass
class FailingDomain:
    """A wrapper that makes a real domain fail on demand — for §37-E's tests.

    Lives in the library rather than the test file because the fault
    injection must go through exactly the path a real failure would, and a
    test-local mock would be free to differ from it.
    """

    inner: object
    mode: str = "raise"           # "raise" | "hang" | "silent"
    hang_s: float = 0.05
    after_tick: int = 0
    _n: int = field(default=0, repr=False)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    @property
    def domain_id(self):
        return self.inner.domain_id

    def declaration(self):
        return self.inner.declaration()

    def evaluate(self, snapshot):
        self._n += 1
        if self._n <= self.after_tick:
            return self.inner.evaluate(snapshot)
        if self.mode == "raise":
            raise RuntimeError("injected plugin fault")
        if self.mode == "hang":
            time.sleep(self.hang_s)
            return self.inner.evaluate(snapshot)
        from .domain import DomainResult
        return DomainResult(domain=self.domain_id, records=())
