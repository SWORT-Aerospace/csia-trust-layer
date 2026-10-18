"""A loss-of-data rule for the seven sensors that never had one (SR-001).

THE GAP
-------
`FailsafePolicy._conditions` gates every rule on `fresh.get(<sensor>)`, so
a sensor that stops delivering valid data is REMOVED FROM SUPERVISION
rather than alarmed on. GPS is the single exception: it carries an
explicit "GPS data invalid" rule.

Measured, and counted from the frozen source: `gps` is referenced 5 times
in `_conditions`, `imu0` 4, `imu1` 3, `mag` 2, `battery` 2, `vibration` 2
-- and **`baro` and `motor_esc` are referenced ZERO times**. Two of the
eight nodes have no failsafe rule of any kind, by trust or by loss.

The sharpest case is attitude: the rules reason over
`imus = [n for n in ("imu0","imu1") if fresh.get(n)]` and then take
`att = max((T[n] for n in imus), default=1.0)`. When NEITHER IMU is fresh
the default applies, attitude confidence reads 1.000, and both attitude
rules become unreachable. Both IMUs dropped for 40 s of a 90 s flight
leaves the failsafe at NORMAL for the whole flight.

WHY THIS IS AN OVERLAY AND NOT AN EDIT
--------------------------------------
`csia/runtime/failsafe.py` is inside FROZEN_PATHS. Editing it would break
the E1 freeze manifest, the tag equivalence to `csia-v1.0-research-final`,
and every claim that descends from them. So the rule lives here, above the
frozen core, in the same direction as `csia_assurance` and `csia_mission`:
this module CALLS the frozen policy and never modifies it.

THE LEVELS ARE DERIVED, NOT CHOSEN
----------------------------------
Inventing a severity per sensor would be exactly the retuning that must
not happen. Each level below is read off the severity the FROZEN config
already assigns to that sensor's degradation:

    sensor      frozen degradation rule          loss-of-data level
    mag         heading_caution -> CAUTION       CAUTION
    battery     power_critical  -> CRITICAL      CRITICAL
    vibration   struct_critical -> CRITICAL      CRITICAL
    imu0/imu1   att_caution     -> CRITICAL      one lost:  CAUTION
                att_emergency   -> EMERGENCY     both lost: EMERGENCY
    gps         nav_degraded    -> CAUTION       DEFERRED to the frozen rule

Losing both IMUs is the exact analogue of `attitude_lost`: the attitude
reference is gone, which the frozen policy calls EMERGENCY. Losing one is
the redundancy case the frozen policy calls CAUTION via `imu_isolated`.

TWO LEVELS ARE A CHOICE, AND ARE LABELLED AS ONE
------------------------------------------------
`baro` and `motor_esc` have NO threshold in `FailsafeConfig`, so there is
nothing to derive from. Their levels are the only judgement in this table,
they default to the lowest actionable level, and `DERIVED_FROM` records
them as UNANCHORED so a reader can see which two numbers are mine.

Timing is not invented either: `dwell_up`, `arm_time` and the disarmed
behaviour all come from the frozen `FailsafeConfig`, and freshness is
whatever the frozen online layer already computed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csia.runtime.failsafe import Action, FailsafeConfig, FailsafeLevel

#: Sensors the frozen policy already alarms on when their data is absent.
#: The overlay must not double-report these.
ALREADY_COVERED = frozenset({"gps"})

#: Sensors with no rule of any kind in the frozen policy -- neither a trust
#: threshold nor a loss rule. Counted from the frozen source, not assumed.
UNSUPERVISED_BY_THE_FROZEN_POLICY = frozenset({"baro", "motor_esc"})

ANCHORED = "ANCHORED_IN_FROZEN_CONFIG"
UNANCHORED = "UNANCHORED_THIS_IS_A_CHOICE"

#: sensor -> (level, provenance, the frozen field it was derived from)
DERIVED_FROM: dict = {
    "mag": (FailsafeLevel.CAUTION, ANCHORED, "heading_caution"),
    "battery": (FailsafeLevel.CRITICAL, ANCHORED, "power_critical"),
    "vibration": (FailsafeLevel.CRITICAL, ANCHORED, "struct_critical"),
    "imu0": (FailsafeLevel.CAUTION, ANCHORED, "imu_isolation (single unit)"),
    "imu1": (FailsafeLevel.CAUTION, ANCHORED, "imu_isolation (single unit)"),
    # No FailsafeConfig threshold mentions either of these.
    "baro": (FailsafeLevel.CAUTION, UNANCHORED, None),
    "motor_esc": (FailsafeLevel.CAUTION, UNANCHORED, None),
}

#: Losing BOTH attitude sources is not two single-IMU losses. The frozen
#: policy calls a lost attitude reference EMERGENCY, and that is what this
#: is: `att` falls back to a default of 1.0 precisely because there is
#: nothing left to read.
BOTH_IMUS_LOST = FailsafeLevel.EMERGENCY


@dataclass
class DataLossCondition:
    sensor: str
    level: FailsafeLevel
    since: float
    reason: str
    provenance: str
    actions: tuple = ()


@dataclass
class DataLossSupervisor:
    """Raises a condition when a MONITORED sensor stops delivering.

    Mirrors the frozen state machine's rules about when a rule may fire at
    all: not before `arm_time`, not while known-disarmed, and only after
    `dwell_up` of the condition holding.
    """

    config: FailsafeConfig = field(default_factory=FailsafeConfig)
    #: sensors seen delivering at least once. A sensor absent for the whole
    #: flight was never fitted and must not raise a loss alarm -- the same
    #: rule the frozen policy applies to GPS via `_ever_fresh`.
    ever_fresh: set = field(default_factory=set)
    _since: dict = field(default_factory=dict)
    conditions: dict = field(default_factory=dict)
    level: FailsafeLevel = FailsafeLevel.NORMAL

    def reset_timers(self) -> None:
        self._since.clear()
        self.conditions = {}
        self.level = FailsafeLevel.NORMAL

    def update(self, state) -> dict:
        """Feed one state; returns the currently dwelled-in conditions."""
        t = float(state.t)
        fresh = dict(getattr(state, "fresh", {}) or {})
        for sensor, ok in fresh.items():
            if ok:
                self.ever_fresh.add(sensor)

        if getattr(state, "armed", None) is False:
            self.reset_timers()
            return {}
        if t < self.config.arm_time:
            return {}

        lost = {s for s in self.ever_fresh
                if s not in ALREADY_COVERED and not fresh.get(s, False)}

        # Clear the clock for anything that came back.
        for sensor in list(self._since):
            if sensor not in lost:
                del self._since[sensor]
        for sensor in lost:
            self._since.setdefault(sensor, t)

        dwelled = {s for s in lost
                   if t - self._since[s] >= self.config.dwell_up}

        out: dict = {}
        imus_lost = {s for s in dwelled if s in ("imu0", "imu1")}
        both_imus_known = {"imu0", "imu1"} <= self.ever_fresh

        for sensor in sorted(dwelled):
            if sensor in ("imu0", "imu1") and len(imus_lost) == 2 \
                    and both_imus_known:
                continue    # reported once, below, as the attitude case
            level, provenance, anchor = DERIVED_FROM.get(
                sensor, (FailsafeLevel.CAUTION, UNANCHORED, None))
            anchor_note = (f"level from FailsafeConfig.{anchor}"
                           if anchor else
                           "level NOT derivable from FailsafeConfig")
            out[f"data_loss_{sensor}"] = DataLossCondition(
                sensor=sensor, level=level, since=self._since[sensor],
                reason=(f"{sensor} stopped delivering valid data at "
                        f"t={self._since[sensor]:.2f}s ({anchor_note})"),
                provenance=provenance,
                actions=(Action("INHIBIT_DEPENDENT_FUNCTIONS",
                                f"stop consuming {sensor}; it is absent, "
                                f"not merely degraded", {"sensor": sensor}),))

        if len(imus_lost) == 2 and both_imus_known:
            since = min(self._since[s] for s in imus_lost)
            out["data_loss_attitude_reference"] = DataLossCondition(
                sensor="imu0+imu1", level=BOTH_IMUS_LOST, since=since,
                reason=("BOTH attitude sources stopped delivering at "
                        f"t={since:.2f}s; the frozen attitude rules read "
                        "max(..., default=1.0) here and cannot fire"),
                provenance=ANCHORED,
                actions=(Action("STABILIZE", "level on the last known "
                                "attitude; no source remains", {}),
                         Action("CONTROLLED_DESCENT", "descend at fixed "
                                "rate; do not attempt navigation",
                                {"rate_mps": self.config.descent_rate}),
                         Action("BROADCAST_MAYDAY", "notify GCS of "
                                "autonomous emergency descent", {})))

        self.conditions = out
        self.level = max((c.level for c in out.values()),
                         default=FailsafeLevel.NORMAL)
        return out


@dataclass
class SupervisedFailsafe:
    """The frozen policy, plus the loss-of-data rule it does not have.

    THE OVERLAY CAN ONLY RAISE THE LEVEL, NEVER LOWER IT. `level` is the
    max of the frozen policy's own level and the supervisor's. A layer
    above the core that could DE-escalate would be able to overrule a
    frozen safety decision, which is the one thing it must never do.
    """

    policy: object = None
    supervisor: DataLossSupervisor = field(
        default_factory=DataLossSupervisor)
    #: SR-006. Absence of data and presence of BAD data are different gaps
    #: and are supervised separately; `low_trust` fires only on a sensor
    #: that is still delivering, so the two never report one cause twice.
    low_trust: object = None

    def __post_init__(self):
        if self.low_trust is None:
            from .lowtrust import LowTrustSupervisor
            self.low_trust = LowTrustSupervisor()
        if self.policy is None:
            from csia.runtime.failsafe import FailsafePolicy
            self.policy = FailsafePolicy()

    @property
    def frozen_level(self) -> FailsafeLevel:
        return self.policy.level

    @property
    def level(self) -> FailsafeLevel:
        return max(self.policy.level, self.supervisor.level,
                   self.low_trust.level)

    # -- drop-in surface for the shadow runner ---------------------------
    # The runner reads these off the policy to build its per-tick record.
    # They are FORWARDED to the frozen policy rather than reimplemented: a
    # second implementation of `_conditions` would be a copy of the thing
    # under test, which the runner's own docstring warns against.

    @property
    def cfg(self) -> FailsafeConfig:
        return self.policy.cfg

    @property
    def transitions(self) -> list:
        return self.policy.transitions

    @property
    def _cond_since(self) -> dict:
        return getattr(self.policy, "_cond_since", {})

    def _conditions(self, state) -> dict:
        return self.policy._conditions(state)

    def data_loss_row(self) -> dict | None:
        """The overlay's own conditions, for the flight log.

        None when nothing is active, so a nominal flight does not carry an
        empty dict on every tick.
        """
        if not self.supervisor.conditions and not self.low_trust.conditions:
            return None
        row = {
            "level": max(self.supervisor.level, self.low_trust.level).name,
            "conditions": {
                name: {"sensor": c.sensor, "level": c.level.name,
                       "since_s": round(c.since, 3),
                       "provenance": c.provenance}
                for name, c in sorted(self.supervisor.conditions.items())},
        }
        if self.low_trust.conditions:
            # SEPARATE KEY. Degradation and absence are different findings
            # and a reader must not have to infer which one fired.
            row["low_trust"] = {
                name: {"sensor": c.sensor, "level": c.level.name,
                       "since_s": round(c.since, 3), "trust": round(c.trust, 4),
                       "threshold": c.threshold, "provenance": c.provenance}
                for name, c in sorted(self.low_trust.conditions.items())}
        return row

    def update(self, state) -> list:
        """Feed one state to both; returns the actions issued this tick."""
        issued = list(self.policy.update(state))
        for sup in (self.supervisor, self.low_trust):
            before = set(sup.conditions)
            sup.update(state)
            for name, condition in sorted(sup.conditions.items()):
                if name not in before:
                    issued.extend(condition.actions)
        return issued

    def explain(self) -> dict:
        return {
            "frozen_level": int(self.policy.level),
            "frozen_level_name": self.policy.level.name,
            "supervisor_level": int(self.supervisor.level),
            "supervisor_level_name": self.supervisor.level.name,
            "low_trust_level": int(self.low_trust.level),
            "low_trust_level_name": self.low_trust.level.name,
            "low_trust_conditions": {
                name: {"sensor": c.sensor, "level": c.level.name,
                       "since_s": round(c.since, 3), "trust": round(c.trust, 4),
                       "threshold": c.threshold, "reason": c.reason,
                       "provenance": c.provenance}
                for name, c in sorted(self.low_trust.conditions.items())},
            "the_two_gaps_are_separate": (
                "data_loss is ABSENCE of data (SR-001); low_trust is "
                "presence of data the trust engine does not believe "
                "(SR-006). low_trust fires only on a FRESH sensor, so one "
                "cause is never reported twice."),
            "effective_level": int(self.level),
            "effective_level_name": self.level.name,
            "data_loss_conditions": {
                name: {"sensor": c.sensor, "level": c.level.name,
                       "since_s": round(c.since, 3), "reason": c.reason,
                       "provenance": c.provenance}
                for name, c in sorted(self.supervisor.conditions.items())},
            "the_overlay_never_lowers_the_frozen_level": (
                "effective = max(frozen, supervisor). A layer above the "
                "core must not be able to de-escalate a frozen safety "
                "decision."),
        }
