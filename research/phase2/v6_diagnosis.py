"""Phase-II diagnostic — why did V6 fail on the slow small-amplitude cells?

E1 (research/phase2/results/e1_modern.json) reported three INVALID trials.
All three are a55.7 at slew 60, 120 and 240 s, and all three failed the same
check:

    V6_truth_matches_schedule   realized displacement within 25% of requested

The realized figures were 39.28, 39.86 and 38.61 m against a requested 55.7 m
(ratio 0.69-0.72), while the SAME parameter value at slew 20 s realized
56.07 m (ratio 1.007) and every a556.6 cell realized 0.85-1.00. The parameter
readback was exact in all eight cells, so the autopilot held the value we
asked for.

WHAT THIS SCRIPT TESTS. E1 estimated "realized displacement" as

    max over the post-injection window of  sep(GPS_RAW_INT(t), GPS_RAW_INT(t_inject))

That is the reported position's motion away from a fixed pre-injection mark.
ArduPilot's simulated receiver adds the glitch to the vehicle's TRUE position
(libraries/SITL/SIM_GPS.cpp:581, `d.latitude += glitch_offsets.x`), so

    reported(t) = truth(t) + glitch(t)
    sep(reported(t), reported(t_inject)) = | glitch(t) + (truth(t) - truth(t_inject)) |

and the estimator therefore contains the vehicle's own real motion. The
vehicle is flying a velocity-commanded square pattern, and — this is the part
that matters — a slow GPS ramp presents to the estimator as a small constant
velocity bias, which the velocity controller cancels by flying the airframe
the other way. The vehicle's true motion is not a nuisance term here; it is
CAUSED BY the fault, and it subtracts from the quantity E1 measured.

The correct instrument for injected sensor displacement is the separation
between the reported position and the simulator's own truth, SIMSTATE:

    injected_offset(t) = sep(GPS_RAW_INT(t), SIMSTATE(t))

which by the line of SIM_GPS.cpp above is the glitch itself.

This script flies one invalid cell (a55.7_s60), one valid cell (a55.7_s20) and
one nominal arm, logging both estimators side by side, plus the vehicle's true
track and the battery channel that trips R10 at t~46 s in every flight. It
injects nothing that E1 did not inject and changes no threshold. It decides
which quantity V6 should be computed from.

Run:  PYTHONPATH=. python research/phase2/v6_diagnosis.py
Out:  research/phase2/results/v6_diagnosis.json
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, DEG_TO_M, P_GLITCH_X, Shim, connect, launch, new_state, pilot,
    read_param, sep_m, set_param)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
INJECT_S = 60.0
POST_S = 30.0
SAMPLE_DT = 1.0


def run(label, amp_m, slew_s, speedup, workdir, nominal=False):
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    end_s = INJECT_S + slew_s + POST_S
    rec = {"label": label, "amplitude_m": 0.0 if nominal else amp_m,
           "slew_s": slew_s, "inject_at_s": INJECT_S, "end_s": end_s,
           "series": [], "commands_sent": 0}
    proc = launch(workdir, speedup)
    try:
        time.sleep(6.0)
        m = connect()
        st = new_state()
        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=20.0))
        ctx = {"t0": None}

        amp_deg = amp_m / DEG_TO_M
        n_steps = max(1, int(slew_s))
        steps_done, applied = 0, 0.0

        raw_ref = truth_ref = None
        next_sample = 0.0
        last = {"batt_v": None, "batt_i": None, "phys_batt": None,
                "trust_batt": None, "ekf_var": None, "phys_gps": None,
                "trust_gps": None}
        seen_tr, alarms = 0, []
        deadline = time.time() + (end_s / speedup) * 4 + 150

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            k = msg.get_type()
            if k == "EKF_STATUS_REPORT":
                last["ekf_var"] = round(
                    float(getattr(msg, "pos_horiz_variance", 0.0)), 6)
            elif k == "BATTERY_STATUS":
                v = [x for x in msg.voltages if 0 < x < 65535]
                last["batt_v"] = round(sum(v) / 1000.0, 4) if v else None
                last["batt_i"] = round(msg.current_battery / 100.0, 3)

            for sensor, t, ch in map_mavlink(Shim(msg), ctx):
                for state in layer.ingest(sensor, t, ch):
                    policy.update(state)
                    for tr in policy.transitions[seen_tr:]:
                        if tr.level.name != "NORMAL":
                            alarms.append({"t": round(tr.t, 2),
                                           "level": tr.level.name,
                                           "reasons": list(tr.reasons)})
                    seen_tr = len(policy.transitions)
                    last["phys_batt"] = state.components.get(
                        "battery", {}).get("phys")
                    last["phys_gps"] = state.components.get(
                        "gps", {}).get("phys")
                    last["trust_batt"] = round(state.trust["battery"], 5)
                    last["trust_gps"] = round(state.trust["gps"], 5)

            st["t"] = ctx.get("t_last", 0.0)
            pilot(m, st, mavutil)

            if (not nominal) and st["t"] >= INJECT_S and steps_done < n_steps:
                want = min(n_steps, int(st["t"] - INJECT_S) + 1)
                while steps_done < want:
                    steps_done += 1
                    applied = amp_deg * steps_done / n_steps
                    set_param(m, P_GLITCH_X, applied, "REAL32")
                    rec["commands_sent"] += 1

            gps = m.messages.get("GPS_RAW_INT")
            sim = m.messages.get("SIMSTATE")
            if gps is not None and sim is not None and gps.fix_type >= 3:
                g = (gps.lat * 1e-7, gps.lon * 1e-7)
                # SIMSTATE carries the vehicle's TRUE position, ungitched.
                tr_p = (sim.lat * 1e-7, sim.lng * 1e-7)
                if st["t"] < INJECT_S:
                    raw_ref, truth_ref = g, tr_p
                if st["t"] >= next_sample and st["t"] > 0:
                    next_sample = st["t"] + SAMPLE_DT
                    rec["series"].append({
                        "t": round(st["t"], 2),
                        "phase": st["phase"],
                        # the injected sensor offset, reported minus truth
                        "gps_minus_truth_m": round(sep_m(g, tr_p), 3),
                        # what E1 measured: reported motion from a fixed mark
                        "gps_from_preinject_m": (round(sep_m(g, raw_ref), 3)
                                                 if raw_ref else None),
                        # the airframe's own real motion from the same mark
                        "truth_from_preinject_m": (
                            round(sep_m(tr_p, truth_ref), 3)
                            if truth_ref else None),
                        "commanded_offset_m": round(
                            applied * DEG_TO_M, 3),
                        **{k2: v2 for k2, v2 in last.items()},
                    })
            if st["t"] >= end_s:
                break

        rec["param_readback_after"] = (None if nominal
                                       else read_param(m, P_GLITCH_X))
        rec["param_requested"] = round(applied, 9)
        rec["final_layer_time_s"] = round(st["t"], 2)
        rec["alarms"] = alarms
        return rec
    except Exception as exc:                                   # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def summarise(rec):
    post = [p for p in rec["series"] if p["t"] >= INJECT_S]
    pre = [p for p in rec["series"] if p["t"] < INJECT_S]
    if not post:
        return {"error": "no post-injection samples"}
    amp = rec["amplitude_m"]
    off_max = max(p["gps_minus_truth_m"] for p in post)
    off_pre = (max(p["gps_minus_truth_m"] for p in pre) if pre else None)
    e1_est = max((p["gps_from_preinject_m"] or 0.0) for p in post)
    truth_max = max((p["truth_from_preinject_m"] or 0.0) for p in post)
    truth_pre = (max((p["truth_from_preinject_m"] or 0.0) for p in pre)
                 if pre else None)
    return {
        "requested_m": amp,
        "injected_offset_max_m": round(off_max, 2),
        "injected_offset_ratio": (round(off_max / amp, 3) if amp else None),
        "preinject_gps_truth_separation_m": (round(off_pre, 2)
                                             if off_pre is not None else None),
        "e1_estimator_m": round(e1_est, 2),
        "e1_estimator_ratio": (round(e1_est / amp, 3) if amp else None),
        "true_vehicle_excursion_max_m": round(truth_max, 2),
        "true_vehicle_excursion_preinject_max_m": (
            round(truth_pre, 2) if truth_pre is not None else None),
        "shortfall_m": round(off_max - e1_est, 2),
    }


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "v6_diagnosis.json")
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    wd = os.path.join(RESULTS, "_wd_diag")
    arms = [("a55.7_s60_INVALID_in_E1", 55.7, 60, False),
            ("a55.7_s20_VALID_in_E1", 55.7, 20, False),
            ("nominal_60", 0.0, 60, True)]
    rows = []
    for label, amp, slew, nom in arms:
        print(f"  {label:26s} ...", flush=True)
        r = run(label, amp, slew, 20, wd, nominal=nom)
        r["summary"] = summarise(r)
        rows.append(r)
        s = r["summary"]
        if "error" in s or "error" in r:
            print(f"      ERROR {r.get('error') or s.get('error')}")
        elif nom:
            print(f"      nominal: gps-truth max "
                  f"{s['injected_offset_max_m']} m, alarms {len(r['alarms'])}")
        else:
            print(f"      requested {s['requested_m']} m  |  injected "
                  f"{s['injected_offset_max_m']} m "
                  f"(x{s['injected_offset_ratio']})  |  E1 estimator "
                  f"{s['e1_estimator_m']} m (x{s['e1_estimator_ratio']})  |  "
                  f"true excursion {s['true_vehicle_excursion_max_m']} m")

    json.dump({
        "question": "is the V6 shortfall an instrument error or a real "
                    "injection shortfall?",
        "glitch_mechanics": (
            "libraries/SITL/SIM_GPS.cpp:581 adds the glitch to the vehicle's "
            "true latitude AFTER the delay buffer, so reported = truth + "
            "glitch exactly and sep(GPS_RAW_INT, SIMSTATE) IS the glitch."),
        "arms": rows,
    }, open(out, "w"), indent=1, sort_keys=True)
    print(f"wrote {os.path.relpath(out, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
