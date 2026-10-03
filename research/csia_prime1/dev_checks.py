#!/usr/bin/env python3
"""PRIME-1 development checks: the successor against the historical release on every
log already on this machine. RESEARCH ONLY. IN-SAMPLE: every log here was used by
2.3, RB-001 or PRIME, so nothing here is promotion evidence (that is the held-out
evaluation, `heldout_eval.py`).

    .venv/bin/python research/csia_prime1/dev_checks.py

Per log and release: events, trigger kinds, symptoms at any time, attribution,
localization candidates, and the in-flight hours. Writes DEV_CHECKS.json.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import common_prime1 as C
import prime_a_gate as PA

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs
from csia_evidence_assurance.stock_log import StockLog

#: Ground truth from the flight records (scoring only; never an Analyzer input).
FAULT = {"V1": 1, "V2": 2, "V3": 3, "V4": 0, "V12": 2, "V13": 2,
         "EF1": 0, "EF2": 1, "EF3": 2, "EF4": 3, "EF5": 1, "EF6": 3, "EH1": 0}
TELEMETRY = {"V9": 1, "V10": 2, "ET1": 2, "ET2": 0}
NOMINAL = {"V5", "V6", "V11", "CAL1", "CAL2", "CAL3", "CAL4", "CAL5", "EN1", "EN2", "EN3", "EN4"}


def in_flight_hours(log) -> float:
    vs = log.topics.get("vehicle_status")
    if vs is None or not len(vs["t"]):
        return 0.0
    t = vs["t"]
    fl = log.in_flight(t)
    return float(np.sum(np.diff(t)[fl[:-1]])) / 3600.0


def one(args):
    path, release = args
    log = StockLog.from_ulog(path)
    run = runs.stock_flight(path, stock_log=log, release=release)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    syms = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})
    loc = m["final"].get("localizations", [])
    return {"log": path.stem, "release": release, "hours": round(in_flight_hours(log), 5),
            "events": [{"t0": e["t0"], "kinds": e["trigger_kinds"]} for e in m["events"]],
            "symptoms": syms, "attribution": m["summary"]["attribution"]["verdict"],
            "unique": [x["key"] for x in loc if x.get("outcome") == "UNIQUE"],
            "telemetry_reasons": sorted({c for v in m["evidence_values"] if v["producer_id"].endswith("telemetry_response")
                                         for c in v["reason_codes"]})}


def main():
    logs = PA.logs()
    jobs = [(p, r) for p in logs for r in ("2.3", "prime1")]
    with ProcessPoolExecutor(4) as ex:
        rows = list(ex.map(one, jobs))
    by = {}
    for r in rows:
        by.setdefault(r["log"], {})[r["release"]] = r
    out = {"label": "PRIME-1 development checks; IN-SAMPLE (every log was used before)", "logs": by}
    summ = {}
    for rel in ("2.3", "prime1"):
        nom = [by[k][rel] for k in by if k in NOMINAL]
        hours = sum(x["hours"] for x in nom)
        summ[rel] = {"nominal_logs": len(nom), "nominal_in_flight_hours": round(hours, 4),
                     "nominal_events": sum(len(x["events"]) for x in nom),
                     "nominal_events_per_hour": round(sum(len(x["events"]) for x in nom) / hours, 1) if hours else None,
                     "nominal_symptom_logs": [x["log"] for x in nom if x["symptoms"]],
                     "wrong_motor_symptoms": [k for k in by if k in FAULT and any(
                         s.endswith(f"motor_{j}") for s in by[k][rel]["symptoms"] for j in range(4) if j != FAULT[k])],
                     "telemetry_case_symptoms": [k for k in by if k in TELEMETRY and by[k][rel]["symptoms"]],
                     "any_unique": [k for k in by if by[k][rel]["unique"]]}
    out["summary"] = summ
    out["decision_differences"] = {k: {"2.3": [by[k]["2.3"]["symptoms"], by[k]["2.3"]["attribution"]],
                                       "prime1": [by[k]["prime1"]["symptoms"], by[k]["prime1"]["attribution"]]}
                                   for k in sorted(by)
                                   if (by[k]["2.3"]["symptoms"], by[k]["2.3"]["attribution"])
                                   != (by[k]["prime1"]["symptoms"], by[k]["prime1"]["attribution"])}
    C.write_json(C.HERE / "DEV_CHECKS.json", out)
    print(json.dumps(summ, indent=1))
    print("decision differences:", json.dumps(out["decision_differences"], indent=1))


if __name__ == "__main__":
    sys.exit(main())
