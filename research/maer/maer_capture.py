"""Capture one scored MAER scenario: raw MAVLink, once, for all five arms.

WHY CAPTURE-THEN-REPLAY. The preregistration requires the A1-vs-A1G comparison
to be EXACTLY paired: both arms must consume the same underlying scenario data.
Running the simulator once per arm cannot deliver that -- ArduPilot's jamming
model would produce a different trajectory for each run, and the comparison
would confound gate placement with trajectory.

So the simulator runs ONCE per scenario and every MAVLink message is recorded
with its receive time. All five arms then replay that identical recording
offline. `AircraftAdapter.__init__` takes a `clock`, so replay can be driven
from recorded receive times rather than wall clock, which makes the whole
pipeline -- staleness included -- deterministic. Pairing is then provable by
input hash rather than asserted.

Conditions, exactly as frozen (MAER_PREREGISTRATION.md at d34c629):

    M0  CLEAN                       no injection
    M1  ARDUPILOT_JAM               SIM_GPS1_JAM = 1 at onset
    M2  PERSISTENCE RAMP            SIM_GPS1_GLTCH_X ramped to 50 m over 20 s,
                                    flown in ALT_HOLD so the airframe does not
                                    chase the glitch and erase the observable
    M3  ARDUPILOT_TRANSPORT_STARVE  GPS_RAW_INT re-requested at 0.5 Hz on the
                                    consumer link at onset

This records. It scores nothing and runs no arm.

  python research/maer/maer_capture.py --condition M1 --onset 8
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
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "research", "maer", "results", "scored", "raw")
CONDITIONS = ("M0", "M1", "M2", "M3")
POST_ONSET_S = 40.0
NOMINAL_HZ = 5.0
STARVED_HZ = 0.5
RAMP_METRES = 50.0
RAMP_S = 20.0
METRES_PER_DEG_LAT = 111194.92664455873

# Everything the ArduPilot adapter handles, plus GPS_RAW_INT for the sidecar.
RECORD_TYPES = ("HEARTBEAT", "RAW_IMU", "SCALED_IMU", "SCALED_IMU2",
                "SCALED_IMU3", "SCALED_PRESSURE", "GPS_RAW_INT",
                "BATTERY_STATUS", "VIBRATION", "ESC_TELEMETRY_1_TO_4",
                "ESC_STATUS", "EKF_STATUS_REPORT")


def _request(conn, msgid, hz):
    conn.mav.command_long_send(conn.target_system, conn.target_component,
                               511, 0, msgid, int(1e6 / hz), 0, 0, 0, 0, 0)


def capture(condition, onset_s, tag):
    from pymavlink import mavutil

    from csia.simulation.rigs import (LAUNCHERS, connect, fly,
                                      provenance_string)

    workdir = os.path.join(ROOT, "research", "maer", ".capture", tag)
    proc, conn_str = LAUNCHERS["ardupilot"](workdir, 1)
    rows = []
    meta = {"condition": condition, "onset_commanded_s": onset_s, "tag": tag}
    try:
        conn = connect(conn_str, "ardupilot")
        # M2 needs the airframe out of the GNSS position loop or it flies the
        # glitch off and the declared observable never appears.
        ev = fly(conn, "ardupilot")
        meta["rig_flight"] = {"armed": ev.get("armed"),
                              "climbed_m": round(ev.get("climbed_m", 0.0), 2)}
        if condition == "M2":
            mid = conn.mode_mapping().get("ALT_HOLD")
            conn.set_mode(mid)
            seen, deadline = False, time.time() + 15.0
            while time.time() < deadline:
                m = conn.recv_match(type="HEARTBEAT", blocking=True,
                                    timeout=1.0)
                if m is not None and m.custom_mode == mid:
                    seen = True
                    break
            meta["hold_mode_confirmed"] = seen
            if not seen:
                raise SystemExit("ALT_HOLD not confirmed; not a valid M2 trial")

        for mid, hz in ((24, NOMINAL_HZ), (26, 25), (27, 25), (29, 10),
                        (147, 10), (241, 10), (0, 4), (193, 5)):
            _request(conn, mid, hz)
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
                d = {kk: vv for kk, vv in m.to_dict().items()}
                d["_t_recv"] = round(time.time() - t0, 6)
                rows.append(d)

        pump(t0 + onset_s)
        t_inject = round(time.time() - t0, 6)
        readback = None

        if condition == "M1":
            conn.mav.param_set_send(conn.target_system, conn.target_component,
                                    b"SIM_GPS1_JAM", 1.0,
                                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
            readback = {"param": "SIM_GPS1_JAM", "value": 1.0}
        elif condition == "M2":
            readback = {"param": "SIM_GPS1_GLTCH_X",
                        "metres": RAMP_METRES, "ramp_s": RAMP_S}
        elif condition == "M3":
            _request(conn, 24, STARVED_HZ)
            readback = {"stream": "GPS_RAW_INT", "requested_hz": STARVED_HZ}

        if condition == "M2":
            # ramp the offset in, then hold, pumping throughout
            steps, end = 40, time.time() + RAMP_S
            for i in range(1, steps + 1):
                frac = i / steps
                deg = RAMP_METRES * frac / METRES_PER_DEG_LAT
                conn.mav.param_set_send(
                    conn.target_system, conn.target_component,
                    b"SIM_GPS1_GLTCH_X", float(deg),
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
                pump(t0 + onset_s + RAMP_S * frac)
            pump(t0 + onset_s + POST_ONSET_S)
        else:
            pump(t0 + onset_s + POST_ONSET_S)

        meta.update({
            "t_inject_rel_s": t_inject,
            "intervention": readback,
            "simulator": provenance_string("ardupilot"),
            "post_onset_s": POST_ONSET_S,
            "nominal_gps_raw_hz": NOMINAL_HZ,
            "messages": len(rows),
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
    # signature over the receiver stream only, for distinctness checking
    sig_seq = [(r.get("fix_type"), r.get("satellites_visible"), r.get("h_acc"))
               for r in rows if r.get("mavpackettype") == "GPS_RAW_INT"]
    meta["scenario_signature"] = hashlib.sha256(
        repr(sig_seq).encode()).hexdigest()
    payload["meta"] = meta

    # gzip: a scenario is ~17 MB of repetitive JSON and ~1.1 MB compressed.
    # The recording IS the scored input, so it is committed rather than
    # regenerated -- at raw size that would be 300 MB for the campaign.
    os.makedirs(OUT_DIR, exist_ok=True)
    dest = os.path.join(OUT_DIR, f"{tag}.json.gz")
    with gzip.open(dest, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, default=str)
    print(f"    {condition} onset={onset_s}s  {len(rows)} msgs  "
          f"sig={meta['scenario_signature'][:12]}  -> "
          f"{os.path.relpath(dest, ROOT)}")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--onset", type=float, required=True)
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()
    tag = args.tag or f"{args.condition}_onset{int(args.onset):02d}"
    capture(args.condition, args.onset, tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
