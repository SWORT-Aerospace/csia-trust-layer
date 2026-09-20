"""CSIA-Lite — phase 7, the independent reproduction (H6).

WHAT H6 ASKS AND WHAT THIS ANSWERS
-----------------------------------
H6: "A CSIA-Lite implementation reproduces the two mechanisms without
importing the proprietary CSIA implementation." Killed if it cannot, or if it
can only do so by importing the production modules.

The two mechanisms:

  1. **Gate-induced occlusion.** A relation can vanish from the evidence while
     every measurement feeding it is fresh, because what removed it was a
     gate, not a staleness signal.
  2. **Support before confidence.** A normalized posterior over a hypothesis
     set always names a winner, including when nothing in the evidence could
     tell the candidates apart. Support asks the prior question.

THE HONEST LIMIT OF "INDEPENDENT"
----------------------------------
Independent of the CODE, not of the author. `import csia` is refused by a test
in a fresh interpreter, and nothing here reads `csia_consequence`. But the same
author wrote both within days, so this is a cross-check on the derivation, not
a replication by a second party. Saying otherwise would be a bigger error than
not writing it.

What makes the cross-check worth anything is that it takes a DIFFERENT ROUTE.
`csia_consequence.support` decides separability with set algebra: two
hypotheses are separable exactly by the features in the symmetric difference
of their LOW-sets. This module never computes a symmetric difference. It builds
a likelihood, evaluates the log-likelihood ratio numerically at the observation
that maximises it, and calls a pair separable when that ratio is not zero.

If a set-algebra answer and a numeric-likelihood answer agree across randomized
inputs, the agreement is evidence about the claim. If this module had reused
the symmetric difference, the agreement would be evidence about nothing.

WHY THE TERMS CANCEL
--------------------
Under this likelihood a feature contributes

    w_k * [ log P(o_k | a) - log P(o_k | b) ]

and the bracket is identically zero whenever `k` is LOW under both hypotheses
or under neither, because then P(o_k | a) and P(o_k | b) are the same function.
A closed gate sets `w_k = 0` and zeroes the term whatever the bracket does.
So a pair is separable only through an open feature on which the two
hypotheses disagree -- which is the same statement the production module makes
with sets, reached without them.

STATUS
------
`SOURCE_ANALYSIS` for what it says about CSIA, `DETERMINISTIC_SIMULATION` for
its own numbers. Nothing here runs an autopilot, touches hardware, or holds
any authority. Standard library only.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Mapping, Sequence, Tuple

IDENTIFIABLE = "IDENTIFIABLE"
AMBIGUOUS = "AMBIGUOUS"
NON_IDENTIFIABLE = "NON_IDENTIFIABLE"

#: P(feature reads abnormal | the hypothesis says it should) and the
#: complement. Any pair with P_LOW != P_HIGH, both strictly inside (0, 1),
#: gives the same separability verdict; the values only scale the ratio.
P_LOW = 0.9
P_HIGH = 0.1


class LiteError(ValueError):
    pass


def _check(hypotheses: Sequence[str], low_sets: Mapping[str, Iterable[str]],
           gates: Mapping[str, float]) -> None:
    if len(set(hypotheses)) != len(hypotheses):
        raise LiteError("a hypothesis is listed twice")
    for h in hypotheses:
        if h not in low_sets:
            raise LiteError(f"no LOW set for hypothesis {h!r}")
    for key, weight in gates.items():
        if not 0.0 <= weight <= 1.0:
            raise LiteError(f"gate weight for {key!r} is {weight}, not in "
                            f"[0, 1]")
    unknown = {k for h in hypotheses for k in low_sets[h]} - set(gates)
    if unknown:
        raise LiteError(f"LOW sets name features with no gate: "
                        f"{sorted(unknown)}")


def log_likelihood(hypothesis: str, low_sets: Mapping[str, Iterable[str]],
                   gates: Mapping[str, float],
                   observation: Mapping[str, bool]) -> float:
    """Gate-weighted log-likelihood of one observation under one hypothesis.

    `observation[k]` is True when feature k reads abnormal. A gate weight of
    zero removes the feature's contribution entirely -- which is the occlusion
    mechanism, written as arithmetic.
    """
    low = set(low_sets[hypothesis])
    total = 0.0
    for key, reads_abnormal in observation.items():
        weight = gates.get(key, 0.0)
        if weight == 0.0:
            continue
        p = P_LOW if key in low else P_HIGH
        total += weight * math.log(p if reads_abnormal else 1.0 - p)
    return total


def _extreme_observations(features: Sequence[str]
                          ) -> Tuple[Dict[str, bool], Dict[str, bool]]:
    """All-abnormal and all-normal. The LLR is linear in the per-feature
    terms, so if it is zero at both extremes with every sign combination
    reachable, it is zero everywhere -- see `max_abs_llr`."""
    return ({k: True for k in features}, {k: False for k in features})


def max_abs_llr(a: str, b: str, low_sets: Mapping[str, Iterable[str]],
                gates: Mapping[str, float]) -> float:
    """The largest |LLR(a, b)| over all observations.

    The ratio is a sum of independent per-feature terms, so its extreme is
    reached by choosing, for each feature separately, whichever of the two
    readings makes its term largest in absolute value. No search over the
    2**n observations is needed, and none is done.
    """
    total = 0.0
    low_a, low_b = set(low_sets[a]), set(low_sets[b])
    for key, weight in gates.items():
        if weight == 0.0:
            continue
        pa = P_LOW if key in low_a else P_HIGH
        pb = P_LOW if key in low_b else P_HIGH
        abnormal = abs(math.log(pa) - math.log(pb))
        normal = abs(math.log(1.0 - pa) - math.log(1.0 - pb))
        total += weight * max(abnormal, normal)
    return total


def separable(a: str, b: str, low_sets, gates, epsilon: float = 1e-12) -> bool:
    """Numerically: is there ANY observation the two disagree about?"""
    return max_abs_llr(a, b, low_sets, gates) > epsilon


def posterior(hypotheses: Sequence[str], low_sets, gates,
              observation: Mapping[str, bool]) -> Dict[str, float]:
    """The thing support is NOT.

    Normalized, so it sums to one and names a leader even when every pair is
    inseparable -- in which case it returns the uniform distribution, and a
    consumer taking `max()` still gets a confident-looking answer. That is
    mechanism 2, demonstrated rather than asserted.
    """
    scores = {h: log_likelihood(h, low_sets, gates, observation)
              for h in hypotheses}
    top = max(scores.values())
    weights = {h: math.exp(v - top) for h, v in scores.items()}
    total = sum(weights.values())
    return {h: w / total for h, w in weights.items()}


def support(hypotheses: Sequence[str], low_sets, gates) -> dict:
    """Mechanism 2: what the evidence could distinguish, before any number."""
    hypotheses = list(hypotheses)
    _check(hypotheses, low_sets, gates)
    if not hypotheses:
        raise LiteError("no hypotheses")
    if len(hypotheses) == 1:
        # One candidate cannot be distinguished from anything, so it is not
        # identified by evidence. The production module reaches the same
        # refusal by a different route; both exist because a set of size one
        # would otherwise score a free success.
        return {"state": NON_IDENTIFIABLE, "unseparated": [],
                "reason": "SINGLE_HYPOTHESIS",
                "separating_features": {}}
    unseparated, separating = [], {}
    for i, a in enumerate(hypotheses):
        for b in hypotheses[i + 1:]:
            if separable(a, b, low_sets, gates):
                separating[f"{a}|{b}"] = sorted(
                    k for k, w in gates.items() if w > 0.0
                    and (k in set(low_sets[a])) != (k in set(low_sets[b])))
            else:
                unseparated.append([a, b])
    if len(unseparated) == len(hypotheses) * (len(hypotheses) - 1) // 2:
        state, reason = NON_IDENTIFIABLE, "NOTHING_SEPARATES_ANY_PAIR"
    elif unseparated:
        state, reason = AMBIGUOUS, "SOME_PAIRS_UNSEPARATED"
    else:
        state, reason = IDENTIFIABLE, "ALL_PAIRS_SEPARATED"
    return {"state": state, "unseparated": unseparated, "reason": reason,
            "separating_features": separating}


def occlusion_demo(low_sets, gates, observation, closing: str) -> dict:
    """Mechanism 1, as a before/after with the data held fresh throughout.

    `closing` is the feature whose gate shuts. Freshness is not modelled as a
    variable at all here, which is the point: nothing in this function can
    represent a staleness signal, so the change in the answer cannot be
    attributed to one.
    """
    if closing not in gates:
        raise LiteError(f"{closing!r} is not a gated feature")
    hypotheses = sorted(low_sets)
    before = support(hypotheses, low_sets, gates)
    after_gates = dict(gates, **{closing: 0.0})
    after = support(hypotheses, low_sets, after_gates)
    post_before = posterior(hypotheses, low_sets, gates, observation)
    post_after = posterior(hypotheses, low_sets, after_gates, observation)
    # DERIVED, not asserted. An earlier draft wrote
    # "posterior_still_names_a_leader": True as a literal, which would have
    # stayed True no matter what the arithmetic did -- the precise failure
    # this module is about. The leader and whether it is a tie are read off
    # the numbers.
    best = max(post_after.values())
    leaders = sorted(h for h, v in post_after.items()
                     if abs(v - best) <= 1e-12)
    return {
        "closing_feature": closing,
        "all_measurements_fresh_throughout": True,
        "support_before": before["state"],
        "support_after": after["state"],
        "posterior_before": post_before,
        "posterior_after": post_after,
        "support_changed": before["state"] != after["state"],
        "posterior_after_sums_to_one": abs(sum(post_after.values()) - 1.0)
                                       < 1e-9,
        "posterior_after_leaders": leaders,
        "posterior_after_leader_is_a_tie": len(leaders) > 1,
        "max_posterior_after": best,
    }


#: This module analyses. It commands nothing.
HAS_ACTUATOR_AUTHORITY = False
HARDWARE_VALIDATED = False
IMPORTS_CSIA = False
