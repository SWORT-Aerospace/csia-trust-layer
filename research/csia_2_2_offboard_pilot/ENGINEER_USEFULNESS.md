# Engineer usefulness: the questions, answered from the reports (Phase 15)

**2026-10-01. NON-CONFIRMATORY.**

**Who answered the questions:** the pilot team, reading the reports. No
external engineer was asked; `EXTERNAL_USER_TEST_PLAN.md` is the plan for
that. This document says only:
- whether the answer is in the report;
- where it is;
- whether it is right against the ground truth.

**The reports** (`reports/`, regenerated with the final code;
`usefulness_reports.py`):

| case | input | real or synthetic |
|---|---|---|
| U1 | XSYS-001 A trial C00-A-E055 (motor 0 at 55 % thrust), V3, with its flight's EKF2 | real SITL log + sealed witness features |
| U2 | B trial C00-B-E055 (RPM telemetry corrupted), V3, with the NB flight's EKF2 | real |
| U3 | U1 under V4_INVALID_WINDOW (W_DYN read outside its validated window) | real |
| U4 | run S1, EKF2 selector on, magnetometer failed at 75 s | real SITL log |
| U5 | frozen CUSUM, v1 power_sag | synthetic (v1 simulation) |
| U6 | frozen CUSUM, v1 imu0_bias_drift | synthetic |
| U7 | E1: IMU failure and EKF lane change | synthetic |
| U8 | MS_A1_SENSOR_DELAY with a predicate made to fail | synthetic |
| batch | the 66 XSYS-001 flight logs, each analysed alone | real |

## The questions

**Key:** **YES** = the report answers it correctly. **PARTIAL** = part of
the answer, or only with a document beside the report. **NO** = not
answered.

| # | question | answer in the report | where | verdict |
|---|---|---|---|---|
| 1 | What went wrong, and where? | U1: COMMAND_NO_RESPONSE on motor_0, SUPPORTED ACTUATION/mechanical. U2: the same symptom, SUPPORTED SENSOR/response_sensor. Both match the stage-0 key | FINAL STATE | YES |
| 2 | What else could it be, and why was it ruled out? | U1: SENSOR/response_sensor eliminated by DYN_T1_NOMINAL_FALSE and CTRL_T3_NOMINAL_FALSE, with the outputs of both | FINAL STATE: "eliminated … by", "refuting evidence" | YES |
| 3 | How much independent evidence is there? | U1: 3 adverse outputs, 1 lineage group, 2 independent lines; the shared sources named (motor command, IMU 1310988) | DEPENDENCE | YES (121/121 trials match the ground-truth source analysis) |
| 4 | Does the ruling-out rest on independent evidence? | U1, U2: "the refuting evidence shares sensor:imu.1310988: it is not independent corroboration" | FINAL STATE | YES |
| 5 | When did it start, and who saw it first? | U1: 0.200 s after onset, W_DYN and W_RPM; W_CTRL only at 15.0 s (its T3 window) | KEY MOMENTS | YES, on the trial's time axis. On a flight log alone, NO (WA-3, question 9) |
| 6 | When was CSIA certain, and did that change? | U1: certain at 0.200 s. U7: three localizations certain at 1.0 s and lost at 1.25 s; attribution UNIQUE SENSOR/source.imu0 from 1.25 s | KEY MOMENTS | YES |
| 7 | What evidence was not used, and why? | U3: W_DYN's T1 outputs REGIME_INVALID at C3 (outside their validated window). U4: 84 outputs PRODUCER_UNAVAILABLE before alignment | EVIDENCE REJECTED, KEY MOMENTS | YES |
| 8 | The answer is ambiguous: what would resolve it? | U3: AMBIGUOUS between ACTUATION/mechanical and SENSOR/response_sensor; CTRL_T3_NOMINAL and DYN_T1_NOMINAL "would discriminate, but could not be evaluated", each with its meaning | FINAL STATE | YES |
| 9 | Was anything not observed at all? | U6: imu0, imu1, baro NO_COVERAGE. Batch: 0 of 68 profile records observed in every flight, stated beside "no symptom" | COVERAGE, PROFILE COVERAGE, FINAL STATE "scope" | YES after WA-3. **Before it: NO, and misleading** |
| 10 | Did the configuration change, and did that affect the evidence? | U4: every EKF2 reset and aiding change in PX4 terms; heading aiding lost at 75.5 s and the heading claim NOT_APPLICABLE after it. U7: the lane change at 1.25 s and the old lane's evidence CONFIGURATION_MISMATCH | TIMELINE, KEY MOMENTS | YES |
| 11 | Were the monitors themselves healthy? | U4: EKF2 UNAVAILABLE then VALID at 2.7 s. U8: CHANNEL_LINK_NOMINAL raised, and "COMMUNICATION/transport_delay may rest on the failed refuter" | PRODUCERS, KEY MOMENTS, FINAL STATE | YES |
| 12 | Does the estimator tell me anything about this fault? | U1: the four innovation claims NOMINAL for 161 ticks, as context. The report does not say that the innovations cannot see this fault class | COVERAGE | PARTIAL: the reason is in `ESTIMATOR_CLAIM_MAPPING.md`, not the report |
| 13 | Can I reproduce this report? | the manifest: input SHA-256, code digests, contract digests, configuration; byte-identical regeneration | `manifest.json` | PARTIAL: the Python and library versions are not recorded |
| 14 | Is this flight like the others? | the batch index and coverage matrix list each flight. The cross-flight consistency of `CAMPAIGN_REPLAY.md` §3 was a research harness | `batch/` | PARTIAL |
| 15 | How bad is it? (thrust lost, RPM deficit) | no magnitude appears. The report gives evidence ids, not measured values | — | NO |
| 16 | What should I do? (repair, inspect, ground the vehicle) | out of scope by design: no recommendation, no authority | — | NO (intended) |

**Count:**
- YES: 11 (one only after WA-3);
- PARTIAL: 3;
- NO: 2 (one by design).

## What the reading taught

1. **The questions an engineer asks first are WHEN questions.** Before the
   pilot, the report had a timeline of states and no key moments
   (`ANALYZER_MVP.md` §3).
2. **"No symptom" is the most dangerous line in the report.** On every
   flight log analysed alone, it was printed without its scope (WA-3).
   It is now the line the report qualifies most.
3. **The value is in questions 2, 3, 4, 7 and 8:**
   - why the alternatives fell;
   - whether the evidence is independent;
   - what was refused;
   - what would decide.

   Individual monitors answer none of them. 2.1.1 alone answers 2 and 8,
   but not 3, 4 or 7.
4. **The report has no magnitudes** (question 15). An engineer will open the
   log for them. Adding the measured value beside each output is a small
   change (`PRODUCT_GAP_ANALYSIS.md`).
5. **On the reports with many localizations,** the FINAL STATE is long:
   U8 has five localizations, each with every refuter. It is correct, but
   it reads as a dump. Grouping localizations that share their refuters is
   a report change, not a semantic one.
