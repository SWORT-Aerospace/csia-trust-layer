#!/usr/bin/env python3
"""Fly the validation runs of VALIDATION_FLIGHTS_DESIGN.md (V1-V10) and
VALIDATION_FLIGHTS_DESIGN_2.md (V11-V13). RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/sitl_validation_runs.py --runs V1,V2 [--out DIR]

Each run: PX4 SIH SITL (the XSYS-001 build), PX4's DEFAULT logging (no
logger_topics.txt), the apparatus MAVLink helper imported unchanged.
Writes <out>/<id>.ulg, <id>.console.txt and <id>.json (schedule, injection,
acknowledgements, status text, SHA-256). The JSON is scoring metadata,
never an Analyzer input.
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

import common_23 as C

sys.path.insert(0, str(C.REPO / "research/px4_actuator_effectiveness/scripts"))
import run_trial as RT  # noqa: E402  (imported unchanged)

from pymavlink import mavutil  # noqa: E402

INJECT = 420
GPS, BAT, ESC = 4, 100, 106
OFF, WRONG = 1, 4
LAT0, LON0, H0 = 47.397743225097656, 8.545594215393066, 489.4

RUNS = {
    "V1": {"param": ("SIH_MOT_EFF2", 0.6), "end": 80.0},
    "V2": {"param": ("SIH_MOT_EFF3", 0.6), "end": 80.0},
    "V3": {"param": ("SIH_MOT_EFF4", 0.6), "end": 80.0},
    "V4": {"param": ("SIH_MOT_EFF1", 0.6), "end": 80.0},
    "V5": {"maneuver": True, "end": 160.0},
    "V6": {"maneuver": True, "end": 160.0, "boot_params": {"SIH_WIND_N": 5.0}},
    "V7": {"inject": (GPS, OFF, 0), "end": 90.0},
    "V8": {"inject": (BAT, WRONG, 0), "end": 90.0},
    "V9": {"inject": (ESC, OFF, 2), "end": 80.0},
    "V10": {"inject": (ESC, WRONG, 3), "end": 80.0},
    # second design (VALIDATION_FLIGHTS_DESIGN_2.md): the steadiness fix, blind
    "V11": {"maneuver_spec": {"start": 40.0, "period": 15.0, "until": 150.0, "pts": [
        (60, 0, 180), (60, 60, 0), (0, 60, 180), (0, 0, 0)]},
            "end": 160.0, "boot_params": {"SIH_WIND_E": 3.0}},
    "V12": {"maneuver_spec": {"start": 40.0, "period": 15.0, "until": 71.0, "pts": [
        (60, 0, 180), (60, 60, 0), (0, 0, 90)]},
            "param": ("SIH_MOT_EFF3", 0.6), "onset": 100.0, "end": 130.0},
    "V13": {"maneuver_spec": {"start": 40.0, "period": 15.0, "until": 130.0, "pts": [
        (60, 0, 180), (60, 60, 0), (0, 60, 180), (0, 0, 0)]},
            "param": ("SIH_MOT_EFF3", 0.6), "onset": 77.0, "end": 140.0},
}
ARM, ONSET = 20.0, 50.0


def workdir_for(base: Path, build: Path) -> Path:
    if base.exists():
        shutil.rmtree(base)
    etc = base / "etc"
    etc.mkdir(parents=True)
    for sub in ("init.d", "init.d-posix", "extras"):
        os.symlink(build / "etc" / sub, etc / sub)
    return base          # no etc/logging/logger_topics.txt: default logging


def _offset(dn, de):
    lat = LAT0 + dn / 6371000.0 * 180.0 / math.pi
    lon = LON0 + de / (6371000.0 * math.cos(math.radians(LAT0))) * 180.0 / math.pi
    return lat, lon


def fly(rid: str, build: Path, out: Path, work: Path) -> dict:
    spec = RUNS[rid]
    wd = workdir_for(work / rid, build)
    boot = dict(spec.get("boot_params", {}), SYS_FAILURE_EN=1)
    env = dict(os.environ, PX4_SIM_MODEL="sihsim_quadx", PX4_SIMULATOR="sihsim",
               PX4_SIM_SPEED_FACTOR="1.0", **{f"PX4_PARAM_{k}": str(v) for k, v in boot.items()})
    console = open(out / f"{rid}.console.txt", "w")
    px4 = subprocess.Popen([str(build / "bin" / "px4"), "-d", "-i", "0", "-w", str(wd)], cwd=wd,
                           env=env, stdout=console, stderr=subprocess.STDOUT, start_new_session=True)
    onset = spec.get("onset", ONSET)
    design = "VALIDATION_FLIGHTS_DESIGN_2.md" if "maneuver_spec" in spec else "VALIDATION_FLIGHTS_DESIGN.md"
    injected = "param" in spec or "inject" in spec
    rec = {"run": rid, "design": design, "spec": {k: v for k, v in spec.items()},
           "boot_params": boot, "arm_s": ARM, "onset_s": onset if injected else None,
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
        if spec.get("maneuver"):
            pts = [(40, 0, 90), (40, 40, 180), (0, 40, 270), (0, 0, 0)] * 3
            for i, (dn, de, yaw) in enumerate(pts):
                t = 40.0 + 10.0 * i
                if t >= spec["end"] - 10:
                    break
                v.wait_until(ms(t))
                lat, lon = _offset(dn, de)
                rec["events_ms"][f"reposition_{i}"] = v.command(
                    mavutil.mavlink.MAV_CMD_DO_REPOSITION, -1, 1, 0, math.radians(yaw), lat, lon,
                    H0 + 10.0)
        elif "maneuver_spec" in spec:
            # timed repositions, and the injection at its own time between them
            ms_ = spec["maneuver_spec"]
            plan = []
            i, t = 0, ms_["start"]
            while t <= ms_["until"]:
                plan.append((t, "reposition", ms_["pts"][i % len(ms_["pts"])], i))
                i, t = i + 1, t + ms_["period"]
            if injected:
                plan.append((onset, "inject", None, None))
            for t, what, pt, k in sorted(plan, key=lambda x: x[0]):
                v.wait_until(ms(t))
                if what == "reposition":
                    lat, lon = _offset(pt[0], pt[1])
                    rec["events_ms"][f"reposition_{k}"] = v.command(
                        mavutil.mavlink.MAV_CMD_DO_REPOSITION, -1, 1, 0, math.radians(pt[2]),
                        lat, lon, H0 + 10.0)
                elif "param" in spec:
                    rec["events_ms"]["onset_param_set"] = v.set_param(*spec["param"])
                else:
                    rec["events_ms"]["inject_sent"] = v.command(INJECT, *spec["inject"])
        else:
            v.wait_until(ms(ONSET))
            if "param" in spec:
                rec["events_ms"]["onset_param_set"] = v.set_param(*spec["param"])
            else:
                rec["events_ms"]["inject_sent"] = v.command(INJECT, *spec["inject"])
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
    return {"run": rid, "outcome": rec["outcome"], "ulog": rec.get("ulog_sha256")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="V1,V2,V3,V4,V5,V6,V7,V8,V9,V10")
    ap.add_argument("--build", default=str(C.CP.PX4_BUILD))
    ap.add_argument("--out", default=str(C.OUT_RAW / "validation"))
    ap.add_argument("--work", default="/tmp/claude-0/csia23_validation_work")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for rid in a.runs.split(","):
        print(json.dumps(fly(rid, Path(a.build).resolve(), out, Path(a.work))), flush=True)


if __name__ == "__main__":
    main()
