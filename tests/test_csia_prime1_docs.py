"""CSIA PRIME-1: guards on the package's documents and recorded results.

- the documents exist and keep the repository's wording rules;
- the decision chooses exactly one token, answers the 21 questions and keeps
  the authority boundary;
- the claim matrix separates the telemetry classes and keeps physical claims
  out; the website claims file has its four sections;
- the offer invents no price, currency or ROI and labels pricing a hypothesis;
- the recorded results hold no ground truth, the bundle audit found no leak,
  the held-out evaluation ran on the frozen code and says SIMULATION-ONLY,
  and no gate claims physical validation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "research/csia_prime1"

DOCS = {"README.md", "DEFECT_FIXES.md", "KNOWN_DEFECT_REGISTER.md", "HELDOUT_PREREGISTRATION.md",
        "EVENT_DISCOVERY_PRIME1.md", "CLAIM_EVIDENCE_MATRIX_PRIME1.md", "PUBLIC_CLAIMS.md", "SUPPORT_MATRIX.md",
        "PILOT_OFFER.md", "PILOT_INTAKE_AND_PROTOCOL.md", "PILOT_METRICS.md", "VALUE_CLASSIFICATION.md",
        "DIFFERENTIATION.md", "PRODUCT_READINESS.md", "PRIME1_REVIEW_AND_DECISION.md"}
PILOT_DOCS = {"QUICKSTART.md", "REPORT_GUIDE.md", "KNOWN_LIMITATIONS.md", "PARTICIPANT_INSTRUCTIONS.md",
              "DIAGNOSTIC_QUESTIONS.md", "FEEDBACK_FORM.md"}
BANNED = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
          "never been studied", "has never been", "no prior art exists")
TOKENS = ("CSIA_PRIME1_READY_FOR_EXTERNAL_PILOT", "CSIA_PRIME1_READY_BUT_BLOCKED_ON_REAL_DATA",
          "CSIA_PRIME1_DEFECT_FIX_FAILED", "CSIA_PRIME1_EVENT_DISCOVERY_NOT_READY",
          "CSIA_PRIME1_REQUIRES_SEMANTIC_REVIEW", "CSIA_PRIME1_REQUIRES_ARCHITECTURE_REVISION")
LEAK_TOKENS = ("failure_injection", "Injected:", "SIH_MOT_EFF", "SYS_FAILURE_EN", "GROUND_TRUTH")


def _all_docs():
    return ([PKG / n for n in sorted(DOCS)] + [PKG / "pilot_package" / n for n in sorted(PILOT_DOCS)]
            + [PKG / "pilot_package_experimenter/SCORING_RUBRIC.md"])


def _chosen(text):
    return [t for t in TOKENS if f"**`{t}`**" in text]


def test_the_prime1_documents_exist_and_keep_the_repositorys_wording_rules():
    assert {p.name for p in PKG.glob("*.md")} == DOCS
    assert {p.name for p in (PKG / "pilot_package").glob("*.md")} == PILOT_DOCS
    for p in _all_docs():
        text = p.read_text(encoding="utf-8").lower()
        assert len(text) > 1500, p.name
        assert not re.search(r"\bnovel\b", text), p.name
        for phrase in BANNED:
            assert phrase not in text, (p.name, phrase)


def test_the_decision_chooses_one_token_answers_21_questions_and_keeps_the_boundary():
    text = (PKG / "PRIME1_REVIEW_AND_DECISION.md").read_text(encoding="utf-8")
    chosen = _chosen(text)
    assert len(chosen) == 1
    assert chosen[0] in (PKG / "README.md").read_text(encoding="utf-8")
    for q in range(1, 22):
        assert f"**{q}. " in text, q
    for gate in ("P1", "P2", "P3", "P4", "P5"):
        assert f"| {gate} " in text, gate
    assert re.search(r"\| P5 [^\n]*\| \*\*NOT MET\*\*", text)
    for doc in ("README.md", "PRIME1_REVIEW_AND_DECISION.md", "PILOT_OFFER.md"):
        t = (PKG / doc).read_text(encoding="utf-8").upper()
        assert "OFFBOARD" in t and "ZERO CONTROL" in t and "NO FORGE" in t, doc


def test_the_claim_matrix_separates_telemetry_classes_and_keeps_physical_claims_out():
    text = (PKG / "CLAIM_EVIDENCE_MATRIX_PRIME1.md").read_text(encoding="utf-8")
    assert ("| # | public claim | artifact | dataset | version | result | limitation | validation level "
            "| public-safe? |") in text
    for cls in ("RPM shortfall", "RPM excess", "telemetry dropout", "stuck", "offline producer",
                "matched motor-vs-telemetry discrimination"):
        assert cls in text, cls
    unsafe = text.split("## 4. Claims that are NOT public-safe")[1]
    for claim in ("on hardware", "Validated on real flights", "ROI", "PHYSICAL_VALIDATED"):
        assert claim in unsafe, claim


def test_the_website_claims_file_has_its_four_sections():
    text = (PKG / "PUBLIC_CLAIMS.md").read_text(encoding="utf-8")
    heads = ["## 1. SUPPORTED NOW", "## 2. SIMULATION ONLY", "## 3. UNDER PHYSICAL VALIDATION", "## 4. DO NOT CLAIM"]
    pos = [text.index(h) for h in heads]
    assert pos == sorted(pos)
    simulation = text.split(heads[1])[1].split(heads[2])[0]
    assert "in PX4 simulation" in simulation


def test_the_offer_labels_pricing_a_hypothesis_and_invents_no_price_or_roi():
    text = (PKG / "PILOT_OFFER.md").read_text(encoding="utf-8")
    assert "COMMERCIAL HYPOTHESIS NOT YET MARKET-VALIDATED" in text
    for doc in ("PILOT_OFFER.md", "PILOT_METRICS.md", "VALUE_CLASSIFICATION.md", "PUBLIC_CLAIMS.md"):
        t = (PKG / doc).read_text(encoding="utf-8")
        assert not re.search(r"[$€£]\s?\d", t), doc
        assert not re.search(r"\d+\s?%", t), doc


def test_the_participant_documents_and_records_hold_no_ground_truth():
    for p in (PKG / "pilot_package").glob("*.md"):
        t = p.read_text(encoding="utf-8")
        for tok in LEAK_TOKENS:
            assert tok not in t, (p.name, tok)
    rec = json.loads((PKG / "PILOT_BUNDLE_PRIME1.json").read_text())
    raw = json.dumps(rec)
    assert "truth" not in rec and "GROUND_TRUTH" not in json.dumps(rec["participant_files_sha256"])
    assert rec["zero_known_leaks"] and rec["all_exit_zero"]
    for name in re.findall(r'^    \("([A-Za-z0-9_]+)", ', (REPO / "research/csia_prime/build_pilot_bundle.py")
                           .read_text(), re.M):
        assert name not in raw, name
    audit = json.loads((PKG / "BLINDNESS_AUDIT.json").read_text())
    assert audit["zero_known_leaks"] is True and audit["verdict"] == "ZERO KNOWN GROUND-TRUTH LEAKS"


def test_the_heldout_evaluation_ran_once_on_the_frozen_code_and_says_simulation_only():
    """heldout_eval.py refuses to run if a frozen file changed or if results exist (so it ran once,
    on the frozen code); the record names its 14 inputs and its simulation-only scope."""
    res = json.loads((PKG / "HELDOUT_RESULTS.json").read_text())
    assert len(res["inputs_sha256"]) == 14
    v = res["verdict"]
    assert v["verdict"] in ("PROMOTE", "NOT_PROMOTED")
    assert v["scope"] == "EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY"
    doc = (PKG / "EVENT_DISCOVERY_PRIME1.md").read_text(encoding="utf-8")
    assert "EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY" in doc and f"**{v['verdict']}**" in doc


def test_nothing_claims_physical_validation():
    contract = json.loads((REPO / "csia_evidence_assurance/support_contract_prime1.json").read_text())
    assert all(c["validation_level"] != "PHYSICAL_VALIDATED" for c in contract["configurations"])
    final = json.loads((PKG / "FINAL_STATE_PRIME1.json").read_text())
    assert final["gates"]["P5_PHYSICAL_VALIDATION"]["met"] is False
