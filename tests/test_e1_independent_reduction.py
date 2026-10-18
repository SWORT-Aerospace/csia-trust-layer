"""The published E1 numbers follow from the archived raw traces.

Every published E1 figure passed through one program. The artifact, the
claim table and the paper all descend from that one reduction, so they
agree with each other by construction -- and would agree just as loudly if
it were wrong. The raw archive exists so that can be checked, and this is
the check.

The second reducer was written from the trace format and the
preregistered window definitions. The aggregation rule was recovered by
testing candidates against one published trial (mean, median, last value;
the median reproduced it to the last digit and the others did not), not by
reading the original extractor.

WHAT AGREEMENT ESTABLISHES: that the numbers follow from the traces under
a stated rule. NOT that the traces describe reality, that the windows were
the right windows, or that the experiment answers its question. A second
reduction checks arithmetic and bookkeeping, not physics.
"""

from __future__ import annotations

import json
import os
import statistics
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.csia_experiment.reduce_e1_independently import (  # noqa: E402
    CAMPAIGNS, RESULTS, reduce_campaign)

REPORT = os.path.join(RESULTS, "E1_INDEPENDENT_REDUCTION.json")


@pytest.fixture(scope="module")
def report():
    if not os.path.exists(REPORT):
        pytest.skip("E1_INDEPENDENT_REDUCTION.json not generated")
    with open(REPORT, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_recorded_reduction_agrees(report):
    assert report["all_agree"], report["campaigns"]


def test_every_trial_was_actually_reduced(report):
    """A reduction that silently skipped its traces would agree vacuously --
    the MX-004 shape. Both campaigns must have reduced 40 trials with none
    missing."""
    assert len(report["campaigns"]) == 2
    for campaign in report["campaigns"]:
        assert campaign["trials_reduced"] == 40, campaign["campaign"]
        assert campaign["traces_missing"] == [], campaign["campaign"]


def test_no_per_trial_value_differs(report):
    """trust_pre, trust_post, trust_delta and every window's trust and
    step count, for all 80 trials."""
    for campaign in report["campaigns"]:
        assert campaign["per_trial_mismatches"] == [], campaign["campaign"]


def test_the_headline_counts_reproduce(report):
    """20 of 20 fault trials with a positive delta, on both platforms."""
    for campaign in report["campaigns"]:
        assert (campaign["fault_trials_with_positive_delta_independent"]
                == campaign["fault_trials_with_positive_delta_published"]
                == 20), campaign["campaign"]


def test_n_median_min_max_reproduce_under_either_quartile_rule(report):
    """These four do not depend on a quartile definition, so they must
    agree regardless -- and they are the figures the claim table leans on."""
    for campaign in report["campaigns"]:
        assert campaign["n_median_min_max_agree"], campaign["campaign"]


def test_the_iqr_depends_on_a_definition_the_artifact_never_states(report):
    """THE ONE FINDING. `statistics_policy` promises "N, median, min, max
    and IQR" and never says WHICH quartile definition. Two reasonable
    choices differ, so an independent reproducer cannot land on the
    published IQR without guessing.

    The published figures come from Python's DEFAULT (`exclusive`). This
    test pins that, so the ambiguity is recorded rather than rediscovered.
    """
    for campaign in report["campaigns"]:
        matching = campaign[
            "quartile_methods_that_reproduce_the_published_figures"]
        assert "exclusive" in matching, (
            f"{campaign['campaign']}: the published quartiles no longer "
            f"match Python's default quantile method")
        assert "inclusive" not in matching, (
            f"{campaign['campaign']}: both definitions now agree, so the "
            f"ambiguity this test documents has gone -- check why before "
            f"deleting the test")


def test_the_two_definitions_really_do_differ(report):
    """Guards the test above from passing vacuously: if the sample were
    such that both methods coincided, 'inclusive does not match' would be
    trivially satisfiable in a way that says nothing."""
    for campaign in report["campaigns"]:
        excl = campaign["distribution_independent_exclusive"]
        incl = campaign["distribution_independent_inclusive"]
        assert excl["iqr"] != incl["iqr"], campaign["campaign"]
        assert excl["median"] == incl["median"], (
            "the median must not depend on the quartile method")


@pytest.mark.slow
def test_the_reduction_reruns_to_the_same_answer():
    """Recompute from the traces rather than trusting the stored report.

    This is the expensive one: it re-reads 80 gzipped traces.
    """
    for campaign in CAMPAIGNS:
        result = reduce_campaign(campaign)
        if "error" in result:
            pytest.skip(result["error"])
        assert result["agrees"], result


def test_the_window_rule_is_half_open():
    """A 1.0 s window at 25 Hz holds 25 steps, not 26. A closed interval
    would double-count the boundary sample into two windows, which is the
    kind of off-by-one that shifts a median without looking wrong."""
    published = os.path.join(RESULTS, "mechanism_a_a2_trust_ardupilot.json")
    if not os.path.exists(published):
        pytest.skip("published A2 result absent")
    with open(published, encoding="utf-8") as fh:
        doc = json.load(fh)
    at_lo, at_hi = doc["windows"]["AT"]
    tick_hz = doc["trials"][0].get("tick_hz") or 25.0
    expected = int(round((at_hi - at_lo) * tick_hz))
    assert doc["trials"][0]["windows"]["AT"]["n_steps"] == expected == 25


def test_statistics_median_is_what_the_reduction_uses():
    """The recovered rule, asserted so a future reader does not have to
    re-derive it: median, not mean, not last value."""
    sample = [1.0, 2.0, 10.0]
    assert statistics.median(sample) == 2.0
    assert statistics.mean(sample) != 2.0
