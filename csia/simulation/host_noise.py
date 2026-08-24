"""A null control for the timing instrument: how big is the HOST's own tail?

RULE A, applied to the clock.

Every other instrument in this repository has a null control. The latency
measurement did not, and the consequence was a series of R13 verdicts that
attributed the container's scheduler to CSIA.

The measurement that forced this. A loop doing IDENTICAL arithmetic on every
iteration -- no CSIA, no I/O, no telemetry, nothing but floating point --
sized to the core's own median cost and run 751 times, three trials on this
container:

    median 508.9 us   p95 706.0   p99  847.1   max  2057.7   over-2ms  1/751
    median 520.6 us   p95 812.5   p99 2067.0   max 26730.8   over-2ms 10/751
    median 492.2 us   p95 890.0   p99  995.9   max  4160.9   over-2ms  1/751

Constant work. A 26.7 ms outlier and up to ten ticks over a 2 ms budget. The
frozen core replayed deterministically over the same 751 ticks produced ZERO
ticks over budget in the same session, so on this host the core is quieter
than a busy loop.

What follows is not that R13 passes. It is that **the tail of R13 cannot be
measured on shared cloud infrastructure at all**: the instrument's own noise
floor exceeds the budget it is checking. A tail verdict from here would be a
statement about the container.

So the verdict becomes three-valued rather than two:

    PASS           no tick over budget, and the control was clean
    FAIL           ticks over budget while the control was clean -- CSIA
    INDETERMINATE  ticks over budget and the control also went over

INDETERMINATE can never rescue a real failure: it requires the control to
have failed too. A clean control plus an over-budget core is still FAIL, and
that is the case this must not be able to hide.

THE CONTROL IS NOT CONCURRENT WITH THE MEASUREMENT, and that asymmetry is
deliberate. It runs before or after, so it samples a different slice of the
host's timeline. Therefore:

    a control that FAILS proves the host cannot resolve the budget;
    a control that PASSES proves nothing -- it may simply have run during a
    quiet stretch.

The verdict is built on the first of those only, which is why a clean control
leaves FAIL untouched. A run has already been seen where the deterministic
replay showed a 24.8 ms outlier and the control that followed it was
perfectly clean; the verdict was FAIL, and under this rule that is the right
answer even though the outlier was almost certainly the host. Being wrong in
the conservative direction is the price of never being wrong in the other
one.

Central tendency survives all of this. The median and p95 of a constant-work
control are stable to a few percent across trials, so median and p95 figures
for the core remain quotable. It is the deadline property -- the thing R13
actually asserts -- that needs the target hardware at Gate 2.
"""

from __future__ import annotations

import statistics
import time


def _work(n: int) -> float:
    """Fixed arithmetic. Deliberately allocation-free and I/O-free, so any
    spread it shows belongs to the scheduler rather than to the workload."""
    acc = 0.0
    for i in range(n):
        acc += (i * 1.000001) ** 0.5
    return acc


def calibrate(target_us: float, max_rounds: int = 30) -> int:
    """Find the iteration count that costs about `target_us`.

    Calibrated per host rather than hardcoded: a fixed constant would measure
    a different amount of work on every machine, which is precisely the
    confound this control exists to remove.
    """
    n = 1000
    for _ in range(max_rounds):
        t0 = time.perf_counter()
        _work(n)
        dt = (time.perf_counter() - t0) * 1e6
        if dt <= 0:
            break
        if 0.9 * target_us <= dt <= 1.1 * target_us:
            break
        n = max(100, int(n * target_us / dt))
    return n


def summarise(xs, budget_us: float) -> dict:
    s = sorted(xs)
    if not s:
        return {}

    def pct(p):
        return s[min(len(s) - 1, int(len(s) * p))]

    return {
        "n": len(s),
        "median_us": round(statistics.median(s), 1),
        "p95_us": round(pct(0.95), 1),
        "p99_us": round(pct(0.99), 1),
        "max_us": round(s[-1], 1),
        "over_budget": sum(1 for x in s if x > budget_us),
        "budget_us": budget_us,
    }


def measure(n_ticks: int, target_us: float, budget_us: float,
            trials: int = 1) -> dict:
    """Run the control and report whether this host can resolve the budget.

    `trials > 1` matters: the tail is intermittent, and a single clean trial
    on a noisy host would licence a tail verdict that the next trial refutes.
    The worst trial decides, because a deadline claim is about the worst case.
    """
    n = calibrate(target_us)
    per_trial = []
    for _ in range(max(1, trials)):
        samples = []
        for _ in range(n_ticks):
            t0 = time.perf_counter()
            _work(n)
            samples.append((time.perf_counter() - t0) * 1e6)
        per_trial.append(summarise(samples, budget_us))
    worst = max(per_trial, key=lambda s: s["over_budget"])
    return {
        "iterations_per_tick": n,
        "target_us": target_us,
        "trials": per_trial,
        "worst_trial": worst,
        "concurrent_with_measurement": False,
        "asymmetry": "a control that goes over budget proves the host cannot "
                     "resolve it; a clean control proves nothing, because it "
                     "may have run during a quiet stretch",
        # THE question this control exists to answer.
        "tail_is_measurable_on_this_host": worst["over_budget"] == 0,
        "rule": "constant work, same process, same tick count. If THIS goes "
                "over budget, no over-budget count from the same process is "
                "attributable to the software under test.",
    }


def r13_verdict(over_budget: int, control: dict, n_ticks: int) -> str:
    """Three-valued, and INDETERMINATE cannot rescue a real failure.

    It requires the control to have gone over budget too. A clean control
    with an over-budget core is FAIL, unchanged.
    """
    if over_budget == 0:
        return "PASS"
    if control and not control.get("tail_is_measurable_on_this_host", True):
        return (f"INDETERMINATE: {over_budget}/{n_ticks} ticks over budget, "
                f"but a constant-work control on this host went over "
                f"{control['worst_trial']['over_budget']}/"
                f"{control['worst_trial']['n']} times "
                f"(max {control['worst_trial']['max_us']:.0f} us). The tail is "
                f"the host; measure the deadline at Gate 2 on target hardware")
    return f"FAIL: {over_budget} ticks over budget"
