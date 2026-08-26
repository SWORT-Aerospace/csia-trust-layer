"""Invalidity masking: the source trace, the harness, and its null controls.

NON_SCORED_TEST_FIXTURE. Everything here is either a static read of committed
source or a synthetic message schedule. No simulator is launched.

The point of the null controls is that the harness must be capable of showing
NO masking. An instrument that reports masking on every input measures nothing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "research", "invalidity_masking", "results")
FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "research", "invalidity_masking", fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def H():
    return _load("_masking_harness", "masking_harness.py")


@pytest.fixture(scope="module")
def carrier(H):
    cap = H.load_fixture(FIXTURE)
    car, gps = H.carrier_and_gps(cap["messages"])
    # a short carrier keeps these tests to a few seconds each
    car = [m for m in car if float(m["_t_recv"]) <= 20.0]
    tmpl = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                and int(m.get("satellites_visible", 0) or 0) >= 10)
    return car, tmpl


# ------------------------------------------------- the source trace
def test_source_trace_still_matches_the_tree():
    """The 28 cited lines must still exist, exactly once each."""
    r = subprocess.run(
        [sys.executable,
         os.path.join(ROOT, "research", "invalidity_masking",
                      "source_to_gate_trace.py")],
        capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_gvalid_has_no_staleness_term_but_fresh_does():
    """The asymmetry the whole finding rests on, read from source."""
    src = open(os.path.join(ROOT, "csia", "runtime", "online.py"),
               encoding="utf-8").read()
    gvalid = [ln for ln in src.splitlines() if "gvalid = " in ln][0]
    assert "last_t" not in gvalid and "_stale" not in gvalid
    assert "fresh = {n: s[n].valid and s[n].seen" in src
    assert "(tau - s[n].last_t) <= self._stale[n]" in src


def test_valid_is_written_in_exactly_one_place():
    src = open(os.path.join(ROOT, "csia", "runtime", "online.py"),
               encoding="utf-8").read()
    writes = [ln for ln in src.splitlines()
              if ".valid = " in ln or ".valid=" in ln]
    assert len(writes) == 1, writes
    assert 'slot.valid = bool(ch.get("valid", True))' in writes[0]


def test_the_handoff_hardcodes_valid_true():
    src = open(os.path.join(ROOT, "csia", "aircraft", "adapters", "base.py"),
               encoding="utf-8").read()
    assert 'chans["valid"] = True' in src
    assert 'chans["valid"] = False' not in src


# ------------------------------------------------- null controls
def test_null_control_no_invalidity_means_no_masking(H, carrier):
    """P0. If nothing is ever invalid, nothing can be masked."""
    car, tmpl = carrier
    msgs = H.synth_stream(car, tmpl, lambda k, t: False, hz=5.0)
    out = H.replay(msgs, "DROP")
    rows = [r for r in out["rows"] if r["t"] >= 5.0]
    assert rows
    assert all(r["raw_obs_invalid"] == 0 for r in rows)
    assert all(r["fresh_gps"] == 1.0 for r in rows)


def test_null_control_permanent_invalidity_does_close_the_gate(H, carrier):
    """P5. The harness must be able to report a CLOSED gate."""
    car, tmpl = carrier
    msgs = H.synth_stream(car, tmpl, lambda k, t: t >= 12.0, hz=5.0)
    out = H.replay(msgs, "DROP")
    post = [r for r in out["rows"] if r["t"] >= 12.0]
    assert any(r["fresh_gps"] == 0.0 for r in post), \
        "an instrument that never reports a closed gate measures nothing"
    # and it closes one timeout after the last accepted sample, not sooner
    closed = [r for r in post if r["fresh_gps"] == 0.0]
    first_closed = min(r["t"] for r in closed)
    assert 12.0 <= first_closed <= 12.0 + H.GPS_STALE_TIMEOUT_S + 0.1


def test_null_control_the_harness_is_deterministic(H, carrier):
    """Two replays of one policy on one stream must be identical."""
    car, tmpl = carrier
    msgs = H.synth_stream(car, tmpl, lambda k, t: t >= 12.0, hz=5.0)
    a = H.replay(msgs, "DROP")["rows"]
    b = H.replay(msgs, "DROP")["rows"]
    assert a == b


# ------------------------------------------------- the mechanism
def test_a_single_dropped_fix_is_masked_at_5hz(H, carrier):
    """One rejected message leaves a 0.4 s gap, under the 0.5 s timeout."""
    car, tmpl = carrier
    msgs = H.synth_stream(car, tmpl, lambda k, t: 12.0 <= t < 12.1, hz=5.0)
    out = H.replay(msgs, "DROP")
    post = [r for r in out["rows"] if 11.0 <= r["t"] <= 14.0]
    inv = [r for r in post if r["raw_obs_invalid"] == 1]
    assert inv, "the schedule did not actually invalidate anything"
    assert all(r["fresh_gps"] == 1.0 for r in inv)


def test_the_gate_tracks_accepted_samples_not_invalid_ones(H, carrier):
    """The retained-state model: only ACCEPTED samples move last_t."""
    car, tmpl = carrier
    msgs = H.synth_stream(car, tmpl, lambda k, t: t >= 12.0, hz=5.0)
    out = H.replay(msgs, "DROP")
    post = [r for r in out["rows"] if r["t"] >= 13.0]
    # slot_last_t must have frozen: no accepted sample arrives after onset
    assert len({r["slot_last_t"] for r in post}) == 1
    # and slot.valid is still True the whole time, despite every observation
    # since onset reporting no fix
    assert all(r["slot_valid"] == 1 for r in post)
    assert all(r["gvalid"] == 1.0 for r in post), \
        "gvalid has no staleness term, so it cannot fall"


def test_propagate_invalid_closes_the_gate_where_drop_does_not(H, carrier):
    """The semantic control changes the outcome. If it did not, there would
    be no defect to report -- only a timeout."""
    car, tmpl = carrier
    msgs = H.synth_stream(car, tmpl,
                          lambda k, t: t >= 12.0 and (k % 5) < 4, hz=5.0)
    drop = H.summarise(H.replay(msgs, "DROP"), t_from=12.0)
    prop = H.summarise(H.replay(msgs, "PROPAGATE_INVALID_HOLD"), t_from=12.0)
    assert drop["n_ticks_last_obs_invalid"] > 0
    assert drop["masking_fraction"] > prop["masking_fraction"]
    assert prop["n_ticks_effective_gate_zero"] > \
        drop["n_ticks_effective_gate_zero"]


def test_the_two_arms_differ_only_in_the_validity_policy(H):
    """One class, one parameter: the control is not a second implementation."""
    from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
    assert issubclass(H.PropagateInvalidAdapter, ArduPilotAdapter)
    over = {n for n in vars(H.PropagateInvalidAdapter)
            if not n.startswith("__")}
    assert over == {"__init__", "_ingest_gps", "to_core_samples", "payload"} \
        or over <= {"__init__", "_ingest_gps", "to_core_samples", "payload"}, over


# ------------------------------------------------- the committed alternative
def test_the_repo_already_contains_both_semantics():
    """The v1 live-MAVLink path propagates invalidity; the v1.1 adapter drops
    it. Both are committed, and both feed the same frozen core."""
    plugins = open(os.path.join(ROOT, "csia", "runtime", "plugins.py"),
                   encoding="utf-8").read()
    assert "if msg.fix_type < 3:" in plugins
    assert '"vz_valid": False, "valid": False' in plugins
    ulog = open(os.path.join(ROOT, "csia", "runtime", "ulog_source.py"),
                encoding="utf-8").read()
    assert '"valid": bool(fix[i] >= 3)' in ulog
    ardu = open(os.path.join(ROOT, "csia", "aircraft", "adapters",
                             "ardupilot.py"), encoding="utf-8").read()
    assert 'self._latest.pop("gnss.position", None)' in ardu


# ------------------------------------------------- committed artifacts
@pytest.mark.skipif(not os.path.exists(os.path.join(
    RES, "INDISTINGUISHABILITY_CHECK.json")), reason="artifact not built")
def test_the_indistinguishability_result_is_recorded_as_measured():
    d = json.load(open(os.path.join(RES, "INDISTINGUISHABILITY_CHECK.json"),
                       encoding="utf-8"))
    assert d["core_state_identical"] is True
    assert d["n_differing_cells"] == 0
    assert d["adapter_retained_the_distinction"]["differ"] is True


@pytest.mark.skipif(not os.path.exists(os.path.join(
    RES, "BOUNDARY_SWEEP_RESULTS.csv")), reason="artifact not built")
def test_the_sweep_contains_both_masked_and_unmasked_outcomes():
    import csv
    rows = list(csv.DictReader(
        open(os.path.join(RES, "BOUNDARY_SWEEP_RESULTS.csv"),
             encoding="utf-8")))
    fracs = [float(r["masking_fraction"]) for r in rows
             if r["masking_fraction"]]
    assert max(fracs) == 1.0 and min(fracs) < 0.1, \
        "the sweep must span both outcomes or it is not a sweep"
    beyond = [int(r["model_n_disagree_beyond_one_tick_of_a_transition"])
              for r in rows]
    assert sum(beyond) == 0, (
        "the retained-state model disagreed with the core away from a "
        "transition; the model in RETAINED_STATE_MODEL.md would be wrong")
