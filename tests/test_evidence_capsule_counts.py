"""The referee-facing capsule may not state a count the ledger contradicts.

Peer-review hardening campaign, sections 16 and 24.

`tools/publication/verify_paper_public.py` prints a NOT VERIFIABLE list, and
that list is the half of the capsule a referee is most likely to quote. Its
first entry claims nothing is verified. If a human works through
`papers/BIB_EXTERNAL_VERIFICATION_PACKET.md` and clears entries, that sentence
becomes false the moment the first one clears -- and the capsule would go on
printing it, in a tool whose whole point is that it does not overstate.

An earlier draft of the capsule hard-coded "2 entries are corroborated and 16
remain unverified". Both numbers were stale within the same session, because
the same session went on to corroborate five more. Prose that counts things
must be checked against the thing it counts.
"""

from __future__ import annotations

import importlib.util
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "papers", "BIB_VERIFICATION_LEDGER.yaml")
CAPSULE = os.path.join(ROOT, "tools", "publication", "verify_paper_public.py")


def _capsule():
    spec = importlib.util.spec_from_file_location("_capsule", CAPSULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ledger_statuses():
    with open(LEDGER, encoding="utf-8") as fh:
        return [r["status"] for r in yaml.safe_load(fh)["entries"]]


def test_the_capsule_does_not_hard_code_a_bibliography_count():
    """A count in prose is a claim, and this one goes stale by design.

    The packet exists so a human clears entries. Any digit in these lines is a
    hostage to that work being done, so there must not be one.
    """
    mod = _capsule()
    for paper, rows in mod.NOT_VERIFIABLE.items():
        for label, why in rows:
            if "bibliograph" not in label.lower():
                continue
            # A numeral COUNTING entries, not a numeral in general: the math
            # capsule legitimately names "Heitjan & Rubin 1991", and a year is
            # not a count. What is forbidden is "N entries" / "N of them are
            # unverified" -- prose that has to be re-edited every time somebody
            # clears a row.
            # 1-3 digits only: a four-digit run is a year, and "Heitjan &
            # Rubin 1991" is a citation rather than a tally.
            counts = re.findall(
                r"\b\d{1,3}\b(?=[^.]{0,40}\b(?:entr|unverified|corroborated))",
                why)
            assert not counts, (
                f"{paper}: the capsule's bibliography line counts entries "
                f"({counts}). Counts drift the moment somebody works through "
                f"BIB_EXTERNAL_VERIFICATION_PACKET.md. Point at the ledger "
                f"instead of restating it.")


def test_the_prior_art_count_in_the_capsule_matches_the_matrix():
    """The one count the capsule DOES state, checked rather than forbidden.

    "20 of 21 prior-art rows are unread or unverified" is a concession, so it
    is worth stating precisely -- and a concession that drifts becomes an
    overstatement in one direction or a false modesty in the other.
    """
    import csv
    path = os.path.join(ROOT, "research", "math-paper", "PRIOR_ART_MATRIX.csv")
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    total = len(rows)
    weak = sum(1 for r in rows if r["status"] != "KNOWN")

    mod = _capsule()
    labels = [lab for rows_ in mod.NOT_VERIFIABLE.values() for lab, _ in rows_]
    stated = [lab for lab in labels if "prior-art rows" in lab]
    assert len(stated) == 1, f"expected one prior-art line, got {stated}"
    expected = f"{weak} of {total} prior-art rows"
    assert expected in stated[0], (
        f"the capsule says {stated[0]!r} but PRIOR_ART_MATRIX.csv now holds "
        f"{total} rows of which {weak} are not KNOWN. Expected "
        f"{expected!r}.")


def test_the_capsule_still_tells_the_truth_about_verification():
    """The one claim it does make: nothing is verified."""
    statuses = _ledger_statuses()
    mod = _capsule()
    labels = [lab for rows in mod.NOT_VERIFIABLE.values() for lab, _ in rows]
    claims_none_verified = any(
        "no bibliography entry is verified" in lab for lab in labels)
    if "VERIFIED" in statuses:
        assert not claims_none_verified, (
            "the ledger now contains a VERIFIED entry, so the capsule's "
            "'no bibliography entry is verified' line is FALSE. Update "
            "tools/publication/verify_paper_public.py -- this is the good "
            "outcome, and the tool must stop understating it.")
    else:
        assert claims_none_verified, (
            "nothing is verified in the ledger, yet the capsule no longer "
            "says so. The NOT VERIFIABLE list is the half a referee quotes; "
            "it may not quietly drop a live blocker.")
