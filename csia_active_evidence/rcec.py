"""The Realized-Current Excitation Certificate. Ten states, never a boolean.

THE QUESTION IT ANSWERS
------------------------
After the flight controller, plant dynamics, actuator lag, saturation,
battery dynamics and telemetry sampling have transformed a requested
diagnostic command into an actual current trajectory, did the vehicle
PHYSICALLY REALIZE enough excitation to resolve the target fault within a
declared error bound?

    NO PROBE MAY BE CALLED INFORMATIVE, DRIFT-CANCELLING, SYMMETRIC,
    SUFFICIENT OR AUTHORIZED ON THE BASIS OF ITS COMMAND WAVEFORM.

`certify()` takes `t`, `i_measured` and `v_measured`. There is no parameter
through which a true current, a commanded waveform or a plant state could be
passed, and `tests/test_rcec.py` asserts that by inspecting the signature.
The command is a proposal; the certificate is about what happened.

THE ERROR DECOMPOSITION, AND WHY IT IS A UNION BOUND
------------------------------------------------------
    B_total = |B_drift| + |B_EIV| + |B_dynamic| + |B_mismatch| + |B_sampling|

`B_dynamic` is the polarization term and it DEPENDS ON THE PROBE'S SPECTRUM,
not only on the pack. A probe whose energy sits above `1/(2 pi tau1)` sees
almost no polarization impedance. That is the one place in this file where a
better waveform earns a smaller error, and it is why waveform design is
worth doing at all.

Added in absolute value, not in quadrature. The terms are NOT independent:
open-circuit drift, polarization and a current-channel scale error all act on
the same regression through the same samples, and a root-sum-square would
assume a cancellation nobody has shown. A union bound is the weakest
assumption available and it is the one used.

    IF ANY TERM CANNOT BE BOUNDED FROM THE DECLARED INPUTS, THE CERTIFICATE
    RETURNS `MODEL_MISMATCH_LIMITED` AND NAMES THE UNBOUNDED TERM.

There is no path by which an unbounded term becomes a zero.

THE RESOLUTION RULE
-------------------
Set separation is the primary path:

    |B_total| + k * SE(Rhat)  <  c * |target change|

with `c < 1` declared in advance. A statistical interval would need an
exchangeability argument that flight ticks do not satisfy, so `SE` enters
only as one term inside a declared margin and never as a p-value.

THE RESIDUAL CHECK, AND WHY IT WAS MISSING
--------------------------------------------
An error budget bounds the terms a model KNOWS ABOUT. It says nothing about
a mechanism the model has no term for, and the first version of this file
had no way to notice one: it computed bounds, compared them to a margin, and
certified. A pack with an unmodelled oscillation would have been certified
with a confident number.

`certify` therefore fits the estimator and compares the RMS of its own
residual against what the declared channel noise predicts:

    expected residual RMS  =  sqrt(sigma_V^2 + R_ref^2 sigma_I^2)

If the realized residual exceeds that by more than `residual_tolerance`, the
data is not described by `V = E - I R` at all and the state is
`UNKNOWN_OR_MODEL_MISMATCH`. That is the open-set path, and it is inside the
certificate rather than bolted on beside it, because a caller who forgot to
run the extra check would otherwise get a clean certificate for a pack
behaving in a way nobody modelled.

ORDER OF EVALUATION IS PART OF THE SEMANTICS
----------------------------------------------
Instrument validity, then execution integrity, then excitation, then drift,
then the error budget. A trace that never happened cannot be measurement
limited, and a certificate for a waveform that was clipped must not inherit
the proposal's numbers. Each state is returned with the reason that produced
it, and no state is ever collapsed into pass/fail inside a stored artifact.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict, field
from typing import Optional, Tuple

import numpy as np

from .realized_moments import (Moments, attenuation, deconvolved_s_ii,
                               moments)

SCHEMA = "csia.active_evidence.rcec/1"
SEMANTICS_VERSION = "csia.active_evidence.rcec.semantics/1"

CERTIFIED = "CERTIFIED_IN_MODEL"
INSUFFICIENT_EXCITATION = "INSUFFICIENT_EXCITATION"
DRIFT_COUPLED = "DRIFT_COUPLED"
MEASUREMENT_LIMITED = "MEASUREMENT_LIMITED"
MODEL_MISMATCH_LIMITED = "MODEL_MISMATCH_LIMITED"
CLIPPED_INVALID = "CLIPPED_CERTIFICATE_INVALID"
ABORTED_INCOMPLETE = "ABORTED_INCOMPLETE"
NO_SAFE_INFORMATIVE_ACTION = "NO_SAFE_INFORMATIVE_ACTION"
UNKNOWN_OR_MODEL_MISMATCH = "UNKNOWN_OR_MODEL_MISMATCH"
INVALID_INSTRUMENT = "INVALID_INSTRUMENT"

STATES = (CERTIFIED, INSUFFICIENT_EXCITATION, DRIFT_COUPLED,
          MEASUREMENT_LIMITED, MODEL_MISMATCH_LIMITED, CLIPPED_INVALID,
          ABORTED_INCOMPLETE, NO_SAFE_INFORMATIVE_ACTION,
          UNKNOWN_OR_MODEL_MISMATCH, INVALID_INSTRUMENT)

#: States in which a caller may act on the resistance estimate. Exactly one.
ACTIONABLE = (CERTIFIED,)

UNBOUNDED = "UNBOUNDED_TERM"


@dataclass(frozen=True)
class ErrorBudget:
    """Declared bounds. EVERY ONE IS AN ENGINEERING DECLARATION.

    A `None` means the quantity is not bounded by anything the operator has
    declared, and the certificate fails closed naming it. It does not mean
    zero, and there is no default that turns it into zero.
    """

    r_reference: float               # ohm, the resistance being estimated near
    target_delta_r: float            # ohm, the change worth resolving
    sigma_v: float                   # V, commissioned
    sigma_i: float                   # A, commissioned
    d_max: float                     # V/s, bound on open-circuit drift
    r1_max: Optional[float] = None   # ohm, bound on polarization resistance
    tau1_min_s: Optional[float] = None  # s, LOWER bound on the RC time constant
    scale_error_max: Optional[float] = None   # fractional current-gain error
    delay_max_s: float = 0.0         # s, current-channel transport delay
    quantum_i: float = 0.0           # A, current quantisation step
    c_fraction: float = 0.5          # the resolution fraction, c < 1
    k_sigma: float = 3.0
    min_samples: int = 50
    min_coverage: float = 0.90       # fraction of the window that must survive
    residual_tolerance: float = 3.0  # multiples of the predicted residual RMS

    def __post_init__(self):
        if not 0.0 < self.c_fraction < 1.0:
            raise ValueError("c_fraction must be strictly between 0 and 1")
        if self.target_delta_r <= 0 or self.sigma_v <= 0:
            raise ValueError("target_delta_r and sigma_v must be positive")
        if self.sigma_i < 0 or self.d_max < 0:
            raise ValueError("sigma_i and d_max must be non-negative")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Execution:
    """What actually happened to the action. Facts, not intentions."""

    proposed_digest: str
    authorized_digest: str
    completed: bool
    saturated_fraction: float = 0.0
    aborted_at_s: Optional[float] = None

    @property
    def was_clipped(self) -> bool:
        return self.proposed_digest != self.authorized_digest

    def to_dict(self) -> dict:
        out = asdict(self)
        out["was_clipped"] = self.was_clipped
        return out


def digest(obj) -> str:
    """Canonical digest of a waveform or a config. Used for staleness."""
    if isinstance(obj, np.ndarray):
        payload = np.round(obj.astype(float), 9).tobytes()
    else:
        payload = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:32]


@dataclass(frozen=True)
class Certificate:
    state: str
    reasons: Tuple[str, ...]
    moments: dict
    terms: dict
    resolution: dict
    coverage: dict
    execution: dict
    budget: dict
    evidence_level: str = "SIMULATOR_SUPPORTED"
    schema: str = SCHEMA
    semantics_version: str = SEMANTICS_VERSION
    not_established: str = (
        "This is a statement about one window of telemetry under a declared "
        "error budget in a named model. It is not a certification, not an "
        "airworthiness finding, not a safety guarantee, and not evidence "
        "about any real battery chemistry.")

    @property
    def actionable(self) -> bool:
        return self.state in ACTIONABLE

    def to_dict(self) -> dict:
        return asdict(self)


def effective_frequency(t, i_meas) -> float:
    """Power-weighted mean frequency of the realized current, in hertz.

    Computed from the trace, not declared. It is what lets the polarization
    bound reward a probe that puts its energy where the nuisance dynamics
    cannot follow.
    """
    x = np.asarray(i_meas, dtype=float)
    t = np.asarray(t, dtype=float)
    if x.size < 8:
        return 0.0
    dt = (t[-1] - t[0]) / max(x.size - 1, 1)
    if dt <= 0:
        return 0.0
    xc = x - x.mean()
    spec = np.abs(np.fft.rfft(xc)) ** 2
    freqs = np.fft.rfftfreq(x.size, d=dt)
    total = float(spec.sum())
    return 0.0 if total <= 0 else float(np.dot(spec, freqs) / total)


def _dynamic_bias(t, i_meas, budget: ErrorBudget):
    """Bound on the apparent resistance contributed by RC polarization.

    THE TERM THAT MADE THE FIRST VERSION OF THIS FILE REFUSE EVERYTHING.
    It originally used the worst case `R1_max` outright, which is correct
    only if the polarization branch can respond instantly. With `R1_max`
    equal to the target change, no excitation of any kind could clear the
    margin, and the campaign's own negative control -- an 8 A cosine that
    must certify -- refused. That is the control doing its job: the
    certificate was not broken, the error model was too crude to let
    waveform design matter at all.

    A first-order polarization branch has impedance magnitude

        |Z1(f)| = R1 / sqrt(1 + (2 pi f tau1)^2)

    so a probe whose energy sits well above `1/(2 pi tau1)` sees almost none
    of it. The bound therefore uses the realized current's power-weighted
    mean frequency against a DECLARED LOWER BOUND on `tau1`. The lower bound
    is the conservative direction: a faster polarization branch follows the
    probe more closely and contributes more.

    Returns `UNBOUNDED` unless BOTH `r1_max` and `tau1_min_s` are declared.
    A missing declaration is never a zero.
    """
    if budget.r1_max is None or budget.tau1_min_s is None:
        return UNBOUNDED
    f_eff = effective_frequency(t, i_meas)
    denom = math.sqrt(1.0 + (2.0 * math.pi * f_eff * budget.tau1_min_s) ** 2)
    return abs(budget.r1_max) / denom


def _sampling_bias(t, i_meas, budget: ErrorBudget, m: Moments) -> float:
    """Bias from current-channel delay and quantisation. COMPUTED, not declared.

    A transport delay makes the regressor `I(t - tau)` while the voltage is
    `V(t)`, so the slope is attenuated by the normalised autocorrelation of
    the current at that lag. That autocorrelation is measurable from the
    trace itself, which is better than a declared worst case, so it is
    measured here and the declared delay bound only sets the lag.

    Quantisation adds `q^2/12` of variance to the regressor, which acts
    exactly like extra sensor noise and is folded in as additional
    attenuation.
    """
    bias = 0.0
    if budget.delay_max_s > 0 and m.n > 4:
        dt = m.duration_s / max(m.n - 1, 1)
        lag = int(round(budget.delay_max_s / dt))
        if 0 < lag < m.n - 2:
            x = np.asarray(i_meas, dtype=float)
            xc = x - x.mean()
            denom = float(np.dot(xc, xc))
            if denom > 0:
                rho = float(np.dot(xc[lag:], xc[:-lag]) / denom)
                bias += abs(budget.r_reference) * abs(1.0 - rho)
    if budget.quantum_i > 0 and m.var_i_measured > 0:
        extra = (budget.quantum_i ** 2) / 12.0
        lam_q = m.var_i_measured / (m.var_i_measured + extra)
        bias += abs(budget.r_reference) * abs(1.0 - lam_q)
    return bias


def certify(t, i_measured, v_measured, budget: ErrorBudget,
            execution: Optional[Execution] = None,
            safety_ok: bool = True,
            observation_consistent: bool = True) -> Certificate:
    """Decide, from realized telemetry, whether the target change is resolvable.

    NOTE THE SIGNATURE. `i_measured` and `v_measured` are the only channels.
    There is no `i_true`, no `command`, no `plant`, and no `override`.
    """
    reasons = []
    t = np.asarray(t, dtype=float)
    i_meas = np.asarray(i_measured, dtype=float)
    v_meas = np.asarray(v_measured, dtype=float)

    empty = {"moments": {}, "terms": {}, "resolution": {}, "coverage": {},
             "execution": execution.to_dict() if execution else {},
             "budget": budget.to_dict()}

    # --- 1. instrument validity -------------------------------------------
    if not (t.shape == i_meas.shape == v_meas.shape):
        return Certificate(state=INVALID_INSTRUMENT,
                           reasons=("CHANNEL_SHAPES_DISAGREE",), **empty)
    if t.size < 3 or not np.all(np.isfinite(t)):
        return Certificate(state=INVALID_INSTRUMENT,
                           reasons=("TIMEBASE_UNUSABLE",), **empty)
    if not (np.all(np.isfinite(i_meas)) and np.all(np.isfinite(v_meas))):
        return Certificate(state=INVALID_INSTRUMENT,
                           reasons=("NON_FINITE_TELEMETRY",), **empty)
    if np.any(np.diff(t) <= 0):
        return Certificate(state=INVALID_INSTRUMENT,
                           reasons=("TIMEBASE_NOT_STRICTLY_INCREASING",),
                           **empty)

    m = moments(t, i_meas)
    cov = {"samples": m.n, "min_samples": budget.min_samples,
           "duration_s": m.duration_s}

    # --- 2. execution integrity, BEFORE any information claim -------------
    if execution is not None:
        if execution.aborted_at_s is not None or not execution.completed:
            return Certificate(
                state=ABORTED_INCOMPLETE,
                reasons=("ACTION_DID_NOT_COMPLETE",),
                moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
                execution=execution.to_dict(), budget=budget.to_dict())
        if execution.was_clipped:
            return Certificate(
                state=CLIPPED_INVALID,
                reasons=("AUTHORIZED_WAVEFORM_DIFFERS_FROM_PROPOSAL",
                         "RECERTIFY_FROM_THE_CLIPPED_ACTION"),
                moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
                execution=execution.to_dict(), budget=budget.to_dict())

    if not safety_ok:
        return Certificate(
            state=NO_SAFE_INFORMATIVE_ACTION,
            reasons=("SAFETY_EVALUATOR_REFUSED",), moments=m.to_dict(),
            terms={}, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    if m.n < budget.min_samples:
        return Certificate(
            state=ABORTED_INCOMPLETE, reasons=("TELEMETRY_COVERAGE_SHORT",),
            moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    if not observation_consistent:
        return Certificate(
            state=UNKNOWN_OR_MODEL_MISMATCH,
            reasons=("OBSERVATION_OUTSIDE_EVERY_MODELLED_HYPOTHESIS",),
            moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    # --- 3. excitation, on the DECONVOLVED sum ----------------------------
    true_s_ii = deconvolved_s_ii(m, budget.sigma_i, budget.k_sigma)
    budgetted = budget.c_fraction * budget.target_delta_r
    # The variance condition inverted: SE = sigma_eff / sqrt(S_II) must be
    # under the margin, so S_II must clear (k sigma_eff / margin)^2.
    sigma_eff = math.sqrt(budget.sigma_v ** 2
                          + (budget.r_reference * budget.sigma_i) ** 2)
    s_ii_min = (budget.k_sigma * sigma_eff / budgetted) ** 2
    cov["s_ii_min_required"] = s_ii_min
    cov["s_ii_measured"] = m.s_ii
    cov["s_ii_deconvolved"] = true_s_ii

    if true_s_ii is None:
        return Certificate(
            state=INSUFFICIENT_EXCITATION,
            reasons=("REALIZED_CURRENT_INDISTINGUISHABLE_FROM_SENSOR_NOISE",),
            moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())
    if true_s_ii < s_ii_min:
        return Certificate(
            state=INSUFFICIENT_EXCITATION,
            reasons=("REALIZED_S_II_BELOW_REQUIREMENT",),
            moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    # --- 4. drift coupling, on the realized lever arm ----------------------
    lever = m.lever_arm_s
    b_drift = budget.d_max * abs(lever)
    gamma_max = (budgetted / budget.d_max) if budget.d_max > 0 else float("inf")
    cov["lever_arm_s"] = lever
    cov["lever_arm_max"] = gamma_max
    if abs(lever) > gamma_max:
        return Certificate(
            state=DRIFT_COUPLED,
            reasons=("REALIZED_CURRENT_CORRELATES_WITH_TIME",),
            moments=m.to_dict(),
            terms={"B_drift": b_drift, "lever_arm_s": lever},
            resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    # --- 5. does the model fit at all? -------------------------------------
    r_hat = estimate_resistance(i_meas, v_meas)
    design = np.column_stack([np.ones(i_meas.size), -i_meas])
    coeffs = np.linalg.lstsq(design, v_meas, rcond=None)[0]
    resid = v_meas - design @ coeffs
    resid_rms = float(np.sqrt(np.mean(resid ** 2)))
    predicted_rms = math.sqrt(budget.sigma_v ** 2
                              + (budget.r_reference * budget.sigma_i) ** 2)
    cov["residual_rms"] = resid_rms
    cov["residual_rms_predicted"] = predicted_rms
    cov["residual_ratio"] = (resid_rms / predicted_rms
                             if predicted_rms > 0 else float("inf"))
    if resid_rms > budget.residual_tolerance * predicted_rms:
        return Certificate(
            state=UNKNOWN_OR_MODEL_MISMATCH,
            reasons=("FIT_RESIDUAL_EXCEEDS_DECLARED_CHANNEL_NOISE",
                     "THE_DATA_IS_NOT_DESCRIBED_BY_V_EQUALS_E_MINUS_I_R"),
            moments=m.to_dict(), terms={}, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    # --- 6. the error budget ----------------------------------------------
    lam = attenuation(m, budget.sigma_i)
    b_eiv = abs(1.0 - lam) * abs(budget.r_reference)
    b_dynamic = _dynamic_bias(t, i_meas, budget)
    b_mismatch = UNBOUNDED
    if budget.scale_error_max is not None:
        s = abs(budget.scale_error_max)
        b_mismatch = abs(budget.r_reference) * s / max(1.0 - s, 1e-9)
    b_sampling = _sampling_bias(t, i_meas, budget, m)

    terms = {"B_drift": b_drift, "B_EIV": b_eiv, "B_dynamic": b_dynamic,
             "B_mismatch": b_mismatch, "B_sampling": b_sampling,
             "attenuation": lam, "lever_arm_s": lever,
             "effective_frequency_hz": effective_frequency(t, i_meas),
             "combination": "union bound, absolute values summed; the terms "
                            "are not independent and no cancellation is "
                            "assumed"}
    unbounded = sorted(k for k in ("B_dynamic", "B_mismatch")
                       if terms[k] == UNBOUNDED)
    if unbounded:
        return Certificate(
            state=MODEL_MISMATCH_LIMITED,
            reasons=tuple([f"UNBOUNDED_TERM:{k}" for k in unbounded]),
            moments=m.to_dict(), terms=terms, resolution={}, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    b_total = b_drift + b_eiv + b_dynamic + b_mismatch + b_sampling
    se = sigma_eff / math.sqrt(true_s_ii)
    margin = budget.c_fraction * budget.target_delta_r
    achieved = b_total + budget.k_sigma * se
    resolution = {"B_total": b_total, "SE": se,
                  "k_sigma_SE": budget.k_sigma * se,
                  "achieved_error": achieved, "allowed_error": margin,
                  "margin": margin - achieved,
                  "rule": ("|B_total| + k*SE < c*|target_delta_r|; set "
                           "separation, with SE as one term inside a "
                           "declared margin and never as a p-value")}
    terms["B_total"] = b_total

    if achieved >= margin:
        dominant = max(("B_drift", "B_EIV", "B_dynamic", "B_mismatch",
                        "B_sampling"), key=lambda k: terms[k])
        reasons.append(f"ERROR_EXCEEDS_MARGIN_DOMINATED_BY:{dominant}")
        state = (MODEL_MISMATCH_LIMITED
                 if dominant in ("B_dynamic", "B_mismatch")
                 else MEASUREMENT_LIMITED)
        return Certificate(
            state=state, reasons=tuple(reasons), moments=m.to_dict(),
            terms=terms, resolution=resolution, coverage=cov,
            execution=execution.to_dict() if execution else {},
            budget=budget.to_dict())

    return Certificate(
        state=CERTIFIED, reasons=("ALL_DECLARED_CONDITIONS_MET_IN_MODEL",),
        moments=m.to_dict(), terms=terms, resolution=resolution,
        coverage=cov, execution=execution.to_dict() if execution else {},
        budget=budget.to_dict())


def estimate_resistance(i_measured, v_measured) -> float:
    """Ordinary least squares on [1, -I]. The estimator the budget bounds."""
    i = np.asarray(i_measured, dtype=float)
    v = np.asarray(v_measured, dtype=float)
    if i.size < 3:
        return float("nan")
    return float(np.linalg.lstsq(np.column_stack([np.ones(i.size), -i]), v,
                                 rcond=None)[0][1])
