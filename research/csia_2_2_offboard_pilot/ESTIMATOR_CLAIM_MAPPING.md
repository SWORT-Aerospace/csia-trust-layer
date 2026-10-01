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

<!-- CAMPAIGN_NUMBERS -->

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
