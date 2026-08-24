"""The timing instrument needs a null control, and it must not become an alibi.

Every other instrument here has one. The latency measurement did not, and a
series of R13 verdicts consequently charged the container's scheduler to CSIA.

The danger in fixing it is obvious: a three-valued verdict is one small step
from a way to explain away every real failure. So the rule is narrow and these
tests pin it: INDETERMINATE requires the CONTROL to have failed as well. A
clean control with an over-budget core is FAIL, exactly as before.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.simulation.host_noise import (                        # noqa: E402
    calibrate, measure, r13_verdict, summarise)

CLEAN = {"tail_is_measurable_on_this_host": True,
         "worst_trial": {"over_budget": 0, "n": 751, "max_us": 900.0}}
NOISY = {"tail_is_measurable_on_this_host": False,
         "worst_trial": {"over_budget": 10, "n": 751, "max_us": 26730.8}}


def test_no_over_budget_ticks_is_a_pass():
    assert r13_verdict(0, CLEAN, 751) == "PASS"
    # Even on a noisy host: nothing went over, so there is nothing to explain.
    assert r13_verdict(0, NOISY, 751) == "PASS"


def test_a_clean_control_means_an_over_budget_tick_is_a_failure():
    """The case this must never be able to hide."""
    v = r13_verdict(9, CLEAN, 751)
    assert v.startswith("FAIL")
    assert "INDETERMINATE" not in v


def test_indeterminate_requires_the_control_to_have_failed_too():
    v = r13_verdict(9, NOISY, 751)
    assert v.startswith("INDETERMINATE")
    assert "26731" in v or "26730" in v      # the control's own tail is quoted


def test_a_missing_control_does_not_soften_the_verdict():
    # No control run is not evidence of a noisy host.
    assert r13_verdict(3, None, 751).startswith("FAIL")
    assert r13_verdict(3, {}, 751).startswith("FAIL")


def test_summarise_counts_over_budget_against_the_stated_budget():
    s = summarise([100.0, 500.0, 2500.0, 3000.0], budget_us=2000.0)
    assert s["over_budget"] == 2
    assert s["max_us"] == 3000.0
    assert s["budget_us"] == 2000.0


def test_calibration_lands_near_the_target():
    # Loose bounds on purpose: this runs on shared CI and the point is that
    # the control measures a comparable amount of work, not an exact one.
    n = calibrate(400.0)
    assert n >= 100


def test_the_control_actually_runs_and_answers_its_question():
    out = measure(n_ticks=40, target_us=200.0, budget_us=2000.0, trials=1)
    assert out["trials"] and out["worst_trial"]["n"] == 40
    assert isinstance(out["tail_is_measurable_on_this_host"], bool)
    assert out["worst_trial"]["median_us"] > 0


def test_the_worst_trial_decides():
    # A deadline claim is about the worst case, so one clean trial on a noisy
    # host must not licence a tail verdict.
    out = measure(n_ticks=20, target_us=200.0, budget_us=2000.0, trials=3)
    assert out["worst_trial"]["over_budget"] == max(
        t["over_budget"] for t in out["trials"])
