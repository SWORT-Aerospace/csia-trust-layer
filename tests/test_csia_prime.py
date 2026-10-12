"""CSIA PRIME (Commercial Reality & Differentiation): permanent tests. OFFBOARD.

Findings that changed or constrain the product are pinned here, so the 2.2,
pilot, 2.3 and RB-001 tests stay exactly as they were.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "research/csia_prime"
sys.path.insert(0, str(REPO / "research/csia_2_3_stock_bridge"))
from synthetic_stock import synth  # noqa: E402  (SYNTHETIC logs)


def _symptoms(log):
    run = runs.stock_flight(stock_log=log, est_log=None)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    return sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]}), m


def _shifted(shift_s):
    log = synth("motor")
    for d in log.topics.values():
        d["t"] = d["t"] + shift_s
    return log


# ------------------------------------------------------------------ D-PRIME-1
def test_a_whole_microsecond_shift_does_not_change_the_conclusion():
    """ULog timestamps are whole microseconds: the product's real-log path."""
    assert _symptoms(_shifted(0.0))[0] == ["COMMAND_NO_RESPONSE|motor_0"]
    assert _symptoms(_shifted(1e-6))[0] == ["COMMAND_NO_RESPONSE|motor_0"]
    assert _symptoms(_shifted(3e-6))[0] == ["COMMAND_NO_RESPONSE|motor_0"]


@pytest.mark.xfail(strict=True, reason="D-PRIME-1 (DEFECT_D_PRIME_1.md): content times are rounded "
                   "to the microsecond, the window anchor is not; a sub-microsecond shift makes the "
                   "2.2 gate reject valid evidence. Reported, not patched (stop condition 2).")
def test_a_sub_microsecond_shift_does_not_change_the_conclusion():
    syms, m = _symptoms(_shifted(0.7e-6))
    assert syms == ["COMMAND_NO_RESPONSE|motor_0"]
    assert m["final"]["evidence"]["rejected"] == []


# ------------------------------------------------------------------ D-PRIME-2
def _telemetry_outputs(scale):
    """motor_2's adverse ESC telemetry outputs when its reported RPM is scaled from 60 s (SYNTHETIC)."""
    syms, m = _symptoms(synth("telemetry", motor=2, eta=scale ** 2))
    return [v for v in m["evidence_values"] if v["record"] == "ACTUATION/motor_2:esc.telemetry_response"
            and v["state"] in ("DEGRADED", "VIOLATED", "ANOMALY")], syms, m


def test_a_telemetry_deficit_is_discovered_and_kept_out_of_the_motor():
    adverse, syms, m = _telemetry_outputs(0.775)
    assert adverse and len(m["events"]) == 1 and syms == []


@pytest.mark.xfail(strict=True, reason="D-PRIME-2 (DEFECT_D_PRIME_2.md): the telemetry CUSUM is one-sided "
                   "(deficit); an RPM report above command opens no event and is never reported. "
                   "Reported, not patched (stop condition 2).")
def test_a_telemetry_excess_is_reported():
    adverse, _, _ = _telemetry_outputs(10.0)
    assert adverse


# ------------------------------------------------------------------ B4 frozen decision rule (SYNTHETIC rows)
def _row(rid, cond, level, L, syms, tel, phys, cause, unique=None, lines=2, esc_lines=1):
    return {"run_id": rid, "condition": cond, "level": level, "L_median": L,
            "symptoms_any_time": syms, "telemetry_state": tel, "physical_state": phys,
            "ground_truth_cause": cause, "unique": unique, "independent_lines": lines,
            "esc_rpm_current_lines": esc_lines}


def test_the_ab_decision_rule_separates_classes_and_flags_every_error():
    sys.path.insert(0, str(PKG))
    import ab_scoring as AB
    good = [_row("a1", "A", 0.6, 0.40, ["COMMAND_NO_RESPONSE|motor_0"], "DEGRADED", "VIOLATED", "drive"),
            _row("b1", "B-phys", 0.6, 0.41, [], "DEGRADED", "NOMINAL", "telemetry")]
    v = AB.score(good)
    assert v["verdict"] == "PASS" and [r["class"] for r in v["rows"]] == ["A_CONFIRMED", "TELEMETRY_ONLY"]
    bad = good + [_row("b2", "B-phys", 0.6, 0.39, ["COMMAND_NO_RESPONSE|motor_0"], "DEGRADED", "VIOLATED",
                       "telemetry")]
    v = AB.score(bad)
    assert v["errors"]["B_AS_A"] == ["b2"] and v["stop_condition"] and v["verdict"] == "FAIL"
    lineage = [dict(r, esc_rpm_current_lines=2) for r in good]
    assert AB.score(lineage)["criteria"]["S4_lineage"] is False


def test_the_frozen_protocol_names_its_scoring_script_and_holds():
    text = (PKG / "B4_MATCHED_AB_PROTOCOL.md").read_text()
    assert "ab_scoring.py" in text and "FROZEN BEFORE ANY HARDWARE EXISTS" in text
    contract = json.loads((PKG / "contracts_draft/bench_loadcell_thrust_response.json").read_text())
    assert contract["DRAFT"] and "sensor:loadcell.<n>" in contract["lineage_rule"]
    # the draft is not in the product's contract directory: nothing loads it yet
    assert not (REPO / "csia_evidence_assurance/contracts/bench_loadcell_thrust_response.json").exists()


# ------------------------------------------------------------------ C1: the negative control is permanent
def test_the_steadiness_gate_is_not_loosened():
    """Track C1: maneuvering is not fixed by raising the threshold. The shipped
    product's theta_steady stays 2.3's calibration revision 3."""
    cal = json.loads((REPO / "csia_evidence_assurance/stock_calibration.json").read_text())
    assert cal["calibration"]["theta_steady"] == pytest.approx(0.09889434104510486, abs=1e-15)


def test_the_loosened_gate_negative_control_stays_on_record():
    """RB-001's preregistered evaluation: the loosened gate (B1) raised 163 false
    COMMAND_NO_RESPONSE and 52 wrong-motor states; the shipped gate (B0) none.
    The as-run result file must keep saying so."""
    ev = json.loads((REPO / "research/rb001_reality_bridge/MANEUVER_RESULTS_EVAL.json").read_text())["score"]
    assert ev["B1"]["false_violated"] == 163 and ev["B1"]["wrong_motor"] == 52
    assert ev["B0"]["false_violated"] == 0 and ev["B0"]["wrong_motor"] == 0
    verdict = json.loads((REPO / "research/rb001_reality_bridge/MANEUVER_VERDICT_EVAL.json").read_text())
    assert verdict["candidates"]["B1"]["verdict"].startswith("FAIL (S1")


# ------------------------------------------------------------------ Track A: the assurance view
from csia_evidence_assurance import assurance_view as AV  # noqa: E402
from csia_evidence_assurance import support as SP  # noqa: E402

A1_ORDER = ("WHAT HAPPENED?", "WHEN DID IT START?", "WHICH SUBSYSTEM IS AFFECTED?",
            "WHAT CAUSES REMAIN POSSIBLE?", "WHAT WAS ELIMINATED, AND WHY?", "WHAT EVIDENCE SUPPORTS THIS?",
            "WHAT EVIDENCE WAS REJECTED, AND WHY?", "WHICH MONITORS SHARE THE SAME SOURCE?",
            "WHAT WAS NOT OBSERVABLE?", "WHAT ADDITIONAL MEASUREMENT WOULD RESOLVE THE AMBIGUITY?")
QUAD = {"hardware": "SITL", "px4_git": "547e2ca", "sys_autostart": 1100, "mav_type": 2, "ca_rotor_count": 4,
        "vehicle_type": 1, "is_vtol": False, "topics": ["actuator_motors", "esc_status", "control_allocator_status",
                                                         "vehicle_angular_velocity", "vehicle_status",
                                                         "vehicle_land_detected", "battery_status"],
        "intervals": {"actuator_motors": {"median_ms": 100.0, "max_ms": 104.0},
                      "esc_status": {"median_ms": 100.0, "max_ms": 104.0}},
        "dropouts": 0, "gyro_mean_while_landed_rad_s": [0.001, -0.002, 0.0005]}


def _view(kind="motor"):
    run = runs.stock_flight(stock_log=synth(kind), est_log=None)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    return m, AV.build(m, SP.check(QUAD, m))


def test_coverage_states_never_collapse_unobserved_evidence_into_no_anomaly():
    for st in ("UNAVAILABLE", "NO_COVERAGE", "REJECTED:STALE", "REJECTED:PRODUCER_INVALID",
               "REJECTED:REGIME_INVALID", "NOT_APPLICABLE", "SOMETHING_NEW"):
        assert AV.record_class({st: 5})["class"] != "NO_ANOMALY", st
    assert AV.state_class("REJECTED:STALE") == "STALE"
    assert AV.state_class("REJECTED:PRODUCER_INVALID") == "FAULTED"
    assert AV.state_class("SOMETHING_NEW") == "UNKNOWN"
    mixed = AV.record_class({"NOMINAL": 81, "UNAVAILABLE": 3})
    assert mixed["class"] == "NO_ANOMALY" and mixed["partial"] is True
    assert AV.record_class({"ANOMALY": 1, "NOMINAL": 9})["class"] == "OBSERVED"
    assert set(AV.CLASSES) == {"OBSERVED", "NO_ANOMALY", "NO_COVERAGE", "UNAVAILABLE", "STALE", "FAULTED",
                               "NOT_APPLICABLE", "UNKNOWN"}


def test_the_first_page_answers_the_engineers_questions_in_order_without_confidence_figures():
    _m, v = _view("motor")
    text = v["summary_text"]
    pos = [text.index(h) for h in A1_ORDER]
    assert pos == sorted(pos)
    assert "%" not in text and not re.search(r"\b(probab|confiden|likel)", text, re.I)
    assert "COMMAND_NO_RESPONSE on motor_0: AMBIGUOUS" in text and "SUPPORT: SUPPORTED" in text


def test_every_conclusion_has_a_receipt_with_lineage_health_time_and_versions():
    _m, v = _view("motor")
    loc = [r for r in v["receipts"] if r["kind"] == "symptom"]
    assert loc, "a symptom must have a receipt"
    for r in loc:
        for k in ("supporting_evidence", "refuting_evidence", "rejected_evidence", "source_lineage",
                  "producer_health", "configuration", "versions", "still_possible", "would_resolve"):
            assert k in r, k
        assert r["versions"]["semantics"] == "2.1.1" and r["versions"]["view"] == AV.VIEW_VERSION
        assert all("content_time_s" in e for e in r["supporting_evidence"] if "record" in e)
    assert [r["kind"] for r in v["receipts"]].count("attribution") == 1


def test_a_telemetry_only_deficit_is_shown_unconfirmed_not_as_a_fault():
    _m, v = _view("telemetry")
    assert "COMMAND_NO_RESPONSE" not in v["summary_text"].split("WHEN DID IT START?")[0]
    assert any(r["kind"] == "unconfirmed" for r in v["receipts"])
    assert not any(r["kind"] == "symptom" for r in v["receipts"])


def test_the_view_is_deterministic():
    _m1, v1 = _view("motor")
    _m2, v2 = _view("motor")
    assert RP.dumps(v1) == RP.dumps(v2)


def test_support_check_names_what_is_outside_the_boundary():
    assert SP.check(QUAD)["status"] == "SUPPORTED"
    boat = dict(QUAD, vehicle_type=3, sys_autostart=50005, ca_rotor_count=None)
    assert SP.check(boat)["status"] == "UNSUPPORTED"
    vtol = dict(QUAD, is_vtol=True, sys_autostart=13014)
    assert SP.check(vtol)["status"] == "UNSUPPORTED"
    old = dict(QUAD, ca_rotor_count=None)
    assert SP.check(old)["status"] == "PARTIAL"
    hexa = dict(QUAD, ca_rotor_count=6)
    assert SP.check(hexa)["status"] == "UNSUPPORTED"
    bias = dict(QUAD, gyro_mean_while_landed_rad_s=[0.0, 0.0, 0.067])
    r = SP.check(bias)
    assert r["status"] == "PARTIAL" and any("gyro bias" in x for x in r["reasons"])
    gap = dict(QUAD, intervals={"esc_status": {"median_ms": 100.0, "max_ms": 350.0}})
    assert SP.check(gap)["status"] == "PARTIAL"


def test_the_support_matrix_backs_every_supported_claim_with_evidence():
    mx = SP.matrix()
    for entry in mx["vehicle"]["supported"] + mx["vehicle"]["unsupported"] + mx["diagnosable"] + mx["partial_coverage"]:
        assert entry.get("evidence"), entry
    assert "any fault on real hardware: no real propulsion validation exists yet" in mx["not_diagnosable"]


def test_re_raised_identical_px4_conditions_become_one_alert_and_propulsion_events_stay_separate():
    def ev(i, t, kind, text=None, motors=()):
        return {"event_id": f"E{i}", "t0": t, "motors": list(motors),
                "triggers": [{"kind": kind, "onset_t": t, "detail": {"text": text} if text else {}}]}
    m = {"events": [ev(1, 10.0, "px4.battery_warning"), ev(2, 30.0, "px4.battery_warning"),
                    ev(3, 200.0, "px4.battery_warning"), ev(4, 40.0, "propulsion.telemetry_change", motors=[1]),
                    ev(5, 45.0, "propulsion.telemetry_change", motors=[1])]}
    a = AV.alerts(m)
    bw = [x for x in a if x["kind"] == "px4.battery_warning"]
    assert [x["raised"] for x in bw] == [2, 1]
    assert len([x for x in a if x["kind"].startswith("propulsion")]) == 2


# ------------------------------------------------------------------ the package (documents, decision, pilot bundle)
DOCS = {"README.md", "PRIME_EXECUTION_PLAN.md", "REAL_DATA_ACQUISITION.md", "STRESS_ENVELOPE.md",
        "B4_MATCHED_AB_PROTOCOL.md", "SIM_TO_REAL_RECEIPTS.md", "DEFECT_D_PRIME_1.md", "B3_CHALLENGE.md",
        "EVENT_DISCOVERY_PREREG.md", "EVENT_DISCOVERY_STUDY.md", "TRACK_A_MVP.md",
        "COMPETITOR_FUNCTION_MATRIX.md", "DEFENSIBILITY_AND_IP.md", "TECHNICAL_DEMO.md",
        "EXTERNAL_PILOT_PACKAGE.md", "COMMERCIAL_PILOT.md", "DEFECT_D_PRIME_2.md", "CLAIM_EVIDENCE_MATRIX.md",
        "PRIME_REVIEW_AND_DECISION.md"}
PILOT_DOCS = {"QUICKSTART.md", "REPORT_GUIDE.md", "DIAGNOSTIC_QUESTIONS.md", "FEEDBACK_FORM.md"}
BANNED = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
          "never been studied", "has never been", "no prior art exists")
TOKENS = ("CSIA_PRIME_BLOCKED_ON_REAL_DATA", "CSIA_PRIME_REALITY_GAP_FOUND",
          "CSIA_PRIME_PHYSICAL_EVIDENCE_SUPPORTED", "CSIA_PRIME_COMMERCIAL_PILOT_READY",
          "CSIA_PRIME_REQUIRES_ARCHITECTURE_REVISION")


def _all_docs():
    return ([PKG / n for n in sorted(DOCS)] + [PKG / "pilot_package" / n for n in sorted(PILOT_DOCS)]
            + [PKG / "pilot_package_experimenter/SCORING_RUBRIC.md"])


def test_the_prime_documents_exist_and_keep_the_repositorys_wording_rules():
    assert {p.name for p in PKG.glob("*.md")} == DOCS
    assert {p.name for p in (PKG / "pilot_package").glob("*.md")} == PILOT_DOCS
    for p in _all_docs():
        text = p.read_text(encoding="utf-8").lower()
        assert len(text) > 1500, p.name
        assert not re.search(r"\bnovel\b", text), p.name
        for phrase in BANNED:
            assert phrase not in text, (p.name, phrase)


def test_the_prime_decision_chooses_one_token_and_keeps_the_authority_boundary():
    text = (PKG / "PRIME_REVIEW_AND_DECISION.md").read_text(encoding="utf-8")
    assert [t for t in TOKENS if f"**`{t}`**" in text] == ["CSIA_PRIME_BLOCKED_ON_REAL_DATA"]
    assert "CSIA_PRIME_BLOCKED_ON_REAL_DATA" in (PKG / "README.md").read_text()
    for q in range(1, 21):
        assert f"**{q}. " in text, q
    for doc in ("README.md", "PRIME_REVIEW_AND_DECISION.md", "COMMERCIAL_PILOT.md", "EXTERNAL_PILOT_PACKAGE.md"):
        t = (PKG / doc).read_text(encoding="utf-8").upper()
        assert "OFFBOARD" in t and "ZERO CONTROL" in t and "NO FORGE" in t, doc


def test_the_claim_matrix_has_the_briefs_columns_and_keeps_physical_claims_out():
    text = (PKG / "CLAIM_EVIDENCE_MATRIX.md").read_text(encoding="utf-8")
    assert "| # | public claim | experiment | dataset | result | limitations | version | public-safe? |" in text
    unsafe = text.split("## 3. Claims that are NOT public-safe")[1]
    for claim in ("on hardware", "Validated on real flights", "Diagnoses maneuvering faults", "ROI"):
        assert claim in unsafe, claim


def test_the_commercial_pilot_invents_no_roi_or_price():
    text = (PKG / "COMMERCIAL_PILOT.md").read_text(encoding="utf-8")
    assert not re.search(r"[$€£]\s?\d", text)
    assert not re.search(r"\d+\s?%", text)


def test_the_pilot_bundle_record_holds_no_truth_and_found_no_leak():
    """PILOT_BUNDLE.json is in the repository; the truth key is written only into the
    experimenter folder outside git. No case name or truth field may appear in the record."""
    rec = json.loads((PKG / "PILOT_BUNDLE.json").read_text())
    raw = json.dumps(rec)
    src = (PKG / "build_pilot_bundle.py").read_text()
    names = re.findall(r'^    \("([A-Za-z0-9_]+)", ', src, re.M)
    assert len(names) == 12
    for n in names:
        assert n not in raw, n
    assert "truth" not in rec and "GROUND_TRUTH" not in json.dumps(rec["participant_files_sha256"])
    assert rec["all_blinded_without_leaks"] and rec["all_exit_zero"]
    assert {v["data"] for v in rec["logs"].values()} == {"SITL", "REAL"}
    assert rec["wheel"]["has_support_matrix"] and not rec["wheel"]["has_research_tests_or_truth"]
    # D-PRIME-2: exactly one blinded log changed its conclusion, and it is recorded, not hidden.
    assert sum(1 for v in rec["logs"].values() if v["conclusions_equal"] is False) == 1
