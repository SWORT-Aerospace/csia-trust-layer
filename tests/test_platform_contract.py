"""Per-platform contract rows: they may narrow, and they may never widen.

Qualification is per platform instance -- CHANNEL_SEMANTICS.yaml has said so
since it was written, and the measurements finally forced the mechanism. PX4
SIH models one IMU, so `imu1.*` is not a message we failed to receive; it does
not exist there. Its BATTERY_STATUS carries the documented -1 sentinel, so
battery current is not "not received", it is not measured. Grading those the
same as a channel that should be present and is absent made every PX4 run FAIL
for reasons true of the airframe rather than of CSIA.

The danger is obvious and these tests are the guard against it: a per-platform
row is the easiest imaginable way to re-admit a stub. Write a platform row,
the guard disappears, the tests go green, and W-5 comes back. So:

  * a platform row can only REMOVE a channel from evidence, never add one;
  * every platform row must carry a reason AND an evidence path;
  * the base contract, and every other platform, are untouched.
"""

import os
import sys

import pytest
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.aircraft.qualification import (                       # noqa: E402
    CONTRACT_PATH, ChannelContract, SemanticContract,
    default_contract, platform_rows_in_force)
from csia.aircraft.sample import Quality                        # noqa: E402


BASE_ROW = {
    "channel": "esc.rpm",
    "qualification": "STUB_OR_NONINFORMATIVE",
    "csia_may_use": False,
}
ADMISSIBLE_ROW = {
    "channel": "imu0.accel",
    "qualification": "INFORMATIVE",
    "csia_may_use": True,
}


def test_a_platform_row_cannot_admit_what_the_base_contract_blocks():
    """The load-bearing rule. Without it this mechanism erases W-5."""
    row = dict(BASE_ROW, platform_qualification={"px4": {
        "qualification": "INFORMATIVE",
        "csia_may_use": True,
        "reason": "it moves on PX4",
        "evidence": "somewhere.json",
    }})
    with pytest.raises(ValueError, match="may not make a channel admissible"):
        ChannelContract(row, platform="px4")


def test_a_platform_row_may_narrow_an_admissible_channel():
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE",
        "csia_may_use": False,
        "reason": "PX4 SIH models one IMU",
        "evidence": "research/v1_1/results/qualification_px4.json",
    }})
    c = ChannelContract(row, platform="px4")
    assert c.quality is Quality.UNAVAILABLE
    assert c.admissible is False
    assert c.base_quality is Quality.INFORMATIVE      # base is preserved


def test_a_platform_row_without_a_reason_is_refused():
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE", "evidence": "x.json"}})
    with pytest.raises(ValueError, match="without a reason"):
        ChannelContract(row, platform="px4")


def test_a_platform_row_without_evidence_is_refused():
    # A qualification decision with no measurement behind it is an opinion,
    # and an opinion in a committed contract is indistinguishable from a
    # measurement.
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE", "reason": "because"}})
    with pytest.raises(ValueError, match="without an evidence path"):
        ChannelContract(row, platform="px4")


def test_a_row_for_another_platform_does_not_apply():
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE",
        "csia_may_use": False,
        "reason": "PX4 only",
        "evidence": "x.json",
    }})
    c = ChannelContract(row, platform="ardupilot")
    assert c.quality is Quality.INFORMATIVE
    assert c.platform_row is None


def test_the_unnarrowed_contract_is_unchanged():
    """`default_contract()` with no platform must behave exactly as before."""
    base = default_contract()
    assert platform_rows_in_force(base) == {}
    assert len(base.admissible_channels()) == 12


def test_ardupilot_carries_no_narrowings_today():
    ap = default_contract("ardupilot")
    assert platform_rows_in_force(ap) == {}
    assert ap.admissible_channels() == default_contract().admissible_channels()


def test_px4_narrowings_are_exactly_the_measured_ones():
    px4 = default_contract("px4")
    assert set(platform_rows_in_force(px4)) == {
        "imu1.accel", "imu1.gyro", "battery.current",
        "esc.current", "esc.rpm"}
    for ch in ("imu1.accel", "imu1.gyro", "battery.current"):
        assert px4.channels[ch].quality is Quality.UNAVAILABLE
        assert px4.channels[ch].admissible is False


def test_px4_esc_rpm_varies_and_is_still_not_admissible():
    """The measurement said it moves. That is not the same as usable.

    INFORMATIVE requires VALIDATED_SEMANTICS *and* demonstrated variation.
    Nobody has read the PX4 source for this field's units or indexing, so
    admitting it on the strength of "it moves" would be W-5's mistake with
    the sign reversed.
    """
    px4 = default_contract("px4")
    row = px4.channels["esc.rpm"]
    assert row.quality is Quality.AVAILABLE_UNVALIDATED
    assert row.admissible is False
    assert "to_promote" in row.platform_row


def test_every_committed_platform_row_carries_reason_and_evidence():
    with open(CONTRACT_PATH, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    seen = 0
    for row in doc["channels"]:
        for platform, pq in (row.get("platform_qualification") or {}).items():
            seen += 1
            assert pq.get("reason"), f"{row['channel']}/{platform}: no reason"
            assert pq.get("evidence"), f"{row['channel']}/{platform}: no evidence"
            assert pq.get("measured"), \
                f"{row['channel']}/{platform}: no measurement recorded"
    assert seen, "no platform rows found; this test would pass vacuously"


def test_every_platform_row_points_at_a_result_file_that_exists():
    # An evidence path nobody can open is the same as no evidence.
    with open(CONTRACT_PATH, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    for row in doc["channels"]:
        for platform, pq in (row.get("platform_qualification") or {}).items():
            path = os.path.join(ROOT, pq["evidence"])
            assert os.path.exists(path), \
                f"{row['channel']}/{platform}: evidence {pq['evidence']} missing"


def test_narrowing_reaches_the_adapter():
    """The point of the exercise: the PX4 adapter must see the PX4 rows."""
    from csia.aircraft.adapters import get_adapter
    assert get_adapter("px4").contract.channels["imu1.accel"].admissible is False
    assert get_adapter("ardupilot").contract.channels["imu1.accel"].admissible


def test_a_narrowed_channel_is_delivered_as_missing_not_as_a_value():
    px4 = SemanticContract(platform="px4")
    cv = px4.qualify("battery.current", 12.5, unit="A")
    assert cv.value is None
    assert cv.missing is not None
