#!/usr/bin/env python3
"""XSYS-001 STAGE 1 — blinded evidence and CSIA v2 localization.

Reads ONLY <blind>/INDEX.json and <blind>/<opaque_id>.npz (on-board signals,
no labels, no parameters, no file names) and the frozen calibration. It never
opens the stage-0 key or QC file; tests/test_xsys_001_preregistration.py
checks that this file names neither.

For every input, every motor m = 0..3 is a potential subject. For each
VARIANT and CHECKPOINT it builds v2 EvidenceRecords and calls v2 localize()
through xsys_v2_adapter:

  checkpoint C1 = t0 + 0.2 s   local symptom from T1
  checkpoint C3 = t0 + 15 s    local symptom from T3   (PRIMARY)

  V0 LOCAL_ONLY     dynamics and compensation withheld (the BL-4 baseline)
  V1 DYN_ONLY       dynamics from T1
  V2 CTRL_ONLY      compensation from T3 (C3 only)
  V3 TEMPORAL       dynamics from T1 + compensation from T3   (PRIMARY)
  V4 INVALID_WINDOW dynamics computed over T3, outside its valid window
                    (temporal-validity negative control; C3 only)

The output is sealed (SHA-256) before stage 2 may join any label.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import xsys_features as F  # noqa: E402
import xsys_freeze_check as FC  # noqa: E402
import xsys_v2_adapter as A  # noqa: E402

VARIANTS = ("V0_LOCAL_ONLY", "V1_DYN_ONLY", "V2_CTRL_ONLY", "V3_TEMPORAL", "V4_INVALID_WINDOW")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def motor_features(ob, m, cal):
    t = ob["t_rel"]
    rho, _ = F.rpm_ratio(ob["rpm_obs"][:, m], ob["cmd_sim"][:, m])
    ax = F.loss_axis(ob["rotor_px"][m], ob["rotor_py"][m])
    L1, ok1 = F.local_deficit(rho, ob["cmd_sim"][:, m], t, "T1")
    L3, ok3 = F.local_deficit(rho, ob["cmd_sim"][:, m], t, "T3")
    D1, okd1 = F.dynamics_statistic(ob["gyro"], t, ax, "T1")
    D3, okd3 = F.dynamics_statistic(ob["gyro"], t, ax, "T3")
    C3, okc3 = F.compensation_statistic(ob["cmd_alloc"], t, m, "T3")
    post = t >= 0
    hit = np.nonzero(post & np.isfinite(rho) & ((1.0 - rho ** 2) >= cal["delta_rpm"]))[0]
    return {
        "L_T1": L1 if ok1 else None, "L_T3": L3 if ok3 else None,
        "D_T1": D1 if okd1 else None, "D_T3": D3 if okd3 else None,
        "C_T3": C3 if okc3 else None,
        "rpm_T1": F.rpm_witness(L1, ok1, cal["delta_rpm"]),
        "rpm_T3": F.rpm_witness(L3, ok3, cal["delta_rpm"]),
        "dyn_T1": F.dynamics_witness(D1, okd1, L1 if ok1 else float("nan"), cal),
        "dyn_T3_invalid": F.dynamics_witness(D3, okd3, L3 if ok3 else float("nan"), cal),
        "ctrl_T3": F.compensation_witness(C3, okc3, L3 if ok3 else float("nan"), cal),
        "detection_latency_s": float(t[hit[0]]) if len(hit) else None,
    }


def plan(variant, checkpoint, f):
    """(rpm, dyn, ctrl, windows) available to a variant at a checkpoint."""
    rpm = f["rpm_T1"] if checkpoint == "C1" else f["rpm_T3"]
    rpm_w = "T1" if checkpoint == "C1" else "T3"
    dyn, dyn_w, ctrl, ctrl_w = None, "withheld", None, "withheld"
    if variant in ("V1_DYN_ONLY", "V3_TEMPORAL"):
        dyn, dyn_w = f["dyn_T1"], "T1"
    if variant in ("V2_CTRL_ONLY", "V3_TEMPORAL") and checkpoint == "C3":
        ctrl, ctrl_w = f["ctrl_T3"], "T3"
    if variant == "V4_INVALID_WINDOW" and checkpoint == "C3":
        dyn, dyn_w = f["dyn_T3_invalid"], "T3 (INVALID: outside its window)"
    return rpm, dyn, ctrl, {"rpm": rpm_w, "dyn": dyn_w, "ctrl": ctrl_w}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True)
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--freeze-manifest", help="confirmatory runs: verify the frozen code before computing")
    a = ap.parse_args()
    manifest_sha = FC.verify_frozen(a.freeze_manifest)[1] if a.freeze_manifest else None
    blind = Path(a.blind)
    cal = json.loads(Path(a.calibration).read_text())["calibration"]
    ids = json.loads((blind / "INDEX.json").read_text())
    out, input_hashes = {}, {}
    for oid in ids:
        p = blind / f"{oid}.npz"
        input_hashes[oid] = sha256_bytes(p.read_bytes())
        ob = dict(np.load(p))
        t_start = time.perf_counter()
        feats = {f"motor_{m}": motor_features(ob, m, cal) for m in range(4)}
        verdicts = {}
        for cp in ("C1", "C3"):
            for v in VARIANTS:
                if cp == "C1" and v in ("V2_CTRL_ONLY", "V4_INVALID_WINDOW"):
                    continue
                per = {}
                for subj, f in feats.items():
                    rpm, dyn, ctrl, w = plan(v, cp, f)
                    stats = {"L": f["L_T1"] if cp == "C1" else f["L_T3"],
                             "D": f["D_T3"] if v == "V4_INVALID_WINDOW" else f["D_T1"], "C": f["C_T3"]}
                    loc = A.localize_subject(A.records_for(subj, rpm, dyn, ctrl, stats, w), subj)
                    per[subj] = None if loc is None else loc.to_dict()
                verdicts[f"{cp}/{v}"] = per
        compute_s = time.perf_counter() - t_start
        t = ob["t_rel"]
        west = {"ekf_test_ratio_max_T1": F.max_in_window(ob["ekf_test_ratio_max"], t, "T1"),
                "ekf_test_ratio_max_T2": F.max_in_window(ob["ekf_test_ratio_max"], t, "T2"),
                "hte_test_ratio_max_T1": F.max_in_window(ob["hte_test_ratio"], t, "T1"),
                "hte_test_ratio_max_T2": F.max_in_window(ob["hte_test_ratio"], t, "T2")}
        out[oid] = {"features": feats, "verdicts": verdicts, "w_est_exploratory": west,
                    "computational_latency_s": compute_s}
    body = json.dumps({"calibration": cal, "trials": out}, indent=1, sort_keys=True, default=float).encode()
    Path(a.out).write_bytes(body)
    seal = {"stage1_output": Path(a.out).name, "stage1_output_sha256": sha256_bytes(body),
            "freeze_manifest_sha256": manifest_sha,
            "inputs_sha256": input_hashes, "sealed_at_unix": time.time()}
    Path(a.out).with_suffix(".seal.json").write_text(json.dumps(seal, indent=1))
    print(json.dumps({"trials": len(out), "stage1_output_sha256": seal["stage1_output_sha256"]}))


if __name__ == "__main__":
    main()
