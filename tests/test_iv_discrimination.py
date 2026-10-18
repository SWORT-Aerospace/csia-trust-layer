"""The pairwise output-set reduction, and the surrogate's blind spot.

The user-supplied related-work draft is explicit that zero intersection
*volume* does not imply an empty intersection. These tests hold the module to
that: the touching case is constructed, and the volume surrogate is shown to
report it identically to a strictly separated pair while the separation margin
and the Hausdorff distance both tell them apart.

Nothing here reproduces any paper's method. The primary text was not
retrievable from this container.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from csia_independent_validation import discrimination as disc
from csia_independent_validation.actions import by_name


def burst():
    return by_name("cosine3_10A_8s").command()


# --- the provenance label travels with the code --------------------------

def test_the_module_labels_itself_a_reduction():
    assert disc.PROVENANCE == "FROZEN_REDUCTION_NOT_A_REPRODUCTION"


def test_no_claim_about_the_paper_is_made_in_the_source():
    """Nothing may be phrased as 'the paper shows'. The text was never read."""
    import pathlib
    source = pathlib.Path(disc.__file__).read_text().lower()
    for phrase in ("the paper shows", "the paper states", "the paper proves",
                   "as shown in section", "per the paper"):
        assert phrase not in source


# --- intervals ------------------------------------------------------------

def test_an_inverted_interval_is_refused():
    with pytest.raises(ValueError):
        disc.Interval(1.0, 0.0)


def test_a_degenerate_interval_is_allowed():
    point = disc.Interval(2.0, 2.0)
    assert point.width == 0.0


def test_overlapping_intervals_report_negative_margin():
    overlap, gap = disc.Interval(0.0, 2.0).intersect(disc.Interval(1.0, 3.0))
    assert overlap == pytest.approx(1.0)
    assert gap == pytest.approx(-1.0)


def test_separated_intervals_report_the_gap():
    overlap, gap = disc.Interval(0.0, 1.0).intersect(disc.Interval(3.0, 4.0))
    assert overlap == 0.0
    assert gap == pytest.approx(2.0)


# --- the counterexample the task asks for --------------------------------

def test_touching_sets_have_zero_volume_and_a_non_empty_intersection():
    """The surrogate's blind spot, constructed.

    ``[0, 1]`` and ``[1, 2]`` meet at exactly one point. The intersection is
    ``{1}``: measure zero, and not empty. A baseline that reads zero volume as
    separation would call these two hypotheses distinguishable when they are
    not.
    """
    overlap, gap = disc.Interval(0.0, 1.0).intersect(disc.Interval(1.0, 2.0))
    assert overlap == 0.0
    assert gap == 0.0

    touching = disc.PairOutcome(
        hypothesis_a=0.0, hypothesis_b=0.01, best_time_s=0.0,
        overlap_volume=overlap, separation_margin=gap)
    assert touching.zero_volume is True
    assert touching.empty_intersection is False
    assert touching.touching is True


def test_a_strictly_separated_pair_is_not_touching():
    separated = disc.PairOutcome(
        hypothesis_a=0.0, hypothesis_b=0.01, best_time_s=0.0,
        overlap_volume=0.0, separation_margin=0.5)
    assert separated.zero_volume is True
    assert separated.empty_intersection is True
    assert separated.touching is False


def test_the_volume_surrogate_cannot_tell_those_two_cases_apart():
    """Both score zero. That is the deficiency, stated as a test."""
    touching = disc.PairOutcome(0.0, 0.01, 0.0, 0.0, 0.0)
    separated = disc.PairOutcome(0.0, 0.01, 0.0, 0.0, 0.5)
    assert disc.objective([touching]) == disc.objective([separated]) == 0.0
    assert touching.separation_margin != separated.separation_margin


def test_hausdorff_distinguishes_what_the_volume_cannot():
    touching_a = [disc.Interval(0.0, 1.0)]
    touching_b = [disc.Interval(1.0, 2.0)]
    far_b = [disc.Interval(5.0, 6.0)]
    assert disc.hausdorff(touching_a, touching_b) == pytest.approx(1.0)
    assert disc.hausdorff(touching_a, far_b) == pytest.approx(5.0)


# --- separation over a sampled trajectory --------------------------------

def test_separate_takes_the_best_time_not_the_first():
    a = [disc.Interval(0.0, 1.0), disc.Interval(0.0, 1.0)]
    b = [disc.Interval(0.5, 1.5), disc.Interval(3.0, 4.0)]
    outcome = disc.separate(a, b, times=[0.0, 0.02])
    assert outcome.best_time_s == pytest.approx(0.02)
    assert outcome.empty_intersection


def test_separate_refuses_mismatched_grids():
    with pytest.raises(ValueError):
        disc.separate([disc.Interval(0.0, 1.0)], [])


def test_separate_refuses_an_empty_set():
    with pytest.raises(ValueError):
        disc.separate([], [])


# --- the output set over the declared envelope ---------------------------

def test_the_output_set_brackets_a_run_inside_the_envelope():
    from csia_independent_validation.plants import (SYNTHETIC_SENSING,
                                                    Sensing, simulate)
    intervals = disc.output_set(burst(), magnitude=0.0, plant="Q1",
                                duration=4.0, seed=5)
    quiet = Sensing(**{**SYNTHETIC_SENSING, "sigma_v": 0.0, "sigma_i": 0.0})
    observation, _ = simulate(burst(), plant="Q1", duration=4.0, seed=5,
                              sensing=quiet)
    for interval, value in zip(intervals, observation.v_meas):
        assert interval.low <= value <= interval.high


def test_a_larger_fault_separates_further():
    small = disc.nominal_versus(burst(), magnitude=0.006, plant="Q1",
                                duration=4.0, seed=5)
    large = disc.nominal_versus(burst(), magnitude=0.040, plant="Q1",
                                duration=4.0, seed=5)
    assert large.separation_margin > small.separation_margin


def test_the_smallest_magnitude_does_not_separate_on_this_command():
    """Reported, not repaired: the declared envelope is wider than the fault."""
    outcome = disc.nominal_versus(burst(), magnitude=0.002, plant="Q1",
                                  duration=8.0, seed=5)
    assert not outcome.empty_intersection
    assert outcome.separation_margin < 0


def test_pairwise_covers_every_unordered_pair():
    magnitudes = (0.0, 0.010, 0.040)
    outcomes = disc.pairwise(burst(), magnitudes=magnitudes, plant="Q1",
                             duration=4.0, seed=5)
    assert len(outcomes) == 3
    assert {(o.hypothesis_a, o.hypothesis_b) for o in outcomes} == {
        (0.0, 0.010), (0.0, 0.040), (0.010, 0.040)}


def test_the_objective_sums_the_best_case_overlaps():
    outcomes = disc.pairwise(burst(), magnitudes=(0.0, 0.010, 0.040),
                             plant="Q1", duration=4.0, seed=5)
    assert disc.objective(outcomes) == pytest.approx(
        sum(o.overlap_volume for o in outcomes))


def test_widening_by_more_sigmas_can_only_reduce_separation():
    tight = disc.output_set(burst(), magnitude=0.040, plant="Q1",
                            duration=4.0, seed=5, k_sigma=1.0)
    loose = disc.output_set(burst(), magnitude=0.040, plant="Q1",
                            duration=4.0, seed=5, k_sigma=6.0)
    assert loose[0].width > tight[0].width
