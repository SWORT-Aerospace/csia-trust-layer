"""P2: pre-shape a command so the REALIZED current comes out time-orthogonal.

THE PROBLEM THIS SOLVES
------------------------
AE-F5 measured that a palindromic command produces a non-palindromic
current, because the loop lags. A first-order lag with time constant `tau`
turns a symmetric command into an asymmetric response, and the resulting
`S_tI` is not zero however carefully the command was drawn.

THE COMPENSATION
----------------
If the command-to-current map is approximately

    tau * dI/dt + I = u

then feeding `u = w + tau * dw/dt` makes `I ~= w`. That is a lead
compensator, and it is the textbook inverse of the lag. Two things stop it
being free:

  * differentiating amplifies noise and can demand more authority than the
    vehicle has. `compensate` therefore CLIPS the compensated command to a
    declared bound and REPORTS the clipping, rather than silently returning
    a waveform that cannot be flown;
  * the inverse is only as good as `tau`. A wrong `tau` over-corrects.

TAU IS ESTIMATED ON DEVELOPMENT SEEDS ONLY
--------------------------------------------
`estimate_lag` fits `tau` from a step response on seeds the campaign
declares as development. Fitting `tau` on the trajectory being scored and
then scoring it would be the train-on-test error MX-030 had to fix, one
level up, and `tests/test_rcec.py` asserts the campaign's development and
locked seed sets are disjoint.

WHAT IT DOES NOT DO
-------------------
It does not guarantee the realized current is orthogonal. It makes a
prediction that the RCEC then CHECKS on the realized telemetry. If the
compensation fails, the certificate says `DRIFT_COUPLED` and the probe is
refused. The compensator is a proposal; the certificate is the authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class LagModel:
    """A first-order command-to-current lag, with the fit's own residual."""

    tau_s: float
    rms_residual_a: float
    fitted_on_seeds: Tuple[int, ...]

    def to_dict(self) -> dict:
        return {"tau_s": self.tau_s, "rms_residual_a": self.rms_residual_a,
                "fitted_on_seeds": list(self.fitted_on_seeds)}


def estimate_lag(simulate, seeds, *, hz: float = 50.0,
                 step_a: float = 6.0, duration: float = 12.0,
                 step_at: float = 4.0,
                 tau_grid=None) -> LagModel:
    """Fit `tau` from a step response on DEVELOPMENT seeds.

    BY DIRECT RESIDUAL MINIMISATION, NOT BY LINEARISATION. The first
    implementation here fitted `-ln(1 - fraction) = t / tau` by least
    squares, which returned 0.569 s against a plant lag of 0.250 s -- a
    factor of 2.3. The linearisation diverges as the response approaches its
    asymptote, so the noisiest, least informative samples at the end of the
    window carried the largest weight and dominated the fit. A compensator
    built on a `tau` that is 2.3x too large over-corrects, demands authority
    it does not need, and would have been reported as a failure of the
    compensation idea rather than of the fit.

    Minimising the RMS residual against the model directly has no such
    weighting: every sample counts once, in amps.

    THE WORD "CONSERVATIVE" WAS WITHDRAWN HERE. An earlier revision said
    underestimating `tau` is conservative because it under-compensates. That
    was asserted, not shown, and a signed sweep over ratios from 0.25 to 4.0
    of the true lag measured two things that contradict it:

      * the achieved error is NOT monotone in the lag ratio
        (`error_is_monotone_in_lag_ratio: false` in
        `results/RCEC_DIAGNOSTICS.json`);
      * at a four-fold underestimate the REALIZED DRIFT LEVER CHANGES SIGN,
        at true lags of 0.10 s and 0.25 s. A sign change moves the bias to
        the other side of the truth, which is not what conservative means.

    What survives is narrower and is stated as a measurement rather than a
    property: on the swept grid the worst achieved error under
    underestimation (0.0196 ohm) was not larger than under the exact lag
    (0.0204 ohm), while overestimation was worse (0.0232 ohm). That is a
    fact about this grid. It is not monotonicity and it is not a guarantee.

    `simulate` is passed in rather than imported so this module never
    depends on one particular plant, and so a test can hand it a plant with
    a known `tau` and check the fit recovers it.
    """
    if tau_grid is None:
        tau_grid = np.geomspace(0.02, 4.0, 240)
    taus, residuals = [], []
    for seed in seeds:
        tr = simulate(lambda t: step_a if t >= step_at else 0.0,
                      duration=duration, seed=int(seed))
        m = tr.t >= step_at
        t = tr.t[m] - step_at
        i = tr.i_meas[m]
        base = float(np.mean(tr.i_meas[tr.t < step_at]))
        final = float(np.mean(i[t > t[-1] * 0.6]))
        amp = final - base
        if abs(amp) < 1e-6:
            continue
        best, best_rms = None, float("inf")
        for tau in tau_grid:
            pred = base + amp * (1.0 - np.exp(-t / tau))
            rms = float(np.sqrt(np.mean((i - pred) ** 2)))
            if rms < best_rms:
                best, best_rms = float(tau), rms
        taus.append(best)
        residuals.append(best_rms)
    if not taus:
        raise RuntimeError("no usable step response; the lag cannot be "
                           "estimated and no default may be substituted")
    return LagModel(tau_s=float(np.median(taus)),
                    rms_residual_a=float(np.median(residuals)),
                    fitted_on_seeds=tuple(int(s) for s in seeds))


def compensate(waveform, t, lag: LagModel, *, authority_a: float
               ) -> Tuple[np.ndarray, dict]:
    """`u = w + tau * dw/dt`, clipped to the declared authority.

    Returns the command and a report. The report is not decoration: a
    compensated waveform that hit the authority limit is no longer the
    inverse of the lag, and the caller must know that rather than discover
    it from a failed certificate.
    """
    w = np.asarray(waveform, dtype=float)
    t = np.asarray(t, dtype=float)
    if w.shape != t.shape or w.size < 3:
        raise ValueError("waveform and t must match and have 3+ samples")
    derivative = np.gradient(w, t)
    raw = w + lag.tau_s * derivative
    clipped = np.clip(raw, -authority_a, authority_a)
    hit = int(np.count_nonzero(np.abs(raw) > authority_a))
    return clipped, {
        "tau_s": lag.tau_s,
        "authority_a": authority_a,
        "samples_clipped": hit,
        "fraction_clipped": hit / w.size,
        "peak_demanded_a": float(np.max(np.abs(raw))),
        "compensation_is_exact_only_if_unclipped": hit == 0,
    }


def as_callable(command, t) -> Callable[[float], float]:
    """Turn a sampled command into the `simulate(command=...)` callable."""
    command = np.asarray(command, dtype=float)
    t = np.asarray(t, dtype=float)
    t0 = float(t[0])
    dt = float(t[1] - t[0])
    n = command.size

    def fn(x: float) -> float:
        k = int(round((x - t0) / dt))
        return float(command[k]) if 0 <= k < n else 0.0

    return fn
