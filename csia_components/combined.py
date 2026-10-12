"""One trust graph over sensors AND components, on the frozen core unchanged.

THE FACT THIS RESTS ON, WHICH IS MEASURED AND NOT ARGUED
---------------------------------------------------------
`csia/trust_engine/engine.py` is node-agnostic. `TrustCore(names, cfg)` takes
arbitrary names; `step(edges, phys, hist, var_ratio, fresh)` takes arbitrary
edges as `{key: (node_a, node_b, lam, gate)}`. It contains no reference to
any sensor. Driving it over nodes called `esc_fl`, `pack` and `cpu` works
today, and `tests/test_components.py` asserts it.

So combining a component graph with the sensor graph is not an extension of
the trust mathematics. It is a larger node set and a larger edge set handed
to the same recursion. NO FROZEN FILE IS TOUCHED HERE OR ANYWHERE IN THIS
PACKAGE.

WHAT COMBINING ACTUALLY BUYS, AND IT IS ONE SPECIFIC THING
-----------------------------------------------------------
Not "more nodes". The frozen core weights every edge by the PARTNER'S OWN
TRUST, so a component node that has become suspect automatically stops
vouching for the sensors it touches, and vice versa, with no new mechanism.

The case that motivates it: an ESC degrades. On the sensor graph alone, the
accelerometer and the motor node disagree over `accel_motor_current`, and the
graph cannot say which end moved -- that ambiguity is exactly what SR-011
measured, where a healthy motor_esc sat at 0.65 because an ADMITTED partner
carried a dead edge. A power-balance relation that implicates the ESC from a
completely different physical constraint breaks the symmetry: two independent
families of evidence now point at the same node.

THAT IS A DESIGN ARGUMENT AND IT HAS NOT BEEN MEASURED. There is no
component-fault data in this repository. Read `catalog.UNVALIDATED_CLAIMS`.

WHAT IS DELIBERATELY NOT DONE
------------------------------
* No component node feeds the FAILSAFE. The frozen policy names eight sensor
  nodes and nothing here changes what it reads. A component trust value is
  published and judged by nobody, which is the same state SR-006 recorded for
  baro and is recorded here rather than quietly fixed.
* No capability is promoted on component evidence. The capability bridge
  stays demote-only and UNKNOWN is still never resolved.
* Nothing runs in the flight-time path. This module is driven offline, from
  recorded or synthetic telemetry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from csia.trust_engine.engine import EngineConfig, TrustCore

from .catalog import RELATIONS, Relation

#: The eight sensor nodes the frozen graph already carries. Restated here
#: ONLY so a combined graph can be asserted to be a superset of them; the
#: authority is `csia.runtime.online.SENSORS` and a test checks they agree.
SENSOR_NODES = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc",
                "battery", "vibration")


@dataclass(frozen=True)
class ComponentEdge:
    """One instantiated relation between two named nodes on a platform."""

    key: str
    relation: str
    node_a: str
    node_b: str
    #: The normalised squared residual, exactly the quantity the frozen core
    #: calls `lam`. One means "at the expected scale"; the core's
    #: consistency is exp(-0.5 * max(0, lam - 1)), so lam <= 1 is perfect
    #: agreement and larger values decay it.
    lam: float
    #: Zero when the relation's gate is not met. THE GATE IS NOT A SOFT
    #: WEIGHT. An unexcited actuator check must contribute nothing, not a
    #: little, or absence of evidence becomes evidence of health.
    gate: float

    def as_core_edge(self) -> tuple:
        return (self.node_a, self.node_b, float(self.lam), float(self.gate))


def normalised_residual(residual: float, scale: float) -> float:
    """Turn a raw residual into the `lam` the frozen core consumes.

    Same shape the sensor layer uses: `(residual / scale) ** 2`. The SCALE is
    the part that does not exist yet for any component relation -- it is the
    expected magnitude when healthy, and it has to be measured per platform.
    Passing a guessed scale here produces a confident number from nothing,
    so `scale` is required and has no default.
    """
    if scale <= 0:
        raise ValueError("scale must be positive; it is the healthy "
                         "magnitude of this residual and cannot be zero or "
                         "guessed as one")
    if not math.isfinite(residual):
        raise ValueError("non-finite residual; a malformed measurement must "
                         "be dropped as absence, never fed to the recursion")
    return (float(residual) / float(scale)) ** 2


class CombinedGraph:
    """Sensor nodes and component nodes under one `TrustCore`.

    The core is the FROZEN one, constructed with a larger name list. Nothing
    about the recursion, the weights, the forgetting factor or the Beta
    prior changes.
    """

    def __init__(self, component_nodes, config: EngineConfig | None = None,
                 sensor_nodes=SENSOR_NODES):
        overlap = sorted(set(component_nodes) & set(sensor_nodes))
        if overlap:
            raise ValueError(
                f"component nodes {overlap} collide with sensor node names. "
                f"A collision would silently merge two different things into "
                f"one trust value -- rename the component node")
        self.sensor_nodes = tuple(sensor_nodes)
        self.component_nodes = tuple(component_nodes)
        self.names = tuple(sensor_nodes) + tuple(component_nodes)
        self.core = TrustCore(self.names, config or EngineConfig())

    def step(self, edges, fresh, phys=None, hist=None, var_ratio=None) -> dict:
        """One tick over the combined graph.

        `edges` are `ComponentEdge`s and/or raw core tuples. A node absent
        from `fresh` is treated as NOT fresh -- the frozen core defaults a
        missing key to True, which would score a node nobody reported on as
        alive, so the default is inverted here and the difference is
        asserted by a test.
        """
        core_edges = {}
        for e in edges:
            if isinstance(e, ComponentEdge):
                core_edges[e.key] = e.as_core_edge()
            else:
                key, value = e
                core_edges[key] = value
        full_fresh = {n: bool(fresh.get(n, False)) for n in self.names}
        return self.core.step(core_edges, phys or {}, hist or {},
                              var_ratio or {}, full_fresh)

    @property
    def trust(self) -> dict:
        return dict(self.core.trust)


def relation(key: str) -> Relation:
    for r in RELATIONS:
        if r.key == key:
            return r
    raise KeyError(f"no relation {key!r}; known: "
                   f"{sorted(r.key for r in RELATIONS)}")


def implicated_by(edge_keys, binding=None) -> dict:
    """Which nodes a set of violated edges implicates, and how often.

    THE POINT OF THIS FUNCTION IS THAT IT RETURNS A SET, NOT A CULPRIT.
    Every non-redundancy relation spans a causal direction the frozen core
    does not encode, so a violated actuator edge narrows the fault to the
    actuator, the plant and the sensor that measured the effect.

    `binding` MAPS RELATION ROLES TO PLATFORM NODES, AND WITHOUT IT THE
    CROSS-FAMILY RESULT IS ALWAYS EMPTY. `Relation.blames` carries ROLES --
    "actuator", "power_source" -- because the catalogue describes relations
    and not any one vehicle. Two relations from different families implicate
    the same PHYSICAL thing only once their roles are bound to the same node
    name, and the first version of this function omitted the binding and so
    could never report the cross-family agreement it exists to report. That
    is recorded rather than quietly corrected.

    A node implicated by edges from TWO DIFFERENT FAMILIES is the case that
    motivates combining the graphs: two independent physical arguments point
    at one component. Many implications inside ONE family are one argument,
    counted several times, and are reported separately for that reason.
    """
    binding = binding or {}
    counts, families, unbound = {}, {}, set()
    for key in edge_keys:
        rel = relation(key)
        for role in rel.blames:
            node = binding.get(role)
            if node is None:
                unbound.add(role)
                node = role
            counts[node] = counts.get(node, 0) + 1
            families.setdefault(node, set()).add(rel.family)
    cross = {n: sorted(families[n]) for n in sorted(families)
             if len(families[n]) > 1}
    return {
        "implicated": {n: counts[n] for n in sorted(counts)},
        "by_independent_families": cross,
        "unbound_roles": sorted(unbound),
        "binding_warning": (
            "roles were left unbound and are reported under their own names; "
            "cross-family agreement between them cannot be detected"
            if unbound else None),
        "reading": ("a node implicated by two or more FAMILIES is supported "
                    "by independent physical arguments; a node implicated "
                    "many times within one family is supported once, by "
                    "that family"),
    }
