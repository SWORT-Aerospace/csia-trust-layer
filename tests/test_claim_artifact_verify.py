"""Guards for the claim-artifact verifier.

Every verdict the verifier can reach is exercised here against a register and
a tree built to produce it. The register under test is synthetic in most
cases: pinning the real one's counts would turn any legitimate regeneration
into a test failure, and what needs protecting is the DECISION, not today's
numbers.

Two properties matter more than the rest and are tested directly:

  * the verifier never writes to an artifact. A verifier that can repair what
    it checks has a green result that means nothing.
  * a locked or otherwise unregenerable artifact is never regenerated, and
    says so as a terminal state rather than an outstanding task.
"""

from __future__ import annotations

import json
import os
import sys

import pytest
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.assurance import claim_artifact_verify as v   # noqa: E402

REGISTER = os.path.join(ROOT, "research", "assurance",
                        "CLAIM_ARTIFACT_REGISTER.yaml")

GOOD_HASH = "0" * 64


def _entry(**over):
    base = {
        "artifact_path": "a.json",
        "paper": ["csia_systems"],
        "claim_id": ["T01"],
        "claim_description": "a claim",
        "artifact_kind": "DERIVED_RESULT",
        "source_commit": "abc123",
        "sha256": GOOD_HASH,
        "generator_path": "gen.py",
        "generator_commit": "def456",
        "input_artifacts": ["UNKNOWN"],
        "environment_requirements": "UNKNOWN",
        "regeneration_status": "REGENERABLE",
        "freeze_status": "NOT_PINNED",
        "limitations": "none recorded",
        "current_verdict": "GENERATOR_PROVEN_INPUTS_UNKNOWN",
    }
    base.update(over)
    return base


def _tree(tmp_path, artifact="a.json", body=b"{}", generator="gen.py"):
    if artifact:
        (tmp_path / artifact).write_bytes(body)
    if generator:
        (tmp_path / generator).write_text("# generator\n")
    return str(tmp_path)


def _sha_of(tmp_path, name):
    return v.sha256(str(tmp_path / name))


# ------------------------------------------------------------ 1. valid

def test_a_valid_artifact_verifies(tmp_path):
    root = _tree(tmp_path)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"))
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.VALID, detail
    assert not detail["problems"]


# ---------------------------------------------------------- 2. changed

def test_a_changed_artifact_reports_drift(tmp_path):
    root = _tree(tmp_path)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"))
    (tmp_path / "a.json").write_bytes(b'{"changed": true}')
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.DRIFT
    assert "hash drift" in detail["problems"][0]


def test_drift_exits_nonzero(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    reg = tmp_path / "REG.yaml"
    reg.write_text(yaml.safe_dump(
        {"entries": [_entry(sha256="1" * 64)]}))
    monkeypatch.setattr(v, "ROOT", root)
    rc = v.main(["--register", str(reg)])
    assert rc == 1, "hash drift must exit nonzero"


# ---------------------------------------------------------- 3. missing

def test_a_missing_artifact_is_reported(tmp_path):
    root = _tree(tmp_path, artifact=None)
    verdict, detail = v.verify_entry(_entry(), root)
    assert verdict == v.MISSING
    assert "artifact absent" in detail["problems"][0]


def test_missing_provenance_exits_nonzero(tmp_path, monkeypatch):
    root = _tree(tmp_path, artifact=None)
    reg = tmp_path / "REG.yaml"
    reg.write_text(yaml.safe_dump({"entries": [_entry()]}))
    monkeypatch.setattr(v, "ROOT", root)
    assert v.main(["--register", str(reg)]) == 1


# -------------------------------------------------- 4. missing generator

def test_a_named_but_absent_generator_is_reported(tmp_path):
    root = _tree(tmp_path, generator=None)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"))
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.MISSING
    assert "generator named but absent" in detail["problems"][0]


# ------------------------------------------------------ 5. missing input

def test_a_declared_but_absent_input_is_reported(tmp_path):
    root = _tree(tmp_path)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"),
                   input_artifacts=["inputs/never_written.json"])
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.MISSING
    assert "declared input absent" in detail["problems"][0]


def test_a_declared_and_present_input_passes(tmp_path):
    root = _tree(tmp_path)
    (tmp_path / "in.json").write_text("{}")
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"),
                   input_artifacts=["in.json"])
    verdict, _ = v.verify_entry(entry, root)
    assert verdict == v.VALID


# ------------------------------- 6. raw: verifiable but not regenerable

def test_a_raw_capture_is_verifiable_but_not_regenerable(tmp_path):
    root = _tree(tmp_path)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"),
                   artifact_kind="RAW_CAPTURE",
                   regeneration_status="VERIFIABLE_ONLY")
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.UNREGENERABLE
    assert any("terminal state" in n for n in detail["notes"]), (
        "an unregenerable artifact must be reported as a terminal state, not "
        "as an outstanding task somebody should clear")


# --------------------------------- 7. locked: must not be regenerated

def test_a_locked_artifact_is_never_regenerated(tmp_path, monkeypatch):
    """The verifier must not run the generator, for any entry."""
    root = _tree(tmp_path)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"),
                   regeneration_status="NOT_REGENERABLE")

    import subprocess
    def explode(*a, **k):
        raise AssertionError("the verifier executed a subprocess; it must "
                             "never run a generator")
    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)

    verdict, _ = v.verify_entry(entry, root)
    assert verdict == v.UNREGENERABLE


def test_the_verifier_exposes_no_regenerate_or_fix_option():
    """A verifier that can rewrite what it verifies proves nothing."""
    import argparse
    seen = set()
    real = argparse.ArgumentParser.add_argument

    def record(self, *a, **k):
        for name in a:
            if isinstance(name, str) and name.startswith("-"):
                seen.add(name)
        return real(self, *a, **k)

    argparse.ArgumentParser.add_argument = record
    try:
        with pytest.raises(SystemExit):
            v.main(["--help"])
    finally:
        argparse.ArgumentParser.add_argument = real

    bad = [o for o in seen if any(k in o.lower() for k in
                                  ("fix", "regen", "update", "refresh",
                                   "write", "repair", "force"))]
    assert not bad, f"mutating options exposed: {bad}"


def test_the_verifier_does_not_modify_the_artifact(tmp_path):
    root = _tree(tmp_path, body=b'{"original": 1}')
    before = (tmp_path / "a.json").read_bytes()
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"))
    v.verify_entry(entry, root)
    assert (tmp_path / "a.json").read_bytes() == before


# ------------------------------------------------- 8. unknown provenance

def test_an_entry_with_no_established_generator_is_unknown(tmp_path):
    root = _tree(tmp_path, generator=None)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"),
                   generator_path="MISSING")
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.UNKNOWN
    assert any("none was guessed" in n for n in detail["notes"])


def test_unknown_outranks_unregenerable(tmp_path):
    """A gap must not hide behind the milder fact."""
    root = _tree(tmp_path, generator=None)
    entry = _entry(sha256=_sha_of(tmp_path, "a.json"),
                   generator_path="MISSING",
                   regeneration_status="NOT_REGENERABLE")
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.UNKNOWN, (
        "an entry that is both unregenerable and missing its provenance is "
        "in the weaker state and must report the provenance gap")
    assert any("more serious" in n for n in detail["notes"])


def test_an_unrecorded_hash_is_unknown_not_valid(tmp_path):
    root = _tree(tmp_path)
    entry = _entry(sha256="UNKNOWN")
    verdict, detail = v.verify_entry(entry, root)
    assert verdict == v.UNKNOWN
    assert any("integrity is UNKNOWN" in n for n in detail["notes"])


# ------------------------------------------- 9. malformed register entry

def test_a_malformed_entry_is_rejected(tmp_path):
    entry = _entry()
    del entry["sha256"]
    verdict, detail = v.verify_entry(entry, str(tmp_path))
    assert verdict == v.UNKNOWN
    assert detail["malformed"] is True
    assert any("sha256" in p for p in detail["problems"])


def test_a_bad_enum_value_is_rejected(tmp_path):
    verdict, detail = v.verify_entry(
        _entry(artifact_kind="SOMETHING_ELSE"), str(tmp_path))
    assert verdict == v.UNKNOWN
    assert any("artifact_kind" in p for p in detail["problems"])


def test_a_non_hex_digest_is_rejected(tmp_path):
    verdict, detail = v.verify_entry(_entry(sha256="not-a-digest"),
                                     str(tmp_path))
    assert verdict == v.UNKNOWN
    assert any("64-hex" in p for p in detail["problems"])


def test_an_unreadable_register_exits_two(tmp_path):
    bad = tmp_path / "REG.yaml"
    bad.write_text("entries: []\n")
    assert v.main(["--register", str(bad)]) == 2


# --------------------------------------------- the real register, as data

def test_the_committed_register_covers_exactly_the_paper_cited_artifacts():
    """The register's scope must match the audit's claim-backing tier."""
    from tools.assurance import evidence_gate_audit as a
    doc = v.load_register(REGISTER)
    listed = {e["artifact_path"] for e in doc["entries"]}
    cited = {r["artifact"] for r in a.audit()["rows"]
             if r["cited_by_a_paper_artifact_map"]}
    assert listed == cited, (
        f"register and audit disagree; only in register: {listed - cited}; "
        f"only in audit: {cited - listed}")


def test_the_committed_register_verifies():
    report = v.verify(REGISTER)
    assert report["entries_checked"] == len(v.load_register(REGISTER)["entries"])
    assert not report["drift"], report["drift"]
    assert not report["missing"], report["missing"]


def test_the_report_refuses_to_equate_a_hash_with_a_gate():
    report = v.verify(REGISTER)
    text = report["a_valid_hash_is_not_a_gate"].lower()
    assert "detects" in text and "gating" in text, (
        "the report must say that hash pinning detects modification while "
        "evidence gating controls generation; conflating them is the whole "
        "error this work exists to avoid")
