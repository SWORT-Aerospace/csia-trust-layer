"""CSIA novelty audit (research/csia_novelty_audit/): structural honesty guards.

The package is a pre-result, snippet-level prior-art audit. These checks keep
it honest as it is edited:
  * all nine deliverables exist;
  * the claim matrix has exactly the required columns, and uses only the
    permitted novelty statuses (never a bare "NOVEL");
  * every source id cited anywhere in the package is defined in the bibliography;
  * no document makes a categorical priority or absence claim;
  * the package stays independent of the XSYS-001 confirmatory data: it does
    not cite the campaign's data directory or any stage output.

Standard library only.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "research" / "csia_novelty_audit"
FILES = ("CSIA_NOVELTY_AUDIT.md", "CSIA_PRIOR_ART_MATRIX.csv", "CSIA_CLOSEST_SYSTEMS.md",
         "CSIA_TERMINOLOGY_CROSSWALK.md", "XSYS_001_NOVELTY_AUDIT.md", "CSIA_NOVELTY_RED_TEAM.md",
         "CSIA_CANDIDATE_CONTRIBUTIONS.md", "BIBLIOGRAPHY.md", "NOVELTY_SEARCH_LOG.md")
COLUMNS = ["CLAIM_ID", "CSIA_CLAIM", "CLOSEST_PRIOR_ART", "YEAR", "DOMAIN", "WHAT_PRIOR_ART_ALREADY_DOES",
           "WHAT_CSIA_DOES", "MATERIAL_DIFFERENCE", "DIFFERENCE_SUBSTANTIVE_OR_TERMINOLOGICAL",
           "EVIDENCE_FOR_DIFFERENCE", "NOVELTY_STATUS", "CONFIDENCE", "WHAT_WOULD_KILL_NOVELTY",
           "REQUIRED_FOLLOWUP"]
STATUSES = {"KNOWN", "LIKELY_KNOWN", "CLOSE_PRIOR_ART", "POSSIBLY_DISTINCT", "APPARENTLY_NOVEL",
            "UNSUPPORTED_NOVELTY_CLAIM"}


def _texts():
    return {name: (D / name).read_text(encoding="utf-8") for name in FILES}


def _matrix():
    with open(D / "CSIA_PRIOR_ART_MATRIX.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_all_deliverables_exist():
    missing = [n for n in FILES if not (D / n).is_file()]
    assert not missing, missing


def test_matrix_columns_and_statuses():
    with open(D / "CSIA_PRIOR_ART_MATRIX.csv", newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == COLUMNS
    rows = _matrix()
    ids = [r["CLAIM_ID"] for r in rows]
    assert ids == [f"C{i}" for i in range(1, len(ids) + 1)] and len(ids) >= 12
    for r in rows:
        assert r["NOVELTY_STATUS"] in STATUSES, (r["CLAIM_ID"], r["NOVELTY_STATUS"])
        assert all(r[c].strip() for c in COLUMNS), r["CLAIM_ID"]


def test_no_status_above_apparently_novel_and_known_claims_stay_known():
    rows = {r["CLAIM_ID"]: r for r in _matrix()}
    # the brief's claims the literature settles outright
    for cid in ("C1", "C2", "C3", "C5", "C8", "C11"):
        assert rows[cid]["NOVELTY_STATUS"] == "KNOWN", cid
    # the bounded-runtime-assurance capability does not exist in CSIA
    assert rows["C19"]["NOVELTY_STATUS"] == "UNSUPPORTED_NOVELTY_CLAIM"
    # a novelty status never carries HIGH confidence while the evidence is snippet-level
    for r in rows.values():
        if r["NOVELTY_STATUS"] in ("APPARENTLY_NOVEL", "POSSIBLY_DISTINCT"):
            assert not r["CONFIDENCE"].upper().startswith(("HIGH", "MEDIUM-HIGH")), r["CLAIM_ID"]


def test_every_cited_source_is_in_the_bibliography():
    texts = _texts()
    defined = set(re.findall(r"^\| (B\d{2,3}|P\d{2}) \|", texts["BIBLIOGRAPHY.md"], re.M))
    cited = set()
    for name, text in texts.items():
        if name != "BIBLIOGRAPHY.md":
            cited |= set(re.findall(r"\b(B\d{2,3}|P\d{2})\b", text))
    assert cited, "no source ids cited"
    assert not (cited - defined), sorted(cited - defined)


def test_no_categorical_priority_or_absence_claims():
    banned = ("no prior work exists", "we are the first", "is the first to", "first ever",
              "no one has", "never been studied", "has never been")
    for name, text in _texts().items():
        low = text.lower()
        hits = [b for b in banned if b in low]
        assert not hits, (name, hits)


def test_package_is_independent_of_confirmatory_data():
    forbidden = ("research/xsys_001_confirmatory_campaign", "xsys_001_confirmatory_raw_artifacts",
                 "STAGE1.json", "RESULTS.json", "KEY.json", "CAMPAIGN_COMPLETION", "STAGE0_REPORT")
    for name, text in _texts().items():
        hits = [f for f in forbidden if f in text]
        assert not hits, (name, hits)
    assert "PRE-RESULT" in _texts()["CSIA_NOVELTY_AUDIT.md"]
