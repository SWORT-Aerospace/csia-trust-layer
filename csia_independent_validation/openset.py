"""Distance from an unknown-fault trajectory to the modelled observation set.

WHY THIS EXISTS
---------------
The prior campaign routed a 0.40 V ringing fault to
``UNKNOWN_OR_MODEL_MISMATCH`` and absorbed a 0.10 V one as
``CERTIFIED_IN_MODEL``. The tempting response is to lower a threshold until the
0.10 V case is caught too. That would be tuning, and it would also be wrong if
the 0.10 V trajectory genuinely lies inside what the model can already explain:
no classifier can separate a point from a set that contains it.

So instead of a threshold, this module measures a distance.

THE MODELLED OBSERVATION SET
----------------------------
For a fixed command ``u``, the set of voltage trajectories the model can
produce is

    Y_model(u) = union over h in H of Y_h(u, Theta_h, E)

where ``H`` is the hypothesis bank -- nominal, and a resistance increase at
each magnitude on the frozen grid -- and ``Theta_h`` is the declared nuisance
envelope: polarization resistance and time constant, and open-circuit drift.
``E`` is the sensing envelope. It is enumerated on a finite grid, so every
distance reported here is an **upper bound** on the true infimum, and the
document says so rather than implying the set was covered.

THE METRIC
----------
The estimator fits an intercept and a slope on ``[1, -I]``, so any component of
a voltage trajectory lying in that two-dimensional subspace is absorbed for
free and cannot contribute to detectability. The distance is therefore measured
on the **residual after projecting that subspace out**, normalised by the
declared voltage-noise sigma and the window length:

    delta_unknown = min over y in Y_model of
                    || P_perp (y_unknown - y) || / (sigma_V sqrt(N))

so ``delta_unknown`` is in units of "sigmas of per-sample sensor noise". A
value near 1 means the unknown trajectory is as far from everything the model
can explain as noise alone would put it -- which is to say, not far at all.

This metric was fixed before the sweep was run.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .plants import Observation, Sensing, SYNTHETIC_Q, QParams, simulate

LAYER = "B"
TRUTH_BEARING = True
SCHEMA = "csia.independent_validation.openset/1"

#: The declared nuisance envelope, enumerated. Same ranges as the certificate's
#: polarization envelope so the two describe the same declared model.
R1_GRID = (0.004, 0.012, 0.020)
TAU_GRID = (1.0, 6.3, 40.0)
DRIFT_GRID = (0.0, 1.0e-3)

#: The hypothesis bank: nominal plus a resistance increase at each magnitude.
MAGNITUDE_GRID = (0.0, 0.002, 0.004, 0.006, 0.010, 0.020, 0.040)


def residual_basis(observation: Observation) -> np.ndarray:
    """The two columns the estimator fits: a constant and the current."""
    current = np.asarray(observation.i_meas, dtype=float)
    return np.column_stack([np.ones_like(current), -current])


def project_out(values: np.ndarray, basis: np.ndarray) -> np.ndarray:
    """Remove everything the estimator can absorb into its own parameters."""
    coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
    return values - basis @ coefficients


@dataclass(frozen=True)
class Separation:
    """One unknown trajectory against the modelled set."""

    delta_unknown: float            # sigmas of per-sample voltage noise
    nearest_magnitude: float        # ohm, the closest hypothesis
    nearest_r1: float
    nearest_tau_s: float
    nearest_drift_v_per_s: float
    members_enumerated: int

    def to_dict(self) -> Dict:
        return {
            "delta_unknown_sigmas": self.delta_unknown,
            "nearest_magnitude_ohm": self.nearest_magnitude,
            "nearest_r1_ohm": self.nearest_r1,
            "nearest_tau_s": self.nearest_tau_s,
            "nearest_drift_v_per_s": self.nearest_drift_v_per_s,
            "members_enumerated": self.members_enumerated,
            "note": ("an upper bound on the infimum: the declared envelope is "
                     "enumerated on a finite grid, not covered"),
        }


class ModelledSet:
    """Enumerates ``Y_model(u)`` once and answers distance queries against it.

    Building the set is the expensive part and it does not depend on the
    unknown trajectory, so it is built once per command and reused across a
    whole sweep.
    """

    def __init__(self, command, *, plant: str = "Q1", duration: float = 8.0,
                 seed: int = 0, sensing: Optional[Sensing] = None) -> None:
        self.command = command
        self.plant = plant
        self.duration = duration
        self.seed = seed
        self.sensing = sensing
        self._members: List[Tuple[np.ndarray, Tuple]] = []
        self._basis: Optional[np.ndarray] = None
        self._sigma_v = 0.0
        self._build()

    def _build(self) -> None:
        base_params = QParams(**SYNTHETIC_Q)
        reference, _ = simulate(self.command, plant=self.plant,
                                duration=self.duration, seed=self.seed,
                                sensing=self.sensing)
        self._basis = residual_basis(reference)
        self._sigma_v = (self.sensing.sigma_v if self.sensing is not None
                         else 0.020)
        from dataclasses import replace
        for magnitude in MAGNITUDE_GRID:
            for r1 in R1_GRID:
                for tau in TAU_GRID:
                    for drift in DRIFT_GRID:
                        params = replace(base_params, r1=r1, tau1_s=tau)
                        observation, _ = simulate(
                            self.command, plant=self.plant,
                            duration=self.duration, seed=self.seed,
                            params=params, sensing=self.sensing,
                            r0_delta=magnitude, drift_v_per_s=drift)
                        residual = project_out(
                            np.asarray(observation.v_meas, dtype=float),
                            self._basis)
                        self._members.append(
                            (residual, (magnitude, r1, tau, drift)))

    @property
    def size(self) -> int:
        return len(self._members)

    def distance(self, observation: Observation) -> Separation:
        """Smallest normalised residual distance to any enumerated member."""
        residual = project_out(
            np.asarray(observation.v_meas, dtype=float), self._basis)
        n = residual.size
        best = math.inf
        best_labels = (float("nan"),) * 4
        for member, labels in self._members:
            difference = residual - member
            value = float(np.linalg.norm(difference)) / (
                self._sigma_v * math.sqrt(n))
            if value < best:
                best, best_labels = value, labels
        return Separation(
            delta_unknown=best, nearest_magnitude=best_labels[0],
            nearest_r1=best_labels[1], nearest_tau_s=best_labels[2],
            nearest_drift_v_per_s=best_labels[3],
            members_enumerated=len(self._members))


def boundary_from(separations: Sequence[float], routed: Sequence[bool], *,
                  target: float = 0.90) -> Dict:
    """Estimate the separation above which routing to unknown is reliable.

    Returns the smallest observed ``delta_unknown`` above which the routing
    rate reaches ``target``, together with the rate below it, and refuses to
    report a boundary when the data does not contain one.
    """
    if len(separations) != len(routed):
        raise ValueError("one routing outcome per separation")
    if not separations:
        return {"boundary": None, "reason": "no observations"}
    order = sorted(zip(separations, routed))
    n = len(order)
    for index in range(n):
        tail = [flag for _, flag in order[index:]]
        if tail and sum(tail) / len(tail) >= target:
            head = [flag for _, flag in order[:index]]
            return {
                "boundary_sigmas": order[index][0],
                "routed_rate_above": sum(tail) / len(tail),
                "routed_rate_below": (sum(head) / len(head)) if head else None,
                "n_above": len(tail), "n_below": len(head),
                "target": target,
            }
    return {"boundary_sigmas": None,
            "reason": (f"no separation reaches a {target:.0%} routing rate "
                       "in the tested range"),
            "routed_rate_overall": sum(routed) / n, "n": n}
