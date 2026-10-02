#!/usr/bin/env python3
"""RB-001 Part 18: stress the log-completeness mechanism offline. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/log_completeness_stress.py

Each case takes a real-structure log (2.3 validation flights, PX4 default
logging), damages it in a known way OFFLINE, and runs the unchanged product
path (`runs.stock_flight` on the damaged StockLog). The question for every
case is the brief's: missing samples must never become healthy evidence.

| case | damage | on |
|---|---|---|
| gap_in_window | esc_status and actuator_motors silent for 2 s inside the AFTER window of the injection event | V4 (loss on motor_0, hover) and V5 (nominal) |
| rate_reduced | esc_status and actuator_motors decimated from 10 Hz to 2 Hz | V4, V5 |
| producer_silent | battery_status removed entirely | V4 |
| esc_topic_absent | esc_status removed entirely | V4 |
| real_jitter | every topic's timestamps perturbed by the jitter RB0 measured on real boards (std 10 ms on actuator_outputs-class topics, 0.7 ms on IMU-class) | V4, V5 |
| logger_dropout | a 120 ms logger dropout (the largest in RB0) declared over the injection | V4 |

Writes LOG_COMPLETENESS_STRESS.json.
"""
from __future__ import annotations

import copy
import json

import numpy as np

import common_rb as C

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from csia_evidence_assurance.stock_log import StockLog

PROP = ("esc_status", "actuator_motors")


def onset(rid, log):
    rec = json.loads((C.SITL_2_3 / f"{rid}.json").read_text())
    ev = rec["events_ms"]
    return ev["onset_param_set"][0] * 1e-3 - log.t0_us * 1e-6 if "onset_param_set" in ev else None


def summarize(log):
    run = R.stock_flight(stock_log=log, est_log=None)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    anytime = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                      if c["what"] != "attribution" and c["to"]})
    vals = m["evidence_values"]
    return {"symptoms_any_time": anytime,
            "events": [round(e["t0"], 2) for e in m["events"]],
            "nominal_outputs": sum(1 for v in vals if v["state"] == "NOMINAL"
                                   and v.get("producer_health", "VALID") == "VALID"),
            "unavailable_by_health": sum(1 for v in vals if v.get("producer_health", "VALID") != "VALID"),
            "unavailable_records": sum(1 for v in vals if v["state"] == "UNAVAILABLE"),
            "notices": [n["source"] + ": " + n["why"] for n in m["coverage_report"]["coverage_notices"]]}


def drop_window(log, topics, a, b):
    out = copy.deepcopy(log)
    for tp in topics:
        d = out.topics[tp]
        keep = ~((d["t"] >= a) & (d["t"] < b))
        out.topics[tp] = {k: v[keep] for k, v in d.items()}
    return out


def decimate(log, topics, ms):
    return log.decimate({tp: ms for tp in topics})


def jitter(log, rng):
    out = copy.deepcopy(log)
    for tp, d in out.topics.items():
        sd = 0.0007 if tp in ("vehicle_angular_velocity",) else 0.010
        t = d["t"] + rng.normal(0.0, sd, len(d["t"]))
        order = np.argsort(t, kind="stable")
        out.topics[tp] = {k: (t[order] if k == "t" else v[order]) for k, v in d.items()}
    return out


def main():
    rows = {}
    rng = np.random.default_rng(20261002)
    for rid in ("V4", "V5"):
        base = StockLog.from_ulog(C.SITL_2_3 / f"{rid}.ulg").decimate()
        t_on = onset(rid, base)
        anchor = t_on if t_on is not None else 49.7     # V5: its second maneuver event
        rows[f"{rid}/undamaged"] = summarize(base)
        rows[f"{rid}/gap_in_window"] = summarize(drop_window(base, PROP, anchor + 11.0, anchor + 13.0))
        rows[f"{rid}/rate_reduced_2Hz"] = summarize(decimate(base, PROP, 500))
        rows[f"{rid}/real_jitter"] = summarize(jitter(base, rng))
        if rid == "V4":
            nb = copy.deepcopy(base)
            nb.topics.pop("battery_status")
            rows["V4/producer_silent_battery"] = summarize(nb)
            ne = copy.deepcopy(base)
            ne.topics.pop("esc_status")
            rows["V4/esc_topic_absent"] = summarize(ne)
            nd = copy.deepcopy(base)
            nd.dropouts = [(t_on + 10.5, 0.12)]
            rows["V4/logger_dropout_120ms"] = summarize(nd)
        print(rid, "done", flush=True)
    for k, v in rows.items():
        print(k, v["symptoms_any_time"], "nominal", v["nominal_outputs"], "health-unavail",
              v["unavailable_by_health"])
    C.write_json(C.HERE / "LOG_COMPLETENESS_STRESS.json", {
        "label": "RB-001 Part 18: offline damage to 2.3 validation logs; product path unchanged",
        "cases": rows})


if __name__ == "__main__":
    main()
