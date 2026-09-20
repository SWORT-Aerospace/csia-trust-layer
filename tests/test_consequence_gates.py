"""Gate inventory, its independent evaluator, and the seed partitions.

Phase 2 of the consequence/support/cross-architecture preregistration. Every
assertion here is at evidence level SOURCE_ANALYSIS: it is about what the
source says the gates do, not about what happens at runtime.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "consequence"))

from csia_consequence import gates, partitions          # noqa: E402


# --- partitions -----------------------------------------------------------

def test_the_partition_manifest_is_pinned():
    assert partitions.manifest_hash() == (
        "36c707f2061d7bc044f39abd723be4ecf01ee3ccaccd54626d755e492e3e562b")


def test_the_locked_partition_refuses_casual_access():
    with pytest.raises(PermissionError, match="locked"):
        partitions.seeds("locked")
    assert len(partitions.seeds(
        "locked", i_am_opening_the_locked_partition=True)) == 32


def test_no_seed_is_reused_from_an_earlier_phase():
    partitions.assert_disjoint()
    partitions.assert_disjoint_from_earlier_phases()


# --- the inventory is anchored to real source -----------------------------

def test_every_recorded_gate_expression_still_occurs_in_the_source():
    """The inventory is hand-read. This is what stops it drifting from the
    code it describes without the suite noticing."""
    missing = [k for k, ok in gates.source_expressions_present().items()
               if not ok]
    assert missing == [], missing


def test_the_inventory_declares_its_evidence_level():
    assert gates.inventory()["evidence_level"] == "SOURCE_ANALYSIS"


def test_both_uncovered_counts_are_reported():
    """Eight with the withdrawal path counted, seven without. Reporting one
    number would hide a classification judgement."""
    inv = gates.inventory()
    assert inv["uncovered_candidate_count"] == 8
    assert inv["uncovered_candidate_count_excluding_withdrawal"] == 7
    assert "withdrawal" in inv["count_note"].lower()


def test_a_freshness_coupled_gate_is_not_an_uncovered_candidate():
    """altitude_baro closes exactly when GPS validity drops, which the
    freshness path already watches."""
    baro = next(g for g in gates.GATES if g.gate_id == "altitude_baro")
    assert baro.coupling == gates.FRESHNESS_COUPLED
    assert baro.uncovered_candidate is False


def test_the_cross_sensor_case_is_recorded_as_uncovered():
    """phys_vibration is gated by ANOTHER sensor's freshness, so the
    vibration channel's own freshness signal stays green while its check is
    switched off."""
    vib = next(g for g in gates.GATES if g.gate_id == "phys_vibration")
    assert vib.uncovered_candidate is True
    assert "CROSS-SENSOR" in vib.note


def test_the_judgement_about_the_withdrawal_path_is_recorded():
    """A classification call that changes the headline count must be
    arguable by a reader, not buried."""
    w = next(g for g in gates.GATES if g.gate_id == "hist_vr_withdrawal")
    assert w.kind == "withdrawal"
    assert "JUDGEMENT" in w.note
    assert "seven" in w.note and "eight" in w.note


def test_a_bad_coupling_label_is_refused():
    with pytest.raises(ValueError, match="bad coupling"):
        gates.Gate("x", "edge", "y", "z", "o", "c", True, True, False,
                   "PROBABLY_FINE")


# --- the independent evaluator -------------------------------------------

def _evaluator():
    import independent_gate_evaluator as ige
    return ige


def test_the_evaluator_parses_every_term_it_finds():
    report = _evaluator().evaluate()
    unparsed = [k for k, v in report["verdicts"].items() if v == "UNPARSED"]
    assert unparsed == [], unparsed
    assert report["terms_found"] >= 15


def test_the_evaluator_reaches_the_same_uncovered_set_as_the_inventory():
    """Two independent derivations -- one hand-read, one parsed from source.

    They disagreed on the first run: the evaluator mis-parsed four terms and
    missed every P[...] term because their commas sit inside a wrapping
    paren. Those were PARSE DEFECTS in the evaluator and were fixed as such.
    The fixes were made after seeing the disagreement, which a reader should
    weigh: they are justifiable on their own (a term that does not parse is a
    bug in the parser), but the sequence is recorded rather than hidden.
    """
    report = _evaluator().evaluate()
    evaluator_set = set(report["freshness_independent"])
    inventory_set = {g.gate_id for g in gates.uncovered_candidates()
                     if g.kind != "withdrawal"}
    assert evaluator_set == inventory_set, (
        f"only in evaluator: {evaluator_set - inventory_set}; "
        f"only in inventory: {inventory_set - evaluator_set}")
    assert report["count_with_withdrawal"] == 8


def test_the_evaluator_states_its_limits():
    report = _evaluator().evaluate()
    limits = " ".join(report["known_limitations"]).lower()
    assert "loop variable" in limits
    assert "velocity_gps_doppler" in limits


def test_the_evaluator_imports_no_csia_module():
    """Independence asserted mechanically, in a fresh interpreter. If it
    agreed with the inventory because it imported the inventory, the
    agreement would prove nothing."""
    code = (
        "import sys, pathlib; "
        f"sys.path.insert(0, {str(ROOT / 'research' / 'consequence')!r}); "
        "import independent_gate_evaluator as ige; ige.evaluate(); "
        "bad=[m for m in sys.modules if m.startswith(('csia','csia_'))]; "
        "print(bad)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


def test_the_evaluator_output_is_deterministic():
    a = json.dumps(_evaluator().evaluate(), sort_keys=True)
    b = json.dumps(_evaluator().evaluate(), sort_keys=True)
    assert a == b


# --- claim discipline -----------------------------------------------------

def test_the_inventory_refuses_to_claim_runtime_evidence():
    note = gates.inventory()["what_this_is_not"].lower()
    assert "not a runtime measurement" in note


def test_no_hardware_or_flight_claim_appears_in_the_phase_sources():
    for path in (ROOT / "csia_consequence/gates.py",
                 ROOT / "csia_consequence/partitions.py",
                 ROOT / "research/consequence/independent_gate_evaluator.py"):
        text = path.read_text().lower()
        for banned in ("flight validated", "hardware validated",
                       "certified", "airworthy", "novel contribution"):
            assert banned not in text, f"{path.name} contains {banned!r}"
