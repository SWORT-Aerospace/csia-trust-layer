"""Semantic qualification: a present field is not automatically evidence.

The regression the whole S2 layer exists for is
`test_esc_sitl_stub_is_not_informative`. If that test ever starts failing
because someone marked the ESC channels admissible, a spurious CRITICAL
returns to every clean flight.
"""

import numpy as np
import pytest

from csia.aircraft.qualification import (SemanticContract, default_contract,
                                         CONTEXT_HARDWARE)
from csia.aircraft.sample import (AircraftSample, ChannelValue, MissingReason,
                                  Quality, SensorFrame)


# --------------------------------------------------------------------------
# The contract itself

def test_contract_loads_and_every_row_is_complete():
    c = default_contract()
    # ONE place to update, at the bottom of this file next to the content
    # hash. A literal here was part of why the version never moved: bumping
    # it broke a test that looked unrelated, so it was easier not to.
    assert c.version == CONTRACT_VERSION
    assert c.frozen_core == "csia-v1.0-research-final"
    required = ("unit", "quantity", "missing_semantics", "aggregation",
                "simulator_implementation", "physical_interpretation")
    for name, row in c.channels.items():
        for key in required:
            assert row.raw.get(key), f"{name} missing '{key}'"


def test_blocked_channels_state_a_reason():
    """A channel refused without a stated reason is unreviewable."""
    for name, quality, reason in default_contract().blocked_channels():
        assert reason.strip(), f"{name} is blocked with no reason given"


def test_only_informative_is_admissible():
    for q in Quality:
        assert q.admissible == (q is Quality.INFORMATIVE)


# --------------------------------------------------------------------------
# W-5: the ESC stub. This is the regression test named in the contract.

def test_esc_sitl_stub_is_not_informative():
    c = default_contract()
    for ch in ("esc.current", "esc.rpm"):
        row = c.channels[ch]
        assert row.quality is Quality.STUB_OR_NONINFORMATIVE, ch
        assert row.may_use is False, ch
        assert not row.admissible, ch
        assert row.simulator_implementation in ("CONSTANT_STUB", "PLACEHOLDER")


def test_esc_stub_value_is_dropped_not_passed_through():
    """The constant 0.8 A must not reach the core even as 'just for logging'.

    Keeping the value around is how it gets used for a decision later.
    """
    c = default_contract()
    cv = c.qualify("esc.current", np.array([0.8, 0.8, 0.8, 0.8]))
    assert cv.value is None
    assert cv.missing is MissingReason.STUB
    assert not cv.usable
    assert "0.8f" in cv.note or "fake" in cv.note


def test_esc_stub_never_reaches_the_frozen_core():
    from csia.aircraft.adapters import get_adapter
    ad = get_adapter("ardupilot")
    ad.ingest({"mavpackettype": "ESC_TELEMETRY_1_TO_4",
               "time_usec": 1_000_000,
               "rpm": [0, 0, 0, 0], "current": [80, 80, 80, 80]})
    s = ad.sample(t_mono=0.1)
    core = dict((sensor, ch) for sensor, _t, ch in ad.to_core_samples(s))
    assert "motor_esc" not in core, "the ESC stub reached the diagnostic core"


def test_esc_can_be_requalified_for_real_hardware():
    """Simulator qualification must not become a permanent hardware verdict.

    Real ESC telemetry IS informative; the row is simulator-specific.
    """
    c = SemanticContract(context=CONTEXT_HARDWARE)
    c.override("esc.current", Quality.INFORMATIVE, True,
               "bench 2026-09: real BLHeli telemetry, current tracks throttle")
    cv = c.qualify("esc.current", np.array([1.0, 2.0, 3.0, 4.0]))
    assert cv.usable
    assert "[OVERRIDE]" in cv.note


def test_override_requires_a_reason():
    c = SemanticContract()
    with pytest.raises(ValueError):
        c.override("esc.current", Quality.INFORMATIVE, True, "")


# --------------------------------------------------------------------------
# The other blocked channels, each for a different reason

def test_gnss_vertical_rate_is_unavailable_not_zero():
    row = default_contract().channels["gnss.velocity_z"]
    assert row.quality is Quality.UNAVAILABLE
    assert "padding" in row.reason or "does not exist" in row.reason


def test_estimator_is_informative_but_excluded_from_diagnosis():
    """CSIA must not consume the estimator it claims independence from."""
    row = default_contract().channels["estimator.variances"]
    assert row.quality is Quality.INFORMATIVE
    assert row.may_use is False
    assert not row.admissible


def test_inert_baro_temperature_is_blocked():
    row = default_contract().channels["baro.temp_c"]
    assert row.quality is Quality.VALIDATED_SEMANTICS
    assert not row.admissible


def test_unknown_channel_is_refused_by_default():
    cv = default_contract().qualify("mystery.channel", 1.0)
    assert cv.missing is MissingReason.NOT_QUALIFIED
    assert not cv.usable


# --------------------------------------------------------------------------
# ChannelValue invariants

def test_value_and_missing_are_mutually_exclusive():
    with pytest.raises(ValueError):
        ChannelValue(channel="x", value=1.0, missing=MissingReason.STALE)
    with pytest.raises(ValueError):
        ChannelValue(channel="x")


def test_missing_cannot_be_informative():
    with pytest.raises(ValueError):
        ChannelValue(channel="x", missing=MissingReason.STALE,
                     quality=Quality.INFORMATIVE)


def test_sample_separates_blocked_from_absent():
    """W-1 needs this: 'saw nothing' vs 'had nothing to see with'."""
    s = AircraftSample(t_mono=0.0)
    s.esc["esc.current"] = ChannelValue.absent(
        "esc.current", MissingReason.STUB,
        quality=Quality.STUB_OR_NONINFORMATIVE)
    s.gnss["gnss.position"] = ChannelValue.absent(
        "gnss.position", MissingReason.NO_3D_FIX)
    blocked = [cv.channel for cv in s.blocked_channels()]
    assert blocked == ["esc.current"]
    assert s.usable_channels() == []


def test_log_dict_is_json_safe():
    import json
    s = AircraftSample(t_mono=1.0)
    s.imu["imu0.accel"] = ChannelValue(
        channel="imu0.accel", value=np.array([0.0, 0.0, 9.81]), unit="m/s^2",
        quality=Quality.INFORMATIVE, frame=SensorFrame.BODY_Z_UP, age_s=0.01)
    blob = json.dumps(s.to_log_dict())
    assert "9.81" in blob
    assert "INFORMATIVE" in blob


# --------------------------------------------------------------------------
# The version must move when the content does.

CONTRACT_VERSION = 2
CONTRACT_CONTENT_SHA256 = \
    "76d8f333bd0e64d842917642ca7d0aa2d6de4bcbc39ffa2033af77d035656489"


def _contract_content_hash():
    """Hash the semantic content, excluding the version field itself.

    Excluded so that bumping the version does not change the hash it is
    supposed to be paired with -- otherwise the two could never agree.
    """
    import hashlib
    import yaml
    from csia.aircraft.qualification import CONTRACT_PATH
    with open(CONTRACT_PATH, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    doc.pop("contract_version", None)
    return hashlib.sha256(
        yaml.safe_dump(doc, sort_keys=True).encode()).hexdigest()


def test_the_contract_version_moves_when_the_contract_does():
    """`contract_version` sat at 1 through five commits that changed it.

    Those commits altered what CSIA may consume on PX4 (five
    platform_qualification rows) and what counts as fresh (two corrected
    producer rates, which MaxAge derives from). Every flight log stamps this
    number so a reader can tell which contract produced it; frozen, it made
    logs from materially different contracts indistinguishable.

    If this fails: decide whether the contract really changed. If it did,
    bump CONTRACT_VERSION here AND in the YAML, and update the hash. Updating
    only the hash defeats the purpose.
    """
    from csia.aircraft.qualification import default_contract
    assert default_contract().version == CONTRACT_VERSION
    assert _contract_content_hash() == CONTRACT_CONTENT_SHA256, (
        "CHANNEL_SEMANTICS.yaml changed. Bump contract_version (currently "
        f"{CONTRACT_VERSION}) and update CONTRACT_CONTENT_SHA256 to "
        f"{_contract_content_hash()}")


def test_the_stamped_version_reaches_the_flight_log():
    """A version nobody records is a version nobody can use."""
    from csia.aircraft.adapters import get_adapter
    meta = get_adapter("px4").sample(t_mono=0.0).metadata
    assert meta["contract_version"] == CONTRACT_VERSION
