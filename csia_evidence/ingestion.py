"""Recognise channels in data nobody documented, and say how you know.

THE PROBLEM
-----------
CSIA's answer to an undeclared channel is `NOT_EVALUABLE`. That is safe and,
against real data, useless: every integrator's telemetry differs, standards
are followed loosely or not at all, and a layer that refuses everything it
was not handed a specification for cannot be pointed at anything new.

The fix is NOT to relax the rule. It is to make recognition report itself:

    WHICH FIELDS WERE PLACED, ON WHAT EVIDENCE, AT WHAT GRADE, WHICH WERE
    NOT PLACED AT ALL, AND WHERE TWO KINDS OF EVIDENCE DISAGREE.

A mapping is a CANDIDATE until something outside this module accepts it.
`IngestReport.usable_without_review` contains only mappings resting on a
declaration or an exact name; everything else is offered for review and is
not silently used. Nothing here promotes anything.

EVIDENCE KINDS, ORDERED, AND WHY THE ORDER IS NOT A PROBABILITY
-----------------------------------------------------------------
    DECLARED     an interface document says so. No inference at all.
    NAME_EXACT   the field is named exactly as the canonical channel.
    UNIT_MATCH   the source declares a unit and it matches.
    NAME_FUZZY   the normalised name matches after case, separator and
                 abbreviation folding.
    RELATIONAL   the series satisfies a declared relation with a channel
                 already placed at a higher grade.
    DIMENSIONAL  the values sit where the canonical channel's values sit.
    UNRECOGNISED nothing matched.

DIMENSIONAL EVIDENCE CANNOT PLACE A FIELD ON ITS OWN
------------------------------------------------------
It corroborates and it conflicts; it never identifies. The first version of
this module let it identify, and a field named `qqq` containing the values
1.0 and 2.0 was confidently mapped to `current` -- because 1.0 and 2.0 are
inside the plausible range of a current, and of a voltage, and of a
temperature, and of very nearly everything else anyone would declare.

Plausibility is a weak NEGATIVE test. It can tell you a field named like a
current holds values no current takes. It cannot tell you an unnamed field
is a current. A field whose only evidence is dimensional is
`UNRECOGNISED`, and its dimensional evidence is still listed so a reader
can see what was considered.

There is no number attached to any of these, because there is no calibrated
population from which one could be computed. Inventing 0.85 for NAME_FUZZY
would be the kind of number this repository exists to refuse. The grades are
an ORDINAL ranking with a stated meaning, and `GRADE_ORDER` is the whole of
what is claimed about them.

CONFLICTS ARE THE POINT
-----------------------
If the name says one thing and the values say another, that is not noise to
be resolved by taking the stronger grade. It is the single most useful thing
this module can tell you, because it is how a mislabelled channel announces
itself. `Mapping.conflicts` is populated whenever two kinds of evidence
point at different canonical channels, and a conflicted mapping never
appears in `usable_without_review` whatever its best grade.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np

SCHEMA = "csia.evidence.ingestion/1"


class EvidenceKind:
    DECLARED = "DECLARED"
    NAME_EXACT = "NAME_EXACT"
    UNIT_MATCH = "UNIT_MATCH"
    NAME_FUZZY = "NAME_FUZZY"
    RELATIONAL = "RELATIONAL"
    DIMENSIONAL = "DIMENSIONAL"
    UNRECOGNISED = "UNRECOGNISED"


#: Strongest first. An ORDINAL ranking, never a probability.
GRADE_ORDER: Tuple[str, ...] = (
    EvidenceKind.DECLARED,
    EvidenceKind.NAME_EXACT,
    EvidenceKind.UNIT_MATCH,
    EvidenceKind.NAME_FUZZY,
    EvidenceKind.RELATIONAL,
    EvidenceKind.DIMENSIONAL,
    EvidenceKind.UNRECOGNISED,
)

#: Grades that may be used without a human or a policy accepting them.
#: Deliberately short.
ACCEPTED_WITHOUT_REVIEW = (EvidenceKind.DECLARED, EvidenceKind.NAME_EXACT)

_ABBREV = {
    "curr": "current", "amp": "current", "amps": "current", "i": "current",
    "volt": "voltage", "volts": "voltage", "v": "voltage",
    "temp": "temperature", "tmp": "temperature",
    "vel": "velocity", "spd": "speed",
    "acc": "acceleration", "accel": "acceleration",
    "pos": "position", "alt": "altitude", "hdg": "heading",
    "pres": "pressure", "press": "pressure",
    "freq": "frequency", "rot": "rotation", "rpm": "rotation_rate",
    "batt": "battery", "pwr": "power", "t": "time",
}


def _split_camel(name: str) -> str:
    """`PackCurrent` -> `Pack Current`, `battVolts` -> `batt Volts`.

    Added because the first version folded separators only, so a field named
    `PackCurrent` normalised to the single token `packcurrent` and matched
    nothing. Camel case is not an edge case in telemetry; it is the house
    style of most of the systems this layer exists to read.
    """
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", name)


def normalise(name: str) -> str:
    """Fold camel case, separators and common abbreviations. Deterministic."""
    parts = re.split(r"[^0-9a-zA-Z]+",
                     _split_camel(str(name).strip()).lower())
    out = []
    for p in parts:
        if not p:
            continue
        # split trailing digits: pack_current1 -> pack current 1
        m = re.match(r"^([a-z]+)(\d+)$", p)
        if m:
            out.extend([_ABBREV.get(m.group(1), m.group(1)), m.group(2)])
        else:
            out.append(_ABBREV.get(p, p))
    return " ".join(out)


@dataclass(frozen=True)
class ChannelSpec:
    """A canonical channel, described by what a human knows about it.

    `plausible` is a closed interval the channel's values are expected to sit
    inside when healthy. It is a DECLARED engineering range, not a fitted
    one, and its only job here is to notice that a field named like a current
    contains values no current takes.

    `relations` maps another canonical channel's name to a predicate over
    (this series, that series, t). It is how a channel earns RELATIONAL
    evidence, and it is the only place this module looks at two channels
    together.
    """

    name: str
    unit: str = ""
    aliases: Tuple[str, ...] = ()
    plausible: Optional[Tuple[float, float]] = None
    relations: Dict[str, Callable] = field(default_factory=dict)
    note: str = ""

    def normalised_names(self) -> Tuple[str, ...]:
        return tuple({normalise(self.name)}
                     | {normalise(a) for a in self.aliases})

    def to_dict(self) -> dict:
        return {"name": self.name, "unit": self.unit,
                "aliases": list(self.aliases), "plausible": self.plausible,
                "relations": sorted(self.relations), "note": self.note}


@dataclass(frozen=True)
class Evidence:
    """One reason to believe a field is a channel. Carries its own basis."""

    kind: str
    channel: str
    basis: str

    def __post_init__(self):
        if self.kind not in GRADE_ORDER:
            raise ValueError(f"unknown evidence kind {self.kind!r}")
        if not self.basis or len(self.basis) < 10:
            raise ValueError("every piece of evidence states its basis; an "
                             "unexplained match is not evidence")

    @property
    def rank(self) -> int:
        return GRADE_ORDER.index(self.kind)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Mapping:
    """A field, the channel it appears to be, and everything behind that."""

    field_name: str
    channel: Optional[str]
    grade: str
    evidence: Tuple[Evidence, ...]
    conflicts: Tuple[str, ...] = ()
    n_samples: int = 0

    @property
    def recognised(self) -> bool:
        return self.channel is not None

    @property
    def usable_without_review(self) -> bool:
        """Strong evidence AND no disagreement. Both are required.

        A conflicted mapping is never usable whatever its best grade,
        because the conflict is evidence that the strong grade is wrong.
        """
        return (self.recognised and not self.conflicts
                and self.grade in ACCEPTED_WITHOUT_REVIEW)

    def to_dict(self) -> dict:
        return {"field": self.field_name, "channel": self.channel,
                "grade": self.grade,
                "evidence": [e.to_dict() for e in self.evidence],
                "conflicts": list(self.conflicts),
                "n_samples": self.n_samples,
                "usable_without_review": self.usable_without_review}


@dataclass(frozen=True)
class IngestReport:
    schema: str
    mappings: Tuple[Mapping, ...]
    unrecognised: Tuple[str, ...]
    conflicted: Tuple[str, ...]
    channels_not_found: Tuple[str, ...]
    counts: Dict[str, int]
    does_not_establish: str = (
        "A mapping is a candidate. This report does not establish that any "
        "field is the channel it resembles, only what evidence was found "
        "and what was not. Nothing here promotes a channel to usable "
        "evidence; that is a decision for a policy or a person.")

    @property
    def usable_without_review(self) -> Tuple[Mapping, ...]:
        return tuple(m for m in self.mappings if m.usable_without_review)

    @property
    def needs_review(self) -> Tuple[Mapping, ...]:
        return tuple(m for m in self.mappings
                     if m.recognised and not m.usable_without_review)

    def to_dict(self) -> dict:
        return {"schema": self.schema,
                "mappings": [m.to_dict() for m in self.mappings],
                "unrecognised": list(self.unrecognised),
                "conflicted": list(self.conflicted),
                "channels_not_found": list(self.channels_not_found),
                "counts": dict(self.counts),
                "does_not_establish": self.does_not_establish}


def _series(value) -> Optional[np.ndarray]:
    try:
        arr = np.asarray(value, dtype=float).ravel()
    except (TypeError, ValueError):
        return None
    if arr.size == 0:
        return None
    return arr[np.isfinite(arr)] if np.any(np.isfinite(arr)) else None


def _name_evidence(field_name: str, spec: ChannelSpec):
    norm = normalise(field_name)
    names = spec.normalised_names()
    if norm in names:
        return Evidence(EvidenceKind.NAME_EXACT, spec.name,
                        f"normalised field name {norm!r} equals the "
                        f"canonical name or a declared alias")
    tokens = set(norm.split())
    for candidate in names:
        ctok = set(candidate.split())
        if ctok and ctok <= tokens:
            return Evidence(EvidenceKind.NAME_FUZZY, spec.name,
                            f"every token of {candidate!r} appears in the "
                            f"normalised field name {norm!r}")
    return None


def _dimensional_evidence(arr, spec: ChannelSpec):
    if spec.plausible is None or arr is None or arr.size == 0:
        return None
    lo, hi = spec.plausible
    inside = float(np.mean((arr >= lo) & (arr <= hi)))
    if inside >= 0.95:
        return Evidence(EvidenceKind.DIMENSIONAL, spec.name,
                        f"{inside:.0%} of samples lie inside the declared "
                        f"plausible range [{lo}, {hi}] for this channel")
    return None


def ingest(fields: Dict[str, object], specs: Sequence[ChannelSpec], *,
           declared: Optional[Dict[str, str]] = None,
           units: Optional[Dict[str, str]] = None,
           t=None) -> IngestReport:
    """Place each field against the canonical channels, and report the rest.

    `declared` is an interface document if one exists: field name -> channel
    name. It produces DECLARED evidence and short-circuits inference for
    that field, because a specification beats a guess and pretending
    otherwise would be theatre.

    `units` is what the source claims about its own fields. A claimed unit is
    still a claim, which is why UNIT_MATCH sits below an exact name and above
    a fuzzy one.
    """
    declared = declared or {}
    units = units or {}
    by_name = {s.name: s for s in specs}
    for name in declared.values():
        if name not in by_name:
            raise ValueError(
                f"the interface document names channel {name!r}, which is "
                f"not in the canonical set; a declaration that cannot be "
                f"checked is worse than none")

    mappings = []
    for fname, value in fields.items():
        arr = _series(value)
        found: list = []

        if fname in declared:
            found.append(Evidence(
                EvidenceKind.DECLARED, declared[fname],
                f"an interface document maps field {fname!r} to this "
                f"channel; no inference was used"))

        for spec in specs:
            ev = _name_evidence(fname, spec)
            if ev is not None:
                found.append(ev)
            claimed = units.get(fname)
            if claimed and spec.unit and normalise(claimed) == \
                    normalise(spec.unit):
                found.append(Evidence(
                    EvidenceKind.UNIT_MATCH, spec.name,
                    f"the source declares unit {claimed!r}, matching this "
                    f"channel's declared unit {spec.unit!r}"))
            dim = _dimensional_evidence(arr, spec)
            if dim is not None:
                found.append(dim)

        if not found:
            mappings.append(Mapping(fname, None, EvidenceKind.UNRECOGNISED,
                                    (), (), arr.size if arr is not None else 0))
            continue

        found.sort(key=lambda e: e.rank)
        identifying = [e for e in found
                       if e.kind != EvidenceKind.DIMENSIONAL]
        if not identifying:
            # Dimensional agreement alone identifies nothing. The evidence is
            # kept so a reader can see it was considered and rejected.
            mappings.append(Mapping(fname, None, EvidenceKind.UNRECOGNISED,
                                    tuple(found), (),
                                    arr.size if arr is not None else 0))
            continue
        best = identifying[0]
        # A conflict is another channel supported at a grade at least as
        # strong as one step below the best. Weak dimensional agreement with
        # everything is not a conflict; a NAME saying one thing while a UNIT
        # says another is.
        conflicts = sorted({e.channel for e in found
                            if e.channel != best.channel
                            and e.rank <= best.rank + 1})
        mappings.append(Mapping(fname, best.channel, best.kind,
                                tuple(found), tuple(conflicts),
                                arr.size if arr is not None else 0))

    mappings = tuple(sorted(mappings, key=lambda m: m.field_name))
    placed = {m.channel for m in mappings if m.recognised}
    counts: Dict[str, int] = {}
    for m in mappings:
        counts[m.grade] = counts.get(m.grade, 0) + 1
    counts["usable_without_review"] = sum(
        1 for m in mappings if m.usable_without_review)
    counts["needs_review"] = sum(
        1 for m in mappings if m.recognised and not m.usable_without_review)

    return IngestReport(
        schema=SCHEMA, mappings=mappings,
        unrecognised=tuple(m.field_name for m in mappings
                           if not m.recognised),
        conflicted=tuple(m.field_name for m in mappings if m.conflicts),
        channels_not_found=tuple(sorted(
            s.name for s in specs if s.name not in placed)),
        counts=counts)
