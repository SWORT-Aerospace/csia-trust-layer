"""WP-C6 Part 3 — unconditional gvalid closure statistics from real telemetry.

`gvalid` is a function of `fix_type` and nothing else, and `fix_type` IS
plumbed (`ulog_source.py:178`). So the gate trace is obtainable on today's
ingestion path WITHOUT solving the labelling problem.

This is NOT q_gvalid. The measurement spec forbids substituting an
unconditional rate for the conditional one and that prohibition stands: an
unconditional rate mixes both hypotheses in unknown proportion. What it does
give is a useful bound in one direction. If gvalid essentially never closes in
real flight, then P(closure | any hypothesis) is small and the phenomenon is
rare regardless of conditioning. That is the cheapest available partial answer
to the programme's most important open question.

HARD RULE, from the brief: if no real telemetry is reachable, say so and
specify exactly what is needed. Do NOT simulate and label it real. This script
therefore refuses to fall back to the simulator.

Run:  PYTHONPATH=. python research/wp_c6/gvalid_unconditional.py
Out:  research/wp_c6/results/gvalid_unconditional.json
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RESULTS = os.path.join(os.path.dirname(__file__), "results")
LOG_GLOB = os.path.join(ROOT, "data", "real_logs", "*.ulg")
ARM_TIME_S = 20.0


def probe_availability():
    """What real telemetry can this environment actually reach?"""
    logs = sorted(glob.glob(LOG_GLOB))
    try:
        import pyulog                                   # noqa: F401
        pyulog_ok = True
    except ImportError:
        pyulog_ok = False
    return {
        "log_glob": os.path.relpath(LOG_GLOB, ROOT),
        "n_ulg_files_present": len(logs),
        "pyulog_installed": pyulog_ok,
        "corpus_report_present": os.path.exists(
            os.path.join(ROOT, "data", "real_logs_report.json")),
    }


def measure(logs):
    """Per-flight gvalid closure statistics. Only called with real logs."""
    from csia.runtime.ulog_source import UlogSource            # noqa: E402
    rows = []
    for path in logs:
        src = UlogSource(path)
        events = [e for e in src.events() if e[1] == "gps"]
        if not events:
            rows.append({"log": os.path.basename(path),
                         "status": "no gps topic"})
            continue
        t0 = events[0][0]
        applicable = [(t - t0, bool(p.get("valid")))
                      for t, _, p in events if t - t0 >= ARM_TIME_S]
        if not applicable:
            rows.append({"log": os.path.basename(path),
                         "status": "shorter than arm window"})
            continue
        closed = [not v for _, v in applicable]
        # contiguous closure runs
        runs, cur = [], 0
        for c in closed:
            if c:
                cur += 1
            elif cur:
                runs.append(cur)
                cur = 0
        if cur:
            runs.append(cur)
        rows.append({
            "log": os.path.basename(path),
            "status": "ok",
            "applicable_samples": len(applicable),
            "closed_samples": sum(closed),
            "occupancy": round(sum(closed) / len(applicable), 6),
            "n_closure_runs": len(runs),
            "longest_run_samples": max(runs) if runs else 0,
        })
    return rows


def main() -> int:
    avail = probe_availability()
    logs = sorted(glob.glob(LOG_GLOB))

    if not logs:
        report = {
            "status": "NO_REAL_TELEMETRY_REACHABLE",
            "measured": None,
            "availability": avail,
            "why": (
                "data/real_logs/ contains no .ulg files. The corpus is "
                "identified by UUID in data/real_logs_report.json but the "
                "files themselves were never committed (gitignored), and "
                "review.px4.io is refused by this environment's egress policy."),
            "explicitly_not_done": (
                "No simulator run was substituted. The brief forbids "
                "simulating and labelling it real, and an unconditional rate "
                "from synthetic denial would measure the fault model, not "
                "flight."),
            "exactly_what_is_needed": [
                "1. A network-permitted host, then: "
                "python tools/fetch_real_logs.py --no-run",
                "2. pip install -e '.[logs]' for pyulog "
                f"(installed here: {avail['pyulog_installed']})",
                "3. Re-run this script; it needs no other change, because "
                "fix_type is already plumbed at ulog_source.py:178 and gvalid "
                "is a function of fix_type alone.",
            ],
            "what_it_would_yield": (
                "Per-flight gvalid occupancy against applicable (post-arm) "
                "time, closure-run count and longest-run length, and the "
                "across-flight distribution. Unconditional only."),
            "what_it_would_NOT_yield": (
                "q_gvalid | h. The conditioning variable does not exist in an "
                "unannotated corpus. See "
                "research/wp_c5/Q_GVALID_MEASUREMENT_SPEC.md section 2."),
        }
    else:
        rows = measure(logs)
        ok = [r for r in rows if r.get("status") == "ok"]
        occ = [r["occupancy"] for r in ok]
        report = {
            "status": "MEASURED",
            "availability": avail,
            "n_flights": len(ok),
            "unconditional_occupancy": {
                "mean_across_flights": round(sum(occ) / len(occ), 6)
                if occ else None,
                "min": min(occ) if occ else None,
                "max": max(occ) if occ else None,
                "flights_with_any_closure": sum(
                    1 for r in ok if r["n_closure_runs"] > 0),
            },
            "IS_NOT_q_gvalid": (
                "This is unconditional. It mixes all hypotheses in unknown "
                "proportion and must not be reported as q_gvalid | h."),
            "per_flight": rows,
        }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "gvalid_unconditional.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"status: {report['status']}")
    print(json.dumps(avail, indent=1))
    if report["status"] == "NO_REAL_TELEMETRY_REACHABLE":
        print("\n" + report["why"])
        print("\nexactly what is needed:")
        for s in report["exactly_what_is_needed"]:
            print("  " + s)
    else:
        print(json.dumps(report["unconditional_occupancy"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
