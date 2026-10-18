# Estimator intervention audit (key question 4)

Closed-loop evidence gap search, 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2.

**The question.** Controllers are not the only source of endogeneity. Do
assurance systems track the provenance of these estimator actions, each of
which changes the later evidence stream?

- estimator resets;
- sensor exclusion;
- covariance inflation;
- lane switching;
- adaptive noise tuning;
- measurement rejection;
- redundancy management.

## 1. Per intervention

| intervention | what it changes downstream | who accounts for it, in the searched sources | level | status |
|---|---|---|---|---|
| **sensor exclusion (GNSS)** | the error bound and the integrity risk of the position solution | ARAIM protection levels **after** exclusion, with integrity budget pre-allocated to exclusion outcomes, including wrong exclusion (L040) | V0 SC | solved for ARAIM |
| **measurement rejection, fault detection in Kalman filters** | the integrity risk of undetected faults; the residual history | Kalman-filter integrity monitoring using current and past residuals (L041); cumulative-innovation monitors (L075) | V0 SC / SS | active |
| **reset (position, velocity, heading, distance-to-bottom)** | discontinuity in the state that controllers and monitors consume | PX4 publishes a counter and delta per reset type to all consumers (L063) | V4 | fielded |
| **lane switch (multiple estimator instances)** | which estimator, and which IMU, downstream modules read | PX4: the switch becomes a reset event with the jump as the delta; the sensor selection is republished; relative test ratios are reset (L064). ArduPilot: reset data are updated for the switch; no second switch within 5 s (L065) | V4 | fielded |
| **lane switch, as seen by a monitor** | the imbalanced-propeller metric's input sensor | PX4 failure detector follows the new accelerometer, but its low-pass state carries across the change (L068) | V4 | partial |
| **escalation by the monitor itself** | the evidence the monitor then judges | ArduCopter EKF failsafe requests a yaw reset, then a lane switch, then keeps counting (L066) | V4 | ad hoc |
| **covariance inflation, adaptive noise tuning** | the innovation statistics that detectors test | adaptive Kalman filters adapt Q and R after a fault is detected (L042); explicit accounting of how adaptation changes later detector statistics was **not** found in the summaries (UNCLEAR) | V0 SS | UNCLEAR |
| **reset transients in innovation tests** | false alarms right after a reset | not found in the summaries (L075; UNCLEAR) | V0 SS | UNCLEAR |
| **re-classification (perception)** | tracking history and predicted path | Uber ATG discarded tracking history on each re-classification; changed afterwards (L056) | V0 SC | incident; fixed locally |
| **validity hold (memorisation)** | whether the next values are accepted as valid | QF72: values accepted at the end of a 1.2 s hold coincided with a second spike; algorithm redesigned (L061) | V0 SC | incident; fixed locally |
| **redundancy management and status reporting** | which sensor is trusted after a failure | MH124: a failure was detected but not reported; the unit ran on the backup, and the backup's failure then reached the flight controls (L055) | V0 SC | incident |
| **calibration** | the correction applied to all later readings | B-2: calibration with moisture present distorted air data (L060) | V0 SC | incident |
| **configuration by operators** | which sensors feed the safe-mode controller | SOHO: gyro configuration and a command sent in response to unexpected telemetry (L054) | V0 SC | incident |

## 2. Assessment

- **Navigation integrity accounts for estimator interventions
  mathematically**, at least for exclusion (L040, L041). This is the most
  mature fragment for this key question.
- **Fielded open-source autopilots propagate reset and lane-switch
  provenance to controllers** (L063-L065). They also apply simple rules:
  - a 5 s hold-off between switches (L065);
  - resetting the selector's own comparison statistics (L064).
- **In the files read, monitors do not systematically receive it.**
  - The PX4 imbalance metric blends two sensors across a switch (L068).
  - The ArduCopter failsafe counter spans its own interventions without an
    explicit model (L066).
  - This is limited to the files read.
- **The incident record shows the consequence is real.** In MH124 (L055),
  QF72 (L061) and Uber ATG (L056), an estimator or validity-management
  action changed what later data meant, and a downstream consumer did not
  account for it.
- **Each was fixed locally**:
  - algorithm redesign (L061);
  - history retention (L056);
  - fault reporting (L055).

  In the searched sources, none of the fixes is a general theory.

## 3. Answer to key question 4

**Assurance systems track estimator-intervention provenance in navigation
integrity (L040, L041) and, as engineering, in fielded autopilots
(L063-L065).**

- **The general residual.** Every monitor that consumes an estimator output
  should be told of resets, exclusions, switches and adaptations, with a
  validity rule for each.
- **That residual is engineering.** The mathematics exists where it matters
  most, in navigation integrity.
- **Candidate P05 is ENGINEERING_ONLY**, N1.
- **Two items are UNCLEAR:** covariance inflation and reset-transient false
  alarms.
