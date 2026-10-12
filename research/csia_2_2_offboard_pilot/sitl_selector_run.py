#!/usr/bin/env python3
"""Run S1: PX4 SIH SITL with the EKF2 selector enabled (SENS_IMU_MODE = 0)
and a stock magnetometer failure injection. RESEARCH ONLY. The design is
frozen in SITL_SELECTOR_RUN_DESIGN.md.

    .venv/bin/python research/csia_2_2_offboard_pilot/sitl_selector_run.py --out DIR

Uses the existing XSYS-001 SITL build and the apparatus's own MAVLink helper
(`research/px4_actuator_effectiveness/scripts/run_trial.py`, imported, not
edited). Parameters are set with PX4's stock `PX4_PARAM_<name>` environment
override; no PX4 or simulator file is changed.

Writes, in DIR (outside git):
- S1.ulg;
- S1.console.txt;
- S1.json: the schedule, command acknowledgements, status text, SHA-256s.

Then `analyze_s1.py` extracts what the Analyzer reads into the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import common_pilot as C

sys.path.insert(0, str(C.REPO / "research/px4_actuator_effectiveness/scripts"))
import run_trial as RT  # noqa: E402  (the apparatus helper, imported unchanged)

from pymavlink import mavutil  # noqa: E402

PARAMS = {"SENS_IMU_MODE": 0, "EKF2_MULTI_IMU": 2, "SYS_FAILURE_EN": 1}
SCHEDULE_S = {"arm": 45.0, "onset": 75.0, "end": 100.0}
MAV_CMD_INJECT_FAILURE = 420
FAILURE_UNIT_SENSOR_MAG, FAILURE_TYPE_OFF, ALL_INSTANCES = 2, 1, 0


def prepare_workdir(workdir: Path, build: Path):
    if workdir.exists():
        shutil.rmtree(workdir)
    etc = workdir / "etc"
    (etc / "logging").mkdir(parents=True)
    for sub in ("init.d", "init.d-posix", "extras"):
        os.symlink(build / "etc" / sub, etc / sub)
    shutil.copy(C.HERE / "config" / "logger_topics_s1.txt", etc / "logging" / "logger_topics.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=str(C.PX4_BUILD))
    ap.add_argument("--workdir", default="/tmp/claude-0/pilot_s1_work")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build, workdir, out = Path(a.build).resolve(), Path(a.workdir).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    prepare_workdir(workdir, build)
    env = dict(os.environ, PX4_SIM_MODEL="sihsim_quadx", PX4_SIMULATOR="sihsim",
               PX4_SIM_SPEED_FACTOR="1.0",
               **{f"PX4_PARAM_{k}": str(v) for k, v in PARAMS.items()})
    console = open(out / "S1.console.txt", "w")
    px4 = subprocess.Popen([str(build / "bin" / "px4"), "-d", "-i", "0", "-w", str(workdir)],
                           cwd=workdir, env=env, stdout=console, stderr=subprocess.STDOUT,
                           start_new_session=True)
    rec = {"name": "S1", "design": "SITL_SELECTOR_RUN_DESIGN.md", "params": PARAMS,
           "schedule_s": SCHEDULE_S, "px4_sha256": C.sha(build / "bin" / "px4"),
           "logger_topics_sha256": C.sha(C.HERE / "config" / "logger_topics_s1.txt"),
           "events_ms": {}}
    wall0 = time.monotonic()
    v = RT.Vehicle("udpin:127.0.0.1:14540")
    try:
        v.start(timeout_s=180)
        ms = lambda s: int(round(s * 1000))  # noqa: E731
        v.wait_until(ms(SCHEDULE_S["arm"]) - 5000)
        rec["events_ms"]["param_takeoff_alt"] = v.set_param("MIS_TAKEOFF_ALT", 10.0)
        v.wait_until(ms(SCHEDULE_S["arm"]))
        rec["events_ms"]["arm_sent"] = v.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        v.wait_until(ms(SCHEDULE_S["arm"]) + 500)
        rec["events_ms"]["takeoff_sent"] = v.command(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0,
            float("nan"), float("nan"), float("nan"), float("nan"))
        v.wait_until(ms(SCHEDULE_S["onset"]))
        rec["events_ms"]["mag_off_sent"] = v.command(MAV_CMD_INJECT_FAILURE, FAILURE_UNIT_SENSOR_MAG,
                                                     FAILURE_TYPE_OFF, ALL_INSTANCES)
        v.wait_until(ms(SCHEDULE_S["end"]))
        rec["events_ms"]["disarm_sent"] = v.command(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
        t0 = time.monotonic()
        while v.armed and time.monotonic() - t0 < 30:
            time.sleep(0.01)
        time.sleep(2.0)
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
    rec["wall_s"] = round(time.monotonic() - wall0, 1)
    logs = sorted(workdir.glob("log/**/*.ulg"))
    if len(logs) != 1:
        raise RuntimeError(f"expected one ULog, found {logs}")
    shutil.copy(logs[0], out / "S1.ulg")
    rec["ulog_sha256"] = C.sha(out / "S1.ulg")
    rec["ulog_bytes"] = (out / "S1.ulg").stat().st_size
    (out / "S1.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: rec[k] for k in ("wall_s", "ulog_sha256", "ulog_bytes")}))


if __name__ == "__main__":
    main()
