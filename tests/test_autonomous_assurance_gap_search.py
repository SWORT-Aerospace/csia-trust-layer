"""Autonomous-assurance gap analysis (research/autonomous_assurance_gap_search/): honesty guards.

The package is a problem-first gap analysis, not a design. These checks keep
it honest as it is edited:
  * exactly the ten deliverables exist;
  * at least ten candidate gaps, each fully filled, each with a red-team
    verdict that agrees with the kill matrix;
  * surviving candidates carry integer scores 0-5 whose sum is the stated
    total, and every score >= 4 cites evidence from the source register;
  * novelty statuses stay within N0-N3, never N4, and N2/N3 never carry HIGH
    or MEDIUM confidence;
  * at most three top gaps, all survivors, each answering every required
    field;
  * every cited source id is defined, with a verification level;
  * no unqualified "novel" and no categorical priority claim;
  * exactly one decision token, on the last line of TOP_THREE_GAPS.md, and it
    is the one the stated decision rule yields from the scores.
Standard library only.
"""

import csv
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "research" / "autonomous_assurance_gap_search"
FILES = ("GAP_LANDSCAPE.md", "CANDIDATE_GAPS.csv", "PRIOR_ART_KILL_MATRIX.csv",
         "REAL_WORLD_FAILURE_EVIDENCE.md", "ASSURANCE_ASSUMPTION_AUDIT.md", "HEALTH_TO_CAPABILITY_AUDIT.md",
         "COMPOUND_DEGRADATION_AUDIT.md", "TOP_THREE_GAPS.md", "FULLTEXT_VERIFICATION_QUEUE.md", "SEARCH_LOG.md")
DECISIONS = ("NO_HIGH_VALUE_GAP_FOUND", "ONE_HIGH_VALUE_GAP_FOUND", "MULTIPLE_HIGH_VALUE_GAPS_FOUND")
SCORES = ("A_IMPORTANCE", "B_UNSOLVEDNESS", "C_DEPTH", "D_AEROSPACE", "E_COMMERCIAL", "F_TESTABILITY",
          "G_EMBEDDED", "H_SWORT_FIT", "I_DEFENSIBILITY", "J_PLATFORM")
FIELDS = ("**Exact problem.**", "**Why current systems fail.**", "**Closest prior art.**",
          "**What is actually missing", "**Who needs it.**", "**Why they would care.**",
          "**Why it is scientifically hard.**", "**Smallest falsifiable question.**",
          "**Why SWORT has an advantage", "**What would kill the direction")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _rows(name):
    with open(D / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _survivors():
    return [r for r in _rows("CANDIDATE_GAPS.csv") if r["RED_TEAM_VERDICT"].startswith("SURVIVES")]


def test_exactly_the_ten_deliverables_exist():
    assert sorted(p.name for p in D.iterdir()) == sorted(FILES)


def test_candidates_are_complete_and_agree_with_the_kill_matrix():
    cands = _rows("CANDIDATE_GAPS.csv")
    kills = {r["GAP_ID"]: r for r in _rows("PRIOR_ART_KILL_MATRIX.csv")}
    assert len(cands) >= 10
    assert [r["GAP_ID"] for r in cands] == [f"G{i:02d}" for i in range(1, len(cands) + 1)]
    assert sorted(kills) == [r["GAP_ID"] for r in cands]
    for r in cands:
        assert all(v.strip() for v in r.values()), r["GAP_ID"]
        assert "CSIA" not in r["PROBLEM"], r["GAP_ID"]                       # problem first
        verdict = r["RED_TEAM_VERDICT"]
        assert verdict.startswith(("KILL", "SURVIVES", "DOWNRANK")), r["GAP_ID"]
        k = kills[r["GAP_ID"]]["VERDICT"]
        assert verdict.split()[0] == k.split("_")[0], (r["GAP_ID"], verdict, k)


def test_survivor_scores_are_bounded_summed_and_evidenced():
    for r in _survivors():
        vals = [int(r[s]) for s in SCORES]
        assert all(0 <= v <= 5 for v in vals), r["GAP_ID"]
        assert sum(vals) == int(r["TOTAL_50"]), r["GAP_ID"]
        evidence = {part.split("=")[0].strip(): part for part in r["EVIDENCE_FOR_SCORES_GE4"].split(";")}
        for s, v in zip(SCORES, vals):
            if v >= 4:
                assert s[0] in evidence and re.search(r"R\d{3}", evidence[s[0]]), (r["GAP_ID"], s)
    for r in _rows("CANDIDATE_GAPS.csv"):
        if r["RED_TEAM_VERDICT"].startswith("KILL"):
            assert all(r[s].startswith("n/a") for s in SCORES), r["GAP_ID"]


def test_novelty_statuses_are_bounded():
    for r in _rows("PRIOR_ART_KILL_MATRIX.csv"):
        assert r["NOVELTY_STATUS"] in ("N0", "N1", "N2", "N3"), r["GAP_ID"]
        if r["NOVELTY_STATUS"] in ("N2", "N3"):
            assert not r["NOVELTY_CONFIDENCE"].upper().startswith(("HIGH", "MEDIUM")), r["GAP_ID"]


def test_top_gaps_are_survivors_and_answer_every_field():
    t = _text("TOP_THREE_GAPS.md")
    top = re.findall(r"^\| \d \| (G\d{2}) \|", t, re.M)
    survivors = {r["GAP_ID"] for r in _survivors()}
    assert 1 <= len(top) <= 3 and set(top) <= survivors, top
    for gid in top:
        section = t.split(f"## {gid}:", 1)[1].split("\n## ", 1)[0]
        missing = [f for f in FIELDS if f not in section]
        assert not missing, (gid, missing)


def test_every_cited_source_is_defined_with_a_level():
    reg = _text("GAP_LANDSCAPE.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (R\d{3}) \|.*$", reg, re.M)}
    for rid, line in rows.items():
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), rid
    cited = set()
    for name in FILES:
        cited |= set(re.findall(r"\b(R\d{3})\b", _text(name)))
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
    last = [ln for ln in _text("TOP_THREE_GAPS.md").strip().splitlines() if ln.strip()][-1]
    assert decision in last
    qualifying = [r for r in _survivors()
                  if int(r["A_IMPORTANCE"]) >= 4 and int(r["B_UNSOLVEDNESS"]) >= 3
                  and int(r["D_AEROSPACE"]) >= 4 and int(r["TOTAL_50"]) >= 30]
    expected = DECISIONS[min(len(qualifying), 2)]
    assert decision == expected, (decision, [r["GAP_ID"] for r in qualifying])
