# PX4 estimator health into CSIA

**2026-09-30. Part 44 of the shadow-validation brief.** Every PX4 field below
was read in the PX4 tree at `547e2ca`, the commit XSYS-001 flew (V4). EKF
integrity monitoring is **not** re-implemented: CSIA consumes what EKF2
already computes.

## 1. What EKF2 already provides

| concept | PX4 field or topic | what it tells CSIA | line |
|---|---|---|---|
| innovation checks | `estimator_status.pos_test_ratio`, `hgt_test_ratio` and the other per-source test ratios (**low-pass filtered**, per the message comment); `estimator_innovation_test_ratios` | how far a fused measurement disagrees with the prediction, relative to its gate | `msg/EstimatorStatus.msg` 80-81; EKF2.hpp 463 |
| GNSS quality checks | `estimator_status.gps_check_fail_flags` | which pre-fusion GNSS checks fail | EstimatorStatus.msg 6 |
| what is being fused | `estimator_status_flags.cs_gnss_pos`, `cs_gnss_vel`, `cs_gps_hgt` … | which sources the output currently depends on | `msg/EstimatorStatusFlags.msg` 9, 18, 51 |
| numerical faults | `estimator_status.filter_fault_flags`; `estimator_status_flags.fs_bad_*` | a fusion step failed numerically | EstimatorStatus.msg 55; EstimatorStatusFlags.msg 60-70 |
| solution validity | `estimator_status.solution_status_flags` | which outputs are valid for control | EstimatorStatus.msg 86 |
| reset counters | `vehicle_local_position.xy_reset_counter`, `z_reset_counter`, `heading_reset_counter`; `estimator_status.reset_count_pos_ne` | the estimate jumped. **Anything integrated across the jump is invalid** | `msg/versioned/VehicleLocalPosition.msg` 21-46; EstimatorStatus.msg 100-104 |
| lane / source switching | `estimator_selector_status.primary_instance`, `instance_changed_count`, `last_instance_change`, `accel_device_id`, `gyro_device_id` | the configuration epoch of the estimator output | `msg/EstimatorSelectorStatus.msg`; `EKF2Selector.cpp` 111-140 |
| sensor rejection | the per-instance `healthy[]`, `combined_test_ratio[]`, `relative_test_ratio[]`, `accel_fault_detected`, `gyro_fault_detected` | which lane and which IMU the selector distrusts | EstimatorSelectorStatus.msg |
| what paces the output | EKF2 publishes only on a new IMU sample | an OUTPUT_MISSING on the estimator has the IMU as its pacing input, not GNSS (`G2_ESTIMATOR_INPUT_AUDIT.md`) | EKF2.cpp 767 |

## 2. What CSIA should consume, and as what

| CSIA evidence (domain / component : relation) | from | claim | validity |
|---|---|---|---|
| COMPUTE/state_estimator : `estimator.innovation.<source>` | per-source test ratio against its gate | "source X disagrees with the prediction" | invalidated by an instance change or a reset of that state. Filtered, so it carries up to about one time constant of pre-event content |
| COMPUTE/state_estimator : `estimator.fusing.<source>` | `cs_*` flags | which inputs the output currently depends on. **This is the dynamic version of the static profile's `depends_on`** | current tick only |
| COMPUTE/state_estimator : `estimator.numerical` | `filter_fault_flags`, `fs_bad_*` | the filter itself misbehaved | current tick only |
| SENSOR/source.gps : `gnss.checks` | `gps_check_fail_flags` | pre-fusion GNSS quality | current tick only |
| COMPUTE/state_estimator : `estimator.epoch` | `instance_changed_count`, the reset counters, and the IMU device ids | **not a diagnostic claim**: the configuration epoch that every estimator-derived record carries | — |

## 3. How configuration changes affect validity

This generalises experiment E1 (`CONFIGURATION_TRANSITION_STUDY.md`).

| event (PX4 field) | stays valid | becomes stale or inadmissible | should be recomputed |
|---|---|---|---|
| lane switch (`instance_changed_count` increments) | sensor-level evidence (IMU and GNSS source health); records from the new lane | anything accumulated on the old lane: miss counters, filtered test ratios, CUSUM sums on old-lane residuals | per-lane accumulators. **PX4 itself resets the relative test ratios here** |
| position reset (`xy_reset_counter` increments) | source-level evidence; heading and height unless reset | residuals or position-derived evidence that span the reset | anything integrating position |
| fusion source change (`cs_gnss_pos` false) | evidence about GNSS itself | the static `depends_on` edge from the estimator to GNSS, for as long as it is not fused (L4 on the profile side) | the estimator's dependency set for C1's alternatives and C3's scope |
| IMU re-selection (`accel_device_id` / `gyro_device_id` change) | the old IMU's own fault evidence: still true of that IMU | the old IMU as an input of the current output (profile edge R6/imu1, CONDITIONAL) | the estimator's dependency set |

## 4. The division of labour

**EKF2 already does:**
- innovation gating;
- per-sensor rejection;
- lane selection;
- numerical fault detection.

**CSIA adds:**
- mapping those outputs to hypotheses in other domains (compute, timing,
  communication, power);
- knowing when an EKF2-derived record stopped describing the current
  configuration;
- refusing to treat the estimator's innovation and a raw threshold on the
  same IMU as two independent confirmations;
- saying so in a trace.

**The fields in §1 are real.** What is not built: the adapter, the successor
relations, and the epoch field on evidence records. Building them is items 1,
2 and 4 of `NEXT_IMPLEMENTATION_TOP5.md`. Transition B (GNSS loss and
recovery) is designed to test exactly this path.
