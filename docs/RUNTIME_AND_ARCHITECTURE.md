# Runtime, architecture and validation evidence

Detailed engineering material relocated verbatim from `README.md` during the
2026-09 repository finalization, so the top-level README could be read in under
two minutes. **No claim, number or caveat was altered in the move**; the
sections below are byte-identical to what the README carried, and the
`csia-dual-paper-evidence-freeze` tag holds the pre-move state.

Read this when you need the deployable-software detail: the runtime data path,
the traceability from the CSIA research description to modules, the production
properties, the hardware integration path, the gates between this repository
and an airframe, and the validation evidence with its limits.

For current project status see `docs/CURRENT_PROGRAM_STATE.md`; for what the
system is and is not ready for see `docs/product/CSIA_READINESS.md`.

---

## Validation status (v0.8.0)

| Evidence | Result |
|---|---|
| **Simulated fault harness** — 5 scripted fault scenarios (`tests/scenarios/`), CI-gated. Synthetic injection, not real faults; assertion bounds are regression contracts set below previously measured performance, so passing indicates no regression, **not** independent detection evidence | spoof: 2.2 s to trust<0.85 / **4.4 s to operator alert** @ 89%; IMU isolation 99%/0%; mag/power/vib 100%. Both latencies reported — they are not the same quantity ([§3](docs/validation/METRIC_DEFINITIONS.md)) |
| **Campaign reproducibility** — `csia bench`, `csia mc` (150 runs), seeker Monte Carlo regenerated after the 2026-07 live-path hardening | **bit-identical** to the committed `campaigns/*.json` and `deliverables/montecarlo_results.*` — the hardening changed no validated behavior |
| **Soak** — looped runtime through the reset path (`tools/soak.py`) | 185 passes / 3.1 h flight-equivalent: 277,500 ticks, 0 errors, +0.0 MB RSS, latency ratio 1.01x |
| **Real flight data** — 26 public PX4 logs, **UNANNOTATED** (`csia analyze-logs`) | **No CSIA alert episode occurred in 24 of 26 logs.** 2 alert episodes across **0.518 monitored flight-hours** → **3.86 episodes/h, 95% CI 0.47–13.94**. Exposure is *monitored* time (post-`arm_time`); raw log duration (0.663 h) overstates it by 21.8%, because no alert can be raised inside the arm window. **Verified-healthy exposure: 0.000 h** — these logs carry no annotation, and CSIA's silence is not evidence of health. **Held-out exposure: 0.000 h** — all 26 shaped `field_mode` and the offline posture. ~30-fold uncertainty; not a reliability claim. See [dataset provenance audit](docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md) and [exposure plan](docs/validation/EXPOSURE_PRECISION_PLAN.md) |
| **ArduPilot SITL** — full autonomous mission, live MAVLink (`tools/sitl_validate.py`) | **PASS**: 6 sensors monitored, min trust 0.78, zero false alarms, landed |
| **SITL fault injection** — GPS glitch + fix-kill injected into the REAL autopilot mid-flight (`--inject gps_glitch`) | **PASS**: both faults detected live from the RAW receiver stream (GPS trust 0.99 → 0.70, nav CAUTION raised) |
| **Native core** (`csia/native/csia_core.c`, C, zero-alloc, parity-pinned to Python at 1e-12 on the **production 8-node/11-edge graph**) | **Host benchmark:** trust kernel 247 ns + diagnosis 427 ns per tick on desktop. The 7–15 µs STM32H743 figure and 0.04% CPU are **estimates, not target measurements**. The C core is **not on any production execution path** — the Python runtime is what executes. See [NATIVE_RUNTIME_STATUS](docs/embedded/NATIVE_RUNTIME_STATUS.md) |

Plug YOUR data in:
```sh
pip install -e ".[logs]"                       # adds pyulog
csia analyze-logs "path/to/*.ulg" --out report.json   # any PX4 .ulg (QGC download)
csia run --source mavlink --conn udp:127.0.0.1:14551  # live vehicle / SITL
python tools/sitl_validate.py                  # end-to-end SITL check
```
Real-world runs use `OnlineTrustLayer(field_mode=True)`: adaptive residual
normalization (each airframe learns its own noise floor), χ²-tail tolerance,
anti-alias downsampling, mag-aided yaw, self-calibrated field magnitude,
minimum-rate channel screening, and monitored-sensor-aware failsafe rules —
all of it forced into existence by real logs, all of it tested.

Held-out validation protocol (C2): [docs/VALIDATION_PROTOCOL.md](docs/VALIDATION_PROTOCOL.md); `tools/fetch_real_logs.py` re-downloads the 26-log campaign by UUID and re-runs it in one command.

**Transition engineering package** (for an Army xTech / SBIR reviewer):
[requirements](docs/requirements/requirements.md) · [traceability matrix](docs/traceability/traceability_matrix.md) · [evidence matrix](docs/evidence/evidence_matrix.md) · [TRL assessment](docs/TRL_ASSESSMENT.md) · [transition report + audit](docs/TRANSITION_REPORT.md) · [validation hardware BOM](docs/HARDWARE_BOM.md). Embedded readiness: [hardware validation plan](docs/hardware_validation.md), [embedded checklist](docs/embedded_checklist.md), report templates. Perf regression: `tools/perf_regression.py` vs `campaigns/perf_baseline.json`. Changelog: [CHANGELOG.md](CHANGELOG.md).
Commercial/SBIR readiness: [docs/COMMERCIALIZATION.md](docs/COMMERCIALIZATION.md).
Engineering review (adversarial, scored): [docs/ARCHITECTURE_REVIEW.md](docs/ARCHITECTURE_REVIEW.md). Org-level 10-year blueprint: [docs/ORG_BLUEPRINT.md](docs/ORG_BLUEPRINT.md).

**Deploying on hardware?** See [docs/HARDWARE.md](docs/HARDWARE.md): the
SOW001 wiring/telemetry/commissioning guide, systemd service, the mandatory
sigma-calibration procedure, and the Tier 2/3 scaling builds (RTK, third
IMU, optical flow, Jetson + visual-inertial odometry, non-aircraft use).

**Platform profiles** (`csia/profiles.py`): the trust mathematics is
platform-agnostic; a `VehicleProfile` bundles the sensor set, tick rate,
engine tuning, and failsafe posture. `sow001_quad` and `sow001_quad_strict`
ship today; the extension contract for new platforms (rover, USV, industrial
sensor networks) is documented in the module.

## The real-time runtime (`csia.runtime`) — the deployable software

`csia run` starts the actual product path, not a replay:

```
SourcePlugin ──samples──▶ OnlineTrustLayer ──TrustState/tick──▶ FailsafePolicy ──actions──▶ Actuators
(MAVLink | simulator)     (25 Hz, causal)     (trust + diagnosis)  (state machine)   (log | MAVLink)
```

- **`OnlineTrustLayer`** ingests one sample at a time and emits a
  `TrustState` per 25 Hz tick: 8 Trust Coefficients, evidence sub-scores,
  and the diagnosis posterior. It shares the exact per-tick cores
  (`TrustCore`, `DiagnosisCore`) with the batch pipeline, and
  `tests/test_runtime.py::test_online_matches_batch` pins the two together
  (converged divergence < 0.01; the only transient difference is causal vs
  retroactive IMU ground calibration, and it must decay).
- **Source plugins** (`csia/runtime/plugins.py`): `SimulatedFlightSource`
  (bench, any catalog scenario) and `MavlinkSource` (SOW001 stack — Pi 5
  companion consuming HIGHRES_IMU / SCALED_IMU2 / SCALED_PRESSURE /
  GLOBAL_POSITION_INT / ESC_STATUS / BATTERY_STATUS / VIBRATION; requires
  `pip install "csia-trust-layer[mavlink]"`, marked experimental until
  validated against the real FC's units and frames).
- **`FailsafePolicy`** (`csia/runtime/failsafe.py`) — the critical-mission
  emergency plan, a deterministic auditable state machine
  NORMAL → CAUTION → CRITICAL → EMERGENCY with per-condition dwell (no
  single-tick flapping), de-escalation hysteresis, and a 10 s arming delay
  (ground checks / calibration / prior convergence). Measured behavior:

  | scenario | failsafe response |
  |---|---|
  | clean | NORMAL for the whole flight, zero transitions |
  | gps_spoof | CAUTION @ 24.4 s: SWITCH_NAV_INERTIAL + INHIBIT_GPS_MODES; back to NORMAL after the spoof ends |
  | power_sag | CRITICAL @ 33.8 s: REDUCE_POWER + LAND_NOW; recovers |
  | dual_imu_failure | CRITICAL (PREPARE_LANDING) → **EMERGENCY @ 49.2 s: STABILIZE on best IMU + CONTROLLED_DESCENT (1.5 m/s) + BROADCAST_MAYDAY** — the "drone stabilizes and brings itself down" contract |

- **Actuators**: `LoggingActuator` (default — ADVISORY output) and
  `MavlinkActuator` (opt-in `enable_commands=True`, maps
  CONTROLLED_DESCENT/LAND_NOW → autopilot LAND, etc.; SITL-validate first).
  Runtime cost: ~140 µs/tick in reference Python (0.35% of the 40 ms tick
  budget at 25 Hz — alert latency is set by evidence statistics and the
  dwell/threshold policy, not by code speed). The **native C core**
  (`csia/native/`, same algorithm, parity-pinned to 1e-12 on the production
  8-node/11-edge graph) runs the trust+diagnosis math in **674 ns/tick on a
  desktop host**. It is sized for the STM32H743 but is **not currently on any
  production execution path and has never been measured on target** — the
  Python runtime is what executes. See
  [NATIVE_RUNTIME_STATUS](docs/embedded/NATIVE_RUNTIME_STATUS.md).
- **Raw-sensor monitoring**: the GPS node consumes GPS_RAW_INT, not the
  EKF's fused output — the autopilot's estimator innovation-gates faults
  out of its own output stream, hiding exactly what an integrity monitor
  exists to catch (proven in SITL: a 55 m glitch is invisible in fused
  output, caught from the raw stream).
- **State log**: `--log run.jsonl` streams one JSON line per tick
  (trust, level, diagnosis, actions) for the GCS or post-flight analysis.
- **Silence watchdog**: a sensor that stops producing samples is declared
  not-fresh within ~5 sample periods and handled by the failsafe — stale
  values are never silently held (tested).
- **Armed-state gating**: the motor edges and the failsafe key on the
  vehicle's ACTUAL armed flag (MAVLink HEARTBEAT / ULog `vehicle_status`)
  when the source provides it — a vehicle idling disarmed on the ground
  cannot poison its motor edges with gravity-vs-zero-thrust evidence, and
  the failsafe never acts on a disarmed vehicle. The t>5 s proxy remains
  only as the simulator bench fallback (both behaviors tested).
- **No fabricated measurements**: `GPS_RAW_INT` carries no vertical
  velocity, so the mapping marks `vz_valid=False` and every GPS check
  judges horizontal components only (df adjusted) — a steady climb no
  longer reads as a spoof-like vertical residual (tested).
- **Reboot/time-jump hardened**: an FC reboot re-anchors the MAVLink epoch
  monotonically instead of dropping all post-reboot data; any source time
  discontinuity resets the trust layer and failsafe dwell timers instead
  of integrating a negative dt (tested; `tools/soak.py` loops hours of
  flight time through the reset path and watches RSS/latency).
- **Stream resilience**: `MavlinkSource` reconnects with capped backoff on
  timeout or connection error, preserving the time epoch and GPS origin
  across the gap — an in-flight monitor never gives up on its stream; the
  stale watchdog + failsafe report the outage while it retries.
- **Self-health**: every JSONL state line carries the monitor's own health
  (contained errors, rejected malformed samples), and `RunSummary` reports
  the same — "who watches the watchman" is answered in the log (tested).
- **Deployment package**: `sudo deploy/install.sh` installs the hardened
  systemd unit (`deploy/csia.service` — advisory only, `Restart=always`,
  no privileges, logs to `/var/log/csia/`) on the companion computer.
- **`csia service`**: runtime + dashboard in one process; the dashboard's
  LIVE tab renders the runtime's trust/diagnosis feed at 1 Hz refresh while
  replay tabs remain available for analysis.

## Architecture (traceability to the CSIA research description)

| CSIA concept | Implementation | Module |
|---|---|---|
| Dynamic Trust Graph (sensors as nodes, physical relationships as edges) | 8 nodes / 11 edges; each edge carries a relation from the source description | `csia/trust_graph/` |
| Physics-based prediction | Internal self-models per sensor (GPS pos-derivative vs Doppler, battery V=OCV−IR, motor I∝rpm³, …) | `csia/prediction/comparator.py` |
| Historical-trend prediction | Holt level+trend one-step forecast + innovation-whiteness statistic | `csia/prediction/predictors.py` |
| Neighbor-sensor prediction | Edge residuals h_ij(z_i, z_j), χ²-normalized per degree of freedom | `csia/prediction/comparator.py` |
| Trust Coefficient (0–1, recursive Bayesian, adaptive forgetting) | Beta(α, β) belief per node; ρ ∈ [0.95, 0.998] driven by predictor disagreement; natural recovery | `csia/trust_engine/engine.py` |
| Graceful degradation, not binary failure | Evidence fusion over 4 sub-scores; gated checks contribute *nothing* (not "consistent") outside their validity regime | engine + comparator |
| Probability distribution over causes | Gate-aware naive Bayes over the consistency signature (e.g. "89% GPS fault, 11% nominal") | `csia/diagnosis/bayes.py` |
| Sensor simulation with injectable faults | Dual ICM-42688-P, MS5611, RM3100, GPS (spoof/dropout), ESC, battery, 1 kHz vibration; 6 fault kinds, validated specs | `csia/sensors/` |
| Dashboard / scenario replay | Static matplotlib + local web app (stdlib server, zero JS dependencies) | `csia/dashboard/` |
| Test harness | pytest: unit + scripted fault scenarios with detection/attribution/isolation/recovery assertions and measured latency | `tests/` |

Key regime gates (a physical relationship is only evidence inside its domain
of validity): **Mag-Heading↔GPS-Course is speed-gated** (zero weight ≤2 m/s,
full ≥3 m/s — a quadrotor's heading is not slaved to its velocity vector);
the IMU attitude filter's accelerometer correction is quasi-static-gated;
GPS checks gate on fix validity; motor edges gate on armed state.

## Production properties

- **Causal by construction.** Every derivative on a measurement stream is a
  strict backward difference; every filter (EW, Holt, complementary attitude,
  Beta recursion) is forward-only. `tests/test_comparator.py::test_causality_no_lookahead`
  proves outputs up to time T are bit-identical with or without data after T —
  the batch implementation is therefore an exact replay of an online
  sample-by-sample loop, ready to port to the companion computer.
- **Deterministic.** All scenario seeds fixed; the test suite asserts
  bit-for-bit stream reproducibility.
- **Validated inputs.** Unknown fault kinds/targets and invalid engine
  configs raise immediately instead of being silently ignored.
- **No magic numbers in the loop.** Engine tunables live in `EngineConfig`;
  comparator σ's are documented noise budgets per check.
- **Measured, honestly labeled latency.** ~85 µs/tick trust core (mean, 8
  nodes / 11 edges, desktop Python). This is **not** embedded timing, and the
  measured window currently includes replay marshalling as well as the trust
  core itself (audit F-08).

## Scenario results (fixed seeds, `csia report`)

Two latencies are reported because they differ by 2-2.7x and must not be
conflated ([METRIC_DEFINITIONS](docs/validation/METRIC_DEFINITIONS.md) §3,
[latency path audit](docs/audit/CSIA_LATENCY_PATH_AUDIT.md)):

- **to trust<0.85** — *analysis only.* Detector-internal; the analysis
  threshold triggers nothing. Retained for historical continuity.
- **to alert** — *operator-facing.* Onset to the first failsafe alert episode,
  which additionally requires the per-class production threshold, `dwell_up`
  and `arm_time`. This is the number comparable to a PX4/ArduPilot health flag.

| scenario | target | min trust | to trust<0.85 (analysis) | **to alert (operator)** | peak diagnosis |
|---|---|---|---|---|---|
| clean | — | 0.92 (no false alarm) | — | — | 98% nominal |
| gps_spoof | gps | 0.59 | 2.2 s | **4.4 s** (CAUTION) | 89% gps_fault |
| gps_dropout | gps | 0.89 (trust holds) | n/a | n/a | 98% nominal (absence of data ≠ fault) |
| imu0_bias_drift | imu0 | 0.77 (imu1 stays 0.86) | 13.0 s (slow ramp) | **never alerts** † | 99% imu0_bias_drift, 0% imu1 |
| mag_emi | mag | 0.28 | 1.5 s | **3.9 s** (CAUTION) | 100% mag_interference |
| power_sag | battery | 0.40 | 1.4 s | **3.4 s** (CRITICAL) | 100% power_fault |
| vibration_anomaly | vibration | 0.17 | 2.2 s | **5.8 s** (CRITICAL) | 100% vibration_anomaly |
| dual_imu_failure | imu0/imu1 | 0.44 | 6.4 s | (see scenario) | 99% imu0_bias_drift, 1% imu1 (failsafe → stabilize + descent) |
| high_speed_dash‡ | — | 0.89 (no false alarm) | — | — | 100% nominal |

† **`imu0_bias_drift` raises no operator alert at any time.** `imu0` degrades,
but the attitude condition reads `max(imu0, imu1)` and `imu1` stays healthy at
≈0.86, above `att_caution` 0.82 — redundancy working as designed. The 13.0 s
figure is a trust crossing with no operator-visible consequence; diagnosis
still isolates `imu0` correctly (at 15.1 s). It is **not** a detection event
and was previously published as if it were.

‡ `high_speed_dash` flies a **different truth profile** (`fast_cruise`,
peak ground speed **52.0 m/s**) instead of the shared hover/circle baseline.
Its purpose is to exercise the velocity readout and the speed-gated
Mag-Heading↔GPS-Course edge at an elevated envelope; the trust layer flies it
**clean** (min trust 0.89, failsafe NORMAL throughout). **Caveat:** the flight
is *kinematic only* — aerodynamic drag is not modeled and sensor tolerances
remain quad-tuned, so this is a regime-envelope demo, not a validated
high-speed flight-dynamics model. Because `csia report` deliberately runs
every scenario against the shared baseline truth for apples-to-apples
comparison, the 0.89 figure above comes from the scenario's own profile (as
rendered in the dashboard replay), not from the `csia report` shared-truth
row.

### Dashboard (tactical cross-sensor console)

The web dashboard renders the live trust graph, per-sensor trust
coefficients, Bayesian fault attribution, the regime gate, ground velocity,
and the autonomous-remediation response loop. A fully self-contained,
zero-dependency build embedding all nine scenario replays is committed at
[`dashboard_standalone.html`](dashboard_standalone.html) — open it directly in
any browser, no server required (rebuild with
`python tools/build_standalone_dashboard.py`).

| GPS spoof (fault detected) | High-speed dash (52 m/s, clean) |
|---|---|
| ![GPS spoof scenario](deliverables/dashboard_gps_spoof.png) | ![High-speed dash scenario](deliverables/dashboard_high_speed_dash.png) |

## Hardware context & integration path

Sensor models mirror the SOW001 flight controller under development:
**STM32H743VIT6** FC with dual **ICM-42688-P** IMUs, **MS5611** barometer,
**RM3100** magnetometer, and a **Raspberry Pi 5** companion computer on
**MAVLink**. The intended integration is: PX4/ArduPilot flies the aircraft;
the CSIA Trust Layer runs on the companion computer consuming MAVLink
telemetry (`HIGHRES_IMU`, `ESC_STATUS`, `GPS_RAW_INT`, `BATTERY_STATUS`, …),
publishing per-sensor trust and diagnosis for the ground station and, later,
for fusion-weight adaptation. The causality guarantee above is what makes
that port mechanical rather than a rewrite.

## Path to flight

The runtime runs on the vehicle today — in an ADVISORY role on the
companion computer. The gates between this repository and the airframe, in
order; each is a measurement campaign, not a rewrite:

1. **Re-run SITL on current code** (`tools/sitl_validate.py`, then
   `--inject gps_glitch`). The SITL rows in the table above were measured
   before the 2026-07 armed-state/vz/reboot hardening and must be
   refreshed before any new claim.
2. **Commissioning calibration on the actual airframe** — the mandatory
   sigma-calibration procedure in docs/HARDWARE.md
   (`OnlineTrustLayer(auto_baseline_s=...)`).
3. **Overnight soak on the Pi 5 itself**:
   `python tools/soak.py --minutes 480`. Desktop reference: 3.1 h
   flight-equivalent, zero errors, zero growth.
4. **Advisory-only supervised flights**: `deploy/install.sh`, service
   consumes live MAVLink, logs `state.jsonl`, commands nothing. Compare
   post-flight logs against expectations before trusting a single number.
5. **Held-out real-log campaign** (docs/VALIDATION_PROTOCOL.md) for a
   false-alarm rate an evaluator can't dismiss.
6. Only after all of the above: consider `MavlinkActuator` with
   `enable_commands=True` — SITL-validated first, range-safety rules
   apply, and it remains uncertified.

Certified flight-critical operation (DO-178C/DO-254, qualified toolchain,
target-hardware verification) is a separate, funded program — see
docs/COMMERCIALIZATION.md. This repository provides the algorithm,
evidence, and deployment path; it does not provide certification.

## Known limitations (read before demoing)

- Comparator σ's are **hand-set noise budgets** from the simulation's own
  sensor models plus maneuvering headroom — on real hardware they must come
  from a ground/hover calibration campaign.
- The diagnosis is naive Bayes with a hand-built cause→signature table; it
  does not handle simultaneous independent faults gracefully (posteriors
  will split or favor the cause with more matching features).
- The truth simulator and the sensor models share the same physics
  constants (thrust law, battery IR). Real-world model mismatch will widen
  residuals; the χ²-excess scoring absorbs some of this, σ recalibration
  absorbs the rest.
- Fault injection is telemetry-level (e.g. power sag alters reported RPM,
  not the physical rotor state).
- Vibration channel is modeled at 1 kHz; a real deployment would sample
  multi-kHz and use a proper order-tracking spectrum, not a single RMS.
