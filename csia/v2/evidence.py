"""The common evidence object every v2 domain emits — §3.

Spec: `engineering/v2/COMMON_EVIDENCE_SCHEMA.md`.

**No novelty is claimed** (§39). This is a record shape.

THE CONSTRAINT THAT SHAPES IT — §18
-----------------------------------
Some domain evidence is categorical, deterministic, thresholded engineering
status, or structural. A CPU deadline is met or missed. A firmware hash
matches or does not. Forcing those into a number in [0, 1] would invent a
precision that does not exist and would make them silently comparable with a
Beta-distributed sensor trust that means something else entirely.

So `observation_state` is a REQUIRED categorical verdict and the numeric
fields are OPTIONAL. A domain with a real residual reports one; a domain
without one does not manufacture one. There is no `score`, `health` or
`confidence` field anywhere in this module, and that is deliberate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class ObservationState(str, Enum):
    """The categorical verdict. Ordered by how restrictive it is."""

    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    VIOLATED = "VIOLATED"
    #: "We could not look." Deliberately NOT the same as NOT_APPLICABLE:
    #: collapsing them is how a missing sensor becomes indistinguishable from
    #: a healthy one.
    UNAVAILABLE = "UNAVAILABLE"
    #: "There is nothing to look at in this configuration."
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Applicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INPUTS_MISSING = "INPUTS_MISSING"


#: How restrictive each state is when several bear on one function. Only used
#: for combining; it is NOT a quality score and never leaves this module as a
#: number.
SEVERITY = {
    ObservationState.NOMINAL: 0,
    ObservationState.NOT_APPLICABLE: 0,
    ObservationState.DEGRADED: 1,
    ObservationState.VIOLATED: 2,
    ObservationState.UNAVAILABLE: 3,
}


@dataclass(frozen=True)
class EvidenceRecord:
    """One domain's statement about one relation at one instant.

    Required: who said it, about what, and the categorical verdict. Everything
    numeric is optional, because not every domain has a number and a schema
    that demanded one would get a fabricated one.
    """

    domain: str
    component: str
    relation: str
    source: str
    observation_state: ObservationState
    applicability: Applicability
    affected_functions: tuple = ()
    reason_codes: tuple = ()

    # -- §6: three timestamps, not one. Their DIFFERENCES are the evidence
    #    the TIMING domain exists to read, and one field would discard them.
    timestamp_validity: float | None = None
    timestamp_arrival: float | None = None
    timestamp_processed: float | None = None

    # -- optional, and optional on purpose
    measured_value: float | None = None
    expected_value: float | None = None
    expected_relation: str | None = None
    residual: float | None = None
    sequential_state: dict | None = None
    provenance: dict = field(default_factory=dict)
    #: §22: explicit structure, NOT an independence score. Two sensors on one
    #: rail are not independent evidence, and saying which rail is the honest
    #: first step; inventing a correlation number for it is not.
    dependencies: tuple = ()
    #: May this record make its component a CAUSE CANDIDATE?
    #:
    #: False for a derived statement — a roll-up, an aggregate, a transcribed
    #: verdict. Those are conclusions computed from other records in the same
    #: tick, so admitting them as candidates counts their own inputs twice and
    #: fills the candidate list with things that are not components and cannot
    #: fail. They remain full evidence for the domain state and the function
    #: graph; they are simply not answers to "what broke".
    attributable: bool = True
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.observation_state, ObservationState):
            raise TypeError("observation_state must be an ObservationState")
        if not isinstance(self.applicability, Applicability):
            raise TypeError("applicability must be an Applicability")
        if not self.domain or not self.component or not self.relation:
            raise ValueError("domain, component and relation are required")

    @property
    def severity(self) -> int:
        return SEVERITY[self.observation_state]

    @property
    def is_adverse(self) -> bool:
        """Does this record count against something?"""
        return self.observation_state in (ObservationState.DEGRADED,
                                          ObservationState.VIOLATED)

    def latencies(self) -> dict:
        """Transport, processing and end-to-end, where the stamps exist."""
        v, a, p = (self.timestamp_validity, self.timestamp_arrival,
                   self.timestamp_processed)
        out = {}
        if v is not None and a is not None:
            out["transport_latency"] = round(a - v, 9)
        if a is not None and p is not None:
            out["processing_latency"] = round(p - a, 9)
        if v is not None and p is not None:
            out["end_to_end_latency"] = round(p - v, 9)
        return out

    def to_dict(self) -> dict:
        d = asdict(self)
        d["observation_state"] = self.observation_state.value
        d["applicability"] = self.applicability.value
        d["affected_functions"] = list(self.affected_functions)
        d["reason_codes"] = list(self.reason_codes)
        d["dependencies"] = list(self.dependencies)
        d["latencies"] = self.latencies()
        return d


def worst(records) -> ObservationState:
    """The most restrictive state among some records. Empty -> UNAVAILABLE.

    Empty is UNAVAILABLE rather than NOMINAL: no evidence is not good news,
    and a function whose domain said nothing has not been shown to be fine.
    """
    records = list(records)
    if not records:
        return ObservationState.UNAVAILABLE
    return max((r.observation_state for r in records),
               key=lambda s: SEVERITY[s])
