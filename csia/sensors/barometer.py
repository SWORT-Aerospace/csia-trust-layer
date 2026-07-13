"""Barometer model — MS5611 class (as on the SOW001 FC).

CSIA role: the Altitude<->Barometric-Pressure edge, cross-checked against
GPS altitude and integrated IMU vertical velocity. Also outputs die
temperature, feeding the Temperature<->Bias-Drift edge.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import FlightTruth

P0_HPA = 1013.25
PRESSURE_NOISE_HPA = 0.012   # ~10 cm altitude RMS at high OSR
PRESSURE_DRIFT_STEP = 0.0004  # slow sensor drift, hPa per sample step


def altitude_to_pressure(alt_m: np.ndarray) -> np.ndarray:
    """ISA troposphere model."""
    return P0_HPA * (1.0 - 2.25577e-5 * alt_m) ** 5.25588


def pressure_to_altitude(p_hpa: np.ndarray) -> np.ndarray:
    return (1.0 - (p_hpa / P0_HPA) ** (1.0 / 5.25588)) / 2.25577e-5


class Barometer(SensorModel):
    name = "baro"
    rate_hz = 50.0

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        n = len(idx)
        t = truth.t[idx]
        pressure = altitude_to_pressure(truth.pos[idx, 2])
        pressure += self.random_walk(n, PRESSURE_DRIFT_STEP)
        pressure += self.white(n, PRESSURE_NOISE_HPA)
        temp = truth.air_temp[idx] + self.white(n, 0.05)

        valid = np.ones(n, dtype=bool)
        for f in faults_for(faults, self.name, "bias_drift"):
            pressure += f.elapsed(t) * float(f.params.get("rate", 0.05))  # hPa/s
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "pressure_hpa": pressure,
                "altitude": pressure_to_altitude(pressure),
                "temp_c": temp, "valid": valid}
