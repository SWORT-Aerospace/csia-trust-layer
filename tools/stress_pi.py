"""On-target endurance + thermal stress harness (Raspberry Pi 5).

Runs the CSIA runtime continuously for a wall-clock duration, sampling RSS,
per-pass tick latency, CPU temperature, and CPU frequency so thermal
throttling shows up as a latency/frequency correlation. This is the on-target
counterpart to tools/soak.py (which is host-agnostic); use it for the
overnight REQ-052 endurance run.

Usage (on the Pi, overnight):
    python tools/stress_pi.py --hours 8 --out reports/soak_pi.jsonl
    # then populate docs/reliability_report_template.md

Pass criteria (populate the template with the actual numbers):
  * RSS growth over the run < 10 MB
  * p99 tick latency stays < 40 ms even under thermal load
  * no unhandled/contained errors
  * CPU never throttles into a deadline miss (temp vs latency uncorrelated
    enough that p99 margin holds)
"""

import argparse
import json
import os
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_int(path):
    try:
        with open(path) as fh:
            return int(fh.read())
    except Exception:
        return None


def _cpu_temp_c():
    v = _read_int("/sys/class/thermal/thermal_zone0/temp")
    return round(v / 1000.0, 1) if v is not None else None


def _cpu_freq_mhz():
    v = _read_int("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    return round(v / 1000.0) if v is not None else None


def _rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--scenario", default="clean")
    ap.add_argument("--out", default=None, help="JSONL sample log")
    args = ap.parse_args(argv)

    from csia.runtime import (SimulatedFlightSource, TrustLayerRuntime,
                              OnlineTrustLayer, FailsafePolicy)

    deadline = time.monotonic() + args.hours * 3600.0
    fh = open(args.out, "w") if args.out else None
    print(f"=== CSIA on-target stress: {args.hours} h, scenario={args.scenario} ===")
    print(f"start temp {_cpu_temp_c()} C, freq {_cpu_freq_mhz()} MHz, "
          f"rss {_rss_mb()} MB")

    rss0 = _rss_mb()
    rss_max = rss0
    p99_worst = 0.0
    total_errors = 0
    passes = 0

    try:
        while time.monotonic() < deadline:
            layer = OnlineTrustLayer()
            rt = TrustLayerRuntime(SimulatedFlightSource(args.scenario),
                                   layer=layer, policy=FailsafePolicy(),
                                   keep_states=True)
            s = rt.run()
            passes += 1
            lat = [st.latency_us for st in s.states]
            p99 = _pct(lat, 0.99) if lat else 0.0
            p99_worst = max(p99_worst, p99)
            rss = _rss_mb()
            rss_max = max(rss_max, rss)
            total_errors += s.errors
            row = {
                "pass": passes, "t": round(time.monotonic(), 1),
                "rss_mb": rss, "p99_us": round(p99, 1),
                "temp_c": _cpu_temp_c(), "freq_mhz": _cpu_freq_mhz(),
                "errors": s.errors,
            }
            if fh:
                fh.write(json.dumps(row) + "\n")
                fh.flush()
            if passes % 10 == 0:
                print(f"pass {passes:5d}: rss {rss} MB, p99 {p99/1000:.1f} ms, "
                      f"temp {row['temp_c']} C, freq {row['freq_mhz']} MHz")
    finally:
        if fh:
            fh.close()

    growth = rss_max - rss0
    print(f"\n=== STRESS DONE: {passes} passes ===")
    print(f"RSS: {rss0} -> {rss_max} MB (growth {growth:+.1f} MB)")
    print(f"worst p99 tick latency: {p99_worst/1000:.2f} ms "
          f"(budget 40 ms, margin {40000/max(p99_worst,1e-6):.1f}x)")
    print(f"contained errors: {total_errors}")
    ok = growth < 10.0 and p99_worst < 40_000 and total_errors == 0
    print("STRESS PASS" if ok else "STRESS FAIL — inspect log")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
