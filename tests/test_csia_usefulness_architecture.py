"""CSIA usefulness architecture review (research/csia_usefulness_architecture/): honesty guards.

The package is a design and audit, not an implementation. These checks keep
it honest as it is edited:
  * exactly the declared deliverables exist, and none of them is code;
  * the Phase 21 decision table covers the 29 mechanisms the brief lists,
    with exactly one allowed decision each and no empty field;
  * the FMEA carries FM-01..FM-18 and uses qualitative ratings only (no
    invented probabilities);
  * every proposed evidence-record field and every improvement cites a
    failure mode that exists in the FMEA;
  * improvement scores are integers 0-5 that sum to the stated total, labels
    are from the allowed set, and exactly five are TOP_FIVE, none of them
    outranked by a non-selected item;
  * every cited source id is defined, with a verification level;
  * no unqualified "novel" and no categorical priority claim.
Standard library only.
"""

import csv
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "research" / "csia_usefulness_architecture"
MD = ("README.md", "SOURCES.md", "01_CURRENT_SYSTEM_AUDIT.md", "02_CSIA_FMEA.md", "03_EVIDENCE_ADMISSIBILITY.md",
      "04_CONFIGURATION_TRANSITIONS.md", "05_PROVENANCE_AND_DEPENDENCE.md", "06_PRODUCERS_REGISTRY_AND_ADAPTERS.md",
      "07_CONFLICT_SEMANTICS.md", "08_PERFORMANCE_SAFETY_BOUNDARY.md", "09_DOWNSTREAM_AND_PRODUCT.md",
      "10_KEEP_REPLACE_TABLE.md", "11_TARGET_ROLE_AND_NON_GOALS.md", "12_TARGET_ARCHITECTURE.md",
      "13_MIGRATION_AND_VALIDATION.md", "14_FIRST_EXPERIMENT.md", "15_IMPROVEMENTS_AND_ROADMAP.md",
      "16_TOP_FIVE_IMPLEMENTATION_SPEC.md", "17_ARCHITECTURE_RED_TEAM.md")
CSV = ("CSIA_FMEA.csv", "TRANSITION_MATRIX.csv", "ARCHITECTURE_DECISIONS.csv", "EVIDENCE_RECORD_V2_FIELDS.csv",
       "IMPROVEMENT_SCORES.csv")
FILES = MD + CSV
DECISIONS = ("KEEP", "REFACTOR", "REPLACE_WITH_EXISTING_METHOD", "GENERALIZE", "DEPRECATE", "REMOVE", "ADD")
#: The brief's Phase 21 list, in order; each must appear in the matching row.
BRIEF_MECHANISMS = ("temporal trust", "v2 localization", "v2 attribution", "EvidenceRecord", "evidence predicates",
                    "function graph", "signature", "SupportCertificate", "ambiguity", "UNSUPPORTED",
                    "temporal-window", "latency", "monitor interfaces", "C runtime", "Python", "FORGE",
                    "audit trail", "configuration", "source identity", "estimator-mode", "controller-mode",
                    "dependency", "correlation", "invalidation", "expiration", "monitor-health", "conflict",
                    "provenance", "downstream API")
SCORES = ("SAFETY_VALUE", "OPERATIONAL_VALUE", "CUSTOMER_VALUE", "GENERALITY", "IMPLEMENTATION_COST_5_CHEAP",
          "COMPUTATIONAL_COST_5_CHEAP", "TESTABILITY", "COMPATIBILITY_WITH_CURRENT_CSIA",
          "REUSE_OF_EXISTING_METHODS", "PRIOR_ART_DEFENSIBILITY")
LABELS = ("ENGINEERING", "RESEARCH", "RESEARCH_PENDING_PRIOR_ART", "EXPERIMENTAL")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _rows(name):
    with open(D / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fm_ids():
    return {r["FM_ID"] for r in _rows("CSIA_FMEA.csv")}


def test_exactly_the_declared_deliverables_exist_and_none_is_code():
    assert sorted(p.name for p in D.iterdir()) == sorted(FILES)
    assert not list(D.rglob("*.py"))


def test_decision_table_covers_the_brief_with_one_decision_each():
    rows = _rows("ARCHITECTURE_DECISIONS.csv")
    assert len(rows) >= len(BRIEF_MECHANISMS)
    assert [r["ID"] for r in rows] == [f"AD-{i:02d}" for i in range(1, len(rows) + 1)]
    for r, key in zip(rows, BRIEF_MECHANISMS):
        assert key.lower() in r["MECHANISM"].lower(), (r["ID"], key)
    for r in rows:
        assert all(v.strip() for v in r.values()), r["ID"]
        assert r["DECISION"] in DECISIONS, r["ID"]
        assert r["PRIORITY"] in ("P0", "P1", "P2", "P3"), r["ID"]


def test_fmea_has_the_brief_modes_and_no_invented_probabilities():
    rows = _rows("CSIA_FMEA.csv")
    ids = [r["FM_ID"] for r in rows]
    assert all(f"FM-{i:02d}" in ids for i in range(1, 19))
    for r in rows:
        assert all(v.strip() for v in r.values()), r["FM_ID"]
        assert r["SEVERITY"] in ("HIGH", "MEDIUM", "LOW"), r["FM_ID"]
        assert r["LIKELIHOOD"] in ("OBSERVED", "PLAUSIBLE", "REMOTE", "UNKNOWN"), r["FM_ID"]
        assert r["DETECTABILITY"] in ("HIGH", "MEDIUM", "LOW"), r["FM_ID"]
        assert not re.search(r"\d", r["LIKELIHOOD"] + r["SEVERITY"] + r["DETECTABILITY"]), r["FM_ID"]


def test_every_field_and_improvement_prevents_a_known_failure_mode():
    known = _fm_ids()
    for r in _rows("EVIDENCE_RECORD_V2_FIELDS.csv"):
        cited = set(re.findall(r"FM-\d{2}", r["FAILURE_MODES_ADDRESSED"]))
        assert cited and cited <= known, r["FIELD"]
        assert r["TIER"] in ("REQUIRED", "OPTIONAL", "DERIVED", "DEBUG_AUDIT"), r["FIELD"]
    for r in _rows("IMPROVEMENT_SCORES.csv"):
        cited = set(re.findall(r"FM-\d{2}", r["FAILURE_MODES_PREVENTED"]))
        assert cited and cited <= known, r["ID"]


def test_improvement_scores_labels_and_top_five():
    rows = _rows("IMPROVEMENT_SCORES.csv")
    for r in rows:
        vals = [int(r[s]) for s in SCORES]
        assert all(0 <= v <= 5 for v in vals), r["ID"]
        assert sum(vals) == int(r["TOTAL_50"]), r["ID"]
        assert r["LABEL"] in LABELS, r["ID"]
    top = [r for r in rows if r["TOP_FIVE"]]
    assert sorted(r["TOP_FIVE"] for r in top) == ["T1", "T2", "T3", "T4", "T5"]
    lowest_top = min(int(r["TOTAL_50"]) for r in top)
    assert all(int(r["TOTAL_50"]) <= lowest_top for r in rows if not r["TOP_FIVE"])


def test_transition_matrix_covers_every_category():
    cats = {r["CATEGORY"] for r in _rows("TRANSITION_MATRIX.csv")}
    assert {"CONTROLLER", "ESTIMATOR", "SENSOR", "POWER", "PLANNER", "COMPUTE"} <= cats


def test_every_cited_source_is_defined_with_a_level():
    reg = _text("SOURCES.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (S\d{3}) \|.*$", reg, re.M)}
    for sid, line in rows.items():
        assert re.search(r"\bV[0-4]\b", line.rsplit("|", 2)[-2]), sid
    cited = set()
    for name in FILES:
        cited |= set(re.findall(r"\b(S\d{3})\b", _text(name)))
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
