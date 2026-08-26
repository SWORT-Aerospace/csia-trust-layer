"""Can genuinely distinct jamming trajectories be generated without patching?

STAGE 0.5 FOUND FIVE BYTE-IDENTICAL RUNS. That is one realisation replayed, and
counting it as N=5 would be a fabricated sample size. This probe tests whether
a preregisterable, non-invasive knob produces genuinely different trajectories.

WHY ONSET TIME IS THE CANDIDATE KNOB. ArduPilot has no seed mechanism:

    get_random16()  libraries/AP_Math/AP_Math.cpp:350
                    static uint32_t m_z = 1234, m_w = 76542 -- hard-coded,
                    never reseeded, drives num_sats
    rand_float()    SITL branch returns random() from libc, which nothing in
                    ArduPilot ever calls srandom() on -- drives horizontal_acc

Both therefore replay the same sequence every boot. But the sequence is
CONSUMED over time by every other SITL user of those generators (sensor noise,
wind, and so on), so the generator STATE at the moment jamming begins is a
function of how long the vehicle has been running. Changing the onset time
changes that state without touching the jamming model, the distribution, or
any simulator source.

That is the brief's option C, and it is only admissible if it actually works.
This probe measures whether it does, rather than assuming it.

Distinctness is judged on the SHA-256 of the (fix_type, satellites_visible,
h_acc) sequence over the jam window -- the same signature that exposed the
Stage 0.5 replays.

  python research/maer/maer_trajectory_distinctness.py --onsets 8,10,12,...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "research", "maer", "MAER_ARDUPILOT_JAM_RAW")
JAM_S = 40.0
SETTLE_S = 3.0
FIELDS = ("time_usec", "fix_type", "satellites_visible", "eph", "epv",
          "h_acc", "v_acc", "vel_acc", "lat", "lon", "alt", "vel", "cog")


def signature(rows):
    seq = [(r["fix_type"], r["satellites_visible"], r["h_acc"])
           for r in rows if r["phase"] == "jam"]
    return hashlib.sha256(repr(seq).encode()).hexdigest()


def one_run(onset_s, tag):
    from pymavlink import mavutil

    from csia.simulation.rigs import LAUNCHERS, connect, provenance_string

    workdir = os.path.join(ROOT, "research", "maer", ".jam_probe", tag)
    proc, conn_str = LAUNCHERS["ardupilot"](workdir, 1)
    try:
        conn = connect(conn_str, "ardupilot")
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

        cap(onset_s, "clean")
        t_inject = round(time.time() - t0, 4)
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                b"SIM_GPS1_JAM", 1.0,
                                mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        cap(JAM_S, "jam")

        return {"tag": tag, "onset_commanded_s": onset_s,
                "t_inject_rel_s": t_inject,
                "simulator": provenance_string("ardupilot"),
                "intervention": {"param": "SIM_GPS1_JAM", "value": 1},
                "variation_mechanism": "jam onset time; no simulator source "
                                       "was modified and the jamming "
                                       "distribution is untouched",
                "rows": rows}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--onsets", default="8,11,14,17,20,23,26,29,32,35")
    args = ap.parse_args()
    onsets = [float(x) for x in args.onsets.split(",") if x.strip()]

    os.makedirs(OUT_DIR, exist_ok=True)
    seen, results = {}, []
    for i, onset in enumerate(onsets, 1):
        tag = f"onset{int(onset):02d}"
        print(f"=== trajectory {i}/{len(onsets)}  onset={onset:.0f}s")
        res = one_run(onset, tag)
        sig = signature(res["rows"])
        res["signature_sha256"] = sig
        jam = [r for r in res["rows"] if r["phase"] == "jam"]
        inv = [r for r in jam if (r["fix_type"] or 0) < 3]
        hacc = {r["h_acc"] for r in inv if r["h_acc"] is not None}
        res["jam_msgs"] = len(jam)
        res["invalid_fix_msgs"] = len(inv)
        res["h_acc_distinct_while_invalid"] = len(hacc)
        dest = os.path.join(OUT_DIR, f"traj_{tag}.json")
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, sort_keys=True, default=str)
        dup = seen.get(sig)
        seen.setdefault(sig, tag)
        print(f"    jam={len(jam)} invalid={len(inv)} "
              f"h_acc_distinct={len(hacc)} sha={sig[:16]}"
              + (f"  DUPLICATE of {dup}" if dup else "  NEW"))
        results.append({"tag": tag, "onset_s": onset, "signature": sig,
                        "duplicate_of": dup, "jam_msgs": len(jam),
                        "invalid_fix_msgs": len(inv),
                        "h_acc_distinct_while_invalid": len(hacc)})

    distinct = sorted({r["signature"] for r in results})
    usable = [r for r in results if r["duplicate_of"] is None
              and r["invalid_fix_msgs"] > 0
              and r["h_acc_distinct_while_invalid"] > 1]
    out = {
        "question": "does varying jam onset produce genuinely distinct "
                    "jamming trajectories, without patching the simulator?",
        "no_seed_mechanism_exists": {
            "get_random16": "AP_Math.cpp:350 static m_z=1234, m_w=76542, "
                            "never reseeded",
            "rand_float": "SITL branch uses libc random(); ArduPilot never "
                          "calls srandom()",
            "sim_parameter": "no SIM_ seed parameter exists",
        },
        "variation_mechanism": "jam onset time",
        "runs": results,
        "distinct_signatures": len(distinct),
        "usable_trajectories": len(usable),
        "meets_minimum_of_5": len(usable) >= 5,
    }
    dest = os.path.join(ROOT, "research", "maer",
                        "MAER_TRAJECTORY_DISTINCTNESS.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"\n  distinct signatures : {len(distinct)} / {len(results)}")
    print(f"  usable trajectories : {len(usable)} "
          f"(distinct, with invalid-fix ticks and live h_acc)")
    print(f"  meets minimum of 5  : {out['meets_minimum_of_5']}")
    print(f"-> {os.path.relpath(dest, ROOT)}")
    return 0 if out["meets_minimum_of_5"] else 1


if __name__ == "__main__":
    sys.exit(main())
