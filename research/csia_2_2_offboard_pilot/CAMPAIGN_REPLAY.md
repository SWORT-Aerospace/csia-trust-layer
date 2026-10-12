# The whole XSYS-001 campaign through 2.2 (Phases 4, 10, 19)

**2026-10-01. NON-CONFIRMATORY.** Every statement about the estimator is
EXPLORATORY, as XSYS-001's preregistration (§7.4) made W_EST.

**Harnesses:** `campaign_xsys.py` (426 s for 66 flights and 121 trials),
`analyze_campaign.py`. **Results:** `CAMPAIGN_XSYS.json`,
`CAMPAIGN_ANALYSIS.json`.

**Inputs:**
- the 66 raw flight logs, each checked against `RAW_DATA_MANIFEST.json`'s
  SHA-256 (66/66 match);
- the sealed stage-1 features;
- the stage-0 key.

No XSYS-001 file was written.

## 1. What was extracted per flight (Phase 4)

| field | source | role in 2.2 |
|---|---|---|
| test ratios (pos, vel, hgt, hdg) | `estimator_status` | the four claims |
| fault flags | `filter_fault_flags` 0-15 | producer health: FAULTED |
| fusion state | `control_mode_flags` | claim lineage; aiding context epochs; alignment (health) |
| reset counters | `reset_count_*` (uint8, unwrapped) | context epochs |
| sensor device identity | `gyro/accel/baro/mag_device_id` | lineage roots; IMU context epoch |
| configuration epoch events | all of the above, as transitions | timeline |
| time slip | `time_slip` | producer health: DEGRADED |
| XSYS witnesses, RPM and controller evidence | the sealed stage-1 features through `xsys_witness` | W_RPM, W_DYN, W_CTRL |

**Classification of the estimator evidence for this fault class**
(`ESTIMATOR_CLAIM_MAPPING.md` §3):

| evidence | class | why |
|---|---|---|
| innovation claims | context (uninformative here) | no output over its gate in any flight; A vs nominal AUC 0.43-0.55 on every claim and window |
| as lineage | redundant | a fourth output of the IMU that W_DYN and W_CTRL already read |
| resets, aiding changes | context | none invalidates an estimator claim (they arrive with the claims) |
| fault flags, time slip | producer health | no fault in any flight; `time_slip` grew 0-5 times per flight (DEGRADED briefly, admitted with a warning) |

**No estimator evidence was forced into a hypothesis.**

## 2. Real configuration transitions (Phase 10)

**Search.** Every flight was searched for resets, source changes, device-id
changes, aiding-mode changes and lane changes.

| transition | flights / occurrences | example |
|---|---|---|
| horizontal position reset | 190 occurrences | E055 at 0.7 s |
| horizontal velocity reset | 184 | E055 at 0.9 s |
| vertical position reset | 66 | E055 at 0.7 s |
| attitude (quaternion) reset | 66 | E055 at 2.5 s |
| heading, velocity, position aiding start (GNSS, magnetic heading) | 66 each | E055 at 2.6 s |
| heading: magnetic heading → 3-axis magnetometer | 64 | E055 at 141.0 s (after take-off) |
| heading: magnetic heading → none | 2 | XS1A1-C00-NB at 10.8 s |
| height-source set changes | most flights | E055 at 143.6 s |
| device-id change | 0 | one baro id appears as 0 before the barometer starts (C04-A-E055); one IMU throughout |
| lane change | **0: impossible** | `SENS_IMU_MODE` = 1 in every flight; the selector never ran |

**The strongest real transition: magnetometer loss.**
- In the campaign: heading aiding lost in 2 nominal flights.
- In run S1: injected at a known time.

| test | result |
|---|---|
| old evidence before the transition | held heading outputs before 75.5 s were admitted with the lane stamp; the aiding change is context, not a dependency |
| new context after | the timeline names "hdg aiding fused: 3-axis magnetometer -> none" at 75.5 s |
| admissibility | heading outputs after the loss are NOT_APPLICABLE (no aiding fused); nothing refused |
| reason trace | the configuration change carries its PX4 description into `key_moments` and the timeline |

**A lane switch was not fabricated.** `LANE_SWITCH_EXPERIMENT_DESIGN.md`
designs the smallest real one.

## 3. Cross-flight consistency (Phase 19)

| property | across 66 flights |
|---|---|
| producer id, PX4 version | one: `px4:ekf2.estimator_status`, 547e2ca |
| contract and its digest | one (the run used one contract file) |
| lane mode | one: STRUCTURAL_0 |
| epoch keys | one set (11 keys) |
| lineage roots | two sets. They differ only in `sensor:mag.197388`, absent in the two flights whose heading aiding was off at their last output. That is a real configuration difference, not drift |
| device ids | one IMU (1310988), one barometer (6620172), one magnetometer (197388) |
| content lag (publication − sample) | median 0.152-0.156 s; max 0.152-0.172 s (inside the contract's 0.4 s) |
| publication period | median 0.008 s |
| alignment time | 2.20-2.96 s |
| transitions per flight | 53 flights 8 aiding + 8 reset changes; 13 flights fewer (5-7) |
| trial verdicts at C3 / V3 | A 55/55 SUPPORTED ACTUATION/mechanical; B 55/55 SUPPORTED SENSOR/response_sensor; N 11/11 no symptom |

**Conclusion.** The same mechanism is described identically on every
comparable flight:
- 3 adverse witnesses;
- 1 lineage group, 2 independent lines;
- the telemetry hypothesis refuted twice, through one IMU.

**No producer-id, lineage, contract, profile, timestamp or epoch drift was
found.**
