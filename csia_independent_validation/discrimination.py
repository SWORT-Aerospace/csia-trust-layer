"""A frozen faithful reduction of pairwise output-set active discrimination.

WHAT THIS IS NOT
----------------
It is **not** an implementation of Ni, Ornik, Chou and Coogan
(arXiv:2606.19590v1). That paper's primary text could not be retrieved from
this container -- seven endpoints, all refused, recorded in
``results/EXTERNAL_ACCESS_CHECK.json`` -- so nothing here is a reproduction of
its method and no statement in this module describes what that paper does.

What it is: the **pairwise output-set overlap objective**, in the form the
user-supplied related-work draft writes it,

    J(pi) = sum over pairs q of  min over t of  Vol( intersection of Y_m(t) )

reduced to this phase's setting. The reduction is one-dimensional in the output
(terminal voltage), and the reachable output set is over-approximated by
enumerating the declared nuisance envelope rather than by an interval inclusion
function over a nonlinear state model. ``PREREGISTRATION_AMENDMENT_3.md`` §2
fixes the reduction; this module implements it and adds nothing.

THE THREE OUTCOMES, WHICH ARE NOT THE SAME THING
------------------------------------------------
The supplied draft is explicit that zero intersection **volume** does not imply
an empty intersection: two intervals that touch at a point have zero volume and
a non-empty intersection. A baseline that reports "zero overlap" for both is
reporting a surrogate as though it were the thing.

So every query returns three fields:

``zero_volume``
    the intersection has measure zero;
``empty_intersection``
    the sets genuinely do not meet;
``separation_margin``
    the signed gap. Positive means strictly apart, and the number is the gap.

``tests/test_iv_discrimination.py`` builds a touching-set counterexample where
the first is true and the second is false.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .plants import QParams, SYNTHETIC_Q, SYNTHETIC_SENSING, Sensing, simulate

LAYER = "B"
TRUTH_BEARING = True
SCHEMA = "csia.independent_validation.discrimination/1"

PROVENANCE = "FROZEN_REDUCTION_NOT_A_REPRODUCTION"

#: The declared nuisance envelope, enumerated. Same grid as ``openset.py``, so
#: the two modules describe one declared model rather than two.
R1_GRID = (0.004, 0.012, 0.020)
TAU_GRID = (1.0, 6.3, 40.0)
DRIFT_GRID = (0.0, 1.0e-3)

#: How many sensor sigmas the output interval is widened by. Declared.
K_SIGMA = 3.0


@dataclass(frozen=True)
class Interval:
    """A closed real interval. Degenerate intervals are allowed and meaningful."""

    low: float
    high: float

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"empty interval [{self.low}, {self.high}]")

    @property
    def width(self) -> float:
        return self.high - self.low

    def intersect(self, other: "Interval") -> Tuple[float, float]:
        """``(overlap_volume, separation_margin)``.

        ``overlap_volume`` is the length of the intersection, zero when the
        intervals touch at a point or do not meet. ``separation_margin`` is the
        signed gap: positive when they are strictly apart, exactly zero when
        they touch, negative by the overlap when they cross. The two carry
        different information and that is the whole point of returning both.
        """
        low = max(self.low, other.low)
        high = min(self.high, other.high)
        overlap = max(high - low, 0.0)
        gap = max(other.low - self.high, self.low - other.high)
        return overlap, gap


@dataclass(frozen=True)
class PairOutcome:
    """One hypothesis pair at the time that separates it best."""

    hypothesis_a: float
    hypothesis_b: float
    best_time_s: float
    overlap_volume: float
    separation_margin: float

    @property
    def zero_volume(self) -> bool:
        return self.overlap_volume <= 0.0

    @property
    def empty_intersection(self) -> bool:
        """Strictly apart. Touching sets have zero volume and are NOT empty."""
        return self.separation_margin > 0.0

    @property
    def touching(self) -> bool:
        """The case the surrogate cannot see: zero volume, non-empty."""
        return self.zero_volume and not self.empty_intersection

    def to_dict(self) -> Dict:
        return {
            "hypothesis_a": self.hypothesis_a,
            "hypothesis_b": self.hypothesis_b,
            "best_time_s": self.best_time_s,
            "overlap_volume": self.overlap_volume,
            "separation_margin": self.separation_margin,
            "zero_volume": self.zero_volume,
            "empty_intersection": self.empty_intersection,
            "touching": self.touching,
        }


def output_set(command, *, magnitude: float, plant: str = "Q1",
               duration: float = 8.0, seed: int = 0,
               k_sigma: float = K_SIGMA) -> List[Interval]:
    """Interval over-approximation of ``Y_h(t)`` for one hypothesis.

    Enumerates the declared nuisance envelope and takes the per-sample minimum
    and maximum, then widens by ``k_sigma`` times the declared voltage sigma.
    This is an over-approximation of a *sampled* envelope, not of a continuum:
    a finer grid can only widen it, so every separation reported here is, if
    anything, optimistic. The docstring says so because a reader will not
    otherwise know.
    """
    base = QParams(**SYNTHETIC_Q)
    sensing = Sensing(**{**SYNTHETIC_SENSING, "sigma_v": 0.0, "sigma_i": 0.0})
    lows: Optional[np.ndarray] = None
    highs: Optional[np.ndarray] = None
    times: Optional[np.ndarray] = None
    for r1, tau, drift in itertools.product(R1_GRID, TAU_GRID, DRIFT_GRID):
        observation, _ = simulate(
            command, plant=plant, duration=duration, seed=seed,
            params=replace(base, r1=r1, tau1_s=tau), sensing=sensing,
            r0_delta=magnitude, drift_v_per_s=drift)
        values = np.asarray(observation.v_meas, dtype=float)
        if lows is None:
            lows, highs, times = values.copy(), values.copy(), observation.t
        else:
            lows = np.minimum(lows, values)
            highs = np.maximum(highs, values)
    assert lows is not None and highs is not None
    pad = k_sigma * SYNTHETIC_SENSING["sigma_v"]
    return [Interval(float(low) - pad, float(high) + pad)
            for low, high in zip(lows, highs)]


def separate(set_a: Sequence[Interval], set_b: Sequence[Interval], *,
             times: Optional[Sequence[float]] = None,
             label_a: float = 0.0, label_b: float = 0.0) -> PairOutcome:
    """The time at which two hypothesis output sets overlap least.

    Follows the objective's ``min over t`` literally: the pair is separable if
    it separates at *any* sampled time, so the reported time is the best one.
    """
    if len(set_a) != len(set_b):
        raise ValueError("both output sets must be sampled on the same grid")
    if not set_a:
        raise ValueError("empty output set")
    best_index = 0
    best_overlap = math.inf
    best_gap = -math.inf
    for index, (a, b) in enumerate(zip(set_a, set_b)):
        overlap, gap = a.intersect(b)
        if (overlap, -gap) < (best_overlap, -best_gap):
            best_overlap, best_gap, best_index = overlap, gap, index
    moment = (float(times[best_index]) if times is not None
              else float(best_index))
    return PairOutcome(hypothesis_a=label_a, hypothesis_b=label_b,
                       best_time_s=moment, overlap_volume=best_overlap,
                       separation_margin=best_gap)


def objective(pairs: Iterable[PairOutcome]) -> float:
    """``J`` as the draft writes it: the summed best-case overlap volume.

    A surrogate. It is zero for a touching pair and zero for a strictly
    separated one, which is exactly the deficiency this module reports
    alongside it rather than hiding.
    """
    return float(sum(pair.overlap_volume for pair in pairs))


def hausdorff(set_a: Sequence[Interval],
              set_b: Sequence[Interval]) -> float:
    """Worst per-sample Hausdorff distance between the two interval families.

    Reported beside the volume surrogate because it distinguishes cases the
    volume cannot: it is strictly positive for touching sets.
    """
    if len(set_a) != len(set_b):
        raise ValueError("both output sets must be sampled on the same grid")
    return max(max(abs(a.low - b.low), abs(a.high - b.high))
               for a, b in zip(set_a, set_b))


def pairwise(command, *, magnitudes: Sequence[float], plant: str = "Q1",
             duration: float = 8.0, seed: int = 0) -> List[PairOutcome]:
    """Every hypothesis pair, at its own best separating time."""
    sets = {m: output_set(command, magnitude=m, plant=plant,
                          duration=duration, seed=seed)
            for m in magnitudes}
    observation, _ = simulate(command, plant=plant, duration=duration,
                              seed=seed)
    out: List[PairOutcome] = []
    for a, b in itertools.combinations(sorted(sets), 2):
        out.append(separate(sets[a], sets[b], times=observation.t,
                            label_a=a, label_b=b))
    return out


def nominal_versus(command, *, magnitude: float, plant: str = "Q1",
                   duration: float = 8.0, seed: int = 0) -> PairOutcome:
    """The one pair the pre-action gate asks about: nominal against the target."""
    nominal = output_set(command, magnitude=0.0, plant=plant,
                         duration=duration, seed=seed)
    faulted = output_set(command, magnitude=magnitude, plant=plant,
                         duration=duration, seed=seed)
    observation, _ = simulate(command, plant=plant, duration=duration,
                              seed=seed)
    return separate(nominal, faulted, times=observation.t, label_a=0.0,
                    label_b=magnitude)
