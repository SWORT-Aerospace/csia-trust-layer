"""Fault and ground-truth annotation, and run-level wall time. SIDECAR ONLY.

THE SEPARATION THIS FILE EXISTS TO ENFORCE
--------------------------------------------
A raw log is what the controller said. An annotation is what the operator
believes. They are different kinds of statement and they get different files:

    <run>.jsonl            immutable, append-only, controller output only
    <run>.annotations.json operator claims, written separately, joined late

Writing "fault injected at 12.4 s" into the raw stream would turn an
immutable record of measurement into a mutable record of belief, and a reader
could no longer recover what the hardware reported without what the operator
thought was happening to it. The raw log is byte-identical whether or not
anybody ever annotates it, and a test asserts that.

GROUND TRUTH IS A CLAIM, AND IS LABELLED AS ONE
-------------------------------------------------
`GroundTruth.basis` is required and has no default. "Channel 3 is the faulty
one" is only as good as the reason for saying so -- an operator who
disconnected it knows; an operator inferring it from the data is reasoning in
a circle, because the data is what is being evaluated. The permitted bases
say which it was.

WALL TIME
---------
`csia_e2m.logging` records monotonic nanoseconds per record and states why:
the wall clock can step backwards under NTP mid-run. That is not reversed.
Wall time is recorded ONCE per run, here, as the operator-facing anchor that
says which afternoon a run happened on. Every intra-run interval is still
computed from the monotonic clock, and a test asserts no per-record wall
timestamp is ever emitted.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ANNOTATION_SCHEMA = "csia.physical.run_annotation/1"

#: How the operator knows the ground truth. Required, no default: an
#: inference from the data under test is not the same claim as having
#: unplugged the wire, and the write-up must be able to tell them apart.
BASIS_OPERATOR_ACTION = "OPERATOR_PHYSICAL_ACTION"
BASIS_INSTRUMENTED = "INDEPENDENT_INSTRUMENT"
BASIS_DESIGNED_SCENARIO = "DESIGNED_SCENARIO"
BASIS_INFERRED = "INFERRED_FROM_DATA_UNDER_TEST"
BASES: Tuple[str, ...] = (BASIS_OPERATOR_ACTION, BASIS_INSTRUMENTED,
                          BASIS_DESIGNED_SCENARIO, BASIS_INFERRED)

#: Bases that do NOT independently establish ground truth. Kept so a
#: consumer can weight them rather than discovering the problem in prose.
CIRCULAR_BASES: Tuple[str, ...] = (BASIS_INFERRED,)


class AnnotationError(ValueError):
    """The annotation is not a statement this file will record."""


@dataclass(frozen=True)
class FaultAnnotation:
    """One fault the operator says they injected.

    Times are MONOTONIC nanoseconds, on the same clock as the raw log, so an
    annotation can be joined to records without a clock conversion that could
    silently drift.
    """

    label: str
    start_host_ns: int
    end_host_ns: Optional[int]
    target: str
    method: str
    injected_by: str

    def __post_init__(self):
        if not self.label:
            raise AnnotationError("a fault annotation needs a label")
        if self.end_host_ns is not None and \
                self.end_host_ns < self.start_host_ns:
            raise AnnotationError(
                f"{self.label}: end {self.end_host_ns} precedes start "
                f"{self.start_host_ns}")
        if not self.method:
            raise AnnotationError(
                f"{self.label}: `method` is required -- how the fault was "
                "injected is part of what makes it reproducible")

    def covers(self, host_ns: int) -> bool:
        if host_ns < self.start_host_ns:
            return False
        return self.end_host_ns is None or host_ns <= self.end_host_ns

    def as_dict(self) -> dict:
        return {"label": self.label, "start_host_ns": int(self.start_host_ns),
                "end_host_ns": (None if self.end_host_ns is None
                                else int(self.end_host_ns)),
                "target": self.target, "method": self.method,
                "injected_by": self.injected_by}


@dataclass(frozen=True)
class GroundTruth:
    """What the operator says was actually true, and how they know."""

    statement: str
    basis: str
    detail: str = ""

    def __post_init__(self):
        if self.basis not in BASES:
            raise AnnotationError(
                f"unknown ground-truth basis {self.basis!r}; permitted: "
                f"{BASES}")
        if not self.statement:
            raise AnnotationError("a ground truth needs a statement")

    @property
    def is_independent(self) -> bool:
        """False when the basis is an inference from the data under test."""
        return self.basis not in CIRCULAR_BASES

    def as_dict(self) -> dict:
        return {"statement": self.statement, "basis": self.basis,
                "detail": self.detail,
                "is_independent": self.is_independent}


@dataclass
class RunAnnotation:
    """Everything the operator asserts about one run. Never the raw log."""

    run_id: str
    experiment: str
    #: Wall time is recorded ONCE, here, and never per record.
    wall_start_utc: str
    operator: str
    hardware_operated: bool = False
    faults: List[FaultAnnotation] = field(default_factory=list)
    ground_truth: List[GroundTruth] = field(default_factory=list)
    notes: str = ""

    def fault_at(self, host_ns: int) -> Optional[FaultAnnotation]:
        for f in self.faults:
            if f.covers(host_ns):
                return f
        return None

    def as_dict(self) -> dict:
        return {
            "schema": ANNOTATION_SCHEMA,
            "run_id": self.run_id,
            "experiment": self.experiment,
            "wall_start_utc": self.wall_start_utc,
            "wall_time_is_run_level_only": True,
            "operator": self.operator,
            "hardware_operated": bool(self.hardware_operated),
            "faults": [f.as_dict() for f in self.faults],
            "ground_truth": [g.as_dict() for g in self.ground_truth],
            "ground_truth_all_independent": all(
                g.is_independent for g in self.ground_truth),
            "notes": self.notes,
            "is_operator_claim_not_controller_output": True,
        }

    def write(self, path: pathlib.Path) -> pathlib.Path:
        path = pathlib.Path(path)
        if path.exists():
            raise AnnotationError(
                f"{path} exists; annotations are not overwritten")
        path.write_text(json.dumps(self.as_dict(), indent=1, sort_keys=True)
                        + "\n", encoding="utf-8")
        return path


def load(path: pathlib.Path) -> dict:
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != ANNOTATION_SCHEMA:
        raise AnnotationError(f"not a {ANNOTATION_SCHEMA} document")
    return doc


def annotation_path(log_path: pathlib.Path) -> pathlib.Path:
    """The sidecar beside a raw log, never the log itself."""
    log_path = pathlib.Path(log_path)
    return log_path.with_suffix(log_path.suffix + ".annotations.json")
