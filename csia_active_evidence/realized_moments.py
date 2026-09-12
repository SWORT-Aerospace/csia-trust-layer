"""The two sums that decide whether a probe actually happened.

    S_II = sum (I_k - Ibar)^2            did the current move?
    S_tI = sum (t_k - tbar)(I_k - Ibar)  did it move in step with time?

BOTH ARE COMPUTED FROM MEASURED CURRENT, ALWAYS
------------------------------------------------
`probes.py` can say what it commanded. `battery_1rc.py` knows what the
current truly was. Neither is available to a vehicle after the fact: a
flight log contains `i_meas`. Every function here therefore takes the
measured channel, and `rcec.py` has no parameter through which the true one
could be passed. That is the whole correction AE-F5 forced.

    S_II IS ON THE MEASURED CHANNEL AND THEREFORE INFLATED.
    S_II(measured) = S_II(true) + N sigma_I^2 in expectation.

`deconvolved_s_ii` removes that, and refuses when the remainder does not
clear the sampling error of the estimate itself -- the AE-F3 defect, which
accepted a pure-noise hover as excited on about half of all windows. The
excitation condition is checked against the DECONVOLVED value, because
sensor noise is not excitation.

THE ONLINE RECURSION
--------------------
`MomentAccumulator` maintains both sums in one pass with bounded state, so a
feedback probe can ask "how much time-imbalance have I accumulated so far"
without storing the trajectory. It uses Welford-style centred updates rather
than raw power sums, because raw sums of `t^2` over a long window lose
precision exactly when the answer matters.

    IT CAN ONLY EVER SEE THE PAST.

`MomentAccumulator.remaining_correction` answers what the UNEXECUTED part of
a waveform must do to bring `S_tI` back to zero. A controller that consulted
future samples would be able to cancel any drift and would be worthless, so
this class has no method that accepts one, and `tests/test_rcec.py` asserts
the online path reproduces the batch value on the prefix it has seen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Moments:
    """Realized excitation statistics over one window."""

    n: int
    mean_i: float
    s_ii: float               # amp^2 * sample, on the MEASURED channel
    s_ti: float               # amp * second * sample
    var_t: float
    duration_s: float

    @property
    def lever_arm_s(self) -> float:
        """S_tI / S_II, seconds. The drift-aliasing lever arm."""
        return 0.0 if self.s_ii <= 0 else self.s_ti / self.s_ii

    @property
    def var_i_measured(self) -> float:
        return 0.0 if self.n <= 0 else self.s_ii / self.n

    def to_dict(self) -> dict:
        out = asdict(self)
        out["lever_arm_s"] = self.lever_arm_s
        out["var_i_measured"] = self.var_i_measured
        return out


def moments(t, i_measured) -> Moments:
    """Compute both sums from a measured current trace. No true values."""
    t = np.asarray(t, dtype=float)
    i = np.asarray(i_measured, dtype=float)
    if t.shape != i.shape:
        raise ValueError("t and current must have the same shape")
    if t.size < 3:
        raise ValueError("at least 3 samples are needed for a second moment")
    tc = t - t.mean()
    ic = i - i.mean()
    return Moments(n=int(i.size), mean_i=float(i.mean()),
                   s_ii=float(np.dot(ic, ic)), s_ti=float(np.dot(tc, ic)),
                   var_t=float(np.dot(tc, tc) / t.size),
                   duration_s=float(t[-1] - t[0]))


def deconvolved_s_ii(m: Moments, sigma_i: float,
                     k_sigma: float = 3.0) -> Optional[float]:
    """S_II with the sensor-noise power removed, or None if indistinguishable.

    E[S_II(measured)] = S_II(true) + N sigma_I^2. Subtracting is necessary and
    NOT SUFFICIENT: the estimate has its own sampling error, so a pure-noise
    window leaves a positive remainder about half the time. The remainder must
    clear `k_sigma` times that sampling error, which for a sum of N squared
    normals is `sigma_I^2 * sqrt(2N)`.

    Returns None rather than a small positive number, so a caller cannot
    accidentally treat noise as a little bit of excitation.
    """
    if sigma_i < 0:
        raise ValueError("sigma_i must be non-negative")
    excess = m.s_ii - m.n * sigma_i ** 2
    floor = k_sigma * (sigma_i ** 2) * math.sqrt(2.0 * m.n)
    return None if excess <= floor else excess


def attenuation(m: Moments, sigma_i: float) -> float:
    """lambda on the measured channel: var_true / var_measured."""
    if m.var_i_measured <= 0:
        return 0.0
    true_var = max(m.var_i_measured - sigma_i ** 2, 0.0)
    return true_var / m.var_i_measured


class MomentAccumulator:
    """One-pass, bounded-state, past-only accumulation of both moments.

    Numerically stable centred updates. `update` returns nothing: a caller
    that wants a decision asks for one explicitly, so a stale read cannot be
    mistaken for a fresh one.
    """

    __slots__ = ("_n", "_mt", "_mi", "_stt", "_sii", "_sti", "_t0", "_tlast")

    def __init__(self):
        self._n = 0
        self._mt = 0.0
        self._mi = 0.0
        self._stt = 0.0
        self._sii = 0.0
        self._sti = 0.0
        self._t0 = None
        self._tlast = None

    def update(self, t: float, i_measured: float) -> None:
        self._n += 1
        n = self._n
        dt = t - self._mt
        di = i_measured - self._mi
        self._mt += dt / n
        self._mi += di / n
        self._stt += dt * (t - self._mt)
        self._sii += di * (i_measured - self._mi)
        self._sti += dt * (i_measured - self._mi)
        if self._t0 is None:
            self._t0 = t
        self._tlast = t

    @property
    def n(self) -> int:
        return self._n

    def snapshot(self) -> Moments:
        if self._n < 3:
            raise ValueError("fewer than 3 samples accumulated")
        return Moments(n=self._n, mean_i=self._mi, s_ii=self._sii,
                       s_ti=self._sti, var_t=self._stt / self._n,
                       duration_s=(self._tlast - self._t0))

    def remaining_correction(self, t_remaining, target_lever_s: float = 0.0):
        """What the UNEXECUTED part must contribute to reach the target.

        Returns the required additional `sum (t - tbar)(I - Ibar)` given what
        has already happened. It is an arithmetic identity on the past, not a
        prediction: a caller still has to find a waveform that delivers it
        within its authority, and `moment_feedback.py` refuses when it
        cannot.
        """
        if self._n < 3:
            return None
        want = target_lever_s * self._sii
        return want - self._sti


def time_orthogonal_reference(t, amplitude: float = 1.0,
                              cycles: int = 2) -> np.ndarray:
    """An analytically time-orthogonal current, for control 2.

    A cosine with a whole number of cycles, phased about the window midpoint,
    has `sum (t-tbar)(I-Ibar) = 0` for a SYMMETRIC sample grid. It is the
    known-answer stimulus the drift condition must pass, and its answer comes
    from the symmetry argument rather than from any code in this package.
    """
    t = np.asarray(t, dtype=float)
    mid = 0.5 * (t[0] + t[-1])
    span = max(float(t[-1] - t[0]), 1e-12)
    return amplitude * np.cos(2.0 * math.pi * cycles * (t - mid) / span)
