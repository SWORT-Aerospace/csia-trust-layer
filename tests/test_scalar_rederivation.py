"""Headline scalars re-derived from the frozen source, not read from a JSON.

THE DEFECT THIS CLOSES
----------------------
`tests/test_systems_paper_numeric_claims.py` pins `S_0 = 475.6775` and
`T_0 = 0.999791` as FACTORS -- good, and deliberately so, because pinning the
product 118.82 alone failed to catch two wrong published explanations of where
it came from.

But it reads both out of `research/wp_c8/results/escalation_algebra.json`, and
nothing re-derives that artifact from the engine. Mutation testing found the
consequence: `alpha0` 8.0 -> 800.0 left every behavioural test green, because
the stored JSON still said 475.6775. The test passed BECAUSE the artifact was
stale (`MUTATION_SURVIVORS.md`, EVIDENCE-05).

This file closes the loop. It drives the frozen `TrustCore` itself and compares
the result to the artifact, so a change to the engine invalidates the artifact
instead of being invisible to it.

WHY THIS IS NOT "WRITING A TEST TO KILL A MUTANT"
--------------------------------------------------
The distinction matters and `MUTATION_SURVIVORS.md` names it. A test aimed at
EVIDENCE-05 would assert `alpha0 == 8.0` -- it would kill the mutant, raise the
score, and establish nothing. This asserts the DERIVATION CHAIN the paper
depends on: that the number in the manuscript is what the frozen recursion
actually produces. It kills EVIDENCE-05 incidentally, which is the right order.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from research.physical_validation.derivation.rederive_s0 import (  # noqa: E402
    PUBLISHED_HORIZON_STEPS, sensitivity, settle)

ARTIFACT = os.path.join(ROOT, "research", "wp_c8", "results",
                        "escalation_algebra.json")

#: The rounding the artifact publishes at. S_0 to 4 dp, T_0 to 6 dp -- read
#: from escalation_algebra.py's own `round()` calls, not chosen here.
S0_DP, T0_DP = 4, 6


def _artifact():
    with open(ARTIFACT, encoding="utf-8") as fh:
        return json.load(fh)["verification_against_shipping_trustcore"]


def test_s0_rederives_from_the_frozen_engine():
    """The number in the manuscript is what the recursion actually produces."""
    got = settle()
    stored = _artifact()["settled_mass_S0"]
    assert round(got["S0_exact"], S0_DP) == stored, (
        f"the frozen TrustCore, driven with the documented settling procedure "
        f"for {PUBLISHED_HORIZON_STEPS} steps, produces "
        f"S_0 = {got['S0_exact']!r} -> {round(got['S0_exact'], S0_DP)}, but "
        f"escalation_algebra.json records {stored}.\n\n"
        f"One of three things happened: the frozen core changed, the settling "
        f"procedure changed, or the artifact is stale. Do NOT update this "
        f"test to match the artifact -- regenerate the artifact from the "
        f"engine and explain the diff.")


def test_t0_rederives_from_the_frozen_engine():
    got = settle()
    stored = _artifact()["settled_trust_T0"]
    assert round(got["T0_exact"], T0_DP) == stored, (
        f"T_0 re-derives to {round(got['T0_exact'], T0_DP)}, artifact says "
        f"{stored}")


def test_the_mass_term_rederives_to_the_published_118_82():
    """The whole chain, end to end: engine -> S_0, T_0 -> 118.82."""
    from decimal import Decimal

    got = settle()
    s0 = Decimal(str(round(got["S0_exact"], S0_DP)))
    t0 = Decimal(str(round(got["T0_exact"], T0_DP)))
    mass = float(round(s0 * (t0 - Decimal("0.75")), 2))

    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    stored = doc["what_dominates_N_star"]["mass_term_S0_times_T0_minus_Tstar"]
    assert mass == stored, (
        f"re-derived mass term {mass} against artifact {stored}")
    assert mass == 118.82, (
        f"the manuscript's mass term is 118.82; the chain now yields {mass}")


# ============================== the oracle property, and why it is an oracle

def test_s0_actually_moves_with_alpha0():
    """A scalar that does not move when its input moves is not derived from it.

    This is what makes the re-derivation above an oracle rather than a second
    copy of the same constant -- and it is the property the stored-artifact
    test could not have.
    """
    rows = sensitivity("alpha0", [8.0, 800.0])
    base, mutated = rows[0]["S0"], rows[1]["S0"]
    assert base != mutated, (
        "S_0 is unchanged by a 100x change in alpha0, so re-deriving it "
        "cannot detect a change to alpha0 and EVIDENCE-05 remains a real gap")
    assert abs(mutated - base) > 1.0, (
        f"alpha0 8 -> 800 moved S_0 only from {base} to {mutated}; the "
        f"sensitivity is too small to be a reliable oracle")


def test_the_rederivation_does_not_read_the_artifact_it_checks():
    """A re-derivation that reads the artifact is a tautology.

    CHECKED AGAINST THE PARSED CODE, not the text. The first version grepped
    for the artifact's filename and fired on this module's own docstring,
    which mentions it while explaining why it is not read. That is the FIFTH
    guard in this repository to fire on its own documentation
    (tests/test_ci_env.py carries two, test_dea_conformance.py one,
    test_experiment_orchestrator.py one). The rule is about what the code
    DOES, so inspect imports and executable string constants -- docstrings are
    not executable.
    """
    import ast

    path = os.path.join(ROOT, "research", "physical_validation", "derivation",
                        "rederive_s0.py")
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names]
            module = getattr(node, "module", None) or ""
            assert "wp_c8" not in module and not any(
                "wp_c8" in n for n in names), (
                f"rederive_s0.py imports from wp_c8 ({module or names}); it "
                f"must derive from the engine alone or it proves nothing")
        # FILE ACCESS, not any mention. The module legitimately DESCRIBES
        # what it does not read -- its report payload says so in a `method`
        # field -- and a guard that forbids the word forbids the disclosure.
        # What must not exist is an actual read.
        if isinstance(node, ast.Call):
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else fn.id if isinstance(fn, ast.Name) else "")
            if name not in ("open", "load", "loads", "read_text", "read_bytes"):
                continue
            for arg in ast.walk(node):
                if (isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and "escalation_algebra" in arg.value):
                    raise AssertionError(
                        f"rederive_s0.py reads {arg.value!r} inside a "
                        f"{name}() call; reading the artifact it checks would "
                        f"make the re-derivation a tautology")


# ====================================== the correction this work turned up

def test_s0_is_not_settled_at_the_published_horizon():
    """`settled_mass_S0` is a stronger word than the number supports.

    The MASS is still climbing at n=1500 and keeps climbing toward the
    concentration cap. What IS settled by then is the TRUST. S_0 is therefore a
    function of the horizon and must be quoted with `n_steps`.

    Recorded as a test rather than only in prose so that if someone later
    changes the horizon, the change is visible rather than silent.
    """
    at_1500 = settle(None, 1500)["S0_exact"]
    at_3000 = settle(None, 3000)["S0_exact"]
    cap = settle(None, 1500)["concentration_cap"]

    assert at_3000 > at_1500 + 20.0, (
        f"S_0 is {at_1500:.4f} at n=1500 and {at_3000:.4f} at n=3000. If these "
        f"have become equal the mass now genuinely settles, and the "
        f"'not settled' finding in rederive_s0.py should be withdrawn.")
    assert at_3000 < cap, "the mass may not exceed 1/(1 - rho_max)"

    # The trust, by contrast, IS settled.
    t_1500 = settle(None, 1500)["T0_exact"]
    t_3000 = settle(None, 3000)["T0_exact"]
    assert abs(t_3000 - t_1500) < 1e-3, (
        f"T_0 moved from {t_1500} to {t_3000}; if the trust is no longer "
        f"settled either, the mass term's second factor needs a horizon too")


def test_the_published_horizon_is_pinned():
    """1500 steps is part of the definition of S_0, not an implementation
    detail, because the value depends on it."""
    assert PUBLISHED_HORIZON_STEPS == 1500
    src = open(os.path.join(ROOT, "research", "wp_c8",
                            "escalation_algebra.py"), encoding="utf-8").read()
    assert "range(1500)" in src, (
        "escalation_algebra.py no longer settles for 1500 steps, so the "
        "published S_0 was taken at a different horizon than this test "
        "assumes")
