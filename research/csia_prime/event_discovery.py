#!/usr/bin/env python3
"""PRIME Track C3-C4: event discovery as its own problem. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/event_discovery.py --stage cal|dev|eval|real

**The problem.** The product raises about 300 dismissed candidate events per
maneuvering hour (2.3: 287/h; RB-001's new flights: 339/h). Every false one
in 2.3 came from one trigger, the compensation-ratio CUSUM. On the real
FMUv5 boat log, PX4's own warnings alone made 147 per armed hour: one
low-battery condition was re-raised 9 times.

**The candidates** replace only the compensation-ratio CUSUM (E1 also
merges PX4 warnings). The telemetry CUSUM and PX4's own monitors are kept in
every candidate. All are established methods; nothing is learned.

| id | trigger for a propulsion change | method |
|---|---|---|
| E0 | compensation-ratio CUSUM (the product) | Page CUSUM |
| E1 | E0, with persistence (a compensation alarm counts only if it lasts ≥ D before clearing) and merging of a re-raised identical PX4 condition within 60 s | hysteresis / debouncing / event merging |
| E2 | E0's compensation alarm, only when the body rate around its onset is within the compensation's own steadiness regime (≤ θ_steady) | rate-conditioned threshold |
| E3 | CUSUM on the control-conditioned residual's per-motor loss estimate (B3's statistic, short window against a trailing reference) | control-conditioned trigger (CUSUM) |
| E4 | GLR mean-shift test on the same per-motor residual series | GLR (Willsky-Jones) |
| E5 | binary segmentation (mean-shift cost) on the same per-motor residual series, offline | change-point detection |

**Thresholds** come from the calibration flights CAL1-CAL5 (nominal) by the
program's rule: 2 × the largest null value. E1's D is 2 × the longest a
nominal compensation alarm lasted. E2 reuses the shipped θ_steady. E3's k is
half of B3's frozen θ_δ. Nothing is chosen on a fault.

**Stages:**
- `cal` writes EVENT_DISCOVERY_CALIBRATION.json;
- `dev` scores the development flights (2.3 V1-V13; already seen);
- `eval` scores RB-001's EN, EF, EH, ET flights once, after the
  preregistration is committed;
- `real` applies the PX4-trigger candidates (E0, E1) to the real boat log.

**Downstream** (C4: event discovery is judged also by what the analysis
does with its events): the product analyses at each candidate's event times
(`runs.stock_flight(known_onsets=…)`, the benchmark hook). False symptoms
and wrong attribution are counted.
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool

import numpy as np

import common_prime as C
import evaluate_maneuver as EM
import maneuver as M
from csia_evidence_assurance import events as EV
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from csia_evidence_assurance import stock_stats as SS
from csia_evidence_assurance.stock_log import StockLog

SETS = {
    "cal": [(C.SITL_RB001, f"CAL{i}") for i in range(1, 6)],
    "dev": [(C.SITL_2_3, f"V{i}") for i in range(1, 14)],
    "eval": [(C.SITL_RB001, r) for r in ("EN1", "EN2", "EN3", "EN4", "EF1", "EF2", "EF3", "EF4",
                                         "EF5", "EF6", "EH1", "ET1", "ET2")],
}
CANDIDATES = ("E0", "E1", "E2", "E3", "E4", "E5")
COMP = "propulsion.compensation_change"
MERGE_S = 60.0                  # E1: a re-raised identical PX4 condition within this is merged (a priori)
HZ = 25.0                       # residual series rate (B3's GLR rate)
SHORT_S, REF_S = 0.5, 5.0       # E3: short window against a trailing reference
GLR_W, GLR_REF, REFRACT = 2.0, 5.0, 5.0
MIN_SEG_S = 2.0                 # E5
DETECT = (-1.0, 2.0)            # an event within [onset - 1, onset + 2] s finds the injection


# ------------------------------------------------------------------ inputs
def load(item):
    d, rid = item
    path = d / f"{rid}.ulg"
    rec = json.loads(path.with_suffix(".json").read_text())
    raw = StockLog.from_ulog(path)
    log = raw.decimate()
    est = R.PX.EstimatorLog.from_ulog(path)
    f = M.load(path, rid)
    tr = EM.truth(rec, f.stock.t0_us)
    return {"rid": rid, "path": str(path), "log": log, "est": est, "flight": f, "truth": tr}


def series(f, mdl):
    """Per-motor lost-fraction proxy r_m(t) at HZ, in flight and unsaturated (B3's projection)."""
    d = M.residual(f, mdl)
    ok = f.in_flight & ~f.sat
    step = max(int(round(100.0 / HZ)), 1)
    idx = np.flatnonzero(ok)[::step]
    t = f.t[idx]
    r = np.full((len(idx), 4), np.nan)
    for k in range(4):
        b = mdl.B[:2, k]
        u = f.u[idx, k]
        good = u > SS.MIN_COMMAND
        r[good, k] = (d[idx][good, :2] @ b) / (u[good] * (b @ b))
    return t, r


def window_dev(t, x):
    """mean over [t - SHORT, t] minus mean over [t - SHORT - REF, t - SHORT], per sample."""
    out = np.full(len(t), np.nan)
    c = np.concatenate([[0.0], np.cumsum(np.nan_to_num(x))])
    n = np.concatenate([[0], np.cumsum(np.isfinite(x))])
    a = np.searchsorted(t, t - SHORT_S)
    b = np.searchsorted(t, t - SHORT_S - REF_S)
    i = np.arange(len(t)) + 1
    ns, nr = n[i] - n[a], n[a] - n[b]
    ok = (ns > 3) & (nr > 25) & (t - t[0] > SHORT_S + REF_S)
    out[ok] = (c[i][ok] - c[a][ok]) / ns[ok] - (c[a][ok] - c[b][ok]) / nr[ok]
    return out


def cusum_peak(t, dev, k):
    s, peak, S = 0.0, 0.0, np.zeros(len(t))
    for j in range(len(t)):
        s = 0.0 if not np.isfinite(dev[j]) else max(0.0, s + dev[j] - k)
        S[j] = s
        peak = max(peak, s)
    return S, peak


def glr_series(t, x, sigma):
    out = np.zeros(len(t))
    for j in range(len(t)):
        w = (t > t[j] - GLR_W) & (t <= t[j]) & np.isfinite(x)
        rf = (t > t[j] - GLR_W - GLR_REF) & (t <= t[j] - GLR_W) & np.isfinite(x)
        if w.sum() < 10 or rf.sum() < 50:
            continue
        dm = x[w].mean() - x[rf].mean()
        out[j] = w.sum() * dm * dm / (2 * sigma * sigma) if dm > 0 else 0.0
    return out


def binseg(t, x, lam, lo=0, hi=None, found=None):
    """Positive mean shifts (loss direction) whose cost reduction exceeds lam."""
    found = [] if found is None else found
    hi = len(x) if hi is None else hi
    seg = x[lo:hi]
    m = int(MIN_SEG_S * HZ)
    if len(seg) < 2 * m:
        return found
    c = np.cumsum(seg)
    tot = c[-1]
    best, bk = 0.0, None
    for k in range(m, len(seg) - m):
        a, b = c[k - 1] / k, (tot - c[k - 1]) / (len(seg) - k)
        red = k * (len(seg) - k) / len(seg) * (b - a) ** 2
        if b > a and red > best:
            best, bk = red, k
    if bk is not None and best > lam:
        found.append((float(t[lo + bk]), best))
        binseg(t, x, lam, lo, lo + bk, found)
        binseg(t, x, lam, lo + bk, hi, found)
    return found


def max_binseg(x):
    m = int(MIN_SEG_S * HZ)
    if len(x) < 2 * m:
        return 0.0
    c = np.cumsum(x)
    tot, best = c[-1], 0.0
    for k in range(m, len(x) - m):
        a, b = c[k - 1] / k, (tot - c[k - 1]) / (len(x) - k)
        if b > a:
            best = max(best, k * (len(x) - k) / len(x) * (b - a) ** 2)
    return best


# ------------------------------------------------------------------ candidates
def triggers(fl, cand, cal, mdl):
    log, est, f = fl["log"], fl["est"], fl["flight"]
    _ev, trs, _n = EV.discover(log, est)
    comp = [t for t in trs if t.kind == COMP]
    rest = [t for t in trs if t.kind != COMP]
    if cand == "E0":
        return trs
    if cand == "E1":
        keep = [t for t in comp if t.cleared_t is None or t.cleared_t - t.alarm_t >= cal["E1_D_s"]]
        merged, last = [], {}
        for t in sorted(rest, key=lambda x: x.onset_t):
            key = (t.kind, t.detail.get("text") if t.kind == "px4.log_message" else t.motor)
            if t.kind.startswith("px4.") and key in last and t.onset_t - last[key] <= MERGE_S:
                last[key] = t.onset_t
                continue
            last[key] = t.onset_t
            merged.append(t)
        return keep + merged
    if cand == "E2":
        keep = []
        for t in comp:
            av = log.topics.get("vehicle_angular_velocity")
            m = (av["t"] >= t.onset_t - 5.0) & (av["t"] <= t.onset_t + 0.5)
            R_ = float(np.max(np.linalg.norm(np.stack([av[f"xyz[{i}]"][m] for i in range(3)], 1), axis=1))) \
                if m.any() else np.inf
            if R_ <= cal["theta_steady"]:
                keep.append(t)
        return keep + rest
    t, r = series(f, mdl)
    out = []
    for k in range(4):
        x = r[:, k]
        if cand == "E3":
            dev = window_dev(t, x)
            S, _p = cusum_peak(t, dev, cal["E3_k"])
            on, in_alarm = None, False
            for j in range(len(t)):
                if S[j] == 0.0:
                    on, in_alarm = t[j], False
                elif S[j] > cal["E3_h"] and not in_alarm:
                    out.append(EV.Trigger("residual", "propulsion.residual_cusum",
                                          float(on if on is not None else t[j]), float(t[j]), k))
                    in_alarm = True
        elif cand == "E4":
            g = glr_series(t, x, cal["E4_sigma"][k])
            last = -np.inf
            for j in np.flatnonzero(g > cal["E4_h"]):
                if t[j] - last > REFRACT:
                    out.append(EV.Trigger("residual", "propulsion.residual_glr", float(t[j] - GLR_W),
                                          float(t[j]), k))
                    last = t[j]
        elif cand == "E5":
            good = np.isfinite(x)
            for cp, _red in binseg(t[good], x[good], cal["E5_lambda"]):
                out.append(EV.Trigger("residual", "propulsion.residual_changepoint", cp, cp, k))
    return out + rest


# ------------------------------------------------------------------ calibration (nominal flights only)
def calibrate(flights, mdl):
    base = json.loads((C.REPO / "csia_evidence_assurance/stock_calibration.json").read_text())["calibration"]
    rb = json.loads((C.RB001 / "MANEUVER_CALIBRATION.json").read_text())["calibration"]
    durations, e3_peaks, e4_vals, e5_vals, sig = [], [], [], [], [[] for _ in range(4)]
    k3 = rb["theta_delta"] / 2.0
    for fl in flights:
        _ev, trs, _n = EV.discover(fl["log"], fl["est"])
        durations += [t.cleared_t - t.alarm_t for t in trs if t.kind == COMP and t.cleared_t is not None]
        t, r = series(fl["flight"], mdl)
        for k in range(4):
            x = r[:, k]
            dev = window_dev(t, x)
            e3_peaks.append(cusum_peak(t, dev, k3)[1])
            sig[k].append(np.nanstd(dev))
            e5_vals.append(max_binseg(x[np.isfinite(x)]))
    sigma = [float(np.nanmean(s)) for s in sig]
    for fl in flights:
        t, r = series(fl["flight"], mdl)
        for k in range(4):
            e4_vals.append(float(np.max(glr_series(t, r[:, k], sigma[k]))))
    return {"theta_steady": base["theta_steady"], "E1_D_s": 2.0 * max(durations) if durations else 0.0,
            "E1_nominal_alarm_durations_max_s": max(durations) if durations else None,
            "E3_k": k3, "E3_h": 2.0 * max(e3_peaks), "E3_null_max": max(e3_peaks),
            "E4_sigma": sigma, "E4_h": 2.0 * max(e4_vals), "E4_null_max": max(e4_vals),
            "E5_lambda": 2.0 * max(e5_vals), "E5_null_max": max(e5_vals),
            "rule": "2 x the largest null value on CAL1-CAL5; E2 reuses the shipped theta_steady"}


# ------------------------------------------------------------------ scoring
def in_flight_hours(fl, until=None):
    f = fl["flight"]
    m = f.in_flight[:-1] & ((f.t[:-1] < until) if until is not None else True)
    return float(np.sum(np.diff(f.t)[m])) / 3600.0


def downstream(fl, t0s):
    run = R.stock_flight(fl["path"], known_onsets=t0s)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    syms = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})
    return syms, m["final"]["attribution"].get("unique")


def score_flight(args):
    fl, cand, cal, mdl, with_downstream = args
    evs = EV.cluster(triggers(fl, cand, cal, mdl))
    tr = fl["truth"]
    t0s = [e.t0 for e in evs]
    row = {"flight": fl["rid"], "kind": tr["kind"], "events": len(evs), "t0": [round(x, 3) for x in t0s]}
    if tr["kind"] in ("physical", "telemetry", "other"):
        on = tr["onset"]
        row["false_events"] = sum(1 for x in t0s if x < on + DETECT[0])
        hit = [x - on for x in t0s if DETECT[0] <= x - on <= DETECT[1]]
        row["detected"] = bool(hit)
        row["onset_error_s"] = round(min(hit, key=abs), 3) if hit else None
        row["nominal_hours"] = in_flight_hours(fl, until=on + DETECT[0])
    else:
        row["false_events"] = len(evs)
        row["nominal_hours"] = in_flight_hours(fl)
    if with_downstream:
        syms, unique = downstream(fl, t0s) if t0s else ([], None)
        motor = tr.get("motor")
        row["symptoms"] = syms
        row["false_symptoms"] = [s for s in syms if tr["kind"] != "physical"
                                 or not s.endswith(f"motor_{motor}")]
        row["right_symptom"] = tr["kind"] == "physical" and f"COMMAND_NO_RESPONSE|motor_{motor}" in syms
        row["unique"] = unique
    return cand, row


def summarize(rows):
    out = {}
    for cand in CANDIDATES:
        rs = [r for c, r in rows if c == cand]
        if not rs:
            continue
        hours = sum(r["nominal_hours"] for r in rs)
        fe = sum(r["false_events"] for r in rs)
        faults = [r for r in rs if r["kind"] == "physical"]
        s = {"false_events": fe, "nominal_in_flight_h": round(hours, 4),
             "false_events_per_h": round(fe / hours, 1) if hours else None,
             "events_total": sum(r["events"] for r in rs),
             "faults": len(faults), "faults_detected": sum(1 for r in faults if r["detected"]),
             "missed": [r["flight"] for r in faults if not r["detected"]]}
        if "symptoms" in rs[0]:
            s["false_symptoms"] = sum(len(r["false_symptoms"]) for r in rs)
            s["wrong_unique"] = sum(1 for r in rs if r["unique"])
            s["faults_confirmed_downstream"] = sum(1 for r in faults if r["right_symptom"])
        out[cand] = s
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("cal", "dev", "eval", "real"), required=True)
    a = ap.parse_args()
    calib_rb = json.loads((C.RB001 / "MANEUVER_CALIBRATION.json").read_text())
    mdl = M.Model.from_dict(calib_rb["model"])
    if a.stage == "real":
        return real()
    with Pool(3) as pool:
        flights = pool.map(load, SETS[a.stage])
    if a.stage == "cal":
        cal = calibrate(flights, mdl)
        C.write_json(C.HERE / "EVENT_DISCOVERY_CALIBRATION.json", {
            "label": "PRIME C3: event-discovery calibration on CAL1-CAL5 (nominal) only",
            "flights": {fl["rid"]: C.sha(fl["path"]) for fl in flights}, "calibration": cal})
        print(json.dumps(cal, indent=1))
        return
    cal = json.loads((C.HERE / "EVENT_DISCOVERY_CALIBRATION.json").read_text())["calibration"]
    jobs = [(fl, cand, cal, mdl, True) for fl in flights for cand in CANDIDATES]
    with Pool(3) as pool:
        rows = pool.map(score_flight, jobs)
    summ = summarize(rows)
    C.write_json(C.HERE / f"EVENT_DISCOVERY_{a.stage.upper()}.json", {
        "label": ("DEVELOPMENT flights (2.3 V1-V13, already seen): in-sample" if a.stage == "dev"
                  else "EVALUATION flights (RB-001 EN/EF/EH/ET), as run, scored once"),
        "calibration_sha256": C.sha(C.HERE / "EVENT_DISCOVERY_CALIBRATION.json"),
        "summary": summ, "flights": [dict(r, candidate=c) for c, r in rows]})
    print(json.dumps(summ, indent=1))


def real():
    """E0 and E1 on the real FMUv5 boat log (PX4 triggers only; no motors)."""
    log = StockLog.from_ulog(C.REAL_PX4_DOCS).decimate()
    _ev, trs, _n = EV.discover(log, None)
    cal = json.loads((C.HERE / "EVENT_DISCOVERY_CALIBRATION.json").read_text())["calibration"]
    fl = {"log": log, "est": None, "flight": None}
    out = {}
    for cand in ("E0", "E1"):
        evs = EV.cluster(triggers(fl, cand, cal, None))
        out[cand] = {"events": len(evs), "t0": [round(e.t0, 2) for e in evs],
                     "kinds": [sorted({t.kind for t in e.triggers}) for e in evs]}
    C.write_json(C.HERE / "EVENT_DISCOVERY_REAL.json", {
        "label": "PRIME C3: PX4-trigger candidates on the real FMUv5 boat log (no propulsion producers run)",
        "sha256": C.REAL_PX4_DOCS_SHA, "results": out})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
