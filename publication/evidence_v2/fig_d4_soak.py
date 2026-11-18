#!/usr/bin/env python3
"""Deliverable 4, figure and table: the 277,500-tick soak. Per-tick execution
time histogram, and memory per pass.

    python publication/evidence_v2/fig_d4_soak.py

Reads the committed measurement (measure_soak.py): data/soak_ticks.csv.gz,
data/soak_passes.csv, data/soak_measurement.json. Plotting is deterministic;
the measurement is not, and its host, load and wall-clock time are in
soak_measurement.json and quoted in the stamp.

Per-tick time is the engine's own `state.latency_us` (csia/runtime/online.py,
perf_counter around one tick of the online layer). It is a desktop-class host
measurement in a shared container, not an on-target figure. Quantiles are order
statistics (numpy `method="inverted_cdf"`).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import numpy as np  # noqa: E402

TICKS = os.path.join(C.DATA, "soak_ticks.csv.gz")
PASSES = os.path.join(C.DATA, "soak_passes.csv")
META = os.path.join(C.DATA, "soak_measurement.json")
FIG = os.path.join(C.FIGURES, "d4_soak.png")
TAB = os.path.join(C.TABLES, "d4_soak_summary.csv")


def q(v, p):
    return float(np.quantile(v, p, method="inverted_cdf"))


def main() -> int:
    meta = json.load(open(META, encoding="utf-8"))
    lat_us = np.array([int(r["latency_ns"]) for r in C.read_csv(TICKS)], dtype=np.int64) / 1000.0
    passes = C.read_csv(PASSES)
    pn = np.array([int(r["pass"]) for r in passes])
    peak = np.array([float(r["rss_peak_mb"]) for r in passes])
    cur = np.array([float(r["rss_current_mb"]) for r in passes])
    mean_pass = np.array([float(r["mean_latency_us"]) for r in passes])

    stats = {"median": q(lat_us, 0.5), "p95": q(lat_us, 0.95), "p99": q(lat_us, 0.99),
             "p99.9": q(lat_us, 0.999), "max": float(lat_us.max()), "mean": float(lat_us.mean())}
    i3 = int(np.where(pn == 3)[0][0])

    plt = C.style()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.0, 3.6))
    bins = np.logspace(np.log10(max(lat_us.min(), 1.0)), np.log10(lat_us.max()), 80)
    a1.hist(lat_us, bins=bins, color=C.SERIES[0], edgecolor=C.SURFACE, linewidth=0.3)
    a1.set_xscale("log")
    a1.set_yscale("log")
    a1.set_xlabel("per-tick execution time, microseconds (log)")
    a1.set_ylabel("ticks (log)")
    from matplotlib.transforms import blended_transform_factory
    tr = blended_transform_factory(a1.transData, a1.transAxes)
    for name, yy in (("median", 1.02), ("p99", 1.09), ("max", 1.02)):
        a1.axvline(stats[name], color=C.TEXT_2, linewidth=0.8, linestyle=(0, (2, 2)))
        a1.text(stats[name], yy, f"{name} {stats[name]:,.0f}", transform=tr, ha="center",
                va="bottom", fontsize=7, color=C.TEXT_2)

    minutes = pn * 1.0                     # one pass = 60 s of flight time
    a2.plot(minutes, peak, color=C.SERIES[0], label="peak RSS (ru_maxrss)")
    a2.plot(minutes, cur, color=C.SERIES[1], label="current RSS (/proc/self/statm)")
    a2.set_xlabel("flight-equivalent minutes (pass number)")
    a2.set_ylabel("MB")
    lo, hi = float(min(cur.min(), peak.min())), float(max(cur.max(), peak.max()))
    a2.set_ylim(lo - 2.0, hi + 2.0)
    a2.set_title(f"peak RSS growth pass 3 to {pn[-1]}: {peak[-1] - peak[i3]:+.2f} MB; "
                 f"current {cur[-1] - cur[i3]:+.2f} MB", fontsize=9, color=C.TEXT)
    a2.text(minutes[-1], cur[-1] + 0.12, "current", ha="right", va="bottom", fontsize=7.5, color=C.TEXT_2)
    a2.text(minutes[-1], peak[-1] - 0.12, "peak", ha="right", va="top", fontsize=7.5, color=C.TEXT_2)
    a2.legend(frameon=False, loc="lower right", fontsize=7.5)
    fig.suptitle(f"Soak: {lat_us.size:,} ticks, {len(passes)} passes of scenario '{meta['scenario']}', "
                 f"{meta['contained_errors']} contained errors; host {meta['host']['cpu_model']}, "
                 f"{meta['host']['cpu_count']} vCPU", fontsize=10, color=C.TEXT, y=1.10)
    C.savefig(fig, FIG)

    crit = meta["soak_py_criteria"]
    rows = [("ticks", meta["ticks"]), ("passes", meta["passes_completed"]),
            ("contained_errors", meta["contained_errors"]),
            ("tick_time_median_us", round(stats["median"], 1)), ("tick_time_p95_us", round(stats["p95"], 1)),
            ("tick_time_p99_us", round(stats["p99"], 1)), ("tick_time_p99_9_us", round(stats["p99.9"], 1)),
            ("tick_time_max_us", round(stats["max"], 1)), ("tick_time_mean_us", round(stats["mean"], 1)),
            ("pass_mean_ratio_last_over_pass3", round(mean_pass[-1] / mean_pass[i3], 4)),
            ("peak_rss_growth_mb_pass3_to_last", round(peak[-1] - peak[i3], 3)),
            ("current_rss_growth_mb_pass3_to_last", round(cur[-1] - cur[i3], 3)),
            ("soak_py_verdict", "PASS" if crit["pass"] else "FAIL"),
            ("wall_seconds", meta["wall_seconds"]), ("measured_at_utc", meta["wall_start_utc"]),
            ("host_cpu", meta["host"]["cpu_model"]), ("host_vcpu", meta["host"]["cpu_count"]),
            ("loadavg_before_1min", meta["host"]["loadavg_before"][0])]
    C.write_csv(TAB, ("quantity", "value"), rows)
    common = dict(inputs=(TICKS, PASSES, META), measured_at_utc=meta["wall_start_utc"],
                  configs=((os.path.join(C.ROOT, "csia", "runtime", "online.py"), "latency_us measurement point"),
                           (os.path.join(C.ROOT, "tools", "soak.py"), "soak loop and pass criteria")),
                  datasets={"dataset_id": "synthetic: csia scenario 'clean', looped 185 passes",
                            "measurement_git_head": meta["git_head_at_measurement"]},
                  seeds={"sensor_seeds": "1-8 fixed (csia/scenarios.make_sensors)"},
                  definitions=[{"metric": "per-tick execution time", "source": "csia/runtime/online.py",
                                "section": "OnlineState.latency_us"},
                               {"metric": "soak pass criteria", "source": "tools/soak.py", "section": "docstring"}],
                  notes=["host-dependent; desktop-class container, not on-target",
                         "ru_maxrss is updated lazily by the kernel and can read slightly below "
                         "the current RSS from /proc/self/statm",
                         "measurement buffers preallocated so the instrument does not grow RSS"])
    C.stamp(FIG, __file__, **common)
    C.stamp(TAB, __file__, **common)
    return 0


if __name__ == "__main__":
    C.main_guard(main)
