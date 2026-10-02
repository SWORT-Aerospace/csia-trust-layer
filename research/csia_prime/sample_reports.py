#!/usr/bin/env python3
"""PRIME A6: representative CSIA Flight Assurance outputs, one per case. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/sample_reports.py

Runs the product's `assure` command on one log per case. It writes each case's
first page and machine outputs under `sample_reports/<case>/`, and the index
SAMPLE_REPORTS.json (input SHA-256, support status, the summary's length).

**Every log is labelled REAL or SITL.** The raw ULogs are not committed.
"""
from __future__ import annotations

import subprocess
import sys

import common_prime as C

CASES = [
    ("01_nominal_hover", C.SITL_RB001 / "CAL1.ulg", "SITL", "nominal hover"),
    ("02_motor_degradation_hover", C.SITL_2_3 / "V1.ulg", "SITL", "motor_1 at 60 % effect, hover"),
    ("03_telemetry_corruption", C.SITL_2_3 / "V10.ulg", "SITL", "ESC 3 reports RPM x 10; motor healthy"),
    ("04_sensor_loss_esc_telemetry_offline", C.SITL_2_3 / "V9.ulg", "SITL", "ESC 2 telemetry offline; motor healthy"),
    ("05_gps_loss", C.SITL_2_3 / "V7.ulg", "SITL", "GPS off in flight"),
    ("06_configuration_change_magnetometer_loss", C.REPO.parent / "csia_2_2_pilot_raw/S1/S1.ulg", "SITL",
     "EKF2 selector on; magnetometer lost at 75 s"),
    ("07_ambiguous_propulsion_event_hold", C.SITL_2_3 / "V12.ulg", "SITL", "motor_2 at 60 % in a hold after maneuvers"),
    ("08_missing_telemetry_real", C.REAL_PYULOG / "sample_log_small.ulg", "REAL",
     "real CubeOrange (VTOL airframe): no actuator_motors, no ESC telemetry"),
    ("09_log_dropouts_real", C.REAL_PYULOG / "sample.ulg", "REAL", "real AUAV X2.1: 4 logger dropouts (119 ms)"),
    ("10_maneuvering_loss", C.SITL_2_3 / "V13.ulg", "SITL", "motor_2 at 60 % mid-maneuver"),
    ("11_unsupported_vehicle_real", C.REAL_PX4_DOCS, "REAL", "real FMUv5 boat (PX4 docs sample log)"),
]
KEEP = ("assurance_summary.txt", "support.json", "alerts.json", "receipts.json", "coverage_states.json",
        "report.txt", "manifest.json")


def main():
    import json
    out_root = C.HERE / "sample_reports"
    index = {}
    for name, path, kind, what in CASES:
        d = out_root / name
        d.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "assure", str(path),
                            "--out", str(d)], cwd=C.REPO, capture_output=True, text=True)
        for f in d.iterdir():
            if f.name not in KEEP:
                f.unlink()
        summary = (d / "assurance_summary.txt").read_text() if (d / "assurance_summary.txt").exists() else ""
        sup = json.loads((d / "support.json").read_text())["support"] if (d / "support.json").exists() else {}
        index[name] = {"input": path.name, "input_sha256": C.sha(path), "data": kind, "case": what,
                       "exit_code": r.returncode, "support": sup.get("status"),
                       "summary_lines": len(summary.splitlines()),
                       "what_happened": summary.split("WHAT HAPPENED?\n")[1].split("WHEN DID")[0].strip().splitlines()
                       if "WHAT HAPPENED?" in summary else None}
        print(name, r.returncode, sup.get("status"), index[name]["summary_lines"], flush=True)
    C.write_json(C.HERE / "SAMPLE_REPORTS.json", {
        "label": "PRIME A6: the product's assure output on one log per case; REAL or SITL as labelled",
        "cases": index})


if __name__ == "__main__":
    main()
