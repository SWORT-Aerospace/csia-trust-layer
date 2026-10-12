#!/usr/bin/env python3
"""XSYS-001-A1: acceptance criteria C1..C5 for the candidate nuisance design,
from the nominal-only design pilots Q2..Q5 and the long hover Q1.

Usage: analyze_design.py --memory MEMORY.json --q1 <ulg> <json> --design <ulg> <json> [...] --out DESIGN_CHECK.json

A design pilot is flown exactly as the candidate design schedules a
condition: pre-arm dwell so that arm = 10 s + S x slot, onset = arm + 20 s,
end = onset + 16 s, benign SDLOG_DIRS_MAX event at onset.
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

import independence_diagnostics as ID


def load(ulg, rec_path):
    rec = json.loads(Path(rec_path).read_text())
    if rec["onset_param"] != "SDLOG_DIRS_MAX" or "NOMINAL-ONLY" not in rec["extra"].get("purpose", ""):
        raise SystemExit(f"{rec_path}: not a nominal-only A1 pilot record")
    f = ID.Flight(ulg)
    if f.sha256 != rec["ulog_sha256"]:
        raise SystemExit(f"{ulg}: does not match its trial record")
    from pyulog import ULog
    ev = ID.XE.onset_time(ULog(str(ulg)), "SDLOG_DIRS_MAX")
    if ev is None:
        raise SystemExit(f"{ulg}: no benign onset event")
    f.t0_us = ev[1]
    f.t_pu_us = ev[0]
    f.rec = rec
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory", required=True)
    ap.add_argument("--q1", nargs=2, required=True)
    ap.add_argument("--design", nargs=2, action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    mem = json.loads(Path(a.memory).read_text())
    tau, S = mem["DX6_memory"]["tau_mem_s"], mem["separation"]["S_s"]
    q1 = load(*a.q1)
    des = [load(*d) for d in a.design]
    res = {"label": "XSYS-001-A1 DESIGN PILOTS - NOMINAL ONLY - NOT CONFIRMATORY",
           "diagnostic_spec_sha256": ID.sha256(ID.HERE / "DIAGNOSTIC_SPEC.json"),
           "memory_json_sha256": ID.sha256(a.memory), "tau_mem_s": tau, "S_s": S,
           "flights": {f.name: {"sha256": f.sha256, "heading_deg": f.rec["heading_deg"],
                                "slot": f.rec["extra"].get("slot"), "t_arm_s": f.t_arm_us * 1e-6,
                                "t0_s": f.t0_us * 1e-6, "t0_minus_update_us": int(f.t0_us - f.t_pu_us)}
                       for f in [q1] + des}}

    # C2: realised separations between design conditions >= 20 + tau_mem
    seps = {f"{x.name}|{y.name}": abs(x.t0_us - y.t0_us) * 1e-6 for x, y in combinations(des, 2)}
    res["C2_separation"] = {"required_s": 20.0 + tau, "design_S_s": S, "realised_onset_separations_s": seps,
                            "pass": S >= 20.0 + tau and min(seps.values()) >= 20.0 + tau - 0.01}

    # C1: no shared noise draws between spans (extended back by tau_mem), every lag
    c1 = {}
    for x, y in combinations(des, 2):
        c1[f"{x.name}|{y.name}"] = ID.identity_global(x, x.span_mask(x.t0_us, tau), y, y.span_mask(y.t0_us, tau))
    res["C1_noise_draw_identity"] = {"pairs": c1, "max_I": max(v["I"] for v in c1.values()),
                                     "pass": all(v["I"] <= 0.001 for v in c1.values())}
    # descriptive: each design span against Q1's whole flight (Q1 is not a design condition)
    q1_all = np.ones(len(q1.t), bool)
    res["replay_vs_Q1_descriptive"] = {
        f.name: ID.identity_global(f, f.span_mask(f.t0_us, tau), q1, q1_all) for f in des}

    # DX5: family membership among the design flights and Q1 at the same simulated time
    fam = {}
    for x, y in combinations([q1] + des, 2):
        edges, fr = ID.family_bins(x, y, 0.0, min(x.t[-1], y.t[-1]) * 1e-6)
        vals = [v for v in fr if v is not None]
        fam[f"{x.name}|{y.name}"] = {"same_fraction_prearm_1_9s": float(np.mean([v for e, v in zip(edges, fr) if 1 <= e < 9 and v is not None])),
                                     "same_fraction_overall": float(np.mean(vals)) if vals else None,
                                     "branch_time_s": ID.branch_time(edges, fr)}
    res["DX5_families_descriptive"] = fam

    # C4: trajectory correlation, spans aligned on t - t0
    c4 = {f"{x.name}|{y.name}": ID.trajectory_corr(x, x.t0_us, y, y.t0_us) for x, y in combinations(des, 2)}
    worst = max((abs(v), k, s) for k, d in c4.items() for s, v in d.items() if v is not None)
    res["C4_trajectory_correlation"] = {"pairs": c4, "worst": {"abs_r": worst[0], "pair": worst[1], "signal": worst[2]},
                                        "pass": worst[0] <= 0.1}

    # C5: threshold validity and heading, every design span and the long hover
    c5 = {}
    for f in des:
        arm = f.t_arm_us * 1e-6
        hov = ID.hover_nulls(f, arm + 17.0, f.t_disarm_us * 1e-6 - 0.3, 0.5)
        ob, tr = f.full()
        g = ob["t_abs_us"]
        m0 = (g >= f.t0_us - 5_000_000) & (g < f.t0_us)
        yaw0 = float(np.degrees(np.angle(np.nanmean(np.exp(1j * tr["yaw"][m0])))))
        err = ((yaw0 - f.rec["heading_deg"] + 180) % 360) - 180
        c5[f.name] = {**hov, "true_heading_T0_deg": yaw0, "heading_error_deg": float(err),
                      "pass": hov["below_thresholds"] and abs(err) <= 5.0}
    c5["Q1_long_hover"] = mem["C5_long_hover"]
    res["C5_threshold_validity"] = {"flights": c5, "pass": all(v["pass"] for v in c5.values())}

    res["C3_from_memory"] = mem["C3_statistic_lag_correlation"]["pass"]
    crit = {"C1": res["C1_noise_draw_identity"]["pass"], "C2": res["C2_separation"]["pass"],
            "C3": res["C3_from_memory"], "C4": res["C4_trajectory_correlation"]["pass"],
            "C5": res["C5_threshold_validity"]["pass"]}
    res["criteria"] = crit
    res["decision"] = ("nuisance condition ACCEPTED as the independent unit" if all(crit.values())
                       else "XSYS_001_REQUIRES_FURTHER_DESIGN_WORK")
    Path(a.out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({"criteria": crit, "decision": res["decision"], "C1_max_I": res["C1_noise_draw_identity"]["max_I"],
                      "C4_worst": res["C4_trajectory_correlation"]["worst"], "C2": res["C2_separation"],
                      "replay_vs_Q1": {k: (v["I"], v.get("best_lag_s")) for k, v in res["replay_vs_Q1_descriptive"].items()},
                      "C5": {k: v["pass"] for k, v in c5.items()}}, indent=1, default=float))


if __name__ == "__main__":
    main()
