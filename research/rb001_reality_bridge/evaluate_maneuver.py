#!/usr/bin/env python3
"""Evaluate the maneuver-study candidates at the product's own events. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/evaluate_maneuver.py --set dev|eval

**Per flight:**
1. The product path, unchanged (`runs.stock_flight` on the ULog alone),
   gives the discovered events and the product's own result: B0 as shipped,
   with every symptom raised at any time.
2. At each event's AFTER checkpoint (t0 + 15 s, when it lies in the log)
   every candidate (`maneuver.decide`) gives a per-motor state, with the
   frozen calibration (MANEUVER_CALIBRATION.json) and its model.
3. The injection (from the run's JSON, read only now) sorts each event:
   - PRE (its AFTER window ends before the onset: a nominal window);
   - POST (the AFTER window starts at or after the onset);
   - STRADDLE (the onset falls inside the AFTER window).
   Telemetry injections (ESC OFF / WRONG) are not physical: every event of
   those flights is scored as nominal.

**Scoring (MANEUVER_PREREGISTRATION.md):**
- **false VIOLATED:** any motor VIOLATED at an event that is nominal (a
  nominal or telemetry flight, or PRE). In 2.1.1 a VIOLATED physical
  response raises COMMAND_NO_RESPONSE, so each one is a false symptom.
- **wrong motor:** a non-injected motor VIOLATED at a POST or STRADDLE event.
- **detected:** the injected motor VIOLATED at a POST or STRADDLE event.

Writes MANEUVER_RESULTS_<SET>.json.
"""
from __future__ import annotations

import argparse
import json


import common_rb as C
import maneuver as M

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R

SETS = {
    "dev": [(C.SITL_2_3, r) for r in ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9",
                                      "V10", "V11", "V12", "V13")],
    "eval": [(C.OUT_RAW / "sitl", r) for r in ("EN1", "EN2", "EN3", "EN4", "EF1", "EF2", "EF3",
                                               "EF4", "EF5", "EF6", "EH1", "ET1", "ET2")],
}


def truth(rec, t0_us):
    ev = rec.get("events_ms", {})
    spec = rec.get("spec", {})
    if "onset_param_set" in ev:
        name = spec["param"][0]
        return {"kind": "physical", "motor": int(name[-1]) - 1, "eta": spec["param"][1],
                "onset": ev["onset_param_set"][0] * 1e-3 - t0_us * 1e-6}
    if "inject_sent" in ev:
        return {"kind": "telemetry" if spec["inject"][0] == 106 else "other",
                "motor": None, "onset": ev["inject_sent"] * 1e-3 - t0_us * 1e-6}
    return {"kind": "nominal", "motor": None, "onset": None}


def event_class(t0, tr):
    if tr["kind"] != "physical":
        return "NOMINAL"
    a, b = t0 + 10.0, t0 + 15.0
    if b <= tr["onset"]:
        return "PRE"
    if a >= tr["onset"]:
        return "POST"
    return "STRADDLE"


def flight_rows(path, name, mdl, cal):
    rec = json.loads(path.with_suffix(".json").read_text())
    run = R.stock_flight(path)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    f = M.load(path, name)
    tr = truth(rec, f.stock.t0_us)
    product_any = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                          if c["what"] != "attribution" and c["to"]})
    d = M.residual(f, mdl)
    t_end = float(f.t[-1])
    events = []
    for e in m["events"]:
        t0 = float(e["t0"])
        if t0 + 15.0 > t_end:
            events.append({"t0": round(t0, 3), "checkpoint": "beyond the log"})
            continue
        s = M.statistics_at(f, mdl, d, t0)
        events.append({"t0": round(t0, 3), "class": event_class(t0, tr), "R": s["R"],
                       "saturated": s["saturated"],
                       "C": [round(x, 5) for x in s["C"]],
                       "delta": [round(x, 5) for x in s["delta"]],
                       "glr": [[round(g, 2), round(x, 5)] for g, x in s["glr"]],
                       "states": {c: M.decide(c, s, cal) for c in M.CANDIDATES}})
    return {"flight": name, "truth": tr, "ulog_sha256": rec.get("ulog_sha256"),
            "outcome": rec.get("outcome"), "product_symptoms_any_time": product_any,
            "events": events}


def score(rows):
    out = {}
    for c in M.CANDIDATES:
        false_v, wrong, unavailable, scored = 0, 0, 0, 0
        detected, faults = [], []
        for r in rows:
            tr = r["truth"]
            if tr["kind"] == "physical":
                faults.append(r["flight"])
            hit = False
            for e in r["events"]:
                if "states" not in e:
                    continue
                st = e["states"][c]
                scored += 1
                unavailable += sum(1 for x in st if x.startswith("UNAVAILABLE"))
                v = [k for k, x in enumerate(st) if x == "VIOLATED"]
                if e["class"] in ("NOMINAL", "PRE"):
                    false_v += len(v)
                else:
                    wrong += sum(1 for k in v if k != tr["motor"])
                    hit = hit or tr["motor"] in v
            if tr["kind"] == "physical" and hit:
                detected.append(r["flight"])
        out[c] = {"false_violated": false_v, "wrong_motor": wrong,
                  "detected": detected, "faults": faults,
                  "missed": [x for x in faults if x not in detected],
                  "events_scored": scored, "motor_states_unavailable": unavailable}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=sorted(SETS), required=True)
    a = ap.parse_args()
    calib = json.loads((C.HERE / "MANEUVER_CALIBRATION.json").read_text())
    cal, mdl = calib["calibration"], M.Model.from_dict(calib["model"])
    rows = []
    for d, rid in SETS[a.set]:
        p = d / f"{rid}.ulg"
        if not p.exists():
            rows.append({"flight": rid, "truth": None, "outcome": "NOT FLOWN", "events": []})
            continue
        rows.append(flight_rows(p, rid, mdl, cal))
        print(rid, rows[-1]["truth"]["kind"], len(rows[-1]["events"]),
              rows[-1]["product_symptoms_any_time"], flush=True)
    sc = score([r for r in rows if r["truth"]])
    C.write_json(C.HERE / f"MANEUVER_RESULTS_{a.set.upper()}.json", {
        "label": ("DEVELOPMENT data (2.3 V1-V13, already seen): not an evaluation"
                  if a.set == "dev" else
                  "EVALUATION set, as run, scored by the preregistered rules"),
        "calibration_sha256": C.sha(C.HERE / "MANEUVER_CALIBRATION.json"),
        "score": sc, "flights": rows})
    print(json.dumps(sc, indent=1))



if __name__ == "__main__":
    main()
