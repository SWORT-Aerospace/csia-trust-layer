"""P0.5 — information-contract validation for the `power_thrust` relation.

The relation under audit, csia/runtime/online.py:546-548:

    E["power_thrust"] = self._lam_upd(
        "power_thrust", batt_i - float(esc_i.sum()) - AVIONICS_CURRENT,
        0.5), 1.0

It asserts a CONSERVATION model — pack current equals the sum of ESC currents
plus a fixed avionics draw — at a scale of 0.5 A, with gate 1.0 (always on
when both nodes are fresh). It joins `motor_esc` and `battery`
(csia/trust_graph/graph.py:50).

This script does not fix anything, does not touch a threshold, and does not
suppress the alarm. It establishes what each input actually is.

CONTROLS, per the standing rules.

  RULE A, null control. The instrument here is "the ESC current we logged".
  The null control originally chosen was `rpm`, carried in the SAME MAVLink
  message and decoded by the SAME code path. That control FAILED: rpm is also
  identically zero, so it cannot certify the logging path.

  The control was therefore replaced with one that does discriminate:
  `BATTERY_STATUS.current_battery`, logged by the same loop on the same ticks
  through the same recv_match path, which sweeps 0 -> 41.25 A across 375
  distinct values. The harness is live. What is constant is the content of
  ESC_TELEMETRY_1_TO_4, in BOTH audited fields.

  The failed control is kept in the artifact rather than deleted, and the
  reason rpm is dead turns out to be a finding in its own right: SITL's motor
  rpm is `motors[i].get_command() * SIM_VIB_MOT_MAX * 60`
  (SIM_Frame.cpp:901), a VIBRATION-model quantity whose parameter defaults to
  0.0 (SITL.cpp:512). It is not a motor-speed model that happens to be
  disabled; it is not a motor-speed model.

  RULE B, no attribution without the intermediate. Every intermediate in the
  chain is logged per tick: raw MAVLink field, ingested value, relation
  residual, edge consistency, node evidence, node trust, failsafe level.

INTERVENTIONS.

  1. nominal hover                     baseline
  2. load sweep, +/-2.5 m/s climb      swings motor load, hence pack current
  3. sentinel path                     offline, deterministic: what CSIA does
                                       with current_battery = -1 ("autopilot
                                       does not measure the current")
  4. predicted-vs-observed             CSIA's own motor-current model
                                       evaluated on the REAL rpm, against the
                                       observed pack current. Separates "the
                                       ESC channel is a stub" from "CSIA's
                                       motor model is wrong".

Run:  PYTHONPATH=. python research/phase2/p05_power_thrust_contract.py
Out:  research/phase2/results/power_thrust_contract.json
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, Shim, connect, launch, new_state, read_param)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
EDGE_SCALE_A = 0.5          # online.py:548
FLIGHT_S = 150.0
SWEEP_START_S = 60.0
SWEEP_PERIOD_S = 12.0
SWEEP_VZ = 2.5              # m/s, alternating sign


def piloted(m, st, mavutil, sweep):
    """modern_rig.pilot with an optional vertical load sweep in `fly`."""
    from research.phase2.modern_rig import pilot
    if st["phase"] != "fly" or not sweep or st["t"] < SWEEP_START_S:
        pilot(m, st, mavutil)
        return 0.0
    if st["t"] - st["last_cmd_t"] < 0.2:
        return st.get("vz_cmd", 0.0)
    st["last_cmd_t"] = st["t"]
    half = int((st["t"] - SWEEP_START_S) / (SWEEP_PERIOD_S / 2)) % 2
    vz = -SWEEP_VZ if half == 0 else SWEEP_VZ   # NED: negative is up
    st["vz_cmd"] = vz
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        0b0000111111000111, 0, 0, 0, 0, 0, vz, 0, 0, 0, 0, 0)
    return vz


def fly(label, speedup, workdir, sweep):
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink
    from csia.sensors.truth import (AVIONICS_CURRENT,
                                    HOVER_CURRENT_PER_MOTOR, HOVER_RPM)

    rec = {"label": label, "sweep": sweep, "samples": [], "transitions": []}
    proc = launch(workdir, speedup)
    try:
        time.sleep(6.0)
        m = connect()
        st = new_state()
        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=20.0))
        ctx = {"t0": None}
        seen_tr = 0
        # RAW MAVLink fields, before any CSIA normalisation
        raw = {"batt_current_cA": None, "batt_voltages_mV": None,
               "esc_current_cA": None, "esc_rpm": None,
               "esc_voltage_cV": None, "esc_count": None}
        # CSIA-ingested values, after plugins.map_mavlink
        ing = {"battery_current_A": None, "motor_esc_current_A": None,
               "motor_esc_rpm": None}
        vz_cmd = 0.0
        deadline = time.time() + (FLIGHT_S / speedup) * 4 + 180

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            k = msg.get_type()
            if k == "BATTERY_STATUS":
                raw["batt_current_cA"] = int(msg.current_battery)
                raw["batt_voltages_mV"] = [int(x) for x in msg.voltages[:4]]
            elif k == "ESC_TELEMETRY_1_TO_4":
                raw["esc_current_cA"] = [int(x) for x in msg.current[:4]]
                raw["esc_rpm"] = [int(x) for x in msg.rpm[:4]]
                raw["esc_voltage_cV"] = [int(x) for x in msg.voltage[:4]]
                raw["esc_count"] = [int(x) for x in msg.count[:4]]

            for sensor, t, ch in map_mavlink(Shim(msg), ctx):
                if sensor == "battery":
                    ing["battery_current_A"] = float(ch["current"])
                elif sensor == "motor_esc":
                    ing["motor_esc_current_A"] = [float(x)
                                                  for x in ch["current"]]
                    ing["motor_esc_rpm"] = [float(x) for x in ch["rpm"]]
                for state in layer.ingest(sensor, t, ch):
                    policy.update(state)
                    for tr in policy.transitions[seen_tr:]:
                        rec["transitions"].append(
                            {"t": round(tr.t, 2), "level": tr.level.name,
                             "reasons": list(tr.reasons)})
                    seen_tr = len(policy.transitions)
                    if ing["battery_current_A"] is None \
                            or ing["motor_esc_current_A"] is None:
                        continue
                    bi = ing["battery_current_A"]
                    ei = sum(ing["motor_esc_current_A"])
                    rpm = ing["motor_esc_rpm"]
                    # CSIA's own motor-current model, on the REAL rpm
                    pred = sum(HOVER_CURRENT_PER_MOTOR * (r / HOVER_RPM) ** 3
                               for r in rpm)
                    ec = state.edges.get("power_thrust", (None, None))
                    rec["samples"].append({
                        "t": round(state.t, 3),
                        "armed": bool(state.armed),
                        "vz_cmd": vz_cmd,
                        # --- raw MAVLink, pre-normalisation ---
                        "raw_batt_current_cA": raw["batt_current_cA"],
                        "raw_esc_current_cA": list(raw["esc_current_cA"]),
                        "raw_esc_rpm": list(raw["esc_rpm"]),
                        "raw_esc_voltage_cV": list(raw["esc_voltage_cV"]),
                        # --- CSIA ingested ---
                        "ing_batt_current_A": round(bi, 4),
                        "ing_esc_current_sum_A": round(ei, 4),
                        "ing_esc_rpm_mean": round(sum(rpm) / 4.0, 1),
                        # --- relation ---
                        "residual_A": round(bi - ei - AVIONICS_CURRENT, 4),
                        "residual_sigma": round(
                            (bi - ei - AVIONICS_CURRENT) / EDGE_SCALE_A, 2),
                        # --- CSIA's motor model on real rpm ---
                        "model_predicted_motor_current_A": round(pred, 3),
                        # --- downstream ---
                        "edge_power_thrust": ec[0],
                        "edge_power_thrust_gate": ec[1],
                        "battery_nbr": state.components["battery"]["nbr"],
                        "battery_phys": state.components["battery"]["phys"],
                        "trust_battery": round(state.trust["battery"], 5),
                        "evidence_battery": round(
                            state.evidence["battery"], 5),
                        "failsafe_level": policy.level.name,
                    })
            st["t"] = ctx.get("t_last", 0.0)
            vz_cmd = piloted(m, st, mavutil, sweep)
            if st["t"] >= FLIGHT_S:
                break

        rec["params"] = {p: read_param(m, p, 4.0) for p in
                         ("BATT_MONITOR", "SIM_BATT_VOLTAGE",
                          "SIM_ESC_TELEM", "SIM_ESC_ARM_RPM")}
        rec["flight_time_s"] = round(st["t"], 2)
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


def spread(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "range": round(max(vals) - min(vals), 4),
            "distinct": len(set(round(v, 6) for v in vals))}


def analyse(rec):
    """RULE A: does a null control move while the audited field does not?"""
    fly_s = [s for s in rec["samples"] if s["armed"] and s["t"] > 30.0]
    if not fly_s:
        return {"error": "no armed samples"}
    pack = spread([s["ing_batt_current_A"] for s in fly_s])
    esc = spread([s["ing_esc_current_sum_A"] for s in fly_s])
    rpm = spread([s["ing_esc_rpm_mean"] for s in fly_s])
    pred = spread([s["model_predicted_motor_current_A"] for s in fly_s])
    res = spread([s["residual_A"] for s in fly_s])
    esc_raw, rpm_raw = set(), set()
    for s in fly_s:
        esc_raw.update(s["raw_esc_current_cA"])
        rpm_raw.update(s["raw_esc_rpm"])

    harness_live = bool(pack and pack["distinct"] > 1)
    esc_constant = bool(esc and esc["distinct"] == 1)
    rpm_constant = bool(rpm and rpm["distinct"] == 1)
    return {
        "window": "armed, t > 30 s",
        "pack_current_A": pack,
        "esc_current_sum_A": esc,
        "esc_rpm_mean": rpm,
        "csia_model_predicted_from_esc_rpm_A": pred,
        "relation_residual_A": res,
        "raw_esc_current_cA_distinct_values": sorted(esc_raw),
        "raw_esc_rpm_distinct_values": sorted(rpm_raw),
        "controls": {
            "intended_null_control": "ESC_TELEMETRY_1_TO_4.rpm, same message",
            "intended_null_control_result": (
                "FAILED — also constant, cannot certify the logging path"
                if rpm_constant else "varies"),
            "substituted_null_control":
                "BATTERY_STATUS.current_battery, same loop, same ticks",
            "substituted_null_control_result": (
                f"LIVE — {pack['distinct']} distinct values spanning "
                f"{pack['range']} A" if harness_live else "DEAD"),
        },
        "null_control_verdict": (
            "HARNESS_LIVE_BOTH_ESC_FIELDS_CONSTANT"
            if harness_live and esc_constant and rpm_constant
            else "HARNESS_LIVE_ESC_CURRENT_CONSTANT"
            if harness_live and esc_constant
            else "HARNESS_LIVE_ESC_FIELDS_VARY"
            if harness_live
            else "HARNESS_DEAD_NOTHING_CONCLUDABLE"),
        "esc_current_tracks_pack_current": (
            None if not (pack and esc)
            else esc["range"] > 0.05 * max(pack["range"], 1e-9)),
        "residual_explained_by_stub": (
            None if not (pack and esc and res) else {
                "pack_mean_minus_stub_minus_avionics": round(
                    (pack["min"] + pack["max"]) / 2 - esc["max"] - 0.6, 2),
                "observed_residual_mid": round(
                    (res["min"] + res["max"]) / 2, 2),
            }),
    }


def reanalyse(path):
    """Recompute the analysis from a stored artifact, no flying."""
    d = json.load(open(path))
    for arm in d["arms"]:
        arm["analysis"] = analyse(arm)
    d["load_sweep_analysis"] = next(
        (a["analysis"] for a in d["arms"] if a["label"] == "load_sweep"), {})
    json.dump(d, open(path, "w"), indent=1, sort_keys=True)
    for arm in d["arms"]:
        a = arm["analysis"]
        print(f"  {arm['label']:16s} {a['null_control_verdict']}")
        print(f"      pack {a['pack_current_A']['min']:.2f}-"
              f"{a['pack_current_A']['max']:.2f} A "
              f"({a['pack_current_A']['distinct']} distinct)   "
              f"esc {a['esc_current_sum_A']['min']:.2f} A "
              f"({a['esc_current_sum_A']['distinct']} distinct)   "
              f"rpm raw {a['raw_esc_rpm_distinct_values']}")
        print(f"      residual {a['relation_residual_A']['min']:.2f} to "
              f"{a['relation_residual_A']['max']:.2f} A; "
              f"stub accounts for "
              f"{a['residual_explained_by_stub']}")
    return 0


def sentinel_probe():
    """Offline, deterministic: what does ingestion do with the -1 sentinel?

    common.xml: BATTERY_STATUS.current_battery is int16 cA with invalid = -1,
    "autopilot does not measure the current".
    """
    from csia.runtime.plugins import map_mavlink

    class FakeBatt:
        def get_type(self):
            return "BATTERY_STATUS"
        voltages = [12600, 65535, 65535, 65535, 65535,
                    65535, 65535, 65535, 65535, 65535]
        current_battery = -1

    out = map_mavlink(FakeBatt(), {"t0": 0.0, "t_last": 1.0})
    got = [c for s, _, c in out if s == "battery"]
    val = got[0]["current"] if got else None
    return {
        "mavlink_sentinel": -1,
        "mavlink_meaning": "autopilot does not measure the current",
        "ingestion_code": "plugins.py:194  max(msg.current_battery, 0)/100.0",
        "ingested_value_A": val,
        "distinguishable_from_genuine_zero": False,
        "consequence": (
            "an autopilot that does not measure pack current is ingested as "
            "0.0 A, and the power_thrust relation then reads it as a pack "
            "drawing nothing while the ESCs draw current. On this SITL build "
            "BATT_MONITOR=4 so current IS measured and this path is NOT the "
            "active cause, but it is a latent interface defect: a missing "
            "value is silently converted into a physically meaningful one."),
        "also_applies_to": (
            "ESC_TELEMETRY_1_TO_4 has no invalid sentinel at all. "
            "AP_ESC_Telem.cpp zero-initialises the struct, so an ESC with no "
            "telemetry is indistinguishable from an ESC drawing 0 A."),
    }


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "power_thrust_contract.json")
    if "--reanalyse" in sys.argv:
        return reanalyse(out)
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    arms = []
    for label, sweep in (("nominal_hover", False), ("load_sweep", True)):
        print(f"  {label:16s} ...", flush=True)
        r = fly(label, 20, os.path.join(RESULTS, "_wd_p05"), sweep)
        r["analysis"] = analyse(r)
        arms.append(r)
        a = r["analysis"]
        if "error" in a:
            print(f"      ERROR {a['error']} {r.get('error','')}")
            continue
        print(f"      pack {a['pack_current_A']['min']:6.2f}-"
              f"{a['pack_current_A']['max']:6.2f} A "
              f"(range {a['pack_current_A']['range']:5.2f}, "
              f"{a['pack_current_A']['distinct']} distinct)")
        print(f"      esc  {a['esc_current_sum_A']['min']:6.2f}-"
              f"{a['esc_current_sum_A']['max']:6.2f} A "
              f"(range {a['esc_current_sum_A']['range']:5.2f}, "
              f"{a['esc_current_sum_A']['distinct']} distinct)")
        print(f"      rpm  {a['esc_rpm_mean_null_control']['min']:6.0f}-"
              f"{a['esc_rpm_mean_null_control']['max']:6.0f} "
              f"({a['esc_rpm_mean_null_control']['distinct']} distinct)"
              f"   <- null control")
        print(f"      raw esc current cA distinct: "
              f"{a['raw_esc_current_cA_distinct_values']}")
        print(f"      NULL CONTROL VERDICT: {a['null_control_verdict']}")

    sweep_a = next((r["analysis"] for r in arms
                    if r["label"] == "load_sweep"), {})
    report = {
        "work_package": "P0.5 modern information contract validation",
        "relation_under_audit": {
            "name": "power_thrust",
            "source": "csia/runtime/online.py:546-548",
            "expression": "batt_i - sum(esc_i) - AVIONICS_CURRENT",
            "scale_A": EDGE_SCALE_A,
            "gate": 1.0,
            "joins": ["motor_esc", "battery"],
            "graph_source": "csia/trust_graph/graph.py:50",
            "model_class": "CONSERVATION (equality of a sum, not "
                           "proportionality)",
            "airframe_independent": True,
            "why_that_matters": "unlike accel_motor_current and "
                                "phys_motor_esc, this relation contains no "
                                "airframe constant, so it is testable "
                                "without the vehicle matching CSIA's 2.0 kg "
                                "reference quad",
        },
        "sentinel_probe": sentinel_probe(),
        "arms": arms,
        "load_sweep_analysis": sweep_a,
    }
    json.dump(report, open(out, "w"), indent=1, sort_keys=True)
    print(f"\nwrote {os.path.relpath(out, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
