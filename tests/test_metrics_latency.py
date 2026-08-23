"""Latency metric semantics (audit finding F-02).

The regression these prevent: publishing a trust-threshold crossing as if it
were an operator-facing alert. Every case below distinguishes the stage that
CSIA actually reached from the stage that was previously reported.
"""

from dataclasses import dataclass, field

import pytest

from csia.metrics import (LEGACY_ANALYSIS_THRESHOLD, FaultWindow, OnsetBasis,
                          associate_episode, measure, production_threshold,
                          time_to_arbitration, time_to_classification,
                          time_to_correct_isolation, time_to_trust_threshold,
                          time_to_trusted_reentry, unassociated_episodes)
from csia.runtime.failsafe import FailsafeLevel, Transition

N, C, X = FailsafeLevel.NORMAL, FailsafeLevel.CAUTION, FailsafeLevel.CRITICAL


# --- lightweight doubles ------------------------------------------------------

@dataclass
class FakeState:
    t: float
    trust: dict
    posterior: dict = field(default_factory=lambda: {"nominal": 1.0})


@dataclass
class FakeSummary:
    states: list = field(default_factory=list)
    transitions: list = field(default_factory=list)
    actions: list = field(default_factory=list)


def states(trust_by_t, posterior_by_t=None):
    posterior_by_t = posterior_by_t or {}
    return [FakeState(t, tr, posterior_by_t.get(t, {"nominal": 1.0}))
            for t, tr in sorted(trust_by_t.items())]


def tr(t, level, previous, *reasons):
    return Transition(t=t, level=level, previous=previous,
                      reasons=list(reasons), actions=[])


GPS = FaultWindow(target="gps", kind="gps_spoof", start=20.0, duration=15.0)


# --- 1. abrupt fault: threshold crossed early, alert delayed by dwell --------

def test_dwell_delays_alert_after_threshold_crossing():
    s = FakeSummary(
        states=states({20.0: {"gps": 0.95}, 21.0: {"gps": 0.80},
                       25.0: {"gps": 0.60}}),
        transitions=[tr(23.0, C, N, "GPS trust 0.71")],
        actions=[(23.0, "SWITCH_NAV_INERTIAL")])
    r = measure(s, GPS)
    assert r.time_to_trust_threshold_s == 1.0     # trust < 0.85 at t=21
    assert r.time_to_alert_event_s == 3.0         # operator alert at t=23
    assert r.time_to_alert_event_s > r.time_to_trust_threshold_s
    assert r.alert_state == "CAUTION"


# --- 2. gradual fault crosses analysis threshold before production threshold -

def test_analysis_threshold_precedes_production_threshold():
    """0.85 is crossed while the gps production threshold (0.75) is not."""
    assert production_threshold("gps") == 0.75
    st = states({20.0: {"gps": 0.9}, 22.0: {"gps": 0.80}, 30.0: {"gps": 0.78}})
    assert time_to_trust_threshold(st, "gps", 20.0, 0.85) == 2.0
    assert time_to_trust_threshold(st, "gps", 20.0, 0.75) is None
    r = measure(FakeSummary(states=st), GPS)
    assert r.time_to_alert_event_s is None and r.outcome == "MISSED"
    assert any("analysis-only" in n for n in r.notes)


# --- 3. alert suppressed during arm time -------------------------------------

def test_alert_before_arm_time_is_not_attributed():
    """A fault inside arm_time raises no alert; latency must be None, not 0."""
    early = FaultWindow("gps", "gps_spoof", start=2.0, duration=5.0)
    r = measure(FakeSummary(states=states({2.0: {"gps": 0.5}}),
                            transitions=[]), early)
    assert r.time_to_alert_event_s is None
    assert r.time_to_trust_threshold_s == 0.0


# --- 4. fault never producing an alert ---------------------------------------

def test_undetected_fault_is_missed_not_zero():
    r = measure(FakeSummary(states=states({25.0: {"gps": 0.99}})), GPS)
    assert r.time_to_alert_event_s is None
    assert r.time_to_trust_threshold_s is None
    assert r.outcome == "MISSED"


# --- 5/6. isolation outcomes --------------------------------------------------

def test_incorrect_isolation_is_reported_as_such():
    st = states({22.0: {"gps": 0.5}},
                {22.0: {"nominal": 0.02, "mag_interference": 0.95}})
    lat, outcome, accused = time_to_correct_isolation(st, "gps", 20.0, 0.90)
    assert lat is None and outcome == "INCORRECT" and accused == "mag"


def test_correct_isolation_after_alert():
    st = states({22.0: {"gps": 0.5}}, {22.0: {"nominal": 0.02, "gps_fault": 0.95}})
    lat, outcome, accused = time_to_correct_isolation(st, "gps", 20.0, 0.90)
    assert (lat, outcome, accused) == (2.0, "CORRECT", "gps")


def test_ambiguous_isolation_when_cause_names_no_source():
    st = states({22.0: {"gps": 0.5}},
                {22.0: {"nominal": 0.02, "unexpected_maneuver": 0.95}})
    _, outcome, _ = time_to_correct_isolation(st, "gps", 20.0, 0.90)
    assert outcome == "AMBIGUOUS"


def test_no_isolation_when_confidence_never_reached():
    st = states({22.0: {"gps": 0.5}}, {22.0: {"nominal": 0.4, "gps_fault": 0.6}})
    lat, outcome, _ = time_to_correct_isolation(st, "gps", 20.0, 0.90)
    assert lat is None and outcome == "NONE"


def test_isolation_threshold_is_reported_with_the_result():
    r = measure(FakeSummary(states=states({22.0: {"gps": 0.5}})), GPS,
                isolation_conf=0.75)
    assert r.isolation_confidence_threshold == 0.75
    assert r.classification_confidence_threshold == 0.90


# --- 7. multiple escalations inside one episode ------------------------------

def test_escalations_within_episode_use_first_alert_time():
    s = FakeSummary(
        states=states({22.0: {"gps": 0.5}}),
        transitions=[tr(23.0, C, N, "gps"), tr(27.0, X, C, "power"),
                     tr(40.0, N, X)])
    r = measure(s, GPS)
    assert r.time_to_alert_event_s == 3.0      # first, not the CRITICAL at 27
    assert r.alert_escalations == 2
    assert r.time_to_alert_episode_s == 3.0


# --- 8. recovery is not alert latency ----------------------------------------

def test_recovery_transition_is_not_an_alert():
    s = FakeSummary(states=states({22.0: {"gps": 0.5}}),
                    transitions=[tr(23.0, C, N, "gps"), tr(40.0, N, C)])
    r = measure(s, GPS)
    assert r.time_to_alert_event_s == 3.0
    assert r.time_to_recovery_s == 5.0          # fault ends 35.0, episode 40.0


def test_recovery_none_when_episode_never_closes():
    s = FakeSummary(states=states({22.0: {"gps": 0.5}}),
                    transitions=[tr(23.0, C, N, "gps")])
    assert measure(s, GPS).time_to_recovery_s is None


def test_trusted_reentry_is_distinct_from_recovery():
    """Posture returns to NORMAL at 40 s, but gps only re-crosses 0.75 at 50 s."""
    s = FakeSummary(
        states=states({36.0: {"gps": 0.60}, 40.0: {"gps": 0.70},
                       50.0: {"gps": 0.80}}),
        transitions=[tr(23.0, C, N, "gps"), tr(40.0, N, C)])
    r = measure(s, GPS)
    assert r.time_to_recovery_s == 5.0          # 40.0 - 35.0
    assert r.time_to_trusted_reentry_s == 15.0  # 50.0 - 35.0
    assert r.time_to_trusted_reentry_s != r.time_to_recovery_s


# --- 9. fault removed before dwell completes ---------------------------------

def test_fault_removed_before_dwell_produces_no_alert():
    brief = FaultWindow("gps", "gps_spoof", start=20.0, duration=0.5)
    r = measure(FakeSummary(states=states({20.2: {"gps": 0.80}})), brief)
    assert r.time_to_alert_event_s is None
    assert r.time_to_trust_threshold_s == pytest.approx(0.2)


# --- 10. flapping ------------------------------------------------------------

def test_flapping_alerts_report_first_crossing_once():
    s = FakeSummary(
        states=states({22.0: {"gps": 0.5}}),
        transitions=[tr(23.0, C, N, "gps"), tr(26.0, N, C),
                     tr(28.0, C, N, "gps"), tr(33.0, N, C)])
    r = measure(s, GPS)
    assert r.time_to_alert_event_s == 3.0
    assert r.alert_escalations == 2             # merged into ONE episode


# --- 11. simultaneous faults --------------------------------------------------

def test_overlapping_faults_each_get_an_association():
    from csia.metrics import alert_episodes
    gps = FaultWindow("gps", "gps_spoof", 20.0, 15.0)
    mag = FaultWindow("mag", "emi_spike", 22.0, 10.0)
    eps = alert_episodes([tr(24.0, C, N, "both"), tr(45.0, N, C)])
    # one episode can legitimately be supported by two faults; report, not arbitrate
    assert associate_episode(eps, gps) is not None
    assert associate_episode(eps, mag) is not None
    assert unassociated_episodes(eps, [gps, mag]) == []


def test_association_ignores_episode_opening_before_onset():
    from csia.metrics import alert_episodes
    eps = alert_episodes([tr(5.0, C, N, "pre-existing"), tr(8.0, N, C)])
    assert associate_episode(eps, GPS) is None
    assert len(unassociated_episodes(eps, [GPS])) == 1


def test_association_respects_grace_window():
    from csia.metrics import alert_episodes
    eps = alert_episodes([tr(60.0, C, N, "late"), tr(70.0, N, C)])
    assert associate_episode(eps, GPS, grace_s=15.0) is None   # 35+15 = 50 < 60
    assert associate_episode(eps, GPS, grace_s=30.0) is not None


# --- 12. alert existing before fault onset ------------------------------------

def test_alert_before_onset_is_not_credited_to_the_fault():
    s = FakeSummary(states=states({10.0: {"gps": 0.5}}),
                    transitions=[tr(10.0, C, N, "unrelated"), tr(15.0, N, C)])
    r = measure(s, GPS)
    assert r.time_to_alert_event_s is None and r.outcome == "MISSED"


# --- 13. onset bases ----------------------------------------------------------

def test_onset_bases_are_distinct_and_never_assumed_equal():
    b = OnsetBasis(configured=20.0, first_corrupted_sample=20.04)
    assert b.resolve("configured") == (20.0, "configured")
    assert b.resolve("corrupted") == (20.04, "first_corrupted_sample")
    # observable is not implemented -> falls back, and says which basis it used
    assert b.resolve("observable")[1] == "first_corrupted_sample"


def test_missing_ground_truth_onset_falls_back_to_configured():
    b = OnsetBasis(configured=20.0)
    assert b.resolve("observable") == (20.0, "configured")
    with pytest.raises(ValueError, match="unknown onset preference"):
        b.resolve("nonsense")


def test_measure_records_which_onset_basis_was_used():
    r = measure(FakeSummary(states=states({21.0: {"gps": 0.5}})), GPS,
                onset=OnsetBasis(20.0, first_corrupted_sample=20.04),
                onset_prefer="corrupted")
    assert r.onset_basis == "first_corrupted_sample"
    assert r.onset_s == 20.04
    assert r.first_corrupted_sample_s == 20.04
    assert r.first_observable_effect_s is None


# --- 14/15. unavailable stages are None, never fabricated --------------------

def test_no_diagnosis_available_yields_none_not_zero():
    r = measure(FakeSummary(states=states({22.0: {"gps": 0.5}})), GPS)
    assert r.time_to_classification_s is None and r.classified_as is None
    assert r.isolation_outcome == "NONE"


def test_no_arbitration_recommendation_yields_none():
    r = measure(FakeSummary(states=states({22.0: {"gps": 0.5}})), GPS)
    assert r.time_to_arbitration_recommendation_s is None


def test_applied_mitigation_is_always_unavailable_with_a_reason():
    r = measure(FakeSummary(states=states({22.0: {"gps": 0.5}})), GPS)
    assert r.time_to_applied_mitigation_s is None
    assert "advisory" in r.applied_mitigation_status


def test_recovery_action_is_not_an_arbitration_recommendation():
    assert time_to_arbitration([(40.0, "RESUME_NORMAL")], 20.0) == (None, None)
    assert time_to_arbitration([(23.0, "SWITCH_NAV_INERTIAL")], 20.0) \
        == (3.0, "SWITCH_NAV_INERTIAL")


def test_missing_states_degrades_gracefully_with_a_note():
    r = measure(FakeSummary(states=[], transitions=[tr(23.0, C, N, "gps")]), GPS)
    assert r.time_to_trust_threshold_s is None
    assert any("keep_states" in n for n in r.notes)
    assert r.time_to_alert_event_s == 3.0     # transitions still usable


# --- 16. determinism ----------------------------------------------------------

def test_repeated_calculation_is_deterministic():
    s = FakeSummary(states=states({22.0: {"gps": 0.5}},
                                  {22.0: {"nominal": 0.02, "gps_fault": 0.95}}),
                    transitions=[tr(23.0, C, N, "gps"), tr(40.0, N, C)],
                    actions=[(23.0, "SWITCH_NAV_INERTIAL")])
    first = measure(s, GPS).to_dict()
    for _ in range(5):
        assert measure(s, GPS).to_dict() == first


def test_classification_names_its_threshold_in_the_result():
    r = measure(FakeSummary(states=states({22.0: {"gps": 0.5}})), GPS)
    assert r.trust_threshold == LEGACY_ANALYSIS_THRESHOLD == 0.85


# --- 17/18. integration against the real runtime ------------------------------

@pytest.mark.slow
def test_real_run_alert_is_later_than_threshold_crossing():
    """End-to-end on the shipping detector: the operator alert must lag the
    0.85 crossing, because it additionally needs the production threshold,
    dwell_up and arm_time. Pins the published-claim correction."""
    from csia.sensors import generate_flight
    from csia.validation import FAULTS, _run_one

    truth = generate_flight()
    target, mk = FAULTS["mag_emi"]
    f = mk(1.0, 20.0)
    r = measure(_run_one(truth, [f], False), f, scenario_id="mag_emi")

    assert r.time_to_trust_threshold_s == pytest.approx(1.52, abs=0.05)
    assert r.time_to_alert_event_s == pytest.approx(3.88, abs=0.05)
    assert r.time_to_alert_event_s > r.time_to_trust_threshold_s
    assert r.isolation_outcome == "CORRECT"
    assert r.outcome == "CORRECT_ALERT_AND_ISOLATION"


@pytest.mark.slow
def test_imu_bias_crosses_threshold_but_never_alerts():
    """The starkest correction: the published '13.0 s detection' for slow IMU
    bias drift corresponds to NO operator alert at all. imu1 stays healthy, so
    max(imu0, imu1) never falls under att_caution and the failsafe never fires
    — redundancy working as designed, but not a detection event."""
    from csia.sensors import generate_flight
    from csia.validation import FAULTS, _run_one

    truth = generate_flight()
    target, mk = FAULTS["imu_bias"]
    f = mk(1.0, 20.0)
    r = measure(_run_one(truth, [f], False), f, scenario_id="imu_bias")

    assert r.time_to_trust_threshold_s == pytest.approx(13.0, abs=0.2)
    assert r.time_to_alert_event_s is None
    assert r.outcome == "MISSED"
    assert r.isolation_outcome == "CORRECT"   # diagnosed correctly regardless
