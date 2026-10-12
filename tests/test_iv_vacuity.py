"""The vacuity audit, and proof that it can catch both kinds of constant.

An auditor for checks-that-cannot-fire is itself a check, so it gets the same
treatment it applies: every verdict it can return is constructed here and must
come back.

The two verdicts that matter are the ones that look identical in a results
table. ``SOUND_BUT_UNEXERCISED`` is zero false certificates out of 3925 with
controls proving the check is reachable. ``VACUOUS_IN_ENVELOPE`` is zero
because zero was the only possible answer. Reporting either as the other is the
defect this whole module exists for.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from csia_independent_validation import vacuity as v

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research/active_evidence/independent_validation/results"


# --- every verdict is reachable ------------------------------------------

def test_a_check_that_fires_both_ways_is_discriminating():
    check = v.Check("x", lambda r: r["a"], positive={"a": True},
                    negative={"a": False})
    rows = [{"a": True}, {"a": False}]
    assert v.verdict(check, v.observe(check, rows)) == v.DISCRIMINATING


def test_a_constant_check_with_working_controls_is_sound_but_unexercised():
    """The good zero. Never fired here, demonstrably able to."""
    check = v.Check("x", lambda r: r["a"], positive={"a": True},
                    negative={"a": False})
    rows = [{"a": False}] * 50
    observed = v.observe(check, rows)
    assert observed["fired"] == 0
    assert v.verdict(check, observed) == v.SOUND_BUT_UNEXERCISED


def test_a_check_declared_constant_over_its_domain_is_vacuous():
    """The bad zero. Constant because constant was the only option."""
    check = v.Check("x", lambda r: True, positive={"a": True},
                    negative={"a": False}, vacuous_over_domain=True,
                    why_vacuous="the domain cannot produce a failing case")
    rows = [{"a": True}] * 50
    assert v.verdict(check, v.observe(check, rows)) == v.VACUOUS_IN_ENVELOPE


def test_a_constant_check_with_no_controls_is_unverified_not_sound():
    """Neither good nor bad, and it must not be reported as either."""
    check = v.Check("x", lambda r: False)
    rows = [{"a": 1}] * 50
    assert v.verdict(check, v.observe(check, rows)) == v.UNVERIFIED


def test_controls_that_do_not_work_do_not_count_as_controls():
    """A 'negative' control that returns True proves nothing."""
    check = v.Check("always", lambda r: True, positive={}, negative={})
    assert check.demonstrated() is False
    rows = [{}] * 10
    assert v.verdict(check, v.observe(check, rows)) == v.UNVERIFIED


def test_no_rows_is_reported_as_no_data():
    check = v.Check("x", lambda r: True, positive={}, negative={})
    assert v.verdict(check, v.observe(check, [])) == v.NO_DATA


def test_rows_the_predicate_cannot_judge_are_excluded_not_counted_false():
    """``None`` means not applicable, and must not be folded into 'did not fire'."""
    check = v.Check("x", lambda r: r.get("a"), positive={"a": True},
                    negative={"a": False})
    observed = v.observe(check, [{"a": True}, {}, {}, {"a": False}])
    assert observed["n"] == 2
    assert observed["fired"] == 1


def test_vacuity_declaration_requires_a_stated_reason():
    """Setting the flag is a confession; the audit carries the confession."""
    check = v.Check("x", lambda r: True, vacuous_over_domain=True,
                    why_vacuous="because the domain is degenerate")
    report = v.audit([check], [{"a": 1}])
    assert report["checks"]["x"]["why_vacuous"]
    assert "x" in report["vacuous"]


def test_the_report_counts_every_verdict_it_returns():
    checks = [
        v.Check("both", lambda r: r["a"], positive={"a": True},
                negative={"a": False}),
        v.Check("never", lambda r: False, positive={"a": True},
                negative={"a": False}),
    ]
    report = v.audit(checks, [{"a": True}, {"a": False}])
    assert sum(report["verdict_counts"].values()) == 2
    assert set(report["verdict_counts"]) == set(v.VERDICTS)


# --- the committed audit, pinned -----------------------------------------

def _audit(partition: str):
    path = RESULTS / f"VACUITY_AUDIT_{partition.upper()}.json"
    if not path.is_file():
        pytest.skip(f"no vacuity audit for {partition}")
    return json.loads(path.read_text())


@pytest.mark.parametrize("partition", ["validation", "final"])
def test_no_check_in_the_committed_audit_is_unverified(partition):
    """UNVERIFIED means a constant nobody can interpret. None may ship."""
    report = _audit(partition)
    assert report["unverified"] == [], (
        f"{report['unverified']} report a constant with no control proving "
        "which kind of constant it is")


@pytest.mark.parametrize("partition", ["validation", "final"])
def test_the_only_vacuous_check_is_the_one_declared_vacuous(partition):
    """Pinned. A second vacuous check appearing is a regression, not a note."""
    report = _audit(partition)
    assert report["vacuous"] == ["gate::pre_safe"]
    entry = report["checks"]["gate::pre_safe"]
    assert entry["rate"] == 1.0
    assert "34 A" in entry["why_vacuous"]


@pytest.mark.parametrize("partition", ["validation", "final"])
def test_the_false_certificate_checks_are_the_good_kind_of_zero(partition):
    """Zero false certificates is a result only because this says so."""
    report = _audit(partition)
    for name in ("false_certificate::point", "false_certificate::change"):
        entry = report["checks"][name]
        assert entry["fired"] == 0
        assert entry["verdict"] == v.SOUND_BUT_UNEXERCISED
        assert entry["demonstrated_both_ways"] is True


@pytest.mark.parametrize("partition", ["validation", "final"])
def test_every_certificate_state_actually_occurs(partition):
    """A state nobody reaches is a branch nobody tested."""
    report = _audit(partition)
    for name, entry in report["checks"].items():
        if name.startswith("certificate_state::"):
            assert entry["fired"] > 0, f"{name} never occurred"
            assert entry["verdict"] == v.DISCRIMINATING
