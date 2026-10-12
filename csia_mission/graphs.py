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


def _k_of_n_of(contract) -> list:
    """A capability's k-of-n groups, parsed once by the canonical parser."""
    from .capability import _validated_k_of_n
    out = []
    for spec in getattr(contract, "requires_k_of_n", ()) or ():
        k, of = _validated_k_of_n(spec, getattr(contract, "capability_id",
                                                "<contract>"))
        out.append({"k": k, "of": of})
    return out


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
        evidence_nodes |= _evidence_of(c.requires_all, c.requires_one_of,
                                       [g["of"] for g in _k_of_n_of(c)])
    for p in prods.values():
        evidence_nodes |= _evidence_of(p.requires_all, p.requires_one_of)
        for q in p.qualities:
            evidence_nodes |= _evidence_of(q.requires_all, q.requires_one_of)

    cap_to_evidence: dict = {}
    cap_to_cap: dict = {}
    for cid, c in sorted(caps.items()):
        k_of = [g["of"] for g in _k_of_n_of(c)]
        cap_to_evidence[cid] = sorted(
            _evidence_of(c.requires_all, c.requires_one_of, k_of))
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

    BOTH ANSWERS ARE RETURNED, AND THEY ARE DIFFERENT QUESTIONS.

        direct_*      names this evidence id itself
        transitive_*  reaches it through a chain of capabilities

    The first version returned only the direct answer, and that answer is
    MISLEADING for the question a reader is usually asking. `gnss.position.
    supported` is named by exactly one capability -- `absolute_navigation` --
    and by NO product, because the products depend on the capability rather
    than on the evidence. A caller asking "what breaks if I lose GNSS?" and
    reading `products: []` would conclude nothing does.

    This is MX-005's shape a second time: a query that stops at the first
    hop, over a graph whose whole point is that dependencies compose.
    """
    cap_ev = graphs[CAPABILITY_GRAPH]["requires_evidence"]
    cap_cap = graphs[CAPABILITY_GRAPH]["requires_capabilities"]
    prod_ev = graphs[MISSION_PRODUCT_GRAPH]["requires_evidence"]
    prod_cap = graphs[MISSION_PRODUCT_GRAPH]["requires_capabilities"]
    prop_edges = graphs[MISSION_PRODUCT_GRAPH]["property_edges"]

    direct_caps = {cid for cid, ev in cap_ev.items() if evidence_id in ev}

    # Capabilities that reach it through subordinates, to a fixed point.
    reaching = set(direct_caps)
    for _ in range(len(cap_cap) + 1):
        grown = {cid for cid, subs in cap_cap.items()
                 if set(subs) & reaching}
        if grown <= reaching:
            break
        reaching |= grown

    direct_prods = {pid for pid, ev in prod_ev.items() if evidence_id in ev}
    direct_props = {f"{pid}.{p}"
                    for pid, per in prop_edges.items()
                    for p, e in per.items() if evidence_id in e["evidence"]}

    # A product is affected at its BASE when it names the evidence directly
    # or one of its own required capabilities reaches it. Every property of
    # such a product goes with it -- there is no data to qualify.
    base_hit_products = set(direct_prods) | {
        pid for pid, caps in prod_cap.items() if set(caps) & reaching}

    trans_props = set(direct_props)
    for pid in base_hit_products:
        for pname in prop_edges.get(pid, {}):
            trans_props.add(f"{pid}.{pname}")
    # A property may ALSO depend on a capability the product does not, and
    # then only that property is affected.
    for pid, per in prop_edges.items():
        for pname, edges in per.items():
            if set(edges["capabilities"]) & reaching:
                trans_props.add(f"{pid}.{pname}")

    # A PRODUCT IS AFFECTED WHEN ANY OF ITS PROPERTIES IS, and the first
    # version computed it only from the product-level capability list. That
    # left `transitive_product_properties` naming `p.survey_grade` while
    # `transitive_products` was empty -- the property affected, the product
    # apparently not. Two answers to one question, and the narrower one was
    # the wrong one for "what breaks if I lose this?".
    trans_prods = set(base_hit_products) | {
        prop.rsplit(".", 1)[0] for prop in trans_props}

    return {
        "evidence": evidence_id,
        "direct_capabilities": sorted(direct_caps),
        "direct_products": sorted(direct_prods),
        "direct_product_properties": sorted(direct_props),
        "transitive_capabilities": sorted(reaching),
        "transitive_products": sorted(trans_prods),
        "transitive_product_properties": sorted(trans_props),
        # Kept as aliases of the DIRECT answer so existing readers do not
        # silently change meaning, with the transitive answer named beside
        # them rather than substituted for them.
        "capabilities": sorted(direct_caps),
        "products": sorted(direct_prods),
        "product_properties": sorted(direct_props),
        "note": ("direct_* names this evidence id itself; transitive_* "
                 "reaches it through a chain of capabilities. For 'what "
                 "breaks if I lose this?', read the transitive answer."),
    }


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
