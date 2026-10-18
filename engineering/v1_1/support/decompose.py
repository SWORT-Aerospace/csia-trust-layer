"""Exact decomposition of the frozen DiagnosisCore score.

Phase 2A. Read-only: `csia/diagnosis` is FROZEN and nothing here modifies it,
imports a copy of it, or re-declares any of its constants. Every constant is
imported from the frozen module so the analysis cannot drift from production.

The obligation this module has to discharge, before any support state is
computed from it, is that the decomposition **reconstructs the production
posterior exactly**. `tests/test_v1_1_support.py` asserts that on every
scenario in the catalogue.

  score[h]  = log_prior[h] + EVIDENCE_MULT * smoothed[h]
  smoothed  = ew_smooth( sum_j contribution_j[h] )
  posterior = softmax(score)

  contribution_j[h] = gate_j * ( log(1 - c_j + EPS)  if j in LOW[h]
                                 log(c_j + EPS)      otherwise )
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# FROZEN core -- imported, never copied.
from csia.diagnosis.bayes import (                        # noqa: E402,F401
    CAUSES, EPS, EVIDENCE_MULT, PRIOR_NOMINAL, SMOOTH_ALPHA,
    CausalDiagnosis)   # CAUSES re-exported for callers
from csia.prediction.predictors import ew_smooth                # noqa: E402

# Re-exported so callers read the frozen table through this module and cannot
# accidentally import a different one.
__all__ = ["CAUSES", "EPS", "EVIDENCE_MULT", "PRIOR_NOMINAL", "SMOOTH_ALPHA",
           "GATE_EPS", "TAU_NUM", "Decomposition", "decompose",
           "log_prior_vector", "production_posterior"]

# The frozen core's own gate cut-off, taken from the same source it uses.
GATE_EPS = 1e-9

# Numerical tolerance for float comparison of two contributions. NOT a
# decision threshold -- see SUPPORT_STATE_SPEC.md section 4. Its insensitivity
# over [1e-15, 1e-9] is asserted by test.
TAU_NUM = 1e-12


def log_prior_vector(names) -> np.ndarray:
    """The frozen core's prior, rebuilt by its own rule."""
    prior = np.full(len(names), (1.0 - PRIOR_NOMINAL) / (len(names) - 1))
    prior[list(names).index("nominal")] = PRIOR_NOMINAL
    return np.log(prior)


def _softmax_rows(score: np.ndarray) -> np.ndarray:
    s = score - score.max(axis=1, keepdims=True)
    p = np.exp(s)
    return p / p.sum(axis=1, keepdims=True)


@dataclass
class Decomposition:
    """Per-tick, per-hypothesis, per-term decomposition of the score."""

    t: np.ndarray                 # (K,)
    names: list                   # hypothesis names, frozen core order
    features: list                # feature names, sorted for determinism
    gate: np.ndarray              # (K, J)
    contribution: np.ndarray      # (K, J, H) instantaneous per-term summand
    ll: np.ndarray                # (K, H) instantaneous sum over terms
    smoothed: np.ndarray          # (K, H) after ew_smooth
    log_prior: np.ndarray         # (H,)
    score: np.ndarray             # (K, H)
    posterior: np.ndarray         # (K, H)

    # -- section 3: ACTIVE ------------------------------------------------
    def active_mask(self, k: int) -> np.ndarray:
        """(J,) bool -- terms carrying evidence at tick k."""
        return self.gate[k] > GATE_EPS

    def active_terms(self, k: int) -> list:
        return [self.features[j] for j in np.nonzero(self.active_mask(k))[0]]

    # -- section 4: DISCRIMINATING ---------------------------------------
    def delta(self, k: int, a: str, b: str) -> np.ndarray:
        """(J,) signed per-term contribution difference for the pair (a, b)."""
        ia, ib = self.names.index(a), self.names.index(b)
        return self.contribution[k, :, ia] - self.contribution[k, :, ib]

    def discriminating(self, k: int, a: str, b: str, tau=TAU_NUM) -> list:
        """Active terms whose contributions to a and b differ."""
        d = np.abs(self.delta(k, a, b))
        m = self.active_mask(k) & (d > tau)
        return [self.features[j] for j in np.nonzero(m)[0]]

    # -- section 6: PRIOR SENSITIVITY -------------------------------------
    def neutral_score(self) -> np.ndarray:
        """Same evidence, uniform prior. Nothing else changes."""
        flat = np.full(len(self.names), np.log(1.0 / len(self.names)))
        return flat[None, :] + EVIDENCE_MULT * self.smoothed

    def leader(self, k: int) -> str:
        return self.names[int(np.argmax(self.score[k]))]

    def neutral_leader(self, k: int) -> str:
        return self.names[int(np.argmax(self.neutral_score()[k]))]

    def score_margin(self, k: int) -> float:
        s = np.sort(self.score[k])[::-1]
        return float(s[0] - s[1])


def decompose(td, causes: dict | None = None) -> Decomposition:
    """Decompose the batch diagnosis of a comparator output `td`.

    Uses `CausalDiagnosis._features`, the frozen core's own feature builder,
    so the feature set and its gates are exactly production's.
    """
    cd = CausalDiagnosis(causes)
    feats = cd._features(td)
    names = list(cd.causes)
    low = [set(cd.causes[c]) for c in names]

    fnames = sorted(feats)
    K = len(td.t)
    J, H = len(fnames), len(names)

    gate = np.zeros((K, J))
    contribution = np.zeros((K, J, H))

    for j, fn in enumerate(fnames):
        c, g = feats[fn]
        c = np.asarray(c, dtype=float) * np.ones(K)
        g = np.asarray(g, dtype=float) * np.ones(K)
        gate[:, j] = g
        lo = np.log(1.0 - c + EPS)
        hi = np.log(c + EPS)
        for h in range(H):
            contribution[:, j, h] = g * (lo if fn in low[h] else hi)

    ll = contribution.sum(axis=1)
    smoothed = np.column_stack([ew_smooth(ll[:, h], SMOOTH_ALPHA)
                                for h in range(H)])
    lp = log_prior_vector(names)
    score = lp[None, :] + EVIDENCE_MULT * smoothed
    posterior = _softmax_rows(score)

    return Decomposition(t=np.asarray(td.t), names=names, features=fnames,
                         gate=gate, contribution=contribution, ll=ll,
                         smoothed=smoothed, log_prior=lp, score=score,
                         posterior=posterior)


def production_posterior(td, causes: dict | None = None) -> np.ndarray:
    """What the frozen core actually outputs, for the equality assertion."""
    return CausalDiagnosis(causes).run(td).posterior
