"""Three narrow propositions, with the assumptions kept in view.

No grand theorem is attempted. Each of these is a small statement with stated
assumptions, units, a proof or a counterexample, and an executable check in
``tests/test_iv_propositions.py``. Where an assumption cannot be verified from
inside the system, it is named as such rather than absorbed into the algebra.

The module contains the *constructions* the propositions refer to. The
statements themselves live in ``FORMAL_PROPOSITIONS.md``; keeping them together
would tempt a reader to treat a docstring as a proof.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Sequence, Tuple

import numpy as np

SCHEMA = "csia.independent_validation.propositions/1"


# --- Proposition A: command certificates are not sufficient --------------

def moments(t: Sequence[float], signal: Sequence[float]
            ) -> Tuple[float, float]:
    """``(S_II, S_tI)`` for a sampled signal. Units: A^2 and s.A.

    ``S_II = sum (x - xbar)^2`` and ``S_tI = sum (t - tbar)(x - xbar)``. These
    are the realized moments the certificate's drift term is built on.
    """
    time = np.asarray(t, dtype=float)
    values = np.asarray(signal, dtype=float)
    centred = values - values.mean()
    return (float(np.sum(centred ** 2)),
            float(np.sum((time - time.mean()) * centred)))


def first_order_lag(command: Sequence[float], dt: float, tau: float,
                    initial: float = 0.0) -> np.ndarray:
    """The transformation ``F``: causal, bounded, linear, time-invariant.

    ``x[k+1] = x[k] e^{-dt/tau} + u[k](1 - e^{-dt/tau})``.

    Causal because ``x[k]`` depends only on ``u[j]`` for ``j <= k``. Bounded
    because it is a convex combination of past inputs, so
    ``|x|_inf <= |u|_inf``. This is not an adversarial construction; it is the
    command-to-current response every one of these plants has.
    """
    values = np.asarray(command, dtype=float)
    decay = math.exp(-dt / tau) if tau > 0 else 0.0
    out = np.empty_like(values)
    state = float(initial)
    for k, value in enumerate(values):
        state = state * decay + float(value) * (1.0 - decay)
        out[k] = state
    return out


def palindromic_command(n: int, cycles: int, amplitude: float) -> np.ndarray:
    """A command that is exactly symmetric about its window midpoint.

    Symmetric in the command is the property the prior phase's probe design
    relied on, and it is the property that does not survive ``F``.
    """
    u = np.linspace(0.0, 1.0, n)
    return amplitude * np.cos(2.0 * math.pi * cycles * u)


@dataclass(frozen=True)
class CommandCounterexample:
    """One instance of Proposition A, with both sides measured."""

    s_ii_command: float
    s_ti_command: float
    lever_command: float
    s_ii_realized: float
    s_ti_realized: float
    lever_realized: float
    s_ii_min: float
    gamma: float

    @property
    def command_passes(self) -> bool:
        return (self.s_ii_command >= self.s_ii_min
                and abs(self.lever_command) <= self.gamma)

    @property
    def realized_passes(self) -> bool:
        return (self.s_ii_realized >= self.s_ii_min
                and abs(self.lever_realized) <= self.gamma)

    @property
    def is_a_counterexample(self) -> bool:
        return self.command_passes and not self.realized_passes

    def to_dict(self) -> Dict:
        return {
            "s_ii_command": self.s_ii_command,
            "s_ti_command": self.s_ti_command,
            "lever_command_s": self.lever_command,
            "s_ii_realized": self.s_ii_realized,
            "s_ti_realized": self.s_ti_realized,
            "lever_realized_s": self.lever_realized,
            "s_ii_min": self.s_ii_min, "gamma_s": self.gamma,
            "command_passes": self.command_passes,
            "realized_passes": self.realized_passes,
            "is_a_counterexample": self.is_a_counterexample,
        }


def command_counterexample(*, n: int = 400, dt: float = 0.02,
                           tau: float = 0.25, cycles: int = 3,
                           amplitude: float = 10.0,
                           s_ii_min: float = 1.0e3,
                           gamma: float = 0.01) -> CommandCounterexample:
    """Build one instance and measure both sides. No claim is asserted here."""
    t = np.arange(n, dtype=float) * dt
    command = palindromic_command(n, cycles, amplitude)
    realized = first_order_lag(command, dt, tau)
    s_ii_u, s_ti_u = moments(t, command)
    s_ii_i, s_ti_i = moments(t, realized)
    return CommandCounterexample(
        s_ii_command=s_ii_u, s_ti_command=s_ti_u,
        lever_command=s_ti_u / s_ii_u if s_ii_u else float("nan"),
        s_ii_realized=s_ii_i, s_ti_realized=s_ti_i,
        lever_realized=s_ti_i / s_ii_i if s_ii_i else float("nan"),
        s_ii_min=s_ii_min, gamma=gamma)


# --- Proposition B: conditional soundness --------------------------------

def sets_are_disjoint(estimate_a: float, estimate_b: float,
                      half_width: float) -> bool:
    """Whether two symmetric error sets of the same half-width are disjoint.

    ``[a - h, a + h]`` and ``[b - h, b + h]`` are disjoint exactly when
    ``|a - b| > 2h``. Trivial, and written as a function so the proposition's
    proof has something executable to point at.
    """
    return abs(estimate_a - estimate_b) > 2.0 * half_width


def soundness_holds(true_nominal: float, true_fault: float,
                    estimate_nominal: float, estimate_fault: float,
                    half_width: float) -> Dict:
    """Check the conclusion of Proposition B on one instance.

    The **assumption** is that the true error lies inside the declared set:
    ``|estimate - true| <= half_width`` on both windows. That assumption is
    checked and reported separately from the conclusion, because it is the
    assumption a reader should be suspicious of and not the algebra.
    """
    assumption = (abs(estimate_nominal - true_nominal) <= half_width
                  and abs(estimate_fault - true_fault) <= half_width)
    disjoint = sets_are_disjoint(estimate_nominal, estimate_fault, half_width)
    true_change_sign = (0 if true_fault == true_nominal
                        else int(math.copysign(1, true_fault - true_nominal)))
    claimed_sign = (0 if estimate_fault == estimate_nominal
                    else int(math.copysign(1, estimate_fault
                                           - estimate_nominal)))
    return {
        "assumption_error_set_contains_truth": assumption,
        "sets_disjoint": disjoint,
        "true_change_sign": true_change_sign,
        "claimed_change_sign": claimed_sign,
        "sign_is_correct": claimed_sign == true_change_sign,
        "conclusion_holds": (not (assumption and disjoint))
                            or claimed_sign == true_change_sign,
    }


# --- Proposition C: staleness after action modification ------------------

@dataclass(frozen=True)
class Prefix:
    """A realized prefix of an action, and whether it can carry a certificate."""

    t: np.ndarray
    i_meas: np.ndarray
    v_meas: np.ndarray
    fraction_executed: float
    recomputed_from_measurement: bool


def truncate(t: Sequence[float], i_meas: Sequence[float],
             v_meas: Sequence[float], fraction: float) -> Prefix:
    """Cut an action short at ``fraction`` of its window."""
    n = len(t)
    keep = max(int(round(n * fraction)), 1)
    return Prefix(t=np.asarray(t, dtype=float)[:keep],
                  i_meas=np.asarray(i_meas, dtype=float)[:keep],
                  v_meas=np.asarray(v_meas, dtype=float)[:keep],
                  fraction_executed=fraction,
                  recomputed_from_measurement=True)


def predicted_moments_bound_realized(predicted: Tuple[float, float],
                                     realized: Tuple[float, float]) -> bool:
    """Does a prediction made for the full waveform still bound the prefix?

    The certificate's excitation condition is a lower bound on ``S_II`` and an
    upper bound on ``|S_tI|/S_II``. A prediction made for the whole window
    bounds a truncated execution only if the truncated window happens to have
    at least as much excitation and no more drift leverage, which truncation
    does not in general provide.
    """
    predicted_s_ii, predicted_lever = predicted
    realized_s_ii, realized_lever = realized
    return (realized_s_ii >= predicted_s_ii
            and abs(realized_lever) <= abs(predicted_lever))
