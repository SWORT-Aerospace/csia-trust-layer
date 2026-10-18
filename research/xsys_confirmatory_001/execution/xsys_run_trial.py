#!/usr/bin/env python3
"""Fly one PX4 SIH trial for the XSYS-001 cross-system experiment.

Derived from research/px4_actuator_effectiveness/scripts/run_trial.py (the
validated apparatus driver, left unchanged) with two additions the
preregistration needs:

  --heading-deg   the nuisance variable: initial vehicle heading, applied at
                  boot through PX4_HOME_YAW -> SIH_LOC_YAW0 (radians,
                  px4-rc.sihsim), before any module starts
  --onset-param / --onset-value
                  the single parameter change made at the onset time. Fault
                  trials set SIH_MOT_EFF1 = eta; nominal trials set the benign
                  logger parameter SDLOG_DIRS_MAX, which is read only when a
                  log file is opened (logger.cpp start_log_file), so both kinds
                  of flight see exactly one parameter_update broadcast at onset

Every event is keyed to SIMULATED time read from the vehicle. MAVLink is the
control path only; every measurement comes from the ULog.
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import signal
import struct
import subprocess
import threading
import time
from pathlib import Path

from pymavlink import mavutil

HERE = Path(__file__).resolve().parent
LOGGER_TOPICS = HERE.parent.parent / "px4_actuator_effectiveness" / "config" / "logger_topics.txt"


class Vehicle:
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
        if self.m.wait_heartbeat(timeout=timeout_s) is None:
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

    def set_param(self, name, value, ptype, wall_timeout_s=30):
        # PX4 advertises MAV_PROTOCOL_CAPABILITY_PARAM_ENCODE_BYTEWISE
        # (mavlink_main.cpp): an INT32 travels as its bit pattern in the float.
        if ptype == mavutil.mavlink.MAV_PARAM_TYPE_INT32:
            wire = struct.unpack("<f", struct.pack("<i", int(value)))[0]
            decode = lambda f: struct.unpack("<i", struct.pack("<f", f))[0]
        else:
            wire, decode = float(value), float
        self.m.mav.param_set_send(1, 1, name.encode(), wire, ptype)
        sent = self.now_ms()
        t0 = time.monotonic()
        while time.monotonic() - t0 < wall_timeout_s:
            with self.lock:
                got = self.params.get(name)
            if got and got[0] >= sent and abs(decode(got[1]) - value) < 1e-6:
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
    shutil.copy(LOGGER_TOPICS, etc / "logging" / "logger_topics.txt")


def heading_rad(deg):
    """Degrees -> radians wrapped to [-pi, pi], the range SIH_LOC_YAW0 accepts."""
    r = math.radians(deg % 360.0)
    return r - 2 * math.pi if r > math.pi else r


PARAM_TYPES = {"SIH_MOT_EFF1": mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
               "SDLOG_DIRS_MAX": mavutil.mavlink.MAV_PARAM_TYPE_INT32}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--heading-deg", type=float, required=True)
    ap.add_argument("--onset-param", required=True, choices=sorted(PARAM_TYPES))
    ap.add_argument("--onset-value", type=float, required=True)
    ap.add_argument("--t-arm", type=float, default=10.0)
    ap.add_argument("--t-onset", type=float, required=True)
    ap.add_argument("--t-end", type=float, required=True)
    ap.add_argument("--takeoff-alt", type=float, default=10.0)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--instance", type=int, default=0)
    ap.add_argument("--extra-json", default="{}", help="metadata copied into the trial record")
    a = ap.parse_args()

    build = Path(a.build).resolve()
    workdir = Path(a.workdir).resolve()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    prepare_workdir(workdir, build)

    yaw = heading_rad(a.heading_deg)
    env = dict(os.environ, PX4_SIM_MODEL="sihsim_quadx", PX4_SIMULATOR="sihsim",
               PX4_SIM_SPEED_FACTOR=str(a.speed), PX4_HOME_YAW=f"{yaw:.6f}")
    console = open(out / f"{a.name}.console.txt", "w")
    px4 = subprocess.Popen([str(build / "bin" / "px4"), "-d", "-i", str(a.instance), "-w", str(workdir)],
                           cwd=workdir, env=env, stdout=console, stderr=subprocess.STDOUT,
                           start_new_session=True)
    rec = {"name": a.name, "px4_sha256": sha256(build / "bin" / "px4"),
           "logger_topics_sha256": sha256(LOGGER_TOPICS),
           "speed_factor": a.speed, "heading_deg": a.heading_deg, "SIH_LOC_YAW0_rad": round(yaw, 6),
           "onset_param": a.onset_param, "onset_value": a.onset_value, "takeoff_alt": a.takeoff_alt,
           "schedule_s": {"arm": a.t_arm, "onset": a.t_onset, "end": a.t_end},
           "extra": json.loads(a.extra_json), "events_ms": {}}
    wall0 = time.monotonic()
    v = Vehicle(f"udpin:127.0.0.1:{14540 + a.instance}")
    try:
        v.start()
        ms = lambda s: int(round(s * 1000))
        v.wait_until(ms(a.t_arm) - 5000)
        rec["events_ms"]["param_takeoff_alt"] = v.set_param(
            "MIS_TAKEOFF_ALT", a.takeoff_alt, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        v.wait_until(ms(a.t_arm))
        rec["events_ms"]["arm_sent"] = v.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        v.wait_until(ms(a.t_arm) + 500)
        rec["events_ms"]["takeoff_sent"] = v.command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0,
                                                     float("nan"), float("nan"), float("nan"), float("nan"))
        v.wait_until(ms(a.t_onset))
        rec["events_ms"]["onset_set"] = v.set_param(a.onset_param, a.onset_value, PARAM_TYPES[a.onset_param])
        v.wait_until(ms(a.t_end))
        rec["events_ms"]["disarm_sent"] = v.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196)
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
    dst = out / f"{a.name}.ulg"
    shutil.copy(logs[0], dst)
    rec["ulog"] = dst.name
    rec["ulog_sha256"] = sha256(dst)
    (out / f"{a.name}.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: rec[k] for k in ("name", "heading_deg", "onset_param", "onset_value", "wall_s")}))


if __name__ == "__main__":
    main()
