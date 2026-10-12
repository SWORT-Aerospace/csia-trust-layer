"""Preregistration guards. NOTHING HERE SCORES A CONFIRMATORY TRIAL.

These tests protect the things that would silently invalidate the campaign:
contamination, a broken instrument, and a preregistration that has drifted from
the artifacts it cites.
"""

from __future__ import annotations

import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "dual_admissibility_confirmatory")
RES = os.path.join(PKG, "results")


def _j(name):
    with open(os.path.join(RES, name), encoding="utf-8") as fh:
        return json.load(fh)


def _needs(name):
    return pytest.mark.skipif(not os.path.exists(os.path.join(RES, name)),
                              reason=f"{name} not built")


@_needs("TOOL_SELF_AUDIT.json")
def test_the_checker_still_catches_the_bug_it_once_caught():
    d = _j("TOOL_SELF_AUDIT.json")
    assert d["checker_detects_the_defect"] is True
    assert d["collapse_with_defect_injected"] is True
    assert d["collapse_with_correct_implementation"] is False
    assert d["implementation_restored"] is True


@_needs("DESIGN_FEASIBILITY.json")
def test_matched_A_is_achievable_over_the_scored_interval():
    d = _j("DESIGN_FEASIBILITY.json")
    for arm, v in d["Q1_matched_A"].items():
        assert v["A_mismatches_in_scored_interval"] == 0, arm
        assert v["A_is_zero_throughout_scored_interval"] is True, arm


@_needs("DESIGN_FEASIBILITY.json")
def test_the_strong_form_of_H1_is_recorded_as_false():
    """The coupled arm is NOT purely coupled. Freezing the strong form would
    have frozen a known falsehood."""
    d = _j("DESIGN_FEASIBILITY.json")
    c0 = d["Q2_does_the_coupled_arm_alias"]["S1"]
    assert c0["aliases_at_leading_cause"] is True
    assert c0["aliases_completely"] is False, (
        "if C0 aliased completely, C0_STRONG would be pointless and the "
        "preregistration would need rewriting")


@_needs("DEVELOPMENT_TRACE_MANIFEST.json")
@_needs("CONFIRMATORY_TRACE_PLAN.json")
def test_no_confirmatory_trial_reuses_a_development_trace():
    dev = {r["path"] for r in _j("DEVELOPMENT_TRACE_MANIFEST.json")["recordings"]}
    plan = _j("CONFIRMATORY_TRACE_PLAN.json")
    for t in plan["trials"]:
        assert t.get("path") not in dev
        assert t["status"] == "NOT CAPTURED", (
            "a captured trial means the hard stop was crossed")


@_needs("CONFIRMATORY_TRACE_PLAN.json")
def test_the_campaign_has_not_been_run():
    """Item 32 is a hard stop. This test is the tripwire."""
    plan = _j("CONFIRMATORY_TRACE_PLAN.json")
    assert all(t["status"] == "NOT CAPTURED" for t in plan["trials"])
    assert plan["counts"]["total"] == 30
    assert plan["counts"]["matched_pairs"] == 10


@_needs("CONFIRMATORY_TRACE_PLAN.json")
def test_matched_pairs_share_onset_and_duration():
    plan = _j("CONFIRMATORY_TRACE_PLAN.json")
    pairs = {}
    for t in plan["trials"]:
        if t["pair_id"]:
            pairs.setdefault(t["pair_id"], []).append(t)
    assert len(pairs) == 10
    for pid, ts in pairs.items():
        assert len(ts) == 2, pid
        assert ts[0]["onset_s"] == ts[1]["onset_s"], pid
        assert ts[0]["duration_s"] == ts[1]["duration_s"], pid
        assert {t["mechanism"] for t in ts} == {
            "SENSOR_INVALID", "TRANSPORT_UNAVAILABLE"}, pid


@_needs("COUNTEREXAMPLE_GENERATOR_FREEZE.json")
def test_the_frozen_generator_files_still_hash_as_frozen():
    import hashlib
    d = _j("COUNTEREXAMPLE_GENERATOR_FREEZE.json")
    for path, want in d["files_frozen"].items():
        got = hashlib.sha256(
            open(os.path.join(ROOT, path), "rb").read()).hexdigest()
        assert got == want, (
            f"{path} changed after the freeze; the campaign is void unless "
            f"this is a new preregistration")


# A banned word is tolerated only on a line that also disclaims it. This is a
# heuristic guard against writing drift, not a proof of anything -- its job is
# to fail loudly if someone later writes "this is novel" in a package whose
# whole conclusion is that it is not.
DENIALS = ("not ", "no ", "none", "nothing", "never", "cannot", "may not",
           "subsumed", "known/", "forbidden", "struck", "downgrad",
           "prior art", "unsupported", "settled", "without")


def test_no_novelty_wording_anywhere_in_the_package():
    banned = ("novel", "first-ever", "unprecedented", "new paradigm",
              "new theorem", "breakthrough")
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        raw = open(os.path.join(PKG, fn), encoding="utf-8").read().lower()
        # strip emphasis, then pad punctuation so "**No.**" matches the
        # denial token "no " rather than reading as the word "no."
        text = raw.replace("*", "").replace("`", "")
        text = re.sub(r"[.,;:!?)\]]", " ", text)
        for w in banned:
            if w not in text:
                continue
            # Allowed only in an explicit denial. A section HEADING may pose
            # the question and answer it on the next line ("Does any novelty
            # claim survive?" / "No."), so the window is the line plus the
            # next two.
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if w not in line:
                    continue
                # A markdown HEADING is a label, not a claim -- and the
                # report format this package must follow mandates headings
                # like "Strongest possible novel contribution remaining".
                # The body under it is what has to disclaim.
                if line.lstrip().startswith("#"):
                    continue
                window = " ".join(lines[i:i + 3])
                assert any(k in window for k in DENIALS), (fn, w, line[:120])


# ---------------------------------------------- Stage 2.1 kill test
@_needs("STAGE2_1_KILL_TEST.json")
def test_heldout_pairs_have_exactly_matched_A():
    d = _j("STAGE2_1_KILL_TEST.json")
    assert d["trace_provenance"] == "HELD_OUT"
    assert d["held_out_pairs"] == 3
    for pair, v in d["per_pair"].items():
        assert v["A_matched_exactly"] is True, pair
        assert v["A_trace_hashes_equal"] is True, pair
        assert v["A_zero_throughout"] is True, pair


@_needs("STAGE2_1_KILL_TEST.json")
def test_one_threshold_applied_to_every_pair():
    """A per-pair threshold would score on an onset artefact and prove
    nothing. The ledger records a single value."""
    d = _j("STAGE2_1_KILL_TEST.json")
    assert isinstance(d["c0_strong_theta"], float)
    assert d["theta_fit_on"] == "DEVELOPMENT traces only"


@_needs("STAGE2_1_KILL_TEST.json")
def test_the_coupled_arm_has_no_live_information():
    """The finding the verdict rests on: nothing the coupled arm exposes
    gains discriminating power after A closes."""
    d = _j("STAGE2_1_KILL_TEST.json")
    for pair, v in d["per_pair"].items():
        for field, info in v["live_vs_inherited"].items():
            assert info["classification"] != "LIVE_INFORMATION", (pair, field)
    assert d["history_removal_control"][
        "any_discrimination_grows_after_closure"] is False


@_needs("STAGE2_1_KILL_TEST.json")
def test_the_kill_test_result_is_recorded_as_measured():
    d = _j("STAGE2_1_KILL_TEST.json")
    s = d["summary"]
    assert s["all_pairs_A_matched"] is True
    # C0_STRONG failed; STATUS_ONLY succeeded. Recorded, not asserted as good.
    assert s["C0_STRONG_mean"] < 0.6
    assert s["STATUS_ONLY_mean"] > s["C0_STRONG_mean"]


@_needs("COUNTEREXAMPLE_CROSS_PATH_RESULTS.json")
def test_cross_path_defect_reproduces_and_stays_separate():
    d = _j("COUNTEREXAMPLE_CROSS_PATH_RESULTS.json")
    p = d["pairs"]["v1_1_adapter__vs__plugins_py"]
    assert p["verdict"] == "PATHS_DIVERGE"
    assert p["shortest_distinguishing_trace"] == "I"
    assert d["status_verdict"] == "IMPLEMENTATION DEFECT / SEMANTIC NON-EQUIVALENCE"
    # the ulog branch must report whether it was exercised, not assume it
    assert d["pairs"]["ulog_source_py"]["invalid_branch"] in (
        "EXERCISED", "NOT_EXERCISED", "UNAVAILABLE")


def test_battery_defect_is_fixed_and_its_pre_fix_record_preserved():
    """D3, executed rather than read. **The defect is now FIXED.**

    This test used to assert that a disowned current was still served as
    usable, because it was: `_reject_sentinel` recorded the sentinel without
    clearing `_latest`, `_channel_value` consults `_latest` first, and the
    retained 5.00 A won until it aged out as STALE -- the wrong reason.

    That was a real finding about v1 and it is preserved, not deleted:

      * the frozen pre-fix behaviour, with its sha256, is in
        `engineering/v1_1/KNOWN_DEFECTS_PRE_FIX.json` (case D1);
      * the research package's own report and citations still resolve, because
        they are now verified against the revision they were taken at rather
        than against the worktree
        (`research/semantic_authority_conflict/authorities.py:CITED_REVISION`).

    What this test now guards is that the fix stayed fixed. Turning a defect
    reproduction into a defect regression test is the point of the exercise;
    deleting it would have thrown away the only executable record.
    """
    from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
    now = {"t": 0.0}
    a = ArduPilotAdapter(clock=lambda: now["t"])

    def bat(cur, t):
        return {"mavpackettype": "BATTERY_STATUS",
                "voltages": [12000] * 4 + [65535] * 6,
                "current_battery": cur, "time_boot_ms": int(t * 1000),
                "id": 0, "battery_function": 0, "type": 0,
                "temperature": 32767, "current_consumed": 0,
                "energy_consumed": 0, "battery_remaining": 80,
                "time_remaining": 0, "charge_state": 1,
                "voltages_ext": [0] * 4, "mode": 0, "fault_bitmask": 0}

    now["t"] = 0.0
    a.ingest(bat(500, 0.0))
    now["t"] = 0.10
    a.ingest(bat(-1, 0.10))                       # producer disowns it
    assert a.sentinel_counts()["battery.current"] == 1

    now["t"] = 0.30
    cv = a.sample(t_mono=0.30).get("battery.current")
    assert cv.usable is False, "pre-v1.1 the retained 5.00 A was still served"
    assert cv.value is None
    assert cv.missing.value == "SENTINEL", (
        "the producer's own disavowal must reach the channel; reporting "
        "STALE instead was the v1 defect this fix removes")

    # and it still ages out: a sentinel from a minute ago says nothing about
    # now, so the channel must not sit on SENTINEL for ever
    now["t"] = 0.80
    cv = a.sample(t_mono=0.80).get("battery.current")
    assert cv.usable is False
