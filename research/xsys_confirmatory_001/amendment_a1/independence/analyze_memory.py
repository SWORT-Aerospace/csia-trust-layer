#!/usr/bin/env python3
"""XSYS-001-A1: memory of the frozen signals and the required onset separation,
from the long nominal hover Q1 (DIAGNOSTIC_SPEC.json: DX6, DX2/DX3, C3, C5).

Usage: analyze_memory.py <Q1 .ulg> <Q1 trial .json> <out MEMORY.json>

Rule (frozen in the spec): S_min = 20 s + tau_mem; the design uses S = S_min
rounded UP to the next multiple of 5 s. C3 is then checked at [S, S + 10] s.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

import independence_diagnostics as ID

SETTLE_AFTER_ARM_S = 12.0          # the calibration's hover start: arm 10 s, hover from 22 s
STEP_S = 0.2
REPORT_LAGS_S = (0.2, 0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 60, 90, 120)


def main():
    ulg, rec_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    rec = json.loads(rec_path.read_text())
    if rec["onset_param"] != "SDLOG_DIRS_MAX" or "NOMINAL-ONLY" not in rec["extra"].get("purpose", ""):
        raise SystemExit("not a nominal-only A1 pilot record")
    f = ID.Flight(ulg)
    if f.sha256 != rec["ulog_sha256"]:
        raise SystemExit("ULog does not match its trial record")
    arm_s, disarm_s = f.t_arm_us * 1e-6, f.t_disarm_us * 1e-6
    lo_s, hi_s = arm_s + SETTLE_AFTER_ARM_S, disarm_s - 0.3
    res = {"label": "XSYS-001-A1 PILOT Q1 - NOMINAL ONLY - NOT CONFIRMATORY",
           "diagnostic_spec_sha256": ID.sha256(ID.HERE / "DIAGNOSTIC_SPEC.json"),
           "input": {"ulog": ulg.name, "sha256": f.sha256, "heading_deg": rec["heading_deg"]},
           "hover_s": [round(lo_s, 3), round(hi_s, 3)]}

    # ---- DX6 memory of the per-step signals
    sig = ID.memory_signals(f, lo_s, hi_s)
    max_lag = int(round(150.0 / 0.004))
    mem, curves = {}, {}
    for k, v in sig.items():
        ac = ID.acf(v, max_lag)
        mem[k] = ID.memory_length(ac, 0.004, 60.0)
        curves[k] = {str(L): float(ac[int(round(L / 0.004))]) for L in REPORT_LAGS_S if int(round(L / 0.004)) < len(ac)}
    if any(v is None for v in mem.values()):
        raise SystemExit(f"a memory length could not be established within the hover: {mem}")
    tau = max(mem.values())
    s_min = 20.0 + tau
    S = 5.0 * math.ceil(s_min / 5.0 - 1e-12)
    res["DX6_memory"] = {"per_signal_s": mem, "tau_mem_s": tau, "acf_at_lags_s": curves}
    res["separation"] = {"S_min_s": s_min, "S_s": S, "rule": "S_min = 20 s + tau_mem, rounded up to a multiple of 5 s"}

    # ---- DX2/DX3 frozen-statistic lag correlation in one stream; C3 at [S, S + 10]
    grid, s = ID.pseudo_onset_series(f, lo_s + 5.0, hi_s - 15.0, STEP_S, need_T3=True)
    keys = sorted(s)
    band = range(int(round(S / STEP_S)), int(round((S + 10.0) / STEP_S)) + 1)
    c3 = {}
    for m in range(4):
        for a in ("L_T1", "D_T1", "L_T3", "C_T3"):
            for b in ("L_T1", "D_T1", "L_T3", "C_T3"):
                xa, xb = s[f"{a}_m{m}"], s[f"{b}_m{m}"]
                vals = [ID.lag_corr(xa, xb, L) for L in band]
                vals = [v for v in vals if v is not None]
                c3[f"{a}(t)~{b}(t+D)_m{m}"] = float(np.mean(vals)) if vals else None
    worst = max(c3, key=lambda k: abs(c3[k]) if c3[k] is not None else -1)
    res["C3_statistic_lag_correlation"] = {
        "band_s": [S, S + 10.0], "pseudo_onsets": len(grid), "mean_rho_in_band": c3,
        "worst": {"pair": worst, "mean_rho": c3[worst]},
        "pass": all(v is not None and abs(v) <= 0.1 for v in c3.values())}
    res["statistic_lag_correlation_curves_m0"] = {
        k: {str(L): ID.lag_corr(s[k], s[k], int(round(L / STEP_S))) for L in REPORT_LAGS_S}
        for k in ("L_T1_m0", "D_T1_m0", "L_T3_m0", "C_T3_m0")}

    # ---- C5 on the long hover: frozen null statistics below thresholds; heading held
    res["C5_long_hover"] = ID.hover_nulls(f, lo_s + 5.0, hi_s, 0.5)
    ob, tr = f.full()
    g = ob["t_abs_us"]
    yaw = np.degrees(tr["yaw"])
    res["C5_long_hover"]["true_heading_deg_at"] = {
        f"{t:.0f}s": float(yaw[np.searchsorted(g, int(t * 1e6))]) for t in (lo_s, (lo_s + hi_s) / 2, hi_s - 1)}
    err = [((y - rec["heading_deg"] + 180) % 360) - 180 for y in res["C5_long_hover"]["true_heading_deg_at"].values()]
    res["C5_long_hover"]["max_heading_error_deg"] = float(np.max(np.abs(err)))
    res["C5_long_hover"]["pass"] = res["C5_long_hover"]["below_thresholds"] and res["C5_long_hover"]["max_heading_error_deg"] <= 5.0

    out.write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({"tau_mem": tau, "per_signal": mem, "S_min": s_min, "S": S,
                      "C3": res["C3_statistic_lag_correlation"]["pass"], "C3_worst": res["C3_statistic_lag_correlation"]["worst"],
                      "C5": res["C5_long_hover"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
