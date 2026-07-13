"""Historical-trend predictor and statistical-confidence machinery.

CSIA role: the second of the three independent predictors. Holt double
exponential smoothing gives a one-step-ahead level+trend forecast per
channel; the normalized innovation feeds the sensor's temporal-stability
score, and the running innovation-variance ratio feeds its statistical
confidence (an innovation-whiteness test: a healthy sensor's normalized
innovations should have unit variance).
"""

import numpy as np


def holt_prediction(x: np.ndarray, alpha: float = 0.3,
                    beta: float = 0.05) -> np.ndarray:
    """One-step-ahead Holt (level + trend) forecast. pred[k] is the forecast
    of x[k] made strictly from x[:k] — no lookahead."""
    n = len(x)
    pred = np.empty(n)
    level, trend = x[0], 0.0
    for k in range(n):
        pred[k] = level + trend
        err = x[k] - pred[k]
        level = pred[k] + alpha * err
        trend = trend + alpha * beta * err
    return pred


def normalized_innovation_sq(x: np.ndarray, pred: np.ndarray,
                             sigma: float) -> np.ndarray:
    return ((x - pred) / sigma) ** 2


def ew_smooth(x: np.ndarray, alpha: float) -> np.ndarray:
    """Exponentially weighted smoothing (sequential, no lookahead)."""
    out = np.empty_like(x)
    acc = x[0]
    for k in range(len(x)):
        acc = (1.0 - alpha) * acc + alpha * x[k]
        out[k] = acc
    return out


# Representative channels per sensor for the historical predictor, with the
# nominal innovation scale sigma. Scales are set from the phase-1 noise
# models plus headroom for benign maneuvering, so nominal flight scores ~1.
HIST_CHANNELS = {
    "imu0":      [("accel", 2, 0.20)],        # specific force z, m/s^2
    "imu1":      [("accel", 2, 0.20)],
    "baro":      [("altitude", None, 0.15)],  # m
    "mag":       [("field_ut", 1, 0.25)],     # uT, lateral component
    # GPS horizontal position is trend-dominated under maneuvering (a Holt
    # one-step forecast lags meters behind a 15 m/s curved track), so the
    # historical predictor watches the smooth channels; horizontal position
    # is cross-checked by the physics predictor (pos-derivative vs Doppler).
    "gps":       [("pos", 2, 0.60), ("vel", 0, 0.50), ("vel", 1, 0.50),
                  ("vel", 2, 0.50)],
    "motor_esc": [("rpm", 0, 60.0)],
    "battery":   [("voltage", None, 0.04), ("current", None, 1.0)],
    "vibration": [("rms", None, 0.035)],
}


def historical_scores(stream: dict, channels) -> tuple[np.ndarray, np.ndarray]:
    """Returns (lam_hist, var_ratio) on the stream's own timeline.
    lam_hist: mean normalized squared innovation across channels.
    var_ratio: EW variance of normalized innovations (whiteness statistic).
    """
    lams = []
    for key, col, sigma in channels:
        x = stream[key] if col is None else stream[key][:, col]
        x = np.asarray(x, dtype=float)
        pred = holt_prediction(x)
        lams.append(normalized_innovation_sq(x, pred, sigma))
    lam = np.mean(lams, axis=0)
    # EW variance of the (mean-)normalized innovation as whiteness statistic.
    var_ratio = ew_smooth(lam, alpha=0.05)
    lam_smooth = ew_smooth(lam, alpha=0.15)
    return lam_smooth, var_ratio
