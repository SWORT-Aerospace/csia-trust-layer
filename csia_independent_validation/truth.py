"""Ground truth. **Layer B only.**

This module is the tripwire. Nothing in Layer A -- the deployable certificate
and everything it transitively imports -- may reach this module, because
anything that can see a :class:`GroundTruth` can cheat without anybody
noticing. ``tests/test_iv_layers.py`` walks Layer A's transitive imports and
fails if this module appears.

The marker below is what that test looks for, and it is also what a human sees
first when they open the file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, Tuple

#: Read by the architectural test. Layer A must never import a module that
#: declares this.
LAYER = "B"
TRUTH_BEARING = True

SCHEMA = "csia.independent_validation.truth/1"


@dataclass(frozen=True)
class GroundTruth:
    """Everything the simulator knew and the certificate is not allowed to.

    ``r0_nominal`` and ``r0_realized`` are the two numbers the whole phase
    turns on: the change the evaluator scores an estimate against is
    ``r0_realized - r0_nominal``, taken from here and never from an estimator.
    """

    plant: str                      # "Q0", "Q1" or "Q2"
    r0_nominal: float               # ohm, before the injected change
    r0_realized: float              # ohm, what the plant actually ran with
    fault_label: str                # "none", "r0_increase", "unknown_ringing"
    r1: float = 0.0                 # ohm, first polarization branch
    tau1_s: float = 0.0             # s
    r2: float = 0.0                 # ohm, second branch (Q2 only)
    tau2_s: float = 0.0             # s
    hysteresis_v: float = 0.0       # V, amplitude (Q2 only)
    hysteresis_gamma: float = 0.0   # dimensionless rate (Q2 only)
    ocv_curvature: float = 0.0      # V
    ringing_amplitude_v: float = 0.0
    ringing_hz: float = 0.0
    ringing_damping: float = 0.0
    ringing_phase_rad: float = 0.0
    ringing_onset_s: float = 0.0
    drift_v_per_s: float = 0.0
    lag_s: float = 0.0              # s, true command-to-current time constant
    #: Per-sample true current and true terminal voltage, unmeasured.
    i_true: Tuple[float, ...] = field(default=(), repr=False)
    v_true: Tuple[float, ...] = field(default=(), repr=False)
    v1_true: Tuple[float, ...] = field(default=(), repr=False)
    seed: int = 0

    @property
    def delta_r0(self) -> float:
        """The change an estimator is being asked to recover."""
        return self.r0_realized - self.r0_nominal

    def to_dict(self, *, with_traces: bool = False) -> Dict:
        out = asdict(self)
        if not with_traces:
            for key in ("i_true", "v_true", "v1_true"):
                out[key] = f"<{len(getattr(self, key))} samples withheld>"
        return out


@dataclass(frozen=True)
class TruthPair:
    """A nominal/fault pair, scored against each other.

    By default the two windows must share a seed. That is the common-random-
    numbers design, and the guard exists because a pair that accidentally
    mismatched seeds would report noise as signal.

    ``independent_windows`` switches the guard off **deliberately**, for the
    design in ``PREREGISTRATION_AMENDMENT_4.md``. That amendment exists
    because sharing a seed turned out to be too strong an assumption, not too
    weak: the fault does not move the current, so a shared seed makes
    ``V_fault - V_nominal = -dR.I_true`` exact, every plant-common nuisance
    cancels, and the change metric saturates (``COUNTEREXAMPLE_LOG.md`` IV-9).
    No deployment re-flies the identical probe under identical noise with and
    without a fault.

    The flag is required rather than inferred, so that an accidental seed
    mismatch still fails and only an intended one passes. It must be spelled
    out at the call site.
    """

    nominal: GroundTruth
    fault: GroundTruth
    independent_windows: bool = False

    def __post_init__(self) -> None:
        if not self.independent_windows and self.nominal.seed != \
                self.fault.seed:
            raise ValueError(
                "a nominal/fault pair must share its seed, otherwise the "
                "change estimate is comparing two different noise draws. If "
                "the windows are meant to be independent, say so with "
                "independent_windows=True")
        if self.nominal.plant != self.fault.plant:
            raise ValueError("a pair must be on one plant")

    @property
    def true_delta_r(self) -> float:
        """``R_fault - R_nominal``. The quantity ``e_dR`` is scored against."""
        return self.fault.r0_realized - self.nominal.r0_nominal


def strip(truth: Optional[GroundTruth]) -> None:
    """There is no way to convert truth into something Layer A may hold.

    This function exists so that the absence of a conversion is explicit
    rather than accidental. It always raises.
    """
    raise PermissionError(
        "ground truth does not cross into Layer A. If you need a number from "
        "the plant on the deployable side, that number is a modelling "
        "assumption and belongs in the declared envelope, not here.")
