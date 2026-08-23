"""WP-C6 Part 3 — the q_gvalid controlled-injection campaign, in SITL.

This is route **L1** of `research/wp_c5/Q_GVALID_MEASUREMENT_SPEC.md`: the
hypothesis label is the injection schedule, so the conditioning variable that
does not exist in the unannotated corpus exists here by construction.

What is real and what is not, stated before any number:

  * REAL: a full ArduPilot autopilot (ArduCopter SITL), its own EKF, its own
    GPS driver, its own MAVLink stream, and the deployed CSIA trust layer
    ingesting that stream through the production `map_mavlink` adapter. The
    gate trace is the layer's own `gvalid`, read out of `TrustState.edges`,
    not a re-derivation.
  * NOT REAL: the vehicle, the receiver, and the RF environment. This is a
    simulator. Every number here is `q_gvalid` **under ArduPilot's SIM GPS
    fault models**, and the spec (section 7) already names that as the
    limitation: real degradation includes partial constellation loss and
    gradual carrier-to-noise decay. That is why arm `glitch` and arm
    `degraded` exist below. They are the closest available approach to a
    fault that does not simply switch the fix flag off.

The internal CSIA simulator is NOT used and is not an accepted fallback. If
the autopilot binary is absent this script emits `SITL_UNAVAILABLE` and says
what is needed. It does not substitute anything and call it flight.

Acquiring the binary (it is GPLv3 ArduPilot and is deliberately not vendored):

    curl -sSLO https://dronekit-assets.s3.amazonaws.com/sitl/copter/\\
sitl-linux-copter-3.3.tar.gz
    mkdir -p sitl && tar xf sitl-linux-copter-3.3.tar.gz -C sitl
    export CSIA_SITL_BINARY=$PWD/sitl/apm
    export CSIA_SITL_EEPROM=$PWD/sitl/default_eeprom.bin

Run:  PYTHONPATH=. python research/wp_c6/q_gvalid_campaign.py
Out:  research/wp_c6/results/q_gvalid_campaign.json
"""

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

RESULTS = os.path.join(os.path.dirname(__file__), "results")

# --- PRE-REGISTRATION ---------------------------------------------------------
# Fixed before any outcome was looked at, per spec section 3. Changing any of
# these after seeing a result invalidates the interval.
PREREG = {
    "tick_hz": 25.0,
    "arm_time_s": 20.0,
    "monitored_tick": "armed is True AND layer time >= arm_time_s",
    "conditioning_window_s": 25.0,
    "conditioning_window": (
        "[injection_time_s, injection_time_s + 25 s]. The hypothesis label is "
        "the injection state, so the window over which q_gvalid|h is "
        "estimated must be the window in which h holds. In the nominal arm "
        "the same instant passes with no parameter applied, so the window is "
        "[60 s, 85 s] in every arm and the design is matched. 25 s is chosen "
        "because ArduPilot's own EKF failsafe switches to LAND under GNSS "
        "loss and the vehicle eventually disarms; the window is sized to sit "
        "inside the armed segment that leaves, in every arm."),
    "min_window_coverage": 0.95,
    "gvalid_closed_at_tick": "TrustState.edges['altitude_baro'][1] == 0.0 "
                             "(online.py:517-518 gates that edge on gvalid "
                             "alone, so it is a direct readout of the gate)",
    "per_flight_statistic": "closed monitored ticks in the conditioning "
                            "window / monitored ticks in the conditioning "
                            "window",
    "secondary_statistic": "the same ratio over the whole monitored window, "
                           "which dilutes the fault arms with their own "
                           "pre-injection nominal segment and is reported "
                           "only for completeness",
    "arm_statistic": "mean over flights (flight is the independence unit, "
                     "NOT the tick: closure is autocorrelated within a "
                     "flight)",
    "n_flights_per_arm": 6,
    "bootstrap_resamples": 10000,
    "interval_method": "BCa over flights for each arm; PAIRED percentile for "
                       "the ratio (the arms share flight specs, so the "
                       "resample is over spec index)",
    "bootstrap_seed": 20260823,
    "min_flights_for_inference": 5,
    "injection_time_s": 60.0,
    "flight_end_s": 120.0,
    "AMENDMENT": (
        "Amended once, after a one-flight-per-arm pipeline smoke test and "
        "BEFORE the campaign was run. Two changes, both recorded here rather "
        "than silently applied. (1) The per-flight statistic was originally "
        "the whole monitored window; that window contains 40 s of "
        "pre-injection nominal flight in every arm, so it estimated a "
        "mixture rather than q_gvalid|h. The conditioning window above "
        "replaces it and the original is retained as the secondary. (2) The "
        "smoke test showed ArduPilot's own EKF failsafe switching to LAND "
        "8.8 s after denial, which eventually disarms the vehicle and "
        "truncates the observation window in the fault arms only. Raising "
        "FS_EKF_THRESH did not stop it even though the readback confirms the "
        "write was accepted, so the LAND is not the EKF variance check; "
        "rather than fight the autopilot the conditioning window is sized "
        "to fit inside the armed segment the failsafe leaves, and the mode "
        "changes are recorded as an observable in their own right. What the "
        "smoke test showed of the outcome: denial closed the gate, glitch "
        "did not."),
}

# --- flight specs: identical across arms, so the design is PAIRED -------------
# Varying home site and wind gives genuinely different flights; using the same
# six in every arm means the ratio is a within-spec comparison.
FLIGHT_SPECS = [
    {"id": 0, "home": "47.397742,8.545594,488,0",   "wind": (0.0, 180.0)},
    {"id": 1, "home": "-35.363261,149.165230,584,0", "wind": (4.0, 45.0)},
    {"id": 2, "home": "37.413360,-121.996500,10,90", "wind": (8.0, 270.0)},
    {"id": 3, "home": "55.953251,-3.188267,47,180",  "wind": (2.0, 90.0)},
    {"id": 4, "home": "-22.906847,-43.172896,15,270", "wind": (6.0, 315.0)},
    {"id": 5, "home": "64.128288,-21.827774,61,45",  "wind": (10.0, 135.0)},
]

# --- arms ---------------------------------------------------------------------
# Each value is a list of (param_name, value, mavlink_type_name) applied at
# INJECTION_TIME_S. `nominal` applies nothing.
ARMS = {
    "nominal": {
        "params": [],
        "what_it_models": "healthy flight. This arm is the denominator of R "
                          "and is the informative half of the campaign.",
    },
    "denial": {
        "params": [("SIM_GPS_DISABLE", 1.0, "INT8")],
        "what_it_models": "outright GNSS denial. The paper's arm-B condition. "
                          "NOTE: this switches the fix flag off directly, so a "
                          "high closure rate here is close to tautological. It "
                          "is included to confirm the mechanism end to end on "
                          "a real autopilot, not as evidence about how often "
                          "real faults close the gate.",
    },
    "glitch": {
        "params": [("SIM_GPS_GLITCH_X", 0.0005, "REAL32"),
                   ("SIM_GPS_GLITCH_Y", 0.0005, "REAL32")],
        "what_it_models": "a position glitch of roughly 55 m with the fix "
                          "RETAINED. This is the fault class the spec's "
                          "section 7 says SITL denial cannot represent, and it "
                          "is the arm that actually tests whether a GNSS fault "
                          "closes the gate.",
    },
    "degraded": {
        "params": [("SIM_GPS_NUMSATS", 4.0, "REAL32"),
                   ("SIM_GPS_BYTELOSS", 20.0, "REAL32")],
        "what_it_models": "partial constellation loss plus receiver link "
                          "corruption. Degradation rather than denial.",
    },
}

DEFAULT_BINARY = os.environ.get("CSIA_SITL_BINARY", "")
DEFAULT_EEPROM = os.environ.get("CSIA_SITL_EEPROM", "")


def locate_sitl(binary, eeprom):
    """Resolve the autopilot binary, or explain precisely what is missing."""
    try:
        import pymavlink                                     # noqa: F401
        have_pymavlink = True
    except ImportError:
        have_pymavlink = False
    ok = bool(binary) and os.path.isfile(binary) and os.access(binary, os.X_OK)
    return ok and have_pymavlink, {
        "binary": binary or "(unset: CSIA_SITL_BINARY)",
        "binary_present": ok,
        "eeprom": eeprom or "(unset: CSIA_SITL_EEPROM)",
        "eeprom_present": bool(eeprom) and os.path.isfile(eeprom),
        "pymavlink_installed": have_pymavlink,
    }


# --- research-side shims, both documented, neither a production change --------

class _Shim:
    """Adapts two ArduCopter 3.3 stream quirks WITHOUT touching plugins.py.

    1. AC 3.3 publishes the primary IMU as RAW_IMU, not SCALED_IMU. ArduPilot
       fills RAW_IMU with the same mG / mrad-s / mgauss units SCALED_IMU uses,
       so relabelling the type is the whole adaptation.
    2. GPS_RAW_INT.time_usec in this build is the LAST FIX time, not the
       message time. It is zero before the first fix and it FREEZES when the
       fix is lost, which is exactly the condition the fault arms create. Fed
       to map_mavlink it reads as the clock jumping backwards and triggers the
       reboot re-anchor at online.py's source layer. It is suppressed here so
       map_mavlink stamps GPS samples with the last stream time, which is what
       it already does for every untimestamped message. This changes the
       timestamp only; fix_type, position and velocity pass through untouched.
       A plausibility guard covers the same failure in any other message.
    """

    IMPLAUSIBLE_US = 1e11        # 1e5 s since boot: not a since-boot clock

    def __init__(self, msg):
        object.__setattr__(self, "_m", msg)
        t = msg.get_type()
        object.__setattr__(self, "_type",
                           "SCALED_IMU" if t == "RAW_IMU" else t)

    def get_type(self):
        return self._type

    def __getattr__(self, k):
        if k == "time_usec":
            if self._type == "GPS_RAW_INT":
                return None
            v = getattr(self._m, k)
            return None if (v and v > self.IMPLAUSIBLE_US) else v
        return getattr(self._m, k)


def fly(binary, eeprom, spec, arm_name, arm_cfg, speedup, workdir, verbose,
        ekf_failsafe=False):
    """One flight. Returns the per-flight record, or a dict with 'error'."""
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))

    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup),
         "--home", spec["home"]],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    rec = {"arm": arm_name, "spec_id": spec["id"], "home": spec["home"],
           "wind": list(spec["wind"])}
    try:
        time.sleep(4.0)
        m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
        m.wait_heartbeat(timeout=60)

        for stream, hz in ((mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 25),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 5)):
            m.mav.request_data_stream_send(m.target_system, m.target_component,
                                           stream, hz, 1)
        # Harness settings, not part of the measurement. FS_THR and FS_GCS
        # are radio/GCS failsafes that fire because this harness is neither a
        # transmitter nor a ground station. FS_EKF_THRESH is raised far above
        # any achievable variance so the EKF failsafe does not LAND and disarm
        # the vehicle under injection, which would truncate the observation
        # window in the fault arms only and bias the denominator;
        # --ekf-failsafe leaves it at the default (0.8) so the autopilot's own
        # response can be measured instead of lost. Two observations, both
        # recorded rather than assumed: setting it to 0 stopped the vehicle
        # arming at all, and setting it to 10 is ACCEPTED (the readback below
        # confirms 10.0) yet the vehicle still switches to LAND under denial.
        # So the LAND is not the EKF variance check; it is ArduPilot losing
        # position in a position-dependent mode. The conditioning window is
        # sized around it rather than the failsafe being fought.
        # None of these touch the GPS driver or the gate.
        _set(m, "FS_THR_ENABLE", 0.0, "INT32")
        _set(m, "FS_GCS_ENABLE", 0.0, "INT32")
        if not ekf_failsafe:
            _set(m, "FS_EKF_THRESH", 10.0, "REAL32")
            m.mav.param_request_read_send(m.target_system, m.target_component,
                                          b"FS_EKF_THRESH", -1)
        _set(m, "SIM_WIND_SPD", spec["wind"][0], "REAL32")
        _set(m, "SIM_WIND_DIR", spec["wind"][1], "REAL32")

        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"motor_esc": 1e9,
                                                  "battery": 1e9,
                                                  "vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(
            arm_time=PREREG["arm_time_s"]))
        ctx = {"t0": None}

        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": False, "monitored": 0,
                 "closed": 0, "gps_fix_seen": set(), "min_trust": {},
                 "causes_at": None, "ticks": 0, "msgs": 0,
                 "seen_transitions": 0, "modes": [], "max_alt": 0.0,
                 "airborne_t": None, "armed_after_injection": 0,
                 "monitored_after_injection": 0,
                 "closed_after_injection": 0}
        alarms = []
        t_inject = PREREG["injection_time_s"]
        t_end = PREREG["flight_end_s"]
        wall_deadline = time.time() + (t_end / speedup) * 4 + 90

        while time.time() < wall_deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            state["msgs"] += 1
            if msg.get_type() == "GPS_RAW_INT":
                state["gps_fix_seen"].add(int(msg.fix_type))
                _gps_effect(msg, state)
            elif msg.get_type() == "PARAM_VALUE" and \
                    msg.param_id == "FS_EKF_THRESH":
                state["fs_ekf_thresh"] = round(float(msg.param_value), 4)
            for sensor, t, ch in map_mavlink(_Shim(msg), ctx):
                for st in layer.ingest(sensor, t, ch):
                    _tick(st, state, policy, alarms)
            state["t"] = ctx.get("t_last", 0.0)

            _pilot(m, state, mavutil)

            if (not state["injected"]) and state["t"] >= t_inject:
                for pname, val, ptype in arm_cfg["params"]:
                    _set(m, pname, val, ptype)
                state["injected"] = True
                if verbose:
                    print(f"      inject @ t={state['t']:.1f}s: "
                          f"{[p[0] for p in arm_cfg['params']] or 'none'}")
            if state["t"] >= t_end:
                break

        post = state["monitored_after_injection"]
        expected = PREREG["conditioning_window_s"] * PREREG["tick_hz"]
        rec.update({
            "window_coverage": round(post / expected, 4),
            "fs_ekf_thresh_readback": state.get("fs_ekf_thresh"),
            "monitored_ticks": state["monitored"],
            "closed_ticks": state["closed"],
            "p_closed": (round(state["closed"] / state["monitored"], 6)
                         if state["monitored"] else None),
            "monitored_ticks_after_injection": post,
            "closed_ticks_after_injection": state["closed_after_injection"],
            "p_closed_after_injection": (
                round(state["closed_after_injection"] / post, 6)
                if post else None),
            "total_ticks": state["ticks"],
            "messages": state["msgs"],
            "reached_injection": state["injected"],
            "final_layer_time_s": round(state["t"], 2),
            "final_phase": state["phase"],
            "airborne_at_s": state["airborne_t"],
            "max_relative_alt_m": round(state["max_alt"], 1),
            "mode_changes": state["modes"],
            "gps_fix_types_seen": sorted(state["gps_fix_seen"]),
            "injection_effect": {
                "max_position_step_m_pre":
                    round(state.get("steps", {}).get("pre", 0.0), 2),
                "max_position_step_m_post":
                    round(state.get("steps", {}).get("post", 0.0), 2),
                "mean_satellites_pre": round(_mean(
                    state.get("sats", {}).get("pre", [])), 2)
                    if state.get("sats", {}).get("pre") else None,
                "mean_satellites_post": round(_mean(
                    state.get("sats", {}).get("post", [])), 2)
                    if state.get("sats", {}).get("post") else None,
            },
            "min_trust_monitored": {k: round(v, 4) for k, v in
                                    sorted(state["min_trust"].items())},
            "alarms": alarms,
            "top_causes_20s_after_injection": state["causes_at"],
        })
        return rec
    except Exception as exc:                                  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def _gps_effect(msg, state):
    """Did the injection actually reach the receiver?

    Without this a null result in the `glitch` arm is indistinguishable from
    a parameter that the autopilot ignored. Records the largest sample-to-
    sample position step and the satellite count, split at the injection.
    """
    win = "post" if state["injected"] else "pre"
    sats = int(getattr(msg, "satellites_visible", 0))
    state.setdefault("sats", {"pre": [], "post": []})[win].append(sats)
    if msg.fix_type < 3:
        # a fixless sample carries lat/lon 0; stepping from or to it would
        # report the distance to null island rather than a receiver glitch
        state["gps_prev"] = None
        return
    prev = state.get("gps_prev")
    state["gps_prev"] = (msg.lat, msg.lon)
    if prev is None:
        return
    dn = (msg.lat - prev[0]) * 1e-7 * 111_320.0
    de = (msg.lon - prev[1]) * 1e-7 * 111_320.0 * math.cos(
        math.radians(msg.lat * 1e-7))
    step = math.hypot(dn, de)
    steps = state.setdefault("steps", {"pre": 0.0, "post": 0.0})
    steps[win] = max(steps[win], step)


def _set(m, name, value, ptype):
    from pymavlink import mavutil
    m.mav.param_set_send(m.target_system, m.target_component,
                         name.encode(), float(value),
                         getattr(mavutil.mavlink, f"MAV_PARAM_TYPE_{ptype}"))


def _tick(st, state, policy, alarms):
    """Record one 25 Hz engine tick against the pre-registered definitions."""
    state["ticks"] += 1
    policy.update(st)
    for tr in policy.transitions[state["seen_transitions"]:]:
        if tr.level.name != "NORMAL":
            alarms.append({"t": round(tr.t, 2), "level": tr.level.name,
                           "reasons": list(tr.reasons)})
    state["seen_transitions"] = len(policy.transitions)
    monitored = bool(st.armed) and st.t >= PREREG["arm_time_s"]
    if not monitored:
        return
    state["monitored"] += 1
    gate = st.edges.get("altitude_baro", (None, None))[1]
    closed = gate is not None and float(gate) == 0.0
    if closed:
        state["closed"] += 1
    t0 = PREREG["injection_time_s"]
    if t0 <= st.t < t0 + PREREG["conditioning_window_s"]:
        state["monitored_after_injection"] += 1
        if closed:
            state["closed_after_injection"] += 1
    for n, v in st.trust.items():
        if st.fresh[n]:
            state["min_trust"][n] = min(state["min_trust"].get(n, 1.0), v)
    if state["causes_at"] is None and \
            st.t >= PREREG["injection_time_s"] + 20.0:
        state["causes_at"] = [[c, round(p, 4)] for c, p in st.top_causes(3)]


GUIDED = 4
TAKEOFF_ALT_M = 20.0


def _pilot(m, state, mavutil, hold_position=False):
    """Wait for a 3D fix, enter GUIDED, arm, take off, fly a square.

    `hold_position` commands zero ground velocity instead of the square. WP-C7
    uses it to isolate the wind response: a multirotor holding position must
    tilt into the wind, and the square pattern's own manoeuvring tilt swamps
    that signal.

    Sequenced on the autopilot's own reported state rather than on elapsed
    time: ArduCopter refuses GUIDED without a 3D fix, and arming before the
    mode has actually changed leaves it on the ground where it auto-disarms.
    Commands are rate limited in SIMULATED time so a fast message loop does
    not flood the link.
    """
    t, phase = state["t"], state["phase"]
    hb = m.messages.get("HEARTBEAT")
    gpi = m.messages.get("GLOBAL_POSITION_INT")
    gps = m.messages.get("GPS_RAW_INT")
    armed = bool(hb and hb.base_mode
                 & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    if hb is not None:
        mode = mavutil.mode_string_v10(hb)
        if not state["modes"] or state["modes"][-1][1] != mode:
            state["modes"].append([round(t, 1), mode])
    if gpi is not None:
        alt = gpi.relative_alt / 1000.0
        state["max_alt"] = max(state["max_alt"], alt)
    else:
        alt = 0.0

    def due(gap=0.5):
        if t - state["last_cmd_t"] < gap:
            return False
        state["last_cmd_t"] = t
        return True

    if phase == "wait_fix":
        if gps is not None and gps.fix_type >= 3:
            state["fix_t"] = t
            state["phase"] = "settle"
    elif phase == "settle":
        if t - state["fix_t"] >= 4.0:
            state["phase"] = "guided"
    elif phase == "guided":
        if hb is not None and hb.custom_mode == GUIDED:
            state["phase"] = "arm"
        elif due():
            m.mav.set_mode_send(
                m.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, GUIDED)
    elif phase == "arm":
        if armed:
            m.mav.command_long_send(m.target_system, m.target_component,
                                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                                    0, 0, 0, 0, 0, 0, 0, TAKEOFF_ALT_M)
            state["phase"] = "climb"
        elif due(1.0):
            m.arducopter_arm()
    elif phase == "climb":
        if alt > 15.0:
            state["phase"] = "fly"
            state["fly_t0"] = t
            state["airborne_t"] = round(t, 1)
        elif not armed and due(2.0):
            state["phase"] = "arm"
    elif phase == "fly" and due(0.2):
        if hold_position:
            vn, ve = 0, 0
        else:
            leg = int((t - state.get("fly_t0", t)) / 8) % 4
            vn, ve = [(4, 0), (0, 4), (-4, 0), (0, -4)][leg]
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111000111, 0, 0, 0, vn, ve, 0, 0, 0, 0, 0, 0)


# --- estimator ----------------------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def bca_ci(data, rng, n_boot, alpha=0.05):
    """BCa interval for the mean, resampling over flights."""
    from scipy.stats import norm
    n = len(data)
    if n < 2:
        return None
    theta = _mean(data)
    boots = sorted(_mean([data[rng.randrange(n)] for _ in range(n)])
                   for _ in range(n_boot))
    prop = sum(1 for b in boots if b < theta) / n_boot
    jack = [_mean([data[i] for i in range(n) if i != j]) for j in range(n)]
    jbar = _mean(jack)
    num = sum((jbar - x) ** 3 for x in jack)
    den = 6.0 * (sum((jbar - x) ** 2 for x in jack)) ** 1.5
    acc = num / den if den > 0 else 0.0
    if prop <= 0.0 or prop >= 1.0:
        lo_i = int(math.floor(alpha / 2 * n_boot))
        hi_i = min(n_boot - 1, int(math.ceil((1 - alpha / 2) * n_boot)))
        return {"lo": round(boots[lo_i], 6), "hi": round(boots[hi_i], 6),
                "method": "percentile (BCa degenerate: bootstrap "
                          "distribution is a point mass relative to theta)"}
    z0 = norm.ppf(prop)
    out = {}
    for tag, a in (("lo", alpha / 2), ("hi", 1 - alpha / 2)):
        z = norm.ppf(a)
        adj = z0 + (z0 + z) / (1 - acc * (z0 + z))
        idx = int(round(norm.cdf(adj) * n_boot))
        out[tag] = round(boots[min(max(idx, 0), n_boot - 1)], 6)
    out["method"] = "BCa"
    out["z0"] = round(float(z0), 4)
    out["acceleration"] = round(float(acc), 6)
    return out


def paired_ratio_ci(num, den, rng, n_boot, alpha=0.05):
    """Percentile interval for mean(num)/mean(den), resampling spec indices.

    The arms share flight specs, so the resample is over the spec index and
    both arms move together. Dividing two separately-computed intervals would
    be wrong and the spec says so.
    """
    n = min(len(num), len(den))
    if n < 2:
        return None
    ratios = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        d = _mean([den[i] for i in idx])
        nu = _mean([num[i] for i in idx])
        ratios.append(float("inf") if d == 0 else nu / d)
    finite = sorted(r for r in ratios if math.isfinite(r))
    n_inf = len(ratios) - len(finite)
    if not finite:
        return {"lo": None, "hi": None,
                "note": "every resample had a zero denominator"}
    lo_i = int(math.floor(alpha / 2 * len(finite)))
    hi_i = min(len(finite) - 1, int(math.ceil((1 - alpha / 2) * len(finite))))
    return {"lo": round(finite[lo_i], 4), "hi": round(finite[hi_i], 4),
            "resamples_with_zero_denominator": n_inf,
            "method": "paired percentile over flight-spec index"}


def analyse(rows, n_boot, seed):
    """Cell counts first. Inference only where the stopping rules allow it."""
    rng = random.Random(seed)
    by_arm, excluded = {}, []
    for arm in ARMS:
        ok = []
        for r in rows:
            if r["arm"] != arm or "error" in r:
                continue
            if r.get("window_coverage", 0.0) < PREREG["min_window_coverage"]:
                excluded.append({
                    "arm": arm, "spec_id": r["spec_id"],
                    "window_coverage": r.get("window_coverage"),
                    "why": "the armed window did not cover the conditioning "
                           "window; including it would put a shortened "
                           "denominator into the estimate"})
                continue
            ok.append(r)
        by_arm[arm] = ok

    cells = {}
    for arm, ok in by_arm.items():
        cells[arm] = {
            "flights_attempted": sum(1 for r in rows if r["arm"] == arm),
            "flights_usable": len(ok),
            "flights_excluded_for_coverage": sum(
                1 for e in excluded if e["arm"] == arm),
            "monitored_ticks": sum(
                r["monitored_ticks_after_injection"] for r in ok),
            "closed_ticks": sum(
                r["closed_ticks_after_injection"] for r in ok),
            "flights_with_at_least_one_closure":
                sum(1 for r in ok if r["closed_ticks_after_injection"] > 0),
            "per_flight_p": [r["p_closed_after_injection"] for r in ok],
            "whole_window_secondary": {
                "monitored_ticks": sum(r["monitored_ticks"] for r in ok),
                "closed_ticks": sum(r["closed_ticks"] for r in ok),
                "per_flight_p": [r["p_closed"] for r in ok],
            },
        }

    gate = {}
    for arm, ok in by_arm.items():
        gate[arm] = len(ok) >= PREREG["min_flights_for_inference"]
    inference_permitted = all(gate.values())

    est = {}
    if inference_permitted:
        for arm, ok in by_arm.items():
            ps = [r["p_closed_after_injection"] for r in ok]
            est[arm] = {
                "q_gvalid": round(_mean(ps), 6),
                "ci95": bca_ci(ps, rng, n_boot),
                "per_flight": [round(p, 6) for p in ps],
                "concentrated_in_two_or_fewer_flights":
                    0 < sum(1 for p in ps if p > 0) <= 2,
            }

    ratios = {}
    if inference_permitted:
        base = [r["p_closed_after_injection"] for r in by_arm["nominal"]]
        for arm in ("denial", "glitch", "degraded"):
            arr = [r["p_closed_after_injection"] for r in by_arm[arm]]
            q_n, q_f = _mean(base), _mean(arr)
            entry = {"point": (None if q_n == 0 else round(q_f / q_n, 4)),
                     "ci95": paired_ratio_ci(arr, base, rng, n_boot)}
            if q_n == 0.0:
                entry["stopping_rule"] = (
                    "spec section 4: zero closures in the nominal arm. The "
                    "ratio is unbounded above. Reported as a one-sided "
                    "statement only.")
                entry["one_sided"] = (
                    "R = infinity as a point estimate; the finite content is "
                    f"q_gvalid|{arm} = {q_f:.6f} against "
                    "q_gvalid|nominal = 0.000000")
            if q_f == 0.0:
                entry["zero_in_fault_arm"] = (
                    "spec section 5: the gate did not close under this fault. "
                    "For this fault class the design-time and effective "
                    "partitions coincide operationally.")
            ratios[arm] = entry
    return cells, inference_permitted, gate, est, ratios, excluded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--eeprom", default=DEFAULT_EEPROM)
    ap.add_argument("--speedup", type=int, default=10)
    ap.add_argument("--flights", type=int,
                    default=PREREG["n_flights_per_arm"])
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_sitl_wd"))
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--ekf-failsafe", action="store_true",
                    help="leave ArduPilot's EKF failsafe at its default so "
                         "the autopilot's OWN response to the injection is "
                         "measured. Truncates the observation window, so "
                         "this is a separate sub-experiment, not the "
                         "campaign.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    verbose = not args.quiet

    os.makedirs(RESULTS, exist_ok=True)
    out_path = args.out or os.path.join(
        RESULTS, "q_gvalid_campaign_ekf_failsafe.json"
        if args.ekf_failsafe else "q_gvalid_campaign.json")

    ready, avail = locate_sitl(args.binary, args.eeprom)
    if not ready:
        report = {
            "status": "SITL_UNAVAILABLE",
            "measured": None,
            "availability": avail,
            "explicitly_not_done": (
                "The internal CSIA simulator was NOT run in place of the "
                "autopilot. A synthetic denial would measure the fault model, "
                "not an autopilot, and the brief forbids labelling that real."),
            "exactly_what_is_needed": [
                "curl -sSLO https://dronekit-assets.s3.amazonaws.com/sitl/"
                "copter/sitl-linux-copter-3.3.tar.gz",
                "mkdir -p sitl && tar xf sitl-linux-copter-3.3.tar.gz -C sitl",
                "pip install pymavlink",
                "export CSIA_SITL_BINARY=$PWD/sitl/apm "
                "CSIA_SITL_EEPROM=$PWD/sitl/default_eeprom.bin",
                "PYTHONPATH=. python research/wp_c6/q_gvalid_campaign.py",
            ],
            "preregistration": PREREG,
        }
        with open(out_path, "w") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
        print("status: SITL_UNAVAILABLE")
        print(json.dumps(avail, indent=1))
        for s in report["exactly_what_is_needed"]:
            print("  " + s)
        return 0

    specs = FLIGHT_SPECS[:args.flights]
    rows = []
    t_start = time.time()
    for arm_name, arm_cfg in ARMS.items():
        for spec in specs:
            if verbose:
                print(f"  {arm_name:9s} spec {spec['id']} "
                      f"wind {spec['wind'][0]:.0f} m/s ...", flush=True)
            rec = fly(args.binary, args.eeprom, spec, arm_name, arm_cfg,
                      args.speedup, args.workdir, verbose,
                      ekf_failsafe=args.ekf_failsafe)
            rows.append(rec)
            if verbose:
                if "error" in rec:
                    print(f"      ERROR {rec['error']}")
                else:
                    print(f"      airborne@{rec['airborne_at_s']} "
                          f"alt {rec['max_relative_alt_m']:.0f} m | "
                          f"monitored {rec['monitored_ticks']:5d} "
                          f"closed {rec['closed_ticks']:5d} "
                          f"p={rec['p_closed']} "
                          f"post-inj p={rec['p_closed_after_injection']} "
                          f"fix={rec['gps_fix_types_seen']}")

    cells, permitted, gate, est, ratios, excluded = analyse(
        rows, PREREG["bootstrap_resamples"], PREREG["bootstrap_seed"])

    report = {
        "status": "MEASURED",
        "generator": "ArduCopter SITL (dronekit-assets copter 3.3) driven "
                     "over MAVLink; ingestion through the production "
                     "csia.runtime.plugins.map_mavlink adapter and the "
                     "production OnlineTrustLayer",
        "this_is_a_simulator": (
            "Every figure is q_gvalid under ArduPilot's SIM GPS fault models. "
            "It is not a measurement of real GNSS environments and must not "
            "be reported as one. Section 7 of the measurement spec stands."),
        "preregistration": PREREG,
        "arms": {k: v["what_it_models"] for k, v in ARMS.items()},
        "ekf_failsafe_left_at_default": bool(args.ekf_failsafe),
        "speedup": args.speedup,
        "wall_seconds": round(time.time() - t_start, 1),
        "cell_counts": cells,
        "flights_excluded": excluded,
        "inference_permitted": permitted,
        "stopping_rule_gate_per_arm": gate,
        "q_gvalid_by_arm": est,
        "ratios_against_nominal": ratios,
        "per_flight": rows,
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print("\n=== CELL COUNTS (spec section 4: these come first) ===")
    print(f"{'arm':<10s} {'flights':>8s} {'monitored':>10s} {'closed':>8s} "
          f"{'flights>=1':>11s}")
    for arm, c in cells.items():
        print(f"{arm:<10s} {c['flights_usable']:>8d} "
              f"{c['monitored_ticks']:>10d} {c['closed_ticks']:>8d} "
              f"{c['flights_with_at_least_one_closure']:>11d}")
    print(f"\ninference permitted: {permitted}")
    if permitted:
        print(f"\n{'arm':<10s} {'q_gvalid':>10s}  95% CI")
        for arm, e in est.items():
            ci = e["ci95"] or {}
            print(f"{arm:<10s} {e['q_gvalid']:>10.6f}  "
                  f"[{ci.get('lo')}, {ci.get('hi')}] ({ci.get('method')})")
        print()
        for arm, r in ratios.items():
            print(f"R({arm}/nominal) = {r['point']}  ci={r['ci95']}")
            for k in ("stopping_rule", "one_sided", "zero_in_fault_arm"):
                if k in r:
                    print(f"    {k}: {r[k]}")
    print(f"\nwrote {os.path.relpath(out_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
