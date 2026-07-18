# CSIA Trust Layer

Working demonstration of SWORT LLC's **Cross-Sensor Intelligence Architecture
(CSIA)**: a real-time cross-sensor validation system that assigns a
continuously updated **Trust Coefficient** to each sensor on an autonomous
aircraft, replacing naive weighted-average sensor fusion with a **Dynamic
Trust Graph** whose edges encode physical relationships between sensors, and
whose anomaly output is a **probability distribution over causes** — never a
binary fault flag.

> **Status: research prototype / desktop simulation — NOT flight software.**
> This code validates the trust-scoring concept and supports investor and
> technical demos. A flight-certified implementation would require a separate
> DO-178C/DO-254 qualification effort on embedded hardware. No certification
> claims are made or implied anywhere in this repository.

## Quick start

```sh
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/csia service        # THE PRODUCT: live runtime + dashboard, one command
                              #   -> http://127.0.0.1:8017, open the LIVE tab
.venv/bin/csia run --scenario gps_spoof        # runtime only, simulated source
.venv/bin/csia run --source mavlink --conn udp:0.0.0.0:14550   # live vehicle/SITL
.venv/bin/csia run --profile sow001_quad_strict --scenario power_sag  # profile posture
.venv/bin/csia serve          # dashboard on replays only
.venv/bin/csia report         # detection/diagnosis summary for all scenarios
.venv/bin/python -m pytest    # full test suite (39 tests, ~4 s)
```

## Validation status (v0.7.0)

| Evidence | Result |
|---|---|
| Simulated fault harness (39 tests, CI) | spoof 2.2 s @ 89%; IMU isolation 99%/0%; mag/power/vib 100% |
| **Real flight data** — 26 public PX4 quadrotor flights, 0.66 h (`csia analyze-logs "data/real_logs/*.ulg"`) | **3 candidate false alarms → 4.5/flight-hour**; 24/26 flights alarm-free (offline posture; logs carry 5/8 channels) |
| **ArduPilot SITL** — full autonomous mission, live MAVLink (`tools/sitl_validate.py`) | **PASS**: 6 sensors monitored, min trust 0.78, zero false alarms, landed |
| **SITL fault injection** — GPS glitch + fix-kill injected into the REAL autopilot mid-flight (`--inject gps_glitch`) | **PASS**: both faults detected live from the RAW receiver stream (GPS trust 0.99 → 0.70, nav CAUTION raised) |
| **Native core** (`csia/native/csia_core.c`, C, zero-alloc, pinned to Python at 1e-12) | trust kernel **247 ns** + diagnosis **427 ns** per tick on desktop → est. 7–15 µs on the STM32H743 itself ≈ 0.04% FC CPU at 25 Hz |

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
  budget at 25 Hz — detection latency is set by evidence statistics, not
  code speed). The **native C core** (`csia/native/`, same algorithm,
  test-pinned to 1e-12) runs the trust+diagnosis math in **674 ns/tick**,
  sized for the STM32H743 flight controller itself, not just the Pi.
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
  nodes / 12 edges, desktop Python). This is **not** embedded timing.

## Scenario results (fixed seeds, `csia report`)

| scenario | target | min trust | detection | peak diagnosis |
|---|---|---|---|---|
| clean | — | 0.92 (no false alarm) | — | 98% nominal |
| gps_spoof | gps | 0.59 | 2.2 s | 89% gps_fault |
| gps_dropout | gps | 0.89 (trust holds) | n/a | 98% nominal (absence of data ≠ fault) |
| imu0_bias_drift | imu0 | 0.77 (imu1 stays 0.86) | 13.0 s (slow ramp) | 99% imu0_bias_drift, 0% imu1 |
| mag_emi | mag | 0.28 | 1.5 s | 100% mag_interference |
| power_sag | battery | 0.40 | 1.6 s | 100% power_fault |
| vibration_anomaly | vibration | 0.17 | 2.6 s | 100% vibration_anomaly |

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

## Repo layout

```
csia/                  installable package (pip install -e .)
  sensors/             synthetic sensor models + fault injection
  trust_graph/         Dynamic Trust Graph structure
  prediction/          three-predictor comparator, attitude, residuals
  trust_engine/        Beta-belief trust engine (EngineConfig)
  diagnosis/           Bayesian causal diagnosis
  dashboard/           replay export, matplotlib dashboard, web app + server
  scenarios.py         canonical scenario catalog + pipeline assembly
  cli.py               csia build | serve | report | info
tests/                 unit tests + tests/scenarios/ fault harness
data/replay/           scenario replay JSONs (generated)
data/sample_logs/      generated figures
phase1..3_*.py         phased demo scripts (thin wrappers over the package)
```
