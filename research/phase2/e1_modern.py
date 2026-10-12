"""Phase-II E1 — the precommitted slow-slew grid, on modern ArduCopter 4.8.

PRECOMMITTED AND UNCHANGED (research/phase2/CANDIDATE_REGISTRY.yaml, E1):

    amplitudes  55.7 m, 556.6 m        both above the project's own 48 m
                                       significance threshold
    slews       20, 60, 120, 240 s     20 s reproduces the Phase-I edge cell;
                                       the rest extend where Phase-I stopped

Eight cells. The grid is not widened, narrowed or re-weighted after seeing
results, and the F3 decision below was written before the first flight.

    every significant cell caught by the autopilot, no joint miss
        -> F3 = REFUTED_AS_TESTED_SAFETY_RELEVANT_PHENOMENON
    at least one VALIDATED significant cell missed by both
        -> F3 = SURVIVES_BOUNDED

A nominal arm runs at each slew, matching the fault windows, to price the R10
budget (zero failsafe transitions on clean flight) on the same build and to
give the airframe-excursion measurement a matched control.

NO TRIAL CONTRIBUTES TO A METRIC UNLESS TRIAL_VALID IS TRUE. See modern_rig.py
for why that contract exists: the Phase-I parameter names are silent no-ops on
this build.

RUN 2. Run 1 of this grid is preserved unaltered at
`results/e1_modern_run1_defective_instrument.json`. Its displacement estimator
contained the airframe's own motion and read 38.89 m on a zero-injection
nominal arm, which invalidated three cells whose injections were in fact
correct to within 2.2%. The grid, the tolerances and the F3 decision rule are
UNCHANGED; only the estimator is corrected, and all eight cells are re-flown so
that no cell is judged by a different instrument than another. See
`V6_INSTRUMENT_DEFECT.md`.

Run:  PYTHONPATH=. python research/phase2/e1_modern.py
Out:  research/phase2/results/e1_modern.json
"""

import argparse
import subprocess
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.phase2.modern_rig import (                        # noqa: E402
    AP_BIN, DEG_TO_M, EKF_THRESH, NAV_CAUTION, PHYS_FLOOR, P_GLITCH_X,
    Shim, connect, instrument_control, launch, new_state, pilot, read_param,
    sep_m, set_param, validity)

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

AMPLITUDES_M = (55.7, 556.6)
SLEWS_S = (20, 60, 120, 240)
INJECT_S = 60.0
POST_S = 30.0
SIG_THRESHOLD_M = 48.0     # csia/scenarios.py gps_spoof reference displacement


def fly(label, amp_m, slew_s, speedup, workdir, nominal=False):
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    end_s = INJECT_S + slew_s + POST_S
    rec = {"label": label, "arm": "nominal" if nominal else "ramp",
           "amplitude_m": 0.0 if nominal else amp_m, "slew_s": slew_s,
           "inject_at_s": INJECT_S, "end_s": end_s,
           "requested_rate_m_s": (0.0 if nominal
                                  else round(amp_m / slew_s, 4)),
           "significant": (not nominal) and amp_m >= SIG_THRESHOLD_M,
           "param_used": P_GLITCH_X, "injection_commands_sent": 0}
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
        steps_done = 0
        applied = 0.0

        # observation accumulators
        ekf_pre, ekf_post_max, ekf_first = [], 0.0, None
        phys_min, phys_floor_ticks, phys_first = 1.0, 0, None
        trust_min, evid_min = 1.0, 1.0
        esc_t, alarms, seen_tr = None, [], 0
        gps_esc_t = [None]
        gate_closed, monitored = 0, 0
        raw_ref = fused_ref = truth_ref = None
        raw_err_max = fused_err_max = 0.0
        # the corrected instrument: reported GPS minus simulator truth
        injected_offset_max = 0.0
        injected_offset_pre_max = 0.0
        truth_excursion_max = 0.0
        csia_gps_post, csia_shift_max = 0, 0.0
        csia_gps_ref = None
        fix_types = set()
        sats_pre, sats_post = [], []
        deadline = time.time() + (end_s / speedup) * 4 + 150

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            k = msg.get_type()
            post = st["t"] >= INJECT_S

            if k == "EKF_STATUS_REPORT":
                v = float(getattr(msg, "pos_horiz_variance", 0.0))
                if post:
                    ekf_post_max = max(ekf_post_max, v)
                    if v > EKF_THRESH and ekf_first is None:
                        ekf_first = round(st["t"], 3)
                else:
                    ekf_pre.append(v)
            elif k == "GPS_RAW_INT":
                fix_types.add(int(msg.fix_type))
                s = int(getattr(msg, "satellites_visible", 0))
                (sats_post if post else sats_pre).append(s)
                if msg.fix_type >= 3:
                    p = (msg.lat * 1e-7, msg.lon * 1e-7)
                    sim = m.messages.get("SIMSTATE")
                    tp = ((sim.lat * 1e-7, sim.lng * 1e-7) if sim is not None
                          else None)
                    if not post:
                        raw_ref = p
                        truth_ref = tp or truth_ref
                        if tp:
                            injected_offset_pre_max = max(
                                injected_offset_pre_max, sep_m(p, tp))
                    else:
                        if raw_ref:
                            raw_err_max = max(raw_err_max, sep_m(p, raw_ref))
                        # THE instrument V3/V6 consume. Free of airframe
                        # motion: SIM_GPS.cpp:581 adds the glitch to truth.
                        if tp:
                            injected_offset_max = max(injected_offset_max,
                                                      sep_m(p, tp))
                        if tp and truth_ref:
                            truth_excursion_max = max(
                                truth_excursion_max, sep_m(tp, truth_ref))
            elif k == "GLOBAL_POSITION_INT":
                p = (msg.lat * 1e-7, msg.lon * 1e-7)
                if not post:
                    fused_ref = p
                elif fused_ref:
                    fused_err_max = max(fused_err_max, sep_m(p, fused_ref))

            for sensor, t, ch in map_mavlink(Shim(msg), ctx):
                # V5: what the CSIA ingestion path itself received
                if sensor == "gps" and ch.get("valid"):
                    pos = ch["pos"]
                    if st["t"] < INJECT_S:
                        csia_gps_ref = pos
                    else:
                        csia_gps_post += 1
                        if csia_gps_ref is not None:
                            d = float(((pos[0] - csia_gps_ref[0]) ** 2
                                       + (pos[1] - csia_gps_ref[1]) ** 2)
                                      ** 0.5)
                            csia_shift_max = max(csia_shift_max, d)
                for state in layer.ingest(sensor, t, ch):
                    policy.update(state)
                    for tr in policy.transitions[seen_tr:]:
                        if tr.level.name != "NORMAL":
                            alarms.append({"t": round(tr.t, 2),
                                           "level": tr.level.name,
                                           "reasons": list(tr.reasons)})
                            if tr.t >= INJECT_S:
                                if esc_t is None:
                                    esc_t = round(tr.t, 3)
                                # An escalation that names something other
                                # than GPS is NOT coverage of a GPS fault.
                                # Counting it as such would be wrong
                                # isolation dressed up as detection.
                                if gps_esc_t[0] is None and any(
                                        "gps" in x.lower()
                                        for x in tr.reasons):
                                    gps_esc_t[0] = round(tr.t, 3)
                    seen_tr = len(policy.transitions)
                    if not (state.armed and state.t >= 20.0):
                        continue
                    monitored += 1
                    g = state.edges.get("altitude_baro", (None, None))[1]
                    if g is not None and float(g) == 0.0:
                        gate_closed += 1
                    if state.t < INJECT_S:
                        continue
                    ph = state.components.get("gps", {}).get("phys")
                    if ph is not None:
                        phys_min = min(phys_min, ph)
                        if ph < PHYS_FLOOR:
                            phys_floor_ticks += 1
                            if phys_first is None:
                                phys_first = round(state.t, 3)
                    trust_min = min(trust_min, state.trust["gps"])
                    evid_min = min(evid_min, state.evidence["gps"])

            st["t"] = ctx.get("t_last", 0.0)
            pilot(m, st, mavutil)

            if (not nominal) and st["t"] >= INJECT_S and steps_done < n_steps:
                want = min(n_steps, int(st["t"] - INJECT_S) + 1)
                while steps_done < want:
                    steps_done += 1
                    applied = amp_deg * steps_done / n_steps
                    set_param(m, P_GLITCH_X, applied, "REAL32")
                    rec["injection_commands_sent"] += 1
            if st["t"] >= end_s:
                break

        rec["param_requested"] = round(applied, 9)
        rec["param_readback_after"] = (
            None if nominal else read_param(m, P_GLITCH_X))
        rec.update({
            "airborne_at_s": st["airborne_t"],
            "max_relative_alt_m": round(st["max_alt"], 1),
            "mode_changes": st["modes"],
            "final_layer_time_s": round(st["t"], 2),
            "monitored_ticks": monitored,
            "gate_closed_ticks": gate_closed,
            "gps_fix_types_seen": sorted(fix_types),
            "mean_sats_pre": (round(sum(sats_pre) / len(sats_pre), 2)
                              if sats_pre else None),
            "mean_sats_post": (round(sum(sats_post) / len(sats_post), 2)
                               if sats_post else None),
            # CORRECTED INSTRUMENT. reported GPS minus simulator truth.
            "max_injected_sensor_offset_m": round(injected_offset_max, 2),
            "preinject_sensor_offset_m": round(injected_offset_pre_max, 2),
            # The airframe's OWN motion away from its position at injection.
            # Compared against a matched-window nominal control below; the
            # excess over that control is the physical consequence of the
            # fault, not of the flight pattern.
            "true_vehicle_excursion_m": round(truth_excursion_max, 2),
            # Run 1's estimator, retained so the two are directly comparable.
            # Contains the airframe motion above. NOT consumed by validity.
            "max_reported_position_change_m": round(raw_err_max, 2),
            "max_fused_position_error_m": round(fused_err_max, 2),
            "csia_gps_samples_post": csia_gps_post,
            "csia_max_gps_input_shift_m": round(csia_shift_max, 2),
            "ekf_var_pre": (round(sum(ekf_pre) / len(ekf_pre), 6)
                            if ekf_pre else None),
            "ekf_var_post": round(ekf_post_max, 6),
            "autopilot_detects": ekf_first is not None,
            "autopilot_detect_delay_s": (round(ekf_first - INJECT_S, 3)
                                         if ekf_first else None),
            "csia_min_phys": round(phys_min, 6),
            "csia_phys_floor_ticks": phys_floor_ticks,
            "csia_detects": phys_floor_ticks > 0,
            "csia_detect_delay_s": (round(phys_first - INJECT_S, 3)
                                    if phys_first else None),
            "csia_min_trust": round(trust_min, 6),
            "csia_min_evidence": round(evid_min, 6),
            "csia_escalates": esc_t is not None,
            "csia_escalate_delay_s": (round(esc_t - INJECT_S, 3)
                                      if esc_t else None),
            # Coverage of a GPS fault requires the escalation to NAME gps.
            "csia_escalates_for_gps": gps_esc_t[0] is not None,
            "csia_gps_escalate_delay_s": (
                round(gps_esc_t[0] - INJECT_S, 3) if gps_esc_t[0] else None),
            "wrong_isolation": (esc_t is not None
                                and gps_esc_t[0] is None),
            "alarms": alarms,
            "nav_caution_threshold": NAV_CAUTION,
        })
        if nominal:
            rec["TRIAL_VALID"] = True
            rec["validity_checks"] = {"nominal_arm": "no injection to verify"}
            rec["invalidity_reason"] = None
        else:
            ok, checks, failed = validity(rec, amp_m)
            rec["TRIAL_VALID"] = ok
            rec["validity_checks"] = checks
            rec["invalidity_reason"] = None if ok else \
                "failed: " + ", ".join(failed)
        return rec
    except Exception as exc:                                   # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["TRIAL_VALID"] = False
        rec["invalidity_reason"] = rec["error"]
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:                      # noqa: F821
            proc.kill()


def categorise(r):
    """Four mutually exclusive coverage categories, on ESCALATION."""
    a = r["autopilot_detects"]
    # CSIA counts as covering a GPS fault only if it escalates AND the
    # escalation names GPS. An unrelated alarm is wrong isolation.
    c = r.get("csia_escalates_for_gps", False)
    if a and c:
        return "BOTH"
    if a:
        return "AUTOPILOT_ONLY"
    if c:
        return "CSIA_ONLY"
    return "JOINT_MISS"


def main() -> int:

    ap = argparse.ArgumentParser()
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_wd_e1"))
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "e1_modern.json")
    if not (os.path.isfile(AP_BIN) and os.access(AP_BIN, os.X_OK)):
        json.dump({"status": "MODERN_TARGET_UNAVAILABLE", "binary": AP_BIN},
                  open(out_path, "w"), indent=1)
        print("MODERN_TARGET_UNAVAILABLE")
        return 0

    rows = []
    print("=== E1 grid, ArduCopter 4.8 (precommitted, unchanged) ===")
    for amp in AMPLITUDES_M:
        for slew in SLEWS_S:
            lbl = f"a{amp:g}_s{slew}"
            print(f"  {lbl:14s} rate={amp / slew:6.2f} m/s ...", flush=True)
            r = fly(lbl, amp, slew, args.speedup, args.workdir)
            rows.append(r)
            _echo(r)

    # One nominal arm per slew, so every fault cell has a control flown over
    # an identical window. Also the R10 sample and the instrument control.
    print("\n=== nominal arms (R10 budget + matched excursion control) ===")
    for slew in SLEWS_S:
        r = fly(f"nominal_{slew}", 0.0, slew, args.speedup, args.workdir,
                nominal=True)
        rows.append(r)
        print(f"  nominal_{slew:<5} transitions={len(r.get('alarms', []))} "
              f"instrument={r.get('max_injected_sensor_offset_m')} m "
              f"run1_instrument={r.get('max_reported_position_change_m')} m "
              f"excursion={r.get('true_vehicle_excursion_m')} m")

    # Excess airframe excursion over the matched-window control.
    control = {r["slew_s"]: r.get("true_vehicle_excursion_m", 0.0)
               for r in rows if r["arm"] == "nominal"}
    for r in rows:
        if r["arm"] != "ramp":
            continue
        c = control.get(r["slew_s"])
        r["nominal_control_excursion_m"] = c
        r["excess_true_excursion_m"] = (
            None if c is None
            else round(r.get("true_vehicle_excursion_m", 0.0) - c, 2))

    faults = [r for r in rows if r["arm"] == "ramp"]
    valid = [r for r in faults if r.get("TRIAL_VALID")]
    invalid = [r for r in faults if not r.get("TRIAL_VALID")]
    sig = [r for r in valid if r["significant"]]

    cov = {"BOTH": 0, "AUTOPILOT_ONLY": 0, "CSIA_ONLY": 0, "JOINT_MISS": 0}
    for r in sig:
        cov[categorise(r)] += 1
    n = len(sig)

    nominal_rows = [r for r in rows if r["arm"] == "nominal"]
    nominal_transitions = sum(len(r.get("alarms", [])) for r in nominal_rows)

    joint_miss = [r for r in sig if categorise(r) == "JOINT_MISS"]
    if not sig:
        verdict = "INCONCLUSIVE"
        why = "no validated significant trials"
    elif joint_miss:
        verdict = "SURVIVES_BOUNDED"
        why = (f"{len(joint_miss)} validated significant cell(s) missed by "
               f"both monitors: "
               f"{[r['label'] for r in joint_miss]}")
    else:
        verdict = "REFUTED_AS_TESTED_SAFETY_RELEVANT_PHENOMENON"
        why = ("every validated significant cell was caught by at least one "
               "monitor; no joint miss in the precommitted grid")

    report = {
        "experiment": "E1 — slow-slew extension on modern ArduPilot",
        "precommitted": True,
        "grid": {"amplitudes_m": list(AMPLITUDES_M),
                 "slews_s": list(SLEWS_S),
                 "cells": len(AMPLITUDES_M) * len(SLEWS_S)},
        "target": {"firmware": "ArduCopter V4.8.0-dev", "binary": AP_BIN},
        "significance_threshold_m": SIG_THRESHOLD_M,
        "significance_source": "csia/scenarios.py:27 gps_spoof reference "
                               "displacement (~3.2 m/s x 15 s)",
        "criteria": {
            "autopilot_detects": f"EKF pos_horiz_variance > {EKF_THRESH}",
            "csia_detects": f"gps physics residual < {PHYS_FLOOR}",
            "csia_escalates": "failsafe leaves NORMAL",
            "coverage_is_computed_on": "ESCALATION for CSIA, DETECTION for "
                                       "the autopilot estimator",
        },
        "instrument": {
            "run": 2,
            "displacement_estimator": "sep(GPS_RAW_INT, SIMSTATE) — the "
                                      "reported position minus the "
                                      "simulator's own truth",
            "why_this_is_the_glitch": "libraries/SITL/SIM_GPS.cpp:581 adds "
                                      "the glitch to the true latitude after "
                                      "the receiver delay buffer",
            "run1_estimator": "sep(GPS_RAW_INT(t), GPS_RAW_INT(t_inject)) — "
                              "contains the airframe's own motion",
            "run1_artifact": "results/e1_modern_run1_defective_instrument"
                             ".json",
            "control": instrument_control(nominal_rows),
        },
        "trial_validity": {
            "contract": "V1..V6, see modern_rig.py",
            "valid_trials": len(valid),
            "invalid_trials": len(invalid),
            "invalid_detail": [{"label": r["label"],
                                "reason": r.get("invalidity_reason")}
                               for r in invalid],
            "policy": "invalid trials are excluded from every metric and "
                      "retained in per_trial",
        },
        "F4_coverage_decomposition_significant": {
            "N_total": n, **{f"N_{k.lower()}": v for k, v in cov.items()},
            "R_incremental_csia_only": (round(cov["CSIA_ONLY"] / n, 4)
                                        if n else None),
            "R_autopilot_dependence": (round(cov["AUTOPILOT_ONLY"] / n, 4)
                                       if n else None),
            "R_joint_miss": (round(cov["JOINT_MISS"] / n, 4) if n else None),
            "note": "counts over a small deterministic grid; not probabilities",
        },
        "airframe_consequence": {
            "quantity": "true_vehicle_excursion_m minus the matched-window "
                        "nominal control",
            "why_it_is_reported": (
                "the injected offset is what the receiver reports; the excess "
                "excursion is where the airframe physically went. A ramp the "
                "estimator accepts is flown; a ramp it rejects is not."),
            "per_cell": [
                {"label": r["label"],
                 "slew_s": r["slew_s"],
                 "injected_offset_m": r["max_injected_sensor_offset_m"],
                 "true_excursion_m": r["true_vehicle_excursion_m"],
                 "nominal_control_m": r.get("nominal_control_excursion_m"),
                 "excess_m": r.get("excess_true_excursion_m"),
                 "ekf_var_post": r["ekf_var_post"],
                 "autopilot_detects": r["autopilot_detects"],
                 "csia_escalates_for_gps": r.get("csia_escalates_for_gps"),
                 "coverage": categorise(r)}
                for r in valid],
        },
        "R10_budget": {
            "budget": 0,
            "nominal_flights": len(nominal_rows),
            "failsafe_transitions_observed": nominal_transitions,
            "within_budget": nominal_transitions == 0,
            "per_flight": [{"label": r["label"],
                            "alarms": r.get("alarms", [])}
                           for r in nominal_rows],
            "blocks_candidate_comparison": nominal_transitions > 0,
            "note": "R10 is a hard constraint in CANDIDATE_REGISTRY.yaml. A "
                    "frozen baseline that violates it on this build must be "
                    "understood before any candidate is scored against it. "
                    "See results/r10_modern.json.",
        },
        "F3_VERDICT": verdict,
        "F3_verdict_reason": why,
        "per_trial": rows,
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    ic = report["instrument"]["control"]
    print(f"\n=== INSTRUMENT CONTROL: {ic['status']} "
          f"(corrected reads {ic.get('corrected_instrument_reads_on_nominal_m')}"
          f" m on nominal, run-1 estimator read "
          f"{ic.get('run1_instrument_reads_on_nominal_m')} m) ===")
    print(f"\n=== TRIAL VALIDITY: {len(valid)} valid, {len(invalid)} invalid "
          f"of {len(faults)} ===")
    for r in invalid:
        print(f"  INVALID {r['label']}: {r.get('invalidity_reason')}")
    print("\n=== AIRFRAME CONSEQUENCE (validated cells) ===")
    print(f"  {'cell':14s} {'inject':>8s} {'excurs':>8s} {'ctrl':>7s} "
          f"{'excess':>8s} {'ekfvar':>8s} {'cover':>15s}")
    for c in report["airframe_consequence"]["per_cell"]:
        print(f"  {c['label']:14s} {c['injected_offset_m']:8.1f} "
              f"{c['true_excursion_m']:8.1f} "
              f"{(c['nominal_control_m'] or 0.0):7.1f} "
              f"{(c['excess_m'] or 0.0):8.1f} {c['ekf_var_post']:8.3f} "
              f"{c['coverage']:>15s}")
    print(f"\n=== F4 COVERAGE, {n} validated significant cells ===")
    for k, v in cov.items():
        print(f"  {k:16s} {v}")
    print(f"\nR10 nominal transitions: {nominal_transitions} "
          f"(budget 0, within={nominal_transitions == 0})")
    print(f"\nF3 VERDICT: {verdict}\n  {why}")
    return 0


def _echo(r):
    if "error" in r:
        print(f"      ERROR {r['error']}")
        return
    print(f"      valid={str(r['TRIAL_VALID']):5s} "
          f"inject={r['max_injected_sensor_offset_m']:>7.1f} m "
          f"(run1_est={r['max_reported_position_change_m']:>7.1f}) "
          f"ekf={str(r['autopilot_detects'])[0]} "
          f"csia_det={str(r['csia_detects'])[0]} "
          f"csia_esc={str(r['csia_escalates'])[0]} "
          f"trust={r['csia_min_trust']:.4f} -> {categorise(r)}")
    if not r["TRIAL_VALID"]:
        print(f"      >>> {r.get('invalidity_reason')}")


if __name__ == "__main__":
    raise SystemExit(main())
