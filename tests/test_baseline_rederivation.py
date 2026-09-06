"""The baseline benchmark, re-derived from the frozen campaign.

WHAT THIS ANSWERS
-----------------
`MUTATION_SURVIVORS.md` reported three integrity-only survivors in
`csia/diagnosis/baselines.py` and concluded that the baselines the paper
compares against rest on "artifact integrity + source freeze" rather than on
behavioural recomputation.

Two things turned out to be true, and they point opposite ways:

  1. THE ORIGINAL FINDING WAS PARTLY A MEASUREMENT ERROR.
     `tests/test_shared_power_baselines.py` exists, asserts `VOTE_C`,
     `DWELL_TICKS`, `D_WINDOW_S` and `D_MIN_SOURCES` against the
     pre-registered protocol, and evaluates all five systems. It was simply
     absent from the mutation campaign's hand-picked test selection. Adding it
     corrects the measurement.

  2. BUT THAT FILE'S RESULT ASSERTIONS READ A STORED ARTIFACT.
     `campaigns/results/shared_power_baseline_v1.json` is committed and read;
     nothing re-derived it from the campaign. That is the same stale-artifact
     shape as `S_0` (EVIDENCE-05), and a constants assertion is a
     SPECIFICATION check, not a behavioural one -- it would pass on a build
     whose baselines computed nonsense from the right constants.

This file supplies the missing behavioural half: it RUNS the five systems over
scenarios drawn from the frozen campaign and compares the verdicts to the
committed artifact.

WHAT WAS MEASURED BEFORE WRITING IT
-----------------------------------
The full 110-scenario benchmark was re-derived and diffed against the committed
artifact. Of the differences:

  * 723 were `tick_cost_us` -- wall-clock timing, not reproducible by
    construction and not a claim;
  * 6 were `A_LEGACY_SINGLE_SOURCE.t_first_detection`, all in the
    `NEGATIVE_INDEPENDENT` dual-IMU family (scenarios 99-104). Their VERDICTS
    are identical -- `fault_detected` and `affected_sources` match exactly --
    so what varies is the tick a legacy single-source rule first crosses on a
    scenario where two independent faults arrive at different times.
  * EVERY OTHER FIELD MATCHED EXACTLY, including every verdict, every
    `shared_vs_independent` call and every `root_cause_supported` flag.

Neither excluded class is load-bearing: grepping
`research/PROSE_NUMERIC_BINDINGS.yaml`, the artifact maps and
`tests/test_shared_power_baselines.py` for `t_first_detection` returns nothing,
and no manuscript binding references this artifact at all.

WHY A SUBSET
------------
The full campaign takes ~64 s. The mutation runner executes its selection once
per mutant, so putting 64 s in the default path would add ~25 minutes to a
campaign. A deterministic subset spanning every family is used instead, and
the selection takes the first three scenarios of EACH family, so coverage is
complete by construction rather than by luck -- a stride-7 subset was tried
first and the coverage guard caught it missing `NEGATIVE_HEALTHY` entirely.
Set `CSIA_BASELINE_FULL=1` to re-derive all 110.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

CAMPAIGN = os.path.join(ROOT, "campaigns",
                        "shared_power_generalization_v1.json")
RESULT = os.path.join(ROOT, "campaigns", "results",
                      "shared_power_baseline_v1.json")

#: Fields that are NOT reproducible and are NOT claims. Each is excluded with
#: a measured reason, not a guess -- see the module docstring.
NON_REPRODUCIBLE_FIELDS = {
    "tick_cost_us": "wall-clock timing; varies per run by construction",
    "t_first_detection": (
        "varies for A_LEGACY_SINGLE_SOURCE on 6 of 110 scenarios, all in the "
        "NEGATIVE_INDEPENDENT dual-IMU family, while every verdict on those "
        "scenarios is identical. No test and no manuscript binding uses it."),
    "t_root_cause": "same class as t_first_detection",
}

#: The verdict fields. These MUST re-derive exactly -- they are what the
#: benchmark claims.
VERDICT_FIELDS = ("fault_detected", "affected_sources", "shared_resource",
                  "shared_vs_independent", "root_cause_supported", "abstained")

#: Scenarios per family. STRATIFIED, NOT A STRIDE: a stride-7 subset was tried
#: first and the coverage guard immediately caught it missing NEGATIVE_HEALTHY
#: entirely. Taking the first N of each family is complete by construction, so
#: the guard can never fail for a reason nobody chose.
PER_FAMILY = 3


def _campaign():
    with open(CAMPAIGN, encoding="utf-8") as fh:
        return json.load(fh)


def _committed():
    with open(RESULT, encoding="utf-8") as fh:
        return json.load(fh)["payload"]


def _selected_indices():
    scenarios = _campaign()["scenarios"]
    if os.environ.get("CSIA_BASELINE_FULL"):
        return list(range(len(scenarios)))
    seen, out = {}, []
    for i, s in enumerate(scenarios):
        family = s["family"]
        if seen.get(family, 0) < PER_FAMILY:
            seen[family] = seen.get(family, 0) + 1
            out.append(i)
    return sorted(out)


def _rederive(indices):
    """Run the five systems over the selected scenarios, as the tool does."""
    from run_shared_power_baseline import evaluate, generate_flight  # noqa

    campaign = _campaign()
    rows = []
    truth = generate_flight()
    for i in indices:
        rows.append(evaluate(campaign["scenarios"][i], truth))
    return rows


# ------------------------------------------------------------------ guards

def test_the_committed_campaign_is_the_one_the_result_cites():
    """A re-derivation against a different campaign proves nothing."""
    assert _campaign()["campaign_aggregate_hash"] == \
        _committed()["campaign_aggregate_hash"]


def test_the_subset_spans_every_family():
    """A subset that stops covering a family silently narrows the check."""
    campaign = _campaign()
    all_families = {s["family"] for s in campaign["scenarios"]}
    covered = {campaign["scenarios"][i]["family"] for i in _selected_indices()}
    missing = sorted(all_families - covered)
    assert not missing, (
        f"the stratified subset misses families {missing}; the selection is "
        f"complete by construction, so this means a family appears in the "
        f"campaign in a way the selector does not see")


def test_every_excluded_field_has_a_stated_reason():
    for field, reason in NON_REPRODUCIBLE_FIELDS.items():
        assert len(reason) > 20, f"{field} is excluded without a real reason"


def test_no_excluded_field_is_a_verdict_field():
    """Excluding a verdict would hollow out the whole check."""
    overlap = set(NON_REPRODUCIBLE_FIELDS) & set(VERDICT_FIELDS)
    assert not overlap, f"verdict field(s) excluded from comparison: {overlap}"


# ------------------------------------------------------- the re-derivation

def test_the_baseline_verdicts_rederive_from_the_frozen_campaign():
    """RUN the five systems and compare verdicts to the committed artifact.

    This is the behavioural half that `test_shared_power_baselines.py` does
    not have: that file asserts the CONSTANTS match the protocol and then
    reads stored results. A build whose baselines computed nonsense from the
    right constants would pass it and fail this.
    """
    indices = _selected_indices()
    rows = _rederive(indices)
    committed = _committed()["scenarios"]

    mismatches = []
    for i, row in zip(indices, rows):
        want, got = committed[i], row
        assert want["scenario_id"] == got["scenario_id"], (
            f"scenario {i} identity drifted: {want['scenario_id']!r} vs "
            f"{got['scenario_id']!r}")
        for system, got_sys in got["systems"].items():
            want_sys = want["systems"][system]
            for field in VERDICT_FIELDS:
                if field not in want_sys:
                    continue
                a, b = want_sys[field], got_sys[field]
                if isinstance(a, list):
                    a, b = list(a), list(b)
                if a != b:
                    mismatches.append(
                        f"scenario[{i}].{system}.{field}: committed {a!r} "
                        f"re-derived {b!r}")

    assert not mismatches, (
        f"{len(mismatches)} baseline verdict(s) do not re-derive from the "
        f"frozen campaign:\n  " + "\n  ".join(mismatches[:15]) +
        "\n\nEither the baselines changed, the campaign changed, or the "
        "committed artifact is stale. Do NOT update the artifact to match -- "
        "find out which.")


def test_the_rederivation_is_sensitive_to_the_baseline_constants():
    """The oracle property: a scalar that does not move is not being derived.

    If perturbing `VOTE_C` leaves every verdict identical, then re-deriving
    the verdicts cannot detect a change to `VOTE_C`, and the three
    baselines mutants remain real gaps no matter what this file asserts.
    """
    import csia.diagnosis.baselines as B

    indices = _selected_indices()
    before = _rederive(indices)

    original = B.VOTE_C
    try:
        B.VOTE_C = 0.0        # no indicator can ever vote faulty
        after = _rederive(indices)
    finally:
        B.VOTE_C = original

    changed = sum(
        1 for a, b in zip(before, after)
        for system in a["systems"]
        for field in VERDICT_FIELDS
        if field in a["systems"][system]
        and a["systems"][system][field] != b["systems"][system][field])
    assert changed > 0, (
        "driving VOTE_C to 0.0 changed no verdict in the subset, so this "
        "re-derivation is not an oracle for the baseline constants and "
        "DIAGNOSIS-04 remains a genuine behavioural gap")
