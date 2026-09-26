#!/usr/bin/env python3
"""Fly one PX4 SIH quadcopter trial and keep its ULog.

Research-only apparatus for docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md.
It does not import, run or touch CSIA.

Every event is keyed to SIMULATED time (time_boot_ms read from the vehicle over
the offboard MAVLink link), so matched trials see the same schedule:

    t_arm      arm
    t_arm+0.5  takeoff to MIS_TAKEOFF_ALT, then PX4 holds position
    t_onset    PARAM_SET SIH_MOT_EFF<motor> = eta   (only when --eta is given)
    t_end      force disarm; the logger closes the ULog on disarm

MAVLink is the CONTROL path only. Every measurement is taken from the ULog.
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from pymavlink import mavutil

HERE = Path(__file__).resolve().parent
APPARATUS = HERE.parent


class Vehicle:
    """Background reader of the offboard MAVLink stream."""

    def __init__(self, url):
        self.m = mavutil.mavlink_connection(url, source_system=255, source_component=190)
        self.lock = threading.Lock()
        self.t_ms = 0
        self.armed = False
        self.acks = []
        self.params = {}
        self.statustext = []
        self.alive = True
        self.th = threading.Thread(target=self._loop, daemon=True)

    def start(self, timeout_s=120):
        hb = self.m.wait_heartbeat(timeout=timeout_s)
        if hb is None:
            raise RuntimeError("no heartbeat from PX4")
        self.th.start()

    def _loop(self):
        while self.alive:
            msg = self.m.recv_match(blocking=True, timeout=0.5)
            if msg is None:
                continue
            t = msg.get_type()
            with self.lock:
                if hasattr(msg, "time_boot_ms"):
                    self.t_ms = max(self.t_ms, msg.time_boot_ms)
                if t == "HEARTBEAT" and msg.get_srcComponent() == 1:
                    self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                elif t == "COMMAND_ACK":
                    self.acks.append((self.t_ms, msg.command, msg.result))
                elif t == "PARAM_VALUE":
                    self.params[msg.param_id] = (self.t_ms, msg.param_value)
                elif t == "STATUSTEXT":
                    self.statustext.append((self.t_ms, msg.text))

    def now_ms(self):
        with self.lock:
            return self.t_ms

    def wait_until(self, t_ms, wall_timeout_s=600):
        t0 = time.monotonic()
        while self.now_ms() < t_ms:
            if time.monotonic() - t0 > wall_timeout_s:
                raise RuntimeError(f"simulated time stalled before {t_ms} ms")
            time.sleep(0.0005)
        return self.now_ms()

    def command(self, cmd, *p):
        p = list(p) + [0.0] * (7 - len(p))
        self.m.mav.command_long_send(1, 1, cmd, 0, *p)
        return self.now_ms()

    def set_param(self, name, value, wall_timeout_s=30):
        self.m.mav.param_set_send(1, 1, name.encode(), float(value),
                                  mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        sent = self.now_ms()
        t0 = time.monotonic()
        while time.monotonic() - t0 < wall_timeout_s:
            with self.lock:
                got = self.params.get(name)
            if got and got[0] >= sent and abs(got[1] - value) < 1e-6:
                return sent, got[0]
            time.sleep(0.001)
        raise RuntimeError(f"PARAM_SET {name}={value} not acknowledged")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_workdir(workdir, build):
    if workdir.exists():
        shutil.rmtree(workdir)
    etc = workdir / "etc"
    (etc / "logging").mkdir(parents=True)
    for sub in ("init.d", "init.d-posix", "extras"):
        os.symlink(build / "etc" / sub, etc / sub)
    shutil.copy(APPARATUS / "config" / "logger_topics.txt", etc / "logging" / "logger_topics.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True, help="PX4 build dir, e.g. .../build/px4_sitl_default")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", required=True, help="directory receiving the ULog and trial JSON")
    ap.add_argument("--name", required=True)
    ap.add_argument("--instance", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0, help="PX4_SIM_SPEED_FACTOR")
    ap.add_argument("--motor", type=int, default=1, help="SIH_MOT_EFF<motor>; 1 = Motor1 = CSIA motor_0")
    ap.add_argument("--eta", type=float, default=None, help="effectiveness set at onset; omit for no injection")
    ap.add_argument("--takeoff-alt", type=float, default=10.0)
    ap.add_argument("--t-arm", type=float, default=20.0, help="simulated seconds after boot")
    ap.add_argument("--t-onset", type=float, default=50.0)
    ap.add_argument("--t-end", type=float, default=75.0)
    a = ap.parse_args()

    build = Path(a.build).resolve()
    workdir = Path(a.workdir).resolve()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    prepare_workdir(workdir, build)

    env = dict(os.environ, PX4_SIM_MODEL="sihsim_quadx", PX4_SIMULATOR="sihsim",
               PX4_SIM_SPEED_FACTOR=str(a.speed))
    console = open(out / f"{a.name}.console.txt", "w")
    px4 = subprocess.Popen([str(build / "bin" / "px4"), "-d", "-i", str(a.instance), "-w", str(workdir)],
                           cwd=workdir, env=env, stdout=console, stderr=subprocess.STDOUT,
                           start_new_session=True)
    rec = {"name": a.name, "build": str(build), "px4_sha256": sha256(build / "bin" / "px4"),
           "speed_factor": a.speed, "motor": a.motor, "eta": a.eta, "takeoff_alt": a.takeoff_alt,
           "schedule_s": {"arm": a.t_arm, "onset": a.t_onset, "end": a.t_end}, "events_ms": {}}
    wall0 = time.monotonic()
    v = Vehicle(f"udpin:127.0.0.1:{14540 + a.instance}")
    try:
        v.start()
        ms = lambda s: int(round(s * 1000))
        v.wait_until(ms(a.t_arm) - 5000)
        rec["events_ms"]["param_takeoff_alt"] = v.set_param("MIS_TAKEOFF_ALT", a.takeoff_alt)
        v.wait_until(ms(a.t_arm))
        rec["events_ms"]["arm_sent"] = v.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        v.wait_until(ms(a.t_arm) + 500)
        rec["events_ms"]["takeoff_sent"] = v.command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0,
                                                     float("nan"), float("nan"), float("nan"), float("nan"))
        if a.eta is not None:
            v.wait_until(ms(a.t_onset))
            rec["events_ms"]["eta_set"] = v.set_param(f"SIH_MOT_EFF{a.motor}", a.eta)
        v.wait_until(ms(a.t_end))
        rec["events_ms"]["disarm_sent"] = v.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
        t0 = time.monotonic()
        while v.armed and time.monotonic() - t0 < 30:
            time.sleep(0.01)
        time.sleep(2.0)  # let the logger close the file
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
    dst = out / f"{a.name}.ulg"
    shutil.copy(logs[0], dst)
    rec["ulog"] = dst.name
    rec["ulog_sha256"] = sha256(dst)
    (out / f"{a.name}.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: rec[k] for k in ("name", "eta", "wall_s", "ulog_sha256")}))


if __name__ == "__main__":
    main()
