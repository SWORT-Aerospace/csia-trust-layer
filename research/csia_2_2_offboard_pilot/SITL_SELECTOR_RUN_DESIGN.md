# SITL run S1: EKF2 selector enabled (SENS_IMU_MODE = 0). Frozen design

**2026-10-01. Frozen before the run. Phases 10 and 11 of the pilot brief.**

## 1. What the owner asked, and what the stock simulator can do

**Request.** "Run the SITL lane-switch test with SENS_IMU_MODE=0."

**What the source shows** (PX4 547e2ca, read at the lines cited, V4):

| fact | where |
|---|---|
| EKF2 runs the selector and multiple lanes only when `SENS_IMU_MODE` = 0 | `src/modules/ekf2/EKF2.cpp` lines 2995-3064 |
| it creates one lane per (IMU, magnetometer) pair whose `vehicle_imu` / `vehicle_magnetometer` instance is advertised | `EKF2.cpp` lines 3066-3131 |
| SIH publishes exactly one IMU, device 1310988 | `src/modules/simulation/simulator_sih/sih.hpp` lines 133-134 |
| the magnetometer simulator is a single module instance, device 197388, with Off and Stuck failure injection | `src/modules/simulation/sensor_mag_sim/SensorMagSim.hpp` line 87, `SensorMagSim.cpp` lines 94-99 |

**Consequence.** With the stock SIH vehicle, EKF2 can create one lane only,
so **a lane switch cannot occur**. A real lane switch needs a second IMU or
a second magnetometer in the simulator: simulator work, designed in
`LANE_SWITCH_EXPERIMENT_DESIGN.md` and not run (pilot Phase 11: "if
significant simulator work is required: STOP at design").

**What this run can show, with no change to PX4 or the simulator:**
- the first real log in this repository with the EKF2 selector running;
- the first real `estimator_selector_status` and selector-published
  `sensor_selection`;
- the 2.2 adapter's SELECTOR mode on real data. Until now it was exercised
  only on a synthetic two-lane log;
- a real aiding transition, from stock failure injection of the
  magnetometer.

**It is not a lane-switch test,** and its results will not be reported as
one.

## 2. Apparatus (existing, unmodified)

**Build.** The XSYS-001 PX4 SITL build, `px4_sitl_default` at 547e2ca with
the SIH_MOT_EFF patch. Every `SIH_MOT_EFF` stays at its default 1.0, which
the apparatus's nominal-equivalence gate showed equal to the unpatched
build. Its SHA-256 is recorded with the run.

**Vehicle.** SIH quadrotor (`sihsim_quadx`, airframe 10040), lockstep, speed
factor 1.

**Parameters**, set through the stock `PX4_PARAM_<name>` environment
override (`ROMFS/.../init.d-posix/rcS` line 234), applied before EKF2
starts:

| parameter | value | why |
|---|---|---|
| `SENS_IMU_MODE` | 0 | starts the EKF2 selector |
| `EKF2_MULTI_IMU` | 2 | asks for two IMU lanes; only one IMU exists, so the log shows what EKF2 does with the request |
| `SYS_FAILURE_EN` | 1 | the SITL default, stated |

**Driver.** `sitl_selector_run.py`:
- imports the apparatus's `run_trial.Vehicle` (no apparatus file is edited);
- uses the apparatus logger topics plus the selector and estimator topics.

**Schedule, simulated time from boot:**

| time | event |
|---|---|
| 45 s | arm |
| 45.5 s | take off to 10 m; PX4 holds position |
| 75 s | `MAV_CMD_INJECT_FAILURE` (420): unit magnetometer (2), type OFF (1), instance 0 (all) |
| 100 s | disarm |

Arming is late because EKF2 may wait up to 30 s at start-up for the second
IMU it was asked for (`EKF2.cpp` line 3077).

**Raw data.** The ULog is not committed. Its SHA-256, the command and the
console are. A compressed extract of the topics the analysis reads is
committed (`data/S1_estimator_extract.npz`), so the analysis is reproducible
from the repository.

## 3. Expected transitions, stated before the run

| id | expectation |
|---|---|
| X1 | `estimator_selector_status` is logged; `instances_available` = 1; `primary_instance` = 0 throughout |
| X2 | `instance_changed_count` changes exactly once, at the initial selection, and never again |
| X3 | `estimator_status` has one instance |
| X4 | after the magnetometer is turned off, EKF2 stops magnetometer fusion within 5 s: `control_mode_flags` bits 4 (mag_hdg) and 5 (mag_3D) both clear; `hdg_test_ratio` becomes NaN (no heading aiding fused), unless EKF2 switches to another yaw source, which will be reported as it happens |
| X5 | no `filter_fault_flags` bit 0-15 is set; the vehicle keeps hovering until disarm |

## 4. What the Analyzer is expected to do

| id | expectation |
|---|---|
| A1 | the PX4 adapter runs in SELECTOR mode (real `instance_changed_count`) |
| A2 | after alignment, every estimator output is ADMISSIBLE and stamped with the real lane epoch; 0 CONFIGURATION_MISMATCH (no switch occurs) |
| A3 | the heading claim becomes NOT_APPLICABLE after X4, and the timeline shows the aiding transition as a configuration change at that time |
| A4 | no estimator output is attributed to a component (the claims are non-attributable) |

## 5. Success metrics

| id | metric | pass |
|---|---|---|
| M1 | selector topic present and the adapter in SELECTOR mode | yes |
| M2 | lane epoch changes after the initial selection | 0 (confirms the single-lane limit) |
| M3 | aiding transition after the injection | within 5 s |
| M4 | valid estimator outputs refused after alignment | 0 |
| M5 | the run is reported as a lane-switch test | never |

**A failed expectation is reported as it is, not re-run until it passes.**
