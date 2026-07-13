"""Ground-truth flight state generator.

CSIA role: every sensor model samples this single shared truth state, so
cross-sensor consistency (the edges of the Dynamic Trust Graph) is physically
meaningful — e.g. motor current and IMU acceleration really do co-vary here,
because both derive from the same thrust profile.

Frame convention: world x/y horizontal, z UP. Gravity g_w = [0, 0, -G].
Attitude is ZYX Euler (roll, pitch, yaw). A quadrotor (~2 kg, 4S pack) flies
a scripted profile: spin-up, climb to 30 m, one lazy circle, hover, descend.
"""

from dataclasses import dataclass

import numpy as np

G = 9.80665  # m/s^2
MASS = 2.0  # kg, SOW001-class quad
HOVER_RPM = 6000.0
HOVER_CURRENT_PER_MOTOR = 4.0  # A
IDLE_RPM = 1200.0
PACK_V_FULL = 16.8  # 4S Li-ion, full charge
PACK_R_INTERNAL = 0.012  # ohm
PACK_CAPACITY_AH = 5.0
AVIONICS_CURRENT = 0.6  # A (FC + Pi 5 companion)
# Per-motor trim: real props/motors are never perfectly matched.
MOTOR_TRIM = np.array([1.000, 0.988, 1.012, 0.995])


@dataclass
class FlightTruth:
    """Dense truth state at a fixed base rate (default 100 Hz)."""

    t: np.ndarray          # (N,) s
    dt: float
    pos: np.ndarray        # (N, 3) m, world frame
    vel: np.ndarray        # (N, 3) m/s
    acc: np.ndarray        # (N, 3) m/s^2 (kinematic, gravity NOT included)
    att: np.ndarray        # (N, 3) rad — roll, pitch, yaw
    rates: np.ndarray      # (N, 3) rad/s body rates (small-angle Euler-rate approx)
    motor_rpm: np.ndarray  # (N, 4)
    motor_current: np.ndarray  # (N, 4) A
    batt_v: np.ndarray     # (N,) V at pack terminals
    batt_i: np.ndarray     # (N,) A total draw
    air_temp: np.ndarray   # (N,) degC at the sensor board

    @property
    def n(self) -> int:
        return len(self.t)


def _smoothstep(x: np.ndarray) -> np.ndarray:
    """Quintic smootherstep: C2-continuous, so the twice-differentiated
    position profile yields a continuous (finite-jerk) acceleration."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6.0 * x - 15.0) + 10.0)


def generate_flight(duration: float = 60.0, dt: float = 0.01,
                    seed: int | None = 42) -> FlightTruth:
    """Scripted flight: ground 0-5 s, climb 5-15 s to 30 m, one 40 m-radius
    circle 15-45 s, hover 45-50 s, descend 50-58 s, settle."""
    rng = np.random.default_rng(seed)
    t = np.arange(0.0, duration, dt)

    # --- position -----------------------------------------------------------
    alt = 30.0 * _smoothstep((t - 5.0) / 10.0) - 28.0 * _smoothstep((t - 50.0) / 8.0)
    radius = 40.0
    theta = 2.0 * np.pi * _smoothstep((t - 15.0) / 30.0)  # one full circle
    x = radius * np.sin(theta)
    y = radius * (1.0 - np.cos(theta))
    pos = np.column_stack([x, y, alt])

    vel = np.gradient(pos, dt, axis=0)
    acc = np.gradient(vel, dt, axis=0)

    # --- attitude -----------------------------------------------------------
    # Yaw follows the path tangent (theta) while translating, PLUS a 90-deg
    # yaw-in-place sweep during the hover segment (45-49.5 s). A quadrotor's
    # heading is NOT slaved to its velocity vector — this deliberate
    # divergence exists so the Mag-Heading<->GPS-Course edge is a real check
    # that must be speed-gated, not a tautology of the truth model.
    yaw = theta + 0.5 * np.pi * _smoothstep((t - 45.0) / 4.5)
    # Small-angle quasi-static tilt: horizontal accel is produced by tilting
    # the thrust vector. Body-forward/lateral accel from world accel via yaw.
    a_fwd = acc[:, 0] * np.cos(yaw) + acc[:, 1] * np.sin(yaw)
    a_lat = -acc[:, 0] * np.sin(yaw) + acc[:, 1] * np.cos(yaw)
    # Signs follow from the z-up ZYX DCM in world_to_body: these are the
    # unique angles that align body z with the specific-force (thrust)
    # vector, so a coordinated turn reads |f| = sqrt(G^2 + a_h^2) on the
    # body-z accelerometer (load factor > 1 in a bank), as physics demands.
    pitch = np.arctan2(a_fwd, G)
    roll = -np.arctan2(a_lat, G)
    att = np.column_stack([roll, pitch, yaw])
    rates = np.gradient(np.column_stack([roll, pitch, np.unwrap(yaw)]), dt, axis=0)

    # --- propulsion (CSIA edges: Accel<->Motor Current, Accel<->ESC RPM,
    #     Power<->Thrust) ----------------------------------------------------
    # Thrust vector must produce the full kinematic accel minus gravity, so
    # its magnitude is m*|a - g| — in a banked turn the horizontal component
    # matters (body-z specific force is |f|, not just G+az). Getting this
    # wrong breaks the Accel<->RPM/Current edges during any coordinated turn.
    thrust = MASS * np.linalg.norm(acc + np.array([0.0, 0.0, G]), axis=1)
    armed = _smoothstep((t - 3.0) / 2.0)  # spin-up 3-5 s
    per_motor_thrust = thrust[:, None] / 4.0 * MOTOR_TRIM[None, :]
    hover_thrust = MASS * G / 4.0
    rpm_cmd = HOVER_RPM * np.sqrt(np.clip(per_motor_thrust / hover_thrust, 0.0, None))
    motor_rpm = IDLE_RPM + armed[:, None] * (rpm_cmd - IDLE_RPM)
    motor_current = HOVER_CURRENT_PER_MOTOR * (motor_rpm / HOVER_RPM) ** 3

    # --- power (CSIA edge: Battery Voltage<->Current Draw) -------------------
    batt_i = motor_current.sum(axis=1) + AVIONICS_CURRENT
    soc = 1.0 - np.cumsum(batt_i) * dt / 3600.0 / PACK_CAPACITY_AH
    v_ocv = PACK_V_FULL - 1.2 * (1.0 - soc)  # shallow discharge slope
    batt_v = v_ocv - batt_i * PACK_R_INTERNAL

    # --- thermal (CSIA edge: Temperature<->Bias Drift) -----------------------
    # Board self-heating dominates on a 60 s flight; lapse rate is minor.
    air_temp = 25.0 + 6.0 * (1.0 - np.exp(-t / 120.0)) - 0.0065 * alt

    return FlightTruth(t=t, dt=dt, pos=pos, vel=vel, acc=acc, att=att,
                       rates=rates, motor_rpm=motor_rpm,
                       motor_current=motor_current, batt_v=batt_v,
                       batt_i=batt_i, air_temp=air_temp)


def world_to_body(vec_w: np.ndarray, att: np.ndarray) -> np.ndarray:
    """Rotate world-frame vectors (N,3) into the body frame given ZYX Euler
    attitude (N,3). Used by IMU (Attitude<->Gravity Vector edge) and
    magnetometer models."""
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
    return np.einsum("nij,nj->ni", R, vec_w)
