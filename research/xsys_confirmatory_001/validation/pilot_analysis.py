#!/usr/bin/env python3
"""XSYS-001 nuisance pilot: APPARATUS data, nominal flights only, NOT CONFIRMATORY.

Eight nominal flights (no fault on any motor) at headings 15, 105, 195 and 285
degrees, each flown twice:
  noevent_pilot_nominal_hXXX   SDLOG_DIRS_MAX set to 7 at 30 s: already the
                               value, so no parameter_update is published
  pilot_nominal_hXXX           SDLOG_DIRS_MAX set to 8 at 30 s: the benign
                               onset event the NB flights use
The logs are archived in research/xsys_confirmatory_001/apparatus_pilot/.

Questions, each answered from the logs:
  Q1 does SIH_LOC_YAW0 set the true heading, and does it hold?
  Q2 does heading select the simulator noise realization? (pre-arm samples;
     and where the event and no-event flights of one heading first differ)
  Q3 does the benign event publish one parameter_update, and where is t0?
  Q4 null excursions of the frozen statistics over all hover windows, against
     the frozen thresholds in calibration/CALIBRATION.json

Usage: pilot_analysis.py <dir with decompressed .ulg> <SHA256SUMS> <out.json>
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
import xsys_extract as X  # noqa: E402
import xsys_features as F  # noqa: E402

HEADINGS = (15, 105, 195, 285)
HOVER_FROM_S = 27.0
PSEUDO_STEP_S = 0.1


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    src, sums, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    want = dict(reversed(line.split()) for line in sums.read_text().splitlines() if line.endswith(".ulg"))
    names = [f"{kind}pilot_nominal_h{h:03d}" for kind in ("noevent_", "") for h in HEADINGS]
    for n in names:
        if sha256(src / f"{n}.ulg") != want[f"{n}.ulg"]:
            raise SystemExit(f"{n}.ulg does not match SHA256SUMS")
    cal = json.loads((HERE.parent / "calibration" / "CALIBRATION.json").read_text())["calibration"]

    loaded = {n: X.load_full(src / f"{n}.ulg") for n in names}
    res = {"label": "APPARATUS NUISANCE PILOT - NOT CONFIRMATORY", "flights": {}}

    # Q1 heading
    for n, (u, params, ob, tr) in loaded.items():
        g = ob["t_abs_us"]
        yaw = np.degrees(tr["yaw"])
        at = lambda s: round(float(yaw[np.searchsorted(g, int(s * 1e6))]), 2)  # noqa: E731
        res["flights"][n] = {"SIH_LOC_YAW0_rad": params.get("SIH_LOC_YAW0"), "dropouts": len(u.dropouts),
                             "true_yaw_deg": {"5s": at(5), "25s": at(25), "45s": at(45)}}

    # Q2 noise realization: identical pre-arm accelerometer samples (1.0-9.5 s)
    ident = {}
    for a in names:
        for b in names:
            A, B = loaded[a][2], loaded[b][2]
            common, ia, ib = np.intersect1d(A["t_abs_us"], B["t_abs_us"], return_indices=True)
            m = (common > 1_000_000) & (common < 9_500_000)
            ident.setdefault(a, {})[b] = round(float(np.mean(A["accel"][ia][m, 2] == B["accel"][ib][m, 2])), 2)
    res["prearm_identical_accel_fraction"] = ident

    # Q2b realization branching: first step at which the event and no-event
    # flight of the same heading differ (RPM or gyro), before or after onset
    res["event_vs_noevent_first_difference_s"] = {}
    for h in HEADINGS:
        o1, o2 = loaded[f"pilot_nominal_h{h:03d}"][2], loaded[f"noevent_pilot_nominal_h{h:03d}"][2]
        common, i1, i2 = np.intersect1d(o1["t_abs_us"], o2["t_abs_us"], return_indices=True)
        same = (np.all(o1["rpm_obs"][i1] == o2["rpm_obs"][i2], axis=1)
                & np.all(o1["gyro"][i1] == o2["gyro"][i2], axis=1))
        res["event_vs_noevent_first_difference_s"][f"h{h:03d}"] = (
            None if same.all() else round(float(common[np.argmin(same)]) * 1e-6, 3))

    # Q3 onset event
    for n in names:
        onset = X.onset_time(loaded[n][0], "SDLOG_DIRS_MAX")
        res["flights"][n]["onset_event"] = (None if onset is None else
                                            {"t_param_update_us": int(onset[0]), "t0_us": int(onset[1]),
                                             "t0_minus_update_us": int(onset[1] - onset[0]),
                                             "value": onset[2]})

    # Q4 null excursions over every hover pseudo-onset
    allv = {"L_T1": [], "D_T1": [], "C_T3": []}
    for n, (u, params, ob, tr) in loaded.items():
        st = u.get_dataset("vehicle_status").data
        t_end = st["timestamp"][st["arming_state"] == 2][-1] * 1e-6 - 0.1
        vals = {"L_T1": [], "D_T1": [], "C_T3": []}
        for t0s in np.arange(HOVER_FROM_S, t_end - 0.2, PSEUDO_STEP_S):
            o, _, _ = X.cut(ob, tr, int(round(t0s * 1e6 / 4000)) * 4000)
            t = o["t_rel"]
            rho, _ = F.rpm_ratio(o["rpm_obs"][:, 0], o["cmd_sim"][:, 0])
            L, okL = F.local_deficit(rho, o["cmd_sim"][:, 0], t, "T1")
            D, okD = F.dynamics_statistic(o["gyro"], t, F.loss_axis(o["rotor_px"][0], o["rotor_py"][0]), "T1")
            if okL:
                vals["L_T1"].append(L)
            if okD:
                vals["D_T1"].append(D)
            if t0s + F.WINDOWS["T3"][1] <= t_end:
                C, okC = F.compensation_statistic(o["cmd_alloc"], t, 0, "T3")
                if okC:
                    vals["C_T3"].append(C)
        res["flights"][n]["null_max_abs"] = {k: float(np.max(np.abs(v))) for k, v in vals.items() if v}
        res["flights"][n]["null_counts"] = {k: len(v) for k, v in vals.items()}
        for k in allv:
            allv[k] += vals[k]
    thr = {"L_T1": cal["delta_rpm"], "D_T1": cal["theta_dyn"], "C_T3": cal["theta_ctrl"]}
    res["null_all_pilot"] = {k: {"max_abs": float(np.max(np.abs(v))), "p99_abs": float(np.quantile(np.abs(v), 0.99)),
                                 "n": len(v), "frozen_threshold": thr[k],
                                 "margin_threshold_over_max": float(thr[k] / np.max(np.abs(v)))}
                             for k, v in allv.items()}
    res["pseudo_onsets"] = {"from_s": HOVER_FROM_S, "step_s": PSEUDO_STEP_S,
                            "note": "overlapping windows; the counts are not independent samples"}
    out.write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps(res["null_all_pilot"], indent=1))
    print(json.dumps({n: (f["true_yaw_deg"], f["onset_event"]) for n, f in res["flights"].items()}, indent=0))


if __name__ == "__main__":
    main()
