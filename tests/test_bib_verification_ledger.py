"""A bibliography marker may not be retired without a verification record.

`tools/publication/bib_guard.py` fails while a marker exists. It cannot fail
when a marker is DELETED, and deleting one is the easiest possible way to turn
the build green without doing any verification. That guard's own docstring
says "Deleting a marker without doing that check is falsification, not a fix";
until now nothing enforced the sentence.

`papers/BIB_VERIFICATION_LEDGER.yaml` carries one row per (paper, key). The
rule:

    marker present  +  UNVERIFIED   ->  honest, blocks submission
    marker absent   +  VERIFIED     ->  honest, does not block
    marker absent   +  UNVERIFIED   ->  FAIL: a marker was retired with no record
    marker present  +  VERIFIED     ->  FAIL: contradictory

and a VERIFIED row must name an accepted route. A web search is a
`rejected_route` by name, so recording one is a deliberate visible act rather
than an oversight.

WHAT THIS DOES NOT DO. It cannot tell whether a human who wrote VERIFIED
actually read the publisher record. Nothing can. What it does is make the
claim explicit, attributable and dated, so the falsification has to be
written down rather than performed by deletion.
"""

from __future__ import annotations

import os
import re

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "papers", "BIB_VERIFICATION_LEDGER.yaml")

#: The same vocabulary bib_guard.py scans for, as literals. Kept here rather
#: than imported so that weakening one file cannot silently weaken both.
MARKERS = ("VERIFY", "TODO", "FIXME", "XXX", "???", "RECONSTRUCTED",
           "FROM-BRIEF-UNVERIFIED", "FROM_BRIEF_UNVERIFIED",
           "CITATION-NEEDED", "CITATION_NEEDED")

PAPERS = {
    "csia_systems": os.path.join(ROOT, "papers", "csia_systems", "refs.bib"),
    "gate_conditioning": os.path.join(ROOT, "papers", "gate_conditioning",
                                      "refs.bib"),
}


def bib_entries(path: str) -> dict:
    """{key: markers found} for every @entry in a .bib file.

    An entry's attributed region is its own brace span PLUS the contiguous
    block of `%` comment lines immediately above it, which is where this
    repository writes `% FROM-BRIEF-UNVERIFIED`. A file-level header is
    separated from the first entry by a blank line and is therefore NOT
    attributed to it -- otherwise the header's own legend, which names every
    marker, would make every first entry look marked.
    """
    lines = open(path, encoding="utf-8").read().splitlines()
    out, i = {}, 0
    while i < len(lines):
        m = re.match(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", lines[i])
        if not m:
            i += 1
            continue
        key = m.group(2)
        top = i
        while top - 1 >= 0 and lines[top - 1].lstrip().startswith("%"):
            top -= 1
        depth, j = 0, i
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            if j > i and depth <= 0:
                break
            j += 1
        block = lines[top:j + 1]
        out[key] = sorted({mk for mk in MARKERS
                           if any(mk in ln for ln in block)})
        i = j + 1
    return out


def _ledger():
    with open(LEDGER, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    assert doc["schema"] == "csia.publication.bib_verification_ledger/1"
    return doc


LEDGER_DOC = _ledger()
ROWS = LEDGER_DOC["entries"]
BY_KEY = {(r["paper"], r["key"]): r for r in ROWS}


def test_the_ledger_has_exactly_one_row_per_bibliography_entry():
    """Catches an entry added with no row, and a row for a deleted entry.
    Either would let something slip past the rule below."""
    actual = set()
    for paper, path in PAPERS.items():
        assert os.path.exists(path), path
        for key in bib_entries(path):
            actual.add((paper, key))
    assert actual, "no bibliography entries found; the parser is broken"
    ledger = set(BY_KEY)
    assert actual == ledger, (
        f"ledger and bibliographies disagree.\n"
        f"  in a .bib with no ledger row: {sorted(actual - ledger)}\n"
        f"  ledger rows with no .bib entry: {sorted(ledger - actual)}")


def test_no_marker_was_retired_without_a_verification_record():
    """THE RULE THIS FILE EXISTS FOR."""
    offenders = []
    for paper, path in PAPERS.items():
        for key, markers in bib_entries(path).items():
            row = BY_KEY.get((paper, key))
            if row is None:
                continue        # reported by the test above
            if not markers and row["status"] != "VERIFIED":
                offenders.append(f"{paper}/{key}")
    assert not offenders, (
        f"{offenders} carry no marker but are not VERIFIED in "
        f"papers/BIB_VERIFICATION_LEDGER.yaml.\n\n"
        f"A marker was retired without a verification record. Either restore "
        f"the marker, or verify the entry against the publisher and record "
        f"the route, checker, date and record consulted. Deleting a marker to "
        f"make a guard pass is falsification, not a fix.")


def test_a_verified_entry_does_not_still_carry_a_marker():
    """The contradictory state. If both are true, one of them is a lie and
    there is no way to tell which."""
    bad = []
    for paper, path in PAPERS.items():
        for key, markers in bib_entries(path).items():
            row = BY_KEY.get((paper, key))
            if row and row["status"] == "VERIFIED" and markers:
                bad.append(f"{paper}/{key} still carries {markers}")
    assert not bad, bad


@pytest.mark.parametrize("row", ROWS,
                         ids=[f"{r['paper']}/{r['key']}" for r in ROWS])
def test_every_row_is_well_formed(row):
    for field in ("paper", "key", "status", "route", "checked_by",
                  "checked_on", "record", "note"):
        assert field in row, f"{row.get('key')}: missing field {field}"
    assert row["status"] in (
        "VERIFIED", "UNVERIFIED", "CORROBORATED_NO_PUBLISHER_RECORD"), \
        row["status"]
    assert (row["note"] or "").strip(), \
        f"{row['key']}: a row with no note explains nothing"

    accepted = set(LEDGER_DOC["accepted_routes"])
    rejected = set(LEDGER_DOC["rejected_routes"])
    corroborating = set(LEDGER_DOC.get("corroboration_only_routes", ()))
    if row["status"] == "VERIFIED":
        assert row["route"] in accepted, (
            f"{row['key']}: VERIFIED via {row['route']!r}, which is not an "
            f"accepted route. Accepted: {sorted(accepted)}")
        for field in ("checked_by", "checked_on", "record"):
            assert row[field], (
                f"{row['key']}: VERIFIED but {field} is empty. A verification "
                f"nobody signed and dated is not a verification.")
    elif row["status"] == "CORROBORATED_NO_PUBLISHER_RECORD":
        # A strictly intermediate state: better evidence than UNVERIFIED,
        # weaker than VERIFIED, and it retires NOTHING. The marker stays and
        # bib-guard stays red, which `test_a_corroborated_row_still_carries_
        # its_marker` below enforces.
        assert row["route"] in corroborating, (
            f"{row['key']}: corroborated via {row['route']!r}, which is not a "
            f"declared corroboration route. Declared: {sorted(corroborating)}")
        for field in ("checked_by", "checked_on", "record"):
            assert row[field], (
                f"{row['key']}: corroborated but {field} is empty. The point "
                f"of the state is that it says exactly what was consulted.")
    else:
        assert row["route"] is None, (
            f"{row['key']}: UNVERIFIED rows must not name a route")
    assert row["route"] not in rejected, (
        f"{row['key']}: {row['route']!r} is a rejected route. A web search "
        f"result is a second unverified source, not a publisher record.")


def test_a_corroborated_row_still_carries_its_marker():
    """CORROBORATED_NO_PUBLISHER_RECORD must not become a soft VERIFIED.

    It exists so that real but insufficient evidence is visible. If it ever
    let a marker be retired, it would be a rename of the failure the ledger
    was built to prevent.
    """
    offenders = []
    for paper, path in PAPERS.items():
        for key, markers in bib_entries(path).items():
            row = BY_KEY.get((paper, key))
            if row and row["status"] == "CORROBORATED_NO_PUBLISHER_RECORD" \
                    and not markers:
                offenders.append(f"{paper}/{key}")
    assert not offenders, (
        f"{offenders} are corroborated only, yet their markers are gone. "
        f"Corroboration is not verification: no accepted route was reachable, "
        f"so nothing may be retired.")


def test_the_accepted_and_rejected_route_lists_do_not_overlap():
    accepted = set(LEDGER_DOC["accepted_routes"])
    rejected = set(LEDGER_DOC["rejected_routes"])
    assert accepted and rejected
    assert not (accepted & rejected), accepted & rejected


def test_the_current_state_is_that_nothing_is_verified():
    """Not a rule -- a snapshot, so that the first entry ever verified shows
    up in a diff of this file as well as of the ledger. Update the count in
    the same commit that verifies something."""
    verified = [f"{r['paper']}/{r['key']}" for r in ROWS
                if r["status"] == "VERIFIED"]
    assert verified == [], (
        f"{verified} are now VERIFIED. That may be entirely correct -- if so, "
        f"update this test's expectation in the same commit, and update "
        f"docs/CURRENT_PROGRAM_STATE.md's bibliography gate.")
