"""Phase 5 — the capability record. A typed output, not a command.

"FORGE-COMPATIBLE" IS A SCHEMA CLAIM, AND AN UNVERIFIED ONE
------------------------------------------------------------
`forge/README_FUTURE.md` states that no Forge production code exists in this
repository and none may be written before the paper lock is released, and
`tests/test_program_state.py` asserts the directory stays code-free. **No
Forge code was written for this study and nothing was added to `forge/`.**

So "FORGE-compatible" here means exactly one thing: this record is emitted in
a schema a profile-driven consumer such as Forge COULD ingest -- named system
functions, a per-function eligibility state, the limiting domain, and
provenance. **That compatibility is UNVERIFIED**, because there is no Forge
to verify it against, and the write-up must say so rather than implying an
integration that does not exist.

THE VOCABULARY IS v2's, NOT A NEW ONE
--------------------------------------
`csia/v2/functions.py` already defines the eligibility states and the
"which domain is limiting" idea, and the ranking rule that `UNKNOWN`
outranks `INELIGIBLE` because "cannot determine" must not be acted on as
though it were "available". Those are imported, not restated, so this module
cannot drift from them.

WHAT THIS RECORD IS NOT
------------------------
Not a command, not a mode change, not an actuator authority, and not a claim
that any function IS safe. It says what the evidence currently justifies.
The distinction is the entire point: a capability record that says
`INELIGIBLE` is a statement about evidence, not an instruction to land.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from csia.v2.functions import DEGRADED, ELIGIBLE, INELIGIBLE, RANK, UNKNOWN

STATES: Tuple[str, ...] = (ELIGIBLE, DEGRADED, INELIGIBLE, UNKNOWN)

#: The functions this study reasons about. Deliberately few and declared:
#: inventing a function taxonomy here would be a second contribution nobody
#: asked for and nobody validated.
PRECISION_NAV = "precision_navigation"
ATTITUDE_CONTROL = "attitude_control"
STRUCTURAL_MARGIN = "structural_margin"
FUNCTIONS: Tuple[str, ...] = (PRECISION_NAV, ATTITUDE_CONTROL,
                              STRUCTURAL_MARGIN)

#: Which source a function depends on, declared rather than inferred.
REQUIRES: Dict[str, Tuple[str, ...]] = {
    PRECISION_NAV: ("gps", "imu0", "imu1"),
    ATTITUDE_CONTROL: ("imu0", "imu1"),
    STRUCTURAL_MARGIN: ("vibration", "motor_esc"),
}

HAS_ACTUATOR_AUTHORITY = False
FORGE_COMPATIBILITY_VERIFIED = False


@dataclass(frozen=True)
class CapabilityRecord:
    """Per-function eligibility with the limiting domain and provenance."""

    t: float
    states: Dict[str, str]
    limiting: Dict[str, Optional[str]]
    support_status: str
    attribution_status: str
    provenance: str
    map_id: str

    def __post_init__(self):
        bad = [f for f, s in self.states.items() if s not in STATES]
        if bad:
            raise ValueError(f"unknown capability state for {bad}")

    @property
    def most_restricted(self) -> str:
        if not self.states:
            return UNKNOWN
        return max(self.states.values(), key=lambda s: RANK[s])

    @property
    def restricted_functions(self) -> Tuple[str, ...]:
        return tuple(sorted(f for f, s in self.states.items()
                            if s != ELIGIBLE))

    def as_record(self) -> dict:
        return {
            "schema": "csia.hybrid.capability/1",
            "t": round(float(self.t), 6),
            "states": dict(sorted(self.states.items())),
            "limiting": dict(sorted(self.limiting.items())),
            "most_restricted": self.most_restricted,
            "restricted_functions": list(self.restricted_functions),
            "support_status": self.support_status,
            "attribution_status": self.attribution_status,
            "provenance": self.provenance,
            "map_id": self.map_id,
            "has_actuator_authority": HAS_ACTUATOR_AUTHORITY,
            "forge_compatibility_verified": FORGE_COMPATIBILITY_VERIFIED,
            "is_experimental": True,
        }


def derive(*, t: float, support_status: str, attribution_status: str,
           degraded_sources: Tuple[str, ...], map_id: str,
           provenance: str) -> CapabilityRecord:
    """Capability from support, NOT from a confidence score.

    The rule, stated once here so it is not spread across call sites:

    * a function whose required source is degraded AND the attribution is
      SUPPORTED is `INELIGIBLE` -- the evidence both says something is wrong
      and says what;
    * a function whose required source is degraded but the attribution is
      NOT supported is `UNKNOWN`, not `INELIGIBLE`: something is wrong and
      the evidence cannot say what, which is a different state and must not
      be collapsed into the confident one;
    * a function with no degraded requirement but a non-IDENTIFIABLE support
      status is `DEGRADED` -- the system cannot currently rule things out;
    * otherwise `ELIGIBLE`.
    """
    degraded = set(degraded_sources)
    states: Dict[str, str] = {}
    limiting: Dict[str, Optional[str]] = {}
    for fn in FUNCTIONS:
        hit = tuple(sorted(s for s in REQUIRES[fn] if s in degraded))
        if hit and attribution_status == "SUPPORTED":
            states[fn], limiting[fn] = INELIGIBLE, hit[0]
        elif hit:
            states[fn], limiting[fn] = UNKNOWN, hit[0]
        elif support_status != "IDENTIFIABLE":
            states[fn], limiting[fn] = DEGRADED, None
        else:
            states[fn], limiting[fn] = ELIGIBLE, None
    return CapabilityRecord(t=float(t), states=states, limiting=limiting,
                            support_status=support_status,
                            attribution_status=attribution_status,
                            provenance=provenance, map_id=map_id)
