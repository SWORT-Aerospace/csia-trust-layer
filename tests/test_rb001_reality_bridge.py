"""RB-001 (CSIA Reality Bridge 001): permanent tests. OFFBOARD, OBSERVATIONAL.

Findings from real or new data that changed the product are pinned here, so
the 2.3 tests stay exactly as they were. The SITL maneuver study and the RB0
analysis are research code; their outputs are checked for the rules the
programme set (data separation, design before flight, as-run kept apart from
post-hoc).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "research/rb001_reality_bridge"
sys.path.insert(0, str(REPO / "research/csia_2_3_stock_bridge"))
from synthetic_stock import synth  # noqa: E402  (SYNTHETIC logs)


def test_an_estimator_schema_from_another_px4_version_is_a_notice_not_a_crash(monkeypatch):
    """RR-01: real PX4 logs from other versions lack estimator_status fields
    the 547e2ca contract reads. The analysis must go on without that
    producer and say why, not crash."""
    def missing(path):
        raise KeyError("hdg_test_ratio")
    monkeypatch.setattr(runs.PX.EstimatorLog, "from_ulog", staticmethod(missing))
    run = runs.stock_flight("real_old_version.ulg", stock_log=synth("nominal"))
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    notes = m["coverage_report"]["coverage_notices"]
    assert any(n["producer_id"] == "px4:ekf2.estimator_status" and "hdg_test_ratio" in n["why"]
               for n in notes)
    assert m["summary"]["attribution"]["justified"] is False


# ------------------------------------------------------------------ the maneuver study's discipline
def _sha(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_the_frozen_files_match_the_preregistration():
    pre = (PKG / "MANEUVER_PREREGISTRATION.md").read_text()
    for name in ("maneuver.py", "evaluate_maneuver.py", "MANEUVER_CALIBRATION.json"):
        assert _sha(PKG / name) in pre, name


def test_calibration_development_and_evaluation_sets_are_disjoint():
    sys.path.insert(0, str(PKG))
    import calibrate_maneuver as CM
    import evaluate_maneuver as EM
    cal = set(CM.CAL)
    ev = {r for _d, r in EM.SETS["eval"]}
    dev = {r for _d, r in EM.SETS["dev"]}
    assert not (cal & ev) and not (cal & dev) and not (ev & dev)
    calib = json.loads((PKG / "MANEUVER_CALIBRATION.json").read_text())
    assert set(calib["flights"]) == cal and set(calib["model"]["fitted_on"]) == cal


def test_the_designs_were_committed_before_their_flights_were_scored():
    import subprocess

    def first(path):
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "--", path],
                             cwd=REPO, capture_output=True, text=True).stdout.split()
        return int(out[-1]) if out else None
    design = first("research/rb001_reality_bridge/MANEUVER_FLIGHTS_DESIGN.md")
    calib = first("research/rb001_reality_bridge/MANEUVER_CALIBRATION.json")
    prereg = first("research/rb001_reality_bridge/MANEUVER_PREREGISTRATION.md")
    result = first("research/rb001_reality_bridge/MANEUVER_RESULTS_EVAL.json")
    if None in (design, calib, prereg):
        pytest.skip("history not available")
    assert design <= calib <= prereg
    if result is not None:
        assert prereg < result


def test_b1_restores_the_false_symptoms_the_gate_removed():
    """Development reference: loosening the 2.3 steadiness gate brings the
    false COMMAND_NO_RESPONSE back (2.3 V5/V6); the gate is not to be
    loosened (the brief, Part 3)."""
    dev = json.loads((PKG / "MANEUVER_RESULTS_DEV.json").read_text())["score"]
    assert dev["B1"]["false_violated"] > 0
    assert dev["B0"]["false_violated"] == 0 and dev["B0"]["missed"] == ["V13"]


def test_the_hardware_inventory_claims_nothing_it_cannot_verify():
    text = (PKG / "HARDWARE_INVENTORY.md").read_text()
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "|" in ln[2:]]
    available = [r for r in rows if re.search(r"\|\s*AVAILABLE\s*\|", r)]
    assert available == [], "nothing physical was verified in this environment"


def test_rb0_real_logs_are_labelled_and_not_calibrated_on():
    rb0 = json.loads((PKG / "RB0_REAL_LOGS.json").read_text())
    assert "nothing calibrated on it" in rb0["label"]
    real = [v for v in rb0["logs"].values() if v["real_hardware"]]
    assert real and all("error" not in v["product"] for v in rb0["logs"].values())
    calib = (PKG / "MANEUVER_CALIBRATION.json").read_text()
    assert ".ulg" not in json.dumps(json.loads(calib)["flights"]) or all(
        k.startswith("CAL") for k in json.loads(calib)["flights"])


# ------------------------------------------------------------------ the package
DOCS = {"README.md", "REVIEW_AND_DECISION.md", "REALITY_GAP_AUDIT.md", "LITERATURE.md",
        "MANEUVER_FLIGHTS_DESIGN.md", "MANEUVER_PREREGISTRATION.md", "MANEUVER_STUDY.md",
        "HARDWARE_INVENTORY.md", "MINIMUM_PHYSICAL_EXPERIMENT.md", "FALSE_ALARM_BUDGET.md",
        "HARDWARE_EVIDENCE_PLANS.md", "HIL_AND_LANE_SWITCH.md", "RB0_REAL_LOGS.md",
        "LOG_COMPLETENESS.md", "PHYSICAL_EVIDENCE_CASES.md", "REALITY_RECEIPTS.md",
        "TRANSFER_CLASSIFICATION.md", "DECISION_QUALITY.md", "RESEARCH_AND_PRODUCT.md",
        "HOLDS_AND_GATES.md"}
BANNED = ("no prior work exists", "we are the first", "is the first to",
          "first ever", "no one has", "never been studied", "has never been",
          "no prior art exists")
TOKENS = ("RB001_EVIDENCE_SURVIVES_PHYSICAL_CONTACT", "RB001_EVIDENCE_NEEDS_PHYSICAL_REDEFINITION",
          "RB001_EVIDENCE_DOES_NOT_SURVIVE", "RB001_BLOCKED_ON_PHYSICAL_DATA",
          "RB001_SEMANTIC_CORE_DEFECT_STOP", "RB001_GOVERNANCE_BLOCK")


def test_the_rb001_documents_exist_and_keep_the_repositorys_wording_rules():
    assert {p.name for p in PKG.glob("*.md")} == DOCS
    for name in sorted(DOCS):
        text = (PKG / name).read_text(encoding="utf-8").lower()
        assert len(text) > 1500, name
        assert not re.search(r"\bnovel\b", text), name
        for phrase in BANNED:
            assert phrase not in text, (name, phrase)


def test_the_rb001_decision_chooses_one_token_and_keeps_the_authority_boundary():
    text = (PKG / "REVIEW_AND_DECISION.md").read_text(encoding="utf-8")
    chosen = [t for t in TOKENS if f"**`{t}`**" in text]
    assert chosen == ["RB001_BLOCKED_ON_PHYSICAL_DATA"]
    assert "RB001_BLOCKED_ON_PHYSICAL_DATA" in (PKG / "README.md").read_text()
    for doc in ("README.md", "REVIEW_AND_DECISION.md"):
        t = (PKG / doc).read_text(encoding="utf-8").upper()
        assert "OFFBOARD" in t and "ZERO CONTROL" in t and "NO FORGE" in t


def test_as_run_and_post_hoc_are_kept_apart():
    """The brief: AS-RUN DATA, AS-RUN RESULT and POST-HOC ANALYSIS separately.
    The as-run evaluation file is the preregistered script's output and is
    never rewritten; anything computed later is labelled post-hoc."""
    study = (PKG / "MANEUVER_STUDY.md").read_text(encoding="utf-8")
    assert "AS-RUN" in study and "POST-HOC" in study
    res = json.loads((PKG / "MANEUVER_RESULTS_EVAL.json").read_text())
    assert res["calibration_sha256"] == _sha(PKG / "MANEUVER_CALIBRATION.json")
