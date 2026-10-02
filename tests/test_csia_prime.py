"""CSIA PRIME (Commercial Reality & Differentiation): permanent tests. OFFBOARD.

Findings that changed or constrain the product are pinned here, so the 2.2,
pilot, 2.3 and RB-001 tests stay exactly as they were.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "research/csia_prime"
sys.path.insert(0, str(REPO / "research/csia_2_3_stock_bridge"))
from synthetic_stock import synth  # noqa: E402  (SYNTHETIC logs)


def _symptoms(log):
    run = runs.stock_flight(stock_log=log, est_log=None)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    return sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]}), m


def _shifted(shift_s):
    log = synth("motor")
    for d in log.topics.values():
        d["t"] = d["t"] + shift_s
    return log


# ------------------------------------------------------------------ D-PRIME-1
def test_a_whole_microsecond_shift_does_not_change_the_conclusion():
    """ULog timestamps are whole microseconds: the product's real-log path."""
    assert _symptoms(_shifted(0.0))[0] == ["COMMAND_NO_RESPONSE|motor_0"]
    assert _symptoms(_shifted(1e-6))[0] == ["COMMAND_NO_RESPONSE|motor_0"]
    assert _symptoms(_shifted(3e-6))[0] == ["COMMAND_NO_RESPONSE|motor_0"]


@pytest.mark.xfail(strict=True, reason="D-PRIME-1 (DEFECT_D_PRIME_1.md): content times are rounded "
                   "to the microsecond, the window anchor is not; a sub-microsecond shift makes the "
                   "2.2 gate reject valid evidence. Reported, not patched (stop condition 2).")
def test_a_sub_microsecond_shift_does_not_change_the_conclusion():
    syms, m = _symptoms(_shifted(0.7e-6))
    assert syms == ["COMMAND_NO_RESPONSE|motor_0"]
    assert m["final"]["evidence"]["rejected"] == []


# ------------------------------------------------------------------ B4 frozen decision rule (SYNTHETIC rows)
def _row(rid, cond, level, L, syms, tel, phys, cause, unique=None, lines=2, esc_lines=1):
    return {"run_id": rid, "condition": cond, "level": level, "L_median": L,
            "symptoms_any_time": syms, "telemetry_state": tel, "physical_state": phys,
            "ground_truth_cause": cause, "unique": unique, "independent_lines": lines,
            "esc_rpm_current_lines": esc_lines}


def test_the_ab_decision_rule_separates_classes_and_flags_every_error():
    sys.path.insert(0, str(PKG))
    import ab_scoring as AB
    good = [_row("a1", "A", 0.6, 0.40, ["COMMAND_NO_RESPONSE|motor_0"], "DEGRADED", "VIOLATED", "drive"),
            _row("b1", "B-phys", 0.6, 0.41, [], "DEGRADED", "NOMINAL", "telemetry")]
    v = AB.score(good)
    assert v["verdict"] == "PASS" and [r["class"] for r in v["rows"]] == ["A_CONFIRMED", "TELEMETRY_ONLY"]
    bad = good + [_row("b2", "B-phys", 0.6, 0.39, ["COMMAND_NO_RESPONSE|motor_0"], "DEGRADED", "VIOLATED",
                       "telemetry")]
    v = AB.score(bad)
    assert v["errors"]["B_AS_A"] == ["b2"] and v["stop_condition"] and v["verdict"] == "FAIL"
    lineage = [dict(r, esc_rpm_current_lines=2) for r in good]
    assert AB.score(lineage)["criteria"]["S4_lineage"] is False


def test_the_frozen_protocol_names_its_scoring_script_and_holds():
    text = (PKG / "B4_MATCHED_AB_PROTOCOL.md").read_text()
    assert "ab_scoring.py" in text and "FROZEN BEFORE ANY HARDWARE EXISTS" in text
    contract = json.loads((PKG / "contracts_draft/bench_loadcell_thrust_response.json").read_text())
    assert contract["DRAFT"] and "sensor:loadcell.<n>" in contract["lineage_rule"]
    # the draft is not in the product's contract directory: nothing loads it yet
    assert not (REPO / "csia_evidence_assurance/contracts/bench_loadcell_thrust_response.json").exists()
