# The producers: CUSUM, PX4 estimator, XSYS-001 witnesses (Phases 15-21)

**2026-10-01. Code:** `csia_evidence_assurance/adapters/`.

**One interface for three kinds of algorithm:**
- **statistical:** the frozen CUSUM;
- **estimator:** PX4 EKF2's own status;
- **physical:** the XSYS-001 witnesses.

Each emits `EvidenceEnvelope`s that its contract declares. No adapter maps a
detection to a cause, and no adapter re-implements the algorithm it wraps.

The frozen v2 domain plugins are wrapped too (`v2_domains.py`), for the
historical replay.

## 1. The frozen CUSUM (Phases 15-17)

**Wrapped.** `csia/v1_1/sequential.py`'s `CusumBank` runs unchanged:
- k = 0.5, h = 500;
- the clean-arm in-control table.

The producer version is derived from those constants (`k0.5-h500.0-ic7da2915bf734`).
A v1.1 payload computed with other constants is CONTRACT_INVALID.

**What `SUSTAINED_SHIFT` says (Phase 16).**
- DEGRADED: the one-sided CUSUM of the node's standardised pre-transform
  chi-square is above h. A sustained upward shift has accumulated in the
  residuals of the physical relations the node takes part in.
- NOMINAL: the statistic advanced and is at or below h.

**What it does not say:** that the node failed. The node's chi-square mixes
every relation it is in. The record is `attributable=False`, so the adapter
does no attribution.

**Producer health:**

| condition | health |
|---|---|
| the statistic did not advance (input gated out or not fresh) | UNAVAILABLE |
| the statistic is not a finite non-negative number | FAULTED |
| otherwise | VALID |

**Lineage.** From the frozen v1 relation table (`csia/trust_graph/graph.py`
EDGES): the node, its relation partners, and each relation's model.

**Coverage (Phase 17).** The bank covers battery, gps, mag, motor_esc and
vibration. It does not cover:
- **imu0 and imu1:** "no per-IMU physics chi-square exists in this
  construction";
- **baro:** "clean-arm sigma0 is degenerate (0.0 over 1500 ticks)".

For those the result carries a coverage notice, never an envelope and never
a NOMINAL. Coverage was not expanded.

**Runs on the frozen v1 scenarios** (`datasets/S_*`, 1,500 ticks each):

| scenario | what the Analyzer reports |
|---|---|
| power_sag | 30.12 s: SUSTAINED_SHIFT on motor_esc. 30.20 s: also battery. 35.36-39.60 s: also vibration. Throughout, **1 independent line**: all three share `sensor:motor_esc` |
| imu0_bias_drift | no CUSUM evidence at all for the faulted source; the coverage notice says CUSUM evidence is unavailable for imu0. The report does not read the absence as nominal |
| both, 0-3.0 s | one output per tick UNAVAILABLE (a node not yet fresh): PRODUCER_INVALID, not NOMINAL |

## 2. The PX4 EKF2 estimator (Phases 18 and 19)

**No estimator integrity logic.** The adapter reads what EKF2 already
publishes. PX4 547e2ca, all V4 (read at the cited lines):

| file | lines | what |
|---|---|---|
| `src/modules/ekf2/EKF2.cpp` | 1943-2017 | `PublishStatus` |
| `src/modules/ekf2/EKF2.cpp` | 2995-3060 | multi mode and the selector |
| `src/modules/ekf2/EKF/ekf_helper.cpp` | 412-558 | the test-ratio getters |
| `src/modules/ekf2/EKF2Selector.cpp` | 110-140 | `SelectInstance` |

| field (`estimator_status`) | use |
|---|---|
| `pos/vel/hgt/hdg_test_ratio` | four claims, `INNOVATION_POS/VEL/HGT/HDG` on COMPUTE/state_estimator. NOMINAL ≤ 1.0 (EKF2's own gate), VIOLATED > 1.0, NOT_APPLICABLE when NaN (EKF2 publishes NaN when no aiding of that kind is fused). `attributable=False`: a failed innovation test does not say whether the IMU, the aiding sensor or the model is wrong |
| `control_mode_flags` | the fused sources (lineage, and the aiding context epoch); tilt and yaw alignment (health) |
| `filter_fault_flags` bits 0-15 | FAULTED (numerical fusion errors, bad delta-velocity bias) |
| `time_slip` | DEGRADED when it grows |
| `reset_count_*` (uint8) | unwrapped context epochs |
| device ids | lineage roots (`sensor:gyro.<id>`, `sensor:accel.<id>`, `sensor:baro.<id>`, `sensor:mag.<id>`); the IMU context epoch |
| `timestamp_sample` / `timestamp` | content time / produced time (`CONTENT_TIME.md`) |
| `estimator_selector_status.instance_changed_count` | the lane epoch |

**Not used:**
- `health_flags`, `timeout_flags`: legacy LPE fields; EKF2 does not assign
  them;
- the GPS check flags: no claim here.

**Epochs (Phase 19).** Only the lane counter is a dependency of the claims.
- **Why it is:** the selector publishes the switch at once; the new lane's
  status follows.
- **Why the reset, aiding and IMU counters are not:** they arrive in the same
  message as the claims, so evidence and context always agree. As a
  dependency they would protect nothing. They are published as context, and
  the timeline shows them as configuration changes.
- **Selector not running** (`SENS_IMU_MODE` != 0, as in every XSYS-001
  flight): the lane epoch is 0 by construction.
- **Selector running but not logged:** the claims are refused
  (MISSING_EPOCH), with a coverage notice.

**The pin** (`test_estimator_lane_switch_epoch_pin`, a synthetic two-lane
log):

| moment | result |
|---|---|
| before the switch | everything admitted |
| between the selector's switch and the new lane's first output | the four held old-lane outputs CONFIGURATION_MISMATCH (R-3); a CUSUM output, which depends on no lane, still admitted |
| after | the new lane's four outputs admitted, with the new lane's lineage (`sensor:gyro.222`) |

**On a real flight** (`datasets/H_full_flight_estimator`, `XS1A1-C00-A-E055.ulg`,
1,718 ticks at 10 Hz, 10 intervals):

| time | what happened |
|---|---|
| 0.1-2.4 s | UNAVAILABLE before alignment (96 outputs) |
| 0.7, 0.9 and 1.1 s | position, velocity and height resets, as context transitions |
| 2.6 s | GNSS position, velocity and magnetic heading fusion start |
| 141.0 s | magnetic heading changes to 3-axis magnetometer fusion (aiding epoch, heading) |
| 143.6 s | a change in the height-source set |

No STALE output. No innovation over the gate. No producer fault.

## 3. The XSYS-001 witnesses (Phases 20 and 21)

**Wrapped from the frozen pipeline:**
- `stage1_evidence.plan` picks the witness and window;
- `xsys_v2_adapter.records_for` builds the records (a test checks the
  records are identical);
- the sealed `STAGE1.json` gives the values.

| witness | record | lineage | validated window |
|---|---|---|---|
| W_RPM | ACTUATION/motor_m `xsys.rpm_response` | `channel:esc_rpm.motor_m`, `channel:motor_command.motor_m` | T1 and T3: [0, 15] s after onset |
| W_DYN | NAVIGATION/motor_m `xsys.dynamics_T1` | `sensor:gyro.1310988`, `calibration:rotor_geometry` | T1: [0, 0.2] s |
| W_CTRL | CONTROL/motor_m `xsys.compensation_T3` | `channel:motor_command.motor_m`, `model:px4_rate_controller`, `model:ekf2`, `sensor:gyro.1310988` | T3: [10, 15] s |

**The gyro id** is `sensor_selection.gyro_device_id`. It is identical in all
66 campaign flight logs (`DATASETS_2_2.json`, `H_gyro_device_ids`). So W_DYN
and W_CTRL share a root with the PX4 estimator's own lineage.

**One interface (Phase 20).** Dataset H runs W_RPM, W_DYN and W_CTRL
(physical) together with the PX4 estimator (estimator), on one time axis:
seconds from onset. The CUSUM (statistical) runs through the same
`FlightAssuranceAnalyzer` in datasets S.

**The validity lesson (Phase 21).** The frozen 0.2 s temporal rule is not
replaced. The contract states exactly the window XSYS-001 validated.
- A T1 dynamics result held to C3 is 14.8 s old and still ADMISSIBLE.
- The same statistic over T3 (the V4_INVALID_WINDOW variant) is
  REGIME_INVALID.

A compensation-state rule was not added: none was validated.

| run | W_DYN | motor_0 at C3 |
|---|---|---|
| A trial, V3_TEMPORAL | T1, admitted | SUPPORTED: ACTUATION/mechanical (truth: actuator degradation) |
| B trial, V3_TEMPORAL | T1, admitted | SUPPORTED: SENSOR/response_sensor (truth: RPM telemetry corruption) |
| A trial, V4_INVALID_WINDOW | T3, **REGIME_INVALID** | AMBIGUOUS: both remain |

Over all 3,872 slots see `REPLAY_AND_RECEIPTS.md`.
