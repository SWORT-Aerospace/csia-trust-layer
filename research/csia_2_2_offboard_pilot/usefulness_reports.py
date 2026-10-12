#!/usr/bin/env python3
"""Phases 15, 16 and 20: the representative reports the usefulness test reads,
and their pinned hashes. NON-CONFIRMATORY. RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_offboard_pilot/usefulness_reports.py

Writes reports/<case>/{report.json, report.txt, manifest.json} for:

| case | input |
|---|---|
| U1_xsys_A_multi | XSYS-001 A trial XS1A1-C00-A-E055, V3_TEMPORAL, with its flight's PX4 estimator |
| U2_xsys_B_multi | XS1A1-C00-B-E055 (RPM telemetry corruption), V3, with its NB flight's estimator |
| U3_xsys_A_invalid_window | XS1A1-C00-A-E055 under V4_INVALID_WINDOW, with the estimator |
| U4_s1_selector | run S1, from the committed extract |
| U5_cusum_power_sag | frozen CUSUM, v1 power_sag |
| U6_cusum_imu0_drift | frozen CUSUM, v1 imu0_bias_drift |
| U7_e1_transition | E1 through the legacy adapters |
| U8_predicate_fault | MS_A1_SENSOR_DELAY with CHANNEL_LINK_NOMINAL failing (the 2.2 dataset F rule) |

The cases needing the raw XSYS-001 logs (U1-U3) are skipped when the logs
are absent; their committed reports stay as they are.

Writes REPORT_HASHES.json: the SHA-256 of every report.json, which
`tests/test_csia_2_2_pilot.py` pins for the cases that need no raw data.
"""
from __future__ import annotations

import json
import sys

import common_pilot as C

from csia_evidence_assurance import report as R  # noqa: E402
from csia_evidence_assurance import runs  # noqa: E402
from csia_evidence_assurance.adapters import px4_estimator as PX  # noqa: E402

OUT = C.HERE / "reports"
HASHES = C.HERE / "REPORT_HASHES.json"


def write(case, run, config=None):
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
    body = R.dumps(m)
    d = OUT / case
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_bytes(body)
    (d / "report.txt").write_text(R.human_report(m))
    (d / "manifest.json").write_bytes(R.dumps(R.manifest(m, body, config or {})))
    return C.sha(d / "report.json")


def e1_run():
    import e1_2_2
    coll = []
    e1_2_2.run(collect=coll)
    gate, contracts = coll[0]
    return runs.Run(coll[1:], {"kind": "e1_transition", "design_sha256": e1_2_2.T.FROZEN_SHA256},
                    gate, contracts)


def predicate_fault_run():
    import datasets_2_2 as D
    run, _extra = D.predicate_fault_run()
    return run


def main():
    hashes = json.loads(HASHES.read_text()) if HASHES.exists() else {}
    raw = C.RAW_FLIGHTS
    if (raw / "XS1A1-C00-A-E055.ulg").exists():
        hashes["U1_xsys_A_multi"] = write("U1_xsys_A_multi", runs.xsys_trial(
            "XS1A1-C00-A-E055", "V3_TEMPORAL", raw / "XS1A1-C00-A-E055.ulg"))
        hashes["U2_xsys_B_multi"] = write("U2_xsys_B_multi", runs.xsys_trial(
            "XS1A1-C00-B-E055", "V3_TEMPORAL", raw / "XS1A1-C00-NB.ulg"))
        hashes["U3_xsys_A_invalid_window"] = write("U3_xsys_A_invalid_window", runs.xsys_trial(
            "XS1A1-C00-A-E055", "V4_INVALID_WINDOW", raw / "XS1A1-C00-A-E055.ulg"))
    hashes["U4_s1_selector"] = write("U4_s1_selector", runs.estimator_log(
        PX.EstimatorLog.from_npz(C.HERE / "data/S1_estimator_extract.npz")), {"tick_s": 0.1})
    hashes["U5_cusum_power_sag"] = write("U5_cusum_power_sag", runs.cusum_scenario("power_sag"))
    hashes["U6_cusum_imu0_drift"] = write("U6_cusum_imu0_drift",
                                          runs.cusum_scenario("imu0_bias_drift"))
    hashes["U7_e1_transition"] = write("U7_e1_transition", e1_run())
    hashes["U8_predicate_fault"] = write("U8_predicate_fault", predicate_fault_run())
    C.write_json(HASHES, hashes)
    print(json.dumps(hashes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
