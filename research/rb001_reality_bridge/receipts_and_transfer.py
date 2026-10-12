#!/usr/bin/env python3
"""RB-001 Parts 27-28: reality receipts and the sim-to-real transfer classification. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/receipts_and_transfer.py

A receipt records one difference between SITL behaviour and REAL behaviour
that was actually observed (RB0, or real-board statistics applied offline).
Differences that are only expected, not observed, belong in the reality-gap
audit, not here.

Transfer classes (the brief): TRANSFERS_DIRECTLY, TRANSFERS_AFTER_RECALIBRATION,
REQUIRES_NEW_VALIDITY_CONDITION, REQUIRES_NEW_MODEL, DOES_NOT_TRANSFER.
"A method is not validated merely because its architecture transfers": every
class below is a prediction or an RB0 observation; none is a physical
validation. Writes REALITY_RECEIPTS.json and TRANSFER_CLASSIFICATION.json.
"""
from __future__ import annotations

import common_rb as C

RECEIPTS = [
    {"id": "RR-01", "assumption": "every PX4 log has PX4 547e2ca's estimator_status schema",
     "sitl_behavior": "all 2.2/2.3 logs had it; the stock path ran",
     "physical_behavior": "6/6 reachable real/older logs lack fields (accel_device_id, hdg_test_ratio): the stock path CRASHED (KeyError)",
     "evidence": "RB0_REAL_LOGS.json (before the fix)",
     "impact_on_csia": "no report at all on other PX4 versions", "calibration_fix": False,
     "evidence_definition_fix": False, "model_limitation": "one contract per PX4 schema version",
     "product_consequence": "FIXED narrowly: a schema mismatch is a coverage notice and the estimator producer is not run (runs.stock_flight); test in tests/test_rb001_reality_bridge.py; historical outputs unchanged",
     "status": "fixed"},
    {"id": "RR-02", "assumption": "an ordinary PX4 log carries actuator_motors and esc_status at 547e2ca's default rates",
     "sitl_behavior": "present at 10 Hz",
     "physical_behavior": "absent on all 4 real boards (pre-control-allocation PX4); a newer SITL log logs esc_status at 4 Hz",
     "evidence": "RB0_REAL_LOGS.json topics_absent; timing", "impact_on_csia": "no propulsion evidence on older vehicles; 0-1 of 29 profile records observed",
     "calibration_fix": False, "evidence_definition_fix": False,
     "model_limitation": "the stock bridge needs PX4 >= control allocation and ESC telemetry",
     "product_consequence": "reported honestly (coverage notices); state the supported PX4 range in the product documentation",
     "status": "documented"},
    {"id": "RR-03", "assumption": "logs have no dropouts",
     "sitl_behavior": "0 logger dropouts in 79 SITL flights",
     "physical_behavior": "3 of 4 real logs have dropouts: 4 (119 ms), 1 (10 ms), 1 (30 ms)",
     "evidence": "RB0_REAL_LOGS.json logger_dropouts", "impact_on_csia": "windows over a dropout must be refused",
     "calibration_fix": False, "evidence_definition_fix": False, "model_limitation": None,
     "product_consequence": "already handled: LOG_COMPLETENESS flagged 6/6 real dropouts",
     "status": "transfers"},
    {"id": "RR-04", "assumption": "sample spacing is regular at the default interval",
     "sitl_behavior": "actuator_outputs jitter about 0-9 ms; largest gaps 4-16 ms",
     "physical_behavior": "real boards: 1.4-16 ms jitter at 100 ms, gaps up to 164 ms; applied to a SITL loss log, the product's default-rate re-decimation creates gaps above the 3-interval rule and the motor loss (C = 0.664) is refused",
     "evidence": "RB0_REAL_LOGS.json timing; LOG_COMPLETENESS_STRESS.json V4/real_jitter",
     "impact_on_csia": "real faults may go unreported on real, jittery logs (an honest refusal, but a miss)",
     "calibration_fix": False, "evidence_definition_fix": True,
     "model_limitation": None,
     "product_consequence": "SPECIFIED, NOT APPLIED: re-decimate only topics logged faster than their default; measure gaps against the log's own median interval. Gate: the first real propulsion log",
     "status": "open"},
    {"id": "RR-05", "assumption": "the logging rate is PX4 547e2ca's default",
     "sitl_behavior": "it is",
     "physical_behavior": "rates differ by version and by logging profile (esc_status 4 Hz in a newer SITL log; CubeOrange's reduced profile logs actuator_outputs at about 9 Hz with 16 ms jitter); at 2 Hz (stress) every propulsion window is refused",
     "evidence": "RB0_REAL_LOGS.json; LOG_COMPLETENESS_STRESS.json rate_reduced_2Hz",
     "impact_on_csia": "total refusal on slower-logged vehicles", "calibration_fix": False,
     "evidence_definition_fix": True, "model_limitation": None,
     "product_consequence": "same fix as RR-04", "status": "open"},
    {"id": "RR-06", "assumption": "the peak body rate measures maneuvering only",
     "sitl_behavior": "SIH hover nulls max 0.049 rad/s; theta_steady 0.0989",
     "physical_behavior": "real boards at rest: 5 s peaks above 0.0989 rad/s in some windows on all three disarmed boards; a 0.067 rad/s uncorrected yaw bias on a CubeOrange at rest",
     "evidence": "RB0_REAL_LOGS.json gyro",
     "impact_on_csia": "on a real vehicle the compensation may never be assessable (NOT_STEADY_FLIGHT everywhere)",
     "calibration_fix": "partly", "evidence_definition_fix": True,
     "model_limitation": "a maximum is the wrong statistic under noise; remove the window median or use PX4's bias-corrected rate",
     "product_consequence": "recalibrate and redefine on RB3/RB5 data before relying on the compensation outside SITL",
     "status": "open"},
    {"id": "RR-07", "assumption": "one IMU, one EKF2 lane",
     "sitl_behavior": "SIH: one IMU, one magnetometer, no lane switch possible",
     "physical_behavior": "a real CubeOrange logs three gyro, three accelerometer and two magnetometer instances",
     "evidence": "RB0_REAL_LOGS.json (sample_log_small topics)",
     "impact_on_csia": "lane switches and IMU-instance lineage changes happen on hardware; the frozen lane-switch design becomes runnable without a simulator change",
     "calibration_fix": False, "evidence_definition_fix": False, "model_limitation": None,
     "product_consequence": "lineage roots must name the selected IMU instance (2.2 already does); run the lane-switch design on a multi-IMU board (HIL_AND_LANE_SWITCH.md)",
     "status": "documented"},
    {"id": "RR-08", "assumption": "publication time equals acquisition time",
     "sitl_behavior": "timestamp minus timestamp_sample = 0",
     "physical_behavior": "0.40 ms median, 0.44 ms p99 on a real CubeOrange (vehicle_angular_velocity)",
     "evidence": "RB0_REAL_LOGS.json timing", "impact_on_csia": "none for IMU-derived evidence (windows 0.2-15 s)",
     "calibration_fix": False, "evidence_definition_fix": False,
     "model_limitation": "ESC telemetry latency is still unmeasured (no sample time in esc_status)",
     "product_consequence": "keep 2.2 content time for IMU-derived outputs; measure ESC latency at RB2-0",
     "status": "transfers (IMU); open (ESC)"},
]

TRANSFER = [
    {"producer": "px4:esc.telemetry_response", "class": "TRANSFERS_AFTER_RECALIBRATION",
     "also": "REQUIRES_NEW_VALIDITY_CONDITION in forward flight (inflow) and if THR_MDL_FAC is wrong",
     "why": "noise, quantization and per-motor offsets are recalibration problems; position-dependent inflow is not"},
    {"producer": "px4:allocator.compensation", "class": "REQUIRES_NEW_VALIDITY_CONDITION",
     "also": "steadiness must be redefined (RR-06); payload/mass changes have no calibration answer",
     "why": "the statistic is sound in a symmetric, constant-mass hover; the conditions that make it sound are what reality breaks"},
    {"producer": "2.3 steadiness condition (theta_steady)", "class": "DOES_NOT_TRANSFER",
     "also": "as defined (a maximum against an SIH threshold); needs a new definition",
     "why": "RB0: rest-state real boards exceed it"},
    {"producer": "px4:vehicle.rate_transient", "class": "DOES_NOT_TRANSFER",
     "also": "as evidence; stays context",
     "why": "a 0.2 s window needs onset accuracy that real timing and noise do not give (2.3 UNKNOWN_ONSET.md)"},
    {"producer": "px4:allocator.status", "class": "TRANSFERS_DIRECTLY",
     "also": None, "why": "PX4's own flags; nothing calibrated by CSIA"},
    {"producer": "px4:battery.status", "class": "TRANSFERS_DIRECTLY",
     "also": "gains reach with a power module (source health NOMINAL)", "why": "presence semantics, no threshold"},
    {"producer": "px4:ekf2.estimator_status (2.2)", "class": "TRANSFERS_DIRECTLY",
     "also": "only on the contract's PX4 schema; DOES_NOT_TRANSFER across versions until per-version contracts exist (RR-01)",
     "why": "EKF2's own gates"},
    {"producer": "event discovery: telemetry and compensation CUSUMs", "class": "TRANSFERS_AFTER_RECALIBRATION",
     "also": "and the maneuvering false-event rate needs maneuver-aware discovery", "why": "k and h are SIH's"},
    {"producer": "event discovery: PX4 monitor triggers", "class": "TRANSFERS_DIRECTLY",
     "also": "real warnings will add candidate events", "why": "PX4's own"},
    {"producer": "log completeness", "class": "REQUIRES_NEW_VALIDITY_CONDITION",
     "also": "dropout detection transfers (RR-03); the gap rule's reference interval does not (RR-04, RR-05)",
     "why": "real jitter and logging rates"},
    {"producer": "frozen v1.1 CUSUM", "class": "DOES_NOT_TRANSFER",
     "also": None, "why": "no input in a PX4 log (2.3)"},
    {"producer": "maneuver-study B3/B4 (research candidate, not in the product)", "class": "REQUIRES_NEW_MODEL",
     "also": "the plant model (g, c, mixing) must be identified on each vehicle from its own nominal flights",
     "why": "it is model-based; the model is SIH's until identified on hardware"},
]


def main():
    C.write_json(C.HERE / "REALITY_RECEIPTS.json", {
        "label": "RB-001 Part 27: observed SITL-vs-real differences only", "receipts": RECEIPTS})
    C.write_json(C.HERE / "TRANSFER_CLASSIFICATION.json", {
        "label": "RB-001 Part 28: predictions and RB0 observations; NONE is a physical validation",
        "classes": TRANSFER})
    print(len(RECEIPTS), "receipts;", len(TRANSFER), "producers classified")


if __name__ == "__main__":
    main()
