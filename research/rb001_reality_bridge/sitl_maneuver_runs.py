#!/usr/bin/env python3
"""Fly the RB-001 maneuver-study SITL runs (MANEUVER_FLIGHTS_DESIGN.md). RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/sitl_maneuver_runs.py --runs CAL1,CAL2 [--out DIR]

Same apparatus as the 2.3 validation flights: the XSYS-001 SITL build (PX4
547e2ca with the SIH_MOT_EFF1-4 patch), PX4's DEFAULT logging, the
apparatus's MAVLink helper and the 2.3 runner's work-directory and offset
helpers, all imported unchanged. Writes <out>/<id>.ulg, <id>.console.txt and
<id>.json (schedule, injection time and target, acknowledgements, SHA-256).
The JSON is scoring metadata, never an Analyzer input.

Every run is observational SITL: the injected faults are the simulator's
(SIH_MOT_EFFn) or PX4's stock failure injection. CSIA commands nothing.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import common_rb as C
import sitl_validation_runs as SV         # the 2.3 runner: helpers imported, file unchanged

RT = SV.RT
mavutil = SV.mavutil
ARM = 20.0


def pattern(start, period, until, pts):
    out, i, t = [], 0, start
    while t <= until:
        out.append((t,) + tuple(pts[i % len(pts)]))
        i, t = i + 1, t + period
    return out


P_CAL2 = pattern(40, 12, 140, [(50, 0, 0, 90), (50, 50, 0, 180), (0, 50, 0, 270), (0, 0, 0, 0)])
P_CAL3 = pattern(40, 8, 140, [(30, 0, 0, 180), (30, 30, 0, 0), (0, 30, 0, 180), (0, 0, 0, 0)])
P_CAL4 = pattern(40, 10, 140, [(30, 0, 5, 0), (30, 30, -3, 0), (0, 30, 5, 0), (0, 0, 0, 0)])
P_CAL5 = pattern(40, 6, 140, [(0, 0, 0, 90), (0, 0, 0, 270), (0, 0, 0, 45), (0, 0, 0, 180)])
P_EN1 = pattern(40, 10, 150, [(45, 0, 0, 135), (45, 45, 0, 270), (0, 45, 0, 45), (0, 0, 0, 180)])
P_EN2 = pattern(40, 7, 150, [(25, 0, 4, 0), (25, 25, -2, 90), (0, 25, 4, 180), (0, 0, 0, 270)])
P_EN3 = pattern(40, 5, 150, [(0, 0, 0, 120), (10, 0, 0, 300), (10, 10, 0, 60), (0, 0, 0, 240)])
P_EN4 = pattern(40, 15, 150, [(70, 0, 0, 180), (70, 70, 0, 0), (0, 70, 0, 180), (0, 0, 0, 0)])

RUNS = {
    # calibration set: nominal only
    "CAL1": {"maneuvers": [], "end": 120.0},
    "CAL2": {"maneuvers": P_CAL2, "end": 150.0},
    "CAL3": {"maneuvers": P_CAL3, "end": 150.0, "boot_params": {"SIH_WIND_N": 3.0}},
    "CAL4": {"maneuvers": P_CAL4, "end": 150.0, "boot_params": {"SIH_WIND_E": 4.0}},
    "CAL5": {"maneuvers": P_CAL5, "end": 150.0},
    # evaluation set: flown only after MANEUVER_PREREGISTRATION.md is committed
    "EN1": {"maneuvers": P_EN1, "end": 160.0, "boot_params": {"SIH_WIND_N": 2.0}},
    "EN2": {"maneuvers": P_EN2, "end": 160.0, "boot_params": {"SIH_WIND_E": 5.0}},
    "EN3": {"maneuvers": P_EN3, "end": 160.0},
    "EN4": {"maneuvers": P_EN4, "end": 160.0, "boot_params": {"SIH_WIND_N": 4.0}},
    "EF1": {"maneuvers": P_EN1, "end": 160.0, "param": ("SIH_MOT_EFF1", 0.6), "onset": 83.0},
    "EF2": {"maneuvers": P_EN2, "end": 160.0, "param": ("SIH_MOT_EFF2", 0.75), "onset": 91.5},
    "EF3": {"maneuvers": P_EN4, "end": 160.0, "param": ("SIH_MOT_EFF3", 0.6), "onset": 97.0,
            "boot_params": {"SIH_WIND_N": 4.0}},
    "EF4": {"maneuvers": P_EN3, "end": 160.0, "param": ("SIH_MOT_EFF4", 0.75), "onset": 72.5},
    "EF5": {"maneuvers": P_EN1, "end": 160.0, "param": ("SIH_MOT_EFF2", 0.85), "onset": 104.0},
    "EF6": {"maneuvers": P_EN3, "end": 160.0, "param": ("SIH_MOT_EFF4", 0.6), "onset": 88.0,
            "boot_params": {"SIH_WIND_E": 3.0}},
    "EH1": {"maneuvers": [], "end": 100.0, "param": ("SIH_MOT_EFF1", 0.8), "onset": 60.0},
    "ET1": {"maneuvers": P_EN1, "end": 160.0, "inject": (SV.ESC, SV.WRONG, 3), "onset": 85.0},
    "ET2": {"maneuvers": P_EN2, "end": 160.0, "inject": (SV.ESC, SV.OFF, 1), "onset": 85.0},
}


def fly(rid: str, build: Path, out: Path, work: Path) -> dict:
    spec = RUNS[rid]
    wd = SV.workdir_for(work / rid, build)
    boot = dict(spec.get("boot_params", {}), SYS_FAILURE_EN=1)
    env = dict(os.environ, PX4_SIM_MODEL="sihsim_quadx", PX4_SIMULATOR="sihsim",
               PX4_SIM_SPEED_FACTOR="1.0", **{f"PX4_PARAM_{k}": str(v) for k, v in boot.items()})
    console = open(out / f"{rid}.console.txt", "w")
    px4 = subprocess.Popen([str(build / "bin" / "px4"), "-d", "-i", "0", "-w", str(wd)], cwd=wd,
                           env=env, stdout=console, stderr=subprocess.STDOUT, start_new_session=True)
    injected = "param" in spec or "inject" in spec
    rec = {"run": rid, "design": "MANEUVER_FLIGHTS_DESIGN.md", "spec": spec, "boot_params": boot,
           "arm_s": ARM, "onset_s": spec.get("onset") if injected else None,
           "px4_sha256": C.sha(build / "bin" / "px4"), "logging": "PX4 default (no logger_topics.txt)",
           "events_ms": {}}
    v = RT.Vehicle("udpin:127.0.0.1:14540")
    ms = lambda s: int(round(s * 1000))  # noqa: E731
    try:
        v.start(timeout_s=180)
        v.wait_until(ms(ARM) - 5000)
        rec["events_ms"]["param_takeoff_alt"] = v.set_param("MIS_TAKEOFF_ALT", 10.0)
        v.wait_until(ms(ARM))
        rec["events_ms"]["arm_sent"] = v.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        v.wait_until(ms(ARM) + 500)
        rec["events_ms"]["takeoff_sent"] = v.command(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, float("nan"), float("nan"),
            float("nan"), float("nan"))
        plan = [(t, "reposition", (dn, de, dh, yaw), i)
                for i, (t, dn, de, dh, yaw) in enumerate(spec["maneuvers"])]
        if injected:
            plan.append((spec["onset"], "inject", None, None))
        for t, what, pt, k in sorted(plan, key=lambda x: x[0]):
            v.wait_until(ms(t))
            if what == "reposition":
                lat, lon = SV._offset(pt[0], pt[1])
                rec["events_ms"][f"reposition_{k}"] = v.command(
                    mavutil.mavlink.MAV_CMD_DO_REPOSITION, -1, 1, 0, math.radians(pt[3]),
                    lat, lon, SV.H0 + 10.0 + pt[2])
            elif "param" in spec:
                rec["events_ms"]["onset_param_set"] = v.set_param(*spec["param"])
            else:
                rec["events_ms"]["inject_sent"] = v.command(SV.INJECT, *spec["inject"])
        v.wait_until(ms(spec["end"]))
        rec["events_ms"]["disarm_sent"] = v.command(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
        t0 = time.monotonic()
        while v.armed and time.monotonic() - t0 < 30:
            time.sleep(0.01)
        time.sleep(2.0)
        rec["outcome"] = "flown"
    except Exception as exc:  # noqa: BLE001 - recorded, not retried (design rule)
        rec["outcome"] = f"FAILED: {type(exc).__name__}: {exc}"
    finally:
        rec["acks"] = v.acks
        rec["statustext"] = v.statustext
        v.alive = False
        os.killpg(px4.pid, signal.SIGINT)
        try:
            px4.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(px4.pid, signal.SIGKILL)
            px4.wait()
        console.close()
        try:
            v.m.close()
        except Exception:  # noqa: BLE001
            pass
    logs = sorted((work / rid).glob("log/**/*.ulg"))
    if len(logs) == 1:
        shutil.copy(logs[0], out / f"{rid}.ulg")
        rec["ulog_sha256"] = C.sha(out / f"{rid}.ulg")
    (out / f"{rid}.json").write_text(json.dumps(rec, indent=1))
    shutil.rmtree(work / rid, ignore_errors=True)      # the ULog is copied; keep the disk free
    return {"run": rid, "outcome": rec["outcome"], "ulog": rec.get("ulog_sha256")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--build", default=str(C.C23.CP.PX4_BUILD))
    ap.add_argument("--out", default=str(C.OUT_RAW / "sitl"))
    ap.add_argument("--work", default="/tmp/claude-0/rb001_sitl_work")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for rid in a.runs.split(","):
        print(json.dumps(fly(rid, Path(a.build).resolve(), out, Path(a.work))), flush=True)


if __name__ == "__main__":
    sys.exit(main())
