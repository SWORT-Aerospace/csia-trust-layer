"""Targeted kills for the second mutation tranche, plus the k-of-n form.

WHERE THESE CAME FROM
---------------------
The second mutation run left 102 survivors at score 0.5278. This file works
through them by category rather than one at a time:

    WIRE FORMAT      the state constants' STRING values were unconstrained.
                     Every test compared against the imported symbol, so
                     `UNKNOWN = "DUNNO"` would have passed while every
                     committed artifact changed. That is not an equivalent
                     mutant -- it is an untested contract with every JSON
                     consumer.
    TRANSITION REPORT `recovery.observe()` returns {"phase", "changed",
                     "note"} and nothing asserted on `changed`. Ten survivors
                     lived in that one unread field.
    GRAPH CLOSURE    the transitive walk's edge cases.
    COMPILER INTERNALS cycle-detection colours, topological ordering, the
                     closure fixed point.
    K_OF_N           a form DECLARED in DEPENDENCY_FORMS, with a parser
                     NOTHING CALLED. Now wired, so the declaration is backed.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission import graphs as G                          # noqa: E402
from csia_mission.capability import (CAPABILITY_STATES,       # noqa: E402
                                     CapabilityContract,
                                     ContractError,
                                     DEGRADED_SUPPORTED, EvidenceStatus,
                                     NOT_EVALUABLE, NOT_SUPPORTED,
                                     SUPPORTED, UNKNOWN,
                                     evaluate_capabilities)
from csia_mission.compute import (COMPUTE_DEGRADED,           # noqa: E402
                                  COMPUTE_NOT_SUPPORTED,
                                  COMPUTE_SUPPORTED,
                                  COMPUTE_UNKNOWN)
from csia_mission.forge_seed import (CompileError,            # noqa: E402
                                     DEPENDENCY_FORMS,
                                     check_compiled,
                                     compile_contracts)
from csia_mission.product import (MissionProductContract,     # noqa: E402
                                  PRODUCT_DEGRADED,
                                  PRODUCT_NOT_EVALUABLE,
                                  PRODUCT_NOT_SUPPORTED,
                                  PRODUCT_SUPPORTED,
                                  QualityRequirement)
from csia_mission.recovery import RecoveryState               # noqa: E402


# --------------------------------------------------------------- wire format

def test_the_state_constants_wire_values_are_pinned():
    """Kills every module-level STATE_CONSTANT mutant.

    These were classified as "provably equivalent" on the reasoning that
    every reader uses the symbol. That reasoning is WRONG for anything that
    leaves the process. Renaming `UNKNOWN` to `"DUNNO"` passes every test
    that compares against the symbol and changes every committed artifact,
    every schema enum, and every downstream consumer.

    The string is a WIRE CONTRACT and gets pinned like one.
    """
    assert SUPPORTED == "SUPPORTED"
    assert DEGRADED_SUPPORTED == "DEGRADED_SUPPORTED"
    assert NOT_SUPPORTED == "NOT_SUPPORTED"
    assert NOT_EVALUABLE == "NOT_EVALUABLE"
    assert UNKNOWN == "UNKNOWN"
    assert CAPABILITY_STATES == ("SUPPORTED", "DEGRADED_SUPPORTED",
                                 "NOT_SUPPORTED", "NOT_EVALUABLE", "UNKNOWN")


def test_the_product_state_wire_values_are_pinned():
    assert PRODUCT_SUPPORTED == "PRODUCT_SUPPORTED"
    assert PRODUCT_DEGRADED == "PRODUCT_DEGRADED"
    assert PRODUCT_NOT_SUPPORTED == "PRODUCT_NOT_SUPPORTED"
    assert PRODUCT_NOT_EVALUABLE == "PRODUCT_NOT_EVALUABLE"


def test_the_compute_state_wire_values_are_pinned():
    """compute.py uses a DIFFERENT vocabulary from the capability layer --
    DEGRADED, not DEGRADED_SUPPORTED -- and that difference is deliberate.
    Pinned so a later tidy-up cannot silently unify them."""
    assert COMPUTE_UNKNOWN == "UNKNOWN"
    assert COMPUTE_SUPPORTED == "SUPPORTED"
    assert COMPUTE_DEGRADED == "DEGRADED"
    assert COMPUTE_NOT_SUPPORTED == "NOT_SUPPORTED"
    assert COMPUTE_DEGRADED != DEGRADED_SUPPORTED


def test_the_declared_dependency_forms_are_pinned():
    assert DEPENDENCY_FORMS == ("AND", "OR", "OPTIONAL", "DEGRADING",
                                "K_OF_N")


# ------------------------------------------------------- recovery `changed`

def _to_restricted(m):
    m.observe(NOT_SUPPORTED, 0.0)
    return m


def test_every_recovery_observation_reports_whether_it_changed_anything():
    """Kills the ten BOOLEAN survivors in recovery.py.

    `observe()` returns a `changed` flag that NOTHING asserted on, so ten
    mutations lived in one unread field. A caller driving a UI or a log off
    that flag would have been silently wrong.
    """
    m = RecoveryState("c", required_fresh_observations=2, min_dwell_s=1.0)

    assert m.observe(SUPPORTED, 0.0)["changed"] is False, "NOMINAL, no change"

    loss = m.observe(NOT_SUPPORTED, 1.0)
    assert loss["changed"] is True and m.phase == "RESTRICTED"
    assert "immediate" in loss["note"]

    again = m.observe(NOT_SUPPORTED, 2.0)
    assert again["changed"] is False, "already RESTRICTED"

    first_back = m.observe(SUPPORTED, 3.0)
    assert first_back["changed"] is True and m.phase == "REMEASURING"
    assert "PRESENCE IS NOT RECOVERY" in first_back["note"]

    counting = m.observe(SUPPORTED, 3.1)
    assert counting["changed"] is False, "counting, not yet re-certified"
    assert "2/2" in counting["note"] or "/2" in counting["note"]

    recert = m.observe(SUPPORTED, 5.0)
    assert recert["changed"] is True and m.phase == "RECERTIFIED"

    restored = m.observe(SUPPORTED, 5.5)
    assert restored["changed"] is True and m.phase == "NOMINAL"
    assert restored["note"] == "restored"


def test_losing_evidence_during_recovery_abandons_it_and_says_so():
    """Kills recovery.py:141 `In -> NotIn` -- the phase membership test."""
    m = RecoveryState("c", required_fresh_observations=3, min_dwell_s=1.0)
    _to_restricted(m)
    m.observe(SUPPORTED, 1.0)
    assert m.phase == "REMEASURING"
    out = m.observe(NOT_SUPPORTED, 2.0)
    assert out["changed"] is True
    assert m.phase == "RESTRICTED"
    assert "again" in out["note"]
    assert m.consecutive_supported == 0


def test_recertification_needs_the_count_met_not_merely_approached():
    """Kills recovery.py:171 `GtE -> Gt` -- the count boundary.

    With `>` the machine would need one MORE observation than declared, which
    is a silent policy change nothing would have caught.
    """
    m = RecoveryState("c", required_fresh_observations=3, min_dwell_s=0.0)
    _to_restricted(m)
    m.observe(SUPPORTED, 1.0)
    m.observe(SUPPORTED, 2.0)
    assert m.phase == "REMEASURING", "two of three"
    m.observe(SUPPORTED, 3.0)
    assert m.phase == "RECERTIFIED", "exactly three must suffice"


def test_recertification_needs_the_dwell_met_at_exactly_the_boundary():
    """Kills recovery.py:172 `GtE -> Gt` -- the dwell boundary."""
    m = RecoveryState("c", required_fresh_observations=2, min_dwell_s=2.0)
    _to_restricted(m)
    m.observe(SUPPORTED, 10.0)
    m.observe(SUPPORTED, 11.9)
    assert m.phase == "REMEASURING", "dwell 1.9 < 2.0"
    m.observe(SUPPORTED, 12.0)
    assert m.phase == "RECERTIFIED", "dwell exactly 2.0 must suffice"


# ------------------------------------------------------------ graph closure

def test_the_closure_loop_terminates_and_is_not_short_by_one():
    """Kills graphs.py:176 `LtE -> Lt` with a chain long enough to notice."""
    caps = [CapabilityContract("c0", requires_all=("e",))]
    for i in range(1, 6):
        caps.append(CapabilityContract(f"c{i}",
                                       requires_capabilities=(f"c{i-1}",)))
    g = G.build(caps, [])
    out = G.consumers_of(g, "e")
    assert set(out["transitive_capabilities"]) == {f"c{i}" for i in range(6)}


def test_a_product_reached_only_through_a_capability_is_transitive_not_direct():
    """Kills graphs.py:189/195 `In -> NotIn` and their BoolOps."""
    caps = [CapabilityContract("c", requires_all=("e",))]
    prods = [MissionProductContract(
        "p", "t", requires_capabilities=("c",),
        qualities=(QualityRequirement("imagery_quality", permits=("u",),
                                      prohibits_without=("u",)),
                   QualityRequirement("survey_grade", permits=("v",),
                                      prohibits_without=("v",))))]
    g = G.build(caps, prods)
    out = G.consumers_of(g, "e")
    assert out["direct_products"] == [], "no product names `e` itself"
    assert out["transitive_products"] == ["p"]
    assert set(out["transitive_product_properties"]) == {
        "p.imagery_quality", "p.survey_grade"}, (
        "a product reached through its base capability loses every property")


def test_a_property_with_its_own_capability_edge_is_reached_independently():
    """Kills graphs.py:191 `Or -> And`: a property may depend on a capability
    the PRODUCT does not."""
    caps = [CapabilityContract("base", requires_all=("e_base",)),
            CapabilityContract("extra", requires_all=("e_extra",))]
    prods = [MissionProductContract(
        "p", "t", requires_capabilities=("base",),
        qualities=(QualityRequirement("imagery_quality", permits=("u",),
                                      prohibits_without=("u",)),
                   QualityRequirement("survey_grade",
                                      requires_capabilities=("extra",),
                                      permits=("v",),
                                      prohibits_without=("v",))))]
    g = G.build(caps, prods)
    out = G.consumers_of(g, "e_extra")
    assert out["transitive_product_properties"] == ["p.survey_grade"], (
        "only the property naming `extra` is reached; the product's other "
        "property does not depend on it")
    assert out["transitive_products"] == ["p"]


# ------------------------------------------------------- compiler internals

def test_the_cycle_finder_reports_a_cycle_reached_through_a_clean_branch():
    """Kills forge_seed.py:288 `Eq -> NotEq` -- the WHITE colour test.

    `a` is clean; the cycle is `b <-> c`. A colour test that never descends
    into unvisited nodes finds nothing here.
    """
    caps = [CapabilityContract("a", requires_all=("e",)),
            CapabilityContract("b", requires_capabilities=("c",)),
            CapabilityContract("c", requires_capabilities=("b",))]
    with pytest.raises(CompileError, match="dependency cycle"):
        compile_contracts(caps, [], {})


def test_a_self_cycle_is_detected():
    caps = [CapabilityContract("a", requires_capabilities=("a",))]
    with pytest.raises(CompileError, match="dependency cycle"):
        compile_contracts(caps, [], {})


def test_the_capability_order_is_a_valid_topological_order():
    """Kills forge_seed.py:305/307/313/315 -- the indegree bookkeeping.

    Every capability must appear AFTER each of its subordinates.
    """
    caps = [CapabilityContract("leaf", requires_all=("e",)),
            CapabilityContract("mid", requires_capabilities=("leaf",)),
            CapabilityContract("top", requires_capabilities=("mid", "leaf")),
            CapabilityContract("island", requires_all=("e",))]
    tables = compile_contracts(caps, [], {})
    order = tables.capability_order
    assert set(order) == {"leaf", "mid", "top", "island"}, (
        "every capability must be ordered, including one with no edges")
    by_id = {c.capability_id: c for c in caps}
    for i, cid in enumerate(order):
        for sub in by_id[cid].requires_capabilities:
            assert order.index(sub) < i, f"{sub} must precede {cid}"


def test_the_independent_checker_closure_reaches_a_deep_chain():
    """Kills forge_seed.py:347/349/350/356/357 -- the fixed-point loop.

    A chain of six needs several expansion rounds; a loop that stops early or
    a `changed` flag stuck either way gives the wrong closure.
    """
    caps = [CapabilityContract("c0", requires_all=("e0",))]
    for i in range(1, 6):
        caps.append(CapabilityContract(
            f"c{i}", requires_all=(f"e{i}",),
            requires_capabilities=(f"c{i-1}",)))
    tables = compile_contracts(caps, [], {})
    check = check_compiled(tables, caps, [])
    assert check["agrees"], check["problems"][:3]
    assert check["transitive_closure_rounds"] >= 2, (
        "a six-deep chain cannot close in one round; a loop reporting one "
        "either did not run or did not expand")


def test_the_compiled_output_hash_is_excluded_from_equality():
    """Kills forge_seed.py:80 `compare=False -> True`.

    Two compilations of the same contracts must compare EQUAL as dataclasses
    even though the hash field is populated after construction.
    """
    caps = [CapabilityContract("c", requires_all=("e",))]
    a = compile_contracts(caps, [], {})
    b = compile_contracts(caps, [], {})
    assert a == b
    assert a.output_hash == b.output_hash and a.output_hash


# ------------------------------------------------------------------- k-of-n

def test_k_of_n_is_a_declared_form_that_the_compiler_actually_emits():
    """The form was in DEPENDENCY_FORMS with a parser NOTHING CALLED.

    A declared capability with no behaviour behind it is the exact shape of
    claim this repository exists to refuse, so it is now wired.
    """
    caps = [CapabilityContract(
        "redundant", requires_k_of_n=({"k": 2, "of": ("a", "b", "c")},))]
    tables = compile_contracts(caps, [], {})
    assert "K_OF_N" in tables.forms_used
    entry = tables.capability_dependencies["redundant"]
    assert entry["K_OF_N"] == [{"k": 2, "of": ["a", "b", "c"]}]
    for e in ("a", "b", "c"):
        assert "capability:redundant" in tables.evidence_consumers[e], (
            f"{e} must appear in the consumer index or a k-of-n dependency "
            f"is invisible to impact analysis")
    assert check_compiled(tables, caps, [])["agrees"]


@pytest.mark.parametrize("up,expected", [
    (("a", "b", "c"), SUPPORTED),
    (("a", "b"), SUPPORTED),
    (("a",), NOT_SUPPORTED),
    ((), NOT_SUPPORTED),
])
def test_k_of_n_boundary_at_exactly_k(up, expected):
    """k=2 of 3: two must suffice and one must not."""
    c = CapabilityContract("c",
                           requires_k_of_n=({"k": 2, "of": ("a", "b", "c")},))
    ev = {e: EvidenceStatus(e, e in up) for e in ("a", "b", "c")}
    rep = evaluate_capabilities([c], ev, 1.0)["c"]
    assert rep.state == expected
    if expected == NOT_SUPPORTED:
        assert "K_OF_N_NOT_MET" in rep.reason_codes


def test_k_of_n_with_enough_unknowns_to_possibly_hold_is_unknown():
    """One supported, one unknown, k=2: it MIGHT hold. UNKNOWN, not
    NOT_SUPPORTED -- the same rule as everywhere else in this layer."""
    c = CapabilityContract("c",
                           requires_k_of_n=({"k": 2, "of": ("a", "b", "c")},))
    ev = {"a": EvidenceStatus("a", True), "b": EvidenceStatus("b", None),
          "c": EvidenceStatus("c", False)}
    rep = evaluate_capabilities([c], ev, 1.0)["c"]
    assert rep.state == UNKNOWN
    assert "EVIDENCE_UNKNOWN" in rep.reason_codes


def test_k_of_n_counts_expired_evidence_as_not_supporting():
    c = CapabilityContract("c",
                           requires_k_of_n=({"k": 2, "of": ("a", "b", "c")},))
    ev = {"a": EvidenceStatus("a", True, expires_at=5.0),
          "b": EvidenceStatus("b", True, expires_at=5.0),
          "c": EvidenceStatus("c", False)}
    assert evaluate_capabilities([c], ev, 4.9)["c"].state == SUPPORTED
    late = evaluate_capabilities([c], ev, 5.1)["c"]
    assert late.state == NOT_SUPPORTED
    assert set(late.expired) == {"a", "b"}


@pytest.mark.parametrize("spec,fragment", [
    (("a", "b"), "must be exactly"),
    ({"k": 0, "of": ("a", "b")}, "vacuous"),
    ({"k": 3, "of": ("a", "b")}, "unsatisfiable"),
    ({"k": 1}, "must be exactly"),
    ({"k": "two", "of": ("a", "b")}, "integer k"),
    ({"k": True, "of": ("a", "b")}, "integer k"),
    ({"k": 1, "of": ()}, "non-empty"),
])
def test_a_malformed_k_of_n_is_refused_with_a_reason(spec, fragment):
    """A bare list is NEVER read as 1-of-n, and k outside [1, n] is refused
    as vacuous or unsatisfiable rather than clamped."""
    c = CapabilityContract("c", requires_k_of_n=(spec,))
    with pytest.raises(ContractError, match=fragment):
        c.validate()


def test_a_malformed_k_of_n_makes_the_capability_not_evaluable():
    """It must fail CLOSED through the evaluator too, not only at validate."""
    c = CapabilityContract("c", requires_k_of_n=({"k": 9, "of": ("a",)},))
    rep = evaluate_capabilities([c], {}, 1.0)["c"]
    assert rep.state == NOT_EVALUABLE
    assert "CONTRACT_MALFORMED" in rep.reason_codes


def test_k_of_n_evidence_is_checked_against_the_vehicle_profile():
    """An unprovided k-of-n option is a compile error like any other."""
    caps = [CapabilityContract(
        "c", requires_k_of_n=({"k": 1, "of": ("provided", "missing")},))]
    with pytest.raises(CompileError, match="no declared provider"):
        compile_contracts(caps, [], {"provides_evidence": ["provided"]})


def test_k_of_n_appears_in_the_graph_evidence_edges():
    caps = [CapabilityContract(
        "c", requires_k_of_n=({"k": 2, "of": ("a", "b", "c")},))]
    g = G.build(caps, [])
    assert set(g[G.CAPABILITY_GRAPH]["requires_evidence"]["c"]) == {
        "a", "b", "c"}
    assert G.consumers_of(g, "b")["direct_capabilities"] == ["c"]
