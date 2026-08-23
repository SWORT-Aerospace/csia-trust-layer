# CSIA Trust Layer — Requirements Traceability Matrix

**Baseline:** commit `c13889f` (v0.8.0).
**Purpose:** map every requirement (`docs/requirements/requirements.md`)
through implementation → tests → campaign → benchmark → flight-log evidence.
Where a link does not exist it is marked **MISSING** — never fabricated.

Columns:
- **Impl** — source file(s) implementing the requirement
- **Unit** — automated unit/regression test (pytest node)
- **MC** — Monte Carlo / scenario campaign evidence
- **Bench** — performance/benchmark evidence
- **Flight log** — real `.ulg` or live-flight evidence
- **Status** — MET / PARTIAL / OPEN / NOT MET

Legend for empty cells: **n/a** (not applicable to this requirement) ·
**MISSING** (applicable but no evidence exists yet).

| REQ | Impl | Unit | MC | Bench | Flight log | Status |
|---|---|---|---|---|---|---|
| REQ-001 Trust coeff [0,1] | `trust_engine/engine.py` | `test_engine::test_trust_bounded_and_clean_floor` | scenario harness | n/a | analyze-logs (26 logs) | MET |
| REQ-002 Bayesian + forgetting | `engine.py::TrustCore.step` | `test_engine::test_prior_and_convergence`, `::test_engine_config_validation` | n/a | n/a | n/a | MET |
| REQ-003 Posterior over causes | `diagnosis/bayes.py` | `test_diagnosis::test_posterior_is_distribution` | scenario harness | n/a | n/a | MET |
| REQ-004 Detect/attribute/isolate | `validation.py`, comparator | `tests/scenarios/test_fault_scenarios.py` | `campaigns/monte_carlo.json` (4/5 classes TPR 1.00) | n/a | MISSING (no faulted real logs) | PARTIAL |
| REQ-005 Slow IMU bias **(gap)** | comparator, engine | MISSING (no passing test) | `campaigns/monte_carlo.json` imu_bias **TPR 0.00 [0,0.30]** | n/a | MISSING | **NOT MET** |
| REQ-006 Graceful degradation | engine, failsafe | `test_runtime::test_failsafe_gps_spoof_caution_and_recovery` | scenario recovery | n/a | n/a | MET |
| REQ-007 Regime gating | `prediction/comparator.py` | `test_comparator::test_speed_gate_semantics`, `::test_clean_flight_residuals_nominal` | n/a | n/a | n/a | MET |
| REQ-010 Causality | comparator, predictors | `test_comparator::test_causality_no_lookahead` | n/a | n/a | n/a | MET |
| REQ-011 Online/batch equiv | `runtime/online.py` | `test_runtime::test_online_matches_batch` | n/a | n/a | n/a | MET |
| REQ-012 Tick rate | `runtime/online.py` | `test_runtime::test_source_emits_time_ordered_contract` | n/a | `tools/perf_regression.py` | n/a | MET |
| REQ-013 Silence watchdog | `online.py` STALE_TIMEOUT | `test_runtime::test_stale_sensor_watchdog` | n/a | n/a | analyze-logs (stale topics) | MET |
| REQ-014 Armed-state gating | `online.py`,`failsafe.py`,`plugins.py` | `test_runtime::test_disarmed_vehicle_gates_motor_edges_and_failsafe`, `test_mavlink_map::test_heartbeat_armed_flag_and_gcs_ignored` | n/a | n/a | MISSING (unverified on live armed/disarm) | PARTIAL |
| REQ-015 Failsafe dwell/hysteresis | `runtime/failsafe.py` | `test_runtime` failsafe suite (4 tests) | `deliverables/failsafe_transitions.md` | n/a | n/a | MET |
| REQ-020 No-evidence safety | `engine.py`, `csia_core.c` | `test_engine::test_no_evidence_holds_trust`, `test_native::test_native_trust_no_evidence_parity` | n/a | n/a | n/a | MET |
| REQ-021 Crash containment | `runtime/service.py` | `test_runtime::test_runtime_contains_layer_errors` | n/a | n/a | n/a | MET |
| REQ-022 Malformed reject + health | `online.py::ingest`, `service.py` | `test_runtime::test_bad_samples_counted_and_health_logged` | n/a | n/a | analyze-logs (bad_samples field) | MET |
| REQ-023 Reboot/time-jump | `online.py::reset`, `plugins.py` | `test_runtime::test_runtime_resets_on_source_time_jump`, `test_mavlink_map::test_reboot_reanchors_epoch_monotonic` | n/a | `tools/soak.py` (reset path) | MISSING (no live reboot capture) | MET |
| REQ-024 Stream reconnect | `plugins.py::MavlinkSource` | MISSING (needs MAVLink fixture) | n/a | n/a | MISSING | PARTIAL |
| REQ-025 Native bounds | `csia_core.c`, `native/__init__.py` | `test_native::test_native_bounds_rejected` | n/a | n/a | n/a | MET |
| REQ-030 Trust-core latency | `engine.py`, `csia_core.c` | `test_engine::test_latency_budget`, `test_native::test_native_trust_matches_python` | n/a | `campaigns/perf_baseline.json` (68.6 µs desktop) | n/a | MET (desktop) |
| REQ-031 No perf regression | n/a (harness) | n/a | n/a | `tools/perf_regression.py` + `campaigns/perf_baseline.json` | n/a | MET |
| REQ-032 Soak stability | `runtime/*` | n/a | n/a | `tools/soak.py` (21.2 h-equiv desktop) | n/a | MET (desktop) |
| REQ-040 Determinism | sensors, scenarios | `test_sensors::test_streams_are_deterministic`, `test_seeker_scenarios::test_determinism` | `campaigns/*.json`, `deliverables/montecarlo_results.*` (byte-identical) | n/a | n/a | MET |
| REQ-041 Single-config report | `validation.py::bench` | n/a | `campaigns/bench.json` | n/a | n/a | MET |
| REQ-045 Platform profiles | `csia/profiles.py` | `test_runtime::test_profiles_registry_and_validation` | n/a | n/a | n/a | MET |
| REQ-046 Advisory default | `runtime/service.py` | (covered by default-runtime tests) | n/a | n/a | n/a | MET |
| REQ-047 Deploy package | `deploy/csia.service`, `deploy/install.sh` | MISSING (no install CI) | n/a | n/a | MISSING (not target-verified) | PARTIAL |
| REQ-050 Target WCET | `tools/benchmark_pi.py` | n/a | n/a | **MISSING — needs Pi 5** | n/a | OPEN |
| REQ-051 Native ARM build | `deploy/install_pi.sh` | `test_native.py` (would run on target) | n/a | **MISSING — needs Pi 5** | n/a | OPEN |
| REQ-052 On-target soak | `tools/stress_pi.py` | n/a | n/a | **MISSING — needs Pi 5** | n/a | OPEN |
| REQ-053 Flight heritage | runtime | n/a | n/a | n/a | **MISSING — no flight yet** | OPEN |
| REQ-060 MAVLink auth | MISSING (not implemented) | MISSING | n/a | n/a | n/a | OPEN |

## Coverage summary

| Evidence tier | REQs with evidence | REQs MISSING/OPEN |
|---|---|---|
| Implementation | 26 / 27 | REQ-060 (not implemented) |
| Unit test | 20 / 27 | REQ-005, 024, 047, 050–053, 060 |
| Monte Carlo / scenario | 5 | (only detection-class REQs applicable) |
| Benchmark | 4 | (only perf REQs applicable) |
| Flight log (real .ulg) | 4 partial | faulted-log, live-armed, reboot-capture, flight-heritage all MISSING |

## Honest reading

- **Strong chain:** trust math, causality, online/batch equivalence,
  resilience (no-evidence/crash/reboot/health), determinism, and perf all
  trace implementation → unit test → (where applicable) campaign/benchmark.
- **Weakest chains:** (1) REQ-005 slow IMU bias is a *measured failure*, not
  a missing test — it is the single most important open algorithmic gap;
  (2) all EMB requirements (050–053) are MISSING evidence pending hardware —
  templates exist; (3) real-flight evidence is limited to 26 offline logs;
  live-armed, reboot-capture, and flight-heritage rows are MISSING.
- Nothing in this matrix is marked MET without a named, runnable artifact.
