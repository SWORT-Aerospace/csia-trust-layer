"""Structured reason codes — Phase 4 §19.

`engineering/v1_1/REASON_CODES.yaml` is the single source of truth. This
module loads it; it does not restate it. A test fails if the eligibility
policy or the ledger ever emits a code the table does not define, so a new
code cannot reach a flight record without also reaching the table.

Prose is rendered FROM a code and is never canonical. `render()` exists so an
operator display can be human-readable without the log becoming prose.
"""

from __future__ import annotations

import functools
import os

import yaml

_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "engineering", "v1_1", "REASON_CODES.yaml")

#: The four eligibility states. `UNKNOWN` here is an ELIGIBILITY state and is
#: deliberately not the unmodeled-fault hypothesis, which remains NOT
#: IMPLEMENTED. They never share a field.
ELIGIBLE = "ELIGIBLE"
DEGRADED = "DEGRADED"
INELIGIBLE = "INELIGIBLE"
UNKNOWN = "UNKNOWN"

STATES = (ELIGIBLE, DEGRADED, INELIGIBLE, UNKNOWN)

#: Ordering used ONLY for dwell and for combining several fired codes into one
#: state. More restrictive is higher. `UNKNOWN` ranks above `INELIGIBLE`
#: because "cannot determine" must not be acted on as if it were "available".
SEVERITY_RANK = {ELIGIBLE: 0, DEGRADED: 1, INELIGIBLE: 2, UNKNOWN: 3}


@functools.lru_cache(maxsize=4)
def load(path: str | None = None) -> dict:
    with open(path or _DEFAULT, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def eligibility_codes(path: str | None = None) -> dict:
    return load(path)["eligibility"]


def ledger_event_types(path: str | None = None) -> tuple:
    return tuple(sorted(load(path)["ledger_events"]))


def severity_of(code: str, support_policy: str | None = None,
                path: str | None = None) -> str:
    """The state `code` forces.

    `POLICY` severity defers to the function's declared `support_policy`,
    because the same evidence means different things to a function that
    assumes its position is correct and one that does not.
    """
    sev = eligibility_codes(path)[code]["severity"]
    if sev != "POLICY":
        return sev
    if support_policy == "REQUIRE_IDENTIFIABLE":
        return INELIGIBLE
    if support_policy == "TOLERATE_AMBIGUITY":
        return DEGRADED
    raise ValueError(f"{code} needs a support_policy; got {support_policy!r}")


def render(code: str, path: str | None = None, **fields) -> str:
    """Human-readable line for a code. Never stored as canonical evidence."""
    tpl = eligibility_codes(path)[code]["render"]
    try:
        return tpl.format(**fields)
    except KeyError:
        return tpl


def worst(states) -> str:
    """Combine fired states. Empty means every requirement was met."""
    states = list(states)
    if not states:
        return ELIGIBLE
    return max(states, key=lambda s: SEVERITY_RANK[s])
