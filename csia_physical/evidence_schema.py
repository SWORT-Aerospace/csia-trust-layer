"""Derived evidence, kept strictly separate from raw observation.

THE SEPARATION
--------------
An observation is what a device reported. Evidence is what somebody
CONCLUDED from one or more observations. They are different kinds of claim
and they live in different documents:

    raw log            what the controller said           immutable
    annotation sidecar what the operator believes         separate file
    evidence document  what was derived from the above    separate file

An evidence record therefore carries `derived_from`: the record ids it rests
on. A derived quantity with no traceable inputs is an assertion, and this
schema has no field in which to make one -- `derived_from` has no default.

WHAT IT MAY NOT CONTAIN
-----------------------
No support state and no capability state. Those are further derivations and
live in `support_schema.py`, because collapsing "this edge disagrees" into
"this function is ineligible" in one record would make the inference
unauditable.

GATED
-----
Every record carries `inputs_admissible`, which is false while the channels
it rests on are capped below `INFORMATIVE` -- and they are, because the
hardware gates are open. Evidence derived from inadmissible inputs is
recorded and is **not** promoted to a finding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

EVIDENCE_SCHEMA = "csia.physical.evidence/1"

AGREE = "AGREE"
DISAGREE = "DISAGREE"
INDETERMINATE = "INDETERMINATE"
OUTCOMES: Tuple[str, ...] = (AGREE, DISAGREE, INDETERMINATE)


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceRecord:
    """One derived comparison, with the records it was derived from."""

    relation: str
    outcome: str
    host_monotonic_ns: int
    derived_from: Tuple[int, ...]
    inputs_admissible: bool
    detail: Dict = field(default_factory=dict)
    note: str = ""

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise EvidenceError(f"unknown outcome {self.outcome!r}")
        if not self.derived_from:
            raise EvidenceError(
                f"{self.relation}: evidence with no `derived_from` is an "
                "assertion, not a derivation")
        if self.outcome != INDETERMINATE and not self.inputs_admissible:
            raise EvidenceError(
                f"{self.relation}: refusing to record {self.outcome} from "
                "inadmissible inputs; the only honest outcome while the "
                "hardware gates are open is INDETERMINATE")

    def as_record(self) -> dict:
        return {
            "schema": EVIDENCE_SCHEMA,
            "relation": self.relation,
            "outcome": self.outcome,
            "host_monotonic_ns": int(self.host_monotonic_ns),
            "derived_from": list(self.derived_from),
            "inputs_admissible": bool(self.inputs_admissible),
            "detail": dict(self.detail),
            "note": self.note,
            "is_derived_not_observed": True,
            "is_experimental": True,
            "hardware_operated": False,
        }


def indeterminate(relation: str, host_monotonic_ns: int,
                  derived_from, why: str) -> EvidenceRecord:
    """The only outcome available while the inputs are not admissible."""
    return EvidenceRecord(relation=relation, outcome=INDETERMINATE,
                          host_monotonic_ns=host_monotonic_ns,
                          derived_from=tuple(derived_from),
                          inputs_admissible=False, note=why)


def document(records: List[EvidenceRecord], *, run_id: str,
             experiment: str) -> dict:
    return {
        "schema": "csia.physical.evidence_document/1",
        "run_id": run_id,
        "experiment": experiment,
        "records": [r.as_record() for r in records],
        "count": len(records),
        "any_admissible": any(r.inputs_admissible for r in records),
        "raw_observations_are_in_a_separate_file": True,
        "is_experimental": True,
        "hardware_operated": False,
    }
