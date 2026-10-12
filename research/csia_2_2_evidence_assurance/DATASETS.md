# Datasets A-H (Phase 27)

**2026-10-01. NON-CONFIRMATORY.**

**Harness:** `datasets_2_2.py`. **Summary:** `DATASETS_2_2.json`. **Reports:**
`datasets/<id>/report.json` (byte-stable, SHA-256 in the summary) and
`report.txt`.

**Selection.** Every dataset was fixed by the rule below before it was run.
None was replaced after its result was seen.
- **Ground truth** for A-D is the shadow study's `ground_truth.py`.
- **XSYS-001 truth** is the stage-0 key.

| id | rule | input |
|---|---|---|
| A | the corpus's nominal aircraft scenario | NOMINAL, 60 ticks |
| B | the corpus's reference correct-UNIQUE case | PROCESS_STALL |
| C | the matched-pair case whose two causes the evidence cannot separate | MS_B4_MECHANICAL |
| D | the frozen v2.0 wrong-UNIQUE case | MS_B5_RESPONSE_SENSOR |
| E | the frozen configuration transition | E1 (`e1_2_2.py`) |
| F | MS_A1_SENSOR_DELAY with one predicate made to raise: the first base predicate, in sorted order, whose fault 2.1.1 reports as MATERIAL on the last tick | CHANNEL_LINK_NOMINAL |
| G | NOMINAL plus seven synthetic monitors (below) | 60 ticks |
| H | the C00 (nuisance-free) matched pair with the largest degradation, V3_TEMPORAL, with the PX4 estimator from each trial's own flight log; the same A trial under V4_INVALID_WINDOW; and the estimator over that whole flight | XS1A1-C00-A-E055, XS1A1-C00-B-E055 |
| S | the frozen CUSUM on the v1 scenario with correlated alarms and on the one outside its coverage | power_sag, imu0_bias_drift |

**The H choice cannot flatter the result.** Under 2.2, all 55 A trials and
all 55 B trials are UNIQUE_CORRECT at C3/V3 (`REPLAY_AND_RECEIPTS.md`).

## Results

| id | final state (2.1.1 through 2.2) | ground truth | rejected over the run |
|---|---|---|---|
| A | no symptom; NO_EVIDENCE; 1 interval | nominal | none |
| B | UNIQUE COMPUTE/state_estimator; OUTPUT_MISSING SUPPORTED process_stall; POSITION_UNAVAILABLE SUPPORTED estimator_stale on three functions | COMPUTE | none |
| C | AMBIGUOUS: ACTUATION/mechanical, SENSOR/response_sensor (COMMAND_NO_RESPONSE and HIGH_CURRENT_LOW_RPM). Frozen v2.0: UNIQUE ACTUATION/motor_0, right here only because the same evidence also arises in D | ACTUATION, not separable by this evidence | none |
| D | AMBIGUOUS: both remain. Frozen v2.0: UNIQUE ACTUATION/motor_0, wrong | SENSOR | none |
| E | UNIQUE SENSOR/source.imu0; 0 stale position-symptom ticks; recovery at tick 25 | SENSOR/source.imu0 | CONFIGURATION_MISMATCH on 9 ticks (R-3), nothing else |
| F | OUTPUT_STALE widens from SUPPORTED (clean) to AMBIGUOUS: COMMUNICATION/transport_delay re-enters, because its refuter CHANNEL_LINK_NOMINAL failed and 2.1.1 reports the fault impact. The other localizations are as without the fault | SENSOR (sensor delay) | none |
| G | no symptom (the synthetic claims carry none); SENSOR/source.imu1: 3 adverse outputs from 3 producers, **1 independent line** | — | relay DUPLICATE ×60; faulted monitor PRODUCER_INVALID ×60; slow monitor STALE ×30 (from 1.5 s, 0.5 s after it stopped) |
| H, A trial V3 | COMMAND_NO_RESPONSE motor_0 SUPPORTED: ACTUATION/mechanical | actuator degradation | none |
| H, B trial V3 | COMMAND_NO_RESPONSE motor_0 SUPPORTED: SENSOR/response_sensor | RPM telemetry corruption | none |
| H, A trial V4 | AMBIGUOUS: both remain | actuator degradation | W_DYN REGIME_INVALID ×4 (one per motor) |
| H, whole flight | no symptom; 10 intervals; no innovation over its gate | motor 0 degraded from onset (154.75 s into the log) to the end | UNAVAILABLE ×96 before alignment |
| S power_sag | SUSTAINED_SHIFT on motor_esc, battery, vibration; 1 independent line | power sag on battery and motor_esc | UNAVAILABLE ×76 in the first 3 s |
| S imu0_bias_drift | no CUSUM evidence; coverage notice for imu0 | imu0 bias drift | UNAVAILABLE ×76 in the first 3 s |

**Dataset G's monitors:**
- threshold, CUSUM and EKF residual of IMU1, each with its own model root
  and the shared `sensor:imu1`;
- a relay republishing the threshold output;
- a slow monitor that stops publishing at 1.0 s;
- a FAULTED monitor that keeps saying NOMINAL;
- a threshold on IMU2.

## What the datasets show

1. **Correct answers pass through unchanged** (A, B, H): 2.2 admits all
   their evidence.
2. **Conservative answers stay conservative** (C, D, F): 2.2 adds no
   strengthening.
3. **Rejected evidence is visible but not reasoned with** (E, G, H-V4).
   Each rejection names its reason.
4. **A monitor that cannot see a fault says so** (S imu0_bias_drift),
   instead of contributing a NOMINAL.
5. **Dependent alarms are reported as one line** (G, S power_sag).

## What they do not show

**No dataset here is new flight data with a fault the estimator can see.**
- In the E055 flight, EKF2's innovation tests stayed under their gate
  throughout, before and after the onset of the motor degradation. The
  other 65 flights were not analysed with the estimator here.
- Dataset G's monitors are synthetic.

A real fault seen by both a statistical and an estimator producer remains
untested.
