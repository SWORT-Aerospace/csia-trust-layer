"""P1 — CSIA's own canonical fault families on the modern rig, B0/B1/B3.

WHY THIS EXISTS. E1's grid was built entirely around GNSS slew behaviour, so
`CSIA_ONLY = 0/8` there says nothing about the fault families CSIA was
actually designed to detect. This runs the frozen catalogue from
`csia/scenarios.py` — unchanged, no new fault modes — against ArduCopter 4.8
and asks the F4 kill question directly:

    does CSIA ever produce coverage the native autopilot does not?

RIG. Primary lane is LEGACY_COMPAT_CONTROL: ESC_TELEMETRY_1_TO_4 suppressed at
ingestion, because P0.5 proved that channel carries no information on this
build and would otherwise contaminate every algorithm comparison. FULL_MODERN
is kept as a separate compatibility lane and is NOT used for scoring. The
suppression is an experimental rig control, never a production fix.

TWO LEDGERS, both mandatory.
  A SAFETY-RESPONSE   did the system produce the declared escalation?
  B CORRECT-DIAGNOSTIC did it escalate FOR the injected fault, rather than
                       because an unrelated subsystem alarmed?
A candidate gets no credit for "detecting" a GNSS fault because a battery
artifact happened to fire LAND_NOW.

PARTITION. Every flight here is on flight spec 0, which PARTITION_AUDIT.md
classifies as CONTAMINATED and therefore usable as DEVELOPMENT. The held-out
validation spec is touched once, separately, with parameters already frozen.

Run:  PYTHONPATH=. python research/phase2/p1_fault_suite.py [--spec N]
Out:  research/phase2/results/fault_suite_coverage.json
      research/phase2/results/p1_streams.json   (per-tick, for offline B2/B4)
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, DEG_TO_M, Shim, connect, launch, new_state, pilot, read_param,
    sep_m, set_param)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

INJECT_S = 60.0
EKF_THRESH = 0.8          # ArduPilot's own FS_EKF_THRESH default
SIG_GPS_M = 48.0          # csia/scenarios.py gps_spoof reference displacement

# Flight specs from research/wp_c6/q_gvalid_campaign.py, unchanged.
FLIGHT_SPECS = {
    0: "47.397742,8.545594,488,0",
    1: "-35.363261,149.165230,584,0",
    2: "37.413360,-121.996500,10,90",
    3: "55.953251,-3.188267,47,180",
    4: "-22.906847,-43.172896,15,270",
    5: "64.128288,-21.827774,61,45",
}

# The frozen catalogue. `scenario` names the entry in csia/scenarios.py this
# arm reproduces; the injection is the ArduCopter 4.8 equivalent, verified
# reachable by p1_injection_discovery / p1_vib_wind_probe.
FAMILIES = [
    {"arm": "nominal", "scenario": "clean", "hold_s": 30.0,
     "inject": [], "ramp": None,
     "target_hypothesis": "nominal", "target_node": None,
     "expected_csia": "NO transition (R10)", "native_channel": None,
     "validity": "no injection to verify"},

    {"arm": "gps_spoof", "scenario": "gps_spoof", "hold_s": 30.0,
     "inject": [], "ramp": ("SIM_GPS1_GLTCH_X", SIG_GPS_M / DEG_TO_M, 15.0),
     "target_hypothesis": "gps_fault", "target_node": "gps",
     "expected_csia": "trust[gps] < 0.75 -> CAUTION nav_degraded",
     "native_channel": "pos_horiz_variance",
     "validity": "sep(GPS_RAW_INT, SIMSTATE) within 25% of 48 m"},

    {"arm": "gps_dropout", "scenario": "gps_dropout", "hold_s": 8.0,
     "inject": [("SIM_GPS1_ENABLE", 0, "INT8")], "ramp": None,
     "target_hypothesis": "nominal", "target_node": "gps",
     "expected_csia": "NO transition — trust must HOLD, not false-alarm",
     "native_channel": "pos_horiz_variance",
     "validity": "GPS_RAW_INT.fix_type drops below 3",
     "is_negative_control": True},

    {"arm": "imu0_bias_drift", "scenario": "imu0_bias_drift", "hold_s": 30.0,
     "inject": [], "ramp": ("SIM_ACC1_BIAS_Z", 1.0, 20.0),
     "target_hypothesis": "imu0_bias_drift", "target_node": "imu0",
     "expected_csia": "max(imu0,imu1) trust < 0.82 -> CAUTION",
     "native_channel": "velocity_variance",
     "validity": "RAW_IMU.zacc shifts by >= 50 mg"},

    {"arm": "mag_emi", "scenario": "mag_emi", "hold_s": 12.0,
     "inject": [("SIM_MAG1_OFS_X", 300.0, "REAL32")], "ramp": None,
     "target_hypothesis": "mag_interference", "target_node": "mag",
     "expected_csia": "trust[mag] < 0.60 -> CAUTION heading_degraded",
     "native_channel": "compass_variance",
     "validity": "RAW_IMU.xmag shifts by >= 100 mgauss"},

    {"arm": "power_sag", "scenario": "power_sag", "hold_s": 12.0,
     "inject": [("SIM_BATT_VOLTAGE", 11.4, "REAL32")], "ramp": None,
     "target_hypothesis": "power_fault", "target_node": "battery",
     "expected_csia": "trust[battery] < 0.70 -> CRITICAL power_fault",
     "native_channel": None,
     "validity": "BATTERY_STATUS voltage drops >= 0.8 V",
     "note": "the scenario's second half (ESC rpm sag) CANNOT be reproduced "
             "on this build: SITL rpm is a vibration-model term pinned at 0. "
             "This arm is therefore the voltage half only."},

    {"arm": "vibration_anomaly", "scenario": "vibration_anomaly",
     "hold_s": 15.0,
     "inject": [("SIM_ACC1_RND", 3.0, "REAL32"),
                ("SIM_ACC2_RND", 3.0, "REAL32"),
                ("SIM_VIB_MOT_MAX", 10.0, "REAL32"),
                ("SIM_VIB_MOT_MASK", 15, "INT32")], "ramp": None,
     "target_hypothesis": "vibration_anomaly", "target_node": "vibration",
     "expected_csia": "trust[vibration] < 0.60 -> CRITICAL structural",
     "native_channel": "velocity_variance",
     "validity": "VIBRATION rms rises >= 3x its pre-injection level"},

    {"arm": "dual_imu_failure", "scenario": "dual_imu_failure",
     "hold_s": 35.0, "inject": [],
     "ramp2": [("SIM_ACC1_BIAS_Z", 2.5, 25.0),
               ("SIM_ACC2_BIAS_Z", -2.2, 25.0)], "ramp": None,
     "target_hypothesis": "imu0_bias_drift|imu1_bias_drift",
     "target_node": "imu0",
     "expected_csia": "max(imu0,imu1) trust < 0.70 -> EMERGENCY",
     "native_channel": "velocity_variance",
     "validity": "both RAW_IMU.zacc and SCALED_IMU2.zacc shift >= 50 mg"},
]

REVERT = {"SIM_GPS1_GLTCH_X": 0.0, "SIM_GPS1_ENABLE": 1, "SIM_ACC1_BIAS_Z": 0.0,
          "SIM_ACC2_BIAS_Z": 0.0, "SIM_MAG1_OFS_X": 0.0,
          "SIM_BATT_VOLTAGE": 12.6, "SIM_ACC1_RND": 0.0, "SIM_ACC2_RND": 0.0,
          "SIM_VIB_MOT_MAX": 0.0, "SIM_VIB_MOT_MASK": 0}

# Which failsafe reason strings name which node, for the diagnostic ledger.
REASON_NODE = {"gps": "gps", "nav": "gps", "magnetometer": "mag",
               "mag ": "mag", "battery": "battery", "power": "battery",
               "vibration": "vibration", "structural": "vibration",
               "attitude": "imu0", "imu": "imu0"}


def reason_nodes(reasons):
    hit = set()
    for r in reasons:
        low = r.lower()
        for key, node in REASON_NODE.items():
            if key in low:
                hit.add(node)
    return sorted(hit)


def fly(fam, spec, rho_max, suppress, speedup, workdir, label):
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink
    from csia.trust_engine.engine import EngineConfig
    import research.phase2.modern_rig as rig

    hold = fam["hold_s"]
    end_s = INJECT_S + hold + 25.0
    rec = {"label": label, "arm": fam["arm"], "scenario": fam["scenario"],
           "flight_spec": spec, "rho_max": rho_max,
           "rig": "LEGACY_COMPAT_CONTROL" if suppress else "FULL_MODERN",
           "suppressed_messages": sorted(suppress),
           "target_hypothesis": fam["target_hypothesis"],
           "target_node": fam["target_node"],
           "expected_csia_response": fam["expected_csia"],
           "validity_rule": fam["validity"],
           "injection_commands_sent": 0, "transitions": [], "statustexts": [],
           "mode_changes": []}
    if fam.get("note"):
        rec["note"] = fam["note"]

    prev_home = rig.HOME
    rig.HOME = FLIGHT_SPECS[spec]
    proc = launch(workdir, speedup)
    rig.HOME = prev_home
    try:
        time.sleep(6.0)
        m = connect()
        st = new_state()
        cfg = EngineConfig(rho_max=rho_max) if rho_max else None
        layer = OnlineTrustLayer(field_mode=True, config=cfg,
                                 stale_timeout_s={"vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=20.0))
        ctx = {"t0": None}
        seen_tr = 0

        # Per-tick streams for offline B2/B4.
        #
        # `phys_*` is the CONSISTENCY, exp(-0.5*max(0, lam-1)), which floors
        # every sub-unity chi-square at exactly 1.0. On the first pass that
        # gave B2 and B4 a saturated input with clean-flight sigma = 0 on
        # every node except gps, which would have made them strawmen. The
        # brief forbids choosing weak baselines, so `lam_*` records the
        # pre-transform smoothed chi-square that the layer already computes
        # (OnlineTrustLayer._lam[f"phys_{node}"], read-only, no production
        # change). That is the residual sequence a classical sequential
        # detector should actually consume.
        S = {"t": [], "phys_gps": [], "phys_mag": [], "phys_baro": [],
             "phys_battery": [], "phys_vibration": [], "phys_imu0": [],
             "phys_imu1": [], "trust_gps": [], "trust_mag": [],
             "trust_battery": [], "trust_vibration": [], "trust_imu0": [],
             "trust_imu1": [], "ekf_pos": [], "ekf_vel": [], "ekf_comp": [],
             "lam_gps": [], "lam_mag": [], "lam_battery": [],
             "lam_vibration": [], "lam_motor_esc": [], "lam_baro": [],
             "lam_gps_eff": []}

        # Injection validity observables, WINDOWED.
        #
        # A first pass compared the whole post-injection period against the
        # whole pre-injection period and marked gps_dropout and
        # imu0_bias_drift invalid. Both injections were fine; the instrument
        # was. The dropout holds for 8 s inside a 33 s post window, so its
        # fraction diluted below threshold, and the accel ramp was averaged
        # together with its own ramp-up and the post-revert recovery.
        #
        # PRE  = the 15 s immediately before injection (airborne, settled)
        # POST = the second half of the hold, when the injection is at full
        #        commanded strength
        PRE_W = (INJECT_S - 15.0, INJECT_S)
        POST_W = (INJECT_S + hold * 0.5, INJECT_S + hold)

        def in_pre():
            return PRE_W[0] <= st["t"] < PRE_W[1]

        def in_post():
            return POST_W[0] <= st["t"] <= POST_W[1]

        pre = {"zacc0": [], "zacc1": [], "magx": [], "battv": [], "vibrms": []}
        post = {"zacc0": [], "zacc1": [], "magx": [], "battv": [],
                "vibrms": [], "fixlow": 0, "fixn": 0}
        gps_off_max, ekf = 0.0, {"pos": 0.0, "vel": 0.0, "comp": 0.0}
        ramp_done, ramp_n = 0, 0
        applied = {}
        first_native, first_csia = {}, None
        deadline = time.time() + (end_s / speedup) * 4 + 200

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            k = msg.get_type()
            isp = st["t"] >= INJECT_S

            if k == "STATUSTEXT":
                sev = int(getattr(msg, "severity", 6))
                txt = msg.text if isinstance(msg.text, str) else \
                    bytes(msg.text).decode(errors="ignore").strip("\x00")
                rec["statustexts"].append(
                    {"t": round(st["t"], 2), "severity": sev, "text": txt})
            elif k == "HEARTBEAT":
                mode = mavutil.mode_string_v10(msg)
                if not rec["mode_changes"] or \
                        rec["mode_changes"][-1][1] != mode:
                    rec["mode_changes"].append([round(st["t"], 1), mode])
            elif k == "EKF_STATUS_REPORT":
                for nm, at in (("pos", "pos_horiz_variance"),
                               ("vel", "velocity_variance"),
                               ("comp", "compass_variance")):
                    v = float(getattr(msg, at, 0.0))
                    if isp:
                        ekf[nm] = max(ekf[nm], v)
                        if v > EKF_THRESH and nm not in first_native:
                            first_native[nm] = round(st["t"], 3)
                    S[f"ekf_{nm}"].append(round(v, 5))
            elif k == "GPS_RAW_INT":
                sim = m.messages.get("SIMSTATE")
                if in_post():
                    post["fixn"] += 1
                    if msg.fix_type < 3:
                        post["fixlow"] += 1
                if sim is not None and msg.fix_type >= 3:
                    d = sep_m((msg.lat * 1e-7, msg.lon * 1e-7),
                              (sim.lat * 1e-7, sim.lng * 1e-7))
                    if isp:
                        gps_off_max = max(gps_off_max, d)
            elif k == "RAW_IMU":
                b = post if in_post() else (pre if in_pre() else None)
                if b is not None:
                    b["zacc0"].append(int(msg.zacc))
                    b["magx"].append(int(msg.xmag))
            elif k == "SCALED_IMU2":
                b = post if in_post() else (pre if in_pre() else None)
                if b is not None:
                    b["zacc1"].append(int(msg.zacc))
            elif k == "BATTERY_STATUS":
                v = [x for x in msg.voltages if 0 < x < 65535]
                b = post if in_post() else (pre if in_pre() else None)
                if v and b is not None:
                    b["battv"].append(sum(v) / 1000.0)
            elif k == "VIBRATION":
                r = math.sqrt((msg.vibration_x ** 2 + msg.vibration_y ** 2
                               + msg.vibration_z ** 2) / 3.0)
                b = post if in_post() else (pre if in_pre() else None)
                if b is not None:
                    b["vibrms"].append(r)

            if k not in suppress:
                for sensor, t, ch in map_mavlink(Shim(msg), ctx):
                    for state in layer.ingest(sensor, t, ch):
                        policy.update(state)
                        for tr in policy.transitions[seen_tr:]:
                            top = max(state.posterior.items(),
                                      key=lambda kv: kv[1])
                            e = {"t": round(tr.t, 2), "level": tr.level.name,
                                 "reasons": list(tr.reasons),
                                 "nodes_named": reason_nodes(tr.reasons),
                                 "top_cause": top[0],
                                 "top_p": round(float(top[1]), 4),
                                 "actions": [a.name for a in tr.actions]}
                            rec["transitions"].append(e)
                            if (tr.level.name != "NORMAL"
                                    and tr.t >= INJECT_S
                                    and first_csia is None):
                                first_csia = e
                        seen_tr = len(policy.transitions)
                        if not state.armed:
                            continue
                        S["t"].append(round(state.t, 3))
                        for n in ("gps", "mag", "baro", "battery",
                                  "vibration", "imu0", "imu1"):
                            c = state.components.get(n, {}).get("phys")
                            S[f"phys_{n}"].append(
                                None if c is None else round(float(c), 6))
                        for n in ("gps", "mag", "battery", "vibration",
                                  "imu0", "imu1"):
                            S[f"trust_{n}"].append(
                                round(float(state.trust[n]), 5))
                        # pre-transform smoothed chi-square, read-only
                        for n in ("gps", "mag", "battery", "vibration",
                                  "motor_esc", "baro"):
                            sm = layer._lam.get(f"phys_{n}")
                            y = None if sm is None or sm.y is None \
                                else float(sm.y)
                            S[f"lam_{n}"].append(
                                None if y is None else round(y, 8))
                        # GPS is the one node whose physics term is NOT
                        # _lam["phys_gps"]. online.py:568-573 forms
                        #     P["gps"] = max(lam_gps, (gps_step_peak/20)^2)
                        # and lam_gps is ~0 in SITL, so the step term does all
                        # the work. Recording only _lam["phys_gps"] handed B4
                        # a stream that is identically zero even under a GPS
                        # spoof, which would have made its GPS blindness an
                        # artifact of the instrument rather than a property of
                        # the method. This records the effective term.
                        lg = S["lam_gps"][-1] or 0.0
                        step = (float(getattr(layer, "_gps_step_peak", 0.0))
                                / 20.0) ** 2
                        S["lam_gps_eff"].append(round(max(lg, step), 8))

            st["t"] = ctx.get("t_last", 0.0)
            pilot(m, st, mavutil)

            # injection
            if st["t"] >= INJECT_S and st["t"] < INJECT_S + hold:
                if fam["inject"] and not applied:
                    for n, v, ty in fam["inject"]:
                        set_param(m, n, v, ty)
                        rec["injection_commands_sent"] += 1
                        applied[n] = v
                for spec_r in ([fam["ramp"]] if fam.get("ramp")
                               else fam.get("ramp2") or []):
                    if spec_r is None:
                        continue
                    name, full, secs = spec_r
                    want = min(int(secs), int(st["t"] - INJECT_S) + 1)
                    key = f"_ramp_{name}"
                    done = rec.get(key, 0)
                    while done < want:
                        done += 1
                        val = full * done / int(secs)
                        set_param(m, name, val, "REAL32")
                        rec["injection_commands_sent"] += 1
                        applied[name] = val
                    rec[key] = done
            elif st["t"] >= INJECT_S + hold and applied:
                for n in list(applied):
                    set_param(m, n, REVERT[n],
                              "INT32" if isinstance(REVERT[n], int)
                              else "REAL32")
                applied = {}
            if st["t"] >= end_s:
                break

        # ---- validity ----
        def mean(x):
            return sum(x) / len(x) if x else None
        v_pre = {k2: mean(v2) for k2, v2 in pre.items() if isinstance(v2, list)}
        v_post = {k2: mean(v2) for k2, v2 in post.items()
                  if isinstance(v2, list)}
        rec["injection_observables"] = {
            "pre_window_s": list(PRE_W), "post_window_s": list(POST_W),
            "pre": v_pre, "post": v_post,
            "gps_offset_max_m": round(gps_off_max, 2),
            "fix_below_3_frac_in_hold": (
                round(post["fixlow"] / post["fixn"], 3)
                if post["fixn"] else None)}
        a = fam["arm"]
        if a == "nominal":
            ok = True
        elif a == "gps_spoof":
            ok = abs(gps_off_max - SIG_GPS_M) <= 0.25 * SIG_GPS_M
        elif a == "gps_dropout":
            ok = (rec["injection_observables"]["fix_below_3_frac_in_hold"]
                  or 0) > 0.5
        elif a == "imu0_bias_drift":
            ok = (v_pre["zacc0"] is not None and v_post["zacc0"] is not None
                  and abs(v_post["zacc0"] - v_pre["zacc0"]) >= 50)
        elif a == "mag_emi":
            ok = (v_pre["magx"] is not None and v_post["magx"] is not None
                  and abs(v_post["magx"] - v_pre["magx"]) >= 100)
        elif a == "power_sag":
            ok = (v_pre["battv"] is not None and v_post["battv"] is not None
                  and (v_pre["battv"] - v_post["battv"]) >= 0.8)
        elif a == "vibration_anomaly":
            ok = (v_pre["vibrms"] not in (None, 0)
                  and v_post["vibrms"] is not None
                  and v_post["vibrms"] >= 3.0 * v_pre["vibrms"])
        elif a == "dual_imu_failure":
            ok = all(v_pre[x] is not None and v_post[x] is not None
                     and abs(v_post[x] - v_pre[x]) >= 50
                     for x in ("zacc0", "zacc1"))
        else:
            ok = False
        rec["TRIAL_VALID"] = bool(ok) and (
            a == "nominal" or rec["injection_commands_sent"] > 0)

        # ---- ledger A: safety response ----
        ch = fam["native_channel"]
        native_fs_mode = any(
            mm[1] in ("LAND", "RTL", "BRAKE", "SMART_RTL")
            for mm in rec["mode_changes"] if mm[0] >= INJECT_S)
        native_warn = [s for s in rec["statustexts"]
                       if s["t"] >= INJECT_S and s["severity"] <= 4]
        native_ekf = bool(ch and ch.startswith and False)
        chmap = {"pos_horiz_variance": "pos", "velocity_variance": "vel",
                 "compass_variance": "comp"}
        native_ekf = bool(ch and ekf[chmap[ch]] > EKF_THRESH) if ch else False
        rec["autopilot_response"] = bool(
            native_ekf or native_fs_mode or native_warn)
        rec["autopilot_evidence"] = {
            "ekf_max": {k2: round(v2, 4) for k2, v2 in ekf.items()},
            "ekf_channel": ch, "ekf_exceeded": native_ekf,
            "failsafe_mode_change": native_fs_mode,
            "warning_statustexts": native_warn[:6],
        }
        rec["autopilot_response_time_s"] = (
            round(min(first_native.values()) - INJECT_S, 3)
            if first_native else None)

        rec["csia_response"] = first_csia is not None
        rec["csia_final_diagnosis"] = (first_csia or {}).get("top_cause")
        rec["csia_response_time_s"] = (
            round(first_csia["t"] - INJECT_S, 3) if first_csia else None)
        rec["safety_action"] = (first_csia or {}).get("actions")

        # ---- ledger B: correct diagnostic ----
        tn = fam["target_node"]
        named = (first_csia or {}).get("nodes_named", [])
        if fam["arm"] == "nominal":
            rec["csia_correct_diagnostic"] = not rec["csia_response"]
            rec["csia_wrong_isolation"] = bool(rec["csia_response"])
            rec["unrelated_alarm"] = bool(rec["csia_response"])
        elif fam.get("is_negative_control"):
            # dropout: the scenario says trust must HOLD. Any escalation is
            # a false alarm, and NO escalation is the correct outcome.
            rec["csia_correct_diagnostic"] = not rec["csia_response"]
            rec["csia_wrong_isolation"] = bool(rec["csia_response"])
            rec["unrelated_alarm"] = bool(
                rec["csia_response"] and tn not in named)
        else:
            hit = tn in named or (tn == "imu0" and "imu0" in named)
            rec["csia_correct_diagnostic"] = bool(rec["csia_response"] and hit)
            rec["csia_wrong_isolation"] = bool(
                rec["csia_response"] and not hit)
            rec["unrelated_alarm"] = bool(
                rec["csia_response"] and named and tn not in named)
        rec["csia_nodes_named"] = named
        rec["streams"] = S
        return rec
    except Exception as exc:                                   # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["TRIAL_VALID"] = False
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def categorise(r, ledger):
    """Four mutually exclusive categories. `ledger` selects A or B."""
    A = r["autopilot_response"]
    C = r["csia_response"] if ledger == "A" else (
        r["csia_response"] and r["csia_correct_diagnostic"])
    if A and C:
        return "BOTH"
    if A:
        return "AUTOPILOT_ONLY"
    if C:
        return "CSIA_ONLY"
    return "JOINT_MISS"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=int, default=0)
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--rho", type=float, nargs="*",
                    default=[0.998, 0.99, 0.98, 0.96])
    ap.add_argument("--out", default="fault_suite_coverage.json")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, args.out)
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out_path, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    suppress = {"ESC_TELEMETRY_1_TO_4"}
    wd = os.path.join(RESULTS, "_wd_p1suite")
    rows = []
    for rho in args.rho:
        cand = "B1" if abs(rho - 0.998) < 1e-9 else f"B3_rho{rho:g}"
        print(f"\n=== {cand}  (rho_max={rho}, S_max={1/(1-rho):.0f}) "
              f"spec={args.spec} ===")
        for fam in FAMILIES:
            lbl = f"{cand}_{fam['arm']}_s{args.spec}"
            r = fly(fam, args.spec, rho, suppress, args.speedup, wd, lbl)
            r["candidate"] = cand
            rows.append(r)
            print(f"  {fam['arm']:18s} valid={str(r.get('TRIAL_VALID'))[:5]:5s} "
                  f"A={str(r.get('autopilot_response'))[0]} "
                  f"C={str(r.get('csia_response'))[0]} "
                  f"correct={str(r.get('csia_correct_diagnostic'))[0]} "
                  f"diag={str(r.get('csia_final_diagnosis'))[:16]:16s} "
                  f"-> {categorise(r, 'A') if 'error' not in r else 'ERR'}")
            if "error" in r:
                print(f"      ERROR {r['error']}")

    streams = {r["label"]: r.pop("streams") for r in rows if "streams" in r}
    sfile = "p1_streams" + ("" if args.out == "fault_suite_coverage.json"
                            else "_" + args.out.replace(".json", "")) + ".json"
    json.dump(streams, open(os.path.join(RESULTS, sfile), "w"))

    report = {"work_package": "P1 fault-suite F4 breadth test",
              "rig": "LEGACY_COMPAT_CONTROL",
              "rig_note": "ESC_TELEMETRY_1_TO_4 suppressed at ingestion; "
                          "experimental control, not a production fix",
              "flight_spec": args.spec,
              "home": FLIGHT_SPECS[args.spec],
              "families_source": "csia/scenarios.py, unchanged",
              "candidates": sorted({r["candidate"] for r in rows}),
              "ledgers": {
                  "A": "SAFETY-RESPONSE: did the system produce the declared "
                       "escalation?",
                  "B": "CORRECT-DIAGNOSTIC: did it escalate FOR the injected "
                       "fault rather than because something unrelated fired?"},
              "per_trial": rows}

    for cand in report["candidates"]:
        cr = [r for r in rows if r["candidate"] == cand
              and r.get("TRIAL_VALID") and r["arm"] != "nominal"
              and "error" not in r]
        summ = {}
        for ledger in ("A", "B"):
            cov = {"BOTH": 0, "AUTOPILOT_ONLY": 0, "CSIA_ONLY": 0,
                   "JOINT_MISS": 0}
            for r in cr:
                cov[categorise(r, ledger)] += 1
            summ[f"ledger_{ledger}"] = cov
        nom = [r for r in rows if r["candidate"] == cand
               and r["arm"] == "nominal"]
        summ["R10_nominal_transitions"] = sum(
            len([t for t in r["transitions"] if t["level"] != "NORMAL"])
            for r in nom)
        summ["valid_fault_trials"] = len(cr)
        summ["wrong_isolation"] = sum(
            1 for r in cr if r.get("csia_wrong_isolation"))
        report.setdefault("summary", {})[cand] = summ

    json.dump(report, open(out_path, "w"), indent=1, sort_keys=True)
    print("\n=== SUMMARY ===")
    for cand, s in report.get("summary", {}).items():
        print(f"  {cand:12s} R10={s['R10_nominal_transitions']:2d}  "
              f"ledgerA={s['ledger_A']}  ledgerB={s['ledger_B']}  "
              f"wrong_iso={s['wrong_isolation']}")
    print(f"wrote {os.path.relpath(out_path, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
