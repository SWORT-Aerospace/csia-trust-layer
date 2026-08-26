"""Capture the three HELD-OUT matched mechanism pairs. Item 4.

These are genuinely new recordings: a fresh ArduPilot SITL boot per trial, on
onsets and durations taken from the frozen plan in cea85f1
(CONFIRMATORY_TRACE_PLAN.json pairs 1-3). None of them existed when S2 was
designed, when the time-alignment or freshness defects were fixed, when
`trust_gps` was selected, or when any threshold or feature rule was chosen.

The two mechanisms, produced at genuinely different places in the stack:

  SENSOR_INVALID        SIM_GPS1_ENABLE = 0 -- the simulated receiver stops
                        producing. The autopilot's GPS driver reports no fix
                        and KEEPS SENDING GPS_RAW_INT with fix_type < 3.
  TRANSPORT_UNAVAILABLE the receiver stays healthy; the MAVLink GPS_RAW_INT
                        stream to the consumer is disabled (message interval
                        set to -1). Nothing arrives.

Same airframe, same adapter, same consumer path. The difference is where the
failure sits, which is the whole point.

WHETHER SENSOR_INVALID IS EVEN PRODUCIBLE is not assumed. Each capture records
the post-onset fix_type histogram and message count, so a run in which the
autopilot went silent instead of reporting no fix is visible rather than
mistaken for transport loss. This is the SITL analogue of HIL criterion 0.

  python research/dual_admissibility_confirmatory/heldout_capture.py
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results", "heldout_raw")
GPS_RAW_INT = 24
NOMINAL_HZ = 5.0
POST_ONSET_PAD_S = 4.0          # tail after the condition ends, for recovery

# Pairs 1-3 of the frozen plan, verbatim.
PAIRS = [
    {"pair": "PAIR_01", "onset_s": 14.0, "duration_s": 6.0},
    {"pair": "PAIR_02", "onset_s": 17.5, "duration_s": 9.0},
    {"pair": "PAIR_03", "onset_s": 21.0, "duration_s": 12.0},
]
MECHANISMS = ("SENSOR_INVALID", "TRANSPORT_UNAVAILABLE")

RECORD_TYPES = ("HEARTBEAT", "RAW_IMU", "SCALED_IMU", "SCALED_IMU2",
                "SCALED_IMU3", "SCALED_PRESSURE", "GPS_RAW_INT",
                "BATTERY_STATUS", "VIBRATION", "ESC_TELEMETRY_1_TO_4",
                "ESC_STATUS", "EKF_STATUS_REPORT")


def _interval(conn, msgid, hz):
    """MAV_CMD_SET_MESSAGE_INTERVAL. hz <= 0 disables the stream."""
    us = -1 if hz is None or hz <= 0 else int(1e6 / hz)
    conn.mav.command_long_send(conn.target_system, conn.target_component,
                               511, 0, msgid, us, 0, 0, 0, 0, 0)


def capture(mechanism, onset_s, duration_s, tag):
    from pymavlink import mavutil

    from csia.simulation.rigs import (LAUNCHERS, connect, fly,
                                      provenance_string)

    workdir = os.path.join(_HERE, ".heldout", tag)
    proc, conn_str = LAUNCHERS["ardupilot"](workdir, 1)
    rows = []
    meta = {"mechanism": mechanism, "onset_commanded_s": onset_s,
            "duration_commanded_s": duration_s, "tag": tag}
    try:
        conn = connect(conn_str, "ardupilot")
        ev = fly(conn, "ardupilot")
        meta["rig_flight"] = {"armed": ev.get("armed"),
                              "climbed_m": round(ev.get("climbed_m", 0.0), 2)}
        for mid, hz in ((GPS_RAW_INT, NOMINAL_HZ), (26, 25), (27, 25),
                        (29, 10), (147, 10), (241, 10), (0, 4), (193, 5)):
            _interval(conn, mid, hz)
        time.sleep(2.0)
        while conn.recv_match(blocking=False) is not None:
            pass

        t0 = time.time()

        def pump(until):
            while time.time() < until:
                m = conn.recv_match(blocking=True, timeout=0.2)
                if m is None:
                    continue
                k = m.get_type()
                if k not in RECORD_TYPES:
                    continue
                d = dict(m.to_dict())
                d["_t_recv"] = round(time.time() - t0, 6)
                rows.append(d)

        pump(t0 + onset_s)
        t_inject = round(time.time() - t0, 6)

        if mechanism == "SENSOR_INVALID":
            conn.mav.param_set_send(conn.target_system, conn.target_component,
                                    b"SIM_GPS1_ENABLE", 0.0,
                                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
            action = {"param": "SIM_GPS1_ENABLE", "value": 0.0}
        else:
            _interval(conn, GPS_RAW_INT, None)      # disable the stream
            action = {"stream": "GPS_RAW_INT", "interval_us": -1}

        pump(t0 + onset_s + duration_s)
        t_release = round(time.time() - t0, 6)

        if mechanism == "SENSOR_INVALID":
            conn.mav.param_set_send(conn.target_system, conn.target_component,
                                    b"SIM_GPS1_ENABLE", 1.0,
                                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        else:
            _interval(conn, GPS_RAW_INT, NOMINAL_HZ)

        pump(t0 + onset_s + duration_s + POST_ONSET_PAD_S)

        gps = [r for r in rows if r.get("mavpackettype") == "GPS_RAW_INT"]
        during = [r for r in gps
                  if t_inject <= float(r["_t_recv"]) < t_release]
        hist = {}
        for r in during:
            f = int(r.get("fix_type", 0) or 0)
            hist[f] = hist.get(f, 0) + 1
        meta.update({
            "t_inject_rel_s": t_inject,
            "t_release_rel_s": t_release,
            "intervention": action,
            "simulator": provenance_string("ardupilot"),
            "messages": len(rows),
            "gps_raw_int_total": len(gps),
            # the criterion-0 evidence, per run
            "gps_raw_int_during_condition": len(during),
            "fix_type_histogram_during_condition":
                {str(k): v for k, v in sorted(hist.items())},
            "all_during_are_invalid": bool(during) and all(
                int(r.get("fix_type", 0) or 0) < 3 for r in during),
        })
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()

    payload = {"meta": meta, "messages": rows}
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    meta["input_sha256"] = hashlib.sha256(blob).hexdigest()
    payload["meta"] = meta

    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f"{tag}.json.gz")
    with gzip.open(dest, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, default=str)
    print(f"    {tag:<34} {len(rows):>6} msgs  GPS during condition="
          f"{meta['gps_raw_int_during_condition']:>4}  "
          f"fix_types={meta['fix_type_histogram_during_condition']}")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default=None,
                    help="capture a single tag, for probing")
    args = ap.parse_args()

    metas = []
    for spec in PAIRS:
        for mech in MECHANISMS:
            tag = f"{spec['pair']}_{mech}"
            if args.only and args.only != tag:
                continue
            metas.append(capture(mech, spec["onset_s"], spec["duration_s"],
                                 tag))
    if metas:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "CAPTURE_INDEX.json"), "a",
                  encoding="utf-8") as fh:
            for m in metas:
                fh.write(json.dumps(m, sort_keys=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
