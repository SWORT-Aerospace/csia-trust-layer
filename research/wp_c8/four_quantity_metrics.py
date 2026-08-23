"""WP-C8 Part 2 — every arm re-reported under the four-quantity decomposition.

WHY THE SINGLE T_FH WAS WRONG. It measured an UNSUPPORTED healthy verdict, not
a FALSE one. Without ground truth, a healthy verdict with no applicable
evidence may still be correct by accident, and calling that "false healthy"
overclaims. Controlled injection gives us the ground truth the corpus cannot,
so the quantity splits four ways. Let A_h = 1 mean the test for hypothesis h is
applicable at this tick, and F_h = 1 mean the injection schedule says h is
truly present.

    T_NA    = time{ A_h = 0 }                              inapplicable
    T_UH    = time{ A_h = 0  AND  healthy }                unsupported healthy
    T_FH    = time{ F_h = 1  AND  healthy }                false healthy
    T_SOFH  = time{ F_h = 1  AND  A_h = 0  AND  healthy }  self-occluded
                                                           false healthy

CONSEQUENCES THIS MEASUREMENT MUST SHOW

  * Denial contributes to T_SOFH: the fault itself closed applicability.
  * The glitch contributes to T_FH and NEVER to T_SOFH, because A_gps = 1
    throughout. Its non-alarm is a sensitivity and interface problem, not
    self-occlusion, and the two must not be pooled.
  * An unannotated corpus can estimate T_NA and T_UH only. F_h does not exist
    in it, so T_FH and T_SOFH are permanently unavailable from the 26 logs.
    That is a limit of the data, not of the method.

VERDICT VOCABULARY. ISO/IEC 9646-1 conformance verdicts
PASS / FAIL / INCONCLUSIVE / INAPPLICABLE, mapped at presentation level onto
HEALTHY / FAULT / UNKNOWN / NOT_APPLICABLE. The precedent for "unusable data is
not normal data" is field-level, not verdict-level: ARINC 429 carries a Sign or
Status Matrix whose codes distinguish Failure Warning and No Computed Data from
Normal Operation, and OPC UA carries a StatusCode whose Bad severity means the
value must not be used. No standard term exists for the exposure quantity
itself, so it is reported by description and not named.

Run:  PYTHONPATH=. python research/wp_c8/four_quantity_metrics.py
Out:  research/wp_c8/results/four_quantity_metrics.json
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c6.q_gvalid_campaign import (                   # noqa: E402
    ARMS, DEFAULT_BINARY, DEFAULT_EEPROM, FLIGHT_SPECS, PREREG, _Shim,
    _pilot, _set, locate_sitl)
from research.wp_c7.false_healthy import (                       # noqa: E402
    abstaining_status, attribution_status, deployed_status, support_state)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
TICK_S = 1.0 / PREREG["tick_hz"]
INJECT_S = PREREG["injection_time_s"]
WINDOW_S = 25.0
END_S = PREREG["flight_end_s"]
TARGET = "gps_fault"

VERDICT_MAP = {
    "HEALTHY": "PASS", "FAULT": "FAIL",
    "UNKNOWN": "INCONCLUSIVE", "NOT_APPLICABLE": "INAPPLICABLE",
}

# Arm -> does the injection schedule assert gps_fault is truly present?
ARM_GROUND_TRUTH = {
    "nominal": False, "denial": True, "glitch": True,
    "link_loss": True, "denial_recovered": True,
}
# `degraded` is renamed: WP-C7's satellite ladder showed the satellite count
# contributes nothing and the closure came from byte loss.
ARM_PARAMS = dict(ARMS)
ARM_PARAMS["link_loss"] = ARM_PARAMS.pop("degraded")


def fly(binary, eeprom, spec, arm_name, arm_cfg, speedup, workdir,
        recovery_at=None):
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup),
         "--home", spec["home"]],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    rec = {"arm": arm_name, "spec_id": spec["id"], "recovery_at_s": recovery_at}
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

        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"motor_esc": 1e9,
                                                  "battery": 1e9,
                                                  "vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=PREREG["arm_time_s"]))
        ctx = {"t0": None}
        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": False, "modes": [],
                 "max_alt": 0.0, "airborne_t": None}
        recovered = recovery_at is None

        ch = {c: _counters() for c in ("attribution", "status", "abstaining")}
        acc = {"window": 0, "na": 0, "seen_tr": 0, "alarms": [],
               "f_true": 0}
        deadline = time.time() + (END_S / speedup) * 4 + 90

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            for sensor, t, c in map_mavlink(_Shim(msg), ctx):
                for st in layer.ingest(sensor, t, c):
                    _score(st, policy, acc, ch, arm_name, recovery_at)
            state["t"] = ctx.get("t_last", 0.0)
            _pilot(m, state, mavutil)
            if (not state["injected"]) and state["t"] >= INJECT_S:
                for p, v, ty in arm_cfg["params"]:
                    _set(m, p, v, ty)
                state["injected"] = True
            if (not recovered) and state["t"] >= recovery_at:
                for p, _, ty in arm_cfg["params"]:
                    _set(m, p, 0.0, ty)
                _set(m, "SIM_GPS_NUMSATS", 10.0, "REAL32")
                recovered = True
            if state["t"] >= END_S:
                break

        w = acc["window"]
        rec.update({
            "airborne_at_s": state["airborne_t"],
            "window_ticks": w,
            "window_seconds": round(w * TICK_S, 2),
            "ticks_F_true": acc["f_true"],
            "T_NA_s": round(acc["na"] * TICK_S, 3),
            "T_NA_fraction": round(acc["na"] / w, 4) if w else None,
            "channels": {name: _finalise(c, w) for name, c in ch.items()},
            "alarms": acc["alarms"],
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


def _counters():
    return {"uh": 0, "fh": 0, "sofh": 0, "healthy": 0,
            "verdicts": {}}


def _finalise(c, w):
    return {
        "T_UH_s": round(c["uh"] * TICK_S, 3),
        "T_FH_s": round(c["fh"] * TICK_S, 3),
        "T_SOFH_s": round(c["sofh"] * TICK_S, 3),
        "T_UH_fraction": round(c["uh"] / w, 4) if w else None,
        "T_FH_fraction": round(c["fh"] / w, 4) if w else None,
        "T_SOFH_fraction": round(c["sofh"] / w, 4) if w else None,
        "healthy_ticks": c["healthy"],
        "verdict_histogram": c["verdicts"],
    }


def _score(st, policy, acc, ch, arm_name, recovery_at):
    policy.update(st)
    for tr in policy.transitions[acc["seen_tr"]:]:
        if tr.level.name != "NORMAL":
            acc["alarms"].append({"t": round(tr.t, 2),
                                  "level": tr.level.name,
                                  "reasons": list(tr.reasons)})
    acc["seen_tr"] = len(policy.transitions)
    if not (st.armed and st.t >= PREREG["arm_time_s"]):
        return
    if not (INJECT_S <= st.t < INJECT_S + WINDOW_S):
        return
    acc["window"] += 1

    silenced = support_state(st)
    # A_h = 1 means the test for h is applicable at this tick.
    a_h = not silenced.get(TARGET, False)
    if not a_h:
        acc["na"] += 1
    # F_h = 1 comes from the injection schedule, never from the layer.
    f_h = ARM_GROUND_TRUTH.get(arm_name, False)
    if f_h and recovery_at is not None and st.t >= recovery_at:
        f_h = False
    if f_h:
        acc["f_true"] += 1

    level = policy.level.name
    for name, status in (
            ("attribution", attribution_status(st)),
            ("status", deployed_status(st, level)),
            ("abstaining", abstaining_status(st, level, silenced))):
        c = ch[name]
        v = VERDICT_MAP.get(status, status)
        c["verdicts"][v] = c["verdicts"].get(v, 0) + 1
        healthy = status == "HEALTHY"
        if healthy:
            c["healthy"] += 1
            if not a_h:
                c["uh"] += 1
            if f_h:
                c["fh"] += 1
            if f_h and not a_h:
                c["sofh"] += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--eeprom", default=DEFAULT_EEPROM)
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--flights", type=int, default=3)
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_wd_4q"))
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "four_quantity_metrics.json")
    ready, avail = locate_sitl(args.binary, args.eeprom)
    if not ready:
        json.dump({"status": "SITL_UNAVAILABLE", "availability": avail},
                  open(out_path, "w"), indent=1, sort_keys=True)
        print("status: SITL_UNAVAILABLE")
        return 0

    rows = []
    for arm in ("nominal", "denial", "glitch", "link_loss"):
        for spec in FLIGHT_SPECS[:args.flights]:
            print(f"  {arm:16s} spec {spec['id']} ...", flush=True)
            r = fly(args.binary, args.eeprom, spec, arm, ARM_PARAMS[arm],
                    args.speedup, args.workdir)
            rows.append(r)
            _echo(r)
    for spec in FLIGHT_SPECS[:args.flights]:
        print(f"  denial_recovered spec {spec['id']} ...", flush=True)
        r = fly(args.binary, args.eeprom, spec, "denial_recovered",
                ARM_PARAMS["denial"], args.speedup, args.workdir,
                recovery_at=INJECT_S + 15.0)
        rows.append(r)
        _echo(r)

    by_arm = {}
    for r in rows:
        if "error" not in r and r.get("window_ticks"):
            by_arm.setdefault(r["arm"], []).append(r)

    def mean(rs, path):
        vals = []
        for r in rs:
            cur = r
            for k in path:
                cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is not None:
                vals.append(cur)
        return round(sum(vals) / len(vals), 3) if vals else None

    summary = {}
    for arm, rs in by_arm.items():
        summary[arm] = {
            "flights": len(rs),
            "ground_truth_F": ARM_GROUND_TRUTH.get(arm),
            "T_NA_s": mean(rs, ("T_NA_s",)),
            "channels": {
                name: {q: mean(rs, ("channels", name, q))
                       for q in ("T_UH_s", "T_FH_s", "T_SOFH_s")}
                for name in ("attribution", "status", "abstaining")},
        }

    glitch = summary.get("glitch", {})
    report = {
        "decomposition": {
            "T_NA": "time{ A_h = 0 } inapplicable",
            "T_UH": "time{ A_h = 0 AND healthy } unsupported healthy",
            "T_FH": "time{ F_h = 1 AND healthy } false healthy",
            "T_SOFH": "time{ F_h = 1 AND A_h = 0 AND healthy } "
                      "self-occluded false healthy",
        },
        "why_the_old_single_quantity_was_wrong": (
            "it measured an unsupported healthy verdict, not a false one. "
            "Without ground truth a healthy verdict with no applicable "
            "evidence may be correct by accident."),
        "verdict_vocabulary": {
            "standard": "ISO/IEC 9646-1 conformance verdicts",
            "mapping": VERDICT_MAP,
            "field_level_precedent": (
                "ARINC 429 Sign/Status Matrix distinguishes Failure Warning "
                "and No Computed Data from Normal Operation; OPC UA "
                "StatusCode Bad severity means the value must not be used. "
                "Both establish that unusable data is not normal data."),
            "not_precedent": (
                "LTL3 and conformal prediction were checked and are different "
                "conditions; neither is claimed here."),
            "no_standard_term_for_the_exposure_quantity": True,
        },
        "target_hypothesis": TARGET,
        "window": [INJECT_S, INJECT_S + WINDOW_S],
        "per_arm": summary,
        "the_glitch_row": {
            "T_SOFH_s": (glitch.get("channels", {})
                         .get("attribution", {}).get("T_SOFH_s")),
            "T_NA_s": glitch.get("T_NA_s"),
            "reason": (
                "A_gps_fault = 1 for every tick of the glitch arm: the fix is "
                "retained, gvalid stays open and phys_gps keeps contributing. "
                "The hypothesis is applicable throughout, so no part of the "
                "glitch arm's exposure can be self-occlusion. Its exposure is "
                "T_FH only, and its cause is detector sensitivity and the "
                "escalation interface, which WP-C8 Part 3 characterises "
                "separately."),
        },
        "corpus_limit": (
            "F_h does not exist in unannotated telemetry, so T_FH and T_SOFH "
            "are permanently unavailable from the 26-log corpus. T_NA and "
            "T_UH are estimable from it. This is a limit of the data, not of "
            "the method."),
        "per_flight": rows,
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print("\n=== FOUR QUANTITIES, seconds in a 25 s window ===")
    print(f"{'arm':<18s} {'F':>2s} {'T_NA':>7s} | "
          f"{'UH att':>7s} {'FH att':>7s} {'SOFH att':>9s} | "
          f"{'FH stat':>8s} | {'FH abst':>8s} {'SOFH abst':>10s}")
    for arm, s in summary.items():
        a, st, ab = (s["channels"]["attribution"], s["channels"]["status"],
                     s["channels"]["abstaining"])
        print(f"{arm:<18s} {str(s['ground_truth_F'])[0]:>2s} "
              f"{_f(s['T_NA_s']):>7s} | {_f(a['T_UH_s']):>7s} "
              f"{_f(a['T_FH_s']):>7s} {_f(a['T_SOFH_s']):>9s} | "
              f"{_f(st['T_FH_s']):>8s} | {_f(ab['T_FH_s']):>8s} "
              f"{_f(ab['T_SOFH_s']):>10s}")
    print(f"\nglitch T_SOFH = {report['the_glitch_row']['T_SOFH_s']} s "
          f"(A_h = 1 throughout, so self-occlusion cannot apply)")
    return 0


def _f(v):
    return "-" if v is None else f"{v:.2f}"


def _echo(r):
    if "error" in r:
        print(f"      ERROR {r['error']}")
        return
    a = r["channels"]["attribution"]
    print(f"      T_NA={r['T_NA_s']}s UH={a['T_UH_s']}s FH={a['T_FH_s']}s "
          f"SOFH={a['T_SOFH_s']}s  F_ticks={r['ticks_F_true']}")


if __name__ == "__main__":
    raise SystemExit(main())
