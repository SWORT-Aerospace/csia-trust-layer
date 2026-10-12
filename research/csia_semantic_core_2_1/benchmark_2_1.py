#!/usr/bin/env python3
"""Phase I: runtime cost of Semantic Core 2.1 against frozen v2. RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1/benchmark_2_1.py

Writes `PHASE_I_BENCHMARK.json`. **Wall-clock numbers are desktop CPython
timings of this container.** They are not reproducible bit for bit, they
say nothing about an embedded target, and the C runtime (`embedded/`) does
not implement 2.1 at all. The file records the interpreter and platform
beside the numbers.

Measured:

- **Stages.** Localization, attribution and the two combined. Frozen v2 is
  measured against 2.1 with the full trace and against 2.1 with
  `trace=False`, on the 44 shipped final ticks and on all 2,640 ticks.
- **Memory.** Peak traced memory and allocated blocks per tick
  (tracemalloc), and retained memory after 2,640 ticks with one reasoner
  reused. 2.1 holds no state between ticks, so nothing should grow.
- **Scaling.** One final tick padded with 1x to 32x unconnected records; the
  log-log slope of time against record count is reported per stage.
- **Worst cases, constructed on purpose:**
  - many records under one (domain, component, relation) key, for C6's
    bucket comparison;
  - a long dependency chain, for the C3 scope closure and the C1
    alternative walk.
- **Property-test overhead**, reported separately: the wall time of
  `tests/test_semantic_core_2_1.py` in its own pytest process.
"""
from __future__ import annotations

import gc
import json
import math
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AUDIT = REPO / "research/csia_semantic_correctness"
for p in (str(REPO), str(AUDIT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import semantic_probe as P  # noqa: E402

from csia.v2.attribution import attribute  # noqa: E402
from csia.v2.localization import localize_all  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import (Corrections, SemanticCore21,  # noqa: E402
                                SuccessorIndex, attribute_2_1,
                                localize_all_2_1)

OUT = HERE / "PHASE_I_BENCHMARK.json"
OS = P.OS
REPEAT = 7


def best_of(fn, n=REPEAT):
    """Median of n runs, seconds. One warm-up run first."""
    fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t0)
    return statistics.median(out)


def stages(engine, ticks):
    """Seconds for the whole list of ticks, per stage and variant."""
    cfg = P.cfg_of(engine)
    full = SemanticCore21.from_engine(engine, trace=True)
    lean = SemanticCore21.from_engine(engine, trace=False)
    recs = [t.records for t in ticks]
    frozen_locs = [localize_all(cfg.symptoms, r, cfg.predicates) for r in recs]
    lean_locs = [localize_all_2_1(lean.symptoms, SuccessorIndex(r, tracing=False),
                                  lean.predicates, False) for r in recs]

    def f_loc():
        for r in recs:
            localize_all(cfg.symptoms, r, cfg.predicates)

    def f_attr():
        for r in recs:
            attribute(r, cfg.relations)

    def f_all():
        for r in recs:
            localize_all(cfg.symptoms, r, cfg.predicates)
            attribute(r, cfg.relations)

    def s_loc(core):
        def run():
            for r in recs:
                localize_all_2_1(core.symptoms,
                                 SuccessorIndex(r, tracing=core.trace),
                                 core.predicates, core.trace)
        return run

    def s_attr():
        for r, locs in zip(recs, lean_locs):
            attribute_2_1(SuccessorIndex(r, tracing=False).records,
                          cfg.relations, locs)

    def s_all(core):
        def run():
            for r in recs:
                core.reason(r)
        return run

    assert frozen_locs is not None
    return {"frozen": {"localization": best_of(f_loc), "attribution": best_of(f_attr),
                       "combined": best_of(f_all)},
            "2_1_trace": {"localization": best_of(s_loc(full)),
                          "combined": best_of(s_all(full))},
            "2_1_no_trace": {"localization": best_of(s_loc(lean)),
                             "attribution": best_of(s_attr),
                             "combined": best_of(s_all(lean))}}


def memory(engine, records):
    cfg = P.cfg_of(engine)
    out = {}
    for tag, fn in (
            ("frozen", lambda: (localize_all(cfg.symptoms, records, cfg.predicates),
                                attribute(records, cfg.relations))),
            ("2_1_trace", lambda: SemanticCore21.from_engine(engine).reason(records)),
            ("2_1_no_trace", lambda: SemanticCore21.from_engine(
                engine, trace=False).reason(records))):
        fn()
        gc.collect()
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        tracemalloc.reset_peak()
        keep = fn()
        cur, peak = tracemalloc.get_traced_memory()
        after = tracemalloc.take_snapshot()
        blocks = sum(s.count_diff for s in after.compare_to(before, "filename")
                     if s.count_diff > 0)
        tracemalloc.stop()
        out[tag] = {"peak_bytes": peak, "result_blocks_allocated": blocks}
        del keep
    return out


def retained(runs):
    """Retained memory after reasoning over every tick with reused
    reasoners. 2.1 holds no state between ticks."""
    cores = {n: SemanticCore21.from_engine(e, trace=True) for n, (e, _r) in runs.items()}
    for n, (_e, res) in runs.items():
        cores[n].reason(res[0].records)
    gc.collect()
    tracemalloc.start()
    a, _ = tracemalloc.get_traced_memory()
    for n, (_e, res) in runs.items():
        for t in res:
            cores[n].reason(t.records)
    gc.collect()
    b, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"ticks": sum(len(r) for _e, r in runs.values()),
            "retained_bytes_after_all_ticks": b - a}


def slope(xs, ys):
    lx, ly = [math.log(x) for x in xs], [math.log(y) for y in ys]
    mx, my = statistics.mean(lx), statistics.mean(ly)
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def scaling(engine, records):
    """Pad one tick with unconnected records: 1x .. 32x its size."""
    cfg = P.cfg_of(engine)
    lean = SemanticCore21.from_engine(engine, trace=False)
    full = SemanticCore21.from_engine(engine, trace=True)
    rows = []
    n0 = len(records)
    for k in (0, 1, 3, 7, 15, 31):
        pad = tuple(P.rec(d, f"{c}_{i}", rel, OS.NOMINAL)
                    for i in range(k * n0 // len(P.AUX) + 1)
                    for d, c, rel in P.AUX)[:k * n0]
        recs = tuple(records) + pad
        rows.append({
            "records": len(recs),
            "frozen_s": best_of(lambda: (localize_all(cfg.symptoms, recs, cfg.predicates),
                                         attribute(recs, cfg.relations)), 5),
            "2_1_no_trace_s": best_of(lambda: lean.reason(recs), 5),
            "2_1_trace_s": best_of(lambda: full.reason(recs), 5)})
    xs = [r["records"] for r in rows]
    return {"rows": rows,
            "loglog_slope": {k: round(slope(xs, [r[k] for r in rows]), 3)
                             for k in ("frozen_s", "2_1_no_trace_s", "2_1_trace_s")}}


def worst_cases():
    lean = SemanticCore21(P.AIR.symptoms, P.AIR.predicates, P.AIR.relations,
                          Corrections(), trace=False)
    out = {}
    # C6: k records under ONE key, each different (distinct timestamps), so
    # every one is compared against every kept one.
    rows = []
    for k in (8, 32, 128, 512):
        recs = tuple(replace(P.rec("COMPUTE", "p", "compute.deadline_met"),
                             timestamp_validity=float(i)) for i in range(k))
        rows.append({"records_under_one_key": k,
                     "seconds": best_of(lambda: SuccessorIndex(recs, tracing=False), 5)})
    out["c6_same_key_bucket"] = {"rows": rows, "loglog_slope": round(
        slope([r["records_under_one_key"] for r in rows], [r["seconds"] for r in rows]), 3)}
    # C3 / C1: a dependency chain of length L below one adverse component.
    rows = []
    for length in (8, 32, 128, 512):
        chain = [P.rec("COMPUTE", f"n{i}", "compute.process_alive",
                       deps=(f"COMPUTE/n{i + 1}",), fns=("F",)) for i in range(length)]
        chain.append(P.rec("COMPUTE", "n0x", "compute.deadline_met", OS.VIOLATED,
                           deps=("COMPUTE/n0",)))
        recs = tuple(chain)
        rows.append({"chain_length": length,
                     "seconds": best_of(lambda: lean.reason(recs), 5)})
    out["c3_c1_dependency_chain"] = {"rows": rows, "loglog_slope": round(
        slope([r["chain_length"] for r in rows], [r["seconds"] for r in rows]), 3)}
    return out


def property_test_overhead():
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "tests/test_semantic_core_2_1.py"], cwd=REPO,
                          capture_output=True, text=True)
    return {"file": "tests/test_semantic_core_2_1.py",
            "wall_seconds": round(time.perf_counter() - t0, 2),
            "returncode": proc.returncode,
            "summary": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""}


def main():
    runs = {}
    for name in sorted(SCENARIOS):
        e, res = P.run_scenario(SCENARIOS[name])
        runs[name] = (e, res)
    finals, all_ticks = {}, {}
    for name, (e, res) in runs.items():
        finals[name] = stages(e, [res[-1]])
    for name, (e, res) in runs.items():
        all_ticks[name] = stages(e, res)

    def total(d, variant, stage):
        return sum(v[variant][stage] for v in d.values() if stage in v[variant])
    summary = {}
    for label, d in (("final_ticks_44", finals), ("all_ticks_2640", all_ticks)):
        s = {}
        for variant, stage in (("frozen", "localization"), ("frozen", "attribution"),
                               ("frozen", "combined"), ("2_1_trace", "localization"),
                               ("2_1_trace", "combined"), ("2_1_no_trace", "localization"),
                               ("2_1_no_trace", "attribution"), ("2_1_no_trace", "combined")):
            s[f"{variant}.{stage}_s"] = round(total(d, variant, stage), 6)
        s["ratio_combined_2_1_trace_over_frozen"] = round(
            s["2_1_trace.combined_s"] / s["frozen.combined_s"], 2)
        s["ratio_combined_2_1_no_trace_over_frozen"] = round(
            s["2_1_no_trace.combined_s"] / s["frozen.combined_s"], 2)
        n = 44 if label == "final_ticks_44" else 2640
        s["per_tick_ms"] = {k.replace("_s", ""): round(v / n * 1e3, 4)
                            for k, v in s.items() if k.endswith("_s")}
        summary[label] = s
    big = max(runs, key=lambda n: len(runs[n][1][-1].records))
    e, res = runs[big]
    out = {
        "WARNING": "desktop CPython timings of one container; not an embedded "
                   "measurement; the C runtime does not implement 2.1",
        "python": sys.version.split()[0], "platform": platform.platform(),
        "machine": platform.machine(),
        "summary": summary,
        "memory_on_the_largest_final_tick": {"scenario": big,
                                             "records": len(res[-1].records),
                                             **memory(e, res[-1].records)},
        "retained_memory": retained(runs),
        "scaling_padded_tick": {"scenario": big, **scaling(e, res[-1].records)},
        "worst_cases": worst_cases(),
        "property_test_overhead": property_test_overhead(),
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"summary": summary,
                      "scaling_slopes": out["scaling_padded_tick"]["loglog_slope"],
                      "worst_cases": {k: v["loglog_slope"] for k, v in out["worst_cases"].items()},
                      "memory": out["memory_on_the_largest_final_tick"],
                      "retained": out["retained_memory"],
                      "property_tests": out["property_test_overhead"]}, indent=1))


if __name__ == "__main__":
    main()
