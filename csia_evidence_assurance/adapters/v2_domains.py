"""The frozen CSIA v2 domain plugins as legacy evidence producers.

For historical replay and for the scenario corpus. Each plugin (one record
`source`: actuation, communication, compute, power, sensor, timing) is one
producer, `v2-domain:<source>`.

**Its contract is derived from the plugin's own declaration**
(`engine.declarations()`): the claims are the relations the plugin declares,
and the producer version is the digest of that declaration. A record of a
relation the plugin did not declare is therefore CONTRACT_INVALID, not
silently accepted.

| contract field | value for a v2 plugin, and why |
|---|---|
| lineage | PER_OUTPUT: the component's own channel (`channel:DOMAIN/component`). A v1.1 transcription (`v1_1.*`, `sensor.aggregate`) also carries `model:v1_1_runtime`, because every one of them was computed by the same v1.1 run; a source-health record carries its sensor |
| update | SNAPSHOT: the plugin re-derives every record each tick |
| validity | none. A TIMING record's age IS its claim (a slow source is the fault), so a freshness rule on it would reject exactly the evidence the TIMING hypotheses need |
| health_reporting | IN_PROCESS: the plugin runs in the analyzer's process, and the frozen plugin runtime already turns a plugin failure into UNAVAILABLE records |
| config_dependency | none in the frozen profile. `legacy_contracts(epoch_claims=...)` adds it for the records a transition makes configuration-dependent (E1), per component: `{(source, relation, component): keys}` becomes its own claim `relation@component`, so the same relation on another component (the `csia` and `logger` processes' deadlines) is not made to carry an epoch it does not depend on |

**Times.** The envelope's `content_time` is the record's
`timestamp_validity`: when the observed information was valid. The
envelope's `produced_time` is the analysis tick, because an in-process
plugin emits its record at the tick. The record's own `timestamp_arrival`
and `timestamp_processed` are NOT envelope metadata. They describe the
measured data flow, and on a TIMING record a late or inconsistent timeline
is the claim itself (CPU_OVERLOAD, CLOCK_DRIFT). Reading them as the
producer's metadata rejected exactly that evidence; see
`research/csia_2_2_evidence_assurance/CONTENT_TIME.md`.
"""

from __future__ import annotations

import hashlib
import json

from ..contract import SCHEMA, ProducerContract
from ..envelope import EvidenceEnvelope
from ..health import ProducerHealth
from ..lineage import Lineage

AIRCRAFT_BASE = "csia/v2/profiles/aircraft.py"
#: The frozen base profile of each v2 system, and the successor profile 2.2
#: reasons with for it (None: the frozen profile itself).
PROFILE_BASE = {"aircraft": AIRCRAFT_BASE,
                "test_stand": "csia/v2/profiles/test_stand.py",
                "pump_skid": "csia/v2/profiles/pump_skid.py"}
SUCCESSOR = {"aircraft": "aircraft_successor_r2"}
V1_1_RELATIONS = ("v1_1.function_eligibility", "v1_1.source_health", "v1_1.support",
                  "sensor.aggregate")


def producer_id(source: str) -> str:
    return f"v2-domain:{source}"


def legacy_contracts(engine, profile_base=AIRCRAFT_BASE, epoch_claims=None) -> dict:
    """One contract per v2 domain plugin, from its declaration.
    `epoch_claims`: {(source, relation, component): (epoch keys)} for
    configuration-dependent records (E1); each becomes the claim
    `relation@component`."""
    decl = engine.declarations()
    out = {}
    for d in decl["domains"]:
        src = d["domain_id"].lower()
        if d["domain_id"] in ("NAVIGATION",):
            src = "sensor"
        version = hashlib.sha256(json.dumps(d, sort_keys=True, default=str)
                                 .encode()).hexdigest()[:16]
        claims = {}
        dom = "SENSOR" if src == "sensor" else d["domain_id"]
        for rel in d.get("relations", ()):
            c = {"meaning": f"the frozen v2 {d['domain_id']} plugin's {rel} statement",
                 "domain": dom, "relation": rel,
                 "attributable": rel not in ("v1_1.function_eligibility", "v1_1.support",
                                             "sensor.aggregate")}
            claims[rel] = c
            for (esrc, erel, comp), dep in sorted((epoch_claims or {}).items()):
                if (esrc, erel) == (src, rel):
                    claims[claim_of(rel, comp)] = dict(c, config_dependency=list(dep))
        raw = {"schema": SCHEMA, "producer_id": producer_id(src),
               "producer_version": version, "contract_version": "v2-legacy-1",
               "claims": claims, "lineage": "PER_OUTPUT",
               "update": {"mode": "SNAPSHOT", "period_s": None},
               "validity": {}, "health_reporting": "IN_PROCESS",
               "profile_compatibility": [profile_base],
               "expected_inputs": d.get("required_inputs", []),
               "fault_behavior": "a plugin failure becomes UNAVAILABLE records via the frozen plugin runtime"}
        out[producer_id(src)] = ProducerContract.from_dict(raw)
    return out


def claim_of(relation: str, component: str) -> str:
    """The claim of a configuration-dependent record (see `legacy_contracts`)."""
    return f"{relation}@{component}"


def lineage_of(record) -> Lineage:
    roots = [f"channel:{record.domain}/{record.component}"]
    if record.relation in V1_1_RELATIONS:
        roots.append("model:v1_1_runtime")
        if record.relation == "v1_1.source_health":
            roots.append(f"sensor:{record.component.split('.', 1)[-1]}")
    return Lineage.of(*roots)


def envelopes(records, t, contracts, epoch_of=None) -> list:
    """The tick's records as envelopes. `epoch_of(record)` -> the stamp for a
    configuration-dependent record, or None."""
    out = []
    for r in records:
        pid = producer_id(r.source)
        c = contracts.get(pid)
        stamp = epoch_of(r) if epoch_of else None
        if stamp is None and r.provenance and isinstance(r.provenance.get("config_epoch"), dict):
            stamp = dict(r.provenance["config_epoch"])
        out.append(EvidenceEnvelope(
            producer_id=pid,
            producer_version=c.producer_version if c else "unknown",
            contract_version=c.contract_version if c else "unknown",
            claim=(claim_of(r.relation, r.component)
                   if c and claim_of(r.relation, r.component) in c.claims else r.relation),
            record=r, lineage=lineage_of(r),
            content_time=float(r.timestamp_validity if r.timestamp_validity is not None else t),
            producer_health=ProducerHealth.VALID,
            produced_time=float(t),
            config_epoch=stamp))
    return out
