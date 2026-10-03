#!/usr/bin/env python3
"""PRIME-1 Phases 9-12: the held-out, prospective event-discovery evaluation. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/heldout_eval.py --freeze   # before flying: hash the frozen code
    .venv/bin/python research/csia_prime1/heldout_eval.py            # once, after flying

**EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY.** Data: the held-out SITL
flights of `sitl_heldout_runs.py` (HELDOUT_PREREGISTRATION.md), flown after
the code and this script were committed. Nothing here is tuned: the run
refuses to start if any frozen file differs from HELDOUT_FREEZE.json, and it
refuses to overwrite HELDOUT_RESULTS.json.

**What is analysed.** Each flight's BLINDED copy: PX4's failure-injection
message and the SIH_MOT_EFFn change removed (PRIME's own `blind()`), i.e. the
log a real vehicle would have produced. Both releases see the same copy:
- `2.3`, the historical product (baseline);
- `prime1`, the successor.

Then:
- `prime1` on the raw copy too (no simulation-leak dependence);
- every nominal flight again with microsecond-grid timestamp jitter;
- the telemetry matrix on held-out bases HN1 (hover) and HN4 (maneuvering).

**Truth** (scoring only): the log time of the SIH parameter change or of
PX4's injection message, read from the RAW log; the motor from the flight
design (`sitl_heldout_runs.TRUTH`).

The criteria are in HELDOUT_PREREGISTRATION.md section 5 and in `verdict()`.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import common_prime1 as C
import sitl_heldout_runs as H
import telemetry_matrix as TM

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs
from csia_evidence_assurance.stock_log import StockLog

RAW = C.OUT_RAW / "heldout"
FREEZE = C.HERE / "HELDOUT_FREEZE.json"
RESULTS = C.HERE / "HELDOUT_RESULTS.json"
WINDOW = (-1.0, 2.0)
NOMINAL = ("HN1", "HN2", "HN3", "HN4", "HN5", "HN6", "HN7", "HN8")
FAULTS = ("HF1", "HF2", "HF3", "HF4", "HT1", "HT2")
JITTER_FRACTION = 0.2          # timestamp jitter std, as a fraction of each topic's logging interval
JITTER_SEED = 20261003
TARGET_FALSE_EVENTS_PER_H = 6.0
FROZEN = ["csia_evidence_assurance/admissibility.py", "csia_evidence_assurance/analyzer.py",
          "csia_evidence_assurance/events.py", "csia_evidence_assurance/stock_stats.py",
          "csia_evidence_assurance/stock_log.py", "csia_evidence_assurance/runs.py",
          "csia_evidence_assurance/releases.py", "csia_evidence_assurance/adapters/px4_stock.py",
          "csia_evidence_assurance/report.py", "csia_evidence_assurance/stock_report.py",
          "csia_evidence_assurance/stock_calibration.json",
          "csia_evidence_assurance/profiles/multirotor_quad.py",
          "csia_evidence_assurance/contracts/stock_esc_telemetry_response.json",
          "csia_evidence_assurance/contracts/stock_esc_telemetry_response_prime1.json",
          "csia_evidence_assurance/contracts/stock_allocator_compensation.json",
          "csia_evidence_assurance/contracts/stock_vehicle_rate_transient.json",
          "csia_evidence_assurance/contracts/stock_allocator_status.json",
          "csia_evidence_assurance/contracts/stock_battery_status.json",
          "research/csia_prime1/heldout_eval.py", "research/csia_prime1/telemetry_matrix.py",
          "research/csia_prime1/sitl_heldout_runs.py", "research/csia_prime1/HELDOUT_PREREGISTRATION.md"]


def hashes() -> dict:
    return {f: hashlib.sha256((C.REPO / f).read_bytes()).hexdigest() for f in FROZEN}


# ------------------------------------------------------------------ inputs
def truth_onset(raw: Path, rid: str):
    """Log time (s from log start) of the injection, from the RAW log. Scoring only."""
    from pyulog import ULog
    u = ULog(str(raw))
    t0 = int(u.start_timestamp)
    for t, k, _v in u.changed_parameters:
        if k.startswith("SIH_MOT_EFF"):
            return round((int(t) - t0) * 1e-6, 6)
    for m in u.logged_messages:
        if "failure_injection_manager" in m.message:
            return round((int(m.timestamp) - t0) * 1e-6, 6)
    return None


def blinded(raw: Path, dst: Path) -> dict:
    import build_pilot_bundle as B           # PRIME's blinding, unchanged
    return B.blind(raw, dst, corrupt=False)


def jittered(log: StockLog, seed: int) -> StockLog:
    """Microsecond-grid timestamp jitter on every stock topic (order kept)."""
    from csia_evidence_assurance.stock_log import STOCK_INTERVAL_MS
    rng = np.random.default_rng(seed)
    log = copy.deepcopy(log)
    for name, d in log.topics.items():
        iv = (STOCK_INTERVAL_MS.get(name) or 20) * 1e-3
        t = d["t"] + rng.normal(0.0, JITTER_FRACTION * iv, len(d["t"]))
        t = np.round(np.maximum.accumulate(t) * 1e6) / 1e6
        d["t"] = t
    return log


def in_flight_hours(log) -> float:
    vs = log.topics.get("vehicle_status")
    if vs is None or not len(vs["t"]):
        return 0.0
    t = vs["t"]
    fl = log.in_flight(t)
    return float(np.sum(np.diff(t)[fl[:-1]])) / 3600.0


def analyse(log, release, path=None):
    run = runs.stock_flight(path, stock_log=log, release=release)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    syms = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})
    loc = m["final"].get("localizations", [])
    return {"events": [{"t0": e["t0"], "kinds": e["trigger_kinds"]} for e in m["events"]],
            "symptoms": syms, "attribution": m["summary"]["attribution"]["verdict"],
            "unique": [x["key"] for x in loc if x.get("outcome") == "UNIQUE"],
            "hours": in_flight_hours(log)}


def one(job):
    rid, kind, release = job
    raw = RAW / f"{rid}.ulg"
    with tempfile.TemporaryDirectory() as td:
        if kind == "raw":
            path = raw
        else:
            path = Path(td) / f"{rid}.ulg"
            blinded(raw, path)
        log = StockLog.from_ulog(path)
        if kind == "jitter":
            log = jittered(log, JITTER_SEED + NOMINAL.index(rid))
        return {"run": rid, "copy": kind, "release": release, **analyse(log, release, path)}


# ------------------------------------------------------------------ scoring
def score(rows, truth_t) -> dict:
    out = {}
    for rel in ("2.3", "prime1"):
        b = {r["run"]: r for r in rows if r["release"] == rel and r["copy"] == "blinded"}
        nom_h = sum(b[k]["hours"] for k in NOMINAL)
        nom_events = sum(len(b[k]["events"]) for k in NOMINAL)
        tel_kinds = {"propulsion.rpm_deficit", "propulsion.rpm_excess", "propulsion.telemetry_change"}
        nom_tel = sum(1 for k in NOMINAL for e in b[k]["events"] if set(e["kinds"]) & tel_kinds)
        found, missed, errs, false_in_fault = {}, [], [], 0
        for k in FAULTS:
            what, motor = H.TRUTH[k]
            on = truth_t[k]
            near = [e for e in b[k]["events"] if on + WINDOW[0] <= e["t0"] <= on + WINDOW[1]]
            want = {"loss": None, "telemetry_excess": {"propulsion.rpm_excess"},
                    "telemetry_offline": {"px4.esc_offline", "propulsion.rpm_deficit",
                                          "propulsion.telemetry_change"}}[what]
            if rel == "2.3" and what == "telemetry_excess":
                want = {"propulsion.telemetry_change"}
            ok = [e for e in near if want is None or set(e["kinds"]) & want]
            found[k] = bool(ok)
            if ok:
                errs.append(ok[0]["t0"] - on)
            else:
                missed.append(k)
            false_in_fault += len(b[k]["events"]) - (1 if ok else 0)
        sym_false = [k for k in NOMINAL if b[k]["symptoms"]] + \
                    [k for k in ("HT1", "HT2") if b[k]["symptoms"]]
        wrong_motor = [k for k in ("HF1", "HF2", "HF3", "HF4") for s in b[k]["symptoms"]
                       if s.startswith("COMMAND_NO_RESPONSE|motor_") and s != f"COMMAND_NO_RESPONSE|motor_{H.TRUTH[k][1]}"]
        wrong_unique = [k for k in b for u in b[k]["unique"]
                        if k in NOMINAL or k in ("HT1", "HT2") or not u.endswith(f"motor_{H.TRUTH[k][1]}")]
        total_h = sum(b[k]["hours"] for k in b)
        out[rel] = {"nominal_in_flight_hours": round(nom_h, 4), "all_in_flight_hours": round(total_h, 4),
                    "candidate_events_per_flight_hour": round(sum(len(b[k]["events"]) for k in b) / total_h, 2),
                    "false_events_nominal": nom_events,
                    "false_events_per_nominal_hour": round(nom_events / nom_h, 2),
                    "false_events_in_fault_flights": false_in_fault,
                    "false_telemetry_events_nominal": nom_tel,
                    "false_symptoms": sym_false, "false_symptoms_per_hour": round(len(sym_false) / total_h, 3),
                    "wrong_motor_symptoms": wrong_motor, "wrong_unique": wrong_unique,
                    "faults_found": found, "missed": missed,
                    "onset_errors_s": [round(x, 3) for x in errs],
                    "median_abs_onset_error_s": round(float(np.median(np.abs(errs))), 3) if errs else None,
                    "losses_confirmed": [k for k in ("HF1", "HF2", "HF3", "HF4")
                                         if f"COMMAND_NO_RESPONSE|motor_{H.TRUTH[k][1]}" in b[k]["symptoms"]]}
        if rel == "prime1":
            j = {r["run"]: r for r in rows if r["release"] == rel and r["copy"] == "jitter"}
            jh = sum(j[k]["hours"] for k in NOMINAL)
            out[rel]["jitter_false_events"] = sum(len(j[k]["events"]) for k in NOMINAL)
            out[rel]["jitter_false_events_per_nominal_hour"] = round(out[rel]["jitter_false_events"] / jh, 2)
            out[rel]["jitter_false_symptoms"] = [k for k in NOMINAL if j[k]["symptoms"]]
            raw = {r["run"]: r for r in rows if r["release"] == rel and r["copy"] == "raw"}
            out[rel]["raw_vs_blinded_identical"] = {
                k: (raw[k]["events"], raw[k]["symptoms"], raw[k]["attribution"])
                == (b[k]["events"], b[k]["symptoms"], b[k]["attribution"]) for k in raw}
    return out


def verdict(s, tm) -> dict:
    p, h = s["prime1"], s["2.3"]
    crit = {
        "S1_safety": not p["false_symptoms"] and not p["wrong_motor_symptoms"] and not p["wrong_unique"]
                     and not p["jitter_false_symptoms"],
        "S2_recall": not p["missed"] and sum(p["faults_found"].values()) >= sum(h["faults_found"].values()),
        "S3_burden": (p["false_events_per_nominal_hour"] <= TARGET_FALSE_EVENTS_PER_H
                      and p["jitter_false_events_per_nominal_hour"] <= TARGET_FALSE_EVENTS_PER_H
                      and p["false_events_per_nominal_hour"] <= 0.5 * h["false_events_per_nominal_hour"]),
        "S4_onset": p["median_abs_onset_error_s"] is not None and p["median_abs_onset_error_s"] <= 0.5,
        "S5_telemetry_matrix": tm["summary"]["prime1"]["pass"] == tm["summary"]["prime1"]["cases"],
        "S6_no_simulation_leak": all(p["raw_vs_blinded_identical"].values()),
    }
    hours = p["nominal_in_flight_hours"]
    return {"criteria": crit, "verdict": "PROMOTE" if all(crit.values()) else "NOT_PROMOTED",
            "scope": "EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY",
            "false_event_rate_95pct_upper_bound_if_zero_per_h": round(3.0 / hours, 1) if hours else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    if a.freeze:
        C.write_json(FREEZE, {"label": "PRIME-1 held-out evaluation: frozen before any held-out flight",
                              "files_sha256": hashes()})
        print("frozen", len(FROZEN), "files")
        return 0
    frozen = json.loads(FREEZE.read_text())["files_sha256"]
    now = hashes()
    changed = [f for f in FROZEN if frozen.get(f) != now[f]]
    if changed:
        sys.exit(f"REFUSED: frozen files changed since the freeze: {changed}")
    if RESULTS.exists():
        sys.exit("REFUSED: HELDOUT_RESULTS.json exists; the evaluation runs once")
    missing = [k for k in NOMINAL + FAULTS if not (RAW / f"{k}.ulg").exists()]
    if missing:
        sys.exit(f"REFUSED: held-out flights missing: {missing}")
    truth_t = {k: truth_onset(RAW / f"{k}.ulg", k) for k in FAULTS}
    jobs = [(k, "blinded", r) for k in NOMINAL + FAULTS for r in ("2.3", "prime1")]
    jobs += [(k, "raw", "prime1") for k in NOMINAL + FAULTS]
    jobs += [(k, "jitter", "prime1") for k in NOMINAL]
    with ProcessPoolExecutor(4) as ex:
        rows = list(ex.map(one, jobs))
    s = score(rows, truth_t)
    tm = TM.run_matrix("heldout")
    v = verdict(s, tm)
    inputs = {k: C.sha(RAW / f"{k}.ulg") for k in NOMINAL + FAULTS}
    C.write_json(RESULTS, {"label": "PRIME-1 held-out evaluation, AS RUN (once); SIMULATION ONLY",
                           "inputs_sha256": inputs, "truth_onsets_log_s": truth_t, "rows": rows,
                           "scores": s, "telemetry_matrix": tm, "verdict": v})
    print(json.dumps({"scores": s, "verdict": v, "telemetry_matrix": tm["summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
