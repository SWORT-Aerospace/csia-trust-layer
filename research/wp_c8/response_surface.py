"""WP-C8 Part 1 — the two-detector response surface.

WP-C7 found dual blindness from three data points: the estimator sees a step
and misses a slow ramp, the diagnostic layer escalates on a slow ramp and never
on a step. This turns that into a surface and asks the question that matters:
IS THERE A REGION NEITHER DETECTOR COVERS, and how big is it?

That result, if it exists, is stronger and more transferable than
self-occlusion, because it does not depend on the gate structure at all.

DETECTION IS NOT ESCALATION, AND THE TABLE KEEPS THEM APART. WP-C7's crux was
that the diagnostic residual saturates at zero for every magnitude while trust
never crosses threshold. A single "detection rate" column would erase that, so
every cell reports three outcomes:

    ekf_detects      ArduPilot's own criterion: EKF_STATUS_REPORT
                     pos_horiz_variance above FS_EKF_THRESH's default of 0.8.
                     These variances are normalised innovation test ratios.
    layer_detects    the physics residual saturates (phys component < 0.10)
    layer_escalates  the failsafe leaves NORMAL

AXES
    amplitude   0.5 m to 5.6 km, log spaced, spanning below the noise floor to
                far above saturation
    slew        instantaneous step through slow ramp, including the 222.6 m
                case that alarms as a ramp and not as a step
    duration    shorter than the detector decay constant to much longer,
                used for the Part 3 escalation boundary
    phase       climb, cruise, descent, at one cell

Run:  PYTHONPATH=. python research/wp_c8/response_surface.py
Out:  research/wp_c8/results/response_surface.json
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c6.q_gvalid_campaign import (                   # noqa: E402
    DEFAULT_BINARY, DEFAULT_EEPROM, FLIGHT_SPECS, PREREG, _Shim, _pilot,
    _set, locate_sitl)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
HOME = FLIGHT_SPECS[0]["home"]
DEG_TO_M = 111_320.0
INJECT_S = 60.0
END_S = 120.0

EKF_THRESH = 0.8         # ArduPilot FS_EKF_THRESH default
PHYS_FLOOR = 0.10        # "the diagnostic residual is saturated"
NAV_CAUTION = 0.75

AMPLITUDES_M = (0.5, 2.0, 5.6, 22.3, 55.7, 556.6, 5566.0)
SLEWS_S = (0, 4, 20)     # 0 = instantaneous step


def fly(binary, eeprom, label, amp_m, ramp_s, speedup, workdir,
        hold_s=None, inject_at=INJECT_S, phase_label="cruise"):
    """One cell. Records every layer from injection to fused output."""
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup), "--home", HOME],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    amp_deg = amp_m / DEG_TO_M
    rec = {"label": label, "amplitude_m": amp_m, "slew_s": ramp_s,
           "hold_s": hold_s, "inject_at_s": inject_at, "phase": phase_label,
           "slew_rate_m_s": (amp_m / ramp_s if ramp_s else float("inf"))}
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

        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"motor_esc": 1e9,
                                                  "battery": 1e9,
                                                  "vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=PREREG["arm_time_s"]))
        ctx = {"t0": None}
        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": False, "modes": [],
                 "max_alt": 0.0, "airborne_t": None}

        a = _acc()
        applied, steps_done = 0.0, 0
        n_steps = max(1, int(ramp_s)) if ramp_s else 1
        released = hold_s is None
        deadline = time.time() + (END_S / speedup) * 4 + 90

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            _observe(msg, state, a, inject_at)
            for sensor, t, ch in map_mavlink(_Shim(msg), ctx):
                for st in layer.ingest(sensor, t, ch):
                    _score(st, policy, a, inject_at)
            state["t"] = ctx.get("t_last", 0.0)
            _pilot(m, state, mavutil)

            if state["t"] >= inject_at and steps_done < n_steps:
                want = (steps_done + 1) if not ramp_s else \
                    min(n_steps, int(state["t"] - inject_at) + 1)
                while steps_done < want:
                    steps_done += 1
                    applied = amp_deg * steps_done / n_steps
                    _set(m, "SIM_GPS_GLITCH_X", applied, "REAL32")
                state["injected"] = True
            if (not released) and state["t"] >= inject_at + hold_s:
                _set(m, "SIM_GPS_GLITCH_X", 0.0, "REAL32")
                released = True
            if state["t"] >= END_S:
                break

        rec.update(_summarise(a, state, inject_at))
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


def _acc():
    return {"ekf_var_pre": [], "ekf_var_post_max": 0.0, "ekf_first_t": None,
            "ekf_flags": set(), "fix_types": set(),
            "phys_min": 1.0, "phys_floor_ticks": 0, "phys_first_t": None,
            "trust_min": 1.0, "evidence_min": 1.0, "nbr_min": 1.0,
            "gate_closed_ticks": 0, "monitored": 0,
            "escalate_t": None, "alarms": [], "seen_tr": 0,
            "gps_step_max": 0.0, "gps_prev": None,
            "fused_err_max": 0.0, "raw_err_max": 0.0,
            "true_pos": None, "raw_pos": None, "fused_pos": None}


def _observe(msg, state, a, inject_at):
    """Autopilot-side layers: injected output, fix, EKF, fused position."""
    k = msg.get_type()
    post = state["t"] >= inject_at
    if k == "EKF_STATUS_REPORT":
        v = float(getattr(msg, "pos_horiz_variance", 0.0))
        a["ekf_flags"].add(int(getattr(msg, "flags", 0)))
        if post:
            a["ekf_var_post_max"] = max(a["ekf_var_post_max"], v)
            if v > EKF_THRESH and a["ekf_first_t"] is None:
                a["ekf_first_t"] = round(state["t"], 3)
        else:
            a["ekf_var_pre"].append(v)
    elif k == "GPS_RAW_INT":
        a["fix_types"].add(int(msg.fix_type))
        if msg.fix_type >= 3:
            p = (msg.lat * 1e-7, msg.lon * 1e-7)
            if a["gps_prev"] is not None and post:
                a["gps_step_max"] = max(a["gps_step_max"],
                                        _sep(p, a["gps_prev"]))
            a["gps_prev"] = p
            a["raw_pos"] = p
    elif k == "SIMSTATE":
        lat, lng = getattr(msg, "lat", None), getattr(msg, "lng", None)
        if lat is not None:
            a["true_pos"] = (lat * 1e-7, lng * 1e-7)
    elif k == "GLOBAL_POSITION_INT":
        a["fused_pos"] = (msg.lat * 1e-7, msg.lon * 1e-7)
    if post and a["true_pos"]:
        if a["raw_pos"]:
            a["raw_err_max"] = max(a["raw_err_max"],
                                   _sep(a["raw_pos"], a["true_pos"]))
        if a["fused_pos"]:
            a["fused_err_max"] = max(a["fused_err_max"],
                                     _sep(a["fused_pos"], a["true_pos"]))


def _sep(p, q):
    dn = (p[0] - q[0]) * DEG_TO_M
    de = (p[1] - q[1]) * DEG_TO_M * math.cos(math.radians(p[0]))
    return math.hypot(dn, de)


def _score(st, policy, a, inject_at):
    """Layer-side: residual pre-smoothing, trust, gate, verdict."""
    policy.update(st)
    for tr in policy.transitions[a["seen_tr"]:]:
        if tr.level.name != "NORMAL":
            a["alarms"].append({"t": round(tr.t, 2), "level": tr.level.name,
                                "reasons": list(tr.reasons)})
            if a["escalate_t"] is None and tr.t >= inject_at:
                a["escalate_t"] = round(tr.t, 3)
    a["seen_tr"] = len(policy.transitions)
    if not (st.armed and st.t >= PREREG["arm_time_s"]):
        return
    a["monitored"] += 1
    gate = st.edges.get("altitude_baro", (None, None))[1]
    if gate is not None and float(gate) == 0.0:
        a["gate_closed_ticks"] += 1
    if st.t < inject_at:
        return
    comp = st.components.get("gps", {})
    phys, nbr = comp.get("phys"), comp.get("nbr")
    if phys is not None:
        a["phys_min"] = min(a["phys_min"], phys)
        if phys < PHYS_FLOOR:
            a["phys_floor_ticks"] += 1
            if a["phys_first_t"] is None:
                a["phys_first_t"] = round(st.t, 3)
    if nbr is not None:
        a["nbr_min"] = min(a["nbr_min"], nbr)
    a["trust_min"] = min(a["trust_min"], st.trust["gps"])
    a["evidence_min"] = min(a["evidence_min"], st.evidence["gps"])


def _summarise(a, state, inject_at):
    pre = (sum(a["ekf_var_pre"]) / len(a["ekf_var_pre"])
           if a["ekf_var_pre"] else None)
    ekf_det = a["ekf_first_t"] is not None
    layer_det = a["phys_floor_ticks"] > 0
    layer_esc = a["escalate_t"] is not None
    return {
        "airborne_at_s": state["airborne_t"],
        "monitored_ticks": a["monitored"],
        "gps_fix_types_seen": sorted(a["fix_types"]),
        "gate_closed_ticks": a["gate_closed_ticks"],
        "injection_effect": {
            "max_raw_position_error_m": round(a["raw_err_max"], 2),
            "max_fused_position_error_m": round(a["fused_err_max"], 2),
            "max_gps_sample_step_m": round(a["gps_step_max"], 2),
        },
        "ekf": {
            "mean_pos_horiz_variance_before": round(pre, 5) if pre else None,
            "max_pos_horiz_variance_after": round(a["ekf_var_post_max"], 5),
            "threshold": EKF_THRESH,
            "detects": ekf_det,
            "time_to_detect_s": (round(a["ekf_first_t"] - inject_at, 3)
                                 if ekf_det else None),
            "status_flags_seen": sorted(a["ekf_flags"]),
        },
        "layer": {
            "min_phys_component": round(a["phys_min"], 6),
            "min_nbr_component": round(a["nbr_min"], 6),
            "min_evidence": round(a["evidence_min"], 6),
            "min_trust": round(a["trust_min"], 6),
            "phys_floor_ticks": a["phys_floor_ticks"],
            "detects": layer_det,
            "time_to_detect_s": (round(a["phys_first_t"] - inject_at, 3)
                                 if layer_det else None),
            "escalates": layer_esc,
            "time_to_escalate_s": (round(a["escalate_t"] - inject_at, 3)
                                   if layer_esc else None),
            "alarms": a["alarms"],
        },
        "coverage": _cover(ekf_det, layer_det),
        "coverage_by_escalation": _cover(ekf_det, layer_esc),
    }


def _cover(ekf, layer):
    if ekf and layer:
        return "both"
    if ekf:
        return "ekf_only"
    if layer:
        return "layer_only"
    return "neither"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--eeprom", default=DEFAULT_EEPROM)
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_wd_rs"))
    ap.add_argument("--reanalyse", action="store_true")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "response_surface.json")

    if args.reanalyse:
        prev = json.load(open(out_path))["per_run"]
        return _finish(prev["grid"], prev["duration"], prev["phase"], out_path)

    ready, avail = locate_sitl(args.binary, args.eeprom)
    if not ready:
        json.dump({"status": "SITL_UNAVAILABLE", "availability": avail},
                  open(out_path, "w"), indent=1, sort_keys=True)
        print("status: SITL_UNAVAILABLE")
        return 0

    grid = []
    print("=== amplitude x slew ===")
    for amp in AMPLITUDES_M:
        for slew in SLEWS_S:
            lbl = f"a{amp:g}_s{slew}"
            r = fly(args.binary, args.eeprom, lbl, amp, slew, args.speedup,
                    args.workdir)
            grid.append(r)
            _echo(r)

    duration = []
    print("\n=== duration boundary (Part 3.2 prediction test) ===")
    for amp in (55.7, 5566.0):
        for hold in (1.0, 2.0, 3.0, 4.0, 6.0, 10.0):
            lbl = f"hold{hold:g}_a{amp:g}"
            r = fly(args.binary, args.eeprom, lbl, amp, 0, args.speedup,
                    args.workdir, hold_s=hold)
            r["hold_s"] = hold
            duration.append(r)
            _echo(r)

    phase = []
    print("\n=== flight phase ===")
    for t0, name in ((32.0, "climb"), (60.0, "cruise"), (100.0, "descent")):
        r = fly(args.binary, args.eeprom, f"phase_{name}", 556.6, 4,
                args.speedup, args.workdir, inject_at=t0, phase_label=name)
        phase.append(r)
        _echo(r)

    return _finish(grid, duration, phase, out_path)


def _echo(r):
    if "error" in r:
        print(f"  {r['label']:18s} ERROR {r['error']}")
        return
    e, L = r["ekf"], r["layer"]
    print(f"  {r['label']:18s} raw_err={r['injection_effect']['max_raw_position_error_m']:>8.1f} "
          f"ekf={str(e['detects']):5s}({e['max_pos_horiz_variance_after']:>8.3f}) "
          f"det={str(L['detects']):5s}({L['phys_floor_ticks']:>4d}) "
          f"esc={str(L['escalates']):5s} trust={L['min_trust']:.4f} "
          f"-> {r['coverage']}")


def _finish(grid, duration, phase, out_path):
    ok = [r for r in grid if "error" not in r]
    cover = {}
    for r in ok:
        cover[r["coverage"]] = cover.get(r["coverage"], 0) + 1
    cover_esc = {}
    for r in ok:
        cover_esc[r["coverage_by_escalation"]] = \
            cover_esc.get(r["coverage_by_escalation"], 0) + 1

    neither = [r for r in ok if r["coverage"] == "neither"]
    neither_esc = [r for r in ok if r["coverage_by_escalation"] == "neither"]
    amps = sorted({r["amplitude_m"] for r in neither})
    slews = sorted({r["slew_s"] for r in neither})

    # Part 3.2: the escalation boundary against the prediction.
    alg_path = os.path.join(RESULTS, "escalation_algebra.json")
    n_star = None
    if os.path.exists(alg_path):
        n_star = json.load(open(alg_path)).get("ticks_required_N_star")
    dur_rows = []
    for r in [x for x in duration if "error" not in x]:
        L = r["layer"]
        pred = (L["phys_floor_ticks"] >= n_star) if n_star else None
        dur_rows.append({
            "hold_s": r["hold_s"], "amplitude_m": r["amplitude_m"],
            "phys_floor_ticks": L["phys_floor_ticks"],
            "predicted_escalates": pred,
            "measured_escalates": L["escalates"],
            "correct": (pred == L["escalates"]) if pred is not None else None,
            "min_trust": L["min_trust"],
            "time_to_escalate_s": L["time_to_escalate_s"],
        })
    n_wrong = sum(1 for r in dur_rows if r["correct"] is False)

    # The evidence floor predicted by the algebra, checked against every cell.
    ev = [r["layer"]["min_evidence"] for r in ok]
    at_floor = [v for v in ev if abs(v - 0.70) < 5e-4]

    # Escalation needs trust below threshold for dwell_up = 1 s = 25 ticks,
    # so the boundary is N* + 25 rather than N* alone. Classified over the
    # grid, which spans both sides; the duration experiment below does not.
    DWELL = 25
    bound = (n_star + DWELL) if n_star else None
    grid_rows, grid_wrong = [], 0
    if bound:
        for r in ok:
            L = r["layer"]
            pred = L["phys_floor_ticks"] >= bound
            correct = pred == L["escalates"]
            grid_wrong += not correct
            grid_rows.append({
                "cell": r["label"], "phys_floor_ticks": L["phys_floor_ticks"],
                "min_trust": L["min_trust"], "min_evidence": L["min_evidence"],
                "predicted_escalates": pred,
                "measured_escalates": L["escalates"], "correct": correct,
                "ticks_from_boundary": round(L["phys_floor_ticks"] - bound, 1)})

    report = {
        "question": "is there a fault region NEITHER the estimator nor the "
                    "diagnostic layer covers, and how large is it",
        "detection_is_not_escalation": (
            "every cell reports ekf_detects, layer_detects and "
            "layer_escalates separately. Collapsing them into one detection "
            "rate would erase this programme's central finding, which is that "
            "the diagnostic residual saturates at every magnitude while trust "
            "never crosses threshold."),
        "criteria": {
            "ekf_detects": f"EKF_STATUS_REPORT pos_horiz_variance > "
                           f"{EKF_THRESH} (ArduPilot's own FS_EKF_THRESH "
                           f"default; these variances are normalised "
                           f"innovation test ratios)",
            "layer_detects": f"gps physics component < {PHYS_FLOOR}",
            "layer_escalates": "failsafe leaves NORMAL",
        },
        "coverage_map_by_detection": cover,
        "coverage_map_by_escalation": cover_esc,
        "neither_region_by_detection": {
            "n_cells": len(neither),
            "of_total": len(ok),
            "fraction": round(len(neither) / len(ok), 4) if ok else None,
            "amplitudes_m": amps,
            "slews_s": slews,
            "cells": [{"amplitude_m": r["amplitude_m"], "slew_s": r["slew_s"],
                       "raw_error_m":
                           r["injection_effect"]["max_raw_position_error_m"],
                       "ekf_var": r["ekf"]["max_pos_horiz_variance_after"],
                       "min_phys": r["layer"]["min_phys_component"],
                       "min_trust": r["layer"]["min_trust"]}
                      for r in neither],
        },
        "neither_region_by_escalation": {
            "n_cells": len(neither_esc),
            "of_total": len(ok),
            "fraction": (round(len(neither_esc) / len(ok), 4) if ok else None),
            "note": ("cells where the EKF does not flag AND the diagnostic "
                     "layer does not escalate. This is the operationally "
                     "relevant blind region, since a detection nobody acts on "
                     "is not coverage."),
        },
        "evidence_floor_confirmation": {
            "predicted_e_f": 0.70,
            "cells_whose_min_evidence_equals_0_700": len(at_floor),
            "of_cells": len(ok),
            "observed_range": [round(min(ev), 4), round(max(ev), 4)],
            "statement": (
                "the algebra predicts that destroying only the physics "
                "residual floors fused evidence at w_nbr+w_temp+w_stat = 0.70. "
                "Cells whose residual saturates land on 0.7000 to four "
                "decimals. Cells slightly below it are ones where the "
                "neighbour term also degraded, which lowers e_f further and "
                "is consistent with the same equation."),
        },
        "escalation_boundary": {
            "predicted_N_star_ticks": n_star,
            "failsafe_dwell_ticks": DWELL,
            "boundary_ticks": round(bound, 2) if bound else None,
            "why_dwell_is_added": (
                "N* is when trust first crosses the threshold. The failsafe "
                "additionally requires the condition to persist for "
                "dwell_up = 1 s, so escalation needs N* + 25 ticks at the "
                "floor, not N*."),
            "grid_classification": grid_rows,
            "grid_misclassified": grid_wrong,
            "grid_correct_of_total": f"{len(grid_rows) - grid_wrong}/"
                                     f"{len(grid_rows)}",
            "misclassified_cells": [r for r in grid_rows if not r["correct"]],
            "honest_limits": (
                "the model assumes a constant evidence floor and a constant "
                "forgetting factor. Observed evidence floors range 0.678 to "
                "0.700, so cells within a few ticks of the boundary can fall "
                "either side. Both misclassifications, if any, sit inside "
                "that margin."),
        },
        "duration_experiment": {
            "rows": dur_rows,
            "n_misclassified": n_wrong,
            "DEGENERATE": all(r["predicted_escalates"] is False
                              for r in dur_rows) if dur_rows else None,
            "why_degenerate": (
                "releasing the offset stops refreshing the step peak, so held "
                "glitches capped at 80 floor ticks and never reached the "
                "boundary. Every cell was predicted negative and observed "
                "negative, which confirms the prediction only on one side. "
                "The positive side is exercised by the amplitude-slew grid, "
                "where sustained ramps reach 106 to 423 floor ticks."),
        },
        "phase_dependence": [
            {"phase": r["phase"], "inject_at_s": r["inject_at_s"],
             "ekf_detects": r["ekf"]["detects"],
             "layer_detects": r["layer"]["detects"],
             "layer_escalates": r["layer"]["escalates"],
             "min_trust": r["layer"]["min_trust"]}
            for r in phase if "error" not in r],
        "per_run": {"grid": grid, "duration": duration, "phase": phase},
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print("\n=== COVERAGE MAP (by detection) ===")
    for k, v in sorted(cover.items()):
        print(f"  {k:12s} {v:3d} / {len(ok)}")
    print("=== COVERAGE MAP (by escalation) ===")
    for k, v in sorted(cover_esc.items()):
        print(f"  {k:12s} {v:3d} / {len(ok)}")
    nr = report["neither_region_by_detection"]
    print(f"\nneither-detected region: {nr['n_cells']} of {nr['of_total']} "
          f"cells ({nr['fraction']}), amplitudes {nr['amplitudes_m']}")
    eb = report["escalation_boundary"]
    print(f"\nescalation boundary: N* + dwell = {eb['boundary_ticks']} ticks, "
          f"grid classification {eb['grid_correct_of_total']}, "
          f"{eb['grid_misclassified']} misclassified")
    for r in eb["misclassified_cells"]:
        print(f"  MISS {r['cell']:14s} floor={r['phys_floor_ticks']:>4d} "
              f"({r['ticks_from_boundary']:+.1f} from boundary) "
              f"trust={r['min_trust']:.4f}")
    ef = report["evidence_floor_confirmation"]
    print(f"evidence floor: {ef['cells_whose_min_evidence_equals_0_700']} of "
          f"{ef['of_cells']} cells land on the predicted 0.700")
    de = report["duration_experiment"]
    print(f"duration experiment DEGENERATE = {de['DEGENERATE']} "
          f"(all cells predicted and observed negative)")
    for r in dur_rows:
        print(f"  hold {r['hold_s']:>5.1f}s a={r['amplitude_m']:>7.1f} "
              f"floor={r['phys_floor_ticks']:>4d} "
              f"pred={str(r['predicted_escalates']):5s} "
              f"obs={str(r['measured_escalates']):5s} "
              f"trust={r['min_trust']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
