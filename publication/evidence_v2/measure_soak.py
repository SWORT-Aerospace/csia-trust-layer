#!/usr/bin/env python3
"""Deliverable 4, MEASUREMENT: the 277,500-tick soak, per tick.

    python publication/evidence_v2/measure_soak.py [--passes 185]

Not part of `make evidence-v2`: timing depends on the host and differs on every
run, so it cannot regenerate bit-for-bit. `make evidence-v2-measure` runs it,
and the committed outputs under data/ are what `fig_d4_soak.py` plots.

What it runs is tools/soak.py's loop with one change of stopping rule: a fixed
pass count instead of a wall-clock deadline, so the tick count is exactly
185 x 1500 = 277,500, the figure README.md quotes. Same scenario ("clean"),
same OnlineTrustLayer() and FailsafePolicy() defaults, same time-discontinuity
reset on every pass.

What it records:
- per tick: `state.latency_us`, the engine's own measurement
  (csia/runtime/online.py, perf_counter around the tick), stored as integer
  nanoseconds in buffers ALLOCATED BEFORE THE RUN. A first version appended a
  tuple per tick to a list, and that list alone grew peak RSS by about 35 MB
  over 277,500 ticks, which read as a leak in the engine. Fixed-size buffers
  keep the instrument's own memory constant;
- per pass: peak RSS (`ru_maxrss`, what tools/soak.py prints; it can only
  grow) and current RSS (/proc/self/statm), plus the pass mean latency;
- the host, its load average before and after, and wall-clock start and end.
"""

from __future__ import annotations

import argparse
import array
import datetime as dt
import os
import platform
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

sys.path.insert(0, C.ROOT)
from csia.runtime import (FailsafePolicy, OnlineTrustLayer,  # noqa: E402
                          SimulatedFlightSource, TrustLayerRuntime)

SCENARIO = "clean"


class CountedLoopSource(SimulatedFlightSource):
    """tools/soak.py's LoopingSource, stopping on a pass count."""

    def __init__(self, scenario, passes):
        super().__init__(scenario)
        self.max_passes = passes
        self.passes = 0

    def samples(self):
        while self.passes < self.max_passes:
            self.passes += 1
            yield from super().samples()


def rss_current_mb() -> float:
    with open("/proc/self/statm") as fh:
        pages = int(fh.read().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE") / (1024.0 * 1024.0)


def rss_peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def cpu_model() -> str | None:
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--passes", type=int, default=185)
    args = ap.parse_args(argv)

    src = CountedLoopSource(SCENARIO, args.passes)
    runtime = TrustLayerRuntime(src, layer=OnlineTrustLayer(), policy=FailsafePolicy())
    cap = args.passes * 1500 + 1500          # 1500 ticks per 60 s pass at 25 Hz, plus slack
    lat_ns = array.array("q", bytes(8 * cap))
    pass_of = array.array("H", bytes(2 * cap))
    passes = []
    cur = {"pass": 0, "n": 0, "sum": 0.0, "i": 0}

    def close_pass():
        if cur["n"]:
            passes.append((cur["pass"], cur["n"], round(rss_peak_mb(), 3),
                           round(rss_current_mb(), 3), round(cur["sum"] / cur["n"], 3)))

    def on_state(state, _actions):
        if src.passes != cur["pass"]:
            close_pass()
            cur.update({"pass": src.passes, "n": 0, "sum": 0.0})
        lat = float(state.latency_us)
        i = cur["i"]
        lat_ns[i] = int(round(lat * 1000.0))
        pass_of[i] = src.passes
        cur["i"] = i + 1
        cur["n"] += 1
        cur["sum"] += lat

    runtime.listeners.append(on_state)
    load_before = os.getloadavg()
    started = utc_now()
    t0 = time.monotonic()
    summary = runtime.run()
    wall = time.monotonic() - t0
    close_pass()
    finished = utc_now()
    load_after = os.getloadavg()
    ticks = [(i, pass_of[i], lat_ns[i]) for i in range(cur["i"])]

    C.write_csv_gz(os.path.join(C.DATA, "soak_ticks.csv.gz"), ("tick", "pass", "latency_ns"), ticks)
    C.write_csv(os.path.join(C.DATA, "soak_passes.csv"),
                ("pass", "ticks", "rss_peak_mb", "rss_current_mb", "mean_latency_us"), passes)
    third, last = passes[2], passes[-1]
    C.write_json(os.path.join(C.DATA, "soak_measurement.json"), {
        "schema": "csia.evidence_v2.soak_measurement/1",
        "script": C.rel(__file__),
        "git_head_at_measurement": C.git("rev-parse", "HEAD"),
        "git_dirty_at_measurement": bool(C.git("status", "--porcelain")),
        "scenario": SCENARIO,
        "passes_requested": args.passes,
        "passes_completed": len(passes),
        "ticks": summary.ticks,
        "ticks_recorded": len(ticks),
        "instrument_buffers": "preallocated array('q') and array('H') of passes x 1500 + 1500",
        "contained_errors": summary.errors,
        "wall_start_utc": started, "wall_end_utc": finished,
        "wall_seconds": round(wall, 3),
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "cpu_model": cpu_model(), "cpu_count": os.cpu_count(),
                 "loadavg_before": [round(x, 2) for x in load_before],
                 "loadavg_after": [round(x, 2) for x in load_after]},
        "software": C.software(),
        "soak_py_criteria": {
            "basis": "tools/soak.py: peak-RSS growth pass 3 to last < 10 MB; last-pass mean "
                     "latency < 2x pass 3; no contained errors",
            "rss_peak_growth_mb_pass3_to_last": round(last[2] - third[2], 3),
            "mean_latency_ratio_last_over_pass3": round(last[4] / third[4], 4),
            "contained_errors": summary.errors,
            "pass": bool(summary.errors == 0 and last[2] - third[2] < 10.0 and last[4] / third[4] < 2.0),
        },
    })
    print(f"{len(ticks)} ticks, {len(passes)} passes, {summary.errors} errors, {wall:.1f} s wall")
    return 0


if __name__ == "__main__":
    C.main_guard(main)
