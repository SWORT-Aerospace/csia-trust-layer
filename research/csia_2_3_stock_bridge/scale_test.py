#!/usr/bin/env python3
"""Phase 11: does the quad profile's reasoning grow with the motor count?

    .venv/bin/python research/csia_2_3_stock_bridge/scale_test.py [--reps 30]

Method. One real event, XS1A1-C00-A-E055 (motor_0 at eta = 0.55), through
the stock producers at its three checkpoints (T1, EARLY, AFTER). For a
profile of N motors (`build_quad_engine(N)`, the scale-test parameter; the
r1 profile is N = 4), motor j's outputs are:
- motor_0's outputs, renamed to motor_j, for the first k motors (adverse);
- motor_1's outputs, renamed, for the rest (healthy, as recorded).
The battery outputs are kept. Every envelope is a real producer output;
only the component name changes.

Measured on the AFTER tick, with a fresh Analyzer per configuration:
- symptoms raised, hypotheses examined, candidates left (ambiguity),
  predicate evaluations (from 2.1.1's own trace);
- the step's wall time (median of `--reps`), peak Python allocation
  (tracemalloc) and the size of its machine form (JSON bytes);
- the diagnosability probe's time and output size (Phase 24).

N = 1 and 4 are the brief's comparison. N = 2, 6, 8, 12, 16 and k up to
N are the search for combinatorial growth. Writes SCALE_2_3.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from dataclasses import replace

import common_23 as C

from csia_evidence_assurance import diagnosability as DG
from csia_evidence_assurance import events as EV
from csia_evidence_assurance import runs as R
from csia_evidence_assurance.adapters import px4_stock as PS
from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer
from csia_evidence_assurance.contract import load_contracts
from csia_evidence_assurance.profiles import multirotor_quad as Q
from csia_evidence_assurance.stock_log import StockLog

FLIGHT = "XS1A1-C00-A-E055"


def base_outputs():
    log = StockLog.from_npz(C.OUT_RAW / "extracts" / f"{FLIGHT}.npz").decimate()
    cal = PS.load_calibration()
    events, _t, _n = EV.discover(log, None, cal)
    t0 = events[0].t0
    sp = PS.StockProducers(log, "sensor:imu.0", cal)
    ticks = [(t0 + PS.CHECKPOINTS[cp], sp.at(t0, cp)) for cp in ("T1", "EARLY", "AFTER")]
    return t0, ticks


def _rename(env, j):
    return replace(env, record=replace(env.record, component=f"motor_{j}"))


def remap(envs, n, k):
    out = [e for e in envs if not e.record.component.startswith("motor_")]
    by = {}
    for e in envs:
        if e.record.component.startswith("motor_"):
            by.setdefault(e.record.component, []).append(e)
    for j in range(n):
        src = by.get("motor_0" if j < k else "motor_1", [])
        out += [_rename(e, j) for e in src]
    return out


def measure(ticks, t0, n, k, reps):
    engine, core, gate = R.quad_setup(n)
    contracts = load_contracts(*PS.CONTRACT_FILES)
    an = FlightAssuranceAnalyzer(core, contracts, gate, Q.BASE)
    seq = [(t, remap(envs, n, k)) for t, envs in ticks]
    for t, envs in seq[:-1]:
        an.step(t, envs, events={PS.EVENT: t0})
    t_last, last = seq[-1]
    res = an.step(t_last, last, events={PS.EVENT: t0})
    times = []
    for _ in range(reps):
        a = time.perf_counter()
        an.step(t_last, last, events={PS.EVENT: t0})
        times.append(time.perf_counter() - a)
    tracemalloc.start()
    an.step(t_last, last, events={PS.EVENT: t0})
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tick = an.last_tick
    locs = tick.localizations
    preds = sum(len(x.trace.get("predicates", {})) for x in locs)
    examined = sum(len(x.supported) + len(x.unresolved) + len(x.v2.rejected) for x in locs)
    left = [len(set(x.supported) | set(x.unresolved)) for x in locs]
    d = res.to_dict()
    observable = sorted({f"{e.record.domain}/{e.record.component}:{e.record.relation}"
                         for _t, envs in seq for e in envs
                         if e.record.observation_state.value != "UNAVAILABLE"})
    a = time.perf_counter()
    dg = DG.analyze(core, Q.sample_records(engine), observable, gate.records)
    dg_s = time.perf_counter() - a
    return {"n_motors": n, "k_adverse": k, "profile_records": len(gate.records),
            "gate": gate.status, "envelopes": len(last),
            "symptoms": len(locs), "hypotheses_examined": examined,
            "candidates_left_per_symptom": left, "predicate_evaluations": preds,
            "headline": d["state"]["headline"], "attribution": d["attribution"]["verdict"],
            "step_ms_median": round(1000 * statistics.median(times), 3),
            "step_ms_max": round(1000 * max(times), 3),
            "peak_alloc_kb": round(peak / 1024, 1),
            "result_json_bytes": len(json.dumps(d, sort_keys=True)),
            "diagnosability_ms": round(1000 * dg_s, 1),
            "diagnosability_json_bytes": len(json.dumps(dg, sort_keys=True))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=30)
    a = ap.parse_args()
    t0, ticks = base_outputs()
    rows = []
    for n in (1, 2, 4, 6, 8, 12, 16):
        for k in sorted({0, 1, min(2, n), n}):
            rows.append(measure(ticks, t0, n, k, a.reps))
            print(json.dumps({x: rows[-1][x] for x in ("n_motors", "k_adverse", "symptoms",
                                                       "hypotheses_examined", "step_ms_median",
                                                       "diagnosability_ms")}), flush=True)
    C.write_json(C.HERE / "SCALE_2_3.json", {
        "label": "Phase 11 scale test; synthetic motor counts built from one real event's outputs",
        "flight": FLIGHT, "event_t0": t0, "reps": a.reps, "rows": rows})


if __name__ == "__main__":
    main()
