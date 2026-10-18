"""Resource envelope and OS-stress campaign, with criteria fixed in advance.

THE CRITERIA ARE DECLARED HERE, BEFORE ANY RUN
-----------------------------------------------
The instruction is explicit: do not select red lines after seeing results. So
the three envelope bands are defined below as CONSTANTS, and the analysis
reads them. Changing one is a visible diff, not a judgement call made while
looking at a plot.

    NORMAL       every decision correct AND p99 tick latency within budget
    DEGRADED     every decision correct, latency budget exceeded
    UNSUPPORTED  a DECISION changed, or the process did not survive

THE QUESTION THIS ANSWERS
-------------------------
Not "how fast is it". It is:

    does compute degradation produce VISIBLE ASSURANCE DEGRADATION before
    SILENT SCIENTIFIC DIVERGENCE?

A run that gets slower and stays correct is a pass. A run that stays fast and
returns a different decision is the failure -- and the band names are chosen so
that reading the table cannot confuse the two.

WHAT IS STRESSED, AND WHAT IS NOT
----------------------------------
CSIA IS NOT MODIFIED. The stressors act on the HOST: CPU load, memory
pressure, and process priority. The frozen core and the firewall run exactly as
they otherwise would.

**Latency numbers from this environment are not deployment numbers.** It is a
shared container; the E1 campaigns already record latency as
"measured and NOT adjudicated" for the same reason, and that discipline carries
here unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

#: DECLARED BEFORE ANY RUN. See the module docstring.
TICK_BUDGET_US = 2000.0          # the R13 budget the shadow runner checks
P99_BUDGET_US = TICK_BUDGET_US   # NORMAL requires p99 within budget
BANDS = ("NORMAL", "DEGRADED", "UNSUPPORTED")


def _percentile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def _vectors():
    vec_dir = os.path.join(ROOT, "csia_assurance", "vectors")
    out = []
    for name in sorted(os.listdir(vec_dir)):
        if name.endswith(".json") and name != "INDEX.json":
            with open(os.path.join(vec_dir, name), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out


def _baseline_decisions(vectors):
    from csia_assurance import qualify
    return {v["id"]: qualify(v["record"], v.get("prior")).state
            for v in vectors}


def measure(vectors, baseline, repeats: int) -> dict:
    """Run the vectors `repeats` times, timing each and checking each."""
    from csia_assurance import qualify
    lat, wrong = [], []
    for _ in range(repeats):
        for v in vectors:
            t0 = time.perf_counter()
            got = qualify(v["record"], v.get("prior"))
            lat.append((time.perf_counter() - t0) * 1e6)
            if got.state != baseline[v["id"]]:
                wrong.append({"vector": v["id"],
                              "baseline": baseline[v["id"]],
                              "got": got.state})
    return {
        "samples": len(lat),
        "mean_us": statistics.fmean(lat) if lat else None,
        "p50_us": _percentile(lat, 0.50),
        "p95_us": _percentile(lat, 0.95),
        "p99_us": _percentile(lat, 0.99),
        "max_us": max(lat) if lat else None,
        "jitter_us": (statistics.pstdev(lat) if len(lat) > 1 else 0.0),
        "decision_changes": wrong,
    }


def band(result: dict, survived: bool) -> str:
    """Apply the declared criteria. No judgement at this point."""
    if not survived or result.get("decision_changes"):
        return "UNSUPPORTED"
    p99 = result.get("p99_us")
    if p99 is None:
        return "UNSUPPORTED"
    return "NORMAL" if p99 <= P99_BUDGET_US else "DEGRADED"


class _Load:
    """Background CPU load, as N spinning subprocesses."""

    def __init__(self, workers: int):
        self.workers, self.procs = workers, []

    def __enter__(self):
        code = ("import time\n"
                "end = time.time() + 600\n"
                "x = 0.0\n"
                "while time.time() < end:\n"
                "    x = (x + 1.000001) % 1e9\n")
        for _ in range(self.workers):
            self.procs.append(subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(0.5)
        return self

    def __exit__(self, *exc):
        for p in self.procs:
            p.terminate()
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        return False


def campaign(quick: bool = False) -> dict:
    vectors = _vectors()
    baseline = _baseline_decisions(vectors)
    repeats = 20 if quick else 200
    cpus = os.cpu_count() or 1

    runs = []

    # 1. unloaded
    r = measure(vectors, baseline, repeats)
    runs.append({"stressor": "none", "detail": "unloaded baseline",
                 "result": r, "band": band(r, True)})

    # 2-3. CPU contention at 1x and 2x the core count
    for mult in (1, 2):
        workers = cpus * mult
        with _Load(workers):
            r = measure(vectors, baseline, repeats)
        runs.append({"stressor": "cpu_contention",
                     "detail": f"{workers} spinning workers on {cpus} cpus",
                     "result": r, "band": band(r, True)})

    # 4. lowest scheduling priority
    old = os.nice(0)
    try:
        os.nice(19 - old if 19 - old > 0 else 0)
        r = measure(vectors, baseline, repeats)
        runs.append({"stressor": "low_priority",
                     "detail": "nice 19", "result": r,
                     "band": band(r, True)})
    except (OSError, PermissionError) as exc:
        runs.append({"stressor": "low_priority",
                     "detail": f"could not renice: {exc}",
                     "result": None, "band": "INCONCLUSIVE"})

    # 5. memory pressure
    try:
        ballast = [bytearray(64 * 1024 * 1024) for _ in range(8)]
        r = measure(vectors, baseline, repeats)
        del ballast
        runs.append({"stressor": "memory_pressure",
                     "detail": "512 MiB resident ballast",
                     "result": r, "band": band(r, True)})
    except MemoryError:
        runs.append({"stressor": "memory_pressure",
                     "detail": "could not allocate ballast",
                     "result": None, "band": "INCONCLUSIVE"})

    silent = [r for r in runs
              if r["result"] and r["result"]["decision_changes"]]
    visible = [r for r in runs if r["band"] == "DEGRADED"]

    return {
        "schema": "csia.assurance.resource_envelope/1",
        "criteria_declared_before_runs": {
            "tick_budget_us": TICK_BUDGET_US,
            "NORMAL": "no decision change AND p99 <= budget",
            "DEGRADED": "no decision change AND p99 > budget",
            "UNSUPPORTED": "a decision changed, or the process did not survive",
        },
        "host": {"cpus": cpus, "platform": sys.platform},
        "vectors": len(vectors),
        "repeats_per_run": repeats,
        "runs": runs,
        "the_question": ("does compute degradation produce VISIBLE assurance "
                         "degradation before SILENT scientific divergence?"),
        "answer": {
            "silent_decision_divergence_runs": len(silent),
            "visible_degradation_runs": len(visible),
            "verdict": ("NO_SILENT_DIVERGENCE" if not silent
                        else "SILENT_DIVERGENCE_OBSERVED"),
        },
        "latency_caveat": (
            "Measured in a SHARED CONTAINER. These are not deployment "
            "numbers, and the E1 discipline -- latency recorded and NOT "
            "adjudicated -- carries here unchanged."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = campaign(quick=args.quick)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
