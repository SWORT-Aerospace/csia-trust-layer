"""Battery pack telemetry — voltage and total current.

CSIA role: the power node. The Battery-Voltage<->Current-Draw edge is a
purely electrical self-consistency check (V drops when I rises through the
pack's internal resistance); the Power<->Thrust edge ties it to propulsion.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import FlightTruth

V_NOISE = 0.012  # V, ADC noise
I_NOISE = 0.06   # A, shunt/hall noise


class Battery(SensorModel):
    name = "battery"
    rate_hz = 10.0

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        n = len(idx)
        t = truth.t[idx]
        v = truth.batt_v[idx] + self.white(n, V_NOISE)
        i = truth.batt_i[idx] + self.white(n, I_NOISE)

        valid = np.ones(n, dtype=bool)
        for f in faults_for(faults, self.name, "power_sag"):
            depth = float(f.params.get("depth_v", 1.0))
            # Smooth dip: onset/recovery over ~10% of the window each side.
            w = f.window(t)
            v -= depth * w * np.sin(np.pi * np.clip(
                f.elapsed(t) / max(f.duration, 1e-9), 0, 1)) ** 0.5
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "voltage": v, "current": i, "valid": valid}
