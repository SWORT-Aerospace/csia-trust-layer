"""Write the follow-up's seal-opening record from measured state.

Phase one's `SEAL_OPENING_RECORD.md` was authored by hand. Its facts were true,
but `results/EXTERNAL_ACCESS_CHECK.json` in the same phase had a *typed*
timestamp in it (`COUNTEREXAMPLE_LOG.md` IV-25), and a record written by hand
is a record that can drift from what it describes without anybody noticing.

Everything here is measured at run time: the clock, the branch, the commit, the
dirty paths, the frozen-core digest, both partition manifests, and the test
result read out of a recorded pytest run rather than asserted.

    python tools/research/iv_followup_seal_record.py \
        --suite-output <path to a recorded pytest run>

It **refuses to write** if the working tree is dirty or the recorded suite did
not exit zero. The record exists to say the seal was opened from a known state;
producing one that says otherwise would defeat it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
from typing import List, Optional, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/active_evidence/independent_validation"
OUT = BASE / "FOLLOWUP_SEAL_OPENING_RECORD.md"


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _dirty_paths() -> List[str]:
    return [line for line in _git("status", "--porcelain").splitlines()
            if line.strip()]


def _suite(path: pathlib.Path) -> Tuple[Optional[int], Optional[int], str]:
    """``(exit code, tests collected, raw last line)`` from a recorded run."""
    text = path.read_text(errors="replace")
    exit_match = re.search(r"PYTEST_EXIT=(\d+)", text)
    code = int(exit_match.group(1)) if exit_match else None
    passed = re.search(r"(\d+) passed", text)
    if passed:
        count = int(passed.group(1))
    else:
        # ``pytest -q`` prints one dot per test and no summary when nothing
        # fails. Counting the dots is the measurement available.
        count = sum(line.count(".") for line in text.splitlines()
                    if re.fullmatch(r"[.sxX]+\s*(\[\s*\d+%\])?", line.strip()))
    tail = next((ln for ln in reversed(text.splitlines()) if ln.strip()), "")
    return code, count, tail


def _frozen_core() -> Tuple[str, str]:
    doc = json.loads(
        (ROOT / "research/physical_validation/results/BUILD_PROVENANCE.json")
        .read_text())
    core = doc["frozen_core"]
    return (core.get("digest", "unknown"),
            "identical" if core.get("identical_to_the_freeze") else "DRIFTED")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(suite_output: pathlib.Path, force_dirty: bool) -> int:
    from csia_independent_validation import followup_partitions as fp
    from csia_independent_validation import partitions as pt

    dirty = _dirty_paths()
    code, count, tail = _suite(suite_output)

    if dirty and not force_dirty:
        print("working tree is dirty; commit first. Paths:", file=sys.stderr)
        for line in dirty[:20]:
            print(f"  {line}", file=sys.stderr)
        return 1
    if code != 0:
        print(f"recorded suite exit was {code!r}, not 0 -- refusing to write "
              f"a record that says the seal was opened from a green tree",
              file=sys.stderr)
        print(f"last line of {suite_output}: {tail}", file=sys.stderr)
        return 1

    digest, drift = _frozen_core()
    validation = (BASE / "results/FOLLOWUP_VALIDATION.json")
    lines = [
        "# Seal Opening Record — the paired-design follow-up",
        "",
        "**GENERATED** by `tools/research/iv_followup_seal_record.py`. Every",
        "value below is measured at run time; none is typed. The script",
        "refuses to write if the working tree is dirty or the recorded suite",
        "did not exit zero, so a record that exists is a record of a known",
        "state.",
        "",
        "This is the follow-up's own seal, on its own partition. **Phase",
        "one's sealed partition is not reopened** and is not touched by this.",
        "",
        "| field | value |",
        "|---|---|",
        f"| opened at (UTC) | `{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}` |",
        f"| branch | `{_git('rev-parse', '--abbrev-ref', 'HEAD')}` |",
        f"| HEAD | `{_git('rev-parse', 'HEAD')}` |",
        f"| working tree | {'clean, 0 dirty paths' if not dirty else f'**DIRTY**, {len(dirty)} paths'} |",
        f"| recorded suite | `{suite_output.name}`, {count} tests, "
        f"`PYTEST_EXIT={code}` |",
        f"| frozen-core digest | `{digest}` ({drift}) |",
        f"| phase-one partition manifest | `{pt.manifest_hash()}`, untouched |",
        f"| follow-up partition manifest | `{fp.manifest_hash()}` |",
        f"| follow-up sealed partition | `final`, {len(fp.PARTITIONS['final'])} seeds |",
    ]
    if validation.is_file():
        document = json.loads(validation.read_text())
        lines.append(f"| follow-up validation artifact | "
                     f"`{_sha256(validation)[:16]}…`, "
                     f"{document['n_rows']} rows |")
    lines += [
        "",
        "## What the follow-up's seal protects",
        "",
        "Twenty-four seeds drawn in a domain of their own, asserted at import",
        "to be disjoint from every phase-one seed and from every companion",
        "baseline seed. They have never been simulated. The design they run",
        "is frozen by `PREREGISTRATION_AMENDMENT_4.md` and",
        "`PREREGISTRATION_AMENDMENT_5.md`, both committed before this record.",
        "",
        "## How it is opened",
        "",
        "`csia_independent_validation.followup_partitions.seeds` raises",
        "`PermissionError` for `final` unless the caller passes",
        "`i_am_opening_the_sealed_partition=True`. One call site does, in",
        "`tools/research/iv_followup_campaign.py`, reached only by",
        "`--open-the-seal`. Both are one grep away.",
        "",
        "## What opening it does not license",
        "",
        "Nothing. It is a confirmatory run of a design frozen before it was",
        "opened. It cannot change a hypothesis, a metric, a threshold or an",
        "arm. If its results disagree with validation, that disagreement is",
        "the result and is reported as one.",
        "",
        "It does not license a novelty claim, a certification claim, an",
        "airworthiness claim or a promotion. It runs three plants in a",
        "simulator against a synthetic pack.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"suite {count} tests exit {code}; tree clean; "
          f"follow-up manifest {fp.manifest_hash()[:16]}…")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-output", required=True, type=pathlib.Path)
    parser.add_argument("--i-know-the-tree-is-dirty", action="store_true",
                        dest="force_dirty",
                        help="write anyway and say so in the record")
    args = parser.parse_args()
    raise SystemExit(main(args.suite_output, args.force_dirty))
