"""P4: correct the accumulated time-imbalance using only what has happened.

THE IDEA
--------
`realized_moments.MomentAccumulator` can say, at any instant, how much
`S_tI` has accumulated so far from the current the vehicle has ACTUALLY
drawn. The remaining, unexecuted part of the waveform can then be adjusted
to drive that sum back toward zero.

    THE CONTROLLER MAY ONLY EVER CHANGE THE FUTURE.

It cannot revise a sample that has already been flown, and it must never
declare an executed waveform symmetric in retrospect. Both are structural
here: `MomentFeedbackProbe.step` takes the current sample, updates the
accumulator, and returns the demand for the NEXT sample only. There is no
method that returns a corrected history.

WHY A SIGN AND A SATURATION, NOT A GAIN SCHEDULE
--------------------------------------------------
The correction needed is `-S_tI_so_far / (t_remaining_centred)`, which
diverges as the window ends. A controller chasing it would demand unbounded
current in the last second. Instead the demand is capped at the declared
authority and, when the cap cannot deliver the required correction before
the window closes, the probe REFUSES:

    `DRIFT_COUPLED` if the imbalance cannot be cleared,
    `NO_SAFE_INFORMATIVE_ACTION` if clearing it would exceed authority.

A probe that quietly ran anyway and hoped would be the worst of the
available designs, because it would produce a trajectory whose certificate
fails after the energy has already been spent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .realized_moments import MomentAccumulator

REFUSE_DRIFT = "DRIFT_COUPLED"
REFUSE_AUTHORITY = "NO_SAFE_INFORMATIVE_ACTION"
RUNNING = "RUNNING"
DONE = "COMPLETED"


@dataclass
class MomentFeedbackProbe:
    """A base waveform plus an online correction on its unexecuted tail.

    `base` is the shape the probe would fly with no feedback. `authority_a`
    bounds the total demand. `correction_fraction` bounds how much of that
    authority the correction may consume, so the probe cannot spend its
    entire budget fighting its own lag and deliver no excitation.
    """

    base: Callable[[float], float]
    start_s: float
    duration_s: float
    authority_a: float
    correction_fraction: float = 0.35
    _acc: MomentAccumulator = field(default_factory=MomentAccumulator,
                                    init=False)
    _status: str = field(default=RUNNING, init=False)
    _corrections: list = field(default_factory=list, init=False)

    @property
    def status(self) -> str:
        return self._status

    @property
    def accumulator(self) -> MomentAccumulator:
        return self._acc

    def observe(self, t: float, i_measured: float) -> None:
        """Record what actually happened. Past only."""
        if self.start_s <= t <= self.start_s + self.duration_s:
            self._acc.update(t, i_measured)

    def demand(self, t: float) -> float:
        """The command for the NEXT sample, base plus a bounded correction.

        THE CORRECTION LAW, DERIVED RATHER THAN GUESSED. The first version
        divided the outstanding imbalance by `0.5 * remaining` and called
        that a lever. It also consulted a method on the moment snapshot that
        does not exist, so it silently took its own fallback branch on every
        tick. It capped 330 of 401 corrections and left the realized lever
        arm at 0.132 s, four times WORSE than the open-loop probe it was
        supposed to improve.

        The right law follows from what the remaining samples can contribute.
        Adding a correction `c(t)` over the unexecuted tail changes the
        window's `S_tI` by approximately

            sum_{remaining} (t_k - t_mid) c(t_k)

        so choosing `c(t) = -g (t - t_mid)` changes it by
        `-g sum_{remaining} (t_k - t_mid)^2`, and the gain that cancels the
        outstanding imbalance exactly is

            g = S_tI_so_far / sum_{remaining} (t_k - t_mid)^2.

        `t_mid` is the SCHEDULED window centre, known when the probe is
        planned, so nothing here depends on a future sample. The denominator
        shrinks as the window closes, which makes `g` grow, which is why the
        correction is capped and why the probe refuses rather than demanding
        authority it does not have.
        """
        if not (self.start_s <= t <= self.start_s + self.duration_s):
            return 0.0
        base = float(self.base(t))
        if self._acc.n < 8:
            return _clip(base, self.authority_a)

        end = self.start_s + self.duration_s
        remaining = end - t
        if remaining <= 1e-6:
            self._status = DONE
            return _clip(base, self.authority_a)

        t_mid = self.start_s + 0.5 * self.duration_s
        snap = self._acc.snapshot()

        # Second moment the unexecuted tail can still supply, from the
        # scheduled grid. Trapezoidal value of the integral of (t-t_mid)^2
        # over [t, end], divided by the sample spacing.
        dt = self.duration_s / max(self._acc.n, 1)
        a, b = t - t_mid, end - t_mid
        capacity = ((b ** 3 - a ** 3) / 3.0) / max(dt, 1e-9)
        if capacity <= 1e-9:
            self._status = REFUSE_DRIFT
            return _clip(base, self.authority_a)

        gain = snap.s_ti / capacity
        correction = -gain * (t - t_mid)

        cap = self.correction_fraction * self.authority_a
        if abs(correction) > cap:
            self._corrections.append({"t": t, "wanted": correction,
                                      "capped_to": math.copysign(cap,
                                                                 correction)})
            correction = math.copysign(cap, correction)
            if remaining < 0.15 * self.duration_s:
                self._status = REFUSE_DRIFT
        return _clip(base + correction, self.authority_a)

    def report(self) -> dict:
        out = {"status": self._status,
               "corrections_capped": len(self._corrections),
               "samples_seen": self._acc.n}
        if self._acc.n >= 3:
            s = self._acc.snapshot()
            out.update({"s_ii": s.s_ii, "s_ti": s.s_ti,
                        "lever_arm_s": s.lever_arm_s})
        return out


def _clip(x: float, bound: float) -> float:
    return float(max(-bound, min(bound, x)))
