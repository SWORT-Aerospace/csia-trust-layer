"""The polarization bound, evaluated rather than guessed at.

WHY A THIRD ATTEMPT
-------------------
The first version used worst-case `R1` outright, which made every waveform
fail and was caught by a control (RC-2). The second replaced it with

    R1_max / sqrt(1 + (2 pi f_eff tau_min)^2)

evaluated at the power-weighted mean frequency of the realized current. That
is what `rcec.py` shipped, and IT IS UNSOUND. Measured against direct
simulation of the branch it bounds, on a three-cycle palindromic probe over
an eight-second window with R1 in [0.004, 0.020] and tau in [1, 40]:

    committed bound   0.00155 ohm
    true worst case   0.00797 ohm

The bound understates by a factor of five, and understating an error term is
the false-certification direction. Two things are wrong with it:

  * `Re[Z1]` is `R1 / (1 + (w tau)^2)`, not `R1 / sqrt(1 + (w tau)^2)`. A
    regression attributes to resistance the IN-PHASE part of the branch
    voltage, not its magnitude;
  * evaluating a nonlinear function at a mean frequency is not the mean of
    the function, and more importantly the whole frequency-domain argument
    assumes STEADY STATE. Over a window shorter than the branch's time
    constant the branch never reaches it, and the initial-condition
    transient dominates. On a 1.2 A/s ramp over 8 s with tau = 13.5 s the
    true apparent resistance is 0.0176 ohm, larger than `R1` itself, and no
    steady-state spectral formula produces that number at all.

A CLOSED FORM WAS TRIED AND ABANDONED
---------------------------------------
Adding a Cauchy-Schwarz transient term to the spectral term gives a bound
that is sound for oscillating probes and VIOLATED for low-variance ones: 80
violations in 1200 (waveform, R1, tau, initial condition) combinations,
because the implicit periodic extension in the transform misrepresents a
ramp. Tightening it to use the computed transient lever arm rather than a
Cauchy-Schwarz product reduced the violations but did not remove them.

THE ANSWER IS THAT NO CLOSED FORM IS NEEDED
---------------------------------------------
The branch is linear with one scalar state. Evaluating it is cheaper than
arguing about it:

    bound = max over the DECLARED envelope of |cov(V1, I) / var(I)|

`V1` is obtained by integrating `tau V1' + V1 = R1 I` over the waveform, and
the maximum is taken over declared ranges of `R1`, `tau` and the initial
condition. It is exact for the branch it models, it costs about 40 ms, and
it uses **only the waveform**:

    NO FAULT LABEL, NO DIAGNOSTIC OUTCOME, NO FITTED PARAMETER ENTERS HERE.

That is the circularity the governing instruction warns about, and the
signature of `bound()` is arranged so there is no argument through which one
could be passed.

MEASURED, AND THE SCOPE OF THE CLAIM
--------------------------------------
Two different objects, kept apart. `bound` is an exhaustive maximum over a
FINITE grid of 105 model instances (5 values of R1, 7 of tau, 3 initial
conditions), so for those instances:

    BOUNDED OVER THE DECLARED DISCRETE MODEL GRID.

The true parameters are continuous and the grid has gaps between its nodes.
`validate` samples the continuum and finds:

    ZERO OBSERVED BOUND VIOLATIONS IN 1,800 PREREGISTERED SIMULATOR
    EVALUATIONS.

THAT IS NOT A PROOF OF SOUNDNESS ON THE CONTINUUM. Under an
independent-and-identically-distributed interpretation of those draws the
one-sided 95% rule-of-three upper limit on the violation rate is

    p_violation < 3/1800 ~= 0.00167

which is an upper confidence limit under an assumption, NOT a formal
guarantee. A bound holding at 105 enumerated and 1800 sampled points may
still fail between them. `research/active_evidence/realized_current/
POLARIZATION_BOUND_SCOPE.md` states what may and may not be said.

Tightness, meaning worst truth over bound, ranges from 0.57 to 0.90.
It discriminates: a six-cycle palindromic probe earns 0.0013 and a slow ramp
earns 0.44, a factor of 336, which is the whole reason waveform design is
worth doing.

WHAT IT DOES NOT ESTABLISH
---------------------------
Coverage is exhaustive only on the discrete grid, and sampled beyond it. If the true `R1`, `tau` or
initial condition lies outside what was declared, the bound is silent, and
`csia_active_evidence` has already measured what an under-declared envelope
costs for hysteresis: eleven false certificates in 290. The declaration is
load-bearing and must come from characterisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional, Sequence, Tuple

import numpy as np

SCHEMA = "csia.active_evidence.polarization/1"

#: Returned when the envelope is not declared. Never a zero.
UNBOUNDED = "UNBOUNDED_TERM"


@dataclass(frozen=True)
class PolarizationEnvelope:
    """What the operator declares about the branch. All of it required.

    `v1_initial_fraction` bounds the branch's state at the start of the
    window as a fraction of `R1 * max|I|`. One means the branch may be fully
    charged in either direction, which is the honest default after an
    unknown prior manoeuvre.
    """

    r1_min: float
    r1_max: float
    tau_min_s: float
    tau_max_s: float
    v1_initial_fraction: float = 1.0
    n_r1: int = 5
    n_tau: int = 7

    def __post_init__(self):
        if not 0.0 <= self.r1_min <= self.r1_max:
            raise ValueError("need 0 <= r1_min <= r1_max")
        if not 0.0 < self.tau_min_s <= self.tau_max_s:
            raise ValueError("need 0 < tau_min_s <= tau_max_s")
        if self.v1_initial_fraction < 0.0:
            raise ValueError("v1_initial_fraction must not be negative")
        if self.n_r1 < 2 or self.n_tau < 2:
            raise ValueError("at least two grid points per axis; a single "
                             "point is a guess wearing an envelope's name")

    def to_dict(self) -> dict:
        return asdict(self)


def apparent_resistance(i_measured, dt: float, r1: float, tau_s: float,
                        v1_initial: float = 0.0) -> float:
    """Exact apparent resistance a linear RC branch adds to a fitted slope.

    Integrates `tau V1' + V1 = R1 I` and returns `cov(V1, I) / var(I)`,
    which is what least squares attributes to resistance.
    """
    i = np.asarray(i_measured, dtype=float).ravel()
    if i.size < 3 or dt <= 0:
        return 0.0
    a = dt / max(tau_s, dt)
    v1 = float(v1_initial)
    out = np.empty(i.size)
    for k in range(i.size):
        v1 += a * (i[k] * r1 - v1)
        out[k] = v1
    ic = i - i.mean()
    denom = float(np.dot(ic, ic))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(ic, out - out.mean()) / denom)


def bound(i_measured, dt: float,
          envelope: Optional[PolarizationEnvelope]):
    """Worst apparent resistance over the declared envelope.

    NOTE THE SIGNATURE. It takes a current waveform and an envelope. There is
    no parameter for a fault, a hypothesis, a label or an outcome, so the
    bound cannot be made to depend on the answer it is helping to compute.

    Returns `UNBOUNDED` when no envelope is declared. Never a zero.
    """
    if envelope is None:
        return UNBOUNDED
    i = np.asarray(i_measured, dtype=float).ravel()
    if i.size < 3:
        return UNBOUNDED
    peak = float(np.max(np.abs(i)))
    worst = 0.0
    for r1 in np.linspace(envelope.r1_min, envelope.r1_max, envelope.n_r1):
        for tau in np.geomspace(envelope.tau_min_s, envelope.tau_max_s,
                                envelope.n_tau):
            amp = envelope.v1_initial_fraction * r1 * peak
            for v0 in (0.0, amp, -amp):
                worst = max(worst,
                            abs(apparent_resistance(i, dt, r1, tau, v0)))
    return worst


def validate(i_measured, dt: float, envelope: PolarizationEnvelope, *,
             draws: int = 200, seed: int = 0) -> dict:
    """Draw inside the envelope and confirm nothing exceeds the bound.

    The check the governing instruction requires: compare the claimed bound
    against direct simulation and expand it if the comparison fails. A
    violation here is a defect in `bound`, not a tolerance to widen.
    """
    b = bound(i_measured, dt, envelope)
    if b == UNBOUNDED:
        return {"bound": UNBOUNDED, "draws": 0, "violations": 0,
                "worst": None, "tightness": None}
    i = np.asarray(i_measured, dtype=float).ravel()
    peak = float(np.max(np.abs(i)))
    rng = np.random.default_rng(seed)
    worst, violations = 0.0, 0
    for _ in range(draws):
        r1 = float(rng.uniform(envelope.r1_min, envelope.r1_max))
        tau = float(math.exp(rng.uniform(math.log(envelope.tau_min_s),
                                         math.log(envelope.tau_max_s))))
        v0 = float(rng.uniform(-1.0, 1.0)) * envelope.v1_initial_fraction \
            * r1 * peak
        d = abs(apparent_resistance(i, dt, r1, tau, v0))
        worst = max(worst, d)
        if d > b * (1.0 + 1e-9):
            violations += 1
    return {"bound": b, "draws": draws, "violations": violations,
            "worst": worst, "tightness": (worst / b) if b > 0 else None,
            "sound_on_this_grid": violations == 0}


def spectral_steady_state(i_measured, dt: float, r1: float,
                          tau_s: float) -> float:
    """The steady-state term alone. KEPT, AND NOT USED FOR A DECISION.

    `sum_f Re[Z1(f)] |I(f)|^2 / sum_f |I(f)|^2`, the correct frequency-domain
    expression with the real part rather than the magnitude. It is retained so
    a reader can see how far the steady-state picture is from the truth over a
    window shorter than the time constant, and so a test can re-measure that
    gap rather than take this docstring's word for it.
    """
    i = np.asarray(i_measured, dtype=float).ravel()
    ic = i - i.mean()
    power = np.abs(np.fft.rfft(ic)) ** 2
    total = float(power.sum())
    if total <= 0:
        return 0.0
    w = 2.0 * math.pi * np.fft.rfftfreq(i.size, d=dt)
    return float(np.dot(r1 / (1.0 + (w * tau_s) ** 2), power) / total)
