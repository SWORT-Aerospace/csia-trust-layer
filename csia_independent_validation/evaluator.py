"""Layer B — the independent outcome evaluator.

WHAT THIS REPLACES
------------------
The prior phase scored itself with

    M_R^cert = |dR_target| - (|B_total| + U_R),

which is a statement about the certificate's own declared error budget. It is
computed from the realized current and the declared envelope, so it came out
**bit-identical across all three plants in all 2012 comparable cells**
(``COUNTEREXAMPLE_LOG.md`` IV-4). A metric that cannot see the plant cannot
tell you whether the estimate was right.

This module scores estimates against what the simulator actually did:

    e_R      = R_hat - R_true
    AE_R     = |e_R|
    RE_R     = |e_R| / max(|R_true|, eps)
    e_dR     = (R_hat_fault - R_hat_nominal) - (R_fault - R_nominal)
    M_R^out  = tau_R - |e_dR|

``M_R^cert`` and ``M_R^out`` are different objects and this package never
substitutes one for the other. Reporting both, and their calibration
relationship, is the deliverable.

WHAT THIS MODULE MAY NOT DO
---------------------------
It may not import the certificate's resolution-margin computation. If the
evaluator reuses the certificate's error budget it cannot falsify the
certificate, which is the entire reason it exists.
``tests/test_iv_layers.py`` and :func:`csia_independent_validation.audit`
enforce that it imports nothing from ``csia_active_evidence`` at all.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Optional, Sequence, Tuple

from .truth import GroundTruth, TruthPair

LAYER = "B"
TRUTH_BEARING = True
SCHEMA = "csia.independent_validation.evaluator/1"

#: Frozen by the preregistration, section 2. Changing any of these after an
#: outcome has been seen invalidates the phase. ``tests/test_iv_evaluator.py``
#: pins them against the preregistration text.
TAU_R_RELATIVE = 0.5
TAU_R_ABSOLUTE = 0.002
COVERAGE_TARGET = 0.90
EPSILON = 1e-9


def tau_r(target_delta: float, *, relative: bool = True) -> float:
    """The accuracy requirement a change estimate is scored against.

    Primary form is relative: an error of half the claimed change. The grid is
    spaced by roughly a factor of two, so that is the loosest requirement under
    which the estimate still has the right sign and cannot be mistaken for the
    neighbouring grid point. It is derived from the experiment's own grid and
    it is **not** an application requirement; there is no application here.
    """
    if relative:
        return TAU_R_RELATIVE * abs(target_delta)
    return TAU_R_ABSOLUTE


@dataclass(frozen=True)
class PointOutcome:
    """How wrong a single resistance estimate was."""

    e_r: float
    ae_r: float
    re_r: float
    r_hat: float
    r_true: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass(frozen=True)
class ChangeOutcome:
    """How wrong an estimate of the *change* was, and whether that is enough.

    ``resolved`` is the preregistered predicate ``M_R^out > 0``. It is always
    reported next to the number, because the prior phase's frontier table was
    read as a certification claim when it was a margin claim.
    """

    e_delta_r: float
    tau_r: float
    m_r_out: float
    true_delta_r: float
    estimated_delta_r: float
    resolved: bool

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass(frozen=True)
class IntervalOutcome:
    """Calibration of an interval or set estimate."""

    covers_truth: bool
    width: float
    nominal_fault_separation: float
    false_exclusion: bool

    def to_dict(self) -> Dict:
        return asdict(self)


def evaluate_point(r_hat: float, truth: GroundTruth) -> PointOutcome:
    """Score a point estimate against the resistance the plant actually ran."""
    r_true = truth.r0_realized
    error = r_hat - r_true
    return PointOutcome(
        e_r=error, ae_r=abs(error),
        re_r=abs(error) / max(abs(r_true), EPSILON),
        r_hat=r_hat, r_true=r_true)


def evaluate_change(r_hat_nominal: float, r_hat_fault: float,
                    pair: TruthPair, *, relative: bool = True
                    ) -> ChangeOutcome:
    """Score an estimate of ``R_fault - R_nominal`` against the true change."""
    estimated = r_hat_fault - r_hat_nominal
    true_change = pair.true_delta_r
    error = estimated - true_change
    threshold = tau_r(true_change, relative=relative)
    margin = threshold - abs(error)
    return ChangeOutcome(
        e_delta_r=error, tau_r=threshold, m_r_out=margin,
        true_delta_r=true_change, estimated_delta_r=estimated,
        resolved=margin > 0.0)


def evaluate_interval(lower: float, upper: float, truth: GroundTruth, *,
                      nominal_interval: Optional[Tuple[float, float]] = None
                      ) -> IntervalOutcome:
    """Coverage, width and separation for an interval estimate.

    ``nominal_fault_separation`` is positive when the two intervals are
    disjoint and negative by the overlap when they are not. A set-separation
    claim is only meaningful when it is positive.
    """
    if upper < lower:
        lower, upper = upper, lower
    r_true = truth.r0_realized
    covers = lower <= r_true <= upper
    separation = float("nan")
    if nominal_interval is not None:
        n_lo, n_hi = sorted(nominal_interval)
        separation = max(lower - n_hi, n_lo - upper)
    return IntervalOutcome(
        covers_truth=covers, width=upper - lower,
        nominal_fault_separation=separation,
        false_exclusion=not covers)


def coverage(outcomes: Iterable[IntervalOutcome]) -> Optional[float]:
    """Empirical coverage. ``None`` rather than a number when there is no n."""
    values = [o.covers_truth for o in outcomes]
    return (sum(values) / len(values)) if values else None


def simultaneous_coverage(outcomes: Sequence[IntervalOutcome]) -> bool:
    """Whether every interval in a claimed-simultaneous family covers truth."""
    return bool(outcomes) and all(o.covers_truth for o in outcomes)


def calibration_by_state(states: Sequence[str],
                         outcomes: Sequence[ChangeOutcome]
                         ) -> Dict[str, Dict[str, float]]:
    """Independent resolution rate conditional on each certificate state.

    This is the table the prior phase could not produce. A
    ``CERTIFIED_IN_MODEL`` row whose ``resolved_fraction`` is below the
    coverage target is a **false certificate** in the only sense that means
    anything, and it is a first-class result, not a defect to repair.
    """
    if len(states) != len(outcomes):
        raise ValueError("one state per outcome")
    grouped: Dict[str, list] = {}
    for state, outcome in zip(states, outcomes):
        grouped.setdefault(state, []).append(outcome)
    table: Dict[str, Dict[str, float]] = {}
    for state, group in sorted(grouped.items()):
        margins = [o.m_r_out for o in group]
        errors = [abs(o.e_delta_r) for o in group]
        table[state] = {
            "n": len(group),
            "resolved_fraction": sum(o.resolved for o in group) / len(group),
            "median_m_r_out": statistics.median(margins),
            "worst_m_r_out": min(margins),
            "median_abs_error_ohm": statistics.median(errors),
            "worst_abs_error_ohm": max(errors),
            "meets_coverage_target":
                (sum(o.resolved for o in group) / len(group))
                >= COVERAGE_TARGET,
        }
    return table


def false_certificates(states: Sequence[str],
                       outcomes: Sequence[ChangeOutcome]) -> list:
    """Cells certified in model whose independent outcome did not resolve.

    Contrast with the prior phase's check, which asked whether a certified row
    had a negative *certificate* margin. That set was empty by construction.
    This one can be non-empty, which is what makes it evidence.
    """
    if len(states) != len(outcomes):
        raise ValueError("one state per outcome")
    return [
        {"index": index, "state": state, "m_r_out": outcome.m_r_out,
         "e_delta_r": outcome.e_delta_r,
         "true_delta_r": outcome.true_delta_r}
        for index, (state, outcome) in enumerate(zip(states, outcomes))
        if state == "CERTIFIED_IN_MODEL" and not outcome.resolved
    ]


def detect_leakage(estimates: Sequence[float], truths: Sequence[float], *,
                   tolerance: float = 1e-12) -> bool:
    """Flag an estimator that is simply returning the answer.

    An estimator with access to truth is not a better estimator, it is a
    broken experiment. Agreement to within floating-point noise across more
    than a couple of cells is not skill.
    """
    if len(estimates) != len(truths):
        raise ValueError("one truth per estimate")
    if len(estimates) < 3:
        return False
    exact = sum(1 for e, t in zip(estimates, truths)
                if abs(e - t) <= tolerance)
    return exact == len(estimates)


def is_degenerate_nominal(outcomes: Sequence[ChangeOutcome], *,
                          tolerance: float = 1e-12) -> bool:
    """Flag an estimator that always returns the nominal value.

    Such an estimator has ``estimated_delta_r == 0`` everywhere, so its change
    error is exactly the true change. It scores perfectly on cells with no
    fault and must fail every cell with one.
    """
    if not outcomes:
        return False
    return all(abs(o.estimated_delta_r) <= tolerance for o in outcomes)


def grid_resolution_area(resolved_by_magnitude: Dict[float, float]) -> float:
    """``A_s``: the mean resolution probability over the frozen grid.

    Finite whether or not a method ever resolves, which the withdrawn
    interaction scalar was not.
    """
    if not resolved_by_magnitude:
        return float("nan")
    return sum(resolved_by_magnitude.values()) / len(resolved_by_magnitude)


def drift_interaction(area_with_drift: float, area_without_drift: float,
                      passive_with_drift: float,
                      passive_without_drift: float) -> float:
    """``I_s``: the preregistered primary interaction statistic.

    Difference in differences against the passive baseline. Every term is a
    mean probability in [0, 1], so the result is always finite and lies in
    [-2, 2]. The statistic it replaces became ``NaN`` the moment a method
    never resolved, because "never" was encoded as infinity.
    """
    for value in (area_with_drift, area_without_drift, passive_with_drift,
                  passive_without_drift):
        if not (0.0 <= value <= 1.0) or math.isnan(value):
            raise ValueError(
                f"{value!r} is not a resolution probability; I_s is only "
                "defined on grid resolution areas")
    return ((area_with_drift - passive_with_drift)
            - (area_without_drift - passive_without_drift))


def censored_frontier(resolved_by_magnitude: Dict[float, float], *,
                      target: float = COVERAGE_TARGET,
                      d_max_tested: float = 0.040):
    """Smallest magnitude reaching ``target``, or the string ``> d_max``.

    Never infinity. The prior phase encoded "never" as ``float("inf")`` and
    then did arithmetic on it, which is how the preregistered interaction
    scalar came out ``NaN``.
    """
    for magnitude in sorted(resolved_by_magnitude):
        if resolved_by_magnitude[magnitude] >= target:
            return magnitude
    return f"> {d_max_tested:g}"
