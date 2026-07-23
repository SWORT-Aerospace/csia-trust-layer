# CSIA Trust Layer — Engineering Requirements

**Baseline:** commit `c13889f` (v0.8.0) and later.
**Scope:** this document describes the requirements the *current software*
already implements or is explicitly open against. It formalizes the legacy
`docs/REQUIREMENTS.md` R-series into a traceable REQ-nnn system with
verification methods and acceptance criteria. **No requirement here
describes future or aspirational capability** — every one is either MET
(with an evidence pointer), PARTIALLY MET, or OPEN/NOT MET, stated honestly.

Status legend: **MET** (verified by named evidence) · **PARTIAL** (verified
in part; gap named) · **OPEN** (no evidence yet; not claimed) · **NOT MET**
(tested and failed; claim withdrawn).

Requirement classes: **FUNC** trust/diagnosis behavior · **RT** real-time /
runtime · **RES** resilience / fault-containment · **PERF** performance ·
**REPRO** reproducibility · **DEPLOY** deployment / configuration ·
**EMB** embedded / target hardware · **SEC** security.

Traceability targets are resolved in `docs/traceability/traceability_matrix.md`.

---

## FUNC — Trust & Diagnosis

### REQ-001 — Per-sensor Trust Coefficient
- **Purpose:** Provide graded per-sensor confidence, not a binary health bit.
- **Requirement:** The system shall compute a Trust Coefficient in [0, 1]
  for each of the 8 sensor nodes on every engine tick.
- **Verification:** Unit test (bounds) + runtime test.
- **Acceptance:** All emitted trust values ∈ [0, 1] across the full test
  suite; one value per node per tick.
- **Status:** MET.
- **Traceability:** `csia/trust_engine/engine.py::TrustCore`; `test_engine.py::test_trust_bounded_and_clean_floor`.

### REQ-002 — Recursive Bayesian update with adaptive forgetting
- **Purpose:** Preserve the validated Beta-Bayesian trust model.
- **Requirement:** Trust shall be maintained as a Beta(α,β) belief updated
  recursively with an adaptive forgetting factor ρ ∈ [ρ_min, ρ_max].
- **Verification:** Unit test (prior + convergence) + config validation.
- **Acceptance:** T(0) = α0/(α0+β0); ρ bounded by config; converges high in
  clean flight (min > 0.95 by flight end).
- **Status:** MET.
- **Traceability:** `engine.py::TrustCore.step`; `test_engine.py::test_prior_and_convergence`, `::test_engine_config_validation`.

### REQ-003 — Probability distribution over causes
- **Purpose:** Diagnosis must inform graduated decisions, never a flag.
- **Requirement:** On anomaly the system shall output a normalized
  posterior probability distribution over the candidate cause set.
- **Verification:** Unit test (posterior sums to 1, non-negative).
- **Acceptance:** Posterior is a valid distribution each tick; peak cause
  matches the injected fault in scenario tests.
- **Status:** MET.
- **Traceability:** `csia/diagnosis/bayes.py`; `test_diagnosis.py::test_posterior_is_distribution`, scenario harness.

### REQ-004 — Fault detection, attribution, isolation
- **Purpose:** Detect a faulted sensor, name the cause, exonerate neighbors.
- **Requirement:** For each catalog fault the system shall lower the faulted
  node's trust below the actionable threshold, attribute the correct cause,
  and keep at least one independent neighbor above threshold where no shared
  edge exists.
- **Verification:** Scripted scenario harness + Monte Carlo campaign.
- **Acceptance:** Per README scenario table; MC TPR with 95% CI reported
  verbatim from `campaigns/monte_carlo.json`.
- **Status:** PARTIAL — MET for gps_spoof, mag_emi, power_sag, vibration
  (TPR 1.00); **NOT MET for slow imu_bias (see REQ-005)**.
- **Traceability:** `tests/scenarios/test_fault_scenarios.py`; `csia/validation.py`.

### REQ-005 — Slow IMU bias-drift detection *(known gap — honest)*
- **Purpose:** Detect a slow accel-bias ramp before it corrupts attitude.
- **Requirement:** Field configuration shall detect slow IMU bias drift.
- **Verification:** Monte Carlo campaign (150 runs, field_mode).
- **Acceptance:** TPR ≥ 0.80 at 95% CI lower bound.
- **Status:** **NOT MET** — measured TPR = 0.00, 95% CI [0.00, 0.30] on
  n = 9 (`campaigns/monte_carlo.json`). Claim withdrawn; tracked as open
  engineering (dual-timescale detector). This requirement is documented so
  the gap is traceable, not hidden.
- **Traceability:** `campaigns/monte_carlo.json` (imu_bias row); legacy R16.

### REQ-006 — Graceful degradation (no latched flags)
- **Purpose:** Trust must recover when a transient ends.
- **Requirement:** A node whose fault clears shall recover trust naturally;
  no fault state shall latch.
- **Verification:** Scenario recovery assertions.
- **Acceptance:** Post-fault trust returns above threshold; failsafe
  de-escalates to NORMAL after the spoof/sag window.
- **Status:** MET.
- **Traceability:** `test_runtime.py::test_failsafe_gps_spoof_caution_and_recovery`.

### REQ-007 — Regime gating (evidence only where valid)
- **Purpose:** A physical relationship is evidence only in its valid regime.
- **Requirement:** Each edge/physics check shall carry a validity gate in
  [0,1]; a gated-out check shall contribute no evidence (not "consistent").
- **Verification:** Unit test (speed gate semantics; clean residuals).
- **Acceptance:** heading_course gated out ≤2 m/s, full ≥3 m/s; gated-in
  residuals near χ² expectation in clean flight.
- **Status:** MET.
- **Traceability:** `csia/prediction/comparator.py`; `test_comparator.py::test_speed_gate_semantics`, `::test_clean_flight_residuals_nominal`.

---

## RT — Real-Time / Runtime

### REQ-010 — Causality (no lookahead)
- **Purpose:** Guarantee the batch pipeline is a faithful replay of the
  online loop — the property that makes the port mechanical.
- **Requirement:** Outputs up to time T shall be bit-identical whether or
  not samples after T exist.
- **Verification:** Regression test (truncation vs full).
- **Acceptance:** atol 1e-10 across all edges/physics/historical channels.
- **Status:** MET.
- **Traceability:** `test_comparator.py::test_causality_no_lookahead`.

### REQ-011 — Online/batch equivalence
- **Purpose:** One algorithm, two drivers, no drift.
- **Requirement:** The online layer and batch pipeline shall agree to
  <0.01 converged trust divergence on identical input.
- **Verification:** Regression test.
- **Acceptance:** late (t>20s) divergence < 0.01; warm-up < 0.07 and decays.
- **Status:** MET.
- **Traceability:** `test_runtime.py::test_online_matches_batch`.

### REQ-012 — Tick rate
- **Purpose:** Deterministic 25 Hz decision cadence.
- **Requirement:** The runtime shall emit one TrustState per 1/tick_hz
  interval, tick timing invariant to sample arrival order.
- **Verification:** Runtime tests + source-contract test.
- **Acceptance:** Tick count matches duration×tick_hz; ordering test passes.
- **Status:** MET.
- **Traceability:** `csia/runtime/online.py`; `test_runtime.py::test_source_emits_time_ordered_contract`.

### REQ-013 — Silence watchdog
- **Purpose:** A silent sensor must not hold stale values forever.
- **Requirement:** A sensor silent >~5 nominal periods shall be declared
  not-fresh and handled by the failsafe.
- **Verification:** Runtime test (GPS goes silent).
- **Acceptance:** fresh=False after silence; nav-degraded caution raised.
- **Status:** MET.
- **Traceability:** `test_runtime.py::test_stale_sensor_watchdog`.

### REQ-014 — Armed-state gating
- **Purpose:** Ground-idle telemetry must not poison motor edges; failsafe
  must not act on a disarmed vehicle.
- **Requirement:** When the source provides armed state (MAVLink HEARTBEAT /
  ULog vehicle_status), motor edges shall gate on it and the failsafe shall
  hold while disarmed; the time proxy is the simulator-only fallback.
- **Verification:** Runtime tests (both directions) + MAVLink map unit test.
- **Acceptance:** Disarmed ground idle → motor-edge gate 0, no failsafe
  action; armed → edges active.
- **Status:** MET.
- **Traceability:** `online.py`, `failsafe.py`, `plugins.py`; `test_runtime.py::test_disarmed_vehicle_gates_motor_edges_and_failsafe`, `test_mavlink_map.py::test_heartbeat_armed_flag_and_gcs_ignored`.

### REQ-015 — Failsafe dwell + hysteresis
- **Purpose:** No single-tick flapping; auditable escalation.
- **Requirement:** Escalation shall require condition persistence (dwell_up);
  de-escalation shall require sustained health (dwell_down).
- **Verification:** Failsafe suite.
- **Acceptance:** Clean → zero transitions; spoof → CAUTION then recovery;
  dual-IMU → CRITICAL then EMERGENCY (stabilize + controlled descent).
- **Status:** MET.
- **Traceability:** `csia/runtime/failsafe.py`; `test_runtime.py` failsafe suite.

---

## RES — Resilience / Fault-Containment

### REQ-020 — No-evidence safety (no divide-by-zero)
- **Purpose:** A node can lose every evidence source at once; that must hold
  the belief, never crash.
- **Requirement:** With zero available sub-scores the update shall hold the
  Beta belief and report a neutral placeholder; Python and C shall agree.
- **Verification:** Unit + native-parity regression.
- **Acceptance:** Trust unchanged; α/β unchanged; C matches Python.
- **Status:** MET (was a demonstrable bug pre-8b94b09; fixed + pinned).
- **Traceability:** `test_engine.py::test_no_evidence_holds_trust`, `test_native.py::test_native_trust_no_evidence_parity`.

### REQ-021 — Monitor crash containment
- **Purpose:** The monitor dying is itself a failure mode.
- **Requirement:** An exception in the per-sample trust math shall be
  contained, counted, logged, and surfaced; the stream shall keep processing.
- **Verification:** Runtime test (injected fault).
- **Acceptance:** errors>0 counted; ticks continue past the fault window.
- **Status:** MET.
- **Traceability:** `csia/runtime/service.py`; `test_runtime.py::test_runtime_contains_layer_errors`.

### REQ-022 — Malformed-sample rejection + self-health
- **Purpose:** Non-finite telemetry must never enter the filters; the
  monitor must report on itself.
- **Requirement:** Non-finite samples shall be rejected pre-filter and
  counted; every JSONL state line shall carry a health record.
- **Verification:** Runtime test (NaN injection).
- **Acceptance:** bad_samples>0; health block in log with matching counts.
- **Status:** MET.
- **Traceability:** `online.py::ingest` guard; `test_runtime.py::test_bad_samples_counted_and_health_logged`.

### REQ-023 — Time-discontinuity recovery (FC reboot)
- **Purpose:** An FC reboot / looped source must not integrate negative dt or
  drop all post-reboot data.
- **Requirement:** A backward source-time jump shall re-anchor the MAVLink
  epoch monotonically and reset layer + failsafe timers.
- **Verification:** Runtime + MAVLink-map tests.
- **Acceptance:** Post-reboot samples retained, monotonic; runtime resets
  with 0 errors.
- **Status:** MET.
- **Traceability:** `test_runtime.py::test_runtime_resets_on_source_time_jump`, `test_mavlink_map.py::test_reboot_reanchors_epoch_monotonic`.

### REQ-024 — Stream reconnection
- **Purpose:** An in-flight monitor must not give up on a dropped link.
- **Requirement:** MavlinkSource shall reconnect with capped backoff,
  preserving time epoch and GPS origin across the gap.
- **Verification:** Code review + manual (needs hardware/SITL).
- **Acceptance:** Reconnect loop with bounded backoff; ctx preserved.
- **Status:** PARTIAL — implemented; automated test OPEN (needs a MAVLink
  fixture). Not exercised in CI.
- **Traceability:** `csia/runtime/plugins.py::MavlinkSource.samples`.

### REQ-025 — Native core bounds safety
- **Purpose:** The embeddable C kernel must not corrupt the stack on bad n.
- **Requirement:** Counts beyond CSIA_MAX_NODES/CAUSES shall return −1 with
  state untouched.
- **Verification:** Native bounds test.
- **Acceptance:** Oversized n/nc raise ValueError via ctypes.
- **Status:** MET.
- **Traceability:** `csia/native/csia_core.c`; `test_native.py::test_native_bounds_rejected`.

---

## PERF — Performance

### REQ-030 — Trust-core latency (desktop reference)
- **Purpose:** Confirm compute headroom on the reference host.
- **Requirement:** Trust-core mean latency shall be <2 ms/tick (Python) and
  the native core shall match Python to 1e-12.
- **Verification:** Latency budget test + native parity + perf harness.
- **Acceptance:** mean < 2 ms; native diff < 1e-12.
- **Status:** MET (desktop). **Embedded WCET OPEN — see REQ-050.**
- **Traceability:** `test_engine.py::test_latency_budget`, `test_native.py`, `tools/perf_regression.py`.

### REQ-031 — No performance regression across commits
- **Purpose:** Catch relative perf regressions on the reference host.
- **Requirement:** Key metrics shall not regress past per-metric tolerance
  vs the blessed baseline.
- **Verification:** `tools/perf_regression.py` vs `campaigns/perf_baseline.json`.
- **Acceptance:** Harness exit 0 (no regression).
- **Status:** MET (baseline seeded at c13889f).
- **Traceability:** `tools/perf_regression.py`, `campaigns/perf_baseline.json`.

### REQ-032 — State/memory stability under soak
- **Purpose:** Products die at hour 6, not minute 2.
- **Requirement:** Continuous operation (with periodic reset) shall not leak
  memory or drift latency.
- **Verification:** `tools/soak.py`.
- **Acceptance:** RSS growth <10 MB and latency ratio <2× over the run.
- **Status:** MET (desktop: 21.2 h-equiv, +0.1 MB, 1.11×). **On-target soak
  OPEN — see REQ-052.**
- **Traceability:** `tools/soak.py`.

---

## REPRO — Reproducibility

### REQ-040 — Determinism
- **Purpose:** Fixed seeds → bit-identical streams and results.
- **Requirement:** Identical inputs shall produce identical outputs.
- **Verification:** Determinism tests + campaign regeneration diff.
- **Acceptance:** Stream determinism test passes; `csia bench`/`mc`/seeker MC
  regenerate byte-identical to committed artifacts.
- **Status:** MET.
- **Traceability:** `test_sensors.py::test_streams_are_deterministic`, `tests/scenarios/test_seeker_scenarios.py::test_determinism`, `campaigns/*.json`, `deliverables/montecarlo_results.*`.

### REQ-041 — Single-configuration reporting
- **Purpose:** Headline numbers from one frozen config (closes review C1).
- **Requirement:** Detection and false-alarm figures shall come from one
  frozen configuration.
- **Verification:** `csia bench` truth table.
- **Acceptance:** `campaigns/bench.json` reproduces; both configs side by side.
- **Status:** MET.
- **Traceability:** `csia/validation.py::bench`, `campaigns/bench.json`.

---

## DEPLOY — Deployment / Configuration

### REQ-045 — Platform profiles (configuration management)
- **Purpose:** Platform specifics in config, not code forks.
- **Requirement:** Sensor set, tick rate, engine tuning, and failsafe posture
  shall be bundled in a VehicleProfile; unknown profiles rejected.
- **Verification:** Profiles registry test.
- **Acceptance:** sow001_quad / _strict present; bad profile raises.
- **Status:** MET.
- **Traceability:** `csia/profiles.py`; `test_runtime.py::test_profiles_registry_and_validation`.

### REQ-046 — Advisory-by-default actuation
- **Purpose:** No uncommanded vehicle action.
- **Requirement:** Failsafe outputs shall be advisory; MAVLink command
  authority shall require explicit opt-in (enable_commands=True).
- **Verification:** Code review (LoggingActuator default; MavlinkActuator gated).
- **Acceptance:** Default runtime commands nothing.
- **Status:** MET.
- **Traceability:** `csia/runtime/service.py::LoggingActuator, MavlinkActuator`.

### REQ-047 — Service deployment package
- **Purpose:** Repeatable install on the companion computer.
- **Requirement:** A systemd unit + idempotent installer shall deploy the
  advisory service with restart-on-failure and least privilege.
- **Verification:** Manual (needs a Linux host / Pi).
- **Acceptance:** `deploy/install.sh` installs, enables, starts; unit is
  advisory-only with Restart=always, NoNewPrivileges.
- **Status:** PARTIAL — package present; end-to-end install verified only on
  target (Phase 7). Not CI-tested.
- **Traceability:** `deploy/csia.service`, `deploy/install.sh`.

---

## EMB — Embedded / Target Hardware *(all OPEN pending hardware)*

### REQ-050 — Worst-case execution time on target
- **Purpose:** Absolute embedded timing, not desktop.
- **Requirement:** Trust+diagnosis tick WCET on the Pi 5 (and est. STM32H7)
  shall be characterized under load.
- **Verification:** `tools/benchmark_pi.py` on hardware.
- **Acceptance:** p99 tick latency < 40 ms (25 Hz budget) with margin stated.
- **Status:** OPEN — no target hardware yet. Template ready.
- **Traceability:** `tools/benchmark_pi.py`, `docs/latency_report_template.md`.

### REQ-051 — Native core cross-compilation for target
- **Purpose:** Prove the C kernel builds and matches on ARM.
- **Requirement:** libcsia_core shall build on the Pi and pass 1e-12 parity.
- **Verification:** `deploy/install_pi.sh` build step + `test_native.py`.
- **Acceptance:** Parity tests pass on aarch64.
- **Status:** OPEN — needs hardware.
- **Traceability:** `csia/native/build.sh`, `deploy/install_pi.sh`.

### REQ-052 — On-target endurance soak
- **Purpose:** Thermal/memory/latency stability on the actual SBC.
- **Requirement:** ≥8 h continuous soak on the Pi 5 shall show no leak,
  no thermal throttle-induced deadline miss.
- **Verification:** `tools/stress_pi.py` overnight.
- **Acceptance:** Per `docs/reliability_report_template.md`.
- **Status:** OPEN — needs hardware.
- **Traceability:** `tools/stress_pi.py`, `docs/reliability_report_template.md`.

### REQ-053 — Real advisory flight heritage
- **Purpose:** The step that makes "has flown in an advisory role" true.
- **Requirement:** At least one supervised advisory-only flight shall be
  recorded (state.jsonl) with the monitor consuming live telemetry.
- **Verification:** Post-flight log analysis vs expectations.
- **Acceptance:** Clean flight log, zero contained errors, sane trust track.
- **Status:** OPEN — no flight yet.
- **Traceability:** `docs/hardware_validation.md`.

---

## SEC — Security *(open backlog)*

### REQ-060 — MAVLink command-path authentication
- **Purpose:** A command-capable link must be authenticated.
- **Requirement:** If command authority is enabled, the MAVLink link shall
  use message signing.
- **Verification:** OPEN.
- **Acceptance:** Signing enabled and verified end-to-end.
- **Status:** OPEN — security backlog; advisory default sidesteps for now.
- **Traceability:** legacy R18.

---

*Requirement count: 27 (17 MET, 4 PARTIAL, 5 OPEN, 1 NOT MET). The NOT MET
and OPEN items are deliberately enumerated — an Army transition reviewer
should be able to find every gap here rather than discover it later.*
