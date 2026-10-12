"""Closest prior-art baselines, reconstructed from standard formulations.

READ THIS FIRST
---------------
No scholarly full text is reachable from this host. A reproducible access check
was run this session: ``api.crossref.org``, ``arxiv.org`` and ``doi.org`` all
returned a proxy ``403 CONNECT tunnel failed``. Nothing here is therefore a
reproduction of any specific paper's method, and nothing here licenses a
novelty claim in either direction.

What these are: **textbook reconstructions** of the standard objectives named
in the task, written from their defining equations, implemented over the same
finite action space every other strategy uses, and labelled as reconstructions
everywhere they are reported. Novelty status stays ``BLOCKED_EXTERNAL_ACCESS``.
``BASELINE_MAPPING.md`` records what each is, what it is not, and what would
have to be read to upgrade the claim.

THE MODEL THEY ALL ASSUME
-------------------------
``V_k = E - R I_k + eta_k`` with ``eta`` zero-mean of variance ``sigma_V^2``,
two unknown parameters ``(E, R)``. That is the estimator's model, which is the
point: these baselines are optimal *for the model the estimator assumes*, and
the interesting question is what happens when the plant is not that model.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Sequence, Tuple

import numpy as np

SCHEMA = "csia.independent_validation.baselines/1"

#: Everything in this module is one of these, and the label travels with the
#: number wherever it is reported.
PROVENANCE = "TEXTBOOK_RECONSTRUCTION_NOT_A_PAPER_REPRODUCTION"


# --- 1. persistent excitation --------------------------------------------

def persistent_excitation_matrix(signal: Sequence[float], order: int
                                 ) -> np.ndarray:
    """The order-``n`` sample covariance matrix of the regressor history.

    A signal is persistently exciting of order ``n`` when this matrix is
    positive definite. The construction is the standard one: stack ``n``
    consecutive samples into a regressor, average the outer products.
    """
    values = np.asarray(signal, dtype=float)
    values = values - values.mean()
    n = values.size
    if order < 1 or n <= order:
        raise ValueError("need more samples than the requested order")
    window = np.lib.stride_tricks.sliding_window_view(values, order)
    return (window.T @ window) / window.shape[0]


def persistent_excitation_level(signal: Sequence[float], order: int) -> float:
    """Smallest eigenvalue of the order-``n`` matrix. Positive means PE of n."""
    matrix = persistent_excitation_matrix(signal, order)
    return float(np.linalg.eigvalsh(matrix)[0])


def is_persistently_exciting(signal: Sequence[float], order: int, *,
                             tolerance: float = 1e-9) -> bool:
    return persistent_excitation_level(signal, order) > tolerance


# --- 2. Fisher information / optimal input design ------------------------

def fisher_information(current: Sequence[float], sigma_v: float
                       ) -> np.ndarray:
    """FIM for ``(E, R)`` under ``V = E - R I + eta``.

    ``J = (1/sigma^2) [[N, -sum I], [-sum I, sum I^2]]``. Derived directly
    from the log-likelihood of a linear-Gaussian model; no citation needed and
    none implied.
    """
    values = np.asarray(current, dtype=float)
    n = values.size
    total = float(values.sum())
    square = float((values ** 2).sum())
    return np.array([[n, -total], [-total, square]]) / (sigma_v ** 2)


def d_optimal_score(current: Sequence[float], sigma_v: float) -> float:
    """``det J``. Maximised by a D-optimal design."""
    return float(np.linalg.det(fisher_information(current, sigma_v)))


def e_optimal_score(current: Sequence[float], sigma_v: float) -> float:
    """``lambda_min(J)``. Maximised by an E-optimal design."""
    return float(np.linalg.eigvalsh(fisher_information(current, sigma_v))[0])


def variance_of_r(current: Sequence[float], sigma_v: float) -> float:
    """Cramer-Rao variance of the resistance estimate alone.

    Inverting the 2x2 FIM gives ``var(R) = sigma^2 / S_II`` exactly, where
    ``S_II`` is the centred second moment of current. So minimising the
    variance of ``R`` under the assumed model is **identically** the objective
    of the P7a benchmark.

    That equivalence is not a coincidence and it is the most useful thing this
    module has to say: P7a is the classical optimal design for this parameter.
    Its poor showing against the outcome oracle is therefore evidence about the
    assumed model being wrong, not about optimal-design theory being wrong.
    """
    values = np.asarray(current, dtype=float)
    centred = values - values.mean()
    s_ii = float(np.sum(centred ** 2))
    if s_ii <= 0:
        return math.inf
    return sigma_v ** 2 / s_ii


# --- 3. finite-model active discrimination -------------------------------

def pairwise_separation(predictions: Dict[str, np.ndarray], sigma_v: float
                        ) -> float:
    """Minimum normalised distance between any two hypothesis predictions.

    The standard finite-model active-discrimination objective: choose the
    input that maximises the worst-case separation between the outputs the
    competing hypotheses would produce, in units of noise sigma.
    """
    keys = sorted(predictions)
    if len(keys) < 2:
        raise ValueError("need at least two hypotheses to discriminate")
    worst = math.inf
    for a, b in itertools.combinations(keys, 2):
        difference = np.asarray(predictions[a]) - np.asarray(predictions[b])
        n = difference.size
        worst = min(worst, float(np.linalg.norm(difference))
                    / (sigma_v * math.sqrt(n)))
    return worst


# --- 4. set-membership volume reduction ----------------------------------

@dataclass(frozen=True)
class FeasibleSet:
    """The ``(E, R)`` pairs consistent with bounded-noise data.

    ``{(E, R) : |V_k - E + R I_k| <= eps for all k}``. In two parameters this
    is a polytope, and its area is computed exactly by vertex enumeration
    rather than estimated, so "volume reduction" here is a number and not a
    proxy for one.
    """

    vertices: np.ndarray
    area: float
    empty: bool

    def to_dict(self) -> Dict:
        return {"area": self.area, "empty": self.empty,
                "n_vertices": int(len(self.vertices))}


def feasible_set(current: Sequence[float], voltage: Sequence[float],
                 epsilon: float, *, bounds: Tuple[float, float, float, float]
                 = (10.0, 25.0, -0.5, 0.5)) -> FeasibleSet:
    """Exact area of the bounded-noise feasible set for ``(E, R)``.

    Each sample contributes two half-planes. The intersection is taken with a
    declared box so the set is bounded when the data constrains only one
    direction, and the box is part of the declared prior rather than a silent
    default.
    """
    i = np.asarray(current, dtype=float)
    v = np.asarray(voltage, dtype=float)
    e_lo, e_hi, r_lo, r_hi = bounds
    # Half-planes a.x <= b with x = (E, R).
    rows = [(1.0, -ik, vk + epsilon) for ik, vk in zip(i, v)]
    rows += [(-1.0, ik, -(vk - epsilon)) for ik, vk in zip(i, v)]
    rows += [(1.0, 0.0, e_hi), (-1.0, 0.0, -e_lo),
             (0.0, 1.0, r_hi), (0.0, -1.0, -r_lo)]
    a = np.array([[r[0], r[1]] for r in rows], dtype=float)
    b = np.array([r[2] for r in rows], dtype=float)

    points = []
    m = len(rows)
    for p, q in itertools.combinations(range(m), 2):
        matrix = a[[p, q]]
        determinant = np.linalg.det(matrix)
        if abs(determinant) < 1e-12:
            continue
        point = np.linalg.solve(matrix, b[[p, q]])
        if np.all(a @ point <= b + 1e-9):
            points.append(point)
    if len(points) < 3:
        return FeasibleSet(vertices=np.zeros((0, 2)), area=0.0,
                           empty=not points)
    hull = np.array(points)
    centre = hull.mean(axis=0)
    order = np.argsort(np.arctan2(hull[:, 1] - centre[1],
                                  hull[:, 0] - centre[0]))
    hull = hull[order]
    x, y = hull[:, 0], hull[:, 1]
    area = 0.5 * abs(float(np.dot(x, np.roll(y, -1))
                           - np.dot(y, np.roll(x, -1))))
    return FeasibleSet(vertices=hull, area=area, empty=False)


# --- 6. conventional post-execution validation ---------------------------

@dataclass(frozen=True)
class ClassicalFit:
    """Ordinary least squares with its textbook standard error.

    Deliberately has **no staleness semantics**: it never asks whether the
    waveform that was executed is the one that was proposed, whether the window
    was truncated, or whether coverage was met. That absence is the baseline's
    defining property and the thing the RCEC adds, so it is written here as a
    property of the class rather than an oversight.
    """

    r_hat: float
    e_hat: float
    standard_error: float
    t_statistic: float
    ci_low: float
    ci_high: float
    n: int

    def to_dict(self) -> Dict:
        return {"r_hat": self.r_hat, "e_hat": self.e_hat,
                "standard_error": self.standard_error,
                "t_statistic": self.t_statistic,
                "ci_low": self.ci_low, "ci_high": self.ci_high, "n": self.n,
                "checks_staleness": False}


def classical_fit(current: Sequence[float], voltage: Sequence[float], *,
                  k_sigma: float = 1.96) -> ClassicalFit:
    i = np.asarray(current, dtype=float)
    v = np.asarray(voltage, dtype=float)
    design = np.column_stack([np.ones_like(i), -i])
    solution, *_ = np.linalg.lstsq(design, v, rcond=None)
    residual = v - design @ solution
    n = i.size
    dof = max(n - 2, 1)
    s2 = float(residual @ residual) / dof
    covariance = s2 * np.linalg.inv(design.T @ design)
    standard_error = math.sqrt(float(covariance[1, 1]))
    r_hat = float(solution[1])
    return ClassicalFit(
        r_hat=r_hat, e_hat=float(solution[0]),
        standard_error=standard_error,
        t_statistic=(r_hat / standard_error if standard_error > 0
                     else math.inf),
        ci_low=r_hat - k_sigma * standard_error,
        ci_high=r_hat + k_sigma * standard_error, n=int(n))


#: Implemented reconstructions, by the name the task uses for them.
IMPLEMENTED = (
    "persistent_excitation",
    "fisher_information_input_design",
    "finite_model_active_discrimination",
    "set_membership_volume_reduction",
    "classical_post_execution_validation",
)

#: Named in the task and deliberately NOT implemented, with the reason.
NOT_IMPLEMENTED = {
    "constrained_robust_tube_mpc_active_diagnosis": (
        "A tube-MPC formulation needs a receding-horizon optimiser over a "
        "disturbance-invariant tube, which is a substantially different "
        "experimental object from a selection rule over a fixed action space. "
        "Reconstructing one from memory and presenting it as the closest "
        "prior art would misrepresent both it and this comparison. Left "
        "unimplemented and recorded as a gap."),
}
