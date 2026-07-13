"""Prediction comparator: turns raw sensor streams into per-edge consistency
residuals and per-sensor predictor disagreement, aligned on the trust
engine's tick timeline.

CSIA role: implements the three-predictor comparison. For sensor i at tick k:
  physics prediction   — internal physical self-model (e.g. GPS position
                         derivative must match Doppler velocity)
  historical prediction— Holt level+trend forecast (predictors.py)
  neighbor prediction  — the value implied by each graph neighbor through
                         the edge's physical relationship; expressed here as
                         the edge residual lambda_ij = (r/sigma)^2

Every residual is a *normalized squared innovation* lambda; the trust engine
maps it to a consistency score c = exp(-lambda/2) in (0, 1].

Gating: each edge carries a gate weight in [0, 1] per tick. The
heading_course (mag<->GPS course-over-ground) edge is gated by horizontal
speed — COG only constrains heading when the vehicle translates; a quadrotor
hovering or yawing in place makes COG noise-dominated garbage, so below
GATE_SPEED_LO m/s the edge contributes nothing, with full weight above
GATE_SPEED_HI m/s. This mirrors what a real airframe needs (quads slip
sideways freely; the constraint is regime-dependent, not universal).
"""

import numpy as np

from ..sensors.truth import (AVIONICS_CURRENT, G, HOVER_CURRENT_PER_MOTOR,
                             HOVER_RPM, MASS, PACK_R_INTERNAL)
from .attitude import (calibrate_imu_stream, complementary_attitude,
                       mag_heading_from_field, wrap_angle)
from .predictors import HIST_CHANNELS, ew_smooth, historical_scores

GATE_SPEED_LO = 2.0  # m/s — heading_course edge contributes nothing below
GATE_SPEED_HI = 3.0  # m/s — full weight above

HOVER_THRUST_PER_MOTOR = MASS * G / 4.0


class TickData:
    """Comparator output aligned on the engine tick timeline.

    edges: {edge_key: (node_a, node_b, lam[K], gate[K])}
    physics: {sensor: lam[K]}         — internal physics predictor
    hist: {sensor: lam[K]}            — historical predictor
    var_ratio: {sensor: ratio[K]}     — innovation whiteness statistic
    fresh: {sensor: bool[K]}          — sensor produced valid data at tick
    """

    def __init__(self, ticks):
        self.t = ticks
        self.edges = {}
        self.physics = {}
        self.hist = {}
        self.var_ratio = {}
        self.fresh = {}
        self.aux = {}


def _align(t_src, x, ticks):
    """Sample-and-hold alignment of a stream onto the tick timeline."""
    idx = np.clip(np.searchsorted(t_src, ticks, side="right") - 1, 0, None)
    return np.asarray(x)[idx]


class PredictionComparator:
    def __init__(self, tick_hz: float = 25.0):
        self.tick_hz = tick_hz

    def build(self, streams: dict, duration: float) -> TickData:
        ticks = np.arange(0.0, duration, 1.0 / self.tick_hz)
        td = TickData(ticks)
        al = lambda name, x: _align(streams[name]["t"], x, ticks)

        # --- per-stream preprocessing (sensor-driver level, done once) -------
        imu = {n: calibrate_imu_stream(streams[n]) for n in ("imu0", "imu1")}
        att = {n: complementary_attitude(imu[n]["t"], imu[n]["accel"],
                                         imu[n]["gyro"]) for n in imu}
        gps = streams["gps"]
        gdt = float(np.mean(np.diff(gps["t"])))
        # All derivatives are strict BACKWARD differences on the stream's
        # native timeline: an online implementation cannot see the next
        # sample, and the phase-4 causality test enforces this.
        gps_fd_vel = _bdiff(gps["pos"], gdt)          # COG velocity
        gps_fd_dvel = _bdiff(gps["vel"], gdt)         # Doppler acceleration
        mag_heading = mag_heading_from_field(
            streams["mag"]["field_ut"],
            _align(imu["imu0"]["t"], att["imu0"], streams["mag"]["t"]))

        # --- tick-aligned quantities -----------------------------------------
        a = {}
        for n in imu:
            a[f"{n}_accel"] = al(n, imu[n]["accel"])
            a[f"{n}_gyro"] = al(n, imu[n]["gyro"])
            a[f"{n}_att"] = al(n, att[n])
        a["baro_alt"] = al("baro", streams["baro"]["altitude"])
        a["baro_temp"] = al("baro", streams["baro"]["temp_c"])
        a["mag_field"] = al("mag", streams["mag"]["field_ut"])
        a["mag_heading"] = al("mag", mag_heading)
        a["gps_pos"] = al("gps", gps["pos"])
        a["gps_vel"] = al("gps", gps["vel"])
        a["gps_fd_vel"] = al("gps", gps_fd_vel)
        a["gps_valid"] = al("gps", gps["valid"].astype(float))
        a["rpm"] = al("motor_esc", streams["motor_esc"]["rpm"])
        a["esc_i"] = al("motor_esc", streams["motor_esc"]["current"])
        a["batt_v"] = al("battery", streams["battery"]["voltage"])
        a["batt_i"] = al("battery", streams["battery"]["current"])
        vib_t = streams["vibration"]["t_rms"]
        a["vib_rms"] = _align(vib_t, streams["vibration"]["rms"], ticks)

        vh = np.hypot(a["gps_vel"][:, 0], a["gps_vel"][:, 1])
        course = np.arctan2(a["gps_vel"][:, 1], a["gps_vel"][:, 0])
        speed_gate = np.clip((vh - GATE_SPEED_LO)
                             / (GATE_SPEED_HI - GATE_SPEED_LO), 0.0, 1.0)
        ones = np.ones_like(ticks)
        gvalid = a["gps_valid"]

        def lam(resid, sigma, df=1.0):
            # Normalized squared innovation per degree of freedom: a healthy
            # residual averages ~1 (chi-square mean), so the engine scores
            # only the EXCESS over 1 — vector residuals must pass their df
            # or nominal flight would read as chronically inconsistent.
            return ew_smooth((np.asarray(resid) / sigma) ** 2 / df, alpha=0.15)

        # --- edge residuals (neighbor predictions), keyed to trust_graph ------
        E = td.edges
        E["redundant_imu"] = ("imu0", "imu1", lam(np.linalg.norm(
            a["imu0_accel"] - a["imu1_accel"], axis=1), 0.09, df=3), ones)

        # Accel<->Motor edges: thrust model. current ~ rpm^3, thrust ~ rpm^2,
        # so specific force z ~ (sum thrust)/m; compare against body accel z.
        f_from_rpm = (HOVER_THRUST_PER_MOTOR
                      * ((a["rpm"] / HOVER_RPM) ** 2).sum(axis=1)) / MASS
        f_from_cur = (HOVER_THRUST_PER_MOTOR * ((np.clip(
            a["esc_i"], 0, None) / HOVER_CURRENT_PER_MOTOR) ** (2.0 / 3.0)
        ).sum(axis=1)) / MASS
        # Only meaningful once armed (idle thrust on ground doesn't lift).
        armed_gate = np.clip((ticks - 5.0) / 1.0, 0.0, 1.0)
        E["accel_motor_current"] = ("imu0", "motor_esc", lam(
            a["imu0_accel"][:, 2] - f_from_cur, 0.45), armed_gate)
        E["accel_esc_rpm"] = ("imu1", "motor_esc", lam(
            a["imu1_accel"][:, 2] - f_from_rpm, 0.45), armed_gate)

        E["altitude_baro"] = ("baro", "gps", lam(
            a["baro_alt"] - a["gps_pos"][:, 2], 2.2), gvalid)

        # Velocity<->GPS Doppler: world-frame accel from IMU (attitude from
        # the complementary filter) vs finite-difference of Doppler velocity.
        a["gps_fd_dvel"] = al("gps", gps_fd_dvel)
        for n, key in (("imu0", "velocity_gps_doppler_0"),
                       ("imu1", "velocity_gps_doppler_1")):
            f_w = _body_to_world(a[f"{n}_accel"], a[f"{n}_att"])
            f_w[:, 2] -= G
            E[key] = (n, "gps", lam(np.linalg.norm(
                ew_smooth_cols(f_w, 0.1) - ew_smooth_cols(a["gps_fd_dvel"], 0.1),
                axis=1), 1.6, df=3), gvalid)

        # Attitude<->Gravity/Mag: mag heading vs gyro-integrated yaw.
        # sigma budgets ~2-3 deg of complementary-filter attitude error
        # leaking into the tilt compensation, on top of mag noise.
        E["attitude_gravity_mag"] = ("imu0", "mag", lam(
            wrap_angle(a["mag_heading"] - a["imu0_att"][:, 2]),
            np.deg2rad(5.0)), ones)

        # Mag Heading <-> GPS course-over-ground — SPEED GATED (see module
        # docstring): a quad's heading is not slaved to its velocity vector.
        E["heading_course"] = ("mag", "gps", lam(
            wrap_angle(a["mag_heading"] - course), np.deg2rad(10.0)),
            speed_gate * gvalid)

        # Known constant avionics load (FC + Pi 5) sits on the pack but not
        # on the ESCs — subtract it or the edge carries a permanent offset.
        E["power_thrust"] = ("motor_esc", "battery", lam(
            a["batt_i"] - a["esc_i"].sum(axis=1) - AVIONICS_CURRENT, 0.5), ones)

        rms_pred = np.sqrt((0.35 * a["rpm"].mean(axis=1) / HOVER_RPM
                            / np.sqrt(2.0)) ** 2 + 0.08 ** 2)
        E["vibration_prop_freq"] = ("vibration", "motor_esc", lam(
            a["vib_rms"] - rms_pred, 0.035), ones)

        # Temp<->Bias-Drift annotation edge: plausibility of temp rate only.
        dtemp = _bdiff(ew_smooth(a["baro_temp"], 0.05), 1.0 / self.tick_hz)
        E["temp_bias_drift"] = ("baro", "battery", lam(dtemp, 0.5),
                                0.2 * ones)

        # --- internal physics predictors: {sensor: (lam, gate)} ---------------
        # gate = 0 means "check not informative here" (no evidence), which the
        # engine treats as absent — NOT as consistent.
        P = td.physics
        # GPS: the spoof catcher. Reported position's derivative must match
        # the independently-measured Doppler velocity.
        # Matched detector for bias-type faults (spoof drift): smooth the
        # residual VECTOR before taking the norm — zero-mean fd noise
        # (~0.8 m/s per horizontal axis, ~1.5 m/s vertical at 10 Hz)
        # averages away over ~1 s while a persistent spoof offset survives
        # at full strength. sigma is the post-smoothing noise scale.
        r_gps = ew_smooth_cols(a["gps_fd_vel"] - a["gps_vel"], 0.1)
        # Gated during the ground-calibration window (smoother warm-up).
        P["gps"] = (lam(np.linalg.norm(r_gps, axis=1), 0.45, df=3),
                    gvalid * (ticks > 3.0))
        # Battery: terminal V must track (slow OCV estimate) - I*R.
        ocv = ew_smooth(a["batt_v"] + a["batt_i"] * PACK_R_INTERNAL, 0.01)
        P["battery"] = (lam(a["batt_v"] - (ocv - a["batt_i"] * PACK_R_INTERNAL),
                            0.06), ones)
        # Motor: per-motor current vs rpm^3 law.
        i_pred = HOVER_CURRENT_PER_MOTOR * (a["rpm"] / HOVER_RPM) ** 3
        P["motor_esc"] = (lam(np.abs(a["esc_i"] - i_pred).mean(axis=1), 0.2),
                          ones)
        # Mag: field magnitude vs local field model.
        P["mag"] = (lam(np.linalg.norm(a["mag_field"], axis=1)
                        - np.hypot(22.0, 42.0), 0.6), ones)
        # IMUs: intentionally NO internal physics check. |f| = G only holds
        # in unaccelerated flight, and a slow accel bias is indistinguishable
        # from a slow climb using |f| alone — a check that can't separate
        # fault from maneuver adds false evidence, not information. IMU
        # health is judged entirely through its graph edges (dual-IMU,
        # motor/RPM, GPS-Doppler, mag).
        # Baro: climb-rate plausibility envelope.
        alt_rate = _bdiff(ew_smooth(a["baro_alt"], 0.1), 1.0 / self.tick_hz)
        P["baro"] = (lam(np.clip(np.abs(alt_rate) - 8.0, 0.0, None), 3.0), ones)
        # Vibration: RMS vs own expected envelope (same law as the edge; the
        # edge implicates motor_esc too, this implicates only the vib node).
        P["vibration"] = (lam(a["vib_rms"] - rms_pred, 0.05), ones)

        # --- historical predictor + whiteness ---------------------------------
        for name, channels in HIST_CHANNELS.items():
            # The vibration hist channel (rms) lives on the 10 Hz RMS
            # timeline, not the sensor's raw 1 kHz timeline.
            src = dict(streams[name])
            t_src = src["t_rms"] if name == "vibration" else src["t"]
            lam_h, vr = historical_scores(src, channels)
            td.hist[name] = _align(t_src, lam_h, ticks)
            td.var_ratio[name] = _align(t_src, vr, ticks)

        for name in HIST_CHANNELS:
            v = streams[name].get("valid")
            td.fresh[name] = al(name, v.astype(float)) > 0.5 if v is not None \
                else np.ones(len(ticks), dtype=bool)

        td.aux = {"speed_gate": speed_gate, "vh": vh, "course": course,
                  "mag_heading": a["mag_heading"],
                  "imu_yaw": a["imu0_att"][:, 2]}
        return td


def _bdiff(x: np.ndarray, dt: float) -> np.ndarray:
    """Causal (backward) difference; first sample repeats to keep length.
    np.gradient is centered and therefore acausal — never use it on
    measurement streams here (the simulator's truth generator may)."""
    d = np.diff(np.asarray(x, dtype=float), axis=0) / dt
    return np.concatenate([d[:1], d], axis=0)


def _body_to_world(vec_b: np.ndarray, att: np.ndarray) -> np.ndarray:
    """Transpose of sensors.truth.world_to_body."""
    r, p, y = att[:, 0], att[:, 1], att[:, 2]
    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    R = np.empty((len(r), 3, 3))
    R[:, 0, 0] = cp * cy
    R[:, 0, 1] = cp * sy
    R[:, 0, 2] = -sp
    R[:, 1, 0] = sr * sp * cy - cr * sy
    R[:, 1, 1] = sr * sp * sy + cr * cy
    R[:, 1, 2] = sr * cp
    R[:, 2, 0] = cr * sp * cy + sr * sy
    R[:, 2, 1] = cr * sp * sy - sr * cy
    R[:, 2, 2] = cr * cp
    return np.einsum("nji,nj->ni", R, vec_b)  # transpose: body -> world


def ew_smooth_cols(x: np.ndarray, alpha: float) -> np.ndarray:
    out = np.empty_like(x)
    for c in range(x.shape[1]):
        out[:, c] = ew_smooth(x[:, c], alpha)
    return out
