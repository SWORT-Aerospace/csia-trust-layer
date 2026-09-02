"""Phase 4.5 §19: what did this phase cost per tick?

Three costs, kept apart because they are paid at different times and only one
of them is on the core path:

  STARTUP     building the timeout map. Paid once, at construction.
  PER-TICK    the runtime impact of the timeout change. Expected to be zero:
              the watchdog compares against a float either way, and only the
              float differs.
  REPORTING   consumer parse and render. Not core, and §19 says not to
              contaminate core timing with it.

    python engineering/v1_1/phase4_5/run_compute.py
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.runtime.online import STALE_TIMEOUT_S                    # noqa: E402
from csia.v1_1.monitor import Monitor, parse                       # noqa: E402
from csia.v1_1.staleness import build_runtime_stale_timeouts       # noqa: E402

REPS = 200


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _time(fn, reps=REPS):
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)
    return {"median_us": round(statistics.median(samples), 3),
            "min_us": round(min(samples), 3), "n": reps}


def _watchdog(stale):
    """The ONLY per-tick work the timeout change touches: one float compare
    per node, exactly as `online.py:604` does it."""
    slots = {n: (True, True, 0.0) for n in stale}

    def run():
        tau = 1.0
        return {n: valid and seen and (tau - last) <= stale[n]
                for n, (valid, seen, last) in slots.items()}
    return run


def main() -> int:
    startup = {p: _time(lambda p=p: build_runtime_stale_timeouts(p), 100)
               for p in ("ardupilot", "px4")}

    derived = build_runtime_stale_timeouts("px4")
    per_tick = {
        "frozen_defaults": _time(_watchdog(dict(STALE_TIMEOUT_S)), 2000),
        "derived_map": _time(_watchdog(derived), 2000),
    }

    payload = json.load(open(os.path.join(ENG, "csia_output_fixloss_example.json"),
                             encoding="utf-8"))
    view = parse(payload)
    mon = Monitor()
    reporting = {
        "consumer_parse": _time(lambda: parse(payload), 200),
        "consumer_render": _time(view.render, 2000),
        "consumer_consume": _time(lambda: mon.consume(payload), 200),
    }

    doc = {
        "artifact": "PHASE4_5_COMPUTE",
        "generation_command":
            "python engineering/v1_1/phase4_5/run_compute.py",
        "csia_sha": _git("rev-parse", "HEAD"),
        "measured_on": "CPython on a general-purpose host",
        "note": "STARTUP is paid once at construction. PER-TICK is the only "
                "core-path cost the timeout change touches -- one float "
                "compare per node, whose VALUE differs and whose COST does "
                "not. REPORTING is the consumer and is not core; section 19 "
                "forbids folding it into a core figure. NO TARGET-HARDWARE "
                "FIGURE EXISTS AND NONE IS CLAIMED.",
        "startup_us": startup,
        "per_tick_us": per_tick,
        "per_tick_delta_us": round(
            per_tick["derived_map"]["median_us"]
            - per_tick["frozen_defaults"]["median_us"], 4),
        "reporting_us": reporting,
        "core_path_changed": False,
    }
    with open(os.path.join(ENG, "PHASE4_5_COMPUTE.json"), "w",
              encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("startup (once):   " + ", ".join(
        f"{p}={v['median_us']:.2f} us" for p, v in startup.items()))
    print(f"per-tick watchdog: frozen="
          f"{per_tick['frozen_defaults']['median_us']:.3f} us  derived="
          f"{per_tick['derived_map']['median_us']:.3f} us  "
          f"delta={doc['per_tick_delta_us']:+.4f} us")
    print("reporting:        " + ", ".join(
        f"{k}={v['median_us']:.2f} us" for k, v in reporting.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
