"""Causal diagnosis: Bayesian inversion of the consistency signature.

CSIA role: when an anomaly appears, the system must output a probability
distribution over likely causes (e.g. "91% GPS fault, 6% nominal, ...")
rather than a binary fault flag.

Method — naive-Bayes over the consistency signature. The comparator produces
a feature vector per tick: every edge consistency c_e = c(lambda_e), every
internal-physics score, and selected temporal-stability scores. Each
candidate cause specifies which features it drives LOW; all others are
expected HIGH. Per-tick log-likelihood of feature value c under expectation:

  L(c | LOW)  = log(1 - c + eps)        L(c | HIGH) = log(c + eps)

weighted by the feature's gate (a gated-out feature is NO evidence — e.g.
heading_course below the speed gate must not count for or against
mag_interference). Log-likelihoods are exponentially smoothed over ~15 ticks
(evidence accumulation), scaled by an evidence multiplier, added to log
priors, and softmaxed into a posterior P(cause | signature)[k].

The discriminative structure mirrors the physics:
  * gps_fault vs unexpected_maneuver: a maneuver moves BOTH IMUs and GPS
    coherently (structural edges stay green, historical scores dip); a spoof
    breaks GPS's internal position/Doppler consistency while every
    cross-sensor edge stays green.
  * imu0 vs imu1 bias: same dual-IMU edge goes low, but the motor edge that
    goes with it names the culprit.
"""

from dataclasses import dataclass

import numpy as np

from ..prediction.predictors import ew_smooth
from ..trust_engine.engine import consistency

EPS = 0.02
SMOOTH_ALPHA = 0.06        # ~15-tick evidence accumulation window
EVIDENCE_MULT = 1.5        # tempering of accumulated evidence
PRIOR_NOMINAL = 0.86       # remaining mass split across fault hypotheses

# cause -> set of features expected LOW while that cause is active.
# Feature names: edge keys from the comparator, phys_<sensor>, temp_<sensor>.
CAUSES = {
    "nominal": [],
    "gps_fault": ["phys_gps"],
    # attitude_gravity_mag breaks the imu0/imu1 tie. It compares mag heading
    # against imu0-integrated yaw, so an imu0 bias corrupts it and an imu1
    # bias does not. It is ungated, so unlike the motor edges it survives
    # disarm/pre-arm, which is where the two hypotheses used to collapse to a
    # shared {redundant_imu} signature (WP1 F-D1, repaired in WP-C3).
    "imu0_bias_drift": ["redundant_imu", "accel_motor_current",
                        "attitude_gravity_mag"],
    "imu1_bias_drift": ["redundant_imu", "accel_esc_rpm"],
    "mag_interference": ["attitude_gravity_mag", "heading_course",
                         "phys_mag", "temp_mag"],
    "power_fault": ["phys_battery", "temp_battery", "accel_motor_current",
                    "accel_esc_rpm", "phys_motor_esc"],
    "vibration_anomaly": ["vibration_prop_freq", "phys_vibration",
                          "temp_vibration"],
    "unexpected_maneuver": ["temp_gps"],
}

# Temporal-stability features exposed to the diagnoser (only the ones that
# are discriminative; IMU/baro hist scores are dominated by maneuvering).
TEMP_FEATURES = ("mag", "battery", "vibration", "gps")


@dataclass
class DiagnosisResult:
    t: np.ndarray
    causes: list
    posterior: np.ndarray  # (K, n_causes)

    def top(self, k: int) -> list:
        """[(cause, prob), ...] sorted descending at tick k."""
        order = np.argsort(self.posterior[k])[::-1]
        return [(self.causes[i], float(self.posterior[k, i])) for i in order]

    def callout(self, k: int, n: int = 3) -> str:
        return ", ".join(f"{100 * p:.0f}% {c}" for c, p in self.top(k)[:n])


class DiagnosisCore:
    """Single-tick diagnosis for the real-time runtime.

    Same math as the batch path: per-tick gate-weighted log-likelihoods,
    exponentially smoothed (evidence accumulation), tempered, softmaxed.
    Input per tick: {feature_name: (c, gate)} with c in (0, 1].
    """

    def __init__(self, causes: dict | None = None):
        self.causes = dict(causes or CAUSES)
        self.names = list(self.causes)
        self._low = [set(self.causes[c]) for c in self.names]
        prior = np.full(len(self.names),
                        (1.0 - PRIOR_NOMINAL) / (len(self.names) - 1))
        prior[self.names.index("nominal")] = PRIOR_NOMINAL
        self._log_prior = np.log(prior)
        self._smoothed = None  # EW state per cause

    def step(self, features: dict) -> dict:
        ll = np.zeros(len(self.names))
        for fname, (c, gate) in features.items():
            if gate <= 1e-9:
                continue
            lo = float(np.log(1.0 - c + EPS))
            hi = float(np.log(c + EPS))
            for ci, low in enumerate(self._low):
                ll[ci] += gate * (lo if fname in low else hi)
        if self._smoothed is None:
            self._smoothed = ll.copy()
        else:
            self._smoothed = ((1.0 - SMOOTH_ALPHA) * self._smoothed
                              + SMOOTH_ALPHA * ll)
        score = self._log_prior + EVIDENCE_MULT * self._smoothed
        score -= score.max()
        post = np.exp(score)
        post /= post.sum()
        return dict(zip(self.names, post))


class CausalDiagnosis:
    def __init__(self, causes: dict | None = None):
        self.causes = dict(causes or CAUSES)

    def _features(self, td) -> dict:
        """{name: (c[K], gate[K])} from comparator output."""
        feats = {}
        for key, (_, _, lam_e, gate_e) in td.edges.items():
            feats[key] = (consistency(lam_e), np.asarray(gate_e, dtype=float)
                          * np.ones(len(lam_e)))
        for name, (lam_p, gate_p) in td.physics.items():
            feats[f"phys_{name}"] = (consistency(lam_p),
                                     np.asarray(gate_p, dtype=float)
                                     * np.ones(len(lam_p)))
        for name in TEMP_FEATURES:
            feats[f"temp_{name}"] = (consistency(td.hist[name]),
                                     np.ones(len(td.hist[name])))
        return feats

    def run(self, td) -> DiagnosisResult:
        feats = self._features(td)
        names = list(self.causes)
        k_total = len(td.t)
        loglik = np.zeros((k_total, len(names)))
        for ci, cause in enumerate(names):
            low = set(self.causes[cause])
            ll = np.zeros(k_total)
            for fname, (c, gate) in feats.items():
                term = np.log((1.0 - c + EPS) if fname in low else (c + EPS))
                ll += gate * term
            loglik[:, ci] = ew_smooth(ll, SMOOTH_ALPHA)

        prior = np.full(len(names), (1.0 - PRIOR_NOMINAL) / (len(names) - 1))
        prior[names.index("nominal")] = PRIOR_NOMINAL
        score = np.log(prior)[None, :] + EVIDENCE_MULT * loglik
        score -= score.max(axis=1, keepdims=True)
        post = np.exp(score)
        post /= post.sum(axis=1, keepdims=True)
        return DiagnosisResult(t=td.t, causes=names, posterior=post)
