"""Sensing sensitivity, and the cancellations that explain the zeros.

Section 11 of the task asks whether sensing defects barely moved the prior
margin because the system is genuinely insensitive or because the instrument
was disconnected. Both answers turned up. One defect -- dropout -- was
disconnected in the first version of the audit harness and is fixed. Four
others are **exactly** zero for reasons that can be derived, and this file
derives each one and then measures it.

A sensitivity of zero is only acceptable when it comes with a derivation. That
is the rule these tests enforce.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from csia_active_evidence import rcec
from csia_independent_validation import evaluator as ev
from csia_independent_validation.plants import (SYNTHETIC_SENSING, Sensing,
                                                simulate)
from csia_independent_validation.truth import TruthPair

DURATION_S = 8.0
DELTA = 0.020


def burst(t: float) -> float:
    if t < 0.0 or t > DURATION_S:
        return 0.0
    return 10.0 * math.cos(2.0 * math.pi * 3.0 * t / DURATION_S)


def _pair_change(sensing: Sensing, seed: int) -> float:
    """``e_dR`` for one matched pair, using only delivered samples."""
    nominal, nominal_truth = simulate(burst, plant="Q1", duration=DURATION_S,
                                      seed=seed, sensing=sensing)
    fault, fault_truth = simulate(burst, plant="Q1", duration=DURATION_S,
                                  seed=seed, sensing=sensing, r0_delta=DELTA)
    _, nominal_i, nominal_v = nominal.kept()
    _, fault_i, fault_v = fault.kept()
    return ev.evaluate_change(
        rcec.estimate_resistance(nominal_i, nominal_v),
        rcec.estimate_resistance(fault_i, fault_v),
        TruthPair(nominal=nominal_truth, fault=fault_truth)).e_delta_r


BASE = Sensing(**SYNTHETIC_SENSING)


# --- exact cancellations, each derived then measured ---------------------

def test_a_constant_voltage_offset_is_absorbed_by_the_intercept():
    """``V + b`` shifts only ``E`` in ``V = E - R I``, so ``R̂`` is unchanged."""
    for seed in (11, 12, 13):
        base = _pair_change(BASE, seed)
        offset = _pair_change(replace(BASE, bias_v=0.5), seed)
        assert offset == pytest.approx(base, abs=1e-15)


def test_a_constant_current_offset_leaves_the_slope_alone():
    """``I + b`` shifts the regressor by a constant.

    Least squares fits a free intercept, so the centred regressor -- and with
    it the slope -- is unchanged; the offset lands entirely in ``E - R b``.
    """
    for seed in (11, 12, 13):
        base = _pair_change(BASE, seed)
        offset = _pair_change(replace(BASE, bias_i=2.0), seed)
        assert offset == pytest.approx(base, abs=1e-13)


def test_voltage_noise_cancels_in_the_paired_difference():
    """Both members of the pair draw the same noise, and OLS is linear in V.

    So the noise contributes identically to both estimates and vanishes from
    their difference. This is IV-9 seen from the sensing side.
    """
    for seed in (11, 12, 13):
        base = _pair_change(BASE, seed)
        noisier = _pair_change(replace(BASE, sigma_v=0.2), seed)
        assert noisier == pytest.approx(base, abs=1e-14)


def test_timestamp_jitter_cannot_reach_an_estimator_that_never_reads_time():
    """``R̂`` regresses V on I. There is no ``t`` anywhere in that fit."""
    for seed in (11, 12, 13):
        base = _pair_change(BASE, seed)
        jittered = _pair_change(replace(BASE, timestamp_jitter_s=0.01), seed)
        assert jittered == pytest.approx(base, abs=1e-15)


def test_the_certificate_does_read_time_so_jitter_reaches_it():
    """The contrast that makes the previous test a derivation and not an alibi."""
    from csia_active_evidence import polarization as pz
    budget = rcec.ErrorBudget(
        r_reference=0.040, target_delta_r=DELTA, sigma_v=0.020, sigma_i=0.080,
        d_max=0.002,
        polarization=pz.PolarizationEnvelope(
            r1_min=0.004, r1_max=0.020, tau_min_s=1.0, tau_max_s=40.0,
            n_r1=5, n_tau=7),
        scale_error_max=0.02, hysteresis_v_max=0.040)
    quiet, _ = simulate(burst, plant="Q1", duration=DURATION_S, seed=11,
                        sensing=BASE)
    mild, _ = simulate(burst, plant="Q1", duration=DURATION_S, seed=11,
                       sensing=replace(BASE, timestamp_jitter_s=0.002))
    heavy, _ = simulate(burst, plant="Q1", duration=DURATION_S, seed=11,
                        sensing=replace(BASE, timestamp_jitter_s=0.01))

    clean = rcec.certify(*quiet.kept(), budget)
    shaken = rcec.certify(*mild.kept(), budget)
    broken = rcec.certify(*heavy.kept(), budget)

    # A little jitter moves the margin; the estimator would not have noticed.
    assert clean.state == shaken.state == "CERTIFIED_IN_MODEL"
    assert clean.resolution["margin"] != shaken.resolution["margin"]

    # Enough jitter and the timebase stops being monotone, which the
    # certificate treats as an instrument failure rather than a measurement.
    assert broken.state == "INVALID_INSTRUMENT"
    assert "TIMEBASE_NOT_STRICTLY_INCREASING" in broken.reasons
    assert broken.resolution.get("margin") is None


# --- defects that must move the outcome ----------------------------------

@pytest.mark.parametrize("field,value", [
    ("scale_i", 0.02), ("sigma_i", 0.2), ("quantum_i", 0.05),
    ("delay_i_s", 0.04), ("quantum_v", 0.01), ("delay_v_s", 0.04),
    ("dropout", 0.2),
])
def test_these_defects_do_reach_the_outcome(field, value):
    moved = [abs(_pair_change(replace(BASE, **{field: value}), seed)
                 - _pair_change(BASE, seed)) for seed in (11, 12, 13)]
    assert max(moved) > 0.0, f"{field} left the outcome untouched"


def test_dropout_is_connected_which_it_was_not_at_first():
    """The regression test for a disconnected instrument.

    The first audit harness passed the full arrays to the estimator, so a 20%
    dropout changed nothing: the samples telemetry had marked invalid were
    still being fitted. Its measured sensitivity was exactly zero, which looked
    like a finding.
    """
    observation, _ = simulate(burst, plant="Q1", duration=DURATION_S, seed=11,
                              sensing=replace(BASE, dropout=0.2))
    kept_t, kept_i, kept_v = observation.kept()
    assert kept_i.size < observation.n
    everything = rcec.estimate_resistance(observation.i_meas,
                                          observation.v_meas)
    delivered = rcec.estimate_resistance(kept_i, kept_v)
    assert everything != delivered


def test_scale_error_is_the_largest_single_sensitivity():
    """A gain error multiplies the regressor, so it attenuates the slope."""
    moves = {}
    for field, value in (("scale_i", 0.01), ("quantum_i", 0.01),
                         ("delay_i_s", 0.01), ("sigma_i", 0.01)):
        moves[field] = statistics_median([
            abs(_pair_change(replace(BASE, **{field: value}), seed)
                - _pair_change(BASE, seed)) for seed in (11, 12, 13)])
    assert moves["scale_i"] == max(moves.values())


def statistics_median(values):
    import statistics
    return statistics.median(values)


def test_a_one_percent_gain_error_moves_the_change_estimate_by_about_one_percent():
    """``I -> (1+s)I`` scales the fitted slope by ``1/(1+s)``, so ``e_dR ≈ -s Δ``."""
    scale = 0.01
    for seed in (11, 12, 13):
        base = _pair_change(BASE, seed)
        scaled = _pair_change(replace(BASE, scale_i=scale), seed)
        predicted = base - scale / (1.0 + scale) * DELTA
        assert scaled == pytest.approx(predicted, abs=2e-6)
