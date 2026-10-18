"""The E1 claim table regenerates from its artifacts, and its rules hold.

A claim table that is edited by hand drifts away from the measurements it
claims to summarise, and nothing goes red. So the numeric fields are generated
(`tools/csia_experiment/build_e1_claim_table.py`) and this file regenerates and
compares.

It also checks the RULES the table exists to enforce, not just that it parses:

  * every required distinction is present with the right status;
  * no row's allowed_wording contains a word the programme forbids;
  * every REPEATED row names an n, and every non-REPEATED row names what did
    not reproduce.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.csia_experiment.build_e1_claim_table import (   # noqa: E402
    COLUMNS, build)

TABLE = os.path.join(ROOT, "research", "physical_validation",
                     "E1_FINAL_CLAIM_TABLE.csv")

#: The distinctions the programme requires the table to make, and the status
#: each must carry. A table that quietly downgrades REFUTED_SUPERSEDED to
#: something softer would pass a parse check and fail this one.
REQUIRED = {
    "E1-STRUCT-A": "REPEATED",
    "E1-STRUCT-P": "REPEATED",
    "E1-FIXLOSS-A": "REPEATED",
    "E1-FIXLOSS-P": "REPEATED",
    "E1-GATE-A": "REPEATED",
    "E1-GATE-P": "REPEATED",
    "E1-LEADER-A": "REPEATED",
    "E1-LEADER-P": "REPEATED",
    "E1-TRUSTSIGN-A": "REPEATED",
    "E1-TRUSTSIGN-P": "REPEATED",
    "E1-TRUSTCAUSE": "REFUTED_SUPERSEDED",
    "E1-TRUSTVAL-A": "NOT_REPEATABLE",
    "E1-TRUSTVAL-P": "NOT_REPEATABLE",
    "E1-TIMING": "CONFIGURATION_DEPENDENT",
    "E1-WATCHDOG": "MEASURED",
    "E1-FL019": "UNRESOLVED",
}

#: Words that may not appear in what the table SAYS IS ALLOWED. They may
#: appear in forbidden_wording -- that is what that column is for.
#:
#: THIS GUARD FIRED ON ITS OWN AUTHOR'S FIRST DRAFT: E1-GATE's allowed_wording
#: read "for PX4, always with the 1-of-4 qualification", where "always" was
#: about a citation convention and not a universality claim. A word scan
#: cannot tell those apart, and the right fix was to reword rather than to
#: carve an exception -- an exception is how the next real one gets through.
#: That is the sixth guard in this repository to fire on its own
#: documentation; the earlier five are recorded in
#: tests/test_scalar_rederivation.py.
FORBIDDEN_IN_ALLOWED = ("always", "in general", "population probability",
                        "prevalence", "universal", "proves")


@pytest.fixture(scope="module")
def rows():
    if not os.path.exists(TABLE):
        pytest.skip("E1_FINAL_CLAIM_TABLE.csv not present")
    with open(TABLE, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_the_table_regenerates_byte_identically(rows):
    """The committed table is what the generator produces from the artifacts.

    If an artifact moved and the table did not, this is where it shows.
    """
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in build():
        w.writerow(r)
    with open(TABLE, encoding="utf-8") as fh:
        assert fh.read() == buf.getvalue(), (
            "E1_FINAL_CLAIM_TABLE.csv differs from what the generator "
            "produces. Re-run tools/csia_experiment/build_e1_claim_table.py "
            "--regenerate and explain the diff.")


def test_every_required_distinction_is_present_with_its_status(rows):
    got = {r["claim_id"]: r["status"] for r in rows}
    missing = sorted(set(REQUIRED) - set(got))
    assert not missing, f"claims missing from the table: {missing}"
    wrong = {k: (REQUIRED[k], got[k]) for k in REQUIRED if got[k] != REQUIRED[k]}
    assert not wrong, f"status changed, expected vs got: {wrong}"


def test_the_columns_are_the_ones_the_programme_asked_for(rows):
    assert list(rows[0]) == COLUMNS


def test_no_allowed_wording_contains_a_forbidden_word(rows):
    bad = []
    for r in rows:
        low = r["allowed_wording"].lower()
        for word in FORBIDDEN_IN_ALLOWED:
            # `prevalence` legitimately appears in forbidden_wording; this
            # checks only what the table says MAY be written.
            if re.search(rf"\b{re.escape(word)}\b", low):
                bad.append((r["claim_id"], word))
    assert not bad, f"forbidden words inside allowed_wording: {bad}"


def test_every_row_names_an_n_or_says_why_not(rows):
    for r in rows:
        for field in ("original_n", "repeat_n"):
            assert r[field].strip(), f"{r['claim_id']}: {field} is empty"


def test_every_non_repeated_row_names_what_did_not_reproduce(rows):
    for r in rows:
        if r["status"] == "REPEATED":
            continue
        text = r["not_reproduced_quantity"].strip()
        assert text and text != "none", (
            f"{r['claim_id']} is {r['status']} but names nothing that failed "
            f"to reproduce. A non-REPEATED status with no failed quantity is "
            f"a status nobody can check")


def test_every_row_cites_an_artifact(rows):
    for r in rows:
        assert r["artifact"].strip(), f"{r['claim_id']} cites no artifact"


def test_the_refuted_causal_claim_forbids_its_own_original_wording(rows):
    """The row exists to stop a specific sentence coming back."""
    row = next(r for r in rows if r["claim_id"] == "E1-TRUSTCAUSE")
    forbidden = row["forbidden_wording"].lower()
    assert "source of disagreement" in forbidden
    assert "causes the rise" in forbidden or "fault causes" in forbidden


def test_the_two_not_repeatable_rows_name_the_watchdog(rows):
    """NOT_REPEATABLE without a named cause is just an unexplained number."""
    for cid in ("E1-TRUSTVAL-A", "E1-TRUSTVAL-P"):
        row = next(r for r in rows if r["claim_id"] == cid)
        dep = row["configuration_dependence"].lower()
        assert "0.5" in dep and "1.0" in dep, (
            f"{cid} does not name the two watchdog values")
        assert "fl-017" in dep, f"{cid} does not cite FL-017"
