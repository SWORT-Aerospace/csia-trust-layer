"""G02 kill test (research/g02_capability_margin/): honesty guards.

The package is a focused prior-art kill test, not a design. These checks keep
it honest as it is edited:
  * exactly the eleven deliverables exist;
  * atomic claims use N0-N3 only (N4 needs V3/V4 full text, and nothing was
    read at V3), N2/N3 never carry HIGH or MEDIUM confidence, and every row is
    filled;
  * usefulness scores are integers 0-5 that sum to the stated total, only
    non-N0 atomic gaps are scored, and every score >= 4 cites evidence;
  * every cited source id is defined in the register with a verification
    level;
  * no unqualified "novel" and no categorical priority claim;
  * exactly one decision token, on the last line of the deep audit, and
    RESEARCH_CONTINUE is only possible if an N2+ claim exists and the audit
    does not record condition 3 as failed.
Standard library only.
"""

import csv
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "research" / "g02_capability_margin"
FILES = ("G02_DEEP_AUDIT.md", "P0_SOURCE_ANALYSIS.md", "G02_CLAIM_MATRIX.csv", "G02_USEFULNESS_MATRIX.csv",
         "POWER_AVAILABLE_VS_REQUIRED.md", "CONTROL_AUTHORITY_PRIOR_ART.md", "TRAJECTORY_FEASIBILITY_PRIOR_ART.md",
         "EVTOL_CERTIFICATION_RELEVANCE.md", "REAL_WORLD_EVIDENCE.md", "FULLTEXT_VERIFICATION_QUEUE.md",
         "SEARCH_LOG.md")
DECISIONS = ("G02_KILL", "G02_ENGINEERING_ONLY", "G02_RESEARCH_CONTINUE")
USE = ("REAL_WORLD_VALUE", "COMMERCIAL_VALUE", "CERTIFICATION_VALUE", "RESEARCH_DEPTH", "SWORT_FIT",
       "IMPLEMENTATION_COST_5_IS_CHEAP", "EXPERIMENTAL_TESTABILITY", "PRIOR_ART_DEFENSIBILITY")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _rows(name):
    with open(D / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_exactly_the_eleven_deliverables_exist():
    assert sorted(p.name for p in D.iterdir()) == sorted(FILES)


def test_atomic_claims_are_bounded():
    rows = _rows("G02_CLAIM_MATRIX.csv")
    assert len(rows) >= 10
    for r in rows:
        assert r["ATOMIC_ID"].startswith("G02-"), r
        assert all(v.strip() for v in r.values()), r["ATOMIC_ID"]
        assert r["NOVELTY_STATUS"] in ("N0", "N1", "N2", "N3"), r["ATOMIC_ID"]
        if r["NOVELTY_STATUS"] in ("N2", "N3"):
            assert not r["CONFIDENCE"].upper().startswith(("HIGH", "MEDIUM")), r["ATOMIC_ID"]


def test_usefulness_scores_are_bounded_summed_evidenced_and_only_for_surviving_gaps():
    status = {r["ATOMIC_ID"]: r["NOVELTY_STATUS"] for r in _rows("G02_CLAIM_MATRIX.csv")}
    for r in _rows("G02_USEFULNESS_MATRIX.csv"):
        assert status[r["ATOMIC_ID"]] != "N0" and status[r["ATOMIC_ID"]] == r["NOVELTY_STATUS"], r["ATOMIC_ID"]
        vals = [int(r[c]) for c in USE]
        assert all(0 <= v <= 5 for v in vals) and sum(vals) == int(r["TOTAL_40"]), r["ATOMIC_ID"]
        for c, v in zip(USE, vals):
            if v >= 4:
                key = c.split("_")[0]
                assert re.search(rf"{key}=[^;]*K\d{{3}}", r["EVIDENCE_FOR_SCORES_GE4"]), (r["ATOMIC_ID"], c)


def test_every_cited_source_is_defined_with_a_level():
    reg = _text("G02_DEEP_AUDIT.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (K\d{3}) \|.*$", reg, re.M)}
    for rid, line in rows.items():
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), rid
    cited = set()
    for name in FILES:
        cited |= set(re.findall(r"\b(K\d{3})\b", _text(name)))
    assert cited and not (cited - set(rows)), sorted(cited - set(rows))


def test_no_unqualified_novelty_or_priority_language():
    banned = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
              "never been studied", "has never been", "no prior art exists")
    for name in FILES:
        low = _text(name).lower()
        assert not [b for b in banned if b in low], name
        stripped = re.sub(r"`[^`\n]*`", "", low)
        stripped = re.sub(r'"[^"\n]*"', "", stripped)
        assert not re.search(r"\bnovel\b", stripped), name


def test_single_decision_consistent_with_the_continue_conditions():
    present = {d for name in FILES for d in DECISIONS if d in _text(name)}
    assert len(present) == 1, present
    decision = present.pop()
    audit = _text("G02_DEEP_AUDIT.md")
    last = [ln for ln in audit.strip().splitlines() if ln.strip()][-1]
    assert decision in last
    has_n2 = any(r["NOVELTY_STATUS"] in ("N2", "N3") for r in _rows("G02_CLAIM_MATRIX.csv"))
    cond3_failed = re.search(r"^\| 3 \| not simply integration[^\n]*\*\*NO\*\*", audit, re.M) is not None
    if decision == "G02_RESEARCH_CONTINUE":
        assert has_n2 and not cond3_failed
    if cond3_failed:
        assert decision != "G02_RESEARCH_CONTINUE"
