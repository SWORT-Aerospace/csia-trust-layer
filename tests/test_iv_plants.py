"""Known-answer and independence tests for the Q0/Q1/Q2 plant family.

Two things have to be true before any of these plants can be used as the
source of ground truth:

1. the integrator is correct, checked against closed form rather than against
   the other simulator in this repository;
2. a branch that does not fire cannot perturb a stream belonging to a
   different subsystem.

The second one is not hypothetical. The first draft drew the timestamp-jitter
block only when jitter was enabled, which shifted the telemetry generator and
silently changed the dropout mask of every run with jitter switched off. It is
fixed and pinned below.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from csia_independent_validation import plants
from csia_independent_validation.plants import (Loop, QParams, Sensing,
                                                SYNTHETIC_LOOP, SYNTHETIC_Q,
                                                SYNTHETIC_SENSING, simulate)


def _silent_loop(**kwargs) -> Loop:
    """A loop with every stochastic term switched off."""
    return Loop(**{**SYNTHETIC_LOOP, "controller_sigma": 0.0,
                   "process_sigma": 0.0, **kwargs})


def _silent_sensing(**kwargs) -> Sensing:
    return Sensing(**{**SYNTHETIC_SENSING, "sigma_v": 0.0, "sigma_i": 0.0,
                      **kwargs})


# --- the integrator, against closed form ---------------------------------

@pytest.mark.parametrize("tau,dt", [(13.5, 0.02), (1.2, 0.02), (0.25, 0.02),
                                    (0.25, 0.1), (40.0, 0.02)])
def test_zoh_step_is_the_exact_solution(tau, dt):
    """``x(t) = x_inf (1 - e^{-t/tau})`` reached by stepping, to 1e-12."""
    state = 0.0
    target = 3.0
    for k in range(1, 200):
        state = plants._zoh(state, target, dt, tau)
        exact = target * (1.0 - math.exp(-k * dt / tau))
        assert state == pytest.approx(exact, abs=1e-12)


def test_forward_euler_would_fail_this_same_check():
    """The prior simulator's integrator, measured, not asserted from memory."""
    tau, dt, target = 0.25, 0.02, 3.0
    euler = 0.0
    for _ in range(1):
        euler += dt / tau * (target - euler)
    exact = target * (1.0 - math.exp(-dt / tau))
    assert euler == pytest.approx(0.24, abs=1e-12)
    assert exact == pytest.approx(0.23065, abs=1e-5)
    # ~4% apart on the first step. The plants are numerically independent.
    assert abs(euler - exact) / exact > 0.03


def test_rk4_thermal_matches_closed_form_for_constant_current():
    """``T(t) = T_amb + drive (1 - e^{-t/tau})`` under a held current."""
    params = QParams(**SYNTHETIC_Q)
    current, dt = 20.0, 0.02
    drive = params.thermal_rise_per_amp2 * current * current
    temp = params.t_ambient_c
    for k in range(1, 500):
        temp = plants._rk4_thermal(temp, current, dt, params)
        exact = params.t_ambient_c + drive * (
            1.0 - math.exp(-k * dt / params.thermal_tau_s))
        assert temp == pytest.approx(exact, abs=1e-9)


def test_q0_terminal_voltage_is_exactly_ocv_minus_ir():
    """With no noise and no lag, Q0 is a closed-form expression."""
    params = QParams(**SYNTHETIC_Q)
    loop = _silent_loop(lag_s=0.0)
    observation, truth = simulate(
        lambda t: 0.0, plant="Q0", duration=2.0, seed=11, params=params,
        sensing=_silent_sensing(), loop=loop)
    capacity_as = params.capacity_ah * 3600.0
    z = params.z_initial
    temp = params.t_ambient_c
    for k in range(observation.n):
        current = truth.i_true[k]
        temp = plants._rk4_thermal(temp, current, observation.dt_nominal,
                                   params)
        z -= current * observation.dt_nominal / capacity_as
        r0 = truth.r0_realized + params.r0_temp_coeff * (
            temp - params.t_ambient_c)
        assert truth.v_true[k] == pytest.approx(
            params.ocv(z, "Q0") - r0 * current, abs=1e-12)


def test_q1_polarization_reaches_i_times_r1():
    """The steady state of ``dV1/dt = -V1/(R1 C1) + I/C1`` is ``I R1``."""
    params = QParams(**SYNTHETIC_Q)
    _, truth = simulate(lambda t: 0.0, plant="Q1", duration=200.0, seed=5,
                        params=params, sensing=_silent_sensing(),
                        loop=_silent_loop(lag_s=0.0))
    assert truth.v1_true[-1] == pytest.approx(
        params.r1 * SYNTHETIC_LOOP["base_current"], rel=1e-3)


# --- the plants are actually different from one another ------------------

def test_each_plant_produces_a_different_voltage():
    traces = {}
    for plant in plants.PLANTS:
        observation, _ = simulate(lambda t: 0.0, plant=plant, duration=6.0,
                                  seed=7, sensing=_silent_sensing(),
                                  loop=_silent_loop())
        traces[plant] = observation.v_meas
    assert not np.allclose(traces["Q0"], traces["Q1"])
    assert not np.allclose(traces["Q1"], traces["Q2"])
    assert not np.allclose(traces["Q0"], traces["Q2"])


def test_the_rc_branch_is_actually_connected_to_the_voltage():
    """Falsifier 7: a richer plant that changes nothing is not connected."""
    params = QParams(**SYNTHETIC_Q)
    with_branch, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=9,
                              params=params, sensing=_silent_sensing(),
                              loop=_silent_loop())
    without, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=9,
                          params=replace(params, r1=0.0),
                          sensing=_silent_sensing(), loop=_silent_loop())
    separation = float(np.max(np.abs(with_branch.v_meas - without.v_meas)))
    assert separation > 1e-3, (
        f"removing R1 moved the terminal voltage by only {separation} V; "
        "the branch is not wired into the observation")


def test_hysteresis_moves_within_a_probe_window():
    """A "dynamic" effect slower than the probe is a constant offset.

    ``gamma |I| / Q`` at 20 A and 4 Ah gives a time constant near 12 s. The
    first draft of this module used a rate a thousand times slower, which
    made Q2's hysteresis indistinguishable from an OCV offset and would have
    quietly removed the one effect Q2 exists to carry.
    """
    params = QParams(**SYNTHETIC_Q)
    rate = params.hysteresis_gamma * 20.0 / (params.capacity_ah * 3600.0)
    assert 5.0 < 1.0 / rate < 30.0, (
        f"hysteresis time constant is {1.0 / rate:.1f} s, which is not "
        "comparable to a probe window")


def test_removing_hysteresis_is_detectable_on_q2():
    params = QParams(**SYNTHETIC_Q)
    command = lambda t: 8.0 * math.sin(2.0 * math.pi * t / 4.0)  # noqa: E731
    with_h, _ = simulate(command, plant="Q2", duration=12.0, seed=13,
                         params=params, sensing=_silent_sensing(),
                         loop=_silent_loop())
    without_h, _ = simulate(command, plant="Q2", duration=12.0, seed=13,
                            params=replace(params, hysteresis_v=0.0),
                            sensing=_silent_sensing(), loop=_silent_loop())
    assert float(np.max(np.abs(with_h.v_meas - without_h.v_meas))) > 1e-4


# --- stream discipline ----------------------------------------------------

def test_seven_named_streams():
    assert plants.STREAM_NAMES == (
        "plant", "voltage_sensor", "current_sensor", "controller",
        "environment", "telemetry", "unknown_fault")
    generators = plants.streams(42)
    assert set(generators) == set(plants.STREAM_NAMES)


def test_injecting_ringing_does_not_disturb_the_current_channel():
    """The unknown-fault branch must not reach the current-sensor stream."""
    quiet, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=21)
    loud, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=21,
                       ringing_amplitude_v=0.40)
    assert np.array_equal(quiet.i_meas, loud.i_meas)
    assert not np.allclose(quiet.v_meas, loud.v_meas)


def test_enabling_jitter_does_not_change_the_dropout_mask():
    """The defect that was in the first draft of this module."""
    base = Sensing(**SYNTHETIC_SENSING)
    without, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=31,
                          sensing=replace(base, dropout=0.2))
    with_jitter, _ = simulate(
        lambda t: 0.0, plant="Q1", duration=6.0, seed=31,
        sensing=replace(base, dropout=0.2, timestamp_jitter_s=0.001))
    assert np.array_equal(without.valid, with_jitter.valid)
    assert not np.array_equal(without.t, with_jitter.t)


def test_changing_r0_does_not_change_any_noise_draw():
    """Common random numbers across a matched nominal/fault pair."""
    nominal, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=41)
    fault, _ = simulate(lambda t: 0.0, plant="Q1", duration=6.0, seed=41,
                        r0_delta=0.02)
    assert np.array_equal(nominal.i_command, fault.i_command)
    assert not np.allclose(nominal.v_meas, fault.v_meas)


def test_same_seed_reproduces_bit_for_bit():
    first, truth_a = simulate(lambda t: 0.0, plant="Q2", duration=5.0, seed=77)
    second, truth_b = simulate(lambda t: 0.0, plant="Q2", duration=5.0, seed=77)
    assert np.array_equal(first.v_meas, second.v_meas)
    assert truth_a.i_true == truth_b.i_true


# --- the measurement chain actually bites --------------------------------

@pytest.mark.parametrize("field,value", [
    ("bias_i", 1.0), ("scale_i", 0.02), ("sigma_i", 0.20),
    ("quantum_i", 0.05), ("delay_i_s", 0.04), ("bias_v", 0.05),
    ("sigma_v", 0.10), ("quantum_v", 0.01), ("delay_v_s", 0.04),
    ("antialias_tau_s", 0.05),
])
def test_every_sensing_defect_changes_the_observation(field, value):
    command = lambda t: 6.0 * math.sin(2.0 * math.pi * t / 3.0)  # noqa: E731
    clean = _silent_sensing()
    base, _ = simulate(command, plant="Q1", duration=6.0, seed=51,
                       sensing=clean, loop=_silent_loop())
    dirty, _ = simulate(command, plant="Q1", duration=6.0, seed=51,
                        sensing=replace(clean, **{field: value}),
                        loop=_silent_loop())
    channel = "i_meas" if field.endswith("_i") or "_i_" in field else None
    moved = (not np.allclose(base.i_meas, dirty.i_meas)
             or not np.allclose(base.v_meas, dirty.v_meas))
    assert moved, f"{field}={value} left the observation untouched"
    del channel


def test_dropout_marks_samples_invalid():
    observation, _ = simulate(
        lambda t: 0.0, plant="Q1", duration=20.0, seed=61,
        sensing=replace(Sensing(**SYNTHETIC_SENSING), dropout=0.25))
    lost = int((~observation.valid).sum())
    assert 0 < lost < observation.n
    kept_t, kept_i, kept_v = observation.kept()
    assert kept_t.size == observation.n - lost


def test_saturation_is_reported():
    observation, _ = simulate(lambda t: 200.0, plant="Q1", duration=3.0,
                              seed=71)
    assert observation.saturated.any()


# --- truth bookkeeping ----------------------------------------------------

def test_truth_records_the_change_that_was_injected():
    _, truth = simulate(lambda t: 0.0, plant="Q1", duration=3.0, seed=81,
                        r0_delta=0.006)
    assert truth.delta_r0 == pytest.approx(0.006)
    assert truth.fault_label == "r0_increase"


def test_unknown_ringing_is_labelled_unknown():
    _, truth = simulate(lambda t: 0.0, plant="Q1", duration=3.0, seed=91,
                        ringing_amplitude_v=0.40)
    assert truth.fault_label == "unknown_ringing"
    assert truth.ringing_amplitude_v == 0.40


def test_truth_hides_its_traces_by_default():
    _, truth = simulate(lambda t: 0.0, plant="Q0", duration=2.0, seed=101)
    assert "withheld" in truth.to_dict()["i_true"]
    assert isinstance(truth.to_dict(with_traces=True)["i_true"], tuple)


def test_unknown_plant_is_rejected():
    with pytest.raises(ValueError):
        simulate(lambda t: 0.0, plant="Q9", duration=1.0, seed=1)


# --- the differential cancellation, derived and then pinned ---------------

def test_a_fault_in_r0_changes_the_voltage_by_exactly_minus_delta_times_i():
    """The identity the whole paired design rests on.

    The current trajectory does not depend on the fault: this loop is driven
    by command and lag, not by terminal voltage. So between a matched pair
    everything except ``R0`` is identical sample for sample, and

        V_fault(t) - V_nominal(t) = -dR . I_true(t)

    holds to floating point. Every plant-common nuisance -- OCV curvature,
    polarization, the second branch, hysteresis, self-heating, drift, and the
    voltage noise draw itself -- cancels in the difference.
    """
    delta = 0.010
    _, nominal = simulate(lambda t: 6.0 * math.cos(t), plant="Q2",
                          duration=8.0, seed=12345)
    _, fault = simulate(lambda t: 6.0 * math.cos(t), plant="Q2",
                        duration=8.0, seed=12345, r0_delta=delta)
    assert nominal.i_true == fault.i_true
    difference = np.array(fault.v_true) - np.array(nominal.v_true)
    expected = -delta * np.array(nominal.i_true)
    assert float(np.max(np.abs(difference - expected))) < 1e-12


def test_the_paired_change_error_is_exactly_the_finite_sample_eiv_factor():
    """What survives the cancellation, and nothing else.

    Because OLS is linear in the response and the regressor is shared,

        R_hat_fault - R_hat_nominal = dR . cov(I_true, I_meas)/var(I_meas)

    so the relative error of the paired change estimate is ``lambda_hat - 1``
    for that particular noise draw, independent of ``dR``. Measured against
    the estimator rather than asserted.
    """
    from csia_active_evidence import rcec

    command = lambda t: 10.0 * math.cos(2.0 * math.pi * 3.0 * t / 8.0)  # noqa
    nominal_obs, nominal_truth = simulate(command, plant="Q1", duration=8.0,
                                          seed=12345)
    i_true = np.array(nominal_truth.i_true)
    i_meas = np.array(nominal_obs.i_meas)
    lambda_hat = (np.cov(i_true, i_meas, bias=True)[0, 1] / i_meas.var())

    r_nominal = rcec.estimate_resistance(nominal_obs.i_meas,
                                         nominal_obs.v_meas)
    for delta in (0.002, 0.010, 0.040):
        fault_obs, _ = simulate(command, plant="Q1", duration=8.0, seed=12345,
                                r0_delta=delta)
        r_fault = rcec.estimate_resistance(fault_obs.i_meas, fault_obs.v_meas)
        assert (r_fault - r_nominal) == pytest.approx(delta * lambda_hat,
                                                      rel=1e-9)


def test_the_point_estimate_does_not_enjoy_that_cancellation():
    """Which is why the point metric is the one that can see the plant."""
    from csia_active_evidence import rcec

    command = lambda t: 10.0 * math.cos(2.0 * math.pi * 3.0 * t / 8.0)  # noqa
    errors = {}
    for plant in plants.PLANTS:
        observation, truth = simulate(command, plant=plant, duration=8.0,
                                      seed=12345)
        estimate = rcec.estimate_resistance(observation.i_meas,
                                            observation.v_meas)
        errors[plant] = abs(estimate - truth.r0_realized)
    assert errors["Q1"] > errors["Q0"] * 2.0
    assert errors["Q2"] > errors["Q0"]
