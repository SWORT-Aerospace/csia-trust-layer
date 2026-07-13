"""Magnetometer model — RM3100 class (as on the SOW001 FC).

CSIA role: heading reference for the Mag-Heading<->Visual/GPS-Course edge and
attitude cross-checks. Magnetometers are the most EMI-sensitive node in the
graph (motor current loops nearby), so this is a prime target for the
emi_spike fault and for the Power<->Mag-disturbance correlation.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import FlightTruth, world_to_body

# Mid-latitude field, world frame (x north, z up): ~22 uT north, ~42 uT down.
B_WORLD_UT = np.array([22.0, 0.0, -42.0])
NOISE_UT = 0.03  # RM3100 class, low-noise magneto-inductive


class Magnetometer(SensorModel):
    name = "mag"
    rate_hz = 50.0

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        n = len(idx)
        t = truth.t[idx]
        b_body = world_to_body(np.tile(B_WORLD_UT, (n, 1)), truth.att[idx])
        # Hard-iron style offset from current draw in nearby power leads.
        b_body[:, 1] += 0.004 * truth.batt_i[idx]
        b_body += self.white(n, NOISE_UT, 3)

        valid = np.ones(n, dtype=bool)
        for f in faults_for(faults, self.name, "emi_spike"):
            amp = float(f.params.get("amplitude", 8.0))
            rate = float(f.params.get("rate_hz", 10.0))
            hit = f.window(t) & (self.rng.random(n) < rate / self.rate_hz)
            b_body[hit] += self.rng.normal(0, amp, (hit.sum(), 3))
        for f in faults_for(faults, self.name, "bias_drift"):
            axis = int(f.params.get("axis", 0))
            b_body[:, axis] += f.elapsed(t) * float(f.params.get("rate", 0.1))
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "field_ut": b_body,
                "heading": heading_from_mag(b_body, truth.att[idx]),
                "valid": valid}


def heading_from_mag(b_body: np.ndarray, att: np.ndarray) -> np.ndarray:
    """Tilt-compensated heading (rad). Uses truth roll/pitch for the tilt
    compensation — a documented simplification; phase 2 replaces this with
    the IMU-derived attitude so mag and IMU stay independent predictors."""
    r, p = att[:, 0], att[:, 1]
    cr, sr, cp, sp = np.cos(r), np.sin(r), np.cos(p), np.sin(p)
    bx, by, bz = b_body[:, 0], b_body[:, 1], b_body[:, 2]
    # De-rotate roll then pitch back to level.
    bx_l = bx * cp + sp * (by * sr + bz * cr)
    by_l = by * cr - bz * sr
    # z-up world frame: heading sign is flipped vs the usual NED formula.
    return np.unwrap(np.arctan2(-by_l, bx_l))
