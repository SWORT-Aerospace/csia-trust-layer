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

#: Source digests, which are a SEPARATE axis from the subset fingerprint:
#: the fingerprint says what was measured, the digest says what it was
#: measured over. Both must agree before two scores may be compared.
SRC_A = "1111111111111111"
SRC_B = "2222222222222222"


def _entry(score, fp, **kw):
    """A comparable entry: same subset, same source, same site count.

    Provenance defaults to *agreeing* so that a test about scores is about
    scores. Tests that are about provenance override these explicitly.
    """
    out = {"score": score, "subset_fingerprint": fp,
           "killed": 1, "evaluated": 2,
           "targets_digest": SRC_A,           # floor side
           "targets_digest_declared": SRC_A,  # measured side, authoritative
           "targets_digest_live": SRC_A,
           "sites": 100, "sites_recomputed": 100}
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
    # Taken from the tool, never re-typed here: a parallel copy of this
    # mapping is exactly what drifted when the frozen-core metric was
    # repointed at the corrected artifact.
    sources = ratchet.MUTATION_ARTIFACTS
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


# --------------------------------------------------------------------------
# MX-020: the mutation half of the ratchet could not fail
# --------------------------------------------------------------------------
#
# This tool does not run the probes -- it reads committed artifacts, and
# nothing regenerates them. So it was comparing files against a floor derived
# from those same files and reporting HOLDS because both sides were the same
# bytes. These tests pin the three things that fixed it: every floored metric
# is actually compared, a score is tied to the source it was taken over, and
# an artifact that saw a different shape of code is stale regardless of what
# any digest says.


def test_every_mutation_metric_in_the_floor_is_actually_compared():
    """THE DEFECT ITSELF. `mutation_assurance_baseline` sat in the floor,
    was measured on every run, and was left out of the comparison loop --
    a number maintained by hand and gated by nothing."""
    floored = {k for k in ratchet.load_floor()
               if k.startswith("mutation_")}
    assert floored, "the floor records no mutation metrics at all"
    missing = floored - set(ratchet.MUTATION_METRICS)
    assert not missing, (
        f"{sorted(missing)} are stored in the floor but never compared")


def test_a_floored_metric_left_out_of_the_loop_would_be_caught():
    """The test above only holds while MUTATION_METRICS is honest. Verify it
    is the loop's real source of keys, not a list that merely happens to
    agree with one."""
    r = ratchet.check(
        {"mutation_assurance_baseline": _entry(0.10, FP_A)},
        {"mutation_assurance_baseline": _entry(0.90, FP_A)})
    assert r["verdict"] == "REGRESSION", (
        "a fall in the assurance baseline was not reported")


def test_a_score_measured_over_different_source_is_not_comparable():
    """A stored score describes the code it was taken over. Once that code
    changes it is a statement about something that is no longer here."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.90, FP_A, targets_digest_declared=SRC_A,
                                    targets_digest_live=SRC_B)},
        {"mutation_mission": _entry(0.90, FP_A)})
    assert r["verdict"] == "NOT_COMPARABLE"
    assert r["not_comparable"][0]["reason"] == "SOURCE_CHANGED"
    assert r["holds"] is False


def test_a_changed_source_is_not_reported_as_a_regression():
    """Not a false accusation, either. A lower score over changed source is
    unknown, not worse."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.10, FP_A, targets_digest_declared=SRC_A,
                                    targets_digest_live=SRC_B)},
        {"mutation_mission": _entry(0.90, FP_A)})
    assert r["problems"] == []
    assert r["verdict"] == "NOT_COMPARABLE"


def test_a_score_with_no_source_provenance_is_not_comparable():
    """Nothing links the number to any state of the code, so it cannot be
    shown to describe this tree. That is not a pass."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.90, FP_A, targets_digest_declared=None,
                                    targets_digest_live=None)},
        {"mutation_mission": _entry(0.90, FP_A, targets_digest=None)})
    assert r["verdict"] == "NOT_COMPARABLE"
    assert r["not_comparable"][0]["reason"] == "UNKNOWN_SOURCE_PROVENANCE"


def test_the_artifact_s_own_digest_outranks_the_floor_s_record():
    """The floor's digest is captured at --update time and assumes the
    artifact was fresh then. Where the probe recorded what it actually
    measured, that is the better evidence and must win."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.90, FP_A, targets_digest_declared=SRC_B,
                                    targets_digest_live=SRC_B)},
        {"mutation_mission": _entry(0.90, FP_A, targets_digest=SRC_A)})
    assert r["verdict"] == "HOLDS", (
        "the floor's weaker record overrode the artifact's own")
    assert r["source_provenance"]["mutation_mission"]["basis"] == \
        "ARTIFACT_DECLARED"


def test_the_weaker_basis_is_labelled_as_weaker():
    """An artifact that predates the field still gets compared, but the
    report must not present the floor's assumption as the probe's record."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.90, FP_A, targets_digest_declared=None,
                                    targets_digest_live=SRC_A)},
        {"mutation_mission": _entry(0.90, FP_A, targets_digest=SRC_A)})
    assert r["verdict"] == "HOLDS"
    prov = r["source_provenance"]["mutation_mission"]
    assert prov["basis"] == "FLOOR_RECORDED"
    assert "assumes" in prov["means"]


def test_a_drifted_site_count_is_stale_whatever_the_digests_say():
    """An INDEPENDENT staleness signal. The site count is a pure function of
    the targets' syntax, so a disagreement proves the artifact predates the
    code even if a digest was recorded wrongly."""
    r = ratchet.check(
        {"mutation_mission": _entry(0.90, FP_A, sites=100,
                                    sites_recomputed=137)},
        {"mutation_mission": _entry(0.90, FP_A)})
    assert r["verdict"] == "NOT_COMPARABLE"
    nc = r["not_comparable"][0]
    assert nc["reason"] == "SITE_COUNT_DRIFT"
    assert nc["sites_in_artifact"] == 100 and nc["sites_now"] == 137


def test_the_report_admits_the_tool_does_not_run_the_probes():
    """The property that makes the digest check load-bearing rather than
    decorative. If this ever stops being said, a reader will assume the
    numbers were measured on this run."""
    r = ratchet.check({}, {})
    said = " ".join(r["this_tool_does_not_run_the_probes"].split())
    assert "nothing regenerates them" in said
    assert "reads the committed mutation artifacts" in said


def test_the_two_digest_implementations_agree():
    """The probe writes `targets_digest` and this tool checks it. Two
    implementations that drift apart would report drift that is not there,
    so they are pinned to each other over real files."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_mp_probe", os.path.join(ROOT, "tools", "xr", "mutation_probe.py"))
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)

    targets = ["csia/runtime/failsafe.py", "csia/trust_engine/engine.py"]
    assert mp.targets_digest(targets) == ratchet.targets_digest(targets)
    assert mp.targets_digest(targets) is not None


def test_a_missing_target_digests_to_none_rather_than_a_partial_hash():
    """A digest that silently skipped a deleted file would compare equal to
    one taken before the deletion."""
    assert ratchet.targets_digest(["csia/does_not_exist.py"]) is None
    assert ratchet.targets_digest([]) is None


def test_every_metric_has_an_artifact_and_they_are_declared_once():
    """MUTATION_METRICS and MUTATION_ARTIFACTS must agree. A metric with no
    artifact is silently never measured; an artifact with no metric is a
    file nothing gates on."""
    assert set(ratchet.MUTATION_METRICS) == set(ratchet.MUTATION_ARTIFACTS)
    for key, path in ratchet.MUTATION_ARTIFACTS.items():
        assert os.path.exists(os.path.join(ROOT, path)), \
            f"{key} points at a missing artifact: {path}"


def test_the_historical_frozen_core_artifact_is_still_on_disk():
    """MX-015 refers to it. Repointing the GATE at the corrected subset must
    not mean deleting the record that explains why the correction was
    needed -- and it must not be what the gate reads either."""
    historical = os.path.join(
        ROOT, "research/mission/results/MUTATION_PROBE_FROZEN_CORE.json")
    assert os.path.exists(historical), "the MX-015 record was removed"
    with open(historical, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["mutation_score"] == 0.35, "the historical record was edited"
    assert not any("hypothesis" in t for t in doc["test_subset"]), (
        "the historical artifact is defined by the omission MX-015 records")
    assert ratchet.MUTATION_ARTIFACTS["mutation_frozen_core"] != \
        "research/mission/results/MUTATION_PROBE_FROZEN_CORE.json", (
        "the gate must not read the subset MX-015 says was misleading")
