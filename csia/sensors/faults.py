"""Injectable fault definitions.

CSIA role: faults are the stimuli the Trust Layer must detect and attribute.
Each fault targets one sensor node of the Dynamic Trust Graph over a time
window; the trust engine (phase 2) should respond by lowering that node's
Trust Coefficient while the causal diagnosis module (phase 3) attributes it.

Supported kinds (matched by each sensor model's ``sample()``):
  bias_drift        — slow additive ramp (IMU/baro/mag), params: axis, rate
  dropout           — samples marked invalid / held (GPS, any)
  emi_spike         — sparse large spikes (mag, IMU), params: amplitude, rate_hz
  gps_spoof         — position walks away while Doppler velocity stays clean,
                      params: drift (m/s vector) — the classic spoof signature
                      the Velocity<->GPS-Doppler edge is designed to catch
  vibration_anomaly — prop/blade damage signature: amplitude growth + a
                      sub-harmonic, params: gain, subharmonic_ratio
  power_sag         — pack voltage dip with correlated RPM sag, params: depth_v
"""

from dataclasses import dataclass, field

import numpy as np

KNOWN_KINDS = frozenset({
    "bias_drift", "dropout", "emi_spike", "gps_spoof",
    "vibration_anomaly", "power_sag",
})


@dataclass
class Fault:
    kind: str
    target: str          # sensor node name, e.g. "gps", "imu0"
    start: float         # s
    duration: float      # s
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        # A typo'd kind would otherwise be silently ignored by every sensor
        # (each model applies only the kinds it knows) — fail loudly instead.
        if self.kind not in KNOWN_KINDS:
            raise ValueError(f"unknown fault kind {self.kind!r}; "
                             f"known: {sorted(KNOWN_KINDS)}")
        if self.duration <= 0 or self.start < 0:
            raise ValueError(f"fault window invalid: start={self.start}, "
                             f"duration={self.duration}")

    def window(self, t: np.ndarray) -> np.ndarray:
        """Boolean mask of samples inside the fault window."""
        return (t >= self.start) & (t < self.start + self.duration)

    def elapsed(self, t: np.ndarray) -> np.ndarray:
        """Seconds since fault onset, zero outside the window."""
        return np.where(self.window(t), t - self.start, 0.0)


def faults_for(faults, target: str, kind: str | None = None):
    """Filter a fault list down to one sensor (and optionally one kind)."""
    return [f for f in faults
            if f.target == target and (kind is None or f.kind == kind)]
