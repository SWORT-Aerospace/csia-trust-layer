"""The planner GATE, and a deterministic mock planner to test it with.

THIS IS NOT ZETH
----------------
ZETH is a future evidence-bounded mission-continuation planner. This file is
two much smaller things:

    1. a GATE that a planner's proposed actions must pass
    2. a deterministic MOCK that chooses between predefined benign branches,
       so the gate has something to be tested against

The mock has no search, no optimisation, no model and no learning. It is a
sorted list and an `if`. If it ever grows any of those, it has stopped being
a test fixture and the file name is a lie.

THE ONE RULE THE GATE ENFORCES
-------------------------------
**A planner may READ support state. It may not WRITE it.**

The gate takes capability reports and product results as INPUTS and returns
AUTHORIZED or REJECTED. There is no argument by which a caller can assert
that a capability is supported, no override flag, no force parameter and no
"advisory" mode that proceeds anyway. The absence is structural: a planner
that wanted to override support would have to modify this file, which is a
visible diff and a review.

BAD_PRODUCT_06 in the conformance suite is a planner that overrides a
NOT_SUPPORTED capability. It must be rejected, and it is rejected here rather
than by a downstream check, because a downstream check is one refactor from
being skipped.

WHY DEGRADED_SUPPORTED IS AUTHORIZED AND UNKNOWN IS NOT
---------------------------------------------------------
DEGRADED_SUPPORTED means the capability is established, through a declared
alternative path or with a declared degradation. Evidence exists. UNKNOWN
means nobody knows. Authorizing on UNKNOWN would be authorizing on the
absence of a measurement, which is the failure this entire programme is
about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .capability import (CapabilityReport, DEGRADED_SUPPORTED,
                         NOT_EVALUABLE, SUPPORTED, UNKNOWN)
from .product import (PRODUCT_DEGRADED, PRODUCT_SUPPORTED,
                      ProductAssuranceResult)

AUTHORIZED = "AUTHORIZED"
REJECTED = "REJECTED"

#: The only two capability states that may authorize an action.
AUTHORIZING_STATES = (SUPPORTED, DEGRADED_SUPPORTED)

REJECTION_REASONS = (
    "CAPABILITY_NOT_SUPPORTED",
    "CAPABILITY_UNKNOWN",
    "CAPABILITY_NOT_EVALUABLE",
    "CAPABILITY_NOT_DECLARED",
    "PRODUCT_NOT_SUPPORTED",
    "PRODUCT_NOT_DECLARED",
    "ACTION_NOT_DECLARED",
)


@dataclass(frozen=True)
class MissionAction:
    """A benign action a planner might propose, and what it needs."""
    action_id: str
    requires_capabilities: tuple = ()
    requires_products: tuple = ()
    description: str = ""


@dataclass(frozen=True)
class Authorization:
    action_id: str
    decision: str
    reasons: tuple = ()
    blocking: Mapping[str, str] = field(default_factory=dict)

    @property
    def authorized(self) -> bool:
        return self.decision == AUTHORIZED


def authorize(action: MissionAction,
              capabilities: Mapping[str, CapabilityReport],
              products: Mapping[str, ProductAssuranceResult] | None = None
              ) -> Authorization:
    """The gate. Reads state; cannot change it.

    NOTE THE SIGNATURE. There is no `override`, no `force`, no `advisory`,
    and no way to pass in an asserted capability state. That is the enforcement
    mechanism, not a convention.
    """
    reasons: list = []
    blocking: dict = {}

    for cid in action.requires_capabilities:
        rep = capabilities.get(cid)
        if rep is None:
            reasons.append("CAPABILITY_NOT_DECLARED")
            blocking[cid] = "NOT_DECLARED"
            continue
        if rep.state in AUTHORIZING_STATES:
            continue
        blocking[cid] = rep.state
        if rep.state == UNKNOWN:
            reasons.append("CAPABILITY_UNKNOWN")
        elif rep.state == NOT_EVALUABLE:
            reasons.append("CAPABILITY_NOT_EVALUABLE")
        else:
            reasons.append("CAPABILITY_NOT_SUPPORTED")

    for pid in action.requires_products:
        res = (products or {}).get(pid)
        if res is None:
            reasons.append("PRODUCT_NOT_DECLARED")
            blocking[pid] = "NOT_DECLARED"
            continue
        if res.state not in (PRODUCT_SUPPORTED, PRODUCT_DEGRADED):
            reasons.append("PRODUCT_NOT_SUPPORTED")
            blocking[pid] = res.state

    seen, ordered = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            ordered.append(r)

    return Authorization(
        action_id=action.action_id,
        decision=REJECTED if ordered else AUTHORIZED,
        reasons=tuple(ordered),
        blocking=dict(sorted(blocking.items())),
    )


# ---------------------------------------------------------------------------
# the deterministic mock. NOT a planner.


@dataclass(frozen=True)
class MissionBranch:
    """One predefined benign mission branch."""
    branch_id: str
    actions: tuple
    priority: int
    description: str = ""


class DeterministicTestPlanner:
    """Picks the highest-priority branch whose every action authorizes.

    NO SEARCH. NO OPTIMISATION. NO MODEL. Branches are sorted by (priority,
    branch_id) and the first fully-authorized one wins. The tie-break on
    branch_id is what makes it deterministic rather than merely repeatable on
    one machine.

    It exists to test the GATE. Its choices are not a mission plan and it has
    no authority over anything.
    """

    def __init__(self, branches: Iterable[MissionBranch],
                 actions: Iterable[MissionAction]):
        self.branches = sorted(branches,
                               key=lambda b: (-b.priority, b.branch_id))
        self.actions = {a.action_id: a for a in actions}

    def choose(self, capabilities: Mapping[str, CapabilityReport],
               products: Mapping[str, ProductAssuranceResult] | None = None
               ) -> dict:
        considered = []
        for branch in self.branches:
            auths = []
            for aid in branch.actions:
                action = self.actions.get(aid)
                if action is None:
                    auths.append(Authorization(aid, REJECTED,
                                               ("ACTION_NOT_DECLARED",)))
                    continue
                auths.append(authorize(action, capabilities, products))
            ok = all(a.authorized for a in auths)
            considered.append({
                "branch_id": branch.branch_id,
                "priority": branch.priority,
                "authorized": ok,
                "authorizations": [
                    {"action_id": a.action_id, "decision": a.decision,
                     "reasons": list(a.reasons), "blocking": dict(a.blocking)}
                    for a in auths],
            })
            if ok:
                return {"chosen": branch.branch_id,
                        "considered": considered,
                        "note": "highest-priority fully-authorized branch"}
        return {
            "chosen": None,
            "considered": considered,
            "note": ("NO BRANCH AUTHORIZED. The planner does not proceed with "
                     "a partially-authorized branch, and there is no code "
                     "path by which it could."),
        }


def attempt_override(*_args, **_kwargs):
    """There is no override. This exists so the absence is greppable.

    A reader looking for the escape hatch finds this function, and this
    sentence, rather than finding nothing and assuming they missed it.
    """
    raise PermissionError(
        "A planner may READ support state and may not WRITE it. There is no "
        "override, no force flag and no advisory mode that proceeds anyway. "
        "If an action requires a capability outside the supported set, the "
        "answer is REJECTED and the fix is to establish the evidence, or to "
        "choose a branch that does not need it.")
