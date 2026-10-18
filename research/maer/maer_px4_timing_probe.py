"""Per-message PX4 timing capture for the receiver-health lead/lag audit.

The source already settles the question -- SensorGpsSim.cpp assigns fix_type
and every health field inside ONE if/else on `_sim_gps_used >= 4`, so they
change in the same publication cycle by construction and no lead is possible.
This probe exists so the claim rests on a measurement as well as a reading, and
so the required timing artifact is produced from data rather than asserted.

  python research/maer/maer_px4_timing_probe.py
"""

from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

CLEAN_S = 20.0
FAULT_S = 25.0
SETTLE_S = 3.0
FIELDS = ("time_usec", "fix_type", "satellites_visible", "eph", "epv",
          "h_acc", "v_acc", "vel_acc", "lat", "lon", "alt", "vel", "cog")


def main() -> int:
    from pymavlink import mavutil

    from csia.simulation.rigs import LAUNCHERS, connect, provenance_string

    workdir = os.path.join(ROOT, "research", "maer", ".raw_probe", "px4_time")
    proc, conn_str = LAUNCHERS["px4"](workdir, 1)
    try:
        conn = connect(conn_str, "px4")
        conn.mav.command_long_send(conn.target_system, conn.target_component,
                                   511, 0, 24, int(1e6 / 10), 0, 0, 0, 0, 0)
        time.sleep(SETTLE_S)
        while conn.recv_match(blocking=False) is not None:
            pass

        rows, t0 = [], time.time()

        def cap(seconds, phase):
            end = time.time() + seconds
            while time.time() < end:
                m = conn.recv_match(type="GPS_RAW_INT", blocking=True,
                                    timeout=0.5)
                if m is None:
                    continue
                d = m.to_dict()
                r = {k: d.get(k) for k in FIELDS}
                r["phase"] = phase
                r["t_rel"] = round(time.time() - t0, 4)
                rows.append(r)

        cap(CLEAN_S, "clean")
        t_inject = round(time.time() - t0, 4)
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                b"SIM_GPS_USED", 0.0,
                                mavutil.mavlink.MAV_PARAM_TYPE_INT32)
        cap(FAULT_S, "fault")

        out = {"platform": "px4",
               "simulator": provenance_string("px4"),
               "intervention": {"param": "SIM_GPS_USED", "value": 0},
               "t_inject_rel_s": t_inject, "rows": rows}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()

    dest = os.path.join(ROOT, "research", "maer", "px4_timing_rows.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    n_inv = sum(1 for r in rows if (r["fix_type"] or 0) < 3)
    print(f"  {len(rows)} msgs, {n_inv} at fix_type<3, inject at "
          f"t={t_inject}s")
    print(f"-> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
