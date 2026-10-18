"""Phase-II — why the frozen baseline violates R10 on modern ArduPilot.

R10 (docs/REQUIREMENTS.md): "Clean nominal flight shall produce zero failsafe
transitions." It is the false-alert budget, and CANDIDATE_REGISTRY.yaml makes
it a HARD constraint: a candidate that breaks it fails outright whatever it
gains.

E1 run 1 found that B1 — the frozen, shipped CSIA v1 at 848f556, unmodified —
breaks it on ArduCopter 4.8. Every flight, including both nominal arms, raises

    failsafe NORMAL -> CRITICAL @ t~46 s: power integrity fault (battery 0.62)

roughly ten seconds after the motors spin up, and recovers about ten seconds
later. The diagnosis reports `nominal p=0.98` while the failsafe is CRITICAL.

This blocks the whole candidate comparison. B2/B3/B4 cannot be scored against
a hard constraint the baseline itself fails, so the mechanism has to be
established first. That is all this script does. NO PRODUCTION CODE IS
CHANGED and nothing here is a proposed repair.

THE ANSWER, so the reader is not led down the path this script first took.

The alarm is raised by the **power_thrust edge**, not by any component of the
battery node. That edge (online.py:546) asserts a current balance:

    batt_i - sum(esc_i) - AVIONICS_CURRENT  ~  0     at a scale of 0.5 A

On this build the pack reports drawing **29.33 A** while the four ESCs report
a combined **3.20 A**. The residual is 25.15 A, or **50 sigma**. The edge
consistency collapses to 3.5e-07, drags `battery`'s neighbour evidence to
0.171, and the failsafe's `power_critical = 0.70` threshold does the rest.

FIRST ATTRIBUTION, AND WHY IT WAS WRONG. This script initially blamed the
phys_battery voltage residual: the plant's pack resistance regresses to
0.0100 ohm against the compiled-in 0.0120, which at 29 A gives 0.058 V against
a 0.06 V scale — arithmetic that fits the alarm suspiciously well. The flight
data refuted it. `components['battery']['phys']` reads 1.000 for the whole
flight, because in field mode `_lam_upd` normalises the chi-square by this
airframe's own running level and anything below 1.0 maps to consistency
exactly 1.0. That residual never reaches the trust recursion. It is still
reported below as a secondary finding — it is a real model mismatch sitting
just under its threshold — but it is not the cause. Every component is now
logged individually rather than inferred.

WHAT IS MEASURED

1. Which component or edge actually collapses, logged per tick: all four
   battery components, both motor_esc components, and both power edges.
2. The current balance the power_thrust edge consumes, from both sources.
3. The plant's pack internal resistance, regressed from the simulated
   battery's own voltage and current, against csia/sensors/truth.py's
   PACK_R_INTERNAL. Secondary.

WHY THIS WAS INVISIBLE IN PHASE I. Two independent structural reasons:

  - ArduCopter 3.3 emits neither BATTERY_STATUS nor ESC_TELEMETRY_1_TO_4, and
    csia/runtime/plugins.py sources `battery` and `motor_esc` from exactly
    those two messages. Neither channel was ever fresh, so online.py:613 gated
    both to zero availability and the power_thrust edge never evaluated. Both
    nodes were dead for the entire Phase-I campaign. (They cast no phantom
    healthy vote; the freshness gate handles that correctly. They simply never
    voted.)
  - The bench simulator generates BOTH sides of this balance from
    csia/sensors/truth.py:137-140, where pack current is defined as the sum of
    the per-motor currents plus AVIONICS_CURRENT. The edge is satisfied by
    construction. No bench test could have found this.

R10 has therefore only ever been verified where the plant is the monitor's own
model, or where the channels were absent. This is the first time the
requirement has met an independent plant.

WHETHER THIS IS A SIM ARTIFACT IS OPEN. Real ESC telemetry current is often a
coarse per-ESC estimate that does not sum to measured pack current, so the
assumption may fail on hardware too. That is recorded as an open question, not
resolved here.

Run:  PYTHONPATH=. python research/phase2/r10_modern.py
Out:  research/phase2/results/r10_modern.json
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, Shim, connect, launch, new_state, pilot, read_param)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
FLIGHT_S = 120.0
RESIDUAL_SCALE_V = 0.06        # online.py:577, the phys_battery lambda scale


def fly_nominal(speedup, workdir):
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    rec = {"samples": [], "alarms": [], "transitions": []}
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
        last_b = {"v": None, "i": None}
        deadline = time.time() + (FLIGHT_S / speedup) * 4 + 150

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            if msg.get_type() == "BATTERY_STATUS":
                v = [x for x in msg.voltages if 0 < x < 65535]
                last_b = {"v": (sum(v) / 1000.0) if v else None,
                          "i": msg.current_battery / 100.0}
            elif msg.get_type() == "ESC_TELEMETRY_1_TO_4":
                rec["esc"] = {
                    "rpm": list(msg.rpm)[:4],
                    "current_ca": list(getattr(msg, "current", [0] * 4))[:4],
                    "voltage_cv": list(getattr(msg, "voltage", [0] * 4))[:4],
                }

            for sensor, t, ch in map_mavlink(Shim(msg), ctx):
                for state in layer.ingest(sensor, t, ch):
                    policy.update(state)
                    for tr in policy.transitions[seen_tr:]:
                        rec["transitions"].append(
                            {"t": round(tr.t, 2), "level": tr.level.name,
                             "reasons": list(tr.reasons)})
                        if tr.level.name != "NORMAL":
                            rec["alarms"].append(rec["transitions"][-1])
                    seen_tr = len(policy.transitions)
                    if last_b["v"] is not None:
                        esc = rec.get("esc", {})
                        esc_a = sum(esc.get("current_ca", [])) / 100.0
                        cb = state.components.get("battery", {})
                        cm = state.components.get("motor_esc", {})
                        rec["samples"].append({
                            "t": round(state.t, 3),
                            "batt_v": round(last_b["v"], 4),
                            "batt_i": round(last_b["i"], 3),
                            "esc_current_sum_a": round(esc_a, 3),
                            "esc_rpm_mean": (
                                round(sum(esc.get("rpm", [0])) / 4.0, 1)
                                if esc.get("rpm") else None),
                            # every component of the battery node, not just
                            # phys: the first attribution attempt assumed the
                            # phys residual and was wrong.
                            "battery_nbr": cb.get("nbr"),
                            "battery_phys": cb.get("phys"),
                            "battery_temp": cb.get("temp"),
                            "battery_stat": cb.get("stat"),
                            "motor_esc_nbr": cm.get("nbr"),
                            "motor_esc_phys": cm.get("phys"),
                            "edge_power_thrust": state.edges.get(
                                "power_thrust", (None, None))[0],
                            "edge_power_thrust_gate": state.edges.get(
                                "power_thrust", (None, None))[1],
                            "edge_accel_motor_current": state.edges.get(
                                "accel_motor_current", (None, None))[0],
                            "trust_battery": round(state.trust["battery"], 5),
                            "trust_motor_esc": round(
                                state.trust["motor_esc"], 5),
                            "armed": bool(state.armed),
                        })
            st["t"] = ctx.get("t_last", 0.0)
            pilot(m, st, mavutil)
            if st["t"] >= FLIGHT_S:
                break

        for p in ("SIM_BATT_VOLTAGE", "SIM_BATT_RES_OHM", "SIM_BATT_CAP_AH",
                  "BATT_MONITOR"):
            rec.setdefault("sim_params", {})[p] = read_param(m, p, 4.0)
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


def regress_resistance(samples):
    """Least squares fit of v = v0 - i*R over the loaded window.

    Restricted to samples with current actually flowing, so the fit is not
    dominated by the pre-arm zero-current cluster.
    """
    pts = [(s["batt_i"], s["batt_v"]) for s in samples if s["batt_i"] > 5.0]
    if len(pts) < 10:
        return None
    unloaded = [s["batt_v"] for s in samples if s["batt_i"] <= 0.5]
    if not unloaded:
        return None
    v_rest = sum(unloaded) / len(unloaded)
    # single-point-per-sample estimate of R, then its spread
    rs = [(v_rest - v) / i for i, v in pts if i > 0]
    rs.sort()
    n = len(rs)
    return {
        "n_loaded_samples": n,
        "v_unloaded_mean": round(v_rest, 4),
        "i_loaded_mean": round(sum(i for i, _ in pts) / len(pts), 3),
        "v_loaded_mean": round(sum(v for _, v in pts) / len(pts), 4),
        "R_plant_median_ohm": round(rs[n // 2], 6),
        "R_plant_p10_ohm": round(rs[max(0, n // 10)], 6),
        "R_plant_p90_ohm": round(rs[min(n - 1, 9 * n // 10)], 6),
        "method": "R = (v_unloaded_mean - v) / i, per loaded sample; the "
                  "unloaded mean is the pre-arm resting voltage",
        "caveat": "the plant's resting voltage also falls as charge depletes, "
                  "so this over-attributes late sag to resistance and is an "
                  "UPPER bound on R_plant over a long flight",
    }


def main() -> int:
    from csia.sensors.truth import HOVER_CURRENT_PER_MOTOR, PACK_R_INTERNAL

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "r10_modern.json")
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE"}, open(out, "w"))
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    print("  flying one clean nominal arm on ArduCopter 4.8 ...", flush=True)
    rec = fly_nominal(20, os.path.join(RESULTS, "_wd_r10"))
    fit = regress_resistance(rec["samples"])

    def trough_of(key):
        vals = [(s[key], s) for s in rec["samples"] if s.get(key) is not None]
        return min(vals, key=lambda kv: kv[0])[1] if vals else None

    troughs = {k: trough_of(k) for k in
               ("battery_nbr", "battery_phys", "battery_temp", "battery_stat",
                "edge_power_thrust", "edge_accel_motor_current",
                "trust_battery", "trust_motor_esc")}
    trough = min((s["trust_battery"] for s in rec["samples"]), default=None)

    # Current-balance check: the power_thrust edge asserts
    #   batt_i - sum(esc_i) - AVIONICS_CURRENT ~ 0   at scale 0.5 A
    loaded = [s for s in rec["samples"] if s["batt_i"] > 5.0]
    balance = None
    if loaded:
        res = [s["batt_i"] - s["esc_current_sum_a"] - 0.6 for s in loaded]
        res.sort()
        balance = {
            "n": len(res),
            "batt_i_mean_a": round(sum(s["batt_i"] for s in loaded)
                                   / len(loaded), 3),
            "esc_current_sum_mean_a": round(
                sum(s["esc_current_sum_a"] for s in loaded) / len(loaded), 3),
            "avionics_current_a": 0.6,
            "residual_median_a": round(res[len(res) // 2], 3),
            "edge_scale_a": 0.5,
            "residual_in_sigma": round(res[len(res) // 2] / 0.5, 1),
            "esc_telemetry_reports_current": any(
                s["esc_current_sum_a"] > 0.01 for s in loaded),
        }

    report = {
        "question": "why does the frozen baseline B1 break R10 on "
                    "ArduCopter 4.8 when it holds on 3.3 and on the bench?",
        "target": {"firmware": "ArduCopter V4.8.0-dev", "binary": AP_BIN},
        "R10": {
            "requirement": "clean nominal flight shall produce zero failsafe "
                           "transitions",
            "source": "docs/REQUIREMENTS.md R10",
            "budget": 0,
            "observed_transitions_out_of_normal": len(rec["alarms"]),
            "within_budget": len(rec["alarms"]) == 0,
            "transitions": rec["transitions"],
        },
        "channel": {
            "node": "battery",
            "residual": "online.py:575-577  batt_v - (ocv - batt_i*R), "
                        "ocv = EW(alpha=0.01) of (batt_v + batt_i*R)",
            "scale_v": RESIDUAL_SCALE_V,
            "assumed_R_ohm": PACK_R_INTERNAL,
            "assumed_R_source": "csia/sensors/truth.py:23 PACK_R_INTERNAL",
            "hover_current_per_motor_a": HOVER_CURRENT_PER_MOTOR,
        },
        "plant_resistance": fit,
        "current_balance": balance,
        "troughs": troughs,
        "esc_telemetry_sample": rec.get("esc"),
        "trust_battery_trough": trough,
        "sim_params": rec.get("sim_params"),
        "attribution": None,
        "first_attribution_was_wrong": (
            "The first pass of this script attributed the alarm to the "
            "phys_battery voltage residual, on the arithmetic that a 0.002 "
            "ohm pack-resistance mismatch at 29 A produces 0.058 V against a "
            "0.06 V scale. The flight data refuted it: components['battery']"
            "['phys'] reads 1.000 for the entire flight. In field mode "
            "_lam_upd normalises the chi-square by this airframe's own "
            "running level and any value below 1.0 maps to consistency "
            "exactly 1.0, so that residual never reaches the trust "
            "recursion. The resistance mismatch is real and is still "
            "reported below, but it is not what fires the alarm. The "
            "components are now logged individually rather than assumed."),
        "why_phase1_could_not_see_it": [
            "ArduCopter 3.3 emits no BATTERY_STATUS and plugins.py:191 reads "
            "the battery channel from BATTERY_STATUS only, so the channel was "
            "never fresh and online.py:613 gated its availability to zero. "
            "The battery node was structurally dead for the whole Phase-I "
            "campaign. It cast no phantom healthy vote; the freshness gate "
            "handles that correctly. It simply never voted.",
            "The bench simulator generates the battery from "
            "csia/sensors/truth.py:143, `batt_v = v_ocv - batt_i * "
            "PACK_R_INTERNAL` — the same equation and the same constant the "
            "monitor inverts. The residual is identically zero by "
            "construction, so no bench test could have detected this.",
        ],
        "flight": {"time_s": rec.get("flight_time_s"),
                   "samples": len(rec["samples"]),
                   "error": rec.get("error")},
        "series": rec["samples"][::5],
        "no_production_change": True,
    }

    if fit:
        r_plant = fit["R_plant_median_ohm"]
        i_hover = fit["i_loaded_mean"]
        d_r = PACK_R_INTERNAL - r_plant
        tol = RESIDUAL_SCALE_V / i_hover if i_hover else None
        report["voltage_channel_secondary_finding"] = {
            "note": "real, but NOT the cause of the alarm — see "
                    "first_attribution_was_wrong",
            "R_assumed_ohm": PACK_R_INTERNAL,
            "R_plant_ohm": r_plant,
            "delta_R_ohm": round(d_r, 6),
            "hover_current_a": i_hover,
            "voltage_residual_v": round(i_hover * d_r, 4),
            "residual_scale_v": RESIDUAL_SCALE_V,
            "R_tolerance_at_hover_ohm": (round(tol, 6) if tol else None),
            "R_tolerance_as_fraction_of_assumed": (
                round(tol / PACK_R_INTERNAL, 4) if tol else None),
        }
    if balance:
        report["attribution"] = {
            "node": "battery",
            "driver": "the power_thrust EDGE, not any battery node component",
            "edge": "online.py:546  batt_i - sum(esc_i) - AVIONICS_CURRENT, "
                    "scale 0.5 A, gate 1.0, joining motor_esc and battery "
                    "(trust_graph/graph.py:50)",
            "measured": balance,
            "evidence": {
                "battery_phys_trough": (troughs.get("battery_phys") or {}).get(
                    "battery_phys"),
                "battery_nbr_trough": (troughs.get("battery_nbr") or {}).get(
                    "battery_nbr"),
                "edge_power_thrust_trough": (
                    troughs.get("edge_power_thrust") or {}).get(
                        "edge_power_thrust"),
            },
            "why_it_recovers": "in field mode _lam_upd divides the "
                               "chi-square by an adaptive running level with "
                               "tau ~90 s (online.py:433). The edge is "
                               "grossly inconsistent from the instant the "
                               "motors draw current, and the alarm clears "
                               "only because that level rises to absorb it — "
                               "the layer adapts to the mismatch rather than "
                               "resolving it.",
        }

    json.dump(report, open(out, "w"), indent=1, sort_keys=True)

    print(f"\n  R10 transitions on clean flight: "
          f"{len(rec['alarms'])} (budget 0)")
    for t in rec["transitions"]:
        print(f"    {t['t']:7.2f}s -> {t['level']:9s} {t['reasons']}")
    print("\n  troughs:")
    for k, s in troughs.items():
        print(f"    {k:26s} {(s or {}).get(k)}  @ t={(s or {}).get('t')}")
    if balance:
        print(f"\n  CURRENT BALANCE (power_thrust edge input)")
        print(f"    pack current      {balance['batt_i_mean_a']:8.2f} A")
        print(f"    sum(esc currents) {balance['esc_current_sum_mean_a']:8.2f}"
              f" A   (telemetry reports current: "
              f"{balance['esc_telemetry_reports_current']})")
        print(f"    residual          {balance['residual_median_a']:8.2f} A "
              f"= {balance['residual_in_sigma']:.0f} sigma at scale "
              f"{balance['edge_scale_a']} A")
    if fit:
        v = report["voltage_channel_secondary_finding"]
        print(f"\n  secondary: R_assumed {v['R_assumed_ohm']:.4f} ohm vs "
              f"R_plant {v['R_plant_ohm']:.4f} ohm -> "
              f"{v['voltage_residual_v']:+.4f} V at {v['hover_current_a']:.1f}"
              f" A (scale {RESIDUAL_SCALE_V} V). Real, but the field-mode "
              f"normaliser keeps it off the trust recursion.")
    print(f"\n  trust_battery trough {trough}")
    print(f"wrote {os.path.relpath(out, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
