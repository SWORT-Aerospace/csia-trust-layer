"""Guards for the candidate-B Stage 0A package.

NOTHING HERE SCORES A RESULT. Stage 0A produced no experimental result. These
tests protect the properties that would make the package dishonest if they
broke: no implementation, no full text claimed, no novelty sentence written
without an audit, the refuted claims stay refuted, and Stage 0B stays unwritten
while its gates are failing.
"""

from __future__ import annotations

import csv
import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "effective_evidence_independence")

REQUIRED = [
    "README.md", "REQUIRED_READING_MANIFEST.md", "FULLTEXT_READING_LOG.md",
    "PRIOR_ART_PROBLEM_SEPARATION.csv", "PRIOR_ART_REDUCTION.md",
    "INDEPENDENCE_TAXONOMY.md", "PROVISIONAL_GRAPH_MODEL.md",
    "FORMAL_REDUCTION.md", "MENGER_CLAIM_COUNTEREXAMPLES.md",
    "META_DIAGNOSIS_REDUCTION.md", "DYNAMIC_FAULT_TREE_REDUCTION.md",
    "ARP4761_CCA_REDUCTION.md", "COMMON_INFORMATION_REDUCTION.md",
    "RUNTIME_TOPOLOGY_SOURCE_AUDIT.md", "SELECTED_DYNAMIC_EXAMPLE.md",
    "CLAIM_LEDGER.json", "STAGE0A_CHATGPT_REVIEW_REPORT.md",
]

VOCAB = {"KNOWN/SUBSUMED", "PROVED - NOVELTY NOT ESTABLISHED",
         "PROVED - POSSIBLE NOVEL CONTRIBUTION", "EMPIRICAL ONLY",
         "PROVISIONAL", "CONJECTURE", "REFUTED"}


def _md(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as fh:
        return fh.read()


def _ledger():
    with open(os.path.join(PKG, "CLAIM_LEDGER.json"), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------- item 34: no coding
def test_the_package_contains_no_code():
    """Item 34 forbids kappa computation code and provenance tooling."""
    bad = []
    for dirpath, _dirs, files in os.walk(PKG):
        for fn in files:
            if fn.endswith((".py", ".sh", ".c", ".cpp", ".ipynb")):
                bad.append(os.path.join(dirpath, fn))
    assert not bad, bad


def test_no_production_csia_file_in_the_package():
    for dirpath, _dirs, files in os.walk(PKG):
        for fn in files:
            p = os.path.join(dirpath, fn).replace(os.sep, "/")
            assert "/csia/" not in p, p


def test_every_required_artifact_exists():
    missing = [f for f in REQUIRED if not os.path.exists(os.path.join(PKG, f))]
    assert not missing, missing


# --------------------------------------------- item 31: no Stage 0B while gated
def test_stage_0b_artifacts_are_absent_while_the_gates_fail():
    led = _ledger()
    gated = (led["prior_art_verdict"] == "INCONCLUSIVE_MISSING_FULLTEXT"
             or led["scientific_verdict"] != "STRONG_STAGE0_CANDIDATE")
    if not gated:
        pytest.skip("gates no longer failing; this guard does not apply")
    assert led["ready_for_stage_0b"] is False
    for fn in ("STAGE0B_PREREGISTRATION_DRAFT.md",
               "STAGE0B_EXECUTION_PROMPT.md"):
        assert not os.path.exists(os.path.join(PKG, fn)), (
            f"{fn} written while a gate is failing")


# ------------------------------------------------- item 1: no snippet novelty
def test_no_source_is_recorded_as_read_in_full():
    p = os.path.join(PKG, "PRIOR_ART_PROBLEM_SEPARATION.csv")
    with open(p, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for r in rows:
        assert r["full_text_read"] == "NO", r["citation"]
    assert _ledger()["full_texts_read"] == 0


def test_the_permitted_novelty_sentence_is_never_written():
    """Item 30 allows 'We did not identify, in the full-text sources
    reviewed...' only when an audit supports it. Zero were reviewed."""
    pat = re.compile(r"we did not identify[^.]{0,80}in the full-text sources",
                     re.I)
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        t = _md(fn)
        for m in pat.finditer(t):
            line_start = t.rfind("\n", 0, m.start()) + 1
            window = t[line_start:m.end() + 200].lower()
            assert ("cannot be written" in window or "appears nowhere" in window
                    or "permits" in window or "allows" in window), (fn, m.group(0))


def test_the_prior_art_verdict_is_one_of_the_allowed_options():
    allowed = {"KILLED_BY_COMMON_CAUSE_ANALYSIS", "KILLED_BY_DYNAMIC_RELIABILITY",
               "KILLED_BY_COMMON_INFORMATION_FUSION", "KILLED_BY_META_DIAGNOSIS",
               "KILLED_BY_STRUCTURAL_FDI",
               "SURVIVES_AS_RUNTIME_DIAGNOSTIC_STRUCTURE_PROBLEM",
               "INCONCLUSIVE_MISSING_FULLTEXT"}
    assert _ledger()["prior_art_verdict"] in allowed


def test_the_scientific_verdict_is_one_of_the_allowed_options():
    allowed = {"STRONG_STAGE0_CANDIDATE", "PROVISIONAL_BUT_TESTABLE",
               "STATIC_DEPENDENCE_ONLY", "PROVENANCE_METRIC_INSUFFICIENT",
               "KNOWN_SUBSUMED", "INCONCLUSIVE"}
    assert _ledger()["scientific_verdict"] in allowed


# ------------------------------------------------------- claim-ledger hygiene
def test_no_claim_is_awarded_novelty():
    led = _ledger()
    assert led["novelty"] == "NOT ESTABLISHED"
    for c in led["claims"]:
        assert c["status"] in VOCAB, (c["id"], c["status"])
        assert c["status"] != "PROVED - POSSIBLE NOVEL CONTRIBUTION", c["id"]


def test_every_claim_carries_its_limits():
    for c in _ledger()["claims"]:
        for k in ("statement", "evidence", "status", "assumptions",
                  "strongest_allowed_wording", "forbidden_stronger_wording",
                  "next_falsification_test"):
            assert c.get(k), (c["id"], k)


def test_refuted_predictions_are_kept():
    led = _ledger()
    assert len(led["refuted_predictions"]) >= 4
    for p in led["refuted_predictions"]:
        assert p["kept"] is True, p["id"]


def test_the_two_corrections_of_the_frontier_report_stay_recorded():
    """kappa is not sufficient (E5) and the bound direction was wrong (E6).
    If either is quietly dropped, the package has started flattering itself."""
    led = _ledger()
    by_id = {c["id"]: c for c in led["claims"]}
    assert by_id["E4"]["status"] == "REFUTED"
    assert by_id["E6"]["status"] == "REFUTED"
    assert "under-estimate" in by_id["E6"]["statement"].lower()
    t = _md("FORMAL_REDUCTION.md")
    assert "neither an upper nor a lower bound" in t.lower()


def test_kappa_is_never_called_independence():
    """Item 5: the rename is the point. 'effective independence' may appear
    only where it is being retired."""
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        lines = _md(fn).lower().splitlines()
        for i, line in enumerate(lines):
            if "effective independence" not in line:
                continue
            window = " ".join(lines[max(0, i - 3):i + 4])
            assert any(k in window for k in (
                "retired", "not", "no ", "instead", "rename", "provisional",
                "false", "refuted", "insufficient", "frontier report",
                "asserts", "asserted", "wrong")), (fn, line[:120])


# ------------------------------------------------------------ honesty guards
def test_the_source_audit_cites_real_lines():
    """Every ArduPilot/PX4 claim in the audit must name a file and a line, and
    the files must exist where the audit says they do."""
    t = _md("RUNTIME_TOPOLOGY_SOURCE_AUDIT.md")
    for rel, root in (
            ("libraries/GCS_MAVLink/GCS_Common.cpp", "/home/user/ardupilot/ardupilot"),
            ("libraries/AP_InertialSensor/AP_InertialSensor.cpp", "/home/user/ardupilot/ardupilot"),
            ("libraries/AP_InertialSensor/AP_InertialSensor.h", "/home/user/ardupilot/ardupilot"),
            ("msg/SensorSelection.msg", "/home/user/px4")):
        assert rel in t, rel
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            pytest.skip(f"{root} not present in this environment")
    assert re.search(r"AP_InertialSensor\.cpp:\d+", t)
    assert re.search(r"GCS_Common\.cpp:\d+", t)


def test_the_px4_contrast_is_not_omitted():
    """The finding that PX4 already publishes the selection weakens the
    candidate. It must stay in the report, not only in the audit."""
    for fn in ("STAGE0A_CHATGPT_REVIEW_REPORT.md", "SELECTED_DYNAMIC_EXAMPLE.md",
               "RUNTIME_TOPOLOGY_SOURCE_AUDIT.md", "README.md"):
        assert "SensorSelection" in _md(fn), fn


def test_no_novelty_wording_anywhere():
    banned = ("first-ever", "unprecedented", "new paradigm", "breakthrough",
              "we prove a new theorem")
    denials = ("not ", "no ", "none", "never", "forbidden", "subsumed",
               "refuted", "cannot", "does not", "corollary", "provisional",
               "unresolved", "inconclusive")
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        raw = _md(fn).lower()
        text = re.sub(r"[.,;:!?)\]]", " ", raw.replace("*", "").replace("`", ""))
        lines = text.splitlines()
        for w in banned:
            if w not in text:
                continue
            for i, line in enumerate(lines):
                if w not in line or line.lstrip().startswith("#"):
                    continue
                window = " ".join(lines[i:i + 3])
                assert any(k in window for k in denials), (fn, w, line[:120])
