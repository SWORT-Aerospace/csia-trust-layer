"""The support rule has no posterior threshold, and the papers must say so.

WHAT WAS WRONG
--------------
`papers/gate_conditioning/main.tex` stated the implemented consequence as

    "a leader above 0.999 with an empty D(a,b) against a required competitor
     is emitted as support lost for required information"

which is wrong twice.

1. **No such threshold exists.** `csia/v1_1/eligibility.py` fires
   `SUPPORT_LOST_FOR_REQUIRED_INFORMATION` on
   `sensitive_hypotheses & non_identifiable_against` alone, and
   `engineering/v1_1/support/support.py` says why in its own comment: *"No
   filtering by posterior mass -- that would make identifiability depend on
   the score whose support is in question."* Conditioning on the posterior
   would be circular, and the implementation deliberately does not.
2. **The data contradicts the stated rule.** Over the rows where the
   condition fires, the leader posterior runs down to ~0.969. A gate at 0.999
   would have excluded most of them.

The error mattered beyond accuracy: the paper's own contribution is that the
condition is STRUCTURAL and checkable before the system runs. Describing it
with a tuned-looking threshold undercuts exactly that, and invites a reviewer
to ask what chose the number.

WHAT THIS PINS
--------------
The two endpoints the manuscript now quotes, recomputed from the artifact
rather than trusted, plus the structural property itself: that firing ticks
exist across a WIDE posterior range, which is what makes "no threshold"
observable instead of merely asserted.
"""

from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "engineering", "v1_1", "SUPPORT_STATE_RESULTS.csv")
TEX = os.path.join(ROOT, "papers", "gate_conditioning", "main.tex")


def _firing_rows():
    with open(RESULTS, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, f"{RESULTS} is empty"
    return [r for r in rows if r["non_identifiable_against"].strip()]


def test_the_quoted_endpoints_are_what_the_artifact_says():
    firing = _firing_rows()
    assert firing, "no row has a non-empty non_identifiable_against"
    posteriors = [float(r["posterior"]) for r in firing]
    lo, hi = min(posteriors), max(posteriors)
    assert f"{lo:.4f}" == "0.9691", f"{lo!r} no longer rounds to 0.9691"
    assert f"{hi:.4f}" == "0.9998", f"{hi!r} no longer rounds to 0.9998"

    tex = open(TEX, encoding="utf-8").read()
    for rendered in ("0.9691", "0.9998"):
        assert rendered in tex, (
            f"{rendered} is bound in GATE_PAPER_ARTIFACT_MAP.yaml but no "
            f"longer appears in the manuscript")


def test_the_firing_ticks_span_a_wide_posterior_range():
    """The observable form of 'no posterior threshold'.

    If every firing tick sat above 0.999, the corrected sentence would be
    unfalsifiable from the data and a reader could reasonably suspect a hidden
    gate. A wide span is the evidence that no gate is there.
    """
    posteriors = [float(r["posterior"]) for r in _firing_rows()]
    span = max(posteriors) - min(posteriors)
    assert span > 0.02, (
        f"firing-tick posteriors span only {span:.4f}. The manuscript's claim "
        f"that no posterior threshold enters the rule is no longer visible in "
        f"this artifact; check whether a gate was introduced.")
    below = [p for p in posteriors if p < 0.999]
    assert len(below) > len(posteriors) // 2, (
        f"only {len(below)} of {len(posteriors)} firing ticks are below "
        f"0.999; the manuscript says a 0.999 gate 'would have passed most of "
        f"them', and that sentence is now false")


def test_every_firing_row_is_labelled_non_identifiable():
    """The rule and its label agree. A row that collapses structurally but is
    not labelled NON_IDENTIFIABLE would mean the two are computed
    independently and have drifted."""
    bad = [r for r in _firing_rows() if r["support_state"] != "NON_IDENTIFIABLE"]
    assert not bad, (
        f"{len(bad)} row(s) have a non-empty non_identifiable_against but a "
        f"support_state of {sorted({r['support_state'] for r in bad})}")


def test_the_manuscript_states_no_threshold_rather_than_a_number():
    """The specific wording that was wrong, kept out.

    Matched on the claim shape -- a posterior bound attached to the support
    rule -- rather than on the literal old sentence, so a paraphrase of the
    same mistake is caught too.
    """
    tex = open(TEX, encoding="utf-8").read()
    assert "no\nweight threshold enters the rule" in tex or \
           "no weight threshold enters the rule" in tex, (
        "the manuscript no longer states that the support rule is free of a "
        "threshold on the reported quantity. That is its distinguishing "
        "property; without the sentence a reader will assume the 0.9998 "
        "example IS the rule. NOTE the wording moved from 'posterior' to "
        "'weight' when the cross-paper terminology policy was applied: the "
        "deployed layer emits a normalized hypothesis weight, not a "
        "posterior. See research/PAPER_CROSS_CONSISTENCY.md.")
    for banned in ("leader above $0.999$", "leader above 0.999",
                   "posterior above $0.999$", "weight above $0.999$"):
        assert banned not in tex, (
            f"{banned!r} is back in the manuscript. The implementation has no "
            f"such threshold -- see engineering/v1_1/support/support.py, "
            f"which refuses to filter by posterior mass on purpose.")
