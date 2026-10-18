"""Guards for research/physical_validation/corrections/FL-053_SC09/.

The correction is PROPOSED. These tests hold the package to that: the historical
evidence it rests on is byte-identical, its claims about that evidence are
mechanically true, the adoption tool previews without writing and refuses
without an owner decision, and nothing in the package reads as adopted while
the failure ledger does not contain FL-053. They keep passing after adoption,
when the record must say ADOPTED instead.
"""

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "research" / "physical_validation" / "corrections" / "FL-053_SC09"
LEDGER = ROOT / "research" / "physical_validation" / "FAILURE_LEDGER.yaml"
BANNED = ("no prior work exists", "we are the first", "is the first to", "first ever", "no one has",
          "never been studied", "has never been", "no prior art exists")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def record():
    return yaml.safe_load((PKG / "CORRECTION_RECORD.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def adopted():
    ids = [e["id"] for e in yaml.safe_load(LEDGER.read_text(encoding="utf-8"))["entries"]]
    return "FL-053" in ids


def _snapshot():
    files = [LEDGER, ROOT / "docs/FIELD_INTEGRATION_RUNBOOK.md", ROOT / "docs/CURRENT_PROGRAM_STATE.md",
             ROOT / "research/physical_validation/PAPER_IMPACT_LEDGER.yaml", PKG / "CORRECTION_RECORD.yaml",
             ROOT / "research/consequence/phase32/SHA256_MANIFEST32.json",
             ROOT / "research/phase4/SHA256_MANIFEST4.json", ROOT / "research/phase5/SHA256_MANIFEST5.json"]
    return {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def test_every_verification_check_passes(record):
    v = _load("verify_correction", PKG / "verification" / "verify_correction.py")
    res = v.checks(record)
    failed = [(c, d) for c, ok, d in res if not ok]
    assert failed == []
    assert {c for c, _, _ in res} == {"C1", "C2", "C3", "C4", "C5", "C6", "C7"}


def test_status_matches_the_ledger_and_is_never_assumed(record, adopted):
    assert record["status"] == ("ADOPTED" if adopted else "PROPOSED")
    if not adopted:
        a = record["adoption"]
        assert a["decided_by"] is None and a["decided_on"] is None and a["decision_reference"] is None


def test_the_four_way_distinction_is_explicit(record):
    v, e = record["valid_values"], {x["id"]: x for x in record["erroneous_items"]}
    assert [v[a]["trust_first_crossing_s"] for a in ("slow_ramp", "spoof_3ms", "fast_ramp")] == [8.72, 3.36, 3.24]
    assert e["E1"]["recorded"] is True and e["E1"]["correct"] is False
    assert e["E2"]["recorded"] == {"slow_ramp": 7.72, "spoof_3ms": 2.36, "fast_ramp": 2.24}
    assert e["E2"]["correct"] == {"slow_ramp": 8.72, "spoof_3ms": 3.36, "fast_ramp": 3.24}
    assert record["substantive_conclusion"]["sc_09"] == "UNCHANGED"
    assert record["proposed_authoritative_statement"]["effective"] == "only when status is ADOPTED"
    assert len(record["historical_record"]["pinned_files"]) >= 10


def test_the_drafts_do_not_read_as_adopted_before_adoption(adopted):
    if adopted:
        pytest.skip("adopted: the drafts have been appended")
    pi = (PKG / "PI-006.paper_impact_entry.yaml").read_text(encoding="utf-8")
    assert "ready_to_integrate: false" in pi and "ready_to_integrate: true" not in pi
    entry = yaml.safe_load("entries:\n" + (PKG / "FL-053.ledger_entry.yaml").read_text(encoding="utf-8"))["entries"]
    assert len(entry) == 1 and entry[0]["id"] == "FL-053"
    for k in ("id", "date", "phase", "kind", "what_happened", "verdict", "consequence", "artifact"):
        assert entry[0].get(k), k


def test_the_adoption_preview_writes_nothing_and_apply_needs_a_decision(adopted, capsys):
    if adopted:
        pytest.skip("adopted: the tool now refuses by design")
    adopt = _load("adopt_fl053", PKG / "adopt.py")
    before = _snapshot()
    assert adopt.main([]) == 0
    assert adopt.main(["--apply"]) == 2
    assert _snapshot() == before
    out = capsys.readouterr().out
    assert "PREVIEW ONLY: 8 files would change" in out and "REFUSED" in out


def test_the_committed_patch_matches_the_ledger_it_would_change(adopted):
    if adopted:
        pytest.skip("adopted")
    patch = (PKG / "ADOPTION.patch").read_text(encoding="utf-8")
    entry = (PKG / "FL-053.ledger_entry.yaml").read_bytes().decode("utf-8")
    led = LEDGER.read_bytes().decode("utf-8")
    appended = (led if led.endswith("\n") else led + "\n") + (entry if entry.endswith("\n") else entry + "\n")
    new = hashlib.sha256(appended.encode()).hexdigest()
    old = hashlib.sha256(led.encode()).hexdigest()
    assert patch.count(f'"research/physical_validation/FAILURE_LEDGER.yaml": "{new}"') == 3
    assert patch.count(f'"research/physical_validation/FAILURE_LEDGER.yaml": "{old}"') == 3
    assert "+  - id: FL-053" in patch and "+  - id: PI-006" in patch


def test_the_package_keeps_the_wording_rules_and_states_the_count_rule():
    text = (PKG / "README.md").read_text(encoding="utf-8")
    assert len(text) > 1500 and "%" not in text
    low = text.lower()
    assert not re.search(r"\bnovel\b", low)
    for phrase in BANNED:
        assert phrase not in low, phrase
    assert "**Status: PROPOSED. Not adopted.**" in text
    assert 'Do not write "nineteen\n> corrections" while FL-053 is proposed.' in text
    assert "canonical Paper I corrections ledger has **14** entries" in text
