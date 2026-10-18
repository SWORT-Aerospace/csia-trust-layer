#!/usr/bin/env python3
"""XSYS-001-A2 post-freeze validation (the Part 9 list, plus executor and tamper
checks). Flies nothing; writes POST_FREEZE_CHECK_A2.json (outside the freeze).

  post_freeze_check_a2.py --px4-src <547e2ca + patch> --build <px4-src>/build/px4_sitl_default
                          --scratch <dir> --pytest <python with pytest>
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
T = {n: REPO / "tests" / f"test_xsys_001_{n}.py" for n in ("preregistration", "a1_amendment", "a2_amendment")}
READY = "C1 C2 C3 C4-A2 C5 ALL PASS (guard tests still required)"


def run(cmd, **kw):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    return p.returncode, p.stdout, p.stderr


def sha(p):
    return subprocess.run(["sha256sum", str(p)], capture_output=True, text=True).stdout.split()[0]


def nodes(py, test, *names):
    rc, o, e = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *[f"{test}::{n}" for n in names]], cwd=REPO)
    return rc == 0, (o.strip().splitlines() or [e.strip()])[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--px4-src", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--pytest", required=True)
    a = ap.parse_args()
    py, s = sys.executable, Path(a.scratch)
    if s.exists():
        shutil.rmtree(s)
    s.mkdir(parents=True)
    c = {}
    A2T, A1T, XT = str(T["a2_amendment"]), str(T["a1_amendment"]), str(T["preregistration"])

    rc, o, _ = run([py, X / "prereg" / "freeze.py", "verify"])
    ok, msg = nodes(a.pytest, XT, "test_manifest_is_the_frozen_one", "test_every_frozen_file_matches_the_manifest")
    c["01_xsys001_unchanged"] = {"pass": rc == 0 and ok, "verify": o.strip(), "test": msg}
    rc, o, _ = run([py, X / "amendment_a1" / "freeze_a1.py", "verify"])
    ok, msg = nodes(a.pytest, A1T, "test_amendment_manifest_is_the_frozen_one_and_binds_the_original",
                    "test_every_amendment_file_matches_its_manifest", "test_acceptance_decision_is_recorded_and_blocks_execution")
    c["02_a1_unchanged"] = {"pass": rc == 0 and ok, "verify": o.strip(), "test": msg}
    rc, o, _ = run([py, HERE / "freeze_a2.py", "verify"])
    ok, msg = nodes(a.pytest, A2T, "test_a2_manifest_is_frozen_and_binds_the_chain",
                    "test_prepilot_files_are_the_ones_committed_before_the_pilots", "test_every_a2_file_is_frozen")
    c["03_a2_frozen"] = {"pass": rc == 0 and ok, "verify": o.strip(), "test": msg}
    c["04_original_manifest_unchanged"] = {"pass": sha(X / "prereg" / "FREEZE_MANIFEST.json") ==
                                           "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b"}
    c["05_a1_manifest_unchanged"] = {"pass": sha(X / "amendment_a1" / "FREEZE_MANIFEST_A1.json") ==
                                     "55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b"}
    ok, msg = nodes(a.pytest, A2T, "test_c1_c2_c3_c5_are_unchanged")
    for k in ("06_C1_unchanged", "07_C2_unchanged", "08_C3_unchanged", "09_C5_unchanged"):
        c[k] = {"pass": ok, "test": msg}
    ok, msg = nodes(a.pytest, A2T, "test_confirmatory_matrix_and_order_are_a1s_unchanged")
    ok1, msg1 = nodes(a.pytest, A1T, "test_amended_matrix_and_order_regenerate_byte_for_byte")
    c["10_confirmatory_matrix_unchanged"] = {"pass": ok and ok1, "test": [msg, msg1]}
    c["11_confirmatory_order_unchanged"] = {"pass": ok and ok1, "test": [msg, msg1]}
    ok, msg = nodes(a.pytest, A2T, "test_science_is_unchanged")
    ok1, msg1 = nodes(a.pytest, A1T, "test_frozen_science_is_the_xsys_001_files_unchanged", "test_frozen_values_are_unchanged")
    for k in ("12_eta_levels_unchanged", "13_thresholds_unchanged", "14_windows_unchanged", "15_hypotheses_unchanged",
              "16_primary_endpoint_unchanged", "17_zero_wrong_unchanged", "18_v2_unchanged", "19_px4_patch_unchanged"):
        c[k] = {"pass": ok and ok1, "test": [msg, msg1]}
    camps = [str(p) for p in (REPO / "research").rglob("CAMPAIGN.json")]
    flights = [str(p) for pat in ("XS1-*", "XS1A1-*") for p in (REPO / "research").rglob(pat)]
    stage_out = [str(p) for pat in ("STAGE1*.json", "KEY.json", "QC.json", "RESULTS.json") for p in (REPO / "research" / "xsys_confirmatory_001").rglob(pat)]
    ok, msg = nodes(a.pytest, A2T, "test_confirmatory_data_only_under_an_accepted_manifest")
    c["20_confirmatory_flights_zero"] = {"pass": ok and not camps and not flights, "campaigns": camps,
                                         "confirmatory_logs_or_records": flights, "count": len(flights)}
    c["21_confirmatory_analysis_trials_zero"] = {"pass": not stage_out, "stage_outputs": stage_out, "count": 0 if not stage_out else len(stage_out)}

    # executor: dry run lists the A1 order; the gate matches the decision; a real run is probed only with a
    # nonexistent PX4 tree, so it cannot fly whatever the gate says
    rc, o, e = run([py, HERE / "execution_a2" / "run_confirmatory_a2.py", "--dry-run", "--px4-src", a.px4_src,
                    "--build", a.build, "--out", s / "exec", "--work", s / "work"])
    lines = [ln for ln in o.splitlines() if ln.strip()]
    listed = [ln.split()[3] for ln in lines[:-1]] if rc == 0 else []
    order = [r["flight_id"] for r in csv.DictReader(open(X / "amendment_a1" / "EXECUTION_ORDER_A1.csv"))]
    c["22_executor_dry_run_lists_a1_order"] = {"pass": rc == 0 and listed == order and len(listed) == 66
                                               and not list((s / "exec").glob("*")),
                                               "summary": json.loads(lines[-1]) if rc == 0 else e[-300:]}
    decision = json.loads((HERE / "C4_A2_RESULTS.json").read_text())["decision"]
    rc_f, _, e_f = run([py, HERE / "execution_a2" / "run_confirmatory_a2.py", "--px4-src", s / "no_px4_tree",
                        "--build", s / "no_px4_build", "--out", s / "exec_real", "--work", s / "work_real"])
    expect = "PX4 source" if decision == READY else "NOT ACCEPTED"
    c["23_executor_gate_matches_decision"] = {"pass": rc_f != 0 and expect in e_f and not list((s / "exec_real").glob("*")),
                                              "decision": decision, "refusal": e_f.strip()[-220:]}

    victim = HERE / "C4_A2_RESULTS.json"
    original = victim.read_bytes()
    try:
        victim.write_bytes(original.replace(b'"label"', b'"label" ', 1))
        rc_t, o_t, _ = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", T["a2_amendment"]], cwd=REPO)
        rc_v, _, _ = run([py, HERE / "freeze_a2.py", "verify"])
        rc_x, _, e_x = run([py, HERE / "execution_a2" / "run_confirmatory_a2.py", "--dry-run", "--px4-src", a.px4_src,
                            "--build", a.build, "--out", s / "exec_t", "--work", s / "work_t"])
    finally:
        victim.write_bytes(original)
    rc_r, _, _ = run([py, HERE / "freeze_a2.py", "verify"])
    c["24_tamper_detected"] = {"pass": rc_t != 0 and rc_v != 0 and rc_x != 0 and "FREEZE VIOLATION" in e_x and rc_r == 0,
                               "guard_test_failed": rc_t != 0, "freeze_a2_verify_failed": rc_v != 0,
                               "executor_refused": rc_x != 0, "restored_and_verified": rc_r == 0}
    rc_all, o_all, _ = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", *T.values()], cwd=REPO)
    c["25_all_guard_tests"] = {"pass": rc_all == 0, "summary": (o_all.strip().splitlines() or [""])[-1]}

    res = {"label": "XSYS-001-A2 POST-FREEZE VALIDATION - NO CONFIRMATORY FLIGHT",
           "a2_manifest_sha256": sha(HERE / "FREEZE_MANIFEST_A2.json"), "decision": decision,
           "checks": dict(sorted(c.items())), "all_pass": all(v["pass"] for v in c.values())}
    text = json.dumps(res, indent=1, default=float) + "\n"
    for path, tag in sorted({str(Path(a.build).resolve()): "<build>", str(s.resolve()): "<scratch>",
                             str(Path(a.px4_src).resolve()): "<px4-src>", str(REPO): "<repo>"}.items(),
                            key=lambda kv: -len(kv[0])):
        text = text.replace(path, tag)
    (HERE / "POST_FREEZE_CHECK_A2.json").write_text(text)
    print(json.dumps({k: v["pass"] for k, v in res["checks"].items()} | {"all_pass": res["all_pass"]}, indent=1))


if __name__ == "__main__":
    main()
