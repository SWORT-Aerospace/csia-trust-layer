"""Evidence-preserving reconfiguration analysis. DESIGN-TIME, EXPERIMENTAL.

THE QUESTION
------------
A reconfiguration R takes the vehicle from configuration A to configuration
B. Which evidence does that destroy, which does it create, and -- the part
that matters --

    does R destroy the very evidence needed to justify the capability
    R is being performed in order to establish?

Call that a SELF-OCCLUDING RECONFIGURATION. A hypothetical: stowing the
camera to reduce drag, in order to extend endurance, when the camera is the
only evidence source for the visual navigation the endurance plan depends on.
After the stow there is no way to establish the capability the stow was for.

STATUS, STATED FIRST BECAUSE IT IS EASY TO OVERSTATE
------------------------------------------------------
    EXPERIMENTAL
    POSSIBLE_RESEARCH_CONTRIBUTION
    NOVELTY_NOT_ESTABLISHED

No literature search has been done for this. It resembles observability
analysis, resembles reconfigurable-systems FDI work, and may well be a known
result under a name this repository has not looked for. **It is not in Paper
I and no priority is claimed.** `docs/mission/NOVELTY_CLASSIFICATION.md`
carries the same three lines.

DESIGN TIME, NOT RUN TIME
--------------------------
This analyses DECLARED configurations. It runs on contracts and profiles, not
on telemetry, and it decides nothing in flight. A run-time version would be a
different thing with different obligations, and calling this one that would
be the overstatement.

WHAT IT CANNOT SEE
------------------
It reasons over DECLARED evidence sets. If configuration B would in fact
produce evidence its profile does not declare, this will report that evidence
as lost -- a false alarm. The opposite error is the one that matters and it
cannot make it: it never reports evidence as available that no profile
declares.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .capability import CapabilityContract

STATUS = "EXPERIMENTAL"
NOVELTY = "NOVELTY_NOT_ESTABLISHED"

SELF_OCCLUDING = "SELF_OCCLUDING_RECONFIGURATION"
EVIDENCE_PRESERVING = "EVIDENCE_PRESERVING"
EVIDENCE_REDUCING = "EVIDENCE_REDUCING"
EVIDENCE_INCREASING = "EVIDENCE_INCREASING"


@dataclass(frozen=True)
class Configuration:
    """A declared vehicle/payload configuration and what it provides."""
    config_id: str
    provides_evidence: frozenset
    description: str = ""

    @staticmethod
    def of(config_id: str, evidence: Iterable[str], description: str = ""):
        return Configuration(config_id, frozenset(evidence), description)


def _satisfiable(contract: CapabilityContract, available: frozenset,
                 by_id: Mapping[str, CapabilityContract] | None = None,
                 _seen: frozenset = frozenset()) -> bool:
    """Could this capability be established from `available` alone?

    TRANSITIVE OVER SUBORDINATE CAPABILITIES, and the first version was not
    (MX-005). It checked only the direct evidence requirements, so a
    capability whose requirements are ENTIRELY subordinate capabilities --
    `local_mapping` requires `relative_navigation` and `RGB_capture` and no
    evidence of its own -- came out satisfiable in every configuration,
    including ones that removed the camera it depends on. The analyser then
    reported the camera stow as not self-occluding for local mapping, which
    is exactly wrong.

    A capability with no direct evidence requirements is not a capability
    with no requirements. Following the chain is the difference between an
    analysis and a spot check.

    Only EVIDENCE is considered at the leaves. Compute, timing and actuator
    state are run-time facts and this is a design-time analysis; including
    them would mean answering a question the inputs cannot support.

    A cycle returns False -- fail closed. A capability that depends on itself
    cannot be established from evidence by any order of resolution, and
    guessing an order would be inventing an answer.
    """
    if contract.capability_id in _seen:
        return False
    if not set(contract.requires_all) <= available:
        return False
    for group in contract.requires_one_of:
        options = set(group if isinstance(group, (list, tuple)) else [group])
        if not (options & available):
            return False

    for cid in contract.requires_capabilities:
        sub = (by_id or {}).get(cid)
        if sub is None:
            # A subordinate with no contract cannot be shown satisfiable.
            # Returning True here would let an unmodelled dependency vanish.
            return False
        if not _satisfiable(sub, available, by_id,
                            _seen | {contract.capability_id}):
            return False
    return True


def _transitive_evidence(contract: CapabilityContract,
                         by_id: Mapping[str, CapabilityContract],
                         _seen: frozenset = frozenset()) -> set:
    """Every evidence id a capability rests on, following subordinates."""
    if contract.capability_id in _seen:
        return set()
    out = set(contract.requires_all)
    for g in contract.requires_one_of:
        out |= set(g if isinstance(g, (list, tuple)) else [g])
    for cid in contract.requires_capabilities:
        sub = by_id.get(cid)
        if sub is not None:
            out |= _transitive_evidence(sub, by_id,
                                        _seen | {contract.capability_id})
    return out


def analyse_transition(from_config: Configuration,
                       to_config: Configuration,
                       contracts: Iterable[CapabilityContract],
                       intended_capability: str | None = None) -> dict:
    """Everything a transition does to the evidence available, per capability.

    `intended_capability` is what the reconfiguration is FOR. Self-occlusion
    is defined relative to it: a transition that removes evidence for some
    unrelated capability is merely reducing, and calling that self-occlusion
    would make the term mean nothing.
    """
    caps = {c.capability_id: c for c in contracts}

    lost = from_config.provides_evidence - to_config.provides_evidence
    gained = to_config.provides_evidence - from_config.provides_evidence
    kept = from_config.provides_evidence & to_config.provides_evidence

    before = {cid: _satisfiable(c, from_config.provides_evidence, caps)
              for cid, c in caps.items()}
    after = {cid: _satisfiable(c, to_config.provides_evidence, caps)
             for cid, c in caps.items()}

    invalidated = sorted(cid for cid in caps if before[cid] and not after[cid])
    enabled = sorted(cid for cid in caps if not before[cid] and after[cid])
    preserved = sorted(cid for cid in caps if before[cid] and after[cid])

    # Witnesses: which load-bearing evidence items a surviving capability
    # loses even though it survives -- it is now resting on fewer legs.
    narrowed = []
    for cid in preserved:
        c = caps[cid]
        was = set(c.requires_all) | {
            e for g in c.requires_one_of
            for e in (g if isinstance(g, (list, tuple)) else [g])
            if e in from_config.provides_evidence}
        now = set(c.requires_all) | {
            e for g in c.requires_one_of
            for e in (g if isinstance(g, (list, tuple)) else [g])
            if e in to_config.provides_evidence}
        if was - now:
            narrowed.append({"capability": cid,
                             "witnesses_lost": sorted(was - now)})

    self_occluding = False
    occlusion_detail = ""
    if intended_capability is not None:
        c = caps.get(intended_capability)
        if c is None:
            occlusion_detail = (
                f"intended capability {intended_capability!r} has no contract; "
                f"self-occlusion CANNOT BE ASSESSED and is not being reported "
                f"as absent")
        elif not after.get(intended_capability, False):
            self_occluding = True
            # The TRANSITIVE requirement set, so the explanation names the
            # evidence that actually went rather than only the direct one.
            needed = _transitive_evidence(c, caps)
            occlusion_detail = (
                f"the transition removes {sorted(needed & lost)}, which "
                f"{intended_capability!r} requires (directly or through a "
                f"subordinate capability). After R there is no evidence path "
                f"by which the capability R was performed for can be "
                f"established.")

    if self_occluding:
        verdict = SELF_OCCLUDING
    elif lost and gained:
        verdict = EVIDENCE_REDUCING if invalidated else EVIDENCE_PRESERVING
    elif lost:
        verdict = EVIDENCE_REDUCING
    elif gained:
        verdict = EVIDENCE_INCREASING
    else:
        verdict = EVIDENCE_PRESERVING

    return {
        "schema": "csia.mission.reconfiguration_analysis/1",
        "status": STATUS,
        "novelty": NOVELTY,
        "transition": f"{from_config.config_id} -> {to_config.config_id}",
        "intended_capability": intended_capability,
        "evidence_lost": sorted(lost),
        "evidence_gained": sorted(gained),
        "evidence_kept": sorted(kept),
        "capabilities_invalidated": invalidated,
        "capabilities_enabled": enabled,
        "capabilities_preserved": preserved,
        "capabilities_narrowed": narrowed,
        "post_transition_evidence_required": sorted(
            {e for cid in invalidated
             for e in _transitive_evidence(caps[cid], caps)}
            - to_config.provides_evidence),
        "new_witnesses_possible": sorted(gained),
        "self_occluding": self_occluding,
        "verdict": verdict,
        "detail": occlusion_detail,
        "what_this_cannot_see": (
            "evidence that configuration B would in fact produce but does "
            "not DECLARE. That direction produces a false alarm. The "
            "opposite error is impossible here: nothing is ever reported as "
            "available unless a configuration declares it."),
    }


def analyse_all(configs: Mapping[str, Configuration],
                contracts: Iterable[CapabilityContract],
                transitions: Iterable) -> dict:
    """A batch of declared transitions. `transitions` is (from, to, intent)."""
    caps = list(contracts)
    rows = []
    for frm, to, intent in transitions:
        rows.append(analyse_transition(configs[frm], configs[to], caps,
                                       intent))
    occluding = [r for r in rows if r["self_occluding"]]
    return {
        "schema": "csia.mission.reconfiguration_campaign/1",
        "status": STATUS,
        "novelty": NOVELTY,
        "configurations": sorted(configs),
        "transitions_analysed": len(rows),
        "self_occluding": [r["transition"] for r in occluding],
        "rows": rows,
        "not_in_paper_i": True,
    }
