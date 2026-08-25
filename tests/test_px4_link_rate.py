"""The PX4 rate conflict, pinned so neither number can be 'fixed' into the other.

Two committed artifacts disagree about `baro.altitude` on PX4 by 10x, and BOTH
are correct:

    research/v1_1/results/qualification_px4.json    9.825 Hz
    research/v1_1/results/shadow_flights/*.jsonl    1.00  Hz

The rate is a property of the LINK -- set by whoever last transmitted
SET_MESSAGE_INTERVAL on it -- not of the platform. The qualification probe
calls `rigs.connect()`, which requests msg 29 at 10 Hz. CSIA binds a passive
companion link and may not transmit, so nothing ever raises its rates.

WHY THESE TESTS EXIST. The first response to the conflict was to "correct" the
contract from 10 Hz to 1 Hz. That is the trap: it replaces one link-conditional
constant with another, and it breaks the qualification probe, which measures
the other link. These tests hold the reconciliation in place from both ends --
the contract must keep describing the REQUESTING link, and the probe artifact
must keep showing that requests, not instances, are the cause.

Reads committed artifacts only. Launches nothing.
"""

from __future__ import annotations

import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROBE = os.path.join(ROOT, "research", "v1_1", "results",
                     "PX4_LINK_RATE_PROBE.json")
CONTRACT = os.path.join(ROOT, "docs", "simulation", "CHANNEL_SEMANTICS.yaml")
QUAL = os.path.join(ROOT, "research", "v1_1", "results",
                    "qualification_px4.json")

# The channels in dispute and the message each is carried by.
DISPUTED = {"SCALED_PRESSURE": "baro.altitude",
            "BATTERY_STATUS": "battery.voltage",
            "VIBRATION": "vibration.rms"}
SLOW_HZ = 2.0        # an unrequested PX4 default, generously bounded
FAST_HZ = 5.0        # a requested 10 Hz stream, generously bounded


@pytest.fixture(scope="module")
def probe():
    if not os.path.exists(PROBE):
        pytest.skip("run tools/simulation/px4_link_rate_probe.py first")
    with open(PROBE, encoding="utf-8") as fh:
        return json.load(fh)


def hz(probe, arm, link, msg):
    return probe["arms"][arm]["links"][link][msg]["hz"]


def test_the_artifact_names_the_build_it_measured(probe):
    """These are defaults of one firmware, and the guard reads the artifact.

    Every other test here checks the contract against a COMMITTED measurement
    rather than a live simulator, so a PX4 upgrade that moved the default
    stream rates would leave them all passing against a stale file. Recording
    the build is what lets a reader tell whether the numbers still apply.
    """
    prov = probe.get("simulator_provenance") or {}
    assert prov.get("firmware") == "PX4-Autopilot", prov
    assert len(prov.get("sha") or "") == 40, prov
    assert probe.get("airframe", {}).get("PX4_SIM_MODEL") == "sihsim_quadx", (
        "the rates were measured on the SIH quadx airframe; another airframe "
        "may stream differently")


def test_the_instance_is_not_the_cause(probe):
    """With neither link requesting, both stream the disputed channels slowly.

    This is the arm that kills the obvious hypothesis. If binding 14550 rather
    than 14540 were what made qualification see 9.8 Hz, the two links would
    differ HERE, and they do not.
    """
    for msg in DISPUTED:
        a = hz(probe, "passive", "14540", msg)
        b = hz(probe, "passive", "14550", msg)
        assert a < SLOW_HZ, f"{msg} on 14540 passive: {a} Hz"
        assert b < SLOW_HZ, f"{msg} on 14550 passive: {b} Hz"


def test_requests_are_per_link_and_are_the_cause(probe):
    """Requesting on one link raises that link ALONE, in both directions."""
    for msg in DISPUTED:
        # requested on 14550 -> 14550 fast, 14540 untouched
        assert hz(probe, "request", "14550", msg) > FAST_HZ, msg
        assert hz(probe, "request", "14540", msg) < SLOW_HZ, msg
        # requested on 14540 -> 14540 fast, 14550 untouched
        assert hz(probe, "request_onboard", "14540", msg) > FAST_HZ, msg
        assert hz(probe, "request_onboard", "14550", msg) < SLOW_HZ, msg


def test_an_unrequested_control_channel_is_unaffected_by_every_arm(probe):
    """ATTITUDE is requested by no arm, so it must not move between them.

    Without this, an arm that changed the whole boot rather than the requested
    streams would look identical to the finding.
    """
    seen = [hz(probe, arm, "14550", "ATTITUDE")
            for arm in ("passive", "request", "request_onboard")]
    assert all(v > 40.0 for v in seen), seen
    assert max(seen) - min(seen) < 5.0, seen


def test_the_contract_describes_the_requesting_link(probe):
    """The declared PX4 rate must match the REQUESTING regime, not the passive one.

    Editing it down to the passive rate is the trap this file exists for: the
    contract is what `qualification_px4.json` is checked against, and that probe
    requests intervals. The starvation is real and the fix is to DRIVE CSIA's
    link, not to edit this number.
    """
    text = open(CONTRACT, encoding="utf-8").read()
    m = re.search(r"- channel: baro\.altitude\b.*?producer_px4:.*?"
                  r"rate_hz:\s*([0-9.]+)", text, re.S)
    assert m, "baro.altitude producer_px4 rate_hz not found in the contract"
    declared = float(m.group(1))
    requesting = hz(probe, "request_onboard", "14540", "SCALED_PRESSURE")
    passive = hz(probe, "passive", "14540", "SCALED_PRESSURE")
    assert abs(declared - requesting) / declared < 0.25, (
        f"declared {declared} Hz no longer matches the requesting link "
        f"({requesting} Hz)")
    assert abs(declared - passive) / declared > 0.5, (
        f"declared {declared} Hz now matches the PASSIVE link ({passive} Hz). "
        f"If this was a deliberate contract change, the qualification probe "
        f"must be changed to measure the passive link in the same commit.")


def test_the_qualification_artifact_matches_the_requesting_regime():
    """Every disputed channel in the committed qualification is a fast measurement.

    This is the other end of the reconciliation: the committed artifact must
    keep testifying about the REQUESTING link. If it ever measures these
    channels slowly, the probe stopped requesting intervals and the contract
    it validates no longer describes anything.
    """
    if not os.path.exists(QUAL):
        pytest.skip("no committed PX4 qualification artifact")
    with open(QUAL, encoding="utf-8") as fh:
        qual = json.load(fh)
    rows = {r.get("channel"): r for r in (qual.get("rows") or [])
            if isinstance(r, dict)}
    for msg, channel in sorted(DISPUTED.items()):
        row = rows.get(channel)
        assert row is not None, f"{channel} absent from the qualification rows"
        measured = row.get("measured_rate_hz")
        assert measured is not None, f"{channel} carries no measured_rate_hz"
        assert float(measured) > FAST_HZ, (
            f"the committed qualification measured {channel} at {measured} Hz, "
            f"which is the PASSIVE regime -- the probe stopped requesting "
            f"intervals")
