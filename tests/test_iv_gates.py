"""The two-gate contract, including the half of it that cannot fail.

The safety sub-gate is vacuous over this action space. That is measured here
rather than discovered by a reader, because a check that cannot fail is exactly
what IV-1 was about, and a phase that found that defect once should not ship it
twice without saying so.
"""
from __future__ import annotations

import math

import pytest

from csia_independent_validation import gates
from csia_independent_validation.actions import ACTION_SPACE, Action, by_name


# --- the safety sub-gate --------------------------------------------------

def test_no_admissible_action_can_fail_the_safety_sub_gate():
    """Vacuous, measured, and reported. 34 A worst case against a 56 A limit."""
    failing = [a.name for a in ACTION_SPACE if not gates.predicted_safe(a)[0]]
    assert failing == []


def test_the_worst_admissible_action_has_ample_headroom():
    worst = max(gates.predicted_safe(a)[1] for a in ACTION_SPACE)
    assert worst == pytest.approx(34.0)
    assert worst < 60.0 - gates.CLIP_MARGIN_A


def test_the_safety_check_itself_works():
    """Positive control. The check is vacuous here, not broken."""
    huge = Action(name="huge", shape_name="hold", amplitude_a=45.0,
                  duration_s=4.0)
    safe, peak = gates.predicted_safe(huge)
    assert not safe
    assert peak == pytest.approx(65.0)


def test_the_module_says_the_sub_gate_is_vacuous():
    """If somebody removes the caveat, this fails."""
    import pathlib
    source = pathlib.Path(gates.__file__).read_text()
    assert "VACUOUS OVER THIS ACTION SPACE" in source
    assert "admissible action can fail the safety check" in source


# --- the separation sub-gate ---------------------------------------------

def test_a_small_fault_does_not_separate_and_the_gate_says_so():
    result = gates.pre_gate("cosine3_10A_8s", 0.002, plant="Q1", seed=5)
    assert result.safe
    assert not result.separates
    assert not result.passes
    assert result.separation_margin_v < 0


def test_a_larger_fault_separates_and_the_gate_passes():
    result = gates.pre_gate("cosine3_10A_8s", 0.010, plant="Q1", seed=5)
    assert result.safe and result.separates and result.passes
    assert result.separation_margin_v > 0
    assert result.overlap_volume_v == 0.0


def test_an_abstention_fails_the_gate_without_inventing_a_reason():
    result = gates.pre_gate(None, 0.010)
    assert not result.passes
    assert not result.safe and not result.separates
    assert math.isnan(result.separation_margin_v)


def test_the_gate_reads_no_truth():
    """Same action and magnitude, different plant, same declared envelope."""
    import inspect
    signature = inspect.signature(gates.pre_gate)
    assert "truth" not in signature.parameters
    assert "r0_true" not in signature.parameters
    assert "fault" not in signature.parameters


# --- the post gate --------------------------------------------------------

def test_only_a_certificate_passes_the_post_gate():
    assert gates.post_gate("CERTIFIED_IN_MODEL")
    for state in ("MODEL_MISMATCH_LIMITED", "INSUFFICIENT_EXCITATION",
                  "DRIFT_COUPLED", "UNKNOWN_OR_MODEL_MISMATCH",
                  "CLIPPED_CERTIFICATE_INVALID", "ABORTED_INCOMPLETE",
                  "INVALID_INSTRUMENT", None):
        assert not gates.post_gate(state)


# --- the policies ---------------------------------------------------------

@pytest.mark.parametrize("policy,pre,post,expected", [
    ("accept_always", False, False, True),
    ("accept_if_pre", True, False, True),
    ("accept_if_pre", False, True, False),
    ("accept_if_post", False, True, True),
    ("accept_if_post", True, False, False),
    ("accept_if_both", True, True, True),
    ("accept_if_both", True, False, False),
    ("accept_if_both", False, True, False),
])
def test_each_policy_accepts_what_it_says_it_does(policy, pre, post, expected):
    assert gates.accepted(policy, pre, post) is expected


def test_an_unknown_policy_is_refused():
    with pytest.raises(ValueError):
        gates.accepted("accept_if_vibes", True, True)


# --- the table ------------------------------------------------------------

def _row(pre, post, resolved, energy=40.0, duration=8.0):
    return {"pre_pass": pre, "post_pass": post, "resolved_point": resolved,
            "energy_as": energy, "duration_s": duration}


def test_the_table_counts_every_cell():
    rows = [_row(True, True, True), _row(True, False, False),
            _row(False, True, False), _row(False, False, False)]
    table = gates.gate_table(rows)
    assert table["n_rows"] == 4
    assert all(cell["n"] == 1 for cell in table["cells"].values())


def test_requiring_both_gates_can_remove_a_false_acceptance():
    rows = [_row(True, True, True), _row(True, False, False),
            _row(False, True, False)]
    table = gates.gate_table(rows)
    assert table["policies"]["accept_if_pre"]["false_accepted"] == 1
    assert table["policies"]["accept_if_post"]["false_accepted"] == 1
    assert table["policies"]["accept_if_both"]["false_accepted"] == 0
    assert table["verdict"]["combined_beats_pre_alone"]
    assert table["verdict"]["combined_beats_post_alone"]


def test_a_redundant_post_gate_is_named_as_redundant():
    """The negative result the amendment names in advance."""
    rows = [_row(True, True, True), _row(False, False, False)]
    table = gates.gate_table(rows)
    assert table["verdict"]["post_gate_redundant"]
    assert table["verdict"]["pre_gate_redundant"]


def test_coverage_cost_is_reported_not_hidden():
    rows = [_row(True, True, True), _row(True, False, True)]
    table = gates.gate_table(rows)
    assert table["policies"]["accept_if_pre"]["coverage"] == 1.0
    assert table["policies"]["accept_if_both"]["coverage"] == 0.5
    assert table["verdict"]["coverage_cost_against_pre_alone"] == \
        pytest.approx(0.5)


def test_an_unscoreable_row_counts_as_wrong():
    rows = [_row(True, True, False)]
    table = gates.gate_table(rows)
    assert table["policies"]["accept_if_both"]["false_accepted"] == 1
    assert "nobody can score" in table["note"]


def test_an_empty_table_invents_nothing():
    table = gates.gate_table([])
    assert table["n_rows"] == 0
    for summary in table["policies"].values():
        assert summary["coverage"] is None
        assert summary["false_accept_rate"] is None
