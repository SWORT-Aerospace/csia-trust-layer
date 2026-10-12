"""Admissibility: may this evidence reach the reasoning core now?

`assess(envelopes, contracts, context)` gives every envelope exactly one
status, the reasons, and any warnings, and builds the record set Semantic
Core 2.1.1 receives. Every status has an operational meaning; there is no
catch-all UNKNOWN.

| status | the evidence | what the core receives |
|---|---|---|
| ADMISSIBLE | may be reasoned with | the record, with its configuration epoch stamped where R-3 reads it |
| CONTRACT_INVALID | cannot be interpreted: no contract, another producer or contract version, an undeclared claim, a claim mapped to the wrong record, a lineage the contract does not declare, a malformed timestamp, or a missing or undeclared configuration epoch | withheld |
| PROFILE_MISMATCH | was declared against another base profile | withheld |
| PRODUCER_INVALID | comes from a producer that is UNAVAILABLE, FAULTED, or UNKNOWN when it must report health; or one reporting VALID with impossible metadata (content after production, or in the future), which marks the producer FAULTED | withheld |
| STALE | content older than the contract's `max_content_age_s` | withheld |
| REGIME_INVALID | content generated outside the event window the producer was validated for (or the event is unknown) | withheld |
| CONFIGURATION_MISMATCH | stamped with a configuration epoch other than the current one. **Decided by 2.1.1's own R-3** (`csia_semantic_core.admission.admit`), not by a second staleness system | the stamped record; the core applies R-3 itself |
| DUPLICATE | the same claim, about the same record, with the same content time, lineage and state as another admitted output under a different producer identity (a republished output) | dropped; the kept copy stands |

**Withheld** means what R-3 means: if an admitted record answers the same
(relation, component), the withheld one is dropped; otherwise it becomes
UNAVAILABLE ("could not look") with its identity and declared structure kept
and its content cleared. So a NOMINAL from a faulted monitor can never read
as nominal, and a rejected record never takes part in localization or
attribution with its content. It stays in the result, with its reason.

**One malformed producer never fails the tick.** Its evidence is withheld,
and the conclusions that needed it become less certain, as 2.1.1 already
handles evidence that could not look.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from csia.v2.evidence import ObservationState
from csia_semantic_core.admission import EpochContext, admit

from .envelope import EvidenceEnvelope, record_key
from .health import ProducerHealth
from .lineage import Lineage

ADMISSIBLE = "ADMISSIBLE"
CONTRACT_INVALID = "CONTRACT_INVALID"
PROFILE_MISMATCH = "PROFILE_MISMATCH"
PRODUCER_INVALID = "PRODUCER_INVALID"
STALE = "STALE"
REGIME_INVALID = "REGIME_INVALID"
CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
DUPLICATE = "DUPLICATE"
STATUSES = (ADMISSIBLE, CONTRACT_INVALID, PROFILE_MISMATCH, PRODUCER_INVALID,
            STALE, REGIME_INVALID, CONFIGURATION_MISMATCH, DUPLICATE)

#: Tolerance for comparing times that come from one clock.
TIME_EPS = 1e-9


@dataclass(frozen=True)
class AnalysisContext:
    """What admissibility needs to know about "now"."""

    t: float
    profile_base: str
    epochs: object = None          # EpochContext, a {key: epoch} map, or None
    events: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Admission:
    evidence_id: str
    producer_id: str
    status: str
    reasons: tuple
    warnings: tuple = ()

    def to_dict(self) -> dict:
        return {"evidence_id": self.evidence_id, "producer_id": self.producer_id,
                "status": self.status, "reasons": list(self.reasons),
                "warnings": list(self.warnings)}


@dataclass(frozen=True)
class Assessment:
    admissions: tuple            # one Admission per envelope, sorted by evidence id
    records: tuple               # what Semantic Core 2.1.1 receives
    epochs: object               # passed to the core with the records
    producer_faults: dict        # {producer_id: [reason, ...]} found this tick
    config_report: dict          # R-3's own admission report

    def by_status(self, status) -> list:
        return [a for a in self.admissions if a.status == status]


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def check(env: EvidenceEnvelope, contracts: dict, ctx: AnalysisContext):
    """-> (status, reasons, warnings, producer_fault or None). The first
    failing check decides the status; every failing check is listed."""
    reasons, warnings, fault = [], [], None
    status = None

    def fail(st, why):
        nonlocal status
        reasons.append(why)
        if status is None:
            status = st

    c = contracts.get(env.producer_id)
    if c is None:
        fail(CONTRACT_INVALID, "NO_CONTRACT_FOR_PRODUCER")
        return status, tuple(reasons), (), None
    if env.producer_version != c.producer_version:
        fail(CONTRACT_INVALID, f"PRODUCER_VERSION_MISMATCH:{env.producer_version}!="
             f"{c.producer_version}")
    if env.contract_version != c.contract_version:
        fail(CONTRACT_INVALID, f"CONTRACT_VERSION_MISMATCH:{env.contract_version}!="
             f"{c.contract_version}")
    spec = c.claims.get(env.claim)
    if spec is None:
        fail(CONTRACT_INVALID, f"UNKNOWN_CLAIM:{env.claim}")
    else:
        r = env.record
        if r.domain != spec.domain or r.relation != spec.relation:
            fail(CONTRACT_INVALID, f"CLAIM_RECORD_MISMATCH:{record_key(r)}")
        if bool(r.attributable) != spec.attributable:
            fail(CONTRACT_INVALID, "ATTRIBUTABILITY_NOT_AS_DECLARED")
    if not isinstance(env.lineage, Lineage):
        fail(CONTRACT_INVALID, "MISSING_OR_INVALID_LINEAGE")
    elif c.lineage != "PER_OUTPUT" and env.lineage != c.lineage:
        fail(CONTRACT_INVALID, "LINEAGE_NOT_AS_DECLARED")
    if not _finite(env.content_time):
        fail(CONTRACT_INVALID, "MALFORMED_CONTENT_TIME")
    if env.produced_time is not None and not _finite(env.produced_time):
        fail(CONTRACT_INVALID, "MALFORMED_PRODUCED_TIME")
    if spec is not None:
        stamp = env.config_epoch or {}
        if not isinstance(stamp, dict):
            fail(CONTRACT_INVALID, "MALFORMED_EPOCH")
        else:
            for k in spec.config_dependency:
                if k not in stamp:
                    fail(CONTRACT_INVALID, f"MISSING_EPOCH:{k}")
            for k in sorted(set(stamp) - set(spec.config_dependency)):
                fail(CONTRACT_INVALID, f"UNDECLARED_EPOCH_KEY:{k}")
    if ctx.profile_base not in c.profile_compatibility:
        fail(PROFILE_MISMATCH, f"NOT_DECLARED_FOR_PROFILE:{ctx.profile_base}")
    h = env.producer_health
    if c.health_reporting == "IN_PROCESS":
        if h is not ProducerHealth.VALID:
            fail(PRODUCER_INVALID, f"IN_PROCESS_PRODUCER_NOT_VALID:{h.value}")
    elif h is ProducerHealth.DEGRADED:
        warnings.append("PRODUCER_DEGRADED")
    elif h is ProducerHealth.UNKNOWN:
        fail(PRODUCER_INVALID, "PRODUCER_HEALTH_NOT_REPORTED")
    elif h in (ProducerHealth.UNAVAILABLE, ProducerHealth.FAULTED):
        fail(PRODUCER_INVALID, f"PRODUCER_{h.value}")
    if h in (ProducerHealth.VALID, ProducerHealth.DEGRADED) and _finite(env.content_time):
        impossible = []
        if env.content_time > ctx.t + TIME_EPS:
            impossible.append("CONTENT_TIME_IN_THE_FUTURE")
        if _finite(env.produced_time):
            if env.produced_time + TIME_EPS < env.content_time:
                impossible.append("PRODUCED_BEFORE_ITS_CONTENT")
            if env.produced_time > ctx.t + TIME_EPS:
                impossible.append("PRODUCED_IN_THE_FUTURE")
        if impossible:
            fault = "IMPOSSIBLE_METADATA_WHILE_REPORTING_" + h.value + ":" + ",".join(impossible)
            fail(PRODUCER_INVALID, fault)
    if _finite(env.content_time):
        if c.max_content_age_s is not None and ctx.t - env.content_time > c.max_content_age_s + TIME_EPS:
            fail(STALE, f"CONTENT_AGE_{ctx.t - env.content_time:.3f}s_OVER_{c.max_content_age_s}s")
        if c.event_window is not None:
            name, lo, hi = c.event_window
            ev = ctx.events.get(name)
            if ev is None:
                fail(REGIME_INVALID, f"VALIDITY_EVENT_UNKNOWN:{name}")
            elif not (ev + lo - TIME_EPS <= env.content_time <= ev + hi + TIME_EPS):
                fail(REGIME_INVALID, f"CONTENT_OUTSIDE_VALIDATED_WINDOW:{name}+[{lo},{hi}]s")
    return status or ADMISSIBLE, tuple(reasons), tuple(warnings), fault


def withheld_record(env: EvidenceEnvelope, status: str):
    """R-3's representation of evidence that could not be admitted:
    UNAVAILABLE, identity and declared structure kept, content cleared."""
    r = env.record
    return replace(r, source=env.producer_id,
                   observation_state=ObservationState.UNAVAILABLE,
                   reason_codes=(f"EVIDENCE_INADMISSIBLE_{status}",),
                   measured_value=None, residual=None, sequential_state=None,
                   timestamp_validity=None, timestamp_arrival=None,
                   timestamp_processed=None,
                   detail={"evidence_inadmissible": status},
                   provenance={"evidence_id": env.evidence_id})


def _dup_key(env):
    r = env.record
    return (env.claim, record_key(r), round(float(env.content_time), 6),
            env.lineage.digest() if isinstance(env.lineage, Lineage) else None,
            r.observation_state, tuple(sorted(r.reason_codes or ())))


def assess(envelopes, contracts: dict, ctx: AnalysisContext) -> Assessment:
    envs = sorted(envelopes, key=lambda e: (e.evidence_id, e.producer_health.value))
    res, faults = [], {}
    for e in envs:
        st, why, warn, fault = check(e, contracts, ctx)
        res.append([st, list(why), list(warn)])
        if fault:
            faults.setdefault(e.producer_id, []).append(fault)
    # a producer found FAULTED by its metadata is FAULTED for the whole tick
    for e, st in zip(envs, res):
        if e.producer_id in faults and st[0] == ADMISSIBLE:
            st[0] = PRODUCER_INVALID
            st[1].append("PRODUCER_FAULTED_THIS_TICK")
    # exact repeats, and republished duplicates under another identity
    seen_id: set = set()
    seen: dict = {}
    for e, st in zip(envs, res):
        if st[0] != ADMISSIBLE:
            continue
        if e.evidence_id in seen_id:
            st[0] = DUPLICATE
            st[1].append(f"DUPLICATE_OF:{e.evidence_id}")
            continue
        seen_id.add(e.evidence_id)
        k = _dup_key(e)
        if k in seen and seen[k].producer_id != e.producer_id:
            st[0] = DUPLICATE
            st[1].append(f"DUPLICATE_OF:{seen[k].evidence_id}")
        else:
            seen.setdefault(k, e)
    # configuration: R-3 itself, on the candidates
    cand = [(e, st) for e, st in zip(envs, res) if st[0] == ADMISSIBLE]
    stamped = [e.stamped_record() for e, _ in cand]
    epochs = EpochContext.of(ctx.epochs) if ctx.epochs is not None else None
    _admitted, report = admit(stamped, epochs or EpochContext())
    by_rid_src = {(record_key(e.record), e.producer_id): st for e, st in cand}
    for entry in report["inadmissible"]:
        st = by_rid_src.get((entry["record"], entry["source"]))
        if st is not None:
            st[0] = CONFIGURATION_MISMATCH
            st[1].append(f"R3:{entry['reason']}:{entry['key']}:evidence={entry['evidence_epoch']}"
                         f":current={entry['current_epoch']}")
    # the record set for the core
    answered = {(e.record.relation, e.record.component) for e, _ in cand}
    records = list(stamped)
    for e, st in zip(envs, res):
        if st[0] in (ADMISSIBLE, CONFIGURATION_MISMATCH, DUPLICATE):
            continue
        if (e.record.relation, e.record.component) in answered:
            continue
        records.append(withheld_record(e, st[0]))
    admissions = tuple(Admission(e.evidence_id, e.producer_id, st[0], tuple(st[1]),
                                 tuple(st[2])) for e, st in zip(envs, res))
    return Assessment(admissions, tuple(records), epochs, faults, report)
