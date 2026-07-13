"""Dual IMU model — ICM-42688-P class (as on the SOW001 STM32H743 FC).

CSIA role: primary inertial nodes of the trust graph. Redundant pair gives
the IMU<->IMU cross-check edge; accel channels feed the Accel<->Motor-Current
and Accel<->ESC-RPM edges; the gravity direction in the accel vector feeds
the Attitude<->Gravity-Vector edge.

Noise model (order-of-magnitude from the ICM-42688-P datasheet):
  accel noise density ~70 ug/sqrt(Hz), gyro ~2.8 mdps/sqrt(Hz),
  plus slow in-run bias random walk and a fixed turn-on bias.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import G, FlightTruth, world_to_body

ACCEL_NOISE_SIGMA = 70e-6 * G * np.sqrt(50.0)   # ~50 Hz bandwidth -> m/s^2
GYRO_NOISE_SIGMA = np.deg2rad(2.8e-3) * np.sqrt(50.0)  # rad/s
ACCEL_BIAS_TURN_ON = 0.02 * G                    # +/-20 mg class
GYRO_BIAS_TURN_ON = np.deg2rad(0.5)              # +/-0.5 dps class
ACCEL_BIAS_WALK = 2e-5 * G                       # per-sample random walk step
GYRO_BIAS_WALK = np.deg2rad(2e-5)


class IMU(SensorModel):
    rate_hz = 100.0

    def __init__(self, name: str = "imu0", seed: int = 0):
        super().__init__(name, seed)

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        n = len(idx)
        t = truth.t[idx]

        # Specific force: what an accelerometer actually senses (kinematic
        # accel minus gravity), rotated into the body frame. At rest it reads
        # +G on body z — this is the Attitude<->Gravity-Vector relationship.
        f_world = truth.acc[idx] + np.array([0.0, 0.0, G])
        accel = world_to_body(f_world, truth.att[idx])
        gyro = truth.rates[idx].copy()

        # Turn-on bias + in-run bias random walk + white noise.
        accel += self.rng.uniform(-1, 1, 3) * ACCEL_BIAS_TURN_ON
        gyro += self.rng.uniform(-1, 1, 3) * GYRO_BIAS_TURN_ON
        accel += self.random_walk(n, ACCEL_BIAS_WALK, 3)
        gyro += self.random_walk(n, GYRO_BIAS_WALK, 3)
        accel += self.white(n, ACCEL_NOISE_SIGMA, 3)
        gyro += self.white(n, GYRO_NOISE_SIGMA, 3)

        valid = np.ones(n, dtype=bool)

        # --- fault injection --------------------------------------------------
        for f in faults_for(faults, self.name, "bias_drift"):
            axis = int(f.params.get("axis", 2))
            rate = float(f.params.get("rate", 0.05))  # m/s^2 per s (or rad/s/s)
            channel = f.params.get("channel", "accel")
            ramp = f.elapsed(t) * rate
            if channel == "accel":
                accel[:, axis] += ramp
            else:
                gyro[:, axis] += ramp
        for f in faults_for(faults, self.name, "emi_spike"):
            amp = float(f.params.get("amplitude", 5.0))
            rate = float(f.params.get("rate_hz", 8.0))
            w = f.window(t)
            hit = w & (self.rng.random(n) < rate / self.rate_hz)
            accel[hit] += self.rng.normal(0, amp, (hit.sum(), 3))
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "accel": accel, "gyro": gyro, "valid": valid}
