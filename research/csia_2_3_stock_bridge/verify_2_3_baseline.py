#!/usr/bin/env python3
"""Phase 0 of CSIA 2.3: lock the accepted pilot state. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/verify_2_3_baseline.py [--final]

Writes BASELINE_2_3.json (or FINAL_STATE_2_3.json with --final), nothing
else. The pilot's own checks are imported from `verify_pilot_baseline.py`
and re-executed; its result files are not rewritten.

| check | how |
|---|---|
| pilot commit | 5eb7f02 is an ancestor of HEAD |
| nothing moved since the pilot (Phase 0 only) | `csia_evidence_assurance/`, `csia_semantic_core/`, both 2.2 packages and their tests identical to 5eb7f02 |
| Semantic Core 2.1.1 | `csia_semantic_core/` identical to 2b2adcc |
| frozen v2.0, earlier 2.2 package | unchanged since 4fb191e |
| 2.1.1 governance, XSYS 55/55 gate, Phase C | the revision's verifier and gate functions |
| 2.2 and pilot tests (WA-1, WA-2, WA-3, FV-1, pinned report hashes) | both test files pass |
| 2.2 replays | scenario corpus, XSYS, E1 and receipts equal to the committed results |
| profile and contracts | r2 ACCEPTED; contract digests |
| 66-flight batch | every flight log re-analysed with the 2.2 estimator path; each `report.json` equal to the pilot's `batch_index.json` hash (Phase 0 only) |
| provenance | `test_the_build_provenance_describes_this_checkout` passes |
"""
from __future__ import annotations

import json
import subprocess
import sys

import common_23 as C
import verify_pilot_baseline as VP

OUT = C.HERE / "BASELINE_2_3.json"
FINAL = C.HERE / "FINAL_STATE_2_3.json"


def batch_66():
    from csia_evidence_assurance import report as R
    from csia_evidence_assurance import runs
    idx = json.loads((C.PILOT / "batch/batch_index.json").read_text())["inputs"]
    want = {r["input"]: r["report_sha256"] for r in idx}
    same, diff = 0, []
    import hashlib
    for name, h in sorted(want.items()):
        run = runs.ulog(C.RAW_FLIGHTS / f"{name}.ulg", 0.1)
        body = R.dumps(R.machine_report(run.results, run.inputs, run.gate, run.contracts))
        if hashlib.sha256(body).hexdigest() == h:
            same += 1
        else:
            diff.append(name)
    return {"flights": len(want), "identical": same, "different": diff}


def provenance_test():
    p = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-p",
                        "no:cacheprovider", "tests/test_post_e1_hardening_round2.py", "-k",
                        "provenance"], cwd=C.REPO, capture_output=True, text=True)
    return {"ok": p.returncode == 0, "tail": p.stdout.strip().splitlines()[-1:]}


def main():
    final = "--final" in sys.argv
    out = {"phase": "2.3 final state" if final else "2.3 Phase 0 baseline",
           "head": C.git("rev-parse", "--short", "HEAD")}
    r = subprocess.run(["git", "merge-base", "--is-ancestor", C.ACCEPTED_PILOT, "HEAD"], cwd=C.REPO)
    out["ancestry"] = dict(VP.ancestry(), **{C.ACCEPTED_PILOT: r.returncode == 0})
    out["semantic_core_changed_since_2_1_1"] = VP.unchanged(VP.C.SEMANTIC_2_1_1, "csia_semantic_core")
    out["frozen_v2_changed_since_2_2"] = VP.unchanged(VP.C.ACCEPTED_2_2, "csia")
    out["previous_2_2_package_changed"] = VP.unchanged(VP.C.ACCEPTED_2_2,
                                                       "research/csia_2_2_evidence_assurance")
    out["pilot_package_changed_since_pilot"] = VP.unchanged(C.ACCEPTED_PILOT,
                                                            "research/csia_2_2_offboard_pilot")
    if not final:
        out["code_changed_since_pilot"] = VP.unchanged(
            C.ACCEPTED_PILOT, "csia_evidence_assurance", "csia_semantic_core",
            "tests/test_evidence_assurance_2_2.py", "tests/test_csia_2_2_pilot.py")
    out["ledger_matches_pinned"] = C.sha(
        C.REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == VP.C.LEDGER_PINNED
    out["gates_2_1_1"] = VP.gates_2_1_1()
    out["tests_2_2"] = VP.pytest_file("tests/test_evidence_assurance_2_2.py")
    out["tests_pilot"] = VP.pytest_file("tests/test_csia_2_2_pilot.py")
    out["replays"] = VP.replays()
    out["profile_and_contracts"] = VP.profile_and_contracts()
    out["dataset_reports_match"] = VP.dataset_reports()
    if not final:
        out["batch_66"] = batch_66()
    out["provenance"] = provenance_test()
    g, rp, pc = out["gates_2_1_1"], out["replays"], out["profile_and_contracts"]
    ok = (all(out["ancestry"].values())
          and out["semantic_core_changed_since_2_1_1"] == "none"
          and out["frozen_v2_changed_since_2_2"] == "none"
          and out["previous_2_2_package_changed"] == "none"
          and out["pilot_package_changed_since_pilot"] == "none"
          and out.get("code_changed_since_pilot", "none") == "none"
          and out["ledger_matches_pinned"]
          and g["governance_ok"] and g["xsys_gate_pass"] and g["phase_c_unchanged"]
          and out["tests_2_2"]["ok"] and out["tests_pilot"]["ok"]
          and rp["v2_corpus_equal"] and rp["xsys_equal"] and rp["receipts_equal"] and rp["e1_equal"]
          and pc["r2_gate"] == "ACCEPTED"
          and all(out["dataset_reports_match"].values())
          and (final or out["batch_66"]["identical"] == 66)
          and out["provenance"]["ok"])
    out["BASELINE_2_3_LOCKED" if not final else "FINAL_STATE_2_3_OK"] = ok
    C.write_json(FINAL if final else OUT, out)
    print(json.dumps({k: v for k, v in out.items() if k != "profile_and_contracts"},
                     indent=1, default=str)[:4000])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
