"""Phase 5 — the fast path. It emits suspicion and nothing else.

WHAT IT MAY SAY, ENFORCED BY STRUCTURE
---------------------------------------
Exactly three verdicts, and the type system is the enforcement:

    NO_CHANGE
    SUSPECTED_CHANGE
    PROVISIONAL_DEGRADATION

`FastAlert` is a frozen dataclass with no field in which a fault identity, a
sensor attribution, a landing authority or an actuator authority could be
expressed. There is no `fault`, no `source`, no `action` and no `level`
attribute, so the restriction is not a convention anyone has to remember --
a caller that wanted to smuggle an attribution through would have to change
this file, and a test asserts the field set.

WHY A SEPARATE DETECTOR AT ALL
-------------------------------
Phase 4 measured the frozen trust-persistence detector at a median 2.52 s
against 0.08 s for CUSUM at a matched observed false-alarm operating point,
with about 1.0 s of that being the `dwell_up` persistence requirement the
detector is built around. A persistence detector cannot alarm faster than its
dwell. The hypothesis this module exists to test is whether the *suspicion*
can be fast while the *attribution* stays slow and supported -- not whether
the persistence requirement was a mistake.

The statistic is the repository's own CUSUM, imported rather than
reimplemented, so that the fast path is not a different algorithm dressed up
as a contribution. `k` stays at its textbook 0.5 and the in-control
statistics stay frozen; only `h_fast` is swept, on `development` only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from csia.v1_1.sequential import CUSUM_K, GATE_EPS, IN_CONTROL, CusumBank

NO_CHANGE = "NO_CHANGE"
SUSPECTED_CHANGE = "SUSPECTED_CHANGE"
PROVISIONAL_DEGRADATION = "PROVISIONAL_DEGRADATION"

#: The closed vocabulary. A test asserts nothing else is ever emitted.
VERDICTS: Tuple[str, ...] = (NO_CHANGE, SUSPECTED_CHANGE,
                             PROVISIONAL_DEGRADATION)

#: Ticks the statistic must stay above `h_fast` before a suspicion is
#: upgraded from SUSPECTED to PROVISIONAL. Deliberately far below the frozen
#: failsafe's 25-tick dwell: the point of the fast path is to be early, and
#: the point of CSIA is to be right.
PROVISIONAL_TICKS = 5

#: This module holds no authority over anything. Read by tests and written
#: into every result document.
HAS_ACTUATOR_AUTHORITY = False
MAY_ATTRIBUTE = False


@dataclass(frozen=True)
class FastAlert:
    """One emission. Carries provenance; carries no attribution.

    The field set IS the contract. There is deliberately no `fault`,
    `source`, `hypothesis`, `action`, `level` or `authority` field, and a
    test asserts that, so a future edit that adds one fails loudly rather
    than quietly widening what the fast path is allowed to claim.
    """

    t: float
    detector_id: str
    verdict: str
    statistic: float
    threshold: float
    evidence_source: str
    freshness: float
    provenance: str
    detector_state: str
    provisional: bool

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError(
                f"{self.verdict!r} is not one of {VERDICTS}; the fast path's "
                "vocabulary is closed")

    def as_record(self) -> dict:
        return {
            "t": round(float(self.t), 6),
            "detector_id": self.detector_id,
            "verdict": self.verdict,
            "statistic": round(float(self.statistic), 6),
            "threshold": float(self.threshold),
            "evidence_source": self.evidence_source,
            "freshness": round(float(self.freshness), 6),
            "provenance": self.provenance,
            "detector_state": self.detector_state,
            "provisional": bool(self.provisional),
            "may_attribute": MAY_ATTRIBUTE,
            "has_actuator_authority": HAS_ACTUATOR_AUTHORITY,
        }


@dataclass
class FastChangeDetector:
    """A CUSUM-like fast path over one node's pre-transform residual.

    `node` must be one the frozen bank covers; `IN_CONTROL` has statistics
    for five nodes and explicitly none for `imu0`/`imu1`, which its own
    module records as a coverage fact rather than a gap to paper over.
    """

    node: str
    h_fast: float
    detector_id: str = "fast_cusum_v1"
    k: float = CUSUM_K
    _bank: Optional[CusumBank] = field(default=None, repr=False)
    _above: int = field(default=0, repr=False)

    def __post_init__(self):
        if self.node not in IN_CONTROL:
            raise KeyError(
                f"{self.node!r} has no frozen in-control statistic; "
                f"covered nodes are {sorted(IN_CONTROL)}")
        self._bank = CusumBank(k=self.k, h=float("inf"))
        self._above = 0

    @property
    def statistic(self) -> float:
        return float(self._bank.S[self.node])

    def update(self, t: float, lam: float, gate: float,
               freshness: float = 1.0) -> FastAlert:
        """One tick. A gated-off tick is not evidence and does not advance S.

        The gating rule is the frozen runtime's, not a new one: absence of
        evidence is not evidence of change, so an inactive tick neither
        advances the statistic nor resets it.
        """
        active = bool(gate > GATE_EPS)
        self._bank.update(self.node, float(lam), active)
        s = self.statistic

        if not active:
            state = "GATED"
        elif s > self.h_fast:
            self._above += 1
            state = "ABOVE"
        else:
            self._above = 0
            state = "BELOW"

        if state != "ABOVE":
            verdict, provisional = NO_CHANGE, False
        elif self._above >= PROVISIONAL_TICKS:
            verdict, provisional = PROVISIONAL_DEGRADATION, True
        else:
            verdict, provisional = SUSPECTED_CHANGE, True

        return FastAlert(
            t=float(t), detector_id=self.detector_id, verdict=verdict,
            statistic=s, threshold=float(self.h_fast),
            evidence_source=f"physics_lambda[{self.node}]",
            freshness=float(freshness),
            provenance="csia.v1_1.sequential.CusumBank (frozen), k=%.3f" % self.k,
            detector_state=state, provisional=provisional)


def first_times(alerts) -> Dict[str, Optional[float]]:
    """First time each verdict was emitted, or None. Order is not an input."""
    out: Dict[str, Optional[float]] = {v: None for v in VERDICTS
                                       if v != NO_CHANGE}
    for a in alerts:
        if a.verdict in out and out[a.verdict] is None:
            out[a.verdict] = float(a.t)
    return out
