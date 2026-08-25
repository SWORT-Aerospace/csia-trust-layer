"""Mechanism A against the PX4 passive-link starvation.

`altitude_baro` carried weight on 8.1 % of PX4 ticks because CSIA's shadow link
is never driven. Mechanism A claims fix loss removes the evidence needed to
attribute `gps_fault`. If part of that evidence was already missing for harness
reasons, the headline could be an artifact of the harness.

What settles it is structural: every relation feeding `gps_fault` is gated on
`gvalid`, so fix loss multiplies all of them to zero regardless of prior
weight. Starvation lowers the PRE-fault pool and cannot touch the POST-fault
state. These tests hold that reasoning in place -- if a relation ever stops
being gated on `gvalid`, the argument fails and so do they.

Reads committed artifacts only.
"""

from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIT = os.path.join(ROOT, "research", "v1_1", "results",
                     "MECHANISM_A_LINK_CONFOUND_AUDIT.json")


@pytest.fixture(scope="module")
def audit():
    if not os.path.exists(AUDIT):
        pytest.skip("run tools/simulation/mechanism_a_link_confound_audit.py")
    with open(AUDIT, encoding="utf-8") as fh:
        return json.load(fh)


def test_no_platform_is_confounded(audit):
    """A CONFOUNDED or INDETERMINATE headline is a submission blocker."""
    bad = {p: v for p, v in audit["verdicts"].items()
           if v in ("CONFOUNDED", "INDETERMINATE")}
    assert not bad, f"Mechanism A headline is not safe on: {bad}"


def test_every_relation_feeding_gps_fault_is_gated_on_validity(audit):
    """The whole argument rests on this, so it is checked, not assumed."""
    for plat, row in audit["platforms"].items():
        assert row["every_relation_gated_on_validity_flag"], plat
        for rel, g in row["gate_structure"].items():
            assert g["carries_validity_flag"], (plat, rel,
                                                g["gate_expression"])


def test_the_fault_drives_the_pool_to_exactly_zero(audit):
    """Post-fault evidence must be zero, with a non-empty pool before it."""
    for plat, row in audit["platforms"].items():
        w = row["gps_gate_weight_sum"]
        assert w["control_arm"] > 0, plat
        assert w["fault_arm_post"] == 0.0, (plat, w)
        assert w["fault_arm_late"] == 0.0, (plat, w)


def test_the_injection_was_observed_downstream(audit):
    """RULE B: the parameter write is not the measurement."""
    for plat, row in audit["platforms"].items():
        assert row["rule_b_observable"]["ticks_observed"] > 0, plat


def test_ardupilot_is_unaffected_and_px4_is_narrowed_not_invalidated(audit):
    """The two platforms differ, and the difference must not be blurred."""
    assert audit["verdicts"]["ardupilot"] == "UNAFFECTED"
    assert audit["verdicts"]["px4"] == "PARTIALLY_AFFECTED"
    px4 = audit["platforms"]["px4"]
    assert px4["starved_relations"] == ["altitude_baro"], px4
    # The other two dark relations are NOT harness starvation and must not be
    # reported as though they were.
    dark = px4["dark_before_fault"]
    assert dark["heading_course"]["verdict"] == "DARK_BY_GATE"
    assert dark["velocity_gps_doppler_1"]["verdict"] == "DARK_STRUCTURAL"


def test_the_px4_pool_is_smaller_and_the_reason_is_recorded(audit):
    """1 of 4 relations on PX4 against 3 of 4 on ArduPilot, with causes."""
    ap = audit["platforms"]["ardupilot"]["gps_gate_weight_sum"]["control_arm"]
    px4 = audit["platforms"]["px4"]["gps_gate_weight_sum"]["control_arm"]
    assert ap == 3.0 and px4 == 1.0, (ap, px4)
    assert len(audit["platforms"]["px4"]["dark_before_fault"]) == 3
