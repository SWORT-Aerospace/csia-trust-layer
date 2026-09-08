"""The detection floor turns 31 misses into a stated limit.

WHAT THE SWEEP IS FOR
---------------------
The supervision measurement left 31 misses in 1000 variations, all
sub-threshold `bias_drift`. Lowering a frozen threshold until they detect
would be retuning a frozen core to rescue a result. Measuring WHERE the
boundary is instead converts them into an envelope a mission planner can
use: a miss below a published floor is the declared limit; a miss above one
is a defect.

THE BUG THIS FILE ALSO GUARDS
------------------------------
The first version of the sweep caught every per-point exception and stored
it as a point with no verdict. Those points read as "not detected", and the
sweep confidently reported UNDETECTED_AT_EVERY_MAGNITUDE for all four pairs
-- from an AttributeError on a field name that does not exist. An instrument
bug had been turned into a finding about the frozen core, and it looked
entirely plausible.

So the rule is pinned here: A SWEEP THAT CANNOT MEASURE MUST RAISE, NEVER
RECORD A MISS.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_stress import detection_floor as df                 # noqa: E402

ARTIFACT = os.path.join(ROOT, "research", "stress", "results",
                        "DETECTION_FLOOR.json")


@pytest.fixture(scope="module")
def report():
    if not os.path.exists(ARTIFACT):
        pytest.skip("DETECTION_FLOOR.json not generated")
    with open(ARTIFACT, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# the instrument
# ---------------------------------------------------------------------------

def test_a_bad_detection_status_raises_rather_than_reading_as_a_miss(
        monkeypatch):
    """THE REGRESSION. A point the sweep cannot interpret must stop it."""
    class _Run:
        detection_status = "SOMETHING_ELSE"
        min_trust = {"imu0": 0.5}

    monkeypatch.setattr(df, "run_profile", lambda *a, **k: _Run())
    with pytest.raises(df.SweepInstrumentError):
        df._run_one("bias_drift", "imu0", 0.05, df.SWEEP["bias_drift"], False)


def test_a_missing_trust_value_raises_rather_than_reading_as_a_miss(
        monkeypatch):
    """Without the target's trust the sweep cannot tell 'not seen' from
    'seen, no rule' -- so it must not guess."""
    class _Run:
        detection_status = df.NOT_DETECTED
        min_trust: dict = {}

    monkeypatch.setattr(df, "run_profile", lambda *a, **k: _Run())
    with pytest.raises(df.SweepInstrumentError):
        df._run_one("bias_drift", "imu0", 0.05, df.SWEEP["bias_drift"], False)


def test_sweep_one_does_not_swallow_an_error(monkeypatch):
    """The swallowing happened one level up, so it is pinned there too."""
    def _boom(*a, **k):
        raise RuntimeError("instrument failure")

    monkeypatch.setattr(df, "_run_one", _boom)
    with pytest.raises(RuntimeError):
        df.sweep_one("bias_drift", "imu0")


# ---------------------------------------------------------------------------
# what a floor means
# ---------------------------------------------------------------------------

def test_a_lone_detection_is_not_a_floor(monkeypatch):
    """Detection at one magnitude with misses ABOVE it is noise, not a
    boundary. Taking the first True as the floor would publish a number the
    data does not support."""
    seq = {0.01: False, 0.02: True, 0.03: False, 0.05: False, 0.08: False,
           0.12: False, 0.16: False, 0.20: False, 0.30: False, 0.45: False,
           0.70: False, 1.00: False}
    monkeypatch.setattr(df, "_run_one",
                        lambda k, t, v, s, sup: (seq[v], 0.75))
    out = df.sweep_one("bias_drift", "imu0")
    assert out["shape"] == df.NON_MONOTONIC
    assert out["detection_floor"] is None


def test_a_monotonic_step_is_a_floor(monkeypatch):
    monkeypatch.setattr(df, "_run_one",
                        lambda k, t, v, s, sup: (v >= 0.08, 0.75))
    out = df.sweep_one("bias_drift", "imu0")
    assert out["shape"] == "MONOTONIC"
    assert out["detection_floor"] == 0.08


def test_no_escalation_with_collapsed_trust_is_not_reported_as_unseen(
        monkeypatch):
    """THE DISTINCTION THAT MATTERS. Trust falling to 0.23 while the level
    never moves means the layer saw the fault and no failsafe rule names
    that sensor. Calling that 'undetected' blames the wrong component."""
    monkeypatch.setattr(df, "_run_one",
                        lambda k, t, v, s, sup: (False, 0.23))
    out = df.sweep_one("bias_drift", "baro")
    assert out["shape"] == df.TRUST_RESPONDS_NO_RULE
    assert out["detection_floor"] is None


def test_no_escalation_with_flat_trust_is_reported_as_unseen(monkeypatch):
    monkeypatch.setattr(df, "_run_one",
                        lambda k, t, v, s, sup: (False, 0.80))
    out = df.sweep_one("bias_drift", "imu0")
    assert out["shape"] == df.UNDETECTED


# ---------------------------------------------------------------------------
# the measured result
# ---------------------------------------------------------------------------

def test_every_live_pair_with_declared_parameters_was_swept(report):
    """Six pairs: the four bias_drift targets, plus the two power_sag ones
    added when motor_esc was brought under supervision (SR-008)."""
    assert set(report["pairs_swept"]) == {
        "bias_drift@baro", "bias_drift@imu0",
        "bias_drift@imu1", "bias_drift@mag",
        "power_sag@battery", "power_sag@motor_esc"}


def test_the_motor_esc_floor_is_far_above_the_campaign_range(report):
    """The frozen core needs 2200 rpm lost before anything escalates, more
    than three times the campaign's maximum draw of 700 -- and that
    detection is not motor_esc being judged, it is the fault growing large
    enough to trip some other sensor's rule."""
    motor = report["campaign_range_vs_floor"]["power_sag@motor_esc"]
    assert motor["reach"] == "ENTIRE_CAMPAIGN_RANGE_BELOW_FLOOR"
    assert motor["floor"] >= 2000
    assert motor["campaign_draws"][1] <= 700


def test_baro_never_escalates_at_any_swept_magnitude(report):
    """MEASURED, and it is not a sensing limit: the stimulus reaches the
    stream (a 327 m altitude error at the top of the sweep) and baro trust
    falls to 0.23. `baro` is one of the two sensors SR-001 records the
    frozen policy as not supervising, and this is what that costs."""
    baro = report["campaign_range_vs_floor"]["bias_drift@baro"]
    assert baro["floor"] is None
    assert baro["reach"] == "NEVER_ESCALATES"
    assert "bias_drift@baro" in report["trust_responded_but_no_rule"]

    from csia_supervision.dataloss import UNSUPERVISED_BY_THE_FROZEN_POLICY
    assert "baro" in UNSUPERVISED_BY_THE_FROZEN_POLICY


def test_the_mag_floor_is_above_the_whole_campaign_range(report):
    """So EVERY mag bias_drift in the 1000-variation campaign is below the
    floor. Those misses are the envelope, not a defect."""
    mag = report["campaign_range_vs_floor"]["bias_drift@mag"]
    assert mag["reach"] == "ENTIRE_CAMPAIGN_RANGE_BELOW_FLOOR"
    assert mag["floor"] > mag["campaign_draws"][1]


def test_the_floors_are_consistent_with_the_observed_misses():
    """A WEAK, DEFENSIBLE CHECK, and deliberately not a per-run attribution:
    campaign variations carry 2-4 simultaneous faults, so the per-target
    counts are targets INVOLVED in a missed run and sum to more than the
    number of missed runs. What the floors predict is which pairs are
    structurally out of reach -- and those two, mag and baro, are exactly
    the two that dominate the miss counts."""
    path = os.path.join(ROOT, "research", "stress", "results",
                        "SUPERVISION_EFFECT_1000.json")
    if not (os.path.exists(path) and os.path.exists(ARTIFACT)):
        pytest.skip("campaign or floor artifact absent")
    with open(path, encoding="utf-8") as fh:
        eff = json.load(fh)
    with open(ARTIFACT, encoding="utf-8") as fh:
        floors = json.load(fh)

    out_of_reach = {
        k.split("@")[1] for k, v in floors["campaign_range_vs_floor"].items()
        if v["reach"] in ("ENTIRE_CAMPAIGN_RANGE_BELOW_FLOOR",
                          "NEVER_ESCALATES")}
    assert out_of_reach == {"mag", "baro", "motor_esc"}

    counts = eff["still_undetected_targets"]
    ranked = sorted(counts, key=lambda k: -counts[k])
    # The two most-involved targets are both structurally out of reach.
    assert set(ranked[:2]) <= out_of_reach, (
        f"the most-involved miss targets should be ones the campaign "
        f"cannot reach; ranking was {ranked}")
    # And out-of-reach targets account for the bulk of the involvements.
    # NOT a per-run attribution -- these are targets INVOLVED in a missed
    # run and sum to more than the number of missed runs.
    total = sum(counts.values())
    unreachable = sum(counts.get(t, 0) for t in out_of_reach)
    assert unreachable / total > 0.6, (
        f"only {unreachable}/{total} involvements are structurally "
        "unreachable; the floors no longer explain the misses")


def test_the_artifact_says_nothing_was_tuned(report):
    """The whole point of publishing a floor rather than moving one."""
    assert "No threshold" in report["nothing_was_tuned"]
    assert "declared before the first run" in report["nothing_was_tuned"]


def test_the_sweep_grid_is_declared_not_fitted():
    """A grid widened until it produced an answer would make every floor
    unfalsifiable. Changing it should require editing this test."""
    values = df.SWEEP["bias_drift"]["values"]
    assert values[0] == 0.01 and values[-1] == 1.00
    assert len(values) == 12
    power = df.SWEEP["power_sag"]["values"]
    assert power[0] == 25.0 and power[-1] == 3000.0
    assert len(power) == 12
    for spec in df.SWEEP.values():
        assert list(spec["values"]) == sorted(spec["values"]), \
            "the grid must be ascending"
