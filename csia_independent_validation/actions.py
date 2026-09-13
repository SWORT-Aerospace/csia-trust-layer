"""The finite action space every strategy and every ceiling chooses from.

Having one enumerable action space is what makes a ceiling meaningful. If the
oracle searched a richer space than the deployable strategies, beating it would
be impossible for uninteresting reasons; if it searched a poorer one, a
deployable strategy could beat it and the "ceiling" would be a mislabel. Both
failures are ruled out by construction here: P7b searches exactly this set,
exhaustively, and every deployable strategy returns one element of it.

Nothing in this module knows anything about faults, plants or truth. An action
is a commanded waveform and its cost, and that is all.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

SCHEMA = "csia.independent_validation.actions/1"

#: Hard constraints. These are declared limits, not measurements, and they
#: apply identically to every strategy and every ceiling.
PEAK_EXCESS_LIMIT_A = 16.0     # A, on top of a 20 A hover draw
ENERGY_LIMIT_AS = 80.0         # A.s of extra charge moved
MAX_DURATION_S = 12.0          # s
LOOP_HZ = 50.0


def _cosine(cycles: int) -> Callable[[float], float]:
    def shape(u: float) -> float:
        return math.cos(2.0 * math.pi * cycles * u)
    return shape


def _triangle(u: float) -> float:
    """Symmetric triangle, +1 at the ends and -1 at the middle."""
    return 1.0 - 4.0 * min(u, 1.0 - u)


def _doublet(u: float) -> float:
    """Up then down. Antisymmetric about the midpoint."""
    return 1.0 if u < 0.5 else -1.0


def _hold(u: float) -> float:
    """A constant offset for the whole window."""
    return 1.0


def _zero(u: float) -> float:
    return 0.0


SHAPES: Dict[str, Callable[[float], float]] = {
    "cosine1": _cosine(1), "cosine2": _cosine(2),
    "cosine3": _cosine(3), "cosine6": _cosine(6),
    "triangle": _triangle, "doublet": _doublet, "hold": _hold,
}

AMPLITUDES_A: Tuple[float, ...] = (4.0, 7.0, 10.0, 14.0)
DURATIONS_S: Tuple[float, ...] = (4.0, 8.0, 12.0)


@dataclass(frozen=True)
class Action:
    """One commanded excitation, with the cost it will incur.

    ``energy_as`` is the integral of the absolute excess current: the extra
    charge the pack actually moves. It is arithmetic on a commanded waveform,
    not a battery measurement.
    """

    name: str
    shape_name: str
    amplitude_a: float
    duration_s: float

    def command(self) -> Callable[[float], float]:
        shape = SHAPES.get(self.shape_name, _zero)
        amplitude = self.amplitude_a
        duration = self.duration_s

        def fn(t: float) -> float:
            if t < 0.0 or t > duration:
                return 0.0
            return amplitude * shape(t / duration if duration > 0 else 0.0)

        return fn

    @property
    def peak_excess_a(self) -> float:
        command = self.command()
        n = max(int(round(self.duration_s * LOOP_HZ)), 2)
        return max(abs(command(k / LOOP_HZ)) for k in range(n + 1))

    @property
    def energy_as(self) -> float:
        command = self.command()
        n = max(int(round(self.duration_s * LOOP_HZ)), 2)
        return sum(abs(command(k / LOOP_HZ)) for k in range(n)) / LOOP_HZ

    @property
    def is_admissible(self) -> bool:
        return (self.peak_excess_a <= PEAK_EXCESS_LIMIT_A + 1e-9
                and self.energy_as <= ENERGY_LIMIT_AS + 1e-9
                and self.duration_s <= MAX_DURATION_S + 1e-9)

    def digest(self) -> str:
        """Identity of the proposed waveform, for staleness checking."""
        payload = f"{self.shape_name}|{self.amplitude_a}|{self.duration_s}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return {"name": self.name, "shape": self.shape_name,
                "amplitude_a": self.amplitude_a,
                "duration_s": self.duration_s,
                "peak_excess_a": self.peak_excess_a,
                "energy_as": self.energy_as,
                "digest": self.digest()}


PASSIVE = Action(name="passive", shape_name="zero", amplitude_a=0.0,
                 duration_s=8.0)


def _build() -> Tuple[Action, ...]:
    actions: List[Action] = [PASSIVE]
    for shape_name in SHAPES:
        for amplitude in AMPLITUDES_A:
            for duration in DURATIONS_S:
                candidate = Action(
                    name=f"{shape_name}_{amplitude:g}A_{duration:g}s",
                    shape_name=shape_name, amplitude_a=amplitude,
                    duration_s=duration)
                if candidate.is_admissible:
                    actions.append(candidate)
    return tuple(actions)


#: Every action any strategy or ceiling in this phase may take. Frozen.
ACTION_SPACE: Tuple[Action, ...] = _build()

#: Actions grouped by the cost class they belong to, for matched-cost
#: comparison. A comparison across classes is a Pareto question, not a
#: like-for-like one, and the runner is required to say which it is doing.
def energy_class(action: Action) -> str:
    energy = action.energy_as
    if energy <= 1e-9:
        return "none"
    if energy < 25.0:
        return "low"
    if energy < 50.0:
        return "medium"
    return "high"


def matched(reference: Action) -> Tuple[Action, ...]:
    """Admissible actions in the same energy class and duration."""
    target = energy_class(reference)
    return tuple(a for a in ACTION_SPACE
                 if energy_class(a) == target
                 and abs(a.duration_s - reference.duration_s) < 1e-9)


def by_name(name: str) -> Action:
    for action in ACTION_SPACE:
        if action.name == name:
            return action
    raise KeyError(f"no action named {name!r}")
