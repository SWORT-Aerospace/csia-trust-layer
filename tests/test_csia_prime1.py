"""CSIA PRIME-1 (Pilot Launch + Product Hardening): permanent regressions. OFFBOARD.

research/csia_prime1/ has the evidence. These tests pin:
- D-PRIME-1: resolution-aware temporal admissibility (the successor) and the
  unchanged historical comparison;
- D-PRIME-2: bidirectional RPM-telemetry discovery with distinct event
  semantics, and the telemetry baseline-validity condition;
- that no simulation-only record (PX4's failure-injection message, SIH
  parameters) changes the successor's discovery or conclusions.

Every historical behaviour is pinned as an ordinary passing test: the defects
stay in release 2.3 by design (no historical output may change).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState as OS
from csia_evidence_assurance import (ADMISSIBLE, PRODUCER_INVALID, REGIME_INVALID, STALE,
                                     AnalysisContext, EvidenceEnvelope, Lineage, ProducerContract,
                                     ProducerHealth)
from csia_evidence_assurance import events as EV
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs
from csia_evidence_assurance.admissibility import check

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "research/csia_2_3_stock_bridge"))
from synthetic_stock import synth  # noqa: E402  (SYNTHETIC logs)

BASE = "aircraft-test"
US = 1e-6


# ------------------------------------------------------------------ helpers
def contract(pid="p:t", window=None, age=None):
    d = {"schema": "csia.evidence_contract/1", "producer_id": pid, "producer_version": "1",
         "contract_version": "c1",
         "claims": {"C": {"meaning": "t", "domain": "SENSOR", "relation": "t.r", "attributable": False,
                          "config_dependency": []}},
         "lineage": "PER_OUTPUT", "update": {"mode": "SNAPSHOT", "period_s": None}, "validity": {},
         "health_reporting": "REPORTED", "profile_compatibility": [BASE]}
    if window is not None:
        d["validity"].update({"event_window_s": [window[1], window[2]], "relative_to": window[0]})
    if age is not None:
        d["validity"]["max_content_age_s"] = age
    return ProducerContract.from_dict(d)


def envelope(ct, pt=None, pid="p:t"):
    r = EvidenceRecord(domain="SENSOR", component="x", relation="t.r", source="t",
                       observation_state=OS.DEGRADED, applicability=Applicability.APPLICABLE,
                       attributable=False)
    return EvidenceEnvelope(producer_id=pid, producer_version="1", contract_version="c1", claim="C",
                            record=r, lineage=Lineage.of("sensor:x"), content_time=ct,
                            producer_health=ProducerHealth.VALID,
                            produced_time=ct if pt is None else pt)


def status(env, c, t, events=None, res=US, producer_res=None):
    ctx = AnalysisContext(t, BASE, None, events or {}, res, producer_res or {})
    return check(env, {c.producer_id: c}, ctx)[0]


EV0 = 49.604                      # an event anchor on the 1 us grid
WIN = ("ev", 0.5, 15.0)


# ------------------------------------------------------------------ D-PRIME-1, the gate
@pytest.mark.parametrize("offset,expected", [
    (0.5, ADMISSIBLE),                      # exact lower boundary
    (15.0, ADMISSIBLE),                     # exact upper boundary
    (15.0 - US, ADMISSIBLE),                # just inside
    (0.5 + US, ADMISSIBLE),
    (15.0 + US, REGIME_INVALID),            # just outside: one tick is outside
    (0.5 - US, REGIME_INVALID),
    (15.0 + 0.4999 * US, ADMISSIBLE),       # the same tick at 1 us resolution
    (15.0 + 0.5001 * US, REGIME_INVALID),   # the next tick
    (15.0 + 1.0 * US, REGIME_INVALID),
])
def test_window_boundaries_are_decided_in_integer_ticks(offset, expected):
    assert status(envelope(EV0 + offset), contract(window=WIN), t=EV0 + 20, events={"ev": EV0}) == expected


@pytest.mark.parametrize("shift_us", [0.3, 0.4999, 0.5001, 0.7, 1.0, 2.7])
def test_equivalent_times_get_the_same_decision_when_anchor_and_content_move_together(shift_us):
    ev = EV0 + shift_us * US
    assert status(envelope(round(ev + 15.0, 6)), contract(window=WIN), t=ev + 20,
                  events={"ev": ev}) == ADMISSIBLE


def test_a_nanosecond_producer_is_compared_at_the_supported_resolution():
    c = contract(window=WIN)
    assert status(envelope(EV0 + 15.0 + 300e-9), c, t=EV0 + 20, events={"ev": EV0}) == ADMISSIBLE
    assert status(envelope(EV0 + 15.0 + 1.2e-6), c, t=EV0 + 20, events={"ev": EV0}) == REGIME_INVALID


def test_a_producer_declaring_a_coarser_clock_is_compared_at_its_resolution():
    c = contract(window=WIN)
    pr = {"p:t": 1e-3}
    assert status(envelope(EV0 + 15.0 + 0.4e-3), c, t=EV0 + 20, events={"ev": EV0}, producer_res=pr) == ADMISSIBLE
    assert status(envelope(EV0 + 15.0 + 0.6e-3), c, t=EV0 + 20, events={"ev": EV0}, producer_res=pr) == REGIME_INVALID


def test_a_negative_offset_window_keeps_its_boundaries():
    c = contract(window=("ev", -5.0, -0.5))
    for off, exp in ((-0.5, ADMISSIBLE), (-5.0, ADMISSIBLE), (-0.5 + US, REGIME_INVALID),
                     (-5.0 - US, REGIME_INVALID), (-2.0, ADMISSIBLE)):
        assert status(envelope(EV0 + off), c, t=EV0, events={"ev": EV0}) == exp, off


def test_each_output_is_judged_against_its_own_named_anchor():
    ca, cb = contract("p:a", window=("a", 0.0, 1.0)), contract("p:b", window=("b", 0.0, 1.0))
    events = {"a": 10.0, "b": 50.0}
    assert status(envelope(10.5, pid="p:a"), ca, t=60, events=events) == ADMISSIBLE
    assert status(envelope(10.5, pid="p:b"), cb, t=60, events=events) == REGIME_INVALID
    assert status(envelope(50.5, pid="p:b"), cb, t=60, events=events) == ADMISSIBLE


def test_an_out_of_order_record_is_impossible_only_beyond_the_resolution():
    c = contract()
    assert status(envelope(20.0, pt=20.0 - 0.3 * US), c, t=30) == ADMISSIBLE
    assert status(envelope(20.0, pt=20.0 - 2 * US), c, t=30) == PRODUCER_INVALID
    assert status(envelope(30.0 + 2 * US), c, t=30) == PRODUCER_INVALID       # content in the future


def test_a_stale_record_is_stale_from_the_next_tick():
    c = contract(age=2.0)
    assert status(envelope(28.0), c, t=30.0) == ADMISSIBLE
    assert status(envelope(28.0 - 0.4 * US), c, t=30.0) == ADMISSIBLE
    assert status(envelope(28.0 - US), c, t=30.0) == STALE


def test_the_historical_comparison_is_unchanged():
    """Release 2.3 (time_resolution_s None): float comparison with the 1 ns tolerance."""
    c = contract(window=WIN)
    ctx = AnalysisContext(EV0 + 20, BASE, None, {"ev": EV0})
    assert check(envelope(EV0 + 15.0 + 0.3 * US), {c.producer_id: c}, ctx)[0] == REGIME_INVALID
    assert check(envelope(EV0 + 15.0), {c.producer_id: c}, ctx)[0] == ADMISSIBLE


# ------------------------------------------------------------------ D-PRIME-1, end to end
def _report(log, release, **kw):
    run = runs.stock_flight(stock_log=log, est_log=None, release=release, **kw)
    return RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)


def _symptoms(m):
    return sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})


def _shifted(us):
    log = synth("motor")
    for d in log.topics.values():
        d["t"] = d["t"] + us * US
    return log


@pytest.mark.parametrize("us", [0.3, 0.4999, 0.5, 0.5001, 0.7, 1.0, 2.7])
def test_prime1_keeps_the_conclusion_under_sub_microsecond_shifts(us):
    m = _report(_shifted(us), "prime1")
    assert _symptoms(m) == ["COMMAND_NO_RESPONSE|motor_0"]
    assert m["final"]["evidence"]["rejected"] == []


def test_release_2_3_keeps_d_prime_1_as_recorded():
    m = _report(_shifted(0.7), "2.3")
    assert _symptoms(m) == [] and len(m["final"]["evidence"]["rejected"]) == 13


# ------------------------------------------------------------------ D-PRIME-2
def _tel(m, motor=2):
    return [v for v in m["evidence_values"] if v["record"] == f"ACTUATION/motor_{motor}:esc.telemetry_response"]


@pytest.mark.parametrize("scale,kind,code", [
    (0.5, EV.RPM_DEFICIT, "ESC_TELEMETRY_DEFICIT"), (0.9, EV.RPM_DEFICIT, "ESC_TELEMETRY_DEFICIT"),
    (1.1, EV.RPM_EXCESS, "ESC_TELEMETRY_EXCESS"), (2.0, EV.RPM_EXCESS, "ESC_TELEMETRY_EXCESS"),
    (10.0, EV.RPM_EXCESS, "ESC_TELEMETRY_EXCESS")])
def test_shortfall_and_excess_open_distinct_events_and_stay_telemetry(scale, kind, code):
    m = _report(synth("telemetry", motor=2, eta=scale * scale), "prime1")
    assert len(m["events"]) == 1 and m["events"][0]["trigger_kinds"] == [kind]
    trig = m["events"][0]["triggers"][0]
    assert trig["detail"]["semantics"] == EV.SEMANTICS[kind]
    assert any(v["state"] == "DEGRADED" and code in v["reason_codes"] for v in _tel(m))
    assert _symptoms(m) == []                      # a telemetry change is never a motor fault


def test_release_2_3_keeps_d_prime_2_as_recorded():
    m = _report(synth("telemetry", motor=2, eta=100.0), "2.3")
    assert m["events"] == [] and not any(v["state"] == "DEGRADED" for v in _tel(m))


def test_a_late_event_does_not_read_a_corrupted_reference_as_nominal():
    """RPM x 10 from 60 s; the analysis is anchored at 80 s, when BEFORE and AFTER are
    both corrupted (the late-event half of D-PRIME-2)."""
    log = synth("telemetry", motor=2, eta=100.0)
    late = _report(copy.deepcopy(log), "prime1", known_onsets=[80.0])
    assert {v["state"] for v in _tel(late)} == {"UNAVAILABLE"}
    assert all("TELEMETRY_BASELINE_INCONSISTENT" in v["reason_codes"] for v in _tel(late))
    hist = _report(copy.deepcopy(log), "2.3", known_onsets=[80.0])
    assert {v["state"] for v in _tel(hist)} == {"NOMINAL"}          # the recorded defect


def test_the_two_arms_are_separate_one_sided_cusums_not_an_absolute_value():
    import inspect
    src = inspect.getsource(EV.propulsion_triggers_prime1)
    assert "abs(" not in src and "d_tel_excess" in src and "RPM_EXCESS" in src and "RPM_DEFICIT" in src


# ------------------------------------------------------------------ Phase 7, no simulation leak
def _with_injection_message(log, t=60.0):
    log = copy.deepcopy(log)
    log.messages = list(log.messages) + [(t, "WARNING", "[failure_injection_manager] Injected: esc wrong, instances 3")]
    log.params = dict(log.params, SIH_MOT_EFF3=0.6)
    return log


@pytest.mark.parametrize("kind,eta", [("telemetry", 100.0), ("motor", 0.6), ("nominal", 1.0)])
def test_an_injection_message_or_sih_parameter_changes_nothing_in_the_product(kind, eta):
    base = synth(kind, motor=2, eta=eta)
    a = _report(copy.deepcopy(base), "prime1")
    b = _report(_with_injection_message(base), "prime1")
    strip = lambda m: [(e["t0"], e["trigger_kinds"]) for e in m["events"]]  # noqa: E731
    assert strip(a) == strip(b)
    assert _symptoms(a) == _symptoms(b)
    assert a["summary"]["attribution"] == b["summary"]["attribution"]
    assert a["evidence_values"] == b["evidence_values"]
    assert a["inputs"]["event_discovery"]["test_harness_messages_ignored"] == 0
    assert b["inputs"]["event_discovery"]["test_harness_messages_ignored"] == 1


def test_the_releases_are_distinguishable_in_every_report():
    """Release 2.3 adds no PRIME-1 field to a report (historical bytes stay identical);
    the successor names its release and its telemetry producer's own version."""
    h = _report(synth("motor"), "2.3")
    assert "release" not in h["inputs"] and "event_discovery" not in h["inputs"]
    assert h["contracts"]["px4:esc.telemetry_response"]["producer_version"] == "csia-2.3-stock-r1"
    s = _report(synth("motor"), "prime1")
    assert s["inputs"]["release"] == "prime1" and s["inputs"]["time_resolution_s"] == 1e-6
    assert s["contracts"]["px4:esc.telemetry_response"]["producer_version"] == "csia-prime1-stock-tel-r1"
    assert s["contracts"]["px4:allocator.compensation"]["producer_version"] == "csia-2.3-stock-r1"
