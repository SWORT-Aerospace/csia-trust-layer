# Validation flights: results against the expectations stated before flying

**2026-10-02.**

**Design:** `VALIDATION_FLIGHTS_DESIGN.md`, committed in 6812abc before
any flight was flown.

**Runner:** `sitl_validation_runs.py`.

**Analysis:** `validation_analysis.py`. It runs the product path on the
ULog alone, then reads each run's JSON for scoring.

**Results:**
- `VALIDATION_RESULTS_AS_FLOWN.json`: scored with the code as frozen;
- `VALIDATION_RESULTS.json`: scored after the fixes in section 3;
- `reports/V1`-`V10`: the product's own reports, post-fix.

**Raw logs are not committed.** Their SHA-256 values are in the results.

## 1. All ten were flown

Every run armed, flew its schedule and disarmed, with PX4's default
logging. None was re-flown. The injection acknowledgements are in each
run's JSON: every `MAV_CMD_INJECT_FAILURE` was ACCEPTED.

## 2. Against the expectations (configuration B, the product default)

| run | expectation (stated before flying) | result | as expected? |
|---|---|---|---|
| V1 | one event within 2 s, on motor_1; COMMAND_NO_RESPONSE on motor_1 only; response_sensor eliminated; mechanical remains | 1 event, -0.136 s, first trigger motor 1; exactly that | **yes** |
| V2 | same, motor_2 | 1 event, -0.056 s; exactly that | **yes** |
| V3 | same, motor_3 | 1 event, -0.156 s; exactly that | **yes** |
| V4 | same, motor_0, ordinary log | 1 event, -0.088 s; exactly that | **yes** |
| V5 | nominal maneuvering: no event; no symptom | **11 events** (compensation triggers at every reposition and yaw turn); no symptom | **no**: false events (`FALSE_POSITIVES.md`) |
| V6 | as V5 with 5 m/s wind | **11 events**; no symptom | **no**: same |
| V7 | GPS off: possibly a failsafe or estimator trigger; no propulsion symptom | PX4 log message at injection (+0.004 s), failsafe 5 s later; no symptom | **yes** |
| V8 | battery wrong: battery-warning and failsafe triggers; no propulsion symptom; warning as context; source health UNAVAILABLE | all of that, at +0.004 s | **yes** |
| V9 | ESC 2 off: telemetry trigger on motor_1; no symptom; compensation NOMINAL (deficit not confirmed) | telemetry trigger on motor_1; no symptom; **compensation UNAVAILABLE** (as flown) / **NOT_APPLICABLE** (post-fix) | **no**: part of the expectation not met; see section 3 |
| V10 | ESC 3 wrong: telemetry trigger (excess) on motor_2; no symptom; excess as context | PX4 log message at injection; excess L = -98.6 on motor_2 as context; a deficit-direction telemetry trigger 7 s later; no symptom | **yes** |

**Seven of ten as expected.**

**The three that differ:**
- **V5 and V6** found that event discovery fires at every maneuver.
- **V9** found a gap between the bridge's code and its own claim register.

**No run produced a wrong diagnosis.** No healthy motor was blamed, and no
injected motor was missed or misplaced.

## 3. What V9 found, and what was changed

**What happened.** PX4's ESC OFF injection clears the ESC's bit in
`esc_online_flags` and reports its RPM as 0.

**The two defects, as frozen:**
1. **The telemetry producer read the zero as a measured 100 % deficit.**
   The claim register (`CLAIMS.json`, ESC_TELEMETRY_RESPONSE) lists
   "telemetry dropout" as a failure mode, but the producer did not
   implement it.
2. **The compensation's power gate could not test a total reported loss.**
   It computes 1/(1 - L) - 1, and a guard against division by zero turned
   L = 1 into "untestable" (UNAVAILABLE). A genuine total loss would need
   unbounded compensation, so it should pass the gate (XSYS-001's own
   witness rule).

**After the fix (`adapters/px4_stock.py`, tests
`test_an_offline_esc_is_telemetry_unavailable_not_a_deficit` and
`test_a_total_reported_loss_without_compensation_passes_the_power_gate`):**
- **An offline ESC:** its telemetry is UNAVAILABLE (ESC_TELEMETRY_OFFLINE)
  and the compensation is NOT_APPLICABLE. The report's "WHAT COULD CSIA
  NOT OBSERVE?" names it.
- **An online ESC reporting a total loss that the vehicle does not
  compensate:** NOMINAL ("deficit not confirmed").

**V9 still differs from its expectation, and the expectation is not
revised.** The expectation assumed the zero RPM would be read as a
deficit, and post-fix it rightly is not. The difference is reported here,
not removed.

**What the fixes did not change:**
- no other validation run;
- no decision in the XSYS-001 replay (`BLIND_ONSET_REPLAY.json`, re-run
  on the final code);
- no 2.2 or pilot report.

**Log completeness was implemented in the same session, after the freeze.**
The claim register had marked it IMPLEMENT, but it had not been coded.
No validation flight had a logger dropout or a topic gap, so it changed no
output.

## 4. What the flights establish, and what they do not

**What they establish:**
- `python -m csia_evidence_assurance analyze V*.ulg` works on ordinary
  logs with no sidecar.
- It localizes each of the four motors.
- It keeps telemetry faults, power and navigation anomalies out of the
  propulsion diagnosis.
- It says what it could not see.

**What they do not establish:**
- **Each condition was flown once,** in SIH, which is nearly noise-free.
  These are checks of behaviour, not rates.
- **Hardware is untested.** Real ESC telemetry, vibration and battery
  current change both the evidence and the noise.
- **The design rule had a cost.** Expectations were not revised, so V9's
  row is "no" even though the post-fix behaviour is the better one.
