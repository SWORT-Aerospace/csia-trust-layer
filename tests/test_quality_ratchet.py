"""The quality ratchet is a gate, and until now it had NO TESTS.

WHY THIS FILE EXISTS
--------------------
`tools/xr/quality_ratchet.py` decides, every night, whether test quality has
fallen. Nothing checked that it could still tell. An unverified gate is the
failure mode this repository has already recorded once: a check that skips
and reads as green.

WHAT IT GUARDS, SPECIFICALLY
----------------------------
MX-015 is in the ledger because a mutation score measured over one test
subset was compared against a conclusion drawn over another, and the decisive
test file was missing from both sides. The ratchet is exactly the place that
error would become automatic -- measure with one subset, compare against a
floor earned under a different one, and read the difference as quality.

So the rule under test is:

    A SCORE IS COMPARABLE TO THE FLOOR ONLY IF THE TARGETS AND THE TEST
    SUBSET MATCH. Otherwise the answer is NOT_COMPARABLE, and

    NOT_COMPARABLE IS NEVER `holds`.

The last line is the one that matters. A comparison that could not be
performed must not read as a comparison that succeeded.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_PATH = os.path.join(ROOT, "tools", "xr", "quality_ratchet.py")
_spec = importlib.util.spec_from_file_location("_quality_ratchet", _PATH)
ratchet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet)


# --------------------------------------------------------------------------
# the fingerprint itself
# --------------------------------------------------------------------------

def _doc(targets, tests):
    return {"targets": list(targets), "test_subset": list(tests)}


def test_fingerprint_ignores_order():
    """A reordered list is the SAME subset and must not read as a change."""
    a = ratchet.subset_fingerprint(_doc(["a.py", "b.py"], ["t1.py", "t2.py"]))
    b = ratchet.subset_fingerprint(_doc(["b.py", "a.py"], ["t2.py", "t1.py"]))
    assert a == b


def test_fingerprint_changes_when_a_test_file_is_added():
    """THE MX-015 CASE. Adding the decisive test file changes the subset."""
    without = ratchet.subset_fingerprint(_doc(
        ["csia/diagnosis/hypothesis.py"],
        ["tests/test_diagnosis.py"]))
    with_it = ratchet.subset_fingerprint(_doc(
        ["csia/diagnosis/hypothesis.py"],
        ["tests/test_diagnosis.py", "tests/test_hypothesis.py"]))
    assert without != with_it


def test_fingerprint_changes_when_a_target_is_dropped():
    a = ratchet.subset_fingerprint(_doc(["a.py", "b.py"], ["t.py"]))
    b = ratchet.subset_fingerprint(_doc(["a.py"], ["t.py"]))
    assert a != b


@pytest.mark.parametrize("doc", [
    {"targets": ["a.py"]},                    # no test_subset
    {"test_subset": ["t.py"]},                # no targets
    {"targets": [], "test_subset": ["t.py"]},  # empty is not a declaration
    {},
])
def test_fingerprint_is_none_when_undeclared(doc):
    """MISSING must stay distinguishable from DIFFERING, not collapse to a
    hash of emptiness that two unrelated artifacts would share."""
    assert ratchet.subset_fingerprint(doc) is None


# --------------------------------------------------------------------------
# the comparison
# --------------------------------------------------------------------------

FP_A = "aaaaaaaaaaaaaaaa"
FP_B = "bbbbbbbbbbbbbbbb"


def _entry(score, fp, **kw):
    out = {"score": score, "subset_fingerprint": fp,
           "killed": 1, "evaluated": 2}
    out.update(kw)
    return out


def test_holds_when_subset_matches_and_score_is_steady():
    r = ratchet.check({"mutation_mission": _entry(0.67, FP_A)},
                      {"mutation_mission": _entry(0.67, FP_A)})
    assert r["verdict"] == "HOLDS"
    assert r["holds"] is True
    assert r["problems"] == [] and r["not_comparable"] == []


def test_regression_when_subset_matches_and_score_fell():
    r = ratchet.check({"mutation_mission": _entry(0.40, FP_A)},
                      {"mutation_mission": _entry(0.67, FP_A)})
    assert r["verdict"] == "REGRESSION"
    assert r["holds"] is False
    assert [p["metric"] for p in r["problems"]] == ["mutation_mission"]


def test_a_drop_within_tolerance_is_not_a_regression():
    """The band is declared in advance and is not zero, because the site
    count reshuffles the sample on any code change."""
    floor = 0.67
    measured = floor - ratchet.MUTATION_TOLERANCE / 2
    r = ratchet.check({"mutation_mission": _entry(measured, FP_A)},
                      {"mutation_mission": _entry(floor, FP_A)})
    assert r["verdict"] == "HOLDS"


def test_changed_subset_is_not_comparable_not_a_regression():
    """A COLLAPSED SCORE OVER A DIFFERENT SUBSET SAYS NOTHING. It must not
    be reported as a quality regression -- that is a false accusation -- and
    it must not be reported as a pass either."""
    r = ratchet.check({"mutation_mission": _entry(0.01, FP_B)},
                      {"mutation_mission": _entry(0.90, FP_A)})
    assert r["verdict"] == "NOT_COMPARABLE"
    assert r["problems"] == []
    assert len(r["not_comparable"]) == 1
    assert r["not_comparable"][0]["reason"] == "SUBSET_CHANGED"


def test_changed_subset_does_not_pass_even_when_the_score_rose():
    """The direction of the difference is irrelevant when the measurements
    are of different things. A RISE over a changed subset is not evidence of
    improvement, so it is not silently accepted."""
    r = ratchet.check({"mutation_mission": _entry(0.99, FP_B)},
                      {"mutation_mission": _entry(0.50, FP_A)})
    assert r["verdict"] == "NOT_COMPARABLE"
    assert r["holds"] is False


@pytest.mark.parametrize("floor_fp,measured_fp", [
    (None, FP_A),
    (FP_A, None),
    (None, None),
])
def test_unfingerprinted_is_not_comparable(floor_fp, measured_fp):
    r = ratchet.check({"mutation_mission": _entry(0.10, measured_fp)},
                      {"mutation_mission": _entry(0.90, floor_fp)})
    assert r["verdict"] == "NOT_COMPARABLE"
    assert r["not_comparable"][0]["reason"] == "UNFINGERPRINTED"
    assert r["holds"] is False


def test_not_comparable_is_never_holds():
    """THE CENTRAL RULE, asserted on its own so it cannot be lost in a
    refactor of the verdict logic."""
    for measured, floor in (
            ({"mutation_mission": _entry(0.9, FP_B)},
             {"mutation_mission": _entry(0.9, FP_A)}),
            ({"mutation_frozen_core": _entry(0.9, None)},
             {"mutation_frozen_core": _entry(0.9, FP_A)}),
    ):
        r = ratchet.check(measured, floor)
        assert r["not_comparable"], "expected an incomparability"
        assert r["holds"] is False, "NOT_COMPARABLE read as a pass"


def test_a_regression_outranks_an_incomparability_in_the_verdict():
    """If one metric genuinely regressed, the run is a REGRESSION even
    though another could not be compared. The weaker verdict must not mask
    the stronger one."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.10, FP_A),
         "mutation_frozen_core": _entry(0.90, FP_B)},
        {"mutation_mission": _entry(0.90, FP_A),
         "mutation_frozen_core": _entry(0.90, FP_A)})
    assert r["verdict"] == "REGRESSION"
    assert r["problems"] and r["not_comparable"]


def test_missing_metric_on_either_side_is_skipped_silently():
    """A metric absent from the floor is not yet ratcheted; that is not a
    failure, and it is not an incomparability either."""
    r = ratchet.check({"mutation_mission": _entry(0.5, FP_A)}, {})
    assert r["verdict"] == "HOLDS"
    r = ratchet.check({}, {"mutation_mission": _entry(0.5, FP_A)})
    assert r["verdict"] == "HOLDS"


def test_coverage_regression_is_still_caught():
    r = ratchet.check({"coverage": {"total_percent": 60.0}},
                      {"coverage": {"total_percent": 88.7}})
    assert r["verdict"] == "REGRESSION"
    assert r["problems"][0]["metric"] == "coverage"


def test_coverage_within_tolerance_holds():
    floor = 88.7
    r = ratchet.check(
        {"coverage": {"total_percent": floor
                      - ratchet.COVERAGE_TOLERANCE / 2}},
        {"coverage": {"total_percent": floor}})
    assert r["verdict"] == "HOLDS"


# --------------------------------------------------------------------------
# the committed floor
# --------------------------------------------------------------------------

def test_the_committed_floor_is_fully_fingerprinted():
    """A floor written without a subset cannot be compared against anything,
    so the nightly would report NOT_COMPARABLE forever. This fails the day
    an unfingerprinted entry is committed."""
    floor = ratchet.load_floor()
    assert floor, "QUALITY_FLOOR.json is missing or empty"
    for key, value in sorted(floor.items()):
        if not key.startswith("mutation_"):
            continue
        assert value.get("subset_fingerprint"), (
            f"{key} has no subset_fingerprint; run --update")
        assert value.get("targets") and value.get("test_subset"), (
            f"{key} must record what it was measured over")


def test_the_committed_floor_fingerprints_match_their_artifacts():
    """The stored fingerprint must be the one the named artifact actually
    produces -- otherwise the floor records a subset nothing was measured
    over."""
    sources = {
        "mutation_mission": "research/mission/results/MUTATION_PROBE.json",
        "mutation_frozen_core":
            "research/mission/results/MUTATION_PROBE_FROZEN_CORE.json",
        "mutation_assurance_baseline":
            "research/mission/results/"
            "MUTATION_PROBE_ASSURANCE_BASELINE.json",
    }
    floor = ratchet.load_floor()
    for key, rel in sorted(sources.items()):
        if key not in floor:
            continue
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            doc = json.load(fh)
        assert floor[key]["subset_fingerprint"] == \
            ratchet.subset_fingerprint(doc), f"{key} floor drifted from {rel}"


def test_the_frozen_core_floor_records_the_subset_that_mx_015_is_about():
    """THE 0.35 IS ONLY MEANINGFUL NEXT TO ITS SUBSET. MX-015 records that
    the frozen-core probe omitted tests/test_hypothesis.py -- the file whose
    subject carries most of the survivors. The floor must keep showing which
    tests produced the number, so nobody reads 0.35 as 'the frozen core's
    mutation score' again.

    This test does NOT require the omission to persist. If the subset is
    later widened to include that file, the fingerprint changes, the ratchet
    says NOT_COMPARABLE, and somebody re-baselines deliberately -- which is
    the intended path, not a failure.
    """
    entry = ratchet.load_floor().get("mutation_frozen_core")
    assert entry, "the frozen-core floor is missing"
    assert entry["test_subset"], "the subset must be recorded"
    assert any("hypothesis" in t for t in entry["targets"]), (
        "hypothesis.py is the file MX-015 is about; it should still be a "
        "target of the frozen-core probe")


def test_tolerances_are_not_silently_widened():
    """DECLARED IN ADVANCE, never widened after seeing a result. If a
    tolerance is genuinely wrong, changing it should require editing this
    test in the same commit and saying why."""
    assert ratchet.MUTATION_TOLERANCE == 0.03
    assert ratchet.COVERAGE_TOLERANCE == 0.5
