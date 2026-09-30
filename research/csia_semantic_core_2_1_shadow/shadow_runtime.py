#!/usr/bin/env python3
"""Runtime cost of shadow operation (Part 26) and the operation counts the
H743 estimate uses (Part 28). RESEARCH ONLY. DESKTOP CPYTHON TIMINGS.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/shadow_runtime.py

Per tick over dataset A (2,640 ticks), three passes, per-tick median:
    v2_0_alone       frozen localize_all + attribute (the reasoning step)
    v2_1_alone       2.1 reason(), trace on and trace off
    shadow_total     v2.0 reasoning + ShadowRunner.observe (2.1, comparison,
                     input hash, record building) -- what a deployment that
                     runs both pays
    shadow_overhead  ShadowRunner.observe alone (the cost added to v2.0)
Memory: tracemalloc peak for one tick of each, on the largest tick; size of
the per-tick comparison record as JSON.
Record scaling: the largest tick padded with unconnected copies of its own
records (renamed components), 1x to 32x.
Operation counts (2.1, per tick): records, localizations, predicate
evaluations, evidence rows read. These are what a C port would execute.
Writes SHADOW_RUNTIME.json only. Nothing here measures an embedded target.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"),
          str(REPO / "research/csia_semantic_core_2_1"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import shadow_validation as S  # noqa: E402

from csia.v2.attribution import attribute  # noqa: E402
from csia.v2.localization import localize_all  # noqa: E402
from csia_semantic_core import (SemanticCore21, SuccessorIndex,  # noqa: E402
                                localize_all_2_1)
from csia_semantic_core.shadow import ShadowRunner  # noqa: E402

OUT = HERE / "SHADOW_RUNTIME.json"
PASSES = 3


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summary(ns):
    us = [x / 1000.0 for x in ns]
    return {"mean_us": round(statistics.fmean(us), 1), "median_us": round(pct(us, 0.5), 1),
            "p95_us": round(pct(us, 0.95), 1), "p99_us": round(pct(us, 0.99), 1),
            "max_us": round(max(us), 1), "n": len(us)}


def v20(engine, recs):
    if engine.symptoms:
        localize_all(engine.symptoms, recs, engine.predicates)
    attribute(recs, engine.relations)


def timed(fn):
    t0 = time.perf_counter_ns()
    fn()
    return time.perf_counter_ns() - t0


def main():
    runs = S.runs_A()
    ticks = [(engine, sa) for engine, res in runs.values() for sa in res]
    cores = {id(e): (SemanticCore21.from_engine(e, trace=True),
                     SemanticCore21.from_engine(e, trace=False),
                     ShadowRunner(e, trace=True, time_v2=False)) for e, _ in ticks}
    per = {k: [[] for _ in ticks] for k in ("v2_0_alone", "v2_1_trace", "v2_1_no_trace",
                                             "shadow_overhead")}
    for _ in range(PASSES):
        for i, (engine, sa) in enumerate(ticks):
            ct, cn, runner = cores[id(engine)]
            recs = sa.records
            per["v2_0_alone"][i].append(timed(lambda: v20(engine, recs)))
            per["v2_1_trace"][i].append(timed(lambda: ct.reason(recs)))
            per["v2_1_no_trace"][i].append(timed(lambda: cn.reason(recs)))
            per["shadow_overhead"][i].append(timed(lambda: runner.observe(sa)))
            runner.log.clear()
    med = {k: [statistics.median(x) for x in v] for k, v in per.items()}
    med["shadow_total"] = [a + b for a, b in zip(med["v2_0_alone"], med["shadow_overhead"])]
    out = {"harness": "semantic_core_2_1_shadow_runtime",
           "label": "desktop CPython timings of one container; not an embedded target",
           "python": sys.version.split()[0], "ticks": len(ticks), "passes": PASSES,
           "per_tick": {k: summary(v) for k, v in med.items()}}
    out["ratios_of_medians"] = {
        "v2_1_trace_over_v2_0": round(pct(med["v2_1_trace"], .5) / pct(med["v2_0_alone"], .5), 2),
        "v2_1_no_trace_over_v2_0": round(pct(med["v2_1_no_trace"], .5) / pct(med["v2_0_alone"], .5), 2),
        "shadow_total_over_v2_0": round(pct(med["shadow_total"], .5) / pct(med["v2_0_alone"], .5), 2)}

    # memory, largest tick
    engine, big = max(ticks, key=lambda x: len(x[1].records))
    ct, cn, runner = cores[id(engine)]
    mem = {"records_in_largest_tick": len(big.records)}
    for label, fn in (("v2_0_alone", lambda: v20(engine, big.records)),
                      ("v2_1_trace", lambda: ct.reason(big.records)),
                      ("v2_1_no_trace", lambda: cn.reason(big.records)),
                      ("shadow_observe", lambda: runner.observe(big))):
        tracemalloc.start()
        fn()
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem[f"{label}_peak_kb"] = round(peak / 1024, 1)
    runner.log.clear()
    rec = runner.observe(big)
    mem["shadow_record_json_bytes_largest_tick"] = len(json.dumps(rec, default=str))
    sizes = []
    for engine_, sa in ticks[::20]:
        r2 = cores[id(engine_)][2]
        sizes.append(len(json.dumps(r2.observe(sa), default=str)))
        r2.log.clear()
    mem["shadow_record_json_bytes_median"] = int(statistics.median(sizes))
    out["memory"] = mem

    # record scaling
    scaling = []
    for k in (1, 2, 4, 8, 16, 32):
        recs = list(big.records)
        for j in range(1, k):
            recs += [replace(r, component=f"{r.component}__pad{j}", dependencies=())
                     for r in big.records]
        recs = tuple(recs)
        a = [timed(lambda: v20(engine, recs)) for _ in range(5)]
        b = [timed(lambda: cn.reason(recs)) for _ in range(5)]
        c = [timed(lambda: ct.reason(recs)) for _ in range(5)]
        scaling.append({"records": len(recs), "v2_0_us": round(min(a) / 1000, 1),
                        "v2_1_no_trace_us": round(min(b) / 1000, 1),
                        "v2_1_trace_us": round(min(c) / 1000, 1)})

    def slope(key):
        xs = [math.log(s["records"]) for s in scaling]
        ys = [math.log(s[key]) for s in scaling]
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                     / sum((x - mx) ** 2 for x in xs), 2)

    out["record_scaling"] = {"points": scaling,
                             "log_log_slope": {k: slope(k) for k in
                                               ("v2_0_us", "v2_1_no_trace_us", "v2_1_trace_us")}}

    # operation counts per tick (2.1)
    counts = {"records": [], "localizations": [], "predicate_evaluations": [],
              "rows_read": []}
    for engine_, sa in ticks:
        core = SemanticCore21.from_engine(engine_, trace=True)
        ix = SuccessorIndex(sa.records, tracing=True)
        locs = localize_all_2_1(core.symptoms, ix, core.predicates) if core.symptoms else ()
        counts["records"].append(len(sa.records))
        counts["localizations"].append(len(locs))
        counts["predicate_evaluations"].append(len(ix.evaluations))
        counts["rows_read"].append(sum(len(ev["read"]) for ev in ix.evaluations))
    out["operation_counts_2_1_per_tick"] = {
        k: {"median": statistics.median(v), "max": max(v)} for k, v in counts.items()}
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
