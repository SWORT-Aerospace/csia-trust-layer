#!/usr/bin/env python3
"""Phase 0: lock the starting state and reproduce the three blockers.
RESEARCH ONLY, read-only except for its own output.

    .venv/bin/python research/csia_semantic_core_2_1_revision/verify_baseline.py [--skip-tests]

Run before any revision code was written, and again at the end of the phase
(`--final`), when the governance checks must still hold and the blockers
must still reproduce on the PRE-REVISION configuration (2.1.1's revisions
are off by default, so 2.1.0 is still what `Corrections()` gives).

Checks:
  - frozen v2 reasoning files against the Phase A lock; no csia/v2 change;
  - the semantic-audit results hash;
  - XSYS-001: result manifest against its seal, every file it lists, the
    protocol chain (XSYS-001, A1, A2), Stage 1 against its seal;
  - Phase C freeze record and the three sealed-phase manifests;
  - the 2.1 implementation package's promotion token (READY_FOR_SHADOW) and
    the shadow package's (REQUIRES_REVISION);
  - the successor profile r1 digest;
  - the shadow package unchanged since its commit;
  - the failure ledger against its pinned hash, and the seven held entries;
  - tests/test_semantic_core_2_1.py (50) and
    tests/test_semantic_core_2_1_shadow.py (51) pass;
  - B1: 2.1.0 under policy A lets one predicate fault create 168 wrong
    SUPPORTED (and the whole reference table reproduces);
  - B2: with R5, R5a or R5b, the IMU pacing-loss counterfactual (W7) gives
    SUPPORTED COMPUTE/process_stall;
  - B3: E1 without validity management gives 9 stale POSITION_UNAVAILABLE
    ticks.

Writes BASELINE_LOCK.json (or FINAL_STATE_CHECK.json with --final).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

import revision_common as RC
from revision_common import REPO, sha, git

OUT = RC.HERE / "BASELINE_LOCK.json"
FINAL_OUT = RC.HERE / "FINAL_STATE_CHECK.json"
AUDIT_RESULTS_SHA = "aa85657795011fe9ed31db1777e84f38fd48b2cdec7115935e24f6b561a6a9b0"


def governance_state() -> dict:
    out = {}
    lock = json.loads((RC.PREV / "PHASE_A_CHARACTERIZATION_LOCK.json").read_text())
    out["frozen_v2_reasoning_files"] = {
        p: sha(REPO / p) == h for p, h in lock["frozen_reasoning_file_sha256"].items()}
    out["commits_touching_csia_v2_since_freeze"] = git(
        "log", "--format=%h", "50c5d3576e9084e7c2789167628392c5de992b6f..HEAD",
        "--", "csia/v2").split()
    out["csia_v2_changed_since_phase_a_lock"] = git(
        "diff", "--stat", lock["head_commit"], "--", "csia/v2") or "none"
    out["semantic_audit_results_sha_matches"] = sha(
        REPO / "research/csia_semantic_correctness/semantic_probe_results.json") == AUDIT_RESULTS_SHA
    out["semantic_audit_dir_changed_since_shadow"] = git(
        "diff", "--stat", RC.SHADOW_HEAD, "--", "research/csia_semantic_correctness") or "none"
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
    dec = (RC.PREV / "PROMOTION_DECISION.md").read_text().split("## Decision", 1)[1]
    out["implementation_promotion_token"] = sorted(set(re.findall(r"SEMANTIC_2_1_[A-Z_]+", dec)))
    rev = (RC.SHADOW / "PROMOTION_REVIEW.md").read_text().split("## Decision", 1)[1]
    out["shadow_promotion_token"] = re.findall(r"\*\*(SEMANTIC_2_1_[A-Z_]+)\*\*", rev)
    out["implementation_package_changed_since_shadow"] = git(
        "diff", "--stat", RC.SHADOW_HEAD, "--", "research/csia_semantic_core_2_1") or "none"
    out["shadow_package_commit"] = git("log", "-1", "--format=%H", "--",
                                       "research/csia_semantic_core_2_1_shadow")
    out["shadow_package_changed_since_its_commit"] = git(
        "diff", "--stat", RC.SHADOW_PACKAGE_COMMIT, "--",
        "research/csia_semantic_core_2_1_shadow") or "none"
    out["shadow_package_file_sha256"] = {
        p.name: sha(p) for p in sorted(RC.SHADOW.iterdir()) if p.is_file()}
    from csia_semantic_core.profile_overlay import load_successor
    out["successor_r1_digest"] = load_successor().digest()
    out["failure_ledger_matches_pinned"] = sha(
        REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == RC.LEDGER_PINNED
    import yaml
    text = (RC.PREV / "PROPOSED_LEDGER_ENTRIES.md").read_text()
    block = text.split("```yaml\n", 1)[1].split("\n```", 1)[0]
    out["proposed_ledger_entries"] = [e["id"] for e in yaml.safe_load("entries:\n" + block)["entries"]]
    out["semantic_core_2_1_last_commit"] = git("log", "-1", "--format=%H", "--", "csia_semantic_core")
    out["semantic_core_2_1_file_sha256"] = {
        p.name: sha(p) for p in sorted((REPO / "csia_semantic_core").glob("*.py"))}
    out["head"] = git("rev-parse", "--short", "HEAD")
    return out


def governance_ok(out) -> bool:
    return (all(out["frozen_v2_reasoning_files"].values())
            and out["commits_touching_csia_v2_since_freeze"] == ["f00d315"]
            and out["csia_v2_changed_since_phase_a_lock"] == "none"
            and out["semantic_audit_results_sha_matches"]
            and out["semantic_audit_dir_changed_since_shadow"] == "none"
            and out["xsys_result_manifest_matches_seal"]
            and not out["xsys_result_manifest_files_differing"]
            and all(out["xsys_protocol_chain_manifests_unchanged"].values())
            and out["xsys_stage1_matches_seal"]
            and not out["phase_c_freeze_record_differing"]
            and not any(out["sealed_phase_manifests_differing"].values())
            and out["implementation_promotion_token"] == ["SEMANTIC_2_1_READY_FOR_SHADOW"]
            and out["shadow_promotion_token"] == ["SEMANTIC_2_1_REQUIRES_REVISION"]
            and out["implementation_package_changed_since_shadow"] == "none"
            and out["shadow_package_commit"] == RC.SHADOW_PACKAGE_COMMIT
            and out["shadow_package_changed_since_its_commit"] == "none"
            and out["successor_r1_digest"] == RC.SUCCESSOR_R1_DIGEST
            and out["failure_ledger_matches_pinned"]
            and out["proposed_ledger_entries"] == [f"FL-0{k}" for k in range(54, 61)])


def run_tests() -> dict:
    out = {}
    for f in ("tests/test_semantic_core_2_1.py", "tests/test_semantic_core_2_1_shadow.py"):
        p = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-p", "no:cacheprovider", f],
                           cwd=REPO, capture_output=True, text=True)
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-300:]
        m = re.search(r"(\d+) passed", tail)
        failed = re.search(r"(\d+) failed", tail)
        out[f] = {"exit": p.returncode, "summary": tail,
                  "passed": int(m.group(1)) if m else 0,
                  "failed": int(failed.group(1)) if failed else 0}
    return out


def blocker_b1() -> dict:
    import fault_replay as FR
    got = FR.run_pre()
    prev = json.loads((RC.SHADOW / "PREDICATE_FAULT_RESULTS.json").read_text())
    keys = ("pairs", "graded", "wrong", "new_wrong", "fault_created_supported",
            "supported_resting_on_failed_refuter", "correct_supported_clean",
            "correct_supported_lost", "attr_new_wrong_unique",
            "attr_correct_unique_clean", "attr_correct_unique_lost",
            "ticks_with_any_conclusion_lost", "fault_evaluated", "fault_visible")
    diff = {p: {k: [prev["per_policy"][p][k], got["per_policy"][p][k]]
                for k in keys if prev["per_policy"][p][k] != got["per_policy"][p][k]}
            for p in FR.REF_POLICIES}
    return {"injections": got["injections"],
            "policy_A_fault_created_supported": got["per_policy"]["A"]["fault_created_supported"],
            "policy_B_reference_fault_created_supported": got["per_policy"]["B"]["fault_created_supported"],
            "per_policy": {p: {k: got["per_policy"][p][k] for k in keys} for p in FR.REF_POLICIES},
            "differences_from_shadow_package": {p: d for p, d in diff.items() if d},
            "seconds": got["seconds"]}


def blocker_b2() -> dict:
    import shadow_validation as S
    import worse_answer_search as W
    from dataclasses import replace
    from csia.v2.evidence import ObservationState as OS
    from csia_semantic_core import SemanticCore21
    import semantic_probe as P
    from csia.v2.profiles import SCENARIOS
    engine, res = P.run_scenario(SCENARIOS["PROCESS_STALL"])
    recs = tuple(replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",),
                         detail=dict(r.detail, fresh=False, missing_reason="stale"))
                 if r.component == "source.imu0" else r for r in res[-1].records)
    core = SemanticCore21.from_engine(engine, trace=False)
    out = {}
    l0, _ = W.v20(engine, recs)
    out["v2_0"] = [(x.verdict, list(x.supported)) for x in l0
                   if x.symptom == "OUTPUT_MISSING" and x.subject == "state_estimator"]
    for label, ov in (("2_1_0", None), ("2_1_0_r1", None), ("R5", S.overlay("R5")),
                      ("R5a", S.overlay("R5a")), ("R5b", S.overlay("R5b"))):
        if label == "2_1_0_r1":
            from csia_semantic_core.profile_overlay import load_successor
            ov = load_successor()
        tr = core.reason(ov.apply(recs) if ov else recs)
        out[label] = [(x.v2.verdict, list(x.supported), list(x.unresolved))
                      for x in tr.localizations
                      if x.symptom == "OUTPUT_MISSING" and x.subject == "state_estimator"]
    out["reproduced"] = all(out[k] and out[k][0][0] == "SUPPORTED"
                            and out[k][0][1] == ["COMPUTE/process_stall"]
                            for k in ("R5", "R5a", "R5b")) and out["2_1_0"][0][0] != "SUPPORTED"
    return out


def blocker_b3() -> dict:
    import transition_study as T
    from csia_semantic_core import SemanticCore21
    import semantic_probe as P
    from csia.v2.profiles import SCENARIOS
    design = T.load_design()
    ticks = T.stream(design)
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    core = SemanticCore21.from_engine(engine, trace=True)
    out = {}
    for policy in ("C_NONE", "B_STATE_EPOCH"):
        stale, stale_ticks = 0, []
        for t, lane, recs, meta in ticks:
            admitted, _s, _o = T.admit(policy, t, lane, recs, meta)
            ag, pos, should = T.grade(design, t, core.reason(admitted))
            if pos and not should:
                stale += 1
                stale_ticks.append(t)
        out[policy] = {"stale_position_symptom_ticks": stale, "ticks": stale_ticks}
    out["reproduced"] = (out["C_NONE"]["stale_position_symptom_ticks"] == 9
                         and out["B_STATE_EPOCH"]["stale_position_symptom_ticks"] == 0)
    return out


def main():
    final = "--final" in sys.argv
    out = {"phase": "final state check" if final else "Phase 0 baseline lock"}
    out["governance"] = governance_state()
    out["governance_ok"] = governance_ok(out["governance"])
    if "--skip-tests" not in sys.argv:
        out["tests"] = run_tests()
    out["B1_policy_A_fault_created_supported"] = blocker_b1()
    out["B2_g2_pacing_counterfactual"] = blocker_b2()
    out["B3_e1_stale_ticks"] = blocker_b3()
    b1 = out["B1_policy_A_fault_created_supported"]
    tests_ok = "tests" not in out or (
        out["tests"]["tests/test_semantic_core_2_1.py"]["passed"] == 50
        and out["tests"]["tests/test_semantic_core_2_1_shadow.py"]["passed"] == 51
        and all(v["failed"] == 0 for v in out["tests"].values()))
    out["blockers_reproduced"] = {
        "B1": b1["policy_A_fault_created_supported"] == 168
              and not b1["differences_from_shadow_package"],
        "B2": out["B2_g2_pacing_counterfactual"]["reproduced"],
        "B3": out["B3_e1_stale_ticks"]["reproduced"]}
    ok = out["governance_ok"] and tests_ok and all(out["blockers_reproduced"].values())
    out["tests_ok"] = tests_ok
    out["BASELINE_AS_EXPECTED"] = ok
    if not ok:
        out["token_if_not_ok"] = "SEMANTIC_2_1_REVISION_BASELINE_MISMATCH"
    RC.write_json(FINAL_OUT if final else OUT, out)
    print(json.dumps({k: v for k, v in out.items() if k != "governance"}, indent=1, default=str)[:5000])
    print("governance_ok", out["governance_ok"])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
