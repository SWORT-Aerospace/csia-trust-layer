"""Non-deployable reference strategies, and the taxonomy the prior phase got wrong.

The prior campaign carried an arm called ``P7_oracle``. It was not an oracle.
Its objective was to maximise the realized second moment of current, which is
not the same thing as maximising diagnosis quality, and on the locked data it
never issued a single certificate anywhere on the magnitude grid -- worse than
every deployable arm despite the highest excitation
(``COUNTEREXAMPLE_LOG.md`` IV-2). Calling it an oracle made every comparison
against it meaningless in the flattering direction.

It is preserved here under an honest name and joined by two objects that are
actually ceilings:

``P7a`` -- maximum-current-second-moment benchmark
    Maximises realized ``S_II`` subject to the hard action and safety
    constraints. Uses no truth. It is a **benchmark**, never an oracle, and
    nothing in this package may call it one.

``P7b`` -- hindsight outcome oracle
    May use true plant parameters, the realized fault, and the complete future
    trajectory. Exhaustively evaluates the whole action space and returns the
    action minimising the independent outcome loss, under exactly the
    constraints every deployable strategy faces. Evaluation only.

``P7c`` -- robust model-envelope oracle
    Does not use the realized fault label. Minimises the worst-case outcome
    loss over the declared plant and magnitude envelope. Non-deployable
    because the enumeration it performs is not available online.

THE CEILING INVARIANT
---------------------
No deployable strategy may outperform ``P7b`` on ``P7b``'s exact objective,
action space, plant instance and constraints, beyond numerical tolerance.
Because ``P7b`` is an exhaustive argmin over the same finite action space that
every deployable strategy draws from, this holds by construction -- which is
the point. The invariant is not there to be interesting when it passes; it is
there to fail loudly when the enumeration, the caching or the random-number
alignment has a bug. If it ever fails, the oracle implementation is invalid and
the phase stops. The deployable strategy does not get relabelled
super-oracular.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from . import evaluator as ev
from .actions import ACTION_SPACE, Action
from .plants import Observation, simulate
from .truth import GroundTruth, TruthPair

LAYER = "B"
TRUTH_BEARING = True
SCHEMA = "csia.independent_validation.ceilings/1"

#: Numerical slack when comparing two losses. Tighter than any real effect in
#: this experiment and looser than floating-point noise on a 600-sample fit.
CEILING_TOLERANCE = 1e-12


@dataclass(frozen=True)
class ActionOutcome:
    """What one action achieved on one plant instance. Layer B only."""

    action: str
    plant: str
    seed: int
    delta: float
    e_delta_r: float
    ae_r: float
    m_r_out: float
    resolved: bool
    s_ii: float
    energy_as: float

    def loss(self, kind: str) -> float:
        if kind == "change":
            return abs(self.e_delta_r)
        if kind == "point":
            return self.ae_r
        raise ValueError(f"unknown loss {kind!r}; have 'change' or 'point'")


def _estimate(observation: Observation) -> float:
    """Ordinary least squares on ``[1, -I]``, written here rather than imported.

    Layer B does not import the certificate. This is the same textbook
    estimator, implemented independently, so that a defect in one is not
    silently shared with the other.
    """
    valid = observation.valid
    current = np.asarray(observation.i_meas, dtype=float)[valid]
    voltage = np.asarray(observation.v_meas, dtype=float)[valid]
    design = np.column_stack([np.ones_like(current), -current])
    solution, *_ = np.linalg.lstsq(design, voltage, rcond=None)
    return float(solution[1])


def _second_moment(observation: Observation) -> float:
    current = np.asarray(observation.i_meas, dtype=float)[observation.valid]
    if current.size < 2:
        return 0.0
    return float(np.sum((current - current.mean()) ** 2))


@dataclass(frozen=True)
class Conditions:
    """Everything about a trial except the action, the plant and the fault.

    An arena carries one set of conditions. Two arenas with different drift or
    different sensing are different experiments, and keeping them in separate
    objects is what stops a ceiling being computed under nominal conditions and
    then compared against deployable arms that ran under elevated drift -- a
    mistake the first version of the runner made.
    """

    drift_v_per_s: float = 0.0
    ringing_amplitude_v: float = 0.0
    sensing: Optional[object] = None

    def to_dict(self) -> Dict:
        return {"drift_v_per_s": self.drift_v_per_s,
                "ringing_amplitude_v": self.ringing_amplitude_v,
                "sensing": (None if self.sensing is None
                            else self.sensing.to_dict())}


class Arena:
    """Runs actions against plants and caches what does not depend on the fault.

    The nominal half of a matched pair does not depend on the injected change,
    so it is computed once per (action, plant, seed). Without the cache an
    exhaustive oracle over 72 actions is six times more expensive than it needs
    to be; with it, the nominal estimate is also guaranteed to be *the same
    estimate* for every magnitude, which is what makes the paired comparison
    honest.

    **Traces are not cached.** An earlier version kept the full observation and
    ground truth for every (action, plant, seed), which at campaign scale is
    hundreds of megabytes of arrays nobody reads twice. Only the scalars the
    comparison needs are kept, and a caller that wants a trace asks for a fresh
    simulation.
    """

    def __init__(self, duration_default: float = 8.0,
                 conditions: Optional[Conditions] = None) -> None:
        self._nominal: Dict[Tuple[str, str, int], Tuple] = {}
        self._outcomes: Dict[Tuple[str, str, int, float], ActionOutcome] = {}
        self._duration_default = duration_default
        self.conditions = conditions or Conditions()
        self._simulations = 0

    @property
    def simulations(self) -> int:
        """How many plant runs this arena has actually performed."""
        return self._simulations

    def simulate_one(self, action: Action, plant: str, seed: int,
                     delta: float) -> Tuple[Observation, GroundTruth]:
        """One plant run under this arena's conditions. Never cached."""
        duration = action.duration_s or self._duration_default
        self._simulations += 1
        return simulate(
            action.command(), plant=plant, duration=duration, seed=seed,
            sensing=self.conditions.sensing, r0_delta=delta,
            drift_v_per_s=self.conditions.drift_v_per_s,
            ringing_amplitude_v=self.conditions.ringing_amplitude_v)

    def nominal(self, action: Action, plant: str, seed: int
                ) -> Tuple[GroundTruth, float, float]:
        """``(truth, r_hat_nominal, S_II)``. The truth carries no traces."""
        key = (action.name, plant, seed)
        if key not in self._nominal:
            observation, truth = self.simulate_one(action, plant, seed, 0.0)
            light = replace(truth, i_true=(), v_true=(), v1_true=())
            self._nominal[key] = (light, _estimate(observation),
                                  _second_moment(observation))
        return self._nominal[key]

    def run(self, action: Action, plant: str, seed: int,
            delta: float) -> ActionOutcome:
        """One matched pair. Deterministic in its arguments, so cached.

        An exhaustive oracle asks for the same cell many times over -- once
        per magnitude when checking the invariant, and again for every
        magnitude in the envelope when P7c takes its minimax. Recomputing is
        not merely slow, it is an invitation to a subtle difference between
        two evaluations of what is supposed to be the same trial.
        """
        key = (action.name, plant, seed, delta)
        cached = self._outcomes.get(key)
        if cached is not None:
            return cached
        nominal_truth, r_nominal, s_ii = self.nominal(action, plant, seed)
        fault_observation, fault_truth = self.simulate_one(
            action, plant, seed, delta)
        fault_truth = replace(fault_truth, i_true=(), v_true=(), v1_true=())
        r_fault = _estimate(fault_observation)
        pair = TruthPair(nominal=nominal_truth, fault=fault_truth)
        change = ev.evaluate_change(r_nominal, r_fault, pair)
        point = ev.evaluate_point(r_fault, fault_truth)
        outcome = ActionOutcome(
            action=action.name, plant=plant, seed=seed, delta=delta,
            e_delta_r=change.e_delta_r, ae_r=point.ae_r,
            m_r_out=change.m_r_out, resolved=change.resolved,
            s_ii=_second_moment(fault_observation),
            energy_as=action.energy_as)
        self._outcomes[key] = outcome
        return outcome


def candidates(constraint: Optional[Callable[[Action], bool]] = None
               ) -> Tuple[Action, ...]:
    """The admissible action set. One set for strategies and ceilings alike."""
    space = tuple(a for a in ACTION_SPACE if a.is_admissible)
    if constraint is None:
        return space
    return tuple(a for a in space if constraint(a))


def p7a_select(arena: Arena, plant: str, seed: int, *,
               constraint: Optional[Callable[[Action], bool]] = None
               ) -> Action:
    """Maximum realized second moment of current. A BENCHMARK, not an oracle.

    Uses no truth: ``S_II`` is computed from the measured current of the
    nominal run. The prior phase's evidence is that this objective is not
    equivalent to diagnosis quality, and that is exactly why it is kept.
    """
    space = candidates(constraint)
    return max(space, key=lambda a: arena.nominal(a, plant, seed)[2])


def p7b_select(arena: Arena, plant: str, seed: int, delta: float, *,
               loss: str = "change",
               constraint: Optional[Callable[[Action], bool]] = None
               ) -> Tuple[Action, ActionOutcome]:
    """Hindsight outcome oracle. Exhaustive argmin over the same action space.

    Non-deployable: it evaluates the realized fault it is supposed to be
    diagnosing. Nothing here may be handed to a deployable selector, and the
    architectural tests enforce that Layer A cannot reach this module.
    """
    space = candidates(constraint)
    outcomes = [arena.run(a, plant, seed, delta) for a in space]
    best = min(outcomes, key=lambda o: o.loss(loss))
    return next(a for a in space if a.name == best.action), best


def p7c_select(arena: Arena, seed: int, *, plants_in_envelope: Sequence[str],
               magnitudes: Sequence[float], loss: str = "change",
               constraint: Optional[Callable[[Action], bool]] = None
               ) -> Tuple[Action, float]:
    """Robust model-envelope oracle. Minimax over the declared envelope.

    It never sees which fault actually occurred; it sees the declared set of
    plants and magnitudes and picks the action whose worst case over that set
    is smallest. Still non-deployable, because enumerating the envelope is not
    something the vehicle can do online, and the docstring says so rather than
    leaving a reader to assume otherwise.
    """
    space = candidates(constraint)
    best_action = None
    best_worst = math.inf
    for action in space:
        worst = max(arena.run(action, plant, seed, delta).loss(loss)
                    for plant in plants_in_envelope
                    for delta in magnitudes)
        if worst < best_worst:
            best_worst, best_action = worst, action
    assert best_action is not None
    return best_action, best_worst


def ceiling_invariant(arena: Arena, plant: str, seed: int, delta: float, *,
                      deployable: Iterable[Action], loss: str = "change",
                      constraint: Optional[Callable[[Action], bool]] = None
                      ) -> Dict:
    """Check that no deployable action beats P7b on P7b's own objective.

    Returns a report rather than raising, so that a violation is recorded as
    evidence instead of vanishing into a traceback. The caller is required to
    stop the phase when ``holds`` is false.
    """
    oracle_action, oracle_outcome = p7b_select(
        arena, plant, seed, delta, loss=loss, constraint=constraint)
    oracle_loss = oracle_outcome.loss(loss)
    violations: List[Dict] = []
    for action in deployable:
        outcome = arena.run(action, plant, seed, delta)
        if outcome.loss(loss) < oracle_loss - CEILING_TOLERANCE:
            violations.append({
                "action": action.name, "loss": outcome.loss(loss),
                "oracle_loss": oracle_loss,
                "margin": oracle_loss - outcome.loss(loss)})
    return {
        "plant": plant, "seed": seed, "delta": delta, "loss": loss,
        "oracle_action": oracle_action.name, "oracle_loss": oracle_loss,
        "violations": violations, "holds": not violations,
        "tolerance": CEILING_TOLERANCE,
    }


def regret(outcome: ActionOutcome, oracle_loss: float, *,
           loss: str = "change") -> float:
    """How much worse than the ceiling. Never negative when the invariant holds."""
    return outcome.loss(loss) - oracle_loss
