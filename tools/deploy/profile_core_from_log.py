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


def core_samples_for_tick(tick, previous):
    """Rebuild the (sensor, t, channels) hand-offs for one logged tick.

    Reconstructs what `to_core_samples` produced at the time, including its
    freshness gate: a sensor is handed over only when one of its channels
    carries a value different from the previous tick.

    KNOWN LIMITATION, stated rather than hidden: two identical consecutive
    readings are indistinguishable from no new reading, so this slightly
    UNDER-counts hand-offs. The bias is toward reporting the core as cheaper
    than it is, which is the safe direction for a budget claim -- and if the
    replay still shows the cost, the cost is real.
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
    args = ap.parse_args()

    result = {"log": os.path.relpath(args.log, ROOT), "modes": {}}
    print(f"=== replaying {os.path.basename(args.log)}")

    for fm in (False, True):
        ticks, per_tick, handoffs, _ = replay(args.log, field_mode=fm,
                                              tick_hz=args.tick_hz)
        s = summarise(per_tick)
        s["handoffs"] = handoffs
        s["handoffs_per_tick"] = round(handoffs / max(1, len(ticks)), 2)
        result["modes"][f"field_mode={fm}"] = s
        print(f"    field_mode={str(fm):5s} median {s['median_us']:8.1f} us  "
              f"p95 {s['p95_us']:8.1f}  max {s['max_us']:9.1f}  "
              f"handoffs/tick {s['handoffs_per_tick']}")

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
