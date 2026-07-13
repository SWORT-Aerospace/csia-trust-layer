"""GPS model — position + Doppler velocity, configurable dropout & spoofing.

CSIA role: the navigation anchor node. Two nearly-independent channels make
it powerful for cross-validation: position (code-phase, meters of correlated
error) and velocity (Doppler, cm/s of white error). The Velocity<->GPS-Doppler
edge exploits exactly this: a spoofer that walks position away while the
vehicle isn't actually moving leaves Doppler (and the IMU) disagreeing —
that disagreement, not a binary flag, is what the trust engine consumes.
"""

import numpy as np

from .base import SensorModel
from .faults import faults_for
from .truth import FlightTruth

POS_SIGMA_H = 1.0    # m, horizontal, Gauss-Markov
POS_SIGMA_V = 1.8    # m, vertical
POS_TAU = 30.0       # s correlation time
VEL_SIGMA = 0.08     # m/s, Doppler, ~white


class GPS(SensorModel):
    name = "gps"
    rate_hz = 10.0

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        n = len(idx)
        t = truth.t[idx]
        pos = truth.pos[idx].copy()
        vel = truth.vel[idx].copy()

        pos[:, :2] += self.gauss_markov(t, POS_SIGMA_H, POS_TAU, 2)
        pos[:, 2] += self.gauss_markov(t, POS_SIGMA_V, POS_TAU, 1)[:, 0]
        vel += self.white(n, VEL_SIGMA, 3)

        valid = np.ones(n, dtype=bool)
        for f in faults_for(faults, self.name, "gps_spoof"):
            # Classic meaconing/spoof signature: reported position walks away
            # at a constant drift while Doppler velocity stays consistent with
            # the true motion (params can also poison velocity if desired).
            drift = np.asarray(f.params.get("drift", (3.0, 0.0, 0.0)), float)
            pos += f.elapsed(t)[:, None] * drift[None, :]
            if f.params.get("spoof_velocity", False):
                vel += f.window(t)[:, None] * drift[None, :]
        for f in faults_for(faults, self.name, "dropout"):
            valid &= ~f.window(t)

        return {"t": t, "pos": pos, "vel": vel, "valid": valid}
