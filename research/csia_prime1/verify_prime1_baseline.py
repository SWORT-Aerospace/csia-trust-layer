#!/usr/bin/env python3
"""CSIA PRIME-1 Phase 1: lock the accepted PRIME state, reproduce both defects. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/verify_prime1_baseline.py [--final]

Writes BASELINE_PRIME1.json (FINAL_STATE_PRIME1.json with --final) and nothing
else. The earlier verifiers' functions are imported and re-executed; their
result files are not rewritten.

| check | how |
|---|---|
| accepted state | PRIME's head babed68 (and RB-001's 16e19d4) are ancestors of HEAD |
| product code | identical to babed68; at --final, every changed file is a documented PRIME-1 change (PRIME1_CHANGES) |
| historical results | the 2.2, pilot, 2.3, RB-001 and PRIME packages and their test files identical to babed68 |
| Semantic Core 2.1.1, frozen v2.0, ledger, XSYS gate, Phase C | as in the earlier verifiers |
| tests | the 2.2, pilot, 2.3, RB-001 and PRIME test files pass (PRIME's two strict expected-fails pin the historical defects) |
| 2.3 reports | the product regenerates 2.3's committed V1, V9, V13 reports byte for byte (`analyze`) |
| PRIME sample reports | the 11 committed PRIME sample outputs regenerate byte for byte (`assure`; `--release prime` at --final) |
| PRIME-A run | every one of the 39 logs analysed without a crash; three logs twice, identical |
| PRIME-E bundle | every member of the as-built PRIME pilot zip matches `PILOT_BUNDLE.json` |
| defects | D-PRIME-1 and D-PRIME-2 reproduce on the historical path (if not: PRIME1_BASELINE_MISMATCH) |
"""
from __future__ import annotations

import filecmp
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import common_prime1 as C
import reproductions as RX
import verify_pilot_baseline as VP
import verify_prime_baseline as VPR

OUT = C.HERE / "BASELINE_PRIME1.json"
FINAL = C.HERE / "FINAL_STATE_PRIME1.json"
#: Product files PRIME-1 may change, each with the defect or workflow it answers.
PRIME1_CHANGES: dict = {
    "csia_evidence_assurance/releases.py": "versioned releases: 2.3 (historical) and prime1 (successor)",
    "csia_evidence_assurance/admissibility.py": "D-PRIME-1: integer-tick comparisons at the declared resolution "
                                                "(only when a resolution is set; 2.3 unchanged)",
    "csia_evidence_assurance/analyzer.py": "D-PRIME-1: passes the release's time resolution to the gate",
    "csia_evidence_assurance/stock_log.py": "D-PRIME-1: canonical integer-microsecond timebase (successor only)",
    "csia_evidence_assurance/stock_stats.py": "D-PRIME-2: the excess deviation (d_tel_excess), additive",
    "csia_evidence_assurance/events.py": "D-PRIME-2 and Phases 6-9: discover_prime1 (deficit/excess arms, "
                                         "ESC offline, gated compensation, merge, harness messages ignored); "
                                         "discover() for 2.3 unchanged",
    "csia_evidence_assurance/adapters/px4_stock.py": "D-PRIME-2: telemetry baseline-validity condition and level "
                                                     "notices (successor only)",
    "csia_evidence_assurance/runs.py": "stock_flight(release=...): the successor path; 2.3 the default",
    "csia_evidence_assurance/contracts/stock_esc_telemetry_response_prime1.json": "D-PRIME-2: the successor's "
                                                                                  "telemetry contract",
    "csia_evidence_assurance/support_prime1.py": "Phases 13-15: support decided before interpretation",
    "csia_evidence_assurance/support_contract_prime1.json": "Phase 15: the support matrix as a product contract",
    "csia_evidence_assurance/view_prime1.py": "Phases 16-17: receipts and the engineer-first page",
    "csia_evidence_assurance/assure_prime1.py": "the prime1 assure path (support first; withheld or full)",
    "csia_evidence_assurance/engagement.py": "Phase 27: the local engagement workflow",
    "csia_evidence_assurance/__main__.py": "assure --release {prime1,prime}; the engagement subcommand",
    "csia_evidence_assurance/assure_cli.py": "csia-assure forwards the engagement subcommand",
    "pyproject.toml": "D-PRIME-3: package data covers every product JSON file; the support contract",
}
HISTORICAL = ("research/csia_2_3_stock_bridge", "research/csia_2_2_offboard_pilot",
              "research/csia_2_2_evidence_assurance", "research/rb001_reality_bridge",
              "research/csia_prime",
              "tests/test_evidence_assurance_2_2.py", "tests/test_csia_2_2_pilot.py",
              "tests/test_csia_2_3_stock_bridge.py", "tests/test_rb001_reality_bridge.py",
              "tests/test_csia_prime.py")
SAMPLE_KEEP = ("assurance_summary.txt", "support.json", "alerts.json", "receipts.json",
               "coverage_states.json", "report.txt", "manifest.json")


def same_output(a: Path, b: Path) -> bool:
    """Byte-identical, except that manifest.json's `code` field (the tree digest of the
    product package at run time, `report.code_digests`) is excluded: it changes whenever any
    file in the package changes, including successor-only files the historical path never
    runs. Every other byte of every output must match."""
    if a.name != "manifest.json":
        return filecmp.cmp(a, b, shallow=False)
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    ja.pop("code", None)
    jb.pop("code", None)
    return ja == jb


def sample_reports(release=None) -> dict:
    """PRIME's 11 sample outputs, regenerated and compared file by file (`same_output`)."""
    import sample_reports as SR
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for name, path, _kind, _what in SR.CASES:
            d = Path(td) / name
            r = RX.assure(path, d, release)
            committed = C.PRIME / "sample_reports" / name
            same = r.returncode == 0 and all(
                same_output(d / f, committed / f) for f in SAMPLE_KEEP if (committed / f).exists())
            out[name] = same
    return out


def prime_a_run(release=None) -> dict:
    """The 39-log no-crash run and the three-log determinism check of PRIME-A."""
    import prime_a_gate as PA
    res = {"no_crash": {}, "determinism": {}}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for p in PA.logs():
            r = RX.assure(p, td / "nc" / p.stem, release)
            res["no_crash"][p.name] = r.returncode
        for p in (C.SITL_2_3 / "V1.ulg", C.REAL_PX4_DOCS, C.PILOT_S1):
            a, b = td / "d1" / p.stem, td / "d2" / p.stem
            RX.assure(p, a, release)
            RX.assure(p, b, release)
            names = sorted(f.name for f in a.iterdir())
            res["determinism"][p.name] = all(filecmp.cmp(a / n, b / n, shallow=False) for n in names)
    return {"logs": len(res["no_crash"]), "crashed": sorted(k for k, v in res["no_crash"].items() if v),
            "deterministic": all(res["determinism"].values()), "determinism": res["determinism"]}


def prime_bundle() -> dict:
    rec = json.loads((C.PRIME / "PILOT_BUNDLE.json").read_text())
    z = C.PRIME_BUNDLE / "csia_pilot_participant.zip"
    if not z.exists():
        return {"present": False}
    bad = []
    with zipfile.ZipFile(z) as zf:
        for name, digest in rec["participant_files_sha256"].items():
            if hashlib.sha256(zf.read(name)).hexdigest() != digest:
                bad.append(name)
    return {"present": True, "members": len(rec["participant_files_sha256"]), "mismatched": bad}


def prime_e_artifacts() -> dict:
    need = ["EXTERNAL_PILOT_PACKAGE.md", "CLAIM_EVIDENCE_MATRIX.md", "COMMERCIAL_PILOT.md",
            "pilot_package/QUICKSTART.md", "pilot_package/REPORT_GUIDE.md",
            "pilot_package/DIAGNOSTIC_QUESTIONS.md", "pilot_package/FEEDBACK_FORM.md",
            "pilot_package_experimenter/SCORING_RUBRIC.md", "PILOT_BUNDLE.json"]
    return {n: (C.PRIME / n).exists() for n in need}


def _rec(name: str) -> dict:
    p = C.HERE / name
    return json.loads(p.read_text()) if p.exists() else {}


def gates(out: dict) -> dict:
    """PRIME-1 Phase 40, read from the measured artifacts (none is asserted here)."""
    hist, fresh = _rec("HISTORICAL_GATE.json"), _rec("FRESH_INSTALL_PRIME1.json")
    held, bundle, real = _rec("HELDOUT_RESULTS.json"), _rec("PILOT_BUNDLE_PRIME1.json"), _rec("REAL_DATA_READY_CHECK.json")
    p1 = (not out["d_prime_1_prime1"]["reproduces"] and not out["d_prime_2_prime1"]["reproduces"]
          and out["defects_reproduce_on_historical_path"] and bool(hist.get("HISTORICAL_UNCHANGED"))
          and bool(fresh.get("identical_to_repository")) and bool(fresh.get("no_repository_dependency")))
    verdict = (held.get("verdict") or {}).get("verdict")
    return {
        "P1_KNOWN_DEFECTS_CLOSED": {"met": p1, "evidence": "D-PRIME-1/2 gone on prime1 and still reproduced on "
                                    "2.3; HISTORICAL_GATE.json; D-PRIME-3: FRESH_INSTALL_PRIME1.json"},
        "P2_EVENT_DISCOVERY_COMMERCIALLY_USABLE": {"met": verdict == "PROMOTE", "heldout_verdict": verdict,
                                                   "scope": "EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY"},
        "P3_EXTERNAL_PILOT_PACKAGE_READY": {"met": bool(bundle.get("zero_known_leaks")) and bool(bundle.get(
            "all_exit_zero")) and bool(fresh.get("identical_to_repository")),
            "evidence": "PILOT_BUNDLE_PRIME1.json, BLINDNESS_AUDIT.json, FRESH_INSTALL_PRIME1.json"},
        "P4_REAL_DATA_READY": {"met": bool(real.get("REAL_DATA_READY")), "evidence": "REAL_DATA_READY_CHECK.json",
                               "not_shown": real.get("not_shown_here")},
        "P5_PHYSICAL_VALIDATION": {"met": False, "why": "no physical propulsion evidence exists; nothing is "
                                   "PHYSICAL_VALIDATED (support contract)"},
    }


def main():
    final = "--final" in sys.argv
    hist_release = "prime" if final else None
    out = {"phase": "CSIA PRIME-1 final state" if final else "CSIA PRIME-1 Phase 1 baseline",
           "head": C.git("rev-parse", "--short", "HEAD"), "branch": C.git("branch", "--show-current")}
    anc = {}
    for c in (C.PRIME_HEAD, VPR.C.ACCEPTED_RB001):
        anc[c] = subprocess.run(["git", "merge-base", "--is-ancestor", c, "HEAD"],
                                cwd=C.REPO).returncode == 0
    out["ancestry"] = dict(VP.ancestry(), **anc)
    changed = set(C.git("diff", "--name-only", C.PRIME_HEAD, "--",
                        "csia_evidence_assurance", "csia_semantic_core", "csia", "pyproject.toml").split())
    out["product_files_changed_since_prime"] = {f: PRIME1_CHANGES.get(f, "UNDOCUMENTED") for f in sorted(changed)}
    product_ok = (not changed) or (final and changed <= set(PRIME1_CHANGES))
    out["historical_results_changed_since_prime"] = VP.unchanged(C.PRIME_HEAD, *HISTORICAL)
    out["semantic_core_changed_since_2_1_1"] = VP.unchanged(VP.C.SEMANTIC_2_1_1, "csia_semantic_core")
    out["frozen_v2_changed_since_2_2"] = VP.unchanged(VP.C.ACCEPTED_2_2, "csia")
    out["ledger_matches_pinned"] = C.sha(
        C.REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == VP.C.LEDGER_PINNED
    out["prime_decision_sha256"] = C.sha(C.PRIME_DECISION)
    out["gates_2_1_1"] = VP.gates_2_1_1()
    for name, f in (("tests_2_2", "tests/test_evidence_assurance_2_2.py"),
                    ("tests_pilot", "tests/test_csia_2_2_pilot.py"),
                    ("tests_2_3", "tests/test_csia_2_3_stock_bridge.py"),
                    ("tests_rb001", "tests/test_rb001_reality_bridge.py"),
                    ("tests_prime", "tests/test_csia_prime.py")):
        out[name] = VP.pytest_file(f)
    out["reports_reproduced_2_3"] = VPR.reproduce_reports()
    out["prime_sample_reports_reproduced"] = sample_reports(hist_release)
    out["prime_a_run"] = prime_a_run(hist_release)
    out["prime_bundle"] = prime_bundle()
    out["prime_e_artifacts"] = prime_e_artifacts()
    out["d_prime_1"] = RX.d_prime_1("2.3" if final else None)
    out["d_prime_2"] = RX.d_prime_2("2.3" if final else None)
    out["environment"] = VPR.environment()
    g = out["gates_2_1_1"]
    reproduced = out["d_prime_1"]["reproduces"] and out["d_prime_2"]["reproduces"]
    ok = (all(out["ancestry"].values()) and product_ok
          and out["historical_results_changed_since_prime"] == "none"
          and out["semantic_core_changed_since_2_1_1"] == "none"
          and out["frozen_v2_changed_since_2_2"] == "none"
          and out["ledger_matches_pinned"]
          and g["governance_ok"] and g["xsys_gate_pass"] and g["phase_c_unchanged"]
          and g["xsys"]["slots"] == 3872 and g["xsys_primary"]["n_success"] == 55
          and all(out[k]["ok"] for k in ("tests_2_2", "tests_pilot", "tests_2_3", "tests_rb001", "tests_prime"))
          and all(out["reports_reproduced_2_3"].values())
          and all(out["prime_sample_reports_reproduced"].values())
          and not out["prime_a_run"]["crashed"] and out["prime_a_run"]["deterministic"]
          and out["prime_bundle"].get("present") and not out["prime_bundle"]["mismatched"]
          and all(out["prime_e_artifacts"].values()))
    out["defects_reproduce_on_historical_path"] = reproduced
    if final:
        out["d_prime_1_prime1"] = RX.d_prime_1("prime1")
        out["d_prime_2_prime1"] = RX.d_prime_2("prime1")
        out["gates"] = gates(out)
        ok = ok and not out["d_prime_1_prime1"]["reproduces"] and not out["d_prime_2_prime1"]["reproduces"]
    if not reproduced:
        out["decision"] = "PRIME1_BASELINE_MISMATCH"
    out["FINAL_STATE_PRIME1_OK" if final else "BASELINE_PRIME1_LOCKED"] = ok and reproduced
    C.write_json(FINAL if final else OUT, out)
    print(json.dumps({k: out[k] for k in ("head", "branch", "historical_results_changed_since_prime",
                                          "prime_sample_reports_reproduced", "prime_bundle")}, indent=1))
    print("d_prime_1", out["d_prime_1"]["shifts_losing_the_symptom_or_rejecting_evidence"])
    print("d_prime_2", out["d_prime_2"]["synthetic"]["excess_scales_never_reported"],
          out["d_prime_2"]["v10_blinded"].get("what_happened"))
    print("OK", ok, "reproduced", reproduced)
    sys.exit(0 if ok and reproduced else 1)


if __name__ == "__main__":
    main()
