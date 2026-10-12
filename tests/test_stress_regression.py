"""The stress regression gate, and the determinism that lets it be exact.

The campaign is bit-for-bit deterministic, so the gate compares exactly
instead of against a tolerance band. These tests establish both halves:
that determinism actually holds (otherwise an exact gate would be a
permanent false alarm), and that the comparison distinguishes UNCHANGED,
CHANGED and NOT_COMPARABLE.

`compare()` is exercised on synthetic records rather than by perturbing
the frozen core, because the frozen core is read-only and a gate should be
testable without touching the thing it guards.
"""

from __future__ import annotations

import json
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.xr.stress_regression import (BASELINE, COMPARED,  # noqa: E402
                                        SEED, compare)


def _record(**overrides):
    run = {"escalated": True, "peak_failsafe_level_name": "CAUTION",
           "detection_latency_s": 1.04, "recovery_status": "RECOVERED",
           "recovery_time_s": 5.04, "targets_named": ["gps"],
           "targets_nameable_but_never_named": []}
    run.update(overrides)
    return {"schema": "csia.stress.baseline/1", "seed": SEED, "count": 1,
            "applicability_fingerprint": "abc123", "runs": {"rand_00000": run}}


# ---------------------------------------------------------------------------
# determinism -- the premise of an exact gate
# ---------------------------------------------------------------------------

def test_the_campaign_is_bit_for_bit_deterministic():
    """WITHOUT THIS, AN EXACT GATE WOULD BE A PERMANENT FALSE ALARM.

    Kept small so it runs in the normal suite; the gate itself uses 200.
    """
    import logging
    logging.disable(logging.CRITICAL)
    from csia_stress.campaign import random_profile
    from csia_stress.observables import run_profile

    def once():
        rng = random.Random(4242)
        out = []
        for i in range(3):
            run = run_profile(random_profile(rng, i))
            out.append({k: run.to_dict()[k] for k in
                        ("escalated", "peak_failsafe_level_name",
                         "final_failsafe_level", "min_trust_per_node")})
        return json.dumps(out, sort_keys=True)

    assert once() == once()


# ---------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------

def test_identical_records_are_unchanged():
    base = _record()
    assert compare(_record(), base)["verdict"] == "UNCHANGED"


@pytest.mark.parametrize("field,value", [
    ("escalated", False),
    ("peak_failsafe_level_name", "EMERGENCY"),
    ("detection_latency_s", 2.5),
    ("recovery_status", "NOT_RECOVERED"),
    ("recovery_time_s", 9.9),
    ("targets_named", ["gps", "mag"]),
    ("targets_nameable_but_never_named", ["mag"]),
])
def test_every_compared_field_is_actually_compared(field, value):
    """A field listed in COMPARED but not diffed would be a gate that looks
    thorough and checks nothing -- one entry per field, so none can be
    silently dropped."""
    assert field in COMPARED
    report = compare(_record(**{field: value}), _record())
    assert report["verdict"] == "CHANGED"
    assert [c["field"] for c in report["changes"]] == [field]


def test_recovery_time_is_one_of_the_compared_fields():
    """This is what makes it a RECOVERY-TIME regression gate and not just a
    detection gate."""
    assert "recovery_time_s" in COMPARED


@pytest.mark.parametrize("field,value", [
    ("seed", 1), ("count", 999), ("applicability_fingerprint", "different"),
])
def test_a_different_experiment_is_not_comparable(field, value):
    """MX-015's rule, applied here: a baseline recorded under a different
    seed, count or applicability matrix is not a baseline for this run."""
    measured = _record()
    measured[field] = value
    report = compare(measured, _record())
    assert report["verdict"] == "NOT_COMPARABLE"
    assert [n["field"] for n in report["not_comparable"]] == [field]
    assert report["changes"] == [], (
        "an incomparable pair must not also report differences; they would "
        "be differences between two experiments")


def test_not_comparable_is_not_a_pass():
    measured = _record()
    measured["seed"] = 999
    assert compare(measured, _record())["verdict"] != "UNCHANGED"


def test_a_new_or_missing_profile_is_reported():
    base = _record()
    measured = _record()
    measured["runs"]["rand_00001"] = dict(measured["runs"]["rand_00000"])
    report = compare(measured, base)
    assert report["verdict"] == "CHANGED"
    assert report["profiles_appeared"] == ["rand_00001"]

    report = compare(base, measured)
    assert report["profiles_vanished"] == ["rand_00001"]


def test_there_is_no_tolerance_band():
    """A tolerance here is where a behavioural change would hide, and the
    campaign's determinism means none is needed.

    Asserted BEHAVIOURALLY rather than by scanning the source for the word
    "tolerance": the first version of this test did that and failed on the
    module's own docstring explaining why there is none.
    """
    tiny = compare(_record(recovery_time_s=5.0400001), _record())
    assert tiny["verdict"] == "CHANGED", "a tolerance band crept in"
    almost = compare(_record(detection_latency_s=1.0400001), _record())
    assert almost["verdict"] == "CHANGED"


# ---------------------------------------------------------------------------
# the committed baseline
# ---------------------------------------------------------------------------

def test_the_committed_baseline_is_well_formed():
    if not os.path.exists(BASELINE):
        pytest.skip("no stress baseline recorded yet")
    with open(BASELINE, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["seed"] == SEED
    assert doc["count"] >= 100, "too few runs to be a useful gate"
    assert len(doc["runs"]) == doc["count"]
    assert doc["applicability_fingerprint"]
    for pid, run in doc["runs"].items():
        for field in COMPARED:
            assert field in run, f"{pid} is missing {field}"
