"""Phase 5 — the seven baselines, declared in one place.

WHY A REGISTRY AND NOT SEVEN SCRIPTS
-------------------------------------
Every baseline must read the same measurements, the same fault trajectories,
the same onsets, the same seeds and the same horizon. Seven scripts is seven
chances for one of them to drift, and the drift would look like a result.
So the baselines are declared as data here, the campaign runs them from this
declaration, and a test asserts the declared set is exactly the seven the
preregistration names.

THE ABLATION ORDER MATTERS
---------------------------
`B6` is the full staged hybrid and is the only one that combines changes.
`B3`, `B4` and `B5` each introduce exactly one change over `B0`, so an
improvement in `B6` that is absent from all three ablations is unexplained
and the write-up must say so rather than attributing it to the combination.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from csia_consequence.action_adapter import (R_ABSTAIN,  # noqa: F401
                                             R_CAUTION_GENERIC, R_NONE,
                                             RESPONSES, Decision, p0_decide)

B0 = "B0"
B1 = "B1"
B2 = "B2"
B3 = "B3"
B4 = "B4"
B5 = "B5"
B6 = "B6"

#: Responses that assert a specific attribution. Withdrawing one of these is
#: the only thing the support layer is allowed to change.
ATTRIBUTING = ("SELECT_IMU0", "SELECT_IMU1")


@dataclass(frozen=True)
class BaselineSpec:
    id: str
    name: str
    uses_fast_path: bool
    uses_support: bool
    support_map: Optional[str]          # "current" | "corrected" | None
    uses_multiscale: bool
    emits_capability: bool
    #: False for the pure detectors, whose evidence and consequence metrics
    #: are reported N/A rather than as zeros.
    has_policy: bool
    summary: str


SPECS: Tuple[BaselineSpec, ...] = (
    BaselineSpec(B0, "current CSIA", False, False, None, False, False, True,
                 "the frozen trust-persistence detector and the frozen "
                 "failsafe, exactly as Phase 4 ran them"),
    BaselineSpec(B1, "CUSUM", False, False, None, False, False, False,
                 "the repository's own CusumBank, k fixed at 0.5, h swept. "
                 "Page (1954), prior art, not a straw man"),
    BaselineSpec(B2, "bare threshold", False, False, None, False, False,
                 False,
                 "instantaneous lambda over tau, no persistence. Included "
                 "because leaving it out would flatter the other two"),
    BaselineSpec(B3, "fast + current CSIA", True, True, "current", False,
                 False, True,
                 "fast path emits suspicion only; CSIA evaluates support "
                 "with the CURRENT SOURCE_INDICATORS"),
    BaselineSpec(B4, "fast + corrected support map", True, True, "corrected",
                 False, False, True,
                 "as B3, with the FL-029 correction applied outside the "
                 "frozen core"),
    BaselineSpec(B5, "multi-timescale CSIA", False, False, None, True, False,
                 True,
                 "fast, medium and slow accumulators over the same trust "
                 "series; earliest alarm wins and the winning scale is "
                 "recorded"),
    BaselineSpec(B6, "full staged hybrid", True, True, "corrected", True,
                 True, True,
                 "fast provisional detection, CSIA support analysis, and a "
                 "capability record"),
)

BY_ID: Dict[str, BaselineSpec] = {s.id: s for s in SPECS}
DETECTOR_ONLY: Tuple[str, ...] = tuple(s.id for s in SPECS if not s.has_policy)


def hybrid_decide(state, level, actions, *, pair_supported: bool,
                  fast_provisional: bool) -> Decision:
    """The preregistered hybrid rule. The ONLY place it names a response.

    Four steps, in order, from §8a of the preregistration:

    1. start from the frozen failsafe, unmodified;
    2. a provisional fast alarm where the frozen policy issues nothing
       becomes a generic caution -- this is the latency mechanism and the
       only place the hybrid may ADD an action;
    3. an ATTRIBUTING response whose pair is not supported is downgraded to
       a generic caution, **not** to an abstention -- this is the H3
       mechanism and the whole difference from P2, which refused;
    4. a supported attributing response stands unchanged.

    Step 2 is where any added false escalation must come from, and step 3 is
    where false refusals are meant to disappear. Both are measured
    separately so neither can hide inside the other.
    """
    base = p0_decide(state, level, actions)
    response, reason = base.response, "hybrid: frozen failsafe, unmodified"

    if response in ATTRIBUTING and not pair_supported:
        response = R_CAUTION_GENERIC
        reason = ("hybrid: attributing response downgraded to a generic "
                  "caution because the discriminated pair is not supported "
                  "-- a non-attributing ACTION, not an abstention")
    elif response == R_NONE and fast_provisional:
        response = R_CAUTION_GENERIC
        reason = ("hybrid: provisional fast alarm with no frozen-policy "
                  "response; generic caution issued, no attribution claimed")

    if response not in RESPONSES:
        raise ValueError(f"hybrid produced unknown response {response!r}")
    return Decision(response, int(level), None,
                    "SUPPORTED" if pair_supported else "UNSUPPORTED", reason)


def declared_ids() -> Tuple[str, ...]:
    return tuple(s.id for s in SPECS)
