"""IMU-only attitude estimation for the prediction comparator.

CSIA role: the Attitude<->Gravity-Vector relationship, implemented honestly.
Phase 1's mag heading borrowed truth attitude for tilt compensation; from
phase 2 onward every attitude used in a cross-check is derived from the IMU
itself (gyro integration corrected toward the accelerometer gravity vector),
so the mag/IMU and mag/GPS edges compare genuinely independent estimates.

Frame: world z UP, ZYX Euler (roll, pitch, yaw), matching src/sensors/truth.
"""

import numpy as np

from ..sensors.truth import G


def calibrate_imu_stream(imu: dict, t_static: float = 2.0) -> dict:
    """Ground calibration: the vehicle is static (motors idle) for the first
    ~3 s, so the accelerometer must read (0, 0, +G) and the gyro 0. Estimate
    and remove turn-on bias from that window — standard pre-arm practice on
    PX4/ArduPilot, and required here so the dual-IMU edge isn't dominated by
    a constant, calibratable offset."""
    mask = imu["t"] < t_static
    out = dict(imu)
    out["accel"] = imu["accel"] - (imu["accel"][mask].mean(axis=0)
                                   - np.array([0.0, 0.0, G]))
    out["gyro"] = imu["gyro"] - imu["gyro"][mask].mean(axis=0)
    return out


def complementary_attitude(t: np.ndarray, accel: np.ndarray,
                           gyro: np.ndarray, k_tilt: float = 0.01) -> np.ndarray:
    """Complementary filter: propagate Euler angles with the gyro, pull
    roll/pitch toward the accelerometer gravity direction with gain k_tilt.
    Yaw is gyro-integrated only (drifts with residual gyro bias — that slow
    drift is exactly what the mag heading edge cross-checks). Returns (N,3).
    """
    n = len(t)
    att = np.zeros((n, 3))
    rp = np.zeros(2)
    yaw = 0.0
    prev_t = t[0]
    for i in range(n):
        dt = t[i] - prev_t
        prev_t = t[i]
        rp = rp + gyro[i, :2] * dt
        yaw = yaw + gyro[i, 2] * dt
        f = accel[i]
        fmag = np.linalg.norm(f)
        # Trust the accel gravity direction only in quasi-static flight:
        # near 1 g AND low turn rate. In a coordinated turn the specific
        # force aligns with body z regardless of bank, so an un-gated
        # correction would pull roll toward zero mid-turn and poison every
        # edge that consumes this attitude (mag tilt comp above all).
        if abs(fmag - G) < 0.4 and np.linalg.norm(gyro[i]) < 0.05:
            roll_acc = np.arctan2(f[1], f[2])
            pitch_acc = -np.arcsin(np.clip(f[0] / fmag, -1.0, 1.0))
            rp = (1.0 - k_tilt) * rp + k_tilt * np.array([roll_acc, pitch_acc])
        att[i, 0], att[i, 1], att[i, 2] = rp[0], rp[1], yaw
    return att


def mag_heading_from_field(field: np.ndarray, att_imu: np.ndarray) -> np.ndarray:
    """Tilt-compensated magnetic heading using the IMU-derived roll/pitch
    (NOT truth attitude). z-up frame, so the sign is flipped vs NED."""
    r, p = att_imu[:, 0], att_imu[:, 1]
    cr, sr, cp, sp = np.cos(r), np.sin(r), np.cos(p), np.sin(p)
    bx, by, bz = field[:, 0], field[:, 1], field[:, 2]
    bx_l = bx * cp + sp * (by * sr + bz * cr)
    by_l = by * cr - bz * sr
    return np.arctan2(-by_l, bx_l)


def wrap_angle(a: np.ndarray) -> np.ndarray:
    """Wrap to [-pi, pi)."""
    return (a + np.pi) % (2.0 * np.pi) - np.pi
