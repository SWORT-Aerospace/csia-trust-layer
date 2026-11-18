#!/usr/bin/env python3
"""Verify every evidence_v2 output: stamped, complete, and bit-for-bit equal to
the committed MANIFEST.sha256.

    python publication/evidence_v2/check_stamps.py            # verify
    python publication/evidence_v2/check_stamps.py --write    # record the manifest

`make evidence-v2` regenerates every output and then runs this without
`--write`, so a regeneration that changes one byte of any figure, table, data
file or stamp fails the target. Checks, per output:

1. a sidecar `<output>.stamp.json` exists with every required field;
2. `output_sha256` in the stamp equals the file on disk;
3. `git_commit` is a real commit, not UNCOMMITTED;
4. the output and its stamp match MANIFEST.sha256.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MANIFEST = os.path.join(C.HERE, "MANIFEST.sha256")
REQUIRED = ("git_commit", "run_timestamp_utc", "script", "script_sha256", "inputs", "configs",
            "datasets", "seeds", "output_sha256", "software")


def outputs():
    found = []
    for sub in ("figures", "tables", "data"):
        base = os.path.join(C.HERE, sub)
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if name.endswith(".stamp.json"):
                found.append(os.path.join(base, name[: -len(".stamp.json")]))
    return found


def main(argv=None) -> int:
    write = "--write" in (argv if argv is not None else sys.argv[1:])
    errors, lines = [], []
    for out in outputs():
        st = json.load(open(out + ".stamp.json", encoding="utf-8"))
        missing = [k for k in REQUIRED if k not in st]
        if missing:
            errors.append(f"{C.rel(out)}: stamp lacks {missing}")
        if st.get("output_sha256") != C.sha256_file(out):
            errors.append(f"{C.rel(out)}: output differs from its stamp")
        if st.get("git_commit") in (None, "UNCOMMITTED"):
            errors.append(f"{C.rel(out)}: stamp git_commit is {st.get('git_commit')}")
        for p in (out, out + ".stamp.json"):
            lines.append(f"{C.sha256_file(p)}  {C.rel(p)}")
    if write:
        with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"wrote {C.rel(MANIFEST)} ({len(lines)} files)")
    else:
        want = open(MANIFEST, encoding="utf-8").read().splitlines() if os.path.exists(MANIFEST) else []
        if sorted(want) != sorted(lines):
            for line in sorted(set(want) ^ set(lines)):
                errors.append(f"manifest mismatch: {line}")
    for e in errors:
        print("FAIL", e)
    print(f"{len(lines) // 2} outputs checked, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    C.main_guard(main)
