#!/usr/bin/env python3
"""PRIME-1 Phase 38: product performance, measured. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/perf_prime1.py

For each log, in a fresh process (so imports and memory are not shared):

| measure | how |
|---|---|
| startup | process start to the product's modules imported |
| parse | `StockLog.from_ulog` + canonical timebase + decimation |
| discovery | `events.discover_prime1` on the parsed log |
| support | `support_prime1.inspect` + `check` |
| analysis and report | `assure_prime1.run` end to end (it parses again: the product does not cache) |
| total | wall time of the command line `python -m csia_evidence_assurance assure`, measured from outside |
| peak memory | the CLI process's maximum resident set (getrusage of the child) |
| report size | bytes written to the output folder |

Each CLI run is repeated three times; the median is reported. One machine,
stated in the output. Writes PERFORMANCE_PRIME1.json.
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import common_prime1 as C

LOGS = [
    ("sitl_hover_motor_loss", C.SITL_2_3 / "V1.ulg", "SITL"),
    ("sitl_maneuvering_loss", C.SITL_2_3 / "V13.ulg", "SITL"),
    ("sitl_long_nominal", C.SITL_RB001 / "CAL1.ulg", "SITL"),
    ("real_auav_x21", C.REAL_PYULOG / "sample.ulg", "REAL"),
    ("real_boat_withheld", C.REAL_PX4_DOCS, "REAL"),
]
REPEATS = 3

STAGES = r'''
import json, sys, time
t0 = time.perf_counter()
from csia_evidence_assurance import assure_prime1, events, support_prime1, releases, runs
from csia_evidence_assurance.adapters import px4_stock, px4_estimator
from csia_evidence_assurance.stock_log import StockLog
t1 = time.perf_counter()
path = sys.argv[1]
info = support_prime1.inspect(path); sup = support_prime1.check(info)
t2 = time.perf_counter()
out = {"startup_s": t1 - t0, "support_s": t2 - t1, "interpretation": sup["interpretation"]}
if sup["interpretation"] == "FULL":
    log = StockLog.from_ulog(path).canonical(1e-6).decimate()
    t3 = time.perf_counter()
    try:
        est = px4_estimator.EstimatorLog.from_ulog(path)
    except Exception:
        est = None
    cal = px4_stock.load_calibration()
    t4 = time.perf_counter()
    events.discover_prime1(log, est, cal, 1e-6)
    t5 = time.perf_counter()
    out.update(parse_s=t3 - t2, discovery_s=t5 - t4)
t6 = time.perf_counter()
assure_prime1.run(path, sys.argv[2], runs.STOCK_TICK_S)
out["analysis_and_report_s"] = time.perf_counter() - t6
print(json.dumps(out))
'''


def cli(path: Path, out: Path) -> tuple[float, int]:
    t = time.perf_counter()
    pid = os.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-m", "csia_evidence_assurance", "assure", str(path),
                                  "--out", str(out)])
    _pid, status, ru = os.wait4(pid, 0)
    wall = time.perf_counter() - t
    assert os.waitstatus_to_exitcode(status) == 0, path
    return wall, ru.ru_maxrss  # kilobytes on Linux


def main():
    rows = {}
    for name, path, kind in LOGS:
        walls, rss, stages = [], [], []
        size = 0
        for _ in range(REPEATS):
            with tempfile.TemporaryDirectory() as td:
                w, r = cli(path, Path(td) / "cli")
                walls.append(w)
                rss.append(r)
                size = sum(f.stat().st_size for f in (Path(td) / "cli").iterdir())
                p = subprocess.run([sys.executable, "-c", STAGES, str(path), str(Path(td) / "st")], cwd=C.REPO,
                                   capture_output=True, text=True, check=True)
                stages.append(json.loads(p.stdout.strip().splitlines()[-1]))
        med = {k: round(statistics.median(s[k] for s in stages), 3) for k in stages[0]
               if isinstance(stages[0][k], float)}
        rows[name] = {"data": kind, "log_bytes": path.stat().st_size, "interpretation": stages[0]["interpretation"],
                      **med, "total_cli_s": round(statistics.median(walls), 3),
                      "peak_memory_mib": round(max(rss) / 1024, 1), "report_bytes": size}
        print(name, rows[name], flush=True)
    C.write_json(C.HERE / "PERFORMANCE_PRIME1.json", {
        "label": "PRIME-1 Phase 38: product performance (median of 3 runs; peak memory is the maximum)",
        "machine": {"python": platform.python_version(), "platform": platform.platform(),
                    "cpus": os.cpu_count()},
        "note": "measured while nothing else ran; the analysis stage re-parses the log (no cache)",
        "logs": rows})


if __name__ == "__main__":
    sys.exit(main())
