#!/usr/bin/env python3
"""XSYS-001 freeze manifest. Standard library only.

  freeze.py freeze   write FREEZE_MANIFEST.json and FREEZE_MANIFEST.sha256
  freeze.py verify   re-hash every frozen file; exit 1 naming any difference

The manifest lists the SHA-256 of every file that defines the experiment:
the preregistration document, the machine-readable configuration, the trial
matrix and execution order, the power analysis, the calibration, every
pipeline and execution script, the pilot record, the PX4 patch and logger
configuration, and the two CSIA v2 modules the adapter calls unchanged.

Every confirmatory output records the SHA-256 of this manifest. The executor
refuses to fly, and stages 0, 1 and 2 refuse to run, if any frozen file
differs. tests/test_xsys_001_preregistration.py holds the manifest's own
SHA-256, so replacing the manifest is a visible change to a test.
"""
import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
X = "research/xsys_confirmatory_001"
PX4_COMMIT = "547e2caa9883bc1609325f02b4914b4e2482fe62"
PATCH = "research/px4_actuator_effectiveness/patch/0001-sih-actuator-effectiveness.patch"
LOGGER = "research/px4_actuator_effectiveness/config/logger_topics.txt"
REFERENCE_BINARY_SHA256 = "4073466f1b3e42ed073b88d45bda4e4d1168a35730eb23f470ae5a0744dfc085"

FROZEN = [
    "docs/research/XSYS_001_PREREGISTRATION.md",
    f"{X}/prereg/PREREG_CONFIG.json",
    f"{X}/prereg/FLIGHT_MATRIX.csv",
    f"{X}/prereg/ANALYSIS_MATRIX.csv",
    f"{X}/prereg/EXECUTION_ORDER.csv",
    f"{X}/prereg/generate_matrix.py",
    f"{X}/prereg/power_analysis.py",
    f"{X}/prereg/POWER.json",
    f"{X}/prereg/freeze.py",
    f"{X}/calibration/calibrate_from_apparatus.py",
    f"{X}/calibration/CALIBRATION.json",
    f"{X}/pipeline/xsys_features.py",
    f"{X}/pipeline/xsys_extract.py",
    f"{X}/pipeline/xsys_v2_adapter.py",
    f"{X}/pipeline/xsys_freeze_check.py",
    f"{X}/pipeline/stage0_prepare.py",
    f"{X}/pipeline/stage1_evidence.py",
    f"{X}/pipeline/stage2_score.py",
    f"{X}/pipeline/dry_run_matrix.py",
    f"{X}/execution/run_confirmatory.py",
    f"{X}/execution/xsys_run_trial.py",
    f"{X}/validation/pilot_analysis.py",
    f"{X}/validation/PILOT_ANALYSIS.json",
    f"{X}/validation/run_dry_run.sh",
    f"{X}/validation/summarize_dry_run.py",
    f"{X}/validation/DRY_RUN_RESULTS.json",
    f"{X}/apparatus_pilot/SHA256SUMS",
    LOGGER,
    PATCH,
    "csia/v2/localization.py",
    "csia/v2/evidence.py",
]
MANIFEST = HERE / "FREEZE_MANIFEST.json"


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


def freeze():
    missing = [r for r in FROZEN if not (REPO / r).exists()]
    if missing:
        raise SystemExit(f"cannot freeze, missing: {missing}")
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    m = {
        "experiment_id": "XSYS-001",
        "statement": ("Preregistration frozen before any confirmatory flight. Changing any file below "
                      "invalidates this manifest; a changed protocol is a new, separately frozen "
                      "preregistration, and results obtained under it are reported under its id."),
        "repository_head_before_freeze_commit": head,
        "logger_config_file": LOGGER,
        "px4": {"commit": PX4_COMMIT, "patch_file": PATCH, "patch_sha256": sha256(REPO / PATCH),
                "reference_binary_sha256_informational": REFERENCE_BINARY_SHA256,
                "binary_rule": ("the executor verifies the SOURCE (547e2ca + exactly this patch) and records "
                                "the campaign binary's SHA-256 once in CAMPAIGN.json; every flight must use it")},
        "reference_environment_informational": versions(),
        "frozen_files": {r: sha256(REPO / r) for r in FROZEN},
    }
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    digest = sha256(MANIFEST)
    (HERE / "FREEZE_MANIFEST.sha256").write_text(f"{digest}  FREEZE_MANIFEST.json\n")
    print(json.dumps({"manifest": str(MANIFEST.relative_to(REPO)), "sha256": digest,
                      "frozen_files": len(FROZEN)}))


def verify():
    m = json.loads(MANIFEST.read_text())
    bad = [r for r, want in m["frozen_files"].items() if not (REPO / r).exists() or sha256(REPO / r) != want]
    recorded = (HERE / "FREEZE_MANIFEST.sha256").read_text().split()[0]
    digest = sha256(MANIFEST)
    if digest != recorded:
        bad.append("FREEZE_MANIFEST.json (differs from FREEZE_MANIFEST.sha256)")
    print(json.dumps({"manifest_sha256": digest, "frozen_files": len(m["frozen_files"]),
                      "violations": bad}))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    {"freeze": freeze, "verify": verify}[sys.argv[1]]()
