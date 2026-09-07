"""Capability assurance: what the aircraft can be said to be able to do.

THE QUESTION THIS LAYER ANSWERS
--------------------------------
Not "is the sensor plugged in". Not "is the score high". It is:

    does the evidence that is SUPPORTED, FRESH and APPLICABLE right now
    justify saying this function is available?

Everything below is that question with the shortcuts removed.

THE FIVE STATES, AND THE ONE RULE THAT MATTERS MOST
----------------------------------------------------
    SUPPORTED            every requirement met by supported, unexpired evidence
    DEGRADED_SUPPORTED   met, but through a declared alternative path, or with
                         a declared degradation in force
    NOT_SUPPORTED        a requirement is definitely not met
    NOT_EVALUABLE        the contract or the input cannot be read at all
    UNKNOWN              a requirement's state is not known

**UNKNOWN IS NEVER PROMOTED TO SUPPORTED.** Not by a default, not by an
`or`, not by "absence of evidence of failure". If the state of a load-bearing
input is unknown, the capability's state is at best UNKNOWN, and the reason
code says which input caused it. This is the single rule most likely to be
eroded by a later convenience change, so it is asserted from both sides in
`tests/test_capability_assurance.py`.

WHAT IS DELIBERATELY ABSENT
---------------------------
**There is no ranking parameter, and no code path reads one.** A hypothesis
ranking may inform the diagnosis inside the frozen core; it may never
establish that a capability is supported. The absence is structural rather
than checked: you cannot pass a ranking to `evaluate_capabilities`, so no
future edit can accidentally start honouring one without changing the
signature, which is a visible diff.

**There is no mission planning.** A contract says what a capability needs. It
does not say when to use it, what to do instead, or what the mission is. That
belongs two layers up, and putting it here would make the capability layer
unable to answer the same question twice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

SUPPORTED = "SUPPORTED"
DEGRADED_SUPPORTED = "DEGRADED_SUPPORTED"
NOT_SUPPORTED = "NOT_SUPPORTED"
NOT_EVALUABLE = "NOT_EVALUABLE"
UNKNOWN = "UNKNOWN"

CAPABILITY_STATES = (SUPPORTED, DEGRADED_SUPPORTED, NOT_SUPPORTED,
                     NOT_EVALUABLE, UNKNOWN)

#: Ordered worst-to-best. Used ONLY to combine subordinate states, never to
#: "average" them: the combination rule is `min`, so a capability is never
#: better than its worst load-bearing dependency.
_SEVERITY = {NOT_EVALUABLE: 0, NOT_SUPPORTED: 1, UNKNOWN: 2,
             DEGRADED_SUPPORTED: 3, SUPPORTED: 4}

#: Every reason a capability can be less than SUPPORTED. A report carrying a
#: reason not in this tuple is a bug, and a test says so.
REASON_CODES = (
    "ALL_REQUIREMENTS_MET",
    "EVIDENCE_NOT_SUPPORTED",
    "EVIDENCE_EXPIRED",
    "EVIDENCE_UNKNOWN",
    "EVIDENCE_ABSENT",
    "SUBORDINATE_CAPABILITY_NOT_SUPPORTED",
    "SUBORDINATE_CAPABILITY_UNKNOWN",
    "NO_ALTERNATIVE_PATH_AVAILABLE",
    "ALTERNATIVE_PATH_IN_USE",
    "COMPUTE_NOT_SUPPORTED",
    "COMPUTE_UNKNOWN",
    "TIMING_NOT_SUPPORTED",
    "TIMING_UNKNOWN",
    "ACTUATOR_NOT_SUPPORTED",
    "ACTUATOR_UNKNOWN",
    "OUTSIDE_OPERATING_ENVELOPE",
    "AWAITING_RECERTIFICATION",
    "CONTRACT_MALFORMED",
    "DEPENDENCY_CYCLE",
    "CONFIGURATION_CHANGED",
)


class ContractError(ValueError):
    """A capability contract that cannot be read as written."""


# ---------------------------------------------------------------------------
# evidence, as this layer receives it


@dataclass(frozen=True)
class EvidenceStatus:
    """One evidence item's state, AS THE FIREWALL LEFT IT.

    This layer does not compute any of these fields. `supported` comes from a
    firewall verdict; `expires_at` from the certificate that verdict produced.
    Constructing one by hand is what tests do; constructing one from a guess
    is what nothing may do.
    """
    evidence_id: str
    supported: bool | None          # None means UNKNOWN, and stays UNKNOWN
    expires_at: float | None = None
    witness: tuple = ()
    source: str = "UNDECLARED"

    def state_at(self, now: float) -> str:
        if self.supported is None:
            return UNKNOWN
        if self.expires_at is not None and now > self.expires_at:
            # EXPIRY BEATS SUPPORT. A witness that was valid at t is not a
            # witness at t + dt, and the whole point of carrying an expiry is
            # that nobody has to remember to check it.
            return NOT_SUPPORTED
        return SUPPORTED if self.supported else NOT_SUPPORTED

    def expired_at(self, now: float) -> bool:
        return (self.expires_at is not None and self.supported is not None
                and now > self.expires_at)


# ---------------------------------------------------------------------------
# the contract


@dataclass(frozen=True)
class CapabilityContract:
    """What a capability needs. Nothing about when to use it.

    `requires_all`        every one of these evidence ids
    `requires_one_of`     at least one; using a non-first entry is a DEGRADED
                          path and is reported as one
    `requires_capabilities` subordinate capabilities, all required
    `requires_compute`    compute domains that must be SUPPORTED
    `requires_timing`     timing domains that must be SUPPORTED
    `requires_actuators`  actuator ids that must be SUPPORTED
    `does_not_require`    stated EXPLICITLY, and checked: if one of these ever
                          appears in a requires_* list the contract is
                          malformed. A capability that quietly acquires a
                          dependency it documented itself as not having is the
                          exact drift this field exists to catch.
    """
    capability_id: str
    requires_all: tuple = ()
    requires_one_of: tuple = ()
    requires_capabilities: tuple = ()
    requires_compute: tuple = ()
    requires_timing: tuple = ()
    requires_actuators: tuple = ()
    does_not_require: tuple = ()
    operating_envelope: Mapping[str, Any] = field(default_factory=dict)
    expiry_policy_s: float | None = None
    recovery_policy: str = "REQUIRES_FRESH_EVIDENCE"
    degradation: str = ""
    description: str = ""

    def validate(self) -> None:
        if not self.capability_id:
            raise ContractError("a capability contract needs a capability_id")
        named = (set(self.requires_all) | set(self.requires_capabilities)
                 | set(self.requires_compute) | set(self.requires_timing)
                 | set(self.requires_actuators))
        for group in self.requires_one_of:
            named |= set(group if isinstance(group, (list, tuple))
                         else (group,))
        contradiction = named & set(self.does_not_require)
        if contradiction:
            raise ContractError(
                f"{self.capability_id}: {sorted(contradiction)} appear in both "
                f"a requires_* list and does_not_require. A contract that "
                f"contradicts its own declared independence cannot be read.")
        if self.recovery_policy not in ("REQUIRES_FRESH_EVIDENCE",
                                        "IMMEDIATE_ON_PRESENCE"):
            raise ContractError(
                f"{self.capability_id}: unknown recovery_policy "
                f"{self.recovery_policy!r}")
        if self.recovery_policy == "IMMEDIATE_ON_PRESENCE":
            raise ContractError(
                f"{self.capability_id}: IMMEDIATE_ON_PRESENCE is REJECTED. "
                f"Presence of a sensor is not evidence that the function it "
                f"serves works. It is accepted as a NAME so that a contract "
                f"written by someone reaching for it fails loudly rather than "
                f"being silently reinterpreted.")

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = [list(x) if isinstance(x, tuple) else x for x in v]
        return d


# ---------------------------------------------------------------------------
# the result


@dataclass(frozen=True)
class CapabilityReport:
    capability_id: str
    state: str
    reason_codes: tuple
    load_bearing_evidence: tuple = ()
    missing: tuple = ()
    expired: tuple = ()
    unknown: tuple = ()
    alternative_path_selected: str | None = None
    subordinates: Mapping[str, str] = field(default_factory=dict)
    detail: str = ""

    @property
    def usable(self) -> bool:
        """True only for the two states that permit action.

        Written as an explicit membership test rather than `!= NOT_SUPPORTED`,
        because the negative form quietly makes UNKNOWN usable.
        """
        return self.state in (SUPPORTED, DEGRADED_SUPPORTED)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("reason_codes", "load_bearing_evidence", "missing",
                  "expired", "unknown"):
            d[k] = list(d[k])
        d["subordinates"] = dict(d["subordinates"])
        return d


# ---------------------------------------------------------------------------
# evaluation


def _domain_state(name: str, states: Mapping[str, Any]) -> str:
    """Read a compute/timing/actuator domain. Absent means UNKNOWN.

    ABSENT IS NOT FALSE AND IS NOT TRUE. A domain nobody reported on is a
    domain nobody measured, and the honest state for that is UNKNOWN. Treating
    it as available is how a compute-health failure gets ignored; treating it
    as failed is how a system refuses to fly because a field was not wired up
    yet. Both are wrong; the third option is the state vocabulary having a
    value for "not known".
    """
    if name not in states:
        return UNKNOWN
    v = states[name]
    if v is None:
        return UNKNOWN
    if isinstance(v, str):
        return v if v in CAPABILITY_STATES else UNKNOWN
    return SUPPORTED if v else NOT_SUPPORTED


def _combine(states: Iterable[str]) -> str:
    """Worst wins. Never an average, never a majority."""
    worst = SUPPORTED
    for s in states:
        if _SEVERITY[s] < _SEVERITY[worst]:
            worst = s
    return worst


def _evaluate_one(contract: CapabilityContract,
                  evidence: Mapping[str, EvidenceStatus],
                  resolved: Mapping[str, CapabilityReport],
                  compute: Mapping[str, Any],
                  timing: Mapping[str, Any],
                  actuators: Mapping[str, Any],
                  envelope: Mapping[str, Any],
                  now: float,
                  recertifying: Iterable[str]) -> CapabilityReport:
    try:
        contract.validate()
    except ContractError as exc:
        return CapabilityReport(contract.capability_id, NOT_EVALUABLE,
                                ("CONTRACT_MALFORMED",), detail=str(exc))

    reasons: list = []
    missing: list = []
    expired: list = []
    unknown: list = []
    load_bearing: list = []
    parts: list = []

    # -- 1. required evidence, all of it -----------------------------------
    for eid in contract.requires_all:
        item = evidence.get(eid)
        if item is None:
            missing.append(eid)
            reasons.append("EVIDENCE_ABSENT")
            parts.append(UNKNOWN)
            unknown.append(eid)
            continue
        st = item.state_at(now)
        if item.expired_at(now):
            expired.append(eid)
            reasons.append("EVIDENCE_EXPIRED")
            parts.append(NOT_SUPPORTED)
        elif st == UNKNOWN:
            unknown.append(eid)
            reasons.append("EVIDENCE_UNKNOWN")
            parts.append(UNKNOWN)
        elif st == NOT_SUPPORTED:
            missing.append(eid)
            reasons.append("EVIDENCE_NOT_SUPPORTED")
            parts.append(NOT_SUPPORTED)
        else:
            load_bearing.append(eid)
            parts.append(SUPPORTED)

    # -- 2. alternative paths ----------------------------------------------
    chosen = None
    for group in contract.requires_one_of:
        options = list(group) if isinstance(group, (list, tuple)) else [group]
        picked, any_unknown = None, False
        for index, eid in enumerate(options):
            item = evidence.get(eid)
            if item is None:
                continue
            st = item.state_at(now)
            if st == SUPPORTED:
                picked = (index, eid)
                break
            if st == UNKNOWN:
                any_unknown = True
            if item.expired_at(now) and eid not in expired:
                expired.append(eid)
        if picked is None:
            if any_unknown:
                reasons.append("EVIDENCE_UNKNOWN")
                parts.append(UNKNOWN)
                unknown.extend(o for o in options if o not in unknown)
            else:
                reasons.append("NO_ALTERNATIVE_PATH_AVAILABLE")
                parts.append(NOT_SUPPORTED)
                missing.extend(o for o in options if o not in missing)
            continue
        index, eid = picked
        load_bearing.append(eid)
        if index == 0:
            parts.append(SUPPORTED)
        else:
            # A NON-PRIMARY PATH IS A DEGRADATION AND IS REPORTED AS ONE.
            # The capability still works; the record says which path carried
            # it, so a later analysis is not left guessing.
            chosen = eid
            reasons.append("ALTERNATIVE_PATH_IN_USE")
            parts.append(DEGRADED_SUPPORTED)

    # -- 3. subordinate capabilities ---------------------------------------
    subordinates = {}
    for cid in contract.requires_capabilities:
        sub = resolved.get(cid)
        if sub is None:
            subordinates[cid] = UNKNOWN
            reasons.append("SUBORDINATE_CAPABILITY_UNKNOWN")
            parts.append(UNKNOWN)
            continue
        subordinates[cid] = sub.state
        if sub.state == SUPPORTED:
            parts.append(SUPPORTED)
        elif sub.state == DEGRADED_SUPPORTED:
            parts.append(DEGRADED_SUPPORTED)
        elif sub.state == UNKNOWN:
            reasons.append("SUBORDINATE_CAPABILITY_UNKNOWN")
            parts.append(UNKNOWN)
        else:
            reasons.append("SUBORDINATE_CAPABILITY_NOT_SUPPORTED")
            parts.append(sub.state)

    # -- 4. compute, timing, actuators -------------------------------------
    for names, table, bad, unk in (
            (contract.requires_compute, compute,
             "COMPUTE_NOT_SUPPORTED", "COMPUTE_UNKNOWN"),
            (contract.requires_timing, timing,
             "TIMING_NOT_SUPPORTED", "TIMING_UNKNOWN"),
            (contract.requires_actuators, actuators,
             "ACTUATOR_NOT_SUPPORTED", "ACTUATOR_UNKNOWN")):
        for name in names:
            st = _domain_state(name, table)
            if st == UNKNOWN:
                reasons.append(unk)
                unknown.append(name)
            elif st == NOT_SUPPORTED:
                reasons.append(bad)
                missing.append(name)
            parts.append(st)

    # -- 5. operating envelope ---------------------------------------------
    for key, bounds in (contract.operating_envelope or {}).items():
        value = envelope.get(key)
        if value is None:
            # An envelope quantity nobody reported is UNKNOWN, not "inside".
            # "No reading, therefore within limits" is the same mistake as
            # "no fault reported, therefore healthy".
            reasons.append("EVIDENCE_UNKNOWN")
            unknown.append(f"envelope.{key}")
            parts.append(UNKNOWN)
            continue
        lo, hi = bounds if isinstance(bounds, (list, tuple)) else (None, None)
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            reasons.append("OUTSIDE_OPERATING_ENVELOPE")
            missing.append(f"envelope.{key}")
            parts.append(NOT_SUPPORTED)
        else:
            parts.append(SUPPORTED)

    # -- 6. recertification hold -------------------------------------------
    if contract.capability_id in set(recertifying):
        # A capability whose evidence has returned but has NOT yet been
        # re-established is held here rather than restored. See recovery.py:
        # presence is not evidence.
        #
        # THE HOLD IS `UNKNOWN`, AND THE FIRST VERSION OF THIS LINE GOT IT
        # WRONG (MX-001). It appended DEGRADED_SUPPORTED, reasoning that the
        # capability was "working but qualified". But DEGRADED_SUPPORTED is
        # an AUTHORIZING state: the planner gate accepts it, and every
        # product resting on the capability qualifies from it. The hold was
        # therefore COSMETIC -- it relabelled the capability and changed
        # nothing downstream, and the disaster-corridor benchmark measured a
        # capability recovery latency of 0.000 s, which is the exact
        # signature of BAD_PRODUCT_05.
        #
        # UNKNOWN is the semantically correct state and it is not a
        # compromise. During re-measurement the evidence is returning but the
        # re-establishment is incomplete: we cannot yet SAY the capability is
        # supported. That is what UNKNOWN means. NOT_SUPPORTED would be
        # stronger than what is known -- it would assert the capability is
        # unavailable, which the returning evidence contradicts.
        #
        # And UNKNOWN is the one state that cannot be promoted, so the hold
        # is enforced by the same rule that protects everything else here
        # rather than by a special case.
        reasons.append("AWAITING_RECERTIFICATION")
        parts.append(UNKNOWN)

    state = _combine(parts) if parts else SUPPORTED
    if state == SUPPORTED and not reasons:
        reasons.append("ALL_REQUIREMENTS_MET")

    # dedupe, preserving order, so a report reads as a list of distinct causes
    seen, ordered = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            ordered.append(r)

    return CapabilityReport(
        capability_id=contract.capability_id,
        state=state,
        reason_codes=tuple(ordered),
        load_bearing_evidence=tuple(sorted(set(load_bearing))),
        missing=tuple(sorted(set(missing))),
        expired=tuple(sorted(set(expired))),
        unknown=tuple(sorted(set(unknown))),
        alternative_path_selected=chosen,
        subordinates=dict(sorted(subordinates.items())),
    )


def evaluate_capabilities(contracts: Iterable[CapabilityContract],
                          evidence: Mapping[str, EvidenceStatus],
                          now: float,
                          compute: Mapping[str, Any] | None = None,
                          timing: Mapping[str, Any] | None = None,
                          actuators: Mapping[str, Any] | None = None,
                          envelope: Mapping[str, Any] | None = None,
                          recertifying: Iterable[str] = ()) -> dict:
    """Evaluate every contract, resolving subordinates first.

    DETERMINISTIC AND ORDER-INDEPENDENT. Contracts are topologically ordered
    before evaluation, so the caller's iteration order cannot change a result.
    A cycle is NOT_EVALUABLE with `DEPENDENCY_CYCLE` -- never a guess, never a
    partial resolution that happens to work this time.

    THERE IS NO `ranking` PARAMETER. See the module docstring.
    """
    by_id = {}
    for c in contracts:
        by_id[c.capability_id] = c

    order, state_of = _topological_order(by_id)
    resolved: dict = {}

    for cid in order:
        if state_of.get(cid) == "CYCLE":
            resolved[cid] = CapabilityReport(
                cid, NOT_EVALUABLE, ("DEPENDENCY_CYCLE",),
                detail="this capability participates in a dependency cycle; "
                       "the evaluation FAILS CLOSED rather than picking an "
                       "arbitrary resolution order")
            continue
        resolved[cid] = _evaluate_one(
            by_id[cid], evidence, resolved,
            compute or {}, timing or {}, actuators or {},
            envelope or {}, now, recertifying)
    return resolved


def _topological_order(by_id: Mapping[str, CapabilityContract]):
    """Kahn's algorithm. Anything left over is in a cycle and is marked."""
    deps = {cid: [d for d in c.requires_capabilities if d in by_id]
            for cid, c in by_id.items()}
    indeg = {cid: 0 for cid in by_id}
    for cid, ds in deps.items():
        for _d in ds:
            indeg[cid] += 1

    ready = sorted(c for c, n in indeg.items() if n == 0)
    order, state_of = [], {}
    while ready:
        cid = ready.pop(0)
        order.append(cid)
        for other, ds in deps.items():
            if cid in ds:
                indeg[other] -= 1
                if indeg[other] == 0:
                    ready.append(other)
                    ready.sort()
    for cid in sorted(by_id):
        if cid not in order:
            order.append(cid)
            state_of[cid] = "CYCLE"
    return order, state_of


# ---------------------------------------------------------------------------
# the certificate


#: NOT "certified". NOT "certification-grade". The prefix is the claim.
CAPABILITY_CERT_STATUS = "EXPERIMENTAL_CAPABILITY_SUPPORT_CERTIFICATE"


@dataclass(frozen=True)
class CapabilitySupportCertificate:
    status: str
    capability_id: str
    support_status: str
    reason_codes: tuple
    load_bearing_evidence: tuple
    support_witnesses: Mapping[str, tuple]
    alternative_path_selected: str | None
    compute_state: Mapping[str, Any]
    timing_state: Mapping[str, Any]
    actuator_state: Mapping[str, Any]
    operating_envelope: Mapping[str, Any]
    vehicle_configuration_hash: str
    payload_configuration_hash: str
    software_hashes: Mapping[str, str]
    semantics_version: str
    issued_at: float
    expires_at: float | None
    certificate_hash: str = field(default="", compare=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reason_codes"] = list(self.reason_codes)
        d["load_bearing_evidence"] = list(self.load_bearing_evidence)
        d["support_witnesses"] = {k: list(v)
                                  for k, v in self.support_witnesses.items()}
        for k in ("compute_state", "timing_state", "actuator_state",
                  "operating_envelope", "software_hashes"):
            d[k] = dict(d[k])
        return d

    def valid_at(self, t: float) -> bool:
        """A certificate with no expiry is NOT valid forever.

        `expires_at is None` means the issuer declared no lifetime, and a
        certificate with no declared lifetime cannot be asserted at a later
        time -- the forbidden transition is 'previous certificate remains
        valid forever', and returning True here would implement it.
        """
        if self.expires_at is None:
            return t <= self.issued_at
        return self.issued_at <= t <= self.expires_at


def build_capability_certificate(report: CapabilityReport,
                                 evidence: Mapping[str, EvidenceStatus],
                                 issued_at: float,
                                 vehicle_configuration_hash: str,
                                 payload_configuration_hash: str,
                                 software_hashes: Mapping[str, str],
                                 compute: Mapping[str, Any] | None = None,
                                 timing: Mapping[str, Any] | None = None,
                                 actuators: Mapping[str, Any] | None = None,
                                 operating_envelope: Mapping | None = None,
                                 expires_at: float | None = None
                                 ) -> CapabilitySupportCertificate:
    """A certificate for ANY state, including the refusals.

    Emitted for NOT_SUPPORTED and UNKNOWN too. A record only of the decisions
    that went well is not a record; the reason codes are the useful part when
    a capability is missing, and discarding them is discarding the diagnosis.
    """
    from .provenance import content_hash

    witnesses = {eid: tuple(evidence[eid].witness)
                 for eid in report.load_bearing_evidence
                 if eid in evidence}

    cert = CapabilitySupportCertificate(
        status=CAPABILITY_CERT_STATUS,
        capability_id=report.capability_id,
        support_status=report.state,
        reason_codes=report.reason_codes,
        load_bearing_evidence=report.load_bearing_evidence,
        support_witnesses=witnesses,
        alternative_path_selected=report.alternative_path_selected,
        compute_state=dict(compute or {}),
        timing_state=dict(timing or {}),
        actuator_state=dict(actuators or {}),
        operating_envelope=dict(operating_envelope or {}),
        vehicle_configuration_hash=vehicle_configuration_hash,
        payload_configuration_hash=payload_configuration_hash,
        software_hashes=dict(software_hashes),
        semantics_version="csia.mission.semantics/1",
        issued_at=issued_at,
        expires_at=expires_at,
    )
    body = cert.to_dict()
    body.pop("certificate_hash", None)
    return CapabilitySupportCertificate(**{**body,
                                           "reason_codes": cert.reason_codes,
                                           "load_bearing_evidence":
                                               cert.load_bearing_evidence,
                                           "support_witnesses":
                                               cert.support_witnesses,
                                           "certificate_hash":
                                               content_hash(body)})
