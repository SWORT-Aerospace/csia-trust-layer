"""Structural vibration accelerometer.

CSIA role: the structural-health node. The Vibration<->Prop-Frequency edge
checks that the dominant vibration line tracks motor RPM/60; a growing
amplitude or a sub-harmonic (half-order) line with unchanged RPM is the
classic damaged-prop signature the vibration_anomaly fault injects.

Samples at 1 kHz internally (a real vib channel would run multi-kHz on the
STM32H7's SDMMC/SPI bus) and also emits a 10 Hz RMS envelope, which is what
the trust graph consumes.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import FlightTruth

BROADBAND_SIGMA = 0.08   # m/s^2 white floor
PER_REV_AMP = 0.35       # m/s^2 per-rev line at hover RPM


class VibrationSensor(SensorModel):
    name = "vibration"
    rate_hz = 1000.0  # own timeline, interpolated from truth

    def sample(self, truth: FlightTruth, faults=()) -> dict:
        faults = list(faults)
        t = np.arange(0.0, truth.t[-1], 1.0 / self.rate_hz)
        n = len(t)
        rpm = np.interp(t, truth.t, truth.motor_rpm.mean(axis=1))
        prop_freq = rpm / 60.0  # per-rev frequency, Hz

        amp = np.full(n, PER_REV_AMP) * (rpm / 6000.0)
        sub_amp = np.zeros(n)
        for f in faults_for(faults, self.name, "vibration_anomaly"):
            w = f.window(t)
            amp = np.where(w, amp * float(f.params.get("gain", 3.0)), amp)
            sub_amp = np.where(w, amp * 0.6, sub_amp)

        phase = 2.0 * np.pi * np.cumsum(prop_freq) / self.rate_hz
        sig = amp * np.sin(phase)
        sig += sub_amp * np.sin(float(1.0 / 2.0) * phase + 0.7)  # half-order line
        sig += self.white(n, BROADBAND_SIGMA)

        # 10 Hz RMS envelope — the channel the trust engine consumes.
        win = int(self.rate_hz / 10.0)
        m = (n // win) * win
        rms = np.sqrt((sig[:m].reshape(-1, win) ** 2).mean(axis=1))
        t_rms = t[:m].reshape(-1, win).mean(axis=1)

        valid = np.ones(n, dtype=bool)
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "accel": sig, "valid": valid,
                "t_rms": t_rms, "rms": rms,
                "prop_freq_hz": prop_freq}
