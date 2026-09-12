"""The versioned request/response, and the invariant it must not break.

THE INVARIANT
-------------
`csia/contracts/validate.py` refuses any CSIA trust contract whose
`authorization.active_action_prohibited` is not literally True, and
`csia/deploy/guard.py` enforces at four layers that CSIA reaches no transmit
path. Active evidence acquisition does not relax either, and this file is
where that is made checkable rather than promised:

    `ACTIVE_ACTION_PROHIBITED = True` and `AUTHORITY = "REQUEST_ONLY"` are
    stamped into every episode document, and `tests/test_active_evidence.py`
    asserts that no module in this package imports pymavlink, opens a
    socket, or calls anything named send.

A `ProbeEpisode` is a RECORD OF A DECISION, not a means of carrying it out.
It contains no callable, no connection and no handle. Producing one changes
nothing about any vehicle; something outside CSIA reads it and decides.

WHAT AN EPISODE IS FOR
----------------------
It is the auditable unit. A reader with the episode alone can reconstruct:
what was ambiguous, what change would have separated the hypotheses, which
probe was asked for and on what grounds, what the independent authorizer
said and why, what was actually executed if anything, and what the
hypothesis set was before and after. Every one of those is a separate field,
because a single "outcome" field is how a refusal and a null result come to
look the same in a log.

THE STOPPING RULE
-----------------
`should_stop` is the auditable termination condition, and it is evaluated
from recorded facts rather than from a budget counter that a caller could
reset. An episode sequence stops when the hypothesis set is resolved, when
no probe in the library can separate what remains, when the authorizer has
refused, when the model has been falsified, or when the declared attempt
limit is reached. Each returns its own reason string; "stopped" on its own
is not an answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple

SCHEMA = "csia.active_evidence.episode/1"
SEMANTICS_VERSION = "csia.active_evidence.semantics/1"

#: Not a comment. Stamped into every episode and asserted by a test.
ACTIVE_ACTION_PROHIBITED = True
AUTHORITY = "REQUEST_ONLY"

STOP_RESOLVED = "STOPPED_HYPOTHESIS_SET_RESOLVED"
STOP_NO_PROBE = "STOPPED_NO_PROBE_CAN_SEPARATE_WHAT_REMAINS"
STOP_REFUSED = "STOPPED_AUTHORIZER_REFUSED"
STOP_MODEL = "STOPPED_MODEL_FALSIFIED_BY_MEASUREMENT"
STOP_BUDGET = "STOPPED_ATTEMPT_LIMIT_REACHED"
CONTINUE = "CONTINUE"
STOP_REASONS = (STOP_RESOLVED, STOP_NO_PROBE, STOP_REFUSED, STOP_MODEL,
                STOP_BUDGET)


@dataclass(frozen=True)
class ProbeEpisode:
    """One complete request-decide-observe-update cycle, as a record."""

    episode_id: str
    ambiguity: dict              # what was non-identifiable, and how known
    requirement: dict            # the inverted excitation requirement
    selection: dict              # selector verdict, ranking and rejections
    request: Optional[dict]      # None when no probe was requested
    authorization: Optional[dict]
    executed: Optional[dict]     # the probe AS RUN, with measured statistics
    update: Optional[dict]       # the set-valued hypothesis update
    stop: str
    schema: str = SCHEMA
    semantics_version: str = SEMANTICS_VERSION
    active_action_prohibited: bool = ACTIVE_ACTION_PROHIBITED
    authority: str = AUTHORITY
    what_this_does_not_establish: str = (
        "Nothing here has run on a vehicle. The authorizer is a "
        "deterministic mock of a decision a flight-envelope owner would "
        "make, the noise model is a declared set of commissioning numbers, "
        "and the identifiability prediction is a local linear analysis of "
        "one relation. This is not a safety argument and not a certified "
        "artifact.")

    def __post_init__(self):
        if self.stop not in STOP_REASONS + (CONTINUE,):
            raise ValueError(f"stop must be one of {STOP_REASONS + (CONTINUE,)}")
        if self.active_action_prohibited is not True:
            raise ValueError(
                "active_action_prohibited is the invariant this package is "
                "built under; an episode that sets it False is not a CSIA "
                "episode. See csia/contracts/validate.py")
        if self.authority != AUTHORITY:
            raise ValueError(f"authority must be {AUTHORITY!r}")

    def to_dict(self) -> dict:
        return asdict(self)


def should_stop(*, surviving: Tuple[str, ...], selection_verdict: str,
                authorization_verdict: Optional[str], model_falsified: bool,
                attempts: int, attempt_limit: int) -> str:
    """The stopping rule. Ordered, and every branch names itself.

    Order matters and is declared: a falsified model stops everything,
    because continuing to probe against a model the measurement has already
    contradicted produces more numbers and no more knowledge.
    """
    if model_falsified:
        return STOP_MODEL
    if len(surviving) <= 1:
        return STOP_RESOLVED
    if selection_verdict == "NO_PROBE_MEETS_THE_REQUIREMENT":
        return STOP_NO_PROBE
    if authorization_verdict == "DENY":
        return STOP_REFUSED
    if attempts >= attempt_limit:
        return STOP_BUDGET
    return CONTINUE
