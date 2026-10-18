#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign, PHASE 0: pre-execution verification.

Operational record-keeping only: it runs the three frozen freeze verifiers and
the frozen A2 executor's own source check, and records the 16 items the
campaign authorization lists. It changes nothing and computes no outcome.

Usage: phase0_verify.py --px4-src <tree> --build <tree>/build/px4_sitl_default --raw <raw-artifact dir>
                        --out PHASE0_VERIFICATION.json --pytest <python with pytest>
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
X = REPO / "research" / "xsys_confirmatory_001"
CHAIN = {"XSYS-001": ("research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json",
                      "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"),
         "XSYS-001-A1": ("research/xsys_confirmatory_001/amendment_a1/FREEZE_MANIFEST_A1.json",
                         "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b"),
         "XSYS-001-A2": ("research/xsys_confirmatory_001/amendment_a2/FREEZE_MANIFEST_A2.json",
                         "d86e857d000d54502ec66bcbc83dbf679c55903aaf8ffe5e557e4514b1dded8f")}
NEED_FREE_GB = 12.0


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run(cmd):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=REPO)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--px4-src", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pytest", required=True, help="an interpreter with pytest, for the guard tests")
    a = ap.parse_args()
    py = sys.executable
    a2 = json.loads((REPO / CHAIN["XSYS-001-A2"][0]).read_text())
    files = a2["frozen_files"]
    c = {}

    for i, (tool, key) in enumerate(((X / "prereg" / "freeze.py", "XSYS-001"),
                                     (X / "amendment_a1" / "freeze_a1.py", "XSYS-001-A1"),
                                     (X / "amendment_a2" / "freeze_a2.py", "XSYS-001-A2")), 1):
        rc, o, e = run([py, tool, "verify"])
        rel, want = CHAIN[key]
        c[f"{i:02d}_verify_{key}_manifest"] = {"pass": rc == 0 and sha256(REPO / rel) == want,
                                               "sha256": sha256(REPO / rel), "verifier": o[-400:]}
    links = (a2["parent_manifest"]["sha256"] == CHAIN["XSYS-001-A1"][1]
             and a2["grandparent_manifest"]["sha256"] == CHAIN["XSYS-001"][1]
             and json.loads((REPO / CHAIN["XSYS-001-A1"][0]).read_text())["parent_manifest"]["sha256"] == CHAIN["XSYS-001"][1])
    c["04_verify_manifest_chain"] = {"pass": links and all(c[k]["pass"] for k in list(c)[:3]),
                                     "chain": {k: v[1] for k, v in CHAIN.items()}}
    for n, rel in (("05_verify_confirmatory_matrix", ("FLIGHT_MATRIX_A1.csv", "ANALYSIS_MATRIX_A1.csv")),
                   ("06_verify_execution_order", ("EXECUTION_ORDER_A1.csv",))):
        det = {}
        for r in rel:
            p = f"research/xsys_confirmatory_001/amendment_a1/{r}"
            det[p] = {"sha256": sha256(REPO / p), "frozen": a2["confirmatory_matrix_unchanged_from_A1"][p]}
        c[n] = {"pass": all(v["sha256"] == v["frozen"] for v in det.values()), "files": det}

    spec = importlib.util.spec_from_file_location("exec_a2", X / "amendment_a2" / "execution_a2" / "run_confirmatory_a2.py")
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)
    try:
        ok_src = ex.verify_source(a.px4_src, REPO / a2["px4"]["patch_file"])
        msg = "HEAD^ is 547e2ca, tree clean, diff 547e2ca..HEAD equals the frozen patch diff"
    except SystemExit as err:
        ok_src, msg = False, str(err)
    head = run(["git", "-C", a.px4_src, "rev-parse", "HEAD"])[1]
    parent = run(["git", "-C", a.px4_src, "rev-parse", "HEAD^"])[1]
    c["07_verify_px4_source_commit"] = {"pass": bool(ok_src) and parent == a2["px4"]["commit"],
                                        "HEAD^": parent, "HEAD": head, "detail": msg}
    patch = REPO / a2["px4"]["patch_file"]
    c["08_verify_px4_patch"] = {"pass": sha256(patch) == a2["px4"]["patch_sha256"] == files[a2["px4"]["patch_file"]],
                                "sha256": sha256(patch)}
    binary = Path(a.build) / "bin" / "px4"
    bsha = sha256(binary) if binary.exists() else None
    c["09_verify_px4_build"] = {"pass": binary.exists(), "binary_sha256": bsha,
                                "equals_reference_build": bsha == a2["px4"]["reference_binary_sha256_informational"],
                                "note": "the binary hash is recorded once in CAMPAIGN.json by the executor"}
    lc = a2["logger_config_file"]
    c["10_verify_logger_configuration"] = {"pass": sha256(REPO / lc) == files[lc], "sha256": sha256(REPO / lc)}
    raw = Path(a.raw)
    raw.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(raw).free / 1e9
    c["11_verify_disk_space"] = {"pass": free >= NEED_FREE_GB, "free_GB": round(free, 1), "required_GB": NEED_FREE_GB}
    flights = raw / "flights"
    inside_x = str(flights.resolve()).startswith(str(X.resolve()))
    inside_repo = str(flights.resolve()).startswith(str(REPO.resolve()))
    c["12_verify_output_location"] = {"pass": not inside_x and not inside_repo and (not flights.exists() or not any(flights.iterdir())),
                                      "raw_flights_dir": str(flights), "outside_research_xsys_confirmatory_001": not inside_x,
                                      "outside_git_working_tree": not inside_repo,
                                      "records_dir_in_repo": str(HERE.relative_to(REPO))}
    stages = {r: files[r] for r in files if r.startswith("research/xsys_confirmatory_001/pipeline/")
              or r.startswith("research/xsys_confirmatory_001/amendment_a1/pipeline_a1/")}
    c["13_verify_stage_0_1_2_hashes"] = {"pass": all(sha256(REPO / r) == h for r, h in stages.items()),
                                         "files": {r: sha256(REPO / r) for r in stages}}
    v2 = {r: files[r] for r in ("csia/v2/localization.py", "csia/v2/evidence.py")}
    c["14_verify_v2_hashes"] = {"pass": all(sha256(REPO / r) == h for r, h in v2.items()), "files": v2}
    camps = [str(p) for p in (REPO / "research").rglob("CAMPAIGN.json")] + [str(p) for p in raw.rglob("CAMPAIGN.json")]
    recs = [str(p) for pat in ("XS1-*", "XS1A1-*") for p in list((REPO / "research").rglob(pat)) + list(raw.rglob(pat))]
    c["15_confirmatory_dataset_has_zero_flights"] = {"pass": not camps and not recs, "campaigns": camps, "flight_files": recs}
    outs = [str(p) for pat in ("KEY.json", "QC.json", "STAGE1*.json", "RESULTS*.json")
            for p in list(HERE.rglob(pat)) + list(raw.rglob(pat))]
    c["16_confirmatory_analysis_has_zero_trials"] = {"pass": not outs, "stage_outputs": outs}
    rc, o, _ = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_xsys_001_preregistration.py",
                    "tests/test_xsys_001_a1_amendment.py", "tests/test_xsys_001_a2_amendment.py"])
    res = {"campaign_id": "XSYS-001-CONFIRMATORY", "phase": "PHASE 0 - PRE-EXECUTION VERIFICATION",
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "checks": c, "guard_tests": {"pass": rc == 0, "summary": o.splitlines()[-1] if o else ""},
           "all_pass": all(v["pass"] for v in c.values()) and rc == 0}
    Path(a.out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v["pass"] for k, v in c.items()} | {"guard_tests": rc == 0, "all_pass": res["all_pass"]}, indent=1))


if __name__ == "__main__":
    main()
