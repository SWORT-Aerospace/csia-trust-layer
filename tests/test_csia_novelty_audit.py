"""CSIA novelty audit (research/csia_novelty_audit/): structural honesty guards.

The package is a pre-result, snippet-level prior-art audit (stage 1) with a
second-stage verification layer (stage 2). These checks keep it honest as it is
edited:
  * all stage-1 and stage-2 deliverables exist;
  * the claim matrix has exactly the required columns, and uses only the
    permitted novelty statuses (never a bare "NOVEL");
  * every source id cited anywhere in the package is defined in the bibliography;
  * no document makes a categorical priority or absence claim;
  * the package stays independent of the XSYS-001 confirmatory data: it does
    not cite the campaign's data directory or any stage output;
  * stage 2: every claim-chart cell starts with YES / PARTIAL / NO / UNCLEAR,
    the chart covers the 27 frozen features, CSIA and 15-25 threats; the
    word "novel" never appears unqualified; every stage-2 source row carries
    a verification level; no element is claimed at N3 or N4; and the
    verification document ends with exactly one permitted verdict.

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
STAGE2 = ("CSIA_NOVELTY_VERIFICATION.md", "CSIA_CLOSEST_PRIOR_ART_CLAIM_CHART.csv",
          "CSIA_PATENT_PRIOR_ART_SCREEN.md", "CSIA_MINIMUM_NOVEL_CORE.md",
          "CSIA_PUBLICATION_CLAIM_BOUNDARY.md", "CSIA_IP_CANDIDATE_MAP.md",
          "CSIA_FULLTEXT_VERIFICATION_QUEUE.md", "XSYS_001_EXACT_PRIOR_ART.md")
ALL_FILES = FILES + STAGE2
FEATURES = [f"F{i:02d}" for i in range(1, 28)]
CELL_STATUS = ("YES", "PARTIAL", "NO", "UNCLEAR")
VERDICTS = ("CSIA_NOVELTY_CANDIDATE_SURVIVES", "CSIA_NOVELTY_REDUCED_TO_NARROW_COMBINATION",
            "CSIA_NOVELTY_NOT_ESTABLISHED")
COLUMNS = ["CLAIM_ID", "CSIA_CLAIM", "CLOSEST_PRIOR_ART", "YEAR", "DOMAIN", "WHAT_PRIOR_ART_ALREADY_DOES",
           "WHAT_CSIA_DOES", "MATERIAL_DIFFERENCE", "DIFFERENCE_SUBSTANTIVE_OR_TERMINOLOGICAL",
           "EVIDENCE_FOR_DIFFERENCE", "NOVELTY_STATUS", "CONFIDENCE", "WHAT_WOULD_KILL_NOVELTY",
           "REQUIRED_FOLLOWUP"]
STATUSES = {"KNOWN", "LIKELY_KNOWN", "CLOSE_PRIOR_ART", "POSSIBLY_DISTINCT", "APPARENTLY_NOVEL",
            "UNSUPPORTED_NOVELTY_CLAIM"}


def _texts(names=ALL_FILES):
    return {name: (D / name).read_text(encoding="utf-8") for name in names}


def _matrix():
    with open(D / "CSIA_PRIOR_ART_MATRIX.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_all_deliverables_exist():
    missing = [n for n in ALL_FILES if not (D / n).is_file()]
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
    assert "PRE-RESULT" in _texts()["CSIA_NOVELTY_VERIFICATION.md"]


def _chart():
    with open(D / "CSIA_CLOSEST_PRIOR_ART_CLAIM_CHART.csv", newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_claim_chart_shape_and_cell_statuses():
    rows = _chart()
    header, body = rows[0], rows[1:]
    assert header[:3] == ["FEATURE_ID", "FEATURE", "CSIA"]
    threats = header[3:]
    assert 15 <= len(threats) <= 25, len(threats)
    assert [h.split(" ")[0] for h in threats] == [f"T{i:02d}" for i in range(1, len(threats) + 1)]
    assert [r[0] for r in body] == FEATURES
    for r in body:
        assert len(r) == len(header), r[0]
        for col, cell in zip(header[2:], r[2:]):
            status = cell.split(" ")[0].rstrip(":")
            assert status in CELL_STATUS, (r[0], col, cell)
            # every cell carries an evidence reference, not a bare status
            assert len(cell) > len(status) + 5, (r[0], col, cell)
            # an unreadable source is never scored NO on the strength of a snippet
            if status == "NO":
                assert "V0" not in cell.split(":", 1)[0], (r[0], col, cell)


def test_bounded_runtime_authority_is_not_credited_to_csia():
    body = {r[0]: r for r in _chart()[1:]}
    assert body["F19"][2].startswith("NO"), body["F19"][2]
    assert body["F20"][2].startswith("NO"), body["F20"][2]


def test_word_novel_never_appears_unqualified_in_stage2():
    for name, text in _texts(STAGE2).items():
        low = text.lower()
        # the brief's own term, and quoted phrases being rejected, are allowed
        low = low.replace("minimum novel core", "")
        low = re.sub(r'"[^"\n]*"', "", low)
        hits = re.findall(r"\bnovel\b", low)
        assert not hits, (name, len(hits))


def test_no_stage2_element_claimed_at_n3_or_n4():
    text = _texts(("CSIA_NOVELTY_VERIFICATION.md",))["CSIA_NOVELTY_VERIFICATION.md"]
    table = text[text.index("## 17. Step 17"):text.index("## 18.")]
    statuses = re.findall(r"\| \*\*(N[0-4])\*\*", table)
    assert statuses, "no status table found"
    assert not {"N3", "N4"} & set(statuses), statuses


def test_stage2_sources_carry_a_verification_level():
    bib = _texts(("BIBLIOGRAPHY.md",))["BIBLIOGRAPHY.md"]
    stage2 = bib[bib.index("# Stage 2 additions"):]
    rows = re.findall(r"^\| (B1[1-4]\d|P2[4-9]) \|.*$", stage2, re.M)
    assert rows, "no stage-2 source rows"
    for line in re.findall(r"^\| (?:B1[1-4]\d|P2[4-9]) \|.*$", stage2, re.M):
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), line[:60]


def test_verification_ends_with_exactly_one_verdict():
    text = _texts(("CSIA_NOVELTY_VERIFICATION.md",))["CSIA_NOVELTY_VERIFICATION.md"]
    present = [v for v in VERDICTS if v in text]
    assert len(present) == 1, present
    last = [ln for ln in text.strip().splitlines() if ln.strip()][-1]
    assert present[0] in last, last
