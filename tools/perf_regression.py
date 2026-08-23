"""Performance regression harness.

Measures the engineering-performance envelope of the CSIA runtime WITHOUT
changing any existing benchmark methodology — it drives the same code paths
`csia report`, `csia run`, and the test suite already exercise, records the
numbers to a versioned JSON history, and fails (exit 2) if any metric
regresses past its per-metric tolerance versus the stored baseline.

Metrics (all on the reference host; embedded numbers come from
tools/benchmark_pi.py on the target):
  import_s        cold `import csia` time (startup proxy)
  build_s         wall time to build all scenario replays (`csia build`)
  trust_core_us   mean trust-core latency, desktop Python (hist.latency_us)
  runtime_tick_us mean online trust+failsafe latency per tick (RunSummary)
  replay_ticks_s  online ticks processed per wall-second (throughput)
  rss_mb          resident set after a full clean scenario run
  mc_runtime_s    wall time for a fixed 30-run Monte Carlo slice

Usage:
  python tools/perf_regression.py --update-baseline   # seed / re-bless
  python tools/perf_regression.py                      # measure + compare
  python tools/perf_regression.py --json out.json      # also emit report

History: campaigns/perf_history.jsonl (one line per run, appended).
Baseline: campaigns/perf_baseline.json (the blessed reference).

NOTE: desktop numbers are informational and host-dependent; the gate exists
to catch relative regressions on ONE machine across commits, not to certify
absolute performance. Absolute embedded timing is Phase 7 (target hardware).
"""

import argparse
import json
import os
import resource
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "campaigns", "perf_history.jsonl")
BASELINE = os.path.join(ROOT, "campaigns", "perf_baseline.json")

# Per-metric regression tolerance: measured may exceed baseline by this
# factor before it is flagged. Timing/memory are "lower is better";
# throughput is "higher is better" (checked inverted).
TOLERANCE = {
    "import_s": 1.5, "build_s": 1.5, "trust_core_us": 1.5,
    "runtime_tick_us": 1.5, "rss_mb": 1.3, "mc_runtime_s": 1.5,
}
HIGHER_BETTER = {"replay_ticks_s"}


def _rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def measure() -> dict:
    m = {}
    # cold import time in a fresh interpreter (honest startup proxy)
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-c", "import csia"], cwd=ROOT, check=True)
    m["import_s"] = round(time.perf_counter() - t0, 4)

    # in-process measurements
    from csia.scenarios import run_scenario
    from csia.sensors import generate_flight
    from csia.runtime import (SimulatedFlightSource, TrustLayerRuntime)

    truth = generate_flight()
    _, _, _, hist, _ = run_scenario("gps_spoof", truth=truth)
    m["trust_core_us"] = round(float(hist.latency_us[10:].mean()), 2)

    t0 = time.perf_counter()
    rt = TrustLayerRuntime(SimulatedFlightSource("clean", truth=truth))
    summary = rt.run()
    wall = time.perf_counter() - t0
    m["runtime_tick_us"] = round(summary.mean_latency_us, 2)
    m["replay_ticks_s"] = round(summary.ticks / wall, 1)
    m["rss_mb"] = round(_rss_mb(), 1)

    # build all replays (subprocess: real `csia build` path, real wall time)
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "csia.cli",
                    "--data-dir", os.path.join(ROOT, "data"), "build"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    m["build_s"] = round(time.perf_counter() - t0, 2)

    # fixed 30-run Monte Carlo slice (runtime proxy; methodology unchanged)
    from csia.validation import monte_carlo
    t0 = time.perf_counter()
    monte_carlo(runs=30, field_mode=True, seed=0, out_path=None)
    m["mc_runtime_s"] = round(time.perf_counter() - t0, 2)
    return m


def compare(measured: dict, baseline: dict) -> list:
    regressions = []
    for k, v in measured.items():
        if k not in baseline:
            continue
        b = baseline[k]
        if k in HIGHER_BETTER:
            # throughput regressed if it dropped below baseline/tol
            if v < b / TOLERANCE.get(k, 1.5):
                regressions.append((k, b, v, "throughput dropped"))
        else:
            tol = TOLERANCE.get(k, 1.5)
            if v > b * tol:
                regressions.append((k, b, v, f">{tol}x baseline"))
    return regressions


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-baseline", action="store_true",
                    help="bless the current measurement as the new baseline")
    ap.add_argument("--json", default=None, help="write the report here too")
    args = ap.parse_args(argv)

    print("measuring performance envelope (desktop reference)...")
    m = measure()
    m["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        m["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT
        ).decode().strip()
    except Exception:
        m["commit"] = "unknown"

    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    with open(HIST, "a") as fh:
        fh.write(json.dumps(m) + "\n")

    for k in sorted(m):
        if k not in ("ts", "commit"):
            print(f"  {k:18s} {m[k]}")

    if args.update_baseline or not os.path.exists(BASELINE):
        with open(BASELINE, "w") as fh:
            json.dump(m, fh, indent=1)
        print(f"baseline written -> {os.path.relpath(BASELINE, ROOT)}")
        rc = 0
    else:
        with open(BASELINE) as fh:
            baseline = json.load(fh)
        regressions = compare(m, baseline)
        if regressions:
            print(f"\n!! {len(regressions)} PERFORMANCE REGRESSION(S) vs "
                  f"baseline {baseline.get('commit')}:")
            for k, b, v, why in regressions:
                print(f"   {k}: baseline {b} -> now {v} ({why})")
            rc = 2
        else:
            print(f"\nOK — no regression vs baseline {baseline.get('commit')}")
            rc = 0

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(m, fh, indent=1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
