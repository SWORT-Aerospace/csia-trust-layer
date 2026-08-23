"""WP-C7 Part 1.2 — did the varied parameters ever reach the simulation?

THIS IS THE BLOCKING CHECK. The WP-C6 campaign reported a per-flight gate
closure rate that was identical to six decimal places across six home sites
and winds from 0 to 10 m/s. Zero between-flight variance is not a normal
experimental result. There are two explanations and they have opposite
consequences:

  REAL      the flights genuinely differ, and the injection deterministically
            dominates the gate. Then the campaign is 24 conditions and its
            numbers stand, though the intervals are still degenerate.
  ARTIFACT  wind and home never reached the simulation. Then the campaign is
            ONE condition replicated 24 times, and every interval in the
            manuscript is wrong.

The test has two halves and both must pass to conclude REAL:

  (a) INPUT REACHED THE SIM. Read SIM_WIND_SPD and SIM_WIND_DIR back from the
      autopilot after writing them, and read the home position out of the
      first fixed GPS sample. A write that was clamped or rejected shows here.
  (b) OUTPUT DIFFERED. Wind that reaches the simulator must change the
      trajectory: a multirotor holding position in wind tilts into it. Measure
      attitude, ground speed and position spread over the cruise window and
      check they separate across specs.

Then, separately, the gate: fly the denial arm and record the exact layer time
of the FIRST gvalid closure per flight. If (a) and (b) pass and first-closure
time is still identical, the zero variance is a property of the gate response
and not of the experiment.

Run:  PYTHONPATH=. python research/wp_c7/variance_investigation.py
Out:  research/wp_c7/results/variance_investigation.json
"""

import argparse
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c6.q_gvalid_campaign import (                   # noqa: E402
    ARMS, DEFAULT_BINARY, DEFAULT_EEPROM, FLIGHT_SPECS, PREREG, _Shim,
    _pilot, _set, locate_sitl)

RESULTS = os.path.join(os.path.dirname(__file__), "results")

# Parameters whose value is read back from the autopilot rather than assumed.
READBACK = ("SIM_WIND_SPD", "SIM_WIND_DIR", "FS_EKF_THRESH")

CRUISE_START_S = 30.0      # airborne and settled by here in every WP-C6 flight


def fly_instrumented(binary, eeprom, spec, arm_name, arm_cfg, speedup,
                     workdir):
    """One flight, instrumented for the variance question rather than q_gvalid.

    Records what the autopilot says its own parameters are, where it thinks it
    is, and what the vehicle actually did, alongside the gate trace.
    """
    from pymavlink import mavutil

    from csia.runtime import OnlineTrustLayer
    from csia.runtime.plugins import map_mavlink

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup),
         "--home", spec["home"]],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    rec = {"arm": arm_name, "spec_id": spec["id"], "home_requested":
           spec["home"], "wind_requested": list(spec["wind"])}
    try:
        time.sleep(4.0)
        m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
        m.wait_heartbeat(timeout=60)
        for stream, hz in ((mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 25),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
                            10),
                           (mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 5)):
            m.mav.request_data_stream_send(m.target_system, m.target_component,
                                           stream, hz, 1)
        _set(m, "FS_THR_ENABLE", 0.0, "INT32")
        _set(m, "FS_GCS_ENABLE", 0.0, "INT32")
        _set(m, "FS_EKF_THRESH", 10.0, "REAL32")
        _set(m, "SIM_WIND_SPD", spec["wind"][0], "REAL32")
        _set(m, "SIM_WIND_DIR", spec["wind"][1], "REAL32")
        for name in READBACK:
            m.mav.param_request_read_send(m.target_system, m.target_component,
                                          name.encode(), -1)

        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"motor_esc": 1e9,
                                                  "battery": 1e9,
                                                  "vibration": 2.0})
        ctx = {"t0": None}
        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": False, "modes": [],
                 "max_alt": 0.0, "airborne_t": None}
        params, home_seen = {}, None
        roll, pitch, gspd, north, east, thr = [], [], [], [], [], []
        first_closure_t, closures, monitored = None, 0, 0
        t_inject = PREREG["injection_time_s"]
        t_end = PREREG["flight_end_s"]
        deadline = time.time() + (t_end / speedup) * 4 + 90

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            k = msg.get_type()
            if k == "PARAM_VALUE" and msg.param_id in READBACK:
                params[msg.param_id] = round(float(msg.param_value), 4)
            elif k == "GPS_RAW_INT" and home_seen is None and msg.fix_type >= 3:
                home_seen = [round(msg.lat * 1e-7, 6),
                             round(msg.lon * 1e-7, 6), round(msg.alt / 1e3, 1)]
            for sensor, t, ch in map_mavlink(_Shim(msg), ctx):
                for st in layer.ingest(sensor, t, ch):
                    if not (st.armed and st.t >= PREREG["arm_time_s"]):
                        continue
                    monitored += 1
                    gate = st.edges.get("altitude_baro", (None, None))[1]
                    if gate is not None and float(gate) == 0.0:
                        closures += 1
                        if first_closure_t is None:
                            first_closure_t = round(st.t, 3)
            state["t"] = ctx.get("t_last", 0.0)

            # trajectory observables over the cruise window
            if state["t"] >= CRUISE_START_S and state["phase"] == "fly":
                att = m.messages.get("ATTITUDE")
                vfr = m.messages.get("VFR_HUD")
                gpi = m.messages.get("GLOBAL_POSITION_INT")
                if att:
                    roll.append(abs(att.roll))
                    pitch.append(abs(att.pitch))
                if vfr:
                    gspd.append(vfr.groundspeed)
                    thr.append(vfr.throttle)
                if gpi:
                    north.append(gpi.lat * 1e-7)
                    east.append(gpi.lon * 1e-7)

            _pilot(m, state, mavutil)
            if (not state["injected"]) and state["t"] >= t_inject:
                for pname, val, ptype in arm_cfg["params"]:
                    _set(m, pname, val, ptype)
                state["injected"] = True
            if state["t"] >= t_end:
                break

        def st_(xs):
            if not xs:
                return None
            return {"mean": round(statistics.fmean(xs), 5),
                    "sd": round(statistics.pstdev(xs), 5) if len(xs) > 1
                    else 0.0,
                    "max": round(max(xs), 5), "n": len(xs)}

        rec.update({
            "param_readback": params,
            "home_from_first_fix": home_seen,
            "airborne_at_s": state["airborne_t"],
            "max_relative_alt_m": round(state["max_alt"], 2),
            "mode_changes": state["modes"],
            "trajectory": {
                "abs_roll_rad": st_(roll), "abs_pitch_rad": st_(pitch),
                "groundspeed_m_s": st_(gspd), "throttle_pct": st_(thr),
                "lat_span_deg": (round(max(north) - min(north), 7)
                                 if north else None),
                "lon_span_deg": (round(max(east) - min(east), 7)
                                 if east else None),
            },
            "gate": {"monitored_ticks": monitored, "closed_ticks": closures,
                     "first_closure_layer_time_s": first_closure_t},
        })
        return rec
    except Exception as exc:                                      # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def hover_probe(binary, eeprom, wind_spd, wind_dir, speedup, workdir):
    """Does SIM_WIND_SPD reach the PHYSICS, or only the parameter store?

    A parameter readback proves the autopilot stored the value. It does not
    prove the simulator uses it. The square-pattern flights above tilt 0.18 to
    0.22 rad regardless of wind, and the ordering does not track wind speed,
    because manoeuvring tilt swamps wind tilt. This flies the same profile with
    zero commanded ground velocity, where the only reason to tilt is wind.
    """
    from pymavlink import mavutil

    from csia.runtime.plugins import map_mavlink                  # noqa: F401

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup),
         "--home", FLIGHT_SPECS[0]["home"]],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    rec = {"wind_spd_requested": wind_spd, "wind_dir_requested": wind_dir}
    try:
        time.sleep(4.0)
        m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
        m.wait_heartbeat(timeout=60)
        for stream, hz in ((mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
                            10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 10)):
            m.mav.request_data_stream_send(m.target_system, m.target_component,
                                           stream, hz, 1)
        _set(m, "FS_THR_ENABLE", 0.0, "INT32")
        _set(m, "FS_GCS_ENABLE", 0.0, "INT32")
        _set(m, "FS_EKF_THRESH", 10.0, "REAL32")
        _set(m, "SIM_WIND_SPD", wind_spd, "REAL32")
        _set(m, "SIM_WIND_DIR", wind_dir, "REAL32")
        m.mav.param_request_read_send(m.target_system, m.target_component,
                                      b"SIM_WIND_SPD", -1)

        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": True, "modes": [],
                 "max_alt": 0.0, "airborne_t": None}
        readback, roll, pitch, gspd = None, [], [], []
        t_end, hold_from = 100.0, 45.0
        deadline = time.time() + (t_end / speedup) * 4 + 90
        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            if msg.get_type() == "PARAM_VALUE" and \
                    msg.param_id == "SIM_WIND_SPD":
                readback = round(float(msg.param_value), 3)
            elif msg.get_type() == "ATTITUDE":
                t = msg.time_boot_ms / 1e3
                state["t"] = t
                if t >= hold_from and state["phase"] == "fly":
                    roll.append(msg.roll)
                    pitch.append(msg.pitch)
                    v = m.messages.get("VFR_HUD")
                    if v:
                        gspd.append(v.groundspeed)
            _pilot(m, state, mavutil, hold_position=True)
            if state["t"] >= t_end:
                break
        tilt = [math.hypot(r, p) for r, p in zip(roll, pitch)]
        rec.update({
            "wind_spd_readback": readback,
            "airborne_at_s": state["airborne_t"],
            "n_samples": len(tilt),
            "mean_tilt_rad": round(statistics.fmean(tilt), 5) if tilt else None,
            "mean_tilt_deg": round(math.degrees(statistics.fmean(tilt)), 3)
            if tilt else None,
            "mean_roll_rad": round(statistics.fmean(roll), 5) if roll else None,
            "mean_pitch_rad": round(statistics.fmean(pitch), 5)
            if pitch else None,
            "mean_groundspeed_m_s": round(statistics.fmean(gspd), 4)
            if gspd else None,
        })
        return rec
    except Exception as exc:                                      # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def variance_decomposition(within, between):
    """Are the between-spec trajectory differences real conditions or jitter?

    Test B showed the six specs produce different mean tilts, but "different"
    is meaningless without knowing what repeating ONE spec produces. This flies
    a single spec three times and compares the within-spec spread against the
    between-spec spread. If between is not comfortably larger than within, the
    specs are replicates wearing different labels.
    """
    def sd(xs):
        return statistics.pstdev(xs) if len(xs) > 1 else 0.0
    w, b = sd(within), sd(between)
    ratio = (b / w) if w > 1e-12 else None
    return {
        "within_spec_values": [round(x, 5) for x in within],
        "between_spec_values": [round(x, 5) for x in between],
        "within_spec_sd": round(w, 6),
        "between_spec_sd": round(b, 6),
        "between_over_within": round(ratio, 2) if ratio else None,
        "specs_are_distinct_conditions": bool(ratio and ratio >= 3.0),
        "criterion": "between-spec sd at least 3x the within-spec sd",
    }


def spread(rows, path):
    """Distinct values of a nested field across flights, and whether they
    differ at all."""
    vals = []
    for r in rows:
        cur = r
        for key in path:
            cur = (cur or {}).get(key) if isinstance(cur, dict) else None
        vals.append(cur)
    distinct = sorted({v for v in vals if v is not None})
    return {"values": vals, "n_distinct": len(distinct),
            "differs_across_flights": len(distinct) > 1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--eeprom", default=DEFAULT_EEPROM)
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_wd"))
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "variance_investigation.json")
    ready, avail = locate_sitl(args.binary, args.eeprom)
    if not ready:
        json.dump({"status": "SITL_UNAVAILABLE", "availability": avail},
                  open(out_path, "w"), indent=1, sort_keys=True)
        print("status: SITL_UNAVAILABLE")
        print(json.dumps(avail, indent=1))
        return 0

    rows = []
    for arm in ("nominal", "denial"):
        for spec in FLIGHT_SPECS:
            print(f"  {arm:8s} spec {spec['id']} wind "
                  f"{spec['wind'][0]:.0f} m/s ...", flush=True)
            rows.append(fly_instrumented(args.binary, args.eeprom, spec, arm,
                                         ARMS[arm], args.speedup,
                                         args.workdir))
            r = rows[-1]
            if "error" in r:
                print(f"      ERROR {r['error']}")
            else:
                tj = r["trajectory"]
                print(f"      wind_rb={r['param_readback'].get('SIM_WIND_SPD')} "
                      f"home={r['home_from_first_fix']} "
                      f"roll={tj['abs_roll_rad'] and tj['abs_roll_rad']['mean']} "
                      f"gspd={tj['groundspeed_m_s'] and tj['groundspeed_m_s']['mean']} "
                      f"first_close={r['gate']['first_closure_layer_time_s']}")

    nom = [r for r in rows if r["arm"] == "nominal" and "error" not in r]
    den = [r for r in rows if r["arm"] == "denial" and "error" not in r]

    inputs = {
        "wind_speed_readback": spread(nom, ("param_readback",
                                            "SIM_WIND_SPD")),
        "wind_dir_readback": spread(nom, ("param_readback", "SIM_WIND_DIR")),
        "home_latitude_from_first_fix": {
            "values": [r["home_from_first_fix"] and r["home_from_first_fix"][0]
                       for r in nom],
            "n_distinct": len({tuple(r["home_from_first_fix"] or [])
                               for r in nom}),
        },
    }
    outputs = {
        "mean_abs_roll": spread(nom, ("trajectory", "abs_roll_rad", "mean")),
        "mean_abs_pitch": spread(nom, ("trajectory", "abs_pitch_rad", "mean")),
        "mean_groundspeed": spread(nom, ("trajectory", "groundspeed_m_s",
                                         "mean")),
        "mean_throttle": spread(nom, ("trajectory", "throttle_pct", "mean")),
        "lat_span": spread(nom, ("trajectory", "lat_span_deg")),
    }
    gate = {
        "denial_first_closure_time_s": spread(
            den, ("gate", "first_closure_layer_time_s")),
        "denial_closed_ticks": spread(den, ("gate", "closed_ticks")),
        "denial_monitored_ticks": spread(den, ("gate", "monitored_ticks")),
    }

    # --- decisive wind test ---------------------------------------------------
    # The square-pattern tilts above do differ, but they neither track wind
    # speed monotonically nor separate cleanly, so "differs" there is not
    # evidence that wind reached the physics. This isolates it.
    print("\n  hover probe: does wind reach the physics ...", flush=True)
    hover = [hover_probe(args.binary, args.eeprom, w, 90.0, args.speedup,
                         args.workdir) for w in (0.0, 6.0, 12.0)]
    for h in hover:
        print(f"    wind {h['wind_spd_requested']:>4.0f} m/s  "
              f"readback={h.get('wind_spd_readback')}  "
              f"tilt={h.get('mean_tilt_deg')} deg  "
              f"gspd={h.get('mean_groundspeed_m_s')}")
    tilts = [h.get("mean_tilt_deg") for h in hover if h.get("mean_tilt_deg")]
    # A probe that produced no samples is a broken probe, not a null result.
    # The first version of this check read three Nones (a missing import) as
    # "wind is cosmetic", which is a finding it had no evidence for.
    probe_ok = len(tilts) == 3 and all(
        h.get("n_samples", 0) > 50 and "error" not in h for h in hover)
    wind_reaches_physics = (
        probe_ok and tilts[2] > tilts[0] + 1.0 and tilts[2] > tilts[1])
    hover_result = {
        "runs": hover,
        "probe_produced_usable_data": probe_ok,
        "tilt_increases_with_wind": wind_reaches_physics,
        "criterion": ("hold-position tilt at 12 m/s exceeds tilt at 0 m/s by "
                      "more than 1 degree and also exceeds 6 m/s"),
        "why_this_test": (
            "a parameter readback proves only that the autopilot stored the "
            "value. Tilt while holding zero ground velocity has no cause "
            "other than wind, so it separates a stored parameter from a "
            "simulated force."),
    }

    # --- replicate probe: within-spec spread, to calibrate "differs" ---------
    print("\n  replicate probe: fly one spec three times ...", flush=True)
    reps = [fly_instrumented(args.binary, args.eeprom, FLIGHT_SPECS[0],
                             "nominal", ARMS["nominal"], args.speedup,
                             args.workdir) for _ in range(3)]
    within = [r["trajectory"]["abs_roll_rad"]["mean"] for r in reps
              if "error" not in r and r["trajectory"]["abs_roll_rad"]]
    between = [v for v in outputs["mean_abs_roll"]["values"] if v is not None]
    decomp = variance_decomposition(within, between)
    print(f"    within-spec sd  {decomp['within_spec_sd']}")
    print(f"    between-spec sd {decomp['between_spec_sd']}  "
          f"ratio {decomp['between_over_within']}  "
          f"distinct={decomp['specs_are_distinct_conditions']}")

    wind_reached = inputs["wind_speed_readback"]["differs_across_flights"]
    home_reached = inputs["home_latitude_from_first_fix"]["n_distinct"] > 1
    traj_differs = any(v["differs_across_flights"] for v in outputs.values())
    gate_identical = not gate["denial_first_closure_time_s"][
        "differs_across_flights"]

    distinct = decomp["specs_are_distinct_conditions"]
    if wind_reached and home_reached and traj_differs and \
            wind_reaches_physics and distinct:
        verdict = "REAL"
        detail = ("Every varied parameter reached the simulation and changed "
                  "the vehicle's behaviour by more than run-to-run jitter. "
                  "The flights are distinct conditions and the WP-C6 campaign "
                  "is 24 conditions, not one replicated 24 times.")
    elif wind_reached and home_reached and distinct and not \
            wind_reaches_physics:
        verdict = "PARTLY_REAL_WIND_IS_COSMETIC"
        detail = ("MIXED, and the manuscript must say so. Home site reached "
                  "the simulation and produced trajectory differences far "
                  "larger than repeating one spec does, so the flights ARE "
                  "distinct conditions along that axis. Wind did NOT: "
                  "SIM_WIND_SPD is stored and read back correctly, but a "
                  "vehicle holding position at 12 m/s tilts no more than one "
                  "at 0 m/s, so no wind force is applied in this build. "
                  "WP-C6 claimed variation along two axes and had one. The "
                  "campaign is not one condition replicated 24 times, but it "
                  "is less varied than it was described as being.")
    elif not (wind_reached and home_reached):
        verdict = "ARTIFACT"
        detail = ("At least one varied parameter did not reach the "
                  "simulation. The campaign is fewer conditions than claimed "
                  "and its per-flight statistics must be re-derived.")
    elif not probe_ok:
        verdict = "WIND_PROBE_FAILED"
        detail = ("The hover probe did not produce usable data, so whether "
                  "wind reaches the physics is UNDETERMINED. This is not a "
                  "null result and must not be read as one. Inputs reached "
                  "the autopilot and the trajectory differed, but the wind "
                  "axis specifically is unverified.")
    elif not wind_reaches_physics:
        verdict = "WIND_IS_COSMETIC"
        detail = ("The autopilot stored SIM_WIND_SPD but holding position at "
                  "12 m/s produced no more tilt than at 0 m/s, so wind did "
                  "not reach the physics. Only home site actually varied "
                  "across the campaign, which is a weaker claim to "
                  "replication than WP-C6 made and the manuscript must say "
                  "so.")
    else:
        verdict = "INPUTS_REACHED_BUT_NO_EFFECT"
        detail = ("The parameters were accepted by the autopilot but changed "
                  "nothing measurable in the trajectory. Treat the flights as "
                  "replicates until an observable that responds is found.")

    report = {
        "question": "did wind and home site reach the simulation, and is the "
                    "zero between-flight variance real or an artifact",
        "why_it_blocks": ("If the parameters never reached the simulator the "
                          "WP-C6 campaign is one condition replicated 24 "
                          "times and every interval derived from it is wrong."),
        "verdict": verdict,
        "verdict_detail": detail,
        "test_a_inputs_reached_the_sim": inputs,
        "test_b_outputs_differed": outputs,
        "test_c_wind_reaches_the_physics": hover_result,
        "test_d_within_versus_between_spec_spread": decomp,
        "gate_response": gate,
        "gate_statistic_is_identical_across_distinct_flights": gate_identical,
        "what_gate_identity_means": (
            "The injection is scripted to a fixed layer time and the "
            "simulated receiver responds to it with a fixed latency, so the "
            "gate trace is the same function of time in every flight "
            "regardless of where the vehicle is or what the wind is doing. "
            "That is a real property of a deterministic injection against a "
            "deterministic receiver model, and it means the bootstrap over "
            "flights has nothing to resample. It is not evidence that the "
            "flights are identical."
            if gate_identical else
            "The gate response differs across flights, so the WP-C6 zero "
            "variance does not reproduce here and needs explaining."),
        "per_flight": rows,
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"\n=== TEST A: inputs reached the simulation ===")
    for k, v in inputs.items():
        print(f"  {k:32s} distinct={v['n_distinct']:2d}  {v.get('values')}")
    print(f"\n=== TEST B: outputs differed ===")
    for k, v in outputs.items():
        print(f"  {k:22s} distinct={v['n_distinct']:2d} differs="
              f"{v['differs_across_flights']}  {v['values']}")
    print(f"\n=== GATE RESPONSE (denial arm) ===")
    for k, v in gate.items():
        print(f"  {k:32s} distinct={v['n_distinct']:2d}  {v['values']}")
    print(f"\nVERDICT: {verdict}\n{detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
