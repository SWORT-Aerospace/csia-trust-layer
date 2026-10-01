# Run S1: the EKF2 selector in SITL (SENS_IMU_MODE = 0). Result

**2026-10-01. NON-CONFIRMATORY.** Design frozen first, at commit e58eaed
(`SITL_SELECTOR_RUN_DESIGN.md`).

**Harness:** `sitl_selector_run.py` (flight), `analyze_s1.py` (analysis).
**Results:** `S1_RESULTS.json`; `reports/S1/report.{json,txt}`.
**Committed extract:** `data/S1_estimator_extract.npz`, from which the
analysis reproduces without the raw log.

## 1. Answer to the request

**Answer: this is not a lane-switch test.**
- The SITL test ran with `SENS_IMU_MODE` = 0, and the EKF2 selector ran.
- EKF2 created **one lane**, because the stock SIH vehicle has one IMU and one
  magnetometer.
- So **no lane switch occurred, and none could**.
- A real switch needs a simulator change: designed in
  `LANE_SWITCH_EXPERIMENT_DESIGN.md`, not run.

## 2. The run

| item | value |
|---|---|
| build | the XSYS-001 SITL build, `px4` SHA-256 4073466f…dfc085, `ver_sw` 547e2caa |
| parameters (stock `PX4_PARAM_*` override, confirmed in the console) | `SENS_IMU_MODE` 1 → 0, `EKF2_MULTI_IMU` 0 → 2 |
| arm / take off / magnetometer OFF / disarm | 45.0 / 45.5 / 75.0 / 100.0 s; every command acknowledged ACCEPTED |
| console | "Injected: mag off, all instances", then "MAG #0 failed: TIMEOUT!" |
| raw ULog | 44,460,605 bytes, SHA-256 561a4ef0…cf8d62, outside git (`/home/user/csia_2_2_pilot_raw/S1/`) |

## 3. The frozen expectations

| id | expectation | observed | met |
|---|---|---|---|
| X1 | selector logged; one lane available; primary 0 | 100 `estimator_selector_status` messages from 0.516 s; `instances_available` = 1; `primary_instance` = 0 throughout | yes |
| X2 | `instance_changed_count` changes once at the initial selection, then never | already 1 at the first logged message (the initial selection preceded it); never changed | yes |
| X3 | one `estimator_status` instance | instance 0 only | yes |
| X4 | magnetometer fusion stops within 5 s of OFF | `mag_hdg` / `mag_3D` both clear at 75.496 s (0.50 s after); `hdg_test_ratio` NaN from then on; no other yaw source (GNSS yaw, vision yaw) fused | yes |
| X5 | no estimator fault; the vehicle keeps hovering | no `filter_fault_flags` bit 0-15 ever set; disarm as scheduled | yes |

**Also seen:**
- `sensor_selection` was published once (gyro 1310988).
- The last logged `vehicle_magnetometer` message is at 74.492 s, at that
  topic's logging interval.

## 4. The Analyzer on the first real selector log

| id | expectation | observed |
|---|---|---|
| A1 | PX4 adapter in SELECTOR mode | yes: the lane epoch comes from the real `instance_changed_count` |
| A2 | after alignment, every output admitted and stamped; 0 CONFIGURATION_MISMATCH | 0 mismatches; every output stamped `{"ekf2.selector.instance_changed_count": 1}` |
| A3 | heading claim NOT_APPLICABLE after X4; the transition in the timeline | NOT_APPLICABLE from 75.496 s; the timeline opens a new interval at 75.5 s on `epochs` (`ekf2.aiding.hdg`) |
| A4 | no estimator output attributed | none: no symptom and NO_EVIDENCE throughout |

**Rejections:** 84, all PRODUCER_UNAVAILABLE before alignment (0.6-2.6 s).

**Timeline:** 1,006 ticks in 11 intervals.

## 5. Metrics

| id | metric | result |
|---|---|---|
| M1 | selector present, SELECTOR mode | yes |
| M2 | lane-epoch changes after the initial selection | 0 |
| M3 | aiding transition after the injection | 0.50 s |
| M4 | valid estimator outputs refused after alignment | 0 |
| M5 | reported as a lane-switch test | no |

## 6. What it adds and what it does not

**Adds:**
- the 2.2 PX4 adapter's selector path and lane epoch, on a real log for the
  first time;
- a real aiding transition from a real sensor failure, at a known time.

**Does not add:** any evidence about what happens when the lane changes.
That rule is still pinned only on the synthetic log.

**A finding for the report (Phase 14).** The timeline line at 75.5 s said
"changed: epochs" without naming the key or its values. An engineer needs
"ekf2.aiding.hdg 1 → 2 (heading aiding lost)". This is addressed in the
Analyzer MVP (`ANALYZER_MVP.md`).
