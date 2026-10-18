# Real data first (PRIME Track B1)

**2026-10-02.**

- **Scripts:** `real_logs.py`.
- **Output:** `REAL_LOG_RESULTS.json`.

**SITL is not physical evidence.** Nothing in this document is
calibrated on, and nothing here is SITL.

## 1. The search, in the brief's order of preference

| # | source | route tried | result | licence / provenance |
|---|---|---|---|---|
| 1 | **user-supplied PX4 ULogs** | the repository, every remote branch (fetched), every path on this machine | **none**. The only ULogs on disk are SITL (2.3, RB-001, XSYS-001, apparatus runs) and the files below | — |
| 2 | **public real PX4 logs** | PX4 Flight Review (logs.px4.io) | **refused** by the environment's network policy (connection refused at the proxy, code 000) | — |
| 2 | | PX4/pyulog test logs (raw GitHub) | 6 logs, already analysed in RB-001: 4 real boards, 2 SITL; no propulsion event, at most 1.1 s airborne | BSD-3; SHA-256 in `RB0_REAL_LOGS.json` |
| 2 | | **the PX4-Autopilot checkout at 547e2ca** (from earlier work in this container), docs assets | **1 new real log:** `sample_log_boat_testing_2022-7-28-13-31-16.ulg`, PlotJuggler's sample. A Pixhawk FMUv5, PX4 git 32f79c3772ca (about 1.13), airframe 50005 (a boat; `vehicle_status.vehicle_type` = 3, rover), 496 s, armed 294 s | PX4 docs (CC-BY-4.0); SHA-256 `304d21d5…5bc9749` |
| 2 | | PX4/flight_review repository (git, public) | no sample logs in the repository (commit ea5c16a) | BSD-3 |
| 3 | **real actuator / ESC datasets** | RflyMAD (Zenodo; the project site rfly-openha.github.io) | **refused** by the network policy | — |
| 3 | | RflyMAD's tool repository `lerlis/data_processing_tools` (git, public, commit 3b5b326) | (a) **the topic descriptor of the 497 real flights' ULogs** (`data_real_PX4.json`); (b) two real flights as **ROS bags** (MAVROS only: IMU, RC out, battery, estimator status; no ESC) | **no licence file in the repository:** used as a description only; nothing redistributed |
| 3 | | ALFA (Figshare), Hugging Face, Kaggle, IEEE DataPort | refused by the network policy | — |
| 4 | **HIL logs** | — | none exist; no HIL hardware | — |
| 5 | **bench data from this program** | — | none: no USB bus, no serial/I2C/SPI device in this environment | — |

**Result: the real propulsion corpus is still empty.** It has no real
multirotor flight with ESC telemetry, and no real fault. The real data
reachable is:
- one real boat log;
- four real board logs that barely flew;
- one dataset's structure.

## 2. What RflyMAD's real logs would give, read from its descriptor

**The most useful public dataset, if the network policy allowed it**, is
RflyMAD (Le et al. 2023): 497 real multicopter flights with labelled
faults. Its real ULogs carry:
- `esc_status` with **RPM, current and voltage**;
- `battery_status` with **measured current**;
- `vehicle_angular_velocity`, `vehicle_rates_setpoint`, `rate_ctrl_status`;
- `actuator_controls_0` (the torque and thrust demand of pre-allocation
  PX4) and `actuator_outputs` (PWM);
- `sensor_gyro_fft`, `sensor_accel` (vibration).

**They do not carry** `actuator_motors`, `control_allocator_status` or
`vehicle_torque_setpoint`. They were recorded with PX4 from before control
allocation.

**What that means for the product as it stands:**
- **the stock ESC telemetry producer and the allocator compensation would
  not run.** They read `actuator_motors` and `control_allocator_status`.
  The coverage notices would say so: no false answer, but no propulsion
  answer either.
- **ESC current is present,** so `actuation.electrical_response` and the
  stall check (2.1.1's STALL_SIGNATURE) would become observable for the
  first time.
- **B3** (`MANEUVER_STUDY.md` in RB-001) needs a torque demand.
  `actuator_controls_0` carries exactly that in this PX4 version, so B3
  could be computed with an input mapping, not a new model.

**The decision this informs (owner):** whether to allow Zenodo in the
environment's network policy, and whether pre-allocation PX4 is in the
product's support boundary (`SUPPORT_MATRIX.json`).

## 3. The product, unchanged, on every real log (`REAL_LOG_RESULTS.json`)

| log | board | airframe | armed | events | symptoms | profile gate | records observed |
|---|---|---|---|---|---|---|---|
| sample.ulg | AUAV X2.1 | 10020 | 0 s | 0 | none | ACCEPTED | 0 / 29 |
| sample_appended.ulg | Pixracer (FMUv4) | 4001 | 0 s | 0 | none | ACCEPTED | 1 / 29 |
| sample_appended_multiple.ulg | FMUv4 Pro | 4001 | 0 s | 0 | none | ACCEPTED | 0 / 29 |
| sample_log_small.ulg | CubeOrange | 13014 (VTOL) | 5.6 s | 0 | none | ACCEPTED | 1 / 29 |
| **boat (PX4 docs)** | **FMUv5** | **50005 (boat)** | **294 s** | **12** | **none** | **ACCEPTED** | 1 / 29 |

**No crash on any real log, and no false symptom on any.** RR-01's fix
holds on a further PX4 version: the boat's `estimator_status` also lacks
`hdg_test_ratio`.

## 4. What the real boat log measured

**1. An unsupported vehicle is analysed as a quadrotor without saying so.**
- The profile gate checks the profile, not the vehicle. It returned
  ACCEPTED for a boat.
- The report's coverage notices say the motor producers did not run
  ("actuator_motors or esc_status missing, or CA_ROTOR_COUNT < 2"). That is
  true, but it is not the answer an engineer needs: **"this vehicle type is
  outside the supported boundary."**
- **Measured usability gap;** answered in Track A by the support check.

**2. PX4's own warnings fragment one condition into many events.**
- **The battery:** `battery_status.warning` rose 32 times in 294 s armed.
  The voltage sat near PX4's low threshold under load (13.36-15.92 V), so
  the product's 3 s clustering made **9 battery-warning events from one
  persistent condition**.
- **The other events:** log messages (kill switch engaged 4 times, low
  battery twice, preflight failures).
- **The rate:** **12 events in 294 s armed, 147 per armed hour**, on a real
  vehicle, from PX4's own monitors alone (no CUSUM noise; the propulsion
  producers did not run). The budget is 6 per hour
  (`FALSE_ALARM_BUDGET.md` in RB-001).
- **Measured usability gap;** answered in the view layer by grouping
  re-raised identical conditions (event discovery itself unchanged, so no
  historical report changes).

**3. Real timing against the product's data-access rules** (15 s windows):

| topic | as logged: median / p99 / max (ms) | 547e2ca default | refused by the product's gap rule | with RB-001's specified fix |
|---|---|---|---|---|
| actuator_motors | 100.2 / 102.7 / 115.2 | 100 | **0 / 481** | 0 / 481 |
| control_allocator_status | 200.3 / 205.4 / 215.3 | 200 | 0 / 481 | 0 / 481 |
| battery_status | 200.0 / 210.3 / 220.6 | 200 | 0 / 481 | 0 / 481 |
| vehicle_angular_velocity | 20.0 / 22.6 / 40.1 | 20 | 0 / 481 | 0 / 481 |
| **failure_detector_status** | **509.6 / 527.5 / 529.6** | **100** | **481 / 481** | 0 / 481 |

**Two findings:**
- **RR-04 did not appear on this real FMUv5.** Its propulsion topics'
  interval standard deviation is 2-3 % of the interval: 2.4 ms at 100 ms
  for `actuator_motors`, 4.7 ms at 200 ms for the allocator. That is well
  below the 10 ms timestamp jitter RB-001 applied offline, which came from
  a reduced-profile CubeOrange's `actuator_outputs`. The angular velocity's
  is 1.9 ms at 20 ms (10 %). The jitter
  hazard is real on some boards and absent on this one. Where a given
  vehicle sits is a per-vehicle measurement, now in the support matrix.
- **RR-05 is confirmed on real hardware.** This PX4 version logs
  `failure_detector_status` at 2 Hz, not 547e2ca's 10 Hz. The gap rule,
  applied to that topic, would refuse every window.
  - **No current output is affected:** the topic is read only as an event
    trigger (rising edges), never through the gap rule.
  - **Any future producer on it would be refused everywhere** until the fix
    is applied.

## 5. What remains open

**Every propulsion question is still unanswered on real data:**
- separability;
- the telemetry producer's real noise floor;
- the compensation under real vibration;
- B3.

**The cheapest routes, unchanged from RB-001:**
1. the owner's own ULogs (any PX4 with control allocation and ESC
   telemetry);
2. Zenodo allowed for RflyMAD;
3. the RB2 bench.
