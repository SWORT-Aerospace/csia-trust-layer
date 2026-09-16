"""Replay a raw log into CSIA-facing observations, deterministically.

    python tools/hardware/e2m_replay.py --run runs/e2m0-001.jsonl \
        --out runs/e2m0-001.observations.jsonl

    # compare two replays of the same log
    python tools/hardware/e2m_replay.py --run runs/e2m0-001.jsonl --digest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_e2m.logging import verify_run                       # noqa: E402
from csia_e2m.replay import check_no_future_leakage, replay   # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--digest", action="store_true",
                        help="print a digest of the observation stream")
    parser.add_argument("--declare", action="append", default=[],
                        metavar="CH=SENSOR",
                        help="declared topology, e.g. --declare 0=imu_a")
    args = parser.parse_args(argv)

    declared = {}
    for item in args.declare:
        channel, _, name = item.partition("=")
        declared[int(channel)] = name

    manifest = args.run.with_suffix(".manifest.json")
    if manifest.is_file():
        report = verify_run(manifest)
        print(f"raw log integrity: {'OK' if report['ok'] else 'FAILED'}",
              file=sys.stderr)
        if not report["ok"]:
            print(f"  {report['reason']}", file=sys.stderr)
            return 1

    observations = list(replay(args.run, declared=declared))
    leakage = check_no_future_leakage(observations)
    if not leakage["ok"]:
        print(f"future leakage: {leakage['violations']}", file=sys.stderr)
        return 1

    payload = [o.as_dict() for o in observations]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            "\n".join(json.dumps(p, sort_keys=True) for p in payload) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)

    blob = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(blob).hexdigest()
    counts = {}
    for o in observations:
        counts[o.identity.state] = counts.get(o.identity.state, 0) + 1
    print(json.dumps({
        "observations": len(observations),
        "observed": sum(1 for o in observations if o.observed),
        "missing": sum(1 for o in observations if not o.observed),
        "identity_states": counts,
        "establishes_attribution": sum(
            1 for o in observations if o.identity.establishes_attribution),
        "stream_sha256": digest,
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
