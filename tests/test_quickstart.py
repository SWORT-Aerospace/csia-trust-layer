"""The integration quickstart still runs, and still runs OUTSIDE the repo.

`engineering/v2/quickstart.py` is the on-ramp a consumer meets first. It
asserts its own results, so running it IS the test -- but two things have to be
checked around it that it cannot check about itself:

  1. it exits ZERO. A quickstart whose assertions started failing would still
     print a plausible narrative up to the point it died, and nobody reads
     stdout in CI.

  2. it works with NO repository checkout and NO data directory. Run from the
     repository root, a missing package resource or a relative path would go
     unnoticed and the first person to hit it would be the first outside
     reader.

The subprocess runs from a temporary directory for exactly that reason.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUICKSTART = os.path.join(ROOT, "engineering", "v2", "quickstart.py")


def _run(cwd):
    return subprocess.run([sys.executable, QUICKSTART], cwd=cwd,
                          capture_output=True, text=True, timeout=900)


def test_the_quickstart_runs_from_outside_the_repository(tmp_path):
    out = _run(str(tmp_path))
    assert out.returncode == 0, (
        "engineering/v2/quickstart.py failed from a directory that is not the "
        f"repository root.\n--- stdout ---\n{out.stdout[-3000:]}\n"
        f"--- stderr ---\n{out.stderr[-3000:]}")
    # Every step must have run; a quickstart that silently skipped one would
    # still exit zero.
    for step in ("1. THE TRAP", "2. THE RIGHT WIRING", "3. A FAULT",
                 "4. AMBIGUITY", "5. PLUGIN FAILURE", "6. THE FOUR RULES"):
        assert step in out.stdout, f"step missing from the run: {step}"


def test_the_quickstart_says_what_the_package_is(tmp_path):
    """The prototype disclaimer is not decoration. It is in `csia info` and it
    is here, and it may not quietly disappear from the first thing a consumer
    reads."""
    out = _run(str(tmp_path))
    assert "NOT FLIGHT SOFTWARE" in out.stdout


def test_the_readiness_document_exists_and_is_referenced():
    doc = os.path.join(ROOT, "docs", "product", "CSIA_READINESS.md")
    assert os.path.exists(doc)
    text = open(doc, encoding="utf-8").read()
    # The three statements that make it a readiness assessment rather than a
    # brochure. If any is deleted, the document has changed character.
    for required in ("NOT FLIGHT SOFTWARE",
                     "Product maturity: M2",
                     "No target-hardware measurement exists and none is "
                     "claimed"):
        assert required in text, f"CSIA_READINESS.md no longer says: {required}"
    assert "quickstart.py" in text

    quickstart = open(QUICKSTART, encoding="utf-8").read()
    assert "CSIA_READINESS.md" in quickstart, \
        "the quickstart no longer points at the readiness document"


def test_the_readiness_document_does_not_claim_flight_readiness():
    """The one way this document could go wrong is by drifting into a
    brochure. These phrases would each be false today."""
    text = open(os.path.join(ROOT, "docs", "product", "CSIA_READINESS.md"),
                encoding="utf-8").read().lower()
    for forbidden in ("flight qualified", "flight-qualified", "do-178",
                      "production ready", "production-ready",
                      "certified", "airworthy"):
        # "flight software" appears inside "NOT FLIGHT SOFTWARE", so match
        # the affirmative forms only.
        assert forbidden not in text.replace("no do-178c", ""), forbidden
