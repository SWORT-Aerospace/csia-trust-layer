"""The difficulty ladder and the factorial design. SPECIFICATION ONLY.

WHY THE OLD METRIC HAD TO GO
------------------------------
Measured on the committed campaign, separation fraction by target change:
every arm scores 0.00 at 0.005 ohm and 1.00 at 0.020 and 0.040. **Exactly one
of four grid points discriminates**, and it splits seven strategies into two
groups. Every difference MX-039 reported between arms rests on that single
point.

A binary outcome cannot express how close an arm came. Two strategies that
miss by a factor of two and by a factor of a hundred score identically, and
so do two that succeed with five per cent and ninety-five per cent margin.

THE REPLACEMENT IS CONTINUOUS AND SIGNED
------------------------------------------
    M_R = |delta_R_target| - (|B_total| + U_R)

    M_R > 0   resolvable inside the stated model
    M_R = 0   boundary
    M_R < 0   insufficient evidence

It is reported in ohms, it never saturates, and its sign carries the verdict
the binary metric used to carry. **The binary metric is retained** and
reported beside it, because MX-039's numbers are published against it and an
audit has to be able to reproduce them.

THE LADDER IS PLACED WHERE THE ANSWER CHANGES
-----------------------------------------------
Sixteen factors, each with an easy, nominal and hard level. Evaluation
concentrates near the transition between resolution and non-resolution
rather than spreading over a fixed grid, because a grid chosen before the
transition is known is how the saturation happened in the first place.

`effort_drift` IS A FACTOR, NOT A NUISANCE TO BE DELETED
---------------------------------------------------------
Removing it moves passive from five unresolved to nine while every active arm
stays at six, reversing the sign of the active advantage. That is an
interaction and it is crossed, not averaged away:

    Delta_active      = Y_active - Y_passive
    Delta_interaction = Delta_active(drift present) - Delta_active(absent)

If the active advantage changes sign across that contrast, the campaign says
so in those words.

NOTHING HERE RUNS ANYTHING. This module declares the design. The amended
locked campaign consumes it, once, after every choice is frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple

SCHEMA = "csia.active_evidence.difficulty/1"

RESOLVABLE = "RESOLVABLE_IN_MODEL"
BOUNDARY = "BOUNDARY"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


def resolution_margin(target_delta_r: float, b_total: float,
                      uncertainty: float) -> float:
    """`M_R = |delta_R| - (|B_total| + U_R)`, in ohms. Signed, never capped."""
    return abs(target_delta_r) - (abs(b_total) + abs(uncertainty))


def classify_margin(m_r: float, tol: float = 0.0) -> str:
    if m_r > tol:
        return RESOLVABLE
    if m_r < -tol:
        return INSUFFICIENT
    return BOUNDARY


@dataclass(frozen=True)
class Factor:
    """One axis of the ladder. Three levels, and the units are stated."""

    name: str
    unit: str
    easy: float
    nominal: float
    hard: float
    note: str = ""

    def level(self, which: str) -> float:
        return {"easy": self.easy, "nominal": self.nominal,
                "hard": self.hard}[which]

    def to_dict(self) -> dict:
        return asdict(self)


#: The sixteen factors the governing instruction names. Every value is a
#: DECLARED engineering level in its own units, not a fitted one.
LADDER: Tuple[Factor, ...] = (
    Factor("target_delta_r", "ohm", 0.040, 0.010, 0.003,
           "smaller is harder; the transition sits near 0.005 to 0.010"),
    Factor("sigma_v", "V", 0.010, 0.020, 0.050),
    Factor("sigma_i", "A", 0.040, 0.080, 0.200),
    Factor("bias_i", "A", 0.0, 0.2, 1.0),
    Factor("scale_error_i", "fraction", 0.0, 0.005, 0.020),
    Factor("ocv_drift", "V/s", 0.001, 0.008, 0.030,
           "the linear open-circuit slope the probe must not alias"),
    Factor("ocv_curvature", "V", 0.10, 0.45, 1.20,
           "nonlinear drift; the estimator has no term for it"),
    Factor("r1", "ohm", 0.004, 0.015, 0.030),
    Factor("tau1", "s", 1.0, 13.5, 40.0,
           "hardest when comparable to the probe window"),
    Factor("loop_lag", "s", 0.05, 0.25, 0.80),
    Factor("lag_model_error", "ratio", 1.0, 0.9, 0.25,
           "assumed over true; 0.25 is the four-fold underestimate that "
           "flips the realized lever sign"),
    Factor("command_clip", "fraction of authority", 1.0, 0.7, 0.3),
    Factor("telemetry_hz", "Hz", 200.0, 50.0, 10.0),
    Factor("timestamp_jitter", "s", 0.0, 0.002, 0.010),
    Factor("dropout", "fraction", 0.0, 0.02, 0.20),
    Factor("probe_energy_budget", "A*s", 80.0, 40.0, 8.0,
           "with duration and mission deviation, the cost side of the "
           "matched comparison"),
)

BY_NAME: Dict[str, Factor] = {f.name: f for f in LADDER}

#: Crossed with every strategy and every plant model.
EFFORT_DRIFT_STATES: Tuple[str, ...] = ("absent", "nominal", "elevated")
EFFORT_DRIFT_MAGNITUDE: Dict[str, Optional[float]] = {
    "absent": None, "nominal": 0.008, "elevated": 0.030}

PLANT_MODELS: Tuple[str, ...] = ("simple", "one_rc", "multi_rc")

STRATEGIES: Tuple[str, ...] = (
    "P0_passive", "P1_palindromic", "P2_compensated", "P3_shaped",
    "P4_feedback", "P5_random_safe", "P6_mission", "P7_oracle")

#: P7 is a ceiling. It is never reported as an available method, and its
#: parameters never inform P2 to P4.
NOT_DEPLOYABLE: Tuple[str, ...] = ("P7_oracle",)


def factorial_cells() -> Tuple[dict, ...]:
    """strategy x effort-drift state x plant model. The declared design."""
    return tuple({"strategy": s, "effort_drift": e, "plant": p}
                 for s in STRATEGIES for e in EFFORT_DRIFT_STATES
                 for p in PLANT_MODELS)


def interaction(active_with: float, passive_with: float,
                active_without: float, passive_without: float) -> dict:
    """The contrast that must not be averaged away.

    Reports both deltas, their difference, and whether the sign of the active
    advantage changed. A sign change is the finding, not noise.
    """
    d_with = active_with - passive_with
    d_without = active_without - passive_without
    return {
        "delta_active_drift_present": d_with,
        "delta_active_drift_absent": d_without,
        "delta_interaction": d_with - d_without,
        "active_advantage_changes_sign": (d_with > 0) != (d_without > 0),
        "reading": ("If the sign changes, the active/passive comparison is "
                    "nuisance-model-dependent and no single number answers "
                    "it."),
    }


def specification() -> dict:
    return {
        "schema": SCHEMA,
        "primary_outcome": "signed resolution margin M_R, in ohms",
        "retained_for_audit": "the binary separation fraction from MX-039",
        "why_replaced": (
            "the binary metric scored 0.00 for every arm at 0.005 ohm and "
            "1.00 for every arm at 0.020 and 0.040, so exactly one of four "
            "grid points discriminated and every reported difference rested "
            "on it"),
        "factors": [f.to_dict() for f in LADDER],
        "effort_drift_states": list(EFFORT_DRIFT_STATES),
        "effort_drift_magnitudes": dict(EFFORT_DRIFT_MAGNITUDE),
        "plant_models": list(PLANT_MODELS),
        "strategies": list(STRATEGIES),
        "not_deployable": list(NOT_DEPLOYABLE),
        "factorial_cells": len(factorial_cells()),
        "per_strategy_outcomes": [
            "smallest resolvable |delta_R0|",
            "resolution probability versus fault magnitude",
            "certificate probability",
            "false-certificate probability",
            "unknown/model-mismatch routing rate",
            "median and worst-case resolution margin",
            "energy cost", "mission cost", "minimum safety margin",
            "realized S_II", "realized |S_tI|/S_II", "runtime",
        ],
        "pairing": ("matched seeds and common random numbers within every "
                    "comparison; passive and active cost-matched on duration "
                    "and energy"),
    }
