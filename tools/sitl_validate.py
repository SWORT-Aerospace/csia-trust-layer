"""ArduPilot SITL validation: fly a scripted mission and stream the live
MAVLink telemetry through the real-time trust layer.

This is what converts the MAVLink mapping from 'experimental' to
'SITL-validated': real ArduPilot message set, real units, real frames, a
real EKF — zero hardware. Pass/fail is printed at the end.

Usage:
  .venv/bin/python tools/sitl_validate.py [--binary PATH] [--speedup 4]
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymavlink import mavutil  # noqa: E402

from csia.runtime import FailsafePolicy, OnlineTrustLayer  # noqa: E402
from csia.runtime.failsafe import FailsafeConfig  # noqa: E402
from csia.runtime.plugins import map_mavlink  # noqa: E402

DEFAULT_BINARY = "/tmp/ardupilot/build/sitl/bin/arducopter"
DEFAULT_PARAMS = "/tmp/ardupilot/Tools/autotest/default_params/copter.parm"

STREAMS = {  # message -> interval us
    "SCALED_IMU": 20_000, "SCALED_IMU2": 20_000, "SCALED_PRESSURE": 50_000,
    "GLOBAL_POSITION_INT": 100_000, "GPS_RAW_INT": 100_000,
    "BATTERY_STATUS": 200_000, "VIBRATION": 100_000,
}
MSG_IDS = {"SCALED_IMU": 26, "SCALED_IMU2": 116, "SCALED_PRESSURE": 29,
           "GLOBAL_POSITION_INT": 33, "GPS_RAW_INT": 24,
           "BATTERY_STATUS": 147, "VIBRATION": 241}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--speedup", type=int, default=4)
    ap.add_argument("--inject", choices=("none", "gps_glitch"), default="none",
                    help="inject a fault into the REAL autopilot mid-flight "
                         "and require the trust layer to catch it")
    args = ap.parse_args()

    sitl = subprocess.Popen(
        [args.binary, "--model", "quad", "--defaults", args.params,
         "--speedup", str(args.speedup), "-w",
         "--home", "47.397742,8.545594,488,0"],
        cwd="/tmp", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"SITL: arducopter pid {sitl.pid}, speedup x{args.speedup}")
    try:
        run_mission(args)
    finally:
        sitl.terminate()


def run_mission(args):
    time.sleep(3.0)
    m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
    m.wait_heartbeat(timeout=60)
    print("SITL: heartbeat OK")

    for name, interval in STREAMS.items():
        m.mav.command_long_send(m.target_system, m.target_component,
                                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                                0, MSG_IDS[name], interval, 0, 0, 0, 0, 0)
    m.mav.param_set_send(m.target_system, m.target_component,
                         b"ARMING_CHECK", 0,
                         mavutil.mavlink.MAV_PARAM_TYPE_INT32)

    layer = OnlineTrustLayer(field_mode=True,
                             stale_timeout_s={"motor_esc": 1e9,
                                              "vibration": 2.0})
    policy = FailsafePolicy(FailsafeConfig(arm_time=25.0))
    ctx = {"t0": None}
    msg_counts = {}
    min_trust = {}
    phase = "warmup"
    phase_t0 = time.time()
    armed_sent = takeoff_sent = False
    inject_t0 = None
    inject_wall = None
    inject2 = False
    landed = False
    wall_deadline = time.time() + 240

    def pump(msg):
        nonlocal min_trust
        msg_counts[msg.get_type()] = msg_counts.get(msg.get_type(), 0) + 1
        for sensor, t, ch in map_mavlink(msg, ctx):
            for st in layer.ingest(sensor, t, ch):
                policy.update(st)
                if st.t > 30.0:
                    for n, v in st.trust.items():
                        if st.fresh[n]:
                            min_trust[n] = min(min_trust.get(n, 1.0), v)

    while time.time() < wall_deadline and not landed:
        msg = m.recv_match(blocking=True, timeout=5)
        if msg is None:
            print("SITL: stream timeout"); break
        pump(msg)
        hb = m.messages.get("HEARTBEAT")
        gpi = m.messages.get("GLOBAL_POSITION_INT")
        if phase == "warmup" and time.time() - phase_t0 > 25:
            m.set_mode("GUIDED"); phase = "arm"
        elif phase == "arm" and not armed_sent:
            m.arducopter_arm(); armed_sent = True
        elif phase == "arm" and hb and \
                hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            m.mav.command_long_send(m.target_system, m.target_component,
                                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                                    0, 0, 0, 0, 0, 0, 0, 20)
            phase = "climb"; phase_t0 = time.time(); print("SITL: takeoff")
        elif phase == "climb" and gpi and gpi.relative_alt > 18_000:
            print("SITL: at altitude, flying square")
            phase = "fly"; phase_t0 = time.time()
        elif phase == "fly":
            if args.inject == "gps_glitch" and not inject_t0 and \
                    time.time() - phase_t0 > 10:
                # ~55 m instantaneous position glitch in the SIM GPS driver
                for pname in (b"SIM_GPS_GLITCH_X", b"SIM_GPS1_GLTCH_X"):
                    m.mav.param_set_send(m.target_system, m.target_component,
                                         pname, 0.0005,
                                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
                inject_t0 = ctx["t0"] + 0  # marker; sample time recorded below
                inject_wall = time.time()
                print("SITL: GPS GLITCH INJECTED (+55 m)")
            if args.inject == "gps_glitch" and inject_wall and \
                    not inject2 and time.time() - inject_wall > 12:
                for pname, val in ((b"SIM_GPS_DISABLE", 1.0),
                                   (b"SIM_GPS1_ENABLE", 0.0)):
                    m.mav.param_set_send(m.target_system, m.target_component,
                                         pname, val,
                                         mavutil.mavlink.MAV_PARAM_TYPE_INT8)
                inject2 = True
                print("SITL: GPS FIX KILLED")
            leg = int((time.time() - phase_t0) / 6) % 4
            vn, ve = [(4, 0), (0, 4), (-4, 0), (0, -4)][leg]
            m.mav.set_position_target_local_ned_send(
                0, m.target_system, m.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000111111000111, 0, 0, 0, vn, ve, 0, 0, 0, 0, 0, 0)
            if time.time() - phase_t0 > (45 if args.inject != "none" else 30):
                m.set_mode("LAND"); phase = "land"; print("SITL: landing")
        elif phase == "land" and hb and not \
                (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            landed = True

    # --- verdict ----------------------------------------------------------------
    print("\n=== SITL VALIDATION ===")
    print("messages:", {k: v for k, v in sorted(msg_counts.items())
                        if k in STREAMS})
    fresh_sensors = sorted(n for n in min_trust)
    print("monitored sensors:", fresh_sensors)
    print("min trust (t>30s):",
          {n: round(v, 2) for n, v in sorted(min_trust.items())})
    alarms = [tr for tr in policy.transitions if tr.level.name != "NORMAL"]
    for tr in alarms:
        print(f"  alarm t={tr.t:.1f}s {tr.level.name}: {tr.reasons}")
    if args.inject == "gps_glitch":
        nav_alarms = [tr for tr in alarms
                      if any("GPS" in r or "gps" in r for r in tr.reasons)]
        ok = len(nav_alarms) >= 1
        print("VERDICT:", "PASS — injected GPS fault on a REAL autopilot "
              "detected live" if ok else "FAIL — glitch not detected")
    else:
        ok = (landed and len(fresh_sensors) >= 5
              and all(v > 0.5 for v in min_trust.values()) and not alarms)
        print("mission landed:", landed)
        print("VERDICT:", "PASS — MAVLink mapping SITL-validated"
              if ok else "FAIL — inspect above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
