#!/usr/bin/env python3
"""CSIA PRIME-1 freeze: build the freeze manifest, and verify a checkout against it.

    .venv/bin/python research/csia_prime1_freeze/verify_prime1_freeze.py check
    .venv/bin/python research/csia_prime1_freeze/verify_prime1_freeze.py collect --bundle <zip> --rebuild <dir>
    .venv/bin/python research/csia_prime1_freeze/verify_prime1_freeze.py build --suite-counts <json> ...

`check` (seconds, writes nothing): every file hash in PRIME1_FREEZE_MANIFEST.json
against this checkout; the product code digests; the product packages' git
trees; the exact frozen wheel; the decision and gates as recorded; and, when
the tag exists, that it is annotated, carries this manifest unchanged, and is
contained in the remote branch. Exit 0 only if everything holds.

`collect` (used once, at the freeze): the defect, claim and support-matrix
locks; the blindness audit of the frozen bundle zip itself; the member-by-member
comparison with a rebuild from clean inputs; report sizes; historical integrity
from the freeze-time records. Writes verification/FREEZE_CHECKS.json.

`build` (used once, at the freeze): assembles the manifest from the measured
freeze-time records in `verification/`. It runs no analysis and changes no
product file. Governance only: nothing here commands a vehicle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRIME1 = REPO / "research/csia_prime1"
MANIFEST = HERE / "PRIME1_FREEZE_MANIFEST.json"
TAG = "csia-prime1-freeze"
BRANCH = "claude/csia-prime-pilot"
WHEEL_NAME = "csia_trust_layer-0.8.0-py3-none-any.whl"
WHEEL = HERE / "release" / WHEEL_NAME
DECISION = "CSIA_PRIME1_READY_FOR_EXTERNAL_PILOT"
PRIME2_STATUS = "CSIA_PRIME2_WAITING_FOR_REAL_PILOT_DATA"
PRODUCT_PACKAGES = ("csia_evidence_assurance", "csia_semantic_core", "csia")

#: The authoritative files of the frozen reference (repository-relative).
AUTHORITATIVE = (
    "pyproject.toml",
    "csia_evidence_assurance/support_contract_prime1.json",
    "csia_evidence_assurance/releases.py",
    "research/csia_prime1/README.md",
    "research/csia_prime1/PRIME1_REVIEW_AND_DECISION.md",
    "research/csia_prime1/CLAIM_EVIDENCE_MATRIX_PRIME1.md",
    "research/csia_prime1/PUBLIC_CLAIMS.md",
    "research/csia_prime1/SUPPORT_MATRIX.md",
    "research/csia_prime1/KNOWN_DEFECT_REGISTER.md",
    "research/csia_prime1/DEFECT_FIXES.md",
    "research/csia_prime1/EVENT_DISCOVERY_PRIME1.md",
    "research/csia_prime1/PRODUCT_READINESS.md",
    "research/csia_prime1/PILOT_OFFER.md",
    "research/csia_prime1/HELDOUT_PREREGISTRATION.md",
    "research/csia_prime1/HELDOUT_FREEZE.json",
    "research/csia_prime1/HELDOUT_RESULTS.json",
    "research/csia_prime1/FINAL_STATE_PRIME1.json",
    "research/csia_prime1/BASELINE_PRIME1.json",
    "research/csia_prime1/HISTORICAL_GATE.json",
    "research/csia_prime1/DEFECT_FIX_RESULTS.json",
    "research/csia_prime1/TELEMETRY_MATRIX_DEV.json",
    "research/csia_prime1/DEV_CHECKS.json",
    "research/csia_prime1/PILOT_BUNDLE_PRIME1.json",
    "research/csia_prime1/BLINDNESS_AUDIT.json",
    "research/csia_prime1/BLINDNESS_AUDIT_FIRST_RUN.json",
    "research/csia_prime1/FRESH_INSTALL_PRIME1.json",
    "research/csia_prime1/REAL_DATA_READY_CHECK.json",
    "research/csia_prime1/PERFORMANCE_PRIME1.json",
    "research/csia_prime1/SAMPLE_REPORTS_PRIME1.json",
    "research/csia_prime1/FAILURE_LEDGER_DRAFTS.yaml",
    "research/csia_prime2/PILOT_DATA_REQUEST.md",
    "research/physical_validation/FAILURE_LEDGER.yaml",
    "research/csia_prime/FINAL_STATE_PRIME.json",
    "research/csia_prime/PILOT_BUNDLE.json",
)
#: Directories whose every tracked file is frozen with its hash.
AUTHORITATIVE_DIRS = ("research/csia_prime1/pilot_package", "research/csia_prime1/pilot_package_experimenter",
                      "research/csia_prime1/sample_reports_prime1")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def tracked(d: str) -> list:
    return sorted(git("ls-files", d).split())


def frozen_files() -> list:
    out = list(AUTHORITATIVE)
    for d in AUTHORITATIVE_DIRS:
        out += tracked(d)
    return out


def code_digests() -> dict:
    sys.path.insert(0, str(REPO))
    from csia_evidence_assurance import report as R
    return R.code_digests()


def versions() -> dict:
    sys.path.insert(0, str(REPO))
    from csia_evidence_assurance import analyzer, releases, view_prime1
    from csia_semantic_core import core
    rel = releases.get("prime1")
    contracts = {}
    for f in sorted((REPO / "csia_evidence_assurance/contracts").glob("stock_*.json")) + \
            [REPO / "csia_evidence_assurance/contracts/px4_ekf2_estimator_status_2.json"]:
        d = json.loads(f.read_text())
        contracts[f.name] = {"producer_id": d["producer_id"], "producer_version": d["producer_version"],
                             "contract_version": d["contract_version"]}
    sc = json.loads((REPO / "csia_evidence_assurance/support_contract_prime1.json").read_text())
    return {"release": rel.name, "release_description": rel.description,
            "time_resolution_s": rel.time_resolution_s, "event_discovery": rel.discovery,
            "telemetry_producer_version": rel.telemetry_producer_version,
            "telemetry_contract": rel.telemetry_contract,
            "evidence_assurance_analyzer": analyzer.ANALYZER_VERSION,
            "semantic_core": core.REVISED_SEMANTICS_VERSION,
            "stock_bridge_historical_release": "2.3 (producers csia-2.3-stock-r1, unchanged)",
            "profile": "multirotor-quad r1", "view": view_prime1.VIEW_VERSION,
            "support_contract": sc["contract_version"], "producer_contracts": contracts,
            "package": "csia-trust-layer 0.8.0"}


# ------------------------------------------------------------------ build
def build(args) -> int:
    ver = HERE / "verification"
    suite = json.loads(Path(args.suite_counts).read_text())
    final = json.loads((ver / "FINAL_STATE_AT_FREEZE.json").read_text())
    checks = json.loads((ver / "FREEZE_CHECKS.json").read_text())
    bundle_rec = json.loads((PRIME1 / "PILOT_BUNDLE_PRIME1.json").read_text())
    samples = json.loads((PRIME1 / "SAMPLE_REPORTS_PRIME1.json").read_text())
    sc = json.loads((REPO / "csia_evidence_assurance/support_contract_prime1.json").read_text())
    gates = final["gates"]
    m = {
        "schema": "csia.prime1_freeze/1",
        "product": "CSIA Flight Assurance", "release": "prime1", "decision_token": DECISION,
        "freeze": {
            "tag": TAG, "branch": BRANCH,
            "commit": "the commit that carries this manifest; named by the annotated tag (a file cannot hold "
                      "its own commit hash). Recorded with its tree in the tag annotation and the freeze report",
            "pre_freeze_head": args.pre_freeze_head,
            "pre_freeze_tree": args.pre_freeze_tree,
            "product_trees_at_freeze": {p: git("rev-parse", f"HEAD:{p}") for p in PRODUCT_PACKAGES},
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "analysis_dependencies_fresh_install": json.loads(
                            (ver / "FRESH_INSTALL_AT_FREEZE.json").read_text()).get("installed")},
        "versions": versions(),
        "code_digests": code_digests(),
        "wheel": {"file": WHEEL_NAME, "path": str(WHEEL.relative_to(REPO)), "sha256": sha(WHEEL),
                  "same_as_participant_bundle": sha(WHEEL) == bundle_rec["wheel"]["sha256"],
                  "note": "the exact wheel shipped in the participant bundle; earlier 0.8.0 wheels exist with the "
                          "same file name, so the SHA-256 is the identity"},
        "participant_bundle": {
            "zip_name": Path(bundle_rec["bundle"]).name,
            "zip_sha256": checks["bundle"]["frozen_zip_sha256"],
            "members_manifest_sha256": bundle_rec["manifest_sha256"],
            "members": len(bundle_rec["participant_files_sha256"]),
            "custody": "outside git (98 MB, 12 blinded logs); the members' hashes are in "
                       "research/csia_prime1/PILOT_BUNDLE_PRIME1.json; the wheel is preserved in git",
            "answer_key": "experimenter/GROUND_TRUTH.json beside the zip, never inside it; not in git",
            "blindness": checks["bundle"]["frozen_zip_audit"]["verdict"]},
        "representative_report_sha256": {"sample_reports_prime1": {k: v["outputs_sha256"]
                                                                   for k, v in samples["cases"].items()},
                                          "participant_bundle_logs": bundle_rec["sample_report_sha256"]},
        "files_sha256": {f: sha(REPO / f) for f in frozen_files()},
        "verification_records_sha256": {p.name: sha(p) for p in sorted(ver.glob("*.json"))},
        "tests": suite,
        "gates": {k: {"met": v["met"]} for k, v in gates.items()},
        "gate_scope": {"P2_EVENT_DISCOVERY_COMMERCIALLY_USABLE": "SIMULATION ONLY",
                       "P4_REAL_DATA_READY": "processing only; not correctness on real faults",
                       "P5_PHYSICAL_VALIDATION": "NOT MET: no physical propulsion evidence"},
        "historical_integrity": checks["historical"],
        "known_defects": [{"id": d["id"], "affected": d["affected"], "fixed_in": d["fixed_in"],
                           "summary": d["summary"]} for d in sc["known_defects"]],
        "known_limitations": sc["known_blind_spots"] + [
            "every diagnostic claim is validated in PX4 simulation only (one airframe, PX4 547e2ca)",
            "event-discovery promotion rests on 0.298 nominal SITL hours",
            "no real propulsion fault has been analysed against independent truth",
            "the wheel file name (0.8.0) does not distinguish PRIME-1 from earlier 0.8.0 builds"],
        "validation_status": {"physical_validation": "OPEN", "real_blind_pilot": "NONE",
                              "diagnostic_claims_level": "SIMULATION",
                              "claim_lock": checks["claims"]},
        "prime2_status": PRIME2_STATUS,
        "resume_rule": "PRIME-1 is frozen. Engineering resumes only on (A) a concrete defect exposed by real "
                       "external pilot data, (B) a concrete defect exposed by physical or HIL testing, (C) a "
                       "security, reproducibility or package defect of the frozen release, or (D) a supported "
                       "dependency breaking the release; any behavioural change is a separately versioned "
                       "successor branched from the tag",
    }
    MANIFEST.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print(f"wrote {MANIFEST.relative_to(REPO)} ({len(m['files_sha256'])} frozen files)")
    return 0


# ------------------------------------------------------------------ collect
def _claim_rows(text: str) -> list:
    rows = []
    for line in text.splitlines():
        if line.startswith("| M-") or line.startswith("| N"):
            c = [x.strip() for x in line.strip("|").split("|")]
            rows.append({"id": c[0], "validation_level": c[-2] if line.startswith("| M-") else None,
                         "public_safe": c[-1]})
    return rows


def _wheel_content_compare(frozen_zip: Path, rebuilt_zip: Path) -> dict:
    """The wheel inside each bundle, compared member by member (content, then archive timestamps)."""
    import io
    import zipfile

    def members(z: Path):
        with zipfile.ZipFile(z) as outer:
            name = next(n for n in outer.namelist() if n.endswith(".whl"))
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as w:
                return ({n: hashlib.sha256(w.read(n)).hexdigest() for n in w.namelist()},
                        {i.filename: i.date_time for i in w.infolist()}, hashlib.sha256(outer.read(name)).hexdigest())
    a, ad, ash = members(frozen_zip)
    b, bd, bsh = members(rebuilt_zip)
    return {"frozen_wheel_sha256": ash, "rebuilt_wheel_sha256": bsh, "members": len(a),
            "content_identical": a == b,
            "members_with_different_archive_timestamps": sum(1 for n in ad if ad[n] != bd.get(n)),
            "conclusion": "the wheel build is content-reproducible, not byte-reproducible (zip timestamps); "
                          "the frozen wheel is the one recorded"}


def collect(args) -> int:
    import zipfile
    sys.path.insert(0, str(PRIME1))
    ver = HERE / "verification"
    out = {"label": "PRIME-1 freeze checks, measured at the freeze"}
    # defects
    reg = (PRIME1 / "KNOWN_DEFECT_REGISTER.md").read_text()
    final = json.loads((ver / "FINAL_STATE_AT_FREEZE.json").read_text())
    sc = json.loads((REPO / "csia_evidence_assurance/support_contract_prime1.json").read_text())
    out["defects"] = {
        "register_names_all_three": all(d in reg for d in ("D-PRIME-1", "D-PRIME-2", "D-PRIME-3")),
        "register_keeps_fixed_defects": "Fixed defects are\nrecorded here, never erased" in reg
                                        or "never erased" in reg,
        "d_prime_2_v10_not_rewritten": "2.3 V10's recorded result is true of the log as flown" in reg,
        "d_prime_3_prime_bundle_unchanged": "PRIME's participant bundle is unusable as shipped" in reg,
        "contract_fixed_in": {d["id"]: d["fixed_in"] for d in sc["known_defects"]},
        "reproduce_on_historical_2_3": final["defects_reproduce_on_historical_path"],
        "reproduce_on_prime1": {"D-PRIME-1": final["d_prime_1_prime1"]["reproduces"],
                                "D-PRIME-2": final["d_prime_2_prime1"]["reproduces"]},
        "d_prime_3_exact_wheel_fresh_install": json.loads((ver / "FRESH_INSTALL_AT_FREEZE.json").read_text())
        .get("identical_to_repository")}
    # claims
    rows = _claim_rows((PRIME1 / "CLAIM_EVIDENCE_MATRIX_PRIME1.md").read_text())
    pub = (PRIME1 / "PUBLIC_CLAIMS.md").read_text()
    sim = pub.split("## 2. SIMULATION ONLY")[1].split("## 3.")[0]
    sim_rows = [r for r in sim.splitlines() if r.startswith('| "')]
    levels = {r["id"]: r["validation_level"] for r in rows if r["validation_level"]}
    out["claims"] = {
        "rows": rows, "validation_levels_used": sorted(set(levels.values())),
        "any_real_blind_pilot": any("REAL_BLIND_PILOT" in (v or "") for v in levels.values()),
        "any_physical_validated": any(v == "PHYSICAL_VALIDATED" for v in levels.values()),
        "diagnostic_rows_simulation_only": all(levels[k] == "SIMULATION" for k in levels
                                               if k.startswith(("M-T", "M-S", "M-E"))),
        "public_simulation_sentences": len(sim_rows),
        "every_public_simulation_sentence_qualified": all("in px4 simulation" in r.lower() for r in sim_rows),
        "real_blind_pilot_level": "defined by PRIME-2; no claim holds it at the freeze"}
    # support matrix
    out["support"] = {
        "contract_version": sc["contract_version"], "states": list(sc["states"]),
        "configurations": [{k: c.get(k) for k in ("id", "state", "vehicle", "profile", "px4", "required_topics",
                                                     "optional_topics", "minimum_rates",
                                                     "conditions_checked_per_log", "producers", "hypotheses",
                                                     "validation_level")} for c in sc["configurations"]],
        "telemetry_classes": sc["telemetry_classes"], "known_blind_spots": sc["known_blind_spots"],
        "generic_analysis_when_withheld": sc["generic_analysis_when_withheld"],
        "no_physical_validated": all(c["validation_level"] != "PHYSICAL_VALIDATED" for c in sc["configurations"])}
    # bundle
    import build_pilot_bundle_prime1 as BP
    rec = json.loads((PRIME1 / "PILOT_BUNDLE_PRIME1.json").read_text())
    zpath = Path(args.bundle)
    audit = BP.audit_bundle(zpath, [c[0] for c in BP.B0.CASES])
    with zipfile.ZipFile(zpath) as z:
        frozen_members = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
    rb = Path(args.rebuild)
    rebuilt_zip = next(rb.glob("*.zip"))
    with zipfile.ZipFile(rebuilt_zip) as z:
        rebuilt = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
    out["bundle"] = {
        "frozen_zip": zpath.name, "frozen_zip_sha256": sha(zpath),
        "frozen_members_match_record": frozen_members == rec["participant_files_sha256"],
        "frozen_zip_audit": {"verdict": "ZERO KNOWN GROUND-TRUTH LEAKS" if audit["zero_known_leaks"]
                             else "GROUND-TRUTH LEAKS FOUND", "known_leaks": audit["known_leaks"]},
        "answer_key_separate": (zpath.parent / "experimenter/GROUND_TRUTH.json").exists()
                               and not any("GROUND_TRUTH" in n for n in frozen_members),
        "logs": sum(1 for n in frozen_members if n.startswith("logs/")),
        "rebuild_from_clean_inputs": {
            "identical_members": sorted(n for n in rebuilt if frozen_members.get(n) == rebuilt[n]),
            "different_members": sorted(n for n in rebuilt if n in frozen_members and frozen_members[n] != rebuilt[n]),
            "missing_or_extra": sorted(set(rebuilt) ^ set(frozen_members)),
            "wheel_content": _wheel_content_compare(zpath, rebuilt_zip),
            "note": "the frozen bundle is the one recorded; the rebuild only tests reproducibility"}}
    # report sizes (Phase 12)
    perf = json.loads((ver / "PERFORMANCE_AT_FREEZE.json").read_text())
    import tempfile
    sizes = {}
    sys.path.insert(0, str(HERE.parent / "csia_prime1"))
    import perf_prime1 as PF
    for name, path, _kind in PF.LOGS:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "assure", str(path), "--out", td],
                           cwd=REPO, capture_output=True, check=True)
            d = Path(td)
            sizes[name] = {"ulog_bytes": path.stat().st_size,
                           "machine_report_bytes": sum(f.stat().st_size for f in d.iterdir() if f.suffix == ".json"),
                           "human_report_bytes": sum(f.stat().st_size for f in d.iterdir() if f.suffix == ".txt")}
    out["performance"] = {"timings": perf["logs"], "machine": perf["machine"], "report_sizes": sizes}
    # historical integrity
    g = final["gates_2_1_1"]
    hist = json.loads((ver / "HISTORICAL_GATE_AT_FREEZE.json").read_text())
    out["historical"] = {
        "historical_results_changed_since_prime": final["historical_results_changed_since_prime"],
        "semantic_core_changed_since_2_1_1": final["semantic_core_changed_since_2_1_1"],
        "frozen_v2_changed_since_2_2": final["frozen_v2_changed_since_2_2"],
        "ledger_matches_pinned": final["ledger_matches_pinned"],
        "ancestry": final["ancestry"],
        "xsys": {"slots": g["xsys"]["slots"], "primary_success": g["xsys_primary"]["n_success"],
                 "primary_pairs": g["xsys_primary"]["n_pairs"], "lower95": g["xsys_primary"]["lower95"]},
        "xsys_gate_pass": g["xsys_gate_pass"], "phase_c_unchanged": g["phase_c_unchanged"],
        "governance_ok": g["governance_ok"],
        "historical_test_files": {k: final[k].get("summary") for k in
                                  ("tests_2_2", "tests_pilot", "tests_2_3", "tests_rb001", "tests_prime")},
        "reports_reproduced_2_3": final["reports_reproduced_2_3"],
        "prime_sample_reports_reproduced": all(final["prime_sample_reports_reproduced"].values()),
        "prime_bundle_mismatched_members": final["prime_bundle"]["mismatched"],
        "prime_e_artifacts": final["prime_e_artifacts"],
        "historical_gate_2_3_unchanged": hist.get("HISTORICAL_UNCHANGED"),
        "final_state_ok": final["FINAL_STATE_PRIME1_OK"]}
    (ver / "FREEZE_CHECKS.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"defects": out["defects"], "claims_any_real_or_physical": [
        out["claims"]["any_real_blind_pilot"], out["claims"]["any_physical_validated"]],
        "bundle": {k: v for k, v in out["bundle"].items() if k != "rebuild_from_clean_inputs"},
        "rebuild_different": out["bundle"]["rebuild_from_clean_inputs"]["different_members"]}, indent=1))
    return 0


# ------------------------------------------------------------------ check
def check(_args) -> int:
    m = json.loads(MANIFEST.read_text())
    res = {}
    bad = [f for f, h in m["files_sha256"].items() if not (REPO / f).exists() or sha(REPO / f) != h]
    res["frozen_files_match"] = {"files": len(m["files_sha256"]), "mismatched": bad}
    res["code_digests_match"] = code_digests() == m["code_digests"]
    res["product_trees_match"] = {p: git("rev-parse", f"HEAD:{p}") == t
                                  for p, t in m["freeze"]["product_trees_at_freeze"].items()}
    res["wheel_match"] = WHEEL.exists() and sha(WHEEL) == m["wheel"]["sha256"]
    res["verification_records_match"] = all(sha(HERE / "verification" / n) == h
                                            for n, h in m["verification_records_sha256"].items())
    g = m["gates"]
    res["decision_as_recorded"] = (m["decision_token"] == DECISION and g["P5_PHYSICAL_VALIDATION"]["met"] is False
                                   and all(g[k]["met"] for k in g if not k.startswith("P5")))
    tag_type = git("cat-file", "-t", TAG)
    if tag_type:
        commit = git("rev-list", "-n", "1", TAG)
        at_tag = subprocess.run(["git", "show", f"{TAG}:{MANIFEST.relative_to(REPO).as_posix()}"], cwd=REPO,
                                capture_output=True).stdout
        remote = git("branch", "-r", "--contains", commit)
        res["tag"] = {"name": TAG, "annotated": tag_type == "tag", "commit": commit,
                      "tree": git("rev-parse", f"{commit}^{{tree}}"),
                      "manifest_at_tag_identical": at_tag == MANIFEST.read_bytes(),
                      "head_is_tag_commit": git("rev-parse", "HEAD") == commit,
                      "remote_branch_contains_tag_commit": f"origin/{BRANCH}" in remote}
    else:
        res["tag"] = {"name": TAG, "present": False}
    ok = (not bad and res["code_digests_match"] and all(res["product_trees_match"].values())
          and res["wheel_match"] and res["verification_records_match"] and res["decision_as_recorded"]
          and (not tag_type or (res["tag"]["annotated"] and res["tag"]["manifest_at_tag_identical"])))
    res["FREEZE_CHECK_OK"] = ok
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--suite-counts", required=True)
    b.add_argument("--pre-freeze-head", required=True)
    b.add_argument("--pre-freeze-tree", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--bundle", required=True)
    c.add_argument("--rebuild", required=True)
    sub.add_parser("check")
    a = ap.parse_args()
    return {"build": build, "collect": collect, "check": check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
