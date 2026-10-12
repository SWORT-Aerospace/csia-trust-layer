#!/usr/bin/env python3
"""SOURCE-ATTRIBUTION CONTROLS for the manuscript.

WHAT THIS NAME MEANS HERE, AND WHY IT IS STATED
------------------------------------------------
The upstream repository carries no artifact, script or term called
"srcattr". This script was written for this package, and "source attribution"
is an INTERPRETATION of that name: the controls below check that every
mathematical result in the manuscript is attributed to a source and carries
its declared novelty status, and that the manuscript claims no novelty and no
priority beyond what it explicitly proves. A reader who meant something else
by the name should read this docstring and disregard the file rather than
assume it checked something it did not.

The interpretation is not arbitrary. It is the discipline the paper already
imposes on itself: every proposition is labelled KNOWN in NOVELTY_AUDIT.md,
each is tied to a row of PRIOR_ART_MATRIX.csv, and the upstream repository
greps the manuscript for phrases that would contradict that. These controls
port those checks into the package so they run without the repository.

WHY "CONTROLS" AND NOT "CHECKS"
--------------------------------
A check that cannot fail proves nothing. Every control here is run twice:
once against the manuscript, and once against a PLANTED VIOLATION built in
memory. If the planted violation passes, the control is vacuous and this
script fails on that ground alone -- a green run means the controls both held
AND were capable of firing.

WHAT THESE CONTROLS DO NOT DO
------------------------------
They do not VERIFY the prior art. Every row of PRIOR_ART_MATRIX.csv is
WEB_SEARCH_ONLY or CANDIDATE_UNVERIFIED, one is NOT_FOUND_NEEDS_HUMAN, and no
publisher record was reachable from the authoring environment. Confirming
that a cited work says what the matrix says it says needs a human with
library access. These controls check ATTRIBUTION IS PRESENT AND CONSISTENT,
which is a different and much weaker property, and they say so in their own
output so the two are not confused.

    python scripts/srcattr_controls.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
SOURCE = os.path.join(PKG, "source")
DEFAULT_OUTPUTS = os.path.join(PKG, "outputs")

MANUSCRIPT = os.path.join(SOURCE, "Gate_Conditioning_v2_2.tex")
NOVELTY = os.path.join(SOURCE, "NOVELTY_AUDIT.md")
PRIOR_ART = os.path.join(SOURCE, "PRIOR_ART_MATRIX.csv")

#: Every mathematical result the manuscript states. If a proposition is added
#: upstream without a novelty row, control 1 fails.
PROPOSITIONS = ("P1", "P2", "P3", "C2", "C3", "P4", "P5a", "P5b",
                "P6a", "P6b", "P7", "P7b", "P7c", "P8")

#: Phrases that would assert novelty the paper does not have. Copied from the
#: upstream novelty audit; the wording is deliberately specific, because a
#: vague list would fire on ordinary prose and be deleted.
FORBIDDEN = (
    "new information theory",
    "first posterior-reweighting theorem",
    "novel kl bound",
    "new bayesian identity",
    "we prove for the first time",
)

#: Phrases that would claim PRIORITY. The paper claims none, for anything.
FORBIDDEN_PRIORITY = (
    "we were the first",
    "we are the first",
    "priority for this result",
    "our priority",
    "predates",
)

#: A line that FORBIDS or DISCLAIMS a phrase necessarily contains it. Skipping
#: whole files would blind the control to the manuscript; skipping lines that
#: carry a prohibition marker keeps it reading every assertion. This is the
#: upstream rule and it is reproduced rather than reinvented.
PROHIBITION_MARKERS = ("forbidden", "must not", "may not", "never",
                       "none claimed", "do not claim", "claim no",
                       "not acceptable", "prohibit", "no novelty",
                       "claims no")


def is_mention_only(line: str, phrase: str) -> bool:
    """USE versus MENTION: a register that quotes a banned phrase in order to
    ban it is mentioning it; a manuscript that writes it plain is using it."""
    quoted = 0
    for q in ('"', "'", "`"):
        quoted += line.count(f"{q}{phrase}{q}")
    return quoted >= line.count(phrase)


def scan_lines(text: str, phrases) -> list:
    """Return [(lineno, phrase, line)] for every ASSERTED occurrence."""
    hits = []
    for n, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if any(m in low for m in PROHIBITION_MARKERS):
            continue
        for phrase in phrases:
            if phrase in low and not is_mention_only(low, phrase):
                hits.append((n, phrase, line.strip()[:120]))
    return hits


# ------------------------------------------------------------- the controls

def control_every_proposition_has_a_novelty_row(novelty_text):
    """C1. Each proposition carries a row in the novelty audit."""
    missing = [p for p in PROPOSITIONS if f"| {p} |" not in novelty_text]
    return (not missing), {"propositions": len(PROPOSITIONS),
                           "missing_rows": missing}


def control_every_proposition_is_labelled_known(novelty_text):
    """C2. The audit's summary sentence still reads KNOWN for all of them.

    Checked as the sentence rather than per row, because that is the sentence
    the paper's own abstract and introduction rest on.
    """
    sentence = "Every mathematical proposition in this paper is labelled KNOWN"
    return (sentence in novelty_text), {"summary_sentence_present":
                                        sentence in novelty_text}


def control_no_novelty_phrase_is_asserted(manuscript_text):
    """C3. No forbidden novelty phrase appears as an assertion."""
    hits = scan_lines(manuscript_text, FORBIDDEN)
    return (not hits), {"asserted_novelty_phrases":
                        [{"line": n, "phrase": p, "text": t}
                         for n, p, t in hits]}


def control_no_priority_is_claimed(manuscript_text):
    """C4. No priority claim, for any result, against anyone."""
    hits = scan_lines(manuscript_text, FORBIDDEN_PRIORITY)
    return (not hits), {"asserted_priority_phrases":
                        [{"line": n, "phrase": p, "text": t}
                         for n, p, t in hits]}


def control_prior_art_matrix_is_not_ragged(rows, fieldnames):
    """C5. Every row has every field.

    A field that grows a comma without gaining its quotes shifts every field
    after it, and the shifted row still LOOKS complete to a reader.
    """
    ragged = [i for i, r in enumerate(rows, start=2)
              if any(r.get(f) is None for f in fieldnames) or None in r]
    return (not ragged), {"rows": len(rows), "ragged_rows": ragged,
                          "fields": len(fieldnames)}


def control_prior_art_verification_status_is_disclosed(rows):
    """C6. The matrix must not claim verification it does not have.

    This control PASSES when the rows are honestly marked unverified. It is
    not a verification of the prior art and must not be read as one.
    """
    blob = json.dumps(rows).upper()
    disclosed = any(marker in blob for marker in
                    ("WEB_SEARCH_ONLY", "CANDIDATE_UNVERIFIED",
                     "NOT_FOUND_NEEDS_HUMAN", "UNVERIFIED"))
    return disclosed, {"unverified_status_markers_present": disclosed,
                       "what_this_is_not":
                           "this control checks that the matrix DISCLOSES its "
                           "unverified state; it does not verify any citation"}


# ------------------------------------------------- the controls' own control

def planted_violations() -> dict:
    """Each control, run against text built to break it.

    A control that passes here is vacuous and the script fails.
    """
    fired = {}

    ok, _ = control_every_proposition_has_a_novelty_row(
        "| P1 | something |")
    fired["C1_every_proposition_has_a_novelty_row"] = not ok

    ok, _ = control_every_proposition_is_labelled_known(
        "this audit says nothing of the kind")
    fired["C2_every_proposition_is_labelled_known"] = not ok

    ok, _ = control_no_novelty_phrase_is_asserted(
        "We present a new Bayesian identity for gated posteriors.")
    fired["C3_no_novelty_phrase_is_asserted"] = not ok

    ok, _ = control_no_priority_is_claimed(
        "We are the first to describe this reweighting.")
    fired["C4_no_priority_is_claimed"] = not ok

    ok, _ = control_prior_art_matrix_is_not_ragged(
        [{"a": "1", "b": None}], ["a", "b"])
    fired["C5_prior_art_matrix_is_not_ragged"] = not ok

    ok, _ = control_prior_art_verification_status_is_disclosed(
        [{"status": "CONFIRMED_AGAINST_PUBLISHER"}])
    fired["C6_prior_art_verification_status_is_disclosed"] = not ok

    return fired


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs", default=DEFAULT_OUTPUTS)
    args = ap.parse_args()

    for path in (MANUSCRIPT, NOVELTY, PRIOR_ART):
        if not os.path.exists(path):
            print(f"FAIL: {path} is missing; the package is incomplete",
                  file=sys.stderr)
            return 2

    manuscript = open(MANUSCRIPT, encoding="utf-8").read()
    novelty = open(NOVELTY, encoding="utf-8").read()
    with open(PRIOR_ART, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    results = {}
    order = []

    def run(name, ok, detail):
        results[name] = {"pass": bool(ok), **detail}
        order.append(name)

    run("C1_every_proposition_has_a_novelty_row",
        *control_every_proposition_has_a_novelty_row(novelty))
    run("C2_every_proposition_is_labelled_known",
        *control_every_proposition_is_labelled_known(novelty))
    run("C3_no_novelty_phrase_is_asserted",
        *control_no_novelty_phrase_is_asserted(manuscript))
    run("C4_no_priority_is_claimed",
        *control_no_priority_is_claimed(manuscript))
    run("C5_prior_art_matrix_is_not_ragged",
        *control_prior_art_matrix_is_not_ragged(rows, fieldnames))
    run("C6_prior_art_verification_status_is_disclosed",
        *control_prior_art_verification_status_is_disclosed(rows))

    fired = planted_violations()

    print("SOURCE-ATTRIBUTION CONTROLS")
    print("-" * 70)
    for name in order:
        r = results[name]
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {name}")
    print()
    print("CONTROLS' OWN CONTROL -- each must fire on a planted violation")
    print("-" * 70)
    for name in sorted(fired):
        print(f"  [{'fires' if fired[name] else 'VACUOUS'}] {name}")

    all_pass = all(r["pass"] for r in results.values())
    all_fire = all(fired.values())

    doc = {
        "artifact": "SRCATTR_CONTROLS",
        "what_this_is": "source-attribution controls for the manuscript: "
                        "attribution present and consistent, no novelty "
                        "asserted, no priority claimed",
        "what_this_is_not": "verification of the prior art. Every row of "
                            "PRIOR_ART_MATRIX.csv is unverified against a "
                            "publisher record and a human with library "
                            "access is required to change that.",
        "name_interpretation": "the upstream repository carries no artifact "
                               "called 'srcattr'; 'source attribution' is "
                               "this package's reading of the name and is "
                               "stated so it can be disputed",
        "propositions_checked": list(PROPOSITIONS),
        "forbidden_novelty_phrases": list(FORBIDDEN),
        "forbidden_priority_phrases": list(FORBIDDEN_PRIORITY),
        "controls": results,
        "controls_fire_on_planted_violations": fired,
        "all_controls_pass": all_pass,
        "all_controls_are_capable_of_failing": all_fire,
        "verdict": "PASS" if (all_pass and all_fire) else "FAIL",
    }

    outputs = os.path.abspath(args.outputs)
    os.makedirs(outputs, exist_ok=True)
    out = os.path.join(outputs, "srcattr_controls.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print()
    print(f"  {os.path.relpath(out, PKG)}")
    if not all_fire:
        print("FAIL: a control passed its planted violation and is therefore "
              "vacuous", file=sys.stderr)
    if not all_pass:
        print("FAIL: a control did not hold against the manuscript",
              file=sys.stderr)
    return 0 if (all_pass and all_fire) else 1


if __name__ == "__main__":
    raise SystemExit(main())
