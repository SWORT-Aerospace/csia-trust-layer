"""Repeat clean shadow flights and measure what the stack does on NOTHING.

A single clean flight tells you almost nothing. The question this answers is
the one a deployment actually turns on:

    **On a flight with no injected fault, does CSIA stay quiet?**

That number has existed for the bench simulator since the freeze ("clean: 0
false alarms", section 2.2 of the verdict document). It has NEVER been
measured through the v1.1 ingestion path -- the adapter, the semantic
qualification layer, the freshness gate and the shadow runner all sit between
the vehicle and the core now, and none of them existed when that row was
written.

It shells out to `shadow_sitl_check.py` rather than reimplementing it. A
campaign runner that duplicates the harness measures the runner.

WHAT COUNTS AS AN ALARM. Any escalation above NORMAL recorded in the flight
log. A CAUTION that recovers is still an alarm: on a real aircraft a
recovering CAUTION has already reached the operator.

WHAT THIS IS NOT. These are SITL flights. "Clean" means no injected fault, not
"representative of a real airframe" -- the noise profile is the simulator's,
and W-3 records that IMU-bias detection is a property of the noise model
rather than of the fault. No number here transfers to hardware.

  python tools/deploy/shadow_campaign.py --platform ardupilot --flights 3
  python tools/deploy/shadow_campaign.py --platform px4 --flights 3
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

HARNESS = os.path.join(ROOT, "tools", "deploy", "shadow_sitl_check.py")


def _escalations(log_dir: str, flight_id: str):
    """Every tick above NORMAL, read from the S9 log itself.

    Read from the log rather than from the harness's stdout: the log is the
    artifact a post-flight reader has, and if the two ever disagree the log is
    what would be believed.

    THE FIELD NAMES WERE CHECKED AGAINST A REAL LOG, not assumed. The first
    version of this function looked for `failsafe.state`, which does not
    exist in the record. It would have reported ZERO escalations on every
    flight and the campaign would have concluded "no false alarms" from a
    reader that could not see one. The record carries
    `recommendation.level` (NORMAL / CAUTION / ...) and `disagreement.state`
    (CSIA_ONLY / BOTH_REACTED / AUTOPILOT_ONLY / BOTH_QUIET).
    """
    out, ticks, seen_levels = [], 0, set()
    if not os.path.isdir(log_dir):
        return {"ticks": 0, "above_normal": [], "levels_seen": [],
                "note": f"log dir not found: {log_dir}"}
    for fn in sorted(os.listdir(log_dir)):
        if flight_id not in fn or not fn.endswith(".jsonl"):
            continue
        with open(os.path.join(log_dir, fn), encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("record") != "tick":
                    continue
                ticks += 1
                level = (rec.get("recommendation") or {}).get("level")
                if not level:
                    continue
                seen_levels.add(level)
                if level != "NORMAL":
                    out.append({
                        "t_mono": rec.get("t_mono"),
                        "level": level,
                        "disagreement": (rec.get("disagreement") or {}).get("state"),
                        "csia_top": (rec.get("disagreement") or {}).get("csia_top"),
                    })
    return {"ticks": ticks, "above_normal": out,
            "levels_seen": sorted(seen_levels)}


def run_flight(platform: str, seconds: float, index: int, out_dir: str):
    out = os.path.join(out_dir, f"flight_{platform}_{index:02d}.json")
    cmd = [sys.executable, HARNESS, "--platform", platform,
           "--seconds", str(seconds), "--fly", "--out", out]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    wall = time.time() - t0
    record = {"index": index, "platform": platform, "exit_code": proc.returncode,
              "wall_s": round(wall, 1), "result_file": os.path.relpath(out, ROOT)}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            record["result"] = json.load(fh)
    else:
        record["stderr_tail"] = proc.stderr[-800:]
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", choices=("ardupilot", "px4"),
                    default="ardupilot")
    ap.add_argument("--flights", type=int, default=3)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_dir = os.path.join(ROOT, "research", "v1_1", "results", "shadow_flights")
    os.makedirs(out_dir, exist_ok=True)

    flights = []
    for i in range(args.flights):
        print(f"=== clean flight {i + 1}/{args.flights} on {args.platform}")
        rec = run_flight(args.platform, args.seconds, i, out_dir)
        res = rec.get("result") or {}
        log_dir = os.path.join(ROOT, res.get("log_dir", ""))
        esc = _escalations(log_dir, res.get("flight_id", "\x00"))
        rec["escalations"] = esc
        # A reader that saw NO ticks has not established "no alarms"; it has
        # established that it could not read the log.
        rec["log_readable"] = esc["ticks"] > 0
        lat = res.get("latency") or {}
        auth = (res.get("command_authority") or {}).get("result")
        print(f"    exit {rec['exit_code']}  ticks {(res.get('stats') or {}).get('ticks')}  "
              f"median {lat.get('median_us')} us  R13 {str(res.get('R13'))[:28]}  "
              f"authority {auth}  "
              f"above-NORMAL {len(esc['above_normal'])}/{esc['ticks']} ticks")
        flights.append(rec)

    ok = [f for f in flights if f.get("result")]
    medians = [f["result"]["latency"]["median_us"] for f in ok
               if (f["result"].get("latency") or {}).get("median_us")]
    alarmed = [f for f in ok if f["escalations"]["above_normal"]]
    unreadable = [f["index"] for f in ok if not f.get("log_readable")]
    authority = {(f["result"].get("command_authority") or {}).get("result")
                 for f in ok}

    summary = {
        "platform": args.platform,
        "flights_requested": args.flights,
        "flights_completed": len(ok),
        "seconds_each": args.seconds,
        # THE number this campaign exists to produce.
        "clean_flights_with_an_escalation": len(alarmed),
        "logs_unreadable": unreadable,
        "escalation_detail": [
            {"index": f["index"],
             "levels": sorted({e["level"]
                               for e in f["escalations"]["above_normal"]}),
             "disagreement": sorted({e["disagreement"]
                                     for e in f["escalations"]["above_normal"]
                                     if e["disagreement"]}),
             "csia_top": sorted({e["csia_top"]
                                 for e in f["escalations"]["above_normal"]
                                 if e["csia_top"]}),
             "ticks_above_normal": len(f["escalations"]["above_normal"]),
             "ticks_total": f["escalations"]["ticks"],
             "first_t_mono": f["escalations"]["above_normal"][0]["t_mono"]}
            for f in alarmed],
        "command_authority_results": sorted(x for x in authority if x),
        "latency_median_us": {
            "per_flight": medians,
            "min": min(medians) if medians else None,
            "max": max(medians) if medians else None,
            "median_of_medians": (round(statistics.median(medians), 1)
                                  if medians else None),
        },
        "R13": [str(f["result"].get("R13")) for f in ok],
        "flights": flights,
        "caveat": "SITL, not hardware. 'Clean' means no injected fault; the "
                  "noise profile is the simulator's, and W-3 records that "
                  "detection can be a property of the noise model rather than "
                  "of the fault. No number here transfers to an aircraft.",
    }
    path = args.out or os.path.join(
        ROOT, "research", "v1_1", "results",
        f"shadow_campaign_{args.platform}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True, default=str)

    print(f"\n=== {len(ok)}/{args.flights} clean flights completed on "
          f"{args.platform}")
    print(f"    flights with an escalation above NORMAL: "
          f"{len(alarmed)}/{len(ok)}")
    print(f"    command authority: {sorted(x for x in authority if x)}")
    if medians:
        print(f"    tick median across flights: {min(medians)}-{max(medians)} us")
    print(f"-> {os.path.relpath(path, ROOT)}")

    # A campaign where a flight did not complete has not measured anything,
    # and a command path that became reachable is the one result that must
    # never be reported as a footnote.
    if len(ok) != args.flights:
        return 1
    if authority != {"NO_COMMAND_PATH_REACHABLE"}:
        return 1
    # "No alarms" from a log nobody could read is not a result.
    if unreadable:
        print(f"    !!! {len(unreadable)} flight log(s) unreadable: the "
              f"escalation count from those is not evidence")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
