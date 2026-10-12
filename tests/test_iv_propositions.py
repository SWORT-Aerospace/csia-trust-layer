"""Executable checks for Propositions A, B and C.

Each proposition has a statement in ``FORMAL_PROPOSITIONS.md``. These are the
known-answer tests that statement points at. Where a proposition rests on an
assumption that cannot be checked from inside the system, there is a test that
violates the assumption and shows the conclusion failing, so nobody can mistake
the assumption for a formality.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from csia_independent_validation import propositions as prop


# --- Proposition A: command certificates are not sufficient --------------

def test_the_transformation_is_causal():
    """Changing the command at sample k cannot move the output before k."""
    n, dt, tau = 200, 0.02, 0.25
    base = prop.palindromic_command(n, 3, 10.0)
    poked = base.copy()
    poked[120] += 50.0
    before = prop.first_order_lag(base, dt, tau)
    after = prop.first_order_lag(poked, dt, tau)
    assert np.array_equal(before[:120], after[:120])
    assert not np.allclose(before[120:], after[120:])


def test_the_transformation_is_bounded():
    """A convex combination of past inputs cannot exceed their supremum."""
    command = prop.palindromic_command(400, 3, 10.0)
    realized = prop.first_order_lag(command, 0.02, 0.25)
    assert float(np.max(np.abs(realized))) <= float(
        np.max(np.abs(command))) + 1e-12


def test_the_command_really_is_palindromic():
    command = prop.palindromic_command(401, 3, 10.0)
    assert np.allclose(command, command[::-1], atol=1e-12)


def test_a_palindromic_command_has_zero_drift_lever():
    n = 401
    t = np.arange(n) * 0.02
    command = prop.palindromic_command(n, 3, 10.0)
    s_ii, s_ti = prop.moments(t, command)
    assert s_ii > 0
    assert abs(s_ti / s_ii) < 1e-9


@pytest.mark.parametrize("cycles", [1, 2, 3, 6])
def test_proposition_a_holds_for_every_tested_waveform(cycles):
    """The command passes; the realized current does not."""
    instance = prop.command_counterexample(cycles=cycles)
    assert instance.command_passes
    assert not instance.realized_passes
    assert instance.is_a_counterexample


def test_the_failing_condition_is_the_drift_lever():
    instance = prop.command_counterexample(cycles=3, gamma=0.01,
                                           s_ii_min=1.0e3)
    assert abs(instance.lever_command) < 1e-9
    assert abs(instance.lever_realized) > 0.027
    assert instance.s_ii_realized >= instance.s_ii_min


def test_excitation_alone_can_also_be_the_failing_condition():
    """A second, independent failure mode: the lag eats the second moment."""
    instance = prop.command_counterexample(cycles=6, s_ii_min=1.0e4,
                                           gamma=1.0)
    assert instance.s_ii_command >= 1.0e4
    assert instance.s_ii_realized < 1.0e4
    assert instance.command_passes
    assert not instance.realized_passes


def test_the_construction_is_not_vacuous_when_there_is_no_lag():
    """With tau -> 0 the realized current is the command and both pass."""
    instance = prop.command_counterexample(tau=1e-9, cycles=3)
    assert instance.command_passes
    assert instance.realized_passes
    assert not instance.is_a_counterexample


def test_lag_magnitude_controls_the_size_of_the_violation():
    levers = [abs(prop.command_counterexample(tau=tau).lever_realized)
              for tau in (0.01, 0.05, 0.25, 1.0)]
    assert levers == sorted(levers)


# --- Proposition B: conditional soundness --------------------------------

def test_disjointness_is_the_obvious_interval_condition():
    assert prop.sets_are_disjoint(0.040, 0.060, 0.009)
    assert not prop.sets_are_disjoint(0.040, 0.060, 0.011)
    assert not prop.sets_are_disjoint(0.040, 0.060, 0.010)   # touching


def test_soundness_conclusion_holds_when_the_assumption_does():
    report = prop.soundness_holds(
        true_nominal=0.040, true_fault=0.060,
        estimate_nominal=0.042, estimate_fault=0.058, half_width=0.005)
    assert report["assumption_error_set_contains_truth"]
    assert report["sets_disjoint"]
    assert report["sign_is_correct"]
    assert report["conclusion_holds"]


def test_the_conclusion_fails_when_the_error_set_does_not_contain_truth():
    """The assumption is not a formality, and this is the proof of that.

    Both estimates sit inside a half-width of each other's truth but neither
    is within a half-width of its own, and the claimed change reverses sign.
    """
    report = prop.soundness_holds(
        true_nominal=0.060, true_fault=0.040,
        estimate_nominal=0.042, estimate_fault=0.058, half_width=0.005)
    assert not report["assumption_error_set_contains_truth"]
    assert report["sets_disjoint"]
    assert not report["sign_is_correct"]
    # The proposition says nothing about this case, so its conclusion is
    # vacuously satisfied -- which is exactly the caveat that has to be stated.
    assert report["conclusion_holds"]


def test_overlapping_sets_make_no_claim():
    report = prop.soundness_holds(
        true_nominal=0.040, true_fault=0.042,
        estimate_nominal=0.041, estimate_fault=0.041, half_width=0.010)
    assert not report["sets_disjoint"]
    assert report["conclusion_holds"]


def test_a_zero_change_is_reported_as_zero_not_as_a_sign():
    report = prop.soundness_holds(0.040, 0.040, 0.040, 0.040, 0.005)
    assert report["true_change_sign"] == 0
    assert report["claimed_change_sign"] == 0


# --- Proposition C: staleness after action modification ------------------

def test_truncation_keeps_only_the_prefix():
    t = np.arange(400) * 0.02
    signal = prop.palindromic_command(400, 3, 10.0)
    prefix = prop.truncate(t, signal, signal, 0.25)
    assert prefix.t.size == 100
    assert np.array_equal(prefix.i_meas, signal[:100])
    assert prefix.recomputed_from_measurement


def _full_and_prefix(fraction, *, n=400, dt=0.02, tau=0.25, cycles=3):
    t = np.arange(n) * dt
    realized = prop.first_order_lag(
        prop.palindromic_command(n, cycles, 10.0), dt, tau)
    full = prop.moments(t, realized)
    prefix = prop.truncate(t, realized, realized, fraction)
    cut = prop.moments(prefix.t, prefix.i_meas)
    return ((full[0], full[1] / full[0]), (cut[0], cut[1] / cut[0]))


@pytest.mark.parametrize("fraction", [0.2, 0.25, 0.4, 0.5, 0.75, 0.9, 0.95])
def test_a_prediction_for_the_whole_window_does_not_bound_a_truncation(
        fraction):
    full_pair, cut_pair = _full_and_prefix(fraction)
    assert not prop.predicted_moments_bound_realized(full_pair, cut_pair)
    assert cut_pair[0] < full_pair[0]              # excitation is always lost


def test_truncation_is_not_conservative_in_either_direction():
    """Measured, after the first version of this test guessed and was wrong.

    A plausible story says a prefix of a palindrome carries more drift
    leverage than the whole, so truncation is at least predictable. It is
    not. Across the executed fraction the realized lever is non-monotone and
    changes sign: at 0.25 it is 3.3 times the full-window value, at 0.40 it
    has flipped positive, and at 0.50 it nearly vanishes. A certificate
    computed for the whole waveform bounds the prefix in neither direction.

    This is the same shape of result as the prior phase's finding that lag
    underestimation is not automatically conservative.
    """
    full_pair, _ = _full_and_prefix(0.5)
    levers = {f: _full_and_prefix(f)[1][1]
              for f in (0.2, 0.25, 0.4, 0.5, 0.75, 0.9)}
    worse = [f for f, lever in levers.items()
             if abs(lever) > abs(full_pair[1])]
    better = [f for f, lever in levers.items()
              if abs(lever) < abs(full_pair[1])]
    signs = {math.copysign(1.0, lever) for lever in levers.values()}
    assert worse, "no tested truncation made the lever worse"
    assert better, "no tested truncation made the lever better"
    assert signs == {-1.0, 1.0}, "the lever never changed sign"
    assert abs(levers[0.25]) > 3.0 * abs(full_pair[1])


@pytest.mark.parametrize("fraction", [0.25, 0.5, 0.75, 0.9])
def test_every_tested_truncation_loses_excitation(fraction):
    n, dt = 400, 0.02
    t = np.arange(n) * dt
    realized = prop.first_order_lag(
        prop.palindromic_command(n, 3, 10.0), dt, 0.25)
    full_s_ii, _ = prop.moments(t, realized)
    prefix = prop.truncate(t, realized, realized, fraction)
    cut_s_ii, _ = prop.moments(prefix.t, prefix.i_meas)
    assert cut_s_ii < full_s_ii


def test_a_full_execution_is_bounded_by_its_own_prediction():
    """The narrow case where recomputation is safe: nothing was modified."""
    n, dt = 400, 0.02
    t = np.arange(n) * dt
    realized = prop.first_order_lag(
        prop.palindromic_command(n, 3, 10.0), dt, 0.25)
    full = prop.moments(t, realized)
    pair = (full[0], full[1] / full[0])
    assert prop.predicted_moments_bound_realized(pair, pair)


def test_recomputing_from_the_prefix_is_self_consistent():
    """A prefix certificate must use the prefix's own moments, not the plan's."""
    n, dt = 400, 0.02
    t = np.arange(n) * dt
    realized = prop.first_order_lag(
        prop.palindromic_command(n, 3, 10.0), dt, 0.25)
    prefix = prop.truncate(t, realized, realized, 0.6)
    own = prop.moments(prefix.t, prefix.i_meas)
    own_pair = (own[0], own[1] / own[0])
    assert prop.predicted_moments_bound_realized(own_pair, own_pair)
    assert prefix.fraction_executed == 0.6
