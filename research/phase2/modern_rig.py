"""Phase-II modern rig: ArduCopter 4.8 driver with a HARD TRIAL-VALIDITY CONTRACT.

WHY THIS FILE EXISTS AT ALL. The Phase-I campaign scripts drive
`SIM_GPS_GLITCH_X`. That parameter DOES NOT EXIST on ArduCopter 4.8 — the SIM
GPS parameters were renamed `SIM_GPS1_*` for multi-receiver support. A
`param_set` to a non-existent name is silently ignored by the autopilot. Run
Phase-I code against a modern build and every fault arm flies clean while being
labelled a fault arm, and the resulting table looks like a spectacular
robustness result.

So no trial in this file produces science until six independent conditions are
verified:

  V1 command_issued        we sent the parameter write
  V2 param_readback        the autopilot reports the value we asked for
  V3 sensor_output_changed the reported GPS position actually moved
  V4 autopilot_affected    the estimator's own state responded
  V5 csia_ingested         the layer's gps channel saw the changed position
  V6 truth_matches_schedule realized displacement matches the request

TRIAL_VALID = V1 AND ... AND V6. A trial that fails any of them emits
TRIAL_VALID=False with the failing check named, and is EXCLUDED from every
metric. Invalid trials are kept in the artifact, never silently dropped.

--------------------------------------------------------------------------
INSTRUMENT CORRECTION, run 2. The contract above is unchanged. The ESTIMATOR
of "realized displacement" that V3 and V6 consume was wrong in run 1 and is
corrected here. See research/phase2/V6_INSTRUMENT_DEFECT.md.

Run 1 estimated realized displacement as the reported position's motion away
from a fixed pre-injection mark. The vehicle is flying, so that quantity
contains the airframe's own motion. Measured on a NOMINAL arm with no
injection at all, it reads 38.89 m — a 39 m noise floor on a 55.7 m signal.

ArduPilot adds the glitch to the vehicle's true position after the receiver
delay buffer (libraries/SITL/SIM_GPS.cpp:581), so

    reported(t) = truth(t) + glitch(t)

and the injected offset is exactly sep(GPS_RAW_INT, SIMSTATE). That estimator
reads 1.21 m on the same nominal arm. V3 and V6 now consume it.

The airframe's own motion is not discarded; a slow ramp that the estimator
accepts drags the vehicle off its commanded track, and that displacement is
recorded separately as true_vehicle_excursion_m against a matched-window
nominal control.
--------------------------------------------------------------------------

Run:  imported by e1_modern.py; not a standalone experiment.
"""

import math
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

AP_ROOT = os.environ.get("CSIA_AP_ROOT", "/home/user/ardupilot/ardupilot")
AP_BIN = os.path.join(AP_ROOT, "build", "sitl", "bin", "arducopter")
DEG_TO_M = 111_320.0
HOME = "47.397742,8.545594,488,0"

# Detection criteria, identical in form to Phase-I so the comparison is like
# for like. Both come from the systems themselves, not from us.
EKF_THRESH = 0.8      # ArduPilot's own FS_EKF_THRESH default
PHYS_FLOOR = 0.10     # CSIA physics residual saturated
NAV_CAUTION = 0.75    # FailsafeConfig.nav_caution

# Modern parameter names. The Phase-I names are listed so a regression to them
# is caught by name rather than by a silent no-op.
P_GLITCH_X = "SIM_GPS1_GLTCH_X"
P_GPS_ENABLE = "SIM_GPS1_ENABLE"
P_NUMSATS = "SIM_GPS1_NUMSATS"
LEGACY_NAMES_MUST_NOT_BE_USED = ("SIM_GPS_GLITCH_X", "SIM_GPS_DISABLE",
                                 "SIM_GPS_NUMSATS", "SIM_GPS_BYTELOSS")

# Validity tolerances. V6's tolerance is as precommitted and is NOT moved.
V6_DISPLACEMENT_TOLERANCE = 0.25   # realized within 25% of requested
V4_MIN_EKF_RESPONSE = 1.5          # estimator variance must rise by this factor

# V3's floor is RAISED from the precommitted 1.0 m to 2.0 m, because the
# corrected instrument has a measured noise ceiling of 1.21 m on the control
# arm (research/phase2/results/v6_diagnosis.json, nominal_60, GPS horizontal
# wander) and a 1.0 m floor would sit below it. Raising a validity floor can
# only ever REMOVE trials from the metric set, never add one, so this cannot
# manufacture a favourable result. It is in any case non-binding: V6 requires
# agreement to within 25% of a >= 48 m request, which is far stricter.
V3_MIN_POSITION_CHANGE_M = 2.0
V3_CONTROL_ARM_NOISE_CEILING_M = 1.21
V3_PRECOMMITTED_FLOOR_M = 1.0

# V5 checks that the layer's own gps channel received changed positions. It is
# computed against a pre-injection mark and therefore carries the same vehicle
# motion contamination described in the module docstring. It is retained
# unchanged and reported as COARSE: V3 and V6 on the corrected instrument are
# strictly stronger, so V5 is never the check that decides a trial here.
V5_IS_COARSE = True


class Shim:
    """Same two documented adaptations as Phase-I, re-verified on 4.8.

    1. ArduPilot publishes the primary IMU as RAW_IMU, not SCALED_IMU, on BOTH
       builds, in the same mG / mrad-s / mgauss units. Relabelling is the whole
       adaptation.
    2. GPS_RAW_INT.time_usec is suppressed. On 3.3 it was last-fix time and
       froze on fix loss; on 4.8 it appears to be a since-boot value, but
       suppressing it costs nothing (map_mavlink then stamps GPS samples with
       the last stream time, which it already does for untimestamped messages)
       and removes a build-dependent behaviour from the comparison.
    """

    def __init__(self, msg):
        object.__setattr__(self, "_m", msg)
        t = msg.get_type()
        object.__setattr__(self, "_type",
                           "SCALED_IMU" if t == "RAW_IMU" else t)

    def get_type(self):
        return self._type

    def __getattr__(self, k):
        if k == "time_usec" and self._type == "GPS_RAW_INT":
            return None
        return getattr(self._m, k)


def sep_m(p, q):
    dn = (p[0] - q[0]) * DEG_TO_M
    de = (p[1] - q[1]) * DEG_TO_M * math.cos(math.radians(p[0]))
    return math.hypot(dn, de)


def set_param(m, name, value, ptype):
    from pymavlink import mavutil
    if name in LEGACY_NAMES_MUST_NOT_BE_USED:
        raise ValueError(
            f"{name} is a Phase-I parameter name and does not exist on "
            "ArduCopter 4.8. Writing it is a silent no-op and would produce a "
            "clean flight labelled as a fault arm.")
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(),
                         float(value),
                         getattr(mavutil.mavlink, f"MAV_PARAM_TYPE_{ptype}"))


def read_param(m, name, timeout=5.0):
    m.mav.param_request_read_send(m.target_system, m.target_component,
                                  name.encode(), -1)
    end = time.time() + timeout
    while time.time() < end:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
        if msg is None:
            break
        if msg.param_id == name:
            return float(msg.param_value)
    return None


def pilot(m, st, mavutil, hold_position=False):
    """Wait for fix, GUIDED, arm, take off, then hold or fly.

    Sequenced on the autopilot's reported state, not on elapsed time: 4.8
    refuses GUIDED without a position estimate and auto-disarms on the ground.
    """
    t = st["t"]
    hb = m.messages.get("HEARTBEAT")
    gpi = m.messages.get("GLOBAL_POSITION_INT")
    gps = m.messages.get("GPS_RAW_INT")
    armed = bool(hb and hb.base_mode
                 & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    if hb is not None:
        mode = mavutil.mode_string_v10(hb)
        if not st["modes"] or st["modes"][-1][1] != mode:
            st["modes"].append([round(t, 1), mode])
    alt = (gpi.relative_alt / 1000.0) if gpi else 0.0
    st["max_alt"] = max(st["max_alt"], alt)

    def due(gap=0.5):
        if t - st["last_cmd_t"] < gap:
            return False
        st["last_cmd_t"] = t
        return True

    ph = st["phase"]
    if ph == "wait_fix":
        if gps is not None and gps.fix_type >= 3:
            st["fix_t"] = t
            st["phase"] = "settle"
    elif ph == "settle":
        if t - st["fix_t"] >= 6.0:
            st["phase"] = "guided"
    elif ph == "guided":
        if hb is not None and hb.custom_mode == 4:
            st["phase"] = "arm"
        elif due():
            m.mav.set_mode_send(
                m.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 4)
    elif ph == "arm":
        if armed:
            m.mav.command_long_send(m.target_system, m.target_component,
                                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                                    0, 0, 0, 0, 0, 0, 0, 20)
            st["phase"] = "climb"
        elif due(1.0):
            m.arducopter_arm()
    elif ph == "climb":
        if alt > 15.0:
            st["phase"] = "fly"
            st["fly_t0"] = t
            st["airborne_t"] = round(t, 1)
        elif not armed and due(2.0):
            st["phase"] = "arm"
    elif ph == "fly" and due(0.2):
        if hold_position:
            vn, ve = 0, 0
        else:
            leg = int((t - st.get("fly_t0", t)) / 8) % 4
            vn, ve = [(4, 0), (0, 4), (-4, 0), (0, -4)][leg]
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111000111, 0, 0, 0, vn, ve, 0, 0, 0, 0, 0, 0)


def new_state():
    return {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0, "fix_t": None,
            "modes": [], "max_alt": 0.0, "airborne_t": None}


def launch(workdir, speedup, instance=0):
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    return subprocess.Popen(
        [AP_BIN, "--model", "quad", "--speedup", str(speedup), "-w",
         "--home", HOME, "--instance", str(instance)],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def connect(instance=0, timeout=90):
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{5760 + 10 * instance}")
    m.wait_heartbeat(timeout=timeout)
    for stream, hz in ((mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 25),
                       (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 10),
                       (mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
                       (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
                       (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 10),
                       (mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 5)):
        m.mav.request_data_stream_send(m.target_system, m.target_component,
                                       stream, hz, 1)
    # Harness settings: no radio and no GCS in this loop, and the flight is
    # long enough that the SITL battery model would otherwise trigger.
    for name, val, ty in (("FS_THR_ENABLE", 0, "INT32"),
                          ("FS_GCS_ENABLE", 0, "INT32"),
                          ("FS_OPTIONS", 0, "INT32"),
                          ("BATT_FS_LOW_ACT", 0, "INT32"),
                          ("BATT_FS_CRT_ACT", 0, "INT32"),
                          ("SIM_BATT_VOLTAGE", 12.6, "REAL32")):
        try:
            set_param(m, name, val, ty)
        except Exception:                                      # noqa: BLE001
            pass
    return m


def validity(rec, requested_m):
    """The six-check contract. Returns (TRIAL_VALID, checks, [failing]).

    V3 and V6 consume `max_injected_sensor_offset_m`, the separation between
    the reported GPS position and the simulator's own truth. That is the
    glitch itself, by SIM_GPS.cpp:581, and it is the only quantity here that
    is free of the airframe's own motion.
    """
    offset = rec.get("max_injected_sensor_offset_m", 0.0)
    checks = {
        "V1_command_issued": bool(rec.get("injection_commands_sent")),
        "V2_param_readback": (
            rec.get("param_readback_after") is not None
            and abs(rec["param_readback_after"]
                    - rec.get("param_requested", 0.0)) < 1e-9),
        "V3_sensor_output_changed": offset >= V3_MIN_POSITION_CHANGE_M,
        "V4_autopilot_affected": (
            rec.get("ekf_var_pre") is not None
            and rec.get("ekf_var_post") is not None
            and (rec["ekf_var_post"]
                 >= V4_MIN_EKF_RESPONSE * max(rec["ekf_var_pre"], 1e-6)
                 or rec.get("max_fused_position_error_m", 0.0)
                 >= V3_MIN_POSITION_CHANGE_M)),
        # COARSE, see V5_IS_COARSE. Retained at the precommitted floor.
        "V5_csia_ingested": rec.get("csia_gps_samples_post", 0) > 0
        and rec.get("csia_max_gps_input_shift_m", 0.0)
        >= V3_PRECOMMITTED_FLOOR_M,
        "V6_truth_matches_schedule": (
            requested_m > 0
            and abs(offset - requested_m)
            <= V6_DISPLACEMENT_TOLERANCE * requested_m),
    }
    failed = [k for k, v in checks.items() if not v]
    return (not failed), checks, failed


def instrument_control(nominal_rows):
    """Campaign-level check: the validity instrument must read null on a
    clean flight.

    This is the check whose absence let run 1 through. It is not a per-trial
    threshold; it asks whether the measuring device reads zero when nothing is
    injected. Run 1's estimator would have failed it at 38.89 m.
    """
    if not nominal_rows:
        return {"status": "NO_CONTROL_ARM", "passes": False}
    worst = max(r.get("max_injected_sensor_offset_m", 0.0)
                for r in nominal_rows)
    contaminated = max(r.get("max_reported_position_change_m", 0.0)
                       for r in nominal_rows)
    return {
        "status": "PASS" if worst < V3_MIN_POSITION_CHANGE_M else "FAIL",
        "passes": worst < V3_MIN_POSITION_CHANGE_M,
        "corrected_instrument_reads_on_nominal_m": round(worst, 2),
        "run1_instrument_reads_on_nominal_m": round(contaminated, 2),
        "must_be_below_m": V3_MIN_POSITION_CHANGE_M,
        "note": "a validity instrument that reads non-null with no injection "
                "cannot certify that an injection happened",
    }
