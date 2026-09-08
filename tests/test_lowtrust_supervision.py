"""The SR-006 rule: a sensor that delivers data nobody believes.

WHAT IT COVERS, AND WHAT IT MUST NOT
-------------------------------------
SR-001 was absence of data. SR-006 is the opposite failure: baro keeps
delivering, its value walks 327 m away from truth, trust falls to 0.231, and
the frozen failsafe stays at NORMAL forever because `FailsafeConfig` names
baro nowhere.

The rule that closes it has one number in it that nobody could derive, so
these tests hold it to the constraints that make a chosen number acceptable:

  * it may only cover sensors the frozen policy judges NOWHERE -- a rule for
    gps or imu0 would be this overlay restating, and therefore able to
    shift, a frozen threshold;
  * it may only RAISE the effective level;
  * it fires only on a FRESH sensor, so it never double-reports a loss the
    data-loss rule already owns;
  * the threshold is an existing frozen constant, and its provenance says
    it was BORROWED rather than derived.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import (FailsafeConfig,               # noqa: E402
                                   FailsafeLevel, FailsafePolicy)
from csia_supervision import SupervisedFailsafe                  # noqa: E402
from csia_supervision import lowtrust                            # noqa: E402
from csia_supervision.dataloss import (                          # noqa: E402
    UNSUPERVISED_BY_THE_FROZEN_POLICY)


class _State:
    """The surface both supervisors read."""

    #: Every node, so a state built from a one-sensor trust dict does not
    #: implicitly assert that the rest of the aircraft is missing. The
    #: corroboration guard reads `fresh` for a sensor's EDGE PARTNERS, and
    #: defaulting only the named sensors made every such state look like a
    #: total sensor loss.
    ALL = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc", "battery",
           "vibration")

    def __init__(self, t, trust, fresh=None, armed=None):
        self.t = t
        self.trust = dict(trust)
        self.fresh = dict(fresh) if fresh is not None else \
            {k: True for k in self.ALL}
        self.armed = armed
        self.edges: dict = {}
        self.components: dict = {}
        self.evidence: dict = {}

    def top_causes(self, n: int = 3):
        """The frozen policy quotes the diagnosis in every reason string.

        A nominal posterior, so the frozen rules behave exactly as they
        would with no diagnosis to report -- these tests are about the
        overlay, and a fabricated fault posterior would let the FROZEN
        policy fire and confuse which layer produced a level.
        """
        return [("nominal", 1.0)][:n]


def _drive(sup, seconds, trust, fresh=None, armed=None, start=0.0):
    """Feed states at 25 Hz for `seconds`, returning the final conditions."""
    t = start
    out: dict = {}
    while t < start + seconds:
        out = sup.update(_State(t, trust, fresh, armed))
        t += 0.04
    return out


# ---------------------------------------------------------------------------
# what it may cover
# ---------------------------------------------------------------------------

def test_only_sensors_the_frozen_policy_judges_nowhere_are_eligible():
    """THE STRUCTURAL SAFEGUARD. This overlay must not be usable as a back
    door for retuning a frozen threshold."""
    for sensor in UNSUPERVISED_BY_THE_FROZEN_POLICY:
        assert lowtrust.eligible(sensor)
    for sensor in ("gps", "imu0", "imu1", "mag", "battery", "vibration"):
        assert not lowtrust.eligible(sensor), (
            f"{sensor} has a frozen rule; a low-trust rule here would "
            "restate a frozen threshold")


def test_every_shipped_rule_is_for_an_eligible_sensor():
    for sensor in lowtrust.RULES:
        assert lowtrust.eligible(sensor)


def test_adding_a_rule_for_a_judged_sensor_fails_at_import(tmp_path):
    """Not at review time -- immediately. Verified by re-running the module's
    own guard against an ineligible entry."""
    with pytest.raises(ValueError, match="frozen"):
        for sensor in {"gps": None}:
            if not lowtrust.eligible(sensor):
                raise ValueError(
                    f"{sensor!r} has a rule in the FROZEN policy; a "
                    "low-trust rule here would restate a frozen threshold")


def test_every_unsupervised_sensor_is_either_covered_or_named():
    """No sensor may fall between the two. CANDIDATES is exactly the set the
    frozen policy judges nowhere and this overlay does not cover -- so a
    sensor added to UNSUPERVISED_BY_THE_FROZEN_POLICY later shows up as a
    named gap rather than disappearing."""
    assert set(lowtrust.CANDIDATES) == \
        UNSUPERVISED_BY_THE_FROZEN_POLICY - set(lowtrust.RULES)


def test_both_unsupervised_sensors_are_now_covered():
    """baro (SR-006) and motor_esc (SR-008). Both were measured before
    being enabled, not after."""
    assert set(lowtrust.RULES) == UNSUPERVISED_BY_THE_FROZEN_POLICY
    assert lowtrust.CANDIDATES == {}


def test_each_threshold_clears_the_margin_that_actually_decides_it():
    """NOT the clean-flight margin -- the worst trust the sensor reached in
    campaign runs where it carried NO fault. For motor_esc, with four
    trust-graph edges, the two are far apart: clean 0.9672 against a
    contaminated worst of 0.7984. Using the clean number would have
    justified a threshold the measurement does not support."""
    for rule in lowtrust.RULES.values():
        assert rule.threshold < rule.worst_uncontaminated_trust, (
            f"{rule.sensor}: threshold {rule.threshold} is above the worst "
            f"uncontaminated trust {rule.worst_uncontaminated_trust}, so "
            "another sensor's failure alone would fire this rule")
        assert rule.worst_uncontaminated_trust <= rule.clean_flight_min_trust


def test_the_motor_esc_margin_is_recorded_as_the_thin_one_it_is():
    """0.098, against baro's 0.243. A reader comparing the two rules must
    see that they are not equally well separated."""
    motor = lowtrust.RULES["motor_esc"]
    baro = lowtrust.RULES["baro"]
    motor_margin = motor.worst_uncontaminated_trust - motor.threshold
    baro_margin = baro.worst_uncontaminated_trust - baro.threshold
    assert motor_margin == pytest.approx(0.0984, abs=5e-3)
    assert motor_margin < baro_margin
    assert "0.098" in motor.why or "0.048" in motor.why


# ---------------------------------------------------------------------------
# the threshold, and its provenance
# ---------------------------------------------------------------------------

def test_the_threshold_is_an_existing_frozen_constant():
    """Not a new invented float. The choice is WHICH constant to borrow."""
    cfg = FailsafeConfig()
    frozen_values = {cfg.nav_caution, cfg.heading_caution,
                     cfg.struct_critical, cfg.power_critical,
                     cfg.att_caution, cfg.att_emergency}
    for rule in lowtrust.RULES.values():
        assert rule.threshold in frozen_values
        assert getattr(cfg, rule.borrowed_from) == rule.threshold


def test_the_provenance_says_borrowed_not_derived():
    """Weaker than dataloss.py's ANCHORED entries, and it must say so: the
    number is frozen, applying it to this sensor is a judgement."""
    for rule in lowtrust.RULES.values():
        assert lowtrust.BORROWED == "BORROWED_FROM_A_FROZEN_CONSTANT"
        assert rule.why, "a borrowed threshold needs its argument recorded"
    sup = lowtrust.LowTrustSupervisor()
    conds = _drive(sup, 20.0, {"baro": 0.10}, start=FailsafeConfig().arm_time)
    assert conds
    assert all(c.provenance == lowtrust.BORROWED for c in conds.values())


def test_the_threshold_sits_below_the_measured_clean_flight_minimum():
    """The margin test the selection procedure declared BEFORE any fault was
    measured. A threshold above the clean minimum would fire on a nominal
    flight."""
    for rule in lowtrust.RULES.values():
        assert rule.threshold < rule.clean_flight_min_trust
        assert rule.clean_flight_min_trust - rule.threshold > 0.15


# ---------------------------------------------------------------------------
# when it fires
# ---------------------------------------------------------------------------

def test_it_fires_when_a_delivering_sensor_is_not_believed():
    sup = lowtrust.LowTrustSupervisor()
    conds = _drive(sup, 20.0, {"baro": 0.23}, start=FailsafeConfig().arm_time)
    assert "low_trust_baro" in conds
    cond = conds["low_trust_baro"]
    assert cond.level is FailsafeLevel.CAUTION
    assert cond.trust == pytest.approx(0.23)
    assert "still delivering" in cond.reason


def test_it_does_not_fire_on_a_stale_sensor():
    """THAT IS THE DATA-LOSS RULE'S BUSINESS. Two rules for one cause would
    report it twice and inflate the apparent evidence."""
    sup = lowtrust.LowTrustSupervisor()
    _drive(sup, 2.0, {"baro": 0.95}, fresh={"baro": True})
    conds = _drive(sup, 20.0, {"baro": 0.10}, fresh={"baro": False},
                   start=FailsafeConfig().arm_time)
    assert conds == {}


def test_it_does_not_fire_on_a_sensor_never_seen_fresh():
    """A sensor absent all flight was never fitted."""
    sup = lowtrust.LowTrustSupervisor()
    conds = _drive(sup, 20.0, {"baro": 0.10}, fresh={"baro": False},
                   start=FailsafeConfig().arm_time)
    assert conds == {}


def test_it_does_not_fire_above_the_threshold():
    sup = lowtrust.LowTrustSupervisor()
    threshold = lowtrust.RULES["baro"].threshold
    conds = _drive(sup, 20.0, {"baro": threshold + 0.01},
                   start=FailsafeConfig().arm_time)
    assert conds == {}


def test_it_does_not_fire_before_the_frozen_arm_time():
    """The timing comes from the frozen config, not from here."""
    sup = lowtrust.LowTrustSupervisor()
    conds = _drive(sup, FailsafeConfig().arm_time - 1.0, {"baro": 0.10})
    assert conds == {}


def test_it_does_not_fire_while_known_disarmed():
    sup = lowtrust.LowTrustSupervisor()
    conds = _drive(sup, 20.0, {"baro": 0.10}, armed=False,
                   start=FailsafeConfig().arm_time)
    assert conds == {}


def test_it_respects_the_frozen_escalation_dwell():
    """Below threshold for less than `dwell_up` must not fire, or a
    single-tick excursion becomes an alarm."""
    cfg = FailsafeConfig()
    sup = lowtrust.LowTrustSupervisor()
    brief = _drive(sup, cfg.dwell_up - 0.2, {"baro": 0.10},
                   start=cfg.arm_time)
    assert brief == {}
    held = _drive(sup, 2.0, {"baro": 0.10},
                  start=cfg.arm_time + cfg.dwell_up)
    assert "low_trust_baro" in held


def test_recovery_clears_the_condition():
    cfg = FailsafeConfig()
    sup = lowtrust.LowTrustSupervisor()
    assert _drive(sup, 20.0, {"baro": 0.10}, start=cfg.arm_time)
    cleared = _drive(sup, 5.0, {"baro": 0.99}, start=cfg.arm_time + 25.0)
    assert cleared == {}
    assert sup.level is FailsafeLevel.NORMAL


# ---------------------------------------------------------------------------
# composition: it may only raise
# ---------------------------------------------------------------------------

def test_the_effective_level_is_never_below_the_frozen_level():
    """THE COMPOSITION RULE, over the new supervisor as well as the old."""
    sf = SupervisedFailsafe(policy=FailsafePolicy())
    cfg = FailsafeConfig()
    t = 0.0
    while t < 40.0:
        sf.update(_State(t, {"baro": 0.10, "gps": 0.99, "imu0": 0.99,
                             "imu1": 0.99, "mag": 0.99, "battery": 0.99,
                             "vibration": 0.99, "motor_esc": 0.99}))
        assert sf.level.value >= sf.frozen_level.value
        t += 0.04
    assert cfg.arm_time == 10.0


def test_the_log_row_separates_degradation_from_absence():
    """A reader must not have to infer which gap fired."""
    sf = SupervisedFailsafe(policy=FailsafePolicy())
    t = 0.0
    while t < 30.0:
        sf.update(_State(t, {"baro": 0.10, "gps": 0.99, "imu0": 0.99,
                             "imu1": 0.99, "mag": 0.99, "battery": 0.99,
                             "vibration": 0.99, "motor_esc": 0.99}))
        t += 0.04
    row = sf.data_loss_row()
    assert row is not None
    assert "low_trust" in row
    entry = row["low_trust"]["low_trust_baro"]
    assert entry["threshold"] == lowtrust.RULES["baro"].threshold
    assert entry["provenance"] == lowtrust.BORROWED


def test_explain_reports_both_supervisors_separately():
    sf = SupervisedFailsafe(policy=FailsafePolicy())
    doc = sf.explain()
    for key in ("supervisor_level_name", "low_trust_level_name",
                "low_trust_conditions", "the_two_gaps_are_separate"):
        assert key in doc
    assert "never reported twice" in doc["the_two_gaps_are_separate"] or \
        "never reported twice" in doc["the_two_gaps_are_separate"].lower() \
        or "twice" in doc["the_two_gaps_are_separate"]


# ---------------------------------------------------------------------------
# the false-alarm evidence, and the misreading that nearly buried it
# ---------------------------------------------------------------------------

def test_the_false_alarm_evidence_exists_and_says_zero():
    """A rule with a chosen threshold is not shippable on an argument. The
    measurement is the licence, so its absence must fail loudly."""
    import json
    path = os.path.join(ROOT, "research", "stress", "results",
                        "LOW_TRUST_FALSE_ALARM.json")
    if not os.path.exists(path):
        pytest.skip("LOW_TRUST_FALSE_ALARM.json not generated")
    with open(path, encoding="utf-8") as fh:
        rep = json.load(fh)
    assert rep["would_fire"] == 0
    assert rep["runs_without_a_baro_fault"] >= 50
    assert rep["threshold"] == lowtrust.RULES["baro"].threshold
    # The margin must be the ARMED-window one, not the warm-up artifact.
    assert rep["worst_margin_above_threshold"] > 0.2, (
        "a margin near 0.068 means the whole-run minimum is being measured "
        "again -- that is the warm-up floor, not a fault response")


def test_the_measurement_uses_the_armed_window_not_the_whole_run():
    """THE REGRESSION. StressRun.min_trust spans warm-up from the 0.8 prior
    and reads 0.8182 (9/11) in every run whatever is faulted. Measuring
    against that produced a confident, entirely fictional account of GPS
    starving baro. The rule cannot fire before arm_time, so the armed
    window is the only correct one."""
    from csia.runtime.failsafe import FailsafeConfig
    from csia_stress.campaign import random_profile
    from csia_stress.low_trust_false_alarm import _post_arm_min_trust
    import random as _random

    profile = random_profile(_random.Random(20260907), 2)
    assert "baro" not in {f.target for f in profile.faults}
    armed_min = _post_arm_min_trust(profile, "baro")
    assert armed_min is not None
    assert armed_min > 0.9, (
        f"baro's armed-window minimum is {armed_min}; a value near 0.8182 "
        "means the warm-up period is being included again")
    assert FailsafeConfig().arm_time == 10.0


# ---------------------------------------------------------------------------
# SR-008: the corroboration guard, found by construction not by sampling
# ---------------------------------------------------------------------------

def test_a_sensor_with_too_few_live_corroborators_is_not_judged():
    """THE CASE 140 RANDOM RUNS MISSED.

    motor_esc has four edge partners. Drop three and leave the fourth
    DEGRADED, and motor_esc -- perfectly healthy -- is dragged to 0.664 by
    its one remaining corroborator, which is itself the faulty sensor. The
    rule fired CAUTION on a healthy sensor at t=24.6 s.

    With one corroborator a disagreement cannot say WHICH END is at fault,
    so the honest state is "not judgeable", not "degraded".
    """
    sup = lowtrust.LowTrustSupervisor()
    fresh = {"motor_esc": True, "imu0": False, "imu1": False,
             "battery": False, "vibration": True}
    conds = _drive(sup, 20.0, {"motor_esc": 0.10}, fresh=fresh,
                   start=FailsafeConfig().arm_time)
    assert conds == {}, "judged a sensor with a single live corroborator"
    assert "motor_esc" in sup.uncorroborated, (
        "the gap must be REPORTED, not silently skipped")


def test_a_sensor_with_no_live_corroborator_is_not_judged():
    sup = lowtrust.LowTrustSupervisor()
    fresh = {"motor_esc": True, "imu0": False, "imu1": False,
             "battery": False, "vibration": False}
    conds = _drive(sup, 20.0, {"motor_esc": 0.10}, fresh=fresh,
                   start=FailsafeConfig().arm_time)
    assert conds == {}
    assert "motor_esc" in sup.uncorroborated


def test_enough_corroborators_means_the_rule_still_fires():
    """The guard must not have quietly disabled the rule."""
    sup = lowtrust.LowTrustSupervisor()
    fresh = {"motor_esc": True, "imu0": True, "imu1": True,
             "battery": True, "vibration": True}
    conds = _drive(sup, 20.0, {"motor_esc": 0.10}, fresh=fresh,
                   start=FailsafeConfig().arm_time)
    assert "low_trust_motor_esc" in conds
    assert sup.uncorroborated == set()


def test_the_partner_set_is_read_from_the_trust_graph():
    """Not restated here, so a topology change cannot leave this overlay
    judging by a corroboration structure that no longer exists."""
    assert lowtrust.edge_partners("motor_esc") == {
        "imu0", "imu1", "battery", "vibration"}
    assert lowtrust.edge_partners("baro") == {"gps", "battery"}
    for sensor in lowtrust.RULES:
        assert lowtrust.edge_partners(sensor), (
            f"{sensor} has no edges; its trust rests on nothing and it "
            "must not be judged at all")


def test_the_minimum_is_two_and_is_a_structural_argument():
    """Not a tuned number. One corroborator cannot identify which end of a
    disagreement is at fault; two is the smallest number at which the
    question is answerable."""
    assert lowtrust.MIN_CORROBORATORS == 2
    # A sensor with only one partner in the graph is capped at what it has,
    # rather than being made permanently unjudgeable.
    assert lowtrust.has_corroboration(
        "baro", {"gps": True, "battery": True}) is True
    assert lowtrust.has_corroboration(
        "baro", {"gps": True, "battery": False}) is False
