"""Tests for the three modules that shipped with ZERO coverage.

WHY THIS FILE EXISTS
--------------------
A coverage run over the mission extension found `graphs.py`, `metrics.py` and
`reconfiguration.py` at **0.0%**. All three had tests that appeared to cover
them -- and those tests read the GENERATED ARTIFACT rather than calling the
code. If the analyser or the metric computation broke in a way that still
produced a plausible-looking JSON file, nothing would have noticed.

That is the same shape as the vacuous-pass defects already in this
programme's ledger (HF-005, MX-004): a check that appears to be measuring
something and is measuring nothing. Reading an artifact is a fine test of the
artifact. It is not a test of the code that wrote it.

`compute.py` was at 30.9% and gets the same treatment for its collector.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission import graphs as G                          # noqa: E402
from csia_mission.capability import CapabilityContract        # noqa: E402
from csia_mission.compute import (COMPUTE_DEGRADED,           # noqa: E402
                                  COMPUTE_NOT_SUPPORTED,
                                  COMPUTE_SUPPORTED,
                                  COMPUTE_UNKNOWN,
                                  ComputeEvidence,
                                  NOT_MEASURABLE_HERE,
                                  as_capability_input, collect_linux)
from csia_mission.metrics import (BY_NAME, DEFINITIONS,       # noqa: E402
                                  compute as compute_metrics,
                                  definitions_doc)
from csia_mission.product import (ProductAssuranceResult,     # noqa: E402
                                  PRODUCT_DEGRADED)
from csia_mission.reconfiguration import (Configuration,      # noqa: E402
                                          EVIDENCE_INCREASING,
                                          EVIDENCE_REDUCING,
                                          SELF_OCCLUDING,
                                          analyse_all,
                                          analyse_transition)
from csia_mission.xr1_contracts import CAPABILITIES, PRODUCTS  # noqa: E402


# ------------------------------------------------------------------- graphs

def test_the_three_graphs_are_built_and_stay_separate():
    g = G.build(CAPABILITIES, PRODUCTS)
    assert set(g["levels"]) == set(G.LEVELS)
    assert g[G.CAPABILITY_GRAPH]["nodes"]
    assert g[G.MISSION_PRODUCT_GRAPH]["nodes"]
    assert g[G.EVIDENCE_GRAPH]["nodes"]
    # The evidence graph must contain every id the other two reference.
    referenced = set()
    for ev in g[G.CAPABILITY_GRAPH]["requires_evidence"].values():
        referenced |= set(ev)
    for ev in g[G.MISSION_PRODUCT_GRAPH]["requires_evidence"].values():
        referenced |= set(ev)
    assert referenced <= set(g[G.EVIDENCE_GRAPH]["nodes"])


def test_every_declared_edge_direction_is_downward():
    """The upward direction is the inversion this architecture prevents."""
    for src, dst in G.PERMITTED_EDGE_DIRECTIONS:
        assert G.LEVELS.index(src) >= G.LEVELS.index(dst), (
            f"{src} -> {dst} points upward")
    # And no reverse pair is declared permitted.
    for src, dst in G.PERMITTED_EDGE_DIRECTIONS:
        if src != dst:
            assert (dst, src) not in G.PERMITTED_EDGE_DIRECTIONS


def test_consumers_of_separates_the_direct_and_transitive_answers():
    """The direct answer alone is MISLEADING, and that is why both exist.

    `gnss.position.supported` is named by exactly ONE capability and by NO
    product -- the products depend on the capability. A caller asking "what
    breaks if I lose GNSS?" and reading the direct product list would
    conclude nothing does.
    """
    g = G.build(CAPABILITIES, PRODUCTS)
    out = G.consumers_of(g, "gnss.position.supported")

    assert out["direct_capabilities"] == ["absolute_navigation"]
    assert out["direct_products"] == [], (
        "no product names the GNSS evidence directly; if one now does, the "
        "contracts changed and this test should say so rather than pass")

    assert "absolute_navigation" in out["transitive_capabilities"]
    assert "global_mapping" in out["transitive_capabilities"], (
        "global_mapping requires absolute_navigation, so it reaches the GNSS "
        "evidence through one hop")
    assert "global_rgb_orthomosaic" in out["transitive_products"]
    assert any(p.endswith("absolute_geolocation")
               for p in out["transitive_product_properties"])

    # And the transitive answer is a SUPERSET of the direct one, always.
    assert set(out["direct_capabilities"]) <= \
        set(out["transitive_capabilities"])
    assert set(out["direct_products"]) <= set(out["transitive_products"])


def test_consumers_of_returns_empty_lists_for_an_unknown_evidence_id():
    g = G.build(CAPABILITIES, PRODUCTS)
    empty = G.consumers_of(g, "nobody.depends.on.this")
    assert empty["direct_capabilities"] == []
    assert empty["transitive_capabilities"] == []
    assert empty["transitive_products"] == []


def test_thermal_products_do_not_reach_the_rgb_evidence():
    """The independence the contracts assert, checked structurally."""
    g = G.build(CAPABILITIES, PRODUCTS)
    out = G.consumers_of(g, "camera.rgb.available")
    assert "bridge_thermal_inspection" not in out["transitive_products"], (
        "an RGB failure must not reach the thermal product; if it does, the "
        "independence the contracts claim is not real")
    assert "bridge_rgb_inspection" in out["transitive_products"]


def test_isolated_survivors_answers_the_question_the_split_exists_for():
    """Removing GNSS must leave the RGB imagery properties standing."""
    g = G.build(CAPABILITIES, PRODUCTS)
    out = G.isolated_survivors(g, ["gnss.position.supported",
                                   "gnss.velocity.supported"])
    assert "bridge_thermal_inspection.imagery_quality" in \
        out["properties_surviving"]
    assert "raw_evidence_package.temporal_consistency" in \
        out["properties_surviving"]
    assert set(out["properties_surviving"]) & set(out["properties_lost"]) \
        == set(), "a property cannot both survive and be lost"


def test_the_graph_is_a_view_not_a_second_source_of_truth():
    """Every capability node must come from a contract, and vice versa."""
    g = G.build(CAPABILITIES, PRODUCTS)
    assert sorted(g[G.CAPABILITY_GRAPH]["nodes"]) == \
        sorted(c.capability_id for c in CAPABILITIES)
    assert sorted(g[G.MISSION_PRODUCT_GRAPH]["nodes"]) == \
        sorted(p.product_id for p in PRODUCTS)


# ------------------------------------------------------------------ metrics

def test_every_definition_is_complete_and_distinct():
    assert len(DEFINITIONS) == len(BY_NAME) == 7
    for d in DEFINITIONS:
        assert d.formula and d.numerator and d.units and d.why
        assert d.direction in ("lower_is_better", "higher_is_better",
                              "neither")
        assert d.trap, f"{d.name} declares no trap; every metric has one"


def test_recovery_latency_is_not_marked_lower_is_better():
    """Marking it so would reward the exact defect it detects."""
    assert BY_NAME["capability_recovery_latency"].direction == "neither"
    assert "Lower is NOT better" in \
        BY_NAME["capability_recovery_latency"].trap


def test_the_false_certification_trap_is_recorded():
    """A system that certifies nothing scores 0.0 and must not look good."""
    trap = BY_NAME["false_product_certification_rate"].trap
    assert "certifies nothing" in trap
    assert "product_coverage" in trap


def _result(pid, supported, unsupported=()):
    return ProductAssuranceResult(
        product_id=pid, state=PRODUCT_DEGRADED,
        supported_properties=tuple(supported),
        unsupported_properties=tuple(unsupported),
        unknown_properties=(), permitted_uses=(), prohibited_uses=(),
        missing_dependencies=(), expired_dependencies=(),
        property_states={}, property_reasons={})


def test_the_metrics_compute_the_declared_formulae():
    products = {"a": _result("a", ["p1", "p2"]),
                "b": _result("b", []),
                "c": _result("c", ["p1"])}
    declared = {"a": 2, "b": 2, "c": 4}
    m = compute_metrics(products, declared,
                        false_certifications=[{"product": "a"}],
                        certifications_issued=10,
                        recovery_latencies={"nav": 1.5},
                        planner_rejections=3, expiry_events=0)
    assert m["product_coverage"] == pytest.approx(2 / 3)
    # (2/2 + 0/2 + 1/4) / 3
    assert m["assured_mission_yield"] == pytest.approx((1.0 + 0.0 + 0.25) / 3)
    assert m["false_product_certification_rate"] == pytest.approx(0.1)
    assert m["false_product_certification_count"] == 1
    assert m["unsupported_planner_request_count"] == 3


def test_the_metrics_report_no_aggregate_score():
    m = compute_metrics({}, {}, certifications_issued=0)
    assert "no_aggregate_score" in m
    assert m["false_product_certification_rate"] is None, (
        "a rate over zero certifications must be None, not 0.0 -- 0.0 would "
        "make a system that certified nothing look perfect")
    assert m["product_coverage"] is None


def test_the_definitions_document_declares_it_predates_the_runs():
    doc = definitions_doc()
    assert doc["declared_before_any_run"] is True
    assert doc["novelty"] == "NOVELTY_NOT_ESTABLISHED"
    assert len(doc["definitions"]) == len(DEFINITIONS)


# ----------------------------------------------------------- reconfiguration

def _configs():
    full = Configuration.of("FULL", ["cam", "imu_ref", "gnss", "clock"])
    stowed = Configuration.of("STOWED", ["imu_ref", "gnss", "clock"])
    return full, stowed


def _caps():
    return [
        CapabilityContract("timing", requires_all=("clock",)),
        CapabilityContract("rgb", requires_all=("cam",),
                           requires_capabilities=("timing",)),
        CapabilityContract("relnav",
                           requires_one_of=(("cam", "imu_ref"),),
                           requires_capabilities=("timing",)),
        CapabilityContract("mapping", requires_capabilities=("rgb",
                                                             "relnav")),
    ]


def test_a_transition_that_destroys_what_it_is_for_is_self_occluding():
    full, stowed = _configs()
    out = analyse_transition(full, stowed, _caps(), "rgb")
    assert out["self_occluding"] is True
    assert out["verdict"] == SELF_OCCLUDING
    assert "cam" in out["evidence_lost"]
    assert out["detail"]


def test_a_transition_with_a_surviving_alternative_is_not_self_occluding():
    """The discrimination that makes the term mean something."""
    full, stowed = _configs()
    out = analyse_transition(full, stowed, _caps(), "relnav")
    assert out["self_occluding"] is False
    assert out["verdict"] == EVIDENCE_REDUCING
    assert "relnav" in out["capabilities_preserved"]


def test_satisfiability_follows_the_capability_chain():
    """MX-005, pinned at the source rather than only in the artifact.

    `mapping` declares NO evidence of its own -- only subordinate
    capabilities. A non-transitive check calls it satisfiable everywhere.
    """
    full, stowed = _configs()
    out = analyse_transition(full, stowed, _caps(), "mapping")
    assert out["self_occluding"] is True, (
        "mapping requires rgb, which requires cam, which the stow removes")
    assert "mapping" in out["capabilities_invalidated"]


def test_adding_evidence_is_reported_as_increasing():
    full, stowed = _configs()
    out = analyse_transition(stowed, full, _caps(), "rgb")
    assert out["verdict"] == EVIDENCE_INCREASING
    assert "cam" in out["evidence_gained"]
    assert "rgb" in out["capabilities_enabled"]


def test_an_unmodelled_intended_capability_is_not_reported_as_clean():
    full, stowed = _configs()
    out = analyse_transition(full, stowed, _caps(), "no_such_capability")
    assert out["self_occluding"] is False
    assert "CANNOT BE ASSESSED" in out["detail"], (
        "an unmodelled capability must be reported as unassessable, not as "
        "absence of self-occlusion")


def test_a_capability_cycle_fails_closed_in_the_analyser():
    caps = [CapabilityContract("a", requires_capabilities=("b",)),
            CapabilityContract("b", requires_capabilities=("a",))]
    full = Configuration.of("FULL", ["x"])
    out = analyse_transition(full, full, caps, "a")
    assert out["self_occluding"] is True, (
        "a capability that depends on itself cannot be established from "
        "evidence by any resolution order; the analyser must fail closed")


def test_narrowed_capabilities_are_reported_even_when_they_survive():
    full, stowed = _configs()
    out = analyse_transition(full, stowed, _caps(), "relnav")
    narrowed = {n["capability"] for n in out["capabilities_narrowed"]}
    assert "relnav" in narrowed, (
        "relnav survives on the imu_ref leg but has lost the cam leg; a "
        "capability now resting on fewer legs is worth reporting")


def test_analyse_all_carries_the_novelty_classification():
    full, stowed = _configs()
    doc = analyse_all({"FULL": full, "STOWED": stowed}, _caps(),
                      [("FULL", "STOWED", "rgb")])
    assert doc["novelty"] == "NOVELTY_NOT_ESTABLISHED"
    assert doc["not_in_paper_i"] is True
    assert doc["transitions_analysed"] == 1


# ------------------------------------------------------------------ compute

def test_every_compute_field_defaults_to_unknown():
    ev = ComputeEvidence(compute_domain="mapping")
    for field in ("availability", "deadline_state", "scheduler_state",
                  "memory_state", "thermal_state", "execution_state",
                  "integrity_state"):
        assert getattr(ev, field) == COMPUTE_UNKNOWN, field
    assert ev.rollup() == COMPUTE_UNKNOWN


def test_an_unknown_field_prevents_a_supported_rollup():
    """A domain whose deadline nobody measured cannot be called SUPPORTED."""
    ev = ComputeEvidence("d", availability=COMPUTE_SUPPORTED,
                         scheduler_state=COMPUTE_SUPPORTED,
                         memory_state=COMPUTE_SUPPORTED,
                         thermal_state=COMPUTE_SUPPORTED)
    assert ev.deadline_state == COMPUTE_UNKNOWN
    assert ev.rollup() == COMPUTE_UNKNOWN


def test_the_unmeasurable_fields_are_exempt_from_the_rollup():
    """Otherwise every rollup would be UNKNOWN forever and report nothing."""
    ev = ComputeEvidence("d", availability=COMPUTE_SUPPORTED,
                         deadline_state=COMPUTE_SUPPORTED,
                         scheduler_state=COMPUTE_SUPPORTED,
                         memory_state=COMPUTE_SUPPORTED,
                         thermal_state=COMPUTE_SUPPORTED)
    assert ev.rollup() == COMPUTE_SUPPORTED
    assert ev.execution_state == COMPUTE_UNKNOWN
    assert ev.integrity_state == COMPUTE_UNKNOWN
    assert set(NOT_MEASURABLE_HERE) == {"execution_state", "integrity_state"}


def test_worst_wins_in_the_rollup():
    ev = ComputeEvidence("d", availability=COMPUTE_SUPPORTED,
                         deadline_state=COMPUTE_DEGRADED,
                         scheduler_state=COMPUTE_SUPPORTED,
                         memory_state=COMPUTE_SUPPORTED,
                         thermal_state=COMPUTE_SUPPORTED)
    assert ev.rollup() == COMPUTE_DEGRADED
    ev2 = ComputeEvidence("d", availability=COMPUTE_NOT_SUPPORTED,
                          deadline_state=COMPUTE_DEGRADED,
                          scheduler_state=COMPUTE_SUPPORTED,
                          memory_state=COMPUTE_SUPPORTED,
                          thermal_state=COMPUTE_SUPPORTED)
    assert ev2.rollup() == COMPUTE_NOT_SUPPORTED


def test_the_linux_collector_leaves_the_deadline_unknown_without_both_inputs():
    """A budget with no measurement is a plan; a measurement with no budget
    is a number. Neither is evidence about a deadline."""
    only_budget = collect_linux("mapping", deadline_budget_s=0.01)
    assert only_budget.deadline_state == COMPUTE_UNKNOWN
    only_obs = collect_linux("mapping", observed_latency_s=0.001)
    assert only_obs.deadline_state == COMPUTE_UNKNOWN
    both = collect_linux("mapping", deadline_budget_s=0.01,
                         observed_latency_s=0.001)
    assert both.deadline_state == COMPUTE_SUPPORTED


def test_the_linux_collector_bands_a_missed_deadline():
    over = collect_linux("mapping", deadline_budget_s=0.01,
                         observed_latency_s=0.015)
    assert over.deadline_state == COMPUTE_DEGRADED
    way_over = collect_linux("mapping", deadline_budget_s=0.01,
                             observed_latency_s=0.5)
    assert way_over.deadline_state == COMPUTE_NOT_SUPPORTED


def test_the_linux_collector_never_claims_integrity():
    ev = collect_linux("mapping")
    assert ev.integrity_state == COMPUTE_UNKNOWN, (
        "there is no attestation hardware here, so there is no integrity "
        "evidence, and a field reading OK would be a fabrication")
    assert ev.execution_state == COMPUTE_UNKNOWN
    d = ev.to_dict()
    assert d["not_measurable_on_this_platform"] == list(NOT_MEASURABLE_HERE)
    assert ev.provenance["requires_no_special_hardware"] is True


def test_memory_state_is_unknown_without_a_declared_budget():
    ev = collect_linux("mapping")
    assert ev.memory_state == COMPUTE_UNKNOWN
    assert "no declared budget" in ev.detail.get("memory_basis", "")


def test_as_capability_input_maps_domains_to_rollups():
    a = ComputeEvidence("mapping", availability=COMPUTE_SUPPORTED,
                        deadline_state=COMPUTE_SUPPORTED,
                        scheduler_state=COMPUTE_SUPPORTED,
                        memory_state=COMPUTE_SUPPORTED,
                        thermal_state=COMPUTE_SUPPORTED)
    b = ComputeEvidence("logging")
    out = as_capability_input([a, b])
    assert out == {"mapping": COMPUTE_SUPPORTED, "logging": COMPUTE_UNKNOWN}
