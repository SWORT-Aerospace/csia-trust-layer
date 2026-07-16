# CSIA Trust Layer — Software Requirements (v0.7)

Numbered, testable requirements. Column "Verified by" maps to the automated
test suite; UNVERIFIED items are open engineering, not claims.

| ID | Requirement | Verified by |
|---|---|---|
| R1 | The system shall compute a Trust Coefficient in [0,1] per sensor at ≥25 Hz | test_engine (bounds), test_runtime |
| R2 | All processing shall be strictly causal (no future samples) | test_comparator::test_causality_no_lookahead |
| R3 | Identical inputs shall produce identical outputs (determinism) | test_sensors::test_streams_are_deterministic |
| R4 | A sensor silent for >5 nominal periods shall be declared not-fresh | test_runtime::test_stale_sensor_watchdog |
| R5 | Absent/stale sensors shall contribute no evidence and trigger no rules on their frozen values | test_runtime (dropout, watchdog), analyze-logs campaign |
| R6 | Non-finite samples shall be rejected, counted, never enter filters | online.ingest guard (unit test: OPEN) |
| R7 | Fault detection shall report a probability distribution over causes, never a binary flag | test_diagnosis |
| R8 | Failsafe escalation shall require condition persistence (dwell) and de-escalate with hysteresis | test_runtime failsafe suite |
| R9 | Loss of both attitude references shall command STABILIZE + CONTROLLED_DESCENT (advisory) | test_failsafe_emergency_descent_on_attitude_loss |
| R10 | Clean nominal flight shall produce zero failsafe transitions | test_failsafe_clean_no_false_alarms; bench.json |
| R11 | The online and batch implementations shall agree (<0.01 converged divergence) | test_online_matches_batch |
| R12 | The native C core shall match the Python reference to 1e-12 | test_native |
| R13 | Trust-core latency shall be <2 ms/tick (ref. Python) / <10 µs (native, desktop) | test_latency_budget; campaigns/bench |
| R14 | Detection/false-alarm figures shall be produced from a single frozen configuration | csia bench (campaigns/bench.json) |
| R15 | GPS integrity shall be evaluated from the raw receiver stream, not EKF output | SITL injection PASS (tools/sitl_validate.py) |
| R16 | UNVERIFIED: field configuration shall detect slow IMU bias drift | **OPEN — bench shows NOT MET (see FMEA F3)** |
| R17 | UNVERIFIED: WCET on target hardware (STM32H7/Pi 5) characterized | OPEN — needs hardware |
| R18 | UNVERIFIED: MAVLink command path authenticated (signing) | OPEN — security backlog |
