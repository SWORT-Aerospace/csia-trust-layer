"""The paired-design fix: an independent baseline window.

`PREREGISTRATION_AMENDMENT_4.md`. The completed phase's change metric saturated
because the nominal and fault windows shared a seed, which made
``V_fault - V_nominal = -dR.I_true`` exact and cancelled every plant-common
nuisance. These tests pin the three baseline sources, prove the cancellation is
actually broken, and check that the guard which used to forbid this still
forbids the accidental version of it.
"""
from __future__ import annotations

import pytest

from csia_independent_validation import followup_partitions as fp
from csia_independent_validation import runner
from csia_independent_validation.truth import GroundTruth, TruthPair

DEV = fp.seeds("development")


def cell(**overrides) -> runner.Cell:
    base = dict(plant="Q1", drift_state="nominal", magnitude=0.010,
                seed=DEV[0])
    base.update(overrides)
    return runner.Cell(**base)


# --- the partitions -------------------------------------------------------

def test_the_followup_manifest_is_pinned():
    assert fp.manifest_hash() == (
        "b6af853781b62631dde39c5b0c83a623a3c3c458d7936d10ac2ccb8218702515")


def test_no_followup_seed_is_a_phase_one_seed():
    fp.assert_disjoint_from_phase_one()


def test_no_companion_collides_with_a_campaign_seed():
    fp.assert_companions_are_not_fault_seeds()


def test_companions_are_derived_not_offset():
    """`seed + 1` is a choice somebody could have made differently."""
    seeds = fp.seeds("development")
    companions = [fp.companion(s) for s in seeds]
    offsets = {c - s for s, c in zip(seeds, companions)}
    assert len(offsets) == len(seeds), "companions look like a fixed offset"


def test_the_followup_final_partition_is_sealed():
    with pytest.raises(PermissionError):
        fp.seeds("final")


# --- the three baseline sources ------------------------------------------

def test_paired_crn_uses_the_same_action_and_seed():
    campaign = runner.Campaign()
    target = cell(nominal_source="paired_crn")
    action = runner.st.p2_compensated(runner.observable())
    baseline_action, baseline_seed = campaign._baseline(action, target)
    assert baseline_action == action
    assert baseline_seed == target.seed


def test_independent_seed_keeps_the_action_and_moves_the_seed():
    campaign = runner.Campaign()
    target = cell(nominal_source="independent_seed")
    action = runner.st.p2_compensated(runner.observable())
    baseline_action, baseline_seed = campaign._baseline(action, target)
    assert baseline_action == action
    assert baseline_seed == fp.companion(target.seed)
    assert baseline_seed != target.seed


def test_independent_window_moves_the_action_too():
    campaign = runner.Campaign()
    target = cell(nominal_source="independent_window")
    action = runner.st.p2_compensated(runner.observable())
    baseline_action, baseline_seed = campaign._baseline(action, target)
    assert baseline_action.name == runner.REFERENCE_ACTION
    assert baseline_seed == fp.companion(target.seed)


def test_an_unknown_nominal_source_is_refused():
    with pytest.raises(ValueError):
        runner.Cell(plant="Q1", drift_state="nominal", magnitude=0.010,
                    seed=1, nominal_source="whatever")


# --- the cancellation is actually broken ---------------------------------

def test_the_paired_design_cancellation_is_broken_by_an_independent_window():
    """The whole point of the amendment, measured.

    Under the paired design the change error is the finite-sample EIV term and
    nothing else. Once the baseline comes from a different window it carries
    the baseline's own estimation error too, which is orders of magnitude
    larger.
    """
    campaign = runner.Campaign()
    errors = {}
    for source in runner.NOMINAL_SOURCES:
        row = campaign.row("P2_compensated", cell(nominal_source=source))
        errors[source] = abs(row["e_delta_r"])
    assert errors["independent_seed"] > 10 * errors["paired_crn"]
    assert errors["independent_window"] > 10 * errors["paired_crn"]


def test_the_point_error_is_untouched_by_the_baseline_choice():
    """`AE_R` scores the fault window alone, so it must not move."""
    campaign = runner.Campaign()
    values = {source: campaign.row("P2_compensated",
                                   cell(nominal_source=source))["ae_r"]
              for source in runner.NOMINAL_SOURCES}
    assert len(set(values.values())) == 1


def test_every_source_is_reachable_for_every_arm():
    campaign = runner.Campaign()
    for source in runner.NOMINAL_SOURCES:
        for arm in ("P0_passive", "P2_compensated", "S2_threshold"):
            row = campaign.row(arm, cell(nominal_source=source))
            assert row["nominal_source"] == source


def test_rows_record_which_window_the_baseline_came_from():
    campaign = runner.Campaign()
    row = campaign.row("P2_compensated",
                       cell(nominal_source="independent_window"))
    assert row["baseline_action"] == runner.REFERENCE_ACTION
    assert row["baseline_seed"] == fp.companion(row["seed"])


# --- the guard that used to forbid this still forbids the accident -------

def _truth(seed, plant="Q1", realized=0.040):
    return GroundTruth(plant=plant, r0_nominal=0.040, r0_realized=realized,
                       fault_label="none", seed=seed)


def test_a_mismatched_pair_is_still_refused_by_default():
    with pytest.raises(ValueError):
        TruthPair(nominal=_truth(1), fault=_truth(2, realized=0.050))


def test_independence_must_be_spelled_out_to_be_allowed():
    pair = TruthPair(nominal=_truth(1), fault=_truth(2, realized=0.050),
                     independent_windows=True)
    assert pair.true_delta_r == pytest.approx(0.010)


def test_the_plant_guard_survives_independence():
    """Different windows, yes. Different plants, never."""
    with pytest.raises(ValueError):
        TruthPair(nominal=_truth(1, plant="Q0"),
                  fault=_truth(2, plant="Q1", realized=0.050),
                  independent_windows=True)
