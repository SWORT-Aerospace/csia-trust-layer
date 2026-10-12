"""Phase 3B gate: five-arm architecture selection.

Section 37's required proofs. The two that matter most:

  * right censoring is PRESERVED -- a no-response must never appear as a
    latency equal to the window end;
  * no unsupported sequential coverage is invented -- an arm may not claim to
    cover a mechanism for which no residual exists.
"""

from __future__ import annotations

import csv
import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")

ARMS = ("T0_TRUST_FLAT", "T1_TRUST_GRAPH", "T2_SEQUENTIAL_ONLY",
        "T3_TRUST_FLAT_PLUS_SEQ", "T4_TRUST_GRAPH_PLUS_SEQ")


def _summary():
    p = os.path.join(ENG, "PHASE3B_SUMMARY.json")
    if not os.path.exists(p):
        pytest.skip("Phase 3B artifacts not built")
    return json.load(open(p, encoding="utf-8"))


def _rows():
    p = os.path.join(ENG, "PHASE3B_ARCHITECTURE_RESULTS.csv")
    if not os.path.exists(p):
        pytest.skip("Phase 3B results not built")
    return list(csv.DictReader(open(p, encoding="utf-8")))


def _cov():
    p = os.path.join(ENG, "MECHANISM_COVERAGE_MATRIX.csv")
    return list(csv.DictReader(open(p, encoding="utf-8")))


# ------------------------------------------------------- inherited integrity
def test_the_frozen_core_is_still_untouched():
    import subprocess
    r = subprocess.run(["git", "diff", "--stat", "csia-v1.0-research-final",
                        "--", "csia/trust_engine", "csia/diagnosis",
                        "csia/runtime/online.py", "csia/runtime/failsafe.py",
                        "csia/scenarios.py", "csia/profiles.py"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("frozen tag unavailable")
    assert r.stdout.strip() == "", r.stdout


# ------------------------------------------------------------ section 4
def test_all_arms_share_the_three_matching_hashes():
    """If arms disagreed on any input hash the comparison is INVALID."""
    for mech in {r["mechanism"] for r in _rows()}:
        rs = [r for r in _rows() if r["mechanism"] == mech]
        assert len(rs) == len(ARMS), mech
        for col in ("raw_trace_sha256", "canonical_input_sha256",
                    "relation_bank_sha256"):
            assert len({r[col] for r in rs}) == 1, (mech, col)


def test_every_arm_appears_for_every_applicable_mechanism():
    applicable = {r["mechanism"] for r in _cov()
                  if r["status"] == "APPLICABLE"}
    seen = {(r["mechanism"], r["arm"]) for r in _rows()}
    for m in applicable:
        for a in ARMS:
            assert (m, a) in seen, (m, a)


# ------------------------------------------------------------ section 8
def test_right_censoring_is_preserved():
    """A no-response must be censored, never a number. If any censored row
    carried a latency equal to a window end, this fails."""
    for r in _rows():
        if r["detection_censored"] == "True":
            assert r["detection_response_s"] in ("", "None"), r
        else:
            assert float(r["detection_response_s"]) > 0, r


def test_a_censored_pair_produces_no_paired_delta():
    p = os.path.join(ENG, "PHASE3B_PAIRED_DIFFERENCES.csv")
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["delta_s"] == "":
            assert r["note"], r
        else:
            float(r["delta_s"])          # must parse


# ------------------------------------------------------------ section 5/12
def test_no_unsupported_sequential_coverage_is_invented():
    """T2 must report NO_SEQUENTIAL_COVERAGE where no residual exists, and
    must not claim a response there."""
    s = _summary()
    for mech, d in s["per_mechanism"].items():
        if d["sequential_covered"]:
            continue
        row = next(r for r in _rows()
                   if r["mechanism"] == mech and r["arm"] == "T2_SEQUENTIAL_ONLY")
        assert row["coverage"] == "NO_SEQUENTIAL_COVERAGE", (mech, row)
        assert row["detection_censored"] == "True", mech


def test_the_imu_mechanisms_have_no_sequential_coverage():
    """Section 12: this is what stops a misleading 'sequential wins'."""
    s = _summary()["per_mechanism"]
    for mech in ("IMU0_BIAS_DRIFT", "DUAL_IMU_FAILURE"):
        assert s[mech]["sequential_covered"] is False, mech
        assert s[mech]["sequential_nodes_alarming"] == [], mech


def test_trust_uniquely_covers_fix_loss_and_dual_imu():
    """The reason trust is retained. If this stops holding, the architecture
    decision must be revisited, not the test relaxed."""
    s = _summary()["per_mechanism"]
    for mech in ("GNSS_FIX_LOSS", "DUAL_IMU_FAILURE"):
        d = s[mech]
        assert d["detection_by_arm"]["T0_TRUST_FLAT"] not in (None, "None")
        assert d["sequential_covered"] is False


# ------------------------------------------------------------ section 9
def test_the_clean_control_has_no_sequential_alarm():
    d = json.load(open(os.path.join(ENG, "PHASE3B_CLEAN_RESULTS.json"),
                       encoding="utf-8"))
    assert d["sequential_alarms_on_clean"] == 0
    for r in _rows():
        if r["mechanism"] == "CLEAN":
            assert r["detection_censored"] == "True", r


def test_no_arm_introduces_a_hidden_clean_transition():
    for r in _rows():
        if r["mechanism"] == "CLEAN":
            assert r["wrong_unique"] == "0", r


# ----------------------------------------------------------- section 11 / 23
def test_a_sequential_alarm_never_promotes_an_unidentifiable_cause():
    """Section 11. On fix loss the leader must stay ambiguous in EVERY arm,
    including the ones carrying a sequential channel."""
    rs = [r for r in _rows() if r["mechanism"] == "GNSS_FIX_LOSS"]
    assert rs
    for r in rs:
        assert int(r["safe_ambiguity"]) > 100, r
        assert int(r["correct_unique"]) == 0, r


def test_support_metadata_is_identical_across_arms():
    """Section 23: every architecture exposes the same diagnosis structure."""
    for mech in {r["mechanism"] for r in _rows()}:
        rs = [r for r in _rows() if r["mechanism"] == mech]
        for col in ("correct_unique", "safe_ambiguity", "wrong_unique",
                    "unsupported_unique", "unavailable"):
            assert len({r[col] for r in rs}) == 1, (mech, col)


# ------------------------------------------------------------ section 23/24
def test_unknown_remains_unimplemented():
    t = open(os.path.join(ENG, "UNKNOWN_MODEL_ADEQUACY_AUDIT.md"),
             encoding="utf-8").read()
    assert "NOT IMPLEMENTED — MODEL ADEQUACY TEST REQUIRED" in t


# ------------------------------------------------------------ the CUSUM
def test_the_cusum_constants_are_exact_and_reproduced():
    d = json.load(open(os.path.join(ENG,
                                    "SEQUENTIAL_SELECTION_REPRODUCTION.json"),
                       encoding="utf-8"))
    assert d["k"] == 0.5
    assert d["h"] == 500.0
    assert d["smallest_h_with_zero_clean_alarms"] == 500.0
    assert d["historical_h_reproduced"] is True
    assert d["grid_clean_alarm_ticks"]["500.0"] == 0
    assert d["textbook_h_negative_result"]["h"] == 5.0
    assert d["textbook_h_negative_result"]["clean_alarm_ticks_v1_1"] > 0


# ------------------------------------------------------------ the decision
def test_the_architecture_decision_is_exactly_one_of_the_options():
    t = open(os.path.join(ENG, "ARCHITECTURE_DECISION.md"),
             encoding="utf-8").read()
    assert "E:  TRUST_FLAT_PLUS_SEQUENTIAL" in t
    assert "Neighbour-trust propagation: REMOVE" in t
    assert "Trust recursion: KEEP" in t
    assert "Sequential (CUSUM) channels: KEEP" in t
    # and it must not read as "delete the relation bank"
    assert "Relation topology and all 11 relations: KEEP" in t


def test_the_simplification_plan_names_the_exact_line():
    t = open(os.path.join(ENG, "GRAPH_SIMPLIFICATION_PLAN.md"),
             encoding="utf-8").read()
    assert "csia/trust_engine/engine.py" in t
    assert "line:  110" in t
    assert "w = float(gate_e)" in t
    assert "Nothing in this plan has been executed" in t


def test_no_imu_sequential_residual_was_added():
    """Section 28 forbids it in this phase."""
    assert not os.path.exists(os.path.join(ENG, "ablation", "imu_cusum.py"))
    t = open(os.path.join(ENG, "PHASE3C_FEASIBILITY_NOTE.md"),
             encoding="utf-8").read()
    assert "Nothing is implemented here" in t
    assert "OPEN_ENGINEERING_QUESTION" in t


def test_no_novelty_language_in_phase_3b_documents():
    import re
    banned = (r"\bnovel\b", r"\bnovelty\b", r"\bbreakthrough\b",
              r"\bnew theorem\b", r"\bfirst-ever\b")
    denials = ("no ", "not ", "never", "none", "cannot", "warranted",
               "is not a", "prior art")
    for fn in ("ARCHITECTURE_DECISION.md", "DETECTOR_COVERAGE_MAP.md",
               "PHASE3C_FEASIBILITY_NOTE.md",
               "FUNCTION_ELIGIBILITY_INPUT_REQUIREMENTS.md"):
        lines = open(os.path.join(ENG, fn),
                     encoding="utf-8").read().lower().splitlines()
        for i, line in enumerate(lines):
            for w in banned:
                if not re.search(w, line):
                    continue
                window = " ".join(lines[max(0, i - 1):i + 2])
                assert any(k in window for k in denials), (fn, w, line[:120])
