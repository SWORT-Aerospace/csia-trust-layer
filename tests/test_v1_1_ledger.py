"""Phase 4C gate: the assurance ledger.

The two that matter most:

  * the ledger REPRODUCES -- same trace, config and software SHA, same event
    sequence including every id and hash (§17);
  * nothing here is described as more than a simple hash chain (§18).
"""

from __future__ import annotations

import json
import os

import pytest

from csia.v1_1 import advisory
from csia.v1_1 import reason_codes as RC
from csia.v1_1.ledger import (EVENT_TYPES, GENESIS, AssuranceLedger,
                              LedgerContext, Snapshot, suppression)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")


def _doc(name):
    p = os.path.join(ENG, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not built")
    return json.load(open(p, encoding="utf-8"))


def _ctx():
    return LedgerContext(platform="test", software_sha="deadbeef",
                         configuration_hash="c0ffee", input_trace_hash="1234",
                         trust_mode="FLAT_V1_1")


def _snap(**over):
    base = dict(
        t=1.0, assurance_state="NORMAL", support_state="EVIDENCE_BACKED",
        ambiguity="UNIQUE", leader="nominal", posterior=0.9,
        active_evidence_count=20, discriminating_evidence_count=3,
        leader_identifiable=True, prior_sensitive=False,
        trust={"gps": 0.9}, fresh={"gps": True}, missing_reason={},
        active_relations=("velocity_gps_doppler",), suppressed_relations=(),
        suppression_reasons={},
        sequential_state={"k": 0.5, "h": 500.0, "alarming": []},
        function_eligibility={"COARSE_NAVIGATION":
                              {"state": "ELIGIBLE",
                               "reason_codes": ["ALL_REQUIREMENTS_MET"]}},
        recommendations=())
    base.update(over)
    return Snapshot(**base)


# ------------------------------------------------------------------ §15
def test_only_a_change_opens_an_event():
    led = AssuranceLedger(_ctx())
    assert led.observe(_snap()) == []            # first tick seeds, emits none
    assert led.observe(_snap(t=1.04)) == []      # nothing changed
    evs = led.observe(_snap(t=1.08, assurance_state="CAUTION"))
    assert len(evs) == 1
    assert evs[0].event_type == "ASSURANCE_STATE_CHANGED"
    assert evs[0].previous_state == "NORMAL"


def test_every_event_type_is_defined_in_the_reason_code_table():
    assert set(EVENT_TYPES) == set(RC.ledger_event_types())


def test_the_within_tick_order_is_fixed():
    led = AssuranceLedger(_ctx())
    led.observe(_snap(function_eligibility={
        "B_FN": {"state": "ELIGIBLE", "reason_codes": []},
        "A_FN": {"state": "ELIGIBLE", "reason_codes": []}}))
    evs = led.observe(_snap(
        t=2.0, assurance_state="CAUTION", support_state="NON_IDENTIFIABLE",
        ambiguity="AMBIGUOUS",
        sequential_state={"k": 0.5, "h": 500.0, "alarming": ["gps"]},
        function_eligibility={
            "B_FN": {"state": "DEGRADED", "reason_codes": []},
            "A_FN": {"state": "DEGRADED", "reason_codes": []}}))
    assert [e.event_type for e in evs] == [
        "ASSURANCE_STATE_CHANGED", "FUNCTION_ELIGIBILITY_CHANGED",
        "FUNCTION_ELIGIBILITY_CHANGED", "SUPPORT_STATE_CHANGED",
        "AMBIGUITY_CHANGED", "SEQUENTIAL_STATE_CHANGED"]
    assert [e.subject for e in evs[1:3]] == ["A_FN", "B_FN"]


# ------------------------------------------------------------------ §16
def test_an_event_carries_every_required_field():
    led = AssuranceLedger(_ctx())
    led.observe(_snap())
    ev = led.observe(_snap(t=2.0, assurance_state="CAUTION"))[0].to_dict()
    for key in ("event_id", "timestamp", "event_type", "previous_state",
                "new_state", "reason_codes", "context", "snapshot",
                "content_sha256", "previous_event_hash", "sequence"):
        assert key in ev, key
    for key in ("platform", "software_sha", "configuration_hash",
                "input_trace_hash", "trust_mode"):
        assert key in ev["context"], key
    for key in ("fresh", "missing_reason", "active_relations",
                "suppressed_relations", "suppression_reasons", "trust",
                "sequential_state", "leader", "posterior",
                "active_evidence_count", "discriminating_evidence_count",
                "leader_identifiable", "ambiguity", "prior_sensitive",
                "function_eligibility", "assurance_state",
                "recommendations", "support_state"):
        assert key in ev["snapshot"], key


def test_suppression_names_a_stale_endpoint_rather_than_a_closed_gate():
    """Two different facts: the check did not apply, or a sensor went away."""
    act, sup, why = suppression(
        {"velocity_gps_doppler": 0.0, "heading_course": 0.0,
         "redundant_imu": 1.0},
        {"velocity_gps_doppler": ("imu0", "gps"),
         "heading_course": ("mag", "gps"), "redundant_imu": ("imu0", "imu1")},
        {"imu0": True, "imu1": True, "mag": True, "gps": False})
    assert act == ("redundant_imu",)
    assert set(sup) == {"velocity_gps_doppler", "heading_course"}
    assert why["velocity_gps_doppler"] == "ENDPOINT_NOT_FRESH:gps"

    _a, _s, why2 = suppression({"redundant_imu": 0.0},
                               {"redundant_imu": ("imu0", "imu1")},
                               {"imu0": True, "imu1": True})
    assert why2["redundant_imu"] == "GATE_CLOSED"


# ------------------------------------------------------------------ §17
def test_event_ids_are_deterministic_and_not_random():
    a, b = AssuranceLedger(_ctx()), AssuranceLedger(_ctx())
    for led in (a, b):
        led.observe(_snap())
        led.observe(_snap(t=2.0, assurance_state="CAUTION"))
    assert [e.to_dict() for e in a.events] == [e.to_dict() for e in b.events]
    assert a.events[0].event_id == b.events[0].event_id


def test_a_ledger_module_never_uses_a_random_identifier():
    """Parsed, not grepped: the docstring says the word 'random' precisely
    to explain that no random id is used, and a grep would match the
    explanation rather than the code."""
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "csia", "v1_1", "ledger.py"),
                          encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    for banned in ("uuid", "random", "secrets", "time", "datetime"):
        assert banned not in imported, banned
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for banned in ("uuid4", "now", "time", "monotonic"):
        assert banned not in names, banned


def test_the_reproduction_artifact_shows_every_mechanism_reproducing():
    d = _doc("ASSURANCE_LEDGER_REPRODUCTION.json")
    assert d["all_reproduced"] is True
    assert d["total_events"] == 159
    assert len(d["per_mechanism"]) == 9
    for mech, r in d["per_mechanism"].items():
        assert r["identical_on_rerun"] is True, mech
        assert r["chain_verified"] is True, mech
        assert r["chain_problems"] == [], mech
        assert r["event_count"] > 0, mech


# ------------------------------------------------------------------ §18
def test_the_chain_detects_a_reordered_or_edited_event():
    led = AssuranceLedger(_ctx())
    led.observe(_snap())
    for i, state in enumerate(("CAUTION", "CRITICAL", "EMERGENCY")):
        led.observe(_snap(t=2.0 + i, assurance_state=state))
    ok, problems = led.verify_chain()
    assert ok and not problems

    led.events[1].new_state = "TAMPERED"
    ok, problems = led.verify_chain()
    assert not ok
    assert any("content hash" in p for p in problems)

    led.events[1].new_state = "CAUTION"
    led.events[1], led.events[2] = led.events[2], led.events[1]
    ok, problems = led.verify_chain()
    assert not ok


def test_the_chain_starts_at_genesis():
    led = AssuranceLedger(_ctx())
    led.observe(_snap())
    led.observe(_snap(t=2.0, assurance_state="CAUTION"))
    assert led.events[0].previous_event_hash == GENESIS
    assert GENESIS == "0" * 64


def test_nothing_claims_to_be_a_blockchain():
    """Section 18. The capability is 'detect a missing or reordered event'."""
    src = open(os.path.join(ROOT, "csia", "v1_1", "ledger.py"),
               encoding="utf-8").read().lower()
    spec = open(os.path.join(ENG, "ASSURANCE_LEDGER_SPEC.md"),
                encoding="utf-8").read().lower()
    for text in (src, spec):
        assert "blockchain" in text          # it is addressed, not avoided
        for line in text.splitlines():
            if "blockchain" in line:
                assert any(k in line for k in ("not ", "never", "no ")), line
    d = _doc("ASSURANCE_LEDGER_REPRODUCTION.json")
    assert "not tamper-proof" in json.dumps(
        _doc("ASSURANCE_LEDGER_EXAMPLE.json")["chain_note"]).lower()
    assert d["all_reproduced"] is True


# ------------------------------------------------------------------ §19
def test_prose_is_rendered_from_a_code_and_is_not_the_record():
    led = AssuranceLedger(_ctx())
    led.observe(_snap())
    ev = led.observe(_snap(t=2.0, assurance_state="CAUTION"))[0]
    assert ev.render() == "assurance NORMAL -> CAUTION"
    assert "render" not in ev.to_dict()      # never stored as canonical


# ------------------------------------------------------------------ §24
def test_recommendations_are_advisory_and_from_a_closed_set():
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "csia", "v1_1", "advisory.py"),
                          encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    # it returns strings; it must not be able to reach a transport at all
    for banned in ("socket", "pymavlink", "serial", "requests", "http",
                   "urllib", "subprocess"):
        assert banned not in imported, banned

    all_states = ("ELIGIBLE", "DEGRADED", "INELIGIBLE", "UNKNOWN")
    seen = set()
    fns = ("COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION",
           "GEOFENCE_SUPPORT", "INERTIAL_CONTINUATION")
    for s in all_states:
        for lvl in range(4):
            seen.update(advisory.recommend({f: s for f in fns}, lvl))
    assert seen <= set(advisory.RECOMMENDATIONS)


def test_losing_every_gnss_function_recommends_the_inertial_fallback():
    r = advisory.recommend(
        {"COARSE_NAVIGATION": RC.INELIGIBLE, "POSITION_HOLD": RC.INELIGIBLE,
         "PRECISION_NAVIGATION": RC.INELIGIBLE,
         "GEOFENCE_SUPPORT": RC.INELIGIBLE,
         "INERTIAL_CONTINUATION": RC.ELIGIBLE}, 1)
    assert "SWITCH_NAV_INERTIAL" in r and "INHIBIT_GPS_MODES" in r
    assert "MANUAL_REVIEW" not in r

    gone = advisory.recommend(
        {"COARSE_NAVIGATION": RC.INELIGIBLE, "POSITION_HOLD": RC.INELIGIBLE,
         "PRECISION_NAVIGATION": RC.INELIGIBLE,
         "GEOFENCE_SUPPORT": RC.INELIGIBLE,
         "INERTIAL_CONTINUATION": RC.INELIGIBLE}, 1)
    assert "SWITCH_NAV_INERTIAL" not in gone
    assert "MANUAL_REVIEW" in gone


def test_a_healthy_tick_recommends_nothing():
    assert advisory.recommend(
        {"COARSE_NAVIGATION": RC.ELIGIBLE, "POSITION_HOLD": RC.ELIGIBLE,
         "PRECISION_NAVIGATION": RC.ELIGIBLE,
         "GEOFENCE_SUPPORT": RC.ELIGIBLE,
         "INERTIAL_CONTINUATION": RC.ELIGIBLE}, 0) == ()


# ----------------------------------------------------- the recorded event
def test_the_fix_loss_event_records_healthy_trust_with_no_support():
    """The result the whole layer exists for: GPS trust 0.987 and every GNSS
    function ineligible. If this stops holding, something has regressed."""
    d = _doc("ASSURANCE_LEDGER_EXAMPLE.json")
    assert d["mechanism"] == "GNSS_FIX_LOSS"
    hit = [e for e in d["events"]
           if e["event_type"] == "FUNCTION_ELIGIBILITY_CHANGED"
           and e["subject"] == "PRECISION_NAVIGATION"
           and e["new_state"] == "INELIGIBLE"]
    assert len(hit) == 1
    ev = hit[0]
    s = ev["snapshot"]
    assert ev["timestamp"] == 26.0
    assert s["trust"]["gps"] > 0.95, "the sensor still looks healthy"
    assert s["fresh"]["gps"] is False
    assert s["leader"] == "nominal" and s["posterior"] > 0.99
    assert s["leader_identifiable"] is False
    assert s["discriminating_evidence_count"] == 0
    assert s["support_state"] == "NON_IDENTIFIABLE"
    assert "SUPPORT_LOST_FOR_REQUIRED_INFORMATION" in ev["reason_codes"]
    assert s["function_eligibility"]["INERTIAL_CONTINUATION"]["state"] \
        == "ELIGIBLE"
    assert "SWITCH_NAV_INERTIAL" in s["recommendations"]
    for rel in ("velocity_gps_doppler", "heading_course", "altitude_baro"):
        assert s["suppression_reasons"][rel] == "ENDPOINT_NOT_FRESH:gps"


def test_the_example_ledger_verifies_end_to_end():
    d = _doc("ASSURANCE_LEDGER_EXAMPLE.json")
    prev = GENESIS
    for i, ev in enumerate(d["events"]):
        assert ev["sequence"] == i
        assert ev["previous_event_hash"] == prev
        assert len(ev["content_sha256"]) == 64
        assert len(ev["event_id"]) == 32
        prev = ev["content_sha256"]
    assert d["final_chain_hash"] == prev
    assert len(d["rendered"]) == len(d["events"])
