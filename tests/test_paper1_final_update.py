"""Guards for publication/system_paper_i/final_update/ (Paper I value bindings).

The binding ledger is only worth having if it fails when the evidence moves,
so these tests check it, then check that the check itself can fail.
"""

import copy
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "publication" / "system_paper_i" / "final_update"
DOCS = {"README.md", "CAMPAIGN_PROVENANCE.md", "REDERIVATION_RECORD.md",
        "MANUSCRIPT_FINDINGS.md", "REFERENCE_STATUS.md"}
BANNED = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
          "never been studied", "has never been", "no prior art exists")


def _verifier():
    spec = importlib.util.spec_from_file_location("verify_bindings", PKG / "verify_bindings.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vb():
    return _verifier()


@pytest.fixture(scope="module")
def ledger(vb):
    return vb.load_ledger()


def test_every_binding_matches_the_committed_artifacts(vb, ledger):
    failures, counts = vb.check(ledger)
    assert failures == []
    assert sum(counts.values()) == len(ledger["bindings"])


def test_a_changed_value_or_hash_is_caught(vb, ledger):
    wrong_value = copy.deepcopy(ledger)
    next(b for b in wrong_value["bindings"] if b["id"] == "MA-01")["expect"] = 377999
    assert any(f.startswith("MA-01") for f in vb.check(wrong_value)[0])

    wrong_hash = copy.deepcopy(ledger)
    wrong_hash["artifacts"]["mechanism_b_bench"]["sha256"] = "0" * 64
    assert any("mechanism_b_bench" in f for f in vb.check(wrong_hash)[0])


def test_a_filter_that_matches_nothing_is_refused_not_passed(vb, ledger):
    bad = copy.deepcopy(ledger)
    row = next(b for b in bad["bindings"] if b["id"] == "MR-03")
    row["aggregate"]["where"] = {"condition": "NO_SUCH_CONDITION"}
    assert any(f.startswith("MR-03") and "vacuous" in f for f in vb.check(bad)[0])


def test_every_artifact_hash_is_a_full_sha256_and_every_commit_a_full_sha1(ledger):
    for name, a in ledger["artifacts"].items():
        if "path" in a:
            assert re.fullmatch(r"[0-9a-f]{64}", a["sha256"]), name
            assert re.fullmatch(r"[0-9a-f]{40}", a["bytes_introduced_at"]), name


def test_the_table_9_values_are_the_raw_crossings_and_the_net_of_dwell_ones_are_forbidden(ledger):
    by_id = {b["id"]: b for b in ledger["bindings"]}
    assert [by_id[f"T9-0{i}"]["expect"] for i in (4, 5, 6)] == [8.72, 3.36, 3.24]
    patterns = [f["pattern"] for f in ledger["forbidden"]]
    assert any(re.search(p, "trust 7.72 s") for p in patterns)


def test_scan_fails_on_a_forbidden_value_and_passes_without_one(vb, ledger, tmp_path, capsys):
    bad = tmp_path / "bad.tex"
    bad.write_text("The trust path crosses at 7.72 s against 2.96 s.\n")
    assert vb.scan(ledger, str(bad)) == 1
    good = tmp_path / "good.tex"
    good.write_text("The trust path crosses at 8.72 s against 2.96 s; % 7.72 in a comment\n")
    assert vb.scan(ledger, str(good)) == 0
    capsys.readouterr()


def test_the_documents_exist_and_keep_the_repositorys_wording_rules():
    assert {p.name for p in PKG.glob("*.md")} == DOCS
    for name in DOCS:
        text = (PKG / name).read_text(encoding="utf-8")
        assert len(text) > 1500, name
        assert "%" not in text, name
        low = text.lower()
        assert not re.search(r"\bnovel\b", low), name
        for phrase in BANNED:
            assert phrase not in low, (name, phrase)


def test_the_readme_states_the_governance_boundary_and_the_level_counts(ledger):
    text = (PKG / "README.md").read_text(encoding="utf-8")
    assert "NO PRIME-1 PRODUCT CODE OR FROZEN RESULT WAS MODIFIED." in text
    counts = {}
    for b in ledger["bindings"]:
        counts[b["level"]] = counts.get(b["level"], 0) + 1
    assert f"{len(ledger['bindings'])} value bindings across {len(ledger['artifacts'])} artifacts" in text
    for level, label in (("T1_REEXECUTED", "T1"), ("T2_RECOMPUTED", "T2"),
                         ("T3_ARTIFACT_RECORDED", "T3"), ("T4_DOCUMENT_ONLY", "T4"),
                         ("NOT_SUPPORTED", "not supported")):
        assert re.search(rf"\| {re.escape(label)} \|[^\n]*\| {counts[level]} \|", text), level


def test_the_findings_carry_the_successor_boundary_and_issue_no_decision_token():
    text = (PKG / "MANUSCRIPT_FINDINGS.md").read_text(encoding="utf-8")
    assert "No result in this\n> manuscript is recomputed using those successor systems." in text
    for token in ("PAPER1_READY_FOR_SUBMISSION", "PAPER1_READY_WITH_EXTERNAL_REFERENCE_CHECK_ONLY",
                  "PAPER1_REQUIRES_ADDITIONAL_INTERNAL_WORK", "PAPER1_REQUIRES_NEW_EXPERIMENT",
                  "PAPER1_CLAIMS_NOT_SUPPORTABLE"):
        for name in DOCS:
            assert token not in (PKG / name).read_text(encoding="utf-8"), (name, token)


def test_the_package_carries_no_product_code_pilot_bundle_or_raw_logs():
    allowed = DOCS | {"VALUE_BINDINGS.yaml", "verify_bindings.py"}
    present = {p.name for p in PKG.iterdir() if p.name != "__pycache__"}
    assert present == allowed
