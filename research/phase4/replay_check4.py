"""Compare two passes of the Phase-4 campaign over the same partition.

WHY THIS IS NOT `cmp`
---------------------
The campaign document carries `ns_total`, a wall-clock nanosecond timing
measurement, because computational cost is one of the preregistered reported
quantities. Wall clock is not a function of the seed, so two honest passes
over the same partition are NOT byte-identical and never will be. A
byte-identity check on this document fails every time and says nothing.

So the campaign DECLARES which fields are environment-specific, this script
strips exactly those and compares everything else, and the comparison it
reports is the one that carries meaning: every seed, every fault cell, every
detector, every declared threshold, all three alarm times.

    python research/phase4/replay_check4.py A.json B.json
"""
from __future__ import annotations

import argparse
import json
import sys


def _strip(document: dict) -> dict:
    """Remove the fields the document itself declares as environment-specific.

    Only the declared ones. A pass that silently removed anything else would
    be hiding a real disagreement, so an undeclared field spelling is a hard
    error rather than a no-op.
    """
    out = json.loads(json.dumps(document))
    declared = out.pop("environment_specific_fields", None)
    if declared is None:
        raise SystemExit(
            "ABORT: the document does not declare environment_specific_fields, "
            "so this script cannot know what it is allowed to ignore.")
    for spec in declared:
        if spec.startswith("runs[]."):
            field = spec.split(".", 1)[1]
            for r in out["runs"]:
                r.pop(field, None)
        else:
            raise SystemExit(f"ABORT: unsupported field spec {spec!r}")
    return out


def compare(a: dict, b: dict) -> dict:
    sa, sb = _strip(a), _strip(b)
    identical = sa == sb
    differing = []
    if not identical:
        for key in sorted(set(sa) | set(sb)):
            if key != "runs" and sa.get(key) != sb.get(key):
                differing.append(key)
        ra, rb = sa.get("runs", []), sb.get("runs", [])
        if len(ra) != len(rb):
            differing.append(f"runs: {len(ra)} vs {len(rb)}")
        else:
            for i, (x, y) in enumerate(zip(ra, rb)):
                if x != y:
                    differing.append(
                        f"runs[{i}] seed={x.get('seed')} gain={x.get('gain')} "
                        f"onset={x.get('onset_s')}")
    return {
        "identical_after_declared_exclusions": identical,
        "excluded": a.get("environment_specific_fields"),
        "runs_compared": len(a.get("runs", [])),
        "differing": differing[:20],
        "n_differing": len(differing),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("a")
    ap.add_argument("b")
    args = ap.parse_args(argv)
    with open(args.a, encoding="utf-8") as fh:
        a = json.load(fh)
    with open(args.b, encoding="utf-8") as fh:
        b = json.load(fh)
    report = compare(a, b)
    print(json.dumps(report, indent=1))
    if report["identical_after_declared_exclusions"]:
        print("P4_REPLAY_IDENTICAL=yes")
        return 0
    print("P4_REPLAY_IDENTICAL=no", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
