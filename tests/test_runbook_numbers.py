"""Every number in the field runbook must still be the code's number.

A runbook is read in a field tent by someone deciding whether what they
are seeing is expected. If it quotes a threshold the code no longer uses,
it will make them accept a wrong reading or chase a correct one. That is
worse than having no runbook.

So the numbers are not transcribed on trust: they are checked here against
the source they came from, and the test fails if either moves.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.deploy.shadow import Mode                          # noqa: E402
from csia.runtime.failsafe import FailsafeConfig             # noqa: E402
from csia.v1_1.staleness import build_runtime_stale_timeouts  # noqa: E402
from csia_supervision import ALREADY_COVERED, DERIVED_FROM   # noqa: E402

RUNBOOK = os.path.join(ROOT, "docs", "FIELD_INTEGRATION_RUNBOOK.md")


@pytest.fixture(scope="module")
def doc():
    """The runbook with all whitespace runs collapsed to single spaces.

    Markdown is hard-wrapped, so a phrase the document really does contain
    can straddle a line break -- "an independent packet\\ncapture" is the
    same sentence as "an independent packet capture", and a test that
    disagrees is testing the wrapping, not the content. This fixture
    already caught itself out that way once.
    """
    if not os.path.exists(RUNBOOK):
        pytest.skip("FIELD_INTEGRATION_RUNBOOK.md is absent")
    with open(RUNBOOK, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


@pytest.mark.parametrize("field,expected", [
    ("arm_time", 10.0), ("dwell_up", 1.0), ("dwell_down", 5.0),
])
def test_the_timing_constants_are_the_code_s(doc, field, expected):
    """An operator predicts the response time from these three."""
    assert getattr(FailsafeConfig(), field) == expected
    assert f"{expected:g}" in doc


@pytest.mark.parametrize("field,expected", [
    ("nav_caution", 0.75), ("heading_caution", 0.60),
    ("struct_critical", 0.60), ("power_critical", 0.70),
    ("att_caution", 0.82), ("att_emergency", 0.70),
])
def test_the_six_trust_thresholds_are_the_code_s(doc, field, expected):
    assert getattr(FailsafeConfig(), field) == pytest.approx(expected)
    assert f"{expected:.2f}" in doc


@pytest.mark.parametrize("platform", ["ardupilot", "px4"])
def test_every_staleness_timeout_is_quoted_correctly(doc, platform):
    """The per-node table is what tells the operator WHEN to expect a
    detection. All sixteen values, both stacks."""
    for node, seconds in sorted(build_runtime_stale_timeouts(platform).items()):
        assert f"{seconds:.3f} s" in doc, (
            f"{platform}.{node} = {seconds:.3f} s is not in the runbook")


def test_the_runbook_states_csia_cannot_command(doc):
    """The single property everything else rests on. If this sentence ever
    leaves the document, the document is dangerous."""
    assert not any(m.may_command for m in Mode)
    lowered = doc.lower()
    assert "no command path" in lowered
    assert "advisory" in lowered


def test_the_runbook_tells_the_operator_not_to_trust_csia_about_csia(doc):
    """H5 must be checked with an INDEPENDENT capture. A system asserting
    its own silence is not evidence of silence."""
    assert "independent packet capture" in doc.lower()
    assert "do not rely on csia to prove csia is silent" in doc.lower()


def test_the_sr001_baseline_table_matches_the_overlay(doc):
    """The left-hand column of the fault table is the SR-001 baseline: for
    seven of eight sensors the frozen policy raises NOTHING on a cut line.
    That is the control for H3, so it has to be right."""
    assert len(DERIVED_FROM) == 7
    assert ALREADY_COVERED == {"gps"}
    for sensor in DERIVED_FROM:
        assert sensor in doc, f"{sensor} is missing from the runbook table"
    assert "NORMAL — no alarm" in doc


def test_the_runbook_does_not_promise_replay_agreement(doc):
    """A runbook that presented replay as a gate would mislead the operator.

    THE REASON CHANGED; THE RULE DID NOT. This test used to require the word
    "divergent", because replay was DIVERGENT on both platforms. HF-018
    closed that (0 of 2248 and 0 of 2242), so the word is gone and the demand
    for it would now force a false statement into the doc.

    What remains true is what the operator actually needs: replay reproduces
    DECISIONS and not VALUES -- ArduPilot puts zero of its decisions within
    the declared tolerance -- the hand-offs are still reconstructed rather
    than logged, and it is not a gate.
    """
    lowered = doc.lower()
    assert "do not treat replay agreement as a gate" in lowered
    assert "values on neither" in lowered, (
        "the runbook no longer says the VALUES are not reproduced; that is "
        "the load-bearing limitation now that the divergence is gone")
    assert "1.80e-05" in lowered, (
        "the runbook must carry the ArduPilot worst-case number, not just "
        "the word 'limitation'")
    assert "reconstructed" in lowered, (
        "the runbook no longer says the hand-offs are reconstructed rather "
        "than logged; that is the weaker-of-two-results caveat on HF-018")


def test_the_runbook_states_the_limits(doc):
    """What CSIA cannot tell you is as load-bearing as what it can."""
    lowered = doc.lower()
    for limit in ("baro", "motor_esc", "multipath", "jamming", "flutter"):
        assert limit in lowered, f"the runbook no longer mentions {limit}"
    assert "structurally unnameable" in lowered


def test_every_hypothesis_has_a_falsifier(doc):
    """A hypothesis with no failing outcome is not a hypothesis."""
    for h in ("H1", "H2", "H3", "H4", "H5", "H6"):
        assert f"**{h} " in doc, f"{h} is missing"
    # One falsifier per hypothesis, at minimum.
    assert doc.lower().count("falsified by") >= 5
    assert "expected to fail" in doc.lower()      # H6, stated up front


def test_the_quoted_ledger_size_is_the_ledger_s_actual_size():
    """The runbook argues from the ledger's size that negative results are
    worth keeping. It had drifted to 51 against a ledger of 54 -- a small
    error, but it is exactly the kind that makes a reader stop trusting
    the other numbers. Coupling it to the file means the next append
    fails this test rather than quietly widening the gap.
    """
    import yaml
    ledger = os.path.join(ROOT, "research", "physical_validation",
                          "FAILURE_LEDGER.yaml")
    if not os.path.exists(ledger):
        pytest.skip("FAILURE_LEDGER.yaml is absent")
    with open(ledger, encoding="utf-8") as fh:
        entries = yaml.safe_load(fh)["entries"]

    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "the ledger has duplicate ids"

    with open(RUNBOOK, encoding="utf-8") as fh:
        text = " ".join(fh.read().split())
    assert f"ledger has {len(entries)} entries" in text, (
        f"the runbook does not say the ledger has {len(entries)} entries")


def test_the_preflight_verdicts_are_described(doc):
    """Including the one that matters: INCONCLUSIVE is not a pass."""
    for verdict in ("READY", "DO_NOT_FLY", "INCONCLUSIVE"):
        assert verdict in doc
    assert "not a pass" in doc.lower()
