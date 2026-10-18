"""Clean-room structural reference. Third implementation, deliberately dull.

WHAT THIS IS FOR
----------------
The systems paper reports 378,000 of 378,000 agreements between production
and an independent checker. A referee's fair objection is that two
implementations written by the same people, from the same understanding, can
share a conceptual mistake and agree perfectly on the wrong answer. Agreement
between two is weak evidence; agreement between three, one of which was
written from the DEFINITION rather than from the other two, is meaningfully
stronger.

So this file is written from one sentence:

    two hypotheses are distinguishable, right now, exactly when some feature
    that is CURRENTLY ACTIVE is expected LOW under one of them and not under
    the other.

Everything below is that sentence in set notation. There is no likelihood, no
smoothing, no threshold, no numeric comparison, and no tolerance.

WHAT IT MUST NOT IMPORT, AND WHY THE LIST IS THIS LONG
-------------------------------------------------------
    NOT csia.*                      -- the production diagnosis
    NOT engineering/v1_1/support/   -- the production support engine
    NOT research/systems-paper/independent_checker.py
                                    -- the SECOND implementation. Importing it
                                       would make this the second
                                       implementation wearing a hat.
    NOT numpy, not yaml, not anything

Standard library only, and in practice not even that beyond `itertools`. A
test asserts the module's import set is empty of repository modules, run in a
fresh interpreter, because a docstring promising independence is not
independence.

THE DEGENERATE CASE, RESTATED BECAUSE IT IS THE ONE HONEST DISAGREEMENT
------------------------------------------------------------------------
Production tests a NUMERIC contribution difference against a tolerance. This
reference is purely structural. They therefore differ exactly when a feature
is structurally distinguishing and numerically contributes nothing -- which
happens when the two log-likelihood branches coincide. That set is known,
reported by the exporter as `degenerate_active`, and observed ZERO times in
378,000 comparisons. It is a real disagreement class, not a rounding
argument, and this reference does not pretend to resolve it.
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, FrozenSet, Iterable, List, Mapping, Set, Tuple

__all__ = [
    "distinguishing_terms", "pairwise_table", "equivalence_classes",
    "classify", "support_witnesses", "analyse",
    "IDENTIFIABLE", "AMBIGUOUS", "NON_IDENTIFIABLE", "NOT_EVALUABLE",
]

IDENTIFIABLE = "IDENTIFIABLE"
AMBIGUOUS = "AMBIGUOUS"
NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
NOT_EVALUABLE = "NOT_EVALUABLE"


def _active(evidence: Mapping[str, float] | Iterable[str]) -> Set[str]:
    """Which features count as active.

    Accepts either a set of names or a mapping name -> gate weight. A gate is
    active when its weight is strictly positive; zero and negative are both
    inactive. Deliberately NOT `>= 0` and deliberately not a tolerance: a
    tolerance here would be a threshold, and a threshold is the thing this
    reference exists not to have.
    """
    if isinstance(evidence, Mapping):
        return {k for k, v in evidence.items() if v > 0}
    return set(evidence)


def distinguishing_terms(low_a: Iterable[str], low_b: Iterable[str],
                         active: Iterable[str]) -> FrozenSet[str]:
    """D(a,b) = (LOW(a) symmetric-difference LOW(b)) intersect ACTIVE.

    The whole reference is this line. Everything else is bookkeeping.
    """
    return frozenset((set(low_a) ^ set(low_b)) & set(active))


def pairwise_table(signatures: Mapping[str, Iterable[str]],
                   evidence) -> Dict[Tuple[str, str], FrozenSet[str]]:
    """Every unordered pair -> its distinguishing set.

    Keys are sorted tuples, so D(a,b) and D(b,a) are the same entry by
    construction rather than by a symmetry check that could pass while the
    underlying computation was asymmetric.
    """
    active = _active(evidence)
    out = {}
    for a, b in combinations(sorted(signatures), 2):
        out[(a, b)] = distinguishing_terms(signatures[a], signatures[b],
                                           active)
    return out


def equivalence_classes(signatures: Mapping[str, Iterable[str]],
                        evidence) -> List[FrozenSet[str]]:
    """Group hypotheses that no active evidence separates.

    Union-find over "D(a,b) is empty". Written as repeated merging rather than
    as a clever structure because clarity is the point of this file.

    NOTE ON TRANSITIVITY, because it is not obvious and it is not an
    assumption: non-distinguishability IS transitive here. If no active
    feature separates a from b, and none separates b from c, then LOW(a),
    LOW(b) and LOW(c) agree on every active feature, so none separates a from
    c. The classes are therefore genuine equivalence classes and not merely
    connected components of a similarity graph.
    """
    names = sorted(signatures)
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), d in pairwise_table(signatures, evidence).items():
        if not d:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

    groups: Dict[str, Set[str]] = {}
    for n in names:
        groups.setdefault(find(n), set()).add(n)
    return sorted((frozenset(g) for g in groups.values()),
                  key=lambda s: sorted(s))


def support_witnesses(target: str, signatures: Mapping[str, Iterable[str]],
                      evidence) -> Dict[str, FrozenSet[str]]:
    """For each competitor, the active features that separate it from target.

    An empty set for some competitor is exactly the condition under which a
    unique attribution of `target` is not evidence-supported.
    """
    active = _active(evidence)
    return {k: distinguishing_terms(signatures[target], signatures[k], active)
            for k in sorted(signatures) if k != target}


def classify(target: str, signatures: Mapping[str, Iterable[str]],
             evidence) -> str:
    """One hypothesis's structural status.

    IDENTIFIABLE       separated from every competitor by some active feature
    AMBIGUOUS          tied with some competitors, separated from others
    NON_IDENTIFIABLE   separated from nothing; every competitor is tied
    NOT_EVALUABLE      fewer than two hypotheses, so the question is empty

    NOT_EVALUABLE is a distinct answer rather than a convenient IDENTIFIABLE.
    A one-hypothesis model trivially "identifies" its only member, and
    reporting that as identifiable is how a degenerate configuration reads as
    a healthy one.
    """
    if target not in signatures:
        raise KeyError(f"{target!r} is not in the hypothesis set")
    if len(signatures) < 2:
        return NOT_EVALUABLE
    w = support_witnesses(target, signatures, evidence)
    empty = [k for k, d in w.items() if not d]
    if not empty:
        return IDENTIFIABLE
    if len(empty) == len(w):
        return NON_IDENTIFIABLE
    return AMBIGUOUS


def analyse(signatures: Mapping[str, Iterable[str]], evidence) -> dict:
    """Everything, in one JSON-safe dict, for cross-implementation comparison.

    Sets become sorted lists so two runs -- or two implementations -- can be
    compared with ==, without a set-ordering artefact producing a false
    disagreement.
    """
    active = sorted(_active(evidence))
    table = pairwise_table(signatures, evidence)
    return {
        "hypotheses": sorted(signatures),
        "active": active,
        "pairwise": {f"{a}|{b}": sorted(d) for (a, b), d in
                     sorted(table.items())},
        "distinguishable": {f"{a}|{b}": bool(d) for (a, b), d in
                            sorted(table.items())},
        "equivalence_classes": [sorted(c) for c in
                                equivalence_classes(signatures, evidence)],
        "classification": {h: classify(h, signatures, evidence)
                           for h in sorted(signatures)},
        "witnesses": {h: {k: sorted(d) for k, d in
                          support_witnesses(h, signatures, evidence).items()}
                      for h in sorted(signatures)},
    }
