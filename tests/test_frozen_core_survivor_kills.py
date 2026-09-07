"""Tests aimed at mutants that SURVIVED the frozen-core mutation probe.

WHERE THE TARGETS CAME FROM
---------------------------
`research/mission/results/MUTATION_PROBE_HYPOTHESIS_FOCUSED.json` lists 24
surviving mutants across `csia/diagnosis/causal.py` (8) and
`csia/diagnosis/hypothesis.py` (16). A survivor is a line the tests EXECUTE
and do not CONSTRAIN: the code ran, the value changed, and nothing noticed.

These tests target the constrainable ones. They are BOUNDARY tests, because
that is what a comparison mutant is: `>=` becomes `>` and only a value
sitting exactly on the threshold can tell the difference. A test that uses
0.9 against a 0.45 threshold executes the line and proves nothing about it.

THE FROZEN CORE IS READ-ONLY HERE. Not one byte of `csia/diagnosis` is
modified. These tests pin what it already does; where a threshold looks
surprising, the test records the measured behaviour rather than asserting
what it ought to be.

ONE SURVIVOR IS PROVABLY UNKILLABLE, and is documented rather than chased --
see `test_documented_equivalent_mutant_in_classify_isolation`. Writing a
test that appeared to kill an equivalent mutant would mean writing a test
that asserts something false.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import math                                                   # noqa: E402

from csia.diagnosis.causal import (KNEE_C, SHARPNESS,          # noqa: E402
                                   SOURCE_DEGRADED,
                                   CausalSharedCauseModel,
                                   normalize_severity)


def consistency_for_severity(target: float) -> float:
    """The consistency value whose severity is exactly `target`.

    Severity is NOT 1 - c: it is a logistic about KNEE_C, and an earlier
    version of this file assumed the linear form and produced 0.973 where
    it expected 0.45. The frozen transform is inverted here rather than a
    magic constant being written down, so the boundary stays exact if the
    knee ever moves -- and a boundary that is not exact tests nothing,
    because a comparison mutant is only visible ON the threshold.
    """
    return KNEE_C + math.log(1.0 / target - 1.0) / (4.0 * SHARPNESS)


#: features are {indicator: (consistency, gate)}; a source's degradation
#: score is the MAX of normalize_severity(c) over its gated indicators.
ON_THRESHOLD = consistency_for_severity(SOURCE_DEGRADED)


def _features(**consistency) -> dict:
    """Build a feature map from indicator -> consistency, all gated in."""
    return {name: (value, 1.0) for name, value in consistency.items()}


def _all_healthy() -> dict:
    return _features(
        phys_battery=1.0, temp_battery=1.0,
        phys_motor_esc=1.0, accel_esc_rpm=1.0,
        phys_vibration=1.0, temp_vibration=1.0, vibration_prop_freq=1.0,
        redundant_imu=1.0, accel_motor_current=1.0,
        phys_gps=1.0, temp_gps=1.0,
        phys_mag=1.0, temp_mag=1.0, heading_course=1.0,
        phys_baro=1.0)


# ---------------------------------------------------------------------------
# causal.py L180-182 -- the ablation flags default ON
# ---------------------------------------------------------------------------

def test_every_reasoning_stage_is_enabled_by_default():
    """SURVIVOR KILL: causal.py L180-182.

    Three ablation flags default to True. Flipping any default to False
    turns off a whole reasoning stage, and no test noticed -- every test
    that cared passed the flag explicitly, so the DEFAULTS were executed
    and never constrained.

    An ablation switch silently defaulting to off is how a paper measures
    an ablated system while believing it measured the full one.
    """
    r = CausalSharedCauseModel()
    assert r.enable_normalization is True
    assert r.enable_topology is True
    assert r.enable_temporal is True
    assert r.enable_contradiction is True
    assert r.enable_independent_alternative is True


def test_the_default_reasoner_actually_runs_the_temporal_stage():
    """The defaults are not just True, they take effect: the default
    reasoner emits a temporal reason code and an ablated one says so."""
    features = _all_healthy()
    features["phys_battery"] = (0.2, 1.0)
    features["phys_motor_esc"] = (0.2, 1.0)

    default = CausalSharedCauseModel()
    default.source_scores(0.0, features)
    enabled = default.assess(1.0, features, "MAIN_POWER_PACK")
    assert "TEMPORAL_DISABLED" not in enabled.reason_codes

    ablated = CausalSharedCauseModel(enable_temporal=False)
    ablated.source_scores(0.0, features)
    off = ablated.assess(1.0, features, "MAIN_POWER_PACK")
    assert "TEMPORAL_DISABLED" in off.reason_codes


# ---------------------------------------------------------------------------
# causal.py L210 -- `deg = score >= SOURCE_DEGRADED`
# ---------------------------------------------------------------------------

def test_the_degradation_threshold_value_is_pinned_from_both_sides():
    """causal.py L210, `score >= SOURCE_DEGRADED`.

    This pins the threshold VALUE: a source just past it is degraded and one
    just short of it is not, so changing 0.45 to anything else is caught.

    IT DOES NOT DISTINGUISH `>=` FROM `>`, AND NOTHING CAN. Severity is a
    logistic about KNEE_C, and no IEEE double input produces a severity
    exactly equal to 0.45 -- searched by walking float neighbours in both
    directions from the analytically inverted point, and again along the
    linear `enable_normalization=False` path, which computes a mean of
    (1 - c). Both come up empty: 1.0 - 0.55 is 0.44999999999999996, and
    there is no float c with 1.0 - c == 0.45 either.

    So that particular comparison mutant is EQUIVALENT IN PRACTICE. It is
    recorded as such rather than chased with a test that would have to
    assert something false to appear to kill it.
    """
    model = CausalSharedCauseModel()

    past = _all_healthy()
    past["phys_battery"] = (ON_THRESHOLD - 0.005, 1.0)     # less consistent
    scored = model.source_scores(0.0, past)["battery"]
    assert scored.degradation_score > SOURCE_DEGRADED
    assert scored.degraded is True

    short = _all_healthy()
    short["phys_battery"] = (ON_THRESHOLD + 0.005, 1.0)    # more consistent
    scored = CausalSharedCauseModel().source_scores(0.0, short)["battery"]
    assert scored.degradation_score < SOURCE_DEGRADED
    assert scored.degraded is False


def test_no_input_can_put_the_severity_exactly_on_the_threshold():
    """The evidence for the equivalence claimed above, as executable code.

    If a future change to KNEE_C, SHARPNESS or SOURCE_DEGRADED ever makes
    the threshold exactly reachable, this test fails and the mutant becomes
    killable -- at which point a boundary test should be written.
    """
    analytic = KNEE_C + math.log(
        1.0 / SOURCE_DEGRADED - 1.0) / (4.0 * SHARPNESS)
    for direction in (-math.inf, math.inf):
        c = analytic
        for _ in range(200):
            c = math.nextafter(c, direction)
            assert normalize_severity(c) != SOURCE_DEGRADED, (
                "the threshold is now exactly reachable; write a real "
                "boundary test for causal.py L210")


# ---------------------------------------------------------------------------
# causal.py L212 -- onset hysteresis, `score < SOURCE_DEGRADED * 0.6`
# ---------------------------------------------------------------------------

def test_onset_is_kept_until_the_source_recovers_well_below_the_threshold():
    """SURVIVOR KILL: causal.py L212.

    Onset time is not forgotten the instant a source stops being degraded.
    It is held until the score falls below 0.6 * SOURCE_DEGRADED, so a
    signal dithering around the threshold does not keep resetting its own
    onset. Both sides of that hysteresis are exercised here.
    """
    reasoner = CausalSharedCauseModel()
    degraded = _all_healthy()
    degraded["phys_battery"] = (0.2, 1.0)
    reasoner.source_scores(5.0, degraded)
    assert reasoner._onset.get("battery") == 5.0

    # Just under the degraded threshold, but ABOVE the release point:
    # the onset must be retained.
    dithering = _all_healthy()
    dithering["phys_battery"] = (consistency_for_severity(
        SOURCE_DEGRADED * 0.8), 1.0)
    reasoner.source_scores(6.0, dithering)
    assert reasoner._onset.get("battery") == 5.0, \
        "onset released while the source was still near the threshold"

    # Well clear: released.
    recovered = _all_healthy()
    recovered["phys_battery"] = (consistency_for_severity(
        SOURCE_DEGRADED * 0.3), 1.0)
    reasoner.source_scores(7.0, recovered)
    assert "battery" not in reasoner._onset


# ---------------------------------------------------------------------------
# causal.py L222 -- strong coupling, `w >= 0.9`
# ---------------------------------------------------------------------------

def test_a_member_coupled_at_exactly_0_9_counts_as_strongly_coupled():
    """SURVIVOR KILL: causal.py L222, `w >= 0.9`.

    The shipped topology has couplings of 1.0 and 0.3, so no shipped
    scenario can tell `>=` from `>` at 0.9. A custom topology can.
    """
    topology = {"RIG": {"battery": 0.9, "motor_esc": 0.89}}
    reasoner = CausalSharedCauseModel(topology=topology)
    features = _all_healthy()
    features["phys_battery"] = (0.1, 1.0)
    features["phys_motor_esc"] = (0.1, 1.0)

    assessment = reasoner.assess(1.0, features, "RIG")
    # battery (0.9) is strong and degraded; motor_esc (0.89) is not strong,
    # so it cannot appear among the strongly-coupled degraded members.
    assert "battery" in assessment.degraded_members
    assert "motor_esc" not in assessment.degraded_members, (
        "0.89 was treated as strong coupling; this distinguishes >= from >")


# ---------------------------------------------------------------------------
# a survivor that CANNOT be killed
# ---------------------------------------------------------------------------

def test_documented_equivalent_mutant_in_classify_isolation():
    """`hypothesis.py` L636 `if named > truth:` is an EQUIVALENT MUTANT.

    By the time control reaches that line, `named == truth` has already
    returned from the branch above it. So on every reachable input
    `named > truth` and `named >= truth` agree, and no test can distinguish
    them. The mutant survives because it changes nothing, not because the
    tests are weak.

    This is recorded rather than chased. `tools/xr/equivalent_mutants.py`
    treats REAL_GAP as its default verdict and found no provable
    equivalents in the mission layer; this is one in the frozen core, found
    by reading the branch that guards it.

    The test below demonstrates the guarding branch really does return
    first, which is what makes the equivalence hold.
    """
    from csia.diagnosis import (HypothesisClass, IsolationOutcome,
                                classify_isolation)

    class _H:
        def __init__(self):
            self.hypothesis_id = "H"
            self.hypothesis_class = HypothesisClass.SINGLE_SOURCE.value
            self.confidence = 0.9
            self.affected_sources = ("gps",)
            self.shared_resource = None

    class _R:
        most_probable_root_cause = "H"
        affected_sources = ("gps",)
        hypotheses = [_H()]

    # named == truth returns here, so the `named > truth` line below is
    # only ever reached when the two sets differ.
    assert classify_isolation(_R(), ("gps",)) == \
        IsolationOutcome.CORRECT_SINGLE_SOURCE.value
