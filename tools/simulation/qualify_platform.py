"""Qualify a live autopilot's telemetry against the semantic contract (S2/S3).

This is the instrument that turns `CHANNEL_SEMANTICS.yaml` from a document
into a measurement. It launches the real simulator, runs the real adapter over
the real stream, and asks of every channel:

    did it arrive?          -> presence
    did it move?            -> INFORMATIVENESS, the property that matters
    does the contract agree?-> contract vs observation, reported side by side

The informativeness probe is the whole point. A channel that arrives on every
tick with an identical value is a stub no matter how healthy the stream looks,
and that is exactly how the ArduPilot SITL ESC current (a hard-coded 0.8 A)
produced a spurious CRITICAL on every clean flight.

Disagreements are reported, never auto-applied. A contract row is a decision;
this tool produces the evidence for changing one, not the change.

  python tools/simulation/qualify_platform.py --platform ardupilot
  python tools/simulation/qualify_platform.py --platform px4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.adapters import get_adapter            # noqa: E402
from csia.aircraft.qualification import default_contract  # noqa: E402
from csia.aircraft.sample import Quality                  # noqa: E402

AP_ROOT = os.environ.get("CSIA_AP_ROOT", "/home/user/ardupilot/ardupilot")
PX4_ROOT = os.environ.get("CSIA_PX4_ROOT", "/home/user/px4")
HOME = "-35.363261,149.165230,584,353"

# A channel is INFORMATIVE only if it varies. The floor is deliberately tiny:
# we are separating "constant" from "not constant", not judging magnitude.
CONSTANT_EPS = 1e-9


def launch_ardupilot(workdir, speedup=10):
    binary = os.path.join(AP_ROOT, "build", "sitl", "bin", "arducopter")
    if not os.path.exists(binary):
        raise SystemExit(f"ArduPilot SITL binary not found: {binary}\n"
                         f"set CSIA_AP_ROOT or build it with "
                         f"./waf configure --board sitl && ./waf copter")
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup), "-w",
         "--home", HOME, "--instance", "0"],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return proc, "tcp:127.0.0.1:5760"


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


def connect(conn_str, platform, timeout=90):
    from pymavlink import mavutil
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


def _scalarize(v):
    """Reduce any channel value to one number for variation testing."""
    if v is None:
        return None
    if isinstance(v, dict):
        nums = [x for x in v.values() if isinstance(x, (int, float))]
        return float(sum(nums)) if nums else None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(abs(hash(v)) % 1000)
    try:
        out = float(np.sum(np.asarray(v, dtype=float)))
    except Exception:
        return None
    # A NaN or inf is not a sample. Letting one through crashed pstdev and,
    # worse, would have let a corrupt value decide a channel's verdict.
    return out if math.isfinite(out) else None


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


def observe(platform, duration_s, conn, adapter):
    """Collect per-channel observations from the live stream."""
    obs = {ch: [] for ch in adapter.contract.channels}
    t0 = time.time()
    msgs = 0
    while time.time() - t0 < duration_s:
        m = conn.recv_match(blocking=True, timeout=2.0)
        if m is None:
            continue
        msgs += 1
        adapter.ingest(m)
        # Read the adapter's own store so a BLOCKED channel is still observed:
        # deciding whether a declared stub really is constant is the evidence
        # the contract row rests on, and a blocked channel never reaches the
        # canonical sample.
        for ch, entry in adapter._latest.items():
            s = _scalarize(entry[0])
            if s is not None:
                obs.setdefault(ch, []).append(s)
    return obs, msgs


def analyse(obs, raw_present, contract):
    rows = []
    for ch, row in sorted(contract.channels.items()):
        vals = obs.get(ch, [])
        n = len(vals)
        if n == 0:
            observed = Quality.UNAVAILABLE
            spread = None
            detail = "never arrived"
        elif row.criterion == "DECODE":
            # A latched enum or boolean. Constancy is its normal state -- a
            # vehicle that stays armed reports the same value all flight --
            # so variation is the wrong criterion. It qualifies by decoding.
            observed = Quality.INFORMATIVE
            detail = (f"latched value {vals[-1]:.6g}, decoded over {n} "
                      f"samples (criterion DECODE, not variation)")
        else:
            spread = (max(vals) - min(vals)) if n > 1 else 0.0
            if spread <= CONSTANT_EPS:
                observed = Quality.STUB_OR_NONINFORMATIVE
                detail = f"constant at {vals[0]:.6g} over {n} samples"
            else:
                observed = Quality.INFORMATIVE
                sd = statistics.pstdev(vals) if n > 2 else spread
                detail = f"range {spread:.6g}, sd {sd:.6g}, n={n}"
        declared = row.quality
        agrees = (observed == declared) or (
            declared in (Quality.VALIDATED_SEMANTICS,
                         Quality.AVAILABLE_UNVALIDATED)
            and observed is Quality.INFORMATIVE)
        rows.append({
            "channel": ch,
            "declared": declared.value,
            "observed": observed.value,
            "agrees": agrees,
            "may_use": row.may_use,
            "admissible": row.admissible,
            "criterion": row.criterion,
            "samples": n,
            "spread": spread,
            "detail": detail,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=sorted(LAUNCHERS),
                    default="ardupilot")
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--speedup", type=int, default=10)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--static", action="store_true",
                    help="skip the motion positive control (probe will be "
                         "reported INVALID_PROBE; for debugging only)")
    args = ap.parse_args()

    workdir = args.workdir or os.path.join(
        ROOT, "build", f"sitl-{args.platform}")
    proc, conn_str = LAUNCHERS[args.platform](workdir, args.speedup)
    print(f"=== {args.platform} SITL launched (pid {proc.pid}) -> {conn_str}")
    try:
        conn = connect(conn_str, args.platform)
        print("=== heartbeat received")
        adapter = get_adapter(args.platform)
        motion = {"armed": False, "climbed_m": 0.0, "alt_samples": []}
        if not args.static:
            print("=== positive control: arming and climbing")
            motion = fly(conn, args.platform)
            print(f"    armed={motion['armed']} "
                  f"climbed={motion['climbed_m']:.1f} m")
        print(f"=== observing {args.seconds:.0f}s")
        obs, msgs = observe(args.platform, args.seconds, conn, adapter)
        rows = analyse(obs, {}, adapter.contract)
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n=== {msgs} messages, {adapter.counters['mapped']} mapped, "
          f"{adapter.counters['unmapped']} unmapped")
    unmapped = adapter.unmapped_types()
    if unmapped:
        top = sorted(unmapped.items(), key=lambda kv: -kv[1])[:8]
        print("    unmapped types: " +
              ", ".join(f"{k}x{v}" for k, v in top))

    print(f"\n{'channel':26s} {'declared':24s} {'observed':24s} agree")
    disagreements = []
    for r in rows:
        mark = "yes" if r["agrees"] else "NO"
        print(f"{r['channel']:26s} {r['declared']:24s} "
              f"{r['observed']:24s} {mark}")
        print(f"{'':26s}   {r['detail']}")
        if not r["agrees"]:
            disagreements.append(r)

    stub_rows = [r for r in rows
                 if r["observed"] == Quality.STUB_OR_NONINFORMATIVE.value
                 and r["samples"] > 0]
    print(f"\n=== observed stubs: {len(stub_rows)}")
    for r in stub_rows:
        flag = "declared" if not r["admissible"] else "*** ADMISSIBLE ***"
        print(f"    {r['channel']:26s} {r['detail']}  [{flag}]")

    admitted_stub = [r for r in stub_rows if r["admissible"]]

    # RULE A on the instrument itself. Without demonstrated motion, "constant"
    # means "nothing happened", not "this channel is a stub", and no channel
    # verdict may be issued from this run.
    probe_valid = bool(motion["armed"] and motion["climbed_m"] >= 1.0)
    if probe_valid:
        verdict = ("FAIL: a stub channel is admissible as evidence"
                   if admitted_stub else "PASS")
    else:
        verdict = ("INVALID_PROBE: the airframe did not move, so constancy "
                   "is uninformative and no channel verdict is issued")

    result = {
        "platform": args.platform,
        "seconds": args.seconds,
        "messages": msgs,
        "counters": adapter.counters,
        "unmapped_types": unmapped,
        "positive_control": {
            "armed": motion["armed"],
            "climbed_m": round(motion["climbed_m"], 2),
            "alt_samples": len(motion["alt_samples"]),
            "satisfied": probe_valid,
            "rule": "RULE A -- an informativeness probe needs a positive "
                    "control; motion is it",
        },
        "PROBE_VALID": probe_valid,
        "rows": rows if probe_valid else [],
        "rows_unscored": [] if probe_valid else rows,
        "disagreements": disagreements if probe_valid else [],
        "observed_stubs": [r["channel"] for r in stub_rows] if probe_valid else [],
        "admissible_stubs": [r["channel"] for r in admitted_stub] if probe_valid else [],
        "verdict": verdict,
    }
    out = args.out or os.path.join(
        ROOT, "research", "v1_1", "results",
        f"qualification_{args.platform}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True, default=str)
    print(f"\n{result['verdict']}")
    print(f"-> {os.path.relpath(out, ROOT)}")
    if not probe_valid:
        return 2
    return 1 if admitted_stub else 0


if __name__ == "__main__":
    sys.exit(main())
