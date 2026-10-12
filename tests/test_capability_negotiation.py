"""Capability negotiation must not report a missing sensor as a healthy one.

The systems paper measures a layer that emits health while holding no
applicable evidence. Capability negotiation is the pre-flight version of the
same question, and it has exactly one way to be useless: collapsing "this
airframe does not have it" into "this is fine".

So the tests below are all about keeping four different kinds of absence
apart:

    UNAVAILABLE      declared, not arriving        -- may be a fault
    STALE            arrived once, aged out        -- may be a fault
    UNKNOWN          nothing yet, too early        -- not yet a claim
    NOT_CONFIGURED   the profile never declared it -- not a fault
    INAPPLICABLE     the airframe cannot have it   -- not a fault

Only the first two are ever a fault. A negotiation that returns AVAILABLE for
any of the last three would manufacture exactly the false health the paper is
about.
"""

from __future__ import annotations

import os

import pytest

from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
from csia.aircraft.adapters.base import PlatformAdapter
from csia.aircraft.capability import (NODE_CHANNELS, Capability, negotiate)
from csia.aircraft.profile import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = os.path.join(ROOT, "profiles")


def test_node_channels_agrees_with_the_adapters_core_map():
    """Two hand-written maps of the same fact, checked against each other.

    `capability.NODE_CHANNELS` says which channels a trust-graph node needs;
    `PlatformAdapter.CORE_MAP` says which channels the adapter feeds the
    frozen core for that node. If the core map gains a sensor and this does
    not, negotiation reports a relation available that the core cannot
    compute.
    """
    core = {node: set(m.values()) for node, m in PlatformAdapter.CORE_MAP.items()}
    drift = []
    for node, channels in NODE_CHANNELS.items():
        if node not in core:
            drift.append(f"{node}: in NODE_CHANNELS, absent from CORE_MAP")
            continue
        # baro.temp_c is optional to the core, so CORE_MAP may carry it while
        # NODE_CHANNELS does not. Everything else must match.
        missing = set(channels) - core[node]
        extra = core[node] - set(channels) - {"baro.temp_c"}
        if missing:
            drift.append(f"{node}: NODE_CHANNELS requires {sorted(missing)} "
                         f"which CORE_MAP does not feed")
        if extra:
            drift.append(f"{node}: CORE_MAP feeds {sorted(extra)} which "
                         f"NODE_CHANNELS does not require")
    assert not drift, "\n  ".join([""] + drift)


def test_a_silent_adapter_reports_unknown_not_unavailable():
    """Nothing has arrived yet. That is not evidence of a fault.

    Reporting UNAVAILABLE here would make every vehicle look broken for its
    first second, and would train a reader to ignore the state that actually
    means something.
    """
    adapter = ArduPilotAdapter()
    report = negotiate(adapter, profile=None)
    assert report.channels["gnss.position"] is Capability.UNKNOWN
    assert report.nodes["gps"] is Capability.UNKNOWN
    assert not report.active_relations
    assert not report.inactive_relations, (
        "a silent adapter must not report relations INACTIVE -- that asserts "
        "they are dark, which is not known yet")
    assert report.unknown_relations


def test_the_single_imu_profile_reports_redundant_imu_inapplicable():
    """The uncomfortable answer, produced before the vehicle flies.

    A single-IMU board cannot feed `redundant_imu`. Saying so up front is the
    entire point: after the fact it is indistinguishable from an IMU that
    failed.
    """
    adapter = ArduPilotAdapter()
    profile = load(os.path.join(PROFILES, "minimal_single_imu_ardupilot.yaml"))
    report = negotiate(adapter, profile=profile)

    assert report.channels["imu1.accel"] is Capability.INAPPLICABLE
    assert report.nodes["imu1"] is Capability.INAPPLICABLE

    by_name = {r.relation: r for r in report.relations}
    assert by_name["redundant_imu"].capability is Capability.INAPPLICABLE
    assert "imu1" in by_name["redundant_imu"].blocking_nodes

    # Omitted, not inapplicable: the board could carry ESC telemetry.
    assert report.channels["esc.rpm"] is Capability.NOT_CONFIGURED
    assert by_name["vibration_prop_freq"].capability is \
        Capability.NOT_CONFIGURED

    # And neither is a fault.
    assert "redundant_imu" not in report.inactive_relations
    assert "redundant_imu" in report.structurally_absent_relations


def test_the_reference_profile_declares_more_than_the_minimal_one():
    """A sanity check with teeth: if these two ever negotiate identically,
    the profile is not reaching negotiation at all."""
    adapter = ArduPilotAdapter()
    ref = negotiate(adapter, load(
        os.path.join(PROFILES, "reference_quad_ardupilot.yaml")))
    minimal = negotiate(adapter, load(
        os.path.join(PROFILES, "minimal_single_imu_ardupilot.yaml")))
    assert len(ref.structurally_absent_relations) < \
        len(minimal.structurally_absent_relations), (
        "the minimal single-IMU profile must lose more relations than the "
        "full reference profile; if not, the profile is being ignored")


def test_a_report_without_a_profile_cannot_say_not_configured():
    """Honest degradation. With no profile there is no declaration, so
    NOT_CONFIGURED is not derivable and must not be invented."""
    report = negotiate(ArduPilotAdapter(), profile=None)
    assert Capability.NOT_CONFIGURED not in report.channels.values(), (
        "without a profile, nothing declares which channels the vehicle is "
        "supposed to have, so NOT_CONFIGURED is an unsupported claim")


def test_the_serialised_report_carries_both_halves():
    """`compatible` alone is a dangerous summary: one live relation out of
    eleven is 'compatible'. The dict must never expose it without the
    breakdown."""
    d = negotiate(ArduPilotAdapter(), load(
        os.path.join(PROFILES, "minimal_single_imu_ardupilot.yaml"))).to_dict()
    assert "compatible" in d
    assert set(d["summary"]) == {"active", "inactive", "structurally_absent",
                                 "unknown"}
    assert d["summary"]["structurally_absent"], (
        "the single-IMU profile must report structurally absent relations in "
        "the summary, or a reader sees only 'compatible'")
