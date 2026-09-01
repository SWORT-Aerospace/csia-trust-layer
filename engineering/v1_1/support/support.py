"""Support state, identifiability, prior sensitivity and ambiguity.

Phase 2. Implements `engineering/v1_1/SUPPORT_STATE_SPEC.md` exactly, and
nothing beyond it. No threshold is introduced anywhere in this file: the only
numeric tolerances are `GATE_EPS` (taken from the frozen core) and `TAU_NUM`
(float comparison, declared in the spec before use).

This is diagnostic METADATA. It never modifies the production posterior; the
production posterior is passed through untouched, and a test asserts it.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from decompose import (Decomposition, TAU_NUM,            # noqa: E402
                       decompose)

# Spec section 8: the label is a total function of three booleans. No
# additional information, no threshold.
SUPPORT_STATES = ("NO_APPLICABLE_EVIDENCE", "NON_IDENTIFIABLE",
                  "PRIOR_SENSITIVE", "EVIDENCE_BACKED")


@dataclass
class TickSupport:
    k: int
    t: float
    leader: str
    posterior: float
    runner_up: str
    score_margin: float
    active_terms: int
    evidence_available: bool
    leader_identifiable: bool
    prior_sensitive: bool
    neutral_leader: str
    non_identifiable_against: list = field(default_factory=list)
    discriminating_terms: dict = field(default_factory=dict)
    support_state: str = "NO_APPLICABLE_EVIDENCE"
    ambiguity: str = "AMBIGUOUS"

    def row(self) -> dict:
        return {
            "k": self.k, "t": round(self.t, 3), "leader": self.leader,
            "posterior": round(self.posterior, 6),
            "runner_up": self.runner_up,
            "score_margin": round(self.score_margin, 6),
            "active_terms": self.active_terms,
            "evidence_available": self.evidence_available,
            "leader_identifiable": self.leader_identifiable,
            "prior_sensitive": self.prior_sensitive,
            "neutral_leader": self.neutral_leader,
            "non_identifiable_against": "|".join(
                self.non_identifiable_against),
            "min_discriminating_terms": (
                min(self.discriminating_terms.values())
                if self.discriminating_terms else 0),
            "support_state": self.support_state,
            "ambiguity": self.ambiguity,
        }


def _label(evidence_available: bool, identifiable: bool,
           prior_sensitive: bool) -> str:
    """Spec section 8, table. A total function, no threshold."""
    if not evidence_available:
        return "NO_APPLICABLE_EVIDENCE"
    if not identifiable:
        return "NON_IDENTIFIABLE"
    return "PRIOR_SENSITIVE" if prior_sensitive else "EVIDENCE_BACKED"


def support_at(dec: Decomposition, k: int, tau: float = TAU_NUM) -> TickSupport:
    """Support analysis for one tick. Spec sections 3-8."""
    order = np.argsort(dec.score[k])[::-1]
    leader = dec.names[int(order[0])]
    runner_up = dec.names[int(order[1])]

    active = dec.active_mask(k)
    n_active = int(active.sum())

    # Spec section 5: identifiable against EVERY other modeled hypothesis.
    # No filtering by posterior mass -- that would make identifiability depend
    # on the score whose support is in question.
    disc, collapsed = {}, []
    for other in dec.names:
        if other == leader:
            continue
        terms = dec.discriminating(k, leader, other, tau=tau)
        disc[other] = len(terms)
        if not terms:
            collapsed.append(other)

    evidence_available = n_active > 0
    identifiable = evidence_available and not collapsed
    neutral_leader = dec.neutral_leader(k)
    prior_sensitive = neutral_leader != leader

    return TickSupport(
        k=k, t=float(dec.t[k]), leader=leader,
        posterior=float(dec.posterior[k, dec.names.index(leader)]),
        runner_up=runner_up, score_margin=dec.score_margin(k),
        active_terms=n_active,
        evidence_available=evidence_available,
        leader_identifiable=identifiable,
        prior_sensitive=prior_sensitive,
        neutral_leader=neutral_leader,
        non_identifiable_against=sorted(collapsed),
        discriminating_terms=disc,
        support_state=_label(evidence_available, identifiable,
                             prior_sensitive),
        # Spec section 7: ambiguity is structural, never a posterior margin.
        ambiguity=("UNIQUE" if identifiable else "AMBIGUOUS"),
    )


def support_series(td, causes: dict | None = None, stride: int = 1,
                   tau: float = TAU_NUM):
    """(Decomposition, [TickSupport]) over a comparator output."""
    dec = decompose(td, causes)
    rows = [support_at(dec, k, tau=tau)
            for k in range(0, len(dec.t), stride)]
    return dec, rows


def design_time_indistinguishable(causes: dict | None = None) -> list:
    """Hypothesis pairs with IDENTICAL LOW sets.

    Spec section 10: such a pair is non-identifiable under EVERY possible
    evidence configuration, which is a design-time property of the CAUSES
    table rather than anything about the current flight. Reported separately
    so a runtime NON_IDENTIFIABLE verdict is not mistaken for one.
    """
    from csia.diagnosis.bayes import CAUSES
    c = dict(causes or CAUSES)
    names = list(c)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if set(c[a]) == set(c[b]):
                out.append((a, b))
    return out
