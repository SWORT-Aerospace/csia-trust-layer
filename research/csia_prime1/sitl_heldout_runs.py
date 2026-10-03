#!/usr/bin/env python3
"""Fly PRIME-1's held-out event-discovery flights (HELDOUT_PREREGISTRATION.md). RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/sitl_heldout_runs.py --runs HN1,HN2,... [--out DIR]

**PROSPECTIVELY GENERATED SITL, NOT PHYSICAL EVIDENCE.** No real held-out log
exists, and no untouched simulation log with maneuvering exists either:
every earlier maneuvering flight was used to choose or develop a discovery
rule. So these flights are designed, committed and only then flown.

Same apparatus as RB-001 and 2.3: the XSYS-001 SITL build (PX4 547e2ca with
the SIH_MOT_EFF1-4 patch), PX4's DEFAULT logging, RB-001's flight procedure
(`sitl_maneuver_runs.fly`, imported unchanged). New schedules, winds,
onsets and fault targets; none of them reuses an earlier flight's.

Writes <out>/<id>.ulg, <id>.console.txt and <id>.json (scoring metadata,
never an Analyzer input). CSIA commands nothing; the faults are the
simulator's (SIH_MOT_EFFn) or PX4's stock failure injection.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import common_prime1 as C
import sitl_maneuver_runs as SMR          # RB-001's runner: imported unchanged

SV = SMR.SV
MAG = 2                                   # FAILURE_UNIT_SENSOR_MAG (2.2 pilot run S1 used the same)
pattern = SMR.pattern

#: Schedules: (start s, period s, until s, [(north m, east m, up m, yaw deg), ...]).
P_A = pattern(40, 9, 150, [(40, 0, 0, 90), (40, 40, 0, 180), (0, 40, 0, 270), (0, 0, 0, 0)])
P_B = pattern(40, 6, 95, [(15, 0, 4, 0), (15, 15, -2, 60), (0, 15, 4, 120), (0, 0, 0, 0)])
P_C = pattern(40, 12, 150, [(60, 0, 0, 180), (60, 60, 0, 0), (0, 60, 0, 180), (0, 0, 0, 0)])
P_D = pattern(40, 8, 150, [(25, 0, 3, 45), (25, 25, -2, 225), (0, 25, 3, 45), (0, 0, 0, 225)])
P_Y = pattern(40, 5, 150, [(0, 0, 0, 60), (0, 0, 0, 240), (0, 0, 0, 120), (0, 0, 0, 300)])
P_L = pattern(70, 8, 150, [(30, 0, 0, 90), (30, 30, 0, 180), (0, 30, 0, 270), (0, 0, 0, 0)])

HELDOUT = {
    # nominal (false-event control); every flight includes start-up, arming, take-off,
    # ESC spin-up, and a forced disarm in flight at the end (ESC spin-down)
    "HN1": {"maneuvers": [], "end": 150.0},
    "HN2": {"maneuvers": P_A, "end": 160.0, "boot_params": {"SIH_WIND_N": 3.0}},
    "HN3": {"maneuvers": P_B, "end": 140.0, "boot_params": {"SIH_WIND_E": 4.0}},
    "HN4": {"maneuvers": P_C, "end": 160.0},
    "HN5": {"maneuvers": P_Y, "end": 160.0, "boot_params": {"SIH_WIND_N": 2.0}},
    "HN6": {"maneuvers": P_A, "end": 160.0, "inject": (MAG, SV.OFF, 0), "onset": 90.0},
    "HN7": {"maneuvers": P_D, "end": 160.0, "boot_params": {"SIH_WIND_E": 2.0}},
    "HN8": {"maneuvers": P_L, "end": 160.0, "boot_params": {"SIH_WIND_N": 5.0}},
    # physical losses (recall)
    "HF1": {"maneuvers": [], "end": 130.0, "param": ("SIH_MOT_EFF2", 0.7), "onset": 75.0},
    "HF2": {"maneuvers": P_B, "end": 150.0, "param": ("SIH_MOT_EFF3", 0.6), "onset": 112.0},
    "HF3": {"maneuvers": P_C, "end": 160.0, "param": ("SIH_MOT_EFF1", 0.65), "onset": 93.5},
    "HF4": {"maneuvers": P_D, "end": 160.0, "param": ("SIH_MOT_EFF4", 0.75), "onset": 101.0,
            "boot_params": {"SIH_WIND_E": 3.0}},
    # telemetry faults on healthy motors (recall); PX4's injection message is removed before analysis
    "HT1": {"maneuvers": P_A, "end": 160.0, "inject": (SV.ESC, SV.WRONG, 2), "onset": 84.0},
    "HT2": {"maneuvers": [], "end": 130.0, "inject": (SV.ESC, SV.OFF, 4), "onset": 70.0},
}
#: Truth for scoring (motor index 0-3; PX4 ESC instance n is motor n-1). Never an Analyzer input.
TRUTH = {"HF1": ("loss", 1), "HF2": ("loss", 2), "HF3": ("loss", 0), "HF4": ("loss", 3),
         "HT1": ("telemetry_excess", 1), "HT2": ("telemetry_offline", 3),
         "HN6": ("magnetometer_off", None)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--build", default=str(SMR.C.C23.CP.PX4_BUILD))
    ap.add_argument("--out", default=str(C.OUT_RAW / "heldout"))
    ap.add_argument("--work", default="/tmp/claude-0/prime1_sitl_work")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    SMR.RUNS.update(HELDOUT)
    for rid in a.runs.split(","):
        r = SMR.fly(rid, Path(a.build).resolve(), out, Path(a.work))
        rec = json.loads((out / f"{rid}.json").read_text())
        rec["design"] = "research/csia_prime1/HELDOUT_PREREGISTRATION.md"
        (out / f"{rid}.json").write_text(json.dumps(rec, indent=1))
        print(json.dumps(r), flush=True)


if __name__ == "__main__":
    sys.exit(main())
