"""Tests for the stress layer, and the findings it produced.

TWO KINDS OF TEST LIVE HERE
---------------------------
1. Tests of the INSTRUMENT: does the applicability matrix actually refuse
   inert faults, is recovery measured from the right instant, does a
   too-short run get reported as such rather than as a failure to recover.
   These can fail because I wrote something wrong.

2. CHARACTERIZATION tests, which pin measured behaviour of the FROZEN core
   -- notably SR-001, the dropout supervision asymmetry. These do not
   assert that the behaviour is correct. They assert that it is what it is
   today, so that the day it changes, somebody sees it. `failsafe.py` is
   frozen and is NOT modified by any of this.

The instrument's own defects, both found by running it and both fixed:
  * recovery was measured from the first return to NORMAL after the first
    ESCALATION, which reported 0.0 s for an intermittent GNSS profile that
    was still being faulted 19 s later;
  * a profile whose faults cleared 5 s before the flight ended was reported
    NOT_RECOVERED when a recovery could not have been observed at all.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import (FailsafeConfig,          # noqa: E402
                                   FailsafeLevel, FailsafePolicy)
from csia.runtime.online import OnlineTrustLayer            # noqa: E402
from csia.sensors.faults import KNOWN_KINDS, Fault          # noqa: E402
from csia_stress import (RECOVERED, StressProfile,          # noqa: E402
                         VacuousFault, by_id, catalog, matrix, run_profile)
from csia_stress.observables import (NAMEABLE_SOURCES,      # noqa: E402
                                     WINDOW_TOO_SHORT)
from csia_stress.profiles import UNMODELLED                 # noqa: E402
from csia_stress.source import StressFlightSource           # noqa: E402


@pytest.fixture(scope="module")
def mtx():
    return matrix()


# ---------------------------------------------------------------------------
# the applicability matrix -- the guard against vacuous stress
# ---------------------------------------------------------------------------

def test_most_fault_combinations_are_inert(mtx):
    """THE REASON THIS PACKAGE VALIDATES PAIRS AT ALL.

    The frozen core accepts any (KNOWN_KIND, known sensor) combination.
    Most of them do nothing, so composing faults without checking would
    produce stress profiles that stress nothing and report clean.
    """
    total = len(KNOWN_KINDS) * 8
    assert len(mtx.pairs) == total == 48
    assert len(mtx.live_pairs()) == 18
    assert len(mtx.inert_pairs()) == 30


def test_matrix_agrees_with_the_sensor_sources(mtx):
    """Derived by injection, cross-checked against what each model handles.

    If these ever disagree, the injection probe is right and this list is
    stale -- the probe measures, the list is a transcription.

    Note the ABSENCE of ("dropout", "vibration"): it perturbs the sampled
    stream but is flattened in transport, so it is not live. See
    test_dropout_on_vibration_is_lost_in_transport.
    """
    expected = {
        ("gps_spoof", "gps"), ("dropout", "gps"),
        ("bias_drift", "imu0"), ("emi_spike", "imu0"), ("dropout", "imu0"),
        ("bias_drift", "imu1"), ("emi_spike", "imu1"), ("dropout", "imu1"),
        ("bias_drift", "mag"), ("emi_spike", "mag"), ("dropout", "mag"),
        ("bias_drift", "baro"), ("dropout", "baro"),
        ("power_sag", "battery"), ("dropout", "battery"),
        ("power_sag", "motor_esc"), ("dropout", "motor_esc"),
        ("vibration_anomaly", "vibration"),
    }
    assert set(mtx.live_pairs()) == expected


def test_a_fault_never_perturbs_another_sensor(mtx):
    """No cross-talk: each injected fault moves only its own target, so a
    multi-fault profile's channels stay independently attributable."""
    assert [p for p, r in mtx.pairs.items() if r.cross_talk] == []


def test_inert_pair_is_accepted_by_the_frozen_core_but_changes_nothing(mtx):
    """The trap this module exists to close, demonstrated end to end."""
    from csia.scenarios import sample_streams
    from csia.sensors import generate_flight

    # The frozen guards accept it: the kind is known and the target exists.
    fault = Fault("gps_spoof", "mag", 20.0, 10.0, {"drift": (3.0, 1.0, 0.0)})
    truth = generate_flight(duration=30.0, dt=0.01)
    base = sample_streams(truth, ())
    with_fault = sample_streams(truth, (fault,))

    import numpy as np
    for channel, values in base["mag"].items():
        assert np.array_equal(np.asarray(values),
                              np.asarray(with_fault["mag"][channel])), \
            "an inert fault must be exactly that -- inert"
    assert not mtx.is_live("gps_spoof", "mag")


def test_profile_with_an_inert_fault_is_refused(mtx):
    """Refused at construction, so it can never reach a result artifact."""
    profile = StressProfile(
        id="bogus", summary="inert",
        faults=(Fault("vibration_anomaly", "gps", 20.0, 10.0, {"gain": 3.0}),))
    with pytest.raises(VacuousFault, match="INERT"):
        profile.validate(mtx)


def test_the_refusal_names_what_the_sensor_would_respond_to(mtx):
    with pytest.raises(VacuousFault, match="responds to"):
        mtx.require_live("power_sag", "imu0", where="test")


# ---------------------------------------------------------------------------
# profile construction
# ---------------------------------------------------------------------------

def test_every_catalog_profile_validates():
    """Nothing shipped is vacuous."""
    profiles = catalog()
    assert len(profiles) >= 10
    for p in profiles:
        p.validate()


def test_catalog_profiles_are_multi_fault_or_declared_single():
    for p in catalog():
        assert p.faults, p.id


def test_profile_refuses_an_unobservable_recovery_window():
    """A run that ends within the de-escalation dwell of the last fault
    cannot answer its own recovery question, so it is refused rather than
    silently reporting NOT_RECOVERED."""
    with pytest.raises(ValueError, match="could not be observed"):
        StressProfile(
            id="too_short", summary="x",
            faults=(Fault("dropout", "gps", 20.0, 35.0),),
            duration=60.0)          # clears at 55 s, 5 s left, dwell is 5 s


def test_profile_refuses_an_invented_flight_profile():
    with pytest.raises(ValueError, match="does not invent"):
        StressProfile(id="x", summary="x",
                      faults=(Fault("dropout", "gps", 20.0, 10.0),),
                      flight_profile="aggressive_high_throttle_maneuver")


def test_unmodelled_phenomena_are_declared_not_faked():
    """RF jamming, multipath, flutter and high-throttle maneuvering have no
    primitive in the frozen sensor model. They are recorded as gaps with a
    reason, and no profile claims to be them."""
    ids = {u.id for u in UNMODELLED}
    assert {"rf_jamming_as_rf", "urban_canyon_multipath",
            "control_surface_flutter", "high_throttle_maneuvering"} <= ids
    for u in UNMODELLED:
        assert u.why_not and u.nearest_available
        assert u.why_the_nearest_is_not_it, (
            f"{u.id}: naming a nearest substitute without saying why it is "
            f"not the thing is how a substitute quietly becomes the claim")
    for p in catalog():
        assert "multipath" not in p.id
        assert "flutter" not in p.id
        assert "jam" not in p.id


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------

def test_intermittent_profile_measures_recovery_after_the_LAST_fault():
    """REGRESSION on a defect in this instrument.

    Measuring from the first return to NORMAL after the first escalation
    reported 0.0 s for this profile: it recovers between denial cycles
    while still being faulted for another 19 s. Recovery is only meaningful
    once there is nothing left to recover from.
    """
    run = run_profile(by_id("env_gnss_denied_intermittent"))
    assert run.recovery_status == RECOVERED
    assert run.recovery_time_s > 0.0, \
        "recovery measured from before the faults finished"


def test_recovery_includes_the_policy_dwell_and_says_so():
    run = run_profile(by_id("env_gnss_denied"))
    assert run.dwell_down_s == FailsafeConfig().dwell_down
    assert run.recovery_time_s >= 0.0
    doc = run.to_dict()["recovery"]
    assert doc["includes_policy_dwell_down_s"] == run.dwell_down_s


def test_window_too_short_is_not_reported_as_a_failure_to_recover():
    """A too-short observation window is a fact about the PROFILE. Calling
    it NOT_RECOVERED would report my profile length as the system's
    behaviour -- which is exactly what an early version of this did."""
    from csia_stress import observables
    assert WINDOW_TOO_SHORT != observables.NOT_RECOVERED
    assert "TOO_SHORT" in WINDOW_TOO_SHORT


def test_every_catalog_profile_is_detected_and_recovers():
    """The measured state of the catalog. A NOT_DETECTED profile would be a
    finding, not a failure of this test -- if this starts failing, read the
    run before changing the assertion."""
    for p in catalog():
        run = run_profile(p)
        assert run.escalated, f"{p.id} injected live faults and never tripped"
        assert run.recovery_status == RECOVERED, \
            f"{p.id}: {run.recovery_status}"


def test_the_requested_msrd_case_runs_and_is_detected():
    """GPS spoof concurrent with magnetometer drift, on the fast profile."""
    run = run_profile(by_id("msrd_gps_spoof_mag_drift_fast"))
    assert run.escalated
    assert run.peak_level >= int(FailsafeLevel.CAUTION)
    assert set(run.attribution["injected_targets"]) == {"gps", "mag"}


# ---------------------------------------------------------------------------
# attribution
# ---------------------------------------------------------------------------

def test_two_sensors_cannot_be_named_by_the_cause_vocabulary():
    """`baro` and `motor_esc` have no cause label pointing at them, so a
    fault on either is structurally unnameable however clearly it is seen.
    Read from the frozen map, so this tracks the core rather than a copy."""
    assert "baro" not in NAMEABLE_SOURCES
    assert "motor_esc" not in NAMEABLE_SOURCES
    assert {"gps", "imu0", "imu1", "mag", "battery",
            "vibration"} <= NAMEABLE_SOURCES


def test_concurrent_faults_are_not_all_separately_accused():
    """MEASURED, not asserted as desirable: under a GPS spoof concurrent
    with a magnetometer drift, the top-1 cause is the GPS for most of the
    window and the magnetometer is never named."""
    run = run_profile(by_id("msrd_gps_spoof_mag_drift_fast"))
    attr = run.attribution
    assert "gps" in attr["targets_named"]
    assert "mag" in attr["targets_nameable_but_never_named"]


# ---------------------------------------------------------------------------
# SR-001 CHARACTERIZATION. Frozen behaviour, pinned so a change is visible.
# ---------------------------------------------------------------------------

def _peak_level(faults, duration=90.0):
    source = StressFlightSource(faults=faults, duration=duration)
    layer, policy = OnlineTrustLayer(), FailsafePolicy()
    states, last_t = [], 0.0
    for sensor, t, channels in source.samples():
        states.extend(layer.ingest(sensor, t, channels))
        last_t = t
    states.extend(layer.flush(last_t))
    peak, fresh_mid = FailsafeLevel.NORMAL, {}
    for state in states:
        policy.update(state)
        peak = max(peak, policy.level)
        if 29.9 <= state.t <= 30.2 and not fresh_mid:
            fresh_mid = {k: bool(v) for k, v in state.fresh.items()}
    return peak, fresh_mid


def test_sr001_gps_is_the_only_sensor_with_a_loss_of_data_rule():
    """SR-001, half one: GPS going invalid DOES escalate."""
    peak, fresh = _peak_level((Fault("dropout", "gps", 20.0, 40.0),))
    assert fresh["gps"] is False
    assert peak >= FailsafeLevel.CAUTION


def test_sr001_losing_both_imus_to_dropout_does_not_escalate():
    """SR-001, half two: THE FINDING.

    Both IMUs stop delivering valid data for 40 s. Freshness detection
    works -- both are correctly marked not fresh -- but every attitude rule
    reasons only over FRESH IMUs, and `att` falls back to
    `max(..., default=1.0)`, i.e. full confidence, when neither is fresh.
    So total loss of the attitude reference raises nothing.

    THIS TEST DOES NOT SAY THAT IS CORRECT. `failsafe.py` is frozen and is
    not modified here. The test pins the behaviour so that if it ever
    changes, the change is visible and deliberate. See SR-001 in
    research/physical_validation/FAILURE_LEDGER.yaml.
    """
    peak, fresh = _peak_level((Fault("dropout", "imu0", 20.0, 40.0),
                               Fault("dropout", "imu1", 20.0, 40.0)))
    assert fresh["imu0"] is False and fresh["imu1"] is False, \
        "freshness detection itself is expected to work"
    assert peak == FailsafeLevel.NORMAL, (
        "SR-001 has changed: losing both IMUs now escalates. That is "
        "probably an improvement -- update this test and the ledger entry "
        "deliberately rather than deleting the assertion.")


@pytest.mark.parametrize("targets", [("battery", "baro"),
                                     ("mag", "baro"),
                                     ("battery", "motor_esc")])
def test_sr001_non_gps_dropouts_do_not_escalate(targets):
    """The asymmetry is general, not specific to the IMUs."""
    faults = tuple(Fault("dropout", t, 20.0, 40.0) for t in targets)
    peak, fresh = _peak_level(faults)
    assert all(fresh[t] is False for t in targets)
    assert peak == FailsafeLevel.NORMAL


def test_sr001_is_about_freshness_gating_not_broken_detection():
    """The control that keeps SR-001 honest: the same sensors DO escalate
    when they deliver BAD data instead of no data. The gap is specifically
    in acting on absence, not in detecting degradation."""
    peak, _ = _peak_level((Fault("vibration_anomaly", "vibration",
                                 20.0, 25.0, {"gain": 3.0}),))
    assert peak >= FailsafeLevel.CRITICAL


def test_dropout_on_vibration_is_lost_in_transport(mtx):
    """A DEFECT IN THE TEST RIG, found by a failing test in this file.

    `dropout` on the vibration node genuinely perturbs the sampled stream:
    every sample in the window is marked invalid. It then reaches the
    online layer as nothing, because `SimulatedFlightSource.samples()`
    emits the 10 Hz RMS envelope with a hardcoded ``valid=True`` and
    discards the flag.

    So the pair is stream-live and transport-inert, and any stress profile
    using it would inject a fault the layer cannot see. It is excluded from
    `live_pairs()` for that reason and REPORTED rather than quietly
    dropped, because "this rig cannot deliver that fault" is something a
    reader of a stress result needs to know.

    This is a property of `csia/runtime/plugins.py`, which is NOT frozen.
    It is recorded, not fixed: changing how the simulator delivers the
    vibration channel would alter an evidence-producing path that existing
    tests and golden corpora depend on, and that is a deliberate decision
    for a human, not a side effect of adding a stress harness.
    """
    result = mtx.pairs[("dropout", "vibration")]
    assert result.effect == "APPLIED", "it does perturb the sampled stream"
    assert result.transport == "IGNORED", "and reaches the layer as nothing"
    assert result.lost_in_transport
    assert not result.live
    assert ("dropout", "vibration") in mtx.lost_in_transport()
    # It must not silently vanish from the report.
    assert ["dropout", "vibration"] in mtx.summary()["lost_in_transport"]


def test_only_that_one_pair_is_lost_in_transport(mtx):
    """Every other live-in-stream pair survives to the layer. If this grows,
    a new delivery gap has appeared and stress results built before it are
    weaker than they looked."""
    assert mtx.lost_in_transport() == (("dropout", "vibration"),)
