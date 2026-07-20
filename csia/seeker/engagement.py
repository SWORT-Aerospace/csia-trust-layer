"""Engagement truth model — simplified closing intercept.

SYNTHETIC FIRST PASS, deliberately simple and fully documented:
  * 2D planar, co-altitude engagement (both bodies at constant altitude,
    zero vertical velocity). Line-of-sight elevation is therefore ~0 and all
    angular information lives in azimuth — which is exactly the channel the
    IR/RF bearing cross-check needs. A real engagement is 3D/6-DOF; this is
    a kinematic stand-in for generating physically-plausible sensor streams.
  * Target: constant-velocity, subsonic, cruise-missile-representative
    (250 m/s). No target maneuver.
  * Interceptor: pure-pursuit guidance at constant speed Vi (default
    900 m/s), i.e. velocity vector always points at the current target
    position. This produces a monotonically closing range over ~15-25 s from
    a 15 km initial separation.

Everything is deterministic given the parameters (no randomness in truth;
sensor noise is applied downstream with fixed seeds).
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Engagement:
    """Dense per-tick engagement truth."""
    t: np.ndarray          # (N,) s
    dt: float
    tick_hz: float
    p_i: np.ndarray        # (N,3) interceptor position, m (world ENU)
    v_i: np.ndarray        # (N,3) interceptor velocity, m/s
    p_t: np.ndarray        # (N,3) target position, m
    v_t: np.ndarray        # (N,3) target velocity, m/s
    rng: np.ndarray        # (N,) interceptor->target range, m
    az: np.ndarray         # (N,) LOS azimuth, rad (world)
    el: np.ndarray         # (N,) LOS elevation, rad (~0, planar)
    closing: np.ndarray    # (N,) closing velocity, m/s (positive = closing)

    @property
    def n(self):
        return len(self.t)


def generate_engagement(tick_hz: float = 100.0, duration: float = 20.0,
                        vi: float = 900.0, vt: float = 250.0,
                        r0: float = 15000.0, az0_deg: float = 20.0,
                        alt: float = 1000.0) -> Engagement:
    """Integrate the pure-pursuit closing engagement at the tick rate.

    Deterministic. Stops early (holds final state) once range < 5 m."""
    dt = 1.0 / tick_hz
    n = int(round(duration * tick_hz))
    t = np.arange(n) * dt

    # target: constant velocity in-plane, magnitude vt, crossing course
    vt_hdg = np.deg2rad(210.0)  # heading (generally toward interceptor half)
    v_t_vec = vt * np.array([np.cos(vt_hdg), np.sin(vt_hdg), 0.0])
    az0 = np.deg2rad(az0_deg)
    p_t0 = np.array([r0 * np.cos(az0), r0 * np.sin(az0), alt])
    p_i0 = np.array([0.0, 0.0, alt])

    p_i = np.zeros((n, 3)); v_i = np.zeros((n, 3))
    p_t = np.zeros((n, 3)); v_t = np.tile(v_t_vec, (n, 1))
    p_i[0] = p_i0; p_t[0] = p_t0
    n_end = n
    for k in range(1, n):
        p_t[k] = p_t[k - 1] + v_t_vec * dt
        los = p_t[k - 1] - p_i[k - 1]
        d = np.linalg.norm(los)
        v_i[k - 1] = vi * los / max(d, 1e-9)
        p_i[k] = p_i[k - 1] + v_i[k - 1] * dt
        if np.linalg.norm(p_t[k] - p_i[k]) < 5.0:
            n_end = k + 1
            break
    # trim at intercept — DO NOT hold a frozen tail (frozen state creates
    # artificial |vel| vs |d(pos)/dt| residuals that would false-alarm).
    n = n_end
    t = t[:n]; p_i = p_i[:n]; v_i = v_i[:n]; p_t = p_t[:n]; v_t = v_t[:n]
    if n > 1:
        v_i[-1] = v_i[-2]

    d = p_t - p_i
    rng = np.linalg.norm(d, axis=1)
    az = np.arctan2(d[:, 1], d[:, 0])
    el = np.arctan2(d[:, 2], np.hypot(d[:, 0], d[:, 1]))
    v_rel = v_t - v_i
    range_rate = np.sum(d * v_rel, axis=1) / np.maximum(rng, 1e-9)
    closing = -range_rate
    return Engagement(t=t, dt=dt, tick_hz=tick_hz, p_i=p_i, v_i=v_i,
                      p_t=p_t, v_t=v_t, rng=rng, az=az, el=el, closing=closing)
