"""Fault-hypothesis layer — SHADOW / ADVISORY ONLY.

Slice 3B. The existing `DiagnosisCore` answers *"which single label best fits
the signature?"* by softmaxing 8 mutually exclusive causes. That cannot express
a shared cause: `power_sag` injects two faults from one physical event, and the
softmax makes `power_fault` and every other label compete for one unit of
probability mass.

This layer answers a different question — *"which sources, shared resources,
estimators or unknown mechanisms explain the evidence?"* — and answers it
WITHOUT normalizing across hypotheses, so a root cause and its downstream
effects can be true at the same time.

PRODUCT BOUNDARY (enforced by architecture, not just intent): `FailsafePolicy`
consumes the diagnosis posterior only to build a display string — no
condition, threshold, dwell, level or action reads it (audit Q10). Nothing
here can alter active behaviour. Every recommendation carries
`active_application_permitted = False`.

Bounded by construction: fixed hypothesis registry, fixed max sources per
hypothesis, stable ordering, deterministic tie-breaking, no runtime allocation
of new hypotheses.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum

HYPOTHESIS_SCHEMA_VERSION = "1.0.0"

#: Bounds for eventual C implementation. Exceeding them is a configuration
#: error, not a runtime resize.
MAX_HYPOTHESES = 32
MAX_SOURCES_PER_HYPOTHESIS = 8


class HypothesisClass(str, Enum):
    SINGLE_SOURCE = "SINGLE_SOURCE"
    MULTI_SOURCE_INDEPENDENT = "MULTI_SOURCE_INDEPENDENT"
    SHARED_POWER = "SHARED_POWER"
    SHARED_CLOCK = "SHARED_CLOCK"
    SHARED_BUS = "SHARED_BUS"
    SHARED_ENVIRONMENT = "SHARED_ENVIRONMENT"
    ESTIMATOR_FAILURE = "ESTIMATOR_FAILURE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    UNKNOWN_INCONSISTENCY = "UNKNOWN_INCONSISTENCY"


class DiagnosticState(str, Enum):
    INACTIVE = "INACTIVE"
    EMERGING = "EMERGING"
    ACTIVE = "ACTIVE"
    RECOVERING = "RECOVERING"


class Authorization(str, Enum):
    ADVISORY_ONLY = "ADVISORY_ONLY"
    SHADOW_ONLY = "SHADOW_ONLY"


class Usability(str, Enum):
    """Per FUNCTION, not per source. A source can be usable for one function
    and unusable for another — GNSS timing can survive a position spoof."""
    USABLE = "USABLE"
    DEGRADED = "DEGRADED"
    UNUSABLE = "UNUSABLE"
    UNKNOWN = "UNKNOWN"


class IsolationOutcome(str, Enum):
    CORRECT_SINGLE_SOURCE = "CORRECT_SINGLE_SOURCE"
    CORRECT_MULTI_SOURCE = "CORRECT_MULTI_SOURCE"
    CORRECT_COMMON_CAUSE = "CORRECT_COMMON_CAUSE"
    CORRECT_ESTIMATOR_CAUSE = "CORRECT_ESTIMATOR_CAUSE"
    PARTIAL_ISOLATION = "PARTIAL_ISOLATION"
    OVER_ISOLATION = "OVER_ISOLATION"
    UNDER_ISOLATION = "UNDER_ISOLATION"
    INCORRECT_ISOLATION = "INCORRECT_ISOLATION"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN_DETECTED = "UNKNOWN_DETECTED"
    NONE = "NONE"


class Recommendation(str, Enum):
    MONITOR_SHARED_RESOURCE = "MONITOR_SHARED_RESOURCE"
    DEGRADE_AFFECTED_SOURCE_SET = "DEGRADE_AFFECTED_SOURCE_SET"
    INCREASE_NAVIGATION_UNCERTAINTY = "INCREASE_NAVIGATION_UNCERTAINTY"
    REQUEST_REDUNDANCY_CHECK = "REQUEST_REDUNDANCY_CHECK"
    REQUEST_ESTIMATOR_HEALTH_CHECK = "REQUEST_ESTIMATOR_HEALTH_CHECK"
    ENTER_DIAGNOSTIC_SHADOW_STATE = "ENTER_DIAGNOSTIC_SHADOW_STATE"
    INSUFFICIENT_EVIDENCE_FOR_SOURCE_ISOLATION = \
        "INSUFFICIENT_EVIDENCE_FOR_SOURCE_ISOLATION"


# --- evidence ----------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceRecord:
    """One explainable observation. Confidence must never be opaque."""
    evidence_id: str
    t: float
    source_or_relationship: str
    residual_value: float             # consistency c in (0, 1]
    normalized_residual: float | None
    expected_uncertainty: float | None
    direction: str                    # LOW | HIGH
    persistence_s: float
    valid: bool                       # gate open at this tick
    context: str                      # SIMULATION | SITL | REAL_LOG_REPLAY ...
    supports: tuple = ()
    contradicts: tuple = ()
    score_contribution: float = 0.0
    reason_code: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --- hypotheses ---------------------------------------------------------------

@dataclass
class Hypothesis:
    """A bounded, statically declared explanation."""
    hypothesis_id: str
    hypothesis_class: str
    affected_sources: tuple = ()
    shared_resource: str | None = None
    parent_hypothesis_id: str | None = None
    required_evidence: tuple = ()      # features expected LOW
    contradicting_evidence: tuple = () # features expected to stay HIGH
    prior: float = 0.01
    confidence: float = 0.0
    isolation_confidence: float = 0.0
    diagnostic_state: str = DiagnosticState.INACTIVE.value
    operational_authorization: str = Authorization.SHADOW_ONLY.value
    reason_codes: tuple = ()

    def __post_init__(self):
        if len(self.affected_sources) > MAX_SOURCES_PER_HYPOTHESIS:
            raise ValueError(
                f"{self.hypothesis_id}: {len(self.affected_sources)} sources "
                f"exceeds MAX_SOURCES_PER_HYPOTHESIS={MAX_SOURCES_PER_HYPOTHESIS}")

    def to_dict(self) -> dict:
        return asdict(self)


#: Shared-resource topology. Declared from the vehicle, not learned.
#: The SOW001 sensor rail feeds the avionics sensors; the motor/ESC branch
#: shares the main pack with the battery monitor.
SHARED_RESOURCES = {
    "MAIN_POWER_PACK": ("battery", "motor_esc", "vibration"),
}

#: The static registry. Order is stable and IS the tie-break order.
REGISTRY = (
    Hypothesis(
        hypothesis_id="H_SHARED_POWER_DEGRADATION",
        hypothesis_class=HypothesisClass.SHARED_POWER.value,
        affected_sources=("battery", "motor_esc"),
        shared_resource="MAIN_POWER_PACK",
        required_evidence=("phys_battery", "temp_battery", "phys_motor_esc",
                           "accel_motor_current", "accel_esc_rpm"),
        contradicting_evidence=("redundant_imu", "phys_gps", "phys_mag"),
        prior=0.01,
    ),
    Hypothesis(
        hypothesis_id="H_MULTI_INDEPENDENT_IMU",
        hypothesis_class=HypothesisClass.MULTI_SOURCE_INDEPENDENT.value,
        affected_sources=("imu0", "imu1"),
        required_evidence=("redundant_imu", "accel_motor_current",
                           "accel_esc_rpm"),
        contradicting_evidence=("phys_battery", "temp_battery"),
        prior=0.01,
    ),
    Hypothesis(
        hypothesis_id="H_ESTIMATOR_DIVERGENCE",
        hypothesis_class=HypothesisClass.ESTIMATOR_FAILURE.value,
        affected_sources=(),
        required_evidence=(),          # no estimator signals exist (audit Q8)
        prior=0.005,
        reason_codes=("NO_ESTIMATOR_SIGNALS_AVAILABLE",),
    ),
    Hypothesis(
        hypothesis_id="H_UNKNOWN_CROSS_SENSOR_INCONSISTENCY",
        hypothesis_class=HypothesisClass.UNKNOWN_INCONSISTENCY.value,
        affected_sources=(),
        prior=0.005,
    ),
)

assert len(REGISTRY) <= MAX_HYPOTHESES

#: Evidence below this consistency counts as "degraded".
DEGRADED_C = 0.75
#: Strongly degraded — required before evidence can support UNKNOWN. A mild
#: dip is not an unexplained inconsistency.
STRONGLY_DEGRADED_C = 0.50
#: Ticks a hypothesis must hold above EMERGING before it may become ACTIVE
#: (25 Hz -> 1.0 s). Mirrors the failsafe's dwell principle: no single-tick
#: conclusions.
DWELL_TICKS = 25
#: Seconds of startup ignored entirely. Trust priors, EW smoothers and gates
#: are still converging; every feature looks transiently degraded. The
#: failsafe applies the same idea via arm_time.
DEFAULT_ARM_TIME_S = 10.0
#: A supported hypothesis must reach this to be ACTIVE.
ACTIVE_CONF = 0.60
EMERGING_CONF = 0.30
#: Unknown activates only when real inconsistency is unexplained by any
#: supported hypothesis. All conditions are required — this is what stops
#: UNKNOWN dominating every ambiguous case.
UNKNOWN_MIN_UNEXPLAINED = 0.35
UNKNOWN_MAX_BEST_SUPPORTED = 0.45
#: H_UNKNOWN_CROSS_SENSOR_INCONSISTENCY is by definition CROSS-sensor: it
#: requires at least this many distinct unexplained relationships. One lone
#: degraded relationship is a single-source concern the legacy diagnoser
#: already covers, and benign manoeuvres routinely produce exactly one (the
#: scripted yaw-in-place drives attitude_gravity_mag to ~0.37 on clean
#: flight). Without this, UNKNOWN fires on healthy flight.
UNKNOWN_MIN_DISTINCT_FEATURES = 2


@dataclass
class HypothesisReport:
    """Shadow diagnostic output. Never consumed by active logic."""
    t: float
    schema_version: str = HYPOTHESIS_SCHEMA_VERSION
    most_probable_root_cause: str | None = None
    active_contributing_causes: tuple = ()
    affected_sources: tuple = ()
    alternative_hypotheses: tuple = ()
    residual_unexplained_evidence: float = 0.0
    diagnostic_ambiguity: float = 0.0
    source_usability: dict = field(default_factory=dict)
    source_fault_confidence: dict = field(default_factory=dict)
    hypotheses: tuple = ()
    evidence: tuple = ()
    recommendations: tuple = ()
    legacy_top_cause: str | None = None
    notes: tuple = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hypotheses"] = [h.to_dict() if hasattr(h, "to_dict") else h
                           for h in self.hypotheses]
        d["evidence"] = [e.to_dict() if hasattr(e, "to_dict") else e
                         for e in self.evidence]
        return d


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


class HypothesisEngine:
    """Scores the static registry against comparator features.

    Deliberately NOT a softmax: each hypothesis is scored independently on
    [0, 1] so a shared cause and its downstream single-source effects can be
    simultaneously active. Ambiguity is reported, not resolved by argmax.
    """

    def __init__(self, registry=REGISTRY, context: str = "SIMULATION",
                 enable_shared_cause: bool = True,
                 enable_temporal_evidence: bool = True,
                 enable_topology_evidence: bool = True,
                 arm_time_s: float = DEFAULT_ARM_TIME_S,
                 dwell_ticks: int = DWELL_TICKS):
        self.registry = tuple(registry)
        self.context = context
        self.enable_shared_cause = enable_shared_cause
        self.enable_temporal_evidence = enable_temporal_evidence
        self.enable_topology_evidence = enable_topology_evidence
        self.arm_time_s = arm_time_s
        self.dwell_ticks = dwell_ticks
        self._onset: dict = {}          # feature -> first tick seen degraded
        self._held: dict = {}           # hypothesis_id -> consecutive ticks
        self._seq = 0

    # -- evidence ---------------------------------------------------------

    def _evidence(self, t, features):
        out = []
        for name in sorted(features):
            c, gate = features[name]
            c = float(c)
            valid = float(gate) > 1e-9
            degraded = valid and c < DEGRADED_C
            if degraded and name not in self._onset:
                self._onset[name] = t
            if not degraded and name in self._onset and c > DEGRADED_C + 0.1:
                self._onset.pop(name, None)
            self._seq += 1
            supports = tuple(h.hypothesis_id for h in self.registry
                             if name in h.required_evidence)
            contradicts = tuple(h.hypothesis_id for h in self.registry
                                if name in h.contradicting_evidence)
            out.append(EvidenceRecord(
                evidence_id=f"E{self._seq:06d}",
                t=t, source_or_relationship=name,
                residual_value=round(c, 4),
                normalized_residual=None,
                expected_uncertainty=None,
                direction="LOW" if degraded else "HIGH",
                persistence_s=round(t - self._onset[name], 3)
                if name in self._onset else 0.0,
                valid=valid, context=self.context,
                supports=supports, contradicts=contradicts,
                score_contribution=round(1.0 - c, 4) if valid else 0.0,
                reason_code=("EVIDENCE_GATED_OUT" if not valid else
                             "DEGRADED_BELOW_THRESHOLD" if degraded else
                             "CONSISTENT")))
        return tuple(out)

    # -- scoring ----------------------------------------------------------

    def _score(self, h, features, t):
        """Support in [0,1] with an explicit reason trail.

        support   = mean degradation over required evidence that is VALID
        penalty   = mean degradation over contradicting evidence
        temporal  = fraction of required evidence degrading in one window
        """
        req = [(n, features[n]) for n in h.required_evidence if n in features]
        valid_req = [(n, c) for n, (c, g) in req if float(g) > 1e-9]
        if not valid_req:
            return 0.0, 0.0, ("NO_VALID_REQUIRED_EVIDENCE",)

        deg = [max(0.0, 1.0 - float(c)) for _, c in valid_req]
        support = sum(deg) / len(deg)
        reasons = []

        contra = [float(features[n][0]) for n in h.contradicting_evidence
                  if n in features and float(features[n][1]) > 1e-9]
        if contra and self.enable_topology_evidence:
            # Healthy contradicting evidence CONFIRMS a localized cause.
            intact = sum(1 for c in contra if c >= DEGRADED_C) / len(contra)
            support *= (0.35 + 0.65 * intact)
            if intact > 0.8:
                reasons.append("UNAFFECTED_RELATIONSHIPS_INTACT")
            elif intact < 0.4:
                reasons.append("CONTRADICTING_EVIDENCE_ALSO_DEGRADED")

        # Temporal co-onset: a SHARED cause degrades its sources together.
        temporal = 0.0
        if self.enable_temporal_evidence:
            onsets = [self._onset[n] for n, _ in valid_req if n in self._onset]
            if len(onsets) >= 2:
                spread = max(onsets) - min(onsets)
                temporal = 1.0 if spread <= 2.0 else (0.5 if spread <= 5.0 else 0.0)
                if temporal >= 1.0:
                    reasons.append("CO_ONSET_WITHIN_2S")
                elif temporal <= 0.0:
                    reasons.append("ONSETS_DISPERSED")
            elif len(onsets) == 1:
                reasons.append("SINGLE_SOURCE_ONSET_ONLY")

        is_shared = h.hypothesis_class in (
            HypothesisClass.SHARED_POWER.value,
            HypothesisClass.SHARED_CLOCK.value,
            HypothesisClass.SHARED_BUS.value,
            HypothesisClass.SHARED_ENVIRONMENT.value)
        if is_shared:
            if not self.enable_shared_cause:
                return 0.0, 0.0, ("SHARED_CAUSE_HYPOTHESIS_DISABLED",)
            # A shared cause REQUIRES co-onset; independent faults must not
            # be promoted to common cause just because they overlap.
            support *= (0.30 + 0.70 * temporal)
            reasons.append("SHARED_RESOURCE_TOPOLOGY_MATCHED"
                           if self.enable_topology_evidence
                           else "TOPOLOGY_EVIDENCE_DISABLED")
        elif h.hypothesis_class == HypothesisClass.MULTI_SOURCE_INDEPENDENT.value:
            # Independent multi-source is favoured by DISPERSED onsets.
            support *= (0.55 + 0.45 * (1.0 - temporal))
            reasons.append("INDEPENDENT_ONSET_PATTERN" if temporal < 1.0
                           else "ONSETS_TOO_ALIGNED_FOR_INDEPENDENT")

        # isolation confidence: how cleanly the affected set separates from
        # the unaffected set.
        iso = 0.0
        if h.affected_sources:
            iso = support * (1.0 if not contra else
                             sum(1 for c in contra if c >= DEGRADED_C) / len(contra))
        return min(1.0, support), min(1.0, iso), tuple(reasons)

    # -- per tick ---------------------------------------------------------

    def step(self, t: float, features: dict,
             legacy_top: str | None = None) -> HypothesisReport:
        ev = self._evidence(t, features)
        scored = []
        for h in self.registry:
            if h.hypothesis_class == HypothesisClass.UNKNOWN_INCONSISTENCY.value:
                continue
            conf, iso, reasons = self._score(h, features, t)
            scored.append((h, conf, iso, reasons))

        armed = t >= self.arm_time_s
        supported_best = max((c for _, c, _, _ in scored), default=0.0)

        # Unexplained evidence: STRONGLY degraded, valid, persistent features
        # claimed by NO hypothesis that is itself doing well. Mild dips and
        # startup transients are not unexplained inconsistencies — requiring
        # strong degradation plus persistence is what stops UNKNOWN from
        # dominating healthy-but-unusual flight.
        claimed = set()
        for h, conf, _, _ in scored:
            if conf >= EMERGING_CONF:
                claimed |= set(h.required_evidence)
        degraded_feats = [e for e in ev if e.valid and e.direction == "LOW"]
        strong = [e for e in degraded_feats
                  if e.residual_value < STRONGLY_DEGRADED_C
                  and e.persistence_s >= 1.0]
        unexplained = [e for e in strong
                       if e.source_or_relationship not in claimed]
        residual = (sum(e.score_contribution for e in unexplained)
                    / max(len(degraded_feats), 1)) if degraded_feats else 0.0

        # UNKNOWN activates only on real, unexplained, persistent
        # inconsistency AFTER arming, and only when no known cause explains it.
        unknown_conf = 0.0
        unknown_reasons = ()
        distinct = {e.source_or_relationship for e in unexplained}
        if armed and len(distinct) >= UNKNOWN_MIN_DISTINCT_FEATURES \
                and residual >= UNKNOWN_MIN_UNEXPLAINED \
                and supported_best <= UNKNOWN_MAX_BEST_SUPPORTED:
            unknown_conf = min(1.0, residual)
            unknown_reasons = ("INCONSISTENCY_UNEXPLAINED_BY_KNOWN_CAUSES",)
        elif not armed:
            unknown_reasons = ("WITHIN_ARM_TIME",)
        elif len(distinct) == 1:
            unknown_reasons = ("SINGLE_RELATIONSHIP_NOT_CROSS_SENSOR",)
        elif supported_best > UNKNOWN_MAX_BEST_SUPPORTED:
            unknown_reasons = ("EXPLAINED_BY_SUPPORTED_HYPOTHESIS",)
        uh = next(h for h in self.registry
                  if h.hypothesis_class
                  == HypothesisClass.UNKNOWN_INCONSISTENCY.value)
        scored.append((uh, unknown_conf, 0.0, unknown_reasons))

        out = []
        for h, conf, iso, reasons in scored:
            if not armed:
                # Priors, EW smoothers and gates are still converging; every
                # feature looks transiently degraded. Report nothing.
                conf, iso = 0.0, 0.0
                reasons = ("WITHIN_ARM_TIME",)
            # Dwell: a hypothesis must hold above EMERGING for dwell_ticks
            # before it may be ACTIVE. No single-tick conclusions.
            held = self._held.get(h.hypothesis_id, 0)
            held = held + 1 if conf >= EMERGING_CONF else 0
            self._held[h.hypothesis_id] = held
            state = (DiagnosticState.ACTIVE.value
                     if conf >= ACTIVE_CONF and held >= self.dwell_ticks else
                     DiagnosticState.EMERGING.value if conf >= EMERGING_CONF
                     else DiagnosticState.INACTIVE.value)
            if conf >= ACTIVE_CONF and held < self.dwell_ticks:
                reasons = tuple(reasons) + ("AWAITING_DWELL",)
            out.append(Hypothesis(
                hypothesis_id=h.hypothesis_id,
                hypothesis_class=h.hypothesis_class,
                affected_sources=h.affected_sources,
                shared_resource=h.shared_resource,
                parent_hypothesis_id=h.parent_hypothesis_id,
                required_evidence=h.required_evidence,
                contradicting_evidence=h.contradicting_evidence,
                prior=h.prior, confidence=round(conf, 4),
                isolation_confidence=round(iso, 4),
                diagnostic_state=state,
                operational_authorization=Authorization.SHADOW_ONLY.value,
                reason_codes=reasons))

        # Deterministic ordering: confidence desc, then REGISTRY order.
        order = {h.hypothesis_id: i for i, h in enumerate(self.registry)}
        ranked = sorted(out, key=lambda h: (-h.confidence,
                                            order[h.hypothesis_id]))
        active = tuple(h.hypothesis_id for h in ranked
                       if h.diagnostic_state == DiagnosticState.ACTIVE.value)
        root = (ranked[0].hypothesis_id
                if ranked[0].diagnostic_state == DiagnosticState.ACTIVE.value
                else None)

        top2 = [h.confidence for h in ranked[:2]] + [0.0]
        ambiguity = round(max(0.0, 1.0 - (top2[0] - top2[1])), 4) \
            if top2[0] >= EMERGING_CONF else 0.0

        affected = tuple(sorted({s for h in ranked
                                 if h.diagnostic_state
                                 == DiagnosticState.ACTIVE.value
                                 for s in h.affected_sources}))

        return HypothesisReport(
            t=t,
            most_probable_root_cause=root,
            active_contributing_causes=active,
            affected_sources=affected,
            alternative_hypotheses=tuple(
                h.hypothesis_id for h in ranked[1:]
                if h.confidence >= EMERGING_CONF),
            residual_unexplained_evidence=round(residual, 4),
            diagnostic_ambiguity=ambiguity,
            source_usability=self._usability(features, affected),
            source_fault_confidence=self._source_conf(ranked),
            hypotheses=tuple(ranked), evidence=ev,
            recommendations=self._recommend(t, ranked, root, residual),
            legacy_top_cause=legacy_top,
            notes=("SHADOW_ONLY: no active failsafe, estimator or arbitration "
                   "behaviour is affected by this report",))

    # -- derived outputs ---------------------------------------------------

    def _usability(self, features, affected):
        """Per-source, per-function usability. Heuristic, not calibrated."""
        u = {}
        for src in ("gps", "mag", "imu0", "imu1", "baro", "battery",
                    "motor_esc", "vibration"):
            phys = features.get(f"phys_{src}")
            c = float(phys[0]) if phys and float(phys[1]) > 1e-9 else None
            if c is None:
                state = Usability.UNKNOWN.value
            elif c < 0.5 or src in affected:
                state = Usability.UNUSABLE.value if c is not None and c < 0.5 \
                    else Usability.DEGRADED.value
            elif c < DEGRADED_C:
                state = Usability.DEGRADED.value
            else:
                state = Usability.USABLE.value
            u[src] = state
        # Function-level split: a GNSS position fault need not invalidate
        # GNSS timing. Recorded explicitly rather than assumed.
        u["gps:position"] = u.get("gps", Usability.UNKNOWN.value)
        u["gps:timing"] = Usability.UNKNOWN.value   # not observed by CSIA
        return u

    def _source_conf(self, ranked):
        out: dict = {}
        for h in ranked:
            for s in h.affected_sources:
                out[s] = round(max(out.get(s, 0.0), h.confidence), 4)
        return out

    def _recommend(self, t, ranked, root, residual):
        recs = []

        def add(rid, fn, hyp, conf, reasons):
            recs.append({
                "recommendation_id": rid, "affected_function": fn,
                "supporting_hypothesis": hyp, "confidence": round(conf, 4),
                "reason_codes": list(reasons), "timestamp": t,
                "authorization_level": Authorization.SHADOW_ONLY.value,
                "persistence_s": 10.0,
                "active_application_permitted": False})

        for h in ranked:
            if h.diagnostic_state != DiagnosticState.ACTIVE.value:
                continue
            if h.shared_resource:
                add(Recommendation.MONITOR_SHARED_RESOURCE.value,
                    h.shared_resource, h.hypothesis_id, h.confidence,
                    h.reason_codes)
                add(Recommendation.DEGRADE_AFFECTED_SOURCE_SET.value,
                    ",".join(h.affected_sources), h.hypothesis_id,
                    h.confidence, h.reason_codes)
            elif h.hypothesis_class == HypothesisClass.ESTIMATOR_FAILURE.value:
                add(Recommendation.REQUEST_ESTIMATOR_HEALTH_CHECK.value,
                    "estimator", h.hypothesis_id, h.confidence, h.reason_codes)
            elif h.affected_sources:
                add(Recommendation.REQUEST_REDUNDANCY_CHECK.value,
                    ",".join(h.affected_sources), h.hypothesis_id,
                    h.confidence, h.reason_codes)
            if h.hypothesis_class == HypothesisClass.UNKNOWN_INCONSISTENCY.value:
                add(Recommendation.ENTER_DIAGNOSTIC_SHADOW_STATE.value,
                    "diagnosis", h.hypothesis_id, h.confidence, h.reason_codes)
                add(Recommendation.INSUFFICIENT_EVIDENCE_FOR_SOURCE_ISOLATION.value,
                    "isolation", h.hypothesis_id, h.confidence, h.reason_codes)
        if root is None and residual >= UNKNOWN_MIN_UNEXPLAINED:
            add(Recommendation.INSUFFICIENT_EVIDENCE_FOR_SOURCE_ISOLATION.value,
                "isolation", None, residual, ("NO_DOMINANT_HYPOTHESIS",))
        return tuple(recs)


# --- isolation scoring --------------------------------------------------------

def classify_isolation(report, truth_sources, truth_class=None,
                       shared_resource=None) -> str:
    """Score a shadow report against ground truth. See METRIC_DEFINITIONS §4."""
    truth = set(truth_sources)
    if report.most_probable_root_cause is None:
        best = max((h.confidence for h in report.hypotheses), default=0.0)
        if best >= EMERGING_CONF:
            return IsolationOutcome.AMBIGUOUS.value
        return IsolationOutcome.NONE.value

    root = next(h for h in report.hypotheses
                if h.hypothesis_id == report.most_probable_root_cause)
    if root.hypothesis_class == HypothesisClass.UNKNOWN_INCONSISTENCY.value:
        return IsolationOutcome.UNKNOWN_DETECTED.value

    named = set(report.affected_sources)
    if not named:
        return IsolationOutcome.NONE.value
    if named == truth:
        if shared_resource and root.shared_resource == shared_resource:
            return IsolationOutcome.CORRECT_COMMON_CAUSE.value
        if root.hypothesis_class == HypothesisClass.ESTIMATOR_FAILURE.value:
            return IsolationOutcome.CORRECT_ESTIMATOR_CAUSE.value
        if len(truth) > 1:
            return IsolationOutcome.CORRECT_MULTI_SOURCE.value
        return IsolationOutcome.CORRECT_SINGLE_SOURCE.value
    if named & truth:
        if named < truth:
            return IsolationOutcome.PARTIAL_ISOLATION.value
        if named > truth:
            return IsolationOutcome.OVER_ISOLATION.value
        return IsolationOutcome.UNDER_ISOLATION.value
    return IsolationOutcome.INCORRECT_ISOLATION.value
