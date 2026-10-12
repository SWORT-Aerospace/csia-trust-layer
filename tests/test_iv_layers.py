"""Gate A — evaluator independence, enforced structurally.

The previous phase's soundness claim was empty because the thing that issued
certificates and the thing that judged them were the same code (see
``COUNTEREXAMPLE_LOG.md`` IV-1). These tests are the structural answer: Layer A
cannot reach ground truth, and the checker that says so is proven able to fail.

Every guard here has a positive control. A leakage test that has never caught a
leak is not evidence of anything.
"""
from __future__ import annotations

import dataclasses

import pytest

from csia_independent_validation import audit
from csia_independent_validation.plants import Observation


# --- the guarantee --------------------------------------------------------

def test_layer_a_cannot_reach_ground_truth():
    assert audit.layer_a_leaks() == {}


def test_layer_a_closure_is_small_enough_to_read():
    """If Layer A's import closure explodes, this guarantee stops meaning much.

    Two packages only, and from this one exactly the two truth-free modules a
    deployable strategy needs: the action space and the strategies themselves.
    """
    reachable = audit.transitive_imports(audit.LAYER_A_MODULES)
    packages = {name.split(".")[0] for name in reachable}
    assert packages == {"csia_active_evidence", "csia_independent_validation"}
    ours = {name for name in reachable
            if name.startswith("csia_independent_validation")}
    assert ours == {"csia_independent_validation",
                    "csia_independent_validation.actions",
                    "csia_independent_validation.strategies",
                    "csia_independent_validation.actions.ACTION_SPACE",
                    "csia_independent_validation.actions.Action",
                    "csia_independent_validation.actions.PASSIVE",
                    "csia_independent_validation.actions.by_name"}


def test_the_certificate_itself_imports_nothing_from_this_package():
    assert not any(name.startswith("csia_independent_validation")
                   for name in audit.direct_imports("csia_active_evidence.rcec"))


def test_truth_bearing_modules_declare_themselves():
    """Discovered from the source, not from a list somebody maintains."""
    declared = audit.truth_bearing_modules()
    assert "csia_independent_validation.truth" in declared
    assert "csia_independent_validation.evaluator" in declared


# --- positive controls: the checker must be able to fail -----------------

def test_checker_catches_a_module_that_does_import_truth():
    """Layer B imports truth by design. Pointed at it, the guard must fire."""
    leaks = audit.layer_a_leaks(["csia_independent_validation.evaluator"])
    assert leaks, "the leak checker did not fire on a module that imports truth"
    assert "csia_independent_validation.truth" in leaks["forbidden_modules"]


def test_checker_catches_transitive_and_not_only_direct_imports():
    """A leak one hop away is still a leak."""
    leaks = audit.layer_a_leaks(["csia_independent_validation.audit",
                                 "csia_independent_validation.evaluator"])
    assert "csia_independent_validation.truth" in leaks["forbidden_modules"]


def test_relative_imports_are_resolved_not_skipped():
    """``from .truth import GroundTruth`` must be seen as the truth module."""
    found = audit.direct_imports("csia_independent_validation.evaluator")
    assert "csia_independent_validation.truth" in found


def test_checker_is_not_vacuous_on_an_empty_module_list():
    assert audit.layer_a_leaks([]) == {}
    assert audit.transitive_imports([]) == set()


# --- the data schema is a leak path too ----------------------------------

def test_observation_carries_nothing_that_smells_of_truth():
    names = [f.name for f in dataclasses.fields(Observation)]
    assert audit.observation_schema_is_clean(names) == []


def test_observation_fields_are_exactly_what_was_declared():
    """Pinned. Adding a field to the Layer A observation is a design change."""
    names = {f.name for f in dataclasses.fields(Observation)}
    assert names == {"t", "i_meas", "v_meas", "i_command", "valid",
                     "saturated", "dt_nominal"}


@pytest.mark.parametrize("leaked", ["r0_true", "fault_label", "true_delta",
                                    "hidden_state", "oracle_choice",
                                    "gt_resistance", "actual_r0"])
def test_schema_checker_catches_a_planted_field(leaked):
    assert audit.observation_schema_is_clean(["t", "i_meas", leaked]) == [
        leaked]


# --- truth refuses to cross the boundary ---------------------------------

def test_there_is_no_supported_way_to_hand_truth_to_layer_a():
    from csia_independent_validation import truth
    with pytest.raises(PermissionError):
        truth.strip(None)


def test_a_pair_must_share_its_seed_and_its_plant():
    from csia_independent_validation.truth import GroundTruth, TruthPair
    a = GroundTruth(plant="Q1", r0_nominal=0.04, r0_realized=0.04,
                    fault_label="none", seed=1)
    b = GroundTruth(plant="Q1", r0_nominal=0.04, r0_realized=0.05,
                    fault_label="r0_increase", seed=2)
    with pytest.raises(ValueError):
        TruthPair(nominal=a, fault=b)
    c = GroundTruth(plant="Q0", r0_nominal=0.04, r0_realized=0.05,
                    fault_label="r0_increase", seed=1)
    with pytest.raises(ValueError):
        TruthPair(nominal=a, fault=c)
    ok = TruthPair(nominal=a, fault=dataclasses.replace(b, seed=1))
    assert ok.true_delta_r == pytest.approx(0.01)


# --- package initialisers run too ----------------------------------------

def test_the_walk_includes_package_initialisers():
    """Importing a.b.c executes a/__init__.py, which can import anything."""
    assert audit._ancestors("csia_independent_validation.plants") == [
        "csia_independent_validation"]
    assert audit._ancestors("csia_active_evidence") == []
    reachable = audit.transitive_imports(
        ["csia_independent_validation.strategies"])
    assert "csia_independent_validation" in reachable


def test_the_package_initialiser_itself_is_truth_free():
    """If it ever imports plants or truth, every Layer A guarantee dies."""
    assert audit.layer_a_leaks(["csia_independent_validation"]) == {}
