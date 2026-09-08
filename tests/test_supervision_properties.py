"""Property-based tests for the supervision layer and the capability bridge.

The mission layer has property tests; these two did not. They are the layers
where a wrong answer is not a wrong number but a wrong SAFETY DIRECTION, and
direction is exactly what example-based tests cover unevenly -- you test the
cases you thought of.

THE TWO INVARIANTS, STATED ONCE
--------------------------------
Both layers are built on a monotonicity that must hold for every input, not
for the inputs someone happened to write down:

    the failsafe overlay may only RAISE      effective = max(frozen, super)
    the capability bridge may only DEMOTE    support is withdrawn, never given

If either ever runs the other way, the system is less safe than the frozen
core it wraps, which is the one outcome neither layer is allowed to produce.
"""

from __future__ import annotations

import os
import sys

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeLevel                  # noqa: E402
from csia_mission.capability import (NOT_SUPPORTED,              # noqa: E402
                                     SUPPORTED, UNKNOWN,
                                     EvidenceStatus)
from csia_mission.xr1_contracts import EVIDENCE                  # noqa: E402
from csia_supervision import DataLossCondition                   # noqa: E402
from csia_supervision import capability_bridge as bridge         # noqa: E402
from csia_supervision.dataloss import (BOTH_IMUS_LOST,           # noqa: E402
                                       DERIVED_FROM,
                                       DataLossSupervisor)

SENSORS = sorted(set(DERIVED_FROM) | {"gps", "motor_esc", "vibration"})

sensor_names = st.sampled_from(SENSORS)
levels = st.sampled_from(sorted(FailsafeLevel, key=lambda x: x.value))
SETTINGS = settings(max_examples=150, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow])


@st.composite
def conditions(draw, min_size=0, max_size=4):
    chosen = draw(st.lists(sensor_names, min_size=min_size,
                           max_size=max_size, unique=True))
    return {s: DataLossCondition(sensor=s, level=draw(levels), since=0.0,
                                 reason="", provenance="PROPERTY")
            for s in chosen}


@st.composite
def evidence_maps(draw):
    """A firewall verdict per declared evidence id, including UNKNOWNs."""
    return {e: EvidenceStatus(evidence_id=e,
                              supported=draw(st.sampled_from([True, False,
                                                              None])),
                              source="FIREWALL")
            for e in EVIDENCE}


# ---------------------------------------------------------------------------
# the bridge: demote-only, for every input
# ---------------------------------------------------------------------------

@SETTINGS
@given(evidence=evidence_maps(), conds=conditions())
def test_the_bridge_never_improves_any_evidence(evidence, conds):
    """THE CENTRAL INVARIANT. Over arbitrary firewall verdicts and arbitrary
    loss sets, no evidence id may come out better than it went in."""
    rank = {NOT_SUPPORTED: 0, UNKNOWN: 1, SUPPORTED: 2}
    merged = bridge.apply(evidence, conds)
    for eid, before in evidence.items():
        after = merged[eid]
        assert rank[after.state_at(0.0)] <= rank[before.state_at(0.0)], (
            f"{eid} improved from {before.state_at(0.0)} to "
            f"{after.state_at(0.0)}")


@SETTINGS
@given(evidence=evidence_maps(), conds=conditions())
def test_the_bridge_never_invents_or_drops_an_evidence_id(evidence, conds):
    """The key set is preserved exactly. A dropped id would read downstream
    as 'never declared' rather than 'withdrawn'."""
    assert set(bridge.apply(evidence, conds)) == set(evidence)


@SETTINGS
@given(evidence=evidence_maps(), conds=conditions())
def test_unknown_is_never_resolved_in_either_direction(evidence, conds):
    """UNKNOWN stays UNKNOWN. Not promoted, and not converted into a firm
    negative just because a sensor went quiet."""
    merged = bridge.apply(evidence, conds)
    for eid, before in evidence.items():
        if before.supported is None:
            assert merged[eid].supported is None, f"{eid} resolved UNKNOWN"


@SETTINGS
@given(evidence=evidence_maps(), a=conditions(), b=conditions())
def test_losing_more_sensors_never_withdraws_less(evidence, a, b):
    """MONOTONE IN THE LOSS SET. Adding a lost sensor cannot restore
    support for anything -- if it could, a worse aircraft would report a
    better capability."""
    union = dict(a)
    union.update(b)
    small = bridge.evidence_overrides(a)
    large = bridge.evidence_overrides(union)
    assert set(small) <= set(large), (
        "a superset of losses withdrew a strict subset of evidence")


@SETTINGS
@given(conds=conditions())
def test_every_override_is_attributable_and_negative(conds):
    """No override may be anything but a withdrawal, and every one must be
    stamped so it is never mistaken for a firewall certification."""
    for status in bridge.evidence_overrides(conds).values():
        assert status.supported is False
        assert status.source == bridge.SOURCE
        assert status.witness, "an override with no witness is unauditable"


@SETTINGS
@given(conds=conditions())
def test_applying_the_bridge_twice_changes_nothing_further(conds):
    """IDEMPOTENT. A second pass over already-withdrawn evidence must not
    shift anything, or the result would depend on how many times a caller
    happened to run it."""
    base = {e: EvidenceStatus(evidence_id=e, supported=True,
                              source="FIREWALL") for e in EVIDENCE}
    once = bridge.apply(base, conds)
    twice = bridge.apply(once, conds)
    assert {k: (v.supported, v.source) for k, v in once.items()} == \
           {k: (v.supported, v.source) for k, v in twice.items()}


@SETTINGS
@given(conds=conditions())
def test_only_mapped_sensors_can_withdraw_anything(conds):
    """An unmapped sensor's loss must reach no evidence at all -- and the
    report must say so rather than presenting silence as no impact."""
    lost = set(conds)
    if lost and lost <= bridge.UNMAPPED:
        assert bridge.evidence_overrides(conds) == {}
        rep = bridge.report({}, conds)
        assert set(rep["sensors_lost_with_no_evidence_mapping"]) == lost


# ---------------------------------------------------------------------------
# the supervisor: raise-only, for every input
# ---------------------------------------------------------------------------

class _State:
    """The minimum surface DataLossSupervisor.update reads."""

    def __init__(self, t, fresh):
        self.t = t
        self.fresh = dict(fresh)
        self.trust = {k: 1.0 for k in fresh}
        self.edges: dict = {}


@SETTINGS
@given(freshness=st.lists(
    st.dictionaries(sensor_names, st.booleans(),
                    min_size=len(SENSORS), max_size=len(SENSORS)),
    min_size=1, max_size=12))
def test_the_supervisor_level_is_never_below_normal(freshness):
    """A supervisor that could go below NORMAL would be able to lower the
    effective level through the max(), which the composition forbids."""
    sup = DataLossSupervisor()
    t = 0.0
    for fresh in freshness:
        t += 1.0
        sup.update(_State(t, fresh))
        assert sup.level.value >= FailsafeLevel.NORMAL.value


@SETTINGS
@given(freshness=st.lists(
    st.dictionaries(sensor_names, st.booleans(),
                    min_size=len(SENSORS), max_size=len(SENSORS)),
    min_size=1, max_size=12))
def test_a_sensor_never_seen_fresh_never_raises_a_loss(freshness):
    """A sensor absent for the whole flight was never fitted. Alarming on
    it would make every unfitted sensor a permanent alarm -- the same rule
    the frozen policy applies to GPS."""
    sup = DataLossSupervisor()
    t = 0.0
    for fresh in freshness:
        t += 1.0
        sup.update(_State(t, fresh))
    never = {s for s in SENSORS if not any(f.get(s) for f in freshness)}
    for cond in sup.conditions.values():
        assert cond.sensor not in never, (
            f"{cond.sensor} raised a loss without ever having been fresh")


@SETTINGS
@given(freshness=st.lists(
    st.dictionaries(sensor_names, st.booleans(),
                    min_size=len(SENSORS), max_size=len(SENSORS)),
    min_size=1, max_size=12))
def test_every_condition_names_a_sensor_that_stopped_delivering(freshness):
    """No condition may be raised for a sensor that is currently fresh."""
    sup = DataLossSupervisor()
    t = 0.0
    last = {}
    for fresh in freshness:
        t += 1.0
        sup.update(_State(t, fresh))
        last = fresh
    for cond in sup.conditions.values():
        assert not last.get(cond.sensor, False), (
            f"{cond.sensor} is fresh and still carries a loss condition")


def test_the_two_imu_rule_is_the_most_severe_single_rule():
    """Losing both inertial sources must outrank losing either alone, or
    the severity ordering does not reflect the physics."""
    for sensor, (level, _prov, _anchor) in DERIVED_FROM.items():
        if sensor in ("imu0", "imu1"):
            assert BOTH_IMUS_LOST.value > level.value, (
                f"losing both IMUs is not more severe than losing {sensor}")


@SETTINGS
@given(conds=conditions(min_size=1))
def test_the_report_is_json_serialisable(conds):
    """It goes into the flight log every tick a condition is active."""
    import json
    json.dumps(bridge.report({}, conds))
