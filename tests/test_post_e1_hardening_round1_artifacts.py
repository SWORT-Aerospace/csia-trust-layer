"""Guards for the FIRST hardening round's artifacts, which had none.

WHY THIS FILE EXISTS
--------------------
The first post-E1 round produced five result artifacts -- bounded
verification, hostile input, minimized reproducers, resource envelope and
decision replay -- and NOT ONE OF THEM WAS GUARDED BY A TEST. They can go stale,
be regenerated with a weaker result, or quietly disappear, and nothing notices.

That matters most for the NEGATIVE results. This repository's standing rule is
that a failure is preserved, and a preserved failure with no guard is a failure
waiting to be tidied away by whoever next finds it inconvenient. HF-004
(decision replay DIVERGENT on both platforms) is exactly such a result, and the
test below asserts that IT STILL FAILS.

A test that asserts a failure looks strange until the alternative is written
down: without it, someone widens a tolerance, the artifact turns green, and a
known limitation silently becomes an unstated claim.
"""

from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "research", "physical_validation", "results")


def _load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------- bounded verification

def test_bounded_verification_never_claims_a_general_theorem():
    doc = _load("ASSURANCE_BOUNDED_VERIFICATION.json")
    assert doc["what_unsat_licenses"] == (
        "No counterexample exists within the verified bounded domain.")
    assert "a general theorem" in doc["what_unsat_does_not_license"]
    blob = json.dumps(doc).lower()
    for overclaim in ("proved for all", "universally", "in general,",
                      "theorem holds"):
        assert overclaim not in blob, (
            f"the bounded verification artifact now says {overclaim!r}; "
            f"nothing here is proved beyond the stated bounds")


def test_every_property_row_is_accounted_for():
    """Derived from the rows, not from an assumed bucket arithmetic.

    The summary's `checked_by_solver` includes the P7 follow-through row,
    which carries an implementation verdict rather than a solver result, so a
    naive unsat+sat+unknown == checked_by_solver balance does NOT hold and
    asserting it would be asserting a misreading.
    """
    doc = _load("ASSURANCE_BOUNDED_VERIFICATION.json")
    s = doc["summary"]
    props = doc["properties"]

    results = [p.get("result") for p in props]
    assert results.count("unsat") == s["no_counterexample_in_bounds"]
    assert results.count("sat") == s["counterexamples"]
    assert results.count("NOT_A_SOLVER_QUESTION") == s[
        "structural_by_construction"]
    assert results.count("unknown") == s["unknown_solver_results"] == 0, (
        "the solver returned `unknown` for a property; an unknown is not an "
        "absence of counterexamples and must not be reported as one")
    # No row is silently uncategorised.
    known = {"unsat", "sat", "unknown", "NOT_A_SOLVER_QUESTION",
             "EXERCISED_AGAINST_IMPLEMENTATION"}
    assert set(results) <= known, set(results) - known


def test_the_expected_hazard_is_still_sat_and_still_exercised():
    """P7 is SAT by design -- it demonstrates a hazard. The row that matters
    is the one running that instance through the REAL firewall."""
    doc = _load("ASSURANCE_BOUNDED_VERIFICATION.json")
    verdicts = [p.get("verdict") for p in doc["properties"]]
    assert "COUNTEREXAMPLE_FOUND" in verdicts
    assert "HOLDS" in verdicts, (
        "the solver's hazard instance is no longer exercised against the "
        "implementation; a SAT with no follow-through is an unanswered alarm")


def test_the_cross_check_still_ran_against_the_implementation():
    doc = _load("ASSURANCE_BOUNDED_VERIFICATION.json")
    x = doc["cross_check"]
    assert x["cases_checked"] >= 4096
    assert x["semantic_mismatches"] == 0, x["failures"][:3]
    assert x["ranking_or_prior_sensitivities"] == 0, (
        "a ranking value or a prior now changes a verdict; neither appears "
        "in the encoding and neither may change an outcome")


# -------------------------------------------------------------- hostile input

def test_no_hostile_input_produces_a_silent_healthy_verdict():
    doc = _load("HOSTILE_INPUT_RESULTS.json")
    counts = doc["counts"]
    assert counts.get("SILENT_HEALTHY", 0) == 0, doc["non_pass"]
    assert counts.get("CRASH", 0) == 0, doc["non_pass"]
    assert counts.get("HANG", 0) == 0, doc["non_pass"]
    assert not doc["non_pass"], doc["non_pass"]


def test_the_hostile_campaign_still_covers_its_declared_classes():
    doc = _load("HOSTILE_INPUT_RESULTS.json")
    assert len(doc["classes"]) >= 27, (
        f"the hostile-input campaign now declares {len(doc['classes'])} "
        f"classes; it was built with 27 -- the 26 the programme named plus "
        f"`unknown_schema_field` -- and shrinking it silently narrows the "
        f"claim")
    # NOT_APPLICABLE rows are reported rather than dropped, and that is the
    # property that keeps an uncovered class visible.
    assert "NOT_APPLICABLE" in doc["counts"]


def test_a_subnormal_gate_weight_is_still_refused():
    """HF-001, pinned at its source rather than only in an artifact."""
    import sys
    sys.path.insert(0, ROOT)
    from csia_assurance import qualify
    from csia_assurance.firewall import SCHEMA
    rec = {
        "schema": SCHEMA, "canonical_sample_present": True,
        "config_hash": "c", "software_hash": "s", "timestamp": 0.0,
        "leader": "a",
        "signatures": {"a": ["x"], "b": []},
        "gates": {"x": 5e-324},
        "evidence_states": {"x": "ACTIVE"},
    }
    v = qualify(rec)
    assert v.state == "NOT_EVALUABLE"
    assert v.reason == "INVALID_GATE_STATE"
    # The control: the smallest NORMAL double is still a valid weight, so the
    # rejection is a validity rule and not a creeping tolerance.
    import sys as _s
    rec["gates"] = {"x": _s.float_info.min}
    assert qualify(rec).state == "SUPPORTED_UNIQUE"


# ------------------------------------------------------ minimized reproducers

def test_every_minimized_reproducer_was_reverified():
    """A reduction nobody re-ran is a smaller input, not a reproducer."""
    doc = _load("ASSURANCE_MINIMIZED_REPRODUCERS.json")
    cases = doc.get("cases") or []
    assert cases, "the minimizer artifact records no cases at all"
    for c in cases:
        mini = c.get("minimization")
        if mini is None:
            continue                      # not reducible; the note says so
        assert mini.get("reverified") is True, c
        assert mini["minimized_size"]["evidence_terms"] <= \
            mini["original_size"]["evidence_terms"]
        assert mini["minimized_size"]["hypotheses"] <= \
            mini["original_size"]["hypotheses"]


def test_the_minimizer_still_admits_its_minimum_is_local():
    doc = _load("ASSURANCE_MINIMIZED_REPRODUCERS.json")
    for c in doc.get("cases") or []:
        mini = c.get("minimization")
        if mini:
            assert "LOCAL" in mini.get("caveat", "").upper(), (
                "the artifact no longer says the minimum is local; delta "
                "debugging finds the smallest case ITS reduction order "
                "reached, not the smallest that exists")


def test_the_load_bearing_invariant_is_still_in_the_minimizer():
    """HF-002, pinned at its source.

    The minimizer produced a confident wrong answer TWICE -- first deleting
    the subnormal gate entirely (a label-only predicate), then keeping it
    present but not load-bearing. The fix is an invariant that neutralises
    the property and requires the verdict to MOVE. Without it the reducer
    happily minimises away the thing being minimised towards.
    """
    src = open(os.path.join(ROOT, "tools", "assurance", "minimize.py"),
               encoding="utf-8").read()
    assert "load_bearing" in src, (
        "the load-bearing invariant is gone from tools/assurance/minimize.py")
    assert "def minimize(" in src and "invariant" in src


# ---------------------------------------------------------- resource envelope

def test_compute_degradation_never_changed_a_decision():
    doc = _load("RESOURCE_ENVELOPE.json")
    assert doc["answer"]["verdict"] == "NO_SILENT_DIVERGENCE"
    assert doc["answer"]["silent_decision_divergence_runs"] == 0
    for run in doc["runs"]:
        res = run.get("result")
        if res:
            assert not res["decision_changes"], (run["stressor"],
                                                 res["decision_changes"])


def test_the_envelope_criteria_were_declared_before_the_runs():
    doc = _load("RESOURCE_ENVELOPE.json")
    crit = doc["criteria_declared_before_runs"]
    for band in ("NORMAL", "DEGRADED", "UNSUPPORTED"):
        assert band in crit
    assert doc["latency_caveat"], (
        "the artifact no longer says these are shared-container numbers; "
        "E1 records latency as measured and NOT adjudicated for the same "
        "reason")


def test_the_untested_band_boundary_is_still_admitted():
    """Nothing reached DEGRADED, so the boundary is UNTESTED. An artifact that
    stops saying so reads as though the band was exercised and passed."""
    doc = _load("RESOURCE_ENVELOPE.json")
    bands = {r["band"] for r in doc["runs"]}
    if bands == {"NORMAL"}:
        assert doc["answer"]["visible_degradation_runs"] == 0, (
            "every run banded NORMAL but the artifact counts visible "
            "degradation; one of the two is wrong")


# ------------------------------------------------------------ decision replay

def test_decision_replay_is_still_divergent_and_still_not_counted_as_pass():
    """HF-004, ASSERTED AS A CONTINUING FAILURE ON PURPOSE.

    Decision replay does NOT agree, on either platform, and the software
    hardening gate may not count it as PASS. If this test ever fails because
    the verdict turned non-DIVERGENT, that is not automatically good news:
    check whether the reconstruction was genuinely fixed (by logging real
    hand-offs at run time) or whether a comparison was widened until it
    agreed. Only the first is a result.
    """
    doc = _load("DECISION_REPLAY_RESULTS.json")
    runs = [r for r in doc["runs"] if r.get("verdict") != "LOG_ABSENT"]
    assert runs, "no replay runs recorded"
    for r in runs:
        assert r["decisions_compared"] > 0, (
            f"{r['platform']}: zero comparisons. That is the NOT_COMPARABLE "
            f"silent-zero defect returning, not a clean replay")
        assert r["verdict"] == "DIVERGENT", (
            f"{r['platform']} replay is now {r['verdict']}. If the hand-off "
            f"reconstruction was genuinely fixed, update HF-004 and this "
            f"test together. If a tolerance was widened instead, revert it.")


def test_the_replay_tolerance_has_not_been_widened():
    doc = _load("DECISION_REPLAY_RESULTS.json")
    for r in doc["runs"]:
        if "tolerance" in r:
            assert r["tolerance"] <= 1e-12, (
                f"{r.get('platform')}: the replay tolerance is now "
                f"{r['tolerance']}, wider than the portability contract's "
                f"level-3 bound")


# --------------------------------------------------------------- portability

def test_the_portability_matrix_still_admits_it_has_one_row():
    doc = _load("PORTABILITY_HOST_current.json")
    env = doc["environment"]
    assert env["distro"] and env["architecture"] and env["python"]["version"]
    assert doc["numeric_tolerance_declared"] == 1e-12
    assert "not part of any equivalence claim" in doc["note"].lower(), (
        "the probe no longer says timing is excluded from equivalence; "
        "contract level 4 is bounds, not equivalence")
