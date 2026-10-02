#!/usr/bin/env python3
"""RB-001 Phase 0: lock the accepted CSIA 2.3 state. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/verify_rb001_baseline.py [--final]

Writes BASELINE_RB001.json (FINAL_STATE_RB001.json with --final) and nothing
else. The earlier verifiers' functions are imported and re-executed; their
result files are not rewritten.

| check | how |
|---|---|
| 2.3 commit | 0f9222c is an ancestor of HEAD |
| no architecture expansion | `csia_evidence_assurance/`, `csia_semantic_core/`, `csia/` identical to 0f9222c |
| historical results | the 2.3 package (including the validation-flight outcomes), both 2.2 packages and their tests identical to 0f9222c |
| Semantic Core 2.1.1, frozen v2.0 | as in the 2.3 verifier |
| 2.1.1 governance, XSYS-001 55/55 gate, Phase C | the revision's gate functions |
| 2.2, pilot and 2.3 tests | the three test files pass |
| ledger | SHA pinned |
"""
from __future__ import annotations

import json
import sys

import common_rb as C
import verify_pilot_baseline as VP

OUT = C.HERE / "BASELINE_RB001.json"
FINAL = C.HERE / "FINAL_STATE_RB001.json"


def main():
    final = "--final" in sys.argv
    import subprocess
    out = {"phase": "RB-001 final state" if final else "RB-001 Phase 0 baseline",
           "head": C.git("rev-parse", "--short", "HEAD")}
    r = subprocess.run(["git", "merge-base", "--is-ancestor", C.ACCEPTED_2_3, "HEAD"], cwd=C.REPO)
    out["ancestry"] = dict(VP.ancestry(), **{C.ACCEPTED_2_3: r.returncode == 0})
    out["product_code_changed_since_2_3"] = VP.unchanged(
        C.ACCEPTED_2_3, "csia_evidence_assurance", "csia_semantic_core", "csia")
    out["historical_results_changed_since_2_3"] = VP.unchanged(
        C.ACCEPTED_2_3, "research/csia_2_3_stock_bridge", "research/csia_2_2_offboard_pilot",
        "research/csia_2_2_evidence_assurance", "tests/test_evidence_assurance_2_2.py",
        "tests/test_csia_2_2_pilot.py", "tests/test_csia_2_3_stock_bridge.py")
    out["semantic_core_changed_since_2_1_1"] = VP.unchanged(VP.C.SEMANTIC_2_1_1, "csia_semantic_core")
    out["frozen_v2_changed_since_2_2"] = VP.unchanged(VP.C.ACCEPTED_2_2, "csia")
    out["ledger_matches_pinned"] = C.sha(
        C.REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == VP.C.LEDGER_PINNED
    out["gates_2_1_1"] = VP.gates_2_1_1()
    out["tests_2_2"] = VP.pytest_file("tests/test_evidence_assurance_2_2.py")
    out["tests_pilot"] = VP.pytest_file("tests/test_csia_2_2_pilot.py")
    out["tests_2_3"] = VP.pytest_file("tests/test_csia_2_3_stock_bridge.py")
    g = out["gates_2_1_1"]
    ok = (all(out["ancestry"].values())
          and out["product_code_changed_since_2_3"] == "none"
          and out["historical_results_changed_since_2_3"] == "none"
          and out["semantic_core_changed_since_2_1_1"] == "none"
          and out["frozen_v2_changed_since_2_2"] == "none"
          and out["ledger_matches_pinned"]
          and g["governance_ok"] and g["xsys_gate_pass"] and g["phase_c_unchanged"]
          and out["tests_2_2"]["ok"] and out["tests_pilot"]["ok"] and out["tests_2_3"]["ok"])
    out["FINAL_STATE_RB001_OK" if final else "BASELINE_RB001_LOCKED"] = ok
    C.write_json(FINAL if final else OUT, out)
    print(json.dumps(out, indent=1, default=str)[:3000])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
