"""What a stress run produced: detection, escalation, and recovery time.

RECOVERY TIME IS DEFINED BY THE SYSTEM, NOT BY ME
-------------------------------------------------
The tempting definition is "time until trust climbs back above X". That
would require me to choose X, and any X I choose is a threshold I invented
sitting next to a frozen core whose thresholds are exactly what may not be
retuned. A regression metric built on an invented constant measures my
constant as much as the system.

So recovery is read off the system's OWN declared state: the failsafe
level returning to NORMAL. `FailsafeConfig` already defines what recovery
means -- `dwell_down = 5.0 s` of sustained health before de-escalation --
and that dwell is INSIDE the measured number rather than subtracted from
it. A recovery time of 5.2 s means 0.2 s of real recovery plus the
policy's own required dwell, and it is reported as the whole thing because
that is when the aircraft actually gets its authority back.

WHAT IS DELIBERATELY NOT A PASS
-------------------------------
`escalated=False` is NOT a passing run. A profile that injects real faults
and never trips the failsafe is either a layer that missed them or a
profile that was too weak, and both need looking at. The campaign records
it as NOT_DETECTED and never folds it into a pass. Likewise a run that
escalates and never recovers is NOT_RECOVERED, not "recovery time
unknown" -- it is a fact about the run, and it is reported as one.
"""

from __future__ import annotations

from dataclasses import dataclass

from csia.diagnosis.baselines import LEGACY_CAUSE_SOURCE
from csia.runtime.failsafe import FailsafeLevel, FailsafePolicy
from csia.runtime.online import OnlineTrustLayer

from .source import StressFlightSource

#: Sensors the legacy cause vocabulary can accuse at all. Taken from the
#: frozen `LEGACY_CAUSE_SOURCE` rather than restated here, so this cannot
#: drift from it. Two of the eight sensor nodes -- `baro` and `motor_esc` --
#: have NO cause label pointing at them, so a fault on either is structurally
#: unnameable by this vocabulary however clearly the trust layer sees it.
NAMEABLE_SOURCES = frozenset(
    v for v in LEGACY_CAUSE_SOURCE.values() if v is not None)

DETECTED = "DETECTED"
NOT_DETECTED = "NOT_DETECTED"
RECOVERED = "RECOVERED"
NOT_RECOVERED = "NOT_RECOVERED"
NOT_APPLICABLE = "NOT_APPLICABLE"
#: The run ended too soon after the faults cleared for recovery to be
#: OBSERVABLE, so "did not recover" would be a statement about the profile's
#: length rather than about the system. Never reported as NOT_RECOVERED.
WINDOW_TOO_SHORT = "RECOVERY_WINDOW_TOO_SHORT"


@dataclass
class StressRun:
    """The measured outcome of one profile."""

    profile_id: str
    ticks: int
    fault_onset: float
    fault_clear: float
    escalated: bool
    peak_level: int
    peak_level_name: str
    detection_status: str
    detection_latency_s: float | None
    recovery_status: str
    recovery_time_s: float | None
    final_level: int
    transitions: list
    min_trust: dict
    dwell_down_s: float
    flight_end_s: float
    observable_recovery_window_s: float
    attribution: dict
    recovered_before_faults_cleared: bool

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "ticks": self.ticks,
            "fault_onset_s": self.fault_onset,
            "fault_clear_s": self.fault_clear,
            "escalated": self.escalated,
            "peak_failsafe_level": self.peak_level,
            "peak_failsafe_level_name": self.peak_level_name,
            "detection": {
                "status": self.detection_status,
                "latency_s": self.detection_latency_s,
                "measured_from": "first fault onset to first escalation",
            },
            "recovery": {
                "status": self.recovery_status,
                "time_s": self.recovery_time_s,
                "measured_from": ("last fault window end to failsafe "
                                  "returning to NORMAL"),
                "includes_policy_dwell_down_s": self.dwell_down_s,
                "note": ("the policy's own de-escalation dwell is INSIDE "
                         "this number, not subtracted from it"),
                "observable_window_s": self.observable_recovery_window_s,
                "recovered_before_faults_cleared": (
                    self.recovered_before_faults_cleared),
                "recovered_before_note": (
                    "TRUE means the failsafe was ALREADY back at NORMAL when "
                    "the last fault window ended, so the reported time is "
                    "near zero and is NOT a measurement of how long recovery "
                    "took. It happens when faults are staggered and the "
                    "trailing one never held a condition. Aggregate recovery "
                    "statistics should exclude these or they read as "
                    "instant recoveries."),
                "observable_window_note": (
                    "seconds of flight remaining after the last fault "
                    "cleared. Shorter than the dwell means a recovery could "
                    "not have been seen even if it happened, which is "
                    "reported as RECOVERY_WINDOW_TOO_SHORT rather than as a "
                    "failure to recover"),
            },
            "flight_end_s": self.flight_end_s,
            "final_failsafe_level": self.final_level,
            "transitions": self.transitions,
            "min_trust_per_node": self.min_trust,
            "attribution": self.attribution,
        }


def run_profile(profile, truth=None) -> StressRun:
    """Run one stress profile through the frozen core and measure it."""
    profile.validate()
    source = StressFlightSource(faults=profile.faults, truth=truth,
                                flight_profile=profile.flight_profile,
                                duration=profile.duration)
    layer = OnlineTrustLayer()
    policy = FailsafePolicy()

    states = []
    last_t = 0.0
    for sensor, t, channels in source.samples():
        states.extend(layer.ingest(sensor, t, channels))
        last_t = t
    states.extend(layer.flush(last_t))

    onset = min(f.start for f in profile.faults)
    clear = max(f.start + f.duration for f in profile.faults)

    first_escalation = None
    returned_normal = None
    peak = FailsafeLevel.NORMAL
    min_trust = {}
    cause_ticks: dict = {}
    level_at_clear = None

    for state in states:
        policy.update(state)
        level = policy.level

        # ATTRIBUTION. Under several concurrent faults, does the diagnosis
        # name them all or settle on one? Only ticks inside the fault span
        # are counted; outside it "nominal" is the correct answer and would
        # dilute the measurement.
        if onset <= float(state.t) <= clear:
            top = state.top_causes(1)
            if top:
                cause_ticks[top[0][0]] = cause_ticks.get(top[0][0], 0) + 1
        if level > peak:
            peak = level
        if level > FailsafeLevel.NORMAL and first_escalation is None:
            first_escalation = float(state.t)
        # THE FIRST RETURN TO NORMAL AT OR AFTER THE FAULTS CLEAR.
        # Measuring from the first return after the first ESCALATION instead
        # gets intermittent profiles badly wrong: a GNSS profile that denies
        # the fix four times returns to NORMAL between cycles, and taking
        # that first return reported a 0.0 s recovery for a run that was
        # still being faulted 19 s later. Recovery is only meaningful once
        # there is nothing left to recover from.
        if (returned_normal is None and level == FailsafeLevel.NORMAL
                and float(state.t) >= clear):
            returned_normal = float(state.t)
        if level_at_clear is None and float(state.t) >= clear:
            level_at_clear = level
        for name, value in state.trust.items():
            v = float(value)
            if name not in min_trust or v < min_trust[name]:
                min_trust[name] = v

    escalated = first_escalation is not None
    if escalated:
        detection_status = DETECTED
        detection_latency = round(first_escalation - onset, 4)
    else:
        # NOT a pass. Either the layer missed a real fault or the profile
        # was too weak to be a stress case; both are findings.
        detection_status = NOT_DETECTED
        detection_latency = None

    # --- attribution ------------------------------------------------------
    injected = sorted({f.target for f in profile.faults})
    total_cause_ticks = sum(cause_ticks.values())
    named_sources = {LEGACY_CAUSE_SOURCE.get(c) for c in cause_ticks}
    nameable = [t for t in injected if t in NAMEABLE_SOURCES]
    unnameable = [t for t in injected if t not in NAMEABLE_SOURCES]
    attribution = {
        "injected_targets": injected,
        "causes_named_during_faults": {
            c: round(n / total_cause_ticks, 4)
            for c, n in sorted(cause_ticks.items(),
                               key=lambda kv: -kv[1])} if total_cause_ticks
        else {},
        "targets_named": sorted(t for t in nameable if t in named_sources),
        "targets_nameable_but_never_named": sorted(
            t for t in nameable if t not in named_sources),
        "targets_structurally_unnameable": unnameable,
        "what_unnameable_means": (
            "the legacy cause vocabulary has no label pointing at this "
            "sensor, so it cannot be accused however clearly the trust "
            "layer sees the fault. That is a property of the vocabulary, "
            "NOT a detection failure -- the failsafe may still act on it."),
        "what_never_named_means": (
            "a fault was injected on a sensor the vocabulary CAN name, and "
            "across the whole fault window the top-1 cause was never that "
            "sensor. Under concurrent faults the posterior concentrates on "
            "one explanation; the others are not separately accused."),
    }

    flight_end = float(states[-1].t) if states else 0.0
    #: De-escalation cannot happen faster than the policy's own dwell, so a
    #: run that ends less than `dwell_down` after the faults clear CANNOT
    #: show a recovery whether or not the system would have recovered.
    observable_window = flight_end - clear

    if not escalated:
        recovery_status, recovery_time = NOT_APPLICABLE, None
    elif returned_normal is not None:
        recovery_status = RECOVERED
        # Faults may clear before or after the failsafe first fires; clamp
        # at zero rather than reporting a negative recovery.
        recovery_time = round(max(0.0, returned_normal - clear), 4)
    elif observable_window < policy.cfg.dwell_down:
        # NOT a finding about the system. Calling this NOT_RECOVERED would
        # report the profile's length as if it were the layer's behaviour.
        recovery_status, recovery_time = WINDOW_TOO_SHORT, None
    else:
        recovery_status, recovery_time = NOT_RECOVERED, None

    return StressRun(
        profile_id=profile.id,
        ticks=len(states),
        fault_onset=onset,
        fault_clear=clear,
        escalated=escalated,
        peak_level=int(peak),
        peak_level_name=peak.name,
        detection_status=detection_status,
        detection_latency_s=detection_latency,
        recovery_status=recovery_status,
        recovery_time_s=recovery_time,
        final_level=int(policy.level),
        transitions=[{"t": round(float(tr.t), 4),
                      "from": int(tr.previous), "to": int(tr.level),
                      "to_name": FailsafeLevel(tr.level).name,
                      "reasons": list(tr.reasons)}
                     for tr in policy.transitions],
        min_trust={k: round(v, 4) for k, v in sorted(min_trust.items())},
        dwell_down_s=policy.cfg.dwell_down,
        flight_end_s=round(flight_end, 4),
        observable_recovery_window_s=round(observable_window, 4),
        attribution=attribution,
        recovered_before_faults_cleared=bool(
            level_at_clear == FailsafeLevel.NORMAL and escalated),
    )
