"""XSYS-001 ULog extraction (stage 0 helper, custodian side).

Produces, for one flown trial:

* ONBOARD signals, the only thing stage 1 ever sees: RPM telemetry, the
  command SIH received, the allocator command, measured body rates and
  specific force, estimator test ratios (aligned on timestamp_sample), and
  the static rotor geometry;
* TRUTH signals, for manipulation checks only: SIH ground-truth rates,
  attitude and altitude, and the rotor state reconstructed from the log.

TIME ZERO. t0 is the first SIH step strictly after the parameter_update
publication caused by the trial's single onset parameter change (fault:
SIH_MOT_EFF1; nominal: SDLOG_DIRS_MAX). SIH reloads parameters at the start
of each step, before the rotor update (sih.cpp:227-234, 361-384), so at t0 the
new effectiveness is already in the rotor equation. Command-send time and
MAVLink receipt time are never used.
"""
from __future__ import annotations

import numpy as np
from pyulog import ULog

from xsys_features import ANALYSIS_SPAN, STEP_S

GRID_US = int(round(STEP_S * 1e6))


def _ds(u, name):
    try:
        return u.get_dataset(name, 0).data
    except (KeyError, IndexError, ValueError):
        return None


def _zoh(t_src, v_src, t_grid, strictly_before=False):
    side = "left" if strictly_before else "right"
    i = np.searchsorted(t_src, t_grid, side=side) - 1
    out = np.full((len(t_grid),) + v_src.shape[1:], np.nan)
    ok = i >= 0
    out[ok] = v_src[i[ok]]
    return out


def _by_sample_time(d, field, t_grid):
    """Place estimator values at the step of their timestamp_sample (the
    delayed fusion horizon), then hold. Never by publication time."""
    ts = d["timestamp_sample"].astype(np.int64)
    order = np.argsort(ts, kind="stable")
    return _zoh(ts[order], d[field].astype(float)[order], t_grid)


def onset_time(u, onset_param):
    """(t_param_update_us, t0_us, value) of the single in-flight change of
    onset_param, or None if the log shows none."""
    changes = [(int(t), float(v)) for t, n, v in u.changed_parameters if n == onset_param]
    if not changes:
        return None
    t_rec, value = changes[-1]
    pu = _ds(u, "parameter_update")["timestamp"].astype(np.int64)
    j = np.searchsorted(pu, t_rec - GRID_US)
    t_pu = int(pu[j]) if j < len(pu) else t_rec
    esc_t = _ds(u, "esc_status")["timestamp"].astype(np.int64)
    k = np.searchsorted(esc_t, t_pu, side="right")
    return t_pu, int(esc_t[k]), value


def load_full(path):
    """Every signal on the full-flight SIH step grid, keyed by absolute time."""
    u = ULog(str(path))
    params = dict(u.initial_parameters)
    esc = _ds(u, "esc_status")
    g = esc["timestamp"].astype(np.int64)
    rpm = np.stack([esc[f"esc[{i}].esc_rpm"] for i in range(4)], axis=1).astype(float)
    d = _ds(u, "actuator_outputs_sim")
    cmd_sim = _zoh(d["timestamp"].astype(np.int64),
                   np.stack([d[f"output[{i}]"] for i in range(4)], axis=1).astype(float), g,
                   strictly_before=True)
    d = _ds(u, "actuator_motors")
    cmd_alloc = _zoh(d["timestamp"].astype(np.int64),
                     np.stack([d[f"control[{i}]"] for i in range(4)], axis=1).astype(float), g)
    d = _ds(u, "sensor_combined")
    gyro = _zoh(d["timestamp"].astype(np.int64),
                np.stack([d[f"gyro_rad[{i}]"] for i in range(3)], axis=1).astype(float), g)
    accel = _zoh(d["timestamp"].astype(np.int64),
                 np.stack([d[f"accelerometer_m_s2[{i}]"] for i in range(3)], axis=1).astype(float), g)
    d = _ds(u, "estimator_innovation_test_ratios")
    fields = ["gps_hpos[0]", "gps_hpos[1]", "gps_vpos", "gps_hvel[0]", "gps_hvel[1]", "gps_vvel",
              "baro_vpos", "heading", "mag_field[0]", "mag_field[1]", "mag_field[2]"]
    with np.errstate(all="ignore"):
        ekf = np.nanmax(np.abs(np.stack([_by_sample_time(d, f, g) for f in fields], axis=1)), axis=1)
    d = _ds(u, "hover_thrust_estimate")
    hte = np.abs(_by_sample_time(d, "accel_innov_test_ratio", g))
    onboard = {
        "t_abs_us": g, "rpm_obs": rpm, "cmd_sim": cmd_sim, "cmd_alloc": cmd_alloc,
        "gyro": gyro, "accel": accel, "ekf_test_ratio_max": ekf, "hte_test_ratio": hte,
        "rotor_px": np.array([float(params.get(f"CA_ROTOR{i}_PX", np.nan)) for i in range(4)]),
        "rotor_py": np.array([float(params.get(f"CA_ROTOR{i}_PY", np.nan)) for i in range(4)]),
    }
    d = _ds(u, "vehicle_angular_velocity_groundtruth")
    w_true = _zoh(d["timestamp"].astype(np.int64),
                  np.stack([d[f"xyz[{i}]"] for i in range(3)], axis=1).astype(float), g)
    d = _ds(u, "vehicle_attitude_groundtruth")
    q = _zoh(d["timestamp"].astype(np.int64),
             np.stack([d[f"q[{i}]"] for i in range(4)], axis=1).astype(float), g)
    tilt = np.arccos(np.clip(1 - 2 * (q[:, 1] ** 2 + q[:, 2] ** 2), -1, 1))
    d = _ds(u, "vehicle_local_position_groundtruth")
    alt = -_zoh(d["timestamp"].astype(np.int64), d["z"].astype(float)[:, None], g)[:, 0]
    yaw = np.arctan2(2 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]), 1 - 2 * (q[:, 2] ** 2 + q[:, 3] ** 2))
    truth = {"w_true": w_true, "tilt": tilt, "alt": alt, "yaw": yaw}
    return u, params, onboard, truth


def cut(onboard, truth, t0_us):
    """Slice to ANALYSIS_SPAN around t0 and add t_rel (seconds)."""
    g = onboard["t_abs_us"]
    lo, hi = t0_us + int(ANALYSIS_SPAN[0] * 1e6), t0_us + int(ANALYSIS_SPAN[1] * 1e6)
    sel = (g >= lo) & (g < hi)
    ob = {k: (v[sel] if isinstance(v, np.ndarray) and v.shape[:1] == g.shape else v)
          for k, v in onboard.items() if k != "t_abs_us"}
    ob["t_rel"] = (g[sel] - t0_us) * 1e-6
    tr = {k: v[sel] for k, v in truth.items()}
    return ob, tr, g[sel]


def extract(path, onset_param):
    u, params, onboard, truth = load_full(path)
    ev = onset_time(u, onset_param)
    if ev is None:
        return None, {"error": f"no in-flight change of {onset_param} in the log"}
    t_pu, t0, value = ev
    ob, tr, g = cut(onboard, truth, t0)
    t_rel = ob["t_rel"]
    meta = {"t0_us": t0, "t_param_update_us": t_pu, "onset_param": onset_param, "onset_value": value,
            "n_steps": int(len(g)), "dropouts": len(u.dropouts),
            "grid_gaps": int(np.sum(np.diff(g) != GRID_US)),
            "max_gap_steps": int(np.max(np.diff(g)) // GRID_US) if len(g) > 1 else 0,
            "span_covered": bool(len(g) and t_rel[0] <= ANALYSIS_SPAN[0] + 0.01
                                 and t_rel[-1] >= ANALYSIS_SPAN[1] - 0.02),
            "params": {k: params.get(k) for k in ("SIH_MOT_EFF1", "SIH_T_TAU", "SIH_T_MAX", "SIH_LOC_YAW0",
                                                  "SDLOG_DIRS_MAX", "CA_ROTOR0_PX", "CA_ROTOR0_PY")}}
    return {"onboard": ob, "truth": tr}, meta
