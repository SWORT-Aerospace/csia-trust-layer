#!/usr/bin/env python3
"""XSYS-001-A2: fly the fresh NOMINAL-ONLY validation pilots of PILOT_MATRIX_A2.csv.

Stopping rule (C4_A2_SPEC.json): every row, in the matrix order, once; a
technical failure (driver exit != 0 or no ULog) is retried ONCE with the
identical configuration; nothing is evaluated here, so nothing can stop on a
result. Every flight is eta = 1.00 (only the benign SDLOG_DIRS_MAX event is set),
flown with the frozen XSYS-001 trial driver, unchanged.

Usage: fly_pilots_a2.py --build <px4 build> --out <dir> --work <dir>
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER = HERE.parent / "execution" / "xsys_run_trial.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    spec_sha = hashlib.sha256((HERE / "C4_A2_SPEC.json").read_bytes()).hexdigest()
    rows = list(csv.DictReader(open(HERE / "PILOT_MATRIX_A2.csv")))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "A2_FLIGHT_LOG.jsonl"
    for pos, r in enumerate(rows, 1):
        pid = r["pilot_id"]
        if r["onset_param"] != "SDLOG_DIRS_MAX":
            raise SystemExit(f"{pid}: not a nominal-only pilot")
        if (out / f"{pid}.ulg").exists() and (out / f"{pid}.json").exists():
            continue
        extra = {"purpose": ("XSYS-001-A2 NOMINAL-ONLY VALIDATION PILOT - eta 1.00, no fault, no corruption, "
                             "no CSIA scoring, never confirmatory"),
                 "pilot_id": pid, "role": r["role"], "slot": r["slot"], "position": pos,
                 "c4_a2_spec_sha256": spec_sha}
        for attempt in (1, 2):
            cmd = [sys.executable, str(DRIVER), "--build", a.build, "--workdir", str(Path(a.work) / pid),
                   "--out", str(out), "--name", pid, "--heading-deg", r["heading_deg"],
                   "--onset-param", r["onset_param"], "--onset-value", r["onset_value"],
                   "--t-arm", r["t_arm_s"], "--t-onset", r["t_onset_s"], "--t-end", r["t_end_s"],
                   "--speed", "1", "--instance", "0", "--extra-json", json.dumps({**extra, "attempt": attempt})]
            t0 = time.time()
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
            ok = p.returncode == 0 and (out / f"{pid}.ulg").exists()
            with open(log, "a") as f:
                f.write(json.dumps({"pilot_id": pid, "position": pos, "attempt": attempt, "returncode": p.returncode,
                                    "ok": ok, "wall_s": round(time.time() - t0, 1)}) + "\n")
            if ok:
                break
        print(json.dumps({"pilot_id": pid, "ok": ok}), flush=True)
    print("A2_PILOTS_DONE")


if __name__ == "__main__":
    main()
