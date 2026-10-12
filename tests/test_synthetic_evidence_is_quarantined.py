"""Synthetic evidence may never reach a paper artifact.

The synthetic adapter exists to construct states a real vehicle rarely
reaches, to generate structures for property testing at volume, and to build
systems that are deliberately wrong so a conformance suite can be shown to
reject them. All three are legitimate and none of them is evidence.

The danger is entirely mundane: a constructed trace gets written to a results
directory during development, and six months later somebody quotes a number
from it. The three labels the adapter stamps on every sample -- `synthetic`,
`synthetic_warning`, `admissible_as_evidence: false` -- exist so that trace
carries its own disqualification. THIS test is what makes them load-bearing:
it greps the research and publication trees and fails if any of them appears.

Scope note, stated because a grep-based guard is only as good as its scope:
this checks committed artifacts, not what a developer has in /tmp. It closes
the path from "constructed during a test" to "cited in a paper", which is the
path that actually goes wrong.
"""

from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Trees whose contents are, or feed, published claims.
#:
#: `figures/` is deliberately absent: it holds only PNGs, and a PNG cannot
#: carry a JSON marker. Including it made the coverage check below fail on a
#: directory there was nothing to check, which is worse than not checking it.
EVIDENCE_TREES = ("research", "publication", "papers", "campaigns")

#: Markers the synthetic adapter stamps. Any of them inside an evidence tree
#: means constructed data reached a place that publishes.
#:
#: THE FIRST DRAFT OF THIS LIST CONTAINED THE BARE PHRASE "SYNTHETIC
#: EVIDENCE", and it flagged papers/csia_systems/main.tex, which says
#: "...with a synthetic evidence sequence: maximum absolute error 0.00...".
#: That sentence is correct methodology, not a violation. A marker loose
#: enough to hit ordinary English would have been silenced by adding an
#: exemption for the manuscript -- and that exemption would then have covered
#: any real violation in the same file. So the marker is the adapter's own
#: distinctive string instead, which cannot occur by accident.
MARKERS = (
    '"synthetic": true',
    "SYNTHETIC EVIDENCE -- constructed for testing",
    '"platform": "synthetic"',
)

#: Files that legitimately DISCUSS the quarantine rather than violating it.
#: Named individually: a pattern-based exemption would grow to cover the
#: violation it is meant to catch.
ALLOWED = {
    "research/physical_validation/EVIDENCE_EXTENSION.yaml",
    "research/physical_validation/FAILURE_LEDGER.yaml",
    "research/physical_validation/PAPER_IMPACT_LEDGER.yaml",
}

SCAN_EXT = (".json", ".jsonl", ".yaml", ".yml", ".csv", ".md", ".tex")


def _files():
    for tree in EVIDENCE_TREES:
        base = os.path.join(ROOT, tree)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", ".git")]
            for name in filenames:
                if not name.endswith(SCAN_EXT):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, ROOT)
                if rel.replace(os.sep, "/") in ALLOWED:
                    continue
                yield rel, full


def test_no_synthetic_marker_appears_in_an_evidence_tree():
    offenders = []
    for rel, full in _files():
        try:
            with open(full, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        low = text.lower()
        for marker in MARKERS:
            if marker.lower() in low:
                offenders.append(f"{rel}: contains {marker!r}")
    assert not offenders, (
        "synthetic (constructed) data has reached a tree that publishes:\n  "
        + "\n  ".join(offenders) + "\n\n"
        "Synthetic samples are for unit tests, property testing, conformance "
        "testing and deliberately-bad-system testing. They are not evidence "
        "and may not appear in research/, publication/, papers/, campaigns/ "
        "or figures/. If a file legitimately DISCUSSES the quarantine, add it "
        "to ALLOWED by name.")


def test_the_synthetic_adapter_actually_stamps_all_three_markers():
    """The guard above is a grep. It is worthless if the marker is absent.

    So this asserts the stamp exists, in the serialised form a written trace
    would carry -- not on the live object, where a `to_log_dict` that dropped
    metadata would still pass.
    """
    from csia.aircraft.adapters.synthetic import SyntheticAdapter

    a = SyntheticAdapter(label="quarantine-check")
    a.set_channel("baro.altitude", 10.0)
    blob = json.dumps(a.sample().to_log_dict())

    assert '"synthetic": true' in blob.lower().replace('"synthetic":true',
                                                       '"synthetic": true')
    assert "SYNTHETIC EVIDENCE -- constructed for testing" in blob
    assert '"admissible_as_evidence": false' in \
        blob.lower().replace('"admissible_as_evidence":false',
                             '"admissible_as_evidence": false')


def test_the_synthetic_platform_string_is_the_disqualification():
    """A trial manifest that records the adapter name already records that
    the trial is not evidence. No extra field to forget."""
    from csia.aircraft.adapters.synthetic import SyntheticAdapter
    assert SyntheticAdapter.platform == "synthetic"


@pytest.mark.parametrize("tree", EVIDENCE_TREES)
def test_the_scan_actually_reaches_each_evidence_tree(tree):
    """A guard that silently scanned nothing would pass forever.

    Checked per tree, so a directory being renamed shows up here rather than
    as a quietly empty scan.
    """
    base = os.path.join(ROOT, tree)
    if not os.path.isdir(base):
        pytest.skip(f"{tree}/ does not exist in this checkout")
    seen = [rel for rel, _ in _files()
            if rel.replace(os.sep, "/").startswith(tree + "/")]
    assert seen, (
        f"{tree}/ exists but the quarantine scan matched no files in it. "
        f"Either every file has an unscanned extension or the walk is "
        f"broken; both make this guard vacuous for that tree.")
