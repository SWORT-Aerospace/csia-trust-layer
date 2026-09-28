"""Closed-loop evidence gap search (research/closed_loop_evidence_gap/): honesty guards.

The package is a problem-first gap search, not a design. These checks keep it
honest as it is edited:
  * exactly the twelve deliverables exist;
  * at least eight candidate problems, numbered in order, each fully filled,
    stated without CSIA, with one of the four brief classifications, agreeing
    with the kill matrix;
  * POTENTIAL_GAP only when all five survival conditions are YES;
  * killed candidates carry no scores; the others carry integer scores 0-5
    that sum to the stated total, and every score >= 4 cites evidence from
    the source register;
  * novelty statuses stay within N0-N2 (nothing is promoted above N2 on
    snippets), and N2 never carries HIGH or MEDIUM confidence;
  * every cited source id is defined, with a verification level;
  * no unqualified "novel" and no categorical priority claim;
  * exactly one decision token, on the last line of TOP_GAPS.md, and it is
    the one the stated decision rule yields from the candidate table.
Standard library only.
"""

import csv
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "research" / "closed_loop_evidence_gap"
FILES = ("PROBLEM_LANDSCAPE.md", "CANDIDATE_PROBLEMS.csv", "PRIOR_ART_KILL_MATRIX.csv",
         "FEEDBACK_MASKING_AUDIT.md", "ACTION_CONDITIONED_EVIDENCE.md", "ESTIMATOR_INTERVENTION_AUDIT.md",
         "PLANNER_DIAGNOSABILITY_TRADEOFF.md", "EVIDENCE_PROVENANCE_AUDIT.md", "REAL_WORLD_CASES.md",
         "TOP_GAPS.md", "FULLTEXT_VERIFICATION_QUEUE.md", "SEARCH_LOG.md")
DECISIONS = ("CLOSED_LOOP_EVIDENCE_NO_GAP", "CLOSED_LOOP_EVIDENCE_ENGINEERING_ONLY",
             "CLOSED_LOOP_EVIDENCE_GAP_FOUND")
CLASSES = ("KILLED", "ENGINEERING_ONLY", "OPEN_BUT_CROWDED", "POTENTIAL_GAP")
SURVIVAL = ("S1_USEFUL", "S2_CURRENT_SYSTEMS_FAIL", "S3_NOT_TERMINOLOGY", "S4_NOT_TRIVIAL_APPLICATION",
            "S5_GENERALIZES")
SCORES = ("REAL_WORLD_IMPORTANCE", "UNSOLVEDNESS", "SCIENTIFIC_DEPTH", "GENERALITY", "AEROSPACE_RELEVANCE",
          "COMMERCIAL_VALUE", "EXPERIMENTAL_TESTABILITY", "EMBEDDED_FEASIBILITY", "SWORT_FIT",
          "PRIOR_ART_DEFENSIBILITY")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _rows(name):
    with open(D / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_exactly_the_twelve_deliverables_exist():
    assert sorted(p.name for p in D.iterdir()) == sorted(FILES)


def test_candidates_are_complete_problem_first_and_agree_with_the_kill_matrix():
    cands = _rows("CANDIDATE_PROBLEMS.csv")
    kills = {r["PROBLEM_ID"]: r for r in _rows("PRIOR_ART_KILL_MATRIX.csv")}
    assert len(cands) >= 8
    assert [r["PROBLEM_ID"] for r in cands] == [f"P{i:02d}" for i in range(1, len(cands) + 1)]
    assert sorted(kills) == [r["PROBLEM_ID"] for r in cands]
    for r in cands:
        pid = r["PROBLEM_ID"]
        assert all(v.strip() for v in r.values()), pid
        assert "CSIA" not in r["PROBLEM"], pid                                # stated without CSIA
        assert r["CLASSIFICATION"] in CLASSES, pid
        assert kills[pid]["CLASSIFICATION"] == r["CLASSIFICATION"], pid
        assert kills[pid]["NOVELTY_STATUS"] == r["NOVELTY_STATUS"], pid
        assert all(r[s] in ("YES", "NO", "PARTIAL", "UNCLEAR") for s in SURVIVAL), pid
        if r["CLASSIFICATION"] == "POTENTIAL_GAP":
            assert all(r[s] == "YES" for s in SURVIVAL), pid


def test_scores_are_bounded_summed_and_evidenced():
    for r in _rows("CANDIDATE_PROBLEMS.csv"):
        pid = r["PROBLEM_ID"]
        if r["CLASSIFICATION"] == "KILLED":
            assert all(r[s].startswith("n/a") for s in SCORES + ("TOTAL_50",)), pid
            continue
        vals = [int(r[s]) for s in SCORES]
        assert all(0 <= v <= 5 for v in vals), pid
        assert sum(vals) == int(r["TOTAL_50"]), pid
        evidence = {part.split("=")[0].strip(): part for part in r["EVIDENCE_FOR_SCORES_GE4"].split(";")}
        for s, v in zip(SCORES, vals):
            if v >= 4:
                assert s in evidence and re.search(r"L\d{3}", evidence[s]), (pid, s)


def test_novelty_statuses_are_bounded():
    for r in _rows("PRIOR_ART_KILL_MATRIX.csv"):
        assert r["NOVELTY_STATUS"] in ("N0", "N1", "N2"), r["PROBLEM_ID"]
        if r["NOVELTY_STATUS"] == "N2":
            assert not r["NOVELTY_CONFIDENCE"].upper().startswith(("HIGH", "MEDIUM")), r["PROBLEM_ID"]


def test_every_cited_source_is_defined_with_a_level():
    reg = _text("PROBLEM_LANDSCAPE.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (L\d{3}) \|.*$", reg, re.M)}
    for rid, line in rows.items():
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), rid
    cited = set()
    for name in FILES:
        cited |= set(re.findall(r"\b(L\d{3})\b", _text(name)))
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


def test_single_decision_follows_the_stated_rule():
    present = {d for name in FILES for d in DECISIONS if d in _text(name)}
    assert len(present) == 1, present
    decision = present.pop()
    for name in FILES:
        assert _text(name).count(decision) == (1 if name == "TOP_GAPS.md" else 0), name
    last = [ln for ln in _text("TOP_GAPS.md").strip().splitlines() if ln.strip()][-1]
    assert decision in last
    cands = _rows("CANDIDATE_PROBLEMS.csv")
    gap = [r for r in cands
           if r["CLASSIFICATION"] == "POTENTIAL_GAP" and all(r[s] == "YES" for s in SURVIVAL)
           and int(r["TOTAL_50"]) >= 30 and int(r["REAL_WORLD_IMPORTANCE"]) >= 4
           and int(r["UNSOLVEDNESS"]) >= 3 and int(r["AEROSPACE_RELEVANCE"]) >= 4
           and int(r["PRIOR_ART_DEFENSIBILITY"]) >= 3]
    engineering = [r for r in cands
                   if r["CLASSIFICATION"] == "ENGINEERING_ONLY" and int(r["REAL_WORLD_IMPORTANCE"]) >= 3]
    expected = DECISIONS[2] if gap else DECISIONS[1] if engineering else DECISIONS[0]
    assert decision == expected, (decision, [r["PROBLEM_ID"] for r in gap + engineering])
