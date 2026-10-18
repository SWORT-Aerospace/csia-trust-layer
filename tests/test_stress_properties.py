"""Property-based tests for the stress layer.

The stress layer had example tests and no property tests. Its job is to
produce stimuli that are REAL -- a campaign that quietly generates faults
nothing acts on reports a tidy pass over an empty experiment, which is the
single worst outcome available to a test rig. The applicability matrix exists
to stop that, and these properties hold it to its own rule over generated
inputs rather than chosen ones.

    EVERY GENERATED PROFILE PERTURBS SOMETHING.
    AN INERT STIMULUS IS REFUSED, NOT SILENTLY RUN.
    THE SAME SEED GIVES THE SAME CAMPAIGN, EXACTLY.

The last one is load-bearing for the regression gate: `stress_regression.py`
compares detection latency, recovery and escalation with NO tolerance band,
which is only defensible if the campaign is bit-for-bit reproducible.
"""

from __future__ import annotations

import os
import random
import sys

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeConfig                 # noqa: E402
from csia.sensors.faults import KNOWN_KINDS, Fault               # noqa: E402
from csia_stress.applicability import VacuousFault, matrix       # noqa: E402
from csia_stress.campaign import (FLIGHT_DURATION,               # noqa: E402
                                  RANDOM_PARAMS, random_profile)
from csia_stress.profiles import StressProfile                   # noqa: E402

SETTINGS = settings(max_examples=120, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow])

MATRIX = matrix()
LIVE = MATRIX.live_pairs()
INERT = MATRIX.inert_pairs()

seeds = st.integers(min_value=0, max_value=2 ** 31 - 1)
indices = st.integers(min_value=0, max_value=99999)


# ---------------------------------------------------------------------------
# generated profiles are real experiments
# ---------------------------------------------------------------------------

@SETTINGS
@given(seed=seeds, index=indices)
def test_every_generated_profile_uses_only_live_pairs(seed, index):
    """THE POINT OF THE WHOLE APPLICABILITY LAYER. A campaign that generates
    an inert fault runs a flight, measures nothing, and reports a result."""
    profile = random_profile(random.Random(seed), index)
    for fault in profile.faults:
        assert MATRIX.is_live(fault.kind, fault.target), (
            f"{fault.kind}@{fault.target} is inert and was generated anyway")


@SETTINGS
@given(seed=seeds, index=indices)
def test_every_generated_profile_is_multi_fault(seed, index):
    """This campaign is MSRD -- simultaneous multi-sensor degradation. A
    single-fault variation would be a different experiment reported under
    the same name."""
    profile = random_profile(random.Random(seed), index)
    assert 2 <= len(profile.faults) <= 4


@SETTINGS
@given(seed=seeds, index=indices)
def test_generated_faults_hit_distinct_sensors(seed, index):
    """Stacking two faults on one sensor is a different thing from
    degrading several, and the campaign claims the latter."""
    profile = random_profile(random.Random(seed), index)
    targets = [f.target for f in profile.faults]
    assert len(targets) == len(set(targets))


@SETTINGS
@given(seed=seeds, index=indices)
def test_every_profile_leaves_room_to_observe_its_own_recovery(seed, index):
    """A run that ends less than `dwell_down` after the last fault clears
    cannot show a recovery whether or not one occurred, so its recovery
    result would be an artifact of the window."""
    dwell = FailsafeConfig().dwell_down
    profile = random_profile(random.Random(seed), index)
    clear = max(f.start + f.duration for f in profile.faults)
    assert profile.duration - clear > dwell, (
        f"only {profile.duration - clear:.2f}s after the last fault clears, "
        f"against a {dwell}s de-escalation dwell")


@SETTINGS
@given(seed=seeds, index=indices)
def test_every_fault_starts_after_the_failsafe_arms(seed, index):
    """Before `arm_time` the policy does not act at all, so a fault injected
    there measures the arming rule rather than the detector."""
    profile = random_profile(random.Random(seed), index)
    for fault in profile.faults:
        assert fault.start >= FailsafeConfig().arm_time


@SETTINGS
@given(seed=seeds, index=indices)
def test_generated_parameters_stay_inside_their_declared_ranges(seed, index):
    """RANDOM_PARAMS declares its ranges before any run. A parameter drawn
    outside them would make the published campaign describe a different
    experiment from the one documented."""
    profile = random_profile(random.Random(seed), index)
    for fault in profile.faults:
        assert fault.kind in RANDOM_PARAMS
        if fault.kind == "bias_drift":
            assert 0.03 <= fault.params["rate"] <= 0.20
            assert fault.params["axis"] in (0, 1, 2)
        elif fault.kind == "emi_spike":
            assert 4.0 <= fault.params["amplitude"] <= 18.0
            assert 5.0 <= fault.params["rate_hz"] <= 20.0
        elif fault.kind == "vibration_anomaly":
            assert 1.8 <= fault.params["gain"] <= 4.5
        elif fault.kind == "power_sag":
            assert 0.6 <= fault.params["depth_v"] <= 2.0
            assert 150.0 <= fault.params["rpm_loss"] <= 700.0


# ---------------------------------------------------------------------------
# determinism, which the zero-tolerance regression gate rests on
# ---------------------------------------------------------------------------

@SETTINGS
@given(seed=seeds, index=indices)
def test_the_same_seed_gives_a_byte_identical_profile(seed, index):
    """`stress_regression.py` compares latency, recovery, escalation and
    attribution EXACTLY, with no tolerance band. That is only defensible if
    the generator is reproducible."""
    a = random_profile(random.Random(seed), index)
    b = random_profile(random.Random(seed), index)
    assert a.id == b.id and a.flight_profile == b.flight_profile
    assert [(f.kind, f.target, f.start, f.duration, f.params)
            for f in a.faults] == \
           [(f.kind, f.target, f.start, f.duration, f.params)
            for f in b.faults]


@SETTINGS
@given(seed=seeds, i=indices, j=indices)
def test_the_index_only_changes_the_label(seed, i, j):
    """The index names the variation; it must not secretly steer the draw,
    or two campaigns of different length would not be comparable."""
    a = random_profile(random.Random(seed), i)
    b = random_profile(random.Random(seed), j)
    assert a.id != b.id or i == j
    assert [(f.kind, f.target) for f in a.faults] == \
           [(f.kind, f.target) for f in b.faults]


# ---------------------------------------------------------------------------
# an inert stimulus is refused
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not INERT, reason="no inert pairs in the matrix")
@given(pair=st.sampled_from(INERT if INERT else [("bias_drift", "gps")]))
@SETTINGS
def test_an_inert_pair_is_refused_at_construction(pair):
    """LOUDLY, at profile construction -- not filtered out later. A fault
    that reaches a result artifact and did nothing is indistinguishable
    from one that did nothing because the system is robust."""
    kind, target = pair
    with pytest.raises(VacuousFault):
        MATRIX.require_live(kind, target, where="property test")


@pytest.mark.skipif(not INERT, reason="no inert pairs in the matrix")
def test_the_refusal_names_what_the_target_does_respond_to():
    """An error that says only 'no' costs the reader a search."""
    kind, target = INERT[0]
    with pytest.raises(VacuousFault) as excinfo:
        MATRIX.require_live(kind, target)
    message = str(excinfo.value)
    assert "INERT" in message
    assert repr(target) in message
    assert "responds to" in message


@SETTINGS
@given(kind=st.sampled_from(sorted(KNOWN_KINDS)),
       target=st.sampled_from(["imu0", "imu1", "baro", "mag", "gps",
                               "battery", "motor_esc", "vibration"]))
def test_live_and_inert_are_a_partition(kind, target):
    """Every probed pair is exactly one of the two. A pair in neither would
    be silently unclassified and could be generated without check."""
    pair = (kind, target)
    if pair not in MATRIX.pairs:
        return
    assert MATRIX.is_live(*pair) != (pair in INERT)


def test_the_matrix_reports_what_it_could_not_deliver():
    """Pairs that perturb the stream and arrive as nothing are REPORTED,
    not quietly dropped -- a fault the rig cannot deliver is a limit of the
    rig that a reader of any stress result needs."""
    lost = MATRIX.lost_in_transport()
    assert isinstance(lost, tuple)
    for pair in lost:
        assert pair not in LIVE, (
            "a pair lost in transport must not also count as live")


# ---------------------------------------------------------------------------
# profile validation
# ---------------------------------------------------------------------------

@SETTINGS
@given(start=st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
       duration=st.floats(min_value=0.1, max_value=40.0, allow_nan=False))
def test_a_profile_with_no_room_to_recover_is_refused_at_construction(
        start, duration):
    """The stimulus is never shortened to fit the window; a profile that
    cannot answer its own recovery question must be REFUSED.

    Two things about this test were wrong when first written, and the
    property found both: the rule is not "the faults fit inside the flight"
    but "more than `dwell_down` remains after they clear", and it is
    enforced in `__post_init__`, not in `validate()`. Constructing the
    profile outside the raises-block let the error escape.
    """
    kind, target = LIVE[0]
    dwell = FailsafeConfig().dwell_down
    room = FLIGHT_DURATION - (start + duration)

    def _build():
        return StressProfile(
            id="prop", summary="property", duration=FLIGHT_DURATION,
            faults=(Fault(kind, target, start, duration, {}),),
            represents="property test", does_not_represent="a scenario")

    if room <= dwell:
        with pytest.raises(ValueError):
            _build()
    else:
        _build().validate()


@SETTINGS
@given(start=st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
       duration=st.floats(min_value=0.1, max_value=40.0, allow_nan=False))
def test_the_refusal_reads_the_dwell_from_the_frozen_config(start, duration):
    """The boundary is `FailsafeConfig().dwell_down` read at runtime, not a
    literal 5.0 copied into the check -- so a frozen-core change surfaces
    here instead of silently shifting what profiles are allowed."""
    kind, target = LIVE[0]
    room = FLIGHT_DURATION - (start + duration)
    if room > FailsafeConfig().dwell_down:
        return
    with pytest.raises(ValueError) as excinfo:
        StressProfile(
            id="prop", summary="property", duration=FLIGHT_DURATION,
            faults=(Fault(kind, target, start, duration, {}),),
            represents="property test", does_not_represent="a scenario")
    assert str(FailsafeConfig().dwell_down) in str(excinfo.value)
