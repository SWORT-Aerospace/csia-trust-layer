"""What was it told to do, what did it do, and what did deviating cost?

THE GAP THIS FILLS
------------------
CSIA reasons about whether a component is healthy. It has had no
representation of TASKING at all: no record of what the system was asked to
achieve, no comparison of that against what happened, and therefore no way
to tell a fault from a deliberate change of plan. Those look identical in
telemetry and they mean opposite things.

The pattern already exists one layer down. `csia/prediction/comparator.py`
scores observed sensor behaviour against physics, history and neighbours.
This is the same comparison applied to intent: observed behaviour against
what was committed to.

THE PART THAT IS NOT OBVIOUS, AND IS THE REASON TO BUILD IT
--------------------------------------------------------------
A deviation is not only a fact about the mission. IT CHANGES WHICH EVIDENCE
IS ADMISSIBLE.

Half of CSIA's relations are gated on an operating condition: an effort
check needs a stationary setpoint, an impedance check needs a varying load,
a heading-versus-course check needs the vehicle to be translating. When the
system stops doing what it was told, those gates move, and the evidence
available for the deviated window is a different set from the evidence
available before it. A debrief that reports "it deviated at t=340" and stops
has thrown away the more useful half of the finding, which is "and for the
next 90 seconds these four relations could not run, so the diagnosis over
that window rests on two channels rather than six."

`CommitmentOutcome.relations_suspended` is that half.

WHAT IT REFUSES TO DO
---------------------
It does not judge whether deviating was correct. An autonomous system that
abandons a commitment to avoid a hazard has done the right thing, and a
layer that scored that as a failure would be actively harmful. This module
reports what held, what did not, for how long, and what it cost in evidence.
Every other question belongs to whoever owns the system.

IT ALSO REFUSES TO CALL AN UNCHECKABLE COMMITMENT SATISFIED
--------------------------------------------------------------
`NOT_EVALUABLE` is a distinct outcome from `HELD`, and the whole module is
arranged so the two cannot be confused. A commitment whose channel is absent
from the record is not a commitment that was met.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np

SCHEMA = "csia.evidence.intent/1"

HELD = "HELD"
DEVIATED = "DEVIATED"
ABANDONED = "ABANDONED"
NOT_EVALUABLE = "NOT_EVALUABLE"
OUTCOMES = (HELD, DEVIATED, ABANDONED, NOT_EVALUABLE)


@dataclass(frozen=True)
class Commitment:
    """One checkable thing the system was tasked to do.

    `predicate` takes the record and returns a boolean array, True where the
    commitment holds. It is supplied by whoever knows the domain; this module
    knows only how to run it and how to describe the result.

    `gates` names the relations that require this commitment to hold in
    order to be eligible. It is the link to CSIA's existing gate semantics
    and it is what makes `relations_suspended` computable.

    `tolerance_s` is how long a breach may last before it counts as a
    deviation rather than a transient. It is a DECLARED number in seconds and
    it appears in the report so a reader can see what was allowed.
    """

    name: str
    predicate: Callable[[Dict[str, object]], object]
    requires: Tuple[str, ...] = ()
    gates: Tuple[str, ...] = ()
    tolerance_s: float = 0.0
    basis: str = ""

    def __post_init__(self):
        if self.tolerance_s < 0:
            raise ValueError(f"{self.name}: tolerance_s must not be negative")

    def to_dict(self) -> dict:
        return {"name": self.name, "requires": list(self.requires),
                "gates": list(self.gates), "tolerance_s": self.tolerance_s,
                "basis": self.basis}


@dataclass(frozen=True)
class Deviation:
    start_s: float
    end_s: float
    recovered: bool

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def to_dict(self) -> dict:
        out = asdict(self)
        out["duration_s"] = self.duration_s
        return out


@dataclass(frozen=True)
class CommitmentOutcome:
    name: str
    outcome: str
    deviations: Tuple[Deviation, ...]
    fraction_held: Optional[float]
    longest_deviation_s: float
    relations_suspended: Tuple[str, ...]
    suspended_fraction_of_record: float
    reason: str

    def to_dict(self) -> dict:
        out = asdict(self)
        out["deviations"] = [d.to_dict() for d in self.deviations]
        out["relations_suspended"] = list(self.relations_suspended)
        return out


@dataclass(frozen=True)
class IntentReport:
    schema: str
    outcomes: Tuple[CommitmentOutcome, ...]
    relations_suspended_anywhere: Tuple[str, ...]
    evidence_thinning: Dict[str, float]
    counts: Dict[str, int]
    does_not_establish: str = (
        "This report says what was committed to, what held, and which "
        "relations could not run while it did not. It does not say whether "
        "deviating was correct: a system that abandons a commitment to "
        "avoid a hazard has done the right thing, and nothing here scores "
        "that as a failure.")

    def to_dict(self) -> dict:
        return {"schema": self.schema,
                "outcomes": [o.to_dict() for o in self.outcomes],
                "relations_suspended_anywhere":
                    list(self.relations_suspended_anywhere),
                "evidence_thinning": dict(self.evidence_thinning),
                "counts": dict(self.counts),
                "does_not_establish": self.does_not_establish}


def _runs_of_false(mask: np.ndarray, t: np.ndarray, tolerance_s: float):
    """Contiguous windows where the commitment did not hold.

    A breach shorter than `tolerance_s` is not reported as a deviation. The
    tolerance is applied to DURATION, not to sample count, so the answer does
    not change with the logging rate -- a defect that would otherwise appear
    the first time two platforms logged at different frequencies.
    """
    out = []
    n = mask.size
    k = 0
    while k < n:
        if mask[k]:
            k += 1
            continue
        j = k
        while j < n and not mask[j]:
            j += 1
        start, end = float(t[k]), float(t[min(j, n - 1)])
        recovered = j < n
        if end - start >= tolerance_s:
            out.append(Deviation(start, end, recovered))
        k = j
    return tuple(out)


def compare(record: Dict[str, object], commitments: Sequence[Commitment], *,
            t_key: str = "t") -> IntentReport:
    """Score each commitment against the record. Reports, never judges."""
    if t_key not in record:
        raise ValueError(
            f"the record has no {t_key!r} channel; every deviation is "
            f"reported as a time window and there is no way to build one "
            f"without a timebase")
    t = np.asarray(record[t_key], dtype=float).ravel()
    if t.size < 2:
        raise ValueError("at least two samples are needed to describe a "
                         "window")
    span = float(t[-1] - t[0]) or 1.0

    outcomes = []
    for c in commitments:
        missing = [r for r in c.requires if r not in record]
        if missing:
            outcomes.append(CommitmentOutcome(
                name=c.name, outcome=NOT_EVALUABLE, deviations=(),
                fraction_held=None, longest_deviation_s=0.0,
                relations_suspended=(), suspended_fraction_of_record=0.0,
                reason=(f"the record lacks {sorted(missing)}; an "
                        f"uncheckable commitment is NOT a commitment that "
                        f"was met")))
            continue
        try:
            mask = np.asarray(c.predicate(record), dtype=bool).ravel()
        except Exception as exc:               # noqa: BLE001 - recorded
            outcomes.append(CommitmentOutcome(
                name=c.name, outcome=NOT_EVALUABLE, deviations=(),
                fraction_held=None, longest_deviation_s=0.0,
                relations_suspended=(), suspended_fraction_of_record=0.0,
                reason=f"the predicate raised {type(exc).__name__}: "
                       f"{str(exc)[:80]}"))
            continue
        if mask.size != t.size:
            outcomes.append(CommitmentOutcome(
                name=c.name, outcome=NOT_EVALUABLE, deviations=(),
                fraction_held=None, longest_deviation_s=0.0,
                relations_suspended=(), suspended_fraction_of_record=0.0,
                reason=(f"the predicate returned {mask.size} values against "
                        f"{t.size} timestamps; a mask that does not align "
                        f"with the timebase cannot place a deviation")))
            continue

        devs = _runs_of_false(mask, t, c.tolerance_s)
        held = float(np.mean(mask))
        longest = max((d.duration_s for d in devs), default=0.0)
        suspended = sum(d.duration_s for d in devs) / span

        if not devs:
            outcome, reason = HELD, "no breach exceeded the declared tolerance"
        elif devs and not devs[-1].recovered:
            outcome = ABANDONED
            reason = ("the commitment did not hold at the end of the record "
                      "and was never re-established")
        else:
            outcome = DEVIATED
            reason = (f"{len(devs)} deviation(s), longest {longest:.3g} s, "
                      f"each re-established")

        outcomes.append(CommitmentOutcome(
            name=c.name, outcome=outcome, deviations=devs,
            fraction_held=held, longest_deviation_s=longest,
            relations_suspended=tuple(c.gates) if devs else (),
            suspended_fraction_of_record=suspended if devs else 0.0,
            reason=reason))

    outcomes = tuple(outcomes)
    thinning: Dict[str, float] = {}
    for o in outcomes:
        for rel in o.relations_suspended:
            thinning[rel] = max(thinning.get(rel, 0.0),
                                o.suspended_fraction_of_record)
    counts = {k: sum(1 for o in outcomes if o.outcome == k) for k in OUTCOMES}
    return IntentReport(
        schema=SCHEMA, outcomes=outcomes,
        relations_suspended_anywhere=tuple(sorted(thinning)),
        evidence_thinning=thinning, counts=counts)
