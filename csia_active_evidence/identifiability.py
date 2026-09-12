"""When can a bounded parameter be identified, and what would it take?

THE ANCHOR PROBLEM
------------------
MX-036 measured that pack internal resistance is undetectable on a steady
hover at every magnitude up to 0.25 ohm, and attributed it to the eligibility
gate correctly refusing to run a regression on a constant load. That is true
and it is not the whole story. This module derives the whole story, in closed
form, and the derivation is independent of the component simulator.

THE MODEL
---------
Over a window short enough that open-circuit voltage and internal resistance
are approximately constant,

    V_k = E - I_k R + eps_k

which as a regression on [1, -I] has two parameters. Three separate things
can stop R from being recovered, and they fail in DIFFERENT ways:

  1. VARIANCE.  Scatter around the truth. More samples help. This is the
     only one of the three that averaging fixes, and it is the only one a
     naive analysis notices.

  2. BIAS FROM ERRORS IN VARIABLES.  The regressor is a MEASURED current
     carrying its own noise sigma_I. Ordinary least squares then attenuates
     the slope by

        lambda = var(I_true) / (var(I_true) + sigma_I^2)

     At a steady operating point var(I_true) is near zero, so lambda -> 0 and
     R_hat -> 0 REGARDLESS OF THE TRUE R. THIS IS A BIAS, NOT A VARIANCE, AND
     MORE DATA DOES NOT FIX IT. It is the real reason a steady hover cannot
     identify pack impedance, and it is sharper than "the regressor is rank
     deficient": the regressor is not rank deficient at all once sensor noise
     is present -- it is rank two and confidently wrong.

  3. BIAS FROM DRIFT ALIASING.  Open-circuit voltage falls as charge is
     drawn. With E(t) = E0 - d*t the slope acquires

        d * cov(t, I) / var(I)

     so a probe whose current is CORRELATED WITH TIME aliases the drift
     straight into R_hat. A ramp is the worst possible shape and it gets
     worse the longer it runs; a zero-time-correlation shape does not, and
     its variance falls as 1/sqrt(N).

MEAN
----
    E[R_hat] = lambda * (R + d * cov(t, I) / var(I))

Verified against Monte Carlo on a generator written inside
`tests/test_identifiability.py`, not against the component simulator.
Worst absolute error over 18 shape/window/amplitude combinations at 4000
trials each: 2.1e-05 ohm.

SCATTER, AND A FORMULA THIS MODULE USED TO GET WRONG
-----------------------------------------------------
The textbook expression for the scatter of a least-squares slope is

    sd(R_hat) = sigma_V / sqrt(sum (I_k - Ibar)^2)                  [NAIVE]

and an earlier revision of this file asserted it, with a docstring claiming
Monte Carlo agreement to 1.5%. WRITING THE MONTE CARLO FALSIFIED IT. Over
108 cases in three noise regimes the naive expression was optimistic by up
to 85%: it reports a precision the estimator does not have, which is the one
direction of error an acquisition requirement must never make.

It is wrong for two reasons, both consequences of the regressor being
measured rather than known:

  * the fit residual is not sigma_V. Substituting I_true = I_meas - u makes
    the effective residual `eps_V - r * u`, so the CURRENT noise enters the
    numerator scaled by the slope being estimated. At a large effective
    slope -- which drift aliasing produces even when R is small -- this term
    dominates.
  * the denominator sum(I - Ibar)^2 is itself random, and R_hat is a ratio
    of two random quantities rather than a linear function of the data.

`estimate_sd` therefore uses the delta-method expansion of that ratio, which
carries the effective slope, the drift component orthogonal to the current,
and the variance of the denominator. Worst deviation from Monte Carlo over
the same 108 cases: 2.2%. Both numbers are re-measured by
`tests/test_identifiability.py::test_the_naive_scatter_formula_is_optimistic`,
which keeps the falsified expression alive as a comparison so the correction
cannot quietly regress.

WHY THIS MATTERS MORE THAN A SEARCH
------------------------------------
Because the requirement INVERTS. Given a resistance change worth resolving,
a confidence, and the platform's own measured noise, `probe_requirement`
returns the excitation that is necessary -- in closed form, with no search
and no simulator in the loop. A selector can then pick the cheapest probe
meeting it, and the prediction is falsifiable: if a probe meeting the
requirement fails to resolve the change in an independent simulator, the
derivation is wrong.

WHAT THIS IS NOT
----------------
It is a LOCAL, LINEAR, TWO-PARAMETER analysis of one relation. It assumes
E and R constant over the window apart from the modelled linear drift, no
RC dynamics, no temperature coupling, no cell imbalance, and additive
Gaussian noise on both channels. The delta-method scatter is a first-order
expansion and degrades as sigma_I approaches std(I) -- exactly the regime
where the attenuation condition already refuses the probe, which is why the
two are reported together and never collapsed into one number.
`research/active_evidence/SIMULATOR_VALIDITY_ENVELOPE.md` records what that
excludes. None of it is a safety argument.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field

import numpy as np


@dataclass(frozen=True)
class NoiseModel:
    """What the platform's own channels do when healthy.

    THESE ARE COMMISSIONING MEASUREMENTS, NOT CONSTANTS. Every number here
    is a property of one vehicle's wiring and sensing, and using another
    vehicle's values is using another vehicle's noise floor.
    """

    sigma_v: float          # volt, one sigma on the terminal-voltage channel
    sigma_i: float          # amp, one sigma on the current channel
    ocv_drift_v_per_s: float = 0.0   # bounded magnitude, not a point estimate

    def __post_init__(self):
        if self.sigma_v <= 0 or self.sigma_i < 0:
            raise ValueError("sigma_v must be positive and sigma_i "
                             "non-negative; these are measured noise "
                             "levels and a zero voltage sigma would make "
                             "every estimate infinitely precise")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExcitationStats:
    """The four statistics of a current profile that decide identifiability.

    Computed FROM a profile, never asserted about one. `from_profile` and
    `from_measured` are the only constructors used in anger, so a probe
    cannot claim a correlation it does not have.

    `var_i` IS THE VARIANCE OF THE TRUE CURRENT, not of the measured one.
    The distinction is the whole of failure mode 2: passing a measured
    current here inflates var_i by sigma_I^2 and reports an attenuation
    factor closer to 1 than the truth, which is the optimistic direction.
    `from_profile` is for a DESIGNED probe, whose true profile is known
    because it is the thing being commanded; `from_measured` is for observed
    data and subtracts the known noise power, refusing when the remainder is
    not positive.
    """

    n: int
    var_i: float               # amp^2, variance of the TRUE current
    cov_ti_over_var_i: float   # second, the drift-aliasing lever arm
    var_t: float               # second^2, needed by the scatter expansion
    source: str = "DESIGNED_PROFILE"

    @staticmethod
    def from_profile(t, current) -> "ExcitationStats":
        """Statistics of a commanded profile, whose true values are known."""
        t, i = _pair(t, current)
        var_i = float(np.var(i))
        var_t = float(np.var(t))
        if var_i <= 0.0:
            # A constant profile has no lever arm at all. Returning zero
            # rather than raising lets a selector SCORE the passive option
            # against the others instead of having to special-case it.
            return ExcitationStats(n=int(i.size), var_i=0.0,
                                   cov_ti_over_var_i=0.0, var_t=var_t)
        cov = float(np.cov(t, i, bias=True)[0, 1])
        return ExcitationStats(n=int(i.size), var_i=var_i,
                               cov_ti_over_var_i=cov / var_i, var_t=var_t)

    @staticmethod
    def from_measured(t, measured_current, noise: "NoiseModel",
                      k_sigma: float = 3.0) -> "ExcitationStats":
        """Statistics of OBSERVED current, with the noise power removed.

        var(I_meas) = var(I_true) + sigma_I^2, so the naive variance of a
        measured channel always overstates the excitation.

        SUBTRACTING THE NOISE POWER IS NOT ENOUGH ON ITS OWN. A sample
        variance is itself an estimate, with sampling standard deviation
        sigma_I^2 * sqrt(2/N) under pure noise, so a window containing NO
        excitation leaves a positive remainder roughly half the time --
        measured at 0.452, 0.473 and 0.479 for N of 100, 500 and 1000. An
        earlier revision refused only on a non-positive remainder and would
        therefore have accepted a steady hover as excited on about half of
        all windows, which is the optimistic direction and precisely the
        error this module exists to prevent.

        The excess must therefore clear `k_sigma` times the sampling
        standard deviation of the variance estimate. That threshold is the
        arithmetic of a chi-squared sampling distribution, not a tuned
        number, and it is reported on the returned object.
        """
        t, i = _pair(t, measured_current)
        var_meas = float(np.var(i))
        si2 = noise.sigma_i ** 2
        var_true = var_meas - si2
        var_t = float(np.var(t))
        floor = k_sigma * si2 * math.sqrt(2.0 / i.size)
        if var_true <= floor:
            raise ValueError(
                f"measured current variance {var_meas:.6g} A^2 exceeds the "
                f"channel noise power {si2:.6g} A^2 by {var_true:.6g}, "
                f"which does not clear the {k_sigma:g}-sigma sampling error "
                f"of the variance estimate itself ({floor:.6g}); this "
                f"window contains no excitation distinguishable from sensor "
                f"noise and no attenuation factor can be estimated from it")
        cov = float(np.cov(t, i, bias=True)[0, 1])
        # cov(t, I_meas) is an unbiased estimate of cov(t, I_true) because
        # the current noise is independent of time; only the DENOMINATOR
        # needed correcting.
        return ExcitationStats(n=int(i.size), var_i=var_true,
                               cov_ti_over_var_i=cov / var_true,
                               var_t=var_t, source="MEASURED_DECONVOLVED")

    @property
    def std_i(self) -> float:
        return math.sqrt(self.var_i)

    def to_dict(self) -> dict:
        return asdict(self)


def _pair(t, x):
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    if t.shape != x.shape or t.size < 3:
        raise ValueError("t and current must be the same shape with at "
                         "least 3 samples")
    return t, x


def attenuation(stats: ExcitationStats, noise: NoiseModel) -> float:
    """lambda = var(I_true) / (var(I_true) + sigma_I^2), in [0, 1].

    The factor by which ordinary least squares shrinks the slope because the
    regressor is measured rather than known. One means no shrinkage; zero
    means the estimate carries no information about R at all.
    """
    denom = stats.var_i + noise.sigma_i ** 2
    return 0.0 if denom <= 0 else stats.var_i / denom


def expected_estimate(r_true: float, stats: ExcitationStats,
                      noise: NoiseModel) -> float:
    """E[R_hat] = lambda * (R + d * cov(t,I)/var(I)).

    Measured worst error 2.1e-05 ohm; see the module docstring.
    """
    lam = attenuation(stats, noise)
    return lam * (r_true + noise.ocv_drift_v_per_s * stats.cov_ti_over_var_i)


def naive_estimate_sd(stats: ExcitationStats, noise: NoiseModel) -> float:
    """sigma_V / sqrt(sum (I - Ibar)^2). THE TEXTBOOK FORM, AND FALSIFIED.

    Kept deliberately, and never called by anything that makes a decision.
    It exists so `tests/test_identifiability.py` can re-measure how
    optimistic it is on every run, and so a reader who reaches for it can
    find out in one grep that this module already tried it. Measured
    optimism: up to 85% over 108 Monte Carlo cases.
    """
    ss = stats.var_i * stats.n
    return float("inf") if ss <= 0 else noise.sigma_v / math.sqrt(ss)


def estimate_sd(stats: ExcitationStats, noise: NoiseModel,
                r_reference: float) -> float:
    """Scatter of R_hat, by the delta method on a ratio of random sums.

    `r_reference` is the resistance the platform is expected to sit near.
    It enters because the current-channel noise reaches the residual scaled
    by the slope being estimated, so a larger resistance is intrinsically
    harder to pin down at the same excitation -- an effect the naive
    expression misses entirely.

    Measured worst deviation from Monte Carlo: 2.2% over 108 cases spanning
    R in {0.04, 0.25} ohm, drift in {0, 0.01} V/s and four profile shapes.
    """
    a = stats.n * stats.var_i               # sum of squares of TRUE current
    if a <= 0:
        return float("inf")
    si2 = noise.sigma_i ** 2
    sv2 = noise.sigma_v ** 2
    b = stats.n * si2
    d = noise.ocv_drift_v_per_s

    lever = stats.cov_ti_over_var_i
    r_det = r_reference + d * lever          # slope the fit actually recovers
    # The part of the open-circuit drift that is ORTHOGONAL to the current:
    # for a ramp it is zero, for a zero-time-correlation shape it is the
    # whole drift, and it reaches the residual through the current noise.
    var_w = max(d * d * stats.var_t - (d * lever) ** 2 * stats.var_i, 0.0)

    lam = a / (a + b)
    r = lam * r_det
    var_num = (r_det ** 2) * si2 * a + si2 * stats.n * var_w \
        + sv2 * a + stats.n * si2 * sv2
    var_den = 4.0 * si2 * a + 2.0 * stats.n * si2 ** 2
    cov_nd = 2.0 * r_det * si2 * a
    var = (var_num - 2.0 * r * cov_nd + (r ** 2) * var_den) / ((a + b) ** 2)
    return math.sqrt(max(var, 0.0))


def resolvable_delta(stats: ExcitationStats, noise: NoiseModel,
                     r_reference: float, k_sigma: float = 3.0) -> float:
    """The smallest resistance CHANGE this excitation can resolve.

    Variance only. A change smaller than this is inside the estimator's own
    scatter; a change larger than it may still be unusable if the bias terms
    are large, which is why `separability` reports all three together and
    this function is not the answer on its own.
    """
    return k_sigma * estimate_sd(stats, noise, r_reference)


@dataclass(frozen=True)
class Separability:
    """Everything needed to judge one excitation, with nothing collapsed.

    Deliberately NOT a single score. A probe can be excellent on variance and
    useless on bias, and one number would hide exactly that -- the same
    reason the configuration sweep reports separation and headroom
    separately and never multiplies them together.
    """

    attenuation: float
    bias_from_attenuation: float    # ohm, at the reference resistance
    bias_from_drift: float          # ohm
    sd: float                       # ohm
    naive_sd: float                 # ohm, the falsified expression
    resolvable_delta: float         # ohm, k-sigma
    total_bias: float               # ohm, the two biases combined
    dominated_by: str               # which term is largest

    def to_dict(self) -> dict:
        return asdict(self)


def separability(stats: ExcitationStats, noise: NoiseModel,
                 r_reference: float, k_sigma: float = 3.0) -> Separability:
    """Decompose the error in R_hat into its three named parts."""
    lam = attenuation(stats, noise)
    b_att = (lam - 1.0) * r_reference
    b_drift = lam * noise.ocv_drift_v_per_s * stats.cov_ti_over_var_i
    sd = estimate_sd(stats, noise, r_reference)
    terms = {"attenuation": abs(b_att), "drift": abs(b_drift),
             "noise": abs(k_sigma * sd)}
    return Separability(
        attenuation=lam,
        bias_from_attenuation=b_att,
        bias_from_drift=b_drift,
        sd=sd,
        naive_sd=naive_estimate_sd(stats, noise),
        resolvable_delta=k_sigma * sd,
        total_bias=b_att + b_drift,
        dominated_by=max(terms, key=terms.get),
    )


@dataclass(frozen=True)
class ProbeRequirement:
    """What an excitation must achieve. Derived, not searched.

    Every field is a NECESSARY condition. A probe satisfying all three is
    predicted to resolve `delta_r` at `k_sigma`; a probe failing any one is
    predicted not to, and which one it fails says what to change.

    The three scalars are CLOSED-FORM GUIDES for a human reading the
    requirement. `met_by` does not use them for the variance condition: it
    evaluates the full delta-method scatter, because the scalar form assumes
    the effective slope equals the reference resistance and drift aliasing
    can make it much larger. Where the two disagree the exact one decides.
    """

    delta_r: float
    k_sigma: float
    r_reference: float
    noise: NoiseModel
    min_std_i: float            # amp, from the attenuation budget
    min_std_i_sqrt_n: float     # amp * sqrt(sample), from the variance budget
    max_abs_cov_ti_over_var_i: float   # second, from the drift budget
    bias_budget: float
    basis: str

    def met_by(self, stats: ExcitationStats) -> dict:
        """Which conditions this excitation meets. Never a single boolean."""
        lam = attenuation(stats, self.noise)
        bias_att = abs(lam - 1.0) * abs(self.r_reference)
        bias_drift = abs(lam * self.noise.ocv_drift_v_per_s
                         * stats.cov_ti_over_var_i)
        sd = estimate_sd(stats, self.noise, self.r_reference)
        checks = {
            "attenuation": bias_att <= self.bias_budget,
            "variance": self.k_sigma * sd <= self.delta_r,
            "drift": bias_drift <= self.bias_budget,
        }
        return {"met": all(checks.values()), "conditions": checks,
                "failed": sorted(k for k, v in checks.items() if not v),
                "margins": {"bias_from_attenuation": bias_att,
                            "bias_from_drift": bias_drift,
                            "k_sigma_sd": self.k_sigma * sd,
                            "bias_budget": self.bias_budget,
                            "delta_r": self.delta_r}}

    def to_dict(self) -> dict:
        out = asdict(self)
        out["noise"] = self.noise.to_dict()
        return out


def probe_requirement(delta_r: float, noise: NoiseModel, r_reference: float,
                      k_sigma: float = 3.0,
                      bias_fraction: float = 0.25) -> ProbeRequirement:
    """Invert the error model: what must an excitation do to resolve delta_r?

    THE POINT OF THE WHOLE MODULE. No search, no simulator, no fitting --
    three inequalities obtained by solving the closed-form error expressions
    for the excitation statistics.

    `bias_fraction` is the share of `delta_r` each bias term is allowed to
    consume. It is a declared engineering budget, not a tuned value, and it
    is reported in the requirement so a reader can see what was allowed.

    Attenuation:  |lambda - 1| * r_reference <= bias_fraction * delta_r
                  => var(I) >= sigma_I^2 * (r_ref/(bias*delta_r) - 1)
    Variance:     k * sigma_eff / (sqrt(N) std(I)) <= delta_r
                  => std(I) sqrt(N) >= k sigma_eff / delta_r
                  with sigma_eff = sqrt(sigma_V^2 + r_ref^2 sigma_I^2), the
                  effective residual once the current noise is folded in.
    Drift:        |lambda * d * cov(t,I)/var(I)| <= bias_fraction * delta_r
                  => |cov(t,I)/var(I)| <= bias * delta_r / d      (lambda<=1)
    """
    if delta_r <= 0 or k_sigma <= 0 or not 0 < bias_fraction < 1:
        raise ValueError("delta_r and k_sigma must be positive and "
                         "bias_fraction strictly between 0 and 1")
    budget = bias_fraction * delta_r

    ratio = abs(r_reference) / budget
    min_var = (noise.sigma_i ** 2) * (ratio - 1.0) if ratio > 1.0 else 0.0
    min_std_i = math.sqrt(max(min_var, 0.0))

    sigma_eff = math.sqrt(noise.sigma_v ** 2
                          + (r_reference * noise.sigma_i) ** 2)
    min_std_sqrt_n = k_sigma * sigma_eff / delta_r

    d = abs(noise.ocv_drift_v_per_s)
    max_cov = float("inf") if d == 0.0 else budget / d

    return ProbeRequirement(
        delta_r=delta_r, k_sigma=k_sigma, r_reference=r_reference,
        noise=noise,
        min_std_i=min_std_i,
        min_std_i_sqrt_n=min_std_sqrt_n,
        max_abs_cov_ti_over_var_i=max_cov,
        bias_budget=budget,
        basis=("inverted from E[R_hat] = lambda (R + d cov(t,I)/var(I)) and "
               "the delta-method scatter of R_hat; both verified against "
               "Monte Carlo in tests/test_identifiability.py"),
    )


def rank_of_design(current) -> int:
    """Numerical rank of the regressor [1, -I]. The textbook condition.

    KEPT, AND DELIBERATELY NOT THE HEADLINE. On real data with any sensor
    noise this returns 2 almost always, including on a steady hover where
    the estimate is worthless -- which is precisely why rank is the wrong
    diagnostic and the attenuation factor is the right one.
    """
    i = np.asarray(current, dtype=float)
    return int(np.linalg.matrix_rank(np.column_stack([np.ones(i.size), -i])))
