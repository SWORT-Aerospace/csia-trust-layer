# Validation flights: design, frozen before flying (Phases 17, 20, 25, 26)

**2026-10-02. Written and committed before any of these flights is flown.**

## 1. Why new flights

Existing data runs out in four places:
1. **Motor identity (Phase 17).** Every XSYS-001 fault, and every apparatus
   sweep fault, is on SIH Motor1 (CSIA motor_0). Nothing shows the
   Analyzer localizing motors 1-3.
2. **An ordinary log (Phase 20).** Every XSYS-001 and apparatus log was
   recorded with the apparatus's custom topic list on top of the default
   profile. None is an ordinary log.
3. **False positives under maneuvering (Phase 26).**
   - XSYS-001 flights hover: take-off, hold, onset, about 34 s airborne.
   - Yaw turns move two motors' commands against the other two, which is
     exactly what the compensation statistic watches.
   - Hover data cannot show how often that fires.
4. **Validation-set classes with no real data (Phase 25):**
   - navigation anomaly;
   - power anomaly;
   - a real ESC telemetry fault on a healthy motor.

## 2. Rules

- **Build:** the XSYS-001 SITL build (PX4 547e2ca with the SIH_MOT_EFF1-4
  patch). Its eta = 1 behaviour passed the nominal-equivalence gate. No
  PX4 or simulator file is changed for these runs.
- **Logging:** PX4's DEFAULT logging. No `logger_topics.txt` is installed;
  the board defaults decide.
- **Faults:**
  - partial thrust loss through `SIH_MOT_EFFn`, set over MAVLink as in
    XSYS-001;
  - everything else through PX4's stock failure injection
    (`MAV_CMD_INJECT_FAILURE`, `SYS_FAILURE_EN = 1`).
- **Driver:** the apparatus's MAVLink helper (`run_trial.Vehicle`),
  imported unchanged.
- **Scoring only:** each run's injection time and target are recorded in
  its JSON, for scoring. They are never an input of the Analyzer.
- **Flown once each.** A run that fails to arm or crashes is recorded as
  such and is not re-flown to get a better result.

## 3. The runs

| id | purpose | injection at onset | schedule (s from boot): arm / onset / end |
|---|---|---|---|
| V1 | motor_1 localization | `SIH_MOT_EFF2` = 0.6 | 20 / 50 / 80 |
| V2 | motor_2 localization | `SIH_MOT_EFF3` = 0.6 | 20 / 50 / 80 |
| V3 | motor_3 localization | `SIH_MOT_EFF4` = 0.6 | 20 / 50 / 80 |
| V4 | motor_0, in an ordinary log | `SIH_MOT_EFF1` = 0.6 | 20 / 50 / 80 |
| V5 | nominal, maneuvering | none; repositions 40 m apart with 90 degree yaw changes every 10 s from 40 s | 20 / — / 160 |
| V6 | nominal, maneuvering, wind | as V5, with `SIH_WIND_N` = 5 m/s from boot | 20 / — / 160 |
| V7 | navigation anomaly | GPS off (`FAILURE_UNIT_SENSOR_GPS`, `OFF`, all instances) | 20 / 50 / 90 |
| V8 | power anomaly | battery wrong (`FAILURE_UNIT_SYSTEM_BATTERY`, `WRONG`; critical level, `SYS_FAIL_BAT_LVL` default) | 20 / 50 / 90 |
| V9 | ESC telemetry lost, motor healthy | ESC 2 off (`FAILURE_UNIT_SYSTEM_ESC`, `OFF`, instance 2 = motor_1) | 20 / 50 / 80 |
| V10 | ESC telemetry wrong, motor healthy | ESC 3 wrong (`FAILURE_UNIT_SYSTEM_ESC`, `WRONG`, instance 3 = motor_2: RPM x 10) | 20 / 50 / 80 |

## 4. Expectations, stated before flying

| id | event discovery | stock analysis (config B) |
|---|---|---|
| V1-V4 | one event within 2 s of onset, triggered on the injected motor | COMMAND_NO_RESPONSE on the injected motor only; SENSOR/response_sensor eliminated; ACTUATION/mechanical among the remaining |
| V5, V6 | no event (a false event if one appears) | no symptom |
| V7 | possibly a failsafe or estimator trigger | no propulsion symptom; navigation is outside the profile's diagnosable records (EKF2 context only) |
| V8 | a battery-warning and failsafe trigger | no propulsion symptom; battery warning reported as context; source health UNAVAILABLE (current not measured) |
| V9 | a telemetry trigger on motor_1 | no symptom; the telemetry deficit on motor_1 is not confirmed by the vehicle (compensation nominal) |
| V10 | a telemetry trigger (excess) on motor_2 | no symptom; telemetry excess reported as context |

A run that differs from its expectation is reported as such. The
expectation is not revised.
