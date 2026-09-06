"""Three structural implementations, 100,000 generated structures, and six
invariants that would each be worth a paper correction if they failed.

WHY THIS EXISTS
---------------
The systems paper reports 378,000 of 378,000 agreements between production
and an independent checker. The fair objection is that two implementations
written by the same people from the same understanding can share a conceptual
mistake and agree perfectly on the wrong answer.

This adds a THIRD -- research/physical_validation/cleanroom/, written from the
definition rather than from either of the other two -- and a FOURTH in the
form of brute-force enumeration inside this file, then drives all of them
with randomly generated structures rather than with the nine committed
scenarios.

WHAT IS AND IS NOT COMPARED HERE, STATED PLAINLY
-------------------------------------------------
Compared on random structures: the clean-room reference, the independent
checker, and brute force.

NOT compared here: the PRODUCTION support engine. Its `discriminating()`
needs a full trust-data object with populated numeric arrays, and
constructing one for a random structure would mean reimplementing production's
input format inside this test -- where any mistake would produce false
disagreements and any shared mistake would produce false agreement. Production's
agreement is established where its numeric path is genuinely exercised: on
real ticks, 378,000 comparisons, reported in the paper.

So the honest summary is: three structural implementations agree on generated
structures; production agrees with one of them on real data. Not "four
implementations agree on everything".

ON PROPERTY FAILURE
-------------------
If a property fails, the minimal counterexample is stored and the property is
NOT redefined to save it. A property that gets weakened until it passes has
stopped being evidence.
"""

from __future__ import annotations

import json
import os
import random
import sys
from itertools import combinations

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research", "physical_validation",
                                "cleanroom"))
sys.path.insert(0, os.path.join(ROOT, "research", "systems-paper"))

import structural_reference as CR              # noqa: E402  clean-room
import independent_checker as IC               # noqa: E402  second impl

#: How many structures. 100,000 is the program's target; the environment
#: variable exists so a developer can shorten a local loop, never so CI can
#: quietly run fewer. The recorded artifact states the number actually run.
N_STRUCTURES = int(os.environ.get("CSIA_PROPERTY_N", "100000"))

#: Fixed seed. A property suite whose seed moves reports a different sample
#: every run and can never be said to have failed on anything in particular.
SEED = 20260906

FEATURES = [f"f{i}" for i in range(8)]
HYPOS = [f"h{i}" for i in range(5)]


def _gen(rng):
    """One random structure: signatures, an active set, and gate weights."""
    n_h = rng.randint(2, len(HYPOS))
    n_f = rng.randint(1, len(FEATURES))
    feats = FEATURES[:n_f]
    signatures = {
        h: frozenset(f for f in feats if rng.random() < 0.45)
        for h in HYPOS[:n_h]
    }
    gates = {f: (rng.random() if rng.random() < 0.7 else 0.0) for f in feats}
    return signatures, gates


def _brute_force(signatures, gates):
    """The definition, enumerated. No sets, no shortcuts.

    Written differently on purpose: an explicit loop over features asking
    "does this feature's LOW membership differ between a and b, and is it
    active?". If this and the set-based reference disagree, one of them has
    the definition wrong.
    """
    active = [f for f, w in gates.items() if w > 0]
    out = {}
    for a, b in combinations(sorted(signatures), 2):
        d = []
        for f in active:
            in_a = f in signatures[a]
            in_b = f in signatures[b]
            if in_a != in_b:
                d.append(f)
        out[(a, b)] = frozenset(d)
    return out


def _checker(signatures, gates):
    """The independent checker's answer, via its own public functions."""
    low = {h: set(s) for h, s in signatures.items()}
    active = {f for f, w in gates.items() if w > 0}
    return {(a, b): IC.active_distinguishing(low, a, b, active)
            for a, b in combinations(sorted(signatures), 2)}


# ---------------------------------------------------------------------------
# The six properties. Each returns None when it holds, or a reason string.
# ---------------------------------------------------------------------------

def _p_symmetry(signatures, gates, rng):
    active = {f for f, w in gates.items() if w > 0}
    for a, b in combinations(sorted(signatures), 2):
        ab = CR.distinguishing_terms(signatures[a], signatures[b], active)
        ba = CR.distinguishing_terms(signatures[b], signatures[a], active)
        if ab != ba:
            return f"D({a},{b})={sorted(ab)} but D({b},{a})={sorted(ba)}"
    return None


def _p_ranking_independence(signatures, gates, rng):
    """Structural support cannot depend on a normalized ranking value.

    The reference has no ranking input at all, so the property is checked the
    only way that means anything: assert the API cannot accept one. A test
    that passed a ranking and observed no change would be testing that an
    ignored argument is ignored.
    """
    import inspect
    params = set(inspect.signature(CR.distinguishing_terms).parameters)
    forbidden = {"weights", "posterior", "ranking", "scores", "p"}
    if params & forbidden:
        return f"the reference accepts a ranking input: {sorted(params & forbidden)}"
    return None


def _p_prior_independence(signatures, gates, rng):
    """Same argument as ranking: priors are not an input."""
    import inspect
    params = set(inspect.signature(CR.analyse).parameters)
    if "priors" in params or "prior" in params:
        return "the reference accepts priors"
    return None


def _p_unrelated_gate_independence(signatures, gates, rng):
    """Closing a gate that controls no discriminator for a pair cannot change
    that pair's support."""
    pairs = list(combinations(sorted(signatures), 2))
    if not pairs:
        return None
    a, b = rng.choice(pairs)
    active = {f for f, w in gates.items() if w > 0}
    d = CR.distinguishing_terms(signatures[a], signatures[b], active)
    unrelated = sorted(active - set(d))
    if not unrelated:
        return None
    victim = rng.choice(unrelated)
    g2 = dict(gates, **{victim: 0.0})
    d2 = CR.distinguishing_terms(signatures[a], signatures[b],
                                 {f for f, w in g2.items() if w > 0})
    if d != d2:
        return (f"closing unrelated gate {victim} changed D({a},{b}) from "
                f"{sorted(d)} to {sorted(d2)}")
    return None


def _p_adding_discriminator_cannot_worsen(signatures, gates, rng):
    """Opening a gate cannot shrink any pair's distinguishing set."""
    closed = sorted(f for f, w in gates.items() if w <= 0)
    if not closed:
        return None
    victim = rng.choice(closed)
    g2 = dict(gates, **{victim: 1.0})
    a1 = {f for f, w in gates.items() if w > 0}
    a2 = {f for f, w in g2.items() if w > 0}
    for a, b in combinations(sorted(signatures), 2):
        d1 = CR.distinguishing_terms(signatures[a], signatures[b], a1)
        d2 = CR.distinguishing_terms(signatures[a], signatures[b], a2)
        if not d1 <= d2:
            return (f"opening {victim} shrank D({a},{b}): {sorted(d1)} -> "
                    f"{sorted(d2)}")
    return None


def _p_removing_non_discriminator_changes_nothing(signatures, gates, rng):
    """Removing a feature that separates NO pair cannot change any pair."""
    active = {f for f, w in gates.items() if w > 0}
    separates = set()
    for a, b in combinations(sorted(signatures), 2):
        separates |= CR.distinguishing_terms(signatures[a], signatures[b],
                                             active)
    spare = sorted(active - separates)
    if not spare:
        return None
    victim = rng.choice(spare)
    a2 = active - {victim}
    for a, b in combinations(sorted(signatures), 2):
        d1 = CR.distinguishing_terms(signatures[a], signatures[b], active)
        d2 = CR.distinguishing_terms(signatures[a], signatures[b], a2)
        if d1 != d2:
            return (f"removing non-discriminating {victim} changed D({a},{b})")
    return None


def _p_unique_attribution_needs_a_witness(signatures, gates, rng):
    """IDENTIFIABLE must mean: an active discriminator against EVERY
    competitor. This is DEA-REQ-001 in structural form."""
    for h in signatures:
        cls = CR.classify(h, signatures, gates)
        w = CR.support_witnesses(h, signatures, gates)
        empty = [k for k, d in w.items() if not d]
        if cls == CR.IDENTIFIABLE and empty:
            return f"{h} is IDENTIFIABLE with no witness against {empty}"
        if cls == CR.NON_IDENTIFIABLE and len(empty) != len(w):
            return f"{h} is NON_IDENTIFIABLE but has a witness"
    return None


PROPERTIES = {
    "SYMMETRY": _p_symmetry,
    "RANKING_INDEPENDENCE": _p_ranking_independence,
    "PRIOR_INDEPENDENCE": _p_prior_independence,
    "UNRELATED_GATE_INDEPENDENCE": _p_unrelated_gate_independence,
    "ADDING_DISCRIMINATING_EVIDENCE": _p_adding_discriminator_cannot_worsen,
    "REMOVING_NON_DISCRIMINATING_EVIDENCE":
        _p_removing_non_discriminator_changes_nothing,
    "UNIQUE_ATTRIBUTION_SUPPORT": _p_unique_attribution_needs_a_witness,
}


@pytest.fixture(scope="module")
def campaign():
    """Run the whole campaign once and share the result across tests."""
    rng = random.Random(SEED)
    counterexamples = {name: None for name in PROPERTIES}
    disagreements = {"cleanroom_vs_checker": None,
                     "cleanroom_vs_bruteforce": None}
    n_pairs = 0

    for i in range(N_STRUCTURES):
        signatures, gates = _gen(rng)
        cr = CR.pairwise_table(signatures, gates)
        ic = _checker(signatures, gates)
        bf = _brute_force(signatures, gates)
        n_pairs += len(cr)

        if cr != ic and disagreements["cleanroom_vs_checker"] is None:
            disagreements["cleanroom_vs_checker"] = {
                "structure": i,
                "signatures": {h: sorted(s) for h, s in signatures.items()},
                "gates": gates,
                "cleanroom": {f"{a}|{b}": sorted(d) for (a, b), d in cr.items()},
                "checker": {f"{a}|{b}": sorted(d) for (a, b), d in ic.items()},
            }
        if cr != bf and disagreements["cleanroom_vs_bruteforce"] is None:
            disagreements["cleanroom_vs_bruteforce"] = {
                "structure": i,
                "signatures": {h: sorted(s) for h, s in signatures.items()},
                "gates": gates,
            }

        for name, fn in PROPERTIES.items():
            if counterexamples[name] is not None:
                continue
            reason = fn(signatures, gates, rng)
            if reason:
                counterexamples[name] = {
                    "structure": i,
                    "reason": reason,
                    "signatures": {h: sorted(s) for h, s in signatures.items()},
                    "gates": gates,
                }

    return {
        "seed": SEED,
        "structures": N_STRUCTURES,
        "pair_comparisons": n_pairs,
        "implementations_compared": ["cleanroom", "independent_checker",
                                     "brute_force"],
        "production_compared": False,
        "production_note": (
            "production's support engine needs a populated trust-data object; "
            "constructing one for a random structure would reimplement its "
            "input format inside the test. Its agreement is established on "
            "real ticks (378,000 comparisons), not here."),
        "disagreements": disagreements,
        "counterexamples": counterexamples,
    }


def test_cleanroom_and_independent_checker_agree(campaign):
    d = campaign["disagreements"]["cleanroom_vs_checker"]
    assert d is None, (
        "the clean-room reference and the independent checker disagree. "
        "Minimal counterexample:\n"
        + json.dumps(d, indent=2, sort_keys=True))


def test_cleanroom_and_brute_force_agree(campaign):
    d = campaign["disagreements"]["cleanroom_vs_bruteforce"]
    assert d is None, (
        "the set-based reference and explicit enumeration disagree, so one of "
        "them has the definition wrong:\n"
        + json.dumps(d, indent=2, sort_keys=True))


@pytest.mark.parametrize("name", sorted(PROPERTIES))
def test_property_holds(campaign, name):
    ce = campaign["counterexamples"][name]
    assert ce is None, (
        f"property {name} FAILED. Do not redefine the property to save it -- "
        f"a property weakened until it passes has stopped being evidence. "
        f"Minimal counterexample:\n" + json.dumps(ce, indent=2, sort_keys=True))


def test_the_campaign_actually_ran_enough_structures(campaign):
    """A property suite that quietly ran 10 structures proves nothing."""
    assert campaign["structures"] >= 100000, (
        f"only {campaign['structures']} structures were generated. The "
        f"program's target is 100,000; CSIA_PROPERTY_N exists for local "
        f"iteration, not for lowering the recorded result.")
    assert campaign["pair_comparisons"] > 0


def test_the_result_is_written_for_the_record(campaign, tmp_path):
    """The artifact a reviewer reads, including what was NOT compared."""
    out = os.path.join(ROOT, "research", "physical_validation", "results",
                       "structural_property_campaign.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(campaign, fh, indent=1, sort_keys=True)
        fh.write("\n")
    assert os.path.exists(out)
