"""Prior-art baselines: textbook reconstructions, checked against their algebra.

No scholarly full text is reachable from this host, so nothing here is a
reproduction of any paper and nothing here supports a novelty claim. What can
be checked is that each reconstruction satisfies the identity that defines it,
and these tests do that.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from csia_independent_validation import baselines as bl


def _signal(n=400, dt=0.02, cycles=3, amplitude=10.0, offset=20.0):
    t = np.arange(n) * dt
    return offset + amplitude * np.cos(2.0 * math.pi * cycles * t / (n * dt))


# --- the provenance label travels with the code --------------------------

def test_every_number_here_is_labelled_a_reconstruction():
    assert bl.PROVENANCE == "TEXTBOOK_RECONSTRUCTION_NOT_A_PAPER_REPRODUCTION"


def test_the_unimplemented_baseline_carries_its_reason():
    assert "constrained_robust_tube_mpc_active_diagnosis" in bl.NOT_IMPLEMENTED
    reason = bl.NOT_IMPLEMENTED["constrained_robust_tube_mpc_active_diagnosis"]
    assert len(reason) > 100


# --- persistent excitation ------------------------------------------------

def test_a_constant_is_not_persistently_exciting():
    assert not bl.is_persistently_exciting(np.full(100, 5.0), 2)


def test_a_single_sinusoid_is_persistently_exciting_of_order_two():
    signal = _signal(cycles=3)
    assert bl.is_persistently_exciting(signal, 2)


def test_the_pe_matrix_is_symmetric_and_positive_semidefinite():
    matrix = bl.persistent_excitation_matrix(_signal(), 5)
    assert np.allclose(matrix, matrix.T)
    assert np.linalg.eigvalsh(matrix)[0] >= -1e-12


def test_pe_needs_more_samples_than_its_order():
    with pytest.raises(ValueError):
        bl.persistent_excitation_level(np.zeros(4), 8)


def test_white_noise_is_persistently_exciting_to_high_order():
    rng = np.random.default_rng(7)
    assert bl.is_persistently_exciting(rng.normal(size=2000), 12)


# --- Fisher information ---------------------------------------------------

def test_the_fisher_matrix_is_the_textbook_one():
    current = _signal(n=50)
    sigma = 0.02
    matrix = bl.fisher_information(current, sigma)
    assert matrix[0, 0] == pytest.approx(50 / sigma ** 2)
    assert matrix[0, 1] == pytest.approx(-current.sum() / sigma ** 2)
    assert matrix[1, 1] == pytest.approx((current ** 2).sum() / sigma ** 2)
    assert matrix[0, 1] == matrix[1, 0]


def test_the_cramer_rao_variance_of_r_is_sigma_squared_over_s_ii():
    """The identity that makes P7a the A-optimal design for this parameter."""
    current = _signal()
    sigma = 0.02
    centred = current - current.mean()
    assert bl.variance_of_r(current, sigma) == pytest.approx(
        sigma ** 2 / float(np.sum(centred ** 2)), rel=1e-12)


def test_the_crb_agrees_with_inverting_the_full_matrix():
    current = _signal()
    sigma = 0.02
    inverse = np.linalg.inv(bl.fisher_information(current, sigma))
    assert bl.variance_of_r(current, sigma) == pytest.approx(
        float(inverse[1, 1]), rel=1e-9)


def test_a_constant_current_gives_no_information_about_resistance():
    """With no variation in the regressor, R and E are not separable."""
    assert math.isinf(bl.variance_of_r(np.full(100, 20.0), 0.02))


def test_more_excitation_means_a_smaller_bound():
    sigma = 0.02
    assert bl.variance_of_r(_signal(amplitude=14.0), sigma) < \
        bl.variance_of_r(_signal(amplitude=4.0), sigma)


# --- finite-model discrimination -----------------------------------------

def test_separation_is_the_minimum_over_pairs():
    predictions = {"a": np.zeros(100), "b": np.full(100, 0.1),
                   "c": np.full(100, 0.5)}
    assert bl.pairwise_separation(predictions, 0.02) == pytest.approx(5.0)


def test_identical_hypotheses_are_not_separable():
    predictions = {"a": np.zeros(50), "b": np.zeros(50)}
    assert bl.pairwise_separation(predictions, 0.02) == 0.0


def test_discrimination_needs_two_hypotheses():
    with pytest.raises(ValueError):
        bl.pairwise_separation({"only": np.zeros(10)}, 0.02)


# --- set-membership -------------------------------------------------------

def test_a_consistent_dataset_gives_a_nonempty_set():
    current = _signal(n=40)
    voltage = 16.0 - 0.04 * current
    result = bl.feasible_set(current, voltage, 0.05)
    assert not result.empty
    assert result.area > 0


def test_the_true_parameters_are_inside_that_set():
    current = _signal(n=40)
    voltage = 16.0 - 0.04 * current
    result = bl.feasible_set(current, voltage, 0.05)
    inside = [abs(16.0 - v[0]) + abs(0.04 - v[1]) for v in result.vertices]
    assert min(inside) < 0.5


def test_a_tighter_bound_never_gives_a_larger_set():
    current = _signal(n=40)
    voltage = 16.0 - 0.04 * current
    tight = bl.feasible_set(current, voltage, 0.02)
    loose = bl.feasible_set(current, voltage, 0.10)
    assert tight.area <= loose.area


def test_data_the_model_cannot_explain_empties_the_set():
    """Model invalidation: the classical set-membership verdict."""
    current = _signal(n=40)
    voltage = 16.0 - 0.04 * current + 0.5 * np.sin(
        np.linspace(0, 20, current.size))
    assert bl.feasible_set(current, voltage, 0.01).empty


# --- classical post-execution validation ---------------------------------

def test_the_classical_fit_recovers_a_clean_line():
    current = _signal(n=200)
    voltage = 16.0 - 0.04 * current
    fit = bl.classical_fit(current, voltage)
    assert fit.r_hat == pytest.approx(0.04, abs=1e-9)
    assert fit.e_hat == pytest.approx(16.0, abs=1e-9)


def test_the_standard_error_shrinks_with_more_data():
    rng = np.random.default_rng(3)
    errors = []
    for n in (100, 400, 1600):
        current = _signal(n=n)
        voltage = 16.0 - 0.04 * current + rng.normal(0, 0.02, n)
        errors.append(bl.classical_fit(current, voltage).standard_error)
    assert errors == sorted(errors, reverse=True)


def test_the_classical_fit_has_no_staleness_concept_and_says_so():
    """Its defining property as a baseline, asserted rather than assumed."""
    current = _signal(n=100)
    voltage = 16.0 - 0.04 * current
    assert bl.classical_fit(current, voltage).to_dict()[
        "checks_staleness"] is False


def test_the_interval_brackets_the_estimate():
    rng = np.random.default_rng(5)
    current = _signal(n=300)
    voltage = 16.0 - 0.04 * current + rng.normal(0, 0.02, current.size)
    fit = bl.classical_fit(current, voltage)
    assert fit.ci_low < fit.r_hat < fit.ci_high
    assert fit.ci_high - fit.ci_low == pytest.approx(
        2 * 1.96 * fit.standard_error)
