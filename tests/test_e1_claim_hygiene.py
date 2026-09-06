"""E1 freeze conditions, as tests rather than as a checklist someone reads.

The freeze requires four things to be true of the repository, not just of one
document:

  1. **no live trust-causation claim** -- the refuted "gate closure causes the
     rise because gated-out disagreement disappears" may appear only inside an
     explicit superseded/refuted framing;
  2. **no stale n=1 current-stack claim** in a manuscript, where repeated
     evidence now exists;
  3. **no forbidden universality wording** attached to the repeated campaigns;
  4. the frozen scientific core **unchanged**.

WHY A PROXIMITY CHECK AND NOT A BARE GREP
------------------------------------------
The refuted sentence must stay findable -- a designer who read the old wording
needs to discover it was withdrawn -- so deleting it would be worse than
keeping it. What must not exist is the sentence standing on its own. So this
checks that every occurrence sits within a few lines of an explicit marker.

That design is a direct consequence of six earlier guards in this repository
firing on their own documentation. A guard that cannot tell "asserting X" from
"recording that X was withdrawn" will fire on the correction and push the next
author toward deleting the history instead of marking it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

#: The refuted causal explanation, in the forms it has actually been written.
CAUSATION = re.compile(
    r"source of disagreement"
    r"|less to disagree about"
    r"|gated[- ]out disagreement disappear", re.I)

#: Markers that turn an occurrence into a record of a withdrawal.
SUPERSEDED = re.compile(
    r"supersed|refut|withdrawn|no longer|FL-016|E1-TRUSTCAUSE"
    r"|earlier draft|previously read|once rested", re.I)

#: How many lines either side count as "in the same breath".
WINDOW = 12

#: Searched for claim hygiene. Frozen historical records are excluded by name
#: below, with the reason, rather than by a pattern that could hide a live one.
SEARCH_DIRS = ("papers", "handoff", "standards", "docs", "research")

#: Text files only. A .json result artifact records what a run measured and is
#: not a claim about causation.
SUFFIXES = (".md", ".tex", ".yaml", ".yml", ".csv")

#: EXEMPT, each for a stated reason.
EXEMPT = {
    # The generator's own source states the forbidden wording so the claim
    # table can forbid it. Not a claim; the definition of one.
    "research/physical_validation/E1_FINAL_CLAIM_TABLE.csv",
}


def _files():
    out = []
    for d in SEARCH_DIRS:
        for base, _dirs, names in os.walk(os.path.join(ROOT, d)):
            if ".git" in base:
                continue
            for n in names:
                if n.endswith(SUFFIXES):
                    p = os.path.join(base, n)
                    rel = os.path.relpath(p, ROOT)
                    if rel not in EXEMPT:
                        out.append((rel, p))
    return sorted(out)


def test_no_live_trust_causation_claim():
    """Every occurrence of the refuted explanation is marked as withdrawn."""
    bare = []
    for rel, path in _files():
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines):
            if not CAUSATION.search(line):
                continue
            lo, hi = max(0, i - WINDOW), min(len(lines), i + WINDOW + 1)
            if not any(SUPERSEDED.search(x) for x in lines[lo:hi]):
                bare.append(f"{rel}:{i + 1}: {line.strip()[:90]}")
    assert not bare, (
        "the refuted trust-causation explanation appears without a "
        "superseded/refuted marker nearby:\n  " + "\n  ".join(bare) +
        "\n\nIt may be RECORDED as withdrawn. It may not be ASSERTED.")


def test_no_stale_n_equals_one_current_stack_claim_in_a_manuscript():
    """A manuscript may not still say the current-stack repeat is n=1.

    `$n=1$` legitimately survives elsewhere in both manuscripts -- one deployed
    LAYER, one implementation -- so this looks only for the trial-count sense,
    which is what the campaigns replaced.
    """
    pattern = re.compile(
        r"n=1\$? fault trial"
        r"|one trial per platform"
        r"|\$n=1\$ fault", re.I)
    hits = []
    for name in ("papers/csia_systems/main.tex",
                 "papers/gate_conditioning/main.tex"):
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if pattern.search(line):
                hits.append(f"{name}:{i}: {line.strip()[:90]}")
    assert not hits, (
        "a manuscript still describes the current-stack repeat as n=1, but "
        "three preregistered campaigns of 20+20 have run:\n  "
        + "\n  ".join(hits))


def test_the_manuscript_does_not_claim_universality_from_the_repeats():
    """20/20 is not 'always', and the guard says so in the paper's own text."""
    path = os.path.join(ROOT, "papers", "csia_systems", "main.tex")
    if not os.path.exists(path):
        pytest.skip("manuscript not present")
    # LaTeX hard-wraps, so every check is against the flattened text. A
    # substring check against the raw source would fail on a reflow that
    # changed nothing, which trains the next author to weaken the guard.
    flat = " ".join(open(path, encoding="utf-8").read().split())
    for token in ("repeated under the tested conditions",
                  "not a rate, a frequency, an exposure figure",
                  "reported separately and never pooled"):
        assert token in flat, (
            f"the current-stack paragraph no longer says: {token!r}")


def test_the_manuscript_carries_the_refutation_visibly():
    """FL-016 is a result, not cleanup. It belongs in the paper, not only in
    the ledger."""
    path = os.path.join(ROOT, "papers", "csia_systems", "main.tex")
    if not os.path.exists(path):
        pytest.skip("manuscript not present")
    flat = " ".join(open(path, encoding="utf-8").read().split())
    assert "took a claim away" in flat or "refute that explanation" in flat, (
        "the manuscript no longer reports that the repeated campaigns "
        "corrected the earlier causal interpretation")
    assert "matched control" in flat


def test_the_frozen_core_is_unchanged():
    """Freeze condition 4, against the recorded hashes rather than a tag.

    The tag is local-only (blocker O-1), so a tag diff SKIPS on a fresh clone
    and a skipped freeze check reads as green. The hash file runs everywhere.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_v1_frozen.py::test_diagnostic_core_matches_its_recorded_hashes",
         "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, (
        "the frozen scientific core no longer matches its recorded hashes:\n"
        + proc.stdout[-2000:])
