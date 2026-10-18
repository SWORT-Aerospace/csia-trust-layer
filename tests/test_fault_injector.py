"""The fault injector protocol, and the one field the whole thing is for.

`confirmed`. Every other part of the protocol is plumbing around a single
question: did the fault actually happen, measured downstream, or did a command
merely return success?

The tests that matter here are the ones about what the injector must NOT say:

  * an injector that cannot measure returns `confirmed: null`, NEVER `true` --
    "we could not tell" and "it did not happen" are different facts, and
    collapsing them is how an unproven intervention becomes a detector miss in
    somebody's results table;
  * the simulated backend marks everything it produces inadmissible;
  * the serial backend refuses to construct, because the device does not exist.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.csia_experiment.fault_injector import (       # noqa: E402
    PROTOCOL_VERSION, InjectorError, SerialInjector, SimulatedInjector,
    injection_record)
from tools.csia_experiment.validity import (             # noqa: E402
    TrialState, adjudicate)

PROTOCOL = os.path.join(ROOT, "hardware", "validation_rig",
                        "FAULT_INJECTOR_PROTOCOL.md")


def _base(**over):
    rec = {"attempted": True, "prereg_deviations": [], "operator_abort": False,
           "rig_faults": [], "null_controls": [{"name": "n", "quiet": True}],
           "first_break": None, "stages": {}}
    rec.update(over)
    return rec


def test_an_injector_that_cannot_measure_never_confirms():
    """THE LOAD-BEARING TEST. `null` is not `false` and is certainly not `true`."""
    inj = SimulatedInjector(can_measure=False)
    inj.send({"seq": 1, "cmd": "arm", "token": "T", "ttl_s": 60})
    out = inj.send({"seq": 2, "cmd": "cut", "channel": "gnss_uart"})
    assert out["ok"] is True, "the actuation did happen"
    assert out["confirmed"] is None, (
        "an injector with no measurement capability must return null, not a "
        "confirmation it cannot support")
    assert out["confirmed"] is not True


def test_an_unconfirmed_injection_breaks_the_evidence_chain():
    inj = SimulatedInjector(can_measure=False)
    rec = injection_record(inj, "gnss_uart", token="T")
    assert rec["first_break"] == "SIMULATOR_STATE_CHANGED"
    assert adjudicate(_base(**{k: v for k, v in rec.items()
                               if k == "first_break"})).state \
        is TrialState.INVALID_SCENARIO, (
        "an unproven intervention is INVALID_SCENARIO -- NOT a detector miss")


def test_a_confirmed_injection_closes_that_stage():
    inj = SimulatedInjector(can_measure=True)
    rec = injection_record(inj, "gnss_uart", token="T")
    assert rec["injection"]["confirmed"] is True
    assert rec["first_break"] is None


def test_the_simulated_backend_marks_everything_it_produces_inadmissible():
    inj = SimulatedInjector()
    rec = injection_record(inj, "gnss_uart", token="T")
    assert rec["admissible_as_evidence"] is False
    assert rec["evidence_tier"] == "E0"
    assert "mock of a measurement" in rec["admissibility_note"]
    assert inj.send({"seq": 9, "cmd": "hello"})["simulated"] is True


def test_the_serial_backend_refuses_rather_than_stubbing():
    with pytest.raises(InjectorError) as exc:
        SerialInjector("/dev/ttyACM0")
    text = str(exc.value)
    assert "not implemented" in text
    assert "USER_ACTION_REQUIRED.md" in text
    assert "FAULT_INJECTOR_PROTOCOL.md" in text


def test_actuation_is_refused_until_armed():
    inj = SimulatedInjector()
    out = inj.send({"seq": 1, "cmd": "cut", "channel": "gnss_uart"})
    assert out["ok"] is False and out["error"] == "NOT_ARMED", (
        "a rig left able to actuate between sessions cuts a line during an "
        "unrelated test")


def test_an_unknown_channel_is_named_rather_than_ignored():
    inj = SimulatedInjector()
    inj.send({"seq": 1, "cmd": "arm", "token": "T", "ttl_s": 60})
    out = inj.send({"seq": 2, "cmd": "cut", "channel": "imu9_spi_cs"})
    assert out["ok"] is False and out["error"] == "UNKNOWN_CHANNEL"
    assert "gnss_uart" in out["detail"], "the error must list what exists"


def test_a_protocol_mismatch_stops_the_run():
    class WrongVersion(SimulatedInjector):
        def _dispatch(self, command):
            out = super()._dispatch(command)
            if command.get("cmd") == "hello":
                out["proto"] = "99.0"
            return out

    with pytest.raises(InjectorError, match="protocol"):
        injection_record(WrongVersion(), "gnss_uart", token="T")


def test_every_response_echoes_its_sequence_number():
    """A response matched to the nearest command is a response matched wrong."""
    inj = SimulatedInjector()
    for seq in (1, 7, 99):
        assert inj.send({"seq": seq, "cmd": "status"})["seq"] == seq


def test_the_protocol_forbids_transmitting_hardware():
    text = open(PROTOCOL, encoding="utf-8").read()
    assert "No RF jamming" in text and "no GNSS spoofing transmitter" in text
    assert "props_removed_for_bench" in text


def test_the_protocol_says_why_no_firmware_exists():
    """Untested firmware in hardware/ would read as a validated component."""
    # Whitespace-normalised: the phrase spans a line break in the document,
    # and reflowing prose to satisfy a substring test is the tail wagging the
    # dog.
    import re
    text = open(PROTOCOL, encoding="utf-8").read()
    flat = re.sub(r"\s+", " ", text)
    assert "NO FIRMWARE WRITTEN" in flat
    assert "untested code for a device that does not exist" in flat


def test_the_protocol_version_matches_the_implementation():
    text = open(PROTOCOL, encoding="utf-8").read()
    assert f"v{PROTOCOL_VERSION}" in text.splitlines()[0], (
        "the document and the code must not drift into two protocols")
