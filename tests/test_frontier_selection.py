"""Guards for the Stage R0.2 frontier-selection package.

NOTHING HERE SCORES A RESULT. This stage produced no experimental result to
score. These tests protect the properties that would make the package
dishonest if they broke:

  * no implementation happened (item 36) and the frozen core is untouched
  * every source is recorded as unread (SEARCH_PROTOCOL section 0)
  * no candidate is awarded novelty on the strength of a missing title
  * the killed directions listed in item 0 stay killed
  * the weighted frontier score is arithmetic, not narrative
  * the Stage-0 prompt has not been executed
"""

from __future__ import annotations

import csv
import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "frontier_selection")

REQUIRED = [
    "README.md", "SEARCH_PROTOCOL.md", "LITERATURE_FRONTIER_MAP.md",
    "PRIMARY_SOURCE_INDEX.csv", "OPEN_ASSUMPTION_LEDGER.csv",
    "CANDIDATE_LONG_LIST.md", "CANDIDATE_SCORECARD.csv",
    "REJECTED_CANDIDATES.md", "TOP_THREE.md", "SELECTED_CANDIDATE.md",
    "SELECTED_CANDIDATE_FORMAL_TARGET.md",
    "SELECTED_CANDIDATE_STAGE0_DESIGN.md",
    "SELECTED_CANDIDATE_STAGE0_PROMPT.md",
    "CLAIM_LEDGER.json", "CHATGPT_REVIEW_REPORT.md",
]

# item 25
WEIGHTS = {"NOVELTY_SURVIVAL": 0.25, "FORMAL_DEPTH": 0.15,
           "FALSIFIABILITY": 0.15, "EXPERIMENTAL_CLARITY": 0.10,
           "HIL_FEASIBILITY": 0.10, "GENERALITY": 0.10,
           "DISSERTATION_VALUE": 0.10, "COMMERCIAL_VALUE": 0.05,
           "PRIOR_ART_RISK": -0.15}

# item 42
VOCAB = {"KNOWN/SUBSUMED", "PROVED - NOVELTY NOT ESTABLISHED",
         "PROVED - POSSIBLE NOVEL CONTRIBUTION", "EMPIRICAL ONLY",
         "PROVISIONAL", "CONJECTURE", "REFUTED"}


def _csv(name):
    p = os.path.join(PKG, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not built")
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _json(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as fh:
        return json.load(fh)


def _md(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------- item 36: no implementation
def test_the_package_contains_no_code_at_all():
    """Item 36 forbids implementing anything in this stage. The cheapest way
    to prove that is that the package holds no executable file."""
    bad = []
    for dirpath, _dirs, files in os.walk(PKG):
        for fn in files:
            if fn.endswith((".py", ".sh", ".c", ".cpp", ".ipynb")):
                bad.append(os.path.join(dirpath, fn))
    assert not bad, bad


def test_the_package_contains_no_production_csia_file():
    for dirpath, _dirs, files in os.walk(PKG):
        for fn in files:
            p = os.path.join(dirpath, fn).replace(os.sep, "/")
            assert "/csia/" not in p, p
    assert os.path.exists(os.path.join(ROOT, "tests", "test_v1_frozen.py"))


def test_the_stage_zero_prompt_has_not_been_executed():
    """Item 43: DO NOT EXECUTE IT. The prompt's own output directory must not
    exist yet."""
    assert not os.path.exists(
        os.path.join(ROOT, "research", "evidence_independence")), (
        "the Stage-0 prompt appears to have been executed in the stage that "
        "wrote it")
    t = _md("SELECTED_CANDIDATE_STAGE0_PROMPT.md")
    assert "DO NOT EXECUTE" in t


def test_every_required_artifact_exists():
    missing = [f for f in REQUIRED if not os.path.exists(os.path.join(PKG, f))]
    assert not missing, missing


# ------------------------------------------- the full-text limitation is stated
def test_no_source_is_recorded_as_read_in_full():
    rows = _csv("PRIMARY_SOURCE_INDEX.csv")
    assert rows
    for r in rows:
        assert r["full_text_read"] == "NO", r["citation_id"]
        assert r["source_depth"] == "SNIPPET_ONLY", r["citation_id"]


def test_the_full_text_block_is_stated_before_any_conclusion():
    """Item 3's fallback is the load-bearing caveat of this stage. It must be
    impossible to read the package without meeting it."""
    proto = _md("SEARCH_PROTOCOL.md")
    assert "PARTIAL_SOURCE_ONLY" in proto
    assert "Zero full texts were read" in proto
    readme = _md("README.md")
    assert "PARTIAL_SOURCE_ONLY" in readme
    report = _md("CHATGPT_REVIEW_REPORT.md")
    # the executive verdict, not a footnote
    head = report.split("## 2.")[0]
    assert "PARTIAL_SOURCE_ONLY" in head or "full text" in head.lower()


def test_no_page_or_section_reference_is_invented():
    """Item 7 asks for exact section/page references when possible. It was
    never possible; the ledger must say so rather than guess."""
    rows = _csv("OPEN_ASSUMPTION_LEDGER.csv")
    assert rows
    for r in rows:
        assert r["section_or_page"] == "NOT_AVAILABLE_SNIPPET_ONLY", r


# ------------------------------------------------------- item 42: no free novelty
def test_no_candidate_is_awarded_novelty():
    led = _json("CLAIM_LEDGER.json")
    assert led["novelty"] == "NOT ESTABLISHED"
    for c in led["claims"]:
        assert c["status"] in VOCAB, (c["id"], c["status"])
        assert c["status"] != "PROVED - POSSIBLE NOVEL CONTRIBUTION", c["id"]


def test_every_claim_carries_its_limits():
    led = _json("CLAIM_LEDGER.json")
    for c in led["claims"]:
        for k in ("statement", "evidence", "status", "assumptions",
                  "strongest_allowed_wording", "forbidden_stronger_wording",
                  "next_falsification_test"):
            assert c.get(k), (c["id"], k)


def test_refuted_predictions_are_kept():
    led = _json("CLAIM_LEDGER.json")
    assert led["refuted_predictions"]
    for p in led["refuted_predictions"]:
        assert p["kept"] is True, p["id"]
        assert p.get("outcome"), p["id"]


def test_the_absence_claim_names_its_own_limitations():
    """Item 3 forbids using snippet absence as evidence of novelty. The claim
    that records an absence must carry the reasons it proves nothing."""
    led = _json("CLAIM_LEDGER.json")
    f7 = [c for c in led["claims"] if c["id"] == "F7"]
    assert f7, "the absence claim has been removed"
    a = f7[0]["assumptions"].upper()
    for token in ("SINGLE ENGINE", "SNIPPET", "PATENT", "STANDARD"):
        assert token in a, token
    assert "This is novel" in f7[0]["forbidden_stronger_wording"]


# ------------------------------------------------ item 0: killed stays killed
def test_the_killed_directions_are_preserved_and_not_resurrected():
    led = _json("CLAIM_LEDGER.json")
    p = led["preserved_prior_verdicts"]
    assert p["generic semantic-equivalence checking"] == "KNOWN/SUBSUMED"
    assert p["dual operational/diagnostic admissibility"] == "KNOWN/SUBSUMED"
    assert "HEURISTICS_SUFFICIENT" in p["AI-assisted contract synthesis"]
    assert "ENGINEERING_INCONSISTENCY_ONLY" in p["conflicting semantic authorities"]
    assert p["unrestricted self-occlusion theorem"].startswith("KILLED")


def test_the_self_occlusion_lookalike_is_disqualified_not_selected():
    """Candidate K outscored two finalists and is excluded on rule. If a later
    edit promotes it, item 0 has been broken."""
    rows = {r["candidate_id"]: r for r in _csv("CANDIDATE_SCORECARD.csv")}
    assert rows["K"]["status"].startswith("DISQUALIFIED"), rows["K"]
    rej = _md("REJECTED_CANDIDATES.md")
    assert "4.200" in rej, "K's score must stay published"


# --------------------------------------------------- the scorecard is arithmetic
def test_the_weighted_frontier_score_is_recomputable():
    rows = _csv("CANDIDATE_SCORECARD.csv")
    assert len(rows) == 12, "item 9 caps the candidate set at 12"
    for r in rows:
        want = sum(w * int(r[k]) for k, w in WEIGHTS.items())
        got = float(r["WEIGHTED_FRONTIER_SCORE"])
        assert abs(want - got) < 1e-9, (r["candidate_id"], want, got)


def test_no_candidate_claims_high_novelty_survival_without_full_text():
    """Novelty survival cannot be estimated from snippets. The cap is the
    honest consequence and must not drift upward."""
    for r in _csv("CANDIDATE_SCORECARD.csv"):
        assert int(r["NOVELTY_SURVIVAL"]) <= 5, r["candidate_id"]


def test_the_selected_candidate_is_the_highest_scoring_eligible_one():
    rows = _csv("CANDIDATE_SCORECARD.csv")
    sel = [r for r in rows if r["status"] == "SELECTED"]
    assert len(sel) == 1, "item 32: recommend exactly ONE candidate"
    eligible = [r for r in rows
                if not r["status"].startswith("DISQUALIFIED")]
    best = max(float(r["WEIGHTED_FRONTIER_SCORE"]) for r in eligible)
    assert float(sel[0]["WEIGHTED_FRONTIER_SCORE"]) == best


def test_exactly_three_finalists():
    rows = _csv("CANDIDATE_SCORECARD.csv")
    finalists = [r for r in rows
                 if r["status"] in ("SELECTED", "TOP_THREE_2", "TOP_THREE_3")]
    assert len(finalists) == 3, [r["candidate_id"] for r in finalists]


# ------------------------------------------------- item 31: source coverage
def test_each_finalist_has_five_close_and_two_hostile_sources():
    score = {r["candidate_id"]: r["status"] for r in _csv("CANDIDATE_SCORECARD.csv")}
    finalists = [c for c, s in score.items()
                 if s in ("SELECTED", "TOP_THREE_2", "TOP_THREE_3")]
    rows = _csv("PRIMARY_SOURCE_INDEX.csv")
    for cid in finalists:
        close = hostile = 0
        for r in rows:
            for tok in r["candidate_relevance"].split(";"):
                tok = tok.strip()
                if tok == f"{cid}:CLOSE":
                    close += 1
                if tok in (f"{cid}:HOSTILE", f"{cid}:FOUNDATIONAL"):
                    hostile += 1
        assert close >= 5, (cid, "CLOSE", close)
        assert hostile >= 2, (cid, "HOSTILE/FOUNDATIONAL", hostile)


def test_the_selected_candidate_names_its_most_dangerous_source():
    t = _md("SELECTED_CANDIDATE.md")
    assert "S063" in t
    assert "ARP4761" in t
    gate = _md("SELECTED_CANDIDATE_STAGE0_PROMPT.md")
    assert "ARP4761" in gate
    assert "STOP" in gate


# ------------------------------------------------------------ honesty guards
def test_the_corollary_is_conceded_not_dressed_up():
    """Reviewer D's objection is correct and must stay conceded."""
    t = _md("SELECTED_CANDIDATE_FORMAL_TARGET.md")
    assert "corollary" in t.lower()
    assert "Menger" in t
    assert "not a contribution" in t.lower()


def test_no_physical_hil_is_claimed():
    # \bhil\b, not a substring search -- "while" contains "hil"
    hil = re.compile(r"\bhil\b")
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        t = _md(fn).lower()
        if not hil.search(t) and "hardware" not in t:
            continue
        assert ("no hardware" in t or "not executed" in t
                or "no physical hil" in t or "design only" in t
                or "was executed in this stage" in t), fn


def test_no_novelty_wording_anywhere_in_the_package():
    banned = ("first-ever", "unprecedented", "new paradigm", "breakthrough",
              "we prove a new theorem")
    denials = ("not ", "no ", "none", "never", "forbidden", "subsumed",
               "known/", "refuted", "cannot", "does not", "corollary",
               "provisional")
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        raw = _md(fn).lower()
        text = re.sub(r"[.,;:!?)\]]", " ",
                      raw.replace("*", "").replace("`", ""))
        lines = text.splitlines()
        for w in banned:
            if w not in text:
                continue
            for i, line in enumerate(lines):
                if w not in line or line.lstrip().startswith("#"):
                    continue
                window = " ".join(lines[i:i + 3])
                assert any(k in window for k in denials), (fn, w, line[:120])
