"""Focused probe: are `vibration` and `wind` injectable on ArduCopter 4.8?

Both came back NOT injectable in p1_injection_discovery, with the parameters
reading back exactly as set. That is the P0.5 pattern, so it needs the same
treatment: observe the UPSTREAM quantity, not just the downstream message.

  vibration:  SIM_ACC*_RND is the amplitude of simulated motor vibration
              (AP_InertialSensor_SITL.cpp:154, SITL.cpp:1060). If it reaches
              the accelerometer, RAW_IMU's sample-to-sample scatter must rise
              whether or not the VIBRATION message reports it. Measuring both
              separates "the injection does not reach the sensor" from "the
              VIBRATION channel does not report it".

  wind:       SIM_WIND_SPD must make a velocity-commanded quad lean. Measured
              on ATTITUDE over a long window, with altitude recorded because
              SIM_WIND_T defaults to WIND_TYPE_SQRT, which scales wind by
              sqrt(alt / SIM_WIND_T_ALT) below 60 m (SIMState.cpp:319-322).

Stage order includes a NULL stage between the two injections (RULE A): if the
metrics do not return toward baseline in the null stage, the instrument is
drifting and nothing may be concluded.

Run:  PYTHONPATH=. python research/phase2/p1_vib_wind_probe.py
Out:  research/phase2/results/p1_vib_wind_probe.json
"""

import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, connect, launch, new_state, pilot, read_param, set_param)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

STAGES = [
    ("baseline", []),
    ("vib_accrnd", [("SIM_ACC1_RND", 10.0, "REAL32"),
                    ("SIM_ACC2_RND", 10.0, "REAL32"),
                    ("SIM_VIB_MOT_MAX", 10.0, "REAL32"),
                    ("SIM_VIB_MOT_MASK", 15, "INT32")]),
    ("vib_freq", [("SIM_ACC1_RND", 10.0, "REAL32"),
                  ("SIM_ACC2_RND", 10.0, "REAL32"),
                  ("SIM_VIB_FREQ_X", 40.0, "REAL32"),
                  ("SIM_VIB_FREQ_Y", 40.0, "REAL32"),
                  ("SIM_VIB_FREQ_Z", 40.0, "REAL32")]),
    ("null_control", []),
    ("wind", [("SIM_WIND_SPD", 15.0, "REAL32"),
              ("SIM_WIND_DIR", 90.0, "REAL32")]),
]
REVERT = {"SIM_ACC1_RND": 0.0, "SIM_ACC2_RND": 0.0, "SIM_VIB_MOT_MAX": 0.0,
          "SIM_VIB_MOT_MASK": 0, "SIM_VIB_FREQ_X": 0.0, "SIM_VIB_FREQ_Y": 0.0,
          "SIM_VIB_FREQ_Z": 0.0, "SIM_WIND_SPD": 0.0, "SIM_WIND_DIR": 180.0}
HOLD_S = 40.0
BASE_S = 45.0


def stats(vals):
    if not vals:
        return None
    n = len(vals)
    mu = sum(vals) / n
    var = sum((v - mu) ** 2 for v in vals) / n
    return {"n": n, "mean": round(mu, 5), "sd": round(var ** 0.5, 5),
            "min": round(min(vals), 5), "max": round(max(vals), 5)}


def main() -> int:
    from pymavlink import mavutil

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "p1_vib_wind_probe.json")
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out_path, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    proc = launch(os.path.join(RESULTS, "_wd_vibwind"), 20)
    rows = []
    try:
        time.sleep(6.0)
        m = connect()
        st = new_state()
        exists = {}
        for _s, params in STAGES:
            for n, _v, _t in params:
                if n not in exists:
                    exists[n] = read_param(m, n, 4.0)

        stage_i = 0
        t_end = BASE_S + HOLD_S
        acc, vib, att, alt, agl = [], [], [], [], []
        prev_acc = None
        for n, v, ty in STAGES[0][1]:
            set_param(m, n, v, ty)

        deadline = time.time() + 1200
        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                break
            k = msg.get_type()
            gpi = m.messages.get("GLOBAL_POSITION_INT")
            st["t"] = (gpi.time_boot_ms / 1000.0) if gpi else st["t"]

            # only measure in the last 60% of each hold, once flying
            measuring = st["t"] > t_end - HOLD_S * 0.6 and st["phase"] == "fly"
            if measuring:
                if k == "RAW_IMU":
                    a = (msg.xacc, msg.yacc, msg.zacc)
                    if prev_acc is not None:
                        # sample-to-sample jitter: rises with accel noise
                        # regardless of what the VIBRATION channel reports
                        acc.append(math.dist(a, prev_acc))
                    prev_acc = a
                elif k == "VIBRATION":
                    vib.append(math.sqrt(
                        (msg.vibration_x ** 2 + msg.vibration_y ** 2
                         + msg.vibration_z ** 2) / 3.0))
                elif k == "ATTITUDE":
                    att.append(math.hypot(msg.roll, msg.pitch))
                elif k == "GLOBAL_POSITION_INT":
                    alt.append(msg.relative_alt / 1000.0)
                elif k == "TERRAIN_REPORT":
                    agl.append(float(getattr(msg, "current_height", 0.0)))

            pilot(m, st, mavutil)

            if st["t"] >= t_end:
                name, params = STAGES[stage_i]
                rows.append({
                    "stage": name,
                    "t_end": round(st["t"], 1),
                    "params": {n: v for n, v, _ in params},
                    "readback": {n: read_param(m, n, 3.0) for n, _, _ in params},
                    "raw_imu_sample_jitter_mg": stats(acc),
                    "vibration_msg_rms": stats(vib),
                    "attitude_lean_rad": stats(att),
                    "relative_alt_m": stats(alt),
                })
                r = rows[-1]
                print(f"  {name:14s} imu_jitter={r['raw_imu_sample_jitter_mg']}")
                print(f"  {'':14s} vib_msg   ={r['vibration_msg_rms']}")
                print(f"  {'':14s} lean      ={r['attitude_lean_rad']}  "
                      f"alt={(r['relative_alt_m'] or {}).get('mean')}")
                for n, _v, ty in params:
                    set_param(m, n, REVERT[n], ty)
                stage_i += 1
                if stage_i >= len(STAGES):
                    break
                acc, vib, att, alt, agl = [], [], [], [], []
                prev_acc = None
                for n, v, ty in STAGES[stage_i][1]:
                    set_param(m, n, v, ty)
                t_end = st["t"] + HOLD_S
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    def g(stage, field, key="mean"):
        r = next((x for x in rows if x["stage"] == stage), None)
        return (r or {}).get(field, {}) and (r[field] or {}).get(key)

    base_j, base_v, base_l = (g("baseline", "raw_imu_sample_jitter_mg"),
                              g("baseline", "vibration_msg_rms"),
                              g("baseline", "attitude_lean_rad"))
    verdict = {
        "vibration_reaches_accelerometer": None,
        "vibration_message_reports_it": None,
        "wind_reaches_airframe": None,
    }
    for s in ("vib_accrnd", "vib_freq"):
        j, v = g(s, "raw_imu_sample_jitter_mg"), g(s, "vibration_msg_rms")
        if base_j and j and j > 1.5 * base_j:
            verdict["vibration_reaches_accelerometer"] = True
        if base_v and v and v > 1.5 * base_v:
            verdict["vibration_message_reports_it"] = True
    if verdict["vibration_reaches_accelerometer"] is None:
        verdict["vibration_reaches_accelerometer"] = False
    if verdict["vibration_message_reports_it"] is None:
        verdict["vibration_message_reports_it"] = False
    lw = g("wind", "attitude_lean_rad")
    verdict["wind_reaches_airframe"] = bool(base_l and lw and lw > 3.0 * base_l)

    report = {
        "purpose": "separate 'injection does not reach the sensor' from "
                   "'the reporting channel does not carry it', for the two "
                   "families that failed p1_injection_discovery",
        "parameter_existence": exists,
        "stages": rows,
        "verdict": verdict,
        "null_control": "the null_control stage sits between the vibration "
                        "and wind injections; metrics must return toward "
                        "baseline there or nothing may be concluded",
    }
    json.dump(report, open(out_path, "w"), indent=1, sort_keys=True)
    print(f"\nverdict: {json.dumps(verdict)}")
    print(f"wrote {os.path.relpath(out_path, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
