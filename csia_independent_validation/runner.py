"""The campaign runner. Layer C drives it; Layers A and B never meet inside it.

This module is the only place in the phase where a deployable selection and a
ground-truth score occur in the same function, and the separation is kept by
sequence rather than by hope:

1. a strategy is handed an :class:`~.strategies.Observable` and returns an
   action -- it never sees the plant, the magnitude, the seed or the outcome;
2. the plant runs that action and returns an observation and a truth;
3. Layer A certifies from the observation alone;
4. Layer B scores from the truth;
5. the row records both, side by side, and nothing flows backwards.

The design is fixed by ``PREREGISTRATION_AMENDMENT_1.md`` and this module
implements it without adding to it.
"""
from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from csia_active_evidence import polarization as _pz
from csia_active_evidence import rcec as _rcec

from . import ceilings, evaluator as ev, strategies as st
from .actions import Action, PASSIVE, energy_class
from .plants import (SYNTHETIC_LOOP, SYNTHETIC_Q, SYNTHETIC_SENSING, Loop,
                     Sensing, simulate)
from .truth import TruthPair

LAYER = "C"
TRUTH_BEARING = True
SCHEMA = "csia.independent_validation.campaign/1"

PLANTS = ("Q0", "Q1", "Q2")
MAGNITUDES = (0.002, 0.004, 0.006, 0.010, 0.020, 0.040)
DRIFT_STATES = {"nominal": 0.0, "elevated": 2.0e-3}

#: P0-P6 plus the three ceilings plus the four selectors.
ARMS = tuple(st.STRATEGIES) + ("P7a_benchmark", "P7b_oracle",
                                  "P7b_point_oracle", "P7c_robust") \
    + tuple(st.SELECTORS)

DURATION_DEFAULT = 8.0
TRUE_LAG_S = SYNTHETIC_LOOP["lag_s"]


def _budget(target_delta: float) -> _rcec.ErrorBudget:
    """The declared envelope. Every number is an engineering declaration."""
    return _rcec.ErrorBudget(
        r_reference=SYNTHETIC_Q["r0"], target_delta_r=target_delta,
        sigma_v=SYNTHETIC_SENSING["sigma_v"],
        sigma_i=SYNTHETIC_SENSING["sigma_i"], d_max=0.002,
        polarization=_pz.PolarizationEnvelope(
            r1_min=0.004, r1_max=0.020, tau_min_s=1.0, tau_max_s=40.0,
            n_r1=5, n_tau=7),
        scale_error_max=0.02, hysteresis_v_max=0.040)


def observable(*, lag_estimate_s: float = TRUE_LAG_S,
               drift_estimate_v_per_s: float = 0.0,
               mission_phase: str = "hover",
               remaining_energy_as: float = 80.0,
               remaining_time_s: float = 12.0,
               clip_margin_a: float = 16.0,
               lag_uncertainty_s: float = 0.05,
               drift_uncertainty_v_per_s: float = 1.0e-4) -> st.Observable:
    """Build the pre-action state a selector is allowed to condition on."""
    return st.Observable(
        lag_estimate_s=lag_estimate_s, lag_uncertainty_s=lag_uncertainty_s,
        drift_estimate_v_per_s=drift_estimate_v_per_s,
        drift_uncertainty_v_per_s=drift_uncertainty_v_per_s,
        sigma_i_bound_a=SYNTHETIC_SENSING["sigma_i"],
        sigma_v_bound_v=SYNTHETIC_SENSING["sigma_v"],
        remaining_energy_as=remaining_energy_as,
        remaining_time_s=remaining_time_s, mission_phase=mission_phase,
        clip_margin_a=clip_margin_a)


@dataclass(frozen=True)
class Cell:
    """One experimental condition. No arm, no outcome."""

    plant: str
    drift_state: str
    magnitude: float
    seed: int
    lag_ratio: float = 1.0
    ringing_v: float = 0.0
    sensing: Optional[Sensing] = None
    execution: str = "full"      # "full", "clipped", "aborted"

    @property
    def drift_v_per_s(self) -> float:
        return DRIFT_STATES[self.drift_state]


class Campaign:
    """Runs cells, one arena per set of experimental conditions.

    The first version of this held a single arena for the whole campaign, so
    every ceiling was computed under nominal drift and no ringing whatever the
    cell said. Under elevated drift that silently compared deployable arms
    running in one world against an oracle solving a different one, and the
    ceiling invariant would have been meaningless exactly where it mattered
    most. Conditions now key the arena.
    """

    def __init__(self) -> None:
        self._arenas: Dict[Tuple, ceilings.Arena] = {}
        self._nominal: Dict[Tuple, Tuple] = {}
        self.plant_runs = 0

    # -- plant access -----------------------------------------------------

    def _sensing(self, cell: Cell) -> Sensing:
        return cell.sensing or Sensing(**SYNTHETIC_SENSING)

    def arena(self, cell: Cell) -> ceilings.Arena:
        """The arena for this cell's conditions. One per distinct world."""
        sensing = self._sensing(cell)
        key = (cell.drift_state, cell.ringing_v,
               tuple(sorted(sensing.to_dict().items())))
        if key not in self._arenas:
            self._arenas[key] = ceilings.Arena(
                duration_default=DURATION_DEFAULT,
                conditions=ceilings.Conditions(
                    drift_v_per_s=cell.drift_v_per_s,
                    ringing_amplitude_v=cell.ringing_v, sensing=sensing))
        return self._arenas[key]

    @property
    def simulations(self) -> int:
        return self.plant_runs + sum(a.simulations
                                     for a in self._arenas.values())

    def _run(self, action: Action, cell: Cell, *, magnitude: float
             ) -> Tuple:
        self.plant_runs += 1
        duration = action.duration_s or DURATION_DEFAULT
        return simulate(
            action.command(), plant=cell.plant, duration=duration,
            seed=cell.seed, sensing=self._sensing(cell),
            r0_delta=magnitude, drift_v_per_s=cell.drift_v_per_s,
            ringing_amplitude_v=cell.ringing_v)

    def _nominal_summary(self, action: Action, cell: Cell) -> Tuple:
        """``(r_hat_nominal, trace-free truth)``, cached.

        The nominal half of a matched pair depends on the action, the plant,
        the conditions and the seed -- never on the magnitude -- and
        :func:`simulate` is deterministic in exactly those. Only the two
        scalars the comparison needs are kept, so the cache costs nothing in
        memory, and a test asserts the cached answer equals a fresh one.
        """
        sensing = self._sensing(cell)
        key = (action.name, cell.plant, cell.drift_state, cell.seed,
               cell.ringing_v, tuple(sorted(sensing.to_dict().items())))
        if key not in self._nominal:
            observation, truth = self._run(action, cell, magnitude=0.0)
            _, current, voltage = observation.kept()
            self._nominal[key] = (
                _rcec.estimate_resistance(current, voltage),
                replace(truth, i_true=(), v_true=(), v1_true=()))
        return self._nominal[key]

    # -- arms --------------------------------------------------------------

    def choose(self, arm: str, cell: Cell, state: st.Observable):
        """What this arm proposes. Ceilings get truth; nothing else does."""
        if arm in st.DEPLOYABLE:
            return st.DEPLOYABLE[arm](state)
        if arm in st.SELECTORS:
            return st.SELECTORS[arm](state)
        arena = self.arena(cell)
        if arm == "P7a_benchmark":
            return ceilings.p7a_select(arena, cell.plant, cell.seed)
        if arm == "P7b_oracle":
            action, _ = ceilings.p7b_select(
                arena, cell.plant, cell.seed, cell.magnitude, loss="change")
            return action
        if arm == "P7b_point_oracle":
            # Same exhaustive hindsight argmin, same action space, different
            # loss. Added by PREREGISTRATION_AMENDMENT_2.md because the
            # change loss turned out to be saturated: a ceiling on a metric
            # that cannot tell thirteen arms apart is valid and useless.
            action, _ = ceilings.p7b_select(
                arena, cell.plant, cell.seed, cell.magnitude, loss="point")
            return action
        if arm == "P7c_robust":
            action, _ = ceilings.p7c_select(
                arena, cell.seed, plants_in_envelope=PLANTS,
                magnitudes=MAGNITUDES, loss="change")
            return action
        raise KeyError(f"unknown arm {arm!r}")

    # -- one row -----------------------------------------------------------

    def row(self, arm: str, cell: Cell) -> Dict:
        state = observable(
            lag_estimate_s=TRUE_LAG_S * cell.lag_ratio,
            drift_estimate_v_per_s=cell.drift_v_per_s)
        proposal = self.choose(arm, cell, state)

        if isinstance(proposal, str):
            return {
                "arm": arm, "plant": cell.plant,
                "drift_state": cell.drift_state, "magnitude": cell.magnitude,
                "seed": cell.seed, "lag_ratio": cell.lag_ratio,
                "ringing_v": cell.ringing_v, "execution": cell.execution,
                "action": None, "abstention": proposal,
                "energy_as": 0.0, "energy_class": "none",
                "duration_s": 0.0, "state": None, "m_r_cert": None,
                "e_delta_r": None, "m_r_out": None, "resolved": False,
                "ae_r": None, "deployable": arm not in (
                    "P7a_benchmark", "P7b_oracle", "P7c_robust"),
            }

        r_nominal, nominal_truth = self._nominal_summary(proposal, cell)
        fault_obs, fault_truth = self._run(proposal, cell,
                                           magnitude=cell.magnitude)
        fault_t, fault_i, fault_v = fault_obs.kept()

        if cell.execution == "aborted":
            keep = max(int(fault_t.size * 0.25), 4)
            fault_t, fault_i, fault_v = (fault_t[:keep], fault_i[:keep],
                                         fault_v[:keep])

        proposed = proposal.digest()
        authorized = proposed if cell.execution != "clipped" else "CLIPPED"
        execution = _rcec.Execution(
            proposed_digest=proposed, authorized_digest=authorized,
            # A clipped action still ran to the end of its window; what
            # changed is the waveform the authority allowed. Only an abort is
            # incomplete. Marking a clipped run incomplete made the
            # certificate answer ABORTED_INCOMPLETE and the clipping path was
            # never exercised at all.
            completed=cell.execution != "aborted",
            saturated_fraction=float(fault_obs.saturated.mean()),
            aborted_at_s=(float(fault_t[-1])
                          if cell.execution == "aborted" else None))

        certificate = _rcec.certify(
            fault_t, fault_i, fault_v, _budget(cell.magnitude),
            execution=execution)

        r_fault = _rcec.estimate_resistance(fault_i, fault_v)
        change = ev.evaluate_change(
            r_nominal, r_fault,
            TruthPair(nominal=nominal_truth,
                      fault=replace(fault_truth, i_true=(), v_true=(),
                                    v1_true=())))
        point = ev.evaluate_point(r_fault, fault_truth)

        return {
            "arm": arm, "plant": cell.plant, "drift_state": cell.drift_state,
            "magnitude": cell.magnitude, "seed": cell.seed,
            "lag_ratio": cell.lag_ratio, "ringing_v": cell.ringing_v,
            "execution": cell.execution, "action": proposal.name,
            "abstention": None,
            "energy_as": proposal.energy_as,
            "energy_class": energy_class(proposal),
            "duration_s": proposal.duration_s or DURATION_DEFAULT,
            "state": certificate.state,
            "m_r_cert": certificate.resolution.get("margin"),
            "e_delta_r": change.e_delta_r, "m_r_out": change.m_r_out,
            "resolved": change.resolved, "ae_r": point.ae_r,
            "deployable": arm not in ("P7a_benchmark", "P7b_oracle",
                                      "P7b_point_oracle", "P7c_robust"),
        }


# --- reductions -----------------------------------------------------------

def resolution_area(rows: Sequence[Dict], *, metric: str = "change") -> float:
    """``A_s`` over the frozen magnitude grid, for one slice of rows."""
    by_magnitude: Dict[float, List[bool]] = {}
    for row in rows:
        by_magnitude.setdefault(row["magnitude"], []).append(
            _resolved(row, metric))
    if not by_magnitude:
        return float("nan")
    return ev.grid_resolution_area(
        {magnitude: sum(flags) / len(flags)
         for magnitude, flags in by_magnitude.items()})


def _resolved(row: Dict, metric: str) -> bool:
    if metric == "change":
        return bool(row["resolved"])
    if metric == "point":
        if row["ae_r"] is None:
            return False
        return row["ae_r"] < ev.TAU_R_RELATIVE * row["magnitude"]
    raise ValueError(f"unknown metric {metric!r}")


def frontier(rows: Sequence[Dict], *, metric: str = "change"):
    """Censored frontier. Returns a magnitude or the string ``> 0.04``."""
    by_magnitude: Dict[float, List[bool]] = {}
    for row in rows:
        by_magnitude.setdefault(row["magnitude"], []).append(
            _resolved(row, metric))
    return ev.censored_frontier(
        {magnitude: sum(flags) / len(flags)
         for magnitude, flags in by_magnitude.items()})


def slice_rows(rows: Iterable[Dict], **conditions) -> List[Dict]:
    return [r for r in rows
            if all(r.get(key) == value for key, value in conditions.items())]
