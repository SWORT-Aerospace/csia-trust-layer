"""Run the mag_emi PROBE campaign. The grid is not a parameter.

RESTORED VERBATIM from 80959bb~1, where it lived at
`tools/deploy/mechanism_b_campaign.py` before that filename was taken over by
the authoritative GNSS-glitch Mechanism B runner. Recovering it under an
unambiguous name is what makes `research/v1_1/MECHANISM_B_MAG_EMI_PROBE.md`
reproducible again; its constants are verified against the saved campaign
artifact `research/v1_1/results/mechanism_b/campaign_ardupilot.json`
(arms CLEAN/SUB/CROSS at 0.0/0.5/15.0 uT, 3 repetitions, 40 s window,
onset t+15 s).

THIS IS NOT THE MECHANISM B CAMPAIGN. It is the `mag_emi` probe at
T* = 0.60, filed separately in MECHANISM_B_MAG_EMI_PROBE.md. The
authoritative Mechanism B runner is `tools/deploy/mechanism_b_campaign.py`.


`research/v1_1/MECHANISM_B_MAG_EMI_PREREGISTRATION.md` section 3 fixes the arms, the
magnitudes, the repetitions, the window and the injection instant, in a commit
that precedes every trial. They are constants here rather than command-line
options, on purpose: a grid you can widen from the shell is not a preregistered
grid. `--platform` selects which platform to fly and nothing else.

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
ARMS = (("CLEAN", 0.0),      # null control (RULE A)
        ("SUB", 0.5),        # expected non-crossing
        ("CROSS", 15.0))     # expected crossing
REPETITIONS = 3
SECONDS = 40.0
INJECT_AT = 15.0
# ---------------------------------------------------------------------------

OUT_DIR = os.path.join(ROOT, "research", "v1_1", "results", "mechanism_b")
TRACE_DIR = os.path.join(ROOT, "logs", "mechanism_b")


def one_flight(platform: str, arm: str, u: float, rep: int) -> dict:
    tag = f"{platform}_{arm}_{rep}"
    result = os.path.join(OUT_DIR, f"{tag}.json")
    trace = os.path.join(TRACE_DIR, f"{tag}.trace.jsonl")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "deploy",
                                        "shadow_sitl_check.py"),
           "--platform", platform, "--fly",
           "--seconds", str(SECONDS),
           "--inject", "mag_emi", "--emi-ut", str(u),
           "--inject-at", str(INJECT_AT),
           "--trust-trace", trace, "--out", result]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    wall = time.time() - t0
    row = {"tag": tag, "arm": arm, "u_ut": u, "rep": rep,
           "returncode": proc.returncode, "wall_s": round(wall, 1),
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
            "write_burst_ms": inj.get("write_burst_ms"),
            "authority": (res.get("command_authority") or {}).get("result"),
        })
    else:
        row["error"] = (proc.stderr or proc.stdout or "")[-500:]
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", required=True,
                    choices=("ardupilot", "px4"))
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TRACE_DIR, exist_ok=True)

    print(f"=== Mechanism B campaign, {args.platform}: "
          f"{len(ARMS)} arms x {REPETITIONS} reps = "
          f"{len(ARMS) * REPETITIONS} flights, {SECONDS:.0f} s window, "
          f"injection at t+{INJECT_AT:.0f}s")
    rows = []
    for arm, u in ARMS:
        for rep in range(REPETITIONS):
            row = one_flight(args.platform, arm, u, rep)
            rows.append(row)
            print(f"  {row['tag']:26s} rc={row['returncode']} "
                  f"ticks={row.get('ticks')} steps={row.get('trace_steps')} "
                  f"confirmed={row.get('injection_confirmed')} "
                  f"burst={row.get('write_burst_ms')}ms "
                  f"({row['wall_s']}s)")

    path = os.path.join(OUT_DIR, f"campaign_{args.platform}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"platform": args.platform, "arms": list(ARMS),
                   "repetitions": REPETITIONS, "seconds": SECONDS,
                   "inject_at": INJECT_AT, "flights": rows,
                   "preregistration":
                       "research/v1_1/MECHANISM_B_MAG_EMI_PREREGISTRATION.md"},
                  fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(path, ROOT)}")

    # A flight that did not produce a trace is a failed measurement. It is
    # NOT a quiet arm, and it must not be reported as one.
    missing = [r["tag"] for r in rows if not r.get("trace_steps")]
    if missing:
        print(f"!!! no trust trace from: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
