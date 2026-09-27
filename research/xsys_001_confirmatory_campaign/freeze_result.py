#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign: freeze the confirmatory result.

Writes CONFIRMATORY_RESULT_MANIFEST.json and its .sha256. The manifest
hashes every confirmatory artifact:
  - the completion record and the raw-data manifest;
  - the stage 0 report, QC and key;
  - the blinded stage 1 inputs;
  - the stage 1 output, its seal and the seal record;
  - the stage 2 result and the descriptive summary;
  - the independence audit and the environment record;
  - the phase 0 record and the campaign records;
  - the report and the operational scripts.
It binds the XSYS-001 -> A1 -> A2 chain, and it verifies that none of the
historical manifests changed.

The verdict line is derived mechanically:
  XSYS_001_CONFIRMATORY_INVALID     an integrity condition failed:
                                      - a frozen file or manifest differs;
                                      - the campaign binary or source is not
                                        the frozen one;
                                      - the stage 1 blinding audit failed, or
                                        its output does not match its seal;
                                      - stage 2 did not run in confirmatory
                                        mode under the A2 manifest
  XSYS_001_PRIMARY_SUPPORTED        otherwise, if the frozen stage 2
                                    decided H_PRIMARY = SUPPORTED
  XSYS_001_PRIMARY_NOT_SUPPORTED    otherwise
It never recomputes a statistic.

Usage: freeze_result.py [--check]   (--check verifies an existing manifest)
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
X = REPO / "research" / "xsys_confirmatory_001"
REPORT = REPO / "docs" / "research" / "XSYS_001_CONFIRMATORY_RESULT.md"
MANIFEST = HERE / "CONFIRMATORY_RESULT_MANIFEST.json"
CHAIN = {"XSYS-001": (X / "prereg" / "FREEZE_MANIFEST.json",
                      "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"),
         "XSYS-001-A1": (X / "amendment_a1" / "FREEZE_MANIFEST_A1.json",
                         "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b"),
         "XSYS-001-A2": (X / "amendment_a2" / "FREEZE_MANIFEST_A2.json",
                         "d86e857d000d54502ec66bcbc83dbf679c55903aaf8ffe5e557e4514b1dded8f")}
COMPONENTS = {
    "completion_record": ["CAMPAIGN_COMPLETION.json", "CAMPAIGN_COMPLETION.sha256"],
    "raw_data_manifest": ["RAW_DATA_MANIFEST.json"],
    "stage0_report": ["stage0/STAGE0_REPORT.json", "stage0/STAGE0_REPORT.sha256", "stage0/QC.json", "stage0/KEY.json"],
    "stage1_sealed_output": ["stage1/STAGE1.json", "stage1/STAGE1.seal.json", "stage1/STAGE1_SEAL_RECORD.json",
                             "stage1/STAGE1_SEAL_RECORD.sha256", "stage1/STAGE1_STRACE.txt"],
    "stage2_result": ["stage2/RESULTS.json"],
    "descriptive_summary": ["RESULT_SUMMARY.json"],
    "environment": ["ENVIRONMENT.json"],
    "independence_audit": ["INDEPENDENCE_AUDIT_A1.json"],
    "phase0": ["PHASE0_VERIFICATION.json"],
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def rel(p):
    return str(Path(p).resolve().relative_to(REPO))


def run(cmd):
    p = subprocess.run([sys.executable, *map(str, cmd)], cwd=REPO, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout.strip() or p.stderr.strip()).splitlines()[-1:]


def build():
    files = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.name not in (MANIFEST.name, MANIFEST.with_suffix(".sha256").name):
            files[rel(p)] = sha256(p)
    files[rel(REPORT)] = sha256(REPORT)
    comp = {k: {f"research/xsys_001_confirmatory_campaign/{f}": files.get(f"research/xsys_001_confirmatory_campaign/{f}")
                for f in v} for k, v in COMPONENTS.items()}
    blind = sorted(f for f in files if f.startswith("research/xsys_001_confirmatory_campaign/stage1_inputs/blind/"))
    comp["blinded_stage1_inputs"] = {"count_npz": sum(f.endswith(".npz") for f in blind),
                                     "files": {f: files[f] for f in blind},
                                     "set_sha256": hashlib.sha256(json.dumps({f: files[f] for f in blind},
                                                                             sort_keys=True).encode()).hexdigest()}
    comp["report"] = {rel(REPORT): files[rel(REPORT)]}

    completion = json.loads((HERE / "CAMPAIGN_COMPLETION.json").read_text())
    s0 = json.loads((HERE / "stage0" / "STAGE0_REPORT.json").read_text())
    s1r = json.loads((HERE / "stage1" / "STAGE1_SEAL_RECORD.json").read_text())
    seal = json.loads((HERE / "stage1" / "STAGE1.seal.json").read_text())
    res = json.loads((HERE / "stage2" / "RESULTS.json").read_text())
    chain_ok = {k: sha256(p) == want for k, (p, want) in CHAIN.items()}
    verifiers = {"XSYS-001": run([X / "prereg" / "freeze.py", "verify"]),
                 "XSYS-001-A1": run([X / "amendment_a1" / "freeze_a1.py", "verify"]),
                 "XSYS-001-A2": run([X / "amendment_a2" / "freeze_a2.py", "verify"])}
    a2 = CHAIN["XSYS-001-A2"][1]
    s0_sha_file = (HERE / "stage0" / "STAGE0_REPORT.sha256").read_text().split()[0]
    comp_sha_file = (HERE / "CAMPAIGN_COMPLETION.sha256").read_text().split()[0]
    blind_npz = {Path(f).stem: h for f, h in comp["blinded_stage1_inputs"]["files"].items() if f.endswith(".npz")}
    integrity = {
        "historical_manifests_unchanged": all(chain_ok.values()),
        "freeze_verifiers_pass": all(ok for ok, _ in verifiers.values()),
        "completion_record_matches_its_seal": sha256(HERE / "CAMPAIGN_COMPLETION.json") == comp_sha_file,
        "campaign_binary_and_records_consistent": all(completion[k] for k in (
            "all_flights_used_campaign_binary", "all_records_carry_A2_manifest", "all_record_ulog_hashes_match",
            "all_xz_roundtrips_ok")),
        "campaign_ran_under_A2": completion["campaign_json_manifest_sha256"] == a2,
        "campaign_source_verified": completion["source"]["source_verified"] is True,
        "stage0_report_matches_its_seal": sha256(HERE / "stage0" / "STAGE0_REPORT.json") == s0_sha_file,
        "stage0_ran_under_A2": s0["stage0_manifest_sha256"] == a2 and s0["stage0_mode"] == "confirmatory",
        "stage0_key_matches_report": sha256(HERE / "stage0" / "KEY.json") == s0["label_key_sha256"],
        "stage0_qc_matches_report": sha256(HERE / "stage0" / "QC.json") == s0["qc_sha256"],
        "blinded_inputs_match_stage0_report": blind_npz == s0["stage1_inputs"]["npz_sha256"],
        "stage1_blind_audit_passed": s1r["blind"] is True,
        "stage1_output_matches_seal": sha256(HERE / "stage1" / "STAGE1.json") == seal["stage1_output_sha256"],
        "stage1_record_matches_its_seal": sha256(HERE / "stage1" / "STAGE1_SEAL_RECORD.json") ==
                                          (HERE / "stage1" / "STAGE1_SEAL_RECORD.sha256").read_text().split()[0],
        "stage1_ran_under_A2": seal["freeze_manifest_sha256"] == a2,
        "stage2_confirmatory_under_A2": res["mode"] == "confirmatory" and res["freeze_manifest_sha256"] == a2
                                        and res["stage1_output_sha256"] == seal["stage1_output_sha256"],
    }
    valid = all(integrity.values())
    hp = res["primary"]["H_PRIMARY"]
    verdict = ("XSYS_001_CONFIRMATORY_INVALID" if not valid else
               "XSYS_001_PRIMARY_SUPPORTED" if hp == "SUPPORTED" else "XSYS_001_PRIMARY_NOT_SUPPORTED")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {
        "campaign_id": "XSYS-001-CONFIRMATORY",
        "record": "XSYS-001 CONFIRMATORY RESULT MANIFEST - the frozen result; historical manifests are not modified",
        "verdict": verdict,
        "primary": {k: res["primary"].get(k) for k in ("H_PRIMARY", "rate", "n_pairs", "n_success", "n_eff", "lower95",
                                                        "p_vs_0.5", "wrong_A_B", "decision_rule")},
        "secondary_interpretation": res["secondary_interpretation"],
        "protocol_chain": {k: {"file": rel(p), "sha256": want, "unchanged": chain_ok[k],
                               "verifier": verifiers[k][1]} for k, (p, want) in CHAIN.items()},
        "integrity": integrity,
        "components": comp,
        "raw_artifacts_outside_git": {
            "location": json.loads((HERE / "RAW_DATA_MANIFEST.json").read_text())["raw_artifact_location"],
            "raw_data_manifest_sha256": files["research/xsys_001_confirmatory_campaign/RAW_DATA_MANIFEST.json"],
            "note": "raw ULogs and their xz copies are recorded by name, SHA-256 and size; they are not in git"},
        "files": files,
        "repository_head_at_freeze": head,
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        m = json.loads(MANIFEST.read_text())
        bad = [f for f, h in m["files"].items() if not (REPO / f).exists() or sha256(REPO / f) != h]
        want = MANIFEST.with_suffix(".sha256").read_text().split()[0]
        ok = not bad and sha256(MANIFEST) == want
        print(json.dumps({"ok": ok, "differs": bad, "verdict": m["verdict"]}))
        raise SystemExit(0 if ok else 1)
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.name} exists: the confirmatory result is frozen once")
    m = build()
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    d = sha256(MANIFEST)
    MANIFEST.with_suffix(".sha256").write_text(f"{d}  {MANIFEST.name}\n")
    print(json.dumps({"verdict": m["verdict"], "integrity": m["integrity"], "files": len(m["files"]),
                      "manifest_sha256": d}, indent=1))


if __name__ == "__main__":
    main()
