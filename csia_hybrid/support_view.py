"""Phase 5 — the CSIA support output the hybrid exposes.

WHAT THIS ADDS OVER `csia_consequence.support`
-----------------------------------------------
The Phase-3 classifier already decides IDENTIFIABLE / AMBIGUOUS /
NON_IDENTIFIABLE from symmetric-difference separability over ACTIVE evidence,
and that argument is reused here rather than reimplemented -- a second
implementation of the same rule would be a second thing to keep in sync, and
the first one is already mutation-tested.

Phase 5 needs a richer evidence taxonomy than active-versus-gated, because
"the edge is shut" and "the edge is open but reading stale data" and "the
edge is open and disagreeing" are three different epistemic situations that
a policy should not treat alike:

    ACTIVE          weight above epsilon, fresh
    GATED           weight at or below epsilon -- the gate is shut
    STALE           weight above epsilon but freshness below STALE_BELOW
    WITHDRAWN       was active earlier in this run and is not now
    CONTRADICTORY   named by the caller as disagreeing with its peers

WITHDRAWN is the one that needs a memory, so this class keeps one. It is the
state that matters for evidence-loss latency: the interval between an edge
being active and the support status losing it.

THE INVARIANT THIS MODULE EXISTS TO ENFORCE
--------------------------------------------
**A high confidence score with no active separating evidence is never
reported as a supported attribution.** `attribution_status` is derived from
the support status and never from the score, and a test drives a 0.99-weight
leader through a fully gated evidence set and asserts the answer is
UNSUPPORTED. That combination is reachable -- it is `SC-20` in the systems
paper's register -- and it is the whole reason this layer exists.

AUTHORITY
---------
None. This emits typed states and provenance. It names no action, holds no
actuator authority, and imports neither the fast path nor the capability
layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Sequence, Tuple

from csia_consequence import support as _support

IDENTIFIABLE = _support.IDENTIFIABLE
AMBIGUOUS = _support.AMBIGUOUS
NON_IDENTIFIABLE = _support.NON_IDENTIFIABLE
STATES: Tuple[str, ...] = (IDENTIFIABLE, AMBIGUOUS, NON_IDENTIFIABLE)

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
PARTIAL = "PARTIAL"
ATTRIBUTION_STATES: Tuple[str, ...] = (SUPPORTED, PARTIAL, UNSUPPORTED)

#: Below this freshness an active edge is reported STALE as well as active.
#: Chosen on development data and frozen by the preregistration.
STALE_BELOW = 0.5

GATE_EPSILON = 0.0

HAS_ACTUATOR_AUTHORITY = False


@dataclass(frozen=True)
class EvidenceView:
    """The five-way split, plus the hypothesis set that consumes it."""

    active: Tuple[str, ...]
    gated: Tuple[str, ...]
    stale: Tuple[str, ...]
    withdrawn: Tuple[str, ...]
    contradictory: Tuple[str, ...]

    def as_dict(self) -> dict:
        return {"active": list(self.active), "gated": list(self.gated),
                "stale": list(self.stale), "withdrawn": list(self.withdrawn),
                "contradictory": list(self.contradictory)}


@dataclass(frozen=True)
class SupportView:
    """What the hybrid exposes. Carries provenance; commands nothing."""

    t: float
    evidence: EvidenceView
    hypotheses: Tuple[str, ...]
    support_status: str
    attribution_status: str
    leader: Optional[str]
    leader_weight: float
    separating_features: Tuple[str, ...]
    reason: str
    provenance: str
    map_id: str

    def __post_init__(self):
        if self.support_status not in STATES:
            raise ValueError(f"unknown support status {self.support_status!r}")
        if self.attribution_status not in ATTRIBUTION_STATES:
            raise ValueError(
                f"unknown attribution status {self.attribution_status!r}")
        if (self.attribution_status == SUPPORTED
                and self.support_status != IDENTIFIABLE):
            raise ValueError(
                "SUPPORTED attribution without IDENTIFIABLE support is the "
                "exact combination this layer exists to prevent")

    def as_record(self) -> dict:
        return {
            "schema": "csia.hybrid.support_view/1",
            "t": round(float(self.t), 6),
            "evidence": self.evidence.as_dict(),
            "hypotheses": list(self.hypotheses),
            "support_status": self.support_status,
            "attribution_status": self.attribution_status,
            "leader": self.leader,
            "leader_weight": round(float(self.leader_weight), 6),
            "separating_features": list(self.separating_features),
            "reason": self.reason,
            "provenance": self.provenance,
            "map_id": self.map_id,
            "has_actuator_authority": HAS_ACTUATOR_AUTHORITY,
            "is_experimental": True,
        }


@dataclass
class SupportTracker:
    """Stateful across a run, because WITHDRAWN needs a memory.

    `low_sets` is injected, not imported, so the same tracker serves `B3`
    (the frozen map) and `B4` (the corrected map) with no branch inside it.
    """

    low_sets: Dict[str, FrozenSet[str]]
    map_id: str
    provenance: str = "csia_hybrid.support_view over csia_consequence.support"
    _ever_active: set = field(default_factory=set, repr=False)
    _first_active_t: Dict[str, float] = field(default_factory=dict, repr=False)
    _lost_t: Dict[str, float] = field(default_factory=dict, repr=False)

    def observe(self, *, t: float, hypotheses: Sequence[str],
                weights: Dict[str, float], freshness: Dict[str, float],
                leader: Optional[str] = None, leader_weight: float = 0.0,
                contradictory: Sequence[str] = ()) -> SupportView:
        """One tick of the support layer.

        `weights` is feature -> realized gate weight this tick, already
        multiplied by freshness, exactly as `csia_consequence.support`
        defines it. `freshness` is the unmultiplied freshness, used only to
        split ACTIVE into fresh and STALE.
        """
        hypotheses = tuple(hypotheses)
        active = tuple(sorted(k for k, w in weights.items()
                              if w > GATE_EPSILON))
        gated = tuple(sorted(k for k, w in weights.items()
                             if w <= GATE_EPSILON))
        stale = tuple(sorted(k for k in active
                             if freshness.get(k, 1.0) < STALE_BELOW))
        for k in active:
            self._ever_active.add(k)
            self._first_active_t.setdefault(k, float(t))
        withdrawn = tuple(sorted(self._ever_active - set(active)))
        for k in withdrawn:
            self._lost_t.setdefault(k, float(t))

        report = _support.classify(
            hypotheses=hypotheses, low_sets=self.low_sets, gates=weights,
            timestamp_s=float(t), provenance=self.provenance,
            gate_epsilon=GATE_EPSILON, contradictory=tuple(contradictory))

        sep = tuple(sorted(
            {f for a, b in _pairs(hypotheses)
             for f in _support.separating_features(self.low_sets, a, b)
             if f in active}))

        if report.status == IDENTIFIABLE:
            attribution = SUPPORTED
        elif report.status == AMBIGUOUS:
            attribution = PARTIAL
        else:
            attribution = UNSUPPORTED

        return SupportView(
            t=float(t),
            evidence=EvidenceView(active, gated, stale, withdrawn,
                                  tuple(sorted(contradictory))),
            hypotheses=hypotheses, support_status=report.status,
            attribution_status=attribution, leader=leader,
            leader_weight=float(leader_weight), separating_features=sep,
            reason=report.reason, provenance=self.provenance,
            map_id=self.map_id)

    def evidence_loss_latency(self, feature: str) -> Optional[float]:
        """Seconds from a feature first being active to it being withdrawn."""
        if feature not in self._first_active_t or feature not in self._lost_t:
            return None
        return round(self._lost_t[feature] - self._first_active_t[feature], 6)


def _pairs(items: Sequence[str]):
    items = tuple(items)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            yield items[i], items[j]
