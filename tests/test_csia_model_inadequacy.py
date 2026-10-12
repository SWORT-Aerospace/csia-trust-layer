"""Model-inadequacy prior-art attack (research/csia_model_inadequacy/): honesty guards.

The package is a problem-validation and prior-art attack, not an
implementation. These checks keep it honest as it is edited:
  * the eight deliverables exist, and nothing else is in the directory;
  * the claim matrix uses only N0-N3 (never N4, which needs V3/V4 full text),
    never HIGH or MEDIUM confidence on an N2/N3 status, and every row is
    filled;
  * every cited source id is defined in the source register, with a
    verification level;
  * the word "novel" never appears unqualified (verbatim queries and quoted
    strings aside), and no document makes a categorical priority claim;
  * exactly one permitted decision appears in the package, and it is on the
    last line of the attack document.
Standard library only.
"""

import csv
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "research" / "csia_model_inadequacy"
FILES = ("PROBLEM_DEFINITION.md", "PRIOR_ART_ATTACK.md", "AMBIGUITY_VS_MODEL_INADEQUACY.md",
         "CLOSEST_SYSTEMS.md", "NOVELTY_CLAIM_MATRIX.csv", "USEFULNESS.md",
         "FULLTEXT_VERIFICATION_QUEUE.md", "SEARCH_LOG.md")
DECISIONS = ("MODEL_INADEQUACY_KILL", "MODEL_INADEQUACY_PIVOT", "MODEL_INADEQUACY_CONTINUE")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _claims():
    with open(D / "NOVELTY_CLAIM_MATRIX.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_exactly_the_eight_deliverables_exist():
    assert sorted(p.name for p in D.iterdir()) == sorted(FILES)


def test_claim_statuses_are_bounded():
    rows = _claims()
    assert [r["CLAIM_ID"] for r in rows] == [f"MI-C{i}" for i in range(1, len(rows) + 1)] and len(rows) >= 10
    for r in rows:
        assert r["NOVELTY_STATUS"] in ("N0", "N1", "N2", "N3"), r["CLAIM_ID"]
        assert all(v.strip() for v in r.values()), r["CLAIM_ID"]
        if r["NOVELTY_STATUS"] in ("N2", "N3"):
            assert not r["CONFIDENCE"].upper().startswith(("HIGH", "MEDIUM")), r["CLAIM_ID"]


def test_every_cited_source_is_defined_with_a_level():
    register = _text("PRIOR_ART_ATTACK.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (M\d{2}) \|.*$", register, re.M)}
    for rid, line in rows.items():
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), rid
    cited = set()
    for name in FILES:
        cited |= set(re.findall(r"\b(M\d{2})\b", _text(name)))
    assert cited and not (cited - set(rows)), sorted(cited - set(rows))


def test_no_unqualified_novelty_or_priority_language():
    banned = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
              "never been studied", "has never been", "no prior art exists")
    for name in FILES:
        low = _text(name).lower()
        assert not [b for b in banned if b in low], name
        stripped = re.sub(r"`[^`\n]*`", "", low)          # verbatim search queries
        stripped = re.sub(r'"[^"\n]*"', "", stripped)     # quoted titles and phrases
        assert not re.search(r"\bnovel\b", stripped), name


def test_package_carries_exactly_one_decision_on_the_attack_documents_last_line():
    present = {d for name in FILES for d in DECISIONS if d in _text(name)}
    assert len(present) == 1, present
    t = _text("PRIOR_ART_ATTACK.md")
    last = [ln for ln in t.strip().splitlines() if ln.strip()][-1]
    assert present.pop() in last
