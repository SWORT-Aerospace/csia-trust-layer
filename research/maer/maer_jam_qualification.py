"""ArduPilot GPS-jamming qualification for the receiver-health candidate.

NOT a scored MAER trial. This asks one question: under a GNSS fault model that
does NOT stop the receiver, does raw receiver-health metadata stay live while
the navigation solution is invalid, and is it distinguishable from the validity
bit?

WHY THIS FAULT MODEL. `SIM_GPS1_ENABLE = 0` kills the driver, so ArduPilot
re-transmits a frozen snapshot -- present, non-sentinel, and saying nothing.
`SIM_GPS1_JAM = 1` instead drives `GPS::simulate_jamming()`
(libraries/SITL/SIM_GPS.cpp:288), which is structurally different from PX4's:

    d.num_sats = 2 + (get_random16() % 15);
    if (d.num_sats >= 4) {
        if (get_random16() % 2 == 0) d.have_lock = false;
        else                         d.have_lock = true;   // DECOUPLED
    } else d.have_lock = false;
    ...
    d.horizontal_acc = fabsf(rand_float())*300;            // ~3 Hz, continuous

`horizontal_acc` is drawn from a continuous distribution independently of
`have_lock`, and reaches the wire as `h_acc = horizontal_acc * 1000` (mm). So
unlike PX4 -- where every health field is a two-valued constant assigned in the
same if/else branch as `fix_type` -- this is a generated process rather than a
relabelled fault switch.

THE MATERIAL-CHANGE CRITERION IS DECLARED HERE, BEFORE ANY FAULT TRACE IS
EVALUATED, and is derived from clean data only:

    a candidate is MATERIALLY CHANGED at time t if its value lies outside the
    closed interval [min, max] observed over the clean baseline window of the
    SAME run.

Under nominal SITL the clean envelope is degenerate (h_acc is the constant
SIM_GPS1_ACC * 1000 = 300 mm), so this reduces to "any departure from the clean
value". That is a weaker criterion than a percentile envelope and it is the
honest one for a constant baseline; it is stated in advance either way.

Stochasticity: `simulate_jamming()` calls `get_random16()` and `rand_float()`,
which SITL does not expose as an externally settable seed. Runs are therefore
independent realisations, not reproducible replays, and that limitation is
recorded in every artifact.

  python research/maer/maer_jam_qualification.py --runs 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

RAW_DIR = os.path.join(ROOT, "research", "maer", "MAER_ARDUPILOT_JAM_RAW")
CLEAN_S = 20.0
JAM_S = 60.0
SETTLE_S = 3.0
FIELDS = ("time_usec", "fix_type", "satellites_visible", "eph", "epv",
          "h_acc", "v_acc", "vel_acc", "hdg_acc", "lat", "lon", "alt",
          "vel", "cog")


def capture(conn, seconds, phase, rows, t0):
    end = time.time() + seconds
    while time.time() < end:
        msg = conn.recv_match(type="GPS_RAW_INT", blocking=True, timeout=0.5)
        if msg is None:
            continue
        d = msg.to_dict()
        row = {k: d.get(k) for k in FIELDS}
        row["phase"] = phase
        row["t_rel"] = round(time.time() - t0, 4)
        rows.append(row)


def one_run(idx):
    from pymavlink import mavutil

    from csia.simulation.rigs import LAUNCHERS, connect, provenance_string

    workdir = os.path.join(ROOT, "research", "maer", ".jam_probe",
                           f"run{idx}")
    proc, conn_str = LAUNCHERS["ardupilot"](workdir, 1)
    try:
        conn = connect(conn_str, "ardupilot")
        conn.mav.command_long_send(conn.target_system, conn.target_component,
                                   511, 0, 24, int(1e6 / 10), 0, 0, 0, 0, 0)
        time.sleep(SETTLE_S)
        while conn.recv_match(blocking=False) is not None:
            pass

        rows, t0 = [], time.time()
        capture(conn, CLEAN_S, "clean", rows, t0)

        t_inject = round(time.time() - t0, 4)
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                b"SIM_GPS1_JAM", 1.0,
                                mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        capture(conn, JAM_S, "jam", rows, t0)

        return {"run": idx, "t_inject_rel_s": t_inject,
                "simulator": provenance_string("ardupilot"),
                "intervention": {"param": "SIM_GPS1_JAM", "value": 1},
                "seed_control": "NOT AVAILABLE -- SITL does not expose the "
                                "jamming RNG seed; runs are independent "
                                "realisations, not reproducible replays",
                "rows": rows}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    for i in range(1, args.runs + 1):
        print(f"=== JAM qualification run {i}/{args.runs}")
        res = one_run(i)
        dest = os.path.join(RAW_DIR, f"jam_run_{i:02d}.json")
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, sort_keys=True, default=str)
        clean = [r for r in res["rows"] if r["phase"] == "clean"]
        jam = [r for r in res["rows"] if r["phase"] == "jam"]
        invalid = [r for r in jam if (r["fix_type"] or 0) < 3]
        print(f"    clean {len(clean)} msgs, jam {len(jam)} msgs, "
              f"{len(invalid)} at fix_type<3")
        print(f"    -> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
