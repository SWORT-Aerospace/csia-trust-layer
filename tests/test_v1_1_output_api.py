"""Phase 4D gate: the versioned output API and the output firewall.

The two that matter most:

  * no field is ever silently reinterpreted across a schema version (§26);
  * every write and control operation is denied, by default-deny (§25).
"""

from __future__ import annotations

import json
import os

import jsonschema
import pytest

from csia.deploy.guard import CommandAuthorityError
from csia.v1_1 import firewall as FW
from csia.v1_1 import output_api as API

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")


def _example(name="csia_output_example.json"):
    p = os.path.join(ENG, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not built")
    return json.load(open(p, encoding="utf-8"))


# ------------------------------------------------------------------ §20
def test_the_schema_itself_is_valid_and_closed():
    s = API.schema()
    jsonschema.Draft202012Validator.check_schema(s)
    assert s["additionalProperties"] is False, (
        "a schema that accepts unknown fields is not a contract")
    for name, sub in s["properties"].items():
        if sub.get("type") == "object" and "properties" in sub:
            assert sub.get("additionalProperties") is False, name


def test_the_top_level_fields_are_the_ones_section_20_names():
    props = set(API.schema()["properties"])
    assert props == {
        "schema_version", "timestamp", "platform", "assurance", "trust",
        "sequential", "diagnosis", "support", "ambiguity", "evidence",
        "function_eligibility", "recommendations", "provenance_summary",
        "ledger_event"}


def test_every_scenario_payload_validated():
    d = json.load(open(os.path.join(ENG, "PHASE4_API_VALIDATION.json"),
                       encoding="utf-8"))
    assert d["all_valid"] is True
    assert d["mechanisms"] == 9
    assert d["payloads_validated"] == 13500
    assert d["schema_version"] == "1.1.0"


def test_the_examples_validate():
    for name in ("csia_output_example.json",
                 "csia_output_fixloss_example.json"):
        API.validate(_example(name))


# ------------------------------------------------------------------ §21
def test_the_diagnosis_block_carries_every_required_field():
    d = _example()["diagnosis"]
    for key in ("leader", "posterior", "runner_up", "score_margin",
                "active_evidence_count", "discriminating_evidence_count",
                "identifiable", "ambiguity", "prior_sensitive",
                "support_state"):
        assert key in d, key


# ------------------------------------------------------------------ §22
def test_the_field_is_posterior_and_never_confidence():
    schema_text = json.dumps(API.schema())
    assert '"posterior"' in schema_text
    payload = _example()
    assert "posterior" in payload["diagnosis"]

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                assert "confidence" not in k.lower(), k
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(payload)


def test_the_fix_loss_payload_shows_posterior_without_support():
    """The case that makes the naming decision matter."""
    p = _example("csia_output_fixloss_example.json")
    assert p["timestamp"] == 26.0
    assert p["diagnosis"]["posterior"] > 0.99
    assert p["diagnosis"]["discriminating_evidence_count"] == 0
    assert p["diagnosis"]["identifiable"] is False
    assert p["diagnosis"]["support_state"] == "NON_IDENTIFIABLE"
    assert p["trust"]["nodes"]["gps"] > 0.95
    assert p["evidence"]["fresh"]["gps"] is False
    for f in ("COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION",
              "GEOFENCE_SUPPORT"):
        assert p["function_eligibility"][f]["state"] == "INELIGIBLE", f
    assert p["function_eligibility"]["INERTIAL_CONTINUATION"]["state"] \
        == "ELIGIBLE"
    assert "SWITCH_NAV_INERTIAL" in p["recommendations"]


# ------------------------------------------------------------------ §23
def test_each_function_reports_state_reasons_and_support():
    for name, row in _example()["function_eligibility"].items():
        for key in ("state", "reason_codes", "required_inputs_available",
                    "support_sufficient"):
            assert key in row, (name, key)
        assert row["state"] in ("ELIGIBLE", "DEGRADED", "INELIGIBLE",
                               "UNKNOWN")


# --------------------------------------------------------------- §8 / §34
def test_the_two_unknowns_never_share_a_field():
    p = _example()
    assert p["diagnosis"]["unknown_fault_model"] == "NOT_IMPLEMENTED"
    assert (API.schema()["properties"]["diagnosis"]["properties"]
            ["unknown_fault_model"]["const"] == "NOT_IMPLEMENTED")
    states = {r["state"] for r in p["function_eligibility"].values()}
    assert states <= {"ELIGIBLE", "DEGRADED", "INELIGIBLE", "UNKNOWN"}


# ------------------------------------------------------------------ §26
def test_a_version_mismatch_is_refused_loudly():
    p = _example()
    API.assert_schema_version(p)
    bad = dict(p, schema_version="2.0.0")
    with pytest.raises(API.SchemaVersionError):
        API.assert_schema_version(bad)
    with pytest.raises(API.SchemaVersionError):
        API.project_v1(bad)


def test_the_v1_projection_never_hides_the_trust_mode():
    """A v1 consumer quietly receiving FLAT trajectories believing them to be
    v1's is the silent reinterpretation section 26 forbids."""
    v1 = API.project_v1(_example())
    assert v1["trust_mode"] == "FLAT_V1_1"
    assert "_v1_compat_note" in v1
    assert set(v1) == {"t", "level", "trust", "trust_mode", "posterior",
                       "leader", "_v1_compat_note"}


def test_the_projection_does_not_rename_or_reinterpret():
    p = _example()
    v1 = API.project_v1(p)
    assert v1["t"] == p["timestamp"]
    assert v1["level"] == p["assurance"]["level"]
    assert v1["posterior"] == p["diagnosis"]["posterior"]
    assert v1["leader"] == p["diagnosis"]["leader"]
    assert v1["trust"] == p["trust"]["nodes"]


# ------------------------------------------------------------------ §28
def test_current_valid_is_versioned_rather_than_a_bare_field():
    p = _example()
    assert "current_valid" in p["evidence"]
    spec = API.schema()["properties"]["evidence"]["properties"]
    assert spec["current_valid"]["type"] == ["boolean", "null"]
    assert set(spec["missing_reason"]["additionalProperties"]["enum"]) == {
        "NOT_RECEIVED", "STALE", "SENTINEL", "NO_3D_FIX"}
    t = open(os.path.join(ENG, "API_COMPATIBILITY.md"),
             encoding="utf-8").read()
    assert "No unversioned semantic change survives Phase 4" in t


def test_a_payload_with_an_unknown_field_fails_validation():
    p = dict(_example(), surprise=1)
    with pytest.raises(jsonschema.ValidationError):
        API.validate(p)


def test_the_sequential_constants_are_pinned_by_the_schema():
    p = _example()
    assert p["sequential"]["k"] == 0.5 and p["sequential"]["h"] == 500.0
    bad = json.loads(json.dumps(p))
    bad["sequential"]["h"] = 5.0
    with pytest.raises(jsonschema.ValidationError):
        API.validate(bad)


def test_provenance_rides_on_every_payload():
    prov = _example()["provenance_summary"]
    for key in ("software_sha", "configuration_hash", "trust_mode",
                "frozen_core_tag"):
        assert prov[key], key
    assert prov["authority"] == "READ_ONLY"
    assert prov["frozen_core_tag"] == "csia-v1.0-research-final"


# ------------------------------------------------------------------ §25
def test_the_firewall_denies_every_named_control_operation():
    fw = FW.OutputFirewall()
    for op in ("WRITE_PARAMETER", "SET_FLIGHT_MODE", "WRITE_MISSION",
               "CLEAR_MISSION", "ACTUATOR_COMMAND", "SET_SERVO", "ARM",
               "DISARM", "RTL", "LAND", "TAKEOFF", "REBOOT_AUTOPILOT",
               "SET_HOME", "CALIBRATE"):
        with pytest.raises(CommandAuthorityError):
            fw.request(op)
        assert not fw.permits(op), op
    assert len(fw.denied_attempts) == 14


def test_the_firewall_permits_reading_and_logging():
    fw = FW.OutputFirewall()
    for op in ("READ_TELEMETRY", "READ_PARAMETERS", "WRITE_LOG", "READ_LOG",
               "EMIT_OUTPUT", "EMIT_RECOMMENDATION"):
        assert fw.request(op) == op
    assert fw.denied_attempts == []


def test_the_firewall_is_default_deny():
    """An operation invented tomorrow must be denied today."""
    fw = FW.OutputFirewall()
    for op in ("SOMETHING_NOBODY_HAS_WRITTEN_YET", "", "read_telemetry",
               "MAV_CMD_NAV_LAND", "WRITE_ANYTHING"):
        with pytest.raises(CommandAuthorityError):
            fw.request(op)


def test_every_denied_operation_is_recorded_before_it_raises():
    """A swallowed command attempt hides the more important half of the
    event: that one was attempted."""
    fw = FW.OutputFirewall()
    with pytest.raises(CommandAuthorityError):
        fw.request("RTL")
    assert fw.denied_attempts == ["RTL"]
    assert "RTL" in fw.evidence()["denied_attempts"]
    assert fw.evidence()["policy"] == "DEFAULT_DENY"


def test_the_firewall_composes_with_the_existing_transport_guard():
    class _Conn:
        mav = object()
        port = None

        def recv_match(self, **kw):
            return None
    fw = FW.OutputFirewall()
    conn = fw.attach(_Conn())
    with pytest.raises(CommandAuthorityError):
        conn.mav.command_long_send()
    with pytest.raises(CommandAuthorityError):
        conn.set_mode("GUIDED")
    assert conn.recv_match() is None


def test_the_permitted_and_denied_sets_do_not_overlap():
    assert not (FW.PERMITTED & set(FW.DENIED))


# ------------------------------------------------------------------ §29
def test_compute_separates_core_from_reporting():
    d = json.load(open(os.path.join(ENG, "PHASE4_COMPUTE.json"),
                       encoding="utf-8"))
    ph = d["phases_us_per_tick"]
    assert set(ph) == {"core_trust_step", "core_sequential_step",
                       "support_metadata", "function_eligibility",
                       "ledger_event", "api_build", "api_serialize"}
    assert d["core_us_per_tick"] > 0 and d["reporting_us_per_tick"] > 0
    assert abs(d["core_us_per_tick"]
               - ph["core_trust_step"]["median_us"]
               - ph["core_sequential_step"]["median_us"]) < 1e-6
    assert "NO TARGET-HARDWARE FIGURE EXISTS" in d["note"]


# ------------------------------------------------------------------ §37
def test_the_golden_trace_plan_freezes_cases_not_numbers():
    t = open(os.path.join(ROOT, "embedded", "v1_1", "GOLDEN_TRACE_PLAN.md"),
             encoding="utf-8").read()
    assert "Nothing is implemented here" in t
    assert "no numerical value is frozen" in t
    assert "There is no C code in this repository" in t
    assert "The tolerance is not declared here and must not be guessed" in t
    for case in ("GNSS_FIX_LOSS", "DUAL_IMU_FAILURE", "BATTERY_SENTINEL",
                 "MAG_SENTINEL"):
        assert case in t, case


def test_no_c_source_was_added():
    """Section 36: no C production implementation in this phase."""
    emb = os.path.join(ROOT, "embedded")
    found = [f for _d, _s, fs in os.walk(emb) for f in fs
             if f.endswith((".c", ".h", ".cpp", ".hpp"))]
    assert not found, found
