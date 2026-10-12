#!/usr/bin/env python3
"""Phase 15: runtime of 2.1.1 against 2.1.0 and frozen v2.0. RESEARCH ONLY.
DESKTOP CPYTHON TIMINGS; nothing here measures an embedded target.

    .venv/bin/python research/csia_semantic_core_2_1_revision/runtime_revision.py

Per tick over dataset A (2,640 ticks), three passes, per-tick median:
    v2_0             frozen localize_all + attribute
    pre_trace_off    2.1.0, trace off        pre_trace_on    2.1.0, trace on
    rev_trace_off    2.1.1 + r2, trace off   rev_trace_on    2.1.1 + r2, trace on
(the overlay is applied before timing: it is profile set-up, not reasoning).

Also:
- memory: tracemalloc peak on the largest tick;
- record scaling: the largest tick padded 1x to 32x (as the shadow study did);
- epoch admission cost: `admission.admit` alone and `reason(..., epochs)`
  against N stamped records, all current or all stale, N = 68 to 2,176;
- fault-policy cost: dataset A with one predicate faulted
  (NO_TIMING_SEGMENT_OVER_BUDGET), FAULT_POLICY_B on against off;
- retained state: the core's attributes before and after 2,640 ticks.

Writes RUNTIME_REVISION.json.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
import time
import tracemalloc
from dataclasses import replace

import revision_common as RC

import predicate_fault_study as F  # noqa: E402
import shadow_runtime as SR  # noqa: E402
import shadow_validation as S  # noqa: E402

from csia_semantic_core import Corrections, EpochContext, SemanticCore21  # noqa: E402
from csia_semantic_core import admission as A  # noqa: E402
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

OUT = RC.HERE / "RUNTIME_REVISION.json"
PASSES = 3
KEY = "ekf2.selector.instance_changed_count"


def timed(fn):
    t0 = time.perf_counter_ns()
    fn()
    return time.perf_counter_ns() - t0


def slope(points, key):
    xs = [math.log(p["records"]) for p in points]
    ys = [math.log(p[key]) for p in points]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                 / sum((x - mx) ** 2 for x in xs), 2)


def state_size(core):
    return {k: (len(v) if hasattr(v, "__len__") else None)
            for k, v in sorted(vars(core).items())}


def main():
    runs = S.runs_A()
    r2 = load_successor("aircraft_successor_r2")
    rev = Corrections.revised()
    ticks = [(engine, sa, r2.apply(sa.records)) for engine, res in runs.values() for sa in res]
    cores = {}
    for e, _sa, _r in ticks:
        if id(e) not in cores:
            cores[id(e)] = {
                "pre_trace_on": SemanticCore21.from_engine(e, trace=True),
                "pre_trace_off": SemanticCore21.from_engine(e, trace=False),
                "rev_trace_on": SemanticCore21.from_engine(e, rev, trace=True, pacing=r2.pacing_map()),
                "rev_trace_off": SemanticCore21.from_engine(e, rev, trace=False, pacing=r2.pacing_map())}
    keys = ("v2_0", "pre_trace_off", "pre_trace_on", "rev_trace_off", "rev_trace_on")
    per = {k: [[] for _ in ticks] for k in keys}
    before = state_size(cores[id(ticks[0][0])]["rev_trace_on"])
    for _ in range(PASSES):
        for i, (engine, sa, recs2) in enumerate(ticks):
            c = cores[id(engine)]
            recs = sa.records
            per["v2_0"][i].append(timed(lambda: SR.v20(engine, recs)))
            per["pre_trace_off"][i].append(timed(lambda: c["pre_trace_off"].reason(recs)))
            per["pre_trace_on"][i].append(timed(lambda: c["pre_trace_on"].reason(recs)))
            per["rev_trace_off"][i].append(timed(lambda: c["rev_trace_off"].reason(recs2)))
            per["rev_trace_on"][i].append(timed(lambda: c["rev_trace_on"].reason(recs2)))
    after = state_size(cores[id(ticks[0][0])]["rev_trace_on"])
    med = {k: [statistics.median(x) for x in v] for k, v in per.items()}
    out = {"harness": "semantic_core_2_1_revision_runtime",
           "label": "desktop CPython timings of one container; not an embedded target",
           "python": sys.version.split()[0], "ticks": len(ticks), "passes": PASSES,
           "per_tick": {k: SR.summary(v) for k, v in med.items()}}
    m = {k: SR.pct(v, .5) for k, v in med.items()}
    out["ratios_of_medians"] = {
        "rev_trace_off_over_pre_trace_off": round(m["rev_trace_off"] / m["pre_trace_off"], 3),
        "rev_trace_on_over_pre_trace_on": round(m["rev_trace_on"] / m["pre_trace_on"], 3),
        "rev_trace_off_over_v2_0": round(m["rev_trace_off"] / m["v2_0"], 2),
        "pre_trace_off_over_v2_0": round(m["pre_trace_off"] / m["v2_0"], 2)}
    out["retained_state"] = {"before": before, "after_2640_ticks_x3": after,
                             "unchanged": before == after}
    engine, big, big2 = max(ticks, key=lambda x: len(x[1].records))
    c = cores[id(engine)]
    mem = {"records_in_largest_tick": len(big.records)}
    for label, fn in (("v2_0", lambda: SR.v20(engine, big.records)),
                      ("pre_trace_off", lambda: c["pre_trace_off"].reason(big.records)),
                      ("pre_trace_on", lambda: c["pre_trace_on"].reason(big.records)),
                      ("rev_trace_off", lambda: c["rev_trace_off"].reason(big2)),
                      ("rev_trace_on", lambda: c["rev_trace_on"].reason(big2))):
        tracemalloc.start()
        fn()
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem[f"{label}_peak_kb"] = round(peak / 1024, 1)
    out["memory"] = mem
    scaling = []
    for k in (1, 2, 4, 8, 16, 32):
        recs = list(big2)
        for j in range(1, k):
            recs += [replace(r, component=f"{r.component}__pad{j}", dependencies=())
                     for r in big2]
        recs = tuple(recs)
        row = {"records": len(recs)}
        for key, fn in (("v2_0_us", lambda: SR.v20(engine, recs)),
                        ("pre_trace_off_us", lambda: c["pre_trace_off"].reason(recs)),
                        ("rev_trace_off_us", lambda: c["rev_trace_off"].reason(recs)),
                        ("rev_trace_on_us", lambda: c["rev_trace_on"].reason(recs))):
            row[key] = round(min(timed(fn) for _ in range(5)) / 1000, 1)
        scaling.append(row)
    out["record_scaling"] = {"points": scaling, "log_log_slope": {
        k: slope(scaling, k) for k in ("v2_0_us", "pre_trace_off_us",
                                       "rev_trace_off_us", "rev_trace_on_us")}}
    adm = []
    for k in (1, 2, 4, 8, 16, 32):
        base = list(big2)
        for j in range(1, k):
            base += [replace(r, component=f"{r.component}__pad{j}", dependencies=())
                     for r in big2]
        cur = tuple(replace(r, provenance=dict(r.provenance or {}, config_epoch={KEY: 3}))
                    for r in base)
        stale = tuple(replace(r, provenance=dict(r.provenance or {}, config_epoch={KEY: 2}))
                      for r in base)
        ctx = EpochContext({KEY: 3}, {KEY: "switch"})
        row = {"records": len(base)}
        row["admit_all_current_us"] = round(min(timed(lambda: A.admit(cur, ctx)) for _ in range(5)) / 1000, 1)
        row["admit_all_stale_us"] = round(min(timed(lambda: A.admit(stale, ctx)) for _ in range(5)) / 1000, 1)
        row["reason_unstamped_us"] = round(min(timed(lambda: c["rev_trace_off"].reason(tuple(base), ctx))
                                               for _ in range(5)) / 1000, 1)
        row["reason_all_stale_us"] = round(min(timed(lambda: c["rev_trace_off"].reason(stale, ctx))
                                               for _ in range(5)) / 1000, 1)
        adm.append(row)
    out["epoch_admission_cost"] = {"points": adm, "log_log_slope": {
        k: slope(adm, k) for k in ("admit_all_current_us", "admit_all_stale_us")}}
    fault = {"r1_off": [], "r1_on": []}
    for engine_, sa, _r in ticks:
        for label, corr in (("r1_off", Corrections()), ("r1_on", Corrections(fault_policy_b=True))):
            core = F.faulted_core(SemanticCore21.from_engine(engine_, corr, trace=False),
                                  "NO_TIMING_SEGMENT_OVER_BUDGET")
            fault[label].append(min(timed(lambda: core.reason(sa.records)) for _ in range(3)))
    out["fault_policy_cost"] = {k: SR.summary(v) for k, v in fault.items()}
    out["fault_policy_cost"]["median_ratio_on_over_off"] = round(
        SR.pct(fault["r1_on"], .5) / SR.pct(fault["r1_off"], .5), 3)
    RC.write_json(OUT, out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.exit(main())
