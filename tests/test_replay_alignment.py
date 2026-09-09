"""A replay must compare the SAME tick, and refuse when it cannot (HF-017).

WHAT WENT WRONG
---------------
The PX4 decision replay reported 119 divergences with a perfectly symmetric
signature: 59 ticks where the replay had `altitude_baro` live and the
recording did not, and 59 the other way. HF-016 read that symmetry correctly
as a phase offset and wrongly assumed the offset was inherent to replaying
from hand-offs.

It was not. It was in the comparison itself. The replayed states carry the
layer's own tick clock -- exact multiples of `dt_tick`, anchored at 0.0 --
while the recorded rows were stamped with wall time and then shifted by the
first row's `t_mono`. On the log that produced the 119, that first row sat at
t = 0.023607 s, which is 0.59 of a tick. Every subsequent pairing was
therefore off by more than half a tick, and at baro's staleness boundary that
flips a freshness bit in whichever direction the boundary is crossed -- one
tick early on the rising edge, one tick early on the falling edge. Symmetric,
by construction.

With the same log, the same reconstruction and the same comparator, joining
on the layer's tick index instead gives 2250 of 2250 BIT_IDENTICAL and zero
divergences.

THE SECOND DEFECT, WHICH IS THE MORE SERIOUS ONE
------------------------------------------------
The long-standing "144 divergent" figure came from a log whose header carries
`stale_timeout_s: None`. The replay applied timeouts derived from the
platform TODAY to a run whose timeouts were never recorded, and reported the
difference as a decision divergence. That is a finding manufactured out of a
gap in the log -- the same defect as MX-021, where a swallowed AttributeError
became "undetected at every magnitude".

A log that does not say what it was configured with is NOT_COMPARABLE, and
NOT_COMPARABLE is never PASS.

WHAT THESE TESTS PIN
--------------------
The invariants, not the measurements. The measured counts live in the
artifact, because `logs/` is gitignored and no flight log is available to a
test on a clean checkout.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.assurance import decision_replay as dr           # noqa: E402


def _write_log(path, header_extra, ticks):
    header = {"record": "header", "flight_id": "TEST", "csia_commit": "abc123"}
    header.update(header_extra)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(header) + "\n")
        for t in ticks:
            fh.write(json.dumps({"record": "tick", **t}) + "\n")
    return str(path)


# --- the comparator that decides DIVERGENT ---------------------------------

def test_live_edges_separates_a_dead_edge_from_a_live_one():
    """The whole DIVERGENT verdict is this one set comparison."""
    live = {"altitude_baro": [0.4, 0.9]}
    dead = {"altitude_baro": [0.4, 0.0]}
    assert dr._live_edges(live) == frozenset({"altitude_baro"})
    assert dr._live_edges(dead) == frozenset()
    assert dr._live_edges(live) != dr._live_edges(dead)


def test_live_edges_is_reflexive():
    gates = {"altitude_baro": [0.4, 0.9], "attitude_gravity_mag": [0.1, 0.8]}
    assert dr._live_edges(gates) == dr._live_edges(dict(gates))


def test_live_edges_ignores_a_malformed_entry_rather_than_raising():
    """A gate map with a scalar where a pair belongs must not crash a replay
    mid-run; the edge simply is not counted as carrying weight."""
    assert dr._live_edges({"x": 0.9, "y": [0.1, 0.5]}) == frozenset({"y"})


def test_controls_pass_and_cover_both_comparators():
    from tools.assurance.instrument_controls import guard
    dr._controls()
    report = guard(dr.INSTRUMENT)
    assert report["verdict"] == "PASS"
    observed = " ".join(str(r.get("observed", "")) for r in report["controls"])
    assert "cat_differs" in observed, (
        "the pair must exercise _live_edges, not only _rel -- a _live_edges "
        "stuck at a constant would turn every divergent replay green")


# --- the provenance refusal ------------------------------------------------

def test_log_without_staleness_config_is_not_comparable(tmp_path):
    path = _write_log(tmp_path / "no_cfg.jsonl", {},
                      [{"t_mono": 0.04}, {"t_mono": 0.08}])
    result = dr.replay(path, "px4")
    assert result["verdict"] == "NOT_COMPARABLE"
    assert result["reason"] == "NO_STALENESS_CONFIG_IN_LOG"


def test_a_not_comparable_result_reports_no_divergence_count(tmp_path):
    """The failure mode being pinned: a number that reads as a measurement.

    `divergent: 144` was quoted for months off a log that could not be
    replayed. An unmeasurable comparison must not emit a count at all.
    """
    path = _write_log(tmp_path / "no_cfg.jsonl", {}, [{"t_mono": 0.04}])
    result = dr.replay(path, "px4")
    for absent in ("divergent", "decisions_compared", "bit_identical"):
        assert absent not in result, (
            f"{absent!r} present on a NOT_COMPARABLE result; a reader will "
            f"quote it as evidence")


def test_staleness_config_that_changed_since_the_run_is_not_comparable(
        tmp_path):
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    changed = dict(build_runtime_stale_timeouts("px4"))
    changed["baro"] = changed["baro"] * 2.0
    path = _write_log(tmp_path / "drift.jsonl", {"stale_timeout_s": changed},
                      [{"t_mono": 0.04}])
    result = dr.replay(path, "px4")
    assert result["verdict"] == "NOT_COMPARABLE"
    assert result["reason"] == "STALENESS_CONFIG_CHANGED_SINCE_THE_RUN"
    assert result["recorded_timeouts"] != result["derived_timeouts"]


def test_matching_staleness_config_passes_the_provenance_gate(tmp_path):
    """Anti-vacuity: the gate must not refuse everything."""
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    path = _write_log(
        tmp_path / "ok.jsonl",
        {"stale_timeout_s": dict(build_runtime_stale_timeouts("px4"))},
        [{"t_mono": 0.04, "canonical": {"channels": {}}, "gates": {},
          "trust_post": {}}])
    result = dr.replay(path, "px4")
    assert result.get("reason") not in (
        "NO_STALENESS_CONFIG_IN_LOG",
        "STALENESS_CONFIG_CHANGED_SINCE_THE_RUN"), (
        "a log carrying exactly the derived timeouts was refused; the gate "
        "refuses everything and proves nothing")


# --- alignment -------------------------------------------------------------

def test_exact_alignment_is_refused_on_a_log_without_tick_tau(tmp_path):
    """Not silently downgraded. A caller who asked for the exact join and
    got the approximation would compare two things that are not comparable."""
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    path = _write_log(
        tmp_path / "old.jsonl",
        {"stale_timeout_s": dict(build_runtime_stale_timeouts("px4"))},
        [{"t_mono": 0.04, "canonical": {"channels": {}}, "gates": {},
          "trust_post": {}}])
    result = dr.replay(path, "px4", align="exact")
    assert result["verdict"] == "NOT_COMPARABLE"
    assert "tick_tau" in result["reason"]


def test_unknown_alignment_raises(tmp_path):
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    path = _write_log(
        tmp_path / "x.jsonl",
        {"stale_timeout_s": dict(build_runtime_stale_timeouts("px4"))},
        [{"t_mono": 0.04, "canonical": {"channels": {}}, "gates": {},
          "trust_post": {}}])
    with pytest.raises(ValueError):
        dr.replay(path, "px4", align="nearest-ish")


def test_the_two_alignments_are_named_distinctly():
    """Results from the two are NOT comparable, so the artifact must say
    which produced it. Two labels that differ is the minimum for that."""
    src = open(os.path.join(ROOT, "tools", "assurance",
                            "decision_replay.py"), encoding="utf-8").read()
    assert "EXACT_LAYER_TICK_INDEX" in src
    assert "NEAREST_WALL_CLOCK_WITHIN_HALF_TICK" in src


def test_half_tick_is_derived_from_the_layer_not_hardcoded():
    """`half_tick = 0.02` was a literal that silently encoded tick_hz=25.

    A layer at any other rate would have been compared against the wrong
    window, with no error and no note in the artifact.
    """
    src = open(os.path.join(ROOT, "tools", "assurance",
                            "decision_replay.py"), encoding="utf-8").read()
    assert "half_tick = dt_tick / 2.0" in src
    assert "half_tick = 0.02" not in src


# --- the default log selection --------------------------------------------

def test_default_logs_only_offers_replayable_logs():
    """`logs/` is gitignored, so the old hardcoded defaults resolved to
    LOG_ABSENT everywhere but one machine -- and both named logs lacked the
    staleness config anyway, so neither was replayable even there."""
    logs, plats = dr._default_logs()
    assert len(logs) == len(plats)
    for log in logs:
        path = os.path.join(ROOT, log)
        assert dr._header_field(path, "stale_timeout_s"), (
            f"{log} was offered as a default and cannot be replayed")


def test_header_field_stops_at_the_first_tick(tmp_path):
    """A header must precede the ticks. Scanning the whole file to find one
    would read a multi-megabyte log to answer a header question."""
    path = tmp_path / "headerless.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"record": "tick", "t_mono": 0.04}) + "\n")
        fh.write(json.dumps({"record": "header", "flight_id": "LATE"}) + "\n")
    assert dr._header_field(str(path), "flight_id") is None


def test_a_run_result_identifies_which_flight_it_came_from(tmp_path):
    """A path is not an identifier when the directory is gitignored."""
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    path = _write_log(
        tmp_path / "id.jsonl",
        {"stale_timeout_s": dict(build_runtime_stale_timeouts("px4")),
         "flight_id": "FLIGHT-XYZ", "csia_commit": "deadbeef"},
        [{"t_mono": 0.04, "canonical": {"channels": {}}, "gates": {},
          "trust_post": {}}])
    result = dr.replay(path, "px4")
    assert result["flight_id"] == "FLIGHT-XYZ"
    assert result["log_csia_commit"] == "deadbeef"
