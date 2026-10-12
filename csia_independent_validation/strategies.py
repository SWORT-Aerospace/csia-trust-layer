"""Deployable strategies P0-P6 and the robust selectors S0-S3.

These are **deployable**: every decision here is made from information a real
implementation could have. Declared configuration, the proposed command, the
measured telemetry of earlier windows, permitted online nuisance estimates, and
nothing else. No strategy in this module receives a plant identity, a fault
label, a true resistance, an outcome, or anything computed by Layer B, and the
architectural tests enforce that by walking the import graph.

The strategies are re-instantiations of the prior phase's arms **inside the
shared finite action space**, not the same code. They have to be, because a
ceiling is only meaningful when the oracle and the strategies choose from one
set (see ``ORACLE_TAXONOMY.md`` §2). Where a prior arm's behaviour does not map
cleanly onto a selection rule over a fixed action set, the mapping is stated in
the docstring rather than implied by the name.

The selectors S0-S3 answer a different question: given only what is observable
before acting, which of P2 and P4 should be used -- or should neither be used
at all. A selector that is forced to pick one of two actions is not a selector,
it is a coin, so all three non-action outcomes are first-class returns.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np

from .actions import ACTION_SPACE, PASSIVE, Action, by_name

LAYER = "A-compatible"
SCHEMA = "csia.independent_validation.strategies/1"

#: Returned instead of an action. Each is a real answer, not a failure.
WAIT_FOR_MISSION_EVIDENCE = "WAIT_FOR_MISSION_EVIDENCE"
NO_SAFE_INFORMATIVE_ACTION = "NO_SAFE_INFORMATIVE_ACTION"
INSUFFICIENT_NUISANCE_KNOWLEDGE = "INSUFFICIENT_NUISANCE_KNOWLEDGE"
ABSTENTIONS = (WAIT_FOR_MISSION_EVIDENCE, NO_SAFE_INFORMATIVE_ACTION,
               INSUFFICIENT_NUISANCE_KNOWLEDGE)

STRATEGIES = ("P0_passive", "P1_palindromic", "P2_compensated", "P3_shaped",
              "P4_feedback", "P5_random_safe", "P6_mission")

#: Minimum predicted second moment for an action to count as informative at
#: all. Declared, frozen before any selector comparison was run.
S_II_MIN = 2.0e3

LOOP_HZ = 50.0


@dataclass(frozen=True)
class Observable:
    """Everything a selector is allowed to condition on.

    Every field is something an implementation could have before acting. There
    is deliberately no field for the plant, the fault, the magnitude or the
    outcome, and ``tests/test_iv_selectors.py`` pins the field names so that
    adding one is a visible design change rather than an accident.
    """

    lag_estimate_s: float           # s, best online estimate
    lag_uncertainty_s: float        # s, half-width of the interval
    drift_estimate_v_per_s: float   # V/s
    drift_uncertainty_v_per_s: float
    sigma_i_bound_a: float          # A, commissioned noise bound
    sigma_v_bound_v: float          # V
    remaining_energy_as: float      # A.s available for probing
    remaining_time_s: float         # s
    mission_phase: str              # "cruise", "hover", "manoeuvre", "landing"
    clip_margin_a: float            # A of headroom before the current limit

    def to_dict(self) -> Dict:
        return {
            "lag_estimate_s": self.lag_estimate_s,
            "lag_uncertainty_s": self.lag_uncertainty_s,
            "drift_estimate_v_per_s": self.drift_estimate_v_per_s,
            "drift_uncertainty_v_per_s": self.drift_uncertainty_v_per_s,
            "sigma_i_bound_a": self.sigma_i_bound_a,
            "sigma_v_bound_v": self.sigma_v_bound_v,
            "remaining_energy_as": self.remaining_energy_as,
            "remaining_time_s": self.remaining_time_s,
            "mission_phase": self.mission_phase,
            "clip_margin_a": self.clip_margin_a,
        }


# --- predicted moments, from the command and the declared lag ------------

def predicted_current(action: Action, lag_s: float,
                      hz: float = LOOP_HZ) -> Tuple[np.ndarray, np.ndarray]:
    """What the realized current is expected to be, given a declared lag.

    A prediction, and named so. It uses the same exact-step form the plants
    use, which is a modelling choice a real implementation would also have to
    make and could also get wrong -- Proposition A is exactly about the gap
    between this and the truth.
    """
    duration = action.duration_s
    n = max(int(round(duration * hz)), 2)
    dt = 1.0 / hz
    t = np.arange(n, dtype=float) * dt
    command = np.array([action.command()(float(x)) for x in t])
    decay = math.exp(-dt / lag_s) if lag_s > 0 else 0.0
    out = np.empty(n)
    state = 0.0
    for k, value in enumerate(command):
        state = state * decay + value * (1.0 - decay)
        out[k] = state
    return t, out


def predicted_moments(action: Action, lag_s: float) -> Tuple[float, float]:
    """``(S_II, drift lever)`` predicted for an action under a declared lag."""
    t, current = predicted_current(action, lag_s)
    centred = current - current.mean()
    s_ii = float(np.sum(centred ** 2))
    s_ti = float(np.sum((t - t.mean()) * centred))
    return s_ii, (s_ti / s_ii if s_ii > 0 else float("nan"))


def _affordable(observable: Observable) -> Tuple[Action, ...]:
    """Actions that fit the remaining energy, time and current headroom."""
    return tuple(a for a in ACTION_SPACE
                 if a.energy_as <= observable.remaining_energy_as
                 and a.duration_s <= observable.remaining_time_s
                 and a.peak_excess_a <= observable.clip_margin_a)


# --- P0 to P6 -------------------------------------------------------------

def p0_passive(observable: Observable) -> Action:
    """Hold station and watch. Costs nothing and excites nothing."""
    return PASSIVE


def p1_palindromic(observable: Observable) -> Action:
    """A fixed symmetric burst, chosen without reference to conditions.

    The naive arm: palindromic in the command, and Proposition A is the
    demonstration that this buys nothing in the realized current.

    Naive about *diagnosis*, not about safety. The first version of this
    returned its fixed waveform whatever the remaining energy, time or current
    headroom, which a test caught: a strategy that proposes an inadmissible
    action is not a naive strategy, it is a broken one. Hard constraints are
    declared and knowable, so every arm respects them and falls back to
    passive. What P1 still ignores is the lag and the drift, which is the
    naivety the comparison is about.
    """
    fixed = by_name("cosine3_10A_8s")
    return fixed if fixed in _affordable(observable) else PASSIVE


def p2_compensated(observable: Observable) -> Action:
    """Minimise the PREDICTED realized drift lever, subject to excitation.

    This is the compensated arm. It uses the online lag estimate to predict
    what the realized current will look like and picks the admissible action
    whose predicted lever is smallest among those that clear ``S_II_MIN``.
    Prediction only -- it never sees the realized waveform before choosing.
    """
    affordable = _affordable(observable)
    eligible = [a for a in affordable
                if predicted_moments(a, observable.lag_estimate_s)[0]
                >= S_II_MIN]
    if not eligible:
        return PASSIVE
    return min(eligible, key=lambda a: abs(
        predicted_moments(a, observable.lag_estimate_s)[1]))


def p3_shaped(observable: Observable) -> Action:
    """Cheapest action that still clears the excitation floor."""
    affordable = _affordable(observable)
    eligible = [a for a in affordable
                if predicted_moments(a, observable.lag_estimate_s)[0]
                >= S_II_MIN]
    if not eligible:
        return PASSIVE
    return min(eligible, key=lambda a: (a.energy_as, a.name))


def p4_feedback(observable: Observable) -> Action:
    """Best predicted excitation per unit of charge moved.

    The prior phase's feedback arm corrected current within a window. Inside a
    fixed action space there is nothing to correct mid-flight, so what carries
    over is its objective: information per unit cost rather than information
    at any cost. The name is kept for continuity with the prior results and
    this paragraph is the mapping.
    """
    affordable = [a for a in _affordable(observable) if a.energy_as > 0]
    if not affordable:
        return PASSIVE
    return max(affordable, key=lambda a: (
        predicted_moments(a, observable.lag_estimate_s)[0] / a.energy_as,
        a.name))


def p5_random_safe(observable: Observable) -> Action:
    """A deterministic pseudo-random admissible pick.

    Deterministic in the observable state, so it is reproducible and carries
    no hidden randomness that could be tuned. It is a control for "does any
    admissible excitation do as well as a designed one".
    """
    affordable = _affordable(observable)
    if not affordable:
        return PASSIVE
    key = hashlib.sha256(
        repr(sorted(observable.to_dict().items())).encode()).digest()
    return affordable[int.from_bytes(key[:4], "big") % len(affordable)]


def p6_mission(observable: Observable) -> Action:
    """An ordinary slow manoeuvre, not designed for diagnosis.

    A sustained hold: the mission-like action whose current correlates with
    time, which is what made the prior phase's mission arm never resolve.
    """
    for name in ("hold_4A_12s", "hold_4A_8s", "hold_4A_4s"):
        try:
            candidate = by_name(name)
        except KeyError:
            continue
        if candidate in _affordable(observable):
            return candidate
    return PASSIVE


DEPLOYABLE: Dict[str, Callable[[Observable], Action]] = {
    "P0_passive": p0_passive, "P1_palindromic": p1_palindromic,
    "P2_compensated": p2_compensated, "P3_shaped": p3_shaped,
    "P4_feedback": p4_feedback, "P5_random_safe": p5_random_safe,
    "P6_mission": p6_mission,
}


# --- S0 to S3 -------------------------------------------------------------

#: Thresholds for S2. Declared and frozen before any selector comparison.
DRIFT_ELEVATED_V_PER_S = 1.0e-3
LAG_UNCERTAINTY_LIMIT = 0.5      # fraction of the lag estimate
MIN_USEFUL_ENERGY_AS = 10.0


def s0_always_p2(observable: Observable):
    return p2_compensated(observable)


def s1_always_p4(observable: Observable):
    return p4_feedback(observable)


def s2_threshold(observable: Observable):
    """Preregistered threshold rule over observable nuisance estimates.

    The prior locked result says P2 is strongest nominally and collapses under
    elevated drift, while P4 holds. This rule encodes that and nothing else,
    and it is allowed to decline.
    """
    if observable.remaining_energy_as < MIN_USEFUL_ENERGY_AS:
        return NO_SAFE_INFORMATIVE_ACTION
    if observable.clip_margin_a < 4.0:
        return NO_SAFE_INFORMATIVE_ACTION
    if observable.lag_estimate_s <= 0:
        return INSUFFICIENT_NUISANCE_KNOWLEDGE
    relative_lag_uncertainty = (observable.lag_uncertainty_s
                                / observable.lag_estimate_s)
    if relative_lag_uncertainty > LAG_UNCERTAINTY_LIMIT:
        return INSUFFICIENT_NUISANCE_KNOWLEDGE
    if observable.mission_phase == "landing":
        return WAIT_FOR_MISSION_EVIDENCE
    drift_upper = (abs(observable.drift_estimate_v_per_s)
                   + observable.drift_uncertainty_v_per_s)
    if drift_upper > DRIFT_ELEVATED_V_PER_S:
        return p4_feedback(observable)
    return p2_compensated(observable)


def s3_minimax(observable: Observable, *,
               nuisance_grid: Optional[Sequence[float]] = None):
    """Choose the action whose worst predicted margin over the lag interval is best.

    ``Theta_current`` is the declared lag interval implied by the online
    estimate and its uncertainty. The predicted margin is a declared
    construction from predicted moments -- not an outcome, not a certificate,
    and not anything Layer B computed.

    It may return any of the three abstentions, and it is never forced to pick
    between P2 and P4.
    """
    if observable.remaining_energy_as < MIN_USEFUL_ENERGY_AS:
        return NO_SAFE_INFORMATIVE_ACTION
    if observable.lag_estimate_s <= 0:
        return INSUFFICIENT_NUISANCE_KNOWLEDGE
    if observable.mission_phase == "landing":
        return WAIT_FOR_MISSION_EVIDENCE

    if nuisance_grid is None:
        low = max(observable.lag_estimate_s - observable.lag_uncertainty_s,
                  1e-3)
        high = observable.lag_estimate_s + observable.lag_uncertainty_s
        nuisance_grid = np.linspace(low, high, 5)

    candidates = [p2_compensated(observable), p4_feedback(observable)]
    candidates = [a for a in candidates if a is not PASSIVE]
    if not candidates:
        return NO_SAFE_INFORMATIVE_ACTION

    def worst_margin(action: Action) -> float:
        worst = math.inf
        for lag in nuisance_grid:
            s_ii, lever = predicted_moments(action, float(lag))
            # A declared score: excitation above the floor, penalised by the
            # drift leverage it will hand a slow open-circuit change.
            margin = (s_ii / S_II_MIN) - abs(lever) * 100.0
            worst = min(worst, margin)
        return worst

    best = max(candidates, key=worst_margin)
    if worst_margin(best) <= 0.0:
        return NO_SAFE_INFORMATIVE_ACTION
    return best


SELECTORS: Dict[str, Callable] = {
    "S0_always_P2": s0_always_p2, "S1_always_P4": s1_always_p4,
    "S2_threshold": s2_threshold, "S3_minimax": s3_minimax,
}
