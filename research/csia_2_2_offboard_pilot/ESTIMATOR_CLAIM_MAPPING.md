# Estimator claim mapping (Phase 5)

**2026-10-01.** This answers the 2.2 limitation "no aircraft hypothesis
reads estimator claims".

**Answer: none should, yet.** The estimator claims stay context. Below, for
each claim and each relevant hypothesis, is the PX4 reason and, where it
exists, the evidence.

## 1. What an innovation claim means in PX4 (547e2ca, V4)

**Definition.**
- `INNOVATION_<POS|VEL|HGT|HDG>` is EKF2's published, low-pass filtered,
  square-rooted innovation test ratio (`EKF2.cpp` lines 1943-2017;
  `ekf_helper.cpp` lines 412-558).
- Above 1.0, the filtered innovation of that aiding kind lies outside EKF2's
  own gate: the aiding sensor and the EKF's IMU-propagated prediction
  disagree persistently.

**A failed test has at least four causes PX4 does not separate:**
1. the aiding sensor is wrong (GNSS glitch, barometer drift, magnetic
   interference);
2. the IMU prediction is wrong (bias, clipping, vibration);
3. the model is wrong (a delay parameter, an unmodelled state);
4. the vehicle is outside the model's assumptions.

**A passed test does not show the aiding sensor is right.** EKF2 estimates
biases and can follow a slow drift inside the gate.

**What the claims also do not say:** anything about timing.
`estimator_status` content is on the delayed fusion horizon (0.15-0.2 s).
The vehicle's current estimate is the output predictor,
`vehicle_local_position`, whose `timestamp_sample` is the current IMU sample
(`EKF2.cpp` lines 1698-1702).

## 2. The mapping

**Key:**
- **S** = may SUPPORT (confirm);
- **R** = may REFUTE;
- **C** = CONTEXTUALIZE (shown beside the localization, no logical role);
- **N** = NOT PARTICIPATE.

| symptom: hypothesis | POS / VEL | HGT | HDG | why |
|---|---|---|---|---|
| POSITION_UNAVAILABLE: SENSOR/navigation_source_invalid | C | C | N | a VIOLATED GNSS innovation fits an invalid source, and fits an IMU or model fault equally: as a confirmer it would be exactly "EKF abnormal → sensor fault". A NOMINAL one cannot refute a slow drift. NOT_APPLICABLE (GNSS no longer fused) fits it and fits starvation |
| POSITION_UNAVAILABLE: COMPUTE/estimator_stale | N | N | N | about the estimator's output timing; the innovations are not. See EM-1 for the freshness of the producer itself |
| POSITION_UNAVAILABLE: TIMING/deadline_violation | N | N | N | timing |
| POSITION_UNAVAILABLE: COMMUNICATION/starvation | C | C | N | GNSS no longer fused (aiding epoch change, claim NOT_APPLICABLE) fits a starved link and fits EKF2 rejecting the data |
| OUTPUT_MISSING (state_estimator): COMPUTE/process_stall, COMMUNICATION/input_starvation | N | N | N | about whether the process produces; the adapter's STALE (estimator stopped publishing) is the related fact, see EM-1 |
| COMMAND_NO_RESPONSE / HIGH_CURRENT_LOW_RPM: ACTUATION/mechanical, SENSOR/response_sensor | N | N | N | a thrust deficit is measured by the IMU and propagated; the aiding innovations need not move. **Measured:** see §3 |
| MULTIPLE_SENSORS_DEGRADED: independent faults or shared node | C | C | C | several innovation kinds failing at once share the prediction (`sensor:imu`, `model:ekf2`). 2.2's lineage already reports them as one line. That is context for a shared cause, not a confirmer |
| VOLTAGE_RAIL_LOW, PROCESS_OUTPUT_LATE, FUNCTION_DEADLINE_MISS, OUTPUT_STALE: their hypotheses | N | N | N | no PX4 relation. EKF2's `time_slip` growth (producer DEGRADED) is context for COMPUTE resource exhaustion |

**Decision:** no S and no R anywhere. The estimator claims remain
non-attributable context. This is allowed by the brief ("keep estimator
output as context only. That is acceptable").

## 3. Evidence on the real campaign (exploratory)

**Status.** EXPLORATORY, as XSYS-001's preregistration (§7.4) made every
statement about W_EST. **Source:** `CAMPAIGN_XSYS.json`.

**Over all 66 flights:** no innovation output of any kind exceeded its
gate.

**Method.** At the motor-degradation onset, the maximum of each claim in
T1 (0-0.2 s), T2 (0.2-2 s) and T3 (10-15 s), minus its maximum in the 5 s
before onset. Then the 55 A flights (degraded) against the 11 NB flights
(nominal), as an AUC: 0.5 means indistinguishable.

| claim | over-gate outputs | AUC A vs NB (T1, T2, T3) | T1 median change, A / NB |
|---|---|---|---|
| INNOVATION_HDG | 0 | T1 0.4315, T2 0.5111, T3 0.4463 | -0.0479 / -0.0313 |
| INNOVATION_HGT | 0 | T1 0.5207, T2 0.5281, T3 0.5471 | -0.0026 / -0.0028 |
| INNOVATION_POS | 0 | T1 0.5256, T2 0.4727, T3 0.5223 | -0.0032 / -0.0034 |
| INNOVATION_VEL | 0 | T1 0.5207, T2 0.5413, T3 0.5537 | -0.0089 / -0.0089 |

**Reading:**
- Every AUC lies between 0.43 and 0.55.
- The median change at onset is negative or near zero in both groups.
- The estimator's aiding innovations do not respond to this fault class.
  This agrees with the apparatus characterization ("EKF aiding innovations
  (non-informative for this fault class)",
  `docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md` line 414) and
  with XSYS-001 keeping W_EST exploratory.

**Classification for this fault class:**

| claim | here |
|---|---|
| INNOVATION_POS, VEL, HGT | **context**: uninformative. Shows the navigation solution stayed consistent while the motor degraded |
| INNOVATION_HDG | **context** |
| all four, as lineage | **redundant** for dependence: they share the IMU with W_DYN and W_CTRL. They add a fourth output of that IMU, which 2.2 counts as no new line |

**Real transitions seen** (66 flights): horizontal position resets (190),
horizontal velocity resets (184), and aiding-set changes. Examples: heading
from magnetic-heading to 3-axis-magnetometer fusion (64 flights); height
sources changing (most flights).

**No transition invalidated any estimator output.** They are context, and
every one is in the timeline (`CAMPAIGN_ANALYSIS.json`).


## 4. Two mappings that might be legitimate later (not implemented)

**EM-1: estimator freshness as the state estimator's "producing" evidence.**
- **Idea.** An admitted, fresh `estimator_status` shows EKF2 is running. That
  could refute COMPUTE/estimator_stale and COMPUTE/process_stall. Its
  absence (STALE) could confirm them.
- **Why not now (a finding).** The aircraft profile declares the state
  estimator's `output_age_limit_s` = 0.10 s (`aircraft.py`, ProcessSpec
  `state_estimator`). PX4's `estimator_status` content is 0.15-0.2 s old by
  design. Fed with content time, every PX4 flight would read "stale".
- **What it would need.** Publication time, or the output predictor's
  `vehicle_local_position` time, as the evidence. That is a successor-profile
  change (r3), through the gate (PV1-PV9 and citations), and owner review.

**EM-2: simultaneous failure of independent aiding kinds as a
shared-prediction indicator.**
- **Idea.** POS, VEL and HGT failing together, with GNSS and barometer on
  separate lineage, points at the shared IMU or EKF prediction.
- **Why not now.** It is plausible PX4 reasoning, but nothing in this
  repository observed it: no flight has an innovation over its gate. Its
  thresholds would be uncalibrated.
