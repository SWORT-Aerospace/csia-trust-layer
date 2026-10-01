"""The frozen v1.1 CUSUM bank as an evidence producer.

**Wrapped, not re-implemented.** `csia/v1_1/sequential.py`'s `CusumBank`
(Page's one-sided CUSUM, k = 0.5, h = 500, in-control statistics from the
clean arm) runs unchanged. The adapter only says what each output means.

WHAT THE CLAIM SAYS, AND DOES NOT
---------------------------------
`SUSTAINED_SHIFT` on node n:
- **DEGRADED:** the CUSUM of n's standardised pre-transform chi-square is
  above h. A sustained upward shift has accumulated in the residuals of the
  physical relations n takes part in.
- **NOMINAL:** the statistic advanced this tick and is at or below h. The
  contract declares `nominal_means: NO_ANOMALY`: the detector has seen
  nothing, which is not an observation that the node is healthy, and the
  coverage report says so.
- **UNAVAILABLE** (producer health): the statistic did not advance this
  tick, because n's input was gated out or not fresh. The frozen bank's own
  rule is that absence of evidence is not evidence of change.

It does **not** say that n failed. n's chi-square mixes every relation n is
in, so a shift on n can come from n or from any partner. The record is
therefore `attributable=False`: the adapter does not smuggle attribution
into the detector. The profile and 2.1.1 decide what the claim bears on.

LINEAGE
-------
Taken from the frozen v1 relation table (`csia/trust_graph/graph.py`
EDGES):
- the node itself;
- every partner it shares a relation with;
- each relation's model.

So CUSUM(battery), CUSUM(motor_esc) and CUSUM(vibration) all share
`sensor:motor_esc`: in the power-sag scenario their three alarms are one
line of evidence, not three.

COVERAGE
--------
The bank covers battery, gps, mag, motor_esc and vibration. It cannot see
imu0, imu1 or baro (`sequential.NO_RESIDUAL`, with the reason). For those
the adapter emits a coverage notice, "CUSUM evidence unavailable for this
source", never an envelope and never a NOMINAL.

VERSION
-------
The producer version is derived from the frozen constants (k, h and the
in-control table). If they change, the version no longer matches the
contract and every output is CONTRACT_INVALID (the v1.1 k/h check, L9).
"""

from __future__ import annotations

import hashlib
import json
import math

from csia.trust_graph.graph import EDGES
from csia.v1_1 import sequential as SEQ
from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState

from ..envelope import EvidenceEnvelope
from ..health import ProducerHealth
from ..lineage import Lineage

PRODUCER_ID = "cusum:v1_1_sequential"
CONTRACT_VERSION = "cusum-2"
CLAIM = "SUSTAINED_SHIFT"
RELATION = "cusum.sustained_shift"


def frozen_version(k=SEQ.CUSUM_K, h=SEQ.CUSUM_H, in_control=SEQ.IN_CONTROL) -> str:
    ic = hashlib.sha256(json.dumps(in_control, sort_keys=True).encode()).hexdigest()[:12]
    return f"k{k}-h{h}-ic{ic}"


def node_lineage(node: str) -> Lineage:
    roots = {f"sensor:{node}"}
    for a, b, rel, _desc in EDGES:
        if node in (a, b):
            roots.add(f"sensor:{b if a == node else a}")
            roots.add(f"model:v1.{rel}")
    return Lineage.of(*roots)


def coverage_notices() -> list:
    return [{"producer_id": PRODUCER_ID, "source": f"source.{n}", "available": False,
             "why": why} for n, why in sorted(SEQ.NO_RESIDUAL.items())]


def _record(node, state, S, h, k):
    return EvidenceRecord(
        domain="SENSOR", component=f"source.{node}", relation=RELATION,
        source=PRODUCER_ID, observation_state=state,
        applicability=Applicability.APPLICABLE,
        reason_codes=("CUSUM_ALARM",) if state is ObservationState.DEGRADED else (),
        measured_value=None if S is None else float(S), expected_value=float(h),
        expected_relation="one-sided CUSUM statistic at or below h",
        attributable=False, detail={"k": k, "h": h})


def _envelope(node, state, S, t, health, version):
    k, h = SEQ.CUSUM_K, SEQ.CUSUM_H
    return EvidenceEnvelope(
        producer_id=PRODUCER_ID, producer_version=version,
        contract_version=CONTRACT_VERSION, claim=CLAIM,
        record=_record(node, state, S, h, k), lineage=node_lineage(node),
        content_time=float(t), producer_health=health, produced_time=float(t),
        detail={"S": None if S is None else round(float(S), 6)})


class CusumProducer:
    """Live: drives a frozen `CusumBank` one tick at a time."""

    def __init__(self, bank=None):
        self.bank = bank if bank is not None else SEQ.CusumBank()
        self.version = frozen_version(self.bank.k, self.bank.h, self.bank.stats)

    def step(self, t, physics: dict, fresh: dict) -> list:
        """`physics` {node: (lam, gate)} and `fresh` {node: bool}, exactly as
        the frozen comparator produces them."""
        alarms = self.bank.step(physics, fresh)
        out = []
        for node in sorted(self.bank.stats):
            if node not in physics:
                continue
            lam, gate = physics[node]
            active = float(gate) > SEQ.GATE_EPS and bool(fresh.get(node, True))
            S = self.bank.S.get(node)
            health = ProducerHealth.VALID
            if not active:
                health = ProducerHealth.UNAVAILABLE
            elif S is None or not math.isfinite(S) or S < 0:
                health = ProducerHealth.FAULTED
            state = (ObservationState.DEGRADED if alarms.get(node)
                     else ObservationState.NOMINAL)
            out.append(_envelope(node, state, S, t, health, self.version))
        return out


def from_v1_1_payload(payload: dict) -> list:
    """Offline: the CUSUM section of a recorded `csia_output_v1_1` payload.
    The payload's own k and h decide the version, so a payload computed with
    other constants does not pass as the frozen detector."""
    seq = payload.get("sequential") or {}
    version = frozen_version(seq.get("k"), seq.get("h"))
    if seq.get("k") == SEQ.CUSUM_K and seq.get("h") == SEQ.CUSUM_H:
        version = frozen_version()
    fresh = (payload.get("evidence") or {}).get("fresh") or {}
    alarming = set(seq.get("alarming", ()))
    S_all = seq.get("S") or {}
    t = float(payload.get("timestamp", 0.0))
    out = []
    for node in sorted(seq.get("covered_nodes", ())):
        health = ProducerHealth.VALID if fresh.get(node, False) else ProducerHealth.UNAVAILABLE
        state = ObservationState.DEGRADED if node in alarming else ObservationState.NOMINAL
        out.append(_envelope(node, state, S_all.get(node), t, health, version))
    return out
