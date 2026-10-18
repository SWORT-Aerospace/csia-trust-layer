"""The decoder must never be able to report itself as the platform.

These tests exist because that already happened. A PX4 qualification run
reported `esc.current` and `esc.rpm` as "never arrived" while PX4 was sending
ESC_STATUS 38 times per run: the installed pymavlink carries a reduced
common.xml with no message 291, so every one of those frames was counted as
`UNKNOWN_291` and binned with the traffic we deliberately ignore.

The finding was written into docs/simulation/PX4_CURRENT.md as a property of
PX4 SIH. It was a property of the parser.

Every test here fixes one link in that chain.
"""

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.aircraft.qualification import default_contract        # noqa: E402
from csia.simulation.dialect import (                           # noqa: E402
    blind_channels, message_names, producer_messages,
    undecodable_frames)

sys.path.insert(0, os.path.join(ROOT, "tools", "simulation"))
from qualify_platform import (                                  # noqa: E402
    UNDECODABLE, analyse, verdict_exit_code)


XML = """<?xml version="1.0"?>
<mavlink>
  <include>inc.xml</include>
  <messages>
    <message id="291" name="ESC_STATUS"><field type="uint8_t" name="index"/></message>
    <message id="410" name="EVENT"><field type="uint8_t" name="destination"/></message>
  </messages>
</mavlink>
"""

INC = """<?xml version="1.0"?>
<mavlink>
  <messages>
    <message id="253" name="STATUSTEXT"><field type="uint8_t" name="severity"/></message>
  </messages>
</mavlink>
"""


@pytest.fixture
def defs(tmp_path, monkeypatch):
    """A miniature vehicle definitions tree, top file plus an include."""
    d = tmp_path / "src" / "modules" / "mavlink" / "mavlink" / \
        "message_definitions" / "v1.0"
    d.mkdir(parents=True)
    (d / "development.xml").write_text(XML)
    (d / "inc.xml").write_text(INC)
    return str(tmp_path)


def test_message_names_reads_the_vehicles_own_xml(defs):
    names = message_names("px4", defs)
    assert names[291] == "ESC_STATUS"
    assert names[410] == "EVENT"


def test_message_names_follows_includes(defs):
    # STATUSTEXT lives in the included file. If includes were not followed,
    # an unknown id would come back unnamed and the guard could not tell
    # whether the contract depends on it.
    assert message_names("px4", defs)[253] == "STATUSTEXT"


def test_message_names_is_empty_without_a_checkout(tmp_path):
    # Must not raise. No checkout is a legitimate state; a crash here would
    # take down a qualification run that is otherwise perfectly valid.
    assert message_names("px4", str(tmp_path)) == {}


def test_undecodable_frames_separates_unknown_from_unmapped():
    unmapped = {"ATTITUDE": 1875, "UNKNOWN_291": 38, "UNKNOWN_410": 2}
    assert undecodable_frames(unmapped) == {291: 38, 410: 2}


def test_unmapped_by_choice_is_not_undecodable():
    # ATTITUDE is decoded perfectly well and simply not consumed. Treating
    # that as a blind spot would make the guard fire on every run and train
    # everyone to ignore it.
    assert undecodable_frames({"ATTITUDE": 4010, "VFR_HUD": 150}) == {}


def test_the_real_contract_names_esc_status_as_a_px4_producer():
    # The link that made the guard possible: the contract already said which
    # message each channel needs. Nothing looked.
    producers = producer_messages(default_contract(), "px4")
    assert set(producers["ESC_STATUS"]) == {"esc.current", "esc.rpm"}


def test_producer_messages_accepts_a_list_of_alternatives():
    # ArduPilot publishes imu0 as RAW_IMU or SCALED_IMU depending on the
    # link, so the contract row holds a list. A guard that only understood
    # the scalar form would be blind on exactly the channels with fallbacks.
    producers = producer_messages(default_contract(), "ardupilot")
    assert "imu0.accel" in producers["RAW_IMU"]
    assert "imu0.accel" in producers["SCALED_IMU"]


def test_the_published_px4_defect_is_now_caught():
    """The regression test for the actual event.

    Undecodable id 291, 38 frames, exactly what the run saw.
    """
    contract = default_contract()
    blind = blind_channels(contract, "px4", {291: 38}, {291: "ESC_STATUS"})
    assert set(blind) == {"esc.current", "esc.rpm"}
    assert blind["esc.current"]["frames"] == 38


def test_an_unknown_id_the_contract_does_not_need_is_not_blindness():
    contract = default_contract()
    # 410 EVENT: undecodable, and no channel depends on it. Recorded in the
    # result file, but it does not void anything.
    assert blind_channels(contract, "px4", {410: 2}, {410: "EVENT"}) == {}


def test_analyse_marks_a_blind_channel_undecodable_not_unavailable():
    contract = default_contract()
    blind = {"esc.rpm": {"message": "ESC_STATUS", "id": 291, "frames": 38}}
    rows = {r["channel"]: r for r in analyse({}, {}, contract, {}, blind)}
    assert rows["esc.rpm"]["observed"] == UNDECODABLE
    # And the fact that made it wrong before: it must NOT be reported absent.
    assert rows["esc.rpm"]["observed"] != "UNAVAILABLE"


def test_a_blind_channel_neither_agrees_nor_disagrees():
    # None, not False. A run that could not read the message is not entitled
    # to a disagreement finding either -- that would be the same error with
    # the sign flipped.
    contract = default_contract()
    blind = {"esc.rpm": {"message": "ESC_STATUS", "id": 291, "frames": 38}}
    rows = {r["channel"]: r for r in analyse({}, {}, contract, {}, blind)}
    assert rows["esc.rpm"]["agrees"] is None


def test_a_fail_verdict_does_not_exit_zero():
    """The gate reported success on a failing qualification.

    The PX4 run of 2026-08-24 printed "FAIL: a channel the contract admits as
    evidence never arrived" and exited 0, because the exit code was computed
    from its own conditions and that branch had none. `make sim-px4` was
    green.
    """
    assert verdict_exit_code(
        "FAIL: a channel the contract admits as evidence never arrived") == 1
    assert verdict_exit_code("FAIL: a stub channel is admissible") == 1


def test_every_verdict_branch_maps_to_an_exit_code():
    for verdict in ("PASS",
                    "FAIL: a stub channel is admissible as evidence",
                    "PARTIAL: no motion, so constancy is not assessed",
                    "INVALID_PROBE: the airframe did not move",
                    "INSTRUMENT_DEAD: the decoder could not read ESC_STATUS"):
        assert verdict_exit_code(verdict) is not None, verdict
    assert verdict_exit_code("PASS") == 0


def test_an_unmapped_verdict_is_not_silently_a_pass():
    # None, so the caller fails loudly. Defaulting to 0 would hide exactly the
    # case where someone adds a verdict and forgets the gate.
    assert verdict_exit_code("SOMETHING_NEW: invented later") is None


def test_channels_the_decoder_could_read_are_unaffected():
    contract = default_contract()
    blind = {"esc.rpm": {"message": "ESC_STATUS", "id": 291, "frames": 38}}
    obs = {"imu0.accel": [1.0, 2.0, 3.0]}
    rows = {r["channel"]: r for r in analyse(obs, {}, contract, {}, blind)}
    assert rows["imu0.accel"]["observed"] == "INFORMATIVE"
    # A channel that genuinely never arrived is still reported absent: the
    # guard narrows a claim, it does not suppress the whole run.
    assert rows["imu1.accel"]["observed"] == "UNAVAILABLE"


def test_a_sentinel_is_not_reported_as_never_arrived():
    """PX4's BATTERY_STATUS arrives at ~9 Hz with current_battery = -1.

    Reporting that as "never arrived" says the stream is unimplemented. It
    says the opposite: the stream works and the vehicle has no current
    sensor. Which one is true decides whether the fix is wiring or hardware.
    """
    contract = default_contract()
    rows = {r["channel"]: r
            for r in analyse({}, {}, contract, {}, {}, {"battery.current": 375})}
    detail = rows["battery.current"]["detail"]
    assert "never arrived" not in detail
    assert "375" in detail and "sentinel" in detail
    # Still UNAVAILABLE as evidence -- the cause changed, not the usability.
    assert rows["battery.current"]["observed"] == "UNAVAILABLE"


def test_a_genuinely_absent_channel_still_says_never_arrived():
    contract = default_contract()
    rows = {r["channel"]: r for r in analyse({}, {}, contract, {}, {}, {})}
    assert rows["imu1.accel"]["detail"] == "never arrived"


def test_adapters_name_the_channel_they_rejected():
    from csia.aircraft.adapters import get_adapter
    for platform in ("ardupilot", "px4"):
        a = get_adapter(platform)
        a._reject_sentinel("battery.current")
        assert a.sentinel_counts() == {"battery.current": 1}
        # The global tally still moves: nothing downstream that reads it
        # breaks because the per-channel detail was added.
        assert a.counters["rejected_sentinel"] == 1


# --------------------------------------------------------------------------
# The sentinel had a name and no producer.

def test_a_sentinel_reaches_the_sample_as_SENTINEL_not_NOT_RECEIVED():
    """`MissingReason.SENTINEL` was defined and produced NOWHERE.

    PX4's BATTERY_STATUS arrives at ~9.7 Hz with current_battery = -1. The
    flight log recorded that as NOT_RECEIVED -- byte for byte identical to a
    message that never came. The per-channel COUNTER was added first and
    written up as though it had fixed this; it had not.
    """
    from csia.aircraft.adapters import get_adapter
    from csia.aircraft.sample import MissingReason

    a = get_adapter("ardupilot")
    a.ingest({"mavpackettype": "BATTERY_STATUS",
              "voltages": [15300] + [65535] * 9,
              "current_battery": -1, "time_boot_ms": 1000})
    s = a.sample(t_mono=0.0)
    assert s.battery["battery.current"].missing is MissingReason.SENTINEL
    # The message DID arrive: voltage from the same packet is present.
    assert s.battery["battery.voltage"].value == 15.3


def test_a_channel_that_never_arrived_is_still_NOT_RECEIVED():
    from csia.aircraft.adapters import get_adapter
    from csia.aircraft.sample import MissingReason
    a = get_adapter("ardupilot")
    assert (a.sample(t_mono=0.0).battery["battery.current"].missing
            is MissingReason.NOT_RECEIVED)


def test_a_real_value_supersedes_an_earlier_sentinel():
    # A sensor that starts reporting must not keep being described as
    # unmeasured.
    from csia.aircraft.adapters import get_adapter
    a = get_adapter("ardupilot")
    for cur in (-1, 520):
        a.ingest({"mavpackettype": "BATTERY_STATUS",
                  "voltages": [15300] + [65535] * 9,
                  "current_battery": cur, "time_boot_ms": 1000})
    cv = a.sample(t_mono=0.0).battery["battery.current"]
    assert cv.value == 5.2 and cv.missing is None


def test_a_sentinel_value_is_still_not_admissible():
    # SENTINEL is a better reason, not a promotion. The value stays absent.
    from csia.aircraft.adapters import get_adapter
    from csia.aircraft.sample import Quality
    a = get_adapter("ardupilot")
    a.ingest({"mavpackettype": "BATTERY_STATUS",
              "voltages": [15300] + [65535] * 9,
              "current_battery": -1, "time_boot_ms": 1000})
    cv = a.sample(t_mono=0.0).battery["battery.current"]
    assert cv.value is None
    assert cv.quality is not Quality.INFORMATIVE
