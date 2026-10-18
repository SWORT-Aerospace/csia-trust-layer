"""The modelled observation set and the distance to it.

A distance is only meaningful if the set it is measured against is the set that
was declared, and if the projection really removes what the estimator can
absorb. Both are checked here, along with the boundary estimator's refusal to
invent a boundary the data does not contain.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from csia_independent_validation import openset
from csia_independent_validation.plants import simulate


def burst(t: float) -> float:
    if t < 0.0 or t > 8.0:
        return 0.0
    return 10.0 * math.cos(2.0 * math.pi * 3.0 * t / 8.0)


@pytest.fixture(scope="module")
def modelled():
    return openset.ModelledSet(burst, plant="Q1", duration=8.0, seed=5)


# --- the set is the declared one -----------------------------------------

def test_the_set_is_the_declared_envelope_enumerated(modelled):
    expected = (len(openset.MAGNITUDE_GRID) * len(openset.R1_GRID)
                * len(openset.TAU_GRID) * len(openset.DRIFT_GRID))
    assert modelled.size == expected == 126


def test_the_hypothesis_bank_contains_the_nominal_case():
    assert 0.0 in openset.MAGNITUDE_GRID


# --- the projection removes what the estimator absorbs -------------------

def test_projection_kills_a_constant_and_a_multiple_of_the_current():
    observation, _ = simulate(burst, plant="Q1", duration=8.0, seed=5)
    basis = openset.residual_basis(observation)
    absorbable = 3.0 * basis[:, 0] - 0.007 * basis[:, 1]
    assert float(np.max(np.abs(
        openset.project_out(absorbable, basis)))) < 1e-9


def test_projection_keeps_something_the_estimator_cannot_absorb():
    observation, _ = simulate(burst, plant="Q1", duration=8.0, seed=5)
    basis = openset.residual_basis(observation)
    oscillation = 0.1 * np.sin(np.linspace(0, 40.0, observation.n))
    assert float(np.max(np.abs(
        openset.project_out(oscillation, basis)))) > 0.01


def test_projection_is_idempotent():
    observation, _ = simulate(burst, plant="Q1", duration=8.0, seed=5)
    basis = openset.residual_basis(observation)
    values = np.asarray(observation.v_meas, dtype=float)
    once = openset.project_out(values, basis)
    twice = openset.project_out(once, basis)
    assert np.allclose(once, twice, atol=1e-9)


# --- distances behave ------------------------------------------------------

def test_a_no_fault_trace_sits_near_the_set(modelled):
    observation, _ = simulate(burst, plant="Q1", duration=8.0, seed=5)
    assert modelled.distance(observation).delta_unknown < 1.0


@pytest.mark.parametrize("amplitude", [0.05, 0.10, 0.20, 0.40, 0.80])
def test_distance_grows_with_ringing_amplitude(modelled, amplitude):
    quiet, _ = simulate(burst, plant="Q1", duration=8.0, seed=5)
    loud, _ = simulate(burst, plant="Q1", duration=8.0, seed=5,
                       ringing_amplitude_v=amplitude)
    assert modelled.distance(loud).delta_unknown > \
        modelled.distance(quiet).delta_unknown


def test_distance_is_monotone_across_the_amplitude_sweep(modelled):
    distances = []
    for amplitude in (0.0, 0.05, 0.10, 0.20, 0.40, 0.80):
        observation, _ = simulate(burst, plant="Q1", duration=8.0, seed=5,
                                  ringing_amplitude_v=amplitude)
        distances.append(modelled.distance(observation).delta_unknown)
    assert distances == sorted(distances)


def test_the_separation_reports_it_is_an_upper_bound(modelled):
    observation, _ = simulate(burst, plant="Q1", duration=8.0, seed=5,
                              ringing_amplitude_v=0.2)
    record = modelled.distance(observation).to_dict()
    assert "upper bound" in record["note"]
    assert record["members_enumerated"] == 126


# --- the boundary estimator ------------------------------------------------

def test_a_clean_separation_yields_a_boundary():
    separations = [0.5, 1.0, 1.5, 4.0, 5.0, 6.0]
    routed = [False, False, False, True, True, True]
    result = openset.boundary_from(separations, routed)
    assert result["boundary_sigmas"] == 4.0
    assert result["routed_rate_above"] == 1.0
    assert result["routed_rate_below"] == 0.0


def test_no_boundary_is_invented_when_the_data_has_none():
    separations = [0.5, 1.0, 4.0, 5.0]
    routed = [True, False, True, False]
    result = openset.boundary_from(separations, routed)
    assert result["boundary_sigmas"] is None
    assert "no separation reaches" in result["reason"]


def test_the_boundary_estimator_refuses_mismatched_inputs():
    with pytest.raises(ValueError):
        openset.boundary_from([1.0, 2.0], [True])


def test_an_empty_sweep_gives_no_boundary():
    assert openset.boundary_from([], [])["boundary"] is None


def test_routing_everything_puts_the_boundary_at_the_smallest_separation():
    result = openset.boundary_from([1.0, 2.0, 3.0], [True, True, True])
    assert result["boundary_sigmas"] == 1.0
    assert result["n_below"] == 0
