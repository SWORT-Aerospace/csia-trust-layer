#!/usr/bin/env python3
"""XSYS-001-A2 evaluation, exactly as C4_A2_SPEC.json defines it. Committed with
the spec BEFORE any A2 pilot was flown.

Usage: analyze_a2.py --pilots <dir with the A2P-*.ulg / .json of PILOT_MATRIX_A2.csv> --out C4_A2_RESULTS.json

Computes, from the fresh nominal-only A2 pilots only:
  C4-A2   per signal, U = one-sided 95% bootstrap bound on
          mean|r|(candidate pairs) - mean|r|(valid independent reference pairs);
          PASS iff U <= 0.10 for all five signals
  EV-A2   per evidence signal, U <= 0.05 and every candidate pair |r| <= 0.20
  C1, C5  unchanged A1 definitions and thresholds, on the fresh pilots
  C3      recomputed on each reference hover, descriptive only
and the decision, with the A1 gates carried from A1's DESIGN_CHECK.json.
"""
import argparse
import csv
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
X = HERE.parent
sys.path.insert(0, str(X / "amendment_a1" / "independence"))
import independence_diagnostics as ID  # noqa: E402  (A1, frozen, unchanged)

SPEC = json.loads((HERE / "C4_A2_SPEC.json").read_text())
SIGNALS = tuple(SPEC["signals"])
EVIDENCE = tuple(SPEC["evidence_signals"])
DELTA, DELTA_E, CAP_E = 0.10, 0.05, 0.20
B, SEED = 20000, 20260927
S_SPACING, TAU_MEM = 25.0, 0.332
C1_MAX = 0.001


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ the statistic (pure)
def upper_bounds(cand, ref, ref_valid, signals, rng, b=B):
    """cand[s]: k x k symmetric |r| (diagonal ignored); ref[s]: n x n symmetric |r|;
    ref_valid: n x n bool, True where the reference pair is valid (never on the diagonal).
    Returns ({s: (delta_hat, U)}, discarded) with ONE joint resampling for all signals."""
    k = next(iter(cand.values())).shape[0]
    n = ref_valid.shape[0]
    iu_c = np.triu_indices(k, 1)
    iu_r = np.triu_indices(n, 1)
    hat = {}
    for s in signals:
        mc = cand[s][iu_c].mean()
        mr = ref[s][iu_r][ref_valid[iu_r]].mean()
        hat[s] = mc - mr
    draws = {s: [] for s in signals}
    discarded = 0
    for _ in range(b):
        ci = rng.integers(0, k, k)
        ri = rng.integers(0, n, n)
        a, bb = ci[iu_c[0]], ci[iu_c[1]]
        okc = a != bb
        ra, rb = ri[iu_r[0]], ri[iu_r[1]]
        okr = (ra != rb) & ref_valid[ra, rb]
        if not okc.any() or not okr.any():
            discarded += 1
            continue
        for s in signals:
            draws[s].append(cand[s][a[okc], bb[okc]].mean() - ref[s][ra[okr], rb[okr]].mean())
    return {s: (float(hat[s]), float(np.quantile(draws[s], 0.95))) for s in signals}, discarded


def decide(carried, fresh_c1, fresh_c5, c4, ev):
    ok = all(carried.values()) and fresh_c1 and fresh_c5 and c4 and ev
    return ("C1 C2 C3 C4-A2 C5 ALL PASS (guard tests still required)" if ok
            else "XSYS_001_REQUIRES_FURTHER_DESIGN_WORK")


# ------------------------------------------------------------------ data
def load_pilots(d):
    rows = list(csv.DictReader(open(HERE / "PILOT_MATRIX_A2.csv")))
    out, problems = {}, []
    for r in rows:
        ulg, js = Path(d) / f"{r['pilot_id']}.ulg", Path(d) / f"{r['pilot_id']}.json"
        if not ulg.exists() or not js.exists():
            problems.append(f"{r['pilot_id']}: not flown")
            continue
        rec = json.loads(js.read_text())
        if "NOMINAL-ONLY" not in rec["extra"].get("purpose", "") or rec["onset_param"] != "SDLOG_DIRS_MAX":
            problems.append(f"{r['pilot_id']}: not a nominal-only A2 pilot record")
            continue
        f = ID.Flight(ulg)
        if f.sha256 != rec["ulog_sha256"]:
            problems.append(f"{r['pilot_id']}: ULog does not match its record")
            continue
        f.row, f.rec = r, rec
        out[r["pilot_id"]] = f
    return rows, out, problems


def reference_spans(f):
    arm, dis = f.t_arm_us, f.t_disarm_us
    spans = []
    for k in range(15):
        t0 = int(round((arm + (20.0 + 25.0 * k) * 1e6) / ID.STEP_US)) * ID.STEP_US
        if t0 - 5_000_000 >= arm and t0 + 15_000_000 <= dis:
            spans.append(t0)
    return spans


def c5_flight(f, lo_s, t0_us, heading_deg):
    hov = ID.hover_nulls(f, lo_s, f.t_disarm_us * 1e-6 - 0.3, 0.5)
    ob, tr = f.full()
    g = ob["t_abs_us"]
    m0 = (g >= t0_us - 5_000_000) & (g < t0_us)
    yaw0 = float(np.degrees(np.angle(np.nanmean(np.exp(1j * tr["yaw"][m0])))))
    err = ((yaw0 - heading_deg + 180.0) % 360.0) - 180.0
    return {**hov, "true_heading_T0_deg": yaw0, "heading_error_deg": float(err),
            "pass": bool(hov["below_thresholds"] and abs(err) <= 5.0)}


def c3_descriptive(f):
    lo = f.t_arm_us * 1e-6 + 17.0
    hi = f.t_disarm_us * 1e-6 - 0.3 - 15.0
    grid, s = ID.pseudo_onset_series(f, lo, hi, 0.2, need_T3=True)
    band = range(int(round(S_SPACING / 0.2)), int(round((S_SPACING + 10.0) / 0.2)) + 1)
    out = {}
    for m in range(4):
        for a in ("L_T1", "D_T1", "L_T3", "C_T3"):
            for b in ("L_T1", "D_T1", "L_T3", "C_T3"):
                vals = [ID.lag_corr(s[f"{a}_m{m}"], s[f"{b}_m{m}"], L) for L in band]
                vals = [v for v in vals if v is not None]
                out[f"{a}(t)~{b}(t+D)_m{m}"] = float(np.mean(vals)) if vals else None
    worst = max(out, key=lambda k: abs(out[k]) if out[k] is not None else -1)
    return {"pseudo_onsets": len(grid), "worst": {"pair": worst, "mean_rho": out[worst]},
            "within_A1_C3_threshold_0.1": all(v is not None and abs(v) <= 0.1 for v in out.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilots", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows, fl, problems = load_pilots(a.pilots)
    res = {"label": "XSYS-001-A2 VALIDATION - FRESH NOMINAL-ONLY PILOTS - NOT CONFIRMATORY",
           "spec_sha256": sha256(HERE / "C4_A2_SPEC.json"), "pilot_matrix_sha256": sha256(HERE / "PILOT_MATRIX_A2.csv"),
           "inputs": {k: f.sha256 for k, f in fl.items()}, "problems": problems}
    if problems or len(fl) != len(rows):
        res["decision"] = "XSYS_001_REQUIRES_FURTHER_DESIGN_WORK"
        res["reason"] = "evaluation incomplete (stopping rule)"
        Path(a.out).write_text(json.dumps(res, indent=1) + "\n")
        print(json.dumps({"decision": res["decision"], "problems": problems}))
        return
    refs = [f for f in fl.values() if f.row["role"] == "REFERENCE"]
    cands = [f for f in fl.values() if f.row["role"] == "CANDIDATE"]
    from pyulog import ULog
    for f in cands:
        ev = ID.XE.onset_time(ULog(str(f.path)), "SDLOG_DIRS_MAX")
        f.t0_us = ev[1]

    # ---- reference spans, valid pairs, |r|
    spans = [(f, t0) for f in refs for t0 in reference_spans(f)]
    n = len(spans)
    ref = {s: np.zeros((n, n)) for s in SIGNALS}
    valid = np.zeros((n, n), bool)
    ref_c1 = []
    for i, j in combinations(range(n), 2):
        (fa, ta), (fb, tb) = spans[i], spans[j]
        if abs(ta - tb) < (S_SPACING - 0.01) * 1e6:
            continue
        idn = ID.identity_global(fa, fa.span_mask(ta, TAU_MEM), fb, fb.span_mask(tb, TAU_MEM))
        ref_c1.append(idn["I"])
        if idn["I"] > C1_MAX:
            continue
        r = ID.trajectory_corr(fa, ta, fb, tb)
        for s in SIGNALS:
            ref[s][i, j] = ref[s][j, i] = abs(r[s])
        valid[i, j] = valid[j, i] = True
    iu = np.triu_indices(n, 1)
    res["reference"] = {"spans": n, "pairs_considered": len(ref_c1), "valid_pairs": int(valid[iu].sum()),
                        "excluded_by_C1": int(sum(v > C1_MAX for v in ref_c1)),
                        "abs_r": {s: {"mean": float(ref[s][iu][valid[iu]].mean()),
                                      "median": float(np.median(ref[s][iu][valid[iu]])),
                                      "p95": float(np.quantile(ref[s][iu][valid[iu]], 0.95)),
                                      "max": float(ref[s][iu][valid[iu]].max())} for s in SIGNALS}}

    # ---- candidate pairs: |r| and fresh C1
    k = len(cands)
    cand = {s: np.zeros((k, k)) for s in SIGNALS}
    c1 = {}
    for i, j in combinations(range(k), 2):
        fa, fb = cands[i], cands[j]
        c1[f"{fa.name}|{fb.name}"] = ID.identity_global(fa, fa.span_mask(fa.t0_us, TAU_MEM), fb, fb.span_mask(fb.t0_us, TAU_MEM))
        r = ID.trajectory_corr(fa, fa.t0_us, fb, fb.t0_us)
        for s in SIGNALS:
            cand[s][i, j] = cand[s][j, i] = abs(r[s])
    iuc = np.triu_indices(k, 1)
    res["candidate"] = {"flights": [f.name for f in cands], "pairs": len(iuc[0]),
                        "abs_r": {s: {"mean": float(cand[s][iuc].mean()), "median": float(np.median(cand[s][iuc])),
                                      "max": float(cand[s][iuc].max()),
                                      "values_sorted": sorted(round(float(v), 4) for v in cand[s][iuc])} for s in SIGNALS}}
    res["fresh_C1"] = {"pairs": c1, "max_I": max(v["I"] for v in c1.values()),
                       "pass": all(v["I"] <= C1_MAX for v in c1.values())}

    # ---- C4-A2 and EV-A2
    rng = np.random.default_rng(SEED)
    bounds, discarded = upper_bounds(cand, ref, valid, SIGNALS, rng)
    res["C4_A2"] = {"per_signal": {s: {"delta_hat": d, "U95": u, "pass": u <= DELTA} for s, (d, u) in bounds.items()},
                    "margin": DELTA, "bootstrap": {"B": B, "seed": SEED, "discarded": discarded},
                    "pass": all(u <= DELTA for _, u in bounds.values())}
    ev = {s: {"U95": bounds[s][1], "max_candidate_abs_r": float(cand[s][iuc].max()),
              "pass": bounds[s][1] <= DELTA_E and float(cand[s][iuc].max()) <= CAP_E} for s in EVIDENCE}
    res["EV_A2"] = {"per_signal": ev, "margin": DELTA_E, "cap": CAP_E, "pass": all(v["pass"] for v in ev.values())}

    # ---- fresh C5, descriptive C3
    c5 = {}
    for f in cands:
        c5[f.name] = c5_flight(f, f.t_arm_us * 1e-6 + 17.0, f.t0_us, float(f.row["heading_deg"]))
    for f in refs:
        c5[f.name] = c5_flight(f, f.t_arm_us * 1e-6 + 17.0, reference_spans(f)[0], float(f.row["heading_deg"]))
    res["fresh_C5"] = {"flights": c5, "pass": all(v["pass"] for v in c5.values())}
    res["C3_descriptive_reference_hovers"] = {f.name: c3_descriptive(f) for f in refs}

    carried = json.loads((X / "amendment_a1" / "independence" / "DESIGN_CHECK.json").read_text())["criteria"]
    carried = {c: carried[c] for c in ("C1", "C2", "C3", "C5")}
    res["carried_from_A1"] = carried
    res["gates"] = {"A1_C1": carried["C1"], "A1_C2": carried["C2"], "A1_C3": carried["C3"], "A1_C5": carried["C5"],
                    "fresh_C1": res["fresh_C1"]["pass"], "fresh_C5": res["fresh_C5"]["pass"],
                    "C4_A2": res["C4_A2"]["pass"], "EV_A2": res["EV_A2"]["pass"]}
    res["decision"] = decide(carried, res["fresh_C1"]["pass"], res["fresh_C5"]["pass"], res["C4_A2"]["pass"],
                             res["EV_A2"]["pass"])
    Path(a.out).write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({"gates": res["gates"], "decision": res["decision"],
                      "C4_A2": {s: (round(v["delta_hat"], 4), round(v["U95"], 4)) for s, v in res["C4_A2"]["per_signal"].items()},
                      "reference": {k2: v for k2, v in res["reference"].items() if k2 != "abs_r"}}, indent=1, default=float))


if __name__ == "__main__":
    main()
