"""Ratio-invariant common-cause reasoning (slice 3C).

Replaces the slice-3B shared-cause statistic, which was an arithmetic mean
over a flat feature list spanning two sources. That shape encoded one
amplitude relationship: battery-side and motor-side features degrade by
different amounts depending on the injected ratio, so the mean peaked only
near the development ratio 1.2 V : 350 rpm and collapsed elsewhere
(docs/audit/CSIA_SHARED_POWER_GENERALIZATION_AUDIT.md).

The redesign asks the causal question instead:

    Are multiple sources degrading in a temporally and structurally
    consistent way that is better explained by ONE shared resource than by
    independent faults?

Two levels, bounded:

    per-source degradation      each source scored against its OWN indicators
            |                   (severity normalised within the source, so no
            v                   cross-source amplitude ratio can leak in)
    shared-resource hypothesis  geometric mean over member sources x temporal
            |                   coherence x topology support/contradiction
            v
    expected affected-source set

Scores are HEURISTIC. They are not calibrated probabilities and must not be
described as such.
"""

import math
from dataclasses import dataclass, field

# --- topology: declared from the vehicle, and actually consulted -------------

#: resource -> sources it feeds. Unlike slice 3B's decorative SHARED_RESOURCES,
#: this is read by the inference path: membership, expected-affected-set
#: derivation, and contradiction when a strongly coupled member stays healthy.
RESOURCE_TOPOLOGY = {
    "MAIN_POWER_PACK": {
        # source -> coupling strength in [0, 1]. A strongly coupled source
        # that stays healthy CONTRADICTS the hypothesis.
        "battery": 1.0,
        "motor_esc": 1.0,
        "vibration": 0.3,     # weakly coupled: rotor loading follows power
    },
}

#: source -> the indicators that speak for THAT source only. Per-source
#: aggregation over its own list is what makes scoring ratio-invariant.
SOURCE_INDICATORS = {
    "battery": ("phys_battery", "temp_battery"),
    "motor_esc": ("phys_motor_esc", "accel_esc_rpm"),
    "vibration": ("phys_vibration", "temp_vibration", "vibration_prop_freq"),
    "imu0": ("redundant_imu", "accel_motor_current"),
    "imu1": ("redundant_imu", "accel_esc_rpm"),
    "gps": ("phys_gps", "temp_gps"),
    "mag": ("phys_mag", "temp_mag", "heading_course"),
    "baro": ("phys_baro",),
}

#: Indicators that are valid consistency checks but NOT diagnostic for a power
#: sag: the imu0<->motor_esc edge validates accel/current coherence, and a sag
#: moves both coherently, so it correctly stays green. Measured 0.000 in every
#: case (audit D-2). Excluded from support; retained as contradiction.
NON_DIAGNOSTIC_FOR_POWER = ("accel_motor_current",)

#: Severity normalisation: consistency c in (0,1] -> degradation in [0,1].
#: Bounded monotonic transformation about a knee. Chosen over a raw (1-c)
#: because indicator scales differ; documented in FAULT_HYPOTHESIS_MODEL.md.
KNEE_C = 0.70
SHARPNESS = 6.0

#: A source counts as degraded above this normalised score.
SOURCE_DEGRADED = 0.45
#: Temporal coherence window: full credit inside, decaying to zero at the far
#: edge. Monotonic — one sample of skew must not change the answer.
TEMPORAL_FULL_S = 2.5
TEMPORAL_ZERO_S = 9.0


def normalize_severity(c: float) -> float:
    """Bounded monotonic severity in [0, 1] from a consistency score.

    Logistic about KNEE_C. Monotonically decreasing in c, so a more consistent
    reading always yields lower severity, and saturates at both ends so a
    single extreme indicator cannot dominate a source's score.
    """
    return 1.0 / (1.0 + math.exp(SHARPNESS * (c - KNEE_C) * 4.0))


def _robust_source_score(indicators, features):
    """Aggregate ONE source's own indicators into one degradation score.

    Uses the max over valid indicators: a source is degraded if ANY of its own
    indicators says so. This is the step that removes cross-source amplitude
    coupling — a weak motor response no longer drags down a strong battery
    signal, because they are never averaged together.
    """
    vals = []
    for name in indicators:
        f = features.get(name)
        if f is None:
            continue
        c, gate = float(f[0]), float(f[1])
        if gate <= 1e-9:
            continue
        vals.append(normalize_severity(c))
    if not vals:
        return None, 0
    return max(vals), len(vals)


def temporal_coherence(onsets) -> float:
    """Monotonic co-onset evidence in [0, 1].

    Slice 3B used a step function (<=2 s -> 1.0, <=5 s -> 0.5, else 0), so one
    extra sample of skew changed the answer discontinuously. This decays
    linearly from TEMPORAL_FULL_S to TEMPORAL_ZERO_S, which also credits
    genuine propagation delay: a resource degrades, dependent systems follow.
    """
    onsets = [o for o in onsets if o is not None]
    if len(onsets) < 2:
        return 0.0
    spread = max(onsets) - min(onsets)
    if spread <= TEMPORAL_FULL_S:
        return 1.0
    if spread >= TEMPORAL_ZERO_S:
        return 0.0
    return 1.0 - (spread - TEMPORAL_FULL_S) / (TEMPORAL_ZERO_S - TEMPORAL_FULL_S)


@dataclass
class SourceDegradation:
    source: str
    degradation_score: float
    indicator_count: int
    onset_t: float | None = None
    degraded: bool = False

    def to_dict(self):
        return {"source": self.source,
                "degradation_score": round(self.degradation_score, 4),
                "indicator_count": self.indicator_count,
                "onset_t": self.onset_t, "degraded": self.degraded}


@dataclass
class SharedCauseAssessment:
    """Ranking and activation are deliberately separate quantities."""
    resource: str
    support: float = 0.0                 # ranking / diagnostic support
    topology_support: float = 0.0
    topology_contradiction: float = 0.0
    temporal_coherence: float = 0.0
    degraded_members: tuple = ()
    healthy_strong_members: tuple = ()
    expected_affected: tuple = ()
    independent_alternative: float = 0.0
    reason_codes: tuple = ()
    per_source: dict = field(default_factory=dict)

    def to_dict(self):
        d = dict(self.__dict__)
        d["per_source"] = {k: v.to_dict() for k, v in self.per_source.items()}
        for k in ("support", "topology_support", "topology_contradiction",
                  "temporal_coherence", "independent_alternative"):
            d[k] = round(d[k], 4)
        return d


class CausalSharedCauseModel:
    """Hierarchical, ratio-invariant shared-resource reasoning.

    Bounded: fixed topology, fixed indicator lists, fixed onset memory
    (one float per source), deterministic ordering. No runtime allocation of
    hypotheses.
    """

    def __init__(self, topology=None,
                 enable_normalization: bool = True,
                 enable_topology: bool = True,
                 enable_temporal: bool = True,
                 enable_contradiction: bool = True,
                 enable_independent_alternative: bool = True):
        self.topology = topology or RESOURCE_TOPOLOGY
        self.enable_normalization = enable_normalization
        self.enable_topology = enable_topology
        self.enable_temporal = enable_temporal
        self.enable_contradiction = enable_contradiction
        self.enable_independent_alternative = enable_independent_alternative
        self._onset: dict = {}          # source -> first t seen degraded

    def source_scores(self, t: float, features: dict) -> dict:
        out = {}
        for src, inds in SOURCE_INDICATORS.items():
            usable = tuple(i for i in inds
                           if i not in NON_DIAGNOSTIC_FOR_POWER)
            score, n = _robust_source_score(usable or inds, features)
            if score is None:
                out[src] = SourceDegradation(src, 0.0, 0)
                continue
            if not self.enable_normalization:
                # ablation: raw mean over the source's own indicators
                vals = [1.0 - float(features[i][0]) for i in (usable or inds)
                        if i in features and float(features[i][1]) > 1e-9]
                score = sum(vals) / len(vals) if vals else 0.0
            deg = score >= SOURCE_DEGRADED
            if deg and src not in self._onset:
                self._onset[src] = t
            elif not deg and src in self._onset and score < SOURCE_DEGRADED * 0.6:
                self._onset.pop(src, None)
            out[src] = SourceDegradation(src, score, n,
                                         self._onset.get(src), deg)
        return out

    def assess(self, t: float, features: dict, resource: str
               ) -> SharedCauseAssessment:
        per_source = self.source_scores(t, features)
        members = self.topology.get(resource, {})
        reasons = []

        strong = {s: w for s, w in members.items() if w >= 0.9}
        degraded = tuple(sorted(s for s in strong if per_source[s].degraded))
        healthy_strong = tuple(sorted(s for s in strong
                                      if not per_source[s].degraded))

        a = SharedCauseAssessment(resource=resource, per_source=per_source,
                                  degraded_members=degraded,
                                  healthy_strong_members=healthy_strong,
                                  expected_affected=tuple(sorted(strong)))

        if len(degraded) < 2:
            a.reason_codes = ("FEWER_THAN_TWO_COUPLED_SOURCES_DEGRADED",)
            return a

        # Geometric mean over member scores: BOTH must be degraded (an
        # arithmetic mean would let a strong battery signal compensate for an
        # absent motor signal), but it is far less brutal than min().
        scores = [per_source[s].degradation_score for s in degraded]
        prod = 1.0
        for v in scores:
            prod *= max(v, 1e-6)
        base = prod ** (1.0 / len(scores))
        reasons.append("GEOMETRIC_MEAN_OVER_COUPLED_SOURCES")

        # --- topology is LOAD-BEARING here ---------------------------------
        if self.enable_topology:
            # support scales with the fraction of strongly coupled members
            # that are degraded ...
            a.topology_support = len(degraded) / max(len(strong), 1)
            reasons.append("SHARED_RESOURCE_MEMBERSHIP_CONFIRMED")
            # ... and a strongly coupled member that stays HEALTHY contradicts
            # a resource-level cause.
            if self.enable_contradiction and healthy_strong:
                a.topology_contradiction = len(healthy_strong) / len(strong)
                reasons.append("STRONGLY_COUPLED_MEMBER_HEALTHY")
            # degraded sources OUTSIDE the resource weaken it too
            outside = [s for s, d in per_source.items()
                       if d.degraded and s not in members]
            if self.enable_contradiction and outside:
                a.topology_contradiction = min(
                    1.0, a.topology_contradiction + 0.25 * len(outside))
                reasons.append("DEGRADATION_OUTSIDE_RESOURCE")
            base *= (0.45 + 0.55 * a.topology_support)
            base *= (1.0 - 0.6 * a.topology_contradiction)
        else:
            reasons.append("TOPOLOGY_DISABLED")

        # --- temporal coherence --------------------------------------------
        if self.enable_temporal:
            a.temporal_coherence = temporal_coherence(
                [per_source[s].onset_t for s in degraded])
            base *= (0.35 + 0.65 * a.temporal_coherence)
            reasons.append("CO_ONSET_COHERENT" if a.temporal_coherence > 0.75
                           else "ONSETS_DISPERSED")
        else:
            reasons.append("TEMPORAL_DISABLED")

        # --- independent-fault alternative ---------------------------------
        if self.enable_independent_alternative:
            # Independent faults are favoured by dispersed onsets and by
            # degradation that does not respect resource membership.
            a.independent_alternative = min(1.0, (
                (1.0 - a.temporal_coherence) * 0.6
                + a.topology_contradiction * 0.4))
            reasons.append("INDEPENDENT_ALTERNATIVE_CONSIDERED")

        a.support = max(0.0, min(1.0, base))
        a.reason_codes = tuple(reasons)
        return a
