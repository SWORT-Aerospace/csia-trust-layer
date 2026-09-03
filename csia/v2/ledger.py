"""The domain-level assurance ledger — §23.

    Extend existing assurance ledger so each event identifies: domain,
    component, evidence, affected functions, cross-domain dependencies.
    Preserve deterministic hashing/replay.

WHAT IS CARRIED OVER FROM v1.1 UNCHANGED
----------------------------------------
The mechanism, deliberately: canonical JSON, `content_sha256` per event,
`previous_event_hash` linking them, event ids derived from content and
sequence rather than generated. Two ledgers that work differently cannot be
reconciled by an investigator months later, and the v1.1 mechanism already
does what §23 asks — so this module reuses its shape rather than inventing a
second one.

The same disclaimer applies with the same force, and repeating it is not
boilerplate:

    **THIS IS A SIMPLE HASH CHAIN. It detects a missing or reordered event.
    It is not a blockchain, is not distributed, and is not tamper-proof
    against anyone who can rewrite the whole file. Do not market it as any of
    those.**

WHAT §23 ADDS
-------------
A v1.1 event says "PRECISION_NAVIGATION went INELIGIBLE, reasons X, Y". A v2
event has to answer the question that only exists once there are several
domains: **which domain, which component, and what did it depend on?** So
every event additionally carries

    domain              the domain whose evidence changed the outcome
    component           the specific rail, process, link or actuator
    limiting_domain     which domain set the new function state
    affected_functions  everything this event bears on
    dependencies        the declared cross-domain structure (§22), so a
                        shared-rail common cause is legible in the record
                        rather than only in the live output
    attribution         the verdict, its candidates and its discriminators

WHY THE ATTRIBUTION IS IN THE EVENT
-----------------------------------
Because it changes. The same function can be INELIGIBLE at t=10 with a UNIQUE
cause and INELIGIBLE at t=40 with an AMBIGUOUS one, and a ledger that recorded
only the state would show nothing happening across the transition that matters
most to an investigator.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

GENESIS = "0" * 64

#: §15's list, extended for the domains v2 adds. A change in any of these
#: opens an event.
EVENT_TYPES = (
    "SYSTEM_STATE_CHANGED",
    "FUNCTION_STATE_CHANGED",
    "DOMAIN_STATE_CHANGED",
    "LIMITING_DOMAIN_CHANGED",
    "ATTRIBUTION_CHANGED",
    #: Phase C §31. One event per localization decision that CHANGED.
    "LOCALIZATION_CHANGED",
)


def _canonical(obj) -> str:
    """Stable JSON. Sorted keys, no whitespace drift, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class V2LedgerContext:
    """Invariant for one run, carried on every event so an event is
    self-describing rather than meaningful only beside its file header."""

    profile: str
    software_sha: str
    configuration_hash: str
    #: The declaration digest of every registered plugin. A ledger replayed
    #: against a differently configured plugin set is not a replay, and this
    #: is what makes that detectable instead of merely unlikely.
    plugin_manifest_hash: str
    v1_1_schema_version: str = "1.1.0"

    def to_dict(self) -> dict:
        return {"profile": self.profile, "software_sha": self.software_sha,
                "configuration_hash": self.configuration_hash,
                "plugin_manifest_hash": self.plugin_manifest_hash,
                "v1_1_schema_version": self.v1_1_schema_version}


@dataclass
class V2Event:
    sequence: int
    event_type: str
    subject: str
    previous_state: str
    new_state: str
    #: §23's additions.
    domain: str | None
    component: str | None
    limiting_domain: str | None
    affected_functions: tuple
    dependencies: tuple
    reason_codes: tuple
    attribution: dict
    #: §31's structured localization record, on LOCALIZATION_CHANGED events.
    localization: dict | None
    context: dict
    snapshot: dict
    event_id: str = ""
    content_sha256: str = ""
    previous_event_hash: str = GENESIS

    def _content(self) -> dict:
        return {
            "sequence": self.sequence, "event_type": self.event_type,
            "subject": self.subject,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "domain": self.domain, "component": self.component,
            "limiting_domain": self.limiting_domain,
            "affected_functions": list(self.affected_functions),
            "dependencies": list(self.dependencies),
            "reason_codes": list(self.reason_codes),
            "attribution": self.attribution,
            "localization": self.localization,
            "context": self.context, "snapshot": self.snapshot,
            "previous_event_hash": self.previous_event_hash,
        }

    def seal(self) -> "V2Event":
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
        """One human-readable line. NOT the canonical record."""
        where = (f" [{self.domain}/{self.component}]"
                 if self.domain and self.component
                 else (f" [{self.domain}]" if self.domain else ""))
        why = f" limited by {self.limiting_domain}" \
            if self.limiting_domain else ""
        return (f"{self.snapshot['t']:8.2f}  {self.event_type} "
                f"{self.subject}: {self.previous_state} -> "
                f"{self.new_state}{why}{where}")


class V2AssuranceLedger:
    """Append-only, deterministic, replayable."""

    def __init__(self, context: V2LedgerContext):
        self.context = context
        self.events: list = []
        self._prev: dict = {}
        self._last_hash = GENESIS

    # ------------------------------------------------------------------
    def _emit(self, *, event_type, subject, previous, new, assurance,
              domain=None, component=None, limiting_domain=None,
              affected_functions=(), dependencies=(), reason_codes=(),
              localization=None):
        ev = V2Event(
            sequence=len(self.events), event_type=event_type,
            subject=subject, previous_state=str(previous),
            new_state=str(new), domain=domain, component=component,
            limiting_domain=limiting_domain,
            affected_functions=tuple(affected_functions),
            dependencies=tuple(dependencies),
            reason_codes=tuple(reason_codes),
            attribution=_attribution_digest(assurance.attribution),
            localization=localization,
            context=self.context.to_dict(),
            snapshot=_snapshot_digest(assurance),
            previous_event_hash=self._last_hash).seal()
        self._last_hash = ev.content_sha256
        self.events.append(ev)
        return ev

    def observe(self, assurance) -> list:
        """Record what CHANGED this tick. Returns the events opened."""
        out = []

        def changed(key, value):
            prior = self._prev.get(key)
            self._prev[key] = value
            return (prior is not None and prior != value), prior

        # -- system -----------------------------------------------------
        moved, prior = changed("__system__", assurance.system)
        if moved:
            out.append(self._emit(
                event_type="SYSTEM_STATE_CHANGED", subject="SYSTEM",
                previous=prior, new=assurance.system, assurance=assurance))

        # -- domains ----------------------------------------------------
        for domain, state in sorted(assurance.domains.items()):
            moved, prior = changed(f"domain:{domain}", state)
            if moved:
                out.append(self._emit(
                    event_type="DOMAIN_STATE_CHANGED", subject=domain,
                    previous=prior, new=state, assurance=assurance,
                    domain=domain,
                    affected_functions=_functions_of(assurance, domain),
                    reason_codes=_domain_codes(assurance, domain)))

        # -- functions --------------------------------------------------
        for name, verdict in sorted(assurance.functions.items()):
            moved, prior = changed(f"fn:{name}", verdict.state)
            if moved:
                comp = _worst_component(assurance, verdict.limiting_domain,
                                        name)
                out.append(self._emit(
                    event_type="FUNCTION_STATE_CHANGED", subject=name,
                    previous=prior, new=verdict.state, assurance=assurance,
                    domain=verdict.limiting_domain, component=comp,
                    limiting_domain=verdict.limiting_domain,
                    affected_functions=(name,),
                    dependencies=_dependencies_of(assurance, comp),
                    reason_codes=verdict.reason_codes))
                continue
            # The state held but the DOMAIN THAT IS HOLDING IT BACK moved.
            # That is a different event and a real one: "still degraded, now
            # because of power rather than compute" is what an investigator
            # needs and a state-only ledger silently loses.
            moved, prior = changed(f"lim:{name}", verdict.limiting_domain)
            if moved:
                out.append(self._emit(
                    event_type="LIMITING_DOMAIN_CHANGED", subject=name,
                    previous=prior, new=verdict.limiting_domain,
                    assurance=assurance, domain=verdict.limiting_domain,
                    limiting_domain=verdict.limiting_domain,
                    affected_functions=(name,),
                    reason_codes=verdict.reason_codes))

        # -- §31 localization: symptom, candidates before, evidence
        #    applied, candidates after, unresolved, affected functions.
        #    Deterministic and hashable: the key is the whole decision, so a
        #    localization that reaches the same verdict by different evidence
        #    opens a new event rather than looking unchanged.
        for loc in getattr(assurance, "localizations", ()):
            key = (loc.verdict, loc.supported, loc.unresolved, loc.evidence)
            slot = f"loc:{loc.symptom}:{loc.subject}"
            # A symptom APPEARING is itself the event, unlike a function
            # state where the first observation is only the baseline. So
            # `prior is None` opens an event here and does not elsewhere.
            prior = self._prev.get(slot)
            self._prev[slot] = key
            if prior == key:
                continue
            functions = tuple(sorted(
                {f for r in assurance.records
                 if r.domain in loc.domains for f in r.affected_functions}))
            out.append(self._emit(
                event_type="LOCALIZATION_CHANGED",
                subject=f"{loc.symptom}:{loc.subject}",
                previous=prior[0] if prior else "",
                new=loc.verdict, assurance=assurance,
                domain=(loc.supported[0].split("/")[0]
                        if loc.supported else None),
                affected_functions=functions,
                reason_codes=loc.evidence,
                localization=loc.to_dict()))

        # -- attribution ------------------------------------------------
        a = assurance.attribution
        key = (a.verdict, tuple(c.id for c in a.candidates), a.common_cause)
        moved, prior = changed("__attribution__", key)
        if moved:
            out.append(self._emit(
                event_type="ATTRIBUTION_CHANGED", subject="CAUSE_SUPPORT",
                previous=prior[0] if prior else "", new=a.verdict,
                assurance=assurance))
        return out

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema": "csia_v2_ledger",
            "context": self.context.to_dict(),
            "chain_note": "content_sha256 + previous_event_hash form a "
                          "simple hash chain for detecting a missing or "
                          "reordered event. NOT a blockchain, not "
                          "distributed, not tamper-proof against rewriting "
                          "the whole file.",
            "event_count": len(self.events),
            "head": self._last_hash,
            "events": [e.to_dict() for e in self.events],
        }

    def verify_chain(self) -> tuple:
        """Re-seal every event and compare. Returns (ok, problems)."""
        problems, prev = [], GENESIS
        for ev in self.events:
            if ev.previous_event_hash != prev:
                problems.append(
                    f"event {ev.sequence}: previous_event_hash "
                    f"{ev.previous_event_hash[:12]} != {prev[:12]}")
            recomputed = hashlib.sha256(
                _canonical(ev._content()).encode("utf-8")).hexdigest()
            if recomputed != ev.content_sha256:
                problems.append(
                    f"event {ev.sequence}: content hash does not match its "
                    f"content")
            prev = ev.content_sha256
        return (not problems), tuple(problems)


# --------------------------------------------------------------- helpers
def plugin_manifest_hash(engine) -> str:
    """A digest of every registered plugin's declaration.

    Deterministic because `registry.domains()` is sorted and declarations are
    canonicalised. Replaying a ledger under a different plugin set changes
    this, which is the point: it makes a mismatched replay detectable rather
    than merely unlikely.
    """
    return hashlib.sha256(
        _canonical(engine.registry.declarations()).encode("utf-8")
    ).hexdigest()


def _attribution_digest(a) -> dict:
    return {"verdict": a.verdict,
            "candidates": [c.id for c in a.candidates],
            "common_cause": a.common_cause,
            "unsupported": list(a.unsupported),
            "discriminators": list(a.discriminators)}


def _snapshot_digest(assurance) -> dict:
    """What the tick looked like. Small enough to keep per event, complete
    enough to explain the event without the full evidence dump."""
    return {"t": round(float(assurance.t), 6),
            "system": assurance.system,
            "domains": dict(sorted(assurance.domains.items())),
            "functions": {k: v.state
                          for k, v in sorted(assurance.functions.items())},
            "limiting_domains": list(assurance.limiting_domains)}


def _functions_of(assurance, domain) -> tuple:
    return tuple(sorted({f for r in assurance.records
                         if r.domain == domain
                         for f in r.affected_functions}))


def _domain_codes(assurance, domain) -> tuple:
    seen = []
    for r in assurance.records:
        if r.domain == domain and (r.is_adverse
                                   or r.observation_state.value ==
                                   "UNAVAILABLE"):
            seen.extend(r.reason_codes)
    return tuple(dict.fromkeys(seen))


def _worst_component(assurance, domain, function) -> str | None:
    """The component in `domain` carrying the most restrictive evidence for
    `function`. Deterministic: ties break on the component name."""
    if not domain:
        return None
    rows = [r for r in assurance.records
            if r.domain == domain and function in r.affected_functions]
    if not rows:
        return None
    return max(rows, key=lambda r: (r.severity, r.component)).component


def _dependencies_of(assurance, component) -> tuple:
    if not component:
        return ()
    out: set = set()
    for r in assurance.records:
        if r.component == component:
            out.update(r.dependencies)
    return tuple(sorted(out))


@dataclass
class LedgerRun:
    """Convenience: evaluate a scenario and keep its ledger together."""

    engine: object
    ledger: V2AssuranceLedger
    results: list = field(default_factory=list)

    def step(self, snapshot):
        result = self.engine.evaluate(snapshot)
        self.results.append(result)
        return result, self.ledger.observe(result)
