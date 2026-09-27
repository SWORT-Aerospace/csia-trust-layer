#!/usr/bin/env python3
"""XSYS-001-A1 amendment freeze. Standard library only.

  freeze_a1.py freeze   write FREEZE_MANIFEST_A1.json and FREEZE_MANIFEST_A1.sha256
  freeze_a1.py verify   re-verify the chain; exit 1 naming any difference

THE CHAIN
  XSYS-001      prereg/FREEZE_MANIFEST.json, SHA-256 in prereg/FREEZE_MANIFEST.sha256
                (868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b),
                left byte-identical, with every file it lists
      |
  XSYS-001-A1   FREEZE_MANIFEST_A1.json:
                  parent_manifest   path and SHA-256 of the XSYS-001 manifest
                  frozen_files      every XSYS-001 frozen file (same hashes; freeze refuses
                                    if one differs), the XSYS-001 manifest and its .sha256,
                                    and every amendment file
                  supersedes        the XSYS-001 files the amendment replaces FOR EXECUTION
                                    (they stay frozen and unchanged, for provenance)

The frozen stages read frozen_files and logger_config_file from whichever
manifest they are given, so running them with FREEZE_MANIFEST_A1.json verifies
the original pipeline and the amendment in one step.
"""
import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
X = HERE.parent
REPO = X.parents[1]
R = "research/xsys_confirmatory_001"
PARENT = f"{R}/prereg/FREEZE_MANIFEST.json"
PARENT_SHA256 = "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"
A = f"{R}/amendment_a1"

AMENDMENT_FILES = [
    "docs/research/XSYS_001_A1_NUISANCE_INDEPENDENCE.md",
    f"{A}/A1_CONFIG.json",
    f"{A}/generate_matrix_a1.py",
    f"{A}/FLIGHT_MATRIX_A1.csv",
    f"{A}/ANALYSIS_MATRIX_A1.csv",
    f"{A}/EXECUTION_ORDER_A1.csv",
    f"{A}/power_a1.py",
    f"{A}/POWER_A1.json",
    f"{A}/freeze_a1.py",
    f"{A}/execution_a1/run_confirmatory_a1.py",
    f"{A}/pipeline_a1/a1_paths.py",
    f"{A}/pipeline_a1/stage0_prepare_a1.py",
    f"{A}/pipeline_a1/stage2_score_a1.py",
    f"{A}/independence/DIAGNOSTIC_SPEC.json",
    f"{A}/independence/independence_diagnostics.py",
    f"{A}/independence/analyze_existing.py",
    f"{A}/independence/analyze_memory.py",
    f"{A}/independence/analyze_design.py",
    f"{A}/independence/audit_campaign_a1.py",
    f"{A}/independence/explore_c4_posthoc.py",
    f"{A}/independence/C4_POSTHOC_EXPLORATORY.json",
    f"{A}/post_freeze_check_a1.py",
    f"{A}/independence/EXISTING_DATA_DEPENDENCE.json",
    f"{A}/independence/MEMORY.json",
    f"{A}/independence/DESIGN_CHECK.json",
    f"{A}/pilot_logs/SHA256SUMS",
    PARENT,
    f"{R}/prereg/FREEZE_MANIFEST.sha256",
]
SUPERSEDES = {
    f"{R}/prereg/FLIGHT_MATRIX.csv": f"{A}/FLIGHT_MATRIX_A1.csv",
    f"{R}/prereg/ANALYSIS_MATRIX.csv": f"{A}/ANALYSIS_MATRIX_A1.csv",
    f"{R}/prereg/EXECUTION_ORDER.csv": f"{A}/EXECUTION_ORDER_A1.csv",
    f"{R}/execution/run_confirmatory.py": f"{A}/execution_a1/run_confirmatory_a1.py",
    f"{R}/pipeline/stage0_prepare.py (entry point only)": f"{A}/pipeline_a1/stage0_prepare_a1.py",
    f"{R}/pipeline/stage2_score.py (entry point only)": f"{A}/pipeline_a1/stage2_score_a1.py",
}
MANIFEST = HERE / "FREEZE_MANIFEST_A1.json"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def versions():
    out = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "pyulog", "pymavlink"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def parent_ok():
    if sha256(REPO / PARENT) != PARENT_SHA256:
        return ["XSYS-001 manifest differs from 868880182a8c..."]
    p = json.loads((REPO / PARENT).read_text())
    return [r for r, want in p["frozen_files"].items() if not (REPO / r).exists() or sha256(REPO / r) != want]


def freeze():
    bad = parent_ok()
    if bad:
        raise SystemExit(f"cannot amend: the XSYS-001 freeze does not verify: {bad}")
    missing = [r for r in AMENDMENT_FILES if not (REPO / r).exists()]
    if missing:
        raise SystemExit(f"cannot freeze, missing: {missing}")
    parent = json.loads((REPO / PARENT).read_text())
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    files = dict(parent["frozen_files"])
    files.update({r: sha256(REPO / r) for r in AMENDMENT_FILES})
    m = {
        "experiment_id": "XSYS-001-A1",
        "amends": "XSYS-001",
        "statement": ("Pre-data amendment of the nuisance-generation mechanism only, frozen before any "
                      "confirmatory flight. Changing any file below invalidates this manifest."),
        "parent_manifest": {"path": PARENT, "sha256": PARENT_SHA256},
        "repository_head_before_freeze_commit": head,
        "logger_config_file": parent["logger_config_file"],
        "px4": parent["px4"],
        "supersedes_for_execution": SUPERSEDES,
        "reference_environment_informational": versions(),
        "frozen_files": files,
    }
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    digest = sha256(MANIFEST)
    (HERE / "FREEZE_MANIFEST_A1.sha256").write_text(f"{digest}  FREEZE_MANIFEST_A1.json\n")
    print(json.dumps({"manifest": str(MANIFEST.relative_to(REPO)), "sha256": digest,
                      "parent_sha256": PARENT_SHA256, "frozen_files": len(files)}))


def verify():
    bad = [f"XSYS-001: {x}" for x in parent_ok()]
    m = json.loads(MANIFEST.read_text())
    if m["parent_manifest"]["sha256"] != PARENT_SHA256:
        bad.append("parent_manifest is not the XSYS-001 manifest")
    bad += [r for r, want in m["frozen_files"].items() if not (REPO / r).exists() or sha256(REPO / r) != want]
    digest = sha256(MANIFEST)
    if digest != (HERE / "FREEZE_MANIFEST_A1.sha256").read_text().split()[0]:
        bad.append("FREEZE_MANIFEST_A1.json (differs from FREEZE_MANIFEST_A1.sha256)")
    print(json.dumps({"amendment_manifest_sha256": digest, "parent_manifest_sha256": PARENT_SHA256,
                      "frozen_files": len(m["frozen_files"]), "violations": bad}))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    {"freeze": freeze, "verify": verify}[sys.argv[1]]()
