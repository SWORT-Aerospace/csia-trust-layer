#!/usr/bin/env python3
"""Analyse the validation flights (VALIDATION_FLIGHTS_DESIGN.md) and score
them against the expectations stated before flying. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/validation_analysis.py

Each flight goes through the product path exactly as an engineer would run
it (`python -m csia_evidence_assurance analyze V1.ulg`): the ULog alone.
The run's JSON (injection time and target) is read afterwards, for scoring
only. Configuration A (stock producers only, `px4_monitors=False`) is run
as well, for Phase 18.

Writes VALIDATION_RESULTS.json and, per flight, reports/<id>/report.txt and
manifest.json (the product's own output). report.json is not copied: it
regenerates byte for byte from the ULog, and its SHA-256 is in the
manifest.
"""
from __future__ import annotations

import json
import shutil

import numpy as np

import common_23 as C

from csia_evidence_assurance import __main__ as CLI
from csia_evidence_assurance import runs as R
from csia_evidence_assurance.stock_log import StockLog

VAL = C.OUT_RAW / "validation"
REPORTS = C.HERE / "reports"
#: run -> (injected motor index, kind); motor index is CSIA's (SIH MotorN = motor_{N-1})
TRUTH = {"V1": (1, "motor"), "V2": (2, "motor"), "V3": (3, "motor"), "V4": (0, "motor"),
         "V5": (None, "nominal"), "V6": (None, "nominal"), "V7": (None, "gps_off"),
         "V8": (None, "battery_wrong"), "V9": (1, "esc_off"), "V10": (2, "esc_wrong"),
         # second design (VALIDATION_FLIGHTS_DESIGN_2.md)
         "V11": (None, "nominal_2"), "V12": (2, "motor_after_maneuvers"),
         "V13": (2, "motor_during_maneuvers")}
MATCH_S = 2.0


def onset_log_s(rec, log) -> float | None:
    """The injection time on the log's clock (log start = log.t0_us)."""
    ev = rec.get("events_ms", {})
    if "onset_param_set" in ev:
        ms = ev["onset_param_set"][0]
    elif "inject_sent" in ev:
        ms = ev["inject_sent"]
    else:
        return None
    return ms * 1e-3 - log.t0_us * 1e-6


def in_flight_s(log) -> float:
    t = np.arange(0.0, max(float(v["t"][-1]) for v in log.topics.values() if len(v["t"])), 0.01)
    return float(np.count_nonzero(log.in_flight(t)) * 0.01)


def final_summary(m) -> dict:
    f = m["final"] or {}
    locs = f.get("localizations", [])
    return {"headline": f.get("state", {}).get("headline"),
            "symptoms": [{"key": x["key"], "outcome": x["outcome"], "candidates": x["candidates"],
                          "eliminated": [e["hypothesis"] for e in x["eliminated"]]} for x in locs],
            "attribution": (f.get("attribution") or {}).get("verdict")}


def context_states(m, record_suffix) -> list:
    return [(v["record"], v["state"], v["measured"], v["window"]) for v in m["evidence_values"]
            if v["record"].endswith(record_suffix)]


def score(rid, m, onset, truth):
    motor, kind = truth
    ev = m["events"]
    fs = final_summary(m)
    out = {"events": len(ev), "event_t0s": [round(e["t0"], 3) for e in ev],
           "trigger_kinds": sorted({k for e in ev for k in e["trigger_kinds"]}),
           "trigger_motors": sorted({t["motor"] for e in ev for t in e["triggers"]
                                     if t["motor"] is not None})}
    if onset is not None:
        near = [e for e in ev if abs(e["t0"] - onset) <= MATCH_S]
        out["onset_log_s"] = round(onset, 3)
        out["matched"] = bool(near)
        out["timing_error_s"] = round(near[0]["t0"] - onset, 3) if near else None
        out["events_before_onset"] = sum(1 for e in ev if e["t0"] < onset - MATCH_S)
        out["events_later_while_injected"] = sum(1 for e in ev if e["t0"] > onset + MATCH_S)
        if near:
            first = min(near[0]["triggers"], key=lambda t: (t["onset_t"], t["alarm_t"]))
            out["first_trigger"] = {"kind": first["kind"], "motor": first["motor"]}
            out["motors_in_matched_event"] = sorted({t["motor"] for t in near[0]["triggers"]
                                                     if t["motor"] is not None})
    else:
        out["events_in_nominal_flight"] = len(ev)
    out["final"] = fs
    syms = fs["symptoms"]
    # every symptom raised at ANY tick, not only at the end (V5 and V6 raised
    # and withdrew false symptoms that the final tick did not show)
    anytime = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                      if c["what"] != "attribution" and c["to"]})
    out["symptoms_any_time"] = anytime
    checks = {}
    if kind == "motor":
        sub = f"motor_{motor}"
        checks["discovery: one event within 2 s of onset"] = out.get("matched") and len(ev) == 1
        checks["discovery: triggered on the injected motor"] = (
            out.get("first_trigger", {}).get("motor") == motor)
        checks["analysis: COMMAND_NO_RESPONSE on the injected motor only"] = (
            [s["key"] for s in syms] == [f"COMMAND_NO_RESPONSE|{sub}"]
            and all(k.endswith(f"|{sub}") for k in anytime))
        mine = [s for s in syms if s["key"].endswith(sub)]
        checks["analysis: SENSOR/response_sensor eliminated"] = bool(
            mine and "SENSOR/response_sensor" in mine[0]["eliminated"])
        checks["analysis: ACTUATION/mechanical among the remaining"] = bool(
            mine and "ACTUATION/mechanical" in mine[0]["candidates"])
    elif kind == "nominal_2":
        checks["analysis: no symptom at any time"] = not syms and not anytime
    elif kind == "motor_after_maneuvers":
        sub = f"motor_{motor}"
        near = [e for e in ev if onset is not None and abs(e["t0"] - onset) <= MATCH_S]
        checks["discovery: an event within 2 s of the injection, motor among its triggers"] = bool(
            near) and motor in near[0]["motors"]
        checks["analysis: COMMAND_NO_RESPONSE on the injected motor, no other motor at any time"] = (
            f"COMMAND_NO_RESPONSE|{sub}" in anytime and all(k.endswith(f"|{sub}") for k in anytime))
        mine = [s_ for s_ in syms if s_["key"].endswith(sub)]
        checks["analysis: SENSOR/response_sensor eliminated"] = bool(
            mine and "SENSOR/response_sensor" in mine[0]["eliminated"])
        checks["analysis: ACTUATION/mechanical among the remaining"] = bool(
            mine and "ACTUATION/mechanical" in mine[0]["candidates"])
    elif kind == "motor_during_maneuvers":
        sub = f"motor_{motor}"
        checks["analysis: no symptom on any other motor at any time"] = all(
            k.endswith(f"|{sub}") for k in anytime)
        near = [e for e in ev if onset is not None and abs(e["t0"] - onset) <= MATCH_S]
        eid = near[0]["event_id"] if near else None
        vals = [v for v in m["evidence_values"] if v["event_id"] == eid
                and v["record"].startswith(f"ACTUATION/{sub}:")]
        checks["analysis: telemetry deficit reported for the injection event"] = any(
            v["record"].endswith("esc.telemetry_response") and v["state"] == "DEGRADED"
            and (v["measured"] or 0) > 0 for v in vals)
        checks["analysis: compensation UNAVAILABLE (NOT_STEADY_FLIGHT) for the injection event"] = any(
            v["record"].endswith("actuation.physical_response") and v["state"] == "UNAVAILABLE"
            and "NOT_STEADY_FLIGHT" in v["reason_codes"] for v in vals)
        out["injection_event"] = eid
    elif kind == "nominal":
        checks["discovery: no event"] = len(ev) == 0
        checks["analysis: no symptom"] = not syms and not anytime
    elif kind == "gps_off":
        checks["analysis: no propulsion symptom"] = not syms and not anytime
        out["estimator_or_failsafe_trigger"] = any(
            k in out["trigger_kinds"] for k in ("px4.estimator_rejection", "px4.failsafe"))
    elif kind == "battery_wrong":
        checks["discovery: battery-warning trigger"] = "px4.battery_warning" in out["trigger_kinds"]
        checks["discovery: failsafe trigger"] = "px4.failsafe" in out["trigger_kinds"]
        checks["analysis: no propulsion symptom"] = not syms and not anytime
        w = context_states(m, "power.battery_warning")
        checks["analysis: battery warning reported as context"] = any(s != "NOMINAL" for _r, s, _v, _w in w)
        sh = context_states(m, "power.source_health")
        checks["analysis: source health UNAVAILABLE"] = bool(sh) and all(s == "UNAVAILABLE" for _r, s, _v, _w in sh)
    elif kind == "esc_off":
        sub = f"motor_{motor}"
        checks["discovery: telemetry trigger on the motor"] = any(
            t["kind"] == "propulsion.telemetry_change" and t["motor"] == motor
            for e in ev for t in e["triggers"])
        checks["analysis: no symptom"] = not syms and not anytime
        comp = [x for x in context_states(m, "actuation.physical_response") if f"/{sub}:" in x[0]]
        checks["analysis: compensation on the motor NOMINAL (deficit not confirmed)"] = bool(
            comp) and comp[-1][1] == "NOMINAL"
        out["telemetry_states"] = [x for x in context_states(m, "esc.telemetry_response")
                                   if f"/{sub}:" in x[0]]
    elif kind == "esc_wrong":
        sub = f"motor_{motor}"
        checks["discovery: telemetry trigger on the motor"] = any(
            t["kind"] == "propulsion.telemetry_change" and t["motor"] == motor
            for e in ev for t in e["triggers"])
        checks["analysis: no symptom"] = not syms and not anytime
        tel = [x for x in context_states(m, "esc.telemetry_response") if f"/{sub}:" in x[0]]
        checks["analysis: telemetry excess reported as context"] = any(
            s == "DEGRADED" and (v or 0) < 0 for _r, s, v, _w in tel)
        out["telemetry_states"] = tel
    out["checks"] = checks
    out["as_expected"] = all(bool(v) for v in checks.values())
    return out


def main():
    rows, cfgA = {}, {}
    REPORTS.mkdir(exist_ok=True)
    for rid in TRUTH:
        ulg = VAL / f"{rid}.ulg"
        rec = json.loads((VAL / f"{rid}.json").read_text())
        if not ulg.exists():
            rows[rid] = {"outcome": rec.get("outcome"), "analysed": False}
            continue
        work = C.OUT_RAW / "validation_reports" / rid
        run = R.stock_flight(ulg)
        w = CLI._write(run, work, {"tick_s": R.STOCK_TICK_S, "path": "stock", "input": ulg.name})
        m = w["m"]
        dst = REPORTS / rid
        dst.mkdir(exist_ok=True)
        for f in ("report.txt", "manifest.json"):     # report.json: reproducible, hash in manifest
            shutil.copy(work / f, dst / f)
        log = StockLog.from_ulog(ulg)
        onset = onset_log_s(rec, log)
        row = score(rid, m, onset, TRUTH[rid])
        row.update({"outcome": rec.get("outcome"), "ulog_sha256": rec.get("ulog_sha256"),
                    "in_flight_s": round(in_flight_s(log), 1),
                    "report_sha256": w["manifest"]["report_sha256"],
                    "profile_records_observed": m["coverage_report"]["profile_records_observed"],
                    "statustext": [s for s in rec.get("statustext", []) if s[0] >= 45000][:12],
                    "acks_inject": [a for a in rec.get("acks", []) if a[1] == 420]})
        rows[rid] = row
        a = R.stock_flight(stock_log=StockLog.from_ulog(ulg), est_log=None, px4_monitors=False)
        from csia_evidence_assurance import report as RP
        ma = RP.machine_report(a.results, a.inputs, a.gate, a.contracts, extras=a.extras)
        cfgA[rid] = score(rid, ma, onset, TRUTH[rid])
        print(rid, row["as_expected"], row["events"], row["final"]["headline"], flush=True)
    C.write_json(C.HERE / "VALIDATION_RESULTS.json", {
        "design": "VALIDATION_FLIGHTS_DESIGN.md (committed before flying)",
        "product_path": "runs.stock_flight on the ULog alone (configuration B)",
        "config_A": "stock producers only (px4_monitors=False)",
        "rows": rows, "config_A_rows": cfgA})


if __name__ == "__main__":
    main()
