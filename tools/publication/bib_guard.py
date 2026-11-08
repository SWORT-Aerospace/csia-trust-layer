"""Publication guard: no unresolved markers in a submission manuscript.

A manuscript that reaches a referee carrying ``VERIFY`` or
``FROM-BRIEF-UNVERIFIED`` beside a citation is telling the referee that the
authors did not check it. This fails the build instead.

WHAT IS SCANNED. Everything under ``papers/`` that is part of a submission
bundle: ``.tex``, ``.bib``, ``.cls``, ``.sty``. Research notes elsewhere in the
repository are NOT scanned -- markers are how in-progress work records its own
uncertainty, and removing them would destroy that signal.

WHAT IS NOT DONE. This guard never edits a bibliography and never invents a
citation. Making it pass means checking each entry against the publisher
record by hand and removing the marker once verified. Deleting a marker
without doing that check is falsification, not a fix.

Exit status 0 = clean, 1 = markers found, 2 = a scanned path is missing.

Run:  python tools/publication/bib_guard.py [--paper PATH ...]
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Each is a marker a human left meaning "not checked yet".
#
# CASE-SENSITIVE, deliberately. A first version matched case-insensitively and
# flagged two ordinary English sentences in the manuscript -- "Dong, Yin and Li
# verify diagnosability..." and "Verify them jointly on the same fault grid."
# A guard that forbids an author from using the verb "verify" is a bad guard.
# Every real marker in this repository is written in capitals, which is the
# convention, so matching capitals costs nothing and removes the false
# positives.
MARKERS = (
    r"VERIFY",
    r"TODO[_\- ]?CITATION",
    r"FROM[_\- ]?BRIEF[_\- ]?UNVERIFIED",
    r"CITATION[_\- ]?NEEDED",
    r"RECONSTRUCTED",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"\?\?\?",
)
MARKER_RE = re.compile("|".join(MARKERS))

SCAN_EXT = (".tex", ".bib", ".cls", ".sty")

# A file may declare itself a non-submission working note with this line.
# Nothing in a submission bundle is permitted to carry it.
OPT_OUT = "publication-guard: research-note"


def scan(paper_dir):
    findings, scanned = [], 0
    for base, _dirs, files in os.walk(paper_dir):
        for name in sorted(files):
            if not name.endswith(SCAN_EXT):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError as exc:
                findings.append((rel, 0, f"unreadable: {exc}", ""))
                continue
            if OPT_OUT in text:
                continue
            scanned += 1
            for n, line in enumerate(text.splitlines(), 1):
                m = MARKER_RE.search(line)
                if m:
                    findings.append((rel, n, m.group(0), line.strip()[:110]))
    return findings, scanned


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", action="append", default=None,
                    help="paper directory; repeatable. Default: every "
                         "immediate subdirectory of papers/")
    args = ap.parse_args()

    papers_root = os.path.join(ROOT, "papers")
    if args.paper:
        dirs = [os.path.join(ROOT, p) for p in args.paper]
    else:
        dirs = [os.path.join(papers_root, d)
                for d in sorted(os.listdir(papers_root))
                if os.path.isdir(os.path.join(papers_root, d))]

    missing = [d for d in dirs if not os.path.isdir(d)]
    if missing:
        for d in missing:
            print(f"ERROR: no such paper directory: "
                  f"{os.path.relpath(d, ROOT)}")
        return 2

    total, total_scanned, files_with_findings = 0, 0, set()
    for d in dirs:
        rel = os.path.relpath(d, ROOT)
        findings, scanned = scan(d)
        total_scanned += scanned
        files_with_findings.update(f for f, _n, _m, _l in findings)
        print(f"=== {rel}  ({scanned} submission files scanned)")
        if not findings:
            print("  PASS  no unresolved markers")
            continue
        by_marker = {}
        for _f, _n, marker, _line in findings:
            by_marker[marker.upper()] = by_marker.get(marker.upper(), 0) + 1
        print(f"  FAIL  {len(findings)} unresolved markers: "
              + ", ".join(f"{k} x{v}" for k, v in sorted(by_marker.items())))
        for f, n, marker, line in findings[:40]:
            print(f"        {f}:{n}  [{marker}]  {line}")
        if len(findings) > 40:
            print(f"        ... and {len(findings) - 40} more")
        total += len(findings)

    print()
    if total:
        print(f"BIBLIOGRAPHY GUARD: FAIL -- {total} unresolved markers in "
              f"{len(files_with_findings)} of {total_scanned} submission "
              f"files: {', '.join(sorted(files_with_findings))}")
        print("This is a publication blocker, not a code defect. Each entry "
              "must be checked against the publisher record by a human and "
              "the marker removed only once verified. Do not delete markers "
              "to make this pass.")
        return 1
    print(f"BIBLIOGRAPHY GUARD: PASS -- {total_scanned} submission files "
          f"clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
