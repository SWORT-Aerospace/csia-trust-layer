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


# --- the guarantee --------------------------------------------------------

def test_layer_a_cannot_reach_ground_truth():
    assert audit.layer_a_leaks() == {}


def test_layer_a_closure_is_small_enough_to_read():
    """If Layer A's import closure explodes, this guarantee stops meaning much."""
    reachable = audit.transitive_imports(audit.LAYER_A_MODULES)
    packages = {name.split(".")[0] for name in reachable}
    assert packages == {"csia_active_evidence"}


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
