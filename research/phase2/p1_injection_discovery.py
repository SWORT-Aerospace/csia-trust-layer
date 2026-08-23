"""P1 step 0b — can CSIA's canonical fault families be injected on 4.8 at all?

Rule 1: COMMAND_ISSUED != INTERVENTION_VALID. Before the fault-suite campaign
is designed, every family needs a parameter that (a) exists on this build and
(b) demonstrably moves the telemetry the family is supposed to corrupt.

The families come from csia/scenarios.py, unchanged. They are the frozen set
the repository was designed against, not new fault modes.

This probe flies ONE aircraft and steps through the candidate injections one
at a time, recording the target telemetry before and during each. It draws no
scientific conclusion; it decides which families are injectable and what the
per-family validity check should be.

Also checks SIM_WIND_SPD, because the Phase-I flight-spec partition varies
(home, wind) and WP-C7 measured wind as cosmetic on ArduCopter 3.3. If it is
cosmetic on 4.8 too, the six flight specs differ only by home site and the
partition is weaker than it reads.

Run:  PYTHONPATH=. python research/phase2/p1_injection_discovery.py
Out:  research/phase2/results/p1_injection_discovery.json
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, connect, launch, new_state, pilot, read_param, set_param)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

# (family, [(param, value, type)], probe_key, description)
# Values are deliberately large: this probe asks "does it reach the sensor",
# not "what is the detection threshold".
PROBES = [
    ("gps_spoof", [("SIM_GPS1_GLTCH_X", 0.0005, "REAL32")], "gps_offset_m",
     "GPS position offset, the E1 injection"),
    ("gps_dropout", [("SIM_GPS1_ENABLE", 0, "INT8")], "gps_fix_type",
     "outright GNSS denial"),
    ("imu0_bias_drift", [("SIM_ACC1_BIAS_Z", 2.0, "REAL32")], "imu0_zacc",
     "accel-z bias on the primary IMU"),
    ("imu1_bias_drift", [("SIM_ACC2_BIAS_Z", -2.0, "REAL32")], "imu1_zacc",
     "accel-z bias on the secondary IMU"),
    ("mag_emi", [("SIM_MAG1_OFS_X", 300.0, "REAL32")], "mag_x",
     "magnetometer offset (EMI stand-in)"),
    ("power_sag", [("SIM_BATT_VOLTAGE", 11.0, "REAL32")], "batt_v",
     "pack voltage sag"),
    # PASS 1 used SIM_VIB_MOT_MAX alone and measured no effect. That was the
    # wrong parameter, not a missing capability:
    # AP_InertialSensor_SITL.cpp:154 scales motor vibration by
    # `accel_noise * vibe_motor_scale`, and SITL.cpp:1060 defaults
    # SIM_ACC1_RND (accel_noise[0]) to 0 — its own description calls it the
    # "scaling factor for simulated vibration from motors". VIB_MOT_MAX gates
    # and sets frequency; ACC*_RND sets amplitude. Pass 1 is preserved at
    # results/p1_injection_discovery_pass1.json.
    ("vibration_anomaly", [("SIM_ACC1_RND", 5.0, "REAL32"),
                           ("SIM_ACC2_RND", 5.0, "REAL32"),
                           ("SIM_VIB_MOT_MAX", 8.0, "REAL32")], "vibe_rms",
     "airframe vibration from motors"),
    # PASS 1 held wind for 12 s and read attitude at a single instant. The
    # wind slew has a 5 s start delay plus a SIM_WIND_TC = 5 s low-pass
    # (SIMState.cpp:298-309), and a single ATTITUDE sample mid-leg is a poor
    # instrument. Now held longer and averaged over a window.
    ("wind_factor", [("SIM_WIND_SPD", 15.0, "REAL32")], "wind_effect",
     "flight-spec wind axis; cosmetic on 3.3 per WP-C7"),
]

SETTLE_S = 25.0     # sim seconds each probe is held
WINDOW_FRAC = 0.4   # average the observable over the last 40% of the hold
BASE_S = 45.0       # airborne and stable before the first probe


def observe(m, mavutil):
    """Snapshot every quantity a probe could move."""
    import math
    g = m.messages.get("GPS_RAW_INT")
    sim = m.messages.get("SIMSTATE")
    imu = m.messages.get("RAW_IMU")
    imu2 = m.messages.get("SCALED_IMU2")
    vib = m.messages.get("VIBRATION")
    bat = m.messages.get("BATTERY_STATUS")
    att = m.messages.get("ATTITUDE")
    ekf = m.messages.get("EKF_STATUS_REPORT")
    out = {}
    if g and sim:
        dn = (g.lat * 1e-7 - sim.lat * 1e-7) * 111320.0
        de = ((g.lon * 1e-7 - sim.lng * 1e-7) * 111320.0
              * math.cos(math.radians(sim.lat * 1e-7)))
        out["gps_offset_m"] = round(math.hypot(dn, de), 2)
    if g:
        out["gps_fix_type"] = int(g.fix_type)
        out["gps_sats"] = int(getattr(g, "satellites_visible", 0))
    if imu:
        out["imu0_zacc"] = int(imu.zacc)
        out["mag_x"] = int(imu.xmag)
    if imu2:
        out["imu1_zacc"] = int(imu2.zacc)
    if vib:
        out["vibe_rms"] = round(
            (vib.vibration_x ** 2 + vib.vibration_y ** 2
             + vib.vibration_z ** 2) ** 0.5 / 3 ** 0.5, 4)
    if bat:
        v = [x for x in bat.voltages if 0 < x < 65535]
        out["batt_v"] = round(sum(v) / 1000.0, 3) if v else None
    if att:
        # wind on a velocity-commanded quad shows as a steady lean
        out["wind_effect"] = round(
            (att.roll ** 2 + att.pitch ** 2) ** 0.5, 4)
    if ekf:
        out["ekf_pos_var"] = round(
            float(getattr(ekf, "pos_horiz_variance", 0.0)), 4)
        out["ekf_compass_var"] = round(
            float(getattr(ekf, "compass_variance", 0.0)), 4)
        out["ekf_vel_var"] = round(
            float(getattr(ekf, "velocity_variance", 0.0)), 4)
    return out


def main() -> int:
    from pymavlink import mavutil

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "p1_injection_discovery.json")
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out_path, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    wd = os.path.join(RESULTS, "_wd_p1disc")
    proc = launch(wd, 20)
    rows, existence = [], {}
    try:
        time.sleep(6.0)
        m = connect()
        st = new_state()

        # 1. existence check for every parameter, before flying
        for fam, params, _, _ in PROBES:
            for name, _v, _t in params:
                existence[name] = read_param(m, name, 5.0)

        # 2. fly, then step through the probes
        t_next = BASE_S
        stage = -1
        baseline = None
        window = []
        deadline = time.time() + 900
        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                break
            gpi = m.messages.get("GLOBAL_POSITION_INT")
            st["t"] = (gpi.time_boot_ms / 1000.0) if gpi else st["t"]
            pilot(m, st, mavutil)

            # accumulate over the last WINDOW_FRAC of each hold, so a single
            # unlucky sample cannot decide a family
            if st["t"] >= t_next - SETTLE_S * WINDOW_FRAC:
                window.append(observe(m, mavutil))

            if st["t"] >= t_next:
                keys = set().union(*[set(w) for w in window]) if window else set()
                snap = {}
                for k in keys:
                    vals = [w[k] for w in window
                            if w.get(k) is not None]
                    snap[k] = (round(sum(vals) / len(vals), 4)
                               if vals else None)
                window = []
                if stage < 0:
                    baseline = snap
                    rows.append({"stage": "baseline", "t": round(st["t"], 1),
                                 "observed": snap})
                else:
                    fam, params, key, desc = PROBES[stage]
                    b = (baseline or {}).get(key)
                    a = snap.get(key)
                    moved = (b is not None and a is not None
                             and abs(float(a) - float(b))
                             > max(0.02 * abs(float(b)), 0.05))
                    rows.append({
                        "stage": fam, "t": round(st["t"], 1),
                        "description": desc,
                        "params": [[n, v] for n, v, _ in params],
                        "params_exist": all(
                            existence.get(n) is not None for n, _, _ in params),
                        "readback": {n: read_param(m, n, 3.0)
                                     for n, _, _ in params},
                        "probe_key": key,
                        "baseline_value": b,
                        "injected_value": a,
                        "target_telemetry_moved": bool(moved),
                        "observed": snap,
                    })
                    print(f"  {fam:20s} {key:14s} {b} -> {a}   "
                          f"moved={moved}")
                    # revert so probes do not compound
                    for name, _v, ty in params:
                        rev = {"SIM_GPS1_GLTCH_X": 0.0, "SIM_GPS1_ENABLE": 1,
                               "SIM_ACC1_BIAS_Z": 0.0, "SIM_ACC2_BIAS_Z": 0.0,
                               "SIM_MAG1_OFS_X": 0.0,
                               "SIM_BATT_VOLTAGE": 12.6,
                               "SIM_ACC1_RND": 0.0, "SIM_ACC2_RND": 0.0,
                               "SIM_VIB_MOT_MAX": 0.0,
                               "SIM_WIND_SPD": 0.0}[name]
                        set_param(m, name, rev, ty)
                stage += 1
                if stage >= len(PROBES):
                    break
                fam, params, key, desc = PROBES[stage]
                for name, val, ty in params:
                    set_param(m, name, val, ty)
                t_next = st["t"] + SETTLE_S
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    injectable = [r["stage"] for r in rows
                  if r.get("target_telemetry_moved")]
    not_injectable = [r["stage"] for r in rows
                      if r.get("target_telemetry_moved") is False]
    report = {
        "purpose": "decide which of CSIA's canonical fault families can be "
                   "injected on ArduCopter 4.8, and what the per-family "
                   "validity check should be",
        "families_source": "csia/scenarios.py, unchanged",
        "rule": "COMMAND_ISSUED != INTERVENTION_VALID",
        "parameter_existence": existence,
        "probes": rows,
        "injectable": injectable,
        "not_injectable": not_injectable,
        "wind_axis_note": (
            "SIM_WIND_SPD drives the flight-spec partition's second factor. "
            "WP-C7 measured it as cosmetic on ArduCopter 3.3. If it is "
            "cosmetic here too, FLIGHT_SPECS 0-5 differ only by home site."),
    }
    json.dump(report, open(out_path, "w"), indent=1, sort_keys=True)
    print(f"\ninjectable:     {injectable}")
    print(f"NOT injectable: {not_injectable}")
    print(f"wrote {os.path.relpath(out_path, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
