#!/usr/bin/env python3
"""POST-HOC analysis of the maneuver-study evaluation. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/posthoc_maneuver.py

Everything here was chosen AFTER the as-run result was seen. It reads the
as-run file, never rewrites it, changes no threshold and re-scores nothing.
Its outputs explain the as-run result; none of them is a result.

Writes MANEUVER_POSTHOC.json:
- B3: how close its estimate is to the true lost fraction (1 - eta), and the
  margin between the largest nominal estimate and theta_delta;
- B4: every wrong-motor VIOLATED, with the estimate that chose the motor;
- B2: why it missed, from the compensation C and the bin threshold;
- the product's own event rate per in-flight hour on the nominal and
  telemetry flights (Part 16 in SITL).
"""
from __future__ import annotations

import json

import numpy as np

import common_rb as C
import maneuver as M


def main():
    res = json.loads((C.HERE / "MANEUVER_RESULTS_EVAL.json").read_text())
    cal = json.loads((C.HERE / "MANEUVER_CALIBRATION.json").read_text())["calibration"]
    th = cal["theta_delta"]
    b3_onset, b4_wrong, b2_miss, nominal_delta, other_delta = [], [], [], [], []
    for r in res["flights"]:
        tr = r["truth"]
        first = True
        for e in r["events"]:
            if "states" not in e:
                continue
            st = e["states"]
            if e["class"] in ("NOMINAL", "PRE"):
                nominal_delta.append(max(e["delta"]))
                continue
            m = tr["motor"]
            other_delta.append(max(x for k, x in enumerate(e["delta"]) if k != m))
            if st["B3"][m] == "VIOLATED" and e["class"] == "POST" and first:
                b3_onset.append({"flight": r["flight"], "t0": e["t0"], "eta": tr["eta"],
                                 "lost_fraction": round(1 - tr["eta"], 3),
                                 "delta": e["delta"][m]})
                first = False
            for k, x in enumerate(st["B4"]):
                if x == "VIOLATED" and k != m:
                    b4_wrong.append({"flight": r["flight"], "t0": e["t0"], "class": e["class"],
                                     "injected": m, "named": k,
                                     "glr": [g[0] for g in e["glr"]],
                                     "estimate_named": e["glr"][k][1],
                                     "delta_injected_b3": e["delta"][m]})
        if tr["kind"] == "physical":
            hit = any(e.get("states", {}).get("B2", [None] * 4)[tr["motor"]] == "VIOLATED"
                      for e in r["events"])
            if not hit:
                for e in r["events"]:
                    if e.get("class") in ("POST", "STRADDLE"):
                        b = M._bin(e["R"])
                        b2_miss.append({"flight": r["flight"], "t0": e["t0"], "class": e["class"],
                                        "R": round(e["R"], 3), "C_injected": e["C"][tr["motor"]],
                                        "theta_C_bin": cal["theta_C_by_bin"][b] if b is not None else None,
                                        "state": e["states"]["B2"][tr["motor"]]})
                        break
    rates = {}
    for rid in ("EN1", "EN2", "EN3", "EN4", "ET1", "ET2"):
        f = M.load(C.OUT_RAW / "sitl" / f"{rid}.ulg", rid)
        hours = float(np.sum(np.diff(f.t)[f.in_flight[:-1]])) / 3600.0
        n = len(next(r for r in res["flights"] if r["flight"] == rid)["events"])
        rates[rid] = {"events": n, "in_flight_h": round(hours, 4)}
    tot_e = sum(v["events"] for v in rates.values())
    tot_h = sum(v["in_flight_h"] for v in rates.values())
    out = {
        "label": "POST-HOC: chosen after the as-run result was seen; explains it, re-scores nothing",
        "results_sha256": C.sha(C.HERE / "MANEUVER_RESULTS_EVAL.json"),
        "B3_first_post_onset_estimate": b3_onset,
        "B3_max_estimate_at_nominal_events": round(max(nominal_delta), 5),
        "B3_max_estimate_other_motors_after_onset": round(max(other_delta), 5),
        "theta_delta": th,
        "B4_wrong_motor": b4_wrong,
        "B2_missed_first_post_event": b2_miss,
        "product_events_nominal_and_telemetry_flights": dict(
            per_flight=rates, events=tot_e, in_flight_h=round(tot_h, 4),
            per_in_flight_hour=round(tot_e / tot_h, 1)),
    }
    C.write_json(C.HERE / "MANEUVER_POSTHOC.json", out)
    print(json.dumps(out, indent=1)[:6000])


if __name__ == "__main__":
    main()
