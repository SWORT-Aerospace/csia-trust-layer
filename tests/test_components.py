"""The component layer must not be able to claim more than it has.

`csia_components` is a SPECIFICATION with a reference implementation and no
validation of any kind. Its main risk is not a wrong number -- it produces
almost none -- but a reader taking it for a working system. So these tests
pin three things: the one fact the whole design rests on, the guards that
keep an unevidenced number out, and the honesty of the package's own
statements about itself.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import csia_components as C                                       # noqa: E402
from csia_components.combined import CombinedGraph, ComponentEdge  # noqa: E402


# --- the one load-bearing fact --------------------------------------------

def test_the_frozen_core_is_node_agnostic():
    """THE WHOLE EXTENSION RESTS ON THIS AND NOTHING ELSE.

    If the frozen trust core knew what a sensor was, a component graph would
    need a frozen change and this package could not exist as written.
    """
    from csia.trust_engine.engine import EngineConfig, TrustCore
    core = TrustCore(["esc_fl", "pack", "cpu"], EngineConfig())
    out = core.step({"e": ("pack", "esc_fl", 0.4, 1.0)}, {}, {}, {},
                    {"esc_fl": True, "pack": True, "cpu": True})
    assert sorted(out) == ["cpu", "esc_fl", "pack"]
    assert out["esc_fl"]["nbr"] is not None


def test_no_frozen_file_is_imported_for_modification():
    """The package may READ the frozen core. It must not shadow or patch it."""
    for name in ("catalog", "combined"):
        src = open(os.path.join(ROOT, "csia_components", f"{name}.py"),
                   encoding="utf-8").read()
        assert "monkeypatch" not in src
        assert "setattr(" not in src


def test_sensor_node_list_matches_the_frozen_one():
    """Restated in this package for convenience; the frozen list is the
    authority and a silent divergence would build a graph that is not a
    superset of the real one."""
    from csia.runtime.online import SENSORS
    from csia_components.combined import SENSOR_NODES
    assert sorted(SENSOR_NODES) == sorted(SENSORS)


# --- the guards that keep unevidenced numbers out --------------------------

def test_a_residual_scale_cannot_be_guessed_as_zero():
    with pytest.raises(ValueError):
        C.normalised_residual(1.0, 0.0)
    with pytest.raises(ValueError):
        C.normalised_residual(1.0, -1.0)


def test_a_non_finite_residual_is_refused_not_fed_to_the_recursion():
    """Malformed telemetry is absence, never poisoned evidence -- the same
    rule the frozen layer applies to its own samples."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            C.normalised_residual(bad, 1.0)


def test_normalised_residual_matches_the_sensor_layers_shape():
    assert C.normalised_residual(2.0, 1.0) == 4.0
    assert C.normalised_residual(0.0, 1.0) == 0.0


def test_a_component_node_may_not_collide_with_a_sensor_name():
    """A collision would merge two different things into one trust value."""
    with pytest.raises(ValueError):
        CombinedGraph(component_nodes=("pack", "imu0"))


def test_an_unreported_node_is_not_fresh_by_default():
    """The frozen core defaults a missing `fresh` key to True, which would
    score a node nobody reported on as alive. The combined graph inverts
    that default, and the difference is the point of this test."""
    g = CombinedGraph(component_nodes=("pack", "esc_fl"))
    edges = [ComponentEdge("power_balance", "power_balance", "pack",
                           "esc_fl", lam=0.2, gate=1.0)]
    for _ in range(5):
        g.step(edges, fresh={"pack": True, "esc_fl": True})
    moved = g.trust["pack"]
    g2 = CombinedGraph(component_nodes=("pack", "esc_fl"))
    for _ in range(5):
        g2.step(edges, fresh={})          # nothing reported
    assert g2.trust["pack"] == pytest.approx(0.8), (
        "a node nobody reported on moved off the prior")
    assert moved != g2.trust["pack"]


def test_a_gated_out_edge_contributes_nothing_not_a_little():
    """An unexcited actuator check must not be scored as agreement. If a
    zero gate still moved trust, absence of evidence would become evidence
    of health."""
    g = CombinedGraph(component_nodes=("esc_fl",))
    fresh = {n: True for n in g.names}
    # A wildly inconsistent edge, fully gated out.
    edges = [ComponentEdge("actuator_response", "actuator_response",
                           "esc_fl", "imu0", lam=900.0, gate=0.0)]
    for _ in range(20):
        g.step(edges, fresh)
    assert g.trust["esc_fl"] == pytest.approx(0.8), (
        "a gated-out edge moved trust; the gate is being treated as a soft "
        "weight rather than as applicability")


def test_a_node_with_no_incident_edge_holds_at_the_prior():
    g = CombinedGraph(component_nodes=("cpu", "canbus", "pack"))
    fresh = {n: True for n in g.names}
    edges = [ComponentEdge("power_balance", "power_balance", "pack",
                           "imu0", lam=9.0, gate=1.0)]
    for _ in range(30):
        g.step(edges, fresh)
    assert g.trust["cpu"] == pytest.approx(0.8)
    assert g.trust["canbus"] == pytest.approx(0.8)
    assert g.trust["pack"] < 0.7, "the edge that WAS present did nothing"


# --- blame ----------------------------------------------------------------

def test_blame_returns_a_set_never_a_culprit():
    for rel in C.RELATIONS:
        if rel.family == "REDUNDANCY":
            continue
        assert len(rel.blames) >= 2, (
            f"{rel.key} names a single culprit; no non-redundancy relation "
            f"can, because the frozen core encodes no causal direction")


def test_cross_family_agreement_needs_a_binding_and_says_so():
    """The gap the first version had: `blames` names ROLES, so two families
    can never coincide until the roles are bound to platform nodes."""
    unbound = C.implicated_by(["actuator_response", "power_balance"])
    assert unbound["by_independent_families"] == {}
    assert unbound["unbound_roles"]
    assert unbound["binding_warning"]

    bind = {"actuator": "esc_fl", "power_loads": "esc_fl",
            "the plant": "airframe", "motion_sensor": "imu0",
            "power_source": "pack",
            "the current sensing itself": "motor_esc"}
    bound = C.implicated_by(["actuator_response", "power_balance"], bind)
    assert bound["unbound_roles"] == []
    assert bound["binding_warning"] is None
    assert "esc_fl" in bound["by_independent_families"]
    assert set(bound["by_independent_families"]["esc_fl"]) == {
        "ACTUATION", "CONSERVATION"}


def test_an_unknown_relation_raises_and_lists_the_known_ones():
    with pytest.raises(KeyError) as excinfo:
        C.relation("no_such_relation")
    assert "power_balance" in str(excinfo.value)


# --- the catalogue's own honesty ------------------------------------------

def test_every_relation_declares_a_gate_and_a_blind_spot():
    """A relation whose blind spot is undocumented will be read as covering
    it, and a relation with no gate will be scored when it carries no
    information."""
    for rel in C.RELATIONS:
        assert rel.gate and len(rel.gate) > 20, rel.key
        assert rel.blind_to and len(rel.blind_to) > 20, rel.key
        assert rel.requires, rel.key
        assert rel.family in C.FAMILIES, rel.key


def test_the_catalogue_covers_the_universal_component_classes():
    """Power, actuation, timing and integrity exist on every automated
    platform. A catalogue missing one of them is not a catalogue of what
    every vehicle has."""
    families = {r.family for r in C.universal()}
    for needed in ("CONSERVATION", "ACTUATION", "TIMING", "INTEGRITY",
                   "THERMAL", "EFFORT"):
        assert needed in families, needed


def test_closed_loop_masking_is_recorded_as_the_central_problem():
    """It is the reason commanded-versus-achieved is the wrong residual, and
    a package that omitted it would ship the naive edge."""
    doc = C.catalog.__doc__ if hasattr(C, "catalog") else None
    from csia_components import catalog
    doc = catalog.__doc__
    assert "CLOSED-LOOP MASKING" in doc
    assert "effort_drift" in doc or "EFFORT_DRIFT" in doc
    assert any(r.key == "effort_drift" for r in C.RELATIONS)


def test_the_package_states_it_is_unvalidated_in_several_places():
    from csia_components import catalog, combined
    assert "NOT VALIDATED" in catalog.__doc__
    assert "UNVALIDATED" in C.__doc__ or "UNVALIDATED" in catalog.__doc__
    assert len(C.UNVALIDATED_CLAIMS) >= 5
    joined = " ".join(C.UNVALIDATED_CLAIMS)
    for required in ("no component-fault", "THRESHOLDS DO NOT EXIST",
                     "NO NOVELTY IS CLAIMED", "BLAME ASSIGNMENT IS NOT"):
        assert required in joined, required
    assert "NOT TOUCHED" in combined.__doc__ or \
        "NO FROZEN FILE IS TOUCHED" in combined.__doc__


def test_no_component_node_reaches_the_failsafe():
    """The frozen policy names eight sensor nodes. Nothing in this package
    may change what it reads, and a component trust value is published and
    judged by nobody -- the same state SR-006 recorded for baro, recorded
    here rather than quietly fixed."""
    from csia_components import combined
    assert "No component node feeds the FAILSAFE" in combined.__doc__
    for name in ("catalog", "combined"):
        src = open(os.path.join(ROOT, "csia_components", f"{name}.py"),
                   encoding="utf-8").read()
        assert "FailsafePolicy" not in src
        assert "SupervisedFailsafe" not in src
