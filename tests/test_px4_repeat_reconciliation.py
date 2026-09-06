"""Behavioural oracles for PX4_REPEAT_RECONCILIATION.md.

The PX4 campaign's value is that it replicates two ArduPilot findings from an
independent campaign on a structurally different platform. These tests pin
that, plus the one finding PX4 has and ArduPilot does not.

  1. the preregistered qualification -- gate 1.0, NOT 3.0 -- holds in 40/40.
     If a later change makes it 3.0, PX4 is no longer running the passive-link
     configuration the original ran, and the repeat stops being a repeat;

  2. both ArduPilot findings replicate: the control arm rises more, and the
     original delta is outside the repeated range;

  3. the watchdog replay reproduces BOTH measured PX4 values from ONE log --
     the controlled experiment that attributes the pre-fault difference -- and
     is pinned as NOT reproducing ArduPilot's, so it cannot quietly be used to
     draw an ArduPilot conclusion later (FL-019).

The replay is slow (it drives the frozen core over a whole flight), so test 3
uses one log per direction rather than the campaign.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.online import STALE_TIMEOUT_S                    # noqa: E402
from csia.v1_1.staleness import build_runtime_stale_timeouts       # noqa: E402

DOC = os.path.join(ROOT, "research", "physical_validation",
                   "PX4_REPEAT_RECONCILIATION.md")
RESULTS = os.path.join(ROOT, "research", "physical_validation", "results",
                       "mechanism_a_p1_trust_px4.json")
TABLE = os.path.join(ROOT, "research", "physical_validation", "results",
                     "PX4_MECHANISM_A_REPEAT_TABLE.csv")
ORIGINAL_ARTIFACT = os.path.join(ROOT, "research", "v1_1", "results",
                                 "mechanism_a_px4.json")
ORIGINAL_FAULT_LOG = os.path.join(
    ROOT, "logs", "shadow-sitl-px4",
    "20260825T005931Z-1b4add14.part000.jsonl")


def _skip_without(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.relpath(path, ROOT)} not present")


def _rows():
    _skip_without(TABLE)
    with open(TABLE, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- 1. the preregistered qualification ------------------------------------

def test_the_gate_is_one_not_three_which_is_the_qualification_retained():
    """PX4 preregistration section 4, measured 40/40 instead of argued once.

    "gps_gate_weight_sum on the control arm is expected to be 1.0, not 3.0."
    A later 3.0 would mean the link configuration changed, and a repeat of a
    different configuration is not a repeat.
    """
    rows = _rows()
    assert len(rows) == 40
    assert {r["gate_pre"] for r in rows} == {"1.0"}, (
        "pre-fault gate weight is no longer 1.0 on every trial; the passive "
        "link configuration the original ran has changed")
    assert {r["gate_post"] for r in rows if r["role"] == "FAULT"} == {"0.0"}
    assert {r["gate_post"] for r in rows if r["role"] == "CONTROL"} == {"1.0"}


def test_the_campaign_is_forty_valid_with_trust_captured():
    _skip_without(RESULTS)
    with open(RESULTS, encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["campaign_id"] == "CAMPAIGN_P1"
    assert res["platform"] == "px4"
    assert len(res["trials"]) == 40
    assert all(t["validity"] == "VALID" for t in res["trials"])
    assert all(t["trust_trajectory"] == "CAPTURED" for t in res["trials"])


def test_the_table_has_no_uncaptured_cells():
    assert not [(r["trial_id"], k) for r in _rows()
                for k, v in r.items() if v == "NOT_CAPTURED"]


# --- 2. both ArduPilot findings replicate ----------------------------------

def test_the_control_arm_rises_more_on_px4_too():
    """FL-016 on a second platform, from an independent campaign."""
    rows = _rows()
    fault = sorted(float(r["trust_delta"]) for r in rows
                   if r["role"] == "FAULT" and r["validity"] == "VALID")
    control = sorted(float(r["trust_delta"]) for r in rows
                     if r["role"] == "CONTROL" and r["validity"] == "VALID")
    assert len(fault) == len(control) == 20
    assert all(d > 0 for d in fault) and all(d > 0 for d in control)
    assert max(fault) < min(control), (
        f"the arms' ranges overlap: fault max {max(fault)}, control min "
        f"{min(control)}")
    assert statistics.median(control) > 2.0 * statistics.median(fault)


def test_the_original_px4_delta_is_outside_the_repeated_fault_range():
    """FL-017 on a second platform."""
    _skip_without(RESULTS)
    with open(RESULTS, encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["question_D_original_n1"]["inside_repeated_fault_range"] is False


def test_the_control_comparison_was_already_possible_from_the_frozen_artifact():
    """The finding was latent in the frozen n=1 artifact on BOTH platforms.

    This is what makes FL-016 a reporting failure rather than a new
    measurement: the control arm's snapshots were always there.
    """
    _skip_without(ORIGINAL_ARTIFACT)
    with open(ORIGINAL_ARTIFACT, encoding="utf-8") as fh:
        art = json.load(fh)
    snap = {arm: art[arm]["snapshots"] for arm in ("fault", "control")}
    d_fault = snap["fault"]["post"]["trust_gps"] - snap["fault"]["pre"]["trust_gps"]
    d_control = (snap["control"]["post"]["trust_gps"]
                 - snap["control"]["pre"]["trust_gps"])
    assert d_control > d_fault, (
        "the frozen PX4 artifact no longer shows the control arm rising more; "
        "if it changed, frozen evidence was edited")


# --- 3. the controlled replay ----------------------------------------------

def test_the_watchdog_replay_reproduces_both_px4_values_from_one_log():
    """Section 3.2. The experiment that attributes the pre-fault difference.

    ONE log, TWO watchdog tables, both measured values recovered. Tolerance is
    0.005 -- the reconstruction under-counts hand-offs, so it cannot be exact,
    and the measured residuals are ~0.001 and ~0.0004 against that budget.
    """
    _skip_without(ORIGINAL_FAULT_LOG)
    from tools.csia_experiment.watchdog_replay import compare
    got = compare(ORIGINAL_FAULT_LOG, "px4")
    assert got["frozen_watchdog_s"] == 0.5
    assert got["derived_watchdog_s"] == 1.0
    # The frozen table recovers what the ORIGINAL artifact recorded.
    assert got["trust_under_frozen"] == pytest.approx(0.985624, abs=0.005)
    # The derived table recovers what the REPEAT measured, from the same log.
    assert got["trust_under_derived"] == pytest.approx(0.952172, abs=0.005)


def test_the_replay_does_not_reproduce_ardupilot_and_is_pinned_as_invalid():
    """FL-019. The replay is NOT an instrument on ArduPilot.

    Asserting that a tool FAILS looks odd until you notice the alternative:
    the reconciliation says ArduPilot's stability is unresolved BECAUSE this
    replay cannot speak to it. If the replay ever starts reproducing
    ArduPilot's measured values, that claim needs revisiting -- and this test
    is what would say so.
    """
    ap_log = os.path.join(ROOT, "logs", "shadow-sitl-ardupilot",
                          "20260825T005244Z-8c32ffe5.part000.jsonl")
    _skip_without(ap_log)
    from tools.csia_experiment.watchdog_replay import compare
    got = compare(ap_log, "ardupilot")
    measured_pre = 0.9246388655509185
    assert abs(got["trust_under_frozen"] - measured_pre) > 0.01, (
        "the replay now reproduces ArduPilot's measured pre-fault trust. "
        "FL-019 says it does not, and that is why ArduPilot's stability is "
        "recorded as UNRESOLVED. Re-open it.")


def test_the_two_watchdogs_are_the_same_pair_on_px4():
    assert STALE_TIMEOUT_S["gps"] == 0.5
    assert build_runtime_stale_timeouts("px4")["gps"] == 1.0


def test_the_reconciliation_document_exists_and_names_its_instrument():
    _skip_without(DOC)
    with open(DOC, encoding="utf-8") as fh:
        text = fh.read()
    for token in ("watchdog_replay.py", "UNRESOLVED", "1.0, not 3.0",
                  "mechanism_a_px4.json"):
        assert token in text, f"{token} is missing from the reconciliation"
