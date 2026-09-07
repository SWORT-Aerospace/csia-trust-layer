"""The three graph levels, kept apart on purpose.

WHY THREE AND NOT ONE
---------------------
It is tempting to draw one big dependency graph from sensors to deliverables.
The reason not to is a single observation:

    AN EVIDENCE FAILURE MAY REMOVE ONE PRODUCT WHILE PRESERVING ANOTHER.

Lose GNSS support and the absolute-geolocation qualification of an image is
gone. The image is not. In one flat graph both hang off the same subtree and
the natural implementation removes both. Three graphs with explicit edges
between them makes the survival of the image a thing you have to write down
rather than a thing you have to remember.

    EVIDENCE GRAPH      sources, relations, gates, witnesses, availability,
                        freshness, transport, applicability
        |  edges: which evidence a capability requires
        v
    CAPABILITY GRAPH    functions: stable_flight, attitude_hold,
                        relative_navigation, absolute_navigation, RGB_capture,
                        local_mapping, global_mapping, ...
        |  edges: which capabilities a product PROPERTY requires
        v
    MISSION PRODUCT     deliverables, each with independently qualified
    GRAPH               quality properties

THE EDGES ONLY POINT DOWNWARD
------------------------------
`cross_level_edges` returns edges from products to capabilities to evidence.
There is no function returning the reverse, because a product influencing a
capability's support state is precisely the inversion this architecture
exists to prevent. Wanting to know "what does this evidence item feed" is a
real question and is answered by inverting the downward edges at read time --
`consumers_of` does that, and it computes rather than stores, so no upward
edge is ever persisted.

THIS MODULE IS A VIEW, NOT A SECOND SOURCE OF TRUTH
-----------------------------------------------------
Every graph is derived from the contracts. Nothing here holds state that the
contracts do not, so a graph cannot disagree with the system it describes.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .capability import CapabilityContract
from .product import MissionProductContract

EVIDENCE_GRAPH = "EVIDENCE_GRAPH"
CAPABILITY_GRAPH = "CAPABILITY_GRAPH"
MISSION_PRODUCT_GRAPH = "MISSION_PRODUCT_GRAPH"

LEVELS = (EVIDENCE_GRAPH, CAPABILITY_GRAPH, MISSION_PRODUCT_GRAPH)

#: The only permitted direction. Written as data so a test can assert it.
PERMITTED_EDGE_DIRECTIONS = (
    (MISSION_PRODUCT_GRAPH, CAPABILITY_GRAPH),
    (MISSION_PRODUCT_GRAPH, EVIDENCE_GRAPH),
    (CAPABILITY_GRAPH, EVIDENCE_GRAPH),
    (CAPABILITY_GRAPH, CAPABILITY_GRAPH),      # subordinate capabilities
)


def _evidence_of(*specs) -> set:
    out: set = set()
    for spec in specs:
        for item in spec:
            if isinstance(item, (list, tuple)):
                out |= set(item)
            else:
                out.add(item)
    return out


def build(capabilities: Iterable[CapabilityContract],
          products: Iterable[MissionProductContract],
          evidence_sources: Mapping[str, Mapping] | None = None) -> dict:
    """The three graphs plus the edges between them, all derived."""
    caps = {c.capability_id: c for c in capabilities}
    prods = {p.product_id: p for p in products}
    sources = dict(evidence_sources or {})

    evidence_nodes: set = set(sources)
    for c in caps.values():
        evidence_nodes |= _evidence_of(c.requires_all, c.requires_one_of)
    for p in prods.values():
        evidence_nodes |= _evidence_of(p.requires_all, p.requires_one_of)
        for q in p.qualities:
            evidence_nodes |= _evidence_of(q.requires_all, q.requires_one_of)

    cap_to_evidence: dict = {}
    cap_to_cap: dict = {}
    for cid, c in sorted(caps.items()):
        cap_to_evidence[cid] = sorted(
            _evidence_of(c.requires_all, c.requires_one_of))
        cap_to_cap[cid] = sorted(c.requires_capabilities)

    prod_to_cap: dict = {}
    prod_to_evidence: dict = {}
    property_edges: dict = {}
    for pid, p in sorted(prods.items()):
        prod_to_cap[pid] = sorted(p.requires_capabilities)
        prod_to_evidence[pid] = sorted(
            _evidence_of(p.requires_all, p.requires_one_of))
        property_edges[pid] = {}
        for q in sorted(p.qualities, key=lambda x: x.property_name):
            property_edges[pid][q.property_name] = {
                "capabilities": sorted(q.requires_capabilities),
                "evidence": sorted(
                    _evidence_of(q.requires_all, q.requires_one_of)),
            }

    return {
        "schema": "csia.mission.graphs/1",
        "levels": list(LEVELS),
        EVIDENCE_GRAPH: {
            "nodes": sorted(evidence_nodes),
            "sources": {k: dict(v) for k, v in sorted(sources.items())},
        },
        CAPABILITY_GRAPH: {
            "nodes": sorted(caps),
            "requires_evidence": cap_to_evidence,
            "requires_capabilities": cap_to_cap,
        },
        MISSION_PRODUCT_GRAPH: {
            "nodes": sorted(prods),
            "requires_capabilities": prod_to_cap,
            "requires_evidence": prod_to_evidence,
            "property_edges": property_edges,
        },
        "why_three": (
            "An evidence failure may remove one product while preserving "
            "another. In one flat graph both hang off the same subtree and "
            "the natural implementation removes both."),
        "edge_direction": "downward only; see PERMITTED_EDGE_DIRECTIONS",
    }


def consumers_of(graphs: Mapping, evidence_id: str) -> dict:
    """What depends on one evidence item. COMPUTED, never stored.

    Storing an upward edge would make it possible for a product to reach a
    capability, which is the inversion this architecture prevents. Computing
    it at read time answers the same question and creates no such path.
    """
    caps = [cid for cid, ev in
            graphs[CAPABILITY_GRAPH]["requires_evidence"].items()
            if evidence_id in ev]
    prods = [pid for pid, ev in
             graphs[MISSION_PRODUCT_GRAPH]["requires_evidence"].items()
             if evidence_id in ev]
    props = []
    for pid, per_prop in graphs[MISSION_PRODUCT_GRAPH][
            "property_edges"].items():
        for pname, edges in per_prop.items():
            if evidence_id in edges["evidence"]:
                props.append(f"{pid}.{pname}")
    return {"evidence": evidence_id,
            "capabilities": sorted(caps),
            "products": sorted(prods),
            "product_properties": sorted(props)}


def isolated_survivors(graphs: Mapping, removed_evidence: Iterable[str]
                       ) -> dict:
    """Which product PROPERTIES survive removing a set of evidence items.

    This is the question the three-level split exists to be able to answer,
    so it gets a function rather than being left as an exercise. It is
    STRUCTURAL -- it says what could still be established, not what is
    established right now; that is `evaluate_products`.
    """
    gone = set(removed_evidence)
    survivors, casualties = [], []
    for pid, per_prop in sorted(
            graphs[MISSION_PRODUCT_GRAPH]["property_edges"].items()):
        base = set(graphs[MISSION_PRODUCT_GRAPH]["requires_evidence"][pid])
        for pname, edges in sorted(per_prop.items()):
            needed = base | set(edges["evidence"])
            (casualties if needed & gone else survivors).append(
                f"{pid}.{pname}")
    return {"removed_evidence": sorted(gone),
            "properties_surviving": survivors,
            "properties_lost": casualties,
            "note": ("STRUCTURAL: what could still be established, not what "
                     "is established now. For the latter, evaluate.")}
