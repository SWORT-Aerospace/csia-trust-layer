#!/usr/bin/env python3
"""Phase 0 of CSIA 2.2: verify the accepted 2.1.1 baseline. RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_evidence_assurance/verify_baseline_2_2.py [--final]

Checks, writing only BASELINE_2_2.json (or FINAL_STATE_2_2.json):
  - every governance check of the 2.1.1 revision's own verifier (frozen v2,
    audit, XSYS manifests and seals, Phase C, sealed manifests, ledger,
    promotion tokens, shadow package unchanged), imported and re-run;
  - the revision package and its decision token unchanged since it was
    accepted (READY_AS_BASELINE);
  - R-1, R-2 and R-3 present and active in Corrections.revised();
    successor profile r2 by digest; the validator has PV1-PV9;
  - the 2.1 (50), shadow (51) and revision (75) test files pass;
  - the XSYS hard gate and the Phase C gate under 2.1.1, re-executed through
    the revision package's own gate functions;
  - the accepted headline numbers in the revision's committed results;
  - build provenance describes this checkout.
If anything differs, the phase must not proceed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

import common_2_2 as C

OUT = C.HERE / "BASELINE_2_2.json"
FINAL = C.HERE / "FINAL_STATE_2_2.json"


def run_tests():
    out = {}
    for f, want in (("tests/test_semantic_core_2_1.py", 50),
                    ("tests/test_semantic_core_2_1_shadow.py", 51),
                    ("tests/test_semantic_core_2_1_revision.py", 75)):
        p = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q",
                            "-p", "no:cacheprovider", f], cwd=C.REPO,
                           capture_output=True, text=True)
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]
        m = re.search(r"(\d+) passed", tail)
        out[f] = {"summary": tail, "passed": int(m.group(1)) if m else 0,
                  "expected": want, "ok": p.returncode == 0 and m is not None
                  and int(m.group(1)) == want}
    p = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q",
                        "-p", "no:cacheprovider", "tests/test_post_e1_hardening_round2.py",
                        "-k", "build_provenance"], cwd=C.REPO, capture_output=True, text=True)
    out["build_provenance"] = {"ok": p.returncode == 0,
                               "summary": p.stdout.strip().splitlines()[-1]}
    return out


def main():
    final = "--final" in sys.argv
    import verify_baseline as VB  # the revision's verifier
    out = {"phase": "2.2 final state" if final else "2.2 Phase 0 baseline"}
    gov = VB.governance_state()
    out["governance_2_1_1_checks_ok"] = VB.governance_ok(gov)
    out["governance"] = {k: v for k, v in gov.items()
                         if k not in ("semantic_core_2_1_file_sha256",)}
    out["revision_package_changed_since_acceptance"] = C.git(
        "diff", "--stat", C.REVISION_HEAD, "--",
        "research/csia_semantic_core_2_1_revision") or "none"
    out["semantic_core_changed_since_acceptance"] = C.git(
        "diff", "--stat", C.REVISION_HEAD, "--", "csia_semantic_core") or "none"
    rev = (C.REVISION / "PROMOTION_REVIEW.md").read_text().split("## Decision", 1)[1]
    out["revision_token"] = re.findall(r"\*\*(SEMANTIC_2_1_[A-Z_]+)\*\*", rev)[:1]
    from csia_semantic_core import Corrections
    from csia_semantic_core.profile_overlay import load_successor
    r = Corrections.revised()
    out["revisions_active"] = {"R1_fault_policy_b": r.fault_policy_b,
                               "R2_pacing_inputs": r.pacing_inputs,
                               "R3_config_epoch": r.config_epoch,
                               "default_is_2_1_0": not Corrections().is_revised}
    out["successor_r2_digest"] = load_successor("aircraft_successor_r2").digest()
    src = (C.REPO / "csia_semantic_core/profile_validator.py").read_text()
    out["validator_rules"] = sorted(set(re.findall(r"\"(PV\d)_", src)))
    def j(name):
        return json.loads((C.REVISION / name).read_text())
    d = j("DATASET_A_THREE_WAY.json")["phase4_rev_r2_vs_v2_0_shadow_classifier"]
    f = j("FAULT_REPLAY_RESULTS.json")
    t = j("TRANSITION_REPLAY_RESULTS.json")["configurations"]
    out["accepted_results"] = {
        "dataset_A_categories": d["categories"],
        "fault_injections": f["PRE"]["injections"],
        "fault_created_supported_pre_post": [
            f["PRE"]["per_policy"]["A"]["fault_created_supported"],
            f["R1_ONLY"]["per_policy"]["B_IMPLEMENTED"]["fault_created_supported"]],
        "E1_stale_ticks_pre_post": [t["PRE_2_1_0"]["stale_position_symptom_ticks"],
                                     t["REVISED_2_1_1"]["stale_position_symptom_ticks"]]}
    import governance_gates as GG
    xs = GG.xsys(True)
    out["xsys_2_1_1"] = xs
    out["xsys_gate_pass"] = GG.xsys_ok(xs)
    import semantic_probe as P
    from csia.v2.profiles import SCENARIOS
    from csia.v2.profiles.matched_scenarios import MATCHED_SETS
    runs = {n: P.run_scenario(SCENARIOS[n]) for m in MATCHED_SETS.values() for n in m}
    pc = GG.phase_c(runs, r, load_successor("aircraft_successor_r2"))
    committed = json.loads((C.REPO / "engineering/v2/V2_PHASEC_GATE.json").read_text())
    out["phase_c_2_1_1_r2"] = pc
    out["phase_c_unchanged"] = (pc["verdict"] == committed["verdict"] and pc["qualifying"] == {
        q["set"]: q["answers"] for q in committed["qualifying_sets"]})
    out["tests"] = run_tests()
    a = out["accepted_results"]
    ok = (out["governance_2_1_1_checks_ok"]
          and out["revision_package_changed_since_acceptance"] == "none"
          and out["semantic_core_changed_since_acceptance"] == "none"
          and out["revision_token"] == ["SEMANTIC_2_1_READY_AS_BASELINE"]
          and all(v for k, v in out["revisions_active"].items())
          and out["successor_r2_digest"] == C.SUCCESSOR_R2_DIGEST
          and out["validator_rules"] == [f"PV{i}" for i in range(1, 10)]
          and a["dataset_A_categories"] == {"CONSERVATIVE_WITHHOLD": 197, "CORRECTNESS_FIX": 273}
          and a["fault_injections"] == 68640
          and a["fault_created_supported_pre_post"] == [168, 0]
          and a["E1_stale_ticks_pre_post"] == [9, 0]
          and out["xsys_gate_pass"] and out["phase_c_unchanged"]
          and all(v["ok"] for v in out["tests"].values()))
    out["BASELINE_AS_ACCEPTED"] = ok
    C.write_json(FINAL if final else OUT, out)
    print(json.dumps({k: v for k, v in out.items() if k != "governance"}, indent=1, default=str)[:4000])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
