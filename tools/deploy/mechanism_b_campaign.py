"""Run the PREREGISTERED Mechanism B campaign. The grid is not a parameter.

`research/v1_1/CURRENT_STACK_REPLICATION.md` (blob
0e186117e2dcc014862872934768e06e0a195592, committed before the first trial)
fixes the conditions, the magnitudes, the repetitions, the window, the onset
instant and the flight mode. They are constants here rather than command-line
options, on purpose: a grid you can widen from the shell is not a preregistered
grid. `--platform` selects which platform to fly and nothing else.

PX4 is INAPPLICABLE and this tool refuses to fly it. Section 2.1 of the
preregistration records the four candidate routes that were read out of PX4
source and why each fails; section 3 forbids substituting another intervention.

  python tools/deploy/mechanism_b_campaign.py --platform ardupilot
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

# --- PREREGISTERED. Changing any of these invalidates the campaign. ---------
PREREG = "research/v1_1/CURRENT_STACK_REPLICATION.md"
PREREG_BLOB = "0e186117e2dcc014862872934768e06e0a195592"

# (condition, metres, ramp_s, predeclared expectation)
CONDITIONS = (
    ("CLEAN",      0.0,  0.0, "no crossing"),   # null control, nothing written
    ("STEP_SMALL", 5.0,  0.0, "no crossing"),
    ("STEP_LARGE", 50.0, 0.0, "no crossing"),
    ("RAMP_20S",   50.0, 20.0, "crossing"),
)
REPETITIONS = 5
SECONDS = 60.0
ONSET_S = 20.0
HOLD_MODE = "ALT_HOLD"          # section 3.2, amended before any trial
PLATFORMS_APPLICABLE = ("ardupilot",)
# ---------------------------------------------------------------------------

OUT_DIR = os.path.join(ROOT, "research", "v1_1", "results", "mechanism_b_gps")
TRACE_DIR = os.path.join(ROOT, "logs", "mechanism_b_gps")


def one_flight(platform: str, cond: str, metres: float, ramp_s: float,
               rep: int) -> dict:
    tag = f"{platform}_{cond}_{rep}"
    result = os.path.join(OUT_DIR, f"{tag}.json")
    trace = os.path.join(TRACE_DIR, f"{tag}.trace.jsonl")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "deploy",
                                        "shadow_sitl_check.py"),
           "--platform", platform, "--fly", "--hold-mode", HOLD_MODE,
           "--seconds", str(SECONDS),
           "--inject", "gps_glitch",
           "--glitch-m", str(metres), "--glitch-ramp-s", str(ramp_s),
           "--inject-at", str(ONSET_S),
           "--trust-trace", trace, "--out", result]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    wall = time.time() - t0
    row = {"tag": tag, "condition": cond, "metres": metres, "ramp_s": ramp_s,
           "rep": rep, "returncode": proc.returncode,
           "wall_s": round(wall, 1),
           "result_file": os.path.relpath(result, ROOT)}
    if os.path.exists(result):
        with open(result, encoding="utf-8") as fh:
            res = json.load(fh)
        inj = res.get("injection") or {}
        row.update({
            "flight_id": res.get("flight_id"),
            "ticks": (res.get("stats") or {}).get("ticks"),
            "trace_steps": res.get("trust_trace_steps"),
            "injection_confirmed": inj.get("confirmed"),
            "writes": len(inj.get("schedule") or []),
            "hold_mode_confirmed": (res.get("rig_flight") or {}).get(
                "hold_mode_confirmed"),
            "authority": (res.get("command_authority") or {}).get("result"),
        })
    else:
        row["error"] = (proc.stderr or proc.stdout or "")[-600:]
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", required=True,
                    choices=("ardupilot", "px4"))
    args = ap.parse_args()

    if args.platform not in PLATFORMS_APPLICABLE:
        print(f"=== {args.platform}: INAPPLICABLE")
        print("    No fix-preserving GNSS position offset exists on this "
              "platform. Four candidate routes were read out of source and "
              "all four fail -- see section 2.1 of the preregistration. "
              "Section 3 forbids substituting another intervention, so no "
              "trials are run and the platform is classified INAPPLICABLE.")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TRACE_DIR, exist_ok=True)

    print(f"=== Mechanism B campaign, {args.platform}: "
          f"{len(CONDITIONS)} conditions x {REPETITIONS} reps = "
          f"{len(CONDITIONS) * REPETITIONS} trials, {SECONDS:.0f} s window, "
          f"onset t+{ONSET_S:.0f}s, hold mode {HOLD_MODE}")
    rows = []
    for cond, metres, ramp_s, expect in CONDITIONS:
        for rep in range(REPETITIONS):
            row = one_flight(args.platform, cond, metres, ramp_s, rep)
            row["expectation"] = expect
            rows.append(row)
            print(f"  {row['tag']:28s} rc={row['returncode']} "
                  f"ticks={row.get('ticks')} steps={row.get('trace_steps')} "
                  f"conf={row.get('injection_confirmed')} "
                  f"writes={row.get('writes')} "
                  f"mode={row.get('hold_mode_confirmed')} "
                  f"({row['wall_s']}s)")

    path = os.path.join(OUT_DIR, f"campaign_{args.platform}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"platform": args.platform,
                   "conditions": [list(c) for c in CONDITIONS],
                   "repetitions": REPETITIONS, "seconds": SECONDS,
                   "onset_s": ONSET_S, "hold_mode": HOLD_MODE,
                   "trials": rows,
                   "preregistration": PREREG,
                   "preregistration_blob": PREREG_BLOB},
                  fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(path, ROOT)}")

    # A trial that produced no trace is a failed measurement. It is NOT a
    # quiet trial and must not be reported as one.
    missing = [r["tag"] for r in rows if not r.get("trace_steps")]
    if missing:
        print(f"!!! no trust trace from: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
