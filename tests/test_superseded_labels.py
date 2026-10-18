"""Labels that a later experiment falsified, and must not come back.

A verdict string travels: it is written into artifacts, read by downstream
tools, quoted into prose, and eventually into a paper. When the interpretation
behind one is falsified, deleting the reasoning is not enough -- the STRING has
to stop being emitted, or the falsified claim keeps propagating under its own
name.

RATE_MISDECLARED is the case in point. It asserted that the contract's declared
rate was wrong. The controlled link-rate experiment
(`tools/simulation/px4_link_rate_probe.py`) showed the declaration is correct
for the link it describes, and that PX4 delivery is link/configuration
conditioned: the driven qualification connection requests the stream and gets
~10 Hz, the passive shadow connection requests nothing and gets the lower
default. The starvation is real; the diagnosis was not. The label is now
STARVED_BY_TRANSPORT.

These tests fail if the falsified label is emitted again as a live verdict.
Historical NOTES about the supersession are allowed and expected -- the point
is to keep the correction legible, not to erase that it happened.

Reads committed artifacts and tool source. Runs nothing.
"""

from __future__ import annotations

import glob
import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(ROOT, "research", "v1_1", "results")

SUPERSEDED = "RATE_MISDECLARED"
REPLACEMENT = "STARVED_BY_TRANSPORT"

# Where a verdict actually lives in an artifact. A bare substring scan over the
# whole file would also hit the supersession NOTE, which is documentation of
# the correction rather than a use of it.
VERDICT_FIELDS = ("verdict", "conclusion")


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _artifacts():
    return sorted(glob.glob(os.path.join(RESULTS, "*.json")))


def test_no_committed_artifact_emits_the_superseded_verdict():
    """The falsified label must not appear in any verdict-bearing field."""
    offenders = []
    for path in _artifacts():
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            continue
        for key, val in _walk(data):
            if key in VERDICT_FIELDS and val == SUPERSEDED:
                offenders.append(os.path.basename(path))
                break
    assert not offenders, (
        f"{SUPERSEDED} is still emitted as a live verdict in: "
        f"{sorted(set(offenders))}. It was falsified by the link-rate "
        f"experiment; use {REPLACEMENT}. Regenerate with "
        f"`make evidence-audit`.")


def test_the_replacement_verdict_is_actually_in_use():
    """A rename that silently stopped classifying anything would also pass above."""
    path = os.path.join(RESULTS, "EVIDENCE_COVERAGE_LEDGER.json")
    if not os.path.exists(path):
        pytest.skip("run tools/simulation/evidence_coverage_ledger.py first")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert REPLACEMENT in data["verdict_meanings"], data["verdict_meanings"]
    seen = {v for k, v in _walk(data) if k == "verdict"}
    assert REPLACEMENT in seen, (
        f"nothing is classified {REPLACEMENT} any more -- the PX4 starvation "
        f"is unfixed, so it should still be reported")


def test_the_supersession_is_documented_rather_than_erased():
    """The correction must stay legible: a silent rename hides that it happened."""
    path = os.path.join(RESULTS, "EVIDENCE_COVERAGE_LEDGER.json")
    if not os.path.exists(path):
        pytest.skip("run tools/simulation/evidence_coverage_ledger.py first")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    note = data["verdict_meanings"].get("SUPERSEDED_LABEL", "")
    assert SUPERSEDED in note, "the artifact no longer records what it replaced"


def test_the_replacement_meaning_refuses_the_two_forbidden_readings():
    """The verdict text must not license either falsified claim."""
    path = os.path.join(RESULTS, "EVIDENCE_COVERAGE_LEDGER.json")
    if not os.path.exists(path):
        pytest.skip("run tools/simulation/evidence_coverage_ledger.py first")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    text = data["verdict_meanings"][REPLACEMENT].lower()
    assert "not evidence that the platform" in text, text
    assert "universally" in text, text
