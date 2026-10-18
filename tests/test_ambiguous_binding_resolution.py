"""Section context narrows some ambiguous prose literals, and not others.

`propose_prose_bindings.py` leaves 27 literals AMBIGUOUS: several artifacts
carry the same value and a number alone cannot say which one the prose
meant. Filtering candidates to the artifacts of the section the sentence
appears in resolves a few.

MOST OF THEM STAY AMBIGUOUS, AND THAT IS THE HONEST ANSWER. 19 of 27 still
have more than one plausible source after the filter. A tool that resolved
all 27 would be guessing, and MX-013 records what guessing costs: of five
earlier tool proposals, two were wrong -- one bound a tick distance, one
the lower bound of a wider population.

Every verdict in ADJUDICATION was reached by reading the prose against the
artifact by hand. The tests below pin those readings, including the two
that are NOT bindings: a spurious match and a prose/artifact disagreement.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.publication.resolve_ambiguous_bindings import (  # noqa: E402
    ADJUDICATION, FALSE_FRIENDS, _is_false_friend)

REPORT = os.path.join(ROOT, "research", "publication",
                      "AMBIGUOUS_BINDING_RESOLUTION.json")


@pytest.fixture(scope="module")
def report():
    if not os.path.exists(REPORT):
        pytest.skip("AMBIGUOUS_BINDING_RESOLUTION.json not generated")
    with open(REPORT, encoding="utf-8") as fh:
        return json.load(fh)


def test_nothing_was_applied(report):
    """These bind into PAPER1_ARTIFACT_MAP.yaml, which the E1 freeze
    manifest hashes. Applying them would break the freeze they are recorded
    in."""
    assert "freeze" in report["nothing_is_applied"].lower()
    import subprocess
    diff = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--",
         "papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml"],
        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert diff == "", "the artifact map was modified; it must not be"


def test_most_literals_are_still_ambiguous(report):
    """The expected outcome. If this ever drops sharply, check whether the
    resolver started guessing rather than resolving."""
    counts = report["counts"]
    assert counts.get("STILL_AMBIGUOUS", 0) >= 15
    assert sum(counts.values()) == 27


def test_the_confirmed_bindings_are_hand_verified(report):
    """Three, each with a stated reason a person can check."""
    confirmed = {k: v for k, v in ADJUDICATION.items()
                 if v["verdict"] == "CONFIRMED"}
    assert set(confirmed) == {"0.678", "0.717", "0.723"}
    for literal, entry in confirmed.items():
        assert entry["binding"].count("#") == 1, literal
        artifact = entry["binding"].split("#")[0]
        assert os.path.exists(os.path.join(ROOT, artifact)), artifact
        assert len(entry["why"]) > 120, (
            f"{literal}: a confirmed binding needs a reason someone can "
            f"check, not an assertion")


def test_the_ramp_bindings_match_the_artifact():
    """The strongest of the three, re-derived here rather than trusted.

    The prose gives minimum trust 0.717 to 0.723 over 5, 20 and 60 s ramps,
    AND 104 to 168 ticks at the floor. The tick range is an independent
    corroboration: it must come from the same three entries.
    """
    path = os.path.join(ROOT, "research", "wp_c7", "results",
                        "glitch_mechanism.json")
    if not os.path.exists(path):
        pytest.skip("glitch_mechanism.json absent")
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)["ramp_versus_step"]

    trusts = [e["min_trust"] for e in entries]
    ticks = [e["floor_ticks"] for e in entries]
    assert round(min(trusts), 3) == 0.717
    assert round(max(trusts), 3) == 0.723
    assert min(ticks) == 104 and max(ticks) == 168
    assert entries[1]["min_trust"] == min(trusts)   # the 0.717 binding
    assert entries[2]["min_trust"] == max(trusts)   # the 0.723 binding


def test_the_floor_upper_end_is_flagged_not_bound():
    """A REAL DISCREPANCY, recorded rather than bound.

    The prose says the measured floor ranges 0.678 to 0.700. The artifact's
    observed_range is [0.6785, 0.9422] -- its upper end is 0.9422. 0.700 is
    the saturation value, not the top of that range, so there is nothing
    honest to bind 0.700 to.
    """
    assert ADJUDICATION["0.700"]["verdict"] == \
        "REVIEW_PROSE_AND_ARTIFACT_DISAGREE"
    assert "binding" not in ADJUDICATION["0.700"]

    path = os.path.join(ROOT, "research", "wp_c8", "results",
                        "response_surface.json")
    if not os.path.exists(path):
        pytest.skip("response_surface.json absent")
    with open(path, encoding="utf-8") as fh:
        efc = json.load(fh)["evidence_floor_confirmation"]
    assert efc["observed_range"][0] == 0.6785, "the 0.678 binding"
    assert efc["observed_range"][1] != 0.700, (
        "if the upper end is now 0.700 the discrepancy has been fixed; "
        "re-read the entry before deleting it")
    assert efc["predicted_e_f"] == 0.7


def test_a_false_friend_is_detected_not_bound():
    """kappa(S) = 0.000 over eight HYPOTHESIS classes matched the count of
    PYTHON CLASSES in a module. Same word, unrelated quantity."""
    assert ADJUDICATION["0.000"]["verdict"] == "SPURIOUS_MATCH"
    assert _is_false_friend({"artifact": "engineering/v2/V2_COMPLEXITY.json",
                             "shared_tokens": ["classes"]})
    # A candidate sharing a MEANINGFUL token must not be dismissed.
    assert not _is_false_friend({
        "artifact": "research/wp_c7/results/glitch_mechanism.json",
        "shared_tokens": ["ramp", "trust"]})
    assert "classes" in FALSE_FRIENDS


def test_a_duplicate_pointer_is_not_reported_as_a_choice():
    """Two pointers to one quantity is not two possible sources."""
    assert ADJUDICATION["0.735"]["verdict"] == "DUPLICATE_POINTER"


def test_every_adjudication_carries_a_reason():
    for literal, entry in ADJUDICATION.items():
        assert entry.get("why"), literal
        assert entry["verdict"] in {
            "CONFIRMED", "SPURIOUS_MATCH", "STILL_AMBIGUOUS",
            "ALREADY_STATED", "DUPLICATE_POINTER",
            "REVIEW_PROSE_AND_ARTIFACT_DISAGREE"}, literal
