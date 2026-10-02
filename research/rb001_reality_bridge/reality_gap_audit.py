#!/usr/bin/env python3
"""RB-001 Part 1: the reality-gap audit, as a structured record. RESEARCH ONLY.

    .venv/bin/python research/rb001_reality_bridge/reality_gap_audit.py

For every evidence claim the 2.3 product (and the maneuver-study candidate)
relies on: the simulation assumption that made it easy, and for each real
threat the expected effect, whether calibration can handle it, whether the
evidence definition must change, and the test that would tell. No evidence
definition is changed here (the brief's rule).

Where RB0 (real logs) or the SITL study already measured something, the row
cites it under `measured`. Writes REALITY_GAP_AUDIT.json.
"""
from __future__ import annotations

import json

import common_rb as C

YES, NO, PARTLY, UNKNOWN = "YES", "NO", "PARTLY", "UNKNOWN"

THREATS = (
    "sensor noise", "sensor bias", "sensor quantization", "timestamp jitter", "clock drift",
    "logging jitter", "packet loss", "ULog dropout", "ESC telemetry latency",
    "ESC telemetry quantization", "RPM estimation error", "motor-to-motor variation",
    "propeller variation", "battery sag", "current measurement noise", "motor heating",
    "ESC heating", "thrust nonlinearity", "deadband", "hysteresis", "mechanical vibration",
    "frame resonance", "aerodynamic disturbance", "wind", "vehicle mass uncertainty",
    "CG uncertainty", "control-loop variation", "actuator saturation", "maneuver coupling",
    "sensor mounting orientation", "calibration error", "real PX4 scheduler behavior")


def row(threat, effect, calibration, definition, test):
    assert threat in THREATS, threat
    return {"threat": threat, "expected_effect": effect, "calibration_can_handle": calibration,
            "definition_must_change": definition, "test_required": test}


CLAIMS = [
    {"claim": "ESC_TELEMETRY_RESPONSE", "statistic": "q_m = (rpm_m^2 / T(c_m)) / median_j; L = 1 - q_after/q_before",
     "role_2_3": "context; trigger (telemetry CUSUM); power gate of the compensation",
     "simulation_assumption": "SIH reports the rotor state as RPM: exact, instantaneous, unquantised, identical motors and propellers, rpm^2 exactly proportional to thrust through PX4's own thrust model (THR_MDL_FAC = 0 in both)",
     "threats": [
         row("ESC telemetry quantization", "eRPM steps (DShot: 1/pole-pairs; serial telemetry: 100 eRPM) add a floor to q's noise", YES, NO, "RB2: logged RPM against an optical tachometer"),
         row("ESC telemetry latency", "RPM lags the command by the telemetry path (bidirectional DShot per frame; serial round-robin tens of ms); event windows are 1.5-5 s, so means are barely affected, the CUSUM onset estimate is", PARTLY, NO, "RB2: command step against RPM, latency distribution"),
         row("RPM estimation error", "a wrong pole count scales all motors alike and cancels in the median normalisation; a per-ESC error does not", YES, NO, "RB2: tachometer"),
         row("motor-to-motor variation", "constant per-motor offsets in q; removed by the event-relative difference (after minus before)", YES, NO, "RB2/RB5: q per motor across runs"),
         row("propeller variation", "as above if constant; a damaged propeller changes q only if it changes thrust per RPM, which RPM cannot show", PARTLY, NO, "RB2: same motor, two propellers, thrust stand"),
         row("thrust nonlinearity", "if THR_MDL_FAC is wrong, q depends on the command level, so climbs and maneuvers move q without a fault", PARTLY, "YES (condition on command level, or use the vehicle's identified thrust curve)", "RB2: thrust-stand sweep of rpm^2 against command"),
         row("battery sag", "lower voltage lowers RPM per command on every motor; the median normalisation cancels a common change", YES, NO, "RB2: supply-voltage sweep"),
         row("motor heating", "slow RPM-per-command drift on one motor; the trailing reference absorbs slow drift (benign), a step is a change", PARTLY, NO, "RB2: long run, thermocouple, q drift"),
         row("aerodynamic disturbance", "forward flight changes inflow differently on front and rear rotors: q splits by position, like a fault", NO, "YES (regime validity: airspeed or attitude condition)", "RB5/RB6: q in forward flight"),
         row("maneuver coupling", "fast command changes: RPM lags, q transiently splits", PARTLY, "MAYBE (window means already average it)", "SITL now; RB5 later"),
         row("sensor noise", "real RPM noise is orders above SIH's: theta_tel = 0.0069 and CUSUM k = 0.039 will fire constantly", YES, NO, "RB2 nominal corpus, RB5 hover"),
         row("ULog dropout", "missing samples: handled by LOG_COMPLETENESS (outputs over a gap UNAVAILABLE)", YES, NO, "RB0 measured: real dropouts flagged"),
         row("ESC heating", "an ESC derating under heat lowers RPM per command on one motor: a genuine loss of effect, correctly a change", YES, NO, "RB2 long run (never by overheating on purpose: observe natural warm-up only)"),
         row("deadband", "ESC/motor deadband at low command makes rpm^2/T(c) nonlinear near idle; samples below MIN_COMMAND (0.15) are already excluded", YES, NO, "RB2 low-command sweep"),
         row("hysteresis", "RPM for a rising command differs from a falling one: maneuvers, which reverse command direction, split q transiently", PARTLY, "MAYBE (window means; or condition on command slope)", "RB2 triangle sweep"),
         row("sensor quantization", "covered by ESC telemetry quantization; command values are floats", YES, NO, "RB2"),
     ]},
    {"claim": "ALLOCATOR_COMPENSATION", "statistic": "C_m = change in c_m / median_j c_j, AFTER [t0+10, t0+15) minus BEFORE",
     "role_2_3": "profile evidence: actuation.physical_response; raises COMMAND_NO_RESPONSE when VIOLATED",
     "simulation_assumption": "a perfectly symmetric vehicle: identical motors and propellers, centre of gravity at the geometric centre, no trim torque, a noise-free command split in hover, constant mass",
     "threats": [
         row("CG uncertainty", "a CG offset is a constant trim in the command split; constant, so the event-relative difference removes it", YES, NO, "RB5: trim before and after a known ballast shift"),
         row("vehicle mass uncertainty", "a payload change mid-flight moves the split exactly like a loss: a false COMMAND_NO_RESPONSE", NO, "YES (needs a validity condition, or corroboration from RPM or current)", "RB5: known ballast added on a restrained vehicle"),
         row("wind", "steady wind adds a steady split; a gust or wind change during the windows moves C", PARTLY, "YES (steadiness must include translational disturbance, or condition on it)", "SITL (CAL3, CAL4, EN1-EN4 have wind); RB6"),
         row("maneuver coupling", "maneuvers move the split as a loss does: measured in 2.3 (V5/V6 false symptoms until NOT_STEADY_FLIGHT); the maneuver study measures the alternatives", NO, "YES (2.3 refuses it; candidates B2-B4)", "SITL maneuver study (this package)"),
         row("mechanical vibration", "vibration adds command noise through the rate loop; window means average it", YES, NO, "RB3/RB5: C null on a running vehicle"),
         row("actuator saturation", "a saturated loop cannot compensate: C understates the loss; 2.3 refuses saturated windows", YES, NO, "SITL (EF flights with eta 0.6 during turns)"),
         row("control-loop variation", "different rate gains change how fast C settles, not where; the AFTER window starts 10 s after", PARTLY, NO, "RB5: two tunings"),
         row("battery sag", "common to all motors: cancels in the ratio to the median", YES, NO, "RB2"),
         row("sensor noise", "real command noise is far above SIH's; theta_ctrl = 0.0069 will not hold", YES, NO, "RB3/RB5 nominal corpus"),
     ]},
    {"claim": "STEADINESS (2.3 r3 validity condition of the compensation)", "statistic": "R = largest |omega| in BEFORE and AFTER, refused above theta_steady = 0.0989 rad/s",
     "role_2_3": "validity condition: compensation UNAVAILABLE (NOT_STEADY_FLIGHT) above it",
     "simulation_assumption": "SIH gyro noise and vibration are tiny, so a peak statistic measures maneuvering and nothing else",
     "threats": [
         row("mechanical vibration", "a peak statistic catches every vibration spike: a hovering real vehicle may never count as steady, so the compensation is never assessable", PARTLY, "YES (a robust statistic: a percentile or a low-passed rate, not the maximum)", "RB0 measured at rest; RB3/RB5 in flight"),
         row("sensor noise", "as above", PARTLY, "YES (same)", "RB0 measured"),
         row("frame resonance", "narrow-band rate oscillation lifts the peak without any maneuver", PARTLY, "YES (same)", "RB3/RB5 spectrum"),
         row("wind", "turbulence keeps rates above theta_steady in calm-looking flight", PARTLY, "MAYBE", "RB6"),
         row("sensor mounting orientation", "a rotated IMU mapping changes the axes, not the magnitude: harmless to R, harmful to the loss axis of D", YES, NO, "RB3"),
         row("sensor bias", "an uncalibrated gyro bias adds a constant to |omega|: R never drops below the bias (RB0: up to 0.067 rad/s yaw bias on a real CubeOrange at rest)", PARTLY, "YES (remove the window median before the peak, or rely on PX4's bias-corrected rate)", "RB0 measured; RB3"),
     ]},
    {"claim": "VEHICLE_RATE_TRANSIENT", "statistic": "D_m = mean body-rate change on motor m's loss axis in [t0, t0+0.2 s)",
     "role_2_3": "context only (0.2 s validity; 2.3 showed its magnitude falls with onset error)",
     "simulation_assumption": "a clean step in rotor effectiveness, a noise-free gyro, an onset known or found to within tens of ms",
     "threats": [
         row("sensor noise", "a 0.2 s mean of a noisy gyro; theta_dyn = 0.029 rad/s from SIH will not hold", YES, NO, "RB3"),
         row("mechanical vibration", "as above, worse", PARTLY, NO, "RB3/RB5"),
         row("timestamp jitter", "the window is 0.2 s; event-time error of tens of ms already halves the magnitude (2.3 UNKNOWN_ONSET.md)", NO, "ALREADY CONTEXT ONLY", "RB0 measured jitter; RB3"),
         row("sensor mounting orientation", "a wrong rotation puts the transient on the wrong motor's axis", NO, "YES (needs the board rotation, SENS_BOARD_ROT, in the lineage)", "RB3: rotated board"),
         row("CG uncertainty", "moves the loss axes slightly", PARTLY, NO, "RB5"),
     ]},
    {"claim": "CONTROL-CONDITIONED RESIDUAL (maneuver-study candidate B3/B4; not in the product)", "statistic": "d_tau = lp(tau_sp) - (omega_dot - c)/g; per-motor loss fraction",
     "role_2_3": "none: research candidate",
     "simulation_assumption": "the torque setpoint is the torque the allocator applied; omega_dot is clean; inertia and effectiveness are constant; no trim torque",
     "threats": [
         row("sensor noise", "omega_dot is a differentiated gyro: real noise is large; window means and the GLR weighting reduce it", PARTLY, NO, "RB3/RB5"),
         row("mechanical vibration", "as above; IMU_DGYRO_CUTOFF filters it at the cost of lag", PARTLY, NO, "RB3/RB5"),
         row("CG uncertainty", "a trim torque is a constant d_tau: event-relative difference removes it", YES, NO, "RB5"),
         row("vehicle mass uncertainty", "inertia scales g: a payload changes g and so the residual during maneuvers (not in hover)", PARTLY, "MAYBE (re-identify g, or refuse after a configuration change)", "RB5 ballast"),
         row("battery sag", "less torque per normalised setpoint on every motor: g drops during the flight; roll/pitch residual grows with maneuver intensity", PARTLY, "MAYBE (g as a function of voltage)", "RB2/RB5 voltage sweep"),
         row("thrust nonlinearity", "the setpoint-to-torque map is not linear at the extremes", PARTLY, NO, "RB2 thrust stand"),
         row("actuator saturation", "the setpoint is not achieved by design: refused when the allocator reports it", YES, NO, "SITL"),
         row("control-loop variation", "the model is of the plant, not the controller: retuning does not change it", YES, NO, "RB5"),
         row("propeller variation", "a weaker propeller is a smaller b_m: indistinguishable from a partial loss (it is one)", NO, NO, "RB2"),
     ]},
    {"claim": "BATTERY_SOURCE_STATUS", "statistic": "voltage and current present and readable",
     "role_2_3": "profile evidence: power.source_health",
     "simulation_assumption": "SIH reports no current (current_a = -1), so the record is always UNAVAILABLE",
     "threats": [
         row("current measurement noise", "with a power module the record becomes NOMINAL and POWER/path_unavailable becomes eliminable: the claim gains reach; its meaning (present and readable) needs no threshold", YES, NO, "RB2/RB3 with a power module"),
         row("calibration error", "a wrong amps-per-volt still reads as present: the claim says nothing about accuracy", NO, "NO (the claim is presence, by v2 semantics)", "RB2: shunt against module"),
         row("battery sag", "context: PX4's warning and the voltage floor", YES, NO, "RB2"),
     ]},
    {"claim": "PX4 MONITORS AS TRIGGERS (failure detector, battery warning, failsafe, WARNING messages, allocator)", "statistic": "rising edges in flight",
     "role_2_3": "event discovery only",
     "simulation_assumption": "SIH flights log almost no warnings; the failure detector never fired",
     "threats": [
         row("real PX4 scheduler behavior", "real flights log more warnings (GPS, sensor, timing): more candidate events, each dismissed or not", PARTLY, NO, "RB0 with real flight logs (not reachable here); RB5/RB6"),
         row("calibration error", "PX4's own thresholds (FD_FAIL_R/P, battery levels) are the vehicle's, not CSIA's: nothing to calibrate", YES, NO, "none"),
     ]},
    {"claim": "ESTIMATOR_STATUS (2.2 adapter)", "statistic": "EKF2 test ratios, aiding and resets",
     "role_2_3": "context (navigation integrity)",
     "simulation_assumption": "one PX4 version (547e2ca) and its estimator_status schema; one IMU, one EKF lane in SIH",
     "threats": [
         row("calibration error", "another PX4 version renames or lacks fields: 2.3 CRASHED on every reachable real log until RR-01 (now a coverage notice)", NO, "YES (done: schema mismatch is a notice; a per-version contract is the real fix)", "RB0 measured"),
         row("sensor noise", "real innovations are larger; the 1.0 gate is EKF2's own", YES, NO, "RB0 real flights (not reachable here)"),
         row("real PX4 scheduler behavior", "multiple IMU and EKF lanes on real boards: lane switches happen, which SIH never showed", PARTLY, NO, "RB3/RB4: lane-switch experiment"),
     ]},
    {"claim": "LOG_COMPLETENESS", "statistic": "a logger dropout or a gap over 3 logging intervals inside a window",
     "role_2_3": "producer health: outputs over a gap UNAVAILABLE",
     "simulation_assumption": "SITL logs had no dropouts at all (0 in 79 flights)",
     "threats": [
         row("ULog dropout", "real logs have them (RB0: 3 of 4 real logs, 10-119 ms); every one was flagged", YES, NO, "RB0 measured"),
         row("logging jitter", "real topic jitter is larger (RB0: actuator_outputs 1.4-16 ms std; largest gaps 65-164 ms) but below the 3-interval rule in most windows", YES, NO, "RB0 measured; RB3"),
         row("packet loss", "MAVLink loss does not touch the ULog; a telemetry-link producer would need its own rule", YES, NO, "not needed now"),
     ]},
    {"claim": "CONTENT TIME (2.2 semantics)", "statistic": "stock producers use the ULog `timestamp` (publication) as content time",
     "role_2_3": "admissibility and validity windows",
     "simulation_assumption": "publication time equals acquisition time",
     "threats": [
         row("timestamp jitter", "IMU publish-minus-sample 0.4 ms on a real CubeOrange (RB0): negligible against 0.2-15 s windows", YES, NO, "RB0 measured"),
         row("ESC telemetry latency", "ESC telemetry carries no sample time in esc_status: its true age is unknown", NO, "MAYBE (content time of ESC outputs = publication minus a measured latency)", "RB2: command step against RPM"),
         row("clock drift", "one clock (the FMU's) stamps every topic; drift matters only against external ground truth", YES, NO, "RB2: align external instruments by a shared step"),
     ]},
]


def main():
    rb0 = json.loads((C.HERE / "RB0_REAL_LOGS.json").read_text())["logs"]
    measured = {
        "real_logger_dropouts": {k: v["logger_dropouts"] for k, v in rb0.items() if v["real_hardware"]},
        "real_dropouts_flagged_by_log_completeness": {k: [v["stocklog_dropouts_seen"], v["dropouts_flagged_by_gap_in"]]
                                                      for k, v in rb0.items() if v["real_hardware"]},
        "real_gyro_peak_rate_at_rest_rad_s": {k: v["gyro"]["peak_rate_rad_s"] for k, v in rb0.items()
                                              if v["real_hardware"]},
        "real_windows_over_theta_steady": {k: [v["gyro"]["windows_over_theta_steady"], v["gyro"]["windows_5s"]]
                                           for k, v in rb0.items() if v["real_hardware"]},
        "product_on_real_logs_before_RR01": "KeyError in the estimator reader on 6/6 logs",
    }
    index = {t: [c["claim"] for c in CLAIMS if any(r["threat"] == t for r in c["threats"])]
             for t in THREATS}
    C.write_json(C.HERE / "REALITY_GAP_AUDIT.json", {
        "label": "RB-001 Part 1: reality-gap audit; no evidence definition changed",
        "claims": CLAIMS, "threat_index": index,
        "threats_with_no_claim_row": [t for t, v in index.items() if not v],
        "measured_so_far": measured})
    print(len(CLAIMS), "claims;", sum(len(c["threats"]) for c in CLAIMS), "rows;",
          "uncovered threats:", [t for t, v in index.items() if not v])


if __name__ == "__main__":
    main()
