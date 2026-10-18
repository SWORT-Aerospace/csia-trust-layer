"""The model bank, and the sentinel that is not a model.

WHY A SMALL BANK
----------------
Eight entries, every one of which the existing component simulator can
actually produce, taken from `csia_components.simulate.FAULT_KINDS` and its
`APPLICABLE` matrix rather than listed here by hand. A bank containing a
fault the plant cannot generate would be swept as though it could be, which
is the defect `csia_stress/fault_params.py` had to be written to stop on the
injection side.

THE SENTINEL IS NOT A GENERATIVE MODEL
---------------------------------------
`UNKNOWN_OR_MODEL_MISMATCH` has no parameters, no signature and no
predicted interval. It is what the updater RETURNS when the observation is
outside every modelled hypothesis's set, and it can never be "selected",
"scored" or "separated from" anything. A sentinel with a likelihood would be
a ninth model wearing a warning label, and the open-set control would pass
for the wrong reason.

MAGNITUDES ARE NOT INVENTED HERE
---------------------------------
Every magnitude is read from `csia_stress.falsify.WORST_PARAMS` where that
file has one for the kind, and otherwise from the detection floors MX-036
measured. The bank declares no number of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Tuple

from csia_components import simulate as S

SCHEMA = "csia.active_evidence.model_bank/1"

#: Returned by the updater. NOT a member of the bank.
UNKNOWN = "UNKNOWN_OR_MODEL_MISMATCH"

NOMINAL = "nominal"


@dataclass(frozen=True)
class FaultHypothesis:
    """One bounded, simulator-producible hypothesis.

    `magnitudes` is a bracket, not a point: a hypothesis is "bearing friction
    somewhere in this range", because a diagnosis that had to name the
    magnitude to name the cause would never fire.
    """

    name: str
    kind: str
    target: str
    magnitudes: Tuple[float, ...]
    units: str
    basis: str

    def __post_init__(self):
        if self.kind != NOMINAL:
            if self.kind not in S.FAULT_KINDS:
                raise ValueError(f"{self.name}: {self.kind!r} is not a fault "
                                 f"kind this simulator can produce")
            if self.kind not in S.APPLICABLE.get(self.target, ()):
                raise ValueError(
                    f"{self.name}: the applicability matrix says {self.kind!r} "
                    f"cannot be applied to {self.target!r}; a bank entry the "
                    f"plant cannot generate would be swept as though it could")
        if not self.magnitudes:
            raise ValueError(f"{self.name}: no magnitude bracket")

    def fault(self, magnitude: float, start: float, duration: float):
        if self.kind == NOMINAL:
            return ()
        return (S.Fault(self.kind, self.target, start, duration, magnitude),)

    def to_dict(self) -> dict:
        return asdict(self)


BANK: Tuple[FaultHypothesis, ...] = (
    FaultHypothesis(
        name="nominal", kind=NOMINAL, target="-", magnitudes=(0.0,),
        units="-", basis="no fault injected"),
    FaultHypothesis(
        name="pack_impedance", kind="pack_impedance_rise", target="pack",
        magnitudes=(0.02, 0.06, 0.12), units="ohm",
        basis=("the MX-036 anchor: undetectable on a steady hover at every "
               "magnitude up to 0.25 ohm")),
    FaultHypothesis(
        name="shunt_bias", kind="shunt_bias", target="current_sensing",
        magnitudes=(0.03, 0.08, 0.15), units="fractional gain error",
        basis="a current SENSOR reads wrong while the hardware is fine"),
    FaultHypothesis(
        name="bearing_friction", kind="bearing_friction", target="esc0",
        magnitudes=(0.5, 1.5, 3.0), units="newton of added drag",
        basis="more current AND more heat for the same rpm"),
    FaultHypothesis(
        name="efficiency_loss", kind="esc_efficiency_loss", target="esc0",
        magnitudes=(0.08, 0.18, 0.35), units="fractional thrust per amp lost",
        basis=("MX-036 falsified the prediction that the controller hides "
               "this; actuator_response detects it at 2.0x to 299x")),
    FaultHypothesis(
        name="thermal_path", kind="thermal_path_loss", target="esc0",
        magnitudes=(0.3, 0.8, 1.5), units="fractional cooling loss",
        basis="same dissipation, worse cooling"),
    FaultHypothesis(
        name="cpu_overrun", kind="cpu_overrun", target="cpu",
        magnitudes=(0.002, 0.006, 0.012), units="second of added loop time",
        basis="a non-physical timing contrast against the power faults"),
    FaultHypothesis(
        name="bus_drops", kind="bus_drops", target="canbus",
        magnitudes=(0.05, 0.15, 0.30), units="fraction of frames lost",
        basis="a link fault that must not look like a power fault"),
)

BY_NAME = {h.name: h for h in BANK}
FAULTY = tuple(h for h in BANK if h.kind != NOMINAL)


def hypothesis(name: str) -> FaultHypothesis:
    if name not in BY_NAME:
        raise KeyError(f"no hypothesis {name!r}; have {sorted(BY_NAME)}")
    return BY_NAME[name]


def pairs() -> Tuple[Tuple[str, str], ...]:
    """Every unordered pair. THE DENOMINATOR, fixed before any measurement.

    A campaign that counted only the pairs it managed to separate would
    report whatever survived.
    """
    names = [h.name for h in BANK]
    return tuple((a, b) for i, a in enumerate(names) for b in names[i + 1:])


def unmodelled_fault(start: float, duration: float):
    """A fault deliberately OUTSIDE the bank, for the open-set control.

    `thermal_path_loss` on esc2 while every bank entry that targets a motor
    targets esc0. The bank has no hypothesis that can explain a thermal
    signature on a different motor, so a system that named one would be
    forcing an observation into a label it does not fit -- which is the
    failure H4 exists to detect.
    """
    return (S.Fault("thermal_path_loss", "esc2", start, duration, 1.5),)
