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


# --------------------------------------------------------------------------
# A verdict nobody could issue is a false affordance.

def test_heading_reference_late_is_reachable():
    """HEADING_REFERENCE_LATE was declared in VERDICTS and returned nowhere.

    It now measures what the write-up previously only asserted: that the
    observation window lies entirely inside the aligned period. The probe
    arms and then observes, so alignment before arming IS that property.
    """
    from csia.simulation.ulog_check import VERDICTS, assess
    t = [0.0, 1.0, 2.0, 3.0, 4.0]
    flags = {"cs_yaw_align": [0, 0, 0, 1, 1], "cs_mag": [0, 0, 0, 1, 1]}
    late = assess(t, flags, armed_at_s=1.0)
    assert late["verdict"] == "HEADING_REFERENCE_LATE"
    assert late["verdict"] in VERDICTS
    assert "WITHOUT a heading reference" in " ".join(late["notes"])


def test_aligning_before_arming_is_valid_and_reports_the_margin():
    from csia.simulation.ulog_check import assess
    t = [0.0, 1.0, 2.0, 3.0, 4.0]
    flags = {"cs_yaw_align": [0, 1, 1, 1, 1], "cs_mag": [0, 1, 1, 1, 1]}
    ok = assess(t, flags, armed_at_s=9.0)
    assert ok["verdict"] == "HEADING_REFERENCE_VALID"
    assert ok["source"] == "MAGNETOMETER"
    assert "8.000 s BEFORE" in " ".join(ok["notes"])


def test_without_an_arming_time_the_verdict_is_unchanged():
    # Not every platform logs one. Absence of the check must not invent a
    # failure, and must not claim the margin either.
    from csia.simulation.ulog_check import assess
    t = [0.0, 1.0, 2.0]
    flags = {"cs_yaw_align": [0, 1, 1], "cs_mag": [0, 1, 1]}
    out = assess(t, flags)
    assert out["verdict"] == "HEADING_REFERENCE_VALID"
    assert out["armed_at_s"] is None
    assert "BEFORE the vehicle armed" not in " ".join(out["notes"])


def test_a_heading_lost_mid_run_outranks_the_late_check():
    from csia.simulation.ulog_check import assess
    t = [0.0, 1.0, 2.0, 3.0]
    flags = {"cs_yaw_align": [0, 1, 1, 0]}
    assert assess(t, flags, armed_at_s=9.0)["verdict"] == \
        "HEADING_REFERENCE_LOST"


def test_never_aligning_is_still_the_strongest_finding():
    from csia.simulation.ulog_check import assess
    out = assess([0.0, 1.0], {"cs_yaw_align": [0, 0]}, armed_at_s=0.5)
    assert out["verdict"] == "NO_HEADING_REFERENCE"


# --------------------------------------------------------------------------
# Gate 2: the measurement that cannot be taken here, made ready to take there.

def test_gate2_reads_the_real_processor_model_not_the_model_number():
    """On x86 `/proc/cpuinfo` has `model : 207` one line above `model name`.

    The first version prefix-matched line by line and reported the processor
    as "207".
    """
    sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))
    from gate2_timing import platform_identity
    ident = platform_identity()
    assert ident["processor_model"] not in ("", "unknown")
    assert not ident["processor_model"].isdigit()
    assert ident["cpu_count"] and ident["machine"]


def test_gate2_refuses_to_certify_an_unconstrained_scheduler():
    sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))
    from gate2_timing import scheduling_environment
    env = scheduling_environment()
    # This container is SCHED_OTHER on 4 shared cores with no cpufreq. Every
    # certification precondition must be reported false, and the fields must
    # be present either way so a later run can be compared against them.
    assert env["suitable_for_certification"] is False
    for key in ("policy", "realtime_policy", "pinned", "governor_fixed",
                "affinity", "cpu_governor"):
        assert key in env


def test_gate2_treats_an_unreadable_governor_as_not_certifiable():
    """Unknown is not acceptable.

    A platform with no cpufreq sysfs has its clock rate decided by something
    this process cannot see, and a deadline measured under an invisible clock
    rate is not certifiable -- the same error as reading a silent diagnostic
    channel as a quiet vehicle.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))
    import gate2_timing
    env = gate2_timing.scheduling_environment()
    if env["cpu_governor"] is None:
        assert env["governor_fixed"] is None
        assert env["suitable_for_certification"] is False


def test_out_of_range_was_removed_rather_than_left_unproduced():
    """A vocabulary member with no producer is a promise the system breaks.

    And this one should never gain a producer: dropping "physically
    impossible" sensor values would discard exactly the evidence CSIA exists
    to notice.
    """
    from csia.aircraft.sample import MissingReason
    assert not hasattr(MissingReason, "OUT_OF_RANGE")
    # Every remaining member is emitted by some code path.
    assert {m.name for m in MissingReason} == {
        "NOT_RECEIVED", "STALE", "NO_3D_FIX", "SENTINEL",
        "FIELD_ABSENT", "NOT_QUALIFIED", "STUB"}
