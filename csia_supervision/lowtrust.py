"""A low-trust rule for the sensors the frozen policy scores but never judges.

THE GAP, WHICH IS NOT THE SAME AS SR-001's
-------------------------------------------
SR-001 was about ABSENCE: a sensor stops delivering and no rule fires.
`dataloss.py` covers that, baro included.

SR-006 found a different one. Drive a bias drift into the barometer and the
sensor keeps delivering perfectly good-looking packets while the value walks
away from truth. Measured: at a drift of 1.0 units/s over 40 s the altitude
error reaches **327 m**, baro trust falls from the 0.8 prior to **0.231** --
and the failsafe level never leaves NORMAL at any magnitude swept.

The trust engine sees it. Nothing acts on it, because `FailsafeConfig` has
no threshold that names baro: the frozen `_conditions` references `baro`
ZERO times. So trust is computed, published, and then judged by nobody.

    absence of data   -> dataloss.py      (SR-001)
    presence of BAD data -> this module   (SR-006)

WHY A THRESHOLD HERE IS A CHOICE, AND WHAT WAS DONE ABOUT IT
-------------------------------------------------------------
There is no frozen number to derive from, so one has to be chosen, and the
standing rule is that a chosen number is never tuned to rescue a result. The
selection procedure was therefore DECLARED BEFORE any fault was measured:

  1. measure the minimum baro trust on CLEAN flights, every flight profile;
  2. the threshold must sit strictly below that minimum with margin, so it
     cannot fire on a nominal flight;
  3. among values satisfying (2), take an EXISTING `FailsafeConfig`
     constant rather than inventing a new float;
  4. if no frozen constant satisfies (2), report that and invent nothing.

Measured at step 1: clean-flight minimum baro trust is **0.9930**
(hover_circle) and **0.9931** (fast_cruise), so every frozen constant
(0.60, 0.70, 0.75, 0.82) clears step 2 comfortably.

Step 3 chose **0.75, the value of `nav_caution`**, because baro's ONLY edge
in the trust graph is `altitude_baro`, spanning (baro, gps) -- and gps trust
is exactly what `nav_caution` governs. Barometric altitude is navigation
state, and this is the threshold the frozen policy already applies to
navigation trust.

**That is an argument from topology, not a derivation.** The number is not
invented, but applying it to this sensor is a judgement, so the provenance
is recorded as `BORROWED_FROM_A_FROZEN_CONSTANT` -- weaker than the
`ANCHORED` entries in `dataloss.py`, stronger than a free choice. A reader
can see exactly which part is mine.

WHAT THIS MODULE STRUCTURALLY CANNOT DO
----------------------------------------
It refuses to carry a rule for any sensor the frozen policy already judges.
`eligible()` is checked at import and in tests: a rule for `gps` or `imu0`
would be this overlay quietly restating a frozen threshold, which is
retuning the frozen core through the back door. The only sensors it may
cover are the ones `FailsafeConfig` names nowhere.

It also fires only on a sensor that is FRESH. A stale sensor is the data-loss
rule's business, and two rules reporting one cause would double-count it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csia.runtime.failsafe import Action, FailsafeConfig, FailsafeLevel

from .dataloss import UNSUPERVISED_BY_THE_FROZEN_POLICY

#: The number comes from the frozen config; applying it to THIS sensor is a
#: judgement. Weaker than dataloss.ANCHORED, stronger than a free choice.
BORROWED = "BORROWED_FROM_A_FROZEN_CONSTANT"


@dataclass(frozen=True)
class LowTrustRule:
    sensor: str
    threshold: float
    level: FailsafeLevel
    borrowed_from: str
    #: The clean-flight minimum this threshold was checked against, so the
    #: false-alarm margin is visible next to the number itself.
    clean_flight_min_trust: float
    why: str


#: THE RULES. One entry, deliberately: `motor_esc` has the identical gap and
#: is NOT covered here, because covering it was not asked for and its
#: false-alarm margin has not been measured under load. See `CANDIDATES`.
RULES: dict = {
    "baro": LowTrustRule(
        sensor="baro",
        threshold=0.75,
        level=FailsafeLevel.CAUTION,
        borrowed_from="nav_caution",
        clean_flight_min_trust=0.9930,
        why=("baro's only trust-graph edge is `altitude_baro`, spanning "
             "(baro, gps); gps trust is what nav_caution governs, and "
             "barometric altitude is navigation state. Level CAUTION "
             "matches the level dataloss.py already assigns baro."),
    ),
}

#: Sensors with the same gap that this module does NOT cover, named so the
#: omission is visible rather than inferred from an absence.
CANDIDATES: dict = {
    "motor_esc": ("same gap -- no frozen rule of any kind -- but its "
                  "clean-flight trust margin under load has not been "
                  "measured, and a rule whose false-alarm rate is unknown "
                  "is worse than a stated gap"),
}


def eligible(sensor: str) -> bool:
    """May this overlay judge `sensor` at all?

    ONLY sensors the frozen policy judges NOWHERE. A rule for a sensor the
    frozen config already thresholds would be this overlay restating -- and
    therefore able to shift -- a frozen safety decision.
    """
    return sensor in UNSUPERVISED_BY_THE_FROZEN_POLICY


# Checked at import: a rule added for an ineligible sensor fails loudly and
# immediately rather than at some later review.
for _sensor in RULES:
    if not eligible(_sensor):
        raise ValueError(
            f"{_sensor!r} has a rule in the FROZEN policy; a low-trust rule "
            f"here would restate a frozen threshold, which is retuning the "
            f"frozen core through the back door")


@dataclass
class LowTrustCondition:
    sensor: str
    level: FailsafeLevel
    since: float
    reason: str
    provenance: str
    trust: float
    threshold: float
    actions: tuple = ()


@dataclass
class LowTrustSupervisor:
    """Raises a condition when an UNJUDGED sensor's trust falls.

    Mirrors the frozen state machine on when a rule may fire at all: not
    before `arm_time`, not while known-disarmed, and only after `dwell_up`
    of the condition holding. Those come from the frozen `FailsafeConfig`
    rather than being chosen here.
    """

    config: FailsafeConfig = field(default_factory=FailsafeConfig)
    rules: dict = field(default_factory=lambda: dict(RULES))
    ever_fresh: set = field(default_factory=set)
    _since: dict = field(default_factory=dict)
    conditions: dict = field(default_factory=dict)
    level: FailsafeLevel = FailsafeLevel.NORMAL

    def reset_timers(self) -> None:
        self._since.clear()
        self.conditions = {}
        self.level = FailsafeLevel.NORMAL

    def update(self, state) -> dict:
        t = float(state.t)
        fresh = dict(getattr(state, "fresh", {}) or {})
        trust = dict(getattr(state, "trust", {}) or {})
        for sensor, ok in fresh.items():
            if ok:
                self.ever_fresh.add(sensor)

        if getattr(state, "armed", None) is False:
            self.reset_timers()
            return {}
        if t < self.config.arm_time:
            return {}

        # FRESH ONLY. A stale sensor belongs to the data-loss rule, and both
        # firing for one cause would report it twice.
        low = set()
        for sensor, rule in self.rules.items():
            if sensor not in self.ever_fresh or not fresh.get(sensor, False):
                continue
            value = trust.get(sensor)
            if value is not None and value < rule.threshold:
                low.add(sensor)

        for sensor in list(self._since):
            if sensor not in low:
                del self._since[sensor]
        for sensor in low:
            self._since.setdefault(sensor, t)

        out: dict = {}
        for sensor in sorted(low):
            if t - self._since[sensor] < self.config.dwell_up:
                continue
            rule = self.rules[sensor]
            value = float(trust.get(sensor))
            out[f"low_trust_{sensor}"] = LowTrustCondition(
                sensor=sensor, level=rule.level, since=self._since[sensor],
                trust=value, threshold=rule.threshold,
                reason=(f"{sensor} trust {value:.3f} below {rule.threshold} "
                        f"since t={self._since[sensor]:.2f}s; the sensor is "
                        f"still delivering, so this is degradation and not "
                        f"loss (threshold borrowed from "
                        f"FailsafeConfig.{rule.borrowed_from})"),
                provenance=BORROWED,
                actions=(Action("INHIBIT_DEPENDENT_FUNCTIONS",
                                f"stop consuming {sensor}; it is delivering "
                                f"data that the trust engine does not "
                                f"believe", {"sensor": sensor}),))

        self.conditions = out
        self.level = max((c.level for c in out.values()),
                         default=FailsafeLevel.NORMAL)
        return out
