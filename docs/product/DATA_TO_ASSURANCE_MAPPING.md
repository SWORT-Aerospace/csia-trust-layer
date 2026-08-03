# Data → Assurance Mapping (v1)

| Signal | Evidence provided | Faults made detectable/isolable | Trust Contract field | If missing | OEM action |
|---|---|---|---|---|---|
| `estimator_innovation_test_ratios` | PX4's own consistency gates, independent of CSIA residuals | estimator-vs-sensor discrimination; H_ESTIMATOR_DIVERGENCE becomes testable | `estimator.functions[].quality_indicators` | precise estimator diagnosis PROHIBITED (3E audit) | enable + retain estimator topics at ≥5 Hz |
| `system_power` (5V/3.3V rails) | rail health, the missing signal of slice 3E | H_SENSOR_RAIL becomes structurally identifiable vs MAIN_POWER_PACK | `dependencies.power_rails` + power_resource contract | sensor-rail vs pack causes INDISTINGUISHABLE | log system_power; declare rail topology |
| `vehicle_imu` instances + `accel_device_id` | per-instrument identity across reboots | which-IMU isolation robust to re-enumeration | `identity.device_id` | instance mixups corrupt per-source calibration | keep device IDs in logs |
| `estimator_status.reset_count_*` | estimator restarts | separates estimator resets from sensor faults; T-2 restart accounting input | `restart_semantics` | resets misread as anomalies (false alerts) | retain status topic |
| `battery_status.warning` + `system_power.brick_valid` | vendor's own fault flags | corroborates shared-power hypotheses | `fault_modes.expected_observability` | CSIA must infer what the vendor already knows | publish flag semantics in contract |
| `vehicle_status.arming_state` | exposure denominator | false-alert/hour becomes computable (slice 3A lesson: 21.8% inflation without it) | validity_domain.flight_phases | rates UNPUBLISHABLE for that flight | always log |
| `control_allocator_status` | saturation | separates actuator saturation from sensor fault during aggression | actuator contract validity_domain | aggressive-flight false positives | retain on v1.13+ |
