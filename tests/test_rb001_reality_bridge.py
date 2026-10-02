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
