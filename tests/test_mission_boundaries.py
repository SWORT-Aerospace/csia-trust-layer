"""Boundary conditions, written from surviving mutants.

WHERE THESE TESTS CAME FROM
----------------------------
A mutation probe over the mission layer scored **0.4676** -- 115 of 216
injected defects went unnoticed. Every test in this file kills a specific
survivor, and each docstring names the mutation it prevents.

Nearly all of them are BOUNDARY EQUALITIES: `>` against `>=`, `<=` against
`<`. Those survive because a test that checks "well before" and "well after"
never visits the instant in between, and the instant in between is where an
off-by-one lives. A suite can have high coverage and none of these.

WHAT THIS FILE DOES NOT DO
---------------------------
It does not chase every survivor. 17 of the 115 are provably equivalent
mutants -- module-level constant renames, where every reader uses the same
symbol -- and killing those is impossible by construction rather than merely
hard. The rest are worth doing in order of value, and this is the first
tranche.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission import graphs as G                          # noqa: E402
from csia_mission.capability import (CapabilityContract,      # noqa: E402
                                     CapabilityReport,
                                     DEGRADED_SUPPORTED, EvidenceStatus,
                                     NOT_SUPPORTED, SUPPORTED, UNKNOWN,
                                     evaluate_capabilities)
from csia_mission.compute import (COMPUTE_DEGRADED,           # noqa: E402
                                  COMPUTE_NOT_SUPPORTED,
                                  COMPUTE_SUPPORTED, collect_linux)
from csia_mission.planner import (AUTHORIZED, MissionAction,  # noqa: E402
                                  MissionBranch, REJECTED,
                                  DeterministicTestPlanner, authorize)
from csia_mission.product import (MissionProductContract,     # noqa: E402
                                  QualityRequirement,
                                  evaluate_product)
from csia_mission.xr1_contracts import CAPABILITIES, PRODUCTS  # noqa: E402


# ------------------------------------------------- capability.py boundaries

def test_evidence_is_still_valid_at_exactly_its_expiry_instant():
    """Kills capability.py:115 `Gt -> GtE`.

    `now > expires_at` means the evidence is valid AT `expires_at` and
    expired one instant later. That is a real decision -- an expiry is a
    deadline, and a deadline is met when reached -- and nothing tested it, so
    a change to `>=` would have passed.
    """
    c = CapabilityContract("c", requires_all=("e",))
    ev = {"e": EvidenceStatus("e", True, expires_at=10.0)}
    assert evaluate_capabilities([c], ev, now=10.0)["c"].state == SUPPORTED
    later = evaluate_capabilities([c], ev, now=10.000001)["c"]
    assert later.state == NOT_SUPPORTED
    assert "EVIDENCE_EXPIRED" in later.reason_codes


def test_expired_at_agrees_with_state_at_at_the_boundary():
    """Kills capability.py:124 `Gt -> GtE`.

    `expired_at` and `state_at` are separate methods that must agree about
    the same instant. They did not have to, and nothing checked it.
    """
    item = EvidenceStatus("e", True, expires_at=10.0)
    assert item.expired_at(10.0) is False
    assert item.state_at(10.0) == SUPPORTED
    assert item.expired_at(10.000001) is True
    assert item.state_at(10.000001) == NOT_SUPPORTED


def test_an_unknown_alternative_option_yields_unknown_not_not_supported():
    """Kills capability.py:327 `Eq -> NotEq`.

    A `requires_one_of` group in which no option is SUPPORTED but one is
    UNKNOWN must give UNKNOWN -- we cannot tell -- rather than
    NOT_SUPPORTED, which asserts the path is unavailable.
    """
    c = CapabilityContract("c", requires_one_of=(("a", "b"),))
    both_out = {"a": EvidenceStatus("a", False),
                "b": EvidenceStatus("b", False)}
    assert evaluate_capabilities([c], both_out, 1.0)["c"].state == \
        NOT_SUPPORTED

    one_unknown = {"a": EvidenceStatus("a", False),
                   "b": EvidenceStatus("b", None)}
    rep = evaluate_capabilities([c], one_unknown, 1.0)["c"]
    assert rep.state == UNKNOWN, (
        "one option unknown means the path might be available; asserting "
        "NOT_SUPPORTED claims more than is known")
    assert "EVIDENCE_UNKNOWN" in rep.reason_codes


def test_the_severity_order_is_strict_so_ties_keep_the_first_worst():
    """Kills capability.py:261 `Lt -> LtE` at the semantic level.

    `_combine` takes the strictly-worse state. With `<=` a later equal-
    severity state would replace an earlier one -- invisible for equal
    values, but it means the reduction is no longer a well-defined minimum.
    Pinned by checking the result is order-independent.
    """
    caps = [CapabilityContract("a", requires_all=("x", "y"))]
    ev = {"x": EvidenceStatus("x", False), "y": EvidenceStatus("y", None)}
    forward = evaluate_capabilities(caps, ev, 1.0)["a"].state
    ev_rev = {"y": ev["y"], "x": ev["x"]}
    assert evaluate_capabilities(caps, ev_rev, 1.0)["a"].state == forward
    assert forward == NOT_SUPPORTED, (
        "NOT_SUPPORTED is strictly worse than UNKNOWN and must win")


# ---------------------------------------------------- planner.py boundaries

def test_authorization_requires_every_capability_not_merely_one():
    """Kills planner.py:119 `Or -> And` and 111/113 `Eq -> NotEq`."""
    action = MissionAction("a", requires_capabilities=("c1", "c2"))
    both = {"c1": CapabilityReport("c1", SUPPORTED, ()),
            "c2": CapabilityReport("c2", SUPPORTED, ())}
    assert authorize(action, both).decision == AUTHORIZED

    for bad in (NOT_SUPPORTED, UNKNOWN, "NOT_EVALUABLE"):
        mixed = {"c1": CapabilityReport("c1", SUPPORTED, ()),
                 "c2": CapabilityReport("c2", bad, ())}
        out = authorize(action, mixed)
        assert out.decision == REJECTED, bad
        assert out.blocking == {"c2": bad}, (
            "the blocking map must name exactly the failing capability")


def test_each_rejection_reason_is_distinct_per_state():
    """Kills planner.py:111 and :113 `Eq -> NotEq` individually.

    UNKNOWN, NOT_EVALUABLE and NOT_SUPPORTED must produce DIFFERENT reason
    codes, or a reader cannot tell "not measured" from "measured and absent".
    """
    action = MissionAction("a", requires_capabilities=("c",))
    got = {}
    for state in (NOT_SUPPORTED, UNKNOWN, "NOT_EVALUABLE"):
        caps = {"c": CapabilityReport("c", state, ())}
        got[state] = authorize(action, caps).reasons
    assert got[UNKNOWN] == ("CAPABILITY_UNKNOWN",)
    assert got["NOT_EVALUABLE"] == ("CAPABILITY_NOT_EVALUABLE",)
    assert got[NOT_SUPPORTED] == ("CAPABILITY_NOT_SUPPORTED",)
    assert len({v for v in got.values()}) == 3


def test_reasons_are_deduplicated_but_not_collapsed_across_kinds():
    """Kills planner.py:124 `NotIn -> In`.

    Two capabilities failing the same way give ONE reason code; two failing
    differently give TWO. With the membership test inverted the list would
    keep only repeats, which is the opposite behaviour.
    """
    action = MissionAction("a", requires_capabilities=("c1", "c2", "c3"))
    caps = {"c1": CapabilityReport("c1", NOT_SUPPORTED, ()),
            "c2": CapabilityReport("c2", NOT_SUPPORTED, ()),
            "c3": CapabilityReport("c3", UNKNOWN, ())}
    reasons = authorize(action, caps).reasons
    assert reasons.count("CAPABILITY_NOT_SUPPORTED") == 1
    assert set(reasons) == {"CAPABILITY_NOT_SUPPORTED", "CAPABILITY_UNKNOWN"}


def test_the_authorized_property_tracks_the_decision():
    """Kills planner.py:68 and :77 `True -> False`."""
    action = MissionAction("a", requires_capabilities=("c",))
    ok = authorize(action, {"c": CapabilityReport("c", SUPPORTED, ())})
    assert ok.authorized is True and ok.decision == AUTHORIZED
    no = authorize(action, {"c": CapabilityReport("c", NOT_SUPPORTED, ())})
    assert no.authorized is False and no.decision == REJECTED


def test_a_branch_with_one_failing_action_is_not_chosen():
    """Kills planner.py:146 `True -> False` -- the all() over a branch."""
    actions = (MissionAction("ok", requires_capabilities=("good",)),
               MissionAction("bad", requires_capabilities=("gone",)))
    branches = (MissionBranch("two_actions", ("ok", "bad"), priority=10),
                MissionBranch("one_action", ("ok",), priority=5))
    caps = {"good": CapabilityReport("good", SUPPORTED, ()),
            "gone": CapabilityReport("gone", NOT_SUPPORTED, ())}
    out = DeterministicTestPlanner(branches, actions).choose(caps)
    assert out["chosen"] == "one_action", (
        "a branch is authorized only when EVERY action is; partial "
        "authorization must not select it")


# ------------------------------------------------------ graphs.py boundaries

def test_the_transitive_closure_reaches_more_than_one_hop():
    """Kills graphs.py:176 `LtE -> Lt` -- the fixed-point iteration bound.

    `global_mapping` -> `absolute_navigation` -> gnss evidence is two hops.
    A loop bound one iteration short finds the first and not the second.
    """
    caps = [CapabilityContract("leaf", requires_all=("e",)),
            CapabilityContract("mid", requires_capabilities=("leaf",)),
            CapabilityContract("top", requires_capabilities=("mid",))]
    prods = [MissionProductContract(
        "p", "t", requires_capabilities=("top",),
        qualities=(QualityRequirement("imagery_quality", permits=("u",),
                                      prohibits_without=("u",)),))]
    g = G.build(caps, prods)
    out = G.consumers_of(g, "e")
    assert set(out["transitive_capabilities"]) == {"leaf", "mid", "top"}, (
        "three hops must all be found; a bound one short stops at 'mid'")
    assert "p" in out["transitive_products"]


def test_a_direct_product_dependency_pulls_in_all_its_properties():
    """Kills graphs.py:189/195 `In -> NotIn` and the BoolOps around them."""
    prods = [MissionProductContract(
        "p", "t", requires_all=("base",),
        qualities=(QualityRequirement("imagery_quality", permits=("u",),
                                      prohibits_without=("u",)),
                   QualityRequirement("relative_geometry", permits=("v",),
                                      prohibits_without=("v",))))]
    g = G.build([], prods)
    out = G.consumers_of(g, "base")
    assert out["direct_products"] == ["p"]
    assert set(out["transitive_product_properties"]) == {
        "p.imagery_quality", "p.relative_geometry"}, (
        "a product whose BASE dependency is lost loses every property")


def test_an_unrelated_evidence_id_pulls_in_nothing():
    """Kills graphs.py:183/191 `In -> NotIn` / `Or -> And` from the other
    side: the inverted membership test would return everything."""
    g = G.build(CAPABILITIES, PRODUCTS)
    out = G.consumers_of(g, "an.evidence.id.nothing.uses")
    assert out["transitive_capabilities"] == []
    assert out["transitive_products"] == []
    assert out["transitive_product_properties"] == []


# ----------------------------------------------------- compute.py boundaries

def test_a_deadline_exactly_at_budget_is_supported():
    """Kills compute.py:155 `LtE -> Lt`.

    ratio == 1.0 means the deadline was MET, not missed. A budget is a limit
    and hitting it exactly is success.
    """
    exact = collect_linux("d", deadline_budget_s=0.01, observed_latency_s=0.01)
    assert exact.deadline_state == COMPUTE_SUPPORTED
    over = collect_linux("d", deadline_budget_s=0.01,
                         observed_latency_s=0.0100001)
    assert over.deadline_state == COMPUTE_DEGRADED


def test_a_deadline_exactly_at_twice_budget_is_degraded_not_unsupported():
    """Kills compute.py:156 `LtE -> Lt` -- the second band boundary."""
    at_2x = collect_linux("d", deadline_budget_s=0.01,
                          observed_latency_s=0.02)
    assert at_2x.deadline_state == COMPUTE_DEGRADED
    past = collect_linux("d", deadline_budget_s=0.01,
                         observed_latency_s=0.0200001)
    assert past.deadline_state == COMPUTE_NOT_SUPPORTED


def test_memory_band_boundaries_are_inclusive_at_their_thresholds():
    """Kills compute.py:174/175 `LtE -> Lt`.

    Exercised through a declared budget large enough that the process RSS is
    a known fraction of it, so the band is a function of the ratio rather
    than of this host's memory use.
    """
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    # budget chosen so ratio is exactly 0.8 -> SUPPORTED (inclusive bound)
    at_80 = collect_linux("d", memory_budget_bytes=int(rss / 0.8))
    assert at_80.memory_state == COMPUTE_SUPPORTED
    # ratio exactly 1.0 -> DEGRADED (inclusive), not NOT_SUPPORTED
    at_100 = collect_linux("d", memory_budget_bytes=rss)
    assert at_100.memory_state == COMPUTE_DEGRADED
    # ratio above 1.0 -> NOT_SUPPORTED
    over = collect_linux("d", memory_budget_bytes=int(rss * 0.5))
    assert over.memory_state == COMPUTE_NOT_SUPPORTED


def test_the_collector_declares_it_needs_no_special_hardware():
    """Kills compute.py:57 `True -> False`.

    The claim is load-bearing: it is what makes the compute contract
    platform-neutral rather than SACA-shaped.
    """
    ev = collect_linux("d")
    assert ev.provenance["requires_no_special_hardware"] is True
    assert ev.provenance["platform"] == "linux"


# ----------------------------------------------------- product.py boundaries

def test_a_product_property_expiring_exactly_now_is_still_supported():
    """The product layer's expiry boundary, matching the capability one."""
    contract = MissionProductContract(
        "p", "t",
        qualities=(QualityRequirement("imagery_quality", requires_all=("e",),
                                      permits=("u",),
                                      prohibits_without=("u",)),))
    ev = {"e": EvidenceStatus("e", True, expires_at=10.0)}
    at = evaluate_product(contract, ev, {}, now=10.0)
    assert at.property_states["imagery_quality"] == SUPPORTED
    after = evaluate_product(contract, ev, {}, now=10.000001)
    assert after.property_states["imagery_quality"] == NOT_SUPPORTED
    assert "e" in after.expired_dependencies


def test_a_degraded_capability_still_qualifies_a_product_property():
    """DEGRADED_SUPPORTED is an established state; it must qualify."""
    contract = MissionProductContract(
        "p", "t",
        qualities=(QualityRequirement("relative_geometry",
                                      requires_capabilities=("c",),
                                      permits=("u",),
                                      prohibits_without=("u",)),))
    caps = {"c": CapabilityReport("c", DEGRADED_SUPPORTED,
                                  ("ALTERNATIVE_PATH_IN_USE",))}
    res = evaluate_product(contract, {}, caps, now=1.0)
    assert res.property_states["relative_geometry"] == DEGRADED_SUPPORTED
    assert "u" in res.permitted_uses
