# Validation flights: results against expectations stated before flying

**2026-10-02.**

**Designs, each committed before its flights were flown:**
- `VALIDATION_FLIGHTS_DESIGN.md` (6812abc): V1-V10;
- `VALIDATION_FLIGHTS_DESIGN_2.md` (edcb896): V11-V13, a blind test of the
  fixes the first set forced.

**Scripts:**
- runner: `sitl_validation_runs.py`;
- analysis: `validation_analysis.py`. It runs the product path on the ULog
  alone, then reads each run's JSON for scoring. Symptoms are scored at
  every tick of the timeline, not only at the end.

**Results:**
- `VALIDATION_RESULTS_AS_FLOWN.json`: V1-V10 with the code as frozen in
  6812abc;
- `VALIDATION_RESULTS.json`: V1-V13 with the final code;
- `reports/V1`-`V13`: the product's own reports.

**Raw logs are not committed.** Their SHA-256 values are in the results.

## 1. All thirteen were flown

Every run armed, flew its schedule and disarmed, with PX4's default
logging. None was re-flown. Every `MAV_CMD_INJECT_FAILURE` was ACCEPTED,
and every parameter injection was acknowledged.

## 2. First design, V1-V10 (configuration B, the product default)

| run | expectation (stated before flying) | as frozen (6812abc) | final code | as expected? |
|---|---|---|---|---|
| V1-V4 | one event within 2 s, on the injected motor; COMMAND_NO_RESPONSE on that motor only; response_sensor eliminated; mechanical remains | exactly that, motors 1, 2, 3, 0; onset errors -0.156 to -0.056 s | same; no other motor at any time | **yes** (4/4) |
| V5 | nominal maneuvering: no event; no symptom | **11 events; 11 times a transient false `COMMAND_NO_RESPONSE` on motors 0 and 1**, each withdrawn when its evidence aged out. The end-of-log result read "no symptom" and hid them. | 11 events; **no symptom at any time** | **no**: false events (and, as frozen, false symptoms) |
| V6 | as V5, 5 m/s wind | as V5: 11 events, 11 transient false symptoms on motors 0 and 1 | 11 events; no symptom at any time | **no**: same |
| V7 | GPS off: possibly a failsafe or estimator trigger; no propulsion symptom | PX4 log message at injection (+0.004 s), failsafe 5 s later; no symptom | same | **yes** |
| V8 | battery wrong: battery-warning and failsafe triggers; no propulsion symptom; warning as context; source health UNAVAILABLE | all of that, at +0.004 s | same | **yes** |
| V9 | ESC 2 off: telemetry trigger on motor_1; no symptom; compensation NOMINAL (deficit not confirmed) | trigger and no symptom; offline ESC read as a 100 % deficit; compensation UNAVAILABLE | telemetry UNAVAILABLE (ESC_TELEMETRY_OFFLINE); compensation NOT_APPLICABLE; no symptom | **no**: part of the expectation not met (section 4) |
| V10 | ESC 3 wrong: telemetry trigger (excess) on motor_2; no symptom; excess as context | PX4 log message at injection; excess L = -98.6 on motor_2 as context; no symptom | same | **yes** |

## 3. Second design, V11-V13: the fixes, tested blind

| run | expectation (stated before flying) | result (final code = the code in edcb896, plus a report-text change) | as expected? |
|---|---|---|---|
| V11 | nominal, maneuvering (15 s, 60 m legs, 180-degree turns), crosswind 3 m/s: no symptom at any time; events counted | 11 events; no symptom at any time; every compensation UNAVAILABLE (NOT_STEADY_FLIGHT) | **yes** |
| V12 | loss on motor_2 at 100 s, in a hold after three maneuvers: event within 2 s with motor_2 among its triggers; COMMAND_NO_RESPONSE on motor_2 and no other motor at any time; response_sensor eliminated; mechanical remains | 3 maneuver events (no symptom), then the injection event (-0.084 s); COMMAND_NO_RESPONSE on motor_2 only; compensation 0.664, telemetry deficit 0.399; response_sensor eliminated; AMBIGUOUS among 4 | **yes** |
| V13 | loss on motor_2 at 77 s, mid-maneuver, maneuvers continuing: no symptom on any other motor at any time; for the injection event, motor_2's telemetry deficit reported and its compensation UNAVAILABLE (NOT_STEADY_FLIGHT) | telemetry event on motor_2 at -0.076 s; deficit DEGRADED; compensation UNAVAILABLE (NOT_STEADY_FLIGHT); no symptom on any motor at any time; later, PX4's allocator reported setpoints not achieved during the turns (`px4.allocation_not_achieved`) | **yes** |

**The verdict on the fixes.** All three blind runs met the expectations
stated before flying.

**V13 is a stated miss, and the product reports it honestly.**
- During continuous maneuvering the loss is not confirmed and no motor is
  blamed.
- The report shows the telemetry deficit and says why the vehicle's
  response could not be assessed.

## 4. What the flights found, and what changed

| found by | defect | fix (tested) |
|---|---|---|
| V5, V6 | the compensation claim's register assumption "near-steady flight in both windows" was not checked; maneuvers moved the command split as a loss does and raised false symptoms | NOT_STEADY_FLIGHT above theta_steady (calibration revision 3: 2 x the apparatus hover null of the peak body rate, 0.0989 rad/s) |
| V5 review | the summary showed the end-of-log result only, which hid symptoms raised and withdrawn | "WHAT HAPPENED?" names every symptom raised at any time; the scoring checks every tick |
| V9 | an ESC offline (`esc_online_flags`) was read as a measured 100 % deficit; the power gate's division guard made a total reported loss untestable | ESC_TELEMETRY_OFFLINE gives UNAVAILABLE; L >= 1 passes the gate |
| V13 review | "WHAT DID CSIA OBSERVE?" listed only outputs still held at the end of the log | the whole flight's adverse outputs are listed, per event |

**Unchanged by the fixes:**
- no XSYS-001 replay decision (`BLIND_ONSET_REPLAY.json`, re-run on the
  final code);
- no 2.2 or pilot report;
- V1-V4, V7, V8, V10.

**The cost of not revising expectations.** V9 still differs from its
expectation, and that is reported, not removed.

## 5. What the flights establish, and what they do not

**What they establish:**
- On ordinary SITL logs, the product names the right motor for a thrust
  loss in hover (5 of 5 including V12) and blames no healthy motor.
- After the fixes it raises no false symptom in four nominal maneuvering
  flights.
- It keeps telemetry, power and navigation anomalies out of the
  propulsion diagnosis.
- It says what it could not assess, and why.

**What they do not establish:**
- **Event discovery is still noisy under maneuvering:** about 11 false
  events per 2.5-minute maneuvering flight (`FALSE_POSITIVES.md`).
- **A loss during continuous maneuvering is not confirmed (V13).** That is
  honest, but it is a miss.
- **The sample is small.** Each condition was flown once, in SIH. These
  are checks of behaviour, not rates. Hardware is untested.
