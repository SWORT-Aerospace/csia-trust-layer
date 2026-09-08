"""Attribute the PX4 decision-replay divergence, or say it is unattributed.

WHY THIS TOOL EXISTS
--------------------
`decision_replay.py` reports DIVERGENT on both platforms. HF-010 explained
and largely removed the ArduPilot divergence -- keying hand-off
reconstruction on channel ARRIVAL TIME rather than on a CHANGED VALUE took
it from 511 categorical differences to 13. It left PX4 at 144, unchanged,
which means whatever causes the PX4 divergence is a DIFFERENT mechanism and
has never been named. HF-004 stays open because of it.

This tool does not try to fix anything. It asks one question:

    WHICH EDGES DIFFER, ON WHICH TICKS, AND IS THERE A SINGLE MECHANISM?

and reports the answer whatever it is. A divergence that turns out to be
unattributable is a valid output; a divergence explained by a story the data
does not support is not.

WHAT IT REPORTS
---------------
  * every divergent tick, not the first five, classified by the exact
    symmetric difference of the live-edge sets
  * how the divergent ticks are distributed in time -- a mechanism that
    fires once looks nothing like one that fires throughout
  * for the dominant signature, the weight the replay and the recording
    each assigned to the edge, which separates "the edge was absent" from
    "the edge was present with weight zero". Those have different causes
    and the set comparison alone cannot tell them apart.

    python tools/assurance/attribute_replay_divergence.py \
        --platform px4 --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

LOGS = {
    "px4": "logs/shadow-sitl-px4/20260825T005931Z-1b4add14.part000.jsonl",
    "ardupilot": ("logs/shadow-sitl-ardupilot/"
                  "20260825T005244Z-8c32ffe5.part000.jsonl"),
}


def _live(d):
    """The same liveness rule decision_replay.py compares on."""
    return frozenset(
        k for k, val in d.items()
        if isinstance(val, (list, tuple)) and len(val) >= 2 and val[1] > 0)


def _weight(d, key):
    val = d.get(key)
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return val[1]
    return None            # absent is not the same as zero


def collect(platform: str, node: str = "gps", gate: str = "arrival") -> dict:
    """Re-run the replay, keeping EVERY divergence rather than five."""
    from csia.runtime.online import OnlineTrustLayer
    from csia.v1_1.staleness import build_runtime_stale_timeouts
    from tools.deploy.profile_core_from_log import (HandoffReconstructor,
                                                    load_ticks)

    log_path = os.path.join(ROOT, LOGS[platform])
    if not os.path.exists(log_path):
        return {"error": f"log absent: {LOGS[platform]}", "aborted": True}

    ticks = list(load_ticks(log_path))
    if not ticks:
        return {"error": "no ticks in log", "aborted": True}

    layer = OnlineTrustLayer(
        tick_hz=25.0, field_mode=True,
        stale_timeout_s=build_runtime_stale_timeouts(platform))
    reconstructor = HandoffReconstructor(gate=gate)

    replayed = []
    for tick in ticks:
        states = []
        for sensor, t, chans in reconstructor.samples_for_tick(tick):
            states.extend(layer.ingest(sensor, t, chans))
        for s in states:
            replayed.append((round(s.t, 6), s.trust.get(node),
                             dict(s.edges or {})))

    t0 = ticks[0]["t_mono"]
    recorded = [(round(x["t_mono"] - t0, 6),
                 (x.get("trust_post") or {}).get(node),
                 dict(x.get("gates") or {}))
                for x in ticks]

    half_tick = 0.02
    rec_sorted = sorted(recorded, key=lambda r: r[0])
    rec_times = [r[0] for r in rec_sorted]

    def nearest(t):
        import bisect
        i = bisect.bisect_left(rec_times, t)
        best = None
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(rec_sorted):
                d = abs(rec_times[j] - t)
                if best is None or d < best[0]:
                    best = (d, rec_sorted[j])
        return best[1] if best and best[0] <= half_tick else None

    divergences = []
    compared = 0
    for t, v, edges in replayed:
        match = nearest(t)
        if match is None or v is None:
            continue
        _, rv, rg = match
        if rv is None:
            continue
        compared += 1
        lr, lrec = _live(edges), _live(rg)
        if lr == lrec:
            continue
        divergences.append({
            "t": t,
            "missing_in_replay": sorted(lrec - lr),
            "extra_in_replay": sorted(lr - lrec),
            # THE DISCRIMINATOR. A set difference cannot distinguish an edge
            # the replay never produced from one it produced with weight 0.
            "weights": {
                k: {"replay": _weight(edges, k), "recorded": _weight(rg, k)}
                for k in sorted((lrec - lr) | (lr - lrec))},
        })

    signatures = Counter(
        (tuple(d["missing_in_replay"]), tuple(d["extra_in_replay"]))
        for d in divergences)

    # A mechanism that fires once and a mechanism that fires throughout look
    # nothing alike, so report the shape rather than only the count.
    times = [d["t"] for d in divergences]
    span = {"first": min(times), "last": max(times)} if times else {}
    if times:
        gaps = [round(b - a, 4) for a, b in zip(times, times[1:])]
        span["distinct_gaps"] = sorted(Counter(gaps).items(),
                                       key=lambda kv: -kv[1])[:5]

    return {
        "schema": "csia.assurance.replay_attribution/1",
        "platform": platform,
        "log": LOGS[platform],
        "node": node,
        "reconstruction_gate": gate,
        "decisions_compared": compared,
        "divergent": len(divergences),
        "distinct_signatures": [
            {"missing_in_replay": list(m), "extra_in_replay": list(e),
             "count": n}
            for (m, e), n in signatures.most_common()],
        "time_span_of_divergence": span,
        "examples": divergences[:8],
        "all_divergent_times": times,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", default="px4", choices=sorted(LOGS))
    ap.add_argument("--gate", default="arrival", choices=["arrival", "value"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    rep = collect(args.platform, gate=args.gate)
    if args.out:
        os.makedirs(os.path.dirname(os.path.join(ROOT, args.out)),
                    exist_ok=True)
        with open(os.path.join(ROOT, args.out), "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")

    if rep.get("aborted"):
        print(rep["error"], file=sys.stderr)
        return 1

    print(f"platform={rep['platform']}  compared={rep['decisions_compared']}"
          f"  divergent={rep['divergent']}")
    for sig in rep["distinct_signatures"]:
        print(f"  {sig['count']:5d}  missing={sig['missing_in_replay']}  "
              f"extra={sig['extra_in_replay']}")
    if rep["examples"]:
        print("  weights on the first divergence:")
        for k, w in rep["examples"][0]["weights"].items():
            print(f"    {k}: replay={w['replay']}  recorded={w['recorded']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
