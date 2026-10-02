"""CSIA 2.3 stock PX4 evidence bridge: permanent tests (Phase 19 and the
product path). OFFBOARD ONLY; nothing here touches flight control.

Most tests run on SYNTHETIC stock logs built below (`synth`), so they need
no raw flight data. They are labelled synthetic: they pin the product's
logic, not its accuracy on real flights. The tests that need a real ULog
skip when it is absent.

The discipline rules (Phase 19):
- NO_COVERAGE is not NOMINAL;
- UNAVAILABLE is not NOMINAL;
- NOT_APPLICABLE is not NOMINAL;
- a FAULTED producer is not a vehicle fault;
- UNKNOWN is not HEALTHY.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState as OS
from csia_evidence_assurance import diagnosability as DG
from csia_evidence_assurance import events as EV
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs
from csia_evidence_assurance import stock_report as SR
from csia_evidence_assurance.adapters import px4_stock as PS
from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer
from csia_evidence_assurance.contract import load_contracts
from csia_evidence_assurance.envelope import EvidenceEnvelope
from csia_evidence_assurance.health import ProducerHealth
from csia_evidence_assurance.lineage import Lineage
from csia_evidence_assurance.profiles import multirotor_quad as Q
from csia_semantic_core.index import SuccessorIndex

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "research/csia_2_3_stock_bridge"
RAW_VALIDATION = Path("/home/user/csia_2_3_raw/validation")
sys.path.insert(0, str(PKG))
from synthetic_stock import synth  # noqa: E402  (SYNTHETIC logs; see the module)

def analyse(log, **kw):
    run = runs.stock_flight(stock_log=log, est_log=None, **kw)
    return run, RP.machine_report(run.results, run.inputs, run.gate, run.contracts,
                                  extras=run.extras)


@pytest.fixture(scope="module")
def motor2():
    return analyse(synth("motor", motor=2))


@pytest.fixture(scope="module")
def tel1():
    return analyse(synth("telemetry", motor=1))


@pytest.fixture(scope="module")
def nominal():
    return analyse(synth("nominal"))


def _loc(m):
    return (m["final"] or {}).get("localizations", [])


# ------------------------------------------------------------------ the product path (synthetic)
def test_motor_loss_is_discovered_localized_and_left_ambiguous(motor2):
    _run, m = motor2
    assert m["schema"] == SR.SCHEMA_4
    assert len(m["events"]) == 1 and abs(m["events"][0]["t0"] - 60.0) <= 0.2
    assert 2 in m["events"][0]["motors"]
    locs = _loc(m)
    assert [x["key"] for x in locs] == ["COMMAND_NO_RESPONSE|motor_2"]
    x = locs[0]
    assert "SENSOR/response_sensor" in [e["hypothesis"] for e in x["eliminated"]]
    assert "ACTUATION/mechanical" in x["candidates"] and len(x["candidates"]) > 1
    assert m["summary"]["attribution"]["justified"] is False


def test_telemetry_only_deficit_is_context_not_a_symptom(tel1):
    """SB-1: an RPM-only deficit stays context; the vehicle does not confirm it."""
    _run, m = tel1
    assert not _loc(m)
    vals = {(v["record"], v["window"]): v for v in m["evidence_values"]}
    assert vals[("ACTUATION/motor_1:esc.telemetry_response", "AFTER")]["state"] == "DEGRADED"
    assert vals[("ACTUATION/motor_1:actuation.physical_response", "AFTER")]["state"] == "NOMINAL"


def test_sb1_an_rpm_only_deficit_on_mechanical_response_would_eliminate_mechanical():
    """Why the telemetry claim is context: 2.1.1's STALL_SIGNATURE reads the
    absence of ACT_STALLED as "stall checked and absent"."""
    _e, core, _g = runs.quad_setup(4)

    def rec(rel, st, codes=()):
        return EvidenceRecord(domain="ACTUATION", component="motor_0", relation=rel, source="t",
                              observation_state=st, applicability=Applicability.APPLICABLE,
                              affected_functions=("PROPULSION",), reason_codes=codes,
                              dependencies=PS.MOTOR_DEPS)
    base = [rec("actuation.physical_response", OS.VIOLATED, ("ACT_NO_PHYSICAL_RESPONSE",))]
    with_rpm = base + [rec("actuation.mechanical_response", OS.DEGRADED, ("ACT_RESPONSE_LOW",))]
    a, b = core.reason(base, None).localizations[0], core.reason(with_rpm, None).localizations[0]
    assert "ACTUATION/mechanical" in a.unresolved
    assert ("ACTUATION/mechanical", "STALL_SIGNATURE_FALSE") in b.v2.rejected


def test_nominal_hover_gives_no_event_and_no_symptom(nominal):
    _run, m = nominal
    assert m["events"] == [] and not _loc(m)
    assert m["summary"]["what_happened"] == ["no event was discovered"]


def test_known_onset_benchmark_hook_matches_discovery(motor2):
    _r, m = motor2
    _r2, k = analyse(synth("motor", motor=2), known_onsets=[60.0])
    assert [x["key"] for x in _loc(k)] == [x["key"] for x in _loc(m)]
    assert k["inputs"]["events_source"] == "known onset (benchmark)"


def test_reports_are_deterministic(motor2):
    _r, m = motor2
    _r2, again = analyse(synth("motor", motor=2))
    assert RP.dumps(m) == RP.dumps(again)


# ------------------------------------------------------------------ Phase 19 discipline
def test_no_coverage_is_not_nominal():
    """Without esc_status there is no propulsion evidence and no propulsion
    trigger: the report must say so, not call the motors healthy."""
    run, m = analyse(synth("motor", motor=2, esc=False))
    assert not _loc(m)
    notices = m["coverage_report"]["coverage_notices"]
    assert any(n["producer_id"] == PS.COMP for n in notices)
    obs = {v["record"] for v in m["evidence_values"] if v["state"] == "NOMINAL"}
    assert not any(r.endswith("actuation.physical_response") for r in obs)
    rows = {r["record"]: r for r in m["coverage_report"]["records"]}
    assert not rows["ACTUATION/motor_2:actuation.physical_response"]["observed"]
    assert m["summary"]["attribution"]["justified"] is False
    assert "esc_status" in m["coverage_report"]["topics_absent"]


def test_unavailable_is_not_nominal(motor2):
    """Battery current -1 (not measured): source health is UNAVAILABLE, it
    is not observed, and path_unavailable can never be eliminated."""
    _r, m = motor2
    sh = [v for v in m["evidence_values"] if v["record"] == "POWER/battery:power.source_health"]
    assert sh and all(v["state"] == "UNAVAILABLE" for v in sh)
    assert "POWER/battery:power.source_health" not in m["profile_coverage"]["observed"]
    floor = [s for s in m["diagnosability"]["symptoms"]
             if s.get("raisable") and s.get("subject") == "motor_2"][0]["never_eliminable"]
    assert "POWER/path_unavailable" in floor
    assert "POWER/path_unavailable" in _loc(m)[0]["candidates"]


def test_not_applicable_is_not_nominal(motor2):
    """Healthy motors' compensation is NOT_APPLICABLE (no local deficit to
    test): no 2.1.1 predicate may read it as a nominal physical response."""
    _r, m = motor2
    na = [v for v in m["evidence_values"] if v["record"].endswith("actuation.physical_response")
          and v["state"] == "NOT_APPLICABLE"]
    assert {v["record"] for v in na} == {f"ACTUATION/motor_{j}:actuation.physical_response"
                                          for j in (0, 1, 3)}
    _e, core, _g = runs.quad_setup(4)
    rec = EvidenceRecord(domain="ACTUATION", component="motor_0",
                         relation="actuation.physical_response", source="t",
                         observation_state=OS.NOT_APPLICABLE,
                         applicability=Applicability.NOT_APPLICABLE,
                         affected_functions=("PROPULSION",), dependencies=PS.MOTOR_DEPS)
    for pid in ("PHYSICAL_RESPONSE_NOMINAL", "PHYSICAL_RESPONSE_NOMINAL_FALSE"):
        assert core.predicates[pid](SuccessorIndex([rec], tracing=False), "motor_0") is None


def test_stock_producers_never_emit_nominal_with_a_non_applicable_applicability():
    """2.1.1 reads the observation state: a NOMINAL record marked
    NOT_APPLICABLE would still count as nominal. The producers must never
    emit that pair (finding D-1)."""
    for kind, mot in (("motor", 2), ("telemetry", 1), ("nominal", 0)):
        log = synth(kind, motor=mot).decimate()
        sp = PS.StockProducers(log, "sensor:imu.0", PS.load_calibration())
        for cp in PS.CHECKPOINTS:
            for e in sp.at(60.0, cp):
                r = e.record
                if r.observation_state is OS.NOMINAL:
                    assert r.applicability is Applicability.APPLICABLE, (kind, cp, r.relation)


def test_faulted_producer_is_not_a_vehicle_fault():
    engine, core, gate = runs.quad_setup(4)
    an = FlightAssuranceAnalyzer(core, load_contracts(*PS.CONTRACT_FILES), gate, Q.BASE)
    rec = EvidenceRecord(domain="ACTUATION", component="motor_0",
                         relation="actuation.physical_response", source=PS.COMP,
                         observation_state=OS.VIOLATED, applicability=Applicability.APPLICABLE,
                         affected_functions=PS.MOTOR_FNS, reason_codes=("ACT_NO_PHYSICAL_RESPONSE",),
                         dependencies=PS.MOTOR_DEPS, measured_value=0.6, expected_value=0.0)
    env = EvidenceEnvelope(PS.COMP, PS.PRODUCER_VERSION, PS.CONTRACT_VERSION, "PHYSICAL_EFFECT",
                           rec, Lineage.of("channel:motor_command.motor_0"), 75.0,
                           ProducerHealth.FAULTED, 75.0)
    r = an.step(75.0, [env], events={PS.EVENT: 60.0}).to_dict()
    assert r["localizations"] == []
    assert r["evidence"]["used"] == []
    assert len(r["evidence"]["rejected"]) == 1
    healthy = an.step(75.0, [EvidenceEnvelope(**{**env.__dict__,
                                                 "producer_health": ProducerHealth.VALID})],
                      events={PS.EVENT: 60.0}).to_dict()
    assert [x["key"] for x in healthy["localizations"]] == ["COMMAND_NO_RESPONSE|motor_0"]


def test_unknown_is_not_healthy(nominal):
    """No event and no symptom is reported as exactly that, with what was
    not observed; never as a healthy vehicle."""
    _r, m = nominal
    text = "\n".join(SR.human_summary(m))
    assert not re.search(r"\bhealthy\b", text.replace("unobserved is not healthy", ""), re.I)
    assert m["summary"]["attribution"]["verdict"] == "NO_EVIDENCE"
    assert m["summary"]["attribution"]["justified"] is False
    assert m["coverage_report"]["profile_records_observed"] < m["coverage_report"]["profile_records_expected"]
    assert any("not measured" in n for n in m["summary"]["not_observed"])


# ------------------------------------------------------------------ events
def test_clustering_joins_triggers_within_the_gap_only():
    t = [EV.Trigger("s", "a", 10.0, 10.1), EV.Trigger("s", "b", 12.9, 13.0),
         EV.Trigger("s", "c", 16.0, 16.1)]
    ev = EV.cluster(t)
    assert [len(e.triggers) for e in ev] == [2, 1] and ev[0].t0 == 10.0 and ev[1].t0 == 16.0


def test_battery_warning_in_flight_is_a_trigger_not_a_diagnosis():
    _r, m = analyse(synth("nominal", battery_warning_at=50.0))
    kinds = {k for e in m["events"] for k in e["trigger_kinds"]}
    assert "px4.battery_warning" in kinds
    assert not _loc(m)
    warn = [v for v in m["evidence_values"] if v["record"] == "POWER/battery:power.battery_warning"]
    assert any(v["state"] != "NOMINAL" for v in warn)


def test_the_frozen_cusum_reports_no_coverage_on_a_px4_log(nominal):
    _r, m = nominal
    assert any(n["producer_id"] == "cusum:v1_1_sequential"
               for n in m["coverage_report"]["coverage_notices"])


# ------------------------------------------------------------------ profile and contracts
def test_quad_profile_passes_its_gate_and_leaves_the_historical_profile_alone():
    g = Q.gate()
    assert g.status == "ACCEPTED" and len(g.records) == 29 == len(Q.record_catalog())
    assert Q.profile_info()["name"] == "multirotor-quad" and Q.VERSION == "r1"
    from csia_evidence_assurance.adapters import v2_domains as V2
    assert Q.BASE != V2.AIRCRAFT_BASE


def test_the_packaged_calibration_is_the_committed_research_calibration():
    pk = json.loads((REPO / "csia_evidence_assurance/stock_calibration.json").read_text())
    rs = json.loads((PKG / "CALIBRATION_2_3.json").read_text())
    assert pk["calibration"] == rs["calibration"] and pk["revision"] == rs["revision"] == 3
    r2 = json.loads((PKG / "CALIBRATION_2_3_r2_superseded.json").read_text())["calibration"]
    assert {k: v for k, v in rs["calibration"].items() if k != "theta_steady"} == r2


def test_the_stock_contracts_load_and_declare_their_windows():
    cs = load_contracts(*PS.CONTRACT_FILES)
    assert set(cs) == {PS.COMP, PS.TEL, PS.DYN, PS.ALLOC, PS.BAT}
    for c in cs.values():
        assert c.producer_version == PS.PRODUCER_VERSION


def test_diagnosability_floor_with_stock_evidence(motor2):
    """With SIH stock evidence the explanations that can never be eliminated
    on a motor are drive_no_current, command_not_delivered, path_unavailable."""
    _r, m = motor2
    s = [x for x in m["diagnosability"]["symptoms"]
         if x.get("raisable") and x["symptom"] == "COMMAND_NO_RESPONSE"
         and x["subject"] == "motor_2"][0]
    assert s["never_eliminable"] == ["ACTUATION/drive_no_current",
                                     "COMMUNICATION/command_not_delivered",
                                     "POWER/path_unavailable"]


def test_the_report_answers_the_engineers_questions_first(motor2):
    _r, m = motor2
    lines = SR.human_summary(m)
    heads = [ln for ln in lines if ln.endswith("?") or "?" in ln.split("(")[0]]
    assert heads[0] == "WHAT HAPPENED?"
    assert lines.index("WHAT HAPPENED?") < lines.index("DETAIL")
    assert "IS ATTRIBUTION JUSTIFIED?" in lines


def test_values_carry_units_thresholds_and_windows(motor2):
    _r, m = motor2
    for v in m["evidence_values"]:
        if v["record"].endswith(("physical_response", "telemetry_response", "rate_transient")):
            assert v["unit"] and v["threshold"] is not None and v["window"]


# ------------------------------------------------------------------ real logs (skip if absent)
@pytest.mark.skipif(not (RAW_VALIDATION / "V1.ulg").exists(), reason="raw validation flight absent")
def test_cli_analyze_defaults_to_the_stock_path(tmp_path):
    import subprocess
    import sys
    p = subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "analyze",
                        str(RAW_VALIDATION / "V1.ulg"), "--out", str(tmp_path / "r")],
                       cwd=REPO, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    m = json.loads((tmp_path / "r/report.json").read_text())
    assert m["schema"] == SR.SCHEMA_4 and m["summary"]
    man = (tmp_path / "r/manifest.json").read_text()
    assert "/home/" not in man and "/tmp/" not in man


def test_the_diagnosability_probe_never_changes_the_core():
    _e, core, _g = runs.quad_setup(4)
    before = {s.symptom_id: [h.hypothesis_id for h in s.hypotheses] for s in core.symptoms}
    DG.analyze(core, Q.sample_records(_e), [], Q.record_catalog())
    assert before == {s.symptom_id: [h.hypothesis_id for h in s.hypotheses] for s in core.symptoms}


def test_a_log_gap_is_neither_nominal_nor_a_vehicle_fault():
    """LOG_COMPLETENESS: esc_status silent for 2 s inside the AFTER window.
    The propulsion outputs over it are UNAVAILABLE (producer health) and
    refused; the motor loss is then not localised from them."""
    log = synth("motor", motor=2)
    es = log.topics["esc_status"]
    keep = ~((es["t"] >= 71.0) & (es["t"] < 73.0))
    log.topics["esc_status"] = {k: v[keep] for k, v in es.items()}
    _r, m = analyse(log)
    gapped = [v for v in m["evidence_values"] if v["window"] == "AFTER"
              and v["record"].endswith(("physical_response", "telemetry_response"))]
    assert gapped and all(v["producer_health"] == "UNAVAILABLE" and "esc_status" in v["log_gap"]
                          for v in gapped)
    assert not any(x["key"].endswith("motor_2") and x["symptom"] == "COMMAND_NO_RESPONSE"
                   for x in _loc(m))


def test_logger_dropouts_make_overlapping_outputs_unavailable():
    log = synth("motor", motor=2)
    log.dropouts = [(60.5, 0.4)]
    sp = PS.StockProducers(log.decimate(), "sensor:imu.0", PS.load_calibration())
    early = sp.at(60.0, "EARLY")
    tel = [e for e in early if e.producer_id == PS.TEL]
    assert tel and all(e.producer_health is ProducerHealth.UNAVAILABLE for e in tel)
    assert any(n["producer_id"] == "log" for n in sp.coverage_notices())


def test_an_offline_esc_is_telemetry_unavailable_not_a_deficit():
    """Validation flight V9 (PX4's ESC OFF injection): the ESC's online bit
    clears and PX4 reports 0 RPM. That is a dropout (claim register failure
    mode), not a measured 100 % deficit."""
    _r, m = analyse(synth("esc_offline", motor=1))
    vals = {(v["record"], v["window"]): v for v in m["evidence_values"]}
    tel = vals[("ACTUATION/motor_1:esc.telemetry_response", "AFTER")]
    comp = vals[("ACTUATION/motor_1:actuation.physical_response", "AFTER")]
    assert tel["state"] == "UNAVAILABLE" and "ESC_TELEMETRY_OFFLINE" in tel["reason_codes"]
    assert comp["state"] == "NOT_APPLICABLE"
    assert not _loc(m)


def test_a_total_reported_loss_without_compensation_passes_the_power_gate():
    """An online ESC reporting 0 RPM while the loop asks nothing more of the
    motor: the reported loss is not confirmed by the vehicle (NOMINAL)."""
    _r, m = analyse(synth("rpm_zero", motor=3))
    vals = {(v["record"], v["window"]): v for v in m["evidence_values"]}
    assert vals[("ACTUATION/motor_3:esc.telemetry_response", "AFTER")]["state"] == "DEGRADED"
    assert vals[("ACTUATION/motor_3:actuation.physical_response", "AFTER")]["state"] == "NOMINAL"
    assert not _loc(m)


def test_compensation_during_a_maneuver_is_unavailable_not_a_loss():
    """Validation flights V5 and V6: a yaw turn moves the command split of
    one motor pair exactly as a loss does. The compensation claim assumes
    near-steady flight in both windows (claim register); when the body rates
    say otherwise it is UNAVAILABLE (NOT_STEADY_FLIGHT) and no symptom is
    raised, at any time."""
    log = synth("nominal")
    am, av = log.topics["actuator_motors"], log.topics["vehicle_angular_velocity"]
    split = (am["t"] >= 61.0) & (am["t"] < 76.0)
    for m in (0, 1):
        am[f"control[{m}]"] = am[f"control[{m}]"].copy()
        am[f"control[{m}]"][split] = 0.56
    yaw = (av["t"] >= 61.0) & (av["t"] < 76.0)
    av["xyz[2]"] = av["xyz[2]"].copy()
    av["xyz[2]"][yaw] = 0.5
    run, m = analyse(log)
    comp = [v for v in m["evidence_values"] if v["record"].endswith("physical_response")
            and v["window"] == "AFTER" and v["record"].split(":")[0].endswith(("motor_0", "motor_1"))]
    assert comp and all(v["state"] == "UNAVAILABLE" and "NOT_STEADY_FLIGHT" in v["reason_codes"]
                        for v in comp)
    assert all(not r.to_dict()["localizations"] for r in run.results)


def test_a_symptom_raised_and_withdrawn_is_reported_in_what_happened():
    """The flight-end result alone hid V5's transient false symptoms: the
    summary names every symptom raised at any time."""
    m = {"final": {"localizations": []}, "key_moments": {"candidate_changes": [
        {"t": 54.8, "what": "COMMAND_NO_RESPONSE|motor_0", "to": ["AMBIGUOUS"]},
        {"t": 59.9, "what": "COMMAND_NO_RESPONSE|motor_0", "to": []}]},
        "profile_coverage": {}, "coverage_report": {}}
    s = SR._summary(m, {"events": [], "evidence_values": [], "diagnosability": {}})
    assert any("COMMAND_NO_RESPONSE|motor_0 was raised 1 time" in x for x in s["what_happened"])
