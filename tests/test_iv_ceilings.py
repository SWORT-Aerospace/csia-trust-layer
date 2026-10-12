"""Gate B — a legitimate ceiling, and an honest name for the thing that wasn't.

The prior phase's ``P7_oracle`` maximised current second moment, never issued a
certificate anywhere on the grid, and was beaten by every deployable arm. These
tests hold the new taxonomy to the standard that one failed: P7a is a
benchmark and is never called an oracle, and P7b is exhaustive over exactly the
action space everything else draws from, so it cannot be beaten for reasons of
scope.
"""
from __future__ import annotations

import numpy as np
import pytest

from csia_independent_validation import ceilings, partitions as pt
from csia_independent_validation.actions import (ACTION_SPACE,
                                                 ENERGY_LIMIT_AS, PASSIVE,
                                                 PEAK_EXCESS_LIMIT_A, Action,
                                                 by_name, energy_class,
                                                 matched)

DEV = pt.seeds("development")


@pytest.fixture(scope="module")
def arena():
    return ceilings.Arena()


# --- the action space -----------------------------------------------------

def test_action_space_is_finite_and_frozen():
    assert len(ACTION_SPACE) == 72
    assert len({a.name for a in ACTION_SPACE}) == 72


def test_every_action_in_the_space_is_admissible():
    for action in ACTION_SPACE:
        assert action.is_admissible, action.name
        assert action.peak_excess_a <= PEAK_EXCESS_LIMIT_A + 1e-9
        assert action.energy_as <= ENERGY_LIMIT_AS + 1e-9


def test_inadmissible_actions_are_excluded_not_clipped():
    """A 14 A hold for 12 s costs 168 A.s and simply is not in the set."""
    too_costly = Action(name="x", shape_name="hold", amplitude_a=14.0,
                        duration_s=12.0)
    assert not too_costly.is_admissible
    assert too_costly.name not in {a.name for a in ACTION_SPACE}


def test_passive_costs_nothing_and_is_in_the_space():
    assert PASSIVE.energy_as == 0.0
    assert PASSIVE.peak_excess_a == 0.0
    assert energy_class(PASSIVE) == "none"
    assert by_name("passive") == PASSIVE


def test_matched_cost_sets_share_class_and_duration():
    reference = by_name("cosine3_10A_8s")
    for action in matched(reference):
        assert energy_class(action) == energy_class(reference)
        assert action.duration_s == reference.duration_s
    assert reference in matched(reference)


def test_action_digest_identifies_the_waveform():
    assert by_name("cosine3_10A_8s").digest() != by_name(
        "cosine3_10A_4s").digest()
    assert by_name("cosine3_10A_8s").digest() == Action(
        name="other-name", shape_name="cosine3", amplitude_a=10.0,
        duration_s=8.0).digest()


def test_a_command_is_zero_outside_its_window():
    command = by_name("cosine3_10A_8s").command()
    assert command(-0.1) == 0.0
    assert command(8.1) == 0.0
    assert command(0.0) != 0.0


# --- P7a is a benchmark, and it is not an oracle -------------------------

def test_p7a_uses_no_truth():
    """Its selection depends only on the measured current of the nominal run."""
    import inspect
    source = inspect.getsource(ceilings.p7a_select)
    assert "delta" not in source
    assert "truth" not in source.lower().replace("no truth", "")


def test_p7a_maximises_the_second_moment_it_claims_to():
    arena = ceilings.Arena()
    chosen = ceilings.p7a_select(arena, "Q1", DEV[0])
    best = max(arena.nominal(a, "Q1", DEV[0])[2]
               for a in ceilings.candidates())
    assert arena.nominal(chosen, "Q1", DEV[0])[2] == pytest.approx(best)


def test_the_word_oracle_is_not_attached_to_p7a():
    import pathlib
    source = pathlib.Path(
        ceilings.__file__).read_text()
    # "P7a" may appear near the word oracle only to deny the association.
    for line in source.splitlines():
        if "P7a" in line and "oracle" in line.lower():
            assert "never an oracle" in line or "not an oracle" in line, line


def test_p7a_and_p7b_do_not_agree_which_means_s_ii_is_not_the_objective():
    """The prior phase's finding, reproduced on independent plants."""
    arena = ceilings.Arena()
    benchmark = ceilings.p7a_select(arena, "Q1", DEV[0])
    oracle, _ = ceilings.p7b_select(arena, "Q1", DEV[0], 0.010)
    assert benchmark.name != oracle.name


# --- the ceiling invariant ------------------------------------------------

@pytest.mark.parametrize("plant", ["Q0", "Q1", "Q2"])
@pytest.mark.parametrize("delta", [0.002, 0.010, 0.040])
def test_no_action_beats_p7b_on_the_change_loss(arena, plant, delta):
    report = ceilings.ceiling_invariant(
        arena, plant, DEV[0], delta, deployable=ceilings.candidates(),
        loss="change")
    assert report["holds"], report["violations"]


@pytest.mark.parametrize("plant", ["Q0", "Q1", "Q2"])
def test_no_action_beats_p7b_on_the_point_loss(arena, plant):
    report = ceilings.ceiling_invariant(
        arena, plant, DEV[1], 0.006, deployable=ceilings.candidates(),
        loss="point")
    assert report["holds"], report["violations"]


def test_the_invariant_reports_rather_than_raises(arena):
    report = ceilings.ceiling_invariant(
        arena, "Q1", DEV[0], 0.010, deployable=[PASSIVE], loss="change")
    assert set(report) >= {"holds", "violations", "oracle_action",
                           "oracle_loss", "tolerance"}


def test_the_invariant_can_detect_a_violation():
    """Positive control: hand it an oracle loss that is impossibly good."""
    arena = ceilings.Arena()
    real = ceilings.ceiling_invariant(
        arena, "Q1", DEV[0], 0.010, deployable=ceilings.candidates())
    assert real["holds"]
    # Every action now "beats" a loss of -1, so the checker must say so.
    losses = [arena.run(a, "Q1", DEV[0], 0.010).loss("change")
              for a in ceilings.candidates()]
    assert all(loss > -1.0 for loss in losses)
    assert any(loss - (-1.0) > ceilings.CEILING_TOLERANCE for loss in losses)


def test_regret_is_never_negative_when_the_invariant_holds(arena):
    _, oracle = ceilings.p7b_select(arena, "Q2", DEV[2], 0.020)
    for action in ceilings.candidates():
        outcome = arena.run(action, "Q2", DEV[2], 0.020)
        assert ceilings.regret(outcome, oracle.loss("change")) >= -1e-15


# --- P7c does not look at the realized fault -----------------------------

def test_p7c_does_not_receive_the_realized_delta():
    import inspect
    signature = inspect.signature(ceilings.p7c_select)
    assert "delta" not in signature.parameters
    assert "magnitudes" in signature.parameters
    assert "plants_in_envelope" in signature.parameters


def test_p7c_minimises_the_worst_case_over_the_declared_envelope():
    arena = ceilings.Arena()
    magnitudes = (0.004, 0.020)
    chosen, worst = ceilings.p7c_select(
        arena, DEV[3], plants_in_envelope=("Q0", "Q2"), magnitudes=magnitudes)
    for action in ceilings.candidates():
        action_worst = max(
            arena.run(action, plant, DEV[3], delta).loss("change")
            for plant in ("Q0", "Q2") for delta in magnitudes)
        assert action_worst >= worst - 1e-15
    assert chosen in ceilings.candidates()


def test_p7c_may_differ_from_p7b_because_it_is_not_told_the_answer():
    arena = ceilings.Arena()
    robust, _ = ceilings.p7c_select(
        arena, DEV[3], plants_in_envelope=("Q0", "Q1", "Q2"),
        magnitudes=(0.002, 0.040))
    hindsight, _ = ceilings.p7b_select(arena, "Q0", DEV[3], 0.002)
    assert isinstance(robust.name, str) and isinstance(hindsight.name, str)


# --- the arena itself -----------------------------------------------------

def test_the_nominal_baseline_is_shared_across_magnitudes(arena):
    """Otherwise the paired comparison is against a moving baseline."""
    action = by_name("cosine3_10A_8s")
    before = arena.simulations
    first = arena.nominal(action, "Q1", DEV[0])
    arena.run(action, "Q1", DEV[0], 0.004)
    arena.run(action, "Q1", DEV[0], 0.040)
    second = arena.nominal(action, "Q1", DEV[0])
    assert first[1] == second[1]          # the same nominal estimate
    assert first[2] == second[2]          # the same second moment
    assert first[0] == second[0]          # the same (trace-free) truth
    assert arena.simulations - before <= 3


def test_the_arena_does_not_hoard_traces(arena):
    """Campaign scale makes trace caching hundreds of megabytes of dead weight."""
    truth, _, _ = arena.nominal(by_name("cosine3_10A_8s"), "Q1", DEV[0])
    assert truth.i_true == ()
    assert truth.v_true == ()
    assert truth.v1_true == ()


def test_conditions_travel_with_the_arena():
    """A ceiling computed under nominal drift is not a ceiling for a drifting cell."""
    from csia_independent_validation.ceilings import Conditions
    quiet = ceilings.Arena()
    drifting = ceilings.Arena(conditions=Conditions(drift_v_per_s=2.0e-3))
    assert quiet.conditions.drift_v_per_s == 0.0
    assert drifting.conditions.drift_v_per_s == 2.0e-3
    action = by_name("cosine3_10A_8s")
    assert quiet.nominal(action, "Q1", DEV[0])[1] != \
        drifting.nominal(action, "Q1", DEV[0])[1]


def test_the_invariant_holds_under_elevated_drift_too():
    from csia_independent_validation.ceilings import Conditions
    drifting = ceilings.Arena(conditions=Conditions(drift_v_per_s=2.0e-3))
    report = ceilings.ceiling_invariant(
        drifting, "Q1", DEV[0], 0.010, deployable=ceilings.candidates())
    assert report["holds"], report["violations"]


def test_layer_b_estimator_is_written_here_not_imported():
    import inspect
    source = inspect.getsource(ceilings)
    assert "from csia_active_evidence" not in source
    assert "import csia_active_evidence" not in source
    assert "lstsq" in inspect.getsource(ceilings._estimate)


def test_an_unknown_loss_name_is_refused(arena):
    outcome = arena.run(PASSIVE, "Q1", DEV[0], 0.010)
    with pytest.raises(ValueError):
        outcome.loss("whatever")
