"""XSYS-001 frozen evidence definitions.

Every statistic the preregistration names is computed HERE and nowhere else.
Calibration (from apparatus data), stage 0 (custodian) and stage 1 (blinded
evidence) all import this module, so a definition cannot drift between the
data that set a threshold and the data it is applied to.

Research-only. It reads ULogs and numbers; it imports nothing from csia/.

Conventions
-----------
* Time is simulated time on the SIH lockstep grid, one sample per 4 ms step
  (the esc_status timestamps). t_rel = (t - t0) in seconds.
* Motor index m is 0-based: m = 0 is SIH Motor1, SIH_MOT_EFF1, CSIA motor_0.
* Windows are half-open [a, b) in t_rel seconds.
"""
from __future__ import annotations

import math

import numpy as np

STEP_S = 0.004
TAU_S = 0.05                         # SIH_T_TAU default; the rotor lag (sih.cpp:374)
ALPHA = STEP_S / TAU_S               # 0.08
RPM_MAX = 10000.0                    # sih.cpp publish_esc_status, multicopter
MIN_COMMAND = 0.15                   # v2 ActuatorSpec.min_command: below it no response is judged

WINDOWS = {
    "T0": (-5.0, 0.0),               # pre-fault baseline
    "T1": (0.0, 0.2),                # early physical transient
    "T2": (0.2, 2.0),                # compensation transition (descriptive only)
    "T3": (10.0, 15.0),              # post-compensation
}
ANALYSIS_SPAN = (-5.0, 15.0)         # every trial must cover this span


def window_mask(t_rel, name):
    a, b = WINDOWS[name]
    return (t_rel >= a - 1e-9) & (t_rel < b - 1e-9)


# ------------------------------------------------------------------ W_RPM
def healthy_rotor_u(cmd, u_init):
    """Rotor state a HEALTHY rotor would have for this command history.

    cmd: the command SIH received at each step (actuator_outputs_sim, paired
    as the latest sample stamped strictly before the step). Same first-order
    lag as SIH (tau = 0.05 s at 4 ms), started from the observed state at the
    first sample.
    """
    u = np.empty(len(cmd))
    u[0] = u_init
    for k in range(1, len(cmd)):
        u[k] = u[k - 1] + ALPHA * (cmd[k] - u[k - 1])
    return u


def rpm_ratio(rpm_obs, cmd, k_start=0):
    """rho = observed RPM / RPM a healthy rotor would show, per step.

    The local ESC-monitor symptom. rho^2 is the implied fraction of expected
    thrust (SIH: thrust proportional to u, RPM = 1e4 sqrt(u)).
    """
    u0 = (rpm_obs[k_start] / RPM_MAX) ** 2
    u_exp = healthy_rotor_u(cmd[k_start:], u0)
    rpm_exp = RPM_MAX * np.sqrt(np.clip(u_exp, 0.0, 1.0))
    rho = np.full(len(rpm_obs), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        rho[k_start:] = np.where(rpm_exp > 0, rpm_obs[k_start:] / rpm_exp, np.nan)
    exp_full = np.full(len(rpm_obs), np.nan)
    exp_full[k_start:] = rpm_exp
    return rho, exp_full


def local_deficit(rho, cmd, t_rel, window):
    """L_W = mean over W of (1 - rho^2): implied fractional thrust deficit.

    Returns (L, measurable). Not measurable when the window has no samples or
    the mean command is below MIN_COMMAND.
    """
    m = window_mask(t_rel, window) & np.isfinite(rho)
    if m.sum() == 0 or np.nanmean(cmd[m]) < MIN_COMMAND:
        return float("nan"), False
    return float(np.mean(1.0 - rho[m] ** 2)), True


# ------------------------------------------------------------------ W_DYN
def loss_axis(px, py):
    """Unit (roll, pitch) direction of the body-rate response to a THRUST LOSS
    on a rotor at body position (px, py), from r x F with F along -z:
    dM = (py, -px) |dT|. Rotor geometry comes from CA_ROTORn_PX/PY."""
    v = np.array([py, -px], dtype=float)
    return v / np.linalg.norm(v)


def dynamics_statistic(gyro, t_rel, axis, window):
    """D_W = mean over W of (omega - mean_T0 omega) projected on the loss axis.

    gyro: (n, 3) measured body rates (sensor_combined.gyro_rad), rad/s. Only
    roll and pitch enter. Returns (D, measurable).
    """
    m0 = window_mask(t_rel, "T0")
    mw = window_mask(t_rel, window)
    if m0.sum() < 100 or mw.sum() == 0:
        return float("nan"), False
    base = gyro[m0, :2].mean(axis=0)
    return float(((gyro[mw, :2] - base) @ axis).mean()), True


# ------------------------------------------------------------------ W_CTRL
def compensation_statistic(cmd_alloc, t_rel, m, window):
    """C_W = mean_W(kappa_m) - mean_T0(kappa_m), kappa_m = c_m / mean_{j != m} c_j.

    cmd_alloc: (n, 4) allocator output (actuator_motors.control). Under a
    physical effectiveness eta that the controller compensates, kappa -> 1/eta.
    Returns (C, measurable).
    """
    others = [j for j in range(cmd_alloc.shape[1]) if j != m]
    with np.errstate(divide="ignore", invalid="ignore"):
        kappa = cmd_alloc[:, m] / cmd_alloc[:, others].mean(axis=1)
    m0 = window_mask(t_rel, "T0") & np.isfinite(kappa)
    mw = window_mask(t_rel, window) & np.isfinite(kappa)
    if m0.sum() < 100 or mw.sum() == 0:
        return float("nan"), False
    return float(kappa[mw].mean() - kappa[m0].mean()), True


# ------------------------------------------------------------------ W_EST (exploratory only)
def max_in_window(values, t_rel, window):
    m = window_mask(t_rel, window) & np.isfinite(values)
    return float(np.max(np.abs(values[m]))) if m.sum() else float("nan")


# ------------------------------------------------------------------ three-valued witnesses
def rpm_witness(L, measurable, delta):
    """LOCAL_RPM_DEFICIT: True / False / None."""
    if not measurable or not math.isfinite(L):
        return None
    return L >= delta


def dynamics_witness(D, measurable, L_gate, cal):
    """DYN_NOMINAL for one window: True (dynamics nominal), False (deficit
    response present), None (not measurable).

    Affirming NOMINAL requires that the local symptom implies a response a
    genuine loss would make detectable: s_dyn * L >= 2 theta_dyn. A response
    OPPOSITE to the loss axis is unexplained by either cause: None.
    """
    th, s = cal["theta_dyn"], cal["s_dyn"]
    if not measurable or not math.isfinite(D) or not math.isfinite(L_gate):
        return None
    if D >= th:
        return False
    if D <= -th:
        return None
    return True if s * L_gate >= 2.0 * th else None


def compensation_witness(C, measurable, L_gate, cal):
    """CTRL_NOMINAL for T3: True (no compensation), False (compensation), None.

    A genuine loss with implied effectiveness 1 - L is compensated by
    kappa - 1 = 1/(1 - L) - 1 (apparatus-validated). Affirming NOMINAL needs
    that expected compensation to be at least 2 theta_ctrl.
    """
    th = cal["theta_ctrl"]
    if not measurable or not math.isfinite(C) or not math.isfinite(L_gate) or L_gate >= 1.0:
        return None
    if C >= th:
        return False
    if C <= -th:
        return None
    expected = 1.0 / (1.0 - L_gate) - 1.0
    return True if expected >= 2.0 * th else None
