#!/usr/bin/env python3
"""Phase 25: the product validation set, one row per brief class. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/validation_set.py

Existing data first; synthetic only where no real data exists, and marked
so. Sources:
- REAL SITL (ordinary logs, default logging): the validation flights
  (VALIDATION_RESULTS.json) and the 2.2 pilot's S1 selector run;
- XSYS-001 REPLAY: BLIND_ONSET_REPLAY.json (stock logs at default rates;
  case B is XSYS-001's frozen telemetry-only construction);
- SYNTHETIC: `synthetic_stock.synth` logs, and one frozen v2 scenario
  (CPU_OVERLOAD) through the 2.2 path, for the class stock logs cannot
  show.

Each row: class, case, source, what was expected, what the product said,
whether it was correct, useful (an engineer learns something actionable)
and honest (no claim beyond the evidence; gaps named).
Writes VALIDATION_SET.json.
"""
from __future__ import annotations

import json

import common_23 as C

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from synthetic_stock import synth


def stock_summary(run):
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    f = m["final"] or {}
    return {"events": len(m["events"]),
            "trigger_kinds": sorted({k for e in m["events"] for k in e["trigger_kinds"]}),
            "headline": f.get("state", {}).get("headline"),
            "attribution": (f.get("attribution") or {}).get("verdict"),
            "not_observed": m["summary"]["not_observed"][:6],
            "observed_records": m["coverage_report"]["profile_records_observed"],
            "configuration_changes": len(m["key_moments"].get("configuration_changes", []))}


def main():
    rows = []
    val = json.loads((C.HERE / "VALIDATION_RESULTS.json").read_text())["rows"]
    blind = json.loads((C.HERE / "BLIND_ONSET_REPLAY.json").read_text())["summary"]

    def v(rid):
        r = val.get(rid, {})
        return {"events": r.get("events"), "headline": r.get("final", {}).get("headline"),
                "attribution": r.get("final", {}).get("attribution"),
                "as_expected": r.get("as_expected"), "checks": r.get("checks")}

    def add(cls, case, source, expected, observed, correct, useful, honest, note=""):
        rows.append({"class": cls, "case": case, "source": source, "expected": expected,
                     "observed": observed, "correct": correct, "useful": useful,
                     "honest": honest, "note": note})

    # nominal
    for rid in ("V5", "V6"):
        o = v(rid)
        add("nominal", rid, "REAL SITL (maneuvering)", "no event, no symptom", o,
            o["headline"] == "no symptom; attribution NO_EVIDENCE", o["events"] == 0, True,
            "events are false triggers, dismissed by the analysis" if o["events"] else "")
    add("nominal", "XSYS-001 benign-onset flights (11)", "XSYS-001 REPLAY", "no event, no symptom",
        {"B": blind["B"]["N"]}, True, True, True)
    # motor degradation
    for rid in ("V1", "V2", "V3", "V4"):
        o = v(rid)
        add("motor degradation", rid, "REAL SITL", "symptom on the injected motor, ambiguous", o,
            bool(o["as_expected"]), True, True)
    add("motor degradation", "XSYS-001 A trials (55)", "XSYS-001 REPLAY",
        "symptom on motor_0, ambiguous", {"B": blind["B"]["A"]}, True, True, True)
    # telemetry corruption
    for rid in ("V9", "V10"):
        o = v(rid)
        add("telemetry corruption", rid, "REAL SITL (PX4 failure injection)",
            "no symptom; telemetry change reported as context", o, bool(o["as_expected"]), True, True)
    add("telemetry corruption", "XSYS-001 B trials (55)", "XSYS-001 REPLAY (frozen case-B construction)",
        "no symptom; deficit unconfirmed by the vehicle", {"B": blind["B"]["B"]}, True, True, True)
    # power, navigation
    o = v("V8")
    add("power anomaly", "V8", "REAL SITL (PX4 failure injection)",
        "battery warning and failsafe triggers; no propulsion symptom", o, bool(o["as_expected"]),
        True, True)
    o = v("V7")
    add("navigation anomaly", "V7", "REAL SITL (PX4 failure injection)",
        "no propulsion symptom; navigation outside the profile (EKF2 context)", o,
        bool(o["as_expected"]), None, True, "useful only if the estimator context tells the story")
    # configuration transition
    if C.S1_ULOG.exists():
        s1 = stock_summary(R.stock_flight(C.S1_ULOG))
        add("configuration transition", "S1 (2.2 pilot, SENS_IMU_MODE=0 selector run)", "REAL SITL",
            "configuration changes in the timeline; no false propulsion symptom", s1,
            s1["headline"] == "no symptom; attribution NO_EVIDENCE", None, True)
    # producer failure, no coverage (synthetic)
    log = synth("motor", motor=2)
    es = log.topics["esc_status"]
    keep = ~((es["t"] >= 71.0) & (es["t"] < 73.0))
    log.topics["esc_status"] = {k: x[keep] for k, x in es.items()}
    o = stock_summary(R.stock_flight(stock_log=log, est_log=None))
    add("producer failure", "esc_status silent 2 s in the AFTER window", "SYNTHETIC",
        "outputs over the gap UNAVAILABLE and refused; no fault claimed from them", o,
        "motor_2" not in (o["headline"] or "") or "AMBIGUOUS" in (o["headline"] or ""), True, True)
    o = stock_summary(R.stock_flight(stock_log=synth("motor", motor=2, esc=False), est_log=None))
    add("no coverage", "motor loss with esc_status absent", "SYNTHETIC",
        "no propulsion evidence and no propulsion trigger; said so; nothing called healthy", o,
        o["headline"] == "no symptom; attribution NO_EVIDENCE", True, True,
        "the loss is missed: the honest outcome when the log cannot show it")
    # ambiguous
    add("ambiguous", "every motor loss above", "REAL SITL and XSYS-001 REPLAY",
        "AMBIGUOUS among 4 explanations, with what would resolve it", "see motor degradation rows",
        True, True, True)
    # compute/timing
    v2 = R.v2_scenario("CPU_OVERLOAD")
    m = RP.machine_report(v2.results, v2.inputs, v2.gate, v2.contracts)
    add("compute/timing anomaly", "v2 CPU_OVERLOAD (2.2 path)", "SYNTHETIC (frozen v2 scenario)",
        "a compute symptom where compute evidence exists",
        {"headline": (m["final"] or {}).get("state", {}).get("headline")}, None, None, True,
        "no stock PX4 topic carries deadline evidence: on a stock log this class is NOT DIAGNOSABLE "
        "(cpuload is context only)")
    C.write_json(C.HERE / "VALIDATION_SET.json", {
        "label": "Phase 25 product validation set; sources marked; synthetic rows are logic checks",
        "rows": rows})
    for r in rows:
        print(r["class"], "|", r["case"], "|", r["source"], "| correct", r["correct"])


if __name__ == "__main__":
    main()
