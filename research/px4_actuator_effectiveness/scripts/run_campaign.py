#!/usr/bin/env python3
"""Run a campaign of SIH trials sequentially and write a manifest.

    nominal   N unmodified and N patched trials, interleaved, no injection
    sweep     patched trials, one motor, eta in LEVELS, R repeats, interleaved

All trials share one schedule in simulated time and run as instance 0 at
PX4_SIM_SPEED_FACTOR 1, one at a time, so that nothing but the build and eta
differs between them.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = (1.00, 0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.25, 0.00)
SCHEDULES = {"nominal": ("--t-arm", "10", "--t-onset", "30", "--t-end", "45"),
             "sweep": ("--t-arm", "10", "--t-onset", "30", "--t-end", "50")}


def trial(py, build, out, work, name, schedule, eta=None):
    cmd = [py, str(HERE / "run_trial.py"), "--build", build, "--workdir", str(work / name),
           "--out", str(out), "--name", name, "--speed", "1", "--instance", "0", *schedule]
    if eta is not None:
        cmd += ["--motor", "1", "--eta", f"{eta:.2f}"]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    ok = r.returncode == 0
    print(f"{name:28s} rc={r.returncode} {time.time() - t0:5.1f}s", flush=True)
    if not ok:
        print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
    return {"name": name, "eta": eta, "rc": r.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("nominal", "sweep"))
    ap.add_argument("--base", required=True)
    ap.add_argument("--patched", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    out, work = Path(a.out), Path(a.work)
    out.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    rows = []
    sched = SCHEDULES[a.mode]
    if a.mode == "nominal":
        for k in range(1, a.n + 1):
            rows.append(dict(trial(py, a.base, out, work, f"nom_base_{k:02d}", sched), build="base"))
            rows.append(dict(trial(py, a.patched, out, work, f"nom_patched_{k:02d}", sched), build="patched"))
    else:
        for r in range(1, a.repeats + 1):
            for eta in LEVELS:
                name = f"sweep_eta{int(round(eta * 100)):03d}_r{r}"
                rows.append(dict(trial(py, a.patched, out, work, name, sched, eta), build="patched", repeat=r))
    (out / f"MANIFEST_{a.mode}.json").write_text(json.dumps(
        {"mode": a.mode, "schedule": sched, "levels": LEVELS if a.mode == "sweep" else None,
         "trials": rows}, indent=1))


if __name__ == "__main__":
    main()
