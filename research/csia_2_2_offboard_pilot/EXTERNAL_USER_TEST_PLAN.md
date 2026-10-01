# External user test plan (Phase 26)

**2026-10-01. A design for a future evaluator. Not run.** No fake user
study was run with the people who built CSIA.

## 1. Question

**Does an engineer who did not build CSIA answer diagnostic questions about
flight logs:**
- more correctly;
- with fewer unsupported claims;
- with better-justified uncertainty,

**with the Analyzer than without it?** Speed is recorded but is not the
primary measure.

## 2. Participants

- **Who:** 6-10 flight-test, controls or autopilot integration engineers who
  have debugged PX4 logs. None may have written or reviewed CSIA code or
  documents.
- **Allocation:** crossover. Each participant does half the cases manually
  and half with the Analyzer, with the assignment counterbalanced (Latin
  square), so case difficulty and order are not confounded with the
  condition.

## 3. Materials (all from this repository's data; no new flights needed)

| case | from | truth | why it is in the set |
|---|---|---|---|
| 1 | XSYS-001 A trial (motor degraded) | actuator degradation | correct multi-producer diagnosis |
| 2 | XSYS-001 B trial (RPM telemetry corrupted) | telemetry fault | the same symptom, the opposite cause |
| 3 | XSYS-001 A trial under the invalid-window variant | actuator degradation | evidence used outside its validated window |
| 4 | XSYS-001 nominal flight | nominal | false-alarm control |
| 5 | run S1 (magnetometer off at 75 s) | magnetometer loss, heading unaided | configuration change |
| 6 | v1 power_sag (CUSUM) | shared power sag | correlated alarms |
| 7 | v1 imu0_bias_drift (CUSUM) | IMU drift outside CUSUM coverage | a monitor blind to the fault |
| 8 | E1 transition | lane change after IMU failure | stale evidence across a configuration change |
| 9 | XSYS-001 A flight log analysed alone (no witnesses) | actuator degradation, unobserved by the only producer | a clean-looking report whose scope is the point (finding WA-3) |

**Truth is held by the experimenter.**

**Manual condition:**
- the raw ULog, or scenario output, plus PX4 Flight Review / pyulog;
- the producers' own outputs (CUSUM state, witness values,
  `estimator_status`);
- the producer documentation.

**Analyzer condition:** the same, plus `report.txt`, `report.json` and
`manifest.json` from `python -m csia_evidence_assurance analyze`, and a
two-page guide.

## 4. Questions per case (from `ENGINEER_USEFULNESS.md`, questions 1-11 and 13 there)

1. What first became abnormal, and when?
2. Which explanations remain, and which are excluded, and by what evidence?
3. Was any evidence unusable, and why?
4. Do any two monitors share a source?
5. Did a monitor fail, or was it unable to see the fault?
6. Did the configuration change, and did that invalidate earlier
   conclusions?
7. Is the diagnosis based on physical evidence or on telemetry?
8. What additional evidence would resolve the ambiguity?
9. How certain may you be, and when did that change?
10. Could another engineer reproduce your answer exactly?

## 5. Measures

| measure | how | primary |
|---|---|---|
| correctness | each answer scored against truth by two blind raters (rubric fixed before the study; disagreements resolved by a third) | yes |
| unsupported certainty | answers that name a single cause where truth is not separable (cases 3, 6, 7), that call a monitor's silence "nominal", or that call case 9 clean | yes |
| dependence recognised | case 6, and cases 1-2 (shared sources) | secondary |
| invalid evidence caught | cases 3 and 8 | secondary |
| time to answer | recorded | secondary, not a claim |
| reproducibility | can a second rater reach the same answer from the participant's notes | secondary |

## 6. Success criteria, fixed now

**The Analyzer is judged useful only if both hold:**
- correctness is higher;
- unsupported certainty is lower,

each by at least one answer per participant on average, with no case where
Analyzer users are worse on unsupported certainty.

**Speed alone is not success.**

## 7. Threats and controls

| threat | control |
|---|---|
| the Analyzer's wording leads the participant | report text frozen before the study; the guide does not mention cases |
| learning across cases | crossover and counterbalancing |
| the experimenter coaches | a written protocol; the experimenter does not answer content questions |
| rubric fitted after the fact | rubric and success criteria committed before the first session |
