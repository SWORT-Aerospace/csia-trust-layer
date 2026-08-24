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

# Motion positive control: the probe needs the airframe to have MOVED,
# not to have reached a particular altitude. 1.5 m clears the 1.0 m
# threshold qualify_platform requires with margin, and it is reachable
# whatever MIS_TAKEOFF_ALT is set to. Keying success off alt_m * 0.5
# made the loop wait for 12.5 m while PX4 climbed to its 2.5 m default.
CLIMB_OK_M = 1.5


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
    # CAPTURE THE CONSOLE. It was going to DEVNULL.
    #
    # PX4 prints boot progress, preflight failures, mode rejections and
    # takeoff decisions to stdout. Three rounds of hypotheses about a failing
    # climb were spent while that output was being discarded, and a fourth was
    # spent on STATUSTEXT -- which turned out to be dead -- when the console
    # says the same things and needs no MAVLink stream at all.
    console = os.path.join(workdir, "px4_console.log")
    fh = open(console, "wb")
    proc = subprocess.Popen(
        [binary, "-d", "-s", os.path.join(etc, "init.d-posix", "rcS"), etc],
        cwd=workdir, env=env, stdout=fh, stderr=subprocess.STDOUT)
    proc.console_path = console
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
        # 253 STATUSTEXT and 33 GLOBAL_POSITION_INT were both missing.
        #
        # STATUSTEXT is the channel PX4 explains itself on. Without it a
        # capture of PX4's diagnostics returns an empty list, and an empty
        # list from an instrument nobody verified is alive is not a finding --
        # it is the absence of one. That is the RULE A null-control failure,
        # committed while adding a diagnostic FOR a RULE A positive control.
        #
        # 33 is what climbed_m is measured from. It happened to arrive on
        # PX4's default stream set, so the altitude figures were real, but
        # depending on a default nobody requested is luck rather than design.
        for mid, hz in ((105, 50), (26, 25), (29, 10), (24, 5),
                        (147, 10), (241, 10), (230, 5), (0, 1),
                        (253, 10), (33, 10)):
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
    # Parameter TYPE matters. Every one of these used to be sent as INT32,
    # including the four COM_ARM_EKF_* thresholds, which PX4 declares as
    # float. A float parameter written with an integer type is not a rounding
    # error -- the receiver reinterprets the payload, so 1.0 does not arrive
    # as 1.0. Each entry now carries its own type.
    #
    # MIS_TAKEOFF_ALT is the important one and it was missing entirely.
    # PX4's NAV_TAKEOFF handler (Commander.cpp:1205) does NOT read param7:
    # it only switches to NAVIGATION_STATE_AUTO_TAKEOFF. The climb target
    # comes from MIS_TAKEOFF_ALT, a float defaulting to 2.5 m
    # (navigator/mission_params.yaml:5-15). So the rig commanded a takeoff to
    # 25 m, the vehicle aimed for 2.5 m, and the loop waited for
    # alt_m * 0.5 = 12.5 m that could never arrive -- 120 s of timeout
    # reported as "climbed 0.43 m".
    I32 = mavutil.mavlink.MAV_PARAM_TYPE_INT32
    F32 = mavutil.mavlink.MAV_PARAM_TYPE_REAL32
    for name, val, ptype in (
            ("COM_RCL_EXCEPT", 7, I32), ("NAV_RCL_ACT", 0, I32),
            ("NAV_DLL_ACT", 0, I32), ("COM_ARM_WO_GPS", 1, I32),
            ("COM_PREARM_MODE", 0, I32), ("COM_ARM_MAG_STR", 0, I32),
            # COM_ARM_EKF_{HGT,VEL,POS,YAW} and SYS_MC_EST_GROUP are GONE.
            # The PX4 console rejected all five: "ERROR [mavlink] unknown
            # param". They were phantom writes -- the same class as the SR1_*
            # failure -- and the earlier work correcting their wire TYPE was
            # correcting the type of parameters that do not exist.
            ("COM_DISARM_LAND", -1.0, F32), ("COM_DISARM_PRFLT", -1.0, F32),
            ("CBRK_SUPPLY_CHK", 894281, I32), ("CBRK_USB_CHK", 197848, I32),
            ("MIS_TAKEOFF_ALT", float(alt_m), F32)):
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                name.encode(), float(val), ptype)
    # VERIFY the write the takeoff depends on, rather than sleeping and
    # hoping. run_campaign.py:46 already does readback for SIM_ parameters;
    # this path did not, which is the same defect that let eight phantom
    # SR1_* writes look successful for four runs.
    time.sleep(1.0)
    conn.mav.param_request_read_send(conn.target_system,
                                     conn.target_component,
                                     b"MIS_TAKEOFF_ALT", -1)
    t_end = time.time() + 5.0
    while time.time() < t_end:
        m = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=1.0)
        if m is None:
            continue
        pid = m.param_id.decode() if isinstance(m.param_id, bytes) \
            else m.param_id
        if pid.strip("\x00") == "MIS_TAKEOFF_ALT":
            evidence["takeoff_alt_param"] = round(float(m.param_value), 2)
            break
    else:
        evidence["takeoff_alt_param"] = None
    if evidence.get("takeoff_alt_param") is None:
        # Not fatal -- the probe still reports what happened -- but a takeoff
        # target that did not stick is the single most likely reason a climb
        # fails, and silence about it is what cost the last four runs.
        log_note = "MIS_TAKEOFF_ALT did not read back; climb target unknown"
        evidence.setdefault("warnings", []).append(log_note)
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

        if k == "STATUSTEXT":
            # The vehicle's own explanation. Three rounds of hypotheses were
            # spent on this climb without once reading the channel PX4 uses to
            # say what is wrong. Capturing it costs nothing and outranks any
            # guess.
            txt = getattr(m, "text", "")
            txt = txt.decode() if isinstance(txt, bytes) else str(txt)
            txt = txt.strip("\x00").strip()
            if txt:
                seen = evidence.setdefault("statustext", [])
                if txt not in seen:
                    seen.append(txt)
        elif k == "COMMAND_ACK":
            # Evidence, not assumption. A takeoff can be TEMPORARILY_REJECTED
            # (Commander.cpp:1211) and the old code could not tell that apart
            # from a takeoff that was accepted and simply climbed slowly.
            if getattr(m, "command", None) == \
                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
                evidence["takeoff_ack"] = int(getattr(m, "result", -1))
            elif getattr(m, "command", None) == \
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                evidence["arm_ack"] = int(getattr(m, "result", -1))
        elif k == "GPS_RAW_INT":
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
                    # param7 MUST be NaN, not the desired height.
                    #
                    # MAVLink defines NAV_TAKEOFF param7 as an AMSL altitude.
                    # navigator/takeoff.cpp:194 takes it verbatim when finite:
                    #
                    #   if (rep->current.valid && PX4_ISFINITE(rep->current.alt))
                    #       takeoff_altitude_amsl = rep->current.alt;
                    #   else
                    #       takeoff_altitude_amsl = current_alt + MIS_TAKEOFF_ALT;
                    #
                    # and then at :207 clamps anything below the vehicle:
                    #   "Already higher than takeoff altitude".
                    #
                    # Sending 25.0 meant "climb to 25 m above SEA LEVEL". SIH
                    # sits at 489.4 m AMSL (SIH_LOC_H0), so the target was
                    # 464 m underground, got clamped to the current altitude,
                    # and the vehicle correctly did nothing. NaN makes the
                    # navigator use MIS_TAKEOFF_ALT relative to where it is.
                    #
                    # Note the rig's HOME="...,584,..." is an ArduPilot --home
                    # flag and has never applied to PX4; SIH_LOC_H0 is the
                    # PX4 equivalent.
                    conn.mav.command_long_send(
                        conn.target_system, conn.target_component,
                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                        0, 0, 0, 0, float("nan"), 0, 0, float("nan"))
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
            elif phase == "climb" and evidence["climbed_m"] >= CLIMB_OK_M:
                phase = "flying"
                break
        evidence["phase"] = phase
    # NULL CONTROL on the diagnostic channel. PX4 emits boot and mode banners
    # constantly, so zero STATUSTEXT over a whole flight means the stream was
    # never delivered -- not that the vehicle had nothing to say. Recorded so
    # a future reader cannot mistake a deaf instrument for a quiet vehicle.
    if not evidence.get("statustext"):
        evidence.setdefault("warnings", []).append(
            "no STATUSTEXT received: the diagnostic channel is dead, so its "
            "silence carries no information")
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
