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


# ------------------------------------------------------------------ Phases 13-15: support before interpretation
from csia_evidence_assurance import engagement as EN  # noqa: E402
from csia_evidence_assurance import support_prime1 as SP1  # noqa: E402
from csia_evidence_assurance import view_prime1 as V1  # noqa: E402

QUAD = {"readable": True, "hardware": "PX4_SITL", "px4_git": "547e2caa98", "px4_release": None,
        "sys_autostart": 10040, "ca_rotor_count": 4, "vehicle_type": 1, "is_vtol": False,
        "topics": sorted(SP1.PROPULSION_TOPICS + ("battery_status",)), "intervals": {},
        "esc_rpm_present": True, "dropouts": 0, "gyro_mean_while_landed_rad_s": [0.0, 0.0, 0.0]}


@pytest.mark.parametrize("change,state", [
    ({}, "SUPPORTED"),
    ({"vehicle_type": 3, "sys_autostart": 50005, "ca_rotor_count": None}, "UNSUPPORTED_VEHICLE_CONFIGURATION"),
    ({"vehicle_type": 2}, "UNSUPPORTED_VEHICLE_CONFIGURATION"),
    ({"is_vtol": True, "sys_autostart": 13014}, "UNSUPPORTED_VEHICLE_CONFIGURATION"),
    ({"ca_rotor_count": 6}, "UNSUPPORTED_VEHICLE_CONFIGURATION"),
    ({"topics": ["battery_status"]}, "UNSUPPORTED_SCHEMA"),
    ({"px4_git": "fd483321a5"}, "UNKNOWN_VERSION"),
    ({"px4_git": "cb09dde606", "px4_release": "v1.15.0-dev"}, "PARTIAL"),
    ({"ca_rotor_count": None}, "PARTIAL"),
    ({"esc_rpm_present": False}, "PARTIAL"),
    ({"gyro_mean_while_landed_rad_s": [0.0, 0.0, 0.067]}, "PARTIAL"),
    ({"dropouts": 2}, "PARTIAL"),
])
def test_support_states_are_decided_before_interpretation(change, state):
    r = SP1.check(dict(QUAD, **change))
    assert r["status"] == state
    assert r["interpretation"] == ("WITHHELD" if state in ("UNSUPPORTED_VEHICLE_CONFIGURATION",
                                                           "UNSUPPORTED_SCHEMA") else "FULL")


def test_an_unsupported_vehicle_is_described_not_called_broken():
    r = SP1.check(dict(QUAD, vehicle_type=3, sys_autostart=50005, ca_rotor_count=None))
    v = r["vehicle"]
    assert v["detected"] == "rover or boat" and v["requested_profile"] == "multirotor-quad r1"
    assert v["supported_vehicle_classes"] and r["generic_analysis_safe"]
    text = V1.generic_text("boat.ulg", r, {"log_integrity": {}, "alerts": []})
    assert "INTERPRETATION WITHHELD" in text and "not judged broken" in text
    assert "COMMAND_NO_RESPONSE" not in text


def test_an_unreadable_file_is_an_unsupported_schema_not_a_crash(tmp_path):
    f = tmp_path / "not_a_log.ulg"
    f.write_bytes(b"this is not a ULog")
    r = SP1.check(SP1.inspect(f))
    assert r["status"] == "UNSUPPORTED_SCHEMA" and r["interpretation"] == "WITHHELD"


def test_the_support_contract_claims_no_physical_validation_and_names_the_defects():
    c = SP1.contract()
    assert {x["validation_level"] for x in c["configurations"]} <= {"SIMULATION", "HIL", "REAL_LOG_CONTEXT_ONLY"}
    assert all(v["validation_level"] != "PHYSICAL_VALIDATED" for v in c["telemetry_classes"].values())
    assert {d["id"]: d["fixed_in"] for d in c["known_defects"]} == {"D-PRIME-1": "prime1", "D-PRIME-2": "prime1"}
    for x in c["configurations"]:
        assert x["state"] in c["states"] and x.get("evidence"), x["id"]


# ------------------------------------------------------------------ Phases 16-17: receipts and first page
RECEIPT_KEYS = {"type", "conclusion", "status", "supporting_evidence", "refuting_evidence", "rejected_evidence",
                "rejection_reasons", "source_lineage", "independent_line_count", "producer_health",
                "content_time_s", "configuration_epoch", "coverage", "would_resolve", "version"}
SECTIONS = ("1. WHAT HAPPENED", "2. WHEN", "3. WHAT CSIA CAN JUSTIFY", "4. WHAT CSIA CANNOT JUSTIFY", "5. WHY",
            "6. KEY EVIDENCE", "7. EVIDENCE REJECTED", "8. DEPENDENCY / SHARED SOURCES",
            "9. MISSING INSTRUMENTATION", "10. NEXT ENGINEERING CHECK", "TECHNICAL DETAIL")


@pytest.fixture(scope="module")
def motor_view():
    m = _report(synth("motor"), "prime1")
    return m, V1.build(m, SP1.check(QUAD))


def test_every_conclusion_has_a_complete_receipt(motor_view):
    m, v = motor_view
    kinds = [r["type"] for r in v["receipts"]]
    assert "SYMPTOM" in kinds and "ATTRIBUTION" in kinds
    for r in v["receipts"]:
        assert RECEIPT_KEYS <= set(r), (r["type"], RECEIPT_KEYS - set(r))
        assert r["version"]["release"] == "prime1" and r["version"]["view"] == V1.VIEW_VERSION
    sym = next(r for r in v["receipts"] if r["type"] == "SYMPTOM")
    assert sym["independent_line_count"] == 2 and sym["content_time_s"] and sym["coverage"]


def test_the_first_page_keeps_the_engineers_order_and_no_confidence_figures(motor_view):
    _m, v = motor_view
    t = v["summary_text"]
    pos = [t.index(s) for s in SECTIONS]
    assert pos == sorted(pos)
    low = t.lower()
    assert "%" not in t and not any(w in low for w in ("probab", "confiden", "likel"))
    assert "COMMAND_NO_RESPONSE on motor_0: AMBIGUOUS" in t


def test_the_view_and_receipts_are_deterministic():
    m1 = _report(synth("motor"), "prime1")
    m2 = _report(synth("motor"), "prime1")
    a, b = V1.build(m1, SP1.check(QUAD)), V1.build(m2, SP1.check(QUAD))
    assert RP.dumps(a["receipts"]) == RP.dumps(b["receipts"]) and a["summary_text"] == b["summary_text"]


# ------------------------------------------------------------------ Phase 27: the engagement workflow
def test_the_engagement_enforces_the_blind_protocol(tmp_path):
    d = tmp_path / "eng"
    EN.init(d, "T", "blind")
    assert (d / ".gitignore").read_text().strip().endswith("*")
    f = tmp_path / "flight.ulg"
    f.write_bytes(b"not a real log: analysed as UNSUPPORTED_SCHEMA")
    with pytest.raises(EN.EngagementError):
        EN.ingest(d, f, {"expected_event_time_s": 50.0})
    r = EN.ingest(d, f, {"esc_telemetry": "yes"})
    assert r["sha256"] == EN._sha(f)
    diag = tmp_path / "diag.json"
    diag.write_text('{"flight.ulg": "truth"}')
    with pytest.raises(EN.EngagementError):
        EN.reveal(d, diag)
    runs_ = EN.run(d)
    assert runs_["runs"]["flight.ulg"]["interpretation"] == "WITHHELD"
    s = EN.seal(d)
    with pytest.raises(EN.EngagementError):
        EN.run(d)
    assert EN.reveal(d, diag)["after_seal_sha256"] == s["seal_sha256"]
    assert EN.verify(d)["ok"]
    out = d / "derived/flight/assurance_summary.txt"
    out.chmod(0o644)
    out.write_text(out.read_text() + "tampered\n")
    assert not EN.verify(d)["ok"]


def test_customer_logs_are_ignored_by_git():
    gi = (REPO / ".gitignore").read_text()
    assert "*.ulg" in gi and "engagements/" in gi and "customer_data/" in gi
