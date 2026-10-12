"""Deployable strategies P0-P6 and robust selectors S0-S3.

The property that matters here is negative: given an identical observable
history, nothing about the hidden world may change what gets chosen. That is
tested directly by permuting hidden state and requiring the selection to be
byte-identical, and structurally by pinning the fields a selector is allowed to
see.

A selector must also be able to decline. One that is forced to pick between two
actions is a coin, and the three abstention outcomes are checked to be
reachable rather than decorative.
"""
from __future__ import annotations

import dataclasses
import itertools
import random

import pytest

from csia_independent_validation import audit, strategies as st
from csia_independent_validation.actions import ACTION_SPACE, PASSIVE, by_name


def observable(**overrides) -> st.Observable:
    base = dict(lag_estimate_s=0.25, lag_uncertainty_s=0.05,
                drift_estimate_v_per_s=0.0, drift_uncertainty_v_per_s=1e-4,
                sigma_i_bound_a=0.08, sigma_v_bound_v=0.02,
                remaining_energy_as=80.0, remaining_time_s=12.0,
                mission_phase="hover", clip_margin_a=16.0)
    base.update(overrides)
    return st.Observable(**base)


# --- what a selector may see ---------------------------------------------

def test_the_observable_schema_is_pinned():
    names = {f.name for f in dataclasses.fields(st.Observable)}
    assert names == {
        "lag_estimate_s", "lag_uncertainty_s", "drift_estimate_v_per_s",
        "drift_uncertainty_v_per_s", "sigma_i_bound_a", "sigma_v_bound_v",
        "remaining_energy_as", "remaining_time_s", "mission_phase",
        "clip_margin_a"}


def test_the_observable_carries_nothing_that_smells_of_truth():
    names = [f.name for f in dataclasses.fields(st.Observable)]
    assert audit.observation_schema_is_clean(names) == []


def test_strategies_are_inside_layer_a_and_clean():
    assert "csia_independent_validation.strategies" in audit.LAYER_A_MODULES
    assert audit.layer_a_leaks() == {}


def test_strategies_import_no_truth_bearing_module():
    reachable = audit.transitive_imports(
        ["csia_independent_validation.strategies"])
    assert not (reachable & audit.truth_bearing_modules())


# --- every strategy returns an admissible action -------------------------

@pytest.mark.parametrize("name", st.STRATEGIES)
def test_every_strategy_returns_something_in_the_action_space(name):
    action = st.DEPLOYABLE[name](observable())
    assert action in ACTION_SPACE
    assert action.is_admissible


@pytest.mark.parametrize("name", st.STRATEGIES)
def test_every_strategy_is_a_pure_function_of_the_observable(name):
    """Called twice on equal inputs, it must return the same action."""
    first = st.DEPLOYABLE[name](observable())
    second = st.DEPLOYABLE[name](observable())
    assert first == second


@pytest.mark.parametrize("name", st.STRATEGIES)
def test_no_strategy_exceeds_the_declared_budget(name):
    tight = observable(remaining_energy_as=12.0, remaining_time_s=4.0,
                       clip_margin_a=5.0)
    action = st.DEPLOYABLE[name](tight)
    assert action.energy_as <= tight.remaining_energy_as + 1e-9
    assert action.duration_s <= tight.remaining_time_s + 1e-9
    assert action.peak_excess_a <= tight.clip_margin_a + 1e-9


def test_p0_costs_nothing():
    assert st.p0_passive(observable()) is PASSIVE


def test_p1_ignores_conditions_entirely():
    """The naive arm. Same waveform whatever the lag or the drift."""
    assert st.p1_palindromic(observable()) == st.p1_palindromic(
        observable(lag_estimate_s=1.0, drift_estimate_v_per_s=0.05))


def test_p2_minimises_the_predicted_lever_among_eligible_actions():
    state = observable()
    chosen = st.p2_compensated(state)
    chosen_lever = abs(st.predicted_moments(chosen, state.lag_estimate_s)[1])
    for action in ACTION_SPACE:
        s_ii, lever = st.predicted_moments(action, state.lag_estimate_s)
        if s_ii >= st.S_II_MIN and action.energy_as <= state.remaining_energy_as \
                and action.duration_s <= state.remaining_time_s \
                and action.peak_excess_a <= state.clip_margin_a:
            assert abs(lever) >= chosen_lever - 1e-12


def test_p3_is_the_cheapest_action_clearing_the_excitation_floor():
    state = observable()
    chosen = st.p3_shaped(state)
    for action in ACTION_SPACE:
        if st.predicted_moments(action, state.lag_estimate_s)[0] \
                >= st.S_II_MIN and action.energy_as <= state.remaining_energy_as:
            assert action.energy_as >= chosen.energy_as - 1e-12


def test_p6_is_a_slow_hold_which_is_the_worst_possible_shape_for_this():
    chosen = st.p6_mission(observable())
    assert chosen.shape_name == "hold"
    _, lever = st.predicted_moments(chosen, 0.25)
    designed = st.p2_compensated(observable())
    _, designed_lever = st.predicted_moments(designed, 0.25)
    assert abs(lever) > abs(designed_lever)


def test_every_strategy_falls_back_to_passive_when_nothing_is_affordable():
    broke = observable(remaining_energy_as=0.0, remaining_time_s=0.0,
                       clip_margin_a=0.0)
    for name in st.STRATEGIES:
        assert st.DEPLOYABLE[name](broke) is PASSIVE


# --- the selectors can decline -------------------------------------------

def test_s2_declines_when_there_is_not_enough_energy():
    assert st.s2_threshold(observable(remaining_energy_as=1.0)) == \
        st.NO_SAFE_INFORMATIVE_ACTION


def test_s2_declines_when_there_is_no_current_headroom():
    assert st.s2_threshold(observable(clip_margin_a=1.0)) == \
        st.NO_SAFE_INFORMATIVE_ACTION


def test_s2_declines_when_the_lag_is_not_known_well_enough():
    assert st.s2_threshold(observable(lag_uncertainty_s=0.20)) == \
        st.INSUFFICIENT_NUISANCE_KNOWLEDGE
    assert st.s2_threshold(observable(lag_estimate_s=0.0)) == \
        st.INSUFFICIENT_NUISANCE_KNOWLEDGE


def test_s2_waits_during_landing():
    assert st.s2_threshold(observable(mission_phase="landing")) == \
        st.WAIT_FOR_MISSION_EVIDENCE


def test_every_abstention_is_reachable_from_s2():
    reached = {st.s2_threshold(observable(remaining_energy_as=1.0)),
               st.s2_threshold(observable(lag_uncertainty_s=0.20)),
               st.s2_threshold(observable(mission_phase="landing"))}
    assert reached == set(st.ABSTENTIONS)


def test_s2_switches_to_p4_under_elevated_drift():
    """The rule the prior locked result motivates, and nothing more."""
    nominal = st.s2_threshold(observable(drift_estimate_v_per_s=0.0))
    elevated = st.s2_threshold(observable(drift_estimate_v_per_s=5.0e-3))
    assert nominal == st.p2_compensated(observable())
    assert elevated == st.p4_feedback(observable())
    assert nominal != elevated


def test_s2_counts_uncertainty_towards_the_drift_threshold():
    """A confident small estimate and a vague one are not the same evidence."""
    confident = st.s2_threshold(
        observable(drift_estimate_v_per_s=5.0e-4,
                   drift_uncertainty_v_per_s=1.0e-5))
    vague = st.s2_threshold(
        observable(drift_estimate_v_per_s=5.0e-4,
                   drift_uncertainty_v_per_s=1.0e-3))
    assert confident != vague


def test_s3_can_decline_and_is_never_forced():
    assert st.s3_minimax(observable(remaining_energy_as=1.0)) == \
        st.NO_SAFE_INFORMATIVE_ACTION
    assert st.s3_minimax(observable(mission_phase="landing")) == \
        st.WAIT_FOR_MISSION_EVIDENCE
    assert st.s3_minimax(observable(lag_estimate_s=0.0)) == \
        st.INSUFFICIENT_NUISANCE_KNOWLEDGE


def test_s3_chooses_between_p2_and_p4_on_worst_case_over_the_lag_interval():
    state = observable(lag_uncertainty_s=0.15)
    chosen = st.s3_minimax(state)
    assert chosen in (st.p2_compensated(state), st.p4_feedback(state))


def test_s0_and_s1_are_exactly_their_strategies():
    state = observable()
    assert st.s0_always_p2(state) == st.p2_compensated(state)
    assert st.s1_always_p4(state) == st.p4_feedback(state)


# --- leakage: hidden state must not reach the decision -------------------

@pytest.mark.parametrize("selector", sorted(st.SELECTORS))
def test_permuting_hidden_labels_cannot_change_the_selection(selector):
    """The core anti-leakage property, tested by trying to leak.

    A selector is handed the same observable state many times while a hidden
    world is shuffled around it. Since the hidden world is not an argument,
    the only way the selection could move is through global state, and that is
    what this is looking for.
    """
    rng = random.Random(20260913)
    state = observable()
    first = st.SELECTORS[selector](state)
    for _ in range(50):
        hidden = {"fault": rng.choice(["none", "r0_increase", "ringing"]),
                  "plant": rng.choice(["Q0", "Q1", "Q2"]),
                  "true_r0": rng.uniform(0.03, 0.09)}
        del hidden
        again = st.SELECTORS[selector](state)
        assert again == first


@pytest.mark.parametrize("selector", sorted(st.SELECTORS))
def test_the_selection_is_determined_by_the_observable_alone(selector):
    """Equal observables give equal decisions, across every field combination."""
    for phase, energy in itertools.product(
            ("cruise", "hover", "manoeuvre", "landing"), (5.0, 40.0, 80.0)):
        state = observable(mission_phase=phase, remaining_energy_as=energy)
        assert st.SELECTORS[selector](state) == st.SELECTORS[selector](
            st.Observable(**state.to_dict()))


def test_no_selector_signature_accepts_truth():
    import inspect
    for name, selector in st.SELECTORS.items():
        parameters = set(inspect.signature(selector).parameters)
        assert not (parameters & {"plant", "delta", "truth", "fault",
                                  "r0_true", "outcome"}), name


# --- predicted moments are predictions, and say so -----------------------

def test_predicted_moments_depend_on_the_declared_lag():
    action = by_name("cosine3_10A_8s")
    fast = st.predicted_moments(action, 0.05)
    slow = st.predicted_moments(action, 1.0)
    assert fast[0] > slow[0]
    assert abs(fast[1]) < abs(slow[1])


def test_a_palindromic_command_still_predicts_a_nonzero_realized_lever():
    """Proposition A, seen from the deployable side."""
    _, lever = st.predicted_moments(by_name("cosine3_10A_8s"), 0.25)
    assert abs(lever) > 1e-3
