#!/usr/bin/env python3
"""PRIME Track C2: B3's sensitivity to the physical mismatches a real vehicle brings. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/b3_challenge.py

**B3** (RB-001 `maneuver.py`, frozen at 9c585800…): the per-motor lost-fraction
estimate from the residual between the demanded torque (low-passed) and the
torque implied by the measured angular acceleration, AFTER minus BEFORE,
roll and pitch. Its frozen threshold θ_δ = 0.0183 and its frozen SIH model
(`MANEUVER_CALIBRATION.json`) are NOT changed here.

**Data: development (2.3 V1-V13) and calibration (RB-001 CAL1-CAL5) only.**
The RB-001 evaluation flights are not touched. Each mismatch is applied
OFFLINE to the flight, so the frozen model no longer matches the "plant":

| variable | applied as | stands for |
|---|---|---|
| `wdot_noise` | white noise on the angular acceleration (rad/s²) | vibration on the differentiated gyro |
| `latency_ms` | the torque setpoint delayed against the angular acceleration | ESC + motor response lag beyond the model's 0.05 s |
| `effectiveness_err` | angular acceleration scaled by (1 + e) | inertia or motor-constant error (the model's g wrong) |
| `effectiveness_drift` | angular acceleration scaled down linearly over the flight | battery sag reducing motor effectiveness |
| `motor_asymmetry` | motor_1 delivers (1 + a) of its modelled torque, throughout | motor-to-motor variation |
| `cg_step` | at t_s the controller needs extra roll torque Δ (torque setpoint and allocator commands shift by Δ; the rotation does not), with an event placed at t_s − 0.5 s | a payload shift or CG change mid-flight |
| `thrust_step` | at t_s collective thrust rises by Δ (commands shift uniformly) | a mass change without a CG change |

**Gyro bias is not a variable:** B3 does not read the angular rate, only
its derivative, so a constant bias cannot reach it. That is structural.

**Scored** at the product's own discovered events (as in RB-001), with the
frozen decision rule:
- **false VIOLATED:** at every nominal event (nominal flights; telemetry
  faults V9, V10; the PRE events of fault flights; the synthetic `cg_step`
  and `thrust_step` events);
- **detection:** the injected motor VIOLATED at a POST or STRADDLE event of
  V1-V4, V12, V13;
- **wrong motor:** another motor VIOLATED at those events.

Writes B3_CHALLENGE.json. SITL bases: not physical evidence.
"""
from __future__ import annotations

import dataclasses
import json
from multiprocessing import Pool

import numpy as np

import common_prime as C
import evaluate_maneuver as EM
import maneuver as M
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R

FLIGHTS = [(C.SITL_2_3, f"V{i}") for i in range(1, 14)] + [(C.SITL_RB001, f"CAL{i}") for i in range(1, 6)]
VARIABLES = {
    "wdot_noise": [0.5, 1, 2, 5, 10, 20],
    "latency_ms": [5, 10, 20, 50, 100],
    "effectiveness_err": [-0.3, -0.2, -0.1, 0.1, 0.2, 0.3],
    "effectiveness_drift": [0.02, 0.05, 0.1, 0.15, 0.2],
    "motor_asymmetry": [-0.2, -0.1, -0.05, 0.05, 0.1, 0.2],
    "cg_step": [0.005, 0.01, 0.02, 0.05, 0.1],
    "thrust_step": [0.02, 0.05, 0.1, 0.2],
}
STEP_AT = {"CAL1": 70.0, "CAL2": 75.0, "CAL3": 75.0, "CAL4": 75.0, "CAL5": 75.0,
           "V5": 75.0, "V6": 75.0, "V11": 75.0}       # nominal flights only, mid-flight
SEEDS = 3


def prepare(item):
    d, rid = item
    path = d / f"{rid}.ulg"
    rec = json.loads(path.with_suffix(".json").read_text())
    f = M.load(path, rid)
    run = R.stock_flight(path)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    tr = EM.truth(rec, f.stock.t0_us)
    t_end = float(f.t[-1])
    events = [float(e["t0"]) for e in m["events"] if float(e["t0"]) + 15.0 <= t_end]
    return rid, f, tr, events


def perturb(f, mdl, var, level, seed):
    rng = np.random.default_rng(seed)
    wd, tau, u = f.omega_dot.copy(), f.tau.copy(), f.u.copy()
    t = f.t
    ramp = (t - t[0]) / max(t[-1] - t[0], 1e-9)
    if var == "wdot_noise":
        wd = wd + rng.normal(0.0, level, wd.shape)
    elif var == "latency_ms":
        tau = np.stack([np.interp(t - level * 1e-3, t, tau[:, i]) for i in range(3)], 1)
    elif var == "effectiveness_err":
        wd = mdl.c + (wd - mdl.c) * (1.0 + level)
    elif var == "effectiveness_drift":
        wd = mdl.c + (wd - mdl.c) * (1.0 - level * ramp)[:, None]
    elif var == "motor_asymmetry":
        # motor_1 delivers (1+a) of its modelled torque: extra angular acceleration a * g * B[:,1] * u_1
        wd = wd + (level * mdl.g[None, :] * mdl.B[None, :, 1] * u[:, 1:2])
    elif var in ("cg_step", "thrust_step"):
        t_s = STEP_AT.get(f.name)
        if t_s is not None:
            after = t >= t_s
            if var == "cg_step":
                tau[after, 0] += level
                u[after] += (mdl.A[:, 0] * level)[None, :]
            else:
                u[after] += (mdl.A[:, 3] * level)[None, :]
    return dataclasses.replace(f, omega_dot=wd, tau=tau, u=u)


def b3_states(f, mdl, cal, d, t0):
    s = {"delta": M.delta_b3(f, mdl, d, t0), "saturated": M.saturated(f, t0)}
    return M.decide("B3", s, cal), s["delta"]


def score(prep, mdl, cal, var, level, seed):
    false_v, detected, wrong, faults, step_false = 0, [], 0, [], 0
    for rid, f, tr, events in prep:
        g = perturb(f, mdl, var, level, seed)
        d = M.residual(g, mdl)
        evs = list(events)
        synthetic = None
        if var in ("cg_step", "thrust_step") and rid in STEP_AT:
            synthetic = STEP_AT[rid] - 0.5
            evs.append(synthetic)
        if tr["kind"] == "physical":
            faults.append(rid)
        hit = False
        for t0 in evs:
            st, _ = b3_states(g, mdl, cal, d, t0)
            v = [k for k, x in enumerate(st) if x == "VIOLATED"]
            cls = EM.event_class(t0, tr) if tr["kind"] == "physical" else "NOMINAL"
            if t0 == synthetic:
                step_false += len(v)
            if cls in ("NOMINAL", "PRE"):
                false_v += len(v)
            else:
                wrong += sum(1 for k in v if k != tr["motor"])
                hit = hit or tr["motor"] in v
        if tr["kind"] == "physical" and hit:
            detected.append(rid)
    return {"false_violated": false_v, "false_at_step_event": step_false, "wrong_motor": wrong,
            "detected": detected, "missed": [x for x in faults if x not in detected]}


def main():
    calib = json.loads((C.RB001 / "MANEUVER_CALIBRATION.json").read_text())
    cal, mdl = calib["calibration"], M.Model.from_dict(calib["model"])
    with Pool(3) as pool:
        prep = pool.map(prepare, FLIGHTS)
    out = {"baseline": score(prep, mdl, cal, "none", 0, 0)}
    print("baseline", out["baseline"], flush=True)
    for var, levels in VARIABLES.items():
        out[var] = {}
        for lv in levels:
            seeds = range(SEEDS) if var == "wdot_noise" else [0]
            rs = [score(prep, mdl, cal, var, lv, 7000 + s) for s in seeds]
            worst = {"false_violated": max(r["false_violated"] for r in rs),
                     "false_at_step_event": max(r["false_at_step_event"] for r in rs),
                     "wrong_motor": max(r["wrong_motor"] for r in rs),
                     "missed_max": max(len(r["missed"]) for r in rs),
                     "runs": rs}
            out[var][str(lv)] = worst
            print(var, lv, {k: v for k, v in worst.items() if k != "runs"}, flush=True)
    C.write_json(C.HERE / "B3_CHALLENGE.json", {
        "label": "PRIME C2: B3 sensitivity on development and calibration flights (SITL); "
                 "frozen model and threshold; not physical evidence",
        "flights": [r for _d, r in FLIGHTS], "theta_delta": cal["theta_delta"],
        "maneuver_py_sha256": C.sha(C.RB001 / "maneuver.py"),
        "calibration_sha256": C.sha(C.RB001 / "MANEUVER_CALIBRATION.json"),
        "results": out})


if __name__ == "__main__":
    main()
