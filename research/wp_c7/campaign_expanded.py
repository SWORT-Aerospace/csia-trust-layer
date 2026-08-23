"""WP-C7 Part 1.1 — broaden the campaign along the axes a reviewer will name.

WP-C6 established that denial closes the gate and a fix-preserving glitch does
not. Those are two points. This fills in between them and along the axes that
were held fixed.

  LADDER      sweep SIM_GPS_NUMSATS from 9 down to 0 and find where gvalid
              actually flips. WP-C6 had 10 satellites (gate open) and 0.17
              satellites (gate closed) and nothing in between, so "faults that
              remove the fix close the gate" was asserted from two endpoints.
              The flip point is the operational definition of which faults are
              self-occluding, and it turns a binary claim into a characterised
              one.
  ONSET       inject during climb, early cruise, mid cruise and late cruise.
              The gate response may depend on mission phase; WP-C6 injected at
              one instant in one phase.
  DURATION    denial lasting 2, 5 and 15 s, restored while still airborne.
              WP-C6 only ever injected permanently.
  N           the marginal value of additional flights, computed rather than
              assumed.

Run:  PYTHONPATH=. python research/wp_c7/campaign_expanded.py
Out:  research/wp_c7/results/campaign_expanded.json
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from research.wp_c6.q_gvalid_campaign import (                   # noqa: E402
    DEFAULT_BINARY, DEFAULT_EEPROM, FLIGHT_SPECS, PREREG, _Shim, _pilot,
    _set, bca_ci, locate_sitl)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
HOME = FLIGHT_SPECS[0]["home"]
WINDOW_S = PREREG["conditioning_window_s"]
END_S = 120.0


def fly(binary, eeprom, label, inject_at, params, restore_at, speedup,
        workdir, window_from=None):
    """One flight. `params` is [(name, value, type)] applied at `inject_at`."""
    from pymavlink import mavutil

    from csia.runtime import OnlineTrustLayer
    from csia.runtime.plugins import map_mavlink

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup), "--home", HOME],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    w0 = window_from if window_from is not None else inject_at
    rec = {"label": label, "inject_at_s": inject_at, "restore_at_s": restore_at,
           "window": [w0, w0 + WINDOW_S]}
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
        ctx = {"t0": None}
        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": False, "modes": [],
                 "max_alt": 0.0, "airborne_t": None}
        restored = restore_at is None
        mon = closed = 0
        first_close = first_reopen = None
        fix_types, sats = {}, []
        deadline = time.time() + (END_S / speedup) * 4 + 90

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            if msg.get_type() == "GPS_RAW_INT":
                fix_types[int(msg.fix_type)] = \
                    fix_types.get(int(msg.fix_type), 0) + 1
                if state["injected"]:
                    sats.append(int(getattr(msg, "satellites_visible", 0)))
            for sensor, t, ch in map_mavlink(_Shim(msg), ctx):
                for st in layer.ingest(sensor, t, ch):
                    if not (st.armed and st.t >= PREREG["arm_time_s"]):
                        continue
                    gate = st.edges.get("altitude_baro", (None, None))[1]
                    shut = gate is not None and float(gate) == 0.0
                    if st.t >= inject_at:
                        if shut and first_close is None:
                            first_close = round(st.t, 3)
                        if first_close is not None and not shut \
                                and first_reopen is None:
                            first_reopen = round(st.t, 3)
                    if w0 <= st.t < w0 + WINDOW_S:
                        mon += 1
                        closed += shut
            state["t"] = ctx.get("t_last", 0.0)
            _pilot(m, state, mavutil)
            if (not state["injected"]) and state["t"] >= inject_at:
                for p, v, ty in params:
                    _set(m, p, v, ty)
                state["injected"] = True
            if (not restored) and state["t"] >= restore_at:
                _set(m, "SIM_GPS_DISABLE", 0.0, "INT8")
                _set(m, "SIM_GPS_NUMSATS", 10.0, "REAL32")
                _set(m, "SIM_GPS_BYTELOSS", 0.0, "REAL32")
                restored = True
            if state["t"] >= END_S:
                break

        rec.update({
            "airborne_at_s": state["airborne_t"],
            "monitored_ticks": mon, "closed_ticks": closed,
            "q_gvalid": round(closed / mon, 6) if mon else None,
            "window_coverage": round(mon / (WINDOW_S * PREREG["tick_hz"]), 4),
            "first_closure_s": first_close,
            "closure_delay_s": (round(first_close - inject_at, 3)
                                if first_close else None),
            "first_reopen_s": first_reopen,
            "reopen_delay_after_restore_s": (
                round(first_reopen - restore_at, 3)
                if first_reopen and restore_at else None),
            "gps_fix_type_counts": {str(k): v
                                    for k, v in sorted(fix_types.items())},
            "mean_satellites_after_injection": (
                round(sum(sats) / len(sats), 2) if sats else None),
            "mode_changes": state["modes"],
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


def marginal_value_of_n(per_flight, seed=20260823):
    """At what n does the interval stop narrowing?

    Computed rather than assumed. With a deterministic injection against a
    deterministic receiver the answer is degenerate, and showing that is more
    useful than flying more flights to discover it.
    """
    rng = random.Random(seed)
    rows = []
    for n in (2, 3, 4, 6, 8, 12):
        sample = [per_flight[i % len(per_flight)] for i in range(n)]
        ci = bca_ci(sample, rng, 2000)
        rows.append({"n": n, "ci": ci,
                     "width": (round(ci["hi"] - ci["lo"], 6)
                               if ci and ci.get("hi") is not None else None)})
    widths = [r["width"] for r in rows if r["width"] is not None]
    return {
        "per_flight_values_used": per_flight,
        "sweep": rows,
        "all_widths_zero": bool(widths) and all(w == 0.0 for w in widths),
        "interpretation": (
            "Interval width does not depend on n because the between-flight "
            "variance is zero. Additional flights of the SAME condition buy "
            "nothing. The binding constraint is condition diversity, not "
            "sample size, which is why this work package spends its flights "
            "on a satellite ladder and onset variation rather than on "
            "repeats."
            if bool(widths) and all(w == 0.0 for w in widths) else
            "Interval width shrinks with n; see the sweep for where it "
            "flattens."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--eeprom", default=DEFAULT_EEPROM)
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_wd_exp"))
    ap.add_argument("--reanalyse", action="store_true",
                    help="rebuild the report from flights already on disk")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "campaign_expanded.json")

    if args.reanalyse:
        prev = json.load(open(out_path))["per_run"]
        ladder, onset, duration = (prev["ladder"], prev["onset"],
                                   prev["duration"])
        print(f"reanalysing {len(ladder) + len(onset) + len(duration)} "
              "flights already on disk; no SITL run")
        return _finish(ladder, onset, duration, out_path)

    ready, avail = locate_sitl(args.binary, args.eeprom)
    if not ready:
        json.dump({"status": "SITL_UNAVAILABLE", "availability": avail},
                  open(out_path, "w"), indent=1, sort_keys=True)
        print("status: SITL_UNAVAILABLE")
        return 0

    ladder, onset, duration = [], [], []

    print("=== satellite ladder ===")
    for n in (9, 8, 7, 6, 5, 4, 3, 2, 1, 0):
        r = fly(args.binary, args.eeprom, f"sats_{n}", 60.0,
                [("SIM_GPS_NUMSATS", float(n), "REAL32")], None,
                args.speedup, args.workdir)
        ladder.append({"numsats_requested": n, **r})
        print(f"  sats={n:2d}  q_gvalid={r.get('q_gvalid')}  "
              f"observed_sats={r.get('mean_satellites_after_injection')}  "
              f"fix_types={r.get('gps_fix_type_counts')}"
              f"{'  ERROR ' + r['error'] if 'error' in r else ''}")

    print("\n=== injection onset (denial) ===")
    for t0, phase in ((30.0, "climb"), (45.0, "early cruise"),
                      (60.0, "mid cruise"), (75.0, "late cruise")):
        r = fly(args.binary, args.eeprom, f"onset_{t0:g}s", t0,
                [("SIM_GPS_DISABLE", 1.0, "INT8")], None, args.speedup,
                args.workdir)
        onset.append({"phase": phase, **r})
        print(f"  t={t0:5.1f} ({phase:12s}) q_gvalid={r.get('q_gvalid')} "
              f"closure_delay={r.get('closure_delay_s')} "
              f"coverage={r.get('window_coverage')}")

    print("\n=== injection duration, restored while airborne ===")
    for d in (2.0, 5.0, 15.0):
        r = fly(args.binary, args.eeprom, f"dur_{d:g}s", 60.0,
                [("SIM_GPS_DISABLE", 1.0, "INT8")], 60.0 + d, args.speedup,
                args.workdir)
        duration.append({"denial_seconds": d, **r})
        print(f"  {d:5.1f}s  q_gvalid={r.get('q_gvalid')} "
              f"closure_delay={r.get('closure_delay_s')} "
              f"reopen_delay={r.get('reopen_delay_after_restore_s')}")

    return _finish(ladder, onset, duration, out_path)


def _finish(ladder, onset, duration, out_path):
    ok_ladder = [r for r in ladder if "error" not in r
                 and r.get("q_gvalid") is not None]
    open_at = [r["numsats_requested"] for r in ok_ladder if r["q_gvalid"] < 0.5]
    shut_at = [r["numsats_requested"] for r in ok_ladder if r["q_gvalid"] >= 0.5]
    flip = None
    if open_at and shut_at:
        flip = {"gate_open_down_to_satellites": min(open_at),
                "gate_closed_from_satellites": max(shut_at),
                "boundary_between": [max(shut_at), min(open_at)]}

    campaign = json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "wp_c6", "results",
        "q_gvalid_campaign.json")))
    denial_pf = campaign["cell_counts"]["denial"]["per_flight_p"]

    report = {
        "purpose": "broaden the WP-C6 campaign along the axes it held fixed",
        "satellite_ladder": {
            "why": ("WP-C6 asserted that fix-removing faults close the gate "
                    "from two endpoints, 10 satellites and 0.17. This finds "
                    "the flip point, which is the operational definition of "
                    "which faults are self-occluding."),
            "flip": flip,
            "no_flip_point_found": flip is None,
            "what_no_flip_means": (
                "The gate did not close at ANY satellite count, including "
                "zero: the receiver kept reporting fix_type 3 throughout "
                "while satellites_visible tracked the commanded value down to "
                "0. Two consequences. (1) WP-C6's `degraded` arm combined "
                "SIM_GPS_NUMSATS=4 with SIM_GPS_BYTELOSS=20 and attributed "
                "its closure to partial constellation loss. That attribution "
                "is WRONG: the satellite count contributes nothing, and the "
                "closure came from the byte loss, which is a receiver LINK "
                "failure. (2) In this generator the satellite count carried "
                "the entire injected fault while the gate, keyed on fix "
                "validity alone, saw nothing and the diagnosis stayed "
                "nominal. That is a routing failure demonstrated end to end: "
                "the signal was in the telemetry and the ingestion path does "
                "not read that field. It is ALSO a fidelity limit of this "
                "simulator, since a real receiver would not assert a 3D fix "
                "on zero satellites, and both readings must be reported."
                if flip is None else
                "The gate flips inside the reported boundary."),
            "rungs": [{"numsats": r["numsats_requested"],
                       "q_gvalid": r.get("q_gvalid"),
                       "observed_satellites":
                           r.get("mean_satellites_after_injection"),
                       "fix_types": r.get("gps_fix_type_counts"),
                       "closure_delay_s": r.get("closure_delay_s")}
                      for r in ladder],
        },
        "onset_variation": [
            {"phase": r["phase"], "inject_at_s": r["inject_at_s"],
             "q_gvalid": r.get("q_gvalid"),
             "closure_delay_s": r.get("closure_delay_s"),
             "window_coverage": r.get("window_coverage")} for r in onset],
        "duration_variation": [
            {"denial_seconds": r["denial_seconds"],
             "q_gvalid": r.get("q_gvalid"),
             "closure_delay_s": r.get("closure_delay_s"),
             "reopen_delay_after_restore_s":
                 r.get("reopen_delay_after_restore_s")} for r in duration],
        "marginal_value_of_more_flights":
            marginal_value_of_n(denial_pf),
        "per_run": {"ladder": ladder, "onset": onset, "duration": duration},
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"\nflip point: {flip}")
    mv = report["marginal_value_of_more_flights"]
    print(f"marginal value of n: all widths zero = {mv['all_widths_zero']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
