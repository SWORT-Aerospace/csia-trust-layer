"""Simulator rigs: launching ArduPilot and PX4 SITL and flying them.

This module MAY command a simulated vehicle. That is legitimate here and
nowhere near `csia.deploy`: a qualification probe has to arm and climb, and a
shadow deployment must never be able to. The separation is enforced by
`tests/test_shadow_mode.py::test_no_send_calls_in_deployment_source` (which
scans `csia/deploy` and `csia/aircraft`, not this file) and by
`test_deploy_never_imports_the_rigs` below it.

It lives in `csia.simulation` rather than beside the scripts because
`run_campaign.py` was importing it as a bare sibling module, which only worked
because the script's own directory happened to be on `sys.path` -- and the
repository's CI-environment guard correctly flagged `qualify_platform` as an
undeclared third-party import.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

AP_ROOT = os.environ.get("CSIA_AP_ROOT", "/home/user/ardupilot/ardupilot")
PX4_ROOT = os.environ.get("CSIA_PX4_ROOT", "/home/user/px4")
HOME = "-35.363261,149.165230,584,353"


def launch_ardupilot(workdir, speedup=10):
    binary = os.path.join(AP_ROOT, "build", "sitl", "bin", "arducopter")
    if not os.path.exists(binary):
        raise SystemExit(f"ArduPilot SITL binary not found: {binary}\n"
                         f"set CSIA_AP_ROOT or build it with "
                         f"./waf configure --board sitl && ./waf copter")
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    # SERIAL1 gives a SECOND MAVLink link, and it is not a convenience.
    #
    # SITL's SERIAL0 (tcp:5760) accepts one client. A shadow monitor sharing
    # it with the rig cannot work: the rig holds it to arm and to request data
    # streams, and when it disconnects the monitor's reconnect gets EOF.
    #
    # More importantly the two links have different AUTHORITY, and that is the
    # real deployment shape rather than a test fixture. SERIAL0 is the rig or
    # the GCS: it commands, and it is what asks the autopilot to stream.
    # SERIAL1 is CSIA: passive, read-only, and structurally unable to ask for
    # anything. On a real aircraft this is a GCS/telemetry link plus a
    # companion port.
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup), "-w",
         "--home", HOME, "--instance", "0",
         "--serial1", "tcp:5762"],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return proc, "tcp:127.0.0.1:5760"


# The passive link per platform: where a shadow monitor listens while the rig
# or a GCS holds the command link. See launch_ardupilot for why two exist.
PASSIVE_LINKS = {
    "ardupilot": "tcp:127.0.0.1:5762",
    "px4": "udp:127.0.0.1:14550",
}


def launch_px4(workdir, speedup=1):
    binary = os.path.join(PX4_ROOT, "build", "px4_sitl_default", "bin", "px4")
    if not os.path.exists(binary):
        raise SystemExit(f"PX4 SITL binary not found: {binary}\n"
                         f"set CSIA_PX4_ROOT or build it with "
                         f"make px4_sitl_default")
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    etc = os.path.join(PX4_ROOT, "build", "px4_sitl_default", "etc")
    env = dict(os.environ)
    # SIH -- Simulation In Hardware. PX4's own rigid-body model, running
    # inside the PX4 process. No Gazebo, no jMAVSim, no external frontend.
    #
    # `PX4_SIM_MODEL=none_iris` was tried first and PX4 never emitted a
    # heartbeat: with no simulator attached, simulator_mavlink blocks on TCP
    # 4560 waiting for one and the rest of the system never boots. SIH has
    # real dynamics, so the motion positive control can actually fire.
    env["PX4_SYS_AUTOSTART"] = "10040"      # sihsim_quadx
    env["PX4_SIM_MODEL"] = "sihsim_quadx"
    proc = subprocess.Popen(
        [binary, "-d", "-s", os.path.join(etc, "init.d-posix", "rcS"), etc],
        cwd=workdir, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return proc, "udp:127.0.0.1:14550"


LAUNCHERS = {"ardupilot": launch_ardupilot, "px4": launch_px4}


def wait_for_port(conn_str, timeout=60.0) -> bool:
    """Wait for a TCP listener to exist before dialling it.

    SITL does not open every serial port at once: SERIAL0 (5760) accepts
    connections about 3 s after launch, SERIAL1 (5762) about 8 s. Dialling
    5762 immediately gets ECONNREFUSED, and pymavlink's own retry can burn its
    heartbeat window on the refused attempts -- which is exactly how a run
    died with "no heartbeat within 90s" against a port that was working fine
    five seconds later.

    Non-TCP connection strings return True immediately; there is nothing to
    wait for.
    """
    import socket as _s
    if not conn_str.startswith("tcp:"):
        return True
    host, _, port = conn_str[4:].rpartition(":")
    host, port = host or "127.0.0.1", int(port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        sock = _s.socket()
        sock.settimeout(0.5)
        try:
            sock.connect((host, port))
            sock.close()
            return True
        except OSError:
            time.sleep(0.5)
        finally:
            try:
                sock.close()
            except OSError:
                pass
    return False


def connect(conn_str, platform, timeout=90):
    from pymavlink import mavutil
    if not wait_for_port(conn_str, timeout=min(timeout, 60.0)):
        raise SystemExit(f"no TCP listener on {conn_str}")
    deadline = time.time() + timeout
    m = None
    while time.time() < deadline:
        try:
            m = mavutil.mavlink_connection(conn_str)
            if m.wait_heartbeat(timeout=10):
                break
        except Exception:
            time.sleep(1.0)
        m = None
    if m is None:
        raise SystemExit(f"no heartbeat on {conn_str} within {timeout}s")
    if platform == "ardupilot":
        for stream, hz in (
                (mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 25),
                (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 10),
                (mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
                (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
                (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 10),
                (mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 5)):
            m.mav.request_data_stream_send(m.target_system,
                                           m.target_component, stream, hz, 1)
    else:
        for mid, hz in ((105, 50), (26, 25), (29, 10), (24, 5),
                        (147, 10), (241, 10), (230, 5), (0, 1)):
            m.mav.command_long_send(m.target_system, m.target_component,
                                    511, 0, mid, int(1e6 / hz), 0, 0, 0, 0, 0)
    return m


def _fly_px4(conn, evidence, alt_m, timeout):
    """Arm and take off on PX4 SIH.

    PX4 is not ArduPilot with different command names: there is no
    `arducopter_arm`, mode changes go through MAV_CMD_DO_SET_MODE with a
    main/sub mode pair, and takeoff is MAV_CMD_NAV_TAKEOFF in AUTO.
    """
    from pymavlink import mavutil
    # PX4 refuses to arm under a pile of preflight checks that exist for a
    # real vehicle and are noise for a qualification probe. Relaxing them is
    # legitimate HERE (a simulator, in a tool that may command) and is
    # recorded in the probe evidence.
    for name, val in (("COM_RCL_EXCEPT", 7), ("NAV_RCL_ACT", 0),
                      ("NAV_DLL_ACT", 0), ("COM_ARM_WO_GPS", 1),
                      ("COM_PREARM_MODE", 0), ("COM_ARM_MAG_STR", 0),
                      ("COM_ARM_EKF_HGT", 1.0), ("COM_ARM_EKF_VEL", 1.0),
                      ("COM_ARM_EKF_POS", 1.0), ("COM_ARM_EKF_YAW", 1.0),
                      ("COM_DISARM_LAND", -1), ("COM_DISARM_PRFLT", -1),
                      ("CBRK_SUPPLY_CHK", 894281), ("CBRK_USB_CHK", 197848),
                      ("SYS_MC_EST_GROUP", 2)):
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                name.encode(), float(val),
                                mavutil.mavlink.MAV_PARAM_TYPE_INT32)
    t0, last, phase, fix_t, base_alt = time.time(), 0.0, "wait_fix", None, None
    while time.time() - t0 < timeout:
        m = conn.recv_match(blocking=True, timeout=2.0)
        if m is None:
            continue
        k, now = m.get_type(), time.time()

        def due(gap=2.0):
            nonlocal last
            if now - last >= gap:
                last = now
                return True
            return False

        if k == "GPS_RAW_INT":
            evidence["fix_type"] = m.fix_type
            if phase == "wait_fix" and m.fix_type >= 3:
                fix_t, phase = now, "settle"
        elif k == "GLOBAL_POSITION_INT":
            alt = m.relative_alt / 1000.0
            evidence["alt_samples"].append(alt)
            base_alt = alt if base_alt is None else base_alt
            evidence["climbed_m"] = max(evidence["climbed_m"], alt - base_alt)
        elif k == "HEARTBEAT":
            armed = bool(m.base_mode & 128)
            evidence["armed"] = evidence["armed"] or armed
            if phase == "settle" and fix_t and now - fix_t >= 8.0:
                phase = "arm"
            elif phase == "arm":
                if armed:
                    conn.mav.command_long_send(
                        conn.target_system, conn.target_component,
                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                        0, 0, 0, 0, float("nan"), 0, 0, alt_m)
                    phase = "climb"
                elif due(1.5):
                    # AUTO.TAKEOFF (main 4, sub 2) first: PX4 will not arm
                    # into a mode it cannot hold, and force-arm (param2=21196)
                    # bypasses the checks a simulator does not need.
                    conn.mav.command_long_send(
                        conn.target_system, conn.target_component,
                        mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        4, 2, 0, 0, 0, 0)
                    conn.mav.command_long_send(
                        conn.target_system, conn.target_component,
                        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        0, 1, 21196, 0, 0, 0, 0, 0)
            elif phase == "climb" and evidence["climbed_m"] >= alt_m * 0.5:
                phase = "flying"
                break
        evidence["phase"] = phase
    return evidence


def fly(conn, platform, alt_m=25.0, timeout=120):
    """Arm and climb, so the airframe is actually in motion while we measure.

    THE PROBE IS INVALID WITHOUT THIS, and the first version of this tool did
    not do it. Measured on a stationary disarmed ArduCopter, nine channels
    read perfectly constant -- battery voltage (no load), GNSS position (not
    moving), barometric altitude (on the ground), armed flag (false) -- and
    the tool reported them as stubs. They are not stubs; nothing was
    happening.

    That is RULE A turned on the instrument itself: an informativeness probe
    needs a positive control. Motion IS the positive control, and
    `motion_observed` below is the evidence that it fired. If the vehicle
    never moved, the run is INVALID_PROBE and no channel verdict is issued.

    Commanding the vehicle is legitimate HERE because this is a simulation
    tool under tools/. Nothing in csia/deploy/ may do this, and a test
    enforces that separation.
    """
    from pymavlink import mavutil
    evidence = {"armed": False, "climbed_m": 0.0, "alt_samples": [],
                "phase": "start", "fix_type": 0}
    if platform == "px4":
        return _fly_px4(conn, evidence, alt_m, timeout)

    for name, val in (("FS_THR_ENABLE", 0), ("FS_GCS_ENABLE", 0),
                      ("FS_OPTIONS", 0), ("BATT_FS_LOW_ACT", 0),
                      ("SIM_SPEEDUP", 10)):
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                name.encode(), float(val),
                                mavutil.mavlink.MAV_PARAM_TYPE_INT32)

    # Sequence copied from the Phase-II rig, which is the version known to
    # work against 4.8: wait for a real 3D fix, let the EKF settle, GUIDED,
    # arm, take off. Arming checks are left ENABLED -- disabling them was the
    # first thing tried and it produced an aircraft that reported armed and
    # never left the ground, which is a worse failure than not arming.
    t0, last, phase, fix_t = time.time(), 0.0, "wait_fix", None
    base_alt = None
    while time.time() - t0 < timeout:
        m = conn.recv_match(blocking=True, timeout=2.0)
        if m is None:
            continue
        k = m.get_type()
        now = time.time()

        def due(gap=2.0):
            nonlocal last
            if now - last >= gap:
                last = now
                return True
            return False

        if k == "GPS_RAW_INT":
            evidence["fix_type"] = m.fix_type
            if phase == "wait_fix" and m.fix_type >= 3:
                fix_t, phase = now, "settle"
        elif k == "GLOBAL_POSITION_INT":
            alt = m.relative_alt / 1000.0
            evidence["alt_samples"].append(alt)
            base_alt = alt if base_alt is None else base_alt
            evidence["climbed_m"] = max(evidence["climbed_m"], alt - base_alt)
        elif k == "HEARTBEAT":
            armed = bool(m.base_mode & 128)
            evidence["armed"] = evidence["armed"] or armed
            if phase == "settle" and fix_t and now - fix_t >= 6.0:
                phase = "guided"
            elif phase == "guided":
                if m.custom_mode == 4:
                    phase = "arm"
                elif due():
                    conn.mav.set_mode_send(
                        conn.target_system,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 4)
            elif phase == "arm":
                if armed:
                    conn.mav.command_long_send(
                        conn.target_system, conn.target_component,
                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                        0, 0, 0, 0, 0, 0, 0, alt_m)
                    phase = "climb"
                elif due(1.0):
                    conn.arducopter_arm()
            elif phase == "climb" and evidence["climbed_m"] >= alt_m * 0.5:
                phase = "flying"
                break
        evidence["phase"] = phase
    return evidence


LAUNCHERS = {"ardupilot": launch_ardupilot, "px4": launch_px4}
