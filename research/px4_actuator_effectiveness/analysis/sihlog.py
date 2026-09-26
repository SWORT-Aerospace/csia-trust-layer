"""Load one PX4 SIH ULog onto the simulator's 4 ms step grid.

Research-only apparatus analysis. Nothing here imports or feeds CSIA.

The grid is the set of esc_status timestamps: SIH publishes esc_status once per
lockstep step, inside read_motors (sih.cpp:361-384 after the patch), so each
grid point is one physical simulator step. Other topics are sampled onto it by
zero-order hold (the last sample at or before the grid time).

Every signal is tagged with one of the five categories the apparatus must keep
apart: COMMAND, PHYSICAL (rotor), TELEMETRY, RESPONSE, ESTIMATE.
"""
from dataclasses import dataclass, field

import numpy as np
from pyulog import ULog

RPM_MAX = 10000.0  # sih.cpp publish_esc_status, multicopter
STEP_US = 4000


def _zoh(t_src, v_src, t_grid):
    i = np.searchsorted(t_src, t_grid, side="right") - 1
    out = np.full((len(t_grid),) + v_src.shape[1:], np.nan)
    ok = i >= 0
    out[ok] = v_src[i[ok]]
    return out


def quat_to_euler(q):
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = np.arcsin(np.clip(2 * (w * y - z * x), -1, 1))
    yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return np.stack([roll, pitch, yaw], axis=1)


def tilt_of(q):
    """Angle between body z and the vertical, rad."""
    x, y = q[:, 1], q[:, 2]
    return np.arccos(np.clip(1 - 2 * (x * x + y * y), -1, 1))


def quat_angle(qa, qb):
    """Rotation angle between two attitude quaternions, rad."""
    d = np.abs(np.sum(qa * qb, axis=1))
    return 2 * np.arccos(np.clip(d, -1, 1))


@dataclass
class Trial:
    path: str
    t_us: np.ndarray = None           # grid, simulated microseconds
    s: dict = field(default_factory=dict)       # grid-aligned signals
    category: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)     # native-rate arrays kept for timing checks
    params: dict = field(default_factory=dict)
    changed_params: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    dropouts: int = 0

    @property
    def t(self):
        return self.t_us * 1e-6


def _topic(u, name):
    try:
        return u.get_dataset(name, 0).data
    except (KeyError, IndexError, ValueError):
        return None


def load(path):
    u = ULog(str(path))
    tr = Trial(path=str(path))
    tr.params = dict(u.initial_parameters)
    tr.changed_params = [(int(t), n, float(v)) for t, n, v in u.changed_parameters]
    tr.messages = [(int(m.timestamp), m.message) for m in u.logged_messages]
    tr.dropouts = len(u.dropouts)

    esc = _topic(u, "esc_status")
    tr.t_us = esc["timestamp"].astype(np.int64)
    g = tr.t_us

    def put(key, cat, t_src, cols):
        v = np.stack(cols, axis=1).astype(float) if isinstance(cols, list) else cols.astype(float)
        tr.s[key] = _zoh(t_src.astype(np.int64), v, g)
        tr.category[key] = cat

    # PHYSICAL rotor state and its TELEMETRY are the same logged variable in SIH
    # (preflight section 3); they are split here only by name, and an offline
    # telemetry fault replaces the TELEMETRY copy while the PHYSICAL one stays true.
    rpm = np.stack([esc[f"esc[{i}].esc_rpm"] for i in range(4)], axis=1).astype(float)
    tr.s["rpm_true"] = rpm
    tr.category["rpm_true"] = "PHYSICAL"
    tr.s["rpm_telemetry"] = rpm.copy()
    tr.category["rpm_telemetry"] = "TELEMETRY"
    tr.s["u_rotor"] = (rpm / RPM_MAX) ** 2
    tr.category["u_rotor"] = "PHYSICAL"
    t_max = float(tr.params.get("SIH_T_MAX", 5.0))
    tr.s["thrust_rotor"] = t_max * tr.s["u_rotor"]
    tr.category["thrust_rotor"] = "PHYSICAL"

    d = _topic(u, "actuator_outputs_sim")
    tr.raw["cmd_sim_t"] = d["timestamp"].astype(np.int64)
    tr.raw["cmd_sim"] = np.stack([d[f"output[{i}]"] for i in range(4)], axis=1).astype(float)
    put("cmd_sim", "COMMAND", d["timestamp"], [d[f"output[{i}]"] for i in range(4)])
    d = _topic(u, "actuator_motors")
    put("cmd_alloc", "COMMAND", d["timestamp"], [d[f"control[{i}]"] for i in range(4)])
    d = _topic(u, "vehicle_torque_setpoint")
    put("torque_sp", "COMMAND", d["timestamp"], [d[f"xyz[{i}]"] for i in range(3)])
    d = _topic(u, "vehicle_thrust_setpoint")
    put("thrust_sp", "COMMAND", d["timestamp"], [d[f"xyz[{i}]"] for i in range(3)])
    d = _topic(u, "rate_ctrl_status")
    put("rate_integ", "COMMAND", d["timestamp"], [d["rollspeed_integ"], d["pitchspeed_integ"], d["yawspeed_integ"]])
    d = _topic(u, "control_allocator_status")
    put("alloc_sat", "COMMAND", d["timestamp"], [d[f"actuator_saturation[{i}]"] for i in range(4)])
    put("alloc_torque_achieved", "COMMAND", d["timestamp"], [d["torque_setpoint_achieved"]])
    d = _topic(u, "vehicle_attitude_setpoint")
    put("q_sp", "COMMAND", d["timestamp"], [d[f"q_d[{i}]"] for i in range(4)])
    d = _topic(u, "vehicle_local_position_setpoint")
    put("pos_sp", "COMMAND", d["timestamp"], [d["x"], d["y"], d["z"]])

    d = _topic(u, "vehicle_angular_velocity_groundtruth")
    put("w_true", "RESPONSE", d["timestamp"], [d[f"xyz[{i}]"] for i in range(3)])
    d = _topic(u, "vehicle_attitude_groundtruth")
    put("q_true", "RESPONSE", d["timestamp"], [d[f"q[{i}]"] for i in range(4)])
    d = _topic(u, "vehicle_local_position_groundtruth")
    put("pos_true", "RESPONSE", d["timestamp"], [d["x"], d["y"], d["z"]])
    d = _topic(u, "sensor_combined")
    put("accel_meas", "RESPONSE", d["timestamp"], [d[f"accelerometer_m_s2[{i}]"] for i in range(3)])
    put("gyro_meas", "RESPONSE", d["timestamp"], [d[f"gyro_rad[{i}]"] for i in range(3)])

    d = _topic(u, "vehicle_attitude")
    put("q_est", "ESTIMATE", d["timestamp"], [d[f"q[{i}]"] for i in range(4)])
    d = _topic(u, "vehicle_local_position")
    put("pos_est", "ESTIMATE", d["timestamp"], [d["x"], d["y"], d["z"], d["vx"], d["vy"], d["vz"]])
    d = _topic(u, "hover_thrust_estimate")
    put("hover_thrust", "ESTIMATE", d["timestamp"], [d["hover_thrust"]])
    put("hte_innov", "ESTIMATE", d["timestamp"], [d["accel_innov"], d["accel_innov_test_ratio"]])
    innov_fields = ["gps_hpos[0]", "gps_hpos[1]", "gps_vpos", "gps_hvel[0]", "gps_hvel[1]", "gps_vvel",
                    "baro_vpos", "rng_vpos", "heading", "mag_field[0]", "mag_field[1]", "mag_field[2]"]
    d = _topic(u, "estimator_innovations")
    put("innov", "ESTIMATE", d["timestamp"], [d[f] for f in innov_fields])
    tr.raw["innov_t"] = d["timestamp"].astype(np.int64)
    tr.raw["innov_t_sample"] = d["timestamp_sample"].astype(np.int64)
    d = _topic(u, "estimator_innovation_test_ratios")
    put("innov_ratio", "ESTIMATE", d["timestamp"], [d[f] for f in innov_fields])
    tr.raw["innov_fields"] = innov_fields

    d = _topic(u, "parameter_update")
    tr.raw["param_update_t"] = d["timestamp"].astype(np.int64)
    d = _topic(u, "vehicle_status")
    tr.raw["status_t"] = d["timestamp"].astype(np.int64)
    tr.raw["arming_state"] = d["arming_state"].astype(int)
    tr.raw["nav_state"] = d["nav_state"].astype(int)
    tr.raw["failsafe"] = d["failsafe"].astype(int)

    # derived RESPONSE signals on the step grid
    tr.s["alpha_true"] = np.vstack([np.zeros((1, 3)), np.diff(tr.s["w_true"], axis=0) / (STEP_US * 1e-6)])
    tr.category["alpha_true"] = "RESPONSE"
    tr.s["euler_true"] = quat_to_euler(tr.s["q_true"])
    tr.category["euler_true"] = "RESPONSE"
    tr.s["tilt_true"] = tilt_of(tr.s["q_true"])[:, None]
    tr.category["tilt_true"] = "RESPONSE"
    tr.s["euler_est"] = quat_to_euler(tr.s["q_est"])
    tr.category["euler_est"] = "ESTIMATE"
    tr.s["att_err"] = quat_angle(tr.s["q_sp"], tr.s["q_est"])[:, None]
    tr.category["att_err"] = "COMMAND"
    return tr


def arm_time_us(tr):
    st = tr.raw["arming_state"]
    i = np.nonzero(st == 2)[0]  # vehicle_status ARMING_STATE_ARMED = 2
    return int(tr.raw["status_t"][i[0]]) if len(i) else None


def eta_change(tr, name="SIH_MOT_EFF1"):
    """(timestamp_us, value) of the in-flight change of the effectiveness parameter, or None.

    pyulog stamps a changed-parameter record with the last data timestamp seen
    before it; the parameter_update publication that caused it is the first one
    at or after that stamp minus one step.
    """
    ch = [(t, v) for t, n, v in tr.changed_params if n == name]
    if not ch:
        return None
    t_rec, v = ch[-1]
    pu = tr.raw["param_update_t"]
    j = np.searchsorted(pu, t_rec - STEP_US)
    t_pu = int(pu[j]) if j < len(pu) else t_rec
    return t_pu, v


def first_step_after(tr, t_us):
    """Index of the first SIH step strictly after t_us: SIH reloads parameters at
    the start of its next step (sih.cpp:227-234)."""
    return int(np.searchsorted(tr.t_us, t_us, side="right"))
