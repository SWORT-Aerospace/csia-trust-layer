"""Phase 4.5 Gate C: the real schema consumer.

The two that matter most:

  * the fix-loss payload is not reduced to "GPS healthy" or "nominal 99%"
    (§15), and the primary status is structurally incapable of reading the
    posterior;
  * nothing is parsed permissively (§16).
"""

from __future__ import annotations

import ast
import copy
import json
import os

import pytest

from csia.deploy.guard import CommandAuthorityError
from csia.v1_1 import output_api as API
from csia.v1_1 import reason_codes as RC
from csia.v1_1.monitor import (Monitor, MonitorView, PayloadRejected,
                               parse)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")


def _payload(name):
    p = os.path.join(ENG, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not built")
    return json.load(open(p, encoding="utf-8"))


def _results():
    p = os.path.join(ENG, "API_CONSUMER_RESULTS.json")
    if not os.path.exists(p):
        pytest.skip("Gate C results not built")
    return json.load(open(p, encoding="utf-8"))


# ------------------------------------------------------------------- §13
def test_the_consumer_imports_no_producer():
    """Not another source of truth. If it could reach the trust engine or the
    eligibility policy it could recompute, and the schema would never be
    tested for sufficiency."""
    tree = ast.parse(open(os.path.join(ROOT, "csia", "v1_1", "monitor.py"),
                          encoding="utf-8").read())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add((node.module or "") + "".join(
                "." + a.name for a in node.names))
        elif isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
    banned = ("trust_engine", "diagnosis", "eligibility", "ledger",
              "scenarios", "online", "advisory", "staleness", "adapters")
    for mod in modules:
        for b in banned:
            assert b not in mod, (mod, b)


def test_the_consumer_reads_a_real_stream_from_a_real_file():
    r = _results()
    assert r["payloads_accepted"] == 2
    assert r["payloads_rejected"] == 0
    assert os.path.exists(os.path.join(ROOT, r["stream"]))


# ------------------------------------------------------------------- §14
def test_every_required_view_field_is_surfaced():
    view = parse(_payload("csia_output_fixloss_example.json"))
    rendered = view.render()
    row = view.to_row()
    for key in ("timestamp", "assurance", "leader", "posterior",
                "support_state", "ambiguity", "active_evidence_count",
                "discriminating_evidence_count", "sequential_alarms",
                "recommendations", "function_eligibility"):
        assert key in row, key
    assert view.ledger_event is not None
    for name in view.function_eligibility:
        assert name in rendered


# ------------------------------------------------------------------- §15
def test_the_fix_loss_payload_is_not_reduced_to_gps_healthy():
    """THE section 15 test. The payload says gps trust 0.987 and nominal at
    p=0.9925. A consumer leading with either would be reporting a healthy
    GPS while four of five functions were unavailable."""
    view = parse(_payload("csia_output_fixloss_example.json"))
    assert view.trust["gps"] > 0.95
    assert view.posterior > 0.99
    assert view.support_state == "NON_IDENTIFIABLE"

    status = view.primary_status
    assert "4 OF 5 FUNCTIONS UNAVAILABLE" in status
    assert "NON_IDENTIFIABLE" in status
    for word in ("healthy", "ok", "nominal", "fine", "99"):
        assert word not in status.lower(), (word, status)
    assert f"{view.posterior:.4f}" not in status


def test_the_primary_status_cannot_read_the_posterior():
    """Structural, not a wording check: two views identical except for the
    posterior must produce the same primary status."""
    payload = _payload("csia_output_fixloss_example.json")
    a = parse(payload)
    other = copy.deepcopy(payload)
    other["diagnosis"]["posterior"] = 0.0001
    b = parse(other)
    assert a.posterior != b.posterior
    assert a.primary_status == b.primary_status


def test_the_posterior_is_never_rendered_without_its_support_qualifier():
    for name in ("csia_output_example.json",
                 "csia_output_fixloss_example.json"):
        view = parse(_payload(name))
        line = view.format_leader()
        assert f"{view.posterior:.4f}" in line
        assert view.support_state in line, name
        assert str(view.discriminating_evidence_count) in line, name
        assert view.ambiguity in line, name
        assert line in view.render()


def test_a_clean_payload_says_all_functions_available():
    view = parse(_payload("csia_output_example.json"))
    assert view.primary_status == "ALL FUNCTIONS AVAILABLE"
    assert view.unavailable == ()


def test_an_undetermined_eligibility_asks_for_a_human():
    payload = copy.deepcopy(_payload("csia_output_example.json"))
    first = sorted(payload["function_eligibility"])[0]
    payload["function_eligibility"][first]["state"] = "UNKNOWN"
    view = parse(payload)
    assert "MANUAL REVIEW" in view.primary_status
    assert RC.SEVERITY_RANK[RC.UNKNOWN] > RC.SEVERITY_RANK[RC.INELIGIBLE]


# ------------------------------------------------------------------- §16
@pytest.mark.parametrize("case", [
    "unknown_schema_version", "malformed_payload", "missing_required_field",
    "sequential_kh_mismatch", "unknown_trust_mode", "unknown_function_state"])
def test_every_negative_case_was_rejected(case):
    rows = {n["case"]: n for n in _results()["negative_tests"]}
    assert rows[case]["rejected"] is True, rows[case]


def test_no_permissive_parsing_anywhere():
    assert _results()["all_negative_tests_rejected"] is True


def test_an_unknown_schema_version_is_refused_not_coerced():
    payload = dict(_payload("csia_output_example.json"),
                   schema_version="2.0.0")
    with pytest.raises(PayloadRejected) as exc:
        parse(payload)
    assert "2.0.0" in str(exc.value)


def test_a_retuned_detector_is_refused():
    """k/h are the frozen detector's. A payload carrying the textbook h=5.0
    came from a different detector and must not be read as this one."""
    payload = copy.deepcopy(_payload("csia_output_example.json"))
    payload["sequential"]["h"] = 5.0
    with pytest.raises(PayloadRejected):
        parse(payload)


def test_a_missing_required_field_is_not_defaulted():
    payload = copy.deepcopy(_payload("csia_output_example.json"))
    del payload["diagnosis"]["posterior"]
    with pytest.raises(PayloadRejected):
        parse(payload)


def test_an_unknown_function_state_is_refused():
    payload = copy.deepcopy(_payload("csia_output_example.json"))
    first = sorted(payload["function_eligibility"])[0]
    payload["function_eligibility"][first]["state"] = "PROBABLY_FINE"
    with pytest.raises(PayloadRejected) as exc:
        parse(payload)
    assert "PROBABLY_FINE" in str(exc.value)


def test_an_unknown_reason_code_is_refused():
    payload = copy.deepcopy(_payload("csia_output_example.json"))
    first = sorted(payload["function_eligibility"])[0]
    payload["function_eligibility"][first]["reason_codes"] = ["MADE_UP_CODE"]
    with pytest.raises(PayloadRejected):
        parse(payload)


def test_a_rejection_is_recorded_rather_than_raised_to_the_stream():
    """A stream consumer must survive one bad line and say which."""
    mon = Monitor()
    assert mon.consume(dict(_payload("csia_output_example.json"),
                            schema_version="9.9.9")) is None
    assert mon.accepted == 0 and len(mon.rejected) == 1
    assert mon.consume(_payload("csia_output_example.json")) is not None
    assert mon.accepted == 1


# ------------------------------------------------------------------- §17
def test_a_v1_consumer_takes_the_projection_or_refuses_the_payload():
    c = _results()["compatibility"]
    assert c["projection_accepted"] is True
    assert c["raw_v1_1_accepted_by_v1_consumer"] is False
    assert c["version_mismatch_refused"] is True
    assert c["projection_carries_trust_mode"] is True


def test_the_projection_never_hides_which_architecture_produced_it():
    payload = _payload("csia_output_example.json")
    v1 = API.project_v1(payload)
    assert v1["trust_mode"] == "FLAT_V1_1"
    assert "_v1_compat_note" in v1


# ------------------------------------------------------------------- §18
def test_every_control_attempt_through_the_monitor_is_denied():
    mon = Monitor()
    for op in ("SET_FLIGHT_MODE", "WRITE_PARAMETER", "RTL", "LAND",
               "SOMETHING_NOBODY_HAS_WRITTEN_YET"):
        with pytest.raises(CommandAuthorityError):
            mon.act(op)
    assert set(mon.firewall.denied_attempts) == {
        "SET_FLIGHT_MODE", "WRITE_PARAMETER", "RTL", "LAND",
        "SOMETHING_NOBODY_HAS_WRITTEN_YET"}
    assert mon.evidence()["firewall"]["policy"] == "DEFAULT_DENY"


def test_the_denied_attempts_are_recorded_in_the_evidence():
    r = _results()["firewall"]
    assert r["all_control_denied"] is True
    assert set(r["evidence"]["denied_attempts"]) == {
        "SET_FLIGHT_MODE", "WRITE_PARAMETER", "RTL", "LAND",
        "SOMETHING_NOBODY_HAS_WRITTEN_YET"}
    assert all(p["allowed"] for p in _results()["firewall"]["permitted"])


def test_consuming_a_payload_goes_through_the_firewall():
    """There is no branch that bypasses it."""
    mon = Monitor()
    mon.consume(_payload("csia_output_example.json"))
    assert "EMIT_OUTPUT" in mon.firewall.evidence()["permitted_operations"]
    assert mon.firewall.denied_attempts == []


def test_the_monitor_holds_no_transport():
    tree = ast.parse(open(os.path.join(ROOT, "csia", "v1_1", "monitor.py"),
                          encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    for banned in ("socket", "pymavlink", "serial", "requests", "urllib",
                   "http", "subprocess"):
        assert banned not in imported, banned


# ------------------------------------------------------------------ gates
def test_gate_e_and_gate_f_passed():
    r = _results()
    assert r["gate_E_consumer_pass"] is True
    assert r["gate_F_firewall_pass"] is True
    fix = r["fix_loss_interpretation"]
    assert fix["primary_status_mentions_healthy"] is False
    assert fix["primary_status_mentions_posterior"] is False
    assert fix["posterior_never_rendered_bare"] is True
    assert fix["gps_trust_in_payload"] > 0.95
    assert len(fix["functions_unavailable"]) == 4
    assert "SWITCH_NAV_INERTIAL" in fix["recommendations"]


def test_the_view_is_serialisable():
    view = parse(_payload("csia_output_fixloss_example.json"))
    json.dumps(view.to_row())
    assert isinstance(view, MonitorView)
