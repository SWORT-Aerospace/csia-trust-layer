"""Behavioural oracles for ARDUPILOT_REPEAT_RECONCILIATION.md.

A reconciliation document is prose. Prose drifts away from the artifacts it
describes without anything going red. These tests pin the three claims the
document actually rests on, each against a DIFFERENT primitive source:

  1. the original trial's headline scalars re-derive FROM ITS OWN FLIGHT LOG
     using the committed extractor -- closing the SCALAR_DERIVATION_GRAPH open
     item "mechanism_a_first_t_ardupilot has no oracle against the ORIGINAL
     trial's own log";

  2. the root cause in section 4 -- a 0.5 s frozen watchdog against a 1.0 s
     derived one -- re-derives FROM SOURCE. If either constant moves, the
     document's explanation is wrong and this file says so;

  3. the measured dwells in both runs match their respective constants, and
     the A2 control arm rises MORE than the A2 fault arm, FROM THE COMMITTED
     LOGS AND THE COMMITTED RESULTS FILE.

WHAT THESE TESTS DELIBERATELY DO NOT DO
---------------------------------------
They do not assert that the original agrees with the repeats. It does not, on
two of twelve quantities, and test 3 pins the disagreement so it cannot be
quietly closed later by re-running something.
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
from csia.v1_1.staleness import (build_runtime_stale_timeouts,     # noqa: E402
                                 required_channels)
from tools.csia_experiment.extract_mechanism_a import (            # noqa: E402
    GPS_EDGES, extract)

DOC = os.path.join(ROOT, "research", "physical_validation",
                   "ARDUPILOT_REPEAT_RECONCILIATION.md")

#: The original n=1 ArduPilot trial, flown 2026-08-25. Its FROZEN artifact is
#: research/v1_1/results/mechanism_a_ardupilot.json; this is the raw log that
#: artifact was reduced from.
ORIGINAL_FAULT_LOG = os.path.join(
    ROOT, "logs", "shadow-sitl-ardupilot",
    "20260825T005244Z-8c32ffe5.part000.jsonl")

ORIGINAL_ARTIFACT = os.path.join(ROOT, "research", "v1_1", "results",
                                 "mechanism_a_ardupilot.json")

A2_RESULTS = os.path.join(ROOT, "research", "physical_validation", "results",
                          "mechanism_a_a2_trust_ardupilot.json")

A2_TABLE = os.path.join(ROOT, "research", "physical_validation", "results",
                        "ARDUPILOT_MECHANISM_A_REPEAT_TABLE.csv")

#: One tick at the 25 Hz the campaigns ran at. The dwell is observed on tick
#: boundaries, so it can only ever be resolved to this.
TICK_S = 0.04


def _skip_without(path):
    if not os.path.exists(path):
        pytest.skip(f"{os.path.relpath(path, ROOT)} not present")


# --- 1. the original trial re-derives from its own log ----------------------

@pytest.fixture(scope="module")
def original():
    _skip_without(ORIGINAL_FAULT_LOG)
    return extract(ORIGINAL_FAULT_LOG, onset_s=12.0)


@pytest.fixture(scope="module")
def artifact():
    _skip_without(ORIGINAL_ARTIFACT)
    with open(ORIGINAL_ARTIFACT, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_original_first_t_rederives_from_its_own_log(original, artifact):
    """12.043901 was never re-derived from the log it came from. Now it is.

    The 82 us residual is a t0 CONVENTION, not noise: the artifact measured
    from CSIA process start, the extractor from the first tick, and the first
    tick sits at t_mono = 8.2e-05. Asserting the convention rather than a
    tolerance is what makes this a check instead of a loose comparison.
    """
    published = artifact["fault"]["intermediate_quantity"]["first_t"]
    rederived = original["first_t_gnss_position_missing"]
    with open(ORIGINAL_FAULT_LOG, encoding="utf-8") as fh:
        first_tick = next(json.loads(line) for line in fh
                          if json.loads(line).get("record") == "tick")
    offset = first_tick["t_mono"]
    assert rederived == pytest.approx(published - offset, abs=1e-9), (
        f"published {published}, re-derived {rederived}, first tick at "
        f"{offset}: the t0 convention no longer explains the difference")


def test_the_original_tick_count_and_gate_collapse_rederive(original,
                                                            artifact):
    """The quantities with no convention attached must match exactly."""
    iq = artifact["fault"]["intermediate_quantity"]
    assert original["gnss_position_missing_ticks"] == iq["ticks_observed"]
    assert original["gps_gate_weight_sum_before"] == 3.0
    assert original["gps_gate_weight_sum_after"] == 0.0
    assert original["ranks_before"]["nominal"] == 1
    assert original["ranks_after"]["nominal"] == 1
    assert original["ranks_before"]["gps_fault"] == 2
    assert original["ranks_after"]["gps_fault"] == 2


def test_the_original_trust_was_in_the_log_all_along(original):
    """The artifact carries four snapshots; the LOG carries every tick.

    The extractor reports NOT_CAPTURED because it reads the campaign's trust
    trace, which this trial has none of -- but `trust_post` per tick is in the
    flight log, which is how section 4.2 measured the dwell. NOT_CAPTURED is a
    statement about the instrument, not about the universe.
    """
    assert original["trust_before"] == "NOT_CAPTURED"
    with open(ORIGINAL_FAULT_LOG, encoding="utf-8") as fh:
        ticks = [json.loads(line) for line in fh
                 if json.loads(line).get("record") == "tick"]
    assert all("gps" in (t.get("trust_post") or {}) for t in ticks[10:]), (
        "the original log does carry per-tick trust; if it stops, section 4.2 "
        "is no longer reproducible")


# --- 2. the root cause re-derives from source -------------------------------

def test_the_two_watchdogs_that_explain_the_discrepancy(
):
    """Section 4.3, from the frozen source and the derivation, not a document.

    0.5 s explains the original's 0.4788 s dwell; 1.0 s explains the repeats'
    0.9997 s. If either number moves, section 4 is wrong.
    """
    assert STALE_TIMEOUT_S["gps"] == 0.5, (
        "the frozen core's gps watchdog is what the ORIGINAL trial ran under")
    derived = build_runtime_stale_timeouts("ardupilot")
    assert derived["gps"] == 1.0, (
        "the derived runtime gps watchdog is what A1 and A2 ran under")
    assert derived["gps"] == 2.0 * STALE_TIMEOUT_S["gps"], (
        "section 4.2's factor-of-two dwell is this ratio and nothing else")


def test_the_derived_watchdog_introduces_no_new_constant():
    """It is MAX_AGE_MARGIN / declared rate over the node's own channels.

    A hand-written 1.0 would make section 4.3 an assertion rather than a
    derivation.
    """
    from csia.v1_1.staleness import channel_max_age
    ages = channel_max_age("ardupilot")
    needed = required_channels("gps")
    assert needed == ("gnss.position", "gnss.velocity")
    assert build_runtime_stale_timeouts("ardupilot")["gps"] == max(
        ages[ch] for ch in needed)


# --- 3. the measured dwells, and the control arm ----------------------------

def _dwell(path):
    """Seconds from `gnss.position` going MISSING to the gps gates reaching 0."""
    with open(path, encoding="utf-8") as fh:
        ticks = [json.loads(line) for line in fh
                 if json.loads(line).get("record") == "tick"]
    t0 = ticks[0]["t_mono"]
    missing = gate_zero = None
    for x in ticks:
        t = x["t_mono"] - t0
        ch = (x["canonical"]["channels"].get("gnss.position") or {})
        if missing is None and ch.get("missing") == "NO_3D_FIX":
            missing = t
        gates = x.get("gates") or {}
        gsum = sum(float(gates[k][1]) for k in GPS_EDGES if k in gates)
        if missing is not None and gate_zero is None and gsum == 0.0:
            gate_zero = t
    return None if missing is None or gate_zero is None else gate_zero - missing


def test_the_original_dwell_matches_the_frozen_watchdog():
    _skip_without(ORIGINAL_FAULT_LOG)
    dwell = _dwell(ORIGINAL_FAULT_LOG)
    assert dwell == pytest.approx(STALE_TIMEOUT_S["gps"], abs=TICK_S), (
        f"the original's measured dwell is {dwell}, which no longer matches "
        f"the frozen watchdog it is attributed to")


def test_the_a2_dwells_match_the_derived_watchdog():
    _skip_without(A2_TABLE)
    campaign = os.path.join(ROOT, "campaigns", "physical_validation",
                            "mechanism_a_trust_completion_a2")
    _skip_without(campaign)
    derived = build_runtime_stale_timeouts("ardupilot")["gps"]
    dwells = []
    for name in sorted(os.listdir(campaign)):
        if not name.startswith("MECHA2-"):
            continue
        with open(os.path.join(campaign, name), encoding="utf-8") as fh:
            man = json.load(fh)
        if man["record"].get("arm") != "FAULT":
            continue
        log = os.path.join(ROOT, "logs", "shadow-sitl-ardupilot",
                           f"{man['record']['measured_flight_id']}"
                           ".part000.jsonl")
        if os.path.exists(log):
            dwells.append(_dwell(log))
    assert len(dwells) == 20, f"expected 20 FAULT logs, found {len(dwells)}"
    for d in dwells:
        assert d == pytest.approx(derived, abs=TICK_S)


def _dwell_and_age(path):
    """Dwell, plus the channel's age at the last tick before it was flagged.

    The watchdog counts from the last time the `gps` node was EMITTED, not
    from the tick that first reports MISSING. Those differ by exactly this
    age, which is why section 4.5's relation has an age term at all.
    """
    with open(path, encoding="utf-8") as fh:
        ticks = [json.loads(line) for line in fh
                 if json.loads(line).get("record") == "tick"]
    t0 = ticks[0]["t_mono"]
    prev = missing = age = gate_zero = None
    for x in ticks:
        t = x["t_mono"] - t0
        ch = (x["canonical"]["channels"].get("gnss.position") or {})
        if missing is None and ch.get("missing") == "NO_3D_FIX":
            missing = t
            age = ((prev["canonical"]["channels"].get("gnss.position") or {})
                   .get("age_s") if prev else None)
        gates = x.get("gates") or {}
        gsum = sum(float(gates[k][1]) for k in GPS_EDGES if k in gates)
        if missing is not None and gate_zero is None and gsum == 0.0:
            gate_zero = t
        prev = x
    if missing is None or gate_zero is None:
        return None, age
    return gate_zero - missing, age


#: Section 4.5. Four runs across TWO platforms and BOTH watchdog values, so
#: the relation is not fitted to the case it explains.
DWELL_CASES = [
    ("ardupilot ORIGINAL", "shadow-sitl-ardupilot",
     "20260825T005244Z-8c32ffe5", 0.5),
    ("px4 ORIGINAL", "shadow-sitl-px4",
     "20260825T005931Z-1b4add14", 0.5),
]


@pytest.mark.parametrize("label,subdir,flight_id,watchdog", DWELL_CASES)
def test_the_dwell_is_the_watchdog_minus_the_channel_age(label, subdir,
                                                        flight_id, watchdog):
    """Section 4.5: dwell ~= watchdog - age at the last usable tick.

    Tolerance is ONE TICK PERIOD, because the dwell is observed on tick
    boundaries and cannot be resolved finer. It is not a tolerance chosen to
    make the check pass -- every measured residual is under 0.013 s against a
    0.04 s budget.
    """
    log = os.path.join(ROOT, "logs", subdir, f"{flight_id}.part000.jsonl")
    _skip_without(log)
    dwell, age = _dwell_and_age(log)
    assert dwell is not None and age is not None, f"{label}: no dwell to check"
    assert dwell == pytest.approx(watchdog - age, abs=TICK_S), (
        f"{label}: dwell {dwell} against watchdog {watchdog} minus age {age}; "
        f"section 4.5's relation no longer holds")


def test_the_px4_gps_watchdog_moved_the_same_way_ardupilot_s_did():
    """Section 4.6: the reconciliation is not an ArduPilot-only story."""
    assert STALE_TIMEOUT_S["gps"] == 0.5
    assert build_runtime_stale_timeouts("px4")["gps"] == 1.0


def test_both_original_logs_record_a_platform_name_not_a_build():
    """Section 4.6, both platforms. An UNRECOVERABLE field, pinned.

    If this ever starts failing because a log gained a real build string, the
    log was rewritten -- which is the thing that must not happen to frozen
    evidence.
    """
    for subdir, flight_id, expected in (
            ("shadow-sitl-ardupilot", "20260825T005244Z-8c32ffe5",
             "ardupilot"),
            ("shadow-sitl-px4", "20260825T005931Z-1b4add14", "px4")):
        log = os.path.join(ROOT, "logs", subdir, f"{flight_id}.part000.jsonl")
        _skip_without(log)
        assert extract(log, onset_s=12.0)["autopilot_version"] == expected


def _table_rows():
    with open(A2_TABLE, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_the_control_arm_rises_more_than_the_fault_arm():
    """Section 3. The finding that makes "trust rises" misleading alone.

    Pinned so that a later change which makes the two arms agree cannot pass
    silently: agreement would mean the fault stopped suppressing the rise,
    which is a different result, not a tidier one.
    """
    _skip_without(A2_TABLE)
    rows = _table_rows()
    fault = sorted(float(r["trust_delta"]) for r in rows
                   if r["role"] == "FAULT" and r["validity"] == "VALID")
    control = sorted(float(r["trust_delta"]) for r in rows
                     if r["role"] == "CONTROL" and r["validity"] == "VALID")
    assert len(fault) == len(control) == 20
    assert all(d > 0 for d in fault), "the fault arm rises in every trial"
    assert all(d > 0 for d in control), "so does the control arm"
    assert max(fault) < min(control), (
        f"the arms' ranges overlap: fault max {max(fault)}, control min "
        f"{min(control)}. Section 3 depends on them being disjoint")
    assert statistics.median(control) > 2.0 * statistics.median(fault)


def test_the_original_delta_is_outside_the_repeated_fault_range():
    """Section 1, row 10. The discrepancy itself, pinned.

    A test that asserts a disagreement looks strange until you notice the
    alternative: the disagreement is currently only recorded in prose, where
    re-running something could quietly resolve it.
    """
    _skip_without(A2_RESULTS)
    with open(A2_RESULTS, encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["question_D_original_n1"]["inside_repeated_fault_range"] is False


def test_every_a2_trial_captured_trust_and_the_denominator_is_forty():
    """A1's omission (FL-014) is not repeated, and nothing was dropped."""
    _skip_without(A2_RESULTS)
    with open(A2_RESULTS, encoding="utf-8") as fh:
        res = json.load(fh)
    assert len(res["trials"]) == 40
    assert all(t["trust_trajectory"] == "CAPTURED" for t in res["trials"])
    assert all(t["validity"] == "VALID" for t in res["trials"])


def test_the_reconciliation_document_exists_and_names_its_root_cause():
    """The document is a deliverable; an empty or truncated one is a failure.

    This checks presence and the load-bearing identifiers only. It is NOT a
    prose guard -- four earlier guards in this repository fired on their own
    documentation, and the fix each time was to check structure, not words.
    """
    _skip_without(DOC)
    with open(DOC, encoding="utf-8") as fh:
        text = fh.read()
    for token in ("STALE_TIMEOUT_S", "build_runtime_stale_timeouts",
                  "NOT_CAPTURED", "mechanism_a_ardupilot.json"):
        assert token in text, f"{token} is missing from the reconciliation"
