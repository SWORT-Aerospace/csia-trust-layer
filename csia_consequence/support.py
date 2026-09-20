"""Explicit support states, derived from active structural support.

WHAT PROBLEM THIS ADDRESSES
---------------------------
`csia/diagnosis/` reports a leader and a normalized weight. A normalized weight
is a share of the hypotheses considered, not a measure of whether the evidence
could tell them apart. `SC-20` in the systems-paper register already records
this: *"a leader at high weight with zero distinguishing evidence"* is
reachable, and the weight does not say so.

This module answers the different question -- given which evidence terms are
ACTIVE right now, could the remaining hypotheses be separated at all? -- and
returns one of three states. It is additive: it imports no frozen module and
changes no diagnostic output.

THE DEFINITION, FROM STRUCTURE NOT CONFIDENCE
----------------------------------------------
Each hypothesis has a LOW-set: the features it predicts will read low. Two
hypotheses are separable by an active feature iff that feature lies in the
SYMMETRIC DIFFERENCE of their LOW-sets -- a feature in both, or in neither,
contributes an identical term to both log-likelihoods and cancels exactly.
That is the same argument `research/systems-paper/independent_checker.py`
implements, and this module reuses the argument, not the code.

    IDENTIFIABLE      every pair in the hypothesis set is separated by at
                      least one ACTIVE feature.
    AMBIGUOUS         some pairs are separated and at least one is not.
    NON_IDENTIFIABLE  no pair is separated by any active feature.

Confidence is not consulted anywhere in that decision. A hypothesis may hold
99% of the normalized weight and still be NON_IDENTIFIABLE, and that
combination is the whole point.

AUTHORITY
---------
None. This emits a status and an optional advisory capability restriction. It
issues no command, holds no actuator authority, and does not decide what a
vehicle should do.

WHAT IT DOES NOT SETTLE
-----------------------
Abstention is not a solved safety problem. Reporting NON_IDENTIFIABLE converts
a wrong confident answer into a refusal, and a refusal has its own cost. The
tradeoff is an empirical question this module does not answer; it only makes
the state explicit enough to measure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, FrozenSet, Optional, Tuple

IDENTIFIABLE = "IDENTIFIABLE"
AMBIGUOUS = "AMBIGUOUS"
NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
STATES = (IDENTIFIABLE, AMBIGUOUS, NON_IDENTIFIABLE)

# Reason codes. Each names WHY, not merely WHAT.
R_ALL_PAIRS_SEPARATED = "ALL_PAIRS_SEPARATED"
R_SOME_PAIRS_UNSEPARATED = "SOME_PAIRS_UNSEPARATED"
R_NO_ACTIVE_EVIDENCE = "NO_ACTIVE_EVIDENCE"
R_ALL_SEPARATING_EVIDENCE_GATED = "ALL_SEPARATING_EVIDENCE_GATED"
R_SINGLE_HYPOTHESIS = "SINGLE_HYPOTHESIS"
R_CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
R_EMPTY_HYPOTHESIS_SET = "EMPTY_HYPOTHESIS_SET"

REASONS = (R_ALL_PAIRS_SEPARATED, R_SOME_PAIRS_UNSEPARATED,
           R_NO_ACTIVE_EVIDENCE, R_ALL_SEPARATING_EVIDENCE_GATED,
           R_SINGLE_HYPOTHESIS, R_CONTRADICTORY_EVIDENCE,
           R_EMPTY_HYPOTHESIS_SET)


@dataclass(frozen=True)
class SupportReport:
    """The output. Carries its own provenance so it cannot be quoted bare."""

    status: str
    reason: str
    hypotheses: Tuple[str, ...]
    active_evidence: Tuple[str, ...]
    gated_evidence: Tuple[str, ...]
    separated_pairs: Tuple[Tuple[str, str], ...]
    unseparated_pairs: Tuple[Tuple[str, str], ...]
    timestamp_s: float
    provenance: str
    recommended_capability_restriction: Optional[str] = None
    detail: Dict = field(default_factory=dict)

    #: Structural, not advisory. Nothing here may command anything.
    HAS_ACTUATOR_AUTHORITY = False

    def __post_init__(self) -> None:
        if self.status not in STATES:
            raise ValueError(f"unknown support status {self.status!r}")
        if self.reason not in REASONS:
            raise ValueError(f"unknown reason code {self.reason!r}")

    @property
    def supports_confident_attribution(self) -> bool:
        return self.status == IDENTIFIABLE

    def as_dict(self) -> dict:
        return {
            "schema": "csia.consequence.support/1",
            "status": self.status, "reason": self.reason,
            "hypotheses": list(self.hypotheses),
            "active_evidence": list(self.active_evidence),
            "gated_evidence": list(self.gated_evidence),
            "separated_pairs": [list(p) for p in self.separated_pairs],
            "unseparated_pairs": [list(p) for p in self.unseparated_pairs],
            "timestamp_s": self.timestamp_s,
            "provenance": self.provenance,
            "recommended_capability_restriction":
                self.recommended_capability_restriction,
            "supports_confident_attribution":
                self.supports_confident_attribution,
            "has_actuator_authority": False,
            "detail": dict(self.detail),
        }


def separating_features(low_sets: Dict[str, FrozenSet[str]], a: str,
                        b: str) -> FrozenSet[str]:
    """Features that can tell `a` from `b`: the symmetric difference.

    A feature in both LOW-sets, or in neither, contributes the same term to
    both log-likelihoods and cancels exactly -- for every value the feature
    can take. So it cannot separate them at any confidence.
    """
    return low_sets[a] ^ low_sets[b]


def classify(*, hypotheses, low_sets: Dict[str, FrozenSet[str]],
             gates: Dict[str, float], timestamp_s: float,
             provenance: str, gate_epsilon: float = 0.0,
             contradictory: Tuple[str, ...] = ()) -> SupportReport:
    """Decide support from which features are ACTIVE, not from confidence.

    `gates` maps feature -> its realized weight this tick, already multiplied
    by freshness. A feature is ACTIVE when its weight exceeds
    ``gate_epsilon``; the default of 0.0 means any non-zero contribution
    counts, which is the conservative reading -- a feature with weight 0.2 is
    attenuated, not absent, and calling it absent would overstate ambiguity.
    """
    hypotheses = tuple(hypotheses)
    active = tuple(sorted(k for k, w in gates.items() if w > gate_epsilon))
    gated = tuple(sorted(k for k, w in gates.items() if w <= gate_epsilon))
    common = dict(hypotheses=hypotheses, active_evidence=active,
                  gated_evidence=gated, timestamp_s=timestamp_s,
                  provenance=provenance)

    if not hypotheses:
        return SupportReport(NON_IDENTIFIABLE, R_EMPTY_HYPOTHESIS_SET,
                             separated_pairs=(), unseparated_pairs=(),
                             **common)
    if contradictory:
        return SupportReport(
            AMBIGUOUS, R_CONTRADICTORY_EVIDENCE, separated_pairs=(),
            unseparated_pairs=(), recommended_capability_restriction=
            "treat attribution as unsupported until the contradiction clears",
            detail={"contradictory_features": list(contradictory)}, **common)
    if len(hypotheses) == 1:
        # One hypothesis is trivially "identified" and that is not evidence.
        # Named as its own reason so it can never be counted as a success.
        return SupportReport(NON_IDENTIFIABLE, R_SINGLE_HYPOTHESIS,
                             separated_pairs=(), unseparated_pairs=(),
                             **common)

    active_set = frozenset(active)
    separated, unseparated = [], []
    per_pair = {}
    for a, b in combinations(sorted(hypotheses), 2):
        needed = separating_features(low_sets, a, b)
        witnesses = tuple(sorted(needed & active_set))
        per_pair[f"{a}|{b}"] = {
            "separating_features": sorted(needed),
            "active_witnesses": list(witnesses),
        }
        (separated if witnesses else unseparated).append((a, b))

    if not unseparated:
        return SupportReport(IDENTIFIABLE, R_ALL_PAIRS_SEPARATED,
                             separated_pairs=tuple(separated),
                             unseparated_pairs=(), detail=per_pair, **common)

    if not separated:
        # Distinguish "nothing is active at all" from "the things that would
        # have separated them are exactly the ones gated off". The second is
        # self-occlusion and is a different finding.
        any_separator_exists = any(
            separating_features(low_sets, a, b) for a, b in unseparated)
        reason = (R_ALL_SEPARATING_EVIDENCE_GATED if active_set == frozenset()
                  or any_separator_exists else R_NO_ACTIVE_EVIDENCE)
        if not active_set:
            reason = R_NO_ACTIVE_EVIDENCE
        return SupportReport(
            NON_IDENTIFIABLE, reason, separated_pairs=(),
            unseparated_pairs=tuple(unseparated),
            recommended_capability_restriction=
            "do not act on attribution; no active evidence separates any pair",
            detail=per_pair, **common)

    return SupportReport(
        AMBIGUOUS, R_SOME_PAIRS_UNSEPARATED,
        separated_pairs=tuple(separated), unseparated_pairs=tuple(unseparated),
        recommended_capability_restriction=
        "attribution is partial; restrict actions that depend on the "
        "unseparated pairs",
        detail=per_pair, **common)
