"""Latency metrics — the single owner of every CSIA time-to-X calculation.

Audit finding F-02: the repository published "detection latency" figures that
were the time for a trust coefficient to cross a hard-coded 0.85. Nothing in
CSIA acts at 0.85. The operator-visible event requires a per-class production
threshold AND ``dwell_up`` AND ``arm_time``, so the published number was
systematically optimistic relative to the alert an operator actually receives,
and it was not comparable to a PX4/ArduPilot health flag.

This module separates the stages that were conflated. Every metric names its
threshold; nothing is called "detection latency".

    onset ──▶ trust crosses analysis threshold   time_to_trust_threshold_s
          ──▶ trust crosses production threshold (implicit in the alert)
          ──▶ +dwell_up, +arm_time ──▶ alert EVENT   time_to_alert_event_s
          ──▶ owning EPISODE opens               time_to_alert_episode_s
          ──▶ diagnosis p(cause) >= conf         time_to_classification_s
          ──▶ diagnosis names the RIGHT source   time_to_correct_isolation_s
          ──▶ policy emits a bounded action      time_to_arbitration_recommendation_s
          ──▶ receiving system confirms          time_to_applied_mitigation_s  (UNAVAILABLE)
    fault removed
          ──▶ posture leaves degraded state      time_to_recovery_s
          ──▶ source trusted enough to contribute time_to_trusted_reentry_s

``time_to_applied_mitigation_s`` is always ``None``: CSIA is advisory and no
actuator reports back confirmation. It is reported as unavailable rather than
simulated (see APPLIED_MITIGATION_UNAVAILABLE).
"""

from dataclasses import asdict, dataclass, field

from .events import alert_episodes, alert_events

# --- constants ---------------------------------------------------------------

#: Legacy analysis threshold. Retained for historical continuity ONLY. It has
#: no operational effect: no failsafe condition in FailsafeConfig uses it.
LEGACY_ANALYSIS_THRESHOLD = 0.85

#: Why time-to-applied-mitigation cannot be produced today.
APPLIED_MITIGATION_UNAVAILABLE = (
    "no closed-loop integration: CSIA actuators are advisory and the "
    "receiving system does not report application back to the trust layer")

#: diagnosis cause -> the sensor node it accuses. Causes that do not accuse a
#: single source map to None (``nominal`` is the null hypothesis;
#: ``unexpected_maneuver`` blames vehicle motion, not a sensor).
CAUSE_TO_SOURCE = {
    "nominal": None,
    "unexpected_maneuver": None,
    "gps_fault": "gps",
    "imu0_bias_drift": "imu0",
    "imu1_bias_drift": "imu1",
    "mag_interference": "mag",
    "power_fault": "battery",
    "vibration_anomaly": "vibration",
}

#: Actions that are bounded operational RECOMMENDATIONS about a source or
#: mode. RESUME_NORMAL is a recovery notice, not a recommendation.
ARBITRATION_ACTIONS = frozenset({
    "SELECT_IMU", "SWITCH_NAV_INERTIAL", "INHIBIT_GPS_MODES",
    "HEADING_HOLD_GYRO", "LIMIT_MANEUVERS", "LIMIT_THROTTLE",
    "REDUCE_POWER", "PREPARE_LANDING", "LAND_SOON", "LAND_NOW",
    "STABILIZE", "CONTROLLED_DESCENT", "BROADCAST_MAYDAY",
})

#: Grace period after a fault window closes during which an opening alert is
#: still attributed to that fault. Covers dwell_up plus trust-recovery lag.
DEFAULT_ASSOC_GRACE_S = 15.0

# _ISOLATION_OUTCOMES ("CORRECT", "INCORRECT", "AMBIGUOUS", "NONE") was
# here, unused, and contradicted the vocabulary actually in use:
# csia.diagnosis.hypothesis.IsolationOutcome has ten members that
# distinguish CORRECT_SINGLE_SOURCE from CORRECT_COMMON_CAUSE, and
# OVER_ISOLATION from UNDER_ISOLATION. Two vocabularies for one concept,
# one of them dead, is how a reader ends up scoring against the wrong
# one.


# --- ground truth ------------------------------------------------------------

@dataclass(frozen=True)
class FaultWindow:
    """Ground-truth fault annotation, independent of the injector used."""
    target: str
    kind: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration

    @classmethod
    def from_fault(cls, f):
        return cls(target=f.target, kind=f.kind, start=float(f.start),
                   duration=float(f.duration))


@dataclass(frozen=True)
class OnsetBasis:
    """The four distinct onset timestamps, which are NOT assumed equal.

    ``configured`` is always known. ``first_corrupted_sample`` requires a
    clean reference run to diff against. ``first_observable_effect`` is not
    implemented — deciding when a corruption becomes *observable* requires a
    per-check detectability model CSIA does not have, and guessing it would
    fabricate precision.
    """
    configured: float
    first_corrupted_sample: float | None = None
    first_observable_effect: float | None = None

    def resolve(self, prefer: str = "configured") -> tuple:
        """Return (onset_time, basis_name) using the best available basis."""
        order = {"configured": ["configured"],
                 "corrupted": ["first_corrupted_sample", "configured"],
                 "observable": ["first_observable_effect",
                                "first_corrupted_sample", "configured"]}
        if prefer not in order:
            raise ValueError(f"unknown onset preference {prefer!r}")
        for name in order[prefer]:
            v = getattr(self, name)
            if v is not None:
                return float(v), name
        raise ValueError("no onset basis available")


# --- result ------------------------------------------------------------------

@dataclass(frozen=True)
class LatencyResult:
    """All latency stages for ONE fault. ``None`` means not reached / N/A."""
    scenario_id: str
    target_source: str
    fault_class: str

    configured_fault_start_s: float
    first_corrupted_sample_s: float | None
    first_observable_effect_s: float | None
    onset_basis: str
    onset_s: float

    trust_threshold: float
    time_to_trust_threshold_s: float | None

    alert_state: str | None
    time_to_alert_event_s: float | None
    time_to_alert_episode_s: float | None
    alert_escalations: int

    classification_confidence_threshold: float
    time_to_classification_s: float | None
    classified_as: str | None

    isolation_confidence_threshold: float
    time_to_correct_isolation_s: float | None
    isolation_outcome: str
    isolated_as: str | None

    time_to_arbitration_recommendation_s: float | None
    arbitration_action: str | None

    time_to_applied_mitigation_s: None = None
    applied_mitigation_status: str = APPLIED_MITIGATION_UNAVAILABLE

    time_to_recovery_s: float | None = None
    time_to_trusted_reentry_s: float | None = None
    recovery_threshold: float | None = None

    outcome: str = "UNEVALUATED"
    notes: tuple = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


# --- production thresholds ---------------------------------------------------

def production_threshold(sensor: str, cfg=None) -> float | None:
    """The trust value at which THIS sensor can contribute to an alert.

    Mirrors FailsafePolicy._conditions. Returns None for a sensor that no
    failsafe condition reads (it can never independently raise an alert).
    """
    if cfg is None:
        from ..runtime.failsafe import FailsafeConfig
        cfg = FailsafeConfig()
    return {"gps": cfg.nav_caution,
            "mag": cfg.heading_caution,
            "vibration": cfg.struct_critical,
            "battery": cfg.power_critical,
            "imu0": cfg.att_caution,
            "imu1": cfg.att_caution}.get(sensor)


# --- fault ↔ alert association ------------------------------------------------

def associate_episode(episodes, fault: FaultWindow,
                      grace_s: float = DEFAULT_ASSOC_GRACE_S,
                      onset: float | None = None):
    """Pick the episode caused by ``fault``, or None.

    Deterministic rule, applied in this order:
      1. Candidates are episodes opening in [onset, fault.end + grace_s].
         An episode opening BEFORE onset is never attributed to this fault
         (it is pre-existing or a false alert).
      2. Among candidates, the EARLIEST-opening episode wins — latency is
         time to the first operator alert this fault caused, not the worst.

    When several faults overlap, call this per fault: an episode may legitimately
    be attributed to more than one, which is reported rather than arbitrated,
    because a single posture can genuinely be supported by two faults.
    """
    lo = fault.start if onset is None else onset
    hi = fault.end + grace_s
    cands = [e for e in episodes if lo <= e.start <= hi]
    return min(cands, key=lambda e: e.start) if cands else None


def unassociated_episodes(episodes, faults,
                          grace_s: float = DEFAULT_ASSOC_GRACE_S) -> list:
    """Episodes attributable to no fault — false alerts or pre-existing state."""
    owned = set()
    for f in faults:
        ep = associate_episode(episodes, f, grace_s)
        if ep is not None:
            owned.add((ep.start, ep.end))
    return [e for e in episodes if (e.start, e.end) not in owned]


# --- per-stage primitives -----------------------------------------------------

def _first(states, pred, after: float):
    for st in states:
        if st.t >= after and pred(st):
            return float(st.t)
    return None


def time_to_trust_threshold(states, source: str, onset: float,
                            threshold: float = LEGACY_ANALYSIS_THRESHOLD):
    """ANALYSIS metric. Names its threshold; not operator-facing."""
    t = _first(states, lambda s: s.trust.get(source, 1.0) < threshold, onset)
    return None if t is None else t - onset


def time_to_classification(states, onset: float, conf: float = 0.90):
    """First tick where any non-nominal cause reaches ``conf``."""
    for st in states:
        if st.t < onset:
            continue
        for cause, p in st.posterior.items():
            if cause != "nominal" and p >= conf:
                return st.t - onset, cause
    return None, None


def time_to_correct_isolation(states, source: str, onset: float,
                              conf: float = 0.90):
    """First tick where the top cause accuses ``source`` at >= ``conf``.

    Returns (latency, outcome, accused). Outcomes:
      CORRECT   — the accused source is the faulted one
      INCORRECT — a different source was accused at confidence first
      AMBIGUOUS — confidence reached, but the leading cause names no source
      NONE      — no cause reached the confidence threshold
    """
    for st in states:
        if st.t < onset:
            continue
        cause, p = max(st.posterior.items(), key=lambda kv: kv[1])
        if cause == "nominal" or p < conf:
            continue
        accused = CAUSE_TO_SOURCE.get(cause, "__unknown__")
        if accused == source:
            return st.t - onset, "CORRECT", accused
        if accused is None:
            return None, "AMBIGUOUS", cause
        return None, "INCORRECT", accused
    return None, "NONE", None


def time_to_arbitration(actions, onset: float, until: float | None = None):
    """First bounded operational recommendation after onset.

    ``actions`` is RunSummary.actions: a list of (t, action_name).
    """
    for t, name in actions:
        if t < onset or (until is not None and t > until):
            continue
        if name in ARBITRATION_ACTIONS:
            return float(t) - onset, name
    return None, None


def time_to_recovery(episode, fault: FaultWindow):
    """Fault removal -> posture leaves the degraded state.

    None if the episode never closed (still degraded when the run ended) or
    if it closed before the fault was removed.
    """
    if episode is None or episode.end is None:
        return None
    return None if episode.end < fault.end else episode.end - fault.end


def time_to_trusted_reentry(states, source: str, fault: FaultWindow,
                            threshold: float | None = None):
    """Fault removal -> source trusted enough to contribute again.

    Deliberately distinct from recovery: the posture can return to NORMAL
    while a source is still below the value at which it would re-trigger.
    Requires the source to hold above ``threshold`` at or after fault end.
    """
    if threshold is None:
        threshold = production_threshold(source)
    if threshold is None:
        return None
    t = _first(states, lambda s: s.trust.get(source, 0.0) >= threshold,
               fault.end)
    return None if t is None else t - fault.end


# --- top-level ----------------------------------------------------------------

def measure(summary, fault, scenario_id: str = "",
            analysis_threshold: float = LEGACY_ANALYSIS_THRESHOLD,
            classification_conf: float = 0.90,
            isolation_conf: float = 0.90,
            merge_s: float | None = None,
            grace_s: float = DEFAULT_ASSOC_GRACE_S,
            onset: OnsetBasis | None = None,
            onset_prefer: str = "configured") -> LatencyResult:
    """Compute every latency stage for one fault against one run.

    ``summary`` needs ``.states`` (run with keep_states=True), ``.transitions``
    and ``.actions``. ``fault`` is a FaultWindow or a sensors.Fault.
    """
    fw = fault if isinstance(fault, FaultWindow) else FaultWindow.from_fault(fault)
    basis = onset or OnsetBasis(configured=fw.start)
    onset_s, basis_name = basis.resolve(onset_prefer)

    states = list(getattr(summary, "states", []) or [])
    notes = []
    if not states:
        notes.append("no per-tick states retained (keep_states=False): "
                     "trust/classification/isolation stages unavailable")

    kw = {} if merge_s is None else {"merge_s": merge_s}
    episodes = alert_episodes(summary.transitions, **kw)
    ep = associate_episode(episodes, fw, grace_s, onset_s)

    # alert EVENT: first severity-increasing edge inside the owning episode
    t_event = None
    alert_state = None
    if ep is not None:
        for tr in alert_events(summary.transitions):
            if ep.start <= tr.t <= (ep.end if ep.end is not None else float("inf")):
                t_event = tr.t - onset_s
                alert_state = getattr(tr.level, "name", str(tr.level))
                break

    t_thr = (time_to_trust_threshold(states, fw.target, onset_s,
                                     analysis_threshold) if states else None)
    t_cls, cls_as = ((None, None) if not states else
                     time_to_classification(states, onset_s, classification_conf))
    t_iso, iso_outcome, iso_as = ((None, "NONE", None) if not states else
                                  time_to_correct_isolation(states, fw.target,
                                                            onset_s, isolation_conf))
    t_arb, arb_action = time_to_arbitration(
        getattr(summary, "actions", []) or [], onset_s)

    recov_thr = production_threshold(fw.target)
    outcome = _classify_outcome(ep, iso_outcome)
    if ep is None and t_thr is not None:
        notes.append("trust crossed the analysis threshold but no operator "
                     "alert was raised — analysis-only detection")

    return LatencyResult(
        scenario_id=scenario_id,
        target_source=fw.target,
        fault_class=fw.kind,
        configured_fault_start_s=fw.start,
        first_corrupted_sample_s=basis.first_corrupted_sample,
        first_observable_effect_s=basis.first_observable_effect,
        onset_basis=basis_name,
        onset_s=onset_s,
        trust_threshold=analysis_threshold,
        time_to_trust_threshold_s=t_thr,
        alert_state=alert_state,
        time_to_alert_event_s=t_event,
        time_to_alert_episode_s=None if ep is None else ep.start - onset_s,
        alert_escalations=0 if ep is None else ep.escalations,
        classification_confidence_threshold=classification_conf,
        time_to_classification_s=t_cls,
        classified_as=cls_as,
        isolation_confidence_threshold=isolation_conf,
        time_to_correct_isolation_s=t_iso,
        isolation_outcome=iso_outcome,
        isolated_as=iso_as,
        time_to_arbitration_recommendation_s=t_arb,
        arbitration_action=arb_action,
        time_to_recovery_s=time_to_recovery(ep, fw),
        time_to_trusted_reentry_s=time_to_trusted_reentry(states, fw.target, fw)
                                  if states else None,
        recovery_threshold=recov_thr,
        outcome=outcome,
        notes=tuple(notes),
    )


def _classify_outcome(episode, isolation_outcome: str) -> str:
    if episode is None:
        return "MISSED"
    if isolation_outcome == "CORRECT":
        return "CORRECT_ALERT_AND_ISOLATION"
    if isolation_outcome == "INCORRECT":
        return "ALERT_WITH_INCORRECT_ISOLATION"
    return "ALERT_WITHOUT_ISOLATION"
