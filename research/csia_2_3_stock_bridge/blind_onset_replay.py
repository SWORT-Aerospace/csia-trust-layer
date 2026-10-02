#!/usr/bin/env python3
"""Phases 15-18: XSYS-001 as a benchmark, with the onset hidden. RESEARCH
ONLY. EXPLORATORY. Reported separately from the confirmatory result.

    .venv/bin/python research/csia_2_3_stock_bridge/blind_onset_replay.py [--workers N]

**Cases:** XSYS-001's own trial matrix:
- 55 A trials: motor 0 degraded, eta 0.55-0.95;
- 55 B trials: RPM telemetry corruption;
- 11 nominal flights.

**The B trials are semi-synthetic.** Each is rebuilt over the whole flight
with XSYS-001's frozen case-B rule (`stage0_prepare.build_b`): motor 0's RPM
on the nominal flight NB becomes the healthy-rotor RPM for NB's own command
times the matched A flight's RPM ratio, from NB's onset to the end of the
log. Nothing else changes.

**Configurations:**

| config | what the Analyzer gets | events |
|---|---|---|
| A | the stock producers only (`runs.stock_flight(px4_monitors=False)`) | discovered from the stock statistics |
| B | A plus PX4's own monitors: failure detector, battery warning, allocator flags, EKF2 (`runs.stock_flight()`) | discovered from all triggers |
| B_known | B at the known onset (Phase 15's reference) | the true onset |
| C_known | XSYS-001's research witnesses with the XSYS-001 specification at the true onset: the confirmatory analysis, recomputed from the logs | the true onset |
| C_disc | the same witnesses recomputed at B's discovered event time (frozen `xsys_extract.cut` and `stage1_evidence.motor_features`) | discovered |

**Scoring** (`ONSET_TRUTH.json`, never an Analyzer input):
- an event matches if its t0 is within 2 s of the true onset;
- every other event is false;
- timing error = matched t0 - true onset.

Writes BLIND_ONSET_REPLAY.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import common_23 as C

from csia_evidence_assurance import report as R  # noqa: E402
from csia_evidence_assurance import runs  # noqa: E402
from csia_evidence_assurance.adapters.px4_estimator import EstimatorLog  # noqa: E402
from csia_evidence_assurance.stock_log import StockLog  # noqa: E402

EXTRACTS = C.OUT_RAW / "extracts"
PIPE = C.REPO / "research/xsys_confirmatory_001/pipeline"
MATCH_S = 2.0


def _pipe():
    if str(PIPE) not in sys.path:
        sys.path.insert(0, str(PIPE))
    import stage1_evidence as S1
    import xsys_extract as X
    import xsys_features as F
    import xsys_v2_adapter as XA
    return S1, X, F, XA


def xsys_cal():
    return json.loads((C.REPO / "research/xsys_confirmatory_001/calibration/CALIBRATION.json")
                      .read_text())["calibration"]


# ------------------------------------------------------------------ case B over the whole flight
def full_b(nb_path, a_path, nb_t0_s, a_t0_s):
    """(B onboard dict on NB's grid, NB's grid times in s from log start).
    The frozen case-B rule, extended from the analysis span to the whole log:
    rho_A and NB's healthy-rotor RPM start, as in stage 0, at onset - 5 s."""
    _S1, X, F, _XA = _pipe()
    u_n, _pn, nb, _tn = X.load_full(nb_path)
    u_a, _pa, a, _ta = X.load_full(a_path)
    gn = (nb["t_abs_us"] - u_n.start_timestamp) * 1e-6
    ga = (a["t_abs_us"] - u_a.start_timestamp) * 1e-6
    kn0 = int(np.searchsorted(gn, nb_t0_s - 5.0))
    ka0 = int(np.searchsorted(ga, a_t0_s - 5.0))
    rho_a = np.full(len(ga), np.nan)
    rho_a[ka0:], _ = F.rpm_ratio(a["rpm_obs"][ka0:, 0], a["cmd_sim"][ka0:, 0])
    rpm_exp = np.full(len(gn), np.nan)
    _r, rpm_exp[kn0:] = F.rpm_ratio(nb["rpm_obs"][kn0:, 0], nb["cmd_sim"][kn0:, 0])
    ka = np.round((ga - a_t0_s) / F.STEP_S).astype(int)
    kb = np.round((gn - nb_t0_s) / F.STEP_S).astype(int)
    idx = np.searchsorted(ka, kb, side="right") - 1
    rho_on = np.where(idx >= 0, rho_a[np.clip(idx, 0, None)], np.nan)
    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in nb.items()}
    post = (gn >= nb_t0_s) & np.isfinite(rho_on) & np.isfinite(rpm_exp)
    b["rpm_obs"][post, 0] = np.round(rpm_exp[post] * rho_on[post])
    return b, gn, u_n.start_timestamp


def stock_with_rpm(stock: StockLog, g_s, rpm0):
    """The NB stock log with motor 0's ESC RPM replaced on its own samples."""
    es = stock.topics["esc_status"]
    i = np.searchsorted(g_s, es["t"] - 1e-7)
    i = np.clip(i, 0, len(g_s) - 1)
    ok = np.abs(g_s[i] - es["t"]) < 1e-5
    new = es["esc[0].esc_rpm"].copy()
    new[ok] = rpm0[i[ok]]
    topics = dict(stock.topics)
    topics["esc_status"] = dict(es, **{"esc[0].esc_rpm": new})
    return StockLog(dict(stock.origin, case_b="motor 0 RPM replaced (frozen case-B rule)"),
                    stock.t0_us, topics, stock.params, stock.messages, stock.sampling)


# ------------------------------------------------------------------ outcome readers
def stock_outcome(run):
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    f = m["final"]
    locs = [(x["key"], x["outcome"], tuple(x["candidates"])) for x in f["localizations"]]
    adverse = f["state"]["abnormal"]["adverse_evidence"]
    held = {}
    for c in m["coverage"]:
        if c["record"].startswith("ACTUATION/motor_0:"):
            held[c["record"].split(":", 1)[1]] = sorted(c["ticks_by_state"])
    return {"headline": f["state"]["headline"], "localizations": locs,
            "attribution": f["attribution"]["verdict"] if f.get("attribution") else None,
            "attribution_candidates": f["attribution"].get("candidates", []) if f.get("attribution") else [],
            "adverse": sorted({a.split("|")[2] for a in adverse}),
            "motor0_states": held, "events": run.extras["events"]}


def classify_stock(kind, out):
    motors = {k.split("|", 1)[1] for k, _o, _c in out["localizations"]
              if k.startswith("COMMAND_NO_RESPONSE|")}
    cands = {c for k, _o, cs in out["localizations"] if k == "COMMAND_NO_RESPONSE|motor_0" for c in cs}
    tel0 = "ACTUATION/motor_0:esc.telemetry_response" in out["adverse"]
    phys0 = out["motor0_states"].get("actuation.physical_response", [])
    if kind == "A":
        if motors - {"motor_0"}:
            return "WRONG_MOTOR"
        if "motor_0" not in motors:
            return "NO_SYMPTOM"
        if "ACTUATION/mechanical" not in cands:
            return "TRUE_CAUSE_ELIMINATED"
        if "SENSOR/response_sensor" in cands:
            return "MOTOR_0_PROPULSION_AMBIGUOUS_INCL_TELEMETRY"
        return "MOTOR_0_PROPULSION_CHAIN_TELEMETRY_EXCLUDED"
    if kind == "B":
        if motors:
            return "SYMPTOM_RAISED" + ("_WRONG_MOTOR" if motors - {"motor_0"} else "")
        if tel0 and "NOMINAL" in phys0:
            return "NO_SYMPTOM_TELEMETRY_DEFICIT_UNCONFIRMED_BY_VEHICLE"
        if tel0:
            return "NO_SYMPTOM_TELEMETRY_DEFICIT_UNTESTED"
        return "NO_SYMPTOM_NOTHING_SEEN"
    return "CORRECT_NO_SYMPTOM" if not motors and not out["adverse"] else (
        "FALSE_SYMPTOM" if motors else "ADVERSE_CONTEXT_ONLY")


def xsys_c(onboard, t0_abs_us, kind):
    """The XSYS-001 specification with witnesses recomputed at t0 (V3, C3)."""
    S1, X, F, XA = _pipe()
    cal = xsys_cal()
    ob, _tr, _g = X.cut(onboard, {k: np.zeros(len(onboard["t_abs_us"])) for k in ("w_true",)}, t0_abs_us)
    feats = {f"motor_{m}": S1.motor_features(ob, m, cal) for m in range(4)}
    per = {}
    for subj, f in feats.items():
        rpm, dyn, ctrl, w = S1.plan("V3_TEMPORAL", "C3", f)
        stats = {"L": f["L_T3"], "D": f["D_T1"], "C": f["C_T3"]}
        loc = XA.localize_subject(XA.records_for(subj, rpm, dyn, ctrl, stats, w), subj)
        per[subj] = None if loc is None else loc.to_dict()
    m0 = per.get("motor_0")
    others = [s for s, v in per.items() if s != "motor_0" and v]
    truth = {"A": "ACTUATION/mechanical", "B": "SENSOR/response_sensor"}.get(kind)
    if m0 is None:
        cls = "NO_SYMPTOM" if not others else "WRONG_MOTOR"
        if kind == "N" and not others:
            cls = "CORRECT_NO_SYMPTOM"
    else:
        cands = sorted(set(m0.get("supported") or []) | set(m0.get("unresolved") or []))
        if others:
            cls = "WRONG_MOTOR"
        elif truth and cands == [truth]:
            cls = "UNIQUE_CORRECT"
        elif truth and truth in cands:
            cls = "AMBIGUOUS_CORRECT"
        else:
            cls = "WRONG"
    return {"class": cls, "motor_0": m0 and {"verdict": m0.get("verdict"),
                                              "candidates": sorted(set(m0.get("supported") or [])
                                                                   | set(m0.get("unresolved") or []))},
            "D_T1_motor_0": feats["motor_0"]["D_T1"], "dyn_T1_motor_0": feats["motor_0"]["dyn_T1"],
            "ctrl_T3_motor_0": feats["motor_0"]["ctrl_T3"], "rpm_T3_motor_0": feats["motor_0"]["rpm_T3"]}


def score_events(events, onset):
    ts = [e["t0"] for e in events]
    match = [t for t in ts if onset is not None and abs(t - onset) <= MATCH_S]
    return {"n_events": len(ts), "matched": bool(match),
            "timing_error_s": round(match[0] - onset, 4) if match else None,
            "false_events": len(ts) - (1 if match else 0)}


# ------------------------------------------------------------------ one case
def one(case):
    kind, aid, flight, onset, a_flight, a_onset, eta = case
    stock = StockLog.from_npz(EXTRACTS / f"{flight}.npz")
    est = EstimatorLog.from_npz(EXTRACTS / f"{flight}.est.npz")
    g_s = onboard_b = None
    if kind == "B":
        onboard_b, g_s, t0us = full_b(C.RAW_FLIGHTS / f"{flight}.ulg", C.RAW_FLIGHTS / f"{a_flight}.ulg",
                                      onset, a_onset)
        stock = stock_with_rpm(stock, g_s, onboard_b["rpm_obs"][:, 0])
    row = {"kind": kind, "analysis_id": aid, "flight": flight, "eta": eta, "onset_s": onset}
    for cfg, kw in (("A", {"px4_monitors": False}), ("B", {}),
                    ("B_known", {"known_onsets": [onset]})):
        run = runs.stock_flight(stock_log=stock, est_log=est, **kw)
        out = stock_outcome(run)
        row[cfg] = {"class": classify_stock(kind, out), "headline": out["headline"],
                    "events": score_events(out["events"], onset if kind != "N" else None),
                    "event_t0s": [e["t0"] for e in out["events"]],
                    "trigger_kinds": sorted({k for e in out["events"] for k in e["trigger_kinds"]}),
                    "motor0_states": out["motor0_states"]}
    # configuration C: the research witnesses, from the full log, at known and discovered onsets
    _S1, X, _F, _XA = _pipe()
    if kind == "B":
        onboard = onboard_b
        start = int(round(t0us))
    else:
        u, _p, onboard, _t = X.load_full(C.RAW_FLIGHTS / f"{flight}.ulg")
        start = int(u.start_timestamp)
    row["C_known"] = xsys_c(onboard, start + int(round(onset * 1e6)), kind)
    disc = [t for t in row["B"]["event_t0s"] if abs(t - onset) <= MATCH_S]
    row["C_disc"] = (xsys_c(onboard, start + int(round(disc[0] * 1e6)), kind) if disc
                     else {"class": "NO_EVENT_DISCOVERED"})
    if disc:
        row["C_disc"]["onset_error_s"] = round(disc[0] - onset, 4)
    return row


def cases():
    truth = json.loads((C.HERE / "ONSET_TRUTH.json").read_text())["flights"]
    key = runs.xsys_key()["trials"]
    out = []
    for _oid, k in sorted(key.items(), key=lambda x: x[1]["analysis_id"]):
        src = k["source_flight_id"]
        a_fl = k["matched_a_flight_id"] or None
        out.append((k["kind"], k["analysis_id"], src, truth[src]["onset_s"], a_fl,
                    truth[a_fl]["onset_s"] if a_fl else None,
                    float(k["eta"]) if k.get("eta") else None))
    return out


def summarize(rows):
    def tab(cfg):
        d: dict = {}
        for r in rows:
            d.setdefault(r["kind"], {}).setdefault(r[cfg]["class"], 0)
            d[r["kind"]][r[cfg]["class"]] += 1
        return {k: dict(sorted(v.items())) for k, v in sorted(d.items())}

    out = {cfg: tab(cfg) for cfg in ("A", "B", "B_known", "C_known", "C_disc")}
    for cfg in ("A", "B"):
        ev = [r[cfg]["events"] for r in rows]
        errs = [e["timing_error_s"] for r, e in zip(rows, ev) if r["kind"] != "N" and e["timing_error_s"] is not None]
        out[f"{cfg}_events"] = {
            "A_trials_matched": sum(1 for r, e in zip(rows, ev) if r["kind"] == "A" and e["matched"]),
            "B_trials_matched": sum(1 for r, e in zip(rows, ev) if r["kind"] == "B" and e["matched"]),
            "nominal_flights_with_events": sum(1 for r, e in zip(rows, ev) if r["kind"] == "N" and e["n_events"]),
            "false_events_total": sum(e["false_events"] for e in ev),
            "timing_error_s": {"median": float(np.median(errs)) if errs else None,
                               "min": min(errs) if errs else None, "max": max(errs) if errs else None,
                               "abs_le_0_05": sum(1 for x in errs if abs(x) <= 0.05),
                               "abs_le_0_1": sum(1 for x in errs if abs(x) <= 0.1), "n": len(errs)}}
    by_eta: dict = {}
    for r in rows:
        if r["kind"] in ("A", "B"):
            k = f"{r['kind']}_{r['eta']}"
            d = by_eta.setdefault(k, {"n": 0, "matched_B": 0, "A_class": {}, "C_disc": {}})
            d["n"] += 1
            d["matched_B"] += int(r["B"]["events"]["matched"])
            d["A_class"][r["B"]["class"]] = d["A_class"].get(r["B"]["class"], 0) + 1
            d["C_disc"][r["C_disc"]["class"]] = d["C_disc"].get(r["C_disc"]["class"], 0) + 1
    out["by_kind_and_eta"] = dict(sorted(by_eta.items()))
    out["decision_differences_B_vs_B_known"] = sum(1 for r in rows if r["B"]["class"] != r["B_known"]["class"])
    out["decision_differences_C_disc_vs_C_known"] = sum(
        1 for r in rows if r["C_disc"]["class"] not in ("NO_EVENT_DISCOVERED",) and r["C_disc"]["class"] != r["C_known"]["class"])
    out["dyn_T1_witness_at_discovered_onset"] = {
        "A": {str(v): sum(1 for r in rows if r["kind"] == "A" and r["C_disc"].get("dyn_T1_motor_0") == v)
              for v in (True, False, None)},
        "A_known": {str(v): sum(1 for r in rows if r["kind"] == "A" and r["C_known"].get("dyn_T1_motor_0") == v)
                    for v in (True, False, None)}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    cs = cases()
    if a.limit:
        cs = [c for c in cs if c[0] == "A"][:a.limit] + [c for c in cs if c[0] == "B"][:a.limit] + \
             [c for c in cs if c[0] == "N"][:a.limit]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, cs))
    out = {"label": "EXPLORATORY product benchmark; not the XSYS-001 confirmatory result",
           "cases": len(rows), "summary": summarize(rows), "rows": rows}
    C.write_json(C.HERE / ("BLIND_ONSET_REPLAY.json" if not a.limit else "blind_trial.json"), out)
    print(json.dumps(out["summary"], indent=1)[:6000])


if __name__ == "__main__":
    main()
