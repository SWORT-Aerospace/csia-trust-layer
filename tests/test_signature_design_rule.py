"""Pin the self-occlusion design rule against the signature matrix.

    RULE: a feature intended to discriminate hypothesis h must not be gated by
          any gate that h closes.

Generalised from the WP-C2 control experiment: the same GPS relation repairs
`gps_fault` ≡ `nominal` when ungated and repairs nothing when gated by
`gvalid`. What matters is not the physics of the feature but its independence
from the gate the fault itself triggers.

One violation exists today and is known, recorded and unrepairable inside the
current feature set (`gps_fault` / `phys_gps` / `gvalid`). These tests pin the
violation list exactly, so a NEW violation fails the build and the known one
fails the build if it is silently fixed without updating the record.

The gate->closure model lives in `research/`, which is not an installed
package, so it is imported via `importorskip`. The hard production assertions
below stand without it.
"""

import pytest

from csia.diagnosis.bayes import CAUSES

# (hypothesis, feature, gate) triples that violate the rule today.
KNOWN_VIOLATIONS = {("gps_fault", "phys_gps", "gvalid")}


def _audit():
    mod = pytest.importorskip(
        "research.wp_c3.design_rule_audit",
        reason="research/ is not an installed package; run with PYTHONPATH=.")
    return mod


def test_violation_list_is_exactly_the_known_one():
    """A new violation is a regression; a disappeared one needs the record
    updated in the same commit."""
    mod = _audit()
    violations, _, _ = mod.audit(CAUSES)
    found = {(v["hypothesis"], v["feature"], g)
             for v in violations for g in v["closed_by_this_hypothesis"]}
    new = found - KNOWN_VIOLATIONS
    gone = KNOWN_VIOLATIONS - found
    assert not new, (
        f"NEW self-occlusion violation(s): {sorted(new)} — a feature meant to "
        f"discriminate a hypothesis is gated by a gate that hypothesis closes")
    assert not gone, (
        f"violation(s) {sorted(gone)} no longer present — if this was "
        f"repaired, update KNOWN_VIOLATIONS and the WP-C3 record in the same "
        f"commit")


def test_the_known_violation_is_fatal_not_merely_weakening():
    """`phys_gps` is `gps_fault`'s SOLE feature, which is why the hypothesis
    is absorbed into `nominal` rather than merely weakened. If a second
    feature is ever added, this assertion should be revisited deliberately."""
    assert CAUSES["gps_fault"] == ["phys_gps"], (
        "gps_fault's signature changed; re-derive whether the gvalid "
        "violation is still fatal")


def test_imu_repair_did_not_introduce_a_violation():
    """The WP-C3 promotion added attitude_gravity_mag to imu0_bias_drift. It
    is ungated, which is the whole point — assert that stays true."""
    mod = _audit()
    violations, at_risk, _ = mod.audit(CAUSES)
    touched = [v for v in violations + at_risk
               if v["hypothesis"] == "imu0_bias_drift"]
    assert not touched, (
        f"the IMU repair introduced a self-occlusion issue: {touched}")
    assert "attitude_gravity_mag" in CAUSES["imu0_bias_drift"]
