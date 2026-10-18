"""Blocking terminology and numeric-family lint for both manuscripts.

Brief §3, §13 and §14 of the peer-review hardening campaign. The cross-paper
policy in `research/PAPER_CROSS_CONSISTENCY.md` is only worth having if it is
enforced; a policy in a markdown file is a policy until the first person edits
a manuscript at speed.

THREE FAMILIES OF ERROR, EACH ONE ALREADY MADE ONCE
---------------------------------------------------
1. TERMINOLOGY. The deployed layer emits a NORMALIZED HYPOTHESIS WEIGHT. It is
   not a posterior (EPS floor, EW smoothing over ~15 ticks, tempering by 1.5,
   softmax over a table-asserted hypothesis set), not a probability, and never
   a confidence. The mathematical paper's q_h and p_h ARE posteriors and the
   word is correct there, so this cannot be a global grep.
2. TRAJECTORY VARIABILITY. `generate_flight(seed)` is byte-identical across
   seeds; the Monte Carlo campaign varied fault class, amplitude, onset and
   the clean/faulted split over ONE trajectory. Any wording implying
   independent flights is false.
3. THE 118.82 FAMILY. 125 is a docstring illustration at the theoretical cap;
   0.98764 exists nowhere; 500 is the cap, not the banked mass. All three have
   appeared in prose, twice in different disguises.
"""

from __future__ import annotations

import os
import re

SYS = "papers/csia_systems/main.tex"
MATH = "papers/gate_conditioning/main.tex"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def _lines(rel):
    return _read(rel).split("\n")


#: Sentences that legitimately MENTION a forbidden word in order to forbid it.
#: A rule against a word necessarily contains the word; the use/mention
#: distinction is what keeps this guard from failing on its own subject.
_MENTION_MARKERS = (
    "not a posterior", "neither a posterior", "do not call", "deliberately",
    "rather than as", "not calibrated", "no posterior threshold",
    "no weight threshold", "we call the output",
)


def _is_mention(line: str) -> bool:
    low = line.lower()
    return any(m in low for m in _MENTION_MARKERS)


def test_the_systems_manuscript_never_calls_its_output_a_posterior():
    """The deployed quantity. Line 251 states the policy; nothing may
    contradict it."""
    offenders = []
    for n, line in enumerate(_lines(SYS), start=1):
        if line.lstrip().startswith("%"):
            continue
        if re.search(r"\bposterior\b", line, re.I) and not _is_mention(line):
            offenders.append(f"{SYS}:{n}: {line.strip()[:110]}")
    assert not offenders, (
        "the systems manuscript uses 'posterior' for its own output:\n  "
        + "\n  ".join(offenders) +
        "\n\nThe deployed layer emits a NORMALIZED HYPOTHESIS WEIGHT. See "
        "research/PAPER_CROSS_CONSISTENCY.md section A.")


def test_neither_manuscript_calls_anything_a_confidence():
    """Forbidden for both objects in both papers, except as a disclaimer."""
    offenders = []
    for rel in (SYS, MATH):
        for n, line in enumerate(_lines(rel), start=1):
            if line.lstrip().startswith("%"):
                continue
            if re.search(r"\bconfidence\b", line, re.I) and not _is_mention(line):
                offenders.append(f"{rel}:{n}: {line.strip()[:110]}")
    assert not offenders, (
        "'confidence' used as a description rather than a disclaimer:\n  "
        + "\n  ".join(offenders))


def test_the_math_manuscript_still_calls_its_formal_objects_posteriors():
    """The other direction, and the reason this is not a global grep.

    q_h and p_h are a prior times a strictly positive function of the data,
    normalized. That IS a posterior. A well-meaning global replace would make
    the mathematical paper wrong, so the guard asserts the word survives where
    it belongs.
    """
    tex = _read(MATH)
    assert tex.count("posterior") >= 10, (
        "'posterior' has been stripped from the mathematical paper. Its q_h "
        "and p_h are posteriors by construction; only the six uses describing "
        "the DEPLOYED layer were to be replaced.")


def test_no_manuscript_implies_the_monte_carlo_varied_the_trajectory():
    """`generate_flight(seed)` is byte-identical across seeds."""
    banned = ("independent flights", "independent flight trajectories",
              "independent trajectories", "randomised flights",
              "randomized flights", "varied the flight", "per-flight seed")
    offenders = []
    for rel in (SYS, MATH):
        low = _read(rel).lower()
        for phrase in banned:
            if phrase in low:
                offenders.append(f"{rel}: {phrase!r}")
    assert not offenders, (
        f"{offenders} implies trajectory variability. The campaign flew ONE "
        f"trajectory; it varied fault class, amplitude, onset and the "
        f"clean/faulted split. See tests/test_flight_truth_determinism.py.")


def test_the_118_family_stays_out_of_both_manuscripts():
    """125, 0.98764 and a measured-sounding 500, all three."""
    offenders = []
    for rel in (SYS, MATH):
        tex = _read(rel)
        for n, line in enumerate(tex.split("\n"), start=1):
            if line.lstrip().startswith("%"):
                continue
            if re.search(r"=\s*\$?125\$?\b", line):
                offenders.append(f"{rel}:{n}: 125 as a result "
                                 f"(it is a docstring illustration at the cap)")
            if "0.98764" in line:
                offenders.append(f"{rel}:{n}: 0.98764 exists in no artifact")
            if re.search(r"\b500\s+units\b", line):
                offenders.append(f"{rel}:{n}: 500 presented as banked mass "
                                 f"(500 is the cap; the mass is 475.6775)")
    assert not offenders, "\n  ".join([""] + offenders)


def test_the_bare_word_weight_is_qualified_where_the_two_papers_collide():
    """COLLISION HAZARD. The systems paper's 'normalized hypothesis weight'
    (the output, sums to 1) and the mathematical paper's w_h (the validity
    factor, sums to nothing) are different objects.

    The mathematical paper must name the validity factor on first use rather
    than relying on the bare word.
    """
    tex = _read(MATH)
    assert "validity factor" in tex, (
        "the mathematical paper no longer names w_h a 'validity factor'. "
        "Without it, a reader of both papers meets two different objects "
        "called 'weight'.")
