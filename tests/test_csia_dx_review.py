"""CSIA-DX review (research/csia_dx/): structural honesty guards.

The package is a problem-formalization and adversarial novelty review, not an
implementation. These checks keep it honest as it is edited:
  * every deliverable exists;
  * the claim table uses only N0-N4, never N4, and never HIGH confidence on
    an N2/N3 status; the review's summary table agrees with it;
  * every cited source id is defined in the bibliography, with a
    verification level;
  * the word "novel" never appears unqualified, and no document makes a
    categorical priority claim;
  * the first experiment is marked as not run;
  * the review ends with exactly one permitted decision.
Standard library only.
"""

import csv
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "research" / "csia_dx"
FILES = ("CSIA_DX_REVIEW.md", "CSIA_DX_CLAIMS.csv", "CSIA_DX_TOY_EXAMPLE_AND_FEASIBILITY.md",
         "CSIA_DX_USEFULNESS_SCORECARD.md", "CSIA_DX_FIRST_EXPERIMENT.md", "BIBLIOGRAPHY.md", "SEARCH_LOG.md")
DECISIONS = ("CSIA_DX_GO", "CSIA_DX_PIVOT", "CSIA_DX_KILL")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _claims():
    with open(D / "CSIA_DX_CLAIMS.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_deliverables_exist():
    assert not [n for n in FILES if not (D / n).is_file()]


def test_claim_statuses_are_bounded():
    rows = _claims()
    assert [r["CLAIM_ID"] for r in rows] == [f"DX-C{i}" for i in range(1, len(rows) + 1)] and len(rows) >= 10
    for r in rows:
        assert r["NOVELTY_STATUS"] in ("N0", "N1", "N2", "N3"), r["CLAIM_ID"]   # N4 needs V3/V4 full text
        assert all(v.strip() for v in r.values()), r["CLAIM_ID"]
        if r["NOVELTY_STATUS"] in ("N2", "N3"):
            assert not r["CONFIDENCE"].upper().startswith(("HIGH", "MEDIUM")), r["CLAIM_ID"]


def test_review_summary_matches_claim_table():
    review = _text("CSIA_DX_REVIEW.md")
    for r in _claims():
        m = re.search(rf"^\| {re.escape(r['CLAIM_ID'])} \|[^\n]*\*\*(N[0-4])\*\*", review, re.M)
        assert m and m.group(1) == r["NOVELTY_STATUS"], r["CLAIM_ID"]


def test_every_cited_source_is_defined_with_a_level():
    bib = _text("BIBLIOGRAPHY.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (D\d{2}) \|.*$", bib, re.M)}
    for rid, line in rows.items():
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), rid
    cited = set()
    for name in FILES:
        if name != "BIBLIOGRAPHY.md":
            cited |= set(re.findall(r"\b(D\d{2})\b", _text(name)))
    assert cited and not (cited - set(rows)), sorted(cited - set(rows))


def test_no_unqualified_novelty_or_priority_language():
    banned = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
              "never been studied", "has never been", "no prior art exists")
    for name in FILES:
        low = _text(name).lower()
        assert not [b for b in banned if b in low], name
        stripped = re.sub(r'"[^"\n]*"', "", low)
        assert not re.search(r"\bnovel\b", stripped), name


def test_first_experiment_is_design_only():
    t = _text("CSIA_DX_FIRST_EXPERIMENT.md")
    assert "NOT RUN" in t and "design only" in t.lower()


def test_review_ends_with_exactly_one_decision():
    t = _text("CSIA_DX_REVIEW.md")
    present = [d for d in DECISIONS if d in t]
    assert len(present) == 1, present
    last = [ln for ln in t.strip().splitlines() if ln.strip()][-1]
    assert present[0] in last
