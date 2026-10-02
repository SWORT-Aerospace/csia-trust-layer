# Sim-to-real receipts (PRIME Track B6)

**2026-10-02.**

**Only what was observed on real data is a receipt.** RB-001's RR-01 to
RR-08 (`research/rb001_reality_bridge/REALITY_RECEIPTS.md`) stand as written.
PRIME adds what its real data showed (`REAL_DATA_ACQUISITION.md`,
`REAL_LOG_RESULTS.json`), and updates two of RB-001's receipts with new real
measurements, without editing RB-001's file.

**Real data in PRIME:**
- one real FMUv5 boat log (PX4 about 1.13, 294 s armed);
- the four real-board pyulog logs;
- RflyMAD's real-log topic descriptor.

**No real propulsion event.**

## 1. New receipts

| id | SITL assumption | real observation | effect on evidence | effect on decision | recalibration sufficient? | new validity condition? | model change? | product consequence |
|---|---|---|---|---|---|---|---|---|
| **RR-09** | the vehicle is the profile's vehicle (a quad X) | a real **boat** (airframe 50005, `vehicle_type` rover) passed the profile gate as ACCEPTED; the motor producers did not run, and the report said only "actuator_motors or esc_status missing, or CA_ROTOR_COUNT < 2" | none produced (correctly) | none, but the report never says the vehicle is **outside the supported boundary** | no | **yes:** a support condition (vehicle type, rotor count, PX4 schema) checked before analysis | no | Track A support check: the `assure` output states SUPPORTED / PARTIAL / UNSUPPORTED with the reason |
| **RR-10** | PX4's own warnings are rare, clean triggers | battery warning **rose 32 times in 294 s** as the voltage sat near the threshold; with log messages, **12 events in 294 s armed = 147 per armed hour**, against a 6 per hour budget | events only (no symptom) | none wrong, but the event list buries the answer | no | no | no | view-layer alert grouping: re-raised identical conditions become one alert with a count and first/last time; event discovery itself unchanged (historical reports unchanged) |
| **RR-11** | a real PX4 log carries `actuator_motors`, `control_allocator_status` and `vehicle_torque_setpoint` | **RflyMAD's 497 real flights** (descriptor) carry `actuator_controls_0`, `actuator_outputs`, `esc_status` with RPM and current, and battery current. They have **no** `actuator_motors`, allocator status or torque setpoint (pre-allocation PX4) | the stock ESC telemetry producer and the compensation **cannot run** | no propulsion conclusion on the largest public real fault dataset; ESC current would make the electrical response and the stall check observable for the first time | no | yes: the supported PX4 range, stated | **input mapping only:** `actuator_controls_0` is the same torque/thrust demand | support matrix lists pre-allocation PX4 as PARTIAL (no propulsion evidence); mapping deferred until the data is reachable |
| **RR-12** | `vehicle_angular_velocity` is bias-free at rest and in hover (SIH) | a real CubeOrange at rest: **0.067 rad/s** yaw bias in `vehicle_angular_velocity` (RB0); the stress envelope puts the compensation's ambiguity edge at **0.05 rad/s** | the steadiness statistic exceeds θ_steady; compensation refused (NOT_STEADY_FLIGHT) | **real losses unconfirmed** on such a vehicle | partly | **yes:** steadiness on a de-biased rate (window median removed), as RR-06 specified | no | support matrix: residual gyro bias < 0.05 rad/s is a condition of propulsion confirmation; the report must say when it fails |

## 2. Updates to RB-001 receipts (new real measurements)

| RB-001 receipt | what RB-001 had | what PRIME measured | updated reading |
|---|---|---|---|
| **RR-04** (jitter + re-decimation refuses real losses) | real-board jitter statistics (a reduced-profile CubeOrange's `actuator_outputs`, about 15 % of its interval) applied to a SITL loss log | **real FMUv5 at default logging:** `actuator_motors` interval std **2.4 %**, the allocator 2.3 %, battery 3.3 %. The gap rule refused **0 of 481** windows. The stress envelope (µs-grid jitter) keeps every confirmation up to 20 % | **board- and profile-dependent, not universal.** It stays open for reduced logging profiles; the support matrix flags jitter per log |
| **RR-05** (logging rate differs by version) | `esc_status` at 248 ms in a newer SITL log | **real FMUv5:** `failure_detector_status` at **509 ms** (2 Hz) against the assumed 100 ms. The gap rule, applied to it, refuses **481 of 481** windows. No current output reads it through the rule (triggers only) | **confirmed on real hardware.** Latent today; any producer built on that topic would be refused everywhere until RB-001's specified fix is applied |

## 3. What is still a prediction, not a receipt

Every propulsion relationship is still a prediction:
- RPM noise and quantization on a real ESC;
- thrust against command;
- the compensation under real vibration;
- B3's real noise floor;
- A against B separability.

They wait for the first real propulsion log or the bench
(`B4_MATCHED_AB_PROTOCOL.md`).

**D-PRIME-1 is not a sim-to-real receipt.** It is a code defect that
offline perturbation exposed, and it does not occur on ULog input
(`DEFECT_D_PRIME_1.md`). It matters for reality in one way: the planned
bench instruments carry nanosecond timestamps.
