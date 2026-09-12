"""Build the eight probe strategies P0-P7 and score them the same way.

EVERY ARM RETURNS A COMMAND CALLABLE AND NOTHING ELSE
------------------------------------------------------
A strategy proposes. The plant realizes. `rcec.certify` judges what was
realized. No strategy here may inspect the realized current of the run it is
being scored on, and P4 -- which does consult realized current -- may only
see the prefix that has already been flown.

P7 IS NOT A STRATEGY
---------------------
It optimizes directly over realized-current trajectories and then reports
what the best achievable realized current WOULD have been. There is no
command that produces it, because the inverse of the loop is not
realizable within the authority bound. It is a CEILING for the other arms
to be compared against and it is labelled `NOT_EXECUTABLE` in every artifact
it appears in. A reader who takes P7 as a result has been warned in three
places.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np

from . import waveform_compensation as WC
from .moment_feedback import MomentFeedbackProbe

ARMS = ("P0_passive", "P1_palindromic", "P2_compensated", "P3_shaped",
        "P4_feedback", "P5_random_safe", "P6_mission", "P7_oracle")
NOT_EXECUTABLE = ("P7_oracle",)


def window_times(start: float, duration: float, hz: float) -> np.ndarray:
    n = max(int(round(duration * hz)), 8)
    return start + np.arange(n, dtype=float) / hz


def palindromic(t, start, duration, amplitude, cycles=3) -> np.ndarray:
    """A whole-cycle cosine, symmetric about the window midpoint.

    Zero commanded `S_tI` by construction. AE-F5 measured that this does NOT
    make the realized current orthogonal, which is the entire premise of
    this campaign.
    """
    mid = start + 0.5 * duration
    return amplitude * np.cos(2.0 * math.pi * cycles * (t - mid) / duration)


def triangle(t, start, duration, amplitude) -> np.ndarray:
    u = (t - start) / duration
    return amplitude * (1.0 - 4.0 * np.abs(u - 0.5))


def chirp(t, start, duration, amplitude, f0=0.3, f1=1.5) -> np.ndarray:
    u = (t - start) / duration
    phase = 2.0 * math.pi * duration * (f0 * u + 0.5 * (f1 - f0) * u * u)
    mid = 0.5 * (phase[0] + phase[-1])
    return amplitude * np.cos(phase - mid)


SHAPES = {"palindromic": palindromic, "triangle": triangle, "chirp": chirp}


@dataclass(frozen=True)
class Proposal:
    arm: str
    command: Callable[[float], float]
    samples: Optional[np.ndarray]
    duration_s: float
    nominal_energy_as: float
    detail: dict
    executable: bool = True


def _energy(samples, hz) -> float:
    if samples is None:
        return 0.0
    return float(np.sum(np.abs(samples)) / hz)


def p0_passive(**_) -> Proposal:
    return Proposal("P0_passive", lambda t: 0.0, None, 0.0, 0.0,
                    {"note": "no added excitation; the known "
                             "non-identifiable baseline"})


def p1_palindromic(*, start, duration, amplitude, hz, **_) -> Proposal:
    t = window_times(start, duration, hz)
    w = palindromic(t, start, duration, amplitude)
    return Proposal("P1_palindromic", WC.as_callable(w, t), w, duration,
                    _energy(w, hz),
                    {"commanded_lever_is_zero_by_construction": True})


def p2_compensated(*, start, duration, amplitude, hz, lag, authority_a,
                   **_) -> Proposal:
    t = window_times(start, duration, hz)
    w = palindromic(t, start, duration, amplitude)
    u, report = WC.compensate(w, t, lag, authority_a=authority_a)
    return Proposal("P2_compensated", WC.as_callable(u, t), u, duration,
                    _energy(u, hz), report)


def p3_shaped(*, start, duration, hz, plant, budget_eval, candidates,
              **_) -> Proposal:
    """Search a bounded parameterisation on DEVELOPMENT seeds only.

    `budget_eval` scores a candidate by SIMULATING its realized current and
    returning the objective. The search never sees a locked seed, and the
    chosen candidate is then flown unchanged.
    """
    best, best_score = None, float("inf")
    for cand in candidates:
        score = budget_eval(cand)
        if score < best_score:
            best, best_score = cand, score
    t = window_times(start, best["duration"], hz)
    w = SHAPES[best["shape"]](t, start, best["duration"], best["amplitude"]) \
        if best["shape"] != "palindromic" else \
        palindromic(t, start, best["duration"], best["amplitude"],
                    best.get("cycles", 3))
    return Proposal("P3_shaped", WC.as_callable(w, t), w, best["duration"],
                    _energy(w, hz),
                    {"chosen": best, "objective": best_score,
                     "candidates_evaluated": len(candidates),
                     "searched_on": "development seeds only"})


def p4_feedback(*, start, duration, amplitude, hz, authority_a,
                **_) -> Tuple[Proposal, MomentFeedbackProbe]:
    t = window_times(start, duration, hz)
    base_samples = palindromic(t, start, duration, amplitude)
    base = WC.as_callable(base_samples, t)
    probe = MomentFeedbackProbe(base=base, start_s=start,
                                duration_s=duration,
                                authority_a=authority_a)
    return Proposal("P4_feedback", probe.demand, base_samples, duration,
                    _energy(base_samples, hz),
                    {"online": True,
                     "sees_only_the_executed_prefix": True}), probe


def p5_random_safe(*, start, duration, amplitude, hz, seed, **_) -> Proposal:
    rng = np.random.default_rng(seed)
    t = window_times(start, duration, hz)
    shape = rng.choice(sorted(SHAPES))
    amp = amplitude * float(rng.uniform(0.6, 1.0))
    w = SHAPES[shape](t, start, duration, amp)
    return Proposal("P5_random_safe", WC.as_callable(w, t), w, duration,
                    _energy(w, hz),
                    {"shape": str(shape), "amplitude": amp, "seed": seed})


def p6_mission(*, start, duration, hz, mission_amplitude=4.0,
               mission_hz=0.1, **_) -> Proposal:
    """A manoeuvre the vehicle flies anyway. ZERO incremental energy.

    Charging this arm for energy it did not cause would rig the comparison
    in favour of probing, which is the falsifier the preregistration cares
    most about.
    """
    def fn(t):
        if t < start:
            return 0.0
        return mission_amplitude * math.sin(2.0 * math.pi * mission_hz
                                            * (t - start))
    return Proposal("P6_mission", fn, None, duration, 0.0,
                    {"incremental_energy_is_zero_by_definition": True,
                     "mission_amplitude_a": mission_amplitude,
                     "mission_hz": mission_hz})


def p7_oracle(*, start, duration, hz, amplitude, **_) -> Proposal:
    """The best REALIZED current an ideal actuator could deliver. NOT FLYABLE.

    A square-wave realized current maximises `S_II` for a bounded amplitude
    and, taken symmetric about the midpoint, has zero `S_tI`. No command
    produces it through a first-order lag with bounded authority, so this is
    a ceiling and never a proposal.
    """
    t = window_times(start, duration, hz)
    mid = start + 0.5 * duration
    w = amplitude * np.where(np.abs(t - mid) < 0.25 * duration, 1.0, -1.0)
    return Proposal("P7_oracle", WC.as_callable(w, t), w, duration,
                    _energy(w, hz),
                    {"NOT_EXECUTABLE": True,
                     "why": ("this is a realized-current trajectory, not a "
                             "command; inverting a first-order lag to "
                             "produce a square current needs unbounded "
                             "authority at each edge")},
                    executable=False)
