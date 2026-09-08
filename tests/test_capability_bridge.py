"""A lost sensor must reach the capability layer, and go no further.

BEFORE THIS BRIDGE, the two layers did not talk. A cut baro line raised a
CAUTION in `csia_supervision` and `altitude_hold` went on reporting
SUPPORTED, because the evidence under it was still whatever the firewall had
last said. The alarm and the capability report disagreed about the same
aircraft.

The bridge closes that. These tests hold it to the rule that makes it safe:

    IT MAY ONLY DEMOTE.

A lost sensor is proof the evidence riding on it is not supportable now. A
present sensor is proof of nothing -- support is the firewall's verdict, and
delivering bytes is not a verdict. So the bridge withdraws support and never
grants it, and never resolves an UNKNOWN into a definite state either.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeLevel                  # noqa: E402
from csia_mission.capability import (DEGRADED_SUPPORTED,         # noqa: E402
                                     NOT_SUPPORTED, SUPPORTED, UNKNOWN,
                                     EvidenceStatus,
                                     evaluate_capabilities)
from csia_mission.xr1_contracts import CAPABILITIES, EVIDENCE    # noqa: E402
from csia_supervision import DataLossCondition                   # noqa: E402
from csia_supervision import capability_bridge as bridge         # noqa: E402


def _cond(sensor, level=FailsafeLevel.CAUTION):
    return DataLossCondition(sensor=sensor, level=level, since=0.0,
                             reason=f"{sensor} stopped delivering",
                             provenance="TEST")


def _all_supported():
    return {e: EvidenceStatus(evidence_id=e, supported=True,
                              source="FIREWALL")
            for e in EVIDENCE}


# ---------------------------------------------------------------------------
# the mapping is honest about itself
# ---------------------------------------------------------------------------

def test_every_mapped_evidence_id_is_one_the_contracts_actually_name():
    """A mapping to an id no contract mentions is a demotion that reaches
    nothing -- it would look like coverage and do nothing at all."""
    named = set(EVIDENCE)
    for sensor, ids in bridge.SENSOR_EVIDENCE.items():
        for eid in ids:
            assert eid in named, f"{sensor} -> {eid} is not a declared id"
    for eid in bridge.REQUIRES_ALL_LOST:
        assert eid in named, f"{eid} is not a declared id"


def test_the_unmapped_sensors_are_declared_rather_than_missing():
    """`motor_esc` and `vibration` have no canonical evidence in the XR-1
    set. They must be listed as unmapped, not quietly absent -- a bridge
    covering six of eight sensors reads exactly like one covering eight."""
    from csia_supervision.dataloss import DERIVED_FROM
    monitored = set(DERIVED_FROM) | {"gps"}
    covered = set(bridge.SENSOR_EVIDENCE)
    assert bridge.UNMAPPED == monitored - covered, (
        "UNMAPPED must be exactly the monitored sensors with no mapping")
    assert bridge.UNMAPPED == {"motor_esc", "vibration"}


def test_losing_one_imu_does_not_demote_attitude():
    """THE DEPENDENCY THAT WAS NOT INVENTED. The estimator has two inertial
    sources; asserting that losing one destroys attitude would be a claim
    no evidence here supports."""
    out = bridge.evidence_overrides({"imu0": _cond("imu0")})
    assert "attitude.supported" not in out
    assert "imu.primary.supported" in out


def test_losing_both_imus_does_demote_attitude_and_says_it_is_derived():
    out = bridge.evidence_overrides(
        {"imu0": _cond("imu0"), "imu1": _cond("imu1")})
    att = out["attitude.supported"]
    assert att.supported is False
    assert all(w.startswith(bridge.DERIVED) for w in att.witness), (
        "a derived demotion must not be presented as a direct reading")
    assert any(w.startswith(bridge.DIRECT)
               for w in out["imu.primary.supported"].witness)


# ---------------------------------------------------------------------------
# demote-only
# ---------------------------------------------------------------------------

def test_the_bridge_never_marks_anything_supported():
    """Across every single-sensor loss AND the no-loss case."""
    for conds in [{}] + [{s: _cond(s)} for s in bridge.SENSOR_EVIDENCE]:
        for status in bridge.evidence_overrides(conds).values():
            assert status.supported is False


def test_no_loss_produces_no_overrides_at_all():
    """Silence, not endorsement. The firewall's verdicts stand untouched."""
    ev = _all_supported()
    assert bridge.evidence_overrides({}) == {}
    assert bridge.apply(ev, {}) == ev


def test_unknown_evidence_is_left_unknown():
    """UNKNOWN IS NEVER RESOLVED BY THIS LAYER. Converting it to a definite
    NOT_SUPPORTED would be manufacturing certainty from a quiet sensor."""
    ev = _all_supported()
    ev["baro.altitude.supported"] = EvidenceStatus(
        evidence_id="baro.altitude.supported", supported=None,
        source="FIREWALL")
    merged = bridge.apply(ev, {"baro": _cond("baro")})
    assert merged["baro.altitude.supported"].supported is None
    assert merged["baro.altitude.supported"].state_at(0.0) == UNKNOWN


def test_an_override_is_attributable_to_this_bridge():
    """A downstream reader must be able to tell an override from a firewall
    verdict; they are not the same kind of claim."""
    merged = bridge.apply(_all_supported(), {"baro": _cond("baro")})
    assert merged["baro.altitude.supported"].source == bridge.SOURCE
    assert merged["gnss.position.supported"].source == "FIREWALL"


# ---------------------------------------------------------------------------
# end to end: the alarm reaches the capability
# ---------------------------------------------------------------------------

def test_a_cut_baro_line_makes_altitude_hold_not_supported():
    """THE CASE THAT MOTIVATED THE BRIDGE."""
    before = evaluate_capabilities(CAPABILITIES, _all_supported(), now=0.0,
                                   compute={}, timing={}, actuators={})
    assert before["altitude_hold"].state == SUPPORTED

    merged = bridge.apply(_all_supported(), {"baro": _cond("baro")})
    after = evaluate_capabilities(CAPABILITIES, merged, now=0.0,
                                  compute={}, timing={}, actuators={})
    assert after["altitude_hold"].state == NOT_SUPPORTED
    assert "EVIDENCE_NOT_SUPPORTED" in after["altitude_hold"].reason_codes
    assert not after["altitude_hold"].usable


def test_the_loss_propagates_to_dependents_but_not_beyond():
    """`stable_flight` requires altitude_hold, so it falls too.
    `absolute_navigation` does not, so it must NOT -- a loss that spreads
    everywhere is as useless as one that spreads nowhere."""
    merged = bridge.apply(_all_supported(), {"baro": _cond("baro")})
    rep = evaluate_capabilities(CAPABILITIES, merged, now=0.0,
                                compute={}, timing={},
                                actuators={"elevon_left": True,
                                           "elevon_right": True})
    assert rep["altitude_hold"].state == NOT_SUPPORTED
    assert rep["stable_flight"].state == NOT_SUPPORTED
    assert rep["absolute_navigation"].state == SUPPORTED
    assert rep["attitude_hold"].state == SUPPORTED


def test_losing_gps_leaves_relative_navigation_alone():
    """The contract says relative navigation does NOT require GNSS. The
    bridge must not be the thing that quietly makes it require it."""
    merged = bridge.apply(_all_supported(), {"gps": _cond("gps")})
    rep = evaluate_capabilities(CAPABILITIES, merged, now=0.0,
                                compute={}, timing={}, actuators={})
    assert rep["absolute_navigation"].state == NOT_SUPPORTED
    assert rep["relative_navigation"].state == SUPPORTED


def test_losing_an_unmapped_sensor_changes_no_capability():
    """And that is REPORTED, not silent. `vibration` has no evidence id, so
    its loss cannot reach the capability layer -- which is a limit to state,
    not a result to present as 'no impact'."""
    merged = bridge.apply(_all_supported(), {"vibration": _cond("vibration")})
    assert merged == _all_supported()
    rep = bridge.report(_all_supported(), {"vibration": _cond("vibration")})
    assert rep["sensors_lost_with_no_evidence_mapping"] == ["vibration"]
    assert rep["evidence_withdrawn"] == []


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def test_the_report_names_what_was_withdrawn_and_what_could_not_be():
    rep = bridge.report(_all_supported(),
                        {"baro": _cond("baro"),
                         "motor_esc": _cond("motor_esc")})
    assert rep["sensors_lost"] == ["baro", "motor_esc"]
    assert rep["evidence_withdrawn"] == ["baro.altitude.supported"]
    assert rep["sensors_lost_with_no_evidence_mapping"] == ["motor_esc"]
    assert "never grants it" in rep["demote_only"]


def test_it_accepts_a_bare_set_of_sensor_names():
    """Callers that have names rather than conditions should not have to
    fabricate condition objects to ask the question."""
    assert bridge.evidence_overrides({"baro"}).keys() == \
        bridge.evidence_overrides({"baro": _cond("baro")}).keys()


#: MEASURED, not hoped for. Three mapped sensors move no capability, for two
#: DIFFERENT reasons, and collapsing them into one number would hide that:
#:
#:   imu1  -- correct. `imu.reference.supported` is an ALTERNATIVE path in a
#:            requires_one_of; losing it while the primary survives is
#:            exactly the case the contract set is built to tolerate.
#:   mag,  -- a gap in the XR-1 CONTRACT SET, not in this bridge.
#:   battery  `mag.field.supported` and `power.telemetry.supported` are
#:            declared evidence ids that NO capability and NO product
#:            contract requires, so withdrawing them cannot reach anything.
#:            The withdrawal is still correct and still logged.
MOVES_A_CAPABILITY = {"baro", "gps", "imu0"}
MOVES_NOTHING = {"imu1", "mag", "battery"}


@pytest.mark.parametrize("sensor", sorted(bridge.SENSOR_EVIDENCE))
def test_the_measured_reach_of_each_mapped_sensor(sensor):
    """Pins what each loss actually does today, in both directions, so a
    change to the contracts or the mapping shows up here rather than
    silently widening or narrowing the bridge's reach."""
    actuators = {"elevon_left": True, "elevon_right": True}
    base = evaluate_capabilities(CAPABILITIES, _all_supported(), now=0.0,
                                 compute={}, timing={}, actuators=actuators)
    merged = bridge.apply(_all_supported(), {sensor: _cond(sensor)})
    after = evaluate_capabilities(CAPABILITIES, merged, now=0.0,
                                  compute={}, timing={}, actuators=actuators)
    changed = [c for c in base if base[c].state != after[c].state]

    if sensor in MOVES_A_CAPABILITY:
        assert changed, f"losing {sensor} should reach the capability layer"
    else:
        assert sensor in MOVES_NOTHING
        assert not changed, (
            f"losing {sensor} now moves {changed}; if that is intended, "
            "move it between the two sets and say why")
    # Either way the withdrawal itself happened.
    assert bridge.evidence_overrides({sensor: _cond(sensor)})


def test_the_evidence_that_gates_nothing_is_named():
    """`mag.field.supported` and `power.telemetry.supported` are declared and
    required by NOTHING -- no capability contract and no product contract.
    Withdrawing them is correct and reaches nobody. That is a property of
    the XR-1 contract set worth failing on if it changes, in either
    direction: if a contract starts requiring them, the bridge's reach grows
    and somebody should know."""
    required = set()
    for c in CAPABILITIES:
        required |= set(c.requires_all)
        for group in c.requires_one_of:
            required |= set(group)
    orphans = {"mag.field.supported", "power.telemetry.supported"}
    assert orphans <= set(EVIDENCE), "these ids must still be declared"
    assert not (orphans & required), (
        "a capability now requires evidence that previously gated nothing; "
        "MOVES_NOTHING above is stale")


def test_losing_one_imu_degrades_rather_than_kills():
    """The alternative path is USED, and reported as the degraded route it
    is -- not silently treated as full support."""
    merged = bridge.apply(_all_supported(), {"imu0": _cond("imu0")})
    rep = evaluate_capabilities(CAPABILITIES, merged, now=0.0,
                                compute={}, timing={},
                                actuators={"elevon_left": True,
                                           "elevon_right": True})
    att = rep["attitude_hold"]
    assert att.state == DEGRADED_SUPPORTED
    assert att.alternative_path_selected == "imu.reference.supported"
    assert att.usable, "a declared alternative path is still usable"
    # and the degradation carries to everything resting on it
    assert rep["stable_flight"].state == DEGRADED_SUPPORTED
