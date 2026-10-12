#!/usr/bin/env python3
"""XSYS-001 threshold calibration from APPARATUS data only.

Inputs are the apparatus ULogs committed under
research/px4_actuator_effectiveness/raw_ulog/ (decompressed; each file's
SHA-256 is checked against that directory's SHA256SUMS). No confirmatory data
exist when this runs, and none may ever be passed to it.

RULE, fixed before any number below was computed:
  every threshold = 2 x the largest |value| of the same statistic observed
  under the null (nominal flight), over pseudo-onsets every 0.5 s in hover.
  The factor 2 is a specificity margin for nuisance conditions (headings,
  onset offsets) the apparatus did not fly.

  s_dyn, the detectability slope of the dynamics witness, is the
  least-squares slope through the origin of D_T1 on L_T1 over the apparatus
  fault trials (eta 0.9 ... 0.5). It sets only when "dynamics nominal" may be
  affirmed; it is never a decision threshold.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
import xsys_extract as X  # noqa: E402
import xsys_features as F  # noqa: E402

HOVER_FROM_S = 22.0
PSEUDO_STEP_S = 0.5


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def stats_at(onboard, truth, t0_us, m=0):
    ob, _, _ = X.cut(onboard, truth, t0_us)
    t = ob["t_rel"]
    rho, _ = F.rpm_ratio(ob["rpm_obs"][:, m], ob["cmd_sim"][:, m])
    ax = F.loss_axis(ob["rotor_px"][m], ob["rotor_py"][m])
    out = {}
    for w in ("T1", "T3"):
        L, okL = F.local_deficit(rho, ob["cmd_sim"][:, m], t, w)
        out[f"L_{w}"] = L if okL else None
    D, okD = F.dynamics_statistic(ob["gyro"], t, ax, "T1")
    out["D_T1"] = D if okD else None
    D3, okD3 = F.dynamics_statistic(ob["gyro"], t, ax, "T3")
    out["D_T3"] = D3 if okD3 else None
    C, okC = F.compensation_statistic(ob["cmd_alloc"], t, m, "T3")
    out["C_T3"] = C if okC else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nominal", nargs="+", required=True, help="apparatus nominal ULogs (no fault)")
    ap.add_argument("--controls", nargs="+", required=True, help="apparatus eta=1.00 sweep ULogs")
    ap.add_argument("--faults", nargs="+", required=True, help="apparatus sweep ULogs with eta < 1")
    ap.add_argument("--sha256sums", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    known = {}
    for f in a.sha256sums:
        for line in Path(f).read_text().splitlines():
            h, name = line.split(None, 1)
            known.setdefault(name.strip(), set()).add(h)
    inputs = []
    for p in a.nominal + a.controls + a.faults:
        h = sha256(p)
        if h not in known.get(Path(p).name, set()):
            raise SystemExit(f"{p}: SHA-256 not in the apparatus SHA256SUMS")
        inputs.append({"file": Path(p).name, "sha256": h})

    null = {"L_T1": [], "L_T3": [], "D_T1": [], "D_T3": [], "C_T3": []}
    for p in a.nominal + a.controls:
        u, params, ob, tr = X.load_full(p)
        g = ob["t_abs_us"]
        st = u.get_dataset("vehicle_status").data
        armed = st["timestamp"][st["arming_state"] == 2]
        t_end = armed[-1] * 1e-6 - 0.1
        for t0s in np.arange(HOVER_FROM_S + 5.0, t_end - 0.2, PSEUDO_STEP_S):
            s = stats_at(ob, tr, int(round(t0s * 1e6 / 4000)) * 4000)
            for k in ("L_T1", "D_T1"):
                if s[k] is not None:
                    null[k].append(s[k])
            if t0s + 15.0 <= t_end:
                for k in ("L_T3", "D_T3", "C_T3"):
                    if s[k] is not None:
                        null[k].append(s[k])

    faults = []
    for p in a.faults:
        u, params, ob, tr = X.load_full(p)
        ev = X.onset_time(u, "SIH_MOT_EFF1")
        eta = ev[2]
        if eta < 0.5 - 1e-9:
            continue              # below the control-authority boundary: excluded by design
        s = stats_at(ob, tr, ev[1])
        s.update({"file": Path(p).name, "eta": eta,
                  "C_T3_predicted_from_L_T3": 1.0 / (1.0 - s["L_T3"]) - 1.0})
        faults.append(s)

    maxabs = {k: float(np.max(np.abs(v))) for k, v in null.items()}
    L1 = np.array([f["L_T1"] for f in faults])
    D1 = np.array([f["D_T1"] for f in faults])
    s_dyn = float((D1 @ L1) / (L1 @ L1))
    cal = {
        "delta_rpm": 2.0 * max(maxabs["L_T1"], maxabs["L_T3"]),
        "theta_dyn": 2.0 * maxabs["D_T1"],
        "theta_ctrl": 2.0 * maxabs["C_T3"],
        "s_dyn": s_dyn,
    }
    report = {
        "rule": __doc__.split("RULE, fixed before any number below was computed:")[1].strip(),
        "calibration": cal,
        "null_max_abs": maxabs,
        "null_counts": {k: len(v) for k, v in null.items()},
        "null_quantiles": {k: {q: float(np.quantile(np.abs(v), q)) for q in (0.5, 0.99, 1.0)}
                           for k, v in null.items()},
        "fault_trials": faults,
        "fit_residual_rms_D_T1": float(np.sqrt(np.mean((D1 - s_dyn * L1) ** 2))),
        "inputs": inputs,
    }
    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ("calibration", "null_max_abs", "null_counts")}, indent=1))
    print(f"{'eta':>5} {'L_T1':>8} {'D_T1':>8} {'L_T3':>8} {'C_T3':>8} {'C_pred':>8} {'D_T3':>8}")
    for f in sorted(faults, key=lambda f: -f["eta"]):
        print(f"{f['eta']:5.2f} {f['L_T1']:8.4f} {f['D_T1']:8.4f} {f['L_T3']:8.4f} {f['C_T3']:8.4f} "
              f"{f['C_T3_predicted_from_L_T3']:8.4f} {f['D_T3']:8.4f}")


if __name__ == "__main__":
    main()
