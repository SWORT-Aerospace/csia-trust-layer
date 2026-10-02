#!/usr/bin/env python3
"""Phase 26: false events on logs where nothing, or nothing at that time,
was injected. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/false_positive_search.py

Logs, each through the product path (`runs.stock_flight`, configuration B:
stock producers and PX4 monitors, discovered events):
1. the 66 XSYS-001 flights, at default logging rates (the stock extracts):
   - 55 fault flights: an event more than 2 s before the injection is
     false;
   - 11 benign-onset flights (NB): every event is false, and one near the
     benign heading-change onset is counted separately;
2. the validation flights (VALIDATION_FLIGHTS_DESIGN.md), when present:
   - V5 and V6 (nominal, maneuvering): every event is false;
   - the others: an event more than 2 s before the injection is false.

Every injection persists to the end of its flight, so an event more than
2 s AFTER it may be a consequence (a failsafe seconds after a GPS loss) or
unrelated. Those are counted apart ("later, while the injection
persists"), never as false and never as detections.

Per false event: its trigger kinds, its duration (to "cleared" when every
CUSUM in it returned to zero), and whether the analysis RETAINED it (a
symptom was raised at one of its checkpoints) or DISMISSED it (no
symptom: the stock producers found nothing 2.1.1 would localise).
Rates are per flight and per in-flight hour (armed and not landed).
Writes FALSE_POSITIVE_SEARCH.json.
"""
from __future__ import annotations

import json

import numpy as np

import common_23 as C

from csia_evidence_assurance import runs as R
from csia_evidence_assurance.adapters import px4_estimator as PX
from csia_evidence_assurance.stock_log import StockLog

MATCH_S = 2.0
EXTRACTS = C.OUT_RAW / "extracts"
VAL = C.OUT_RAW / "validation"


def in_flight_s(log) -> float:
    t_end = max(float(v["t"][-1]) for v in log.topics.values() if len(v["t"]))
    t = np.arange(0.0, t_end, 0.01)
    return float(np.count_nonzero(log.in_flight(t)) * 0.01)


def symptoms_by_event(run) -> dict:
    """event id -> symptom keys raised at any of its checkpoints."""
    out = {}
    for e in run.extras["events"]:
        keys = set()
        for r in run.results:
            d = r.to_dict()
            if d["event_time"] >= e["t0"] - 1e-6 and d["event_time"] <= e["t0"] + 15.0 + 1e-6:
                keys |= {x["key"] for x in d["localizations"]}
        out[e["event_id"]] = sorted(keys)
    return out


def flight_row(name, stock, est, onset, kind):
    run = R.stock_flight(stock_log=stock, est_log=est)
    syms = symptoms_by_event(run)
    evs = []
    for e in run.extras["events"]:
        true = onset is not None and kind != "NB" and abs(e["t0"] - onset) <= MATCH_S
        later = onset is not None and kind != "NB" and e["t0"] > onset + MATCH_S
        dur = (e["cleared_t"] - e["t0"]) if e.get("cleared_t") else None
        evs.append({"event_id": e["event_id"], "t0": round(e["t0"], 3), "true": true,
                    "later_while_injected": later,
                    "near_benign_onset": kind == "NB" and onset is not None
                    and abs(e["t0"] - onset) <= MATCH_S,
                    "before_onset": onset is not None and e["t0"] < onset - MATCH_S,
                    "trigger_kinds": e["trigger_kinds"], "motors": e["motors"],
                    "triggers": len(e["triggers"]),
                    "duration_s": None if dur is None else round(dur, 3),
                    "symptoms": syms[e["event_id"]],
                    "retained": bool(syms[e["event_id"]])})
    return {"flight": name, "kind": kind, "onset_log_s": onset,
            "in_flight_s": round(in_flight_s(stock.decimate()), 2), "events": evs,
            "false_events": [e for e in evs if not e["true"] and not e["later_while_injected"]],
            "later_events": [e for e in evs if e["later_while_injected"]]}


def main():
    truth = json.loads((C.HERE / "ONSET_TRUTH.json").read_text())["flights"]
    rows = []
    for name, tr in sorted(truth.items()):
        stock = StockLog.from_npz(EXTRACTS / f"{name}.npz")
        est = PX.EstimatorLog.from_npz(EXTRACTS / f"{name}.est.npz")
        rows.append(flight_row(name, stock, est, tr["onset_s"], tr["condition"]))
        print(name, len(rows[-1]["events"]), len(rows[-1]["false_events"]), flush=True)
    vt = {"V1": "motor", "V2": "motor", "V3": "motor", "V4": "motor", "V5": "nominal",
          "V6": "nominal", "V7": "gps_off", "V8": "battery_wrong", "V9": "esc_off",
          "V10": "esc_wrong"}
    for rid, kind in vt.items():
        ulg = VAL / f"{rid}.ulg"
        if not ulg.exists():
            continue
        rec = json.loads((VAL / f"{rid}.json").read_text())
        stock = StockLog.from_ulog(ulg)
        ev = rec.get("events_ms", {})
        ms = ev.get("onset_param_set", [None])[0] if "onset_param_set" in ev else ev.get("inject_sent")
        onset = None if ms is None else ms * 1e-3 - stock.t0_us * 1e-6
        rows.append(flight_row(rid, stock, PX.EstimatorLog.from_ulog(ulg), onset, kind))
        print(rid, len(rows[-1]["events"]), len(rows[-1]["false_events"]), flush=True)

    def agg(sel):
        rs = [r for r in rows if sel(r)]
        fe = [e for r in rs for e in r["false_events"]]
        hours = sum(r["in_flight_s"] for r in rs) / 3600.0
        kinds: dict = {}
        for e in fe:
            for k in e["trigger_kinds"]:
                kinds[k] = kinds.get(k, 0) + 1
        return {"flights": len(rs), "in_flight_h": round(hours, 3),
                "false_events": len(fe),
                "later_events_while_injected": sum(len(r["later_events"]) for r in rs),
                "flights_with_false_events": sum(1 for r in rs if r["false_events"]),
                "per_flight": round(len(fe) / len(rs), 3) if rs else None,
                "per_in_flight_hour": round(len(fe) / hours, 2) if hours else None,
                "by_trigger_kind": dict(sorted(kinds.items())),
                "retained": sum(1 for e in fe if e["retained"]),
                "dismissed": sum(1 for e in fe if not e["retained"]),
                "before_onset": sum(1 for e in fe if e["before_onset"]),
                "near_benign_onset": sum(1 for e in fe if e["near_benign_onset"]),
                "durations_s": sorted(e["duration_s"] for e in fe if e["duration_s"] is not None)}
    summary = {"xsys_fault_flights": agg(lambda r: r["kind"] == "A"),
               "xsys_benign_onset_flights": agg(lambda r: r["kind"] == "NB"),
               "validation_nominal_maneuvering": agg(lambda r: r["kind"] == "nominal"),
               "validation_injected": agg(lambda r: r["flight"].startswith("V")
                                          and r["kind"] != "nominal"),
               "all": agg(lambda r: True)}
    C.write_json(C.HERE / "FALSE_POSITIVE_SEARCH.json", {
        "label": "Phase 26: false events, configuration B (stock producers and PX4 monitors)",
        "match_s": MATCH_S, "summary": summary, "flights": rows})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
