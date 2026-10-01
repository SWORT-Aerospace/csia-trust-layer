"""The evidence envelope: one producer output, as CSIA receives it.

Every field is kept only because a demonstrated failure needs it
(`research/csia_2_2_evidence_assurance/EVIDENCE_ENVELOPE.md` has the table):

| field | prevents |
|---|---|
| `producer_id`, `claim` | a republished output counted as a second producer (shadow preview case 5, L8); a result read with a meaning it does not have (L6) |
| `producer_version`, `contract_version` | a producer read with the semantics of another version (L9, the v1.1 k/h check) |
| `record` | the 2.1.1 evidence itself (domain, component, relation, state, declared structure) |
| `lineage` | false independence between monitors of one source (L1, L2, L12; preview cases 1, 3) |
| `content_time` | processing latency read as freshness; an old content read as current (preview case 6, E1) |
| `produced_time` | only to show the latency between observation and output, and to catch impossible metadata (content after production) |
| `config_epoch` | evidence from a configuration no longer in force (E1; reused by 2.1.1's R-3) |
| `producer_health` | a NOMINAL from a faulted monitor read as healthy aircraft evidence |

**Deferred:** `profile_version` per envelope. The profile is a property of
the analysis, checked once at load (`profile_gate.py`), and the contract
carries the profiles it is compatible with. A per-envelope copy would only
be a second place for the same fact to disagree.

**`evidence_id`** is derived, not supplied: producer, claim, record key and
content time. The same output always gets the same id, which is what makes
reports byte-stable and receipts comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from csia.v2.evidence import EvidenceRecord

from .health import ProducerHealth
from .lineage import Lineage


def record_key(record) -> str:
    """`DOMAIN/component:relation`, the key 2.1.1's trace uses."""
    return f"{record.domain}/{record.component}:{record.relation}"


@dataclass(frozen=True)
class EvidenceEnvelope:
    producer_id: str
    producer_version: str
    contract_version: str
    claim: str
    record: EvidenceRecord
    lineage: Lineage
    content_time: float
    producer_health: ProducerHealth
    produced_time: float | None = None
    config_epoch: dict | None = None
    #: Free detail a producer wants on the trace (never read by admissibility).
    detail: dict = field(default_factory=dict)

    @property
    def evidence_id(self) -> str:
        ct = ("nan" if not isinstance(self.content_time, (int, float))
              or not math.isfinite(self.content_time)
              else f"{float(self.content_time):.6f}")
        return f"{self.producer_id}|{self.claim}|{record_key(self.record)}|{ct}"

    @property
    def key(self) -> tuple:
        """What a newer output of the same producer replaces."""
        return (self.producer_id, self.claim, record_key(self.record))

    def stamped_record(self) -> EvidenceRecord:
        """The record as the core receives it: the configuration epoch the
        evidence was generated under goes where 2.1.1's R-3 reads it, and
        the record's source names the producer."""
        prov = dict(self.record.provenance or {})
        if self.config_epoch:
            prov["config_epoch"] = dict(self.config_epoch)
        prov["evidence_id"] = self.evidence_id
        return replace(self.record, source=self.producer_id, provenance=prov)

    def to_dict(self) -> dict:
        return {"evidence_id": self.evidence_id, "producer_id": self.producer_id,
                "producer_version": self.producer_version,
                "contract_version": self.contract_version, "claim": self.claim,
                "record": record_key(self.record),
                "state": self.record.observation_state.value,
                "lineage": self.lineage.to_list(),
                "content_time": _num(self.content_time),
                "produced_time": _num(self.produced_time),
                "config_epoch": self.config_epoch,
                "producer_health": self.producer_health.value}


def _num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)) and math.isfinite(x):
        return round(float(x), 6)
    return str(x)
