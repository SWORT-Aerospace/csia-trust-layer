"""The independent outcome evaluator, and the controls that give it teeth.

An evaluator nobody has tried to fool is decoration. Each detector here has a
positive case that must fire and a negative case that must not, in the same
file, so neither can quietly stop working.

The arithmetic tests are deliberately hand-computed rather than compared
against another function in the same module.
"""
from __future__ import annotations

import math

import pytest

from csia_independent_validation import evaluator as ev
from csia_independent_validation.truth import GroundTruth, TruthPair


def _truth(r0_realized: float, *, r0_nominal: float = 0.040,
           seed: int = 1, plant: str = "Q1") -> GroundTruth:
    label = "none" if r0_realized == r0_nominal else "r0_increase"
    return GroundTruth(plant=plant, r0_nominal=r0_nominal,
                       r0_realized=r0_realized, fault_label=label, seed=seed)


def _pair(delta: float, *, seed: int = 1, plant: str = "Q1") -> TruthPair:
    return TruthPair(nominal=_truth(0.040, seed=seed, plant=plant),
                     fault=_truth(0.040 + delta, seed=seed, plant=plant))


# --- the frozen constants -------------------------------------------------

def test_constants_match_the_preregistration():
    """If these drift, the phase is no longer the one that was registered."""
    import pathlib
    import re

    text = (pathlib.Path(__file__).resolve().parents[1]
            / "research/active_evidence/independent_validation"
            / "PREREGISTRATION.md").read_text()
    assert "`TAU_R_RELATIVE` | `0.5`" in text
    assert "`TAU_R_ABSOLUTE` | `0.002` ohm" in text
    assert "`COVERAGE_TARGET` | `0.90`" in text
    assert ev.TAU_R_RELATIVE == 0.5
    assert ev.TAU_R_ABSOLUTE == 0.002
    assert ev.COVERAGE_TARGET == 0.90
    assert re.search(r"`d_max_tested` \| `0.040` ohm", text)


def test_tau_is_relative_by_default_and_absolute_on_request():
    assert ev.tau_r(0.010) == pytest.approx(0.005)
    assert ev.tau_r(-0.010) == pytest.approx(0.005)
    assert ev.tau_r(0.010, relative=False) == 0.002


# --- point estimates ------------------------------------------------------

def test_point_error_is_signed_and_absolute_error_is_not():
    over = ev.evaluate_point(0.045, _truth(0.040))
    under = ev.evaluate_point(0.035, _truth(0.040))
    assert over.e_r == pytest.approx(+0.005)
    assert under.e_r == pytest.approx(-0.005)
    assert over.ae_r == under.ae_r == pytest.approx(0.005)


def test_relative_error_divides_by_the_true_value():
    outcome = ev.evaluate_point(0.050, _truth(0.040))
    assert outcome.re_r == pytest.approx(0.010 / 0.040)


def test_relative_error_does_not_divide_by_zero():
    outcome = ev.evaluate_point(0.001, _truth(0.0, r0_nominal=0.0))
    assert math.isfinite(outcome.re_r)


def test_point_estimate_is_scored_against_realized_not_nominal():
    """The trap: scoring against r0_nominal would make every fault look free."""
    outcome = ev.evaluate_point(0.040, _truth(0.060))
    assert outcome.e_r == pytest.approx(-0.020)


# --- change estimates -----------------------------------------------------

def test_perfect_change_estimate_resolves():
    outcome = ev.evaluate_change(0.040, 0.050, _pair(0.010))
    assert outcome.e_delta_r == pytest.approx(0.0)
    assert outcome.tau_r == pytest.approx(0.005)
    assert outcome.m_r_out == pytest.approx(0.005)
    assert outcome.resolved


def test_change_estimate_off_by_more_than_tau_does_not_resolve():
    #   estimated change 0.004 against a true change of 0.010
    #   error 0.006, tau 0.005, so the margin is negative
    outcome = ev.evaluate_change(0.040, 0.044, _pair(0.010))
    assert outcome.e_delta_r == pytest.approx(-0.006)
    assert outcome.m_r_out == pytest.approx(-0.001)
    assert not outcome.resolved


def test_the_boundary_is_strict():
    """M_R_out exactly zero is not resolved. Ties go against the claim."""
    outcome = ev.evaluate_change(0.040, 0.045, _pair(0.010))
    assert outcome.e_delta_r == pytest.approx(-0.005)
    assert outcome.m_r_out == pytest.approx(0.0)
    assert not outcome.resolved


def test_change_error_uses_the_difference_not_either_estimate():
    """Both estimates wrong by the same amount is a correct change estimate."""
    outcome = ev.evaluate_change(0.060, 0.070, _pair(0.010))
    assert outcome.e_delta_r == pytest.approx(0.0)
    assert outcome.resolved


# --- controls that must fire ----------------------------------------------

def test_an_estimator_that_returns_truth_is_detected_as_leakage():
    truths = [0.040, 0.046, 0.050, 0.060]
    assert ev.detect_leakage(list(truths), truths)


def test_an_honest_estimator_is_not_flagged_as_leakage():
    truths = [0.040, 0.046, 0.050, 0.060]
    noisy = [t + 1e-4 for t in truths]
    assert not ev.detect_leakage(noisy, truths)


def test_leakage_detector_needs_enough_cells_to_mean_anything():
    """Two exact hits is a coincidence, not evidence."""
    assert not ev.detect_leakage([0.04, 0.05], [0.04, 0.05])


def test_leakage_detector_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        ev.detect_leakage([0.04], [0.04, 0.05])


def test_an_estimator_that_always_returns_nominal_fails_change_evaluation():
    outcomes = [ev.evaluate_change(0.040, 0.040, _pair(d))
                for d in (0.004, 0.010, 0.020)]
    assert ev.is_degenerate_nominal(outcomes)
    assert not any(o.resolved for o in outcomes)
    # its change error is exactly the true change, every time
    for outcome, delta in zip(outcomes, (0.004, 0.010, 0.020)):
        assert outcome.e_delta_r == pytest.approx(-delta)


def test_a_working_estimator_is_not_called_degenerate():
    outcomes = [ev.evaluate_change(0.040, 0.040 + d * 0.9, _pair(d))
                for d in (0.004, 0.010, 0.020)]
    assert not ev.is_degenerate_nominal(outcomes)


# --- intervals ------------------------------------------------------------

def test_interval_coverage_and_width():
    outcome = ev.evaluate_interval(0.038, 0.043, _truth(0.040))
    assert outcome.covers_truth
    assert not outcome.false_exclusion
    assert outcome.width == pytest.approx(0.005)


def test_false_exclusion_is_recorded():
    outcome = ev.evaluate_interval(0.050, 0.060, _truth(0.040))
    assert not outcome.covers_truth
    assert outcome.false_exclusion


def test_interval_endpoints_may_arrive_in_either_order():
    assert ev.evaluate_interval(0.043, 0.038, _truth(0.040)).covers_truth


def test_set_separation_is_positive_only_when_the_sets_are_disjoint():
    disjoint = ev.evaluate_interval(0.050, 0.055, _truth(0.052),
                                    nominal_interval=(0.038, 0.042))
    assert disjoint.nominal_fault_separation == pytest.approx(0.008)
    overlapping = ev.evaluate_interval(0.041, 0.055, _truth(0.052),
                                       nominal_interval=(0.038, 0.045))
    assert overlapping.nominal_fault_separation < 0


def test_empirical_coverage_refuses_to_invent_a_rate_from_nothing():
    assert ev.coverage([]) is None
    outcomes = [ev.evaluate_interval(0.038, 0.043, _truth(0.040)),
                ev.evaluate_interval(0.050, 0.060, _truth(0.040))]
    assert ev.coverage(outcomes) == pytest.approx(0.5)


def test_simultaneous_coverage_needs_every_member():
    good = [ev.evaluate_interval(0.038, 0.043, _truth(0.040))] * 3
    assert ev.simultaneous_coverage(good)
    bad = good + [ev.evaluate_interval(0.050, 0.060, _truth(0.040))]
    assert not ev.simultaneous_coverage(bad)
    assert not ev.simultaneous_coverage([])


# --- calibration and the false certificates that can actually exist -------

def test_calibration_table_is_keyed_by_certificate_state():
    states = ["CERTIFIED_IN_MODEL"] * 3 + ["INSUFFICIENT_EXCITATION"] * 2
    outcomes = [ev.evaluate_change(0.040, 0.050, _pair(0.010)),
                ev.evaluate_change(0.040, 0.050, _pair(0.010)),
                ev.evaluate_change(0.040, 0.044, _pair(0.010)),
                ev.evaluate_change(0.040, 0.040, _pair(0.010)),
                ev.evaluate_change(0.040, 0.040, _pair(0.010))]
    table = ev.calibration_by_state(states, outcomes)
    assert table["CERTIFIED_IN_MODEL"]["n"] == 3
    assert table["CERTIFIED_IN_MODEL"]["resolved_fraction"] == pytest.approx(
        2 / 3)
    assert not table["CERTIFIED_IN_MODEL"]["meets_coverage_target"]
    assert table["INSUFFICIENT_EXCITATION"]["resolved_fraction"] == 0.0


def test_a_false_certificate_is_findable_here():
    """The whole point. The prior phase's equivalent check could not fire."""
    states = ["CERTIFIED_IN_MODEL", "CERTIFIED_IN_MODEL"]
    outcomes = [ev.evaluate_change(0.040, 0.050, _pair(0.010)),
                ev.evaluate_change(0.040, 0.041, _pair(0.010))]
    found = ev.false_certificates(states, outcomes)
    assert len(found) == 1
    assert found[0]["index"] == 1
    assert found[0]["m_r_out"] < 0


def test_a_sound_run_yields_no_false_certificates():
    states = ["CERTIFIED_IN_MODEL"] * 2
    outcomes = [ev.evaluate_change(0.040, 0.050, _pair(0.010))] * 2
    assert ev.false_certificates(states, outcomes) == []


def test_non_certified_states_are_never_false_certificates():
    states = ["MODEL_MISMATCH_LIMITED"]
    outcomes = [ev.evaluate_change(0.040, 0.040, _pair(0.010))]
    assert ev.false_certificates(states, outcomes) == []


def test_calibration_requires_one_state_per_outcome():
    with pytest.raises(ValueError):
        ev.calibration_by_state(["CERTIFIED_IN_MODEL"], [])


# --- censoring-aware statistics -------------------------------------------

def test_grid_resolution_area_is_a_mean_over_the_frozen_grid():
    assert ev.grid_resolution_area({0.002: 0.0, 0.004: 0.5,
                                    0.010: 1.0, 0.020: 1.0}) == pytest.approx(
        0.625)


def test_drift_interaction_stays_finite_when_a_method_never_resolves():
    """The failure that made the prior phase's scalar NaN."""
    value = ev.drift_interaction(area_with_drift=0.0, area_without_drift=0.5,
                                 passive_with_drift=0.0,
                                 passive_without_drift=0.0)
    assert value == pytest.approx(-0.5)
    assert math.isfinite(value)


def test_drift_interaction_refuses_anything_that_is_not_a_probability():
    with pytest.raises(ValueError):
        ev.drift_interaction(float("inf"), 0.5, 0.0, 0.0)
    with pytest.raises(ValueError):
        ev.drift_interaction(float("nan"), 0.5, 0.0, 0.0)
    with pytest.raises(ValueError):
        ev.drift_interaction(1.5, 0.5, 0.0, 0.0)


def test_censored_frontier_reports_a_bound_not_infinity():
    never = ev.censored_frontier({0.002: 0.0, 0.010: 0.2, 0.040: 0.5})
    assert never == "> 0.04"
    assert not isinstance(never, float)
    found = ev.censored_frontier({0.002: 0.0, 0.010: 0.95, 0.040: 1.0})
    assert found == 0.010


def test_censored_frontier_takes_the_smallest_magnitude_that_qualifies():
    assert ev.censored_frontier(
        {0.020: 1.0, 0.004: 0.90, 0.010: 0.99}) == 0.004
