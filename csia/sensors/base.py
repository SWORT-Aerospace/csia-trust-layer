"""Common sensor-model machinery.

CSIA role: each SensorModel is one *node* of the Dynamic Trust Graph. A model
samples the shared FlightTruth at its own output rate, adds a realistic noise
model, and applies any injected faults addressed to it. Output is a dict of
aligned numpy arrays, always including ``t`` and ``valid``.
"""

import numpy as np

from .truth import FlightTruth


class SensorModel:
    """Base class. Subclasses set ``name``/``rate_hz`` and implement
    ``_measure(truth, idx, faults) -> dict[str, np.ndarray]``."""

    name: str = "sensor"
    rate_hz: float = 100.0

    def __init__(self, name: str | None = None, seed: int = 0):
        if name is not None:
            self.name = name
        self.rng = np.random.default_rng(seed)

    def sample(self, truth: FlightTruth, faults=()) -> dict:
        idx = self._decimate_indices(truth)
        out = self._measure(truth, idx, list(faults))
        out.setdefault("t", truth.t[idx])
        out.setdefault("valid", np.ones(len(idx), dtype=bool))
        return out

    def _decimate_indices(self, truth: FlightTruth) -> np.ndarray:
        step = max(1, int(round(1.0 / (self.rate_hz * truth.dt))))
        return np.arange(0, truth.n, step)

    def _measure(self, truth: FlightTruth, idx: np.ndarray, faults) -> dict:
        raise NotImplementedError

    # --- shared noise helpers -------------------------------------------------
    def white(self, n: int, sigma: float, ncol: int | None = None) -> np.ndarray:
        shape = (n,) if ncol is None else (n, ncol)
        return self.rng.normal(0.0, sigma, shape)

    def random_walk(self, n: int, sigma_step: float,
                    ncol: int | None = None) -> np.ndarray:
        return np.cumsum(self.white(n, sigma_step, ncol), axis=0)

    def gauss_markov(self, t: np.ndarray, sigma: float, tau: float,
                     ncol: int = 1) -> np.ndarray:
        """First-order Gauss-Markov (exponentially correlated) noise — used
        for GPS position error, which wanders rather than being white."""
        dt = float(np.mean(np.diff(t))) if len(t) > 1 else 1.0
        a = np.exp(-dt / tau)
        drive = self.rng.normal(0.0, sigma * np.sqrt(1 - a * a), (len(t), ncol))
        out = np.empty_like(drive)
        prev = self.rng.normal(0.0, sigma, ncol)
        for k in range(len(t)):
            prev = a * prev + drive[k]
            out[k] = prev
        return out
