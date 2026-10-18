"""Run the SHADOW stack end to end against a live autopilot.

Everything else in the deployment tree is tested against a `FakeConnection`.
This is the first thing that puts the whole chain on real telemetry:

    ArduPilot/PX4 SITL
      -> pymavlink UDP/TCP
      -> ReadOnlyMavlinkConnection   (real socket, real transmit denial)
      -> PlatformAdapter             (real messages, real units, real staleness)
      -> AircraftSample
      -> OnlineTrustLayer            (FROZEN v1)
      -> FailsafePolicy              (recommendations only)
      -> FlightLog                   (a real file on disk)

It answers two questions no unit test can:

  1. Does the pipeline survive a live stream at all -- rates, gaps, message
     types nobody anticipated, a flight controller that reboots?
  2. Does it hold R13 (<= 2 ms per tick) THROUGH THE NEW STACK? The 297-356
     us/tick figure in the freeze document is the OLD ingestion path. The
     adapter and the qualification layer add per-tick work that has never
     been measured.

Latency is reported as a distribution, not a mean. A mean hides the tail, and
the tail is what misses a deadline.

  python tools/deploy/shadow_sitl_check.py --platform ardupilot --seconds 30
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import statistics
import subprocess
import sys
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.deploy.guard import CommandAuthorityError          # noqa: E402
from csia.deploy.shadow import Mode, ShadowConfig, ShadowRunner  # noqa: E402
from csia.simulation.rigs import (                       # noqa: E402
    LAUNCHERS, connect, fly, provenance_string, simulator_provenance)
from csia.simulation.host_noise import (                 # noqa: E402
    measure as measure_host_noise, r13_verdict)
from csia.simulation.tee import MavlinkTee               # noqa: E402

R13_BUDGET_US = 2000.0
# Where the tee publishes and CSIA listens. UDP because a listener
# binding a port cannot accidentally become a client of anything.
TEE_OUT = ("127.0.0.1", 14561)

# THE LINK TOPOLOGY IS PER PLATFORM, and it was not.
#
# `RIG_LINK` was a single constant holding ArduPilot's SERIAL1
# (tcp:127.0.0.1:5762). `--platform px4` was offered and could not run: PX4
# never opens that port, so the harness died with "no TCP listener on
# tcp:127.0.0.1:5762" after launching the simulator and starting the tee.
#
# The two platforms genuinely differ, and measurement decided the shape
# rather than symmetry:
#
#   ArduPilot NEEDS the tee. Stream rates are per-link runtime state
#   established only by a transmit on that link (GCS.h:537,
#   persist_streamrates() == false), and CSIA cannot transmit. Something with
#   authority has to drive SERIAL0; the rig commands on SERIAL1.
#
#   PX4 DOES NOT -- FOR PRESENCE. It runs several mavlink instances, each
#   streaming a full set unprompted. Measured on a live SIH boot, 4 s per link:
#       Normal   bind 14550 -> heartbeat, 29 message types
#       Onboard  bind 14540 -> heartbeat, 35 message types, HIGHRES_IMU 50 Hz
#       Onboard  bind 14030 -> heartbeat, 22 types (4 kB/s cap)
#   So the rig commands on the Normal link and CSIA binds the Onboard link,
#   which is what a companion port IS on a real PX4 vehicle.
#
#   THAT MEASUREMENT COUNTED MESSAGE TYPES, AND RATE IS WHAT DECIDES
#   STALENESS. A 1 Hz message is present in a 4 s window, so a type count
#   cannot tell 1 Hz from 10 Hz, and the conclusion originally drawn here --
#   "interposing a tee would model a constraint the platform does not have" --
#   does not follow from it. Re-measured over 40 s per link, three arms in one
#   simulator run (tools/simulation/px4_link_rate_probe.py):
#
#                          14540 passive   14550 passive   14550 requesting
#       SCALED_PRESSURE       1.000 Hz        0.975 Hz         9.800 Hz
#       BATTERY_STATUS        0.500 Hz        0.475 Hz         9.775 Hz
#       VIBRATION             0.500 Hz        0.100 Hz         9.775 Hz
#
#   PX4 has exactly the constraint ArduPilot has: SET_MESSAGE_INTERVAL is
#   per-link runtime state, in both directions -- requesting on 14550 leaves
#   14540 untouched, and a request sent on 14540 raises 14540 alone (baro
#   1.000 -> 9.825 Hz) while 14550 stays at 0.975. What differs is only the
#   DEFAULT: ArduPilot's unprompted link carries no sensor data at all, while
#   PX4's carries all of it slowly. Slowly is still a defect, because
#   max_age = MAX_AGE_MARGIN / declared_rate is derived from a contract number
#   measured on the REQUESTING link, so baro gets a 0.50 s budget against a
#   1.00 s arrival and is stale on half of all ticks. Measured downstream:
#   the baro node was fresh on 8.2 % of PX4 ticks and `altitude_baro` carried
#   weight on 8.1 %, against 99.9 % on ArduPilot.
#
#   NOT FIXED HERE, deliberately. The fix is to give PX4 the same driven link
#   ArduPilot has (the tee, with a SET_MESSAGE_INTERVAL profile instead of
#   MAV_DATA_STREAM_*), and CSIA still must not transmit. That changes how
#   flights are captured, so it is a decision to take explicitly rather than
#   a side effect of a comment correction. Recorded in
#   research/v1_1/PX4_LINK_RATE_FINDING.md.
RIG_LINKS = {
    "ardupilot": "tcp:127.0.0.1:5762",     # SERIAL1
    "px4": "udp:127.0.0.1:14550",          # Normal instance (the GCS link)
}
# Where CSIA listens when the platform needs no tee.
DIRECT_PASSIVE = {
    "px4": "udpin:127.0.0.1:14540",        # Onboard instance -- the companion port
}
NEEDS_TEE = {"ardupilot": True, "px4": False}

# MECHANISM A: remove the GNSS fix, mid-flight, from the RIG's link.
#
# Both interventions were read out of the simulator source before being used,
# because an injection nobody verified is an assumption:
#
#   ArduPilot  SITL's GPS parameter group carries ENABLE
#              (SIM_GPS.cpp:42, AP_PARAM_FLAG_ENABLE), runtime-settable.
#   PX4        SENS_EN_GPSSIM is reboot_required:true and therefore USELESS
#              in flight. SIM_GPS_USED is not, and SensorGpsSim.cpp:155-167
#              reads:
#                   if (_sim_gps_used.get() >= 4) fix_type = 3;
#                   else                          fix_type = 0;
#              so driving it to 0 produces a genuine no-fix condition.
#
# The rig sends this, never CSIA. It is the same authority that arms and
# climbs, and CSIA's connection remains structurally unable to transmit.
#
# RULE B: the injection is not the measurement. The INTERMEDIATE QUANTITY --
# gnss.position going MISSING with NO_3D_FIX -- is recorded per tick in the
# flight log, and an injection that did not produce it is a failed trial
# rather than a result.
#
# THE PARAMETER TYPE IS PART OF THE INTERVENTION, not a detail.
#
# The first PX4 arm sent SIM_GPS_USED as REAL32. PX4 stores it as INT32, so
# the write was ignored, no PARAM_VALUE came back, the fix never dropped, and
# the arm produced a null result that would have read as "PX4 does not show
# the mechanism". A parameter readback proved otherwise: PX4 echoed
# SIM_GPS_USED = 1.401298464324817e-44, the float32 reinterpretation of the
# integer 10, and SENS_EN_GPSSIM = 1.401298464324817e-45, i.e. integer 1.
#
# This is the same type defect fixed in `_fly_px4` this morning, reintroduced
# in new code with the sign reversed. ArduPilot's MAVLink parameter interface
# is float-based and REAL32 works there; PX4's is typed and does not.
#
# MECHANISM B: `mag_emi`, a constant hard-iron offset on the magnetometer.
#
# Preregistered in research/v1_1/MECHANISM_B_MAG_EMI_PREREGISTRATION.md, committed
# before any trial ran. Fix loss CANNOT test the history/threshold-crossing
# mechanism -- self-occlusion removes the evidence, the node never moves, and
# there is no crossing to time. `mag_emi` is the one injection available on
# both current simulators that PRESERVES the evidence: the channel keeps
# arriving, every mag gate stays open, and the residuals move instead of
# disappearing.
#
# The two deltas are chosen so the PUBLISHED FIELD MOVES IDENTICALLY on both
# platforms -- +u uT on each FRD axis -- which is what makes the arms
# comparable at all:
#
#   ArduPilot  SIM_MAG1_OFS_{X,Y,Z}, milligauss (SITL.h:204, boot default
#              (5,13,-18) at SITL.h:156). AP_Compass_SITL.cpp:124 SUBTRACTS
#              it, and the compensating COMPASS_OFS is written once at
#              construction (:30-32) and never re-synced, so a runtime change
#              is not re-absorbed by calibration. Adapter converts mgauss ->
#              uT with x0.1 (ardupilot.py:148), hence delta = -10*u.
#   PX4        SIM_MAG_OFFSET_{X,Y,Z}, gauss, ParamFloat (SensorMagSim.hpp:
#              101-103), no reboot_required, and SensorMagSim.cpp:113-118
#              calls updateParams() on parameter_update so the write is live.
#              :153-155 ADDS it. Adapter converts gauss -> uT with x100
#              (px4.py:126), hence delta = +u/100. The module runs because
#              airframe 10040_sihsim_quadx:17 sets SENS_EN_MAGSIM 1, and SIH
#              itself publishes no magnetometer.
#
# The write is RELATIVE to the parameter's current value, read back from the
# vehicle first. That is what makes u = 0 a genuine no-op null control rather
# than a small perturbation -- ArduPilot's boot default is not zero.
#
# RULE B for this injection is NOT the readback. It is the observed
# `mag.field_ut` vector shift of u*sqrt(3) uT across the injection instant,
# which is exact and attitude-independent because the offset is a constant
# body-frame vector.
INJECTIONS = {
    "gps_fix_loss": {
        "ardupilot": ("SIM_GPS1_ENABLE", 0, "REAL32"),
        "px4": ("SIM_GPS_USED", 0, "INT32"),
    },
}

#
# MECHANISM B (authoritative): `gps_glitch`, a FIX-PRESERVING GNSS position
# offset. Preregistered in research/v1_1/CURRENT_STACK_REPLICATION.md, blob
# 0e186117e2dcc014862872934768e06e0a195592, committed before the first trial.
#
# ArduPilot: SIM_GPS1_GLTCH_X, degrees of latitude, REAL32.
#   SIM_GPS.cpp:70-75  AP_GROUPINFO("GLTCH", 6, GPSParms, glitch, 0) -- a
#                      Vector3f in the PER-INSTANCE group, hence SIM_GPS1_.
#   SIM_GPS.cpp:581-583  d.latitude += glitch_offsets.x   (degrees)
#                        d.longitude += glitch_offsets.y  (degrees)
#                        d.altitude += glitch_offsets.z   (metres)
#   NOT SIM_GPS_GLITCH: SITL.cpp:681 records "// 6 was GPS_GLITCH", i.e. the
#   old name was removed and a write to it lands nowhere. The preregistration
#   calls this out explicitly.
#
# Fix type and satellite count are untouched, so `gvalid` stays 1 and the
# evidence the mechanism needs remains applicable. That is the whole point:
# fix loss closes the gate and turns this into a Mechanism A trial.
#
# WHY THE RESIDUAL IS IMMUNE TO THE AIRFRAME'S RESPONSE. online.py:364,562:
#   _gps_fd_vel = (pos - ppos)/dt        finite difference of REPORTED position
#   r_raw       = _gps_fd_vel - vel      minus the receiver's DOPPLER velocity
# The glitch adds to position only, never to velocity, so r_raw equals the
# glitch RATE regardless of what the vehicle physically does while chasing the
# offset. A position glitch on a position-controlling vehicle always provokes
# real motion; here that motion cancels out of the residual exactly.
#
# PX4 has no equivalent -- four candidate routes were read out of source and
# all four fail (preregistration section 2.1). It is declared INAPPLICABLE.
#
# Authalic Earth radius, the one ArduPilot itself uses in this file
# (SIM_GPS.cpp:548, earth_rad_inv = 1.569612305760477e-7 -> R = 6371000 m).
METRES_PER_DEG_LAT = 111194.92664455873          # pi/180 * 6371000

GPS_GLITCH = {
    "ardupilot": ("SIM_GPS1_GLTCH_X", "REAL32", 1.0 / METRES_PER_DEG_LAT),
}

# platform -> (parameter stems, MAV type, delta in native units per uT)
MAG_EMI = {
    "ardupilot": (("SIM_MAG1_OFS_X", "SIM_MAG1_OFS_Y", "SIM_MAG1_OFS_Z"),
                  "REAL32", -10.0),      # milligauss, subtracted by SITL
    "px4": (("SIM_MAG_OFFSET_X", "SIM_MAG_OFFSET_Y", "SIM_MAG_OFFSET_Z"),
            "REAL32", 0.01),             # gauss, added by SensorMagSim
}

# MAVLink reports an INT32 parameter's value in a float field, bit-for-bit.
# Comparing that float against the integer you sent always fails.
_INT_PARAM_TYPES = None


def decode_param_value(msg):
    """Return a parameter's value with its declared type honoured."""
    import struct
    from pymavlink import mavutil as _mv
    global _INT_PARAM_TYPES
    if _INT_PARAM_TYPES is None:
        _INT_PARAM_TYPES = {
            getattr(_mv.mavlink, f"MAV_PARAM_TYPE_{n}")
            for n in ("UINT8", "INT8", "UINT16", "INT16", "UINT32", "INT32")
            if hasattr(_mv.mavlink, f"MAV_PARAM_TYPE_{n}")}
    value = float(msg.param_value)
    if getattr(msg, "param_type", None) in _INT_PARAM_TYPES:
        return float(struct.unpack("<i", struct.pack("<f", value))[0])
    return value


# THE FIRST PARAM_VALUE TO ARRIVE IS NOT THE ANSWER TO YOUR REQUEST.
#
# Measured on a live ArduPilot SITL: after three PARAM_SET frames the vehicle
# applied all three correctly, and a readback that matched the first arriving
# PARAM_VALUE per name reported the OLD values for two of them. ArduPilot
# broadcasts PARAM_VALUE acks on a lag of more than a second, interleaved with
# unrelated parameters (INS_GYROFFS_*, ARMING_SKIPCHK, EK3_SRC1_POSXY ...), so
# a queued ack from before the write is what a naive read matches.
#
# The failure mode is the dangerous direction: a correctly applied injection
# reported as NOT CONFIRMED, i.e. a real effect discarded as a failed trial.
# It cost one harness verification run to find, which is what harness
# verification runs are for.
def _param_name(msg):
    pid = msg.param_id
    pid = pid.decode() if isinstance(pid, bytes) else str(pid)
    return pid.strip("\x00")


def _drain(conn, budget_s=0.5):
    """Discard buffered PARAM_VALUE traffic so a stale ack cannot be matched."""
    deadline = time.time() + budget_s
    while time.time() < deadline:
        if conn.recv_match(type="PARAM_VALUE", blocking=False) is None:
            return


def read_param(conn, name, timeout=5.0, settle=0.6):
    """Read one parameter, honouring its declared type. None on timeout.

    Returns the LAST matching value seen within `settle` of the previous one,
    not the first, for the reason above.
    """
    _drain(conn)
    conn.mav.param_request_read_send(
        conn.target_system, conn.target_component, name.encode(), -1)
    last, last_t = None, None
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.2)
        if m is None:
            if last is not None and time.time() - last_t >= settle:
                break
            continue
        if _param_name(m) == name:
            last, last_t = decode_param_value(m), time.time()
    return last


def confirm_param(conn, name, target, timeout=10.0):
    """Poll until the vehicle reports `name` == `target`, or give up.

    Polling rather than a single read because the ack lag is longer than any
    reasonable single-shot timeout. This waits for the vehicle's own report to
    catch up with a write; it never substitutes the commanded value for an
    observed one, and a timeout returns the last value actually seen together
    with False.
    """
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        seen = read_param(conn, name, timeout=min(3.0, max(0.5,
                                                           deadline - time.time())))
        if seen is not None:
            last = seen
            if abs(seen - target) <= 1e-4 * max(1.0, abs(target)):
                return last, True
    return last, False


def prepare_mag_emi(conn, platform, micro_tesla):
    """Read the current offsets and compute the targets. BEFORE the run.

    Relative to the current value because u = 0 has to be a genuine no-op
    write: ArduPilot's boot default for SIM_MAG1_OFS is (5, 13, -18) mG, so
    writing zeros would itself be a perturbation and the null control would
    not be null.

    THIS RUNS AT SETUP, NOT AT THE INJECTION INSTANT. A robust read costs
    about 0.8 s per axis, and doing the three reads inside the injection timer
    put the actual field step 2.5 s after the commanded time -- measured, on a
    harness verification run. Since the injection instant is what N_obs is
    counted from, that offset would have gone straight into E2 as a 62-tick
    error attributed to the mechanism. The offsets are static before the
    injection, so reading them early costs nothing and removes the skew.
    """
    stems, _ptype, per_ut = MAG_EMI[platform]
    delta = per_ut * float(micro_tesla)
    before = {name: read_param(conn, name) for name in stems}
    return {"stems": stems, "before": before, "delta": delta,
            "target": {n: (None if v is None else v + delta)
                       for n, v in before.items()}}


def fire_mag_emi(conn, platform, plan):
    """Send the three writes back-to-back, then confirm. Returns the record.

    THE WRITE BURST IS ATOMIC ON PURPOSE. E2 asks whether a closed form
    derived for a STEP predicts the crossing; three writes spread over
    hundreds of milliseconds would be a staircase, i.e. a different question.
    `write_burst_ms` records how close to atomic it actually was rather than
    assuming, and confirmation happens afterwards so it cannot delay the step.
    """
    from pymavlink import mavutil as _mv
    stems, ptype, _per_ut = MAG_EMI[platform]
    mav_ptype = getattr(_mv.mavlink, f"MAV_PARAM_TYPE_{ptype}")
    target = plan["target"]

    t_burst = time.time()
    for name in stems:
        if target[name] is None:
            continue
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                name.encode(), float(target[name]), mav_ptype)
    burst_ms = (time.time() - t_burst) * 1e3

    axes, ok = [], True
    for name in stems:
        if target[name] is None:
            after, good = None, False
        else:
            after, good = confirm_param(conn, name, target[name])
        ok = ok and good
        axes.append({"param": name, "before": plan["before"][name],
                     "commanded": target[name], "readback": after,
                     "confirmed": bool(good)})
    u = abs(plan["delta"] / MAG_EMI[platform][2])
    return {"axes": axes, "confirmed": bool(ok),
            "micro_tesla_per_axis": round(u, 6),
            "native_delta_per_axis": plan["delta"],
            "native_unit": "mgauss" if platform == "ardupilot" else "gauss",
            "write_burst_ms": round(burst_ms, 3),
            "wrote_at_wall": t_burst,
            "expected_field_shift_ut": round(u * 3 ** 0.5, 6)}


def prepare_gps_glitch(conn, platform, metres):
    """Read the base parameter and compute the target. RUNS AT SETUP.

    THE READ MUST NOT HAPPEN INSIDE THE INJECTION TIMER. A robust parameter
    read costs the better part of a second -- it drains, requests, and waits
    out ArduPilot's ack lag -- and doing it in the timer callback put the
    actual write 2.487 s after the commanded 20.0 s onset in the completed
    campaign. That campaign remains valid because its analysis counted from
    the RECORDED write time rather than the commanded one, but the defect is
    real: a ramp starts late, and on a window shorter than onset + ramp_s it
    would run off the end of the run.

    Same defect, same fix as `prepare_mag_emi`. The parameter is static before
    onset, so reading it early costs nothing.
    """
    name, ptype, per_m = GPS_GLITCH[platform]
    base = read_param(conn, name)
    return {
        "param": name, "param_type": ptype, "per_m": per_m,
        "base": base, "metres": float(metres),
        "target_final": (None if base is None
                         else base + per_m * float(metres)),
    }


def run_gps_glitch(conn, platform, plan, ramp_s, at_s, t_ref, result,
                   cancel=None, hz=5.0):
    """Drive SIM_GPS1_GLTCH_X on a preregistered schedule. Records the truth.

    `ramp_s == 0` is the step condition: one write. Otherwise the offset is
    ramped linearly to `plan["metres"]` over `ramp_s` seconds and then HELD,
    written at the simulated receiver's own 5 Hz (SIM_GPS.cpp:81) so the
    commanded value changes no faster than the GPS publishes.

    NO PARAMETER READS HAPPEN HERE -- see `prepare_gps_glitch`. The callback
    does nothing but send the write sequence, so the gap between the commanded
    onset and the first write is a scheduler artefact of milliseconds rather
    than seconds. Both times are recorded separately (`commanded_at_s` and
    `wrote_at_rel_s`) so the analysis never has to assume they agree.

    `cancel` is a `threading.Event`. The ramp checks it before every write and
    before every sleep, so teardown can actually stop a ramp in progress --
    `Timer.cancel()` cannot, because by then the callback is already running.

    The schedule this function executes IS the fault truth. It is written into
    the result so the analysis reads truth from the injection, never from the
    layer under test.
    """
    from pymavlink import mavutil as _mv
    name, ptype, per_m = plan["param"], plan["param_type"], plan["per_m"]
    base, metres = plan["base"], plan["metres"]
    mav_ptype = getattr(_mv.mavlink, f"MAV_PARAM_TYPE_{ptype}")
    result["injection"]["commanded_at_s"] = at_s
    if base is None:
        result["injection"]["confirmed"] = False
        result["injection"]["error"] = f"could not read {name} at setup"
        return
    result["injection"]["before"] = base

    schedule, cancelled = [], False

    def _write(metres_now):
        target = base + per_m * metres_now
        conn.mav.param_set_send(conn.target_system, conn.target_component,
                                name.encode(), float(target), mav_ptype)
        schedule.append({"t_rel": round(time.time() - t_ref, 4),
                         "metres": round(metres_now, 6),
                         "param_value": target})

    def _stop():
        return cancel is not None and cancel.is_set()

    if ramp_s <= 0.0:
        if not _stop():
            _write(metres)
        else:
            cancelled = True
    else:
        n = int(round(ramp_s * hz))
        t0 = time.time()
        for i in range(1, n + 1):
            if _stop():
                cancelled = True
                break
            _write(metres * i / n)
            # absolute schedule, so a slow write cannot make the ramp drift
            nxt = t0 + i / hz
            while True:
                gap = nxt - time.time()
                if gap <= 0:
                    break
                if _stop():
                    cancelled = True
                    break
                # short naps so cancellation is honoured promptly rather than
                # after a whole inter-write interval
                time.sleep(min(gap, 0.05))
            if cancelled:
                break
    result["injection"]["schedule"] = schedule
    result["injection"]["ramp_s"] = ramp_s
    result["injection"]["metres"] = metres
    result["injection"]["cancelled"] = cancelled
    result["injection"]["writes"] = len(schedule)
    result["injection"]["wrote_at_rel_s"] = (schedule[0]["t_rel"]
                                             if schedule else None)
    if cancelled:
        # A cancelled injection did not execute its declared schedule and is
        # not a trial. Say so in the artifact rather than leaving a short
        # schedule to be read as a complete one.
        result["injection"]["confirmed"] = False
        result["injection"]["error"] = (
            f"injection cancelled after {len(schedule)} of "
            f"{int(round(ramp_s * hz)) if ramp_s > 0 else 1} writes")
        print(f"    [t+{at_s:.1f}s] gps_glitch CANCELLED after "
              f"{len(schedule)} writes")
        return

    # Readback AFTER the schedule finishes, against the final commanded value.
    final = plan["target_final"]
    seen, good = confirm_param(conn, name, final)
    result["injection"]["readback"] = seen
    result["injection"]["commanded_final"] = final
    result["injection"]["confirmed"] = bool(good)
    print(f"    [t+{at_s:.1f}s] gps_glitch {metres} m over {ramp_s} s: "
          f"{name} {base} -> {final} ({len(schedule)} writes); readback="
          f"{seen} -> {'CONFIRMED' if good else 'NOT CONFIRMED'}")


def start_tee_process(source, out_addr, platform, profile, status_path,
                      timeout=30.0, min_types=5):
    """Run the tee in its own interpreter and wait for real traffic.

    The positive control is unchanged in substance and is now read from the
    tee's status file instead of an attribute: "did the feed carry sensor
    data before we started timing" is the question, and a separate process
    cannot be interrogated by touching `self.stats`.
    """
    if os.path.exists(status_path):
        os.unlink(status_path)
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    cmd = [sys.executable, "-m", "csia.simulation.tee",
           "--source", source, "--out", f"{out_addr[0]}:{out_addr[1]}",
           "--platform", platform, "--profile", profile,
           "--status", status_path]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    deadline = time.time() + timeout
    seen = 0
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"tee process exited early (rc {proc.returncode})")
        try:
            with open(status_path, encoding="utf-8") as fh:
                seen = len(json.load(fh).get("by_type", {}))
        except (OSError, ValueError):
            seen = 0
        if seen >= min_types:
            return proc, seen
        time.sleep(0.5)
    proc.kill()
    raise SystemExit(
        f"tee process never carried sensor traffic ({seen} message types). "
        f"Without it this run would measure an idle loop again.")


def summarise(latencies):
    if not latencies:
        return {}
    s = sorted(latencies)

    def pct(p):
        return s[min(len(s) - 1, int(len(s) * p))]

    return {
        "n": len(s),
        "min_us": round(s[0], 2),
        "median_us": round(statistics.median(s), 2),
        "mean_us": round(statistics.fmean(s), 2),
        "p95_us": round(pct(0.95), 2),
        "p99_us": round(pct(0.99), 2),
        "max_us": round(s[-1], 2),
        "budget_us": R13_BUDGET_US,
        "over_budget": sum(1 for x in s if x > R13_BUDGET_US),
        "worst_headroom_x": round(R13_BUDGET_US / s[-1], 2) if s[-1] else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=sorted(LAUNCHERS),
                    default="ardupilot")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--speedup", type=int, default=1)
    ap.add_argument("--fly", action="store_true",
                    help="arm and climb first, so the stack sees a moving "
                         "airframe rather than a parked one")
    ap.add_argument("--stream-profile", choices=("full", "companion"),
                    default="full",
                    help="companion = only the streams CSIA reads")
    ap.add_argument("--tee-mode", choices=("process", "thread"),
                    default="process",
                    help="process (default) runs the tee in its own "
                         "interpreter so it cannot steal GIL time from the "
                         "tick being measured; thread is the old in-process "
                         "arrangement, kept as the null control that shows "
                         "the difference")
    ap.add_argument("--inject",
                    choices=sorted(INJECTIONS) + ["mag_emi", "gps_glitch"],
                    default=None,
                    help="fault to inject mid-run, sent on the RIG's link")
    ap.add_argument("--glitch-m", type=float, default=0.0,
                    help="gps_glitch magnitude in metres of latitude; 0.0 is "
                         "the clean control (no parameter written)")
    ap.add_argument("--glitch-ramp-s", type=float, default=0.0,
                    help="0 = step; >0 ramps linearly to --glitch-m over this "
                         "many seconds and then holds")
    ap.add_argument("--hold-mode", default=None,
                    help="flight mode to switch to after the climb, before "
                         "the scored window. ALT_HOLD keeps the airframe out "
                         "of the GNSS position loop so a position glitch is "
                         "not cancelled by the vehicle chasing it")
    ap.add_argument("--inject-at", type=float, default=12.0,
                    help="seconds into the shadow window to inject")
    ap.add_argument("--emi-ut", type=float, default=0.0,
                    help="mag_emi magnitude in microtesla PER BODY AXIS; 0.0 "
                         "is the null control (the write happens, the field "
                         "does not move)")
    ap.add_argument("--trust-trace", default=None,
                    help="write one row per ENGINE STEP to this path -- the "
                         "flight log keeps only the last step of each shadow "
                         "tick and cannot reconstruct a recursion")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    workdir = os.path.join(ROOT, "build", f"shadow-{args.platform}")
    logdir = os.path.join(ROOT, "logs", f"shadow-sitl-{args.platform}")
    proc, conn_str = LAUNCHERS[args.platform](workdir, args.speedup)
    print(f"=== {args.platform} SITL launched (pid {proc.pid}) -> {conn_str}")

    result = {"platform": args.platform, "seconds": args.seconds}
    # EVERY NAME THE `finally` BLOCK TOUCHES IS BOUND HERE, before the try.
    # They used to be assigned inside it, so any failure before the injection
    # was set up -- a SITL launch that never came up, a tee that would not
    # start, a refused connection -- reached teardown with `inject_timer`
    # undefined and raised NameError there. That was papered over with an
    # `except NameError: pass`, which also swallows a genuine NameError from a
    # real bug in teardown and turns it into a silent skipped cleanup.
    tee = None
    tee_proc = None
    status_path = None
    inject_timer = None
    glitch_cancel = None
    try:
        # The rig holds the COMMAND link (SERIAL0) for the whole run. It is
        # what asks the autopilot to stream, because a shadow monitor cannot:
        # request_data_stream_send is a transmit, and the guard denies it. On
        # a real aircraft that request comes from the GCS or from the FC's own
        # SR*_ parameters -- see docs/deployment/AIRCRAFT_INTEGRATION.md.
        # It is NOT closed early: the streams stop when the requester leaves.
        # THE TELEMETRY TEE. This is what makes an R13 measurement possible.
        #
        # Stream rates are per-link and require a transmit on that link, and
        # CSIA cannot transmit. So the tee takes the GCS role: it holds
        # SERIAL0, requests the streams there, and forwards every byte to a
        # UDP endpoint that CSIA merely listens on. CSIA never asks for
        # anything -- it reads a feed someone else established, which is what
        # a tee is on a real aircraft.
        #
        # The rig commands on SERIAL1 instead. Commands work on any link;
        # only STREAMS are per-link, which is precisely the distinction that
        # took four runs to establish.
        #
        # OUT OF PROCESS BY DEFAULT. The tee used to run as a thread here, and
        # under the GIL every byte it decoded was time stolen from the tick
        # this script exists to time. Controlled measurement, synthetic tick
        # against N competing GIL threads: 679.5 us at 0, 954.6 us at 1,
        # 1598.3 us at 2 -- against a live figure of ~1590 us. Most of the R13
        # FAIL was the instrument.
        #
        # It is also the faithful arrangement: on a real aircraft the tee is
        # the GCS or a UART split, never a thread inside CSIA.
        types = None
        if not NEEDS_TEE.get(args.platform, True):
            print(f"=== no tee: {args.platform} streams a full set on every "
                  f"mavlink instance without being asked, so CSIA binds a "
                  f"separate link directly (measured: 35 message types)")
        elif args.tee_mode == "process":
            status_path = os.path.join(workdir, "tee_status.json")
            tee_proc, types = start_tee_process(
                conn_str, TEE_OUT, args.platform, args.stream_profile,
                status_path)
            print(f"=== tee: {conn_str} -> udp {TEE_OUT}  "
                  f"({types} message types flowing, pid {tee_proc.pid}, "
                  f"SEPARATE INTERPRETER)")
        else:
            tee = MavlinkTee(conn_str, [TEE_OUT], platform=args.platform,
                             profile=args.stream_profile)
            tee.start()
            if not tee.wait_for_traffic(min_types=5, timeout=25.0):
                raise SystemExit(
                    f"tee never carried sensor traffic: "
                    f"{sorted(tee.stats['by_type'])}. Without it this run "
                    f"would measure an idle loop again.")
            types = len(tee.stats["by_type"])
            print(f"=== tee: {conn_str} -> udp {TEE_OUT}  "
                  f"({types} message types flowing, IN-PROCESS THREAD -- "
                  f"this contends for the GIL with the measured tick)")
        if NEEDS_TEE.get(args.platform, True):
            result["tee"] = {
                "source": conn_str, "out": f"{TEE_OUT[0]}:{TEE_OUT[1]}",
                "profile": args.stream_profile, "mode": args.tee_mode,
                "shares_interpreter_with_csia": args.tee_mode == "thread",
                "types_flowing_before_measurement": types}
        else:
            result["tee"] = {
                "used": False,
                "reason": "this platform streams a full set on every mavlink "
                          "instance unprompted; CSIA binds a separate link "
                          "directly, which is what a companion port is",
                "csia_link": DIRECT_PASSIVE[args.platform]}
        rig_conn = connect(RIG_LINKS[args.platform], args.platform)

        print(f"=== rig commands on {RIG_LINKS[args.platform]}"
              + (" (streams are per-link)"
                 if NEEDS_TEE.get(args.platform, True) else ""))
        if args.fly:
            print("=== rig: arming and climbing (rig authority, not CSIA)")
            ev = fly(rig_conn, args.platform)
            print(f"    armed={ev['armed']} climbed={ev['climbed_m']:.2f} m")
            result["rig_flight"] = {"armed": ev["armed"],
                                    "climbed_m": round(ev["climbed_m"], 2)}
            # Carry the rig's own parameter verification into the result. It
            # was being computed and discarded, which is the same failure as
            # not checking: a verification nobody can read afterwards cannot
            # be used to judge whether a trial was valid.
            for k in ("failsafe_params", "takeoff_alt_param",
                      "takeoff_alt_confirmed", "warnings"):
                if k in ev:
                    result["rig_flight"][k] = ev[k]
            bad = [w for w in (ev.get("warnings") or [])]
            if bad:
                print("    !! rig parameter warnings: " + "; ".join(bad))
            if args.hold_mode:
                # WHY THIS EXISTS. A GNSS position glitch on a vehicle that
                # controls position from GNSS is cancelled by the vehicle:
                # measured on a harness run, a commanded 50 m ramp produced
                # only 1.55 m of reported offset because the airframe flew
                # ~48 m the other way chasing it. That is an indirect
                # COMMANDED AIRFRAME DISPLACEMENT, which the preregistration's
                # Type row excludes, and it also makes the declared downstream
                # observable ("receiver reports the offset position")
                # unmeasurable. ALT_HOLD keeps the airframe out of the GNSS
                # position loop, so the offset stays in the reported position
                # where it can be observed. RC and GCS failsafes are already
                # disabled by fly().
                mid = rig_conn.mode_mapping().get(args.hold_mode)
                if mid is None:
                    raise SystemExit(f"unknown flight mode {args.hold_mode!r}")
                rig_conn.set_mode(mid)
                seen, deadline = None, time.time() + 15.0
                while time.time() < deadline:
                    m = rig_conn.recv_match(type="HEARTBEAT", blocking=True,
                                            timeout=1.0)
                    if m is not None and m.custom_mode == mid:
                        seen = args.hold_mode
                        break
                result["rig_flight"]["hold_mode"] = args.hold_mode
                result["rig_flight"]["hold_mode_confirmed"] = seen is not None
                print(f"    hold mode {args.hold_mode} -> "
                      f"{'CONFIRMED' if seen else 'NOT CONFIRMED'}")
                if seen is None:
                    raise SystemExit(
                        f"vehicle did not enter {args.hold_mode}; a trial "
                        f"flown in the wrong mode is not a trial")

        from pymavlink import mavutil

        passive = (f"udpin:{TEE_OUT[0]}:{TEE_OUT[1]}"
                   if NEEDS_TEE.get(args.platform, True)
                   else DIRECT_PASSIVE[args.platform])
        print(f"=== CSIA listens (read-only) on {passive}")

        def factory():
            # The TEED feed. Bound, never dialled; CSIA only listens.
            c = mavutil.mavlink_connection(passive)
            c.wait_heartbeat(timeout=60)
            return c

        cfg = ShadowConfig(platform=args.platform, connection=passive,
                           mode=Mode.SHADOW, tick_hz=25.0, log_dir=logdir,
                           max_runtime_s=args.seconds,
                           # NOT args.platform. That field is the flight
                           # log's firmware provenance and its own test uses
                           # "4.8.0-dev@01a504b"; passing the platform name
                           # recorded a constant where the build belonged.
                           autopilot_version=provenance_string(args.platform),
                           trust_trace_path=args.trust_trace)
        runner = ShadowRunner(cfg, connection_factory=factory)
        runner.connect()
        print(f"=== command authority: "
              f"{runner.authority_evidence['result']} "
              f"(write_half={runner.authority_evidence.get('write_half_state')})")

        # An adversarial probe on the LIVE socket: prove the real connection
        # refuses to transmit, not just the fake one in the unit tests.
        denied = []
        for call in ("command_long_send", "set_mode_send",
                     "rc_channels_override_send"):
            try:
                getattr(runner.conn.mav, call)(1, 1, 400, 0, 1, 0, 0)
                denied.append(f"{call}: REACHED THE WIRE")
            except CommandAuthorityError:
                denied.append(f"{call}: denied")
        print("=== live transmit probe: " + "; ".join(denied))
        result["live_transmit_probe"] = denied

        if args.inject == "gps_glitch":
            if args.platform not in GPS_GLITCH:
                raise SystemExit(
                    f"gps_glitch is INAPPLICABLE on {args.platform}: no "
                    f"fix-preserving position offset exists (see "
                    f"research/v1_1/CURRENT_STACK_REPLICATION.md section 2.1). "
                    f"The preregistration forbids substituting another "
                    f"intervention.")
            t_ref = [None]
            # Reads happen HERE, before the window opens, so the timer
            # callback does nothing but write. See prepare_gps_glitch.
            glitch_plan = prepare_gps_glitch(rig_conn, args.platform,
                                             args.glitch_m)
            glitch_cancel = threading.Event()
            print(f"=== gps_glitch prepared: {glitch_plan['param']} "
                  f"base={glitch_plan['base']} "
                  f"target={glitch_plan['target_final']}")

            def _inject_glitch():
                run_gps_glitch(rig_conn, args.platform, glitch_plan,
                               args.glitch_ramp_s, args.inject_at,
                               t_ref[0], result, cancel=glitch_cancel)
            result["injection"] = {
                "kind": "gps_glitch", "at_s": args.inject_at, "sent_by": "rig",
                "param": GPS_GLITCH[args.platform][0],
                "param_type": GPS_GLITCH[args.platform][1],
                "metres": args.glitch_m, "ramp_s": args.glitch_ramp_s,
                "metres_per_deg_lat": METRES_PER_DEG_LAT,
                "arm": ("CLEAN CONTROL (no parameter written)"
                        if args.glitch_m == 0.0 else
                        ("RAMP" if args.glitch_ramp_s > 0 else "STEP")),
                "rule": "RULE B -- the intermediate quantity is the reported "
                        "gnss.position offset with fix type and satellite "
                        "count unchanged and gvalid still 1, not the write",
                "prereg": "research/v1_1/CURRENT_STACK_REPLICATION.md",
                "prereg_blob":
                    "0e186117e2dcc014862872934768e06e0a195592",
            }
            if args.glitch_m == 0.0:
                # The clean control writes NOTHING. Section 3 calls for an
                # identical flight with no parameter applied, so there is no
                # write to make and none is made.
                result["injection"]["confirmed"] = None
                result["injection"]["commanded_at_s"] = args.inject_at
            else:
                t_ref[0] = time.time()
                inject_timer = threading.Timer(args.inject_at, _inject_glitch)
                inject_timer.daemon = True
                inject_timer.start()
        elif args.inject == "mag_emi":
            # MECHANISM B. Three parameters, written relative to their current
            # values, so u = 0 is a real no-op write and not a small
            # perturbation of ArduPilot's non-zero boot default. The reads
            # happen HERE, before the window opens, so the timer does nothing
            # but send three frames.
            emi_plan = prepare_mag_emi(rig_conn, args.platform, args.emi_ut)
            print(f"=== mag_emi prepared: {emi_plan['before']} "
                  f"delta={emi_plan['delta']}")
            t_ref = [None]

            def _inject_emi():
                rec = fire_mag_emi(rig_conn, args.platform, emi_plan)
                if t_ref[0] is not None:
                    rec["wrote_at_rel_s"] = round(
                        rec["wrote_at_wall"] - t_ref[0], 3)
                result["injection"].update(rec)
                for a in rec["axes"]:
                    print(f"      {a['param']}: {a['before']} -> "
                          f"{a['commanded']} readback={a['readback']} "
                          f"{'ok' if a['confirmed'] else 'MISMATCH'}")
                print(f"    [t+{args.inject_at:.1f}s] INJECTED mag_emi "
                      f"{args.emi_ut} uT/axis (rig authority) -> "
                      f"{'CONFIRMED' if rec['confirmed'] else 'NOT CONFIRMED'}")
            t_ref[0] = time.time()
            inject_timer = threading.Timer(args.inject_at, _inject_emi)
            inject_timer.daemon = True
            inject_timer.start()
            result["injection"] = {
                "kind": "mag_emi", "at_s": args.inject_at, "sent_by": "rig",
                "params": list(MAG_EMI[args.platform][0]),
                "param_type": MAG_EMI[args.platform][1],
                "arm": ("NULL CONTROL (write happens, field does not move)"
                        if args.emi_ut == 0.0 else "INJECTED"),
                "rule": "RULE B -- the intermediate quantity is the observed "
                        "mag.field_ut vector shift of u*sqrt(3) uT across the "
                        "injection instant, not the parameter write",
                "prereg": "research/v1_1/MECHANISM_B_MAG_EMI_PREREGISTRATION.md",
            }
        elif args.inject:
            name, value, ptype = INJECTIONS[args.inject][args.platform]
            mav_ptype = getattr(mavutil.mavlink, f"MAV_PARAM_TYPE_{ptype}")
            def _inject():
                # The RIG transmits. CSIA's socket is shut for writing and
                # every send on it raises CommandAuthorityError.
                rig_conn.mav.param_set_send(
                    rig_conn.target_system, rig_conn.target_component,
                    name.encode(), float(value), mav_ptype)
                # READ IT BACK. A parameter write nobody confirmed is an
                # assumption, and an unconfirmed injection is indistinguishable
                # from a platform that does not exhibit the mechanism -- which
                # is exactly how the first PX4 arm produced a null result that
                # meant nothing. `fly()` verifies MIS_TAKEOFF_ALT this way for
                # the same reason.
                #
                # This used to match the FIRST arriving PARAM_VALUE, which is
                # a stale queued ack often enough to matter -- see the comment
                # on `read_param`. It reported CONFIRMED for the published
                # Mechanism A arms, and those results stand independently
                # because the intermediate quantity (450 and 448 NO_3D_FIX
                # ticks) confirmed the injection landed. The readback is
                # nonetheless made robust so no later run inherits the flaw.
                seen, good = confirm_param(rig_conn, name, float(value))
                result["injection"]["readback"] = seen
                result["injection"]["confirmed"] = bool(good)
                print(f"    [t+{args.inject_at:.1f}s] INJECTED {args.inject}: "
                      f"{name} = {value} (rig authority); readback="
                      f"{seen} -> "
                      f"{'CONFIRMED' if result['injection']['confirmed'] else 'NOT CONFIRMED'}")
            inject_timer = threading.Timer(args.inject_at, _inject)
            inject_timer.daemon = True
            inject_timer.start()
            result["injection"] = {
                "kind": args.inject, "param": name, "value": value,
                "param_type": ptype, "at_s": args.inject_at,
                "sent_by": "rig", "rule": "RULE B -- the intermediate "
                "quantity (gnss.position MISSING/NO_3D_FIX) is what counts, "
                "not the parameter write",
            }
        else:
            result["injection"] = {"kind": None,
                                   "role": "CONTROL: fix preserved"}

        print(f"=== running SHADOW for {args.seconds:.0f} s"
              + (f", injecting {args.inject} at t+{args.inject_at:.0f}s"
                 if args.inject else " (CONTROL, no injection)"))
        t0 = time.time()
        header = runner.run()
        wall = time.time() - t0

        lat = getattr(runner, "tick_latencies", None)
        if not lat:
            lat = [runner.stats["max_latency_us"]] if runner.stats["ticks"] \
                else []
        result.update({
            "flight_id": header.flight_id,
            "wall_s": round(wall, 2),
            "stats": runner.stats,
            "adapter_counters": runner.adapter.counters,
            "unmapped_types": runner.adapter.unmapped_types(),
            "latency": summarise(lat),
            "phases": {k: summarise(list(v))
                       for k, v in runner.phase_us.items()},
            "command_authority": runner.authority_evidence,
            "log_dir": os.path.relpath(logdir, ROOT),
            "simulator_provenance": simulator_provenance(args.platform),
            "trust_trace": (os.path.relpath(args.trust_trace, ROOT)
                            if args.trust_trace else None),
            "trust_trace_steps": getattr(runner, "_trace_rows", 0),
        })

        print(f"\n=== ticks: {runner.stats['ticks']}  "
              f"messages: {runner.stats['messages']}")

        # POSITIVE CONTROL on the latency instrument, and it is not optional.
        #
        # The first version of this script reported "R13: PASS, median 168.8
        # us, 8x headroom" on a run that ingested ZERO messages. Those were
        # the cost of an EMPTY tick -- the adapter had nothing to convert, the
        # core had nothing to score. Certifying a timing budget from that is
        # the same error as scoring a fault injection that never reached the
        # vehicle: ticks ran is not telemetry was processed.
        #
        # An R13 verdict therefore requires a stream that actually flowed AND
        # channels that actually reached the core.
        usable = len(runner.adapter.sample(t_mono=0.0).usable_channels())
        control = {
            "messages_ingested": runner.stats["messages"],
            "usable_channels_at_end": usable,
            "satisfied": runner.stats["messages"] > 0 and usable > 0,
            "rule": "a latency figure from an idle tick measures the loop, "
                    "not the workload",
        }
        result["latency_positive_control"] = control

        L = result["latency"]
        if not L:
            result["R13"] = "NOT_MEASURED: no ticks"
        elif not control["satisfied"]:
            result["R13"] = (
                f"INVALID_MEASUREMENT: {runner.stats['messages']} messages "
                f"ingested, {usable} usable channels -- these ticks were "
                f"idle, so the latency below is the empty-loop cost and is "
                f"NOT an R13 result")
        else:
            print("=== tick latency through the FULL v1.1 stack")
            print(f"    median {L['median_us']:.1f} us | p95 {L['p95_us']:.1f} "
                  f"| p99 {L['p99_us']:.1f} | max {L['max_us']:.1f} us")
            # The tee runs as a THREAD in this interpreter. Under the GIL its
            # forwarding work is charged to the core's wall clock, and a
            # controlled test (same log, same core, varying only concurrent
            # in-process threads) measured 679 / 955 / 1598 us at 0 / 1 / 2
            # threads. An earlier run of this harness reported 1590 us and it
            # was recorded as an R13 failure of CSIA. It was not.
            #
            # For a clean core figure use
            # tools/deploy/profile_core_from_log.py, which replays a flight
            # log with nothing else in the process.
            # The caveat must match the run that produced the numbers. It
            # was printed unconditionally, so a process-mode run would have
            # carried a warning about a thread it did not have -- a stale
            # caveat is as misleading as a missing one.
            if args.tee_mode == "thread":
                result["timing_caveat"] = (
                    "phases include GIL contention from the IN-PROCESS tee "
                    "thread; NOT a clean core measurement. Re-run with "
                    "--tee-mode process. See W-8.")
                print("    NOTE: phases include in-process tee contention -- "
                      "not a clean core figure (see W-8)")
            elif not NEEDS_TEE.get(args.platform, True):
                # No tee at all on this platform. Saying "the tee is
                # out-of-process" on a run that has no tee is the same stale
                # caveat defect as printing the thread warning on a process
                # run -- a caveat has to describe the run that produced the
                # numbers.
                result["timing_caveat"] = (
                    "no tee in this configuration: CSIA binds a separate "
                    "mavlink instance directly. Remaining variance is the "
                    "host, which also runs the simulator.")
                print("    NOTE: no tee in this configuration; remaining "
                      "variance is the host (SITL shares this container)")
            else:
                result["timing_caveat"] = (
                    "tee ran in a SEPARATE interpreter, so no GIL contention "
                    "from it. Remaining contention is the host: this "
                    "container also runs SITL, and run-to-run spread on the "
                    "same command exceeds the tee effect. An R13 verdict from "
                    "shared cloud infrastructure is a statement about the "
                    "host as much as about CSIA.")
                print("    NOTE: tee is out-of-process; remaining variance is "
                      "the host (SITL shares this container)")
            ph = result["phases"]
            print("    phases (median us): "
                  + "  ".join(f"{k}={ph[k]['median_us']:.1f}"
                              for k in ("sample", "convert", "core")
                              if ph.get(k)))
            print(f"    R13 budget {R13_BUDGET_US:.0f} us -> "
                  f"{L['over_budget']} tick(s) over budget, "
                  f"worst-case headroom {L['worst_headroom_x']}x")
            # RULE A on the CLOCK. Before attributing an over-budget tick
            # to CSIA, measure what a constant workload does in the same
            # process on the same host -- see csia/simulation/host_noise.py
            # for the numbers that forced this. It cannot turn a real failure
            # into a pass: INDETERMINATE requires the control to fail too.
            noise = measure_host_noise(
                n_ticks=L["n"], target_us=L["median_us"],
                budget_us=R13_BUDGET_US, trials=3)
            result["host_noise_control"] = noise
            w = noise["worst_trial"]
            print(f"    host-noise control (constant work, same process): "
                  f"median {w['median_us']:.0f} us, max {w['max_us']:.0f} us, "
                  f"{w['over_budget']}/{w['n']} over budget")
            result["R13"] = r13_verdict(L["over_budget"], noise, L["n"])
        if L and not control["satisfied"]:
            print(f"    (idle-loop cost, NOT R13: median "
                  f"{L['median_us']:.1f} us over {L['n']} empty ticks)")
        print(f"=== R13: {result['R13']}")
    finally:
        # Cancel before teardown: a timer that fires after rig_conn is gone
        # would raise inside a daemon thread and be swallowed, which is how a
        # trial silently becomes a CONTROL.
        if inject_timer is not None:
            # cancel() alone only stops a timer that has not fired. Once the
            # ramp callback is running, only the Event stops it -- and a
            # thread still writing parameters after teardown would be writing
            # to a vehicle nobody is measuring.
            inject_timer.cancel()
            if glitch_cancel is not None:
                glitch_cancel.set()
            inject_timer.join(timeout=10.0)
            if inject_timer.is_alive():
                print("!!! injection thread still alive after teardown -- "
                      "parameter writes may have continued past the run")
                result.setdefault("injection", {})["teardown"] = \
                    "THREAD_STILL_ALIVE"
            else:
                result.setdefault("injection", {})["teardown"] = "joined"
        try:
            if tee is not None:
                tee.stop()
        except Exception:
            pass
        if tee_proc is not None:
            tee_proc.send_signal(signal.SIGINT)
            try:
                tee_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tee_proc.kill()
            if status_path and os.path.exists(status_path):
                try:
                    with open(status_path, encoding="utf-8") as fh:
                        result.setdefault("tee", {})["final_status"] = \
                            json.load(fh)
                except Exception:
                    pass
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    out = args.out or os.path.join(ROOT, "research", "v1_1", "results",
                                   f"shadow_sitl_{args.platform}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(out, ROOT)}")
    # INDETERMINATE is not a pass. It exits non-zero, with its own code, so
    # a CI job cannot read "the host was too noisy to tell" as success.
    r13 = str(result.get("R13", ""))
    if r13.startswith("PASS"):
        return 0
    return 2 if r13.startswith("INDETERMINATE") else 1


if __name__ == "__main__":
    sys.exit(main())
