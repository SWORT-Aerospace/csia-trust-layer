"""Replay an S9 flight log and answer the six questions it exists to answer.

    What did the aircraft know?      What did CSIA know?
    What evidence was unavailable?   What did CSIA conclude?
    What did the autopilot conclude? Did they disagree?

Reads the JSONL parts (including .gz) in order and reports. It computes
nothing new: everything below was recorded at flight time, which is the point
-- a post-flight answer that depends on re-running the layer is not evidence
about the flight.

  python tools/simulation/replay_flight_log.py logs/shadow/<flight_id>
"""

import argparse
import collections
import glob
import gzip
import json
import os
import sys


def read(path_or_prefix):
    if os.path.isdir(path_or_prefix):
        pats = [os.path.join(path_or_prefix, "*.part*")]
    else:
        pats = [path_or_prefix + ".part*", path_or_prefix]
    files = sorted(p for pat in pats for p in glob.glob(pat))
    if not files:
        raise SystemExit(f"no log parts found for {path_or_prefix!r}")
    for p in files:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="flight id, directory, or part path")
    ap.add_argument("--max-examples", type=int, default=3)
    args = ap.parse_args()

    header = footer = None
    ticks = 0
    states = collections.Counter()
    blocked = collections.Counter()
    missing = collections.Counter()
    tops = collections.Counter()
    levels = collections.Counter()
    lat = []
    examples = collections.defaultdict(list)

    for row in read(args.log):
        rec = row.get("record")
        if rec == "header":
            header = header or row
            continue
        if rec == "footer":
            footer = row
            continue
        ticks += 1
        d = row.get("disagreement", {})
        states[d.get("state", "?")] += 1
        if len(examples[d.get("state")]) < args.max_examples:
            examples[d.get("state")].append(
                (row["t_mono"], d.get("csia_top"), d.get("csia_level"),
                 d.get("autopilot_mode")))
        for b in row.get("evidence_unavailable", []):
            blocked[b["channel"]] += 1
        for name, c in row["canonical"]["channels"].items():
            if c.get("missing"):
                missing[f"{name}:{c['missing']}"] += 1
        tops[(row.get("diagnosis") or {}).get("top")] += 1
        levels[(row.get("recommendation") or {}).get("level")] += 1
        lat.append(row.get("latency_us", 0.0))

    if header is None:
        raise SystemExit("log has no header record; provenance is unknown")

    print("=== provenance")
    for k in ("flight_id", "mode", "profile", "adapter_platform",
              "adapter_version", "autopilot_version", "csia_version",
              "csia_commit", "frozen_core_tag", "vehicle_config_hash",
              "contract_version"):
        print(f"    {k:22s} {header.get(k)}")
    ca = header.get("command_authority", {})
    print(f"    {'command_authority':22s} {ca.get('result')}")

    print(f"\n=== {ticks} ticks")
    if lat:
        lat_sorted = sorted(lat)
        p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))]
        print(f"    latency mean {sum(lat)/len(lat):.1f} us, "
              f"p95 {p95:.1f} us, max {max(lat):.1f} us "
              f"(budget 2000 us)")
        if max(lat) > 2000:
            print("    *** R13 EXCEEDED on at least one tick ***")

    print("\n=== did they disagree?")
    for state, n in states.most_common():
        print(f"    {state:16s} {n:7d}  {100.0*n/max(ticks,1):5.1f}%")
        for t, top, level, mode in examples.get(state, []):
            print(f"        t={t:8.2f}  csia={top}/{level}  autopilot={mode}")

    print("\n=== what CSIA concluded")
    for name, n in tops.most_common(8):
        print(f"    {str(name):24s} {n:7d}")
    print("    levels: " + ", ".join(f"{k}={v}" for k, v in
                                     levels.most_common()))

    print("\n=== what evidence was unavailable")
    if blocked:
        for ch, n in blocked.most_common():
            print(f"    REFUSED  {ch:24s} {n:7d} ticks")
    else:
        print("    no channel was refused as evidence")
    for key, n in missing.most_common(10):
        print(f"    missing  {key:32s} {n:7d} ticks")

    if footer:
        print(f"\n=== footer: {footer.get('ticks')} ticks, "
              f"{footer.get('write_errors')} write errors")
    else:
        print("\n=== NO FOOTER: the log was not closed cleanly "
              "(crash, power loss, or still running)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
