"""Which evidence relations actually carried weight, per platform, measured.

TWICE NOW A RESULT HAS TURNED ON THIS AND IT WAS FOUND BY HAND.

  * `heading_course` -- the only magnetometer cross-check against an
    INDEPENDENT reference -- carried gate weight 0.0 for every tick of every
    hover flight, because its gate is `speed_gate * gvalid` and a hovering
    vehicle has no ground track. That left `attitude_gravity_mag` as the sole
    weighted mag check, and its reference is mag-slaved. The whole mag_emi
    finding rests on it.
  * PX4 SIH publishes no second IMU, so `redundant_imu` is dark and a GPS
    fault propagated into an attitude EMERGENCY unchecked.

Both were discovered by reading gate columns out of one flight at a time. This
derives the whole matrix mechanically from committed flight logs: for every
relation, on every platform, the share of ticks on which it carried non-zero
weight, and the mean weight when it did.

A relation at 0.0 is not evidence that is weak. It is evidence that is ABSENT,
and a diagnostic layer's coverage claim means nothing without knowing which
relations were live on the platform it ran on.

Reads committed artifacts only. Runs nothing, changes nothing.

  python tools/simulation/evidence_availability.py
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CAMPAIGNS = (
    "research/v1_1/results/mechanism_b_gps/*.json",
    "research/v1_1/results/mechanism_b/*.json",
    "research/v1_1/results/shadow_flights/*.json",
)
LIVE = 1e-6          # weight above which a relation is carrying evidence


def flight_logs(result):
    fid, ld = result.get("flight_id"), result.get("log_dir")
    if not fid or not ld:
        return []
    return [p for p in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl")))
            if fid in os.path.basename(p)]


def scan(result):
    """{relation: [n_live, sum_weight, n_ticks]} for one flight."""
    stats, ticks = {}, 0
    for path in flight_logs(result):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("record") != "tick":
                    continue
                gates = rec.get("gates") or {}
                if not gates:
                    continue
                ticks += 1
                for name, val in gates.items():
                    if not isinstance(val, (list, tuple)) or len(val) < 2:
                        continue
                    w = float(val[1])
                    s = stats.setdefault(name, [0, 0.0])
                    if w > LIVE:
                        s[0] += 1
                        s[1] += w
    return stats, ticks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "EVIDENCE_AVAILABILITY.json"))
    args = ap.parse_args()

    per = {}          # platform -> relation -> [live_ticks, weight_sum, ticks]
    flights = {}
    for pat in CAMPAIGNS:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            with open(path, encoding="utf-8") as fh:
                res = json.load(fh)
            plat = res.get("platform")
            if not plat:
                continue
            stats, ticks = scan(res)
            if not ticks:
                continue
            flights[plat] = flights.get(plat, 0) + 1
            acc = per.setdefault(plat, {})
            acc["__ticks__"] = acc.get("__ticks__", 0) + ticks
            for name, (live, wsum) in stats.items():
                a = acc.setdefault(name, [0, 0.0])
                a[0] += live
                a[1] += wsum

    if not per:
        print("no flight logs with gate data found")
        return 2

    platforms = sorted(per)
    relations = sorted({r for p in platforms for r in per[p]
                        if r != "__ticks__"})
    matrix = {}
    for rel in relations:
        row = {}
        for plat in platforms:
            live, wsum = per[plat].get(rel, [0, 0.0])
            ticks = per[plat]["__ticks__"]
            row[plat] = {
                "live_tick_share": round(live / ticks, 6) if ticks else None,
                "mean_weight_when_live": (round(wsum / live, 6) if live
                                          else None),
                "live_ticks": live, "ticks": ticks,
            }
        matrix[rel] = row

    print("=== evidence availability, share of ticks carrying non-zero weight")
    print(f"  flights scanned: "
          + ", ".join(f"{p}={flights[p]}" for p in platforms))
    hdr = f"  {'relation':28s}" + "".join(f"{p:>14s}" for p in platforms)
    print(hdr)
    dark = []
    for rel in relations:
        cells = ""
        for plat in platforms:
            sh = matrix[rel][plat]["live_tick_share"]
            cells += f"{(f'{sh:.3f}' if sh is not None else '-'):>14s}"
        print(f"  {rel:28s}{cells}")
        for plat in platforms:
            if matrix[rel][plat]["live_ticks"] == 0:
                dark.append((rel, plat))
    if dark:
        print("\n  RELATIONS THAT NEVER CARRIED WEIGHT (absent, not weak):")
        for rel, plat in dark:
            print(f"    {rel:28s} {plat}")

    out = {
        "what_this_measures": "share of logged ticks on which each evidence "
                              "relation carried non-zero gate weight",
        "why": "a relation at 0.0 is evidence that is ABSENT, not weak, and a "
               "coverage claim means nothing without knowing which relations "
               "were live on the platform it ran on",
        "live_threshold": LIVE,
        "flights_scanned": flights,
        "matrix": matrix,
        "never_live": [{"relation": r, "platform": p} for r, p in dark],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
