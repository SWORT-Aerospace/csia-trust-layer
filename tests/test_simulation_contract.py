"""Trial-validity contract: an unproven intervention is not a negative result.

The property these tests protect is the one that cost us a whole campaign:
a scenario whose physical effect was never demonstrated must not be scored as
a detector failure.
"""

import pytest

from csia.simulation.contract import (NullControl, Stage, TrialContract,
                                      TrialNotValid, TrialVerdict)
from csia.simulation.profiles import PROFILES, get_profile


def full_chain(tc):
    for s in Stage:
        tc.record(s, True, measured=1.0, expected=1.0)
    return tc


def new(name="gnss_spoof"):
    return TrialContract(scenario=name, platform="ardupilot",
                         autopilot_version="4.8.0-dev@01a504b",
                         profile="FIELD_DERIVED_NOISE")


# --------------------------------------------------------------------------
# The chain

def test_complete_chain_is_valid():
    tc = full_chain(new())
    assert tc.trial_valid
    assert tc.verdict is TrialVerdict.VALID
    assert tc.first_break is None


def test_missing_stage_is_invalid_scenario_not_a_failure():
    """The distinction the whole module exists for."""
    tc = new()
    tc.record(Stage.COMMAND_ISSUED, True, measured=0.00045)
    tc.record(Stage.SIMULATOR_STATE_CHANGED, False, measured=0.0,
              expected=0.00045, detail="SIMSTATE never moved")
    assert not tc.trial_valid
    assert tc.verdict is TrialVerdict.INVALID_SCENARIO
    assert tc.verdict is not TrialVerdict.VALID
    assert "FAIL" not in tc.verdict.value


def test_first_break_names_where_the_chain_broke():
    tc = new()
    tc.record(Stage.COMMAND_ISSUED, True)
    tc.record(Stage.SIMULATOR_STATE_CHANGED, True)
    tc.record(Stage.SENSOR_OUTPUT_CHANGED, False)
    assert tc.first_break is Stage.SENSOR_OUTPUT_CHANGED


def test_command_issued_alone_does_not_make_a_trial():
    """COMMAND ISSUED != FAULT INJECTED."""
    tc = new()
    tc.record(Stage.COMMAND_ISSUED, True, measured="PARAM_VALUE echoed")
    assert not tc.trial_valid


def test_metrics_cannot_be_computed_from_an_invalid_trial():
    tc = new()
    tc.record(Stage.COMMAND_ISSUED, True)
    with pytest.raises(TrialNotValid):
        tc.require_valid()


def test_valid_trial_permits_scoring():
    full_chain(new()).require_valid()          # must not raise


# --------------------------------------------------------------------------
# RULE A: null controls

def test_null_control_that_moves_kills_the_trial():
    """A moving null control means the instrument is broken, not the system."""
    tc = full_chain(new())
    tc.add_null_control(NullControl(
        name="zero_injection_arm", measured=38.89, tolerance=1.21,
        unit="m", basis="measured control noise ceiling"))
    assert tc.verdict is TrialVerdict.INSTRUMENT_DEAD
    assert not tc.trial_valid


def test_quiet_null_control_leaves_a_complete_trial_valid():
    tc = full_chain(new())
    tc.add_null_control(NullControl(name="zero_injection_arm", measured=0.4,
                                    tolerance=1.21, unit="m"))
    assert tc.trial_valid


def test_instrument_dead_outranks_a_complete_chain():
    """Even a perfect chain proves nothing if the instrument reads noise."""
    tc = full_chain(new())
    tc.add_null_control(NullControl(name="control", measured=99.0,
                                    tolerance=0.1))
    assert tc.verdict is TrialVerdict.INSTRUMENT_DEAD


def test_unmeasured_null_control_is_not_silently_quiet():
    nc = NullControl(name="control", tolerance=1.0)
    assert nc.quiet is None
    tc = full_chain(new())
    tc.add_null_control(nc)
    # Unmeasured is not a moving control, so the trial is not killed -- but
    # `quiet is None` is visible in the record rather than reading as a pass.
    assert tc.trial_valid
    assert tc.to_dict()["null_controls"][0]["quiet"] is None


# --------------------------------------------------------------------------
# RULE B: mechanism intermediates

def test_mechanism_intermediate_is_recorded_with_its_source():
    tc = full_chain(new())
    tc.record_intermediate("heading_course_consistency", 0.12,
                           unit="dimensionless",
                           source="TrustState.edges[heading_course]")
    d = tc.to_dict()["mechanism_intermediates"]["heading_course_consistency"]
    assert d["value"] == 0.12
    assert d["source"]


# --------------------------------------------------------------------------
# Serialization

def test_serialized_record_carries_everything_a_reviewer_needs():
    tc = full_chain(new())
    tc.parameters = {"SIM_GPS1_GLITCH_X": 0.00045}
    d = tc.to_dict()
    for key in ("TRIAL_VALID", "verdict", "first_break", "stages",
                "null_controls", "mechanism_intermediates", "parameters",
                "autopilot_version", "profile"):
        assert key in d
    assert d["TRIAL_VALID"] is True
    assert len(d["stages"]) == len(list(Stage))


def test_every_stage_records_a_measured_value():
    """A boolean without a number is an assertion, not evidence."""
    tc = full_chain(new())
    for stage in tc.to_dict()["stages"].values():
        assert stage["measured"] is not None


def test_summary_is_readable():
    tc = full_chain(new())
    tc.add_null_control(NullControl(name="clean", measured=0.0,
                                    tolerance=1.0))
    line = tc.summary()
    assert "YYYYYY" in line and "VALID" in line and "quiet" in line


# --------------------------------------------------------------------------
# S4 profiles

def test_every_profile_declares_whether_it_is_representative():
    for p in PROFILES.values():
        assert p.representative is False, (
            f"{p.name} claims to be representative; 26 logs are not a fleet")
        assert p.basis


def test_field_profile_refuses_fault_conditioned_quantities():
    p = get_profile("FIELD_DERIVED_NOISE")
    joined = " ".join(p.not_estimable).lower()
    assert "false-alarm" in joined
    assert "recall" in joined
    assert p.estimable_from_unlabelled


def test_unknown_profile_is_rejected():
    with pytest.raises(KeyError):
        get_profile("OPTIMISTIC")
