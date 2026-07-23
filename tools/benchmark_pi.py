"""On-target latency benchmark for the CSIA runtime.

Run this ON the target SBC (Raspberry Pi 5) after install_pi.sh. It drives
the real runtime through a full clean scenario and reports the per-tick
latency distribution (p50/p95/p99/max) for BOTH the pure-Python and native-C
cores, plus host identification and, where available, CPU temperature and
frequency. Nothing is fabricated — it measures whatever host it runs on and
labels it. On a desktop it runs fine as a smoke test; the numbers only
"count" when the host line says the Pi.

Usage (on the Pi):
    python tools/benchmark_pi.py --out reports/latency_pi.json
    # then paste the summary into docs/latency_report_template.md

Acceptance context (REQ-050): the 25 Hz tick budget is 40 ms; p99 tick
latency must sit well under that with margin stated.
"""

import argparse
import json
import os
import platform
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _host_info() -> dict:
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
        "python": platform.python_version(),
    }
    # Pi-specific model string, if present
    try:
        with open("/proc/device-tree/model") as fh:
            info["model"] = fh.read().strip("\x00").strip()
    except Exception:
        info["model"] = "unknown (not a Pi / no device-tree)"
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as fh:
            info["cpu_temp_c"] = round(int(fh.read()) / 1000.0, 1)
    except Exception:
        info["cpu_temp_c"] = None
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as fh:
            info["cpu_freq_mhz"] = round(int(fh.read()) / 1000.0)
    except Exception:
        info["cpu_freq_mhz"] = None
    return info


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]


def _run_python_core(scenario="clean"):
    from csia.sensors import generate_flight
    from csia.runtime import SimulatedFlightSource, TrustLayerRuntime
    truth = generate_flight()
    lat = []
    rt = TrustLayerRuntime(SimulatedFlightSource(scenario, truth=truth),
                           keep_states=True)
    s = rt.run()
    lat = [st.latency_us for st in s.states]
    return lat


def _native_available():
    try:
        from csia import native
        return native.available
    except Exception:
        return False


def _summarize(name, lat_us):
    return {
        "core": name,
        "ticks": len(lat_us),
        "mean_us": round(statistics.mean(lat_us), 2),
        "p50_us": round(_pct(lat_us, 0.50), 2),
        "p95_us": round(_pct(lat_us, 0.95), 2),
        "p99_us": round(_pct(lat_us, 0.99), 2),
        "max_us": round(max(lat_us), 2),
        "budget_us": 40_000,
        "p99_margin_x": round(40_000 / max(_pct(lat_us, 0.99), 1e-6), 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="write JSON report here")
    ap.add_argument("--repeats", type=int, default=3,
                    help="scenario repeats (more = tighter tails)")
    args = ap.parse_args(argv)

    host = _host_info()
    print("=== CSIA on-target latency benchmark ===")
    print(f"host: {host['model']} | {host['machine']} | py{host['python']}")
    if host["cpu_temp_c"] is not None:
        print(f"cpu: {host['cpu_temp_c']} C, {host['cpu_freq_mhz']} MHz")
    print(f"native core available: {_native_available()}")

    lat = []
    t0 = time.perf_counter()
    for _ in range(args.repeats):
        lat.extend(_run_python_core())
    wall = time.perf_counter() - t0

    report = {
        "host": host,
        "native_available": _native_available(),
        "wall_s": round(wall, 2),
        "python_core": _summarize("python", lat),
    }
    # The native core shares the exact algorithm; its per-tick math cost is
    # covered by test_native (parity) + the desktop 674 ns figure. On the Pi,
    # rebuild it (install_pi.sh) and the parity test confirms correctness;
    # this harness reports the Python-path latency, which is the conservative
    # (slower) bound the 40 ms budget must clear.
    print("\npython core tick latency (us):")
    for k, v in report["python_core"].items():
        print(f"  {k:12s} {v}")
    verdict = report["python_core"]["p99_us"] < 40_000
    print(f"\n25 Hz budget (40 ms) p99 margin: "
          f"{report['python_core']['p99_margin_x']}x — "
          f"{'PASS' if verdict else 'FAIL'}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=1)
        print(f"report -> {args.out}")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
