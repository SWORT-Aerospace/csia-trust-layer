"""RB-001 Parts 3-5: maneuver-aware candidates for the physical-response
evidence. RESEARCH ONLY. Nothing here is wired into the product.

THE PROBLEM
-----------
CSIA 2.3's compensation statistic C (stock_stats.event_changes) reads the
closed loop asking one motor for more than the others. A maneuver moves the
command split the same way, so 2.3 (calibration r3) refuses C when the body
rates show the vehicle was not near-steady (NOT_STEADY_FLIGHT). That removed
the false COMMAND_NO_RESPONSE on maneuvering flights and opened a coverage
hole: a loss during continuous maneuvering is not confirmed (V13).

THE CANDIDATES (all evaluated at the product's own discovered events, AFTER
checkpoint, BEFORE = [t0-5, t0-0.5), AFTER = [t0+10, t0+15)):

| id | statistic | regime handling | source |
|---|---|---|---|
| B0 | C (2.3) | refused above theta_steady (2.3 r3, hover nulls) | the current product |
| B1 | C (2.3) | steadiness threshold loosened to 2 x the calibration maneuvering null of R | the brief's "looser threshold" |
| B2 | C (2.3) | threshold on C conditioned on the regime R (bins of peak body rate), each 2 x the calibration null in its bin | regime-conditioned / gain-scheduled thresholds |
| B3 | delta_m, control-conditioned residual | none needed: the residual is conditioned on the commanded torque | analytical redundancy: torque demand against measured angular acceleration |
| B4 | GLR_m on the same residual, motor-specific time-varying signature, heteroscedastic noise model | variance conditioned on the body rate | Willsky & Jones (1976) GLR; heteroscedastic residual evaluation |

THE CONTROL-CONDITIONED RESIDUAL (B3, B4)
------------------------------------------
PX4 logs the torque the rate controller demanded (vehicle_torque_setpoint,
normalised) and the measured angular acceleration
(vehicle_angular_velocity.xyz_derivative). With a per-axis model fitted on
nominal calibration flights,

    omega_dot_i(t) = g_i * lp(tau_i, T)(t) + c_i

the torque the vehicle failed to produce is

    d_tau(t) = lp(tau, T)(t) - (omega_dot(t) - c) / g.

Nominal flight, maneuvering or not: d_tau ~ 0, because the demand is
explained by the acceleration it caused. A loss on motor m to eta: the loop
demands extra torque it does not get, d_tau ~ (1 - eta) * u_m * b_m, where
u_m is the motor command and b_m the torque one unit of motor m produces
(columns of the pseudo-inverse of the allocator's mixing, fitted from the
calibration flights: u = A_tau * tau + a_T * T + a_0).

B3: delta_m = (mean d_tau . b_m) / (mean u_m * |b_m|^2) over the window,
roll and pitch only, after minus before. delta_m estimates the lost fraction
1 - eta of motor m. VIOLATED on the motor with the largest delta_m when it is
at or above theta_delta.

B4: GLR_m = (sum s_m' W r)^2 / (sum s_m' W s_m), r = d_tau - mean_before(d_tau),
s_m = u_m * b_m, W = diag(1 / sigma_i^2(|omega|)), at 25 Hz. VIOLATED on the
argmax motor when GLR_m >= h_glr and its estimate delta_m > 0.

All five refuse (UNAVAILABLE) when the allocator reports saturation over most
of the AFTER window, as 2.3 does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from csia_evidence_assurance import stock_stats as SS
from csia_evidence_assurance.stock_log import StockLog

TOPICS = ("vehicle_torque_setpoint", "vehicle_thrust_setpoint", "vehicle_angular_velocity",
          "actuator_motors", "control_allocator_status", "vehicle_status",
          "vehicle_land_detected")
LP_T = 0.05          # s, motor/torque lag (chosen on development flights V5, V6)
DECIM_HZ = 25.0      # B4 sample rate
WINDOW = {"BEFORE": (-5.0, -0.5), "AFTER": (10.0, 15.0)}
R_BINS = (0.0, 0.1, 0.3, 0.6, 1.2, math.inf)


# ------------------------------------------------------------------ data
@dataclass
class Flight:
    name: str
    t: np.ndarray                 # 100 Hz grid: vehicle_angular_velocity sample times
    omega: np.ndarray             # (n, 3) rad/s
    omega_dot: np.ndarray         # (n, 3) rad/s^2
    tau: np.ndarray               # (n, 3) normalised torque setpoint, zero-order held
    thrust: np.ndarray            # (n,) normalised collective (-z), zero-order held
    u: np.ndarray                 # (n, 4) motor commands, zero-order held
    u_t: np.ndarray               # actuator_motors sample times
    u_raw: np.ndarray             # (k, 4)
    sat: np.ndarray               # (n,) allocator not achieved or saturated, zero-order held
    in_flight: np.ndarray         # (n,) bool
    stock: StockLog = field(repr=False, default=None)


def _times(d, t0):
    ts = d.get("timestamp_sample")
    ts = ts if ts is not None and np.all(np.asarray(ts) > 0) else d["timestamp"]
    return (np.asarray(ts).astype(np.int64) - t0) * 1e-6


def load(path, name=None) -> Flight:
    from pyulog import ULog
    u = ULog(str(path), list(TOPICS), False)
    t0 = int(u.start_timestamp)
    D = {}
    for d in u.data_list:
        if d.multi_id == 0 and d.name not in D:
            D[d.name] = dict(d.data)
    av = D["vehicle_angular_velocity"]
    t = _times(av, t0)
    order = np.argsort(t, kind="stable")
    t = t[order]
    omega = np.stack([np.asarray(av[f"xyz[{i}]"], float)[order] for i in range(3)], 1)
    wd = np.stack([np.asarray(av[f"xyz_derivative[{i}]"], float)[order] for i in range(3)], 1)
    ts = D["vehicle_torque_setpoint"]
    tt = _times(ts, t0)
    tau = np.stack([SS.zoh(tt, np.asarray(ts[f"xyz[{i}]"], float), t) for i in range(3)], 1)
    th = D["vehicle_thrust_setpoint"]
    thrust = -SS.zoh(_times(th, t0), np.asarray(th["xyz[2]"], float), t)
    am = D["actuator_motors"]
    ut = _times(am, t0)
    ur = np.stack([np.asarray(am[f"control[{m}]"], float) for m in range(4)], 1)
    u_ = SS.zoh(ut, ur, t)
    ca = D.get("control_allocator_status")
    if ca is not None:
        ct = _times(ca, t0)
        bad = ((np.asarray(ca["torque_setpoint_achieved"]) == 0)
               | (np.asarray(ca["thrust_setpoint_achieved"]) == 0))
        for m in range(4):
            k = f"actuator_saturation[{m}]"
            if k in ca:
                bad = bad | (np.asarray(ca[k]) != 0)
        sat = SS.zoh(ct, bad.astype(float), t) > 0.5
    else:
        sat = np.zeros(len(t), bool)
    vs, ld = D["vehicle_status"], D["vehicle_land_detected"]
    armed = SS.zoh(_times(vs, t0), np.asarray(vs["arming_state"], float), t) == 2
    landed = SS.zoh(_times(ld, t0), np.asarray(ld["landed"], float), t) > 0.5
    fl = armed & ~landed & np.isfinite(wd).all(1) & np.isfinite(tau).all(1)
    return Flight(name or str(path), t, omega, wd, tau, thrust, u_, ut, ur, sat, fl,
                  StockLog.from_ulog(path).decimate())


def lowpass(t, x, tau_c):
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, len(x)):
        a = min(1.0, max(t[k] - t[k - 1], 0.0) / tau_c)
        y[k] = y[k - 1] + a * (x[k] - y[k - 1])
    return y


# ------------------------------------------------------------------ the model
@dataclass
class Model:
    g: np.ndarray            # (3,) rad/s^2 per unit normalised torque
    c: np.ndarray            # (3,) rad/s^2
    A: np.ndarray            # (4, 5) mixing: u_m = A[m] . [tau_x, tau_y, tau_z, T, 1]
    B: np.ndarray            # (3, 4) torque per unit motor command: pinv of A's torque block
    sigma_a: np.ndarray      # (3,) heteroscedastic noise of d_tau at 25 Hz: sigma^2 = a + b |omega|^2
    sigma_b: np.ndarray      # (3,)
    fitted_on: list

    def to_dict(self):
        return {"g": self.g.tolist(), "c": self.c.tolist(), "A": self.A.tolist(),
                "B": self.B.tolist(), "sigma_a": self.sigma_a.tolist(),
                "sigma_b": self.sigma_b.tolist(), "lp_T_s": LP_T, "fitted_on": self.fitted_on}

    @classmethod
    def from_dict(cls, d):
        return cls(*(np.asarray(d[k]) for k in ("g", "c", "A", "B", "sigma_a", "sigma_b")),
                   d["fitted_on"])


def residual(f: Flight, mdl: Model) -> np.ndarray:
    tf = np.stack([lowpass(f.t, f.tau[:, i], LP_T) for i in range(3)], 1)
    return tf - (f.omega_dot - mdl.c) / mdl.g


def fit_model(flights) -> Model:
    X, Y = [], []
    for f in flights:
        ok = f.in_flight & ~f.sat
        tf = np.stack([lowpass(f.t, f.tau[:, i], LP_T) for i in range(3)], 1)
        X.append(tf[ok])
        Y.append(f.omega_dot[ok])
    X, Y = np.concatenate(X), np.concatenate(Y)
    g, c = np.zeros(3), np.zeros(3)
    for i in range(3):
        g[i], c[i] = np.polyfit(X[:, i], Y[:, i], 1)
    rows, us = [], []
    for f in flights:
        tq = np.stack([SS.zoh(f.t, f.tau[:, i], f.u_t) for i in range(3)], 1)
        T = SS.zoh(f.t, f.thrust, f.u_t)
        fl = SS.zoh(f.t, (f.in_flight & ~f.sat).astype(float), f.u_t) > 0.5
        rows.append(np.column_stack([tq, T, np.ones(len(T))])[fl])
        us.append(f.u_raw[fl])
    Rx, U = np.concatenate(rows), np.concatenate(us)
    A = np.linalg.lstsq(Rx, U, rcond=None)[0].T          # (4, 5)
    B = np.linalg.pinv(A[:, :3])                          # (3, 4)
    mdl = Model(g, c, A, B, np.zeros(3), np.zeros(3), [f.name for f in flights])
    ra, rb = [], []
    for f in flights:
        d = residual(f, mdl)
        ok = f.in_flight & ~f.sat
        step = max(int(round(100.0 / DECIM_HZ)), 1)
        idx = np.flatnonzero(ok)[::step]
        ra.append(d[idx])
        rb.append(np.linalg.norm(f.omega[idx], axis=1) ** 2)
    ra, rb = np.concatenate(ra), np.concatenate(rb)
    sa, sb = np.zeros(3), np.zeros(3)
    for i in range(3):
        coef = np.linalg.lstsq(np.column_stack([np.ones(len(rb)), rb]), ra[:, i] ** 2, rcond=None)[0]
        sa[i], sb[i] = max(coef[0], 1e-12), max(coef[1], 0.0)
    mdl.sigma_a, mdl.sigma_b = sa, sb
    return mdl


# ------------------------------------------------------------------ statistics
def _mask(t, t0, w):
    a, b = WINDOW[w]
    return (t >= t0 + a) & (t < t0 + b)


def peak_rate(f: Flight, t0, w):
    """2.3's steadiness statistic, on the decimated stock log exactly as the
    product computes it (stock_stats.peak_rate)."""
    return SS.peak_rate(f.stock, t0, w)


def saturated(f: Flight, t0):
    m = _mask(f.t, t0, "AFTER") & f.in_flight
    return bool(m.any() and f.sat[m].mean() > 0.5)


def comp_C(f: Flight, t0):
    """2.3's C per motor (stock_stats on the decimated stock log)."""
    ms = SS.motor_series(f.stock)
    if ms is None:
        return [float("nan")] * 4, [0] * 4
    ch = SS.event_changes(ms, t0)
    return ch["C_AFTER"], [min(a, b) for a, b in zip(ch["n_before"], ch["n_AFTER"])]


def delta_b3(f: Flight, mdl: Model, d_tau, t0):
    """Per motor: lost-fraction estimate, AFTER minus BEFORE, roll and pitch."""
    out = []
    for w in ("BEFORE", "AFTER"):
        m = _mask(f.t, t0, w) & f.in_flight
        if m.sum() < 100:
            return [float("nan")] * 4
        dt = d_tau[m, :2].mean(0)
        row = []
        for k in range(4):
            b = mdl.B[:2, k]
            um = f.u[m, k].mean()
            row.append(float(dt @ b / (um * (b @ b))) if um > SS.MIN_COMMAND else float("nan"))
        out.append(row)
    return [a - b for a, b in zip(out[1], out[0])]


def glr_b4(f: Flight, mdl: Model, d_tau, t0):
    """Per motor: (GLR, delta estimate) on the AFTER window against the BEFORE mean."""
    mb = _mask(f.t, t0, "BEFORE") & f.in_flight
    ma = _mask(f.t, t0, "AFTER") & f.in_flight
    if mb.sum() < 100 or ma.sum() < 100:
        return [(float("nan"), float("nan"))] * 4
    step = max(int(round(100.0 / DECIM_HZ)), 1)
    ia = np.flatnonzero(ma)[::step]
    r = d_tau[ia] - d_tau[mb].mean(0)
    w2 = np.linalg.norm(f.omega[ia], axis=1) ** 2
    W = 1.0 / (mdl.sigma_a[None, :] + mdl.sigma_b[None, :] * w2[:, None])
    out = []
    for k in range(4):
        s = f.u[ia, k][:, None] * mdl.B[:, k][None, :]
        num = float(np.sum(s * W * r))
        den = float(np.sum(s * W * s))
        out.append((num * num / den, num / den) if den > 0 else (float("nan"), float("nan")))
    return out


def statistics_at(f: Flight, mdl: Model, d_tau, t0) -> dict:
    C, n = comp_C(f, t0)
    return {"t0": round(float(t0), 3),
            "R": max(peak_rate(f, t0, "BEFORE"), peak_rate(f, t0, "AFTER")),
            "saturated": saturated(f, t0), "C": C, "n": n,
            "delta": delta_b3(f, mdl, d_tau, t0),
            "glr": glr_b4(f, mdl, d_tau, t0)}


# ------------------------------------------------------------------ decisions
def _bin(R):
    for i in range(len(R_BINS) - 1):
        if R_BINS[i] <= R < R_BINS[i + 1]:
            return i
    return None


def decide(cand: str, s: dict, cal: dict) -> list:
    """Per motor state: VIOLATED, NOT_VIOLATED or UNAVAILABLE (with the reason)."""
    if s["saturated"]:
        return ["UNAVAILABLE:SATURATED"] * 4
    if cand in ("B0", "B1", "B2"):
        R = s["R"]
        if not math.isfinite(R):
            return ["UNAVAILABLE:NO_RATES"] * 4
        if cand == "B0" and R > cal["theta_steady_r3"]:
            return ["UNAVAILABLE:NOT_STEADY"] * 4
        if cand == "B1" and R > cal["theta_steady_B1"]:
            return ["UNAVAILABLE:NOT_STEADY"] * 4
        th = cal["theta_ctrl_r3"]
        if cand == "B2":
            b = _bin(R)
            th = cal["theta_C_by_bin"][b] if b is not None else None
            if th is None:
                return ["UNAVAILABLE:REGIME_NOT_CALIBRATED"] * 4
        return [("VIOLATED" if (math.isfinite(c) and c >= th) else
                 "NOT_VIOLATED" if math.isfinite(c) and n >= 10 else "UNAVAILABLE:NOT_MEASURABLE")
                for c, n in zip(s["C"], s["n"])]
    if cand == "B3":
        d = s["delta"]
        if not all(math.isfinite(x) for x in d):
            return ["UNAVAILABLE:NOT_MEASURABLE"] * 4
        k = int(np.argmax(d))
        return ["VIOLATED" if (j == k and d[j] >= cal["theta_delta"]) else "NOT_VIOLATED"
                for j in range(4)]
    if cand == "B4":
        g = s["glr"]
        if not all(math.isfinite(x[0]) for x in g):
            return ["UNAVAILABLE:NOT_MEASURABLE"] * 4
        # argmax among motors whose estimate is a LOSS: diagonal motors have
        # near-opposite signatures, so both get a large GLR (development, V1-V4)
        pos = [j for j in range(4) if g[j][1] > 0]
        if not pos:
            return ["NOT_VIOLATED"] * 4
        k = max(pos, key=lambda j: g[j][0])
        return ["VIOLATED" if (j == k and g[j][0] >= cal["h_glr"]) else "NOT_VIOLATED"
                for j in range(4)]
    raise ValueError(cand)


CANDIDATES = ("B0", "B1", "B2", "B3", "B4")
