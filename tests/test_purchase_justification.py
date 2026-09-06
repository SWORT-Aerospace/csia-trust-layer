"""The hardware purchase list, and the CSV defect that has now happened twice.

WHY THIS TEST EXISTS
--------------------
`papers/PRIOR_ART_MATRIX.csv` was silently corrupted earlier in this program:
an edit introduced a comma into an unquoted field, every subsequent column
shifted by one, `status` became prose, and THE WHOLE TEST SUITE STILL PASSED.
Nothing read the file positionally, so nothing could notice.

Writing `hardware/validation_rig/PURCHASE_JUSTIFICATION.csv` reproduced the
identical defect on the first attempt -- "Companion computer (single-board,
USB/serial + Ethernet)" left unquoted -- and it was caught only because the
file was checked immediately after writing.

Twice is a pattern, so the check is a test rather than a habit.

WHAT IS CHECKED, AND WHY EACH ONE
---------------------------------
  1. every row has exactly the header's field count -- the ragged-row check
     that would have caught both defects;
  2. no field is empty -- a blank `claim_it_does_not_license` is how an
     unbounded claim gets in;
  3. `tier` is drawn from the evidence-tier vocabulary, read from
     PAPER_IMPACT_LEDGER.yaml rather than repeated here;
  4. NO ROW CARRIES AN INVENTED PRICE. This environment cannot reach a vendor,
     so a dollar figure in this file would be fabricated. UNPRICED is the
     honest value and the cost_note says why.
"""

from __future__ import annotations

import csv
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "hardware", "validation_rig",
                        "PURCHASE_JUSTIFICATION.csv")
LEDGER = os.path.join(ROOT, "research", "physical_validation",
                      "PAPER_IMPACT_LEDGER.yaml")

EXPECTED_FIELDS = [
    "tier", "item", "quantity", "purpose", "claim_it_licenses",
    "claim_it_does_not_license", "blocked_without_it", "unit_cost_usd",
    "cost_note",
]


def _rows():
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_the_header_is_what_the_readers_expect():
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == EXPECTED_FIELDS, (
        f"header is {header}. Renaming a column silently changes what every "
        f"consumer reads positionally -- which is how PRIOR_ART_MATRIX.csv "
        f"was corrupted.")


def test_no_row_is_ragged():
    """The check that would have caught the defect twice.

    csv.DictReader gives a short row fewer keys and a long row a `None` key,
    so both directions are visible here and invisible to anything that reads
    the file by column name only.
    """
    ragged = []
    for row in _rows():
        if None in row or len(row) != len(EXPECTED_FIELDS):
            ragged.append(f"{row.get('item')!r}: {len(row)} fields, "
                          f"expected {len(EXPECTED_FIELDS)}")
    assert not ragged, (
        f"ragged rows: {ragged}. An unquoted comma inside a field shifts "
        f"every column after it and reads as valid CSV.")


def test_no_field_is_blank():
    blank = [f"{r['item']!r}.{k}" for r in _rows()
             for k, v in r.items() if not (v or "").strip()]
    assert not blank, (
        f"empty fields: {blank}. A blank claim_it_does_not_license is how an "
        f"unbounded claim gets into a purchase justification.")


def test_every_tier_is_a_real_evidence_tier():
    with open(LEDGER, encoding="utf-8") as fh:
        tiers = set(yaml.safe_load(fh)["evidence_tiers"])
    unknown = sorted({r["tier"] for r in _rows()} - tiers)
    assert not unknown, (
        f"rows claim evidence tiers {unknown}, which "
        f"PAPER_IMPACT_LEDGER.yaml does not define ({sorted(tiers)}). A "
        f"purchase justified against a tier nobody defined justifies nothing.")


def test_no_row_carries_a_price_this_environment_could_not_check():
    """A fabricated dollar figure is a fabricated number like any other.

    Vendor sites are unreachable here -- the agent proxy answers 403 to
    CONNECT -- so any price in this file would have been invented. UNPRICED
    with a stated reason is the honest value, and docs/HARDWARE_BOM.md already
    holds planning estimates that say on their face to verify at purchase.
    """
    priced = [(r["item"], r["unit_cost_usd"]) for r in _rows()
              if re.search(r"\d", r["unit_cost_usd"])]
    assert not priced, (
        f"these rows carry a numeric price: {priced}. If prices were obtained "
        f"from a real vendor, cite the source in cost_note and update this "
        f"test deliberately -- do not delete it.")

    unexplained = [r["item"] for r in _rows()
                   if r["unit_cost_usd"] == "UNPRICED"
                   and len(r["cost_note"]) < 10]
    assert not unexplained, (
        f"UNPRICED without a reason: {unexplained}")


def test_the_two_hardest_constraints_are_stated_in_the_file():
    """Receive-only GNSS, and props off. Both are program rules, not defaults.

    A purchase list is where scope creep enters a project: the row that says
    'GNSS receiver' is one word away from the row that says 'GNSS simulator',
    and one of those is out of scope by instruction.
    """
    text = open(CSV_PATH, encoding="utf-8").read()
    assert "RECEIVE-ONLY" in text and "No GPS spoofing transmitter" in text, \
        "the GNSS row must state that no transmitter is in scope"
    assert "Props are removed" in text, \
        "the propulsion row must state the props-off rule"
    for forbidden in ("jammer", "spoofing transmitter is required",
                      "counter-UAS", "targeting"):
        assert forbidden not in text.lower().replace(
            "no gps spoofing transmitter", ""), \
            f"{forbidden!r} appears in the purchase list"


def test_no_field_back_references_another_row():
    """A CSV is read row-wise. "As above" depends on row order.

    Three fields on the ESC row said "As above." and the cost_note on eight
    rows said "as above" -- both were caught, the second by
    test_no_row_carries_a_price_this_environment_could_not_check firing on a
    reason shorter than ten characters. A tool that filters this file to one
    tier, or sorts it, silently turns those into references to nothing.
    """
    offenders = []
    for row in _rows():
        for key, value in row.items():
            if re.match(r"^\s*(as|see)\s+(above|below|previous|row)",
                        (value or ""), re.I):
                offenders.append(f"{row['item']!r}.{key} = {value!r}")
    assert not offenders, (
        f"row-order-dependent fields: {offenders}. Every row must stand "
        f"alone -- repeat the text rather than pointing at a neighbour.")
