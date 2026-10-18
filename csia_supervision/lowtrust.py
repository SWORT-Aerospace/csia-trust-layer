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
    #: THE MARGIN THAT ACTUALLY DECIDES THE THRESHOLD: the worst trust this
    #: sensor reached across campaign runs in which it carried NO fault. A
    #: clean flight is the easy case; what matters is whether OTHER sensors'
    #: failures drag this one below the line. For a well-connected sensor
    #: the two numbers are far apart.
    worst_uncontaminated_trust: float
    why: str


#: THE RULES. Both sensors the frozen policy judges nowhere are covered.
#: Each threshold was measured before it was enabled -- see the module
#: docstring for the procedure, which was declared before any fault was run.
RULES: dict = {
    "baro": LowTrustRule(
        sensor="baro",
        threshold=0.75,
        level=FailsafeLevel.CAUTION,
        borrowed_from="nav_caution",
        clean_flight_min_trust=0.9930,
        #: Worst observed in campaign runs carrying NO baro fault. Baro has
        #: one edge, so another sensor's failure barely touches it.
        worst_uncontaminated_trust=0.9930,
        why=("baro's only trust-graph edge is `altitude_baro`, spanning "
             "(baro, gps); gps trust is what nav_caution governs, and "
             "barometric altitude is navigation state. Level CAUTION "
             "matches the level dataloss.py already assigns baro."),
    ),
}

#: Sensors with the same gap that this module does NOT cover, and why.
CANDIDATES: dict = {
    "motor_esc": (
        "WITHDRAWN after the falsification search found a false alarm the "
        "corroboration guard cannot fix (SR-009/SR-010). motor_esc has FOUR "
        "edge partners, which creates a state baro cannot reach: some "
        "partners rejected as unfit to corroborate while their contamination "
        "of the trust value REMAINS. Measured: battery dropped and vibration "
        "at 0.300 were both correctly rejected, imu0 (0.918) and imu1 "
        "(0.939) still supplied the two corroborators the guard requires, "
        "and motor_esc -- healthy -- sat at 0.667 because the rejected "
        "vibration partner was dragging it there. A sensor cannot be judged "
        "by a trust value contaminated by the partners just deemed unfit to "
        "judge it. Reinstating this rule needs a trust value computed "
        "WITHOUT the rejected partners. "
        "TWO CORRECTIONS TO THAT SENTENCE, both measured (SR-011). "
        "FIRST, it is NOT a frozen-core change. Every term the recursion "
        "needs is already published in TrustState, so it reproduces exactly "
        "outside the core -- measured drift 0.0 against the core's own "
        "trust over 4500 ticks. `csia_supervision/contamination.py` does it "
        "and changes no frozen file. "
        "SECOND, AND THIS IS WHY THE RULE STILL STAYS WITHDRAWN: computing "
        "the trust without the rejected partners does NOT fix it. Traced on "
        "the same combination at t=40.0 s, motor_esc sits at 0.65000 with "
        "all three incident edges at consistency 0.0000, and the only "
        "ADMITTED partner is imu0 at 0.8528 against its own att_caution "
        "standing of 0.82. imu0's bias drift breaks the accel/motor-current "
        "relation while imu0's own trust stays above threshold. The "
        "contamination arrives through an admitted edge, so filtering "
        "partners by standing cannot remove it -- partner-level standing "
        "and edge-level agreement are different facts and the guard only "
        "tests the first."),
}


def edge_partners(sensor: str) -> frozenset:
    """The sensors this one is cross-checked against, from the trust graph.

    READ from `csia.trust_graph.graph.EDGES` rather than restated, so a
    change to the topology cannot leave this overlay judging a sensor by a
    corroboration structure that no longer exists.
    """
    from csia.trust_graph.graph import EDGES
    out = set()
    for a, b, *_ in EDGES:
        if a == sensor:
            out.add(b)
        elif b == sensor:
            out.add(a)
    return frozenset(out)


#: How many live edge partners a judgement needs. NOT a tuned number: with
#: exactly ONE live corroborator, a disagreement on that edge cannot say
#: which END of it is at fault, so a low trust is equally consistent with
#: this sensor being bad and with its lone corroborator being bad. Two is
#: the smallest number at which the question is answerable at all.
MIN_CORROBORATORS = 2


#: The threshold that governs each sensor, so "is this partner itself in
#: good standing?" is answered by the number the system ALREADY applies to
#: that sensor -- not by a new one invented here. Five come straight from
#: the frozen FailsafeConfig; the two the frozen policy judges nowhere use
#: this overlay's own borrowed thresholds.
GOVERNING_THRESHOLD: dict = {
    "imu0": "att_caution",
    "imu1": "att_caution",
    "mag": "heading_caution",
    "battery": "power_critical",
    "vibration": "struct_critical",
    "gps": "nav_caution",
}


def _standing(sensor: str, config: FailsafeConfig) -> float:
    """The trust below which `sensor` is itself considered suspect."""
    field = GOVERNING_THRESHOLD.get(sensor)
    if field is not None:
        return float(getattr(config, field))
    rule = RULES.get(sensor)
    return float(rule.threshold) if rule else 0.0


def has_corroboration(sensor: str, fresh: dict, trust: dict | None = None,
                      config: FailsafeConfig | None = None) -> bool:
    """Are there enough sensors in GOOD STANDING left to vouch for this one?

    THE GUARD THAT KEEPS THIS RULE HONEST. A trust value is only evidence of
    degradation when something was in a position to disagree with it. Once
    the partners are gone -- or are themselves suspect -- the sensor's trust
    decays because nothing can corroborate it, not because it is bad, and
    firing a "degraded" alarm there states a fault where the truth is that
    nothing is knowable.

    IT COUNTED LIVE PARTNERS, WHICH WAS NOT ENOUGH, AND THE FALSIFICATION
    SEARCH PROVED IT ON ITS FIRST COMBINATION. With battery dropped and
    imu0, imu1 and vibration all DEGRADED BUT STILL DELIVERING, motor_esc
    had three live partners -- comfortably past MIN_CORROBORATORS -- and
    those three degraded partners together dragged a perfectly healthy
    motor_esc to 0.65, firing CAUTION at t=27.8 s. Liveness was the wrong
    test: a partner that is itself failing is not in a position to disagree
    with anything, because its disagreement is equally explained by its own
    fault.

    So a corroborator must now be live AND in good standing -- above the
    threshold the system already applies to IT (`GOVERNING_THRESHOLD`),
    which introduces no new number anywhere.

    `trust` is optional only so the older two-argument call keeps working;
    without it the check degrades to the liveness test that was shown to be
    insufficient, and callers inside this module always pass it.

    This is the same rule the capability bridge applies in the other
    direction: UNKNOWN is never resolved into a definite state.
    """
    partners = edge_partners(sensor)
    cfg = config or FailsafeConfig()
    if trust is None:
        live = sum(1 for p in partners if fresh.get(p, False))
    else:
        live = sum(1 for p in partners
                   if fresh.get(p, False)
                   and float(trust.get(p, 0.0)) >= _standing(p, cfg))
    return live >= min(MIN_CORROBORATORS, len(partners))


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
    #: Sensors whose trust could not be judged this tick because every edge
    #: partner was gone. Not a condition -- an absence of grounds for one.
    uncorroborated: set = field(default_factory=set)

    def reset_timers(self) -> None:
        self._since.clear()
        self.conditions = {}
        self.uncorroborated = set()
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
        self.uncorroborated = set()
        for sensor, rule in self.rules.items():
            if sensor not in self.ever_fresh or not fresh.get(sensor, False):
                continue
            # NO CORROBORATION, NO JUDGEMENT. A low trust with every edge
            # partner gone -- or every one of them itself suspect -- means
            # nothing could vouch for this sensor, not that the sensor is
            # bad. `trust` is passed because LIVENESS ALONE WAS NOT ENOUGH:
            # three live-but-degraded partners passed the old check and
            # dragged a healthy motor_esc below its threshold. Reported
            # separately rather than silently skipped, so the gap stays
            # visible.
            if not has_corroboration(sensor, fresh, trust, self.config):
                self.uncorroborated.add(sensor)
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
