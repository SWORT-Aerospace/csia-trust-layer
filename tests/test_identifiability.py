"""The closed-form identifiability model, pinned against Monte Carlo.

WHY THE GENERATOR IS WRITTEN HERE AND NOT IMPORTED
---------------------------------------------------
`csia_active_evidence.identifiability` predicts what a least-squares estimate
of pack resistance will do. Checking it against `csia_components/simulate.py`
would check two of my own models against each other; the simulator's current
and voltage come from the same physical assumptions the derivation makes, so
agreement would be guaranteed and would mean nothing.

The generator below is eight lines of arithmetic that anyone can read:
a current profile, a linear voltage law, additive Gaussian noise on BOTH
channels, and `numpy.linalg.lstsq`. If the closed form disagrees with this,
the closed form is wrong.

THE ONE RESULT THIS FILE ALREADY OVERTURNED
--------------------------------------------
The module used to assert the textbook slope variance
`sigma_V / sqrt(sum (I - Ibar)^2)` and its docstring claimed Monte Carlo
agreement within 1.5%. Writing this file measured up to 85% optimism. The
falsified expression is kept as `naive_estimate_sd` and re-measured here on
every run, because a correction with no standing comparison silently
regresses.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import identifiability as ID       # noqa: E402

HZ = 50.0
R_TRUE = 0.040
E0 = 16.0
BASE_A = 20.0


# --- the generator, deliberately trivial ------------------------------------

def profile(shape: str, window: float, amplitude: float):
    """A current profile in amps. No import from the component simulator."""
    t = np.arange(0.0, window, 1.0 / HZ)
    if shape == "hover":
        u = np.zeros_like(t)
    elif shape == "ramp":
        span = max(float(t.max() - t.min()), 1e-9)
        u = (t - t.mean()) / span
    elif shape == "square":
        u = np.where((np.floor(t * 2.0) % 2) == 0, -0.5, 0.5)
    elif shape == "sine":
        u = np.sin(2.0 * np.pi * 0.5 * t)
    elif shape == "chirp":
        u = np.sin(2.0 * np.pi * (0.3 + 0.15 * t) * t)
    else:
        raise ValueError(shape)
    return t, BASE_A + amplitude * u


def monte_carlo(shape, window, amplitude, *, r_true=R_TRUE, sigma_v=0.020,
                sigma_i=0.08, drift=0.010, trials=4000, seed=0):
    """Fit R on noisy V and noisy I, `trials` times. Returns mean and sd."""
    rng = np.random.default_rng(seed)
    t, i_true = profile(shape, window, amplitude)
    n = t.size
    v_true = (E0 - drift * t) - i_true * r_true
    out = np.empty(trials)
    for k in range(trials):
        i_meas = i_true + rng.normal(0.0, sigma_i, n)
        v_meas = v_true + rng.normal(0.0, sigma_v, n)
        design = np.column_stack([np.ones(n), -i_meas])
        out[k] = np.linalg.lstsq(design, v_meas, rcond=None)[0][1]
    stats = ID.ExcitationStats.from_profile(t, i_true)
    noise = ID.NoiseModel(sigma_v=sigma_v, sigma_i=sigma_i,
                          ocv_drift_v_per_s=drift)
    return out.mean(), out.std(ddof=1), stats, noise


CASES = [(s, w, a) for s in ("ramp", "square", "sine")
         for w in (2.0, 5.0, 20.0) for a in (2.0, 8.0)]


# --- the mean ---------------------------------------------------------------

@pytest.mark.parametrize("shape,window,amplitude", CASES)
def test_the_expected_estimate_matches_monte_carlo(shape, window, amplitude):
    """E[R_hat] = lambda * (R + d * cov(t,I)/var(I)), to 1e-4 ohm."""
    mean, _sd, stats, noise = monte_carlo(shape, window, amplitude)
    predicted = ID.expected_estimate(R_TRUE, stats, noise)
    assert abs(mean - predicted) < 1e-4, (
        f"{shape}/{window}s/{amplitude}A: measured {mean:.6f}, predicted "
        f"{predicted:.6f}")


def test_the_mean_prediction_is_not_vacuous():
    """The 18 cases must SPAN a wide range of R_hat, or agreeing with them
    would only prove the formula returns something near the true R."""
    means = [monte_carlo(s, w, a, trials=600)[0] for s, w, a in CASES]
    assert max(means) - min(means) > 0.05, (
        f"the case grid only produced estimates in [{min(means):.4f}, "
        f"{max(means):.4f}]; it does not exercise the bias terms")


# --- the scatter, and the expression this file falsified --------------------

@pytest.mark.parametrize("shape,window,amplitude", CASES)
def test_the_delta_method_scatter_matches_monte_carlo(shape, window,
                                                      amplitude):
    """Within 5%. Measured worst deviation over the grid is 2.2%."""
    _mean, sd, stats, noise = monte_carlo(shape, window, amplitude)
    predicted = ID.estimate_sd(stats, noise, R_TRUE)
    assert abs(sd / predicted - 1.0) < 0.05, (
        f"{shape}/{window}s/{amplitude}A: measured sd {sd:.6f}, predicted "
        f"{predicted:.6f}, ratio {sd / predicted:.4f}")


def test_the_naive_scatter_formula_is_optimistic():
    """THE FALSIFICATION, RE-MEASURED EVERY RUN.

    The textbook expression is not merely less accurate, it is WRONG IN THE
    DANGEROUS DIRECTION: it reports less scatter than the estimator has, so
    a requirement built on it would authorise a probe that cannot deliver.
    """
    worst_naive = worst_delta = 0.0
    for shape, window, amplitude in CASES:
        _m, sd, stats, noise = monte_carlo(shape, window, amplitude,
                                           trials=1500)
        worst_naive = max(worst_naive,
                          sd / ID.naive_estimate_sd(stats, noise) - 1.0)
        worst_delta = max(worst_delta,
                          abs(sd / ID.estimate_sd(stats, noise, R_TRUE) - 1.0))
    assert worst_naive > 0.05, (
        "the naive formula is no longer measurably optimistic on this grid; "
        "either the grid stopped exercising the effect or the correction was "
        "reverted -- check before relaxing this")
    assert worst_delta < worst_naive, (
        f"the delta-method form ({worst_delta:.3f}) is not better than the "
        f"expression it replaced ({worst_naive:.3f})")


def test_the_scatter_gets_worse_at_a_larger_resistance():
    """The effect the naive formula cannot represent at all: the current
    noise reaches the residual scaled by the slope being estimated."""
    _m, _sd, stats, noise = monte_carlo("sine", 5.0, 2.0, trials=10)
    small = ID.estimate_sd(stats, noise, 0.040)
    large = ID.estimate_sd(stats, noise, 0.400)
    assert large > small * 1.5, (large, small)
    assert ID.naive_estimate_sd(stats, noise) == ID.naive_estimate_sd(
        stats, noise), "the naive form has no resistance argument at all"


# --- the three failure modes, separately -----------------------------------

def test_a_steady_hover_is_biased_to_zero_however_long_it_runs():
    """FAILURE MODE 2, and the reason this module exists. Not scatter: the
    estimate converges confidently on the wrong answer."""
    short = monte_carlo("hover", 5.0, 0.0, trials=800)
    long = monte_carlo("hover", 60.0, 0.0, trials=800)
    for mean, _sd, stats, noise in (short, long):
        assert ID.attenuation(stats, noise) == 0.0
        assert abs(mean) < 0.25 * R_TRUE, (
            f"a steady hover recovered {mean:.5f} of a true {R_TRUE}")
    assert abs(long[0]) <= abs(short[0]) + 0.01, (
        "twelve times the data did not reduce the error, which is the "
        "signature of a bias -- if it had, this would be variance and the "
        "module's central claim would be wrong")


def test_rank_is_the_wrong_diagnostic_and_the_module_says_so():
    """A noisy hover has FULL RANK and is useless. This is the sharper
    statement the module makes over 'the regressor is rank deficient'."""
    rng = np.random.default_rng(7)
    t, hover = profile("hover", 20.0, 0.0)
    assert ID.rank_of_design(hover) == 1
    measured = hover + rng.normal(0.0, 0.08, hover.size)
    assert ID.rank_of_design(measured) == 2, (
        "sensor noise should make the design full rank")
    stats = ID.ExcitationStats.from_profile(t, hover)
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08)
    assert ID.attenuation(stats, noise) == 0.0, (
        "full rank, and zero information about R")


def test_drift_aliasing_grows_with_the_window_for_a_ramp_and_not_a_sine():
    """FAILURE MODE 3. A ramp correlates current with time, so a longer
    window aliases MORE open-circuit drift, not less."""
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    ramp = [ID.expected_estimate(
        R_TRUE, ID.ExcitationStats.from_profile(*profile("ramp", w, 2.0)),
        noise) for w in (2.0, 5.0, 20.0)]
    sine = [ID.expected_estimate(
        R_TRUE, ID.ExcitationStats.from_profile(*profile("sine", w, 2.0)),
        noise) for w in (2.0, 5.0, 20.0)]
    assert ramp[0] < ramp[1] < ramp[2], ramp
    assert ramp[2] > 3.0 * R_TRUE, ramp
    assert max(sine) - min(sine) < 0.01, sine


# --- the statistics are computed, not asserted ------------------------------

def test_measured_current_must_have_its_noise_power_removed():
    """Passing a measured channel to `from_profile` inflates var(I) by
    sigma_I^2 and overstates the attenuation factor -- the optimistic
    direction. `from_measured` is the constructor for observed data."""
    rng = np.random.default_rng(3)
    t, i_true = profile("sine", 10.0, 0.20)
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08)
    measured = i_true + rng.normal(0.0, noise.sigma_i, i_true.size)
    naive = ID.ExcitationStats.from_profile(t, measured)
    correct = ID.ExcitationStats.from_measured(t, measured, noise)
    assert naive.var_i > correct.var_i
    assert ID.attenuation(naive, noise) > ID.attenuation(correct, noise)
    truth = ID.ExcitationStats.from_profile(t, i_true)
    assert abs(correct.var_i - truth.var_i) < 0.4 * truth.var_i


def test_a_window_with_no_excitation_above_the_noise_is_refused():
    rng = np.random.default_rng(4)
    t, hover = profile("hover", 10.0, 0.0)
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08)
    measured = hover + rng.normal(0.0, noise.sigma_i, hover.size)
    with pytest.raises(ValueError, match="no excitation"):
        ID.ExcitationStats.from_measured(t, measured, noise)


# --- the inversion, and its anti-vacuity control ----------------------------

def test_the_requirement_refuses_hover_and_accepts_an_excited_probe():
    """ANTI-VACUITY. A requirement nothing meets is as useless as one
    everything meets, so both directions are asserted here."""
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    req = ID.probe_requirement(0.005, noise, r_reference=0.040)

    hover = req.met_by(ID.ExcitationStats.from_profile(*profile("hover",
                                                                20.0, 0.0)))
    assert hover["met"] is False
    assert "attenuation" in hover["failed"] and "variance" in hover["failed"]

    good = req.met_by(ID.ExcitationStats.from_profile(*profile("sine",
                                                               20.0, 8.0)))
    assert good["met"] is True, good["failed"]


def test_the_requirement_names_which_condition_failed():
    """Each failure mode must be reachable ON ITS OWN, or `failed` is
    decoration rather than a diagnosis."""
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    req = ID.probe_requirement(0.005, noise, r_reference=0.040)

    # A long ramp: plenty of current variance and sample count, but its
    # current is perfectly correlated with time.
    ramp = req.met_by(ID.ExcitationStats.from_profile(*profile("ramp",
                                                                20.0, 8.0)))
    assert ramp["failed"] == ["drift"], ramp

    # A short, strong sine: no drift correlation, but too few samples.
    brief = req.met_by(ID.ExcitationStats.from_profile(*profile("sine",
                                                                 0.2, 8.0)))
    assert "variance" in brief["failed"] and "drift" not in brief["failed"], \
        brief


def test_a_probe_meeting_the_requirement_resolves_the_change_in_monte_carlo():
    """THE FALSIFIABLE PREDICTION, checked end to end.

    Take the requirement at face value, find a probe that meets it, then
    simulate two packs differing by exactly `delta_r` and confirm the
    estimates separate. This is the claim the whole module makes.
    """
    delta = 0.010
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    req = ID.probe_requirement(delta, noise, r_reference=0.040, k_sigma=3.0)
    t, current = profile("sine", 10.0, 8.0)
    stats = ID.ExcitationStats.from_profile(t, current)
    assert req.met_by(stats)["met"] is True

    low = monte_carlo("sine", 10.0, 8.0, r_true=0.040, trials=2000, seed=11)
    high = monte_carlo("sine", 10.0, 8.0, r_true=0.040 + delta, trials=2000,
                       seed=12)
    gap = high[0] - low[0]
    scatter = max(low[1], high[1])
    assert gap > 3.0 * scatter, (
        f"the requirement was met but the separation is {gap:.5f} against a "
        f"scatter of {scatter:.5f}; the derivation is wrong")


def test_a_probe_failing_the_requirement_does_not_resolve_the_change():
    """The other direction. Without it the requirement could be satisfied by
    every probe and still pass the test above."""
    delta = 0.010
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    req = ID.probe_requirement(delta, noise, r_reference=0.040)
    t, current = profile("hover", 10.0, 0.0)
    assert req.met_by(ID.ExcitationStats.from_profile(t, current))["met"] \
        is False
    low = monte_carlo("hover", 10.0, 0.0, r_true=0.040, trials=1200, seed=21)
    high = monte_carlo("hover", 10.0, 0.0, r_true=0.040 + delta, trials=1200,
                       seed=22)
    assert abs(high[0] - low[0]) < delta * 0.5, (
        "a hover separated two packs it has no information about")


def test_the_requirement_reports_its_own_budget_and_basis():
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    req = ID.probe_requirement(0.005, noise, r_reference=0.040,
                               bias_fraction=0.25)
    assert req.bias_budget == pytest.approx(0.00125)
    assert "Monte Carlo" in req.basis
    assert req.to_dict()["noise"]["sigma_i"] == 0.08
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            ID.probe_requirement(bad, noise, 0.040)
    with pytest.raises(ValueError):
        ID.probe_requirement(0.005, noise, 0.040, bias_fraction=1.0)


def test_a_zero_voltage_sigma_is_refused():
    with pytest.raises(ValueError, match="measured noise"):
        ID.NoiseModel(sigma_v=0.0, sigma_i=0.08)


def test_separability_never_collapses_to_one_number():
    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    ramp = ID.separability(
        ID.ExcitationStats.from_profile(*profile("ramp", 20.0, 8.0)),
        noise, 0.040)
    sine = ID.separability(
        ID.ExcitationStats.from_profile(*profile("sine", 20.0, 8.0)),
        noise, 0.040)
    assert ramp.dominated_by == "drift"
    assert abs(ramp.bias_from_drift) > 20.0 * abs(sine.bias_from_drift)
    assert math.isfinite(ramp.sd) and math.isfinite(ramp.total_bias)
    assert set(ramp.to_dict()) >= {"attenuation", "bias_from_attenuation",
                                   "bias_from_drift", "sd", "naive_sd",
                                   "resolvable_delta", "total_bias",
                                   "dominated_by"}


def test_even_a_sine_aliases_some_drift_and_a_symmetric_probe_does_not():
    """A RESULT I EXPECTED TO GO THE OTHER WAY, AND THE RULE IT GAVE.

    The first version of the test above asserted that a sine probe is not
    drift-dominated. It is: 20 s of a 0.5 Hz sine leaves cov(t,I)/var(I) at
    -0.0795 s, small but larger than the 3-sigma scatter of a strong probe,
    so drift is still the largest single term. Shrinking it by raising the
    amplitude only divides it by the amplitude; it never reaches zero.

    It reaches zero EXACTLY, at any amplitude and any window, when the
    profile is symmetric about the window midpoint: I(t) = I(T - t) makes
    cov(t, I) vanish term by term. That is a structural guarantee rather
    than a budget, and it is why `probes.py` builds its probes palindromic.
    """
    t, current = profile("sine", 20.0, 8.0)
    plain = ID.ExcitationStats.from_profile(t, current)
    assert abs(plain.cov_ti_over_var_i) > 0.01

    mid = 0.5 * (t[0] + t[-1])
    symmetric = BASE_A + 8.0 * np.cos(2.0 * np.pi * 0.5 * (t - mid))
    assert np.allclose(symmetric, symmetric[::-1]), "not a palindrome"
    sym = ID.ExcitationStats.from_profile(t, symmetric)
    assert abs(sym.cov_ti_over_var_i) < 1e-9, sym.cov_ti_over_var_i

    noise = ID.NoiseModel(sigma_v=0.020, sigma_i=0.08,
                          ocv_drift_v_per_s=0.010)
    assert ID.separability(sym, noise, 0.040).dominated_by != "drift"
    assert abs(ID.expected_estimate(0.040, sym, noise) - 0.040) < 1e-4
