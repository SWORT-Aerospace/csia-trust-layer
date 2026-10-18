"""The stock propulsion statistics, defined once. OFFBOARD ONLY.

Calibration (`research/csia_2_3_stock_bridge/calibrate_23.py`), the stock
producers and the event-discovery layer all import this module, so a
definition cannot drift between the data that set a threshold and the data
it is applied to (the XSYS-001 discipline).

Every statistic is per motor m, from stock topics only (`stock_log.py`):

| name | definition | stage it reflects |
|---|---|---|
| q_m, telemetry response | (rpm_m^2 / T(c_m)) / median over all motors j of (rpm_j^2 / T(c_j)) | TELEMETRY RESPONSE: ESC-reported rotor speed per commanded thrust, against the other rotors |
| kappa_m, compensation ratio | c_m / median over all motors j of c_j | COMMAND / CONTROLLER COMPENSATION: the closed loop asking one motor for more than the others |

**Median, not mean of the others (calibration revision 2).** With the mean
of the other motors, one motor's change entered every other motor's
denominator: a deficit on motor 0 appeared as an "excess" on motors 1-3.
The median of all motors cannot be moved by a single deviating motor (four
motors: the mean of the middle two).
| R_w, steadiness | the largest body-rate magnitude in window w; the compensation claim assumes near-steady flight (R <= theta_steady) in BEFORE and AFTER | PHYSICAL VEHICLE STATE |
| D_m, rate transient | mean over [t0, t0 + 0.2 s) of (omega - omega_before) projected on motor m's thrust-loss axis | PHYSICAL VEHICLE RESPONSE |

T(c) = (1 - f) c + f c^2 is PX4's thrust model with f = THR_MDL_FAC. Only
samples in flight with command >= MIN_COMMAND are used.

**Event-relative change.** An event at t0 compares windows:
- BEFORE: [t0 - 5, t0 - 0.5);
- EARLY: [t0 + 0.5, t0 + 2);
- AFTER: [t0 + 10, t0 + 15), XSYS-001's T3.

The changes are:
- telemetry deficit L_tel = 1 - q_after / q_before;
- compensation C = kappa_after - kappa_before.

**Change detection (event discovery).** One-sided CUSUM (Page 1954) in
physical units:
- deviation: d(t) = reference - q(t) for the telemetry, kappa(t) - reference
  for the compensation;
- reference: the median over the in-flight samples of [t - 10 s, t - 2 s];
- recursion: S = max(0, S + d - k);
- alarm at S >= h;
- onset estimate: the last sample with S = 0 before the alarm (the usual
  CUSUM change-point estimate).

k and h come from calibration; nothing here sets them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_COMMAND = 0.15
WINDOWS = {"BEFORE": (-5.0, -0.5), "EARLY": (0.5, 2.0), "AFTER": (10.0, 15.0),
           "T1": (0.0, 0.2)}
REF_SPAN = (-10.0, -2.0)


def thrust_model(c, f):
    c = np.clip(np.asarray(c, float), 0.0, 1.0)
    return (1.0 - f) * c + f * c * c


def zoh(t_src, v_src, t_dst):
    i = np.searchsorted(t_src, t_dst, side="right") - 1
    out = np.full((len(t_dst),) + np.asarray(v_src).shape[1:], np.nan)
    ok = i >= 0
    out[ok] = np.asarray(v_src)[i[ok]]
    return out


@dataclass
class MotorSeries:
    """Per-motor series on their own topic clocks, in flight only (NaN
    elsewhere)."""
    t_esc: np.ndarray        # ESC report times
    q: np.ndarray            # (n, motors), telemetry response
    t_cmd: np.ndarray        # allocator output times
    kappa: np.ndarray        # (n, motors), compensation ratio
    command: np.ndarray      # (n, motors), at t_cmd
    n_motors: int


def motor_series(log) -> MotorSeries | None:
    """None when the log lacks the command or the ESC topic, or declares no
    rotors."""
    n = log.n_motors
    if n < 2 or not (log.has("actuator_motors") and log.has("esc_status")):
        return None
    am, es = log.topics["actuator_motors"], log.topics["esc_status"]
    if any(f"control[{m}]" not in am or f"esc[{m}].esc_rpm" not in es for m in range(n)):
        return None
    c = np.stack([am[f"control[{m}]"] for m in range(n)], axis=1)
    rpm = np.stack([es[f"esc[{m}].esc_rpm"] for m in range(n)], axis=1)
    f = float(log.params.get("THR_MDL_FAC") or 0.0)
    c_at = zoh(am["t"], c, es["t"])
    with np.errstate(divide="ignore", invalid="ignore"):
        e = rpm ** 2 / thrust_model(c_at, f)
        q = e / np.median(e, axis=1, keepdims=True)
        kappa = c / np.median(c, axis=1, keepdims=True)
    ok_e = log.in_flight(es["t"])[:, None] & (c_at >= MIN_COMMAND)
    ok_c = log.in_flight(am["t"])[:, None] & (c >= MIN_COMMAND)
    q = np.where(ok_e & np.isfinite(q), q, np.nan)
    kappa = np.where(ok_c & np.isfinite(kappa), kappa, np.nan)
    return MotorSeries(es["t"], q, am["t"], kappa, c, n)


def window_mean(t, v, t0, name):
    a, b = WINDOWS[name]
    m = (t >= t0 + a) & (t < t0 + b)
    x = v[m]
    if x.ndim == 1:
        x = x[np.isfinite(x)]
        return (float(np.mean(x)) if x.size else float("nan")), int(x.size)
    out, n = [], []
    for k in range(x.shape[1]):
        col = x[:, k][np.isfinite(x[:, k])]
        out.append(float(np.mean(col)) if col.size else float("nan"))
        n.append(int(col.size))
    return out, n


def event_changes(ms: MotorSeries, t0: float) -> dict:
    """L_tel (per motor) for EARLY and AFTER, C (per motor) for EARLY and
    AFTER, with the sample counts that make them measurable."""
    qb, nqb = window_mean(ms.t_esc, ms.q, t0, "BEFORE")
    kb, nkb = window_mean(ms.t_cmd, ms.kappa, t0, "BEFORE")
    out = {"q_before": qb, "kappa_before": kb, "n_before": [min(a, b) for a, b in zip(nqb, nkb)]}
    for w in ("EARLY", "AFTER"):
        qa, nqa = window_mean(ms.t_esc, ms.q, t0, w)
        ka, nka = window_mean(ms.t_cmd, ms.kappa, t0, w)
        out[f"L_tel_{w}"] = [1.0 - a / b if np.isfinite(a) and np.isfinite(b) and b > 0
                             else float("nan") for a, b in zip(qa, qb)]
        out[f"C_{w}"] = [a - b for a, b in zip(ka, kb)]
        out[f"n_{w}"] = [min(a, b) for a, b in zip(nqa, nka)]
    return out


def loss_axis(px, py):
    """Unit (roll, pitch) direction of the body-rate response to a thrust
    loss on a rotor at (px, py): r x F with F along -z gives (py, -px)."""
    v = np.array([py, -px], dtype=float)
    return v / np.linalg.norm(v)


def rate_transient(log, t0: float, motor: int):
    """(D, samples) on motor's loss axis in [t0, t0 + 0.2 s) against
    BEFORE, or (nan, 0)."""
    if not log.has("vehicle_angular_velocity"):
        return float("nan"), 0
    px, py = log.params.get(f"CA_ROTOR{motor}_PX"), log.params.get(f"CA_ROTOR{motor}_PY")
    if px is None or py is None:
        return float("nan"), 0
    av = log.topics["vehicle_angular_velocity"]
    g = np.stack([av["xyz[0]"], av["xyz[1]"]], 1)
    base, nb = window_mean(av["t"], g, t0, "BEFORE")
    m = (av["t"] >= t0) & (av["t"] < t0 + 0.2)
    if min(nb) < 10 or not m.any():
        return float("nan"), int(m.sum())
    return float(((g[m] - np.asarray(base)) @ loss_axis(px, py)).mean()), int(m.sum())


# ------------------------------------------------------------------ change detection
def peak_rate(log, t0: float, window: str) -> float:
    """The largest body-rate magnitude |omega| (rad/s) in an event window,
    or NaN. The steadiness test of the compensation claim's assumption
    "near-steady flight in both windows" (claim register)."""
    if not log.has("vehicle_angular_velocity"):
        return float("nan")
    av = log.topics["vehicle_angular_velocity"]
    a, b = WINDOWS[window]
    m = (av["t"] >= t0 + a) & (av["t"] < t0 + b)
    if not m.any():
        return float("nan")
    g = np.stack([av["xyz[0]"][m], av["xyz[1]"][m], av["xyz[2]"][m]], 1)
    return float(np.max(np.linalg.norm(g, axis=1)))


def trailing_reference(t, x):
    """Median of the finite samples in [t - 10, t - 2] for every sample, or
    NaN where fewer than 10 exist."""
    ref = np.full(len(t), np.nan)
    a, b = REF_SPAN
    lo = np.searchsorted(t, t + a, side="left")
    hi = np.searchsorted(t, t + b, side="right")
    for i in range(len(t)):
        w = x[lo[i]:hi[i]]
        w = w[np.isfinite(w)]
        if w.size >= 10:
            ref[i] = np.median(w)
    return ref


def cusum(t, d, k, h):
    """One-sided CUSUM over deviations d (NaN resets and pauses). Returns a
    list of (onset_estimate_t, alarm_t, peak_S) and the S series."""
    S = np.zeros(len(t))
    alarms, s, last_zero = [], 0.0, None
    in_alarm = False
    for i in range(len(t)):
        if not np.isfinite(d[i]):
            s, last_zero, in_alarm = 0.0, None, False
            S[i] = 0.0
            continue
        s = max(0.0, s + d[i] - k)
        S[i] = s
        if s == 0.0:
            last_zero = t[i]
            if in_alarm:
                in_alarm = False
        elif s >= h and not in_alarm:
            in_alarm = True
            onset = last_zero if last_zero is not None else t[i]
            alarms.append([float(onset), float(t[i]), float(s)])
        if in_alarm and alarms:
            alarms[-1][2] = max(alarms[-1][2], float(s))
    return [tuple(a) for a in alarms], S


def deviations(ms: MotorSeries):
    """Per motor: (t, d_tel) with d_tel = ref - q, and (t, d_ctrl) with
    d_ctrl = kappa - ref."""
    out = []
    for m in range(ms.n_motors):
        rq = trailing_reference(ms.t_esc, ms.q[:, m])
        rk = trailing_reference(ms.t_cmd, ms.kappa[:, m])
        out.append({"t_tel": ms.t_esc, "d_tel": rq - ms.q[:, m],
                    "t_ctrl": ms.t_cmd, "d_ctrl": ms.kappa[:, m] - rk})
    return out
