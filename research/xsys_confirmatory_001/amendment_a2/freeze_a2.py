#!/usr/bin/env python3
"""XSYS-001-A2 amendment freeze. Standard library only.

  freeze_a2.py freeze   write FREEZE_MANIFEST_A2.json and FREEZE_MANIFEST_A2.sha256
  freeze_a2.py verify   re-verify the whole chain; exit 1 naming any difference

THE CHAIN (never rewritten)
  XSYS-001      prereg/FREEZE_MANIFEST.json            868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b
      |
  XSYS-001-A1   amendment_a1/FREEZE_MANIFEST_A1.json   55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b
      |
  XSYS-001-A2   amendment_a2/FREEZE_MANIFEST_A2.json:
                  parent_manifest       the A1 manifest, by path and SHA-256
                  grandparent_manifest  the XSYS-001 manifest, by path and SHA-256
                  frozen_files          every A1 frozen file (which already carries every XSYS-001
                                        file) with the same hash, both manifests and their .sha256,
                                        and every A2 file
                  prepilot_commit       the files committed at 4f3378f BEFORE any A2 pilot flew;
                                        freeze refuses if one of them differs from that commit
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
A2 = f"{R}/amendment_a2"
XSYS = {"path": f"{R}/prereg/FREEZE_MANIFEST.json",
        "sha256": "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"}
A1 = {"path": f"{R}/amendment_a1/FREEZE_MANIFEST_A1.json",
      "sha256": "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b"}
PREPILOT_COMMIT = "4f3378f"
PREPILOT = {
    f"{A2}/C4_A2_SPEC.json": "cec3e3ce1c74ec533b97dd95ef44b18517d0607c2ed7589b5cab3e72e539aaa1",
    f"{A2}/PILOT_MATRIX_A2.csv": "221ab182933b26a7404405d32bd82b5b4a588c5f5f6b357930aff62ba3f0a830",
    f"{A2}/analyze_a2.py": "a3dfe02c0d21522b572cf03e4e7b20929122270479b219e9223a4177fba3d07f",
    f"{A2}/fly_pilots_a2.py": "a8b852d33b8d719b22731238d32a9d6947a7e403fd770e5990985bed4c38f22e",
    f"{A2}/generate_pilots_a2.py": "7581782ce439c5c4cc7d809ef981555e0137e3772ead6918720f373e0fe1e642",
    "docs/research/XSYS_001_A2_C4_CORRECTION.md": "54fb4e0d500cfc2aff1e00c897c6ee9b2b5a47f25ddd92dfeaf15f29d055e678",
}
POSTPILOT = [
    "docs/research/XSYS_001_A2_RESULTS.md",
    f"{A2}/A2_CONFIG.json",
    f"{A2}/C4_A2_RESULTS.json",
    f"{A2}/pilot_logs/SHA256SUMS",
    f"{A2}/freeze_a2.py",
    f"{A2}/execution_a2/run_confirmatory_a2.py",
    f"{A2}/post_freeze_check_a2.py",
    A1["path"], f"{R}/amendment_a1/FREEZE_MANIFEST_A1.sha256",
    XSYS["path"], f"{R}/prereg/FREEZE_MANIFEST.sha256",
]
MANIFEST = HERE / "FREEZE_MANIFEST_A2.json"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def chain_violations():
    bad = []
    for m in (XSYS, A1):
        if sha256(REPO / m["path"]) != m["sha256"]:
            bad.append(f"{m['path']} is not {m['sha256'][:12]}...")
    for m in (XSYS, A1):
        files = json.loads((REPO / m["path"]).read_text())["frozen_files"]
        bad += [f"{m['path']}: {r}" for r, h in files.items() if not (REPO / r).exists() or sha256(REPO / r) != h]
    return bad


def freeze():
    bad = chain_violations()
    bad += [f"pre-pilot file changed: {r}" for r, h in PREPILOT.items() if sha256(REPO / r) != h]
    missing = [r for r in POSTPILOT if not (REPO / r).exists()]
    if bad or missing:
        raise SystemExit(f"cannot freeze A2: {bad} missing {missing}")
    a1 = json.loads((REPO / A1["path"]).read_text())
    files = dict(a1["frozen_files"])
    files.update({r: sha256(REPO / r) for r in list(PREPILOT) + POSTPILOT})
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    ver = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "pyulog", "pymavlink"):
        try:
            ver[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            ver[pkg] = None
    m = {
        "experiment_id": "XSYS-001-A2",
        "amends": "XSYS-001-A1",
        "statement": ("Second pre-data amendment, limited to the definition of C4. XSYS-001 and XSYS-001-A1 "
                      "are unchanged. Changing any file below invalidates this manifest."),
        "parent_manifest": A1,
        "grandparent_manifest": XSYS,
        "prepilot_commit": PREPILOT_COMMIT,
        "prepilot_files": PREPILOT,
        "confirmatory_matrix_unchanged_from_A1": {
            r: files[r] for r in (f"{R}/amendment_a1/FLIGHT_MATRIX_A1.csv", f"{R}/amendment_a1/ANALYSIS_MATRIX_A1.csv",
                                  f"{R}/amendment_a1/EXECUTION_ORDER_A1.csv")},
        "decision_file": f"{A2}/C4_A2_RESULTS.json",
        "decision": json.loads((HERE / "C4_A2_RESULTS.json").read_text())["decision"],
        "repository_head_before_freeze_commit": head,
        "logger_config_file": a1["logger_config_file"],
        "px4": a1["px4"],
        "reference_environment_informational": ver,
        "frozen_files": files,
    }
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    digest = sha256(MANIFEST)
    (HERE / "FREEZE_MANIFEST_A2.sha256").write_text(f"{digest}  FREEZE_MANIFEST_A2.json\n")
    print(json.dumps({"manifest": str(MANIFEST.relative_to(REPO)), "sha256": digest,
                      "parent_sha256": A1["sha256"], "grandparent_sha256": XSYS["sha256"],
                      "frozen_files": len(files), "decision": m["decision"]}))


def verify():
    bad = chain_violations()
    m = json.loads(MANIFEST.read_text())
    if m["parent_manifest"] != A1 or m["grandparent_manifest"] != XSYS:
        bad.append("chain links differ")
    bad += [r for r, h in m["frozen_files"].items() if not (REPO / r).exists() or sha256(REPO / r) != h]
    bad += [f"pre-pilot {r}" for r, h in m["prepilot_files"].items() if sha256(REPO / r) != h]
    digest = sha256(MANIFEST)
    if digest != (HERE / "FREEZE_MANIFEST_A2.sha256").read_text().split()[0]:
        bad.append("FREEZE_MANIFEST_A2.json (differs from FREEZE_MANIFEST_A2.sha256)")
    print(json.dumps({"a2_manifest_sha256": digest, "a1_manifest_sha256": A1["sha256"],
                      "xsys001_manifest_sha256": XSYS["sha256"], "frozen_files": len(m["frozen_files"]),
                      "violations": bad}))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    {"freeze": freeze, "verify": verify}[sys.argv[1]]()
