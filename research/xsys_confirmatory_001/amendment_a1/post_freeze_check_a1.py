#!/usr/bin/env python3
"""XSYS-001-A1 post-freeze validation: the 20 checks of the amendment request.
Flies nothing; writes POST_FREEZE_CHECK_A1.json (not part of the freeze).

  post_freeze_check_a1.py --px4-src <547e2ca + patch> --build <px4-src>/build/px4_sitl_default
                          --sweep <decompressed apparatus sweep> --scratch <dir> --pytest <python with pytest>
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
X = HERE.parent
REPO = X.parents[1]
MAN = HERE / "FREEZE_MANIFEST_A1.json"
PARENT = X / "prereg" / "FREEZE_MANIFEST.json"
T_ORIG = REPO / "tests" / "test_xsys_001_preregistration.py"
T_A1 = REPO / "tests" / "test_xsys_001_a1_amendment.py"


def run(cmd, **kw):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    return p.returncode, p.stdout, p.stderr


def sha(p):
    return subprocess.run(["sha256sum", str(p)], capture_output=True, text=True).stdout.split()[0]


def pytest_nodes(py, test, *names):
    ids = [f"{test}::{n}" for n in names]
    rc, o, e = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *ids], cwd=REPO)
    return rc == 0, o.strip().splitlines()[-1] if o.strip() else e.strip()[-200:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--px4-src", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--sweep", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--pytest", required=True)
    a = ap.parse_args()
    py = sys.executable
    s = Path(a.scratch)
    if s.exists():
        shutil.rmtree(s)
    s.mkdir(parents=True)
    c = {}
    A1T = str(T_A1)

    ok, msg = pytest_nodes(a.pytest, A1T, "test_original_preregistration_and_manifest_are_byte_identical")
    rc, o, _ = run([py, X / "prereg" / "freeze.py", "verify"])
    c["01_original_preregistration_byte_identical"] = {"pass": ok and rc == 0, "freeze_py_verify": o.strip(), "test": msg}
    c["02_original_manifest_byte_identical"] = {"pass": sha(PARENT) == "868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b",
                                                "sha256": sha(PARENT)}
    rc, o, _ = run([py, HERE / "freeze_a1.py", "verify"])
    ok, msg = pytest_nodes(a.pytest, A1T, "test_amendment_manifest_is_the_frozen_one_and_binds_the_original",
                           "test_every_amendment_file_matches_its_manifest", "test_amendment_covers_every_amendment_file")
    c["03_amendment_exists_and_frozen"] = {"pass": rc == 0 and ok, "freeze_a1_verify": o.strip(), "test": msg}
    ok, msg = pytest_nodes(a.pytest, A1T, "test_amended_matrix_and_order_regenerate_byte_for_byte")
    c["04_revised_matrix_regenerates"] = {"pass": ok, "test": msg}
    c["05_revised_order_regenerates"] = {"pass": ok, "test": msg}
    ok, msg = pytest_nodes(a.pytest, A1T, "test_frozen_science_is_the_xsys_001_files_unchanged",
                           "test_frozen_values_are_unchanged")
    for k in ("06_hypotheses_unchanged", "07_eta_set_unchanged", "08_thresholds_unchanged",
              "09_temporal_windows_unchanged", "10_primary_endpoint_unchanged", "11_zero_wrong_unchanged",
              "12_statistical_decision_rule_unchanged", "13_v2_files_unchanged", "14_px4_apparatus_unchanged"):
        c[k] = {"pass": ok, "test": msg}
    ok2, msg2 = pytest_nodes(a.pytest, A1T, "test_matched_pairs_and_levels_are_unchanged")
    c["07_eta_set_unchanged"] = {"pass": ok and ok2, "test": msg2}
    ok, msg = pytest_nodes(a.pytest, A1T, "test_neither_superseded_nor_unaccepted_design_is_ever_flown")
    camps = [str(p) for p in (REPO / "research").rglob("CAMPAIGN.json")]
    logs = [str(p) for pat in ("XS1-*", "XS1A1-*") for p in (REPO / "research").rglob(pat)]
    c["15_no_confirmatory_data"] = {"pass": ok and not camps and not logs, "campaign_files": camps,
                                    "confirmatory_logs": logs, "test": msg}

    # 16-18 executor
    out = s / "exec"
    rc, o, e = run([py, HERE / "execution_a1" / "run_confirmatory_a1.py", "--dry-run", "--px4-src", a.px4_src,
                    "--build", a.build, "--out", out, "--work", s / "work"])
    lines = [ln for ln in o.splitlines() if ln.strip()]
    listed = [ln.split()[3] for ln in lines[:-1]] if rc == 0 else []
    order = [r["flight_id"] for r in csv.DictReader(open(HERE / "EXECUTION_ORDER_A1.csv"))]
    rows = {r["flight_id"]: r for r in csv.DictReader(open(HERE / "FLIGHT_MATRIX_A1.csv"))}
    onsets_match_matrix = all(ln.split()[-1] == rows[ln.split()[3]]["t_onset_s"] for ln in lines[:-1]) if rc == 0 else False
    ok, msg = pytest_nodes(a.pytest, A1T, "test_executor_flies_the_amended_matrix_with_the_frozen_driver")
    c["16_executor_points_to_amended_matrix"] = {"pass": rc == 0 and listed == order and onsets_match_matrix and ok,
                                                 "listed_equals_A1_order": listed == order, "test": msg,
                                                 "summary": json.loads(lines[-1]) if rc == 0 else e[-300:]}
    c["17_dry_run_lists_66_flights"] = {"pass": len(listed) == 66 == len(order), "listed": len(listed)}
    flown = list(out.glob("*.ulg")) + list(out.glob("CAMPAIGN.json"))
    # the acceptance gate, probed WITHOUT --dry-run but with a nonexistent PX4 tree and build: even a broken
    # gate could not fly, and a refusal naming NOT ACCEPTED proves the gate stops the run first
    rc_f, _, e_f = run([py, HERE / "execution_a1" / "run_confirmatory_a1.py", "--px4-src", s / "no_px4_tree",
                        "--build", s / "no_px4_build", "--out", s / "exec_real", "--work", s / "work_real"])
    refused = rc_f != 0 and "NOT ACCEPTED" in e_f and not list((s / "exec_real").glob("*"))
    c["18_executor_does_not_fly"] = {"pass": rc == 0 and not flown and not (out / "EXECUTION_LOG.jsonl").exists()
                                     and refused,
                                     "dry_run_files_written": [p.name for p in out.glob("*")],
                                     "real_run_refused_by_acceptance_gate": refused,
                                     "refusal": e_f.strip()[-200:]}

    # 19 blinding: the A1 chain end to end on apparatus data (dry-run mode), then inspect stage 1's inputs
    rc0, o0, e0 = run([py, X / "pipeline" / "dry_run_matrix.py", a.sweep, s / "dry"])
    d = s / "dry"
    cmds = [
        [py, HERE / "pipeline_a1" / "stage0_prepare_a1.py", "--mode", "dry-run", "--flight-matrix", d / "DRY_RUN_FLIGHT_MATRIX.csv",
         "--analysis-matrix", d / "DRY_RUN_ANALYSIS_MATRIX.csv", "--flights", a.sweep, "--blind", d / "blind",
         "--key", d / "KEY.json", "--qc", d / "QC.json"],
        [py, X / "pipeline" / "stage1_evidence.py", "--freeze-manifest", MAN, "--blind", d / "blind",
         "--calibration", X / "calibration" / "CALIBRATION.json", "--out", d / "STAGE1.json"],
        [py, HERE / "pipeline_a1" / "stage2_score_a1.py", "--stage1", d / "STAGE1.json", "--key", d / "KEY.json",
         "--qc", d / "QC.json", "--analysis-matrix", d / "DRY_RUN_ANALYSIS_MATRIX.csv", "--out", d / "RESULTS.json"],
    ]
    rcs = [run(cmd)[0] for cmd in cmds]
    blind = d / "blind"
    npz = sorted(blind.glob("*.npz"))
    keys_ok, rel_ok = True, True
    for p in npz:
        z = np.load(p)
        keys_ok &= sorted(z.files) == sorted(["t_rel", "rpm_obs", "cmd_sim", "cmd_alloc", "gyro", "accel",
                                              "ekf_test_ratio_max", "hte_test_ratio", "rotor_px", "rotor_py"])
        rel_ok &= bool(abs(z["t_rel"][0] + 5.0) < 0.01)
    names_ok = all(len(p.stem) == 16 and all(ch in "0123456789abcdef" for ch in p.stem) for p in npz)
    index = json.loads((blind / "INDEX.json").read_text()) if (blind / "INDEX.json").exists() else None
    seal = json.loads((d / "STAGE1.seal.json").read_text()) if (d / "STAGE1.seal.json").exists() else {}
    ok, msg = pytest_nodes(a.pytest, A1T, "test_stage1_is_unchanged_and_blind_and_wrappers_only_redirect_paths",
                           "test_order_does_not_reveal_role_level_or_segment")
    ok_o, msg_o = pytest_nodes(a.pytest, str(T_ORIG), "test_blind_stage_cannot_name_a_label_source")
    # the stage wrappers' manifest check, confirmatory mode, without flights
    fl = s / "no_flights"
    fl.mkdir()
    (fl / "CAMPAIGN.json").write_text(json.dumps({"freeze_manifest_sha256": sha(MAN), "px4_sha256": "x",
                                                   "source_verified": True}))
    base = [py, HERE / "pipeline_a1" / "stage0_prepare_a1.py", "--mode", "confirmatory", "--freeze-manifest", MAN,
            "--analysis-matrix", HERE / "ANALYSIS_MATRIX_A1.csv", "--flights", fl, "--blind", s / "b",
            "--key", s / "k.json", "--qc", s / "q.json"]
    rc_a, _, e_a = run(base + ["--flight-matrix", HERE / "FLIGHT_MATRIX_A1.csv"])
    rc_b, _, e_b = run(base + ["--flight-matrix", X / "prereg" / "FLIGHT_MATRIX.csv"])
    c["19_stage1_remains_blind"] = {
        "pass": (rc0 == 0 and rcs == [0, 0, 0] and len(npz) == 33 and keys_ok and rel_ok and names_ok
                 and index == sorted(p.stem for p in npz) and seal.get("freeze_manifest_sha256") == sha(MAN)
                 and ok and ok_o and rc_a != 0 and "campaign incomplete" in e_a
                 and rc_b != 0 and "FREEZE VIOLATION" in e_b),
        "a1_chain_dry_run_exit_codes": rcs, "blinded_inputs": len(npz),
        "npz_holds_only_onboard_signals": keys_ok, "time_is_relative_to_t0": rel_ok,
        "file_names_are_opaque_ids": names_ok, "stage1_verified_A1_manifest": seal.get("freeze_manifest_sha256") == sha(MAN),
        "stage0_a1_accepts_A1_matrix_then_refuses_incomplete_campaign": rc_a != 0 and "campaign incomplete" in e_a,
        "stage0_a1_refuses_original_matrix": rc_b != 0 and "FREEZE VIOLATION" in e_b,
        "tests": [msg, msg_o]}

    # 20 tamper one amended frozen file
    victim = HERE / "FLIGHT_MATRIX_A1.csv"
    original = victim.read_bytes()
    try:
        victim.write_bytes(original.replace(b"0.95,SIH_MOT_EFF1", b"0.94,SIH_MOT_EFF1", 1))
        rc_t, o_t, _ = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", T_A1], cwd=REPO)
        rc_v, _, _ = run([py, HERE / "freeze_a1.py", "verify"])
        rc_x, _, e_x = run([py, HERE / "execution_a1" / "run_confirmatory_a1.py", "--dry-run", "--px4-src", a.px4_src,
                            "--build", a.build, "--out", s / "exec_t", "--work", s / "work_t"])
    finally:
        victim.write_bytes(original)
    rc_r, _, _ = run([py, HERE / "freeze_a1.py", "verify"])
    c["20_tamper_detected"] = {"pass": rc_t != 0 and rc_v != 0 and rc_x != 0 and "FREEZE VIOLATION" in e_x and rc_r == 0,
                               "guard_test_failed": rc_t != 0, "freeze_a1_verify_failed": rc_v != 0,
                               "executor_refused": rc_x != 0, "restored_and_verified": rc_r == 0,
                               "guard_test_summary": o_t.strip().splitlines()[-1] if o_t.strip() else ""}

    # both guard tests, whole files
    rc1, o1, _ = run([a.pytest, "-m", "pytest", "-q", "-p", "no:cacheprovider", T_ORIG, T_A1], cwd=REPO)
    res = {"label": "XSYS-001-A1 POST-FREEZE VALIDATION - NO CONFIRMATORY FLIGHT",
           "amendment_manifest_sha256": sha(MAN), "parent_manifest_sha256": sha(PARENT),
           "checks": dict(sorted(c.items())), "guard_tests": {"pass": rc1 == 0, "summary": o1.strip().splitlines()[-1]},
           "all_pass": all(v["pass"] for v in c.values()) and rc1 == 0}
    text = json.dumps(res, indent=1, default=float) + "\n"
    for path, tag in sorted({str(Path(a.build).resolve()): "<build>", str(s.resolve()): "<scratch>",
                             str(Path(a.px4_src).resolve()): "<px4-src>", str(Path(a.sweep).resolve()): "<sweep>",
                             str(REPO): "<repo>"}.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(path, tag)
    (HERE / "POST_FREEZE_CHECK_A1.json").write_text(text)
    print(json.dumps({k: v["pass"] for k, v in res["checks"].items()} | {"guard_tests": rc1 == 0, "all_pass": res["all_pass"]}, indent=1))


if __name__ == "__main__":
    main()
