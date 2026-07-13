"""Motor/ESC telemetry model — RPM + current per motor.

CSIA role: the propulsion node. Feeds the Accel<->Motor-Current,
Accel<->ESC-RPM, Power<->Thrust and Vibration<->Prop-Frequency edges.
On the SOW001 stack this arrives as ESC telemetry over the FC, relayed
to the Pi 5 companion via MAVLink ESC_STATUS.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import FlightTruth

RPM_NOISE = 15.0     # eRPM telemetry jitter
CURRENT_NOISE = 0.08  # A


class MotorESC(SensorModel):
    name = "motor_esc"
    rate_hz = 50.0

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        n = len(idx)
        t = truth.t[idx]
        rpm = truth.motor_rpm[idx] + self.white(n, RPM_NOISE, 4)
        current = np.clip(truth.motor_current[idx] + self.white(n, CURRENT_NOISE, 4), 0.0, None)

        valid = np.ones(n, dtype=bool)
        for f in faults_for(faults, self.name, "power_sag"):
            # Correlated sag: pack voltage dip -> all motors lose RPM.
            depth = float(f.params.get("rpm_loss", 400.0))
            rpm -= (depth * f.window(t))[:, None]
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "rpm": rpm, "current": current, "valid": valid}
