#!/usr/bin/env python3
"""Phase 13: the frozen v1.1 CUSUM as an event trigger, where it has coverage.

    .venv/bin/python research/csia_2_3_stock_bridge/cusum_trigger_study.py

The frozen CUSUM bank (k = 0.5, h = 500) reads the v1 simulation's
per-node physics chi-square. A PX4 log has no such input, so on PX4 data
it has no coverage (events.py reports that). Its coverage is the frozen v1
scenarios, and this study runs it there, unchanged, through the adapter
(`adapters/cusum.py`), and turns each node's alarm rising edge into an
`events.Trigger`. Clustering is `events.cluster` (GAP_S = 3.0 s), the same
rule the PX4 path uses.

Per scenario: the injected faults (from the scenario definition, for
scoring only), the alarms, the events after clustering, detection delay,
false events (an alarm before any fault's onset, or more than 2 s after
it ended), the onset estimate's error (scored apart from detection), duplicates absorbed by clustering, and
clearance (whether and when each alarmed node returned to S <= h).

It is a trigger study, not attribution: the CUSUM's records are
attributable=False, and no event says which node failed.
Writes CUSUM_TRIGGER_STUDY.json.
"""
from __future__ import annotations

import numpy as np

import common_23 as C

from csia.scenarios import SCENARIOS, run_scenario
from csia.v1_1 import sequential as SEQ
from csia_evidence_assurance import events as EV
from csia_evidence_assurance.adapters import cusum as CU

MATCH_S = 2.0


def study(name):
    title, faults, td, _hist, _diag = run_scenario(name)
    prod = CU.CusumProducer()
    names = sorted(td.fresh)
    prev, S_hist, alarm_t, clear_t = {}, {}, {}, {}
    triggers = []
    for k in range(len(td.t)):
        t = float(td.t[k])
        fresh = {n: bool(td.fresh[n][k]) for n in names}
        phys = {n: (float(lam[k]), float(np.asarray(g).flat[min(k, np.asarray(g).size - 1)]))
                for n, (lam, g) in td.physics.items()}
        for e in prod.step(t, phys, fresh):
            node = e.record.component.split(".", 1)[1]
            on = e.record.observation_state.value == "DEGRADED"
            S_hist.setdefault(node, []).append((t, e.detail.get("S")))
            if on and not prev.get(node):
                alarm_t.setdefault(node, []).append(t)
                # onset estimate: the last tick with S = 0 before the alarm
                last0 = max((tt for tt, s in S_hist[node] if s is not None and s <= 0), default=t)
                triggers.append(EV.Trigger("cusum:v1_1_sequential", "cusum.sustained_shift",
                                           last0, t, None, e.detail.get("S"), "CUSUM statistic",
                                           None, {"node": node}))
            if prev.get(node) and not on:
                clear_t.setdefault(node, []).append(t)
            prev[node] = on
    events = EV.cluster(triggers)
    fl = [{"kind": f.kind, "target": f.target, "start": f.start, "end": f.start + f.duration}
          for f in faults]
    onsets = sorted({f["start"] for f in fl})
    rows = []
    for e in events:
        # matched on the ALARM: at or after a fault's onset and before its
        # end + MATCH_S. The onset estimate is scored separately: a CUSUM
        # with h = 500 wanders above 0 in control, so "the last S = 0" can
        # lie well before the onset.
        near = [o for o in onsets if o <= e.first_alarm_t <= max(
            f["end"] for f in fl if f["start"] == o) + MATCH_S] if onsets else []
        rows.append({"event_id": e.event_id, "t0": round(e.t0, 3),
                     "first_alarm_t": round(e.first_alarm_t, 3),
                     "nodes": sorted({t.detail["node"] for t in e.triggers}),
                     "triggers": len(e.triggers),
                     "matched_onset": near[0] if near else None,
                     "delay_from_onset_s": round(e.first_alarm_t - near[0], 3) if near else None,
                     "onset_estimate_error_s": round(e.t0 - near[0], 3) if near else None})
    fault_nodes = sorted({f["target"] for f in fl})
    return {"scenario": name, "title": title, "faults": fl,
            "covered_nodes": sorted(SEQ.CusumBank().stats),
            "not_covered": sorted(SEQ.NO_RESIDUAL),
            "fault_targets_covered": [n for n in fault_nodes if n in SEQ.CusumBank().stats],
            "fault_targets_not_covered": [n for n in fault_nodes if n not in SEQ.CusumBank().stats],
            "alarms": {n: v for n, v in sorted(alarm_t.items())},
            "cleared": {n: v for n, v in sorted(clear_t.items())},
            "alarms_total": len(triggers), "events": rows,
            "duplicates_absorbed": len(triggers) - len(events),
            "false_events": sum(1 for r in rows if r["matched_onset"] is None),
            "detected": [o for o in onsets if any(r["matched_onset"] == o for r in rows)],
            "missed": [o for o in onsets if not any(r["matched_onset"] == o for r in rows)],
            "duration_s": float(td.t[-1])}


def main():
    out = [study(n) for n in SCENARIOS]
    for r in out:
        print(r["scenario"], "alarms", r["alarms_total"], "events", len(r["events"]),
              "false", r["false_events"], "missed", r["missed"], flush=True)
    tot_s = sum(r["duration_s"] for r in out)
    C.write_json(C.HERE / "CUSUM_TRIGGER_STUDY.json", {
        "label": "frozen v1.1 CUSUM as an event trigger on the frozen v1 scenarios (its coverage)",
        "match_s": MATCH_S, "gap_s": EV.GAP_S, "scenarios": out,
        "totals": {"scenarios": len(out), "simulated_s": round(tot_s, 1),
                   "alarms": sum(r["alarms_total"] for r in out),
                   "events": sum(len(r["events"]) for r in out),
                   "false_events": sum(r["false_events"] for r in out),
                   "faults": sum(len({f["start"] for f in r["faults"]}) for r in out),
                   "missed": sum(len(r["missed"]) for r in out)}})


if __name__ == "__main__":
    main()
