#!/usr/bin/env python3
"""PRIME Track B2: the reality stress envelope, by offline perturbation. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/stress_envelope.py

**What this is.** Each run takes an already-flown SITL log (PX4 default
logging), perturbs its signals OFFLINE in one known way, and runs the
UNCHANGED product path (`runs.stock_flight` on the perturbed StockLog; the
product decimates and analyses it as it would a real log). Nothing is tuned.

**What it measures:** how far each signal property can move before the
product's answer changes. The question "where does real hardware sit on
this curve?" is answered by real data only. The real magnitudes measured so
far (RB0, the FMUv5 boat log) are reported beside each variable in
STRESS_ENVELOPE.md. **SITL base logs are not physical evidence.**

**Bases** (no flight is new):

| base | log | truth | the product, unperturbed |
|---|---|---|---|
| A_hover | 2.3 V4 | motor_0 at 60 % effect from the onset, hover | COMMAND_NO_RESPONSE on motor_0 |
| A_hold | 2.3 V12 | motor_2 at 60 %, a hold after maneuvers | COMMAND_NO_RESPONSE on motor_2 |
| A_maneuver | 2.3 V13 | motor_2 at 60 % mid-maneuver | nothing (the known miss) |
| B_telemetry | RB-001 CAL1 hover with motor_0's logged RPM x sqrt(0.6) from 70 s | telemetry corruption, healthy motor: XSYS-001's case-B construction, matched to A_hover's local symptom | nothing |
| N_hover | RB-001 CAL1 | nominal hover | nothing |
| N_maneuver | 2.3 V5 | nominal maneuvering | nothing (11 dismissed events) |

**Variables** (levels in VARIABLES; 0 is the unperturbed base):
- timing: jitter, sample loss, logging rate, ESC latency, producer restart;
- RPM: quantization, noise, per-motor gain mismatch, ESC lag;
- IMU: gyro bias, gyro noise, vibration (an aliased tone at 13 Hz);
- slow drifts: common-mode supply sag, one healthy motor drifting (a
  temperature proxy).

**Not perturbable offline:** mass, CG, wind and maneuver regime act through
the closed loop, so a signal edit would be a fiction. They are covered only
by flights already flown (winds 0-5 m/s; the 2.3 and RB-001 maneuver
patterns) and stay open for real data. Configuration changes are not read
by the stock path in flight, by design (`stock_log.py`).

Writes STRESS_ENVELOPE.json.
"""
from __future__ import annotations

import copy
import json
import sys
import zlib
from multiprocessing import Pool

import numpy as np

import common_prime as C
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from csia_evidence_assurance.stock_log import STOCK_INTERVAL_MS, StockLog

PROP = ("esc_status", "actuator_motors", "control_allocator_status", "battery_status",
        "rate_ctrl_status", "failure_detector_status")
CORRUPT_T = 70.0
SEEDS = 5
RANDOM_VARS = {"jitter_pct", "loss_p", "rpm_noise_pct", "gyro_noise"}
VARIABLES = {
    "jitter_pct": [0, 2, 5, 10, 20, 40],            # timestamp std, % of the topic's interval
    "loss_p": [0, 0.02, 0.05, 0.1, 0.2, 0.4],        # independent sample loss, every topic
    "rate_mult": [1, 1.5, 2, 2.5, 3, 5],             # propulsion/allocator/battery logging interval x
    "esc_latency_ms": [0, 50, 100, 200, 400, 1000],  # esc_status timestamps late by
    "producer_restart_s": [0, 0.5, 1, 2, 5, 10],     # esc_status silent, inside the event
    "rpm_quant": [0, 10, 25, 50, 100, 250],          # RPM step (hover ~7000 rpm)
    "rpm_noise_pct": [0, 0.5, 1, 2, 5, 10],          # RPM noise std, % of the motor's mean
    "motor_gain_pct": [0, 1, 2, 5, 10, 20],          # static per-motor RPM gain mismatch (+,-,+1/2,-1/2)
    "esc_lag_ms": [0, 20, 50, 100, 200, 500],        # first-order lag on RPM
    "gyro_bias": [0, 0.005, 0.01, 0.02, 0.05, 0.1],  # rad/s on each axis
    "gyro_noise": [0, 0.002, 0.005, 0.01, 0.02, 0.05],  # rad/s std
    "vibration": [0, 0.005, 0.01, 0.02, 0.05, 0.1],  # rad/s amplitude, aliased 13 Hz tone
    "supply_sag_pct": [0, 2, 5, 10, 15, 25],         # all motors' RPM down by this much over the flight
    "motor_drift_pct": [0, 1, 2, 5, 10, 20],         # one healthy motor's RPM drifts down over the flight
}
BASES = {
    "A_hover": {"log": ("2.3", "V4"), "injected": 0},
    "A_hold": {"log": ("2.3", "V12"), "injected": 2},
    "A_maneuver": {"log": ("2.3", "V13"), "injected": 2},
    "B_telemetry": {"log": ("rb001", "CAL1"), "injected": None, "corrupted": 0},
    "N_hover": {"log": ("rb001", "CAL1"), "injected": None},
    "N_maneuver": {"log": ("2.3", "V5"), "injected": None},
}
DRIFT_MOTOR = 1          # never an injected or corrupted motor in any base


def rpm_keys(log):
    return [k for k in log.topics["esc_status"] if k.endswith("esc_rpm")]


def onset(src, rid, log):
    d = C.SITL_2_3 if src == "2.3" else C.SITL_RB001
    rec = json.loads((d / f"{rid}.json").read_text())
    ev = rec.get("events_ms", {})
    if "onset_param_set" in ev:
        return ev["onset_param_set"][0] * 1e-3 - log.t0_us * 1e-6
    return None


def load_base(name):
    b = BASES[name]
    src, rid = b["log"]
    path = (C.SITL_2_3 if src == "2.3" else C.SITL_RB001) / f"{rid}.ulg"
    log = StockLog.from_ulog(path)
    t_on = onset(src, rid, log)
    if b.get("corrupted") is not None:
        e = log.topics["esc_status"]
        k = f"esc[{b['corrupted']}].esc_rpm"
        e[k] = np.where(e["t"] >= CORRUPT_T, e[k] * np.sqrt(0.6), e[k])
    anchor = t_on if t_on is not None else (CORRUPT_T if name in ("B_telemetry", "N_hover") else 49.7)
    return log, anchor


def perturb(log, var, level, seed, anchor):
    if level == 0 or (var == "rate_mult" and level == 1):
        return log
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(log)
    T = out.topics
    if var == "jitter_pct":
        for tp, d in T.items():
            iv = STOCK_INTERVAL_MS.get(tp) or 0
            if not iv:
                continue
            t = d["t"] + rng.normal(0.0, level / 100.0 * iv * 1e-3, len(d["t"]))
            o = np.argsort(t, kind="stable")
            T[tp] = {k: (t[o] if k == "t" else v[o]) for k, v in d.items()}
    elif var == "loss_p":
        for tp, d in T.items():
            if not STOCK_INTERVAL_MS.get(tp):
                continue
            keep = rng.random(len(d["t"])) >= level
            T[tp] = {k: v[keep] for k, v in d.items()}
    elif var == "rate_mult":
        out = out.decimate({tp: STOCK_INTERVAL_MS[tp] * level for tp in PROP if tp in T})
        out.sampling = {k: "as logged" for k in out.topics}     # the product re-decimates as for any log
    elif var == "esc_latency_ms":
        T["esc_status"]["t"] = T["esc_status"]["t"] + level * 1e-3
    elif var == "producer_restart_s":
        d = T["esc_status"]
        keep = ~((d["t"] >= anchor + 1.0) & (d["t"] < anchor + 1.0 + level))
        T["esc_status"] = {k: v[keep] for k, v in d.items()}
    elif var in ("rpm_quant", "rpm_noise_pct", "motor_gain_pct", "esc_lag_ms", "supply_sag_pct",
                 "motor_drift_pct"):
        e = T["esc_status"]
        t = e["t"]
        ramp = (t - t[0]) / max(t[-1] - t[0], 1e-9)
        for i, k in enumerate(rpm_keys(out)):
            r = e[k].astype(float)
            if var == "rpm_quant":
                r = np.round(r / level) * level
            elif var == "rpm_noise_pct":
                r = r + rng.normal(0.0, level / 100.0 * max(float(np.mean(r[r > 0])) if np.any(r > 0) else 0, 1.0), len(r))
            elif var == "motor_gain_pct":
                r = r * (1.0 + (1, -1, 0.5, -0.5, 1, -1, 0.5, -0.5)[i] * level / 100.0)
            elif var == "esc_lag_ms":
                y = np.empty_like(r)
                y[0] = r[0]
                for j in range(1, len(r)):
                    a = 1.0 - np.exp(-(t[j] - t[j - 1]) / (level * 1e-3))
                    y[j] = y[j - 1] + a * (r[j] - y[j - 1])
                r = y
            elif var == "supply_sag_pct":
                r = r * (1.0 - level / 100.0 * ramp)
            elif var == "motor_drift_pct" and i == DRIFT_MOTOR:
                r = r * (1.0 - level / 100.0 * ramp)
            e[k] = r
        if var == "supply_sag_pct" and "battery_status" in T:
            b = T["battery_status"]
            bt = b["t"]
            b["voltage_v"] = b["voltage_v"] * (1.0 - level / 100.0 * (bt - bt[0]) / max(bt[-1] - bt[0], 1e-9))
    elif var in ("gyro_bias", "gyro_noise", "vibration"):
        g = T["vehicle_angular_velocity"]
        t = g["t"]
        for ax in range(3):
            k = f"xyz[{ax}]"
            if var == "gyro_bias":
                g[k] = g[k] + level
            elif var == "gyro_noise":
                g[k] = g[k] + rng.normal(0.0, level, len(t))
            else:
                g[k] = g[k] + level * np.sin(2 * np.pi * 13.0 * t + ax * 2.1)
    return out


def summarize(log, base):
    run = R.stock_flight(stock_log=log, est_log=None)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    syms = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})
    first = {}
    for c in m["key_moments"].get("candidate_changes", []):
        if c["what"] != "attribution" and c["to"] and c["what"] not in first:
            first[c["what"]] = round(c["t"], 2)
    motors = [int(s.rsplit("_", 1)[1]) for s in syms if "motor_" in s]
    inj = BASES[base]["injected"]
    vals = m["evidence_values"]
    corrupted = BASES[base].get("corrupted")
    tel_deficit = any(v["state"] == "DEGRADED" and v["record"].endswith("esc.telemetry_response")
                      and f"motor_{corrupted}:" in v["record"] for v in vals) if corrupted is not None else None
    return {"symptoms": syms, "first_symptom_t": first,
            "right_motor": inj is not None and inj in motors,
            "other_motor": [k for k in motors if k != inj],
            "attribution": m["summary"]["attribution"]["verdict"],
            "unique": m["final"]["attribution"].get("unique"),
            "events": len(m["events"]),
            "refused": sum(1 for v in vals if v.get("producer_health", "VALID") != "VALID"),
            "unavailable": sum(1 for v in vals if v["state"] == "UNAVAILABLE"),
            "telemetry_deficit_on_corrupted_motor": tel_deficit}


_CACHE = {}


def job(args):
    base, var, level, seed = args
    if base not in _CACHE:
        _CACHE[base] = load_base(base)
    log, anchor = _CACHE[base]
    try:
        return (base, var, level, seed, summarize(perturb(log, var, level, seed, anchor), base))
    except Exception as exc:  # noqa: BLE001 - a crash under perturbation is a finding
        return (base, var, level, seed, {"error": f"{type(exc).__name__}: {exc}"})


def main():
    jobs = []
    for base in BASES:
        jobs.append((base, "none", 0, 0))
        for var, levels in VARIABLES.items():
            for level in levels[1:]:
                for seed in (range(SEEDS) if var in RANDOM_VARS else [0]):
                    jobs.append((base, var, level, zlib.crc32(var.encode()) % 9973 * 10 + seed))
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    with Pool(procs) as pool:
        res = pool.map(job, jobs, chunksize=8)
    out = {}
    for base, var, level, seed, r in res:
        out.setdefault(base, {}).setdefault(var, {}).setdefault(str(level), []).append(dict(r, seed=seed))
    C.write_json(C.HERE / "STRESS_ENVELOPE.json", {
        "label": "PRIME B2: offline perturbation of already-flown SITL logs; product path unchanged; "
                 "a tolerance envelope, NOT physical evidence",
        "bases": {k: {"log": "/".join(v["log"]), "injected": v["injected"],
                      "corrupted": v.get("corrupted")} for k, v in BASES.items()},
        "variables": VARIABLES, "seeds_for_random_variables": SEEDS,
        "corruption_time_s": CORRUPT_T, "runs": out})
    print(len(res), "runs")


if __name__ == "__main__":
    main()
