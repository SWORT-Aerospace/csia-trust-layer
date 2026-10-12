# The real multi-producer case: independence and corroboration (Phases 6, 7, 8)

**2026-10-01. NON-CONFIRMATORY.**

**The case** (`MULTI_PRODUCER_EVENT_MATRIX.md` row 1): motor 0 thrust loss
in the 55 XSYS-001 A flights. Analysed with its 55 B trials (RPM telemetry
corruption) and 11 N trials (nominal). Every trial ran through the Analyzer
with the flight's own PX4 estimator (`campaign_xsys.py`, V3_TEMPORAL).

## 1. Each producer traced to its raw sources (Phase 7)

**From the code paths, not from algorithm names:**
- `research/xsys_confirmatory_001/pipeline/xsys_extract.py` `load_full`
  (frozen);
- `xsys_features.py`;
- PX4 547e2ca.

| producer | statistic | raw topics read | raw sources |
|---|---|---|---|
| W_RPM | RPM deficit against command, T1 / T3 | `esc_status.esc[m].esc_rpm`, `actuator_outputs_sim.output[m]` | ESC RPM telemetry; the motor command |
| W_DYN | body-rate response along the loss axis, T1 | `sensor_combined.gyro_rad`, `CA_ROTOR*_PX/PY` | the IMU (gyro); the rotor geometry |
| W_CTRL | controller compensation, T3 | `actuator_motors.control[m]` | the motor command, which the rate controller computes from `vehicle_angular_velocity` (the IMU's gyro corrected by EKF2's bias estimate) and EKF2's attitude |
| PX4 EKF2 | innovation test ratios | `estimator_status` | the IMU (gyro and accel, one device, 1310988), GNSS, barometer, magnetometer, EKF2 |

**The lineage graph** (an edge means "shares a raw source"):

```
   W_RPM ──(motor command)── W_CTRL ──(IMU, EKF2)── PX4 EKF2
                               │                      │
                               └──────(IMU)──── W_DYN ─┘
```

W_RPM and W_DYN share nothing. W_RPM and PX4 EKF2 share nothing.

| pair | ground truth | 2.2 lineage | agree |
|---|---|---|---|
| W_RPM, W_DYN | TRULY INDEPENDENT (ESC telemetry against the IMU) | disjoint | yes |
| W_RPM, W_CTRL | PARTIALLY DEPENDENT (the motor command) | share `channel:motor_command.motor_0` | yes |
| W_DYN, W_CTRL | PARTIALLY DEPENDENT (the IMU) | share `sensor:imu.1310988` | yes |
| W_DYN, PX4 EKF2 | PARTIALLY DEPENDENT (the IMU) | share `sensor:imu.1310988` | yes, **after finding WA-1** |
| W_CTRL, PX4 EKF2 | PARTIALLY DEPENDENT (the IMU, EKF2) | share `sensor:imu.1310988`, `model:ekf2` | yes |
| W_RPM, PX4 EKF2 | TRULY INDEPENDENT | disjoint | yes |

**No pair is FULLY DEPENDENT.** Every pair adds at least one source of its
own.

**WA-1.** Before the fix, the PX4 adapter named the IMU's gyro and
accelerometer as two roots. A gyro monitor and an accelerometer monitor of
the same chip would have counted as independent. They did not in this case,
because W_DYN and EKF2 both used the gyro name. The repair is in
`WRONG_ANSWER_SEARCH.md`.

**Simulation caveat.** In SIH the RPM telemetry and the rotor state are one
variable (XSYS-001 preflight G1). So "independent" here means independent
measurement and computation channels, which is what a source fault
corrupts. It does not mean independent physics.

## 2. The corroboration policy on the real case (Phase 8)

**Per trial at C3** (`CAMPAIGN_ANALYSIS.json`):
- **naive count:** adverse admitted outputs;
- **2.2:** independent lines;
- **ground truth:** the largest set of the adverse producers with no
  shared raw source (§1).

| trials | naive count | 2.2 lineage-aware | ground-truth independent sources |
|---|---|---|---|
| 55 A (motor degraded) | 3 | 2 | 2 |
| 55 B (RPM telemetry corrupted) | 1 | 1 | 1 |
| 11 N (nominal) | 0 | 0 | 0 |

| measure | result |
|---|---|
| false corroboration (2.2 > ground truth) | 0 trials |
| missed independent corroboration (2.2 < ground truth) | 0 trials |
| duplicate counting | none possible: no republished output in the campaign. The DUPLICATE status is pinned on synthetic relays (2.2 dataset G, the three-monitor regression) |
| stale corroboration | none. W_DYN's T1 output is held to C3 by its validated window, not by age (ADMISSIBLE, 14.8 s old) |
| faulted-producer corroboration | none in the campaign (no producer FAULTED). In injected tests, 242 faulted or unavailable producers saying the opposite changed 0 decisions and were never adverse (`WRONG_ANSWER_SEARCH.json`, P7) |

**Verdicts with the estimator present (C3, V3_TEMPORAL):**
- 55/55 A: SUPPORTED ACTUATION/mechanical;
- 55/55 B: SUPPORTED SENSOR/response_sensor;
- 11/11 N: no symptom.

**Rejections:** 0.

**The naive count is wrong by one in every A trial;** the lineage-aware
count is right in every trial. This is the policy's first test on real
monitors. It survives.

**Limits of the test:**
- the ground truth is a code-path analysis done by the same team that wrote
  the lineage;
- the case has one dependence structure, repeated 55 times.


## 3. What the Analyzer adds here that the monitors alone do not

**From the U1 report (`research/csia_2_2_offboard_pilot/reports/U1_xsys_A_multi/`):**
- the exclusion of the telemetry hypothesis rests on two refuters, W_DYN and
  W_CTRL, which share the IMU. The report now says so ("the refuting
  evidence shares sensor:imu.1310988: it is not independent
  corroboration");
- the three adverse witnesses are one lineage group and two independent
  lines;
- the estimator, which also reads that IMU, is NOMINAL throughout. Its
  innovations do not participate in the diagnosis
  (`ESTIMATOR_CLAIM_MAPPING.md`), so its silence is not counted against the
  fault.

**Ways the monitors alone could mislead:**
- **Reading the three witnesses separately**, an engineer sees three
  monitors agreeing on a motor problem, where the evidence is two lines.
- **Reading W_DYN and W_CTRL separately**, the engineer sees two monitors
  excluding a telemetry fault, where the exclusion is one IMU's evidence
  twice.

**What it does not change:** the verdict itself. 2.1.1 with the frozen XSYS
specification reaches the same diagnosis without 2.2 (the XSYS-001 result).
