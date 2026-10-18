#!/usr/bin/env python3
"""Part 1: verify the state this phase starts from. RESEARCH ONLY, read-only.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/verify_state.py

Checks, without writing anything except STATE_VERIFICATION.json:
frozen v2 reasoning hashes (Phase A lock), the Semantic Core 2.1 package
commit, the semantic audit results hash, every XSYS-001 result-manifest hash
and protocol-chain manifest, the Phase C freeze record, the Phase 3.2/4/5
sealed manifests, the promotion token, the failure-ledger hash and the
proposed ledger entries.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREV = REPO / "research/csia_semantic_core_2_1"
OUT = HERE / "STATE_VERIFICATION.json"
LEDGER_PINNED = "6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f"
AUDIT_RESULTS_SHA = "aa85657795011fe9ed31db1777e84f38fd48b2cdec7115935e24f6b561a6a9b0"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def main():
    out = {}
    lock = json.loads((PREV / "PHASE_A_CHARACTERIZATION_LOCK.json").read_text())
    out["frozen_v2_reasoning_files"] = {
        p: sha(REPO / p) == h for p, h in lock["frozen_reasoning_file_sha256"].items()}
    # csia/v2 differs from the freeze commit only by f00d315 (2026-09-04,
    # lint-only: an f-string without placeholders, an unused variable, an
    # unused import). Checked: no commit after the freeze other than f00d315
    # touches csia/v2, and nothing changed since the Phase A lock.
    out["commits_touching_csia_v2_since_freeze"] = git(
        "log", "--format=%h", "50c5d3576e9084e7c2789167628392c5de992b6f..HEAD",
        "--", "csia/v2").split()
    out["csia_v2_changed_since_phase_a_lock"] = git(
        "diff", "--stat", lock["head_commit"], "--", "csia/v2") or "none"
    out["semantic_core_2_1_last_commit"] = git("log", "-1", "--format=%H", "--", "csia_semantic_core")
    out["semantic_audit_results_sha_matches"] = sha(
        REPO / "research/csia_semantic_correctness/semantic_probe_results.json") == AUDIT_RESULTS_SHA
    camp = REPO / "research/xsys_001_confirmatory_campaign"
    man = json.loads((camp / "CONFIRMATORY_RESULT_MANIFEST.json").read_text())
    seal = (camp / "CONFIRMATORY_RESULT_MANIFEST.sha256").read_text().split()[0]
    out["xsys_result_manifest_matches_seal"] = sha(camp / "CONFIRMATORY_RESULT_MANIFEST.json") == seal
    out["xsys_result_manifest_files_differing"] = [
        p for p, h in man["files"].items() if not (REPO / p).exists() or sha(REPO / p) != h]
    out["xsys_protocol_chain_manifests_unchanged"] = {
        k: sha(REPO / v["file"]) == v["sha256"] for k, v in man["protocol_chain"].items()}
    s1 = camp / "stage1/STAGE1.json"
    out["xsys_stage1_matches_seal"] = sha(s1) == json.loads(
        (camp / "stage1/STAGE1.seal.json").read_text())["stage1_output_sha256"]
    freeze = (REPO / "engineering/v2/V2_PHASEC_FREEZE.md").read_text()
    bad = []
    for want, name in re.findall(r"^([0-9a-f]{64})\s+(\S+)", freeze, flags=re.M):
        if name == "V2_PHASEC_COMPUTE.json":
            continue
        p = REPO / "engineering/v2" / name
        if not p.exists() or sha(p) != want:
            bad.append(name)
    out["phase_c_freeze_record_differing"] = bad
    sealed = {}
    for rel in ("research/consequence/phase32/SHA256_MANIFEST32.json",
                "research/phase4/SHA256_MANIFEST4.json",
                "research/phase5/SHA256_MANIFEST5.json"):
        m = json.loads((REPO / rel).read_text())
        sealed[rel] = [p for p, h in m["files"].items() if sha(REPO / p) != h]
    out["sealed_phase_manifests_differing"] = sealed
    dec = (PREV / "PROMOTION_DECISION.md").read_text().split("## Decision", 1)[1]
    tokens = re.findall(r"SEMANTIC_2_1_[A-Z_]+", dec)
    out["promotion_token"] = sorted(set(tokens))
    out["failure_ledger_matches_pinned"] = sha(
        REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == LEDGER_PINNED
    import yaml
    text = (PREV / "PROPOSED_LEDGER_ENTRIES.md").read_text()
    block = text.split("```yaml\n", 1)[1].split("\n```", 1)[0]
    ents = yaml.safe_load("entries:\n" + block)["entries"]
    out["proposed_ledger_entries"] = [e["id"] for e in ents]
    ok = (all(out["frozen_v2_reasoning_files"].values())
          and out["commits_touching_csia_v2_since_freeze"] == ["f00d315"]
          and out["csia_v2_changed_since_phase_a_lock"] == "none"
          and out["semantic_audit_results_sha_matches"]
          and out["xsys_result_manifest_matches_seal"]
          and not out["xsys_result_manifest_files_differing"]
          and all(out["xsys_protocol_chain_manifests_unchanged"].values())
          and out["xsys_stage1_matches_seal"]
          and not out["phase_c_freeze_record_differing"]
          and not any(sealed.values())
          and out["promotion_token"] == ["SEMANTIC_2_1_READY_FOR_SHADOW"]
          and out["failure_ledger_matches_pinned"]
          and out["proposed_ledger_entries"] == [f"FL-0{k}" for k in range(54, 61)])
    out["STATE_AS_EXPECTED"] = ok
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1, sort_keys=True))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
