"""Replay a shadow flight log into the frozen core and time it.

Closes the gap W-8 left open: the live core cost (1542.7 us/tick) was much
larger than the replay figure predicted, and nobody knew why. Guessing was
already tried four times, so this measures.

Why a LOG replay rather than another SITL run:

  * **Deterministic.** Same log, same numbers. A SITL run varies with host
    load, scheduling and the simulator's own timing, which is exactly the
    noise that makes a 6% difference unreadable.
  * **No autopilot needed.** It runs anywhere, including on the companion
    computer at Gate 2 — which is where the freeze document says the full
    drive cost must actually be measured, and where SITL will not be.
  * **Real data.** Synthetic drive loops answer a different question. The gap
    might BE the difference between bench values and live ones.

Two timing modes, and they answer different questions:

  wall   perf_counter around each core hand-off, no profiler. This is the
         TRUE cost and it is directly comparable to the shadow runner's phase
         timing, which uses the same method.
  prof   cProfile, for attribution only. Its absolute numbers are inflated by
         per-call overhead and must never be quoted as the cost.

  python tools/deploy/profile_core_from_log.py logs/shadow-.../x.jsonl
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import statistics
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.adapters.base import PlatformAdapter    # noqa: E402
from csia.runtime.online import OnlineTrustLayer           # noqa: E402
from csia.simulation.host_noise import (                   # noqa: E402
    measure as measure_host_noise, r13_verdict)

R13_BUDGET_US = 2000.0

# Channels whose value is a vector and must be restored as an ndarray: the
# core does arithmetic on them, and a list would either crash or silently
# behave differently from the live run.
VECTOR_CHANNELS = {"imu0.accel", "imu0.gyro", "imu1.accel", "imu1.gyro",
                   "mag.field_ut", "gnss.position", "gnss.velocity",
                   "esc.rpm", "esc.current"}


def load_ticks(path: str):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "tick":
                yield rec


#: Reconstruction gates. `arrival` reproduces what the live adapter does;
#: `value` is the original approximation, kept so the two can be COMPARED
#: rather than one silently replacing the other. See HF-010.
GATE_ARRIVAL = "arrival"
GATE_VALUE = "value"

#: Arrival times are reconstructed as `t_mono - age_s`, two independently
#: rounded quantities, so a HELD value's arrival wobbles by a few
#: microseconds instead of repeating exactly. Comparing at full precision
#: therefore makes every stamp look new, which is over-counting rather than
#: reconstruction -- the first version of this did exactly that.
#:
#: The quantum is set from TWO MEASURED SCALES, not chosen by taste. Across
#: both committed shadow logs:
#:
#:     held-value arrival jitter   max 3.19e-05 s (ardupilot)
#:                                 max 1.25e-04 s (px4)
#:     real inter-arrival gaps     min 0.0186 s   (ardupilot)
#:                                 min 0.0198 s   (px4)
#:
#: The two populations are separated by 159x on the tighter platform. One
#: millisecond sits ~8x above the worst jitter and ~19x below the smallest
#: real gap, in the middle of that gap on a log scale. Any value in
#: [1.3e-4, 1.8e-2] gives the same answer, which is what makes this a
#: quantisation rather than a tuning knob.
ARRIVAL_QUANTUM_S = 1e-3


class HandoffReconstructor:
    """Rebuild the hand-off sequence a logged run actually performed.

    THE LIVE GATE KEYS ON ARRIVAL TIME, NOT ON VALUE
    ------------------------------------------------
    `PlatformAdapter.to_core_samples` emits a sensor when its channels'
    ARRIVAL TIMESTAMPS differ from the last hand-off::

        stamps = tuple(self._latest[ch][1] for ch in mapping.values() ...)
        if stamps and self._emitted.get(sensor) == stamps: continue

    The original reconstruction compared VALUES instead, so two identical
    consecutive readings -- a stationary vehicle, a saturated channel, a
    slowly-varying temperature -- looked like no new reading. It was
    documented as a slight under-count.

    IT IS NOT SLIGHT. Measured on a committed 751-tick shadow log: 1454
    hand-offs by value against 3527 by arrival time, so the value method
    misses 58.8% of them. That is the mechanism behind HF-004's DIVERGENT
    decision replay -- a sensor never handed over is an edge never made
    live, which is exactly the shape of the recorded divergences.

    The log already carries what is needed: each channel records `age_s`,
    so arrival time is `t_mono - age_s`, the same quantity `_latest`
    holds. NOTHING NEW HAD TO BE LOGGED and the frozen core is untouched;
    the reconstruction was simply reading the wrong field.
    """

    def __init__(self, gate: str = GATE_ARRIVAL):
        if gate not in (GATE_ARRIVAL, GATE_VALUE):
            raise ValueError(f"unknown gate {gate!r}")
        self.gate = gate
        self._emitted: dict = {}      # sensor -> last emitted stamp tuple
        self._values: dict = {}       # channel -> last value (value gate)

    def samples_for_tick(self, tick) -> list:
        chans = tick["canonical"]["channels"]
        t_mono = tick["t_mono"]
        out = []
        for sensor, mapping in PlatformAdapter.CORE_MAP.items():
            built, complete, changed, stamps = {}, True, False, []
            for core_key, channel in mapping.items():
                cv = chans.get(channel)
                if cv is None or not cv.get("usable"):
                    if channel == "baro.temp_c":
                        continue
                    complete = False
                    break
                val = cv["value"]
                if channel in VECTOR_CHANNELS:
                    val = np.asarray(val, dtype=float)
                built[core_key] = val
                # A channel that has never arrived is absent from the live
                # adapter's `_latest` and so contributes no stamp.
                age = cv.get("age_s")
                if age is not None:
                    stamps.append(
                        (channel, round((t_mono - age) / ARRIVAL_QUANTUM_S)))
                if self._values.get(channel) != cv["value"]:
                    changed = True
            if not complete or not built:
                continue

            if self.gate == GATE_ARRIVAL:
                key = tuple(stamps)
                if key and self._emitted.get(sensor) == key:
                    self._remember(mapping, chans)
                    continue
                self._emitted[sensor] = key
            elif not changed:
                self._remember(mapping, chans)
                continue

            self._remember(mapping, chans)
            if sensor == "gps":
                built["vz_valid"] = False
            if sensor != "vehicle_status":
                built["valid"] = True
            out.append((sensor, t_mono, built))
        return out

    def _remember(self, mapping, chans) -> None:
        for channel in mapping.values():
            cv = chans.get(channel)
            if cv is not None and cv.get("usable"):
                self._values[channel] = cv["value"]


def core_samples_for_tick(tick, previous):
    """Backwards-compatible wrapper around the VALUE gate.

    Retained because it is the shape earlier callers used. New code should
    use `HandoffReconstructor`, which carries its own state and defaults to
    the arrival gate that matches the live adapter.
    """
    chans = tick["canonical"]["channels"]
    out = []
    for sensor, mapping in PlatformAdapter.CORE_MAP.items():
        built, complete, changed = {}, True, False
        for core_key, channel in mapping.items():
            cv = chans.get(channel)
            if cv is None or not cv.get("usable"):
                if channel == "baro.temp_c":
                    continue
                complete = False
                break
            val = cv["value"]
            if channel in VECTOR_CHANNELS:
                val = np.asarray(val, dtype=float)
            built[core_key] = val
            prev = (previous or {}).get(channel)
            if prev is None or prev != cv["value"]:
                changed = True
        if not complete or not built or not changed:
            continue
        if sensor == "gps":
            built["vz_valid"] = False
        if sensor != "vehicle_status":
            built["valid"] = True
        out.append((sensor, tick["t_mono"], built))
    return out


def replay(path, field_mode=True, tick_hz=25.0, profile=False):
    layer = OnlineTrustLayer(tick_hz=tick_hz, field_mode=field_mode)
    ticks = list(load_ticks(path))
    per_tick, handoffs, prev = [], 0, None

    pr = cProfile.Profile() if profile else None
    if pr:
        pr.enable()
    for tick in ticks:
        samples = core_samples_for_tick(tick, prev)
        prev = {k: v["value"]
                for k, v in tick["canonical"]["channels"].items()
                if v.get("usable")}
        t0 = time.perf_counter()
        for sensor, t, chans in samples:
            layer.ingest(sensor, t, chans)
        per_tick.append((time.perf_counter() - t0) * 1e6)
        handoffs += len(samples)
    if pr:
        pr.disable()
    return ticks, per_tick, handoffs, pr


def summarise(xs):
    s = sorted(xs)
    if not s:
        return {}
    return {"n": len(s), "median_us": round(statistics.median(s), 1),
            "mean_us": round(statistics.fmean(s), 1),
            "p95_us": round(s[int(len(s) * 0.95)], 1),
            "max_us": round(s[-1], 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--tick-hz", type=float, default=25.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--passes", type=int, default=1,
                    help="repeat each mode N times; the spread across "
                         "identical passes is itself a measurement of the "
                         "host, and a single pass hides it")
    ap.add_argument("--no-control", action="store_true",
                    help="skip the host-noise null control (then no tail "
                         "verdict is issued at all)")
    args = ap.parse_args()

    result = {"log": os.path.relpath(args.log, ROOT), "modes": {}}
    print(f"=== replaying {os.path.basename(args.log)}")

    worst_over = 0
    n_ticks = 0
    for fm in (False, True):
        passes = []
        for _ in range(max(1, args.passes)):
            ticks, per_tick, handoffs, _ = replay(args.log, field_mode=fm,
                                                  tick_hz=args.tick_hz)
            s = summarise(per_tick)
            s["handoffs"] = handoffs
            s["handoffs_per_tick"] = round(handoffs / max(1, len(ticks)), 2)
            s["over_budget"] = sum(1 for x in per_tick if x > R13_BUDGET_US)
            passes.append(s)
            n_ticks = max(n_ticks, len(per_tick))
            print(f"    field_mode={str(fm):5s} median {s['median_us']:8.1f} us"
                  f"  p95 {s['p95_us']:8.1f}  max {s['max_us']:9.1f}  "
                  f"over2ms {s['over_budget']:3d}  "
                  f"handoffs/tick {s['handoffs_per_tick']}")
        # The FIRST pass stays under the original key so existing readers of
        # this file keep working; the spread is recorded alongside it.
        # dict(), not the object itself: assigning `passes` into passes[0]
        # makes the structure contain itself and json.dump raises
        # "Circular reference detected" AFTER the whole replay has run.
        result["modes"][f"field_mode={fm}"] = dict(passes[0])
        if len(passes) > 1:
            result["modes"][f"field_mode={fm}"]["passes"] = passes
            result["modes"][f"field_mode={fm}"]["median_spread_us"] = round(
                max(p["median_us"] for p in passes)
                - min(p["median_us"] for p in passes), 1)
            result["modes"][f"field_mode={fm}"]["max_spread_us"] = round(
                max(p["max_us"] for p in passes)
                - min(p["max_us"] for p in passes), 1)
        worst_over = max(worst_over,
                         max(p["over_budget"] for p in passes))

    # The clean-core figure is worth nothing without knowing what the host
    # does to a CONSTANT workload in the same process. Measured on this
    # container: a busy loop sized to the core's median went over the 2 ms
    # budget on up to 10 of 751 iterations, with a 26.7 ms outlier.
    if not args.no_control:
        median = result["modes"]["field_mode=True"]["median_us"]
        noise = measure_host_noise(n_ticks=n_ticks or 751, target_us=median,
                                   budget_us=R13_BUDGET_US, trials=3)
        result["host_noise_control"] = noise
        w = noise["worst_trial"]
        print(f"\n=== host-noise control (constant work, same process): "
              f"median {w['median_us']:.0f} us  max {w['max_us']:.0f} us  "
              f"{w['over_budget']}/{w['n']} over budget")
        result["R13_replay"] = r13_verdict(worst_over, noise, n_ticks or 751)
        print(f"=== R13 (deterministic replay): {result['R13_replay']}")

    # Attribution pass. Inflated absolute numbers; ratios only.
    _t, _p, _h, pr = replay(args.log, field_mode=True, tick_hz=args.tick_hz,
                            profile=True)
    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf).sort_stats("tottime")
    ps.print_stats(14)
    hot = []
    for line in buf.getvalue().splitlines():
        if "csia/" in line and "{" not in line:
            parts = line.split(None, 5)
            if len(parts) >= 6:
                hot.append({"tottime_s": parts[1], "cumtime_s": parts[3],
                            "where": parts[5].strip()[:88]})
    result["attribution_profiled_ratios_only"] = hot[:10]
    print("\n=== attribution (cProfile; RATIOS ONLY, absolutes are inflated)")
    for h in hot[:10]:
        print(f"    tot {h['tottime_s']:>8s}  cum {h['cumtime_s']:>8s}  "
              f"{h['where']}")

    out = args.out or os.path.join(ROOT, "research", "v1_1", "results",
                                   "core_profile_from_log.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
    print(f"\n-> {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
