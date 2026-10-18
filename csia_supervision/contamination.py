"""Where a sensor's trust came from, edge by edge.

THE PROBLEM THIS EXISTS FOR
---------------------------
SR-010 withdrew the motor_esc low-trust rule after a falsification search
found a healthy sensor raising CAUTION on combination 1 of 95. Two structural
guards were tried and both failed for the same reason, recorded then:

    The guard gates WHETHER TO JUDGE. It does not clean THE VALUE BEING
    JUDGED. A sensor can be judged on a trust value that was dragged down by
    exactly the partners the guard has just ruled unfit to judge it.

`T_i` is a scalar with no provenance attached. Every consumer downstream --
the failsafe policy, the supervision overlay, the capability bridge -- reads
it on faith and cannot ask which evidence produced it.

WHAT THIS MODULE DOES, AND WHAT IT DOES NOT
--------------------------------------------
It reconstructs, OUTSIDE the frozen core and without changing one byte of it,
the per-edge terms that the core computes and discards. From those terms a
caller can ask: *what would this sensor's neighbour consistency have been if
only these partners were counted?*

It does NOT compute a different trust value and it does NOT feed one back.
`T_i` remains whatever the frozen core says it is. This is a decomposition of
a number, not a replacement for it.

THE ARITHMETIC, WHICH IS THE FROZEN CORE'S AND NOT MINE
--------------------------------------------------------
`csia/trust_engine/engine.py:107-118`, for node n:

    for each edge e incident to n, with partner o:
        w_e = gate_e * trust_prev[o]
        SKIP the edge entirely if w_e <= 1e-6
        num += w_e * consistency_e
        den += w_e
    c_nbr = num / den   if den > 1e-6 else None

Two details are easy to get wrong and both change the answer:

  * `trust_prev[o]` is the PREVIOUS tick's trust. The core updates
    `self.trust` only after every node has been scored (engine.py:154, "all
    nodes saw tick k-1 trust during this step"), so a decomposition that uses
    the state's own `trust` map is off by one tick.
  * The `w_e <= 1e-6` cutoff DROPS the edge from both numerator and
    denominator. Treating it as a zero-weight contribution instead leaves
    `den` unchanged and gives a different mean.

EVERY RESULT FROM THIS MODULE IS CHECKED AGAINST THE CORE
----------------------------------------------------------
`verify` recomputes `c_nbr` from the decomposition and compares it to the
value the core published in `state.components[n]["nbr"]`. A decomposition
that does not sum back to the number it claims to decompose is not evidence
about anything, and the instrument that uses it must refuse to emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: The core's own cutoff. An edge at or below this weight is not merely
#: down-weighted -- it is absent from the mean entirely.
WEIGHT_EPSILON = 1e-6

#: What the core's trust map holds before the first tick:
#: alpha0 / (alpha0 + beta0), from EngineConfig. A decomposition of tick 0
#: needs it because there is no previous state to read.
from csia.trust_engine.engine import EngineConfig     # noqa: E402

PRIOR_TRUST = EngineConfig().alpha0 / (EngineConfig().alpha0
                                       + EngineConfig().beta0)


def edge_endpoints() -> dict:
    """edge key -> (node_a, node_b), derived independently of the layer.

    Built the same way `OnlineTrustLayer.__init__` builds `_edge_meta`,
    INCLUDING the `velocity_gps_doppler` split into `_0` and `_1` -- one
    relation name serves two distinct edges and a map that collapses them
    attributes imu1's evidence to imu0.

    Derived here rather than read from the layer's private attribute so the
    two are independent, and `test_contamination.py` asserts they are equal.
    A silent divergence would misattribute evidence with no error anywhere.
    """
    from csia.trust_graph.graph import EDGES
    meta = {}
    for a, b, relation, _desc in EDGES:
        meta.setdefault(relation, (a, b))
    meta["velocity_gps_doppler_0"] = ("imu0", "gps")
    meta["velocity_gps_doppler_1"] = ("imu1", "gps")
    meta.pop("velocity_gps_doppler", None)
    return meta


@dataclass(frozen=True)
class EdgeContribution:
    """One edge's share of a sensor's neighbour evidence."""

    edge: str
    partner: str
    #: exp(-0.5 * max(0, lam - 1)): how well the two endpoints agree.
    consistency: float
    #: The edge gate, already carrying both endpoints' freshness.
    gate: float
    #: The PARTNER's trust at the previous tick -- the weight the core gives
    #: this partner's opinion.
    partner_trust: float
    #: gate * partner_trust.
    weight: float
    #: weight / total admitted weight. How much of the sensor's neighbour
    #: evidence this one edge is responsible for.
    share: float


@dataclass(frozen=True)
class NeighbourDecomposition:
    """A sensor's `c_nbr`, taken apart into the edges that produced it."""

    sensor: str
    contributions: tuple
    #: The reconstructed neighbour consistency. None when the core would
    #: also report None (no edge cleared the weight cutoff).
    c_nbr: Optional[float]
    weight_total: float
    #: Edges incident to this sensor that the cutoff DROPPED. Recorded
    #: because "no corroboration" and "corroboration from a partner nobody
    #: trusts" are different situations and the aggregate hides both.
    dropped: tuple

    def restricted(self, admissible) -> "RestrictedNeighbour":
        """`c_nbr` over the admissible partners alone.

        This is the whole point of the module: a judgement about sensor n can
        rest on the evidence from partners in good standing rather than on an
        aggregate that a suspect partner has already moved.
        """
        keep = [c for c in self.contributions if c.partner in admissible]
        w = sum(c.weight for c in keep)
        value = (sum(c.weight * c.consistency for c in keep) / w
                 if w > WEIGHT_EPSILON else None)
        return RestrictedNeighbour(
            sensor=self.sensor,
            admissible=frozenset(admissible),
            c_nbr=value,
            partners_counted=tuple(sorted(c.partner for c in keep)),
            partners_excluded=tuple(sorted(
                c.partner for c in self.contributions
                if c.partner not in admissible)),
            weight_admissible=w,
            coverage=(w / self.weight_total
                      if self.weight_total > WEIGHT_EPSILON else 0.0),
        )


@dataclass(frozen=True)
class RestrictedNeighbour:
    """`c_nbr` recomputed over a subset of partners."""

    sensor: str
    admissible: frozenset
    c_nbr: Optional[float]
    partners_counted: tuple
    partners_excluded: tuple
    weight_admissible: float
    #: What fraction of the sensor's neighbour evidence survived the
    #: restriction. A judgement made at coverage 0.15 rests on almost
    #: nothing, and a caller that does not look at this number will not know.
    coverage: float


def decompose(sensor: str, state, prev_trust: dict,
              endpoints: Optional[dict] = None) -> NeighbourDecomposition:
    """Take one sensor's neighbour consistency apart.

    `prev_trust` is the trust map from the PREVIOUS tick -- for the first
    tick, `{n: PRIOR_TRUST}`. Passing this tick's own map silently shifts
    every weight by one tick, which is why `verify` exists.
    """
    meta = endpoints if endpoints is not None else edge_endpoints()
    kept, dropped = [], []
    for edge, value in (state.edges or {}).items():
        pair = meta.get(edge)
        if pair is None:
            continue
        a, b = pair
        if sensor not in (a, b):
            continue
        partner = b if a == sensor else a
        consistency, gate = float(value[0]), float(value[1])
        weight = gate * float(prev_trust.get(partner, PRIOR_TRUST))
        if weight <= WEIGHT_EPSILON:
            dropped.append(edge)
            continue
        kept.append((edge, partner, consistency, gate, weight))

    total = sum(k[4] for k in kept)
    contributions = tuple(
        EdgeContribution(edge=e, partner=p, consistency=c, gate=g,
                         partner_trust=(w / g if g > 0 else 0.0),
                         weight=w,
                         share=(w / total if total > WEIGHT_EPSILON else 0.0))
        for e, p, c, g, w in kept)
    value = (sum(k[4] * k[2] for k in kept) / total
             if total > WEIGHT_EPSILON else None)
    return NeighbourDecomposition(
        sensor=sensor, contributions=contributions, c_nbr=value,
        weight_total=total, dropped=tuple(sorted(dropped)))


def verify(state, prev_trust: dict, endpoints: Optional[dict] = None,
           tolerance: float = 1e-12) -> dict:
    """Check the decomposition against the number the core published.

    THE CONTROL FOR EVERY CLAIM IN THIS MODULE. A per-edge breakdown that
    does not sum back to the core's own `c_nbr` is a story about the system,
    not a measurement of it.

    Returns a per-sensor comparison and an overall verdict. `agree` counts
    only sensors where BOTH sides produced a value or BOTH produced None --
    a reconstruction that returns None where the core returned 0.4 is a
    disagreement, not a skip.
    """
    meta = endpoints if endpoints is not None else edge_endpoints()
    rows, worst, disagreements = [], 0.0, 0
    for sensor, comps in (state.components or {}).items():
        core = comps.get("nbr")
        mine = decompose(sensor, state, prev_trust, meta).c_nbr
        if core is None or mine is None:
            ok = (core is None) == (mine is None)
            diff = None
        else:
            diff = abs(core - mine)
            ok = diff <= tolerance
            worst = max(worst, diff)
        if not ok:
            disagreements += 1
        rows.append({"sensor": sensor, "core": core, "reconstructed": mine,
                     "abs_diff": diff, "agree": ok})
    return {
        "sensors": rows,
        "disagreements": disagreements,
        "worst_abs_diff": worst,
        "tolerance": tolerance,
        "verdict": "EXACT" if disagreements == 0 else "RECONSTRUCTION_WRONG",
    }


class ShadowTrust:
    """The frozen Beta recursion, re-run outside the core on RESTRICTED evidence.

    WHY A WHOLE RECURSION AND NOT JUST `c_nbr`
    -------------------------------------------
    The low-trust rules threshold `T_i`, a Beta posterior accumulated over
    thousands of ticks. `c_nbr` is an instantaneous consistency score on a
    different scale. Swapping one for the other and keeping the threshold
    would be inventing a number, so instead the same recursion is run on the
    same components with ONLY `c_nbr` replaced by its restricted form. The
    output is on `T_i`'s scale and the existing threshold means what it meant.

    WHAT IS RESTRICTED AND WHAT IS NOT
    -----------------------------------
    The partner SET, and nothing else. The per-edge consistencies and the
    partner trusts are the CORE's, read from the state. This is a
    decomposition of the core's number under a counterfactual partner set --
    not a parallel trust engine with its own beliefs feeding its own edge
    weights. Letting the shadow's trust drive the shadow's weights would make
    it a different system, and comparing it to the core would then establish
    nothing.

    THE CONTROL, WHICH IS THE ONLY REASON TO BELIEVE ANY OF THIS
    -------------------------------------------------------------
    With every partner admissible, this must reproduce `state.trust` exactly.
    `ShadowTrust.max_drift_when_unrestricted` records how far it did not, and
    a probe whose unrestricted drift is non-trivial has measured its own bug
    rather than the system.

    Arithmetic mirrored from `csia/trust_engine/engine.py:131-149`. Not one
    byte of that file changed.
    """

    def __init__(self, sensors, admissible=None, config: EngineConfig = None):
        cfg = config or EngineConfig()
        self.cfg = cfg
        self.sensors = list(sensors)
        self.alpha = {n: cfg.alpha0 for n in self.sensors}
        self.beta = {n: cfg.beta0 for n in self.sensors}
        self.trust = {n: cfg.alpha0 / (cfg.alpha0 + cfg.beta0)
                      for n in self.sensors}
        #: sensor -> callable(sensor, state, prev_trust) -> set of admissible
        #: partners. None means "every partner", i.e. the control.
        self.admissible = admissible
        self.max_drift_when_unrestricted = 0.0
        self._endpoints = edge_endpoints()
        self.coverage = {n: 1.0 for n in self.sensors}

    def step(self, state, prev_trust: dict) -> dict:
        cfg = self.cfg
        for n in self.sensors:
            comps = (state.components or {}).get(n) or {}
            if self.admissible is None:
                c_nbr = comps.get("nbr")
                cover = 1.0
            else:
                d = decompose(n, state, prev_trust, self._endpoints)
                r = d.restricted(self.admissible(n, state, prev_trust))
                c_nbr, cover = r.c_nbr, r.coverage
            self.coverage[n] = cover

            parts = [(cfg.w_nbr, c_nbr), (cfg.w_phys, comps.get("phys")),
                     (cfg.w_temp, comps.get("temp")),
                     (cfg.w_stat, comps.get("stat"))]
            avail = [(w, c) for w, c in parts if c is not None]
            wsum = sum(w for w, _ in avail)
            evidence = (sum(w * c for w, c in avail) / wsum
                        if avail else 0.5)
            scores = [c for _, c in avail]
            spread = max(scores) - min(scores) if len(scores) > 1 else 0.0
            rho = cfg.rho_max - (cfg.rho_max - cfg.rho_min) * spread
            if avail and (state.fresh or {}).get(n, True):
                self.alpha[n] = rho * self.alpha[n] + evidence
                self.beta[n] = rho * self.beta[n] + (1.0 - evidence)
            self.trust[n] = self.alpha[n] / (self.alpha[n] + self.beta[n])
            if self.admissible is None:
                core = (state.trust or {}).get(n)
                if core is not None:
                    self.max_drift_when_unrestricted = max(
                        self.max_drift_when_unrestricted,
                        abs(float(core) - self.trust[n]))
        return dict(self.trust)


def supporting_edges(sensor: str, state, prev_trust: dict,
                     endpoints: Optional[dict] = None) -> list:
    """The edges holding this sensor up, heaviest share first."""
    d = decompose(sensor, state, prev_trust, endpoints)
    return sorted(d.contributions, key=lambda c: c.share, reverse=True)


def evidence_support(evidence_id: str, state, prev_trust: dict,
                     endpoints: Optional[dict] = None) -> dict:
    """WHICH evidence is holding a capability up, and which leg is weak.

    The question the system could not answer before. `evidence_overrides`
    reports that `baro.altitude.supported` is SUPPORTED or is not; it cannot
    say what that support rests on. Here the same evidence id is traced back
    through the sensor it reads from to the edges corroborating that sensor,
    each with its share of the total.

    THIS IS DESCRIPTIVE AND CHANGES NO STATE. It does not promote, demote or
    resolve anything -- the capability bridge remains demote-only and UNKNOWN
    is still never resolved. A weak leg reported here is information for a
    human, not an input to a gate.

    "WEAK LEG" IS TWO DIFFERENT QUESTIONS AND THEY ARE REPORTED SEPARATELY.
    The edge carrying the SMALLEST SHARE contributes least; the edge with the
    LOWEST CONSISTENCY agrees least. A well-corroborated partner in flat
    disagreement is the interesting case and it has a large share, so
    collapsing the two into one "weakest" field would hide exactly the
    situation worth seeing. Both are None when the sensor has no admitted
    corroboration at all, which is not the same as "the weak leg is fine".
    """
    from csia_supervision.capability_bridge import (REQUIRES_ALL_LOST,
                                                    SENSOR_EVIDENCE)
    sensors = sorted(s for s, ids in SENSOR_EVIDENCE.items()
                     if evidence_id in ids)
    if not sensors and evidence_id in REQUIRES_ALL_LOST:
        sensors = sorted(REQUIRES_ALL_LOST[evidence_id])
    if not sensors:
        return {"evidence_id": evidence_id, "status": "NO_SENSOR_MAPPING",
                "detail": ("no sensor in SENSOR_EVIDENCE or REQUIRES_ALL_LOST "
                           "reads this evidence; its support cannot be traced "
                           "and is not guessed")}
    legs = []
    for sensor in sensors:
        d = decompose(sensor, state, prev_trust, endpoints)
        ranked = sorted(d.contributions, key=lambda c: c.share, reverse=True)
        legs.append({
            "sensor": sensor,
            "trust": (state.trust or {}).get(sensor),
            "c_nbr": d.c_nbr,
            "edges": [{"edge": c.edge, "partner": c.partner,
                       "share": c.share, "consistency": c.consistency,
                       "partner_trust": c.partner_trust} for c in ranked],
            "edges_dropped_below_weight_cutoff": list(d.dropped),
            "smallest_share": ({"edge": ranked[-1].edge,
                                "partner": ranked[-1].partner,
                                "share": ranked[-1].share}
                               if ranked else None),
            "lowest_consistency": (
                {"edge": min(ranked, key=lambda c: c.consistency).edge,
                 "partner": min(ranked, key=lambda c: c.consistency).partner,
                 "consistency": min(c.consistency for c in ranked),
                 "share": min(ranked, key=lambda c: c.consistency).share}
                if ranked else None),
        })
    return {
        "evidence_id": evidence_id, "status": "TRACED", "legs": legs,
        "reading_note": (
            "`smallest_share` contributes least; `lowest_consistency` agrees "
            "least. They are different questions and a well-corroborated "
            "partner in flat disagreement shows up only in the second."),
    }
