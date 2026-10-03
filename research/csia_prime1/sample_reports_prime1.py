#!/usr/bin/env python3
"""PRIME-1 sample sanitized reports: the successor product's output, one log per case. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/sample_reports_prime1.py

Runs `csia-assure` (release prime1, the default) on one log per case and keeps
each case's first page and machine outputs under `sample_reports_prime1/<case>/`.
The index SAMPLE_REPORTS_PRIME1.json records the input SHA-256, the support
state and the hash of every kept output.

**Every SITL log is analysed as a sanitized copy** (the PRIME-1 bundle's
`blind`: PX4's injection messages and the SIH fault parameters removed), as a
customer log would arrive. **Every log is labelled REAL or SITL.** No ULog is
committed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import common_prime1 as C
import build_pilot_bundle_prime1 as BP  # noqa: E402  (after common_prime1: PRIME on the path)

CASES = [
    ("01_nominal_hover", C.SITL_RB001 / "CAL1.ulg", "SITL", "nominal hover"),
    ("02_motor_loss_hover", C.SITL_2_3 / "V1.ulg", "SITL", "motor_1 at 60 % effect, hover"),
    ("03_rpm_excess_motor_healthy", C.SITL_2_3 / "V10.ulg", "SITL", "ESC 3 reports RPM x 10; motor healthy"),
    ("04_esc_telemetry_offline", C.SITL_2_3 / "V9.ulg", "SITL", "ESC 2 telemetry offline; motor healthy"),
    ("05_maneuvering_loss", C.SITL_2_3 / "V13.ulg", "SITL", "motor_2 at 60 % mid-maneuver"),
    ("06_log_dropouts_real", C.REAL_PYULOG / "sample.ulg", "REAL", "real AUAV X2.1: 4 logger dropouts"),
    ("07_unsupported_vtol_real", C.REAL_PYULOG / "sample_log_small.ulg", "REAL", "real CubeOrange, VTOL airframe"),
    ("08_unsupported_boat_real", C.REAL_PX4_DOCS, "REAL", "real FMUv5 boat (PX4 docs sample log)"),
]
KEEP = ("assurance_summary.txt", "support.json", "alerts.json", "receipts.json", "coverage_states.json",
        "report.txt", "generic_report.json", "manifest.json")
WORK = C.OUT_RAW / "sample_inputs"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    out_root = C.HERE / "sample_reports_prime1"
    if out_root.exists():
        shutil.rmtree(out_root)
    WORK.mkdir(parents=True, exist_ok=True)
    index = {}
    for name, src, kind, what in CASES:
        # the analysed file carries the case's neutral name, so the page shows no source label
        log = WORK / f"{name}.ulg"
        if kind == "SITL":
            record = BP.blind(src, log, corrupt=False)
        else:
            shutil.copyfile(src, log)
            record = {"copied_unchanged": True}
        d = out_root / name
        r = subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "assure", str(log), "--out", str(d)],
                           cwd=C.REPO, capture_output=True, text=True)
        for f in d.iterdir():
            if f.name not in KEEP:
                f.unlink()
        sup = json.loads((d / "support.json").read_text())["support"]
        index[name] = {"case": what, "data": kind, "source": src.name, "source_sha256": _sha(src),
                       "analysed_sha256": _sha(log), "sanitization": record, "exit_code": r.returncode,
                       "support": sup["status"], "outputs_sha256": {f.name: _sha(f) for f in sorted(d.iterdir())}}
        print(name, r.returncode, sup["status"], flush=True)
    C.write_json(C.HERE / "SAMPLE_REPORTS_PRIME1.json", {
        "label": "PRIME-1 sample sanitized reports: csia-assure (release prime1) on one log per case; REAL or SITL "
                 "as labelled; SITL logs sanitized as in the pilot bundle", "cases": index})


if __name__ == "__main__":
    sys.exit(main())
