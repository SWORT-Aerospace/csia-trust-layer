"""Support state and a FORGE-compatible capability record, for the physical path.

WHY A SEPARATE SCHEMA FROM `csia_hybrid.support_view`
-------------------------------------------------------
`csia_hybrid.support_view` serves the SIMULATION study: its inputs are
simulated edge gates. This one serves the PHYSICAL path, where the inputs are
bench reads whose semantics are not yet established. The vocabulary is
deliberately identical -- reusing the three states rather than inventing a
fourth -- but the provenance fields differ, and a document from one must not
be mistaken for a document from the other. The schema strings differ for that
reason.

CSIA AND FORGE STAY SEPARATE
------------------------------
The support state is a CSIA conclusion. The capability record is what a
consumer such as Forge could ingest. They are two records, not one, and the
capability record names the support record it rests on.

`forge/README_FUTURE.md` forbids Forge production code in this repository and
`tests/test_program_state.py` enforces it. **No Forge code exists here and
none was written.** `forge_compatibility_verified` is false in every record,
because there is no Forge to verify against.

GATED
-----
While the hardware gates are open every physical support state is
`NON_IDENTIFIABLE` with reason `INPUTS_NOT_ADMISSIBLE`. That is not a
placeholder: a channel whose semantics are unestablished cannot separate two
hypotheses, so the honest state is the one that says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SUPPORT_SCHEMA = "csia.physical.support_state/1"
CAPABILITY_SCHEMA = "csia.physical.capability/1"

IDENTIFIABLE = "IDENTIFIABLE"
AMBIGUOUS = "AMBIGUOUS"
NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
STATES: Tuple[str, ...] = (IDENTIFIABLE, AMBIGUOUS, NON_IDENTIFIABLE)

R_INPUTS_NOT_ADMISSIBLE = "INPUTS_NOT_ADMISSIBLE"
R_NO_ACTIVE_SEPARATOR = "NO_ACTIVE_SEPARATOR"
R_SEPARATED = "SEPARATED"
REASONS: Tuple[str, ...] = (R_INPUTS_NOT_ADMISSIBLE, R_NO_ACTIVE_SEPARATOR,
                            R_SEPARATED)

ELIGIBLE = "ELIGIBLE"
DEGRADED = "DEGRADED"
INELIGIBLE = "INELIGIBLE"
UNKNOWN = "UNKNOWN"
CAPABILITY_STATES: Tuple[str, ...] = (ELIGIBLE, DEGRADED, INELIGIBLE, UNKNOWN)

FORGE_COMPATIBILITY_VERIFIED = False
HAS_ACTUATOR_AUTHORITY = False


class SupportError(ValueError):
    pass


@dataclass(frozen=True)
class PhysicalSupportState:
    """A support conclusion over physical channels, with its provenance."""

    host_monotonic_ns: int
    hypotheses: Tuple[str, ...]
    status: str
    reason: str
    active_channels: Tuple[str, ...]
    inadmissible_channels: Tuple[str, ...]
    derived_from: Tuple[int, ...]
    run_id: str

    def __post_init__(self):
        if self.status not in STATES:
            raise SupportError(f"unknown support status {self.status!r}")
        if self.reason not in REASONS:
            raise SupportError(f"unknown reason {self.reason!r}")
        if self.status == IDENTIFIABLE and self.inadmissible_channels:
            raise SupportError(
                "refusing IDENTIFIABLE while some channel is inadmissible: "
                "a channel whose semantics are unestablished cannot separate "
                "two hypotheses")

    def as_record(self) -> dict:
        return {
            "schema": SUPPORT_SCHEMA,
            "host_monotonic_ns": int(self.host_monotonic_ns),
            "hypotheses": list(self.hypotheses),
            "status": self.status, "reason": self.reason,
            "active_channels": list(self.active_channels),
            "inadmissible_channels": list(self.inadmissible_channels),
            "derived_from": list(self.derived_from),
            "run_id": self.run_id,
            "supports_confident_attribution": self.status == IDENTIFIABLE,
            "has_actuator_authority": HAS_ACTUATOR_AUTHORITY,
            "is_experimental": True,
            "hardware_operated": False,
        }


@dataclass(frozen=True)
class CapabilityRecord:
    """FORGE-COMPATIBLE SCHEMA ONLY. Not a Forge integration, not a command."""

    host_monotonic_ns: int
    states: Dict[str, str]
    limiting: Dict[str, Optional[str]]
    support_status: str
    rests_on_support_at_ns: int
    run_id: str

    def __post_init__(self):
        bad = [f for f, s in self.states.items()
               if s not in CAPABILITY_STATES]
        if bad:
            raise SupportError(f"unknown capability state for {bad}")

    def as_record(self) -> dict:
        return {
            "schema": CAPABILITY_SCHEMA,
            "host_monotonic_ns": int(self.host_monotonic_ns),
            "states": dict(sorted(self.states.items())),
            "limiting": dict(sorted(self.limiting.items())),
            "support_status": self.support_status,
            "rests_on_support_at_ns": int(self.rests_on_support_at_ns),
            "run_id": self.run_id,
            "forge_compatibility_verified": FORGE_COMPATIBILITY_VERIFIED,
            "no_forge_code_exists_in_this_repository": True,
            "has_actuator_authority": HAS_ACTUATOR_AUTHORITY,
            "is_experimental": True,
            "hardware_operated": False,
        }


def gated_support(host_monotonic_ns: int, hypotheses, adapted,
                  run_id: str) -> PhysicalSupportState:
    """The support state while the hardware gates are open.

    Always `NON_IDENTIFIABLE` with `INPUTS_NOT_ADMISSIBLE`, and that is a
    measurement rather than a placeholder: every channel is capped below
    `INFORMATIVE` until the datasheet and inventory gates close, and an
    inadmissible channel cannot tell two hypotheses apart.
    """
    inadmissible = tuple(sorted(a.channel.channel for a in adapted
                                if not a.channel.usable))
    active = tuple(sorted(a.channel.channel for a in adapted
                          if a.channel.usable))
    return PhysicalSupportState(
        host_monotonic_ns=host_monotonic_ns,
        hypotheses=tuple(hypotheses),
        status=NON_IDENTIFIABLE, reason=R_INPUTS_NOT_ADMISSIBLE,
        active_channels=active, inadmissible_channels=inadmissible,
        derived_from=tuple(a.record_id for a in adapted), run_id=run_id)


def capability_from(support: PhysicalSupportState, functions
                    ) -> CapabilityRecord:
    """Capability from support, never from a confidence score.

    While support is `NON_IDENTIFIABLE` for want of admissible inputs, every
    function is `UNKNOWN` -- not `INELIGIBLE`. "We cannot determine this" is
    a different statement from "this is unavailable", and collapsing them
    would let an unverified bench read present as a confident restriction.
    """
    if support.status == IDENTIFIABLE:
        states = {f: ELIGIBLE for f in functions}
        limiting = {f: None for f in functions}
    else:
        states = {f: UNKNOWN for f in functions}
        limiting = {f: support.reason for f in functions}
    return CapabilityRecord(
        host_monotonic_ns=support.host_monotonic_ns, states=states,
        limiting=limiting, support_status=support.status,
        rests_on_support_at_ns=support.host_monotonic_ns,
        run_id=support.run_id)
