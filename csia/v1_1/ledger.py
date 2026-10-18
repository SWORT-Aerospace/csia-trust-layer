"""Assurance ledger — Phase 4 §§15–19.

A deterministic, machine-readable record of **why the assurance state
changed**, reproducible from the trace, the configuration and the software
SHA. It is the thing that lets someone ask, months later, "what did the system
know at 26.00 s, and on what evidence?" and get an answer that is not a
reconstruction from memory.

WHAT IS AND IS NOT CLAIMED
--------------------------
`content_sha256` per event plus `previous_event_hash` forms **a simple hash
chain**. Its purpose is exactly what §18 states: detecting a missing or
reordered event. **It is not a blockchain, is not distributed, is not
tamper-proof against someone who can rewrite the whole file**, and nothing
here should be described as any of those.

DETERMINISM
-----------
§17. Event ids are hashes of content and sequence, never random UUIDs, so the
same trace replayed on the same software produces the same ids. A test runs a
mechanism twice and compares the full event sequence including every hash.

REASONS
-------
§19. Reasons are structured codes from `REASON_CODES.yaml`. `render()` can
turn one into a sentence for a human display; the sentence is never the
canonical record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from ..runtime.failsafe import FailsafeLevel
from . import advisory
from . import reason_codes as RC

GENESIS = "0" * 64

#: §15. A change in any of these opens an event.
EVENT_TYPES = ("ASSURANCE_STATE_CHANGED", "FUNCTION_ELIGIBILITY_CHANGED",
               "SUPPORT_STATE_CHANGED", "AMBIGUITY_CHANGED",
               "SEQUENTIAL_STATE_CHANGED")


def _canonical(obj) -> str:
    """Stable JSON. Sorted keys, no whitespace drift, no float surprises."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class LedgerContext:
    """Invariant for one run. Every event carries it, so an event is
    self-describing rather than meaningful only next to its file header."""

    platform: str
    software_sha: str
    configuration_hash: str
    input_trace_hash: str
    trust_mode: str
    schema_version: str = "1.1.0"


@dataclass(frozen=True)
class Snapshot:
    """The evidence an event is stamped with. All §16 fields."""

    t: float
    assurance_state: str
    support_state: str
    ambiguity: str
    leader: str
    posterior: float
    active_evidence_count: int
    discriminating_evidence_count: int
    leader_identifiable: bool
    prior_sensitive: bool
    trust: dict
    fresh: dict
    missing_reason: dict
    active_relations: tuple
    suppressed_relations: tuple
    suppression_reasons: dict
    sequential_state: dict
    function_eligibility: dict          # {name: {"state", "reason_codes"}}
    recommendations: tuple = ()

    def body(self) -> dict:
        d = asdict(self)
        d["t"] = round(float(self.t), 4)
        d["posterior"] = round(float(self.posterior), 9)
        d["trust"] = {k: round(float(v), 9) for k, v in sorted(
            self.trust.items())}
        d["fresh"] = {k: bool(v) for k, v in sorted(self.fresh.items())}
        d["missing_reason"] = dict(sorted(self.missing_reason.items()))
        d["active_relations"] = sorted(self.active_relations)
        d["suppressed_relations"] = sorted(self.suppressed_relations)
        d["suppression_reasons"] = dict(sorted(
            self.suppression_reasons.items()))
        d["recommendations"] = list(self.recommendations)
        return d


@dataclass
class Event:
    sequence: int
    event_type: str
    subject: str
    previous_state: str
    new_state: str
    reason_codes: tuple
    context: dict
    snapshot: dict
    event_id: str = ""
    content_sha256: str = ""
    previous_event_hash: str = GENESIS

    def _content(self) -> dict:
        return {"sequence": self.sequence, "event_type": self.event_type,
                "subject": self.subject,
                "previous_state": self.previous_state,
                "new_state": self.new_state,
                "reason_codes": list(self.reason_codes),
                "context": self.context, "snapshot": self.snapshot,
                "previous_event_hash": self.previous_event_hash}

    def seal(self) -> "Event":
        payload = _canonical(self._content()).encode("utf-8")
        self.content_sha256 = hashlib.sha256(payload).hexdigest()
        self.event_id = hashlib.sha256(
            _canonical({"seq": self.sequence,
                        "content": self.content_sha256}).encode("utf-8")
        ).hexdigest()[:32]
        return self

    def to_dict(self) -> dict:
        d = self._content()
        d["event_id"] = self.event_id
        d["content_sha256"] = self.content_sha256
        d["timestamp"] = self.snapshot["t"]
        return d

    def render(self) -> str:
        """Human-readable line. NOT the canonical record (§19)."""
        tpl = RC.load()["ledger_events"][self.event_type]["render"]
        return tpl.format(previous_state=self.previous_state,
                          new_state=self.new_state, function=self.subject)


class AssuranceLedger:
    """Append-only within a run. `observe` emits an event per change."""

    def __init__(self, context: LedgerContext):
        self.context = context
        self.events: list = []
        self._prev: dict = {}
        self._last_hash = GENESIS

    # -- internals ------------------------------------------------------
    def _emit(self, event_type, subject, previous, new, codes, snap):
        ev = Event(sequence=len(self.events), event_type=event_type,
                   subject=subject, previous_state=str(previous),
                   new_state=str(new), reason_codes=tuple(codes),
                   context=asdict(self.context), snapshot=snap,
                   previous_event_hash=self._last_hash).seal()
        self._last_hash = ev.content_sha256
        self.events.append(ev)
        return ev

    # -- the one entry point -------------------------------------------
    def observe(self, snap: Snapshot) -> list:
        """Record whatever changed since the previous call. May emit none.

        Order within a tick is FIXED — assurance, then functions in sorted
        name order, then support, ambiguity, sequential — because a ledger
        whose event order depended on dict iteration would not reproduce.
        """
        body = snap.body()
        out = []

        def changed(key, value):
            was = self._prev.get(key, "__none__")
            self._prev[key] = value
            return (was != value, was)

        moved, was = changed("assurance", snap.assurance_state)
        if moved and was != "__none__":
            out.append(self._emit("ASSURANCE_STATE_CHANGED", "assurance",
                                  was, snap.assurance_state, (), body))

        for name in sorted(snap.function_eligibility):
            row = snap.function_eligibility[name]
            moved, was = changed(f"fn:{name}", row["state"])
            if moved and was != "__none__":
                out.append(self._emit("FUNCTION_ELIGIBILITY_CHANGED", name,
                                      was, row["state"],
                                      row.get("reason_codes", ()), body))

        moved, was = changed("support", snap.support_state)
        if moved and was != "__none__":
            out.append(self._emit("SUPPORT_STATE_CHANGED", "support",
                                  was, snap.support_state, (), body))

        moved, was = changed("ambiguity", snap.ambiguity)
        if moved and was != "__none__":
            out.append(self._emit("AMBIGUITY_CHANGED", "ambiguity",
                                  was, snap.ambiguity, (), body))

        alarming = "|".join(sorted(snap.sequential_state.get("alarming", ())))
        moved, was = changed("sequential", alarming)
        if moved and was != "__none__":
            out.append(self._emit("SEQUENTIAL_STATE_CHANGED", "sequential",
                                  was or "(none)", alarming or "(none)", (),
                                  body))
        return out

    # -- output ---------------------------------------------------------
    def to_dict(self) -> dict:
        return {"artifact": "ASSURANCE_LEDGER",
                "schema_version": self.context.schema_version,
                "context": asdict(self.context),
                "chain_note": "content_sha256 + previous_event_hash form a "
                              "simple hash chain for detecting a missing or "
                              "reordered event. It is not a blockchain and "
                              "is not tamper-proof.",
                "event_count": len(self.events),
                "final_chain_hash": self._last_hash,
                "events": [e.to_dict() for e in self.events]}

    def verify_chain(self) -> tuple:
        """Re-derive every hash. Returns (ok, [problems])."""
        problems, prev = [], GENESIS
        for i, ev in enumerate(self.events):
            if ev.sequence != i:
                problems.append(f"event {i}: sequence {ev.sequence}")
            if ev.previous_event_hash != prev:
                problems.append(f"event {i}: chain break")
            check = Event(sequence=ev.sequence, event_type=ev.event_type,
                          subject=ev.subject,
                          previous_state=ev.previous_state,
                          new_state=ev.new_state,
                          reason_codes=ev.reason_codes, context=ev.context,
                          snapshot=ev.snapshot,
                          previous_event_hash=ev.previous_event_hash).seal()
            if check.content_sha256 != ev.content_sha256:
                problems.append(f"event {i}: content hash mismatch")
            if check.event_id != ev.event_id:
                problems.append(f"event {i}: id mismatch")
            prev = ev.content_sha256
        return (not problems), problems


# --------------------------------------------------------------- helpers
def suppression(relation_gates: dict, endpoints: dict, fresh: dict) -> tuple:
    """Split relations into active / suppressed, with a reason for each.

    The frozen runtime multiplies every edge gate by BOTH endpoints'
    freshness (`online.py:610`), so a suppressed relation is either gated out
    by its own applicability test or has a stale endpoint. Saying which is the
    difference between "the check did not apply" and "a sensor went away".
    """
    active, suppressed, why = [], [], {}
    for rel, gate in sorted(relation_gates.items()):
        if float(gate) > 1e-9:
            active.append(rel)
            continue
        suppressed.append(rel)
        stale = [n for n in endpoints.get(rel, ()) if not fresh.get(n, True)]
        why[rel] = ("ENDPOINT_NOT_FRESH:" + ",".join(sorted(stale))
                    if stale else "GATE_CLOSED")
    return tuple(active), tuple(suppressed), why


def snapshot_from(t, levels_name, support_row, trust, fresh, relation_gates,
                  endpoints, sequential_state, verdicts,
                  missing_reason=None) -> Snapshot:
    """Assemble a §16 snapshot from the layers' own outputs."""
    active, suppressed, why = suppression(relation_gates, endpoints, fresh)
    elig = {n: {"state": v.state, "reason_codes": list(v.reason_codes)}
            for n, v in sorted(verdicts.items())}
    level = (levels_name if isinstance(levels_name, str)
             else FailsafeLevel(int(levels_name)).name)
    return Snapshot(
        t=float(t), assurance_state=level,
        support_state=support_row.support_state,
        ambiguity=support_row.ambiguity,
        leader=support_row.leader,
        posterior=float(support_row.posterior),
        active_evidence_count=int(support_row.active_terms),
        discriminating_evidence_count=int(
            min(support_row.discriminating_terms.values())
            if support_row.discriminating_terms else 0),
        leader_identifiable=bool(support_row.leader_identifiable),
        prior_sensitive=bool(support_row.prior_sensitive),
        trust=dict(trust), fresh=dict(fresh),
        missing_reason=dict(missing_reason or {}),
        active_relations=active, suppressed_relations=suppressed,
        suppression_reasons=why, sequential_state=sequential_state,
        function_eligibility=elig,
        recommendations=advisory.recommend(
            {n: v.state for n, v in verdicts.items()},
            int(FailsafeLevel[level])))
