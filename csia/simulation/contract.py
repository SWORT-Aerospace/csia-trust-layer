"""Trial-validity contract: a scenario is not a result until the chain closes.

The rule that produced this module, stated as Phase-II permanent rule 1:

    COMMAND ISSUED != FAULT INJECTED.

Setting `SIM_GPS1_GLITCH_X` and observing nothing is not a negative result. It
is an unproven intervention, and scoring it as a miss manufactures evidence
that a detector failed when the fault may never have existed. We have made
this mistake and it cost a whole campaign: the E1 run-1 displacement
instrument measured injected offset and airframe motion together, and read
38.89 m on a zero-injection arm.

Six stages, each a boolean **plus the measured intermediate that justifies
it**. A stage is not satisfied by an assertion; it is satisfied by a number.

    COMMAND_ISSUED            the parameter write returned success
    SIMULATOR_STATE_CHANGED   the simulator's own state reflects it
    SENSOR_OUTPUT_CHANGED     the sensor stream downstream of it moved
    AUTOPILOT_RECEIVED_CHANGE the autopilot's estimator saw it
    CSIA_RECEIVED_CHANGE      the canonical sample carries it
    GROUND_TRUTH_MATCHES      the observed magnitude matches what was ordered

Verdicts are three-valued on purpose. A scenario whose physical effect cannot
be verified is `INVALID_SCENARIO` -- **not** PASS and **not** FAIL. Collapsing
it to FAIL is how a broken injection becomes a published detector weakness.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class Stage(enum.Enum):
    COMMAND_ISSUED = "COMMAND_ISSUED"
    SIMULATOR_STATE_CHANGED = "SIMULATOR_STATE_CHANGED"
    SENSOR_OUTPUT_CHANGED = "SENSOR_OUTPUT_CHANGED"
    AUTOPILOT_RECEIVED_CHANGE = "AUTOPILOT_RECEIVED_CHANGE"
    CSIA_RECEIVED_CHANGE = "CSIA_RECEIVED_CHANGE"
    GROUND_TRUTH_MATCHES_EXPECTATION = "GROUND_TRUTH_MATCHES_EXPECTATION"


ORDER = list(Stage)


class TrialVerdict(enum.Enum):
    """Three-valued, and the third value is the important one."""

    VALID = "VALID"                       # chain closed; the trial is scorable
    INVALID_SCENARIO = "INVALID_SCENARIO"  # intervention unproven; NOT a fail
    INSTRUMENT_DEAD = "INSTRUMENT_DEAD"    # the null control also moved


@dataclass
class StageResult:
    """One stage: the boolean, and the number that earned it."""

    stage: Stage
    satisfied: bool
    measured: Any = None
    expected: Any = None
    unit: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stage"] = self.stage.value
        return d


@dataclass
class NullControl:
    """A control arm that must NOT respond.

    RULE A: every scientific instrument must have a null control. If the
    instrument reads a change on an arm where nothing was injected, the
    instrument is broken and no conclusion may be drawn from any arm -- the
    correct output is INSTRUMENT_DEAD, not a detection result.

    `tolerance` is the measured noise ceiling of the control, not a number
    chosen to make a trial pass. Raising it must be justified by control data.
    """

    name: str
    measured: Optional[float] = None
    tolerance: float = 0.0
    unit: str = ""
    basis: str = ""

    @property
    def quiet(self) -> Optional[bool]:
        if self.measured is None:
            return None
        return abs(self.measured) <= self.tolerance

    def to_dict(self) -> dict:
        d = asdict(self)
        d["quiet"] = self.quiet
        return d


@dataclass
class TrialContract:
    """One trial's evidence chain."""

    scenario: str
    platform: str
    autopilot_version: str
    profile: str
    parameters: dict = field(default_factory=dict)
    stages: dict = field(default_factory=dict)
    null_controls: list = field(default_factory=list)
    mechanism_intermediates: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    # -- recording ---------------------------------------------------------

    def record(self, stage: Stage, satisfied: bool, *, measured=None,
               expected=None, unit: str = "", detail: str = "") -> StageResult:
        r = StageResult(stage=stage, satisfied=bool(satisfied),
                        measured=measured, expected=expected, unit=unit,
                        detail=detail)
        self.stages[stage] = r
        return r

    def add_null_control(self, nc: NullControl):
        self.null_controls.append(nc)

    def record_intermediate(self, quantity: str, value, unit: str = "",
                            source: str = ""):
        """RULE B: no mechanism attribution without the intermediate quantity.

        If a trial claims "the spoof broke the heading_course edge", the edge
        consistency at that tick must be here. Claiming a mechanism whose
        intermediate was never observed is how we once blamed a battery
        voltage residual for a fault driven by an entirely different edge.
        """
        self.mechanism_intermediates[quantity] = {
            "value": value, "unit": unit, "source": source}

    # -- adjudication ------------------------------------------------------

    @property
    def missing_stages(self) -> list:
        return [s for s in ORDER
                if s not in self.stages or not self.stages[s].satisfied]

    @property
    def first_break(self) -> Optional[Stage]:
        """Where the chain broke. The most useful single field in the record.

        Knowing a trial was invalid is much less useful than knowing whether
        the parameter write failed or the sensor never moved.
        """
        for s in ORDER:
            r = self.stages.get(s)
            if r is None or not r.satisfied:
                return s
        return None

    @property
    def verdict(self) -> TrialVerdict:
        for nc in self.null_controls:
            if nc.quiet is False:
                return TrialVerdict.INSTRUMENT_DEAD
        return (TrialVerdict.VALID if self.first_break is None
                else TrialVerdict.INVALID_SCENARIO)

    @property
    def trial_valid(self) -> bool:
        return self.verdict is TrialVerdict.VALID

    def require_valid(self):
        """Raise unless the trial may be scored.

        Campaign code calls this before computing any metric, so
        "never compute science metrics from invalid trials" is enforced by
        the type system rather than by remembering.
        """
        if not self.trial_valid:
            raise TrialNotValid(
                f"{self.scenario}: {self.verdict.value}; "
                f"first break at "
                f"{self.first_break.value if self.first_break else 'null control'}")

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "platform": self.platform,
            "autopilot_version": self.autopilot_version,
            "profile": self.profile,
            "parameters": self.parameters,
            "TRIAL_VALID": self.trial_valid,
            "verdict": self.verdict.value,
            "first_break": (self.first_break.value
                            if self.first_break else None),
            "stages": {s.value: self.stages[s].to_dict()
                       for s in ORDER if s in self.stages},
            "missing_stages": [s.value for s in self.missing_stages],
            "null_controls": [nc.to_dict() for nc in self.null_controls],
            "mechanism_intermediates": self.mechanism_intermediates,
            "notes": self.notes,
        }

    def summary(self) -> str:
        marks = []
        for s in ORDER:
            r = self.stages.get(s)
            marks.append("." if r is None else ("Y" if r.satisfied else "N"))
        nc = ",".join(f"{n.name}={'quiet' if n.quiet else 'MOVED'}"
                      for n in self.null_controls) or "none"
        return (f"{self.scenario:24s} [{''.join(marks)}] "
                f"{self.verdict.value:17s} null:{nc}")


class TrialNotValid(RuntimeError):
    """Raised when a metric is requested from an unscorable trial."""
