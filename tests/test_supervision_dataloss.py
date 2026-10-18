"""SR-001 closed: a loss-of-data rule for the seven sensors without one.

The frozen failsafe alarms when a sensor's TRUST falls and says nothing
when the sensor stops delivering -- for every sensor but GPS. This overlay
supplies the missing rule ABOVE the frozen core, which is not modified.

Three properties carry the safety argument, and each has its own test:

  1. it ESCALATES where the frozen policy was silent (SR-001 closed)
  2. it NEVER LOWERS a level the frozen policy raised
  3. it does NOT FIRE on a clean flight, or on a sensor never fitted

(3) is the one that decides whether this is an improvement or a nuisance.
A rule that alarms on healthy flight would be worse than the gap it fills,
because an alarm nobody believes is an alarm nobody acts on.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import (FailsafeConfig,           # noqa: E402
                                   FailsafeLevel, FailsafePolicy)
from csia.runtime.online import OnlineTrustLayer             # noqa: E402
from csia.sensors.faults import Fault                        # noqa: E402
from csia_stress.source import StressFlightSource            # noqa: E402
from csia_supervision import (ALREADY_COVERED,               # noqa: E402
                              ANCHORED, BOTH_IMUS_LOST, DERIVED_FROM,
                              UNANCHORED,
                              UNSUPERVISED_BY_THE_FROZEN_POLICY,
                              DataLossSupervisor, SupervisedFailsafe)

SENSORS = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc", "battery",
           "vibration")


def _run(faults, duration=90.0):
    """Drive both the frozen policy and the overlay over one flight."""
    source = StressFlightSource(faults=faults, duration=duration)
    layer = OnlineTrustLayer()
    frozen = FailsafePolicy()
    supervised = SupervisedFailsafe()

    states, last_t = [], 0.0
    for sensor, t, channels in source.samples():
        states.extend(layer.ingest(sensor, t, channels))
        last_t = t
    states.extend(layer.flush(last_t))

    peak_frozen = peak_effective = FailsafeLevel.NORMAL
    # Conditions are transient by design: they clear when the sensor comes
    # back. Collect every one that was EVER active, because checking at the
    # end of a flight whose faults cleared 30 s earlier finds nothing --
    # which is the overlay working, not failing.
    ever_active: set = set()
    for state in states:
        frozen.update(state)
        supervised.update(state)
        ever_active |= set(supervised.supervisor.conditions)
        peak_frozen = max(peak_frozen, frozen.level)
        peak_effective = max(peak_effective, supervised.level)
    supervised.ever_active = ever_active
    return peak_frozen, peak_effective, supervised


# ---------------------------------------------------------------------------
# 1. it escalates where the frozen policy was silent
# ---------------------------------------------------------------------------

def test_sr001_losing_both_imus_now_reaches_emergency():
    """THE HEADLINE. Both attitude sources stop delivering for 40 s.

    The frozen rules reason over FRESH imus and take
    `max(..., default=1.0)`, so with neither fresh the attitude confidence
    reads 1.000 and both attitude rules are unreachable -- the frozen peak
    is NORMAL for the whole flight. The overlay calls it what it is.
    """
    frozen, effective, sup = _run((Fault("dropout", "imu0", 20.0, 40.0),
                                   Fault("dropout", "imu1", 20.0, 40.0)))
    assert frozen == FailsafeLevel.NORMAL, (
        "the frozen gap has closed on its own; re-read SR-001")
    assert effective == FailsafeLevel.EMERGENCY
    assert "data_loss_attitude_reference" in sup.ever_active


def test_the_attitude_case_is_reported_once_not_twice():
    """Losing both IMUs is ONE attitude-reference failure, not two sensor
    losses. Reporting it twice would double-count the same event."""
    _, _, sup = _run((Fault("dropout", "imu0", 20.0, 40.0),
                      Fault("dropout", "imu1", 20.0, 40.0)))
    names = sup.ever_active
    assert "data_loss_attitude_reference" in names
    assert "data_loss_imu0" not in names and "data_loss_imu1" not in names


@pytest.mark.parametrize("sensor,expected", [
    ("mag", FailsafeLevel.CAUTION),
    ("battery", FailsafeLevel.CRITICAL),
    ("baro", FailsafeLevel.CAUTION),
    ("motor_esc", FailsafeLevel.CAUTION),
    ("imu0", FailsafeLevel.CAUTION),
])
def test_each_sensor_loss_now_escalates_to_its_derived_level(sensor, expected):
    frozen, effective, sup = _run((Fault("dropout", sensor, 20.0, 40.0),))
    assert frozen == FailsafeLevel.NORMAL, (
        f"{sensor}: the frozen policy now covers this loss on its own")
    assert effective == expected
    assert f"data_loss_{sensor}" in sup.ever_active


def test_the_vibration_rule_exists_but_cannot_be_exercised_here():
    """SR-002 MEETS SR-001, and the honest answer is "untestable in this rig".

    `dropout` on the vibration node marks every sample invalid in the
    sampled stream and reaches the layer as NOTHING, because
    SimulatedFlightSource emits the 10 Hz RMS envelope with a hardcoded
    valid=True. So `fresh["vibration"]` never goes false, and the overlay
    correctly stays quiet -- there is no loss for it to see.

    The RULE is present and its level is derived from
    FailsafeConfig.struct_critical like every other. What is missing is a
    way to DELIVER the stimulus, which is a property of the simulator, not
    of this overlay. Asserting CRITICAL here would be asserting something
    the rig cannot produce.
    """
    from csia_stress import matrix
    assert ("dropout", "vibration") in matrix().lost_in_transport()
    level, provenance, anchor = DERIVED_FROM["vibration"]
    assert level == FailsafeLevel.CRITICAL
    assert provenance == ANCHORED and anchor == "struct_critical"

    # And it really does stay quiet, for the SR-002 reason.
    frozen, effective, sup = _run((Fault("dropout", "vibration", 20.0, 40.0),))
    assert effective == FailsafeLevel.NORMAL
    assert "data_loss_vibration" not in sup.ever_active


def test_all_seven_uncovered_sensors_have_a_rule():
    """The request was a rule for the OTHER SEVEN. Counted, not assumed."""
    covered = set(DERIVED_FROM) | {"imu0", "imu1"}
    assert set(SENSORS) - ALREADY_COVERED == covered
    assert len(set(SENSORS) - ALREADY_COVERED) == 7


# ---------------------------------------------------------------------------
# 2. it never lowers a frozen level
# ---------------------------------------------------------------------------

def test_gps_is_left_to_the_frozen_rule():
    """GPS already has a loss-of-data rule. The overlay must not
    double-report it, and must not change its level."""
    frozen, effective, sup = _run((Fault("dropout", "gps", 20.0, 40.0),))
    assert frozen == FailsafeLevel.CAUTION
    assert effective == FailsafeLevel.CAUTION
    assert "data_loss_gps" not in sup.ever_active
    assert "gps" in ALREADY_COVERED


def test_the_overlay_cannot_lower_a_frozen_level():
    """THE SAFETY PROPERTY. effective = max(frozen, supervisor), so a layer
    above the core can add urgency and never remove it."""
    frozen, effective, _ = _run((Fault("vibration_anomaly", "vibration",
                                       20.0, 25.0, {"gain": 3.0}),))
    assert frozen == FailsafeLevel.CRITICAL
    assert effective >= frozen

    # And directly, on the composition itself.
    sup = SupervisedFailsafe()
    sup.policy.level = FailsafeLevel.EMERGENCY
    sup.supervisor.level = FailsafeLevel.NORMAL
    assert sup.level == FailsafeLevel.EMERGENCY


def test_a_bad_data_fault_is_unchanged_by_the_overlay():
    """Degradation, as opposed to absence, was never the gap. The overlay
    must leave those runs exactly where the frozen policy put them."""
    for faults in (
            (Fault("gps_spoof", "gps", 20.0, 20.0, {"drift": (3.0, 1.0, 0.0)}),),
            (Fault("bias_drift", "imu0", 20.0, 30.0,
                   {"axis": 2, "rate": 0.18, "channel": "accel"}),),
    ):
        frozen, effective, _ = _run(faults)
        assert effective == frozen


# ---------------------------------------------------------------------------
# 3. it does not fire when it should not
# ---------------------------------------------------------------------------

def test_a_clean_flight_stays_normal():
    """THE TEST THAT DECIDES WHETHER THIS IS AN IMPROVEMENT.

    A loss-of-data rule that alarms on healthy flight is worse than the gap
    it fills.
    """
    frozen, effective, sup = _run(())
    assert frozen == FailsafeLevel.NORMAL
    assert effective == FailsafeLevel.NORMAL
    assert sup.ever_active == set(), (
        "the overlay raised a data-loss condition on a CLEAN flight")


def test_a_sensor_never_fitted_never_alarms():
    """A node absent for the whole flight was not fitted. Alarming on it
    would make every reduced-sensor airframe scream on takeoff -- the same
    rule the frozen policy applies to GPS via `_ever_fresh`."""
    supervisor = DataLossSupervisor()

    class _State:
        t = 50.0
        armed = True
        fresh = {"imu0": True, "imu1": True}   # mag never mentioned

    supervisor.update(_State())
    assert supervisor.conditions == {}
    assert "mag" not in supervisor.ever_fresh


def test_nothing_fires_before_arm_time():
    supervisor = DataLossSupervisor()

    class _Early:
        t = FailsafeConfig().arm_time - 1.0
        armed = True
        fresh = {"mag": False}

    supervisor.update(_Early())
    assert supervisor.conditions == {}


def test_a_known_disarmed_vehicle_resets_the_clock():
    """Failsafe actions are meaningless on the ground, and a pre-disarm
    onset must not escalate the instant the vehicle arms."""
    supervisor = DataLossSupervisor()

    class _S:
        def __init__(self, t, armed, fresh):
            self.t, self.armed, self.fresh = t, armed, fresh

    supervisor.update(_S(20.0, True, {"mag": True}))
    supervisor.update(_S(21.0, True, {"mag": False}))
    assert supervisor._since, "the clock should have started"
    supervisor.update(_S(22.0, False, {"mag": False}))
    assert supervisor._since == {} and supervisor.conditions == {}


def test_a_brief_gap_shorter_than_the_dwell_does_not_alarm():
    """`dwell_up` comes from the frozen config, not from a number chosen
    here, so a momentary dropout is not an emergency."""
    supervisor = DataLossSupervisor()
    dwell = FailsafeConfig().dwell_up

    class _S:
        def __init__(self, t, fresh):
            self.t, self.armed, self.fresh = t, True, fresh

    supervisor.update(_S(20.0, {"mag": True}))
    supervisor.update(_S(20.0 + dwell / 2, {"mag": False}))
    assert supervisor.conditions == {}
    supervisor.update(_S(20.0 + dwell * 2, {"mag": False}))
    assert "data_loss_mag" in supervisor.conditions


def test_a_recovered_sensor_clears_its_condition():
    supervisor = DataLossSupervisor()

    class _S:
        def __init__(self, t, fresh):
            self.t, self.armed, self.fresh = t, True, fresh

    supervisor.update(_S(20.0, {"mag": True}))
    supervisor.update(_S(25.0, {"mag": False}))
    # dwell_up must elapse before the condition is raised
    supervisor.update(_S(25.0 + FailsafeConfig().dwell_up * 2, {"mag": False}))
    assert "data_loss_mag" in supervisor.conditions
    supervisor.update(_S(30.0, {"mag": True}))
    assert supervisor.conditions == {}
    assert supervisor.level == FailsafeLevel.NORMAL


# ---------------------------------------------------------------------------
# provenance: which numbers are derived and which are mine
# ---------------------------------------------------------------------------

def test_every_level_is_either_anchored_or_labelled_as_a_choice():
    for sensor, (level, provenance, anchor) in DERIVED_FROM.items():
        assert provenance in (ANCHORED, UNANCHORED), sensor
        if provenance == ANCHORED:
            assert anchor, f"{sensor}: anchored but names no frozen field"
        else:
            assert anchor is None


def test_exactly_the_two_unsupervised_sensors_are_unanchored():
    """`baro` and `motor_esc` are referenced ZERO times in the frozen
    conditions, so there is no severity to derive. Those two levels are the
    only judgement in the table, and they are labelled as such."""
    unanchored = {s for s, (_, p, _) in DERIVED_FROM.items()
                  if p == UNANCHORED}
    assert unanchored == UNSUPERVISED_BY_THE_FROZEN_POLICY
    assert unanchored == {"baro", "motor_esc"}


def test_the_anchors_name_real_frozen_config_fields():
    config = vars(FailsafeConfig())
    for sensor, (_, provenance, anchor) in DERIVED_FROM.items():
        if provenance != ANCHORED or anchor is None:
            continue
        field = anchor.split()[0]
        assert field in config or field.startswith("imu_"), (
            f"{sensor}: anchor {anchor!r} names no FailsafeConfig field")


def test_losing_both_imus_is_the_emergency_the_frozen_policy_calls_it():
    """The frozen policy calls a lost attitude reference EMERGENCY. Total
    loss of both sources is that, so the overlay uses the same level rather
    than a new one."""
    assert BOTH_IMUS_LOST == FailsafeLevel.EMERGENCY


def test_the_frozen_failsafe_is_not_modified():
    """The overlay exists BECAUSE the file is frozen. If this ever fails,
    the reason for the whole package has gone."""
    import subprocess
    diff = subprocess.run(
        ["git", "diff", "--stat", "csia-v1.0-research-final", "--",
         "csia/runtime/failsafe.py"],
        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert diff == "", "csia/runtime/failsafe.py differs from the freeze tag"


# ---------------------------------------------------------------------------
# boundaries. Survivors of the mutation probe on this module: only a value
# sitting exactly ON a threshold distinguishes >= from >.
# ---------------------------------------------------------------------------

class _Tick:
    """A minimal state that satisfies BOTH the overlay and the frozen policy.

    The frozen `_conditions` reads `trust`, `fresh`, `armed` and
    `top_causes`, so a stub carrying only freshness drives the supervisor
    fine and crashes the frozen policy. All nodes are healthy here, so the
    frozen policy stays NORMAL and any escalation observed is the overlay's.
    """

    NODES = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc", "battery",
             "vibration")

    def __init__(self, t, fresh, armed=True):
        self.t, self.fresh, self.armed = t, fresh, armed
        self.trust = {n: 0.99 for n in self.NODES}
        self.edges = {}

    def top_causes(self, n=3):
        return [("nominal", 0.99)][:n]


def test_the_rule_arms_exactly_at_arm_time_not_after():
    """SURVIVOR KILL: `if t < self.config.arm_time`.

    Only a state AT arm_time tells `<` from `<=`. A rule that armed one
    tick late would be invisible to any test using a round number.
    """
    arm = FailsafeConfig().arm_time
    dwell = FailsafeConfig().dwell_up

    supervisor = DataLossSupervisor()
    supervisor.update(_Tick(arm - 5.0, {"mag": True}))
    supervisor.update(_Tick(arm, {"mag": False}))          # exactly at arm
    supervisor.update(_Tick(arm + dwell, {"mag": False}))
    assert "data_loss_mag" in supervisor.conditions, (
        "the rule did not arm at arm_time itself")


def test_the_dwell_fires_exactly_at_dwell_up_not_after():
    """SURVIVOR KILL: `if t - self._since[s] >= self.config.dwell_up`."""
    dwell = FailsafeConfig().dwell_up
    supervisor = DataLossSupervisor()
    supervisor.update(_Tick(20.0, {"mag": True}))
    supervisor.update(_Tick(21.0, {"mag": False}))         # onset at 21.0
    supervisor.update(_Tick(21.0 + dwell, {"mag": False}))  # exactly dwelled
    assert "data_loss_mag" in supervisor.conditions

    just_short = DataLossSupervisor()
    just_short.update(_Tick(20.0, {"mag": True}))
    just_short.update(_Tick(21.0, {"mag": False}))
    just_short.update(_Tick(21.0 + dwell * 0.99, {"mag": False}))
    assert just_short.conditions == {}


def test_a_sensor_missing_from_the_fresh_map_counts_as_lost():
    """SURVIVOR KILL: the `fresh.get(s, False)` default.

    A sensor that WAS delivering and then vanishes from the freshness map
    entirely is not 'assumed fine'. Defaulting to True there would make a
    silently-dropped node invisible -- which is the whole failure SR-001 is
    about, reintroduced one layer up.
    """
    supervisor = DataLossSupervisor()
    dwell = FailsafeConfig().dwell_up
    supervisor.update(_Tick(20.0, {"mag": True, "battery": True}))
    supervisor.update(_Tick(21.0, {"battery": True}))          # mag GONE
    supervisor.update(_Tick(21.0 + dwell, {"battery": True}))
    assert "data_loss_mag" in supervisor.conditions


def test_one_imu_never_fitted_reports_a_single_sensor_loss():
    """SURVIVOR KILL: `both_imus_known = {"imu0","imu1"} <= self.ever_fresh`.

    On a single-IMU airframe, losing that IMU is a sensor loss, not the
    'both attitude sources gone' case -- there was never a second one. The
    guard exists so a one-IMU vehicle does not get an EMERGENCY the moment
    its only IMU blinks.
    """
    supervisor = DataLossSupervisor()
    dwell = FailsafeConfig().dwell_up
    supervisor.update(_Tick(20.0, {"imu0": True}))     # imu1 never seen
    supervisor.update(_Tick(21.0, {"imu0": False}))
    supervisor.update(_Tick(21.0 + dwell, {"imu0": False}))
    assert "data_loss_imu0" in supervisor.conditions
    assert "data_loss_attitude_reference" not in supervisor.conditions
    assert supervisor.level == FailsafeLevel.CAUTION


def test_actions_are_issued_once_per_condition_not_every_tick():
    """SURVIVOR KILL: `if name not in before`.

    Re-issuing STABILIZE and BROADCAST_MAYDAY 25 times a second would make
    the action stream useless. The frozen policy issues each condition's
    actions exactly once; the overlay matches that.
    """
    supervised = SupervisedFailsafe()
    dwell = FailsafeConfig().dwell_up
    supervised.update(_Tick(20.0, {"mag": True}))
    supervised.update(_Tick(21.0, {"mag": False}))
    first = supervised.update(_Tick(21.0 + dwell, {"mag": False}))
    again = supervised.update(_Tick(21.0 + dwell * 3, {"mag": False}))
    assert first, "the condition should have issued its actions"
    assert again == [], "actions were re-issued while the condition held"


def test_explain_reports_both_levels_and_which_is_effective():
    """The overlay must be auditable: a reader has to be able to see what
    the FROZEN core said and what the overlay added."""
    supervised = SupervisedFailsafe()
    dwell = FailsafeConfig().dwell_up
    supervised.update(_Tick(20.0, {"battery": True}))
    supervised.update(_Tick(21.0, {"battery": False}))
    supervised.update(_Tick(21.0 + dwell, {"battery": False}))
    doc = supervised.explain()
    assert doc["frozen_level_name"] == "NORMAL"
    assert doc["supervisor_level_name"] == "CRITICAL"
    assert doc["effective_level_name"] == "CRITICAL"
    assert "data_loss_battery" in doc["data_loss_conditions"]
    assert doc["data_loss_conditions"]["data_loss_battery"]["provenance"] \
        == ANCHORED


def test_a_vehicle_whose_only_fresh_nodes_are_the_two_imus():
    """SURVIVOR KILL: `{"imu0","imu1"} <= self.ever_fresh`.

    Subset versus PROPER subset is invisible on a full airframe, where
    `ever_fresh` holds all eight nodes and both comparisons are true. They
    differ only when `ever_fresh` is EXACTLY the two IMUs -- a rig with no
    other sensor delivering. There, `<=` is true and `<` is false, so a
    proper-subset mutant would silently stop recognising the
    attitude-reference case on precisely the vehicle that has nothing else
    to fall back on.
    """
    supervisor = DataLossSupervisor()
    dwell = FailsafeConfig().dwell_up
    supervisor.update(_Tick(20.0, {"imu0": True, "imu1": True}))
    assert supervisor.ever_fresh == {"imu0", "imu1"}, (
        "this test needs ever_fresh to be exactly the two IMUs")
    supervisor.update(_Tick(21.0, {"imu0": False, "imu1": False}))
    supervisor.update(_Tick(21.0 + dwell,
                            {"imu0": False, "imu1": False}))
    assert "data_loss_attitude_reference" in supervisor.conditions
    assert supervisor.level == FailsafeLevel.EMERGENCY
