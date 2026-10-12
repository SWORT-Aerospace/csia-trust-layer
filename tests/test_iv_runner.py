"""The campaign runner: the one place Layers A and B both appear.

The separation is kept by sequence, so these tests check the sequence. A
strategy is handed an observable and nothing else; the plant runs; the
certificate reads the observation; the evaluator reads the truth; the row
records both and nothing flows backwards.

The regression that matters most here is conditions. The first version of the
runner held one arena for the whole campaign, so every ceiling was computed
under nominal drift no matter what the cell said.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from csia_independent_validation import partitions as pt, runner
from csia_independent_validation import strategies as st
from csia_independent_validation.plants import SYNTHETIC_SENSING, Sensing

DEV = pt.seeds("development")


@pytest.fixture(scope="module")
def campaign():
    return runner.Campaign()


def cell(**overrides) -> runner.Cell:
    base = dict(plant="Q1", drift_state="nominal", magnitude=0.020,
                seed=DEV[0])
    base.update(overrides)
    return runner.Cell(**base)


# --- the arm list -------------------------------------------------------

def test_every_declared_arm_is_runnable(campaign):
    assert len(runner.ARMS) == 15
    for arm in runner.ARMS:
        row = campaign.row(arm, cell())
        assert row["arm"] == arm


def test_ceilings_are_marked_not_deployable(campaign):
    for arm in ("P7a_benchmark", "P7b_oracle", "P7b_point_oracle",
                "P7c_robust"):
        assert campaign.row(arm, cell())["deployable"] is False
    for arm in st.STRATEGIES:
        assert campaign.row(arm, cell())["deployable"] is True


def test_an_unknown_arm_is_refused(campaign):
    with pytest.raises(KeyError):
        campaign.choose("P99", cell(), runner.observable())


# --- conditions reach the arena -----------------------------------------

def test_conditions_key_the_arena():
    """The regression. One arena per world, not one arena per campaign."""
    campaign = runner.Campaign()
    quiet = campaign.arena(cell(drift_state="nominal"))
    drifting = campaign.arena(cell(drift_state="elevated"))
    assert quiet is not drifting
    assert quiet.conditions.drift_v_per_s == 0.0
    assert drifting.conditions.drift_v_per_s == runner.DRIFT_STATES[
        "elevated"]


def test_the_same_conditions_reuse_one_arena():
    campaign = runner.Campaign()
    first = campaign.arena(cell(plant="Q0", magnitude=0.002))
    second = campaign.arena(cell(plant="Q2", magnitude=0.040))
    assert first is second


def test_ringing_and_sensing_also_key_the_arena():
    campaign = runner.Campaign()
    base = campaign.arena(cell())
    ringing = campaign.arena(cell(ringing_v=0.4))
    noisy = campaign.arena(cell(sensing=replace(
        Sensing(**SYNTHETIC_SENSING), sigma_v=0.2)))
    assert len({id(base), id(ringing), id(noisy)}) == 3
    assert ringing.conditions.ringing_amplitude_v == 0.4


def test_the_oracle_is_computed_under_the_cell_conditions():
    """Under elevated drift the oracle must not be solving the quiet problem."""
    campaign = runner.Campaign()
    quiet = campaign.row("P7b_oracle", cell(drift_state="nominal"))
    drifting = campaign.row("P7b_oracle", cell(drift_state="elevated"))
    assert quiet["m_r_out"] != drifting["m_r_out"]


# --- what a strategy is handed -------------------------------------------

def test_a_strategy_receives_only_an_observable(campaign):
    """Pinned by construction: choose() passes one argument to a strategy."""
    import inspect
    source = inspect.getsource(runner.Campaign.choose)
    assert "st.DEPLOYABLE[arm](state)" in source
    assert "st.SELECTORS[arm](state)" in source
    assert "cell.magnitude" not in source.split("P7b_oracle")[0]


def test_the_observable_never_carries_the_magnitude():
    state = runner.observable()
    assert "magnitude" not in state.to_dict()
    assert "plant" not in state.to_dict()


def test_the_lag_estimate_follows_the_lag_ratio():
    fast = runner.observable(lag_estimate_s=runner.TRUE_LAG_S * 0.5)
    assert fast.lag_estimate_s == pytest.approx(runner.TRUE_LAG_S * 0.5)


# --- abstentions ---------------------------------------------------------

def test_an_abstaining_selector_produces_a_row_with_no_action():
    campaign = runner.Campaign()
    original = st.SELECTORS["S2_threshold"]
    try:
        st.SELECTORS["S2_threshold"] = (
            lambda state: st.NO_SAFE_INFORMATIVE_ACTION)
        row = campaign.row("S2_threshold", cell())
    finally:
        st.SELECTORS["S2_threshold"] = original
    assert row["action"] is None
    assert row["abstention"] == st.NO_SAFE_INFORMATIVE_ACTION
    assert row["energy_as"] == 0.0
    assert row["m_r_out"] is None
    assert row["resolved"] is False
    assert row["state"] is None


# --- execution modification ---------------------------------------------

def test_clipping_invalidates_the_certificate(campaign):
    row = campaign.row("P2_compensated", cell(execution="clipped"))
    assert row["state"] == "CLIPPED_CERTIFICATE_INVALID"


def test_aborting_invalidates_the_certificate(campaign):
    row = campaign.row("P2_compensated", cell(execution="aborted"))
    assert row["state"] == "ABORTED_INCOMPLETE"


def test_a_full_execution_is_not_invalidated(campaign):
    row = campaign.row("P2_compensated", cell(execution="full"))
    assert row["state"] not in ("CLIPPED_CERTIFICATE_INVALID",
                                "ABORTED_INCOMPLETE")


# --- reductions ----------------------------------------------------------

def _rows(pairs):
    return [{"magnitude": magnitude, "resolved": resolved,
             "ae_r": 0.0 if resolved else 1.0, "arm": "X",
             "drift_state": "nominal"}
            for magnitude, resolved in pairs]


def test_resolution_area_is_a_mean_over_the_grid():
    rows = _rows([(0.002, False), (0.010, True), (0.040, True)])
    assert runner.resolution_area(rows) == pytest.approx(2 / 3)


def test_resolution_area_of_an_empty_slice_is_not_a_number():
    import math
    assert math.isnan(runner.resolution_area([]))


def test_frontier_reports_a_bound_when_nothing_resolves():
    rows = _rows([(0.002, False), (0.010, False), (0.040, False)])
    assert runner.frontier(rows) == "> 0.04"


def test_frontier_finds_the_smallest_resolving_magnitude():
    rows = _rows([(0.002, False), (0.010, True), (0.040, True)])
    assert runner.frontier(rows) == 0.010


def test_the_point_metric_uses_a_different_predicate():
    rows = [{"magnitude": 0.010, "resolved": True, "ae_r": 0.009,
             "arm": "X", "drift_state": "nominal"}]
    assert runner.resolution_area(rows, metric="change") == 1.0
    assert runner.resolution_area(rows, metric="point") == 0.0


def test_an_unknown_metric_is_refused():
    with pytest.raises(ValueError):
        runner.resolution_area(_rows([(0.010, True)]), metric="vibes")


def test_slice_rows_matches_on_every_named_condition():
    rows = [{"arm": "A", "plant": "Q0"}, {"arm": "A", "plant": "Q1"},
            {"arm": "B", "plant": "Q0"}]
    assert runner.slice_rows(rows, arm="A") == rows[:2]
    assert runner.slice_rows(rows, arm="A", plant="Q1") == [rows[1]]
    assert runner.slice_rows(rows, arm="Z") == []


# --- the nominal cache ----------------------------------------------------

def test_the_nominal_cache_returns_what_a_fresh_run_would():
    """An optimisation is only allowed if it is provably the same answer."""
    from csia_active_evidence import rcec

    campaign = runner.Campaign()
    action = st.p2_compensated(runner.observable())
    target = cell()
    cached_r, cached_truth = campaign._nominal_summary(action, target)

    fresh_obs, fresh_truth = campaign._run(action, target, magnitude=0.0)
    _, current, voltage = fresh_obs.kept()
    assert cached_r == rcec.estimate_resistance(current, voltage)
    assert cached_truth.r0_nominal == fresh_truth.r0_nominal
    assert cached_truth.r0_realized == fresh_truth.r0_realized
    assert cached_truth.seed == fresh_truth.seed


def test_the_nominal_cache_is_shared_across_magnitudes():
    campaign = runner.Campaign()
    campaign.row("P2_compensated", cell(magnitude=0.002))
    after_first = campaign.plant_runs
    campaign.row("P2_compensated", cell(magnitude=0.040))
    # the second magnitude costs one fault run, not two
    assert campaign.plant_runs - after_first == 1


def test_the_nominal_cache_is_not_shared_across_conditions():
    campaign = runner.Campaign()
    quiet, _ = campaign._nominal_summary(
        st.p2_compensated(runner.observable()), cell(drift_state="nominal"))
    drifting, _ = campaign._nominal_summary(
        st.p2_compensated(runner.observable()), cell(drift_state="elevated"))
    assert quiet != drifting


def test_the_cache_stores_no_traces():
    campaign = runner.Campaign()
    _, truth = campaign._nominal_summary(
        st.p2_compensated(runner.observable()), cell())
    assert truth.i_true == () and truth.v_true == () and truth.v1_true == ()


def test_the_point_oracle_optimises_a_different_loss_from_the_change_oracle():
    """Amendment 2's arm. Same search, same space, different objective."""
    campaign = runner.Campaign()
    target = cell(magnitude=0.006)
    change = campaign.row("P7b_oracle", target)
    point = campaign.row("P7b_point_oracle", target)
    assert change["action"] != point["action"]
    assert point["ae_r"] <= change["ae_r"] + 1e-12
    assert abs(change["e_delta_r"]) <= abs(point["e_delta_r"]) + 1e-12
