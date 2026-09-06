"""The eight trial states, and a machine-executable predicate for each.

WHY EIGHT, AND WHY THESE EIGHT
-------------------------------
`csia/simulation/contract.py` defines three, and they are the right three for a
simulator campaign:

    VALID              the evidence chain closed; the trial is scorable
    INVALID_SCENARIO   the intervention was never proven; NOT a failure
    INSTRUMENT_DEAD    the null control also moved; no arm may be read

A physical campaign has five more outcomes, and every one of them has already
cost somebody a campaign somewhere:

    ABORTED_BY_OPERATOR  a human stopped it. Recorded, never silently dropped.
    HARDWARE_FAULT       the RIG broke, not the vehicle under test. The
                         distinction is the whole point: a snapped wire in the
                         injector is not a diagnostic result.
    TIMING_INSUFFICIENT  the run happened but the timing budget cannot support
                         the metric being claimed from it.
    PREREG_VIOLATION     the trial as run differs from what was preregistered.
                         Scoring it anyway is the definition of a garden of
                         forking paths.
    NOT_ATTEMPTED        planned, counted in the denominator, never run.

THE LAST ONE IS THE ARITHMETIC
-------------------------------
A campaign that reports only the trials it ran has an unrecorded denominator.
`reconcile()` enforces:

    planned == valid + invalid + not_attempted

and refuses to produce a summary that does not balance. FAILURE_LEDGER.yaml
says the same thing in prose; this makes it a check.

EVERY STATE IS DECIDED BY A PREDICATE, NOT BY A LABEL
------------------------------------------------------
An operator typing "HARDWARE_FAULT" into a field is an assertion. Each state
below carries `predicate(record) -> bool | None`, evaluated from the recorded
evidence:

    True   the record establishes this state
    False  the record rules it out
    None   the record does not say -- which is itself reportable, and is NOT
           the same as False

`adjudicate()` evaluates them in a fixed precedence and returns the first that
holds, together with WHICH predicate fired and what it read. A state nobody can
derive from the record is not a state this module will assign.
"""

from __future__ import annotations

import enum
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")))

from csia.simulation.contract import TrialVerdict  # noqa: E402


class TrialState(enum.Enum):
    """Eight states. The first three are TrialVerdict, by the same names."""

    VALID = "VALID"
    INVALID_SCENARIO = "INVALID_SCENARIO"
    INSTRUMENT_DEAD = "INSTRUMENT_DEAD"
    ABORTED_BY_OPERATOR = "ABORTED_BY_OPERATOR"
    HARDWARE_FAULT = "HARDWARE_FAULT"
    TIMING_INSUFFICIENT = "TIMING_INSUFFICIENT"
    PREREG_VIOLATION = "PREREG_VIOLATION"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"

    @property
    def scorable(self) -> bool:
        """Only VALID trials may contribute to any metric."""
        return self is TrialState.VALID

    @property
    def attempted(self) -> bool:
        return self is not TrialState.NOT_ATTEMPTED


#: The three states that mean "we tried and it did not produce a result".
#: Every one of them belongs in FAILURE_LEDGER.yaml with its own entry.
INVALID_STATES = (
    TrialState.INVALID_SCENARIO, TrialState.INSTRUMENT_DEAD,
    TrialState.ABORTED_BY_OPERATOR, TrialState.HARDWARE_FAULT,
    TrialState.TIMING_INSUFFICIENT, TrialState.PREREG_VIOLATION,
)


@dataclass
class Predicate:
    """One machine-executable validity rule."""

    state: TrialState
    describe: str
    #: record -> True (holds) / False (ruled out) / None (record is silent)
    fn: Callable
    #: what the predicate needs the record to carry. A record missing these
    #: cannot be adjudicated for this state, and `evaluate` says so.
    requires: tuple = ()

    def evaluate(self, record: dict) -> dict:
        missing = [k for k in self.requires if k not in record]
        if missing:
            return {"state": self.state.value, "holds": None,
                    "reason": f"record does not carry {missing}",
                    "missing": missing}
        holds = self.fn(record)
        return {"state": self.state.value, "holds": holds,
                "reason": self.describe, "missing": []}


def _not_attempted(rec) -> Optional[bool]:
    return not bool(rec.get("attempted", False))


def _prereg_violation(rec) -> Optional[bool]:
    deviations = rec.get("prereg_deviations")
    if deviations is None:
        return None
    return bool(deviations)


def _aborted(rec) -> Optional[bool]:
    return bool(rec.get("operator_abort"))


def _hardware_fault(rec) -> Optional[bool]:
    faults = rec.get("rig_faults")
    if faults is None:
        return None
    return bool(faults)


def _timing_insufficient(rec) -> Optional[bool]:
    """The run happened; can it support the metric being claimed?

    Two independent ways to fail, and BOTH are needed. A campaign can have a
    fine mean tick period and still miss the deadline on the tail, and the tail
    is what a deadline claim is about.
    """
    budget = rec.get("timing_budget")
    observed = rec.get("timing_observed")
    if not budget or not observed:
        return None
    over = []
    for key, limit in budget.items():
        got = observed.get(key)
        if got is None:
            return None
        if got > limit:
            over.append(f"{key}={got} > {limit}")
    return bool(over)


def _instrument_dead(rec) -> Optional[bool]:
    """RULE A. A null control that moved invalidates every arm, not just this
    one, so this outranks the chain check below."""
    controls = rec.get("null_controls")
    if controls is None:
        return None
    seen = False
    for control in controls:
        quiet = control.get("quiet")
        if quiet is None:
            continue
        seen = True
        if quiet is False:
            return True
    return False if seen else None


def _invalid_scenario(rec) -> Optional[bool]:
    """The evidence chain did not close: the intervention is unproven.

    NOT a failure of the detector, and scoring it as one manufactures evidence
    that a detector missed a fault that may never have existed.
    """
    if rec.get("first_break") is not None:
        return True
    stages = rec.get("stages")
    if stages is None:
        return None
    return False


#: PRECEDENCE, AND WHY IT IS THIS ORDER.
#:
#: Each state answers a different question, and the earlier ones make the later
#: ones unanswerable rather than merely also-true:
#:
#:   NOT_ATTEMPTED        nothing ran, so nothing else can be evaluated.
#:   PREREG_VIOLATION     what ran was not the planned experiment, so its
#:                        result is not the planned result -- checked BEFORE
#:                        the chain, because a chain that closes on the wrong
#:                        experiment is still the wrong experiment.
#:   ABORTED_BY_OPERATOR  a human stopped it; downstream measurements are
#:                        truncated by construction.
#:   HARDWARE_FAULT       the rig broke. Distinguished from a vehicle fault,
#:                        which is a RESULT.
#:   INSTRUMENT_DEAD      RULE A. The null control moved, so no arm is
#:                        readable -- this invalidates the campaign, not the
#:                        trial, and must outrank the per-trial chain.
#:   INVALID_SCENARIO     the chain broke: the intervention is unproven.
#:   TIMING_INSUFFICIENT  everything above is fine and the run is real, but the
#:                        timing budget cannot support the metric. Deliberately
#:                        LAST of the invalid states: a trial can be timing-
#:                        insufficient for a latency claim and still perfectly
#:                        valid evidence for a categorical one, so it is only
#:                        reached when nothing more fundamental is wrong.
#:   VALID                nothing above holds.
PRECEDENCE = (
    Predicate(TrialState.NOT_ATTEMPTED,
              "the trial was planned and never run",
              _not_attempted, requires=("attempted",)),
    Predicate(TrialState.PREREG_VIOLATION,
              "the trial as run differs from the preregistration",
              _prereg_violation, requires=("prereg_deviations",)),
    Predicate(TrialState.ABORTED_BY_OPERATOR,
              "a human stopped the run",
              _aborted, requires=("operator_abort",)),
    Predicate(TrialState.HARDWARE_FAULT,
              "the rig itself faulted, as distinct from the vehicle",
              _hardware_fault, requires=("rig_faults",)),
    Predicate(TrialState.INSTRUMENT_DEAD,
              "RULE A: a null control moved, so no arm may be read",
              _instrument_dead, requires=("null_controls",)),
    Predicate(TrialState.INVALID_SCENARIO,
              "the evidence chain broke; the intervention is unproven",
              _invalid_scenario, requires=()),
    Predicate(TrialState.TIMING_INSUFFICIENT,
              "the timing budget cannot support the metric claimed",
              _timing_insufficient, requires=()),
)


@dataclass
class Adjudication:
    state: TrialState
    fired: Optional[str]
    evaluations: list = field(default_factory=list)
    undecidable: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "scorable": self.state.scorable,
            "fired_predicate": self.fired,
            "evaluations": self.evaluations,
            "undecidable": self.undecidable,
        }


def adjudicate(record: dict) -> Adjudication:
    """Assign one of the eight states from the record, and say how.

    A predicate returning None -- the record is silent -- does NOT default to
    False. It is listed in `undecidable`, because "we cannot tell whether the
    rig faulted" is a different statement from "the rig did not fault", and a
    campaign that reports the second when it means the first is overclaiming.
    """
    evaluations, undecidable = [], []
    for pred in PRECEDENCE:
        result = pred.evaluate(record)
        evaluations.append(result)
        if result["holds"] is None:
            undecidable.append(result)
            continue
        if result["holds"]:
            return Adjudication(state=pred.state, fired=pred.state.value,
                                evaluations=evaluations,
                                undecidable=undecidable)
    return Adjudication(state=TrialState.VALID, fired=None,
                        evaluations=evaluations, undecidable=undecidable)


def from_contract_verdict(verdict) -> TrialState:
    """Map csia/simulation/contract.py's three-valued verdict into the eight.

    The names are shared on purpose: this is a widening, not a translation, and
    a test asserts every TrialVerdict has a TrialState of the same name. If
    that ever stops being true the two vocabularies have forked and the
    orchestrator is quietly speaking a different language from the contract.
    """
    return TrialState(TrialVerdict(verdict).value)


def reconcile(records: list) -> dict:
    """Campaign arithmetic, and it must balance.

    planned == valid + invalid + not_attempted

    A campaign summary that does not balance is not printed; it raises. The
    alternative is a report whose denominator is whatever survived, which is
    the specific defect FAILURE_LEDGER.yaml exists to prevent.
    """
    counts = {s: 0 for s in TrialState}
    for rec in records:
        counts[adjudicate(rec).state] += 1

    valid = counts[TrialState.VALID]
    not_attempted = counts[TrialState.NOT_ATTEMPTED]
    invalid = sum(counts[s] for s in INVALID_STATES)
    planned = len(records)

    if valid + invalid + not_attempted != planned:
        raise ValueError(
            f"trial arithmetic does not balance: planned={planned}, "
            f"valid={valid}, invalid={invalid}, "
            f"not_attempted={not_attempted}. Every state must be counted "
            f"exactly once; a state added to TrialState and not to "
            f"INVALID_STATES falls through this check.")

    return {
        "planned": planned,
        "attempted": planned - not_attempted,
        "valid": valid,
        "invalid": invalid,
        "not_attempted": not_attempted,
        "by_state": {s.value: counts[s] for s in TrialState if counts[s]},
        "scorable_fraction_note": (
            "valid / attempted, NOT valid / planned. Both denominators are "
            "reported above so a reader can compute either and see which one "
            "a quoted rate used."),
    }
