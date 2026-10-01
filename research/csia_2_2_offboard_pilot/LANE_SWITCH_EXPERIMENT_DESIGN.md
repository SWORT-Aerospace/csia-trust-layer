# The smallest experiment that produces a real EKF2 lane switch (Phase 11)

**2026-10-01. DESIGN FROZEN. NOT RUN.** It needs a simulator change. The
pilot brief says: "If significant simulator work is required: STOP at
design."

## 1. Why the existing apparatus cannot do it

**No log in this repository contains an EKF2 lane switch.**
- Every XSYS-001 flight ran with `SENS_IMU_MODE` = 1, so the selector never
  started.
- Run S1 (`SITL_SELECTOR_RUN.md`) ran the selector on the stock SIH vehicle:
  one IMU and one magnetometer, so one lane. The stock vehicle cannot
  switch.

**Source** (PX4 547e2ca, V4):
- `EKF2.cpp` lines 3066-3131: one lane per available (IMU, magnetometer)
  pair;
- `sih.hpp` lines 133-134: SIH has one IMU;
- `SensorMagSim.hpp` line 87: one magnetometer.

## 2. What the selector needs (`EKF2Selector.cpp`, lines 155-205 and 319-352)

| condition | effect |
|---|---|
| ≥ 2 lanes | a switch is possible at all |
| 2 gyros, one inconsistent | `gyro_fault_detected`, but which gyro is faulty cannot be determined; the switch is then decided by the lanes' combined test ratios with a zero threshold |
| ≥ 3 gyros, one inconsistent | the faulty gyro's device id is named; every lane using it is excluded; the best lane on another IMU is selected (`SelectInstance`, `_instance_changed_count++`, line 132) |
| inconsistency | a gyro's difference from the mean of all gyros; it accumulates at (inconsistency − `EKF2_SEL_IMU_RAT`) per second, floored at 0, and a fault is declared above `EKF2_SEL_IMU_ANG` |
| defaults | `EKF2_SEL_IMU_RAT` = 7°/s, `EKF2_SEL_IMU_ANG` = 15° |

**Arithmetic for a bias step `b` on one of `n` gyros:** its inconsistency is
`b·(1 − 1/n)`.
- **n = 2:** `b/2`; the bias must exceed 14°/s just to start accumulating,
  and the faulty IMU is not identified.
- **n = 3:** `2b/3`. With `b` = 20°/s: 13.3°/s, accumulating 6.3°/s, so a
  fault is declared about 2.4 s after onset.

**Chosen: three IMUs** (the common flight-controller configuration), so the
selector names the faulty IMU, and a 20°/s bias step.

## 3. The change it requires

**One SIH change**, on a separate PX4 tree at 547e2ca. The XSYS-001
apparatus build is not touched.

1. **Two more IMUs** in `simulator_sih`: `PX4Accelerometer` / `PX4Gyroscope`
   with device ids 1310996 and 1311004. The SITL defaults already carry
   `CAL_ACC1_ID` 1310996, `CAL_ACC2_ID` 1311004 and the matching gyro ids (seen
   in every XSYS-001 log's parameters). Each IMU gets the same truth and
   independent noise from SIH's existing noise model.
2. **One parameter, `SIH_IMU0_GBIAS`** (°/s, default 0): a constant bias
   added to IMU 0's gyro x axis. It is set at onset by PARAM_SET, as
   `SIH_MOT_EFF` was in XSYS-001.

**Size:** about 40 lines in `sih.hpp` / `sih.cpp`, plus one parameter
definition.

**Governance:** a simulator change like this needs the owner's approval. The
SIH_MOT_EFF patch had it: `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`
records "I approve the PX4 research build and the minimal SIH
actuator-effectiveness patch."

## 4. Configuration and schedule

| item | value |
|---|---|
| parameters | `SENS_IMU_MODE` = 0, `EKF2_MULTI_IMU` = 3, `SENS_MAG_MODE` = 1 (one magnetometer): three lanes |
| arm | 45 s (EKF2 waits for its IMUs at start-up) |
| take off | to 10 m; PX4 holds position |
| onset | 75 s: `SIH_IMU0_GBIAS` = 20 |
| disarm | 100 s |
| logging | the S1 logger topics plus `sensors_status_imu` and every `estimator_status` instance (0-2) |
| repeats | 5 at onset bias 20°/s, and 2 controls at 0°/s |

## 5. Expected transitions, stated now

| id | expectation |
|---|---|
| L1 | `instances_available` = 3; primary lane 0 (IMU 1310988) before onset |
| L2 | within 10 s of onset: `gyro_fault_detected`; `instance_changed_count` increments exactly once; the primary moves to a lane on IMU 1310996 or 1311004; `sensor_selection.gyro_device_id` changes the same way |
| L3 | controls: no increment after the initial selection |

## 6. What the Analyzer must do, and the success metrics

**Analysis at the estimator's publication rate around the switch** (tick
0.004 s from 1 s before to 1 s after it), and at 10 Hz elsewhere.

| id | metric | pass |
|---|---|---|
| S1 | held outputs of the old lane after the selector's switch | all CONFIGURATION_MISMATCH (R-3), none admitted |
| S2 | outputs of the new lane | admitted from its first publication; lineage names the new IMU (`sensor:gyro.<new id>`) |
| S3 | evidence that depends on no lane (a CUSUM or v2 output in the same run) | admitted throughout |
| S4 | valid estimator outputs refused outside the switch interval | 0 |
| S5 | timeline | the lane change appears once, at the selector's publication time, with the transition event |
| S6 | controls | 0 CONFIGURATION_MISMATCH |

**A failure of S1-S6 is a 2.2 defect to report.** A failure of L1-L3 means
the experiment did not produce its condition, and is reported as such.

## 7. What it would add

The first real pin of Phase 19's rule: old-lane evidence stale, new-lane
evidence admissible, unrelated evidence untouched. Until then the rule is
pinned only on a synthetic log (`test_estimator_lane_switch_epoch_pin`) and
by R-3's own tests.
