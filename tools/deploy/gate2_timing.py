"""Gate 2 R13 measurement, ready to run on the target companion computer.

WHAT THIS IS FOR.

"Measure R13 on target hardware at Gate 2" has been a sentence in a document
for a while. This makes it a command. It cannot produce the ARM number from a
cloud container -- nothing can -- but it removes everything between someone
holding the hardware and that number, and it refuses to certify a result the
conditions do not support.

    python tools/deploy/gate2_timing.py FLIGHT_LOG.jsonl

Needs no autopilot, no SITL, no simulator, no network and no pymavlink: it
replays a recorded shadow flight log through the frozen core. Copy the repo
and one `.jsonl` onto the companion and run it.

WHY A REPLAY IS THE RIGHT MEASUREMENT HERE. R13 is a property of CSIA's
per-tick work, and a replay drives exactly that work with exactly the data a
real flight produced -- same channels, same rates, same gaps, same handoff
pattern. A synthetic loop would measure something else. And it is
deterministic, so the same log gives the same work every time, which is what
makes host-to-host comparison meaningful.

WHAT MAKES A RESULT ADMISSIBLE. Three things, all checked and all recorded:

  1. A HOST-NOISE NULL CONTROL. A loop of constant arithmetic, sized to the
     tick's own cost, run in the same process. On the development container
     this control goes over a 2 ms budget up to ten times in 751 iterations
     with a 26.7 ms outlier -- the instrument's own noise floor exceeds the
     budget it is checking, so no tail verdict from there means anything.
     If the control fails on the target too, the answer is INDETERMINATE and
     the scheduling has to be fixed before the question can be asked.

  2. THE SCHEDULING ENVIRONMENT, read from the kernel rather than assumed:
     policy, priority, affinity, CPU governor, isolated CPUs. A deadline
     measured under SCHED_OTHER on a shared core with on-demand frequency
     scaling is not a deadline measurement. These are recorded whether or not
     they are ideal, because a result whose conditions are unknown cannot be
     compared with anything later.

  3. THE PLATFORM IDENTITY: CPU model, core count, kernel, Python build.
     A number without the machine it came from is not evidence.

The verdict is three-valued and INDETERMINATE never rescues a failure: it
requires the control to have failed as well. See csia/simulation/host_noise.py.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))

from csia.simulation.host_noise import (                   # noqa: E402
    measure as measure_host_noise, r13_verdict)

R13_BUDGET_US = 2000.0


def _read(path, cast=str, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return cast(fh.read().strip())
    except (OSError, ValueError):
        return default


def scheduling_environment() -> dict:
    """What the kernel says about how this process is scheduled.

    Read, never assumed, and reported even when it is bad: a timing result
    whose conditions are unknown cannot be compared against a later one.
    """
    env = {
        "policy": "UNKNOWN",
        "priority": None,
        "affinity": None,
        "nice": None,
        "cpu_governor": None,
        "isolated_cpus": _read("/sys/devices/system/cpu/isolated", str, ""),
        "nohz_full": _read("/sys/devices/system/cpu/nohz_full", str, ""),
    }
    policies = {}
    for name in ("SCHED_OTHER", "SCHED_FIFO", "SCHED_RR", "SCHED_BATCH",
                 "SCHED_IDLE", "SCHED_DEADLINE"):
        value = getattr(os, name, None)
        if value is not None:
            policies[value] = name
    try:
        env["policy"] = policies.get(os.sched_getscheduler(0), "UNKNOWN")
        env["priority"] = os.sched_getparam(0).sched_priority
    except (AttributeError, OSError):
        pass
    try:
        env["affinity"] = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        pass
    try:
        env["nice"] = os.nice(0)
    except (AttributeError, OSError):
        pass
    gov = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    env["cpu_governor"] = gov
    # A real-time policy, pinned CPUs and a fixed governor are what make a
    # deadline measurement mean anything. None of them is required to RUN --
    # all of them are required to CERTIFY.
    env["realtime_policy"] = env["policy"] in ("SCHED_FIFO", "SCHED_RR",
                                               "SCHED_DEADLINE")
    env["pinned"] = bool(env["affinity"]) and len(env["affinity"]) <= 2
    # `is True`, not `is not False`. An unreadable governor -- a container, a
    # VM, a platform with no cpufreq sysfs -- means the frequency is being
    # decided by something we cannot see, and a deadline measured under an
    # invisible clock rate is not certifiable. Treating unknown as acceptable
    # is the same error as treating a silent diagnostic channel as a quiet
    # vehicle. The operator can still RUN it; they cannot certify from it.
    env["governor_fixed"] = gov in ("performance", "powersave") if gov else None
    env["suitable_for_certification"] = bool(
        env["realtime_policy"] and env["pinned"]
        and env["governor_fixed"] is True)
    return env


def platform_identity() -> dict:
    # KEY ORDER OUTSIDE, LINES INSIDE. The first version looped over lines
    # and took the first key that prefix-matched, so on x86 it matched the
    # numeric `model : 207` field that sits one line above `model name` and
    # reported the processor as "207". Prefix matching also needs the
    # separator, or "model" swallows "model name" forever.
    model = None
    cpuinfo = _read("/proc/cpuinfo", str, "")
    lines = cpuinfo.splitlines()
    for key in ("model name", "Model", "Hardware", "cpu model", "CPU part"):
        for line in lines:
            name, sep, value = line.partition(":")
            if sep and name.strip().lower() == key.lower() and value.strip():
                model = value.strip()
                break
        if model:
            break
    return {
        "machine": platform.machine(),
        "processor_model": model or platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "system": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "device_tree_model": _read("/proc/device-tree/model", str),
    }


def summarise(xs) -> dict:
    s = sorted(xs)
    if not s:
        return {}

    def pct(p):
        return s[min(len(s) - 1, int(len(s) * p))]

    return {
        "n": len(s),
        "min_us": round(s[0], 1),
        "median_us": round(statistics.median(s), 1),
        "mean_us": round(statistics.fmean(s), 1),
        "p95_us": round(pct(0.95), 1),
        "p99_us": round(pct(0.99), 1),
        "max_us": round(s[-1], 1),
        "over_budget": sum(1 for x in s if x > R13_BUDGET_US),
        "budget_us": R13_BUDGET_US,
        "median_headroom_x": round(R13_BUDGET_US / statistics.median(s), 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", help="a shadow flight log (.jsonl) recorded "
                                "anywhere; it carries its own data")
    ap.add_argument("--passes", type=int, default=5,
                    help="repeat the identical replay N times. The spread "
                         "across identical work is a measurement of the "
                         "host, and one pass hides it")
    ap.add_argument("--field-mode", action="store_true", default=True)
    ap.add_argument("--bench-mode", dest="field_mode", action="store_false")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    # Imported here rather than at module scope: numpy is needed for the
    # replay but not for the environment report, and a companion that cannot
    # import it should get a clear error at the right moment.
    from profile_core_from_log import replay

    ident = platform_identity()
    sched = scheduling_environment()
    print(f"=== platform: {ident['processor_model']} "
          f"({ident['machine']}, {ident['cpu_count']} cores), "
          f"{ident['system']} {ident['release']}, "
          f"{ident['python_implementation']} {ident['python']}")
    if ident["device_tree_model"]:
        print(f"    device tree: {ident['device_tree_model']}")
    print(f"=== scheduling: policy {sched['policy']} prio {sched['priority']}, "
          f"affinity {sched['affinity']}, governor {sched['cpu_governor']}")
    if not sched["suitable_for_certification"]:
        print("    *** NOT A CERTIFICATION ENVIRONMENT. Missing: "
              + ", ".join(filter(None, [
                  None if sched["realtime_policy"] else
                  "a real-time policy (chrt -f 80 ...)",
                  None if sched["pinned"] else
                  "CPU pinning (taskset -c N ...)",
                  None if sched["governor_fixed"] is True else
                  ("a fixed CPU governor"
                   if sched["cpu_governor"] else
                   "a READABLE CPU governor (none exposed here, so the "
                   "clock rate is set by something invisible to this "
                   "process)")])))

    print(f"=== replaying {os.path.basename(args.log)} x{args.passes}"
          f" (field_mode={args.field_mode})")
    per_pass, worst_over, n_ticks = [], 0, 0
    for i in range(max(1, args.passes)):
        _ticks, per_tick, handoffs, _ = replay(args.log,
                                               field_mode=args.field_mode)
        s = summarise(per_tick)
        s["handoffs_per_tick"] = round(handoffs / max(1, len(per_tick)), 2)
        per_pass.append(s)
        n_ticks = max(n_ticks, s["n"])
        worst_over = max(worst_over, s["over_budget"])
        print(f"    pass {i}: median {s['median_us']:8.1f} us  "
              f"p95 {s['p95_us']:8.1f}  p99 {s['p99_us']:8.1f}  "
              f"max {s['max_us']:9.1f}  over-budget {s['over_budget']:3d}")

    medians = [s["median_us"] for s in per_pass]
    control = measure_host_noise(n_ticks=n_ticks,
                                 target_us=statistics.median(medians),
                                 budget_us=R13_BUDGET_US, trials=3)
    w = control["worst_trial"]
    print(f"=== host-noise control (constant work, same process): "
          f"median {w['median_us']:.0f} us  max {w['max_us']:.0f} us  "
          f"{w['over_budget']}/{w['n']} over budget")

    verdict = r13_verdict(worst_over, control, n_ticks)
    # A verdict is a measurement; CERTIFIED is a measurement plus the
    # conditions that make it transferable. They are reported separately so
    # neither can be mistaken for the other.
    certified = (verdict == "PASS" and sched["suitable_for_certification"])
    print(f"=== R13: {verdict}")
    print(f"=== CERTIFIABLE AT GATE 2: {'YES' if certified else 'NO'}"
          + ("" if certified else
             " -- a PASS under a scheduler nobody constrained is not a "
             "deadline result"))

    result = {
        "requirement": "R13 <= 2 ms per tick",
        "log": os.path.basename(args.log),
        "field_mode": args.field_mode,
        "platform": ident,
        "scheduling": sched,
        "passes": per_pass,
        "median_of_pass_medians_us": round(statistics.median(medians), 1),
        "median_spread_us": round(max(medians) - min(medians), 1),
        "worst_over_budget": worst_over,
        "host_noise_control": control,
        "R13": verdict,
        "certifiable": certified,
        "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "how_to_certify": [
            "run on the TARGET companion computer, not a workstation",
            "chrt -f 80 taskset -c 2 python tools/deploy/gate2_timing.py LOG",
            "set the CPU governor to performance",
            "isolate the core (isolcpus=/nohz_full=) if the platform allows",
            "the host-noise control must show 0 ticks over budget, or the "
            "measurement is about the scheduler",
        ],
    }
    out = args.out or os.path.join(ROOT, "research", "v1_1", "results",
                                   "gate2_timing.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(out, ROOT)}")

    if verdict.startswith("PASS"):
        return 0 if certified else 3
    return 2 if verdict.startswith("INDETERMINATE") else 1


if __name__ == "__main__":
    sys.exit(main())
