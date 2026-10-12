#!/usr/bin/env python3
"""XSYS-001 post-freeze validation. Flies nothing; writes POST_FREEZE_CHECK.json.

Run AFTER prereg/freeze.py freeze, with the research interpreter:

  post_freeze_check.py --px4-src <547e2ca + patch, committed> --build <px4-src>/build/px4_sitl_default
                       --sweep <decompressed apparatus sweep dir> --scratch <dir> [--pytest <python with pytest>]

Checks, each recorded with its evidence:
  1. freeze.py verify: every frozen file matches the manifest
  2. the executor's --dry-run: manifest, PX4 source and binary verified; the
     66 flights listed in the frozen order; nothing flown, no CAMPAIGN.json
  3. the executor refuses an unpatched PX4 tree
  4. stage 0 in confirmatory mode refuses an incomplete campaign (no flights)
  5. stage 0 in confirmatory mode refuses a matrix that differs from the frozen one
  6. the frozen pipeline, re-run on the apparatus dry-run data, reproduces the
     frozen DRY_RUN_RESULTS.json decisions and tallies
  7. the guard test passes, and fails when one byte of a frozen file changes
     (the file is restored afterwards)
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
X = HERE.parent
REPO = X.parents[1]
MANIFEST = X / "prereg" / "FREEZE_MANIFEST.json"


def run(cmd, **kw):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    return p.returncode, p.stdout, p.stderr


def tail(s, n=300):
    return s.strip()[-n:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--px4-src", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--unpatched-src", help="a PX4 tree that is NOT 547e2ca + the patch")
    ap.add_argument("--sweep", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--pytest", default=sys.executable)
    a = ap.parse_args()
    py = sys.executable
    s = Path(a.scratch)
    if s.exists():
        shutil.rmtree(s)
    s.mkdir(parents=True)
    out = {"label": "POST-FREEZE VALIDATION - NO CONFIRMATORY FLIGHT", "checks": {}}
    c = out["checks"]

    rc, o, e = run([py, X / "prereg" / "freeze.py", "verify"])
    c["1_freeze_verify"] = {"pass": rc == 0, "output": json.loads(o) if rc == 0 else tail(o + e)}

    rc, o, e = run([py, X / "execution" / "run_confirmatory.py", "--dry-run", "--manifest", MANIFEST,
                    "--px4-src", a.px4_src, "--build", a.build, "--out", s / "exec", "--work", s / "work"])
    lines = [ln for ln in o.splitlines() if ln.strip()]
    listed = [ln.split()[3] for ln in lines[:-1]]
    order = [r["flight_id"] for r in csv.DictReader(open(X / "prereg" / "EXECUTION_ORDER.csv"))]
    summary = json.loads(lines[-1]) if rc == 0 else None
    c["2_executor_dry_run"] = {
        "pass": rc == 0 and listed == order and not (s / "exec" / "CAMPAIGN.json").exists()
        and not list((s / "exec").glob("*.ulg")),
        "summary": summary, "flights_listed": len(listed), "listed_equals_frozen_order": listed == order,
        "campaign_json_written": (s / "exec" / "CAMPAIGN.json").exists(), "first_three": lines[:3],
        "stderr": tail(e)}

    if a.unpatched_src:
        rc, o, e = run([py, X / "execution" / "run_confirmatory.py", "--dry-run", "--manifest", MANIFEST,
                        "--px4-src", a.unpatched_src, "--build", a.build, "--out", s / "exec2", "--work", s / "w2"])
        c["3_executor_refuses_unpatched_tree"] = {"pass": rc != 0 and "PX4 source" in e, "message": tail(e, 200)}

    fl = s / "no_flights"
    fl.mkdir()
    man_sha = subprocess.run(["sha256sum", str(MANIFEST)], capture_output=True, text=True).stdout.split()[0]
    (fl / "CAMPAIGN.json").write_text(json.dumps({"freeze_manifest_sha256": man_sha, "px4_sha256": "x",
                                                   "source_verified": True}))
    stage0 = [py, X / "pipeline" / "stage0_prepare.py", "--mode", "confirmatory", "--freeze-manifest", MANIFEST,
              "--analysis-matrix", X / "prereg" / "ANALYSIS_MATRIX.csv", "--flights", fl,
              "--blind", s / "b", "--key", s / "k.json", "--qc", s / "q.json"]
    rc, o, e = run(stage0 + ["--flight-matrix", X / "prereg" / "FLIGHT_MATRIX.csv"])
    c["4_stage0_refuses_incomplete_campaign"] = {"pass": rc != 0 and "campaign incomplete" in e,
                                                 "message": tail(e, 200)}
    alt = s / "FLIGHT_MATRIX_altered.csv"
    alt.write_text((X / "prereg" / "FLIGHT_MATRIX.csv").read_text().replace("0.95,C00", "0.94,C00", 1))
    rc, o, e = run(stage0 + ["--flight-matrix", alt])
    c["5_stage0_refuses_altered_matrix"] = {"pass": rc != 0 and "FREEZE VIOLATION" in e, "message": tail(e, 200)}

    rc, o, e = run(["bash", HERE / "run_dry_run.sh", py, a.sweep, s / "dry", s / "DRY_RUN_RESULTS_rerun.json"])
    ok6 = rc == 0
    diffs = []
    if ok6:
        frozen = json.loads((HERE / "DRY_RUN_RESULTS.json").read_text())
        again = json.loads((s / "DRY_RUN_RESULTS_rerun.json").read_text())

        def strip(r):
            r = json.loads(json.dumps(r))
            for kind in ("A", "B"):
                r["full_run"]["results"]["latency"][kind].pop("computational_latency_s_median", None)
            return r
        f, g = strip(frozen), strip(again)
        for key in ("primary", "secondary", "outcome_tallies", "v2_verdict_tallies_motor_0", "pairs", "exclusions",
                    "pair_resolution_rate_by_variant_C3", "secondary_holm_family", "latency"):
            if f["full_run"]["results"][key] != g["full_run"]["results"][key]:
                diffs.append(key)
        for key in ("pairs", "exclusions", "primary"):
            if f["exclusion_path"][key] != g["exclusion_path"][key]:
                diffs.append("exclusion_path." + key)
        if not g["seal_path"]["stage2_refused"]:
            diffs.append("seal_path")
    c["6_frozen_pipeline_reproduces_dry_run"] = {"pass": ok6 and not diffs, "differences": diffs,
                                                 "stderr": "" if ok6 else tail(e)}

    test = REPO / "tests" / "test_xsys_001_preregistration.py"
    rc, o, e = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", test], cwd=REPO)
    passed_clean = rc == 0
    victim = X / "pipeline" / "stage2_score.py"
    original = victim.read_bytes()
    try:
        victim.write_bytes(original.replace(b"NULL_RATE = 0.5", b"NULL_RATE = 0.4", 1))
        rc2, o2, e2 = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", test], cwd=REPO)
    finally:
        victim.write_bytes(original)
    rc3, _, _ = run([py, X / "prereg" / "freeze.py", "verify"])
    c["7_guard_test"] = {"pass": passed_clean and rc2 != 0 and rc3 == 0, "clean_run": tail(o, 120),
                         "tampered_run_failed": rc2 != 0, "tampered_run": tail(o2, 300),
                         "restored_and_verified": rc3 == 0}

    out["all_pass"] = all(v["pass"] for v in c.values())
    text = json.dumps(out, indent=1) + "\n"
    # local paths -> placeholders; longest first, since <build> lies inside <px4-src>
    local = {str(Path(a.build).resolve()): "<build>", a.build: "<build>", str(s.resolve()): "<scratch>",
             str(Path(a.px4_src).resolve()): "<px4-src>", a.px4_src: "<px4-src>",
             str(Path(a.sweep).resolve()): "<sweep>", str(REPO): "<repo>"}
    if a.unpatched_src:
        local[str(Path(a.unpatched_src).resolve())] = "<unpatched-src>"
    for path in sorted(local, key=len, reverse=True):
        text = text.replace(path, local[path])
    (HERE / "POST_FREEZE_CHECK.json").write_text(text)
    print(json.dumps({k: v["pass"] for k, v in c.items()} | {"all_pass": out["all_pass"]}, indent=1))


if __name__ == "__main__":
    main()
