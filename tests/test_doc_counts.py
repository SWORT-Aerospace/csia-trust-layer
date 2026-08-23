"""Guard against stale test counts in outward-facing documentation.

A hand-maintained test count in prose is wrong the moment the next test
lands. This project published "39", "48", "62" and "77" in public artifacts;
every one of them was the true collected count at some commit, and every one
of them was stale by the time a reader saw it (see
``docs/audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md`` §1.3 for the timeline).

The rule enforced here: a *live* document may not state a suite-level test
count unless it equals the count pytest actually collects. Historical records
that are explicitly dated and scoped are exempt — an audit that says "62 tests
at commit 3ecd788" is a true statement about the past and must not be
rewritten.

Exemption is granted three ways:
  1. the file lives under a historical-record path (``EXEMPT_PREFIXES``);
  2. the line names a commit sha or an ISO date, which scopes the claim;
  3. the line carries an explicit ``<!-- doc-count-ok -->`` marker.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Records of what was true at a stated commit. These are supposed to contain
# historical counts; rewriting them would destroy the audit trail.
EXEMPT_PREFIXES = (
    "docs/audit/",
    "research/",
)

# Suite-level count phrasing. Deliberately narrow: "failsafe suite (4 tests)"
# in the traceability matrix counts tests for one requirement, not the suite,
# and must not be caught here.
COUNT_PATTERNS = (
    re.compile(r"(\d+)[\s\-]tests?\s+(?:suite|harness)", re.I),
    re.compile(r"(?:full|test)\s+suite\s*[(,:]\s*(\d+)", re.I),
    re.compile(r"harness\s*\(\s*(\d+)\s*tests?", re.I),
    re.compile(r"(\d+)\s+tests?,\s*CI", re.I),
    re.compile(r"suite\s+of\s+(\d+)", re.I),
)

# A line that scopes its claim to a commit or a date is a historical statement.
SCOPED = re.compile(r"\b[0-9a-f]{7,40}\b|\b\d{4}-\d{2}-\d{2}\b", re.I)
MARKER = "<!-- doc-count-ok -->"


def _tracked_markdown():
    """Tracked .md files, so untracked scratch notes never fail the suite."""
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        pytest.skip("git not available; cannot determine tracked files")
    return [ROOT / line for line in out.stdout.split("\n") if line.strip()]


def collected_test_count() -> int:
    """Ask pytest how many tests it collects. Collection only — nothing runs."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        pytest.skip(f"collection failed (exit {out.returncode}); "
                    "cannot establish the reference count")

    # Modern pytest -q prints one "path/to/file.py: N" line per module.
    per_file = re.findall(r"^\S+\.py:\s*(\d+)\s*$", out.stdout, re.M)
    if per_file:
        return sum(int(n) for n in per_file)

    # Fallback for the "N tests collected" summary form.
    summary = re.search(r"(\d+)\s+tests?\s+collected", out.stdout)
    if summary:
        return int(summary.group(1))

    pytest.skip("could not parse a collected-test count from pytest output")


def _violations(expected: int):
    bad = []
    for path in _tracked_markdown():
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(EXEMPT_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.split("\n"), start=1):
            if MARKER in line or SCOPED.search(line):
                continue
            for pattern in COUNT_PATTERNS:
                for found in pattern.finditer(line):
                    value = int(found.group(1))
                    if value != expected:
                        bad.append((rel, lineno, value, line.strip()[:110]))
    return bad


def test_no_document_states_a_stale_test_count():
    """Every unscoped suite count in live docs must match what pytest collects.

    Fix by deleting the number, not by updating it: the count changes every
    time a test lands, and prose does not follow. If the statement is about a
    past commit, name that commit on the same line and it becomes exempt.
    """
    expected = collected_test_count()
    bad = _violations(expected)
    assert not bad, (
        f"pytest collects {expected} tests, but these documents state a "
        f"different suite count:\n"
        + "\n".join(f"  {rel}:{ln}  says {val}  |  {snippet}"
                    for rel, ln, val, snippet in bad)
        + "\n\nPrefer removing the count from prose entirely. To keep a "
          "historical statement, name its commit or date on the same line, "
          f"or append {MARKER}."
    )


def test_guard_would_catch_a_stale_count():
    """The detector must actually fire — a guard that cannot fail is not one."""
    stale = [
        "Simulated fault harness (77 tests, CI)",
        "full test suite (62 tests)",
        "a 48-test suite covering the runtime",
        "Runtime + failsafe + plugins, 39 tests, CI",
        "regression suite of 100 cases",
    ]
    for line in stale:
        assert any(p.search(line) for p in COUNT_PATTERNS), (
            f"pattern set failed to flag a stale count: {line!r}")


def test_guard_does_not_fire_on_scoped_or_unrelated_counts():
    """Historical and per-requirement counts must survive untouched."""
    allowed = [
        # per-requirement count in the traceability matrix, not the suite
        "`test_runtime` failsafe suite (4 tests)",
        # explicitly scoped to a commit
        "62 tests at commit 3ecd788",
        # explicitly dated
        "the suite collected 77 tests on 2026-08-03",
    ]
    for line in allowed:
        if SCOPED.search(line):
            continue
        assert not any(p.search(line) for p in COUNT_PATTERNS), (
            f"pattern set wrongly flagged an allowed line: {line!r}")
