"""Soak test: run the runtime continuously and watch for leaks/drift.

Products die at hour 6, not minute 2. This drives the ONLINE layer with a
looping simulated source for a wall-clock duration (fast-as-possible, so
hours of flight time take minutes), exercising the time-discontinuity reset
path on every loop, and reports per-pass memory (RSS) and tick latency so
growth is visible.

Usage:
    python tools/soak.py --minutes 30 [--scenario clean]

Pass criteria (printed at the end):
  * RSS growth from pass 3 to the last pass below 10 MB
  * no contained trust-layer errors
  * mean tick latency stable (last pass < 2x pass 3)
"""

import argparse
import resource
import sys
import time

from csia.runtime import (FailsafePolicy, OnlineTrustLayer,
                          SimulatedFlightSource, TrustLayerRuntime)


class LoopingSource(SimulatedFlightSource):
    """Replays the scenario until the deadline. Each pass restarts time at
    zero — deliberately exercising the runtime's reset-on-time-jump path,
    exactly what a looped bench run or an FC reboot produces."""

    def __init__(self, scenario, deadline_s):
        super().__init__(scenario)
        self.deadline = time.monotonic() + deadline_s
        self.passes = 0

    def samples(self):
        while time.monotonic() < self.deadline:
            self.passes += 1
            yield from super().samples()


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--scenario", default="clean")
    args = ap.parse_args(argv)

    src = LoopingSource(args.scenario, args.minutes * 60.0)
    layer = OnlineTrustLayer()
    runtime = TrustLayerRuntime(src, layer=layer, policy=FailsafePolicy())

    samples = []   # (pass, rss_mb, mean_latency_us)
    lat_acc = [0.0, 0]
    seen_pass = [0]

    def on_state(state, _actions):
        lat_acc[0] += state.latency_us
        lat_acc[1] += 1
        if src.passes != seen_pass[0]:
            if seen_pass[0] > 0 and lat_acc[1]:
                samples.append((seen_pass[0], rss_mb(),
                                lat_acc[0] / lat_acc[1]))
                print(f"pass {seen_pass[0]:4d}: rss {samples[-1][1]:7.1f} MB"
                      f"  mean tick {samples[-1][2]:6.1f} us")
            seen_pass[0] = src.passes
            lat_acc[0] = lat_acc[1] = 0

    runtime.listeners.append(on_state)
    t0 = time.monotonic()
    summary = runtime.run()
    dt_min = (time.monotonic() - t0) / 60.0

    print(f"\n=== SOAK: {src.passes} passes ({src.passes:d} x 60 s flight "
          f"time) in {dt_min:.1f} wall-min ===")
    print(f"ticks {summary.ticks}, contained errors {summary.errors}")
    ok = summary.errors == 0
    if len(samples) >= 3:
        growth = samples[-1][1] - samples[2][1]
        lat_ratio = samples[-1][2] / max(samples[2][2], 1e-9)
        print(f"RSS growth (pass 3 -> last): {growth:+.1f} MB; "
              f"latency ratio {lat_ratio:.2f}x")
        ok = ok and growth < 10.0 and lat_ratio < 2.0
    print("SOAK PASS" if ok else "SOAK FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
