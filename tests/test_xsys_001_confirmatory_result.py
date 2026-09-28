"""XSYS-001 confirmatory result: the frozen record stays frozen and consistent.

The result lives in research/xsys_001_confirmatory_campaign/ and is bound by
CONFIRMATORY_RESULT_MANIFEST.json (written once by freeze_result.py). These
checks fail if:
  * any file the manifest hashes changed, or the manifest itself changed;
  * a historical protocol manifest (XSYS-001, A1, A2) changed;
  * the verdict no longer follows mechanically from the integrity record and
    the frozen stage-2 decision;
  * the stage-1 output no longer matches its seal, or the stage-0 key and QC
    no longer match the sealed custody report;
  * the blindness audit record or its self-test no longer reads PASS;
  * the report's headline numbers drift from RESULTS.json, or its verdict
    line disagrees with the manifest;
  * a raw ULog enters git history;
  * the report makes a claim the result does not license.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "research" / "xsys_001_confirmatory_campaign"
X = ROOT / "research" / "xsys_confirmatory_001"
REPORT = ROOT / "docs" / "research" / "XSYS_001_CONFIRMATORY_RESULT.md"
MANIFEST = H / "CONFIRMATORY_RESULT_MANIFEST.json"
CHAIN = {
    X / "prereg" / "FREEZE_MANIFEST.json": "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b",
    X / "amendment_a1" / "FREEZE_MANIFEST_A1.json": "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b",
    X / "amendment_a2" / "FREEZE_MANIFEST_A2.json": "d86e857d000d54502ec66bcbc83dbf679c55903aaf8ffe5e557e4514b1dded8f",
}
VERDICTS = ("XSYS_001_PRIMARY_SUPPORTED", "XSYS_001_PRIMARY_NOT_SUPPORTED", "XSYS_001_CONFIRMATORY_INVALID")


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_manifest_matches_its_seal_and_every_file():
    m = _json(MANIFEST)
    assert _sha(MANIFEST) == MANIFEST.with_suffix(".sha256").read_text().split()[0]
    bad = [f for f, h in m["files"].items() if not (ROOT / f).is_file() or _sha(ROOT / f) != h]
    assert not bad, bad


def test_historical_manifests_unchanged():
    for p, want in CHAIN.items():
        assert _sha(p) == want, p


def test_verdict_follows_mechanically():
    m = _json(MANIFEST)
    res = _json(H / "stage2" / "RESULTS.json")
    assert m["verdict"] in VERDICTS
    if not all(m["integrity"].values()):
        assert m["verdict"] == "XSYS_001_CONFIRMATORY_INVALID"
    else:
        want = ("XSYS_001_PRIMARY_SUPPORTED" if res["primary"]["H_PRIMARY"] == "SUPPORTED"
                else "XSYS_001_PRIMARY_NOT_SUPPORTED")
        assert m["verdict"] == want
    p = res["primary"]
    supported = p["lower95"] is not None and p["lower95"] > 0.5 and p["wrong_A_B"] == 0
    assert (p["H_PRIMARY"] == "SUPPORTED") == supported
    assert res["mode"] == "confirmatory" and res["freeze_manifest_sha256"] == CHAIN[X / "amendment_a2" / "FREEZE_MANIFEST_A2.json"]


def test_seals_and_custody_hold():
    seal = _json(H / "stage1" / "STAGE1.seal.json")
    assert _sha(H / "stage1" / "STAGE1.json") == seal["stage1_output_sha256"]
    s0 = _json(H / "stage0" / "STAGE0_REPORT.json")
    assert _sha(H / "stage0" / "STAGE0_REPORT.json") == (H / "stage0" / "STAGE0_REPORT.sha256").read_text().split()[0]
    assert _sha(H / "stage0" / "KEY.json") == s0["label_key_sha256"]
    assert _sha(H / "stage0" / "QC.json") == s0["qc_sha256"]
    comp = _json(H / "CAMPAIGN_COMPLETION.json")
    assert _sha(H / "CAMPAIGN_COMPLETION.json") == (H / "CAMPAIGN_COMPLETION.sha256").read_text().split()[0]
    assert _sha(H / "RAW_DATA_MANIFEST.json") == comp["raw_data_manifest_sha256"]
    assert _json(H / "stage2" / "RESULTS.json")["stage1_output_sha256"] == seal["stage1_output_sha256"]


def test_blindness_audit_passed_and_was_self_tested():
    rec = _json(H / "stage1" / "STAGE1_SEAL_RECORD.json")
    assert rec["blind"] is True and rec["strace_forbidden_hits"] == []
    assert all(rec["blindness_checks"].values())
    assert _json(H / "BLINDNESS_AUDIT_SELFTEST.json")["self_test"] == "PASS"
    gate = _json(H / "UNBLINDING_GATE.json")
    assert gate["all_pass"] is True and all(gate["gate"].values())


def test_report_numbers_and_verdict_match_the_frozen_result():
    text = REPORT.read_text(encoding="utf-8")
    m = _json(MANIFEST)
    p = _json(H / "stage2" / "RESULTS.json")["primary"]
    first = next(line for line in text.splitlines() if "XSYS_001_" in line)
    assert m["verdict"] in first, first
    assert [v for v in VERDICTS if v in text] == [m["verdict"]]
    for literal in (repr(p["lower95"]), str(p["n_pairs"]), str(p["n_success"])):
        assert literal in text, literal
    assert f"| WRONG | {p['wrong_A_B']} |" in text
    assert "DURABLE_STORAGE_PENDING" in text or "DURABLE_STORAGE_COMPLETE" in text


def test_report_makes_no_unlicensed_claim():
    low = REPORT.read_text(encoding="utf-8").lower()
    assert not re.search(r"\bnovel\b", low)
    for phrase in ("we are the first", "is the first to", "first ever", "validated in real flight",
                   "flight-proven", "certified for", "outperforms"):
        assert phrase not in low, phrase


def test_no_raw_ulog_in_git():
    out = subprocess.run(["git", "ls-files", "*.ulg", "*.ulg.xz"], cwd=ROOT, capture_output=True, text=True).stdout
    tracked = [f for f in out.splitlines() if "xsys_001_confirmatory" in f]
    assert not tracked, tracked
