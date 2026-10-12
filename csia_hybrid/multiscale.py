"""Phase 5 — fast, medium and slow accumulators over one node.

WHY THREE TIMESCALES
--------------------
Phase 4 measured two things that pull in opposite directions. The frozen
trust-persistence detector alarms at a median 2.52 s on an ABRUPT fault,
about 1.0 s of which is its `dwell_up` requirement; and it has an observed
false-alarm rate of zero at every one of its declared thresholds, which the
memoryless comparators do not. A single accumulator has to pick a point on
that curve. Three do not.

    FAST    short dwell, high threshold  -- catches the step, tolerates the
                                            noise only because it demands a
                                            large excursion
    MEDIUM  the frozen dwell, unchanged  -- the Phase-4 operating point,
                                            included so the ablation has a
                                            like-for-like arm
    SLOW    long dwell, low threshold    -- catches the ramp that never makes
                                            a large excursion at all

The combined verdict is the EARLIEST of the three, which is the only rule
that can improve latency without changing what any single accumulator does.
It also means the combined false-alarm rate is bounded below by the worst of
the three, and the write-up must report that rather than presenting the
earliest-wins rule as free.

THE RESET RULE IS PREREGISTERED AND OBSERVABLE
-----------------------------------------------
An adaptive reset that fires on "the statistic looks wrong" is a tuning knob
wearing a disguise. The preregistration requires a reset to be triggered by
an observable condition, so the only one implemented here is:

    STRUCTURAL_LOSS_OF_SUPPORT -- the gate closed, so the evidence that was
    accumulating is no longer being measured at all.

That is the frozen runtime's own rule for what stops being evidence, and it
is not a new judgement. No reset fires on magnitude, on rate, or on
disagreement with another accumulator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from csia.v1_1.sequential import GATE_EPS

FAST = "FAST"
MEDIUM = "MEDIUM"
SLOW = "SLOW"
SCALES: Tuple[str, ...] = (FAST, MEDIUM, SLOW)

#: The one preregistered reset condition. Observable, and the frozen
#: runtime's own definition of "this stopped being evidence".
RESET_STRUCTURAL_LOSS = "STRUCTURAL_LOSS_OF_SUPPORT"
RESET_REASONS: Tuple[str, ...] = (RESET_STRUCTURAL_LOSS,)


@dataclass
class Accumulator:
    """One timescale: a dwell over a threshold on the trust series.

    Deliberately the SAME shape as the frozen detector -- `trust < theta`
    for `dwell` consecutive active ticks -- so that the multi-timescale arm
    differs from `B0` in its parameters and its combination rule, and in
    nothing else. An arm that also changed the statistic would not be an
    ablation of timescale.
    """

    name: str
    theta: float
    dwell: int
    _run: int = field(default=0, repr=False)
    _resets: int = field(default=0, repr=False)

    def update(self, trust: float, gate: float) -> bool:
        """One tick. Returns True on the tick the dwell is satisfied."""
        if gate <= GATE_EPS:
            # Structural loss of support: the evidence is not being measured,
            # so a partial run is not carried across the gap.
            if self._run:
                self._resets += 1
            self._run = 0
            return False
        if trust < self.theta:
            self._run += 1
            if self._run >= self.dwell:
                self._run = 0
                return True
        else:
            self._run = 0
        return False

    @property
    def resets(self) -> int:
        return self._resets


@dataclass
class MultiScaleDetector:
    """Fast, medium and slow together. Earliest alarm wins, and it is recorded
    WHICH scale won, because a latency improvement nobody can attribute to a
    timescale is not an ablation result."""

    theta_fast: float
    dwell_fast: int
    theta_medium: float
    dwell_medium: int
    theta_slow: float
    dwell_slow: int
    _acc: Dict[str, Accumulator] = field(default_factory=dict, repr=False)
    _times: Dict[str, List[float]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._acc = {
            FAST: Accumulator(FAST, self.theta_fast, self.dwell_fast),
            MEDIUM: Accumulator(MEDIUM, self.theta_medium, self.dwell_medium),
            SLOW: Accumulator(SLOW, self.theta_slow, self.dwell_slow),
        }
        self._times = {s: [] for s in SCALES}

    def update(self, t: float, trust: float, gate: float) -> List[str]:
        fired = []
        for scale in SCALES:
            if self._acc[scale].update(trust, gate):
                fired.append(scale)
                self._times[scale].append(float(t))
        return fired

    def all_times(self) -> Dict[str, List[float]]:
        """EVERY alarm time per scale, not just the first.

        Recording only the first is a measurement defect, not a shortcut: an
        accumulator that fires once during convergence and again after the
        fault would be scored as having alarmed at the convergence time and
        never detected the fault at all. The combined series below is what a
        delay may be computed from, and it needs every crossing.
        """
        return {s: list(v) for s, v in self._times.items()}

    def combined_times(self) -> List[float]:
        """All alarms from all three scales, in time order."""
        return sorted(t for times in self._times.values() for t in times)

    def first_alarm(self) -> Tuple[Optional[float], Optional[str]]:
        """Earliest alarm across the three, and which scale produced it."""
        times = [(v[0], s) for s, v in self._times.items() if v]
        if not times:
            return None, None
        t, scale = min(times)
        return t, scale

    def scale_of(self, when: float) -> Optional[str]:
        """Which scale produced the alarm at `when` (earliest scale wins)."""
        for scale in SCALES:
            if any(abs(t - when) < 1e-9 for t in self._times[scale]):
                return scale
        return None

    def per_scale(self) -> Dict[str, Optional[float]]:
        return {s: (v[0] if v else None) for s, v in self._times.items()}

    def resets(self) -> Dict[str, int]:
        return {s: self._acc[s].resets for s in SCALES}
