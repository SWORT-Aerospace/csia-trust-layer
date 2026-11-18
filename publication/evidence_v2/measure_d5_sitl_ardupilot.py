#!/usr/bin/env python3
"""Deliverable 5, MEASUREMENT: re-run tools/sitl_validate.py at the current
HEAD on ArduPilot SITL, without and with `--inject gps_glitch`.

    python publication/evidence_v2/measure_d5_sitl_ardupilot.py \\
        --ap-root /home/user/ardupilot/ardupilot [--reps 3]

Not part of `make evidence-v2`: a SITL flight runs on the wall clock and is
not bit-for-bit repeatable. `make evidence-v2-measure` runs it; the committed
data/d5_sitl_ardupilot.json is what `tab_d5_sitl_before_after.py` tabulates.

tools/sitl_validate.py is run UNCHANGED, as the pre-hardening rows C12 and C13
of docs/evidence/evidence_matrix.md were. This wrapper only launches it, keeps
its stdout, and parses the lines it prints (messages, monitored sensors, min
trust after t = 30 s, alarm transitions, VERDICT, mission landed).

The PX4 SIH row is not attempted. PX4 SIH has no GPS-glitch parameter, and
research/v1_1/CURRENT_STACK_REPLICATION.md declares it INAPPLICABLE before any
trial and forbids a substitute intervention.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

TOOL = os.path.join(C.ROOT, "tools", "sitl_validate.py")
OUT = os.path.join(C.DATA, "d5_sitl_ardupilot.json")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def parse(stdout: str) -> dict:
    out = {"alarms": []}
    for line in stdout.splitlines():
        s = line.strip()
        for key, prefix in (("messages", "messages:"), ("monitored_sensors", "monitored sensors:"),
                            ("min_trust_after_30s", "min trust (t>30s):")):
            if s.startswith(prefix):
                try:
                    out[key] = ast.literal_eval(s[len(prefix):].strip())
                except (ValueError, SyntaxError):
                    out[key] = s[len(prefix):].strip()
        m = re.match(r"alarm t=([0-9.]+)s (\w+): (.*)$", s)
        if m:
            out["alarms"].append({"t_s": float(m.group(1)), "level": m.group(2), "reasons": m.group(3)})
        if s.startswith("VERDICT:"):
            out["verdict"] = s[len("VERDICT:"):].strip()
        if s.startswith("mission landed:"):
            out["landed"] = s.endswith("True")
        if "GPS GLITCH INJECTED" in s:
            out["glitch_injected"] = True
        if "GPS FIX KILLED" in s:
            out["fix_killed"] = True
    return out


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ap-root", required=True)
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args(argv)
    binary = os.path.join(args.ap_root, "build", "sitl", "bin", "arducopter")
    params = os.path.join(args.ap_root, "Tools", "autotest", "default_params", "copter.parm")
    ap_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.ap_root,
                               capture_output=True, text=True).stdout.strip()
    version = open(os.path.join(args.ap_root, "ArduCopter", "version.h"), encoding="utf-8").read()
    fw = re.search(r'#define THISFIRMWARE "([^"]+)"', version).group(1)

    runs = []
    for mode in ("none", "gps_glitch"):
        for rep in range(1, args.reps + 1):
            started = utc_now()
            t0 = time.monotonic()
            proc = subprocess.run([sys.executable, TOOL, "--binary", binary, "--params", params,
                                   "--inject", mode], cwd=C.ROOT, capture_output=True, text=True,
                                  timeout=600)
            runs.append({"inject": mode, "rep": rep, "returncode": proc.returncode,
                         "wall_start_utc": started, "wall_seconds": round(time.monotonic() - t0, 1),
                         "parsed": parse(proc.stdout), "stdout": proc.stdout.splitlines(),
                         "stderr_tail": proc.stderr.splitlines()[-20:]})
            print(f"{mode:10s} rep {rep}: rc={proc.returncode} {runs[-1]['parsed'].get('verdict')}")
            time.sleep(5)

    C.write_json(OUT, {
        "schema": "csia.evidence_v2.d5_sitl_ardupilot/1",
        "tool": C.rel(TOOL), "tool_sha256": sha(TOOL),
        "csia_head_at_measurement": C.git("rev-parse", "HEAD"),
        "csia_dirty_at_measurement": bool(C.git("status", "--porcelain")),
        "ardupilot_commit": ap_commit, "ardupilot_firmware": fw,
        "ardupilot_build": "./waf configure --board sitl && ./waf copter",
        "arducopter_binary_sha256": sha(binary), "copter_parm_sha256": sha(params),
        "software": C.software(), "reps": args.reps, "runs": runs,
        "px4_sih": {"status": "INAPPLICABLE", "basis": "research/v1_1/CURRENT_STACK_REPLICATION.md: "
                    "no GPS-glitch parameter exists in PX4 SIH; declared before any trial; "
                    "substitute interventions forbidden"},
    })
    return 0


if __name__ == "__main__":
    C.main_guard(main)
