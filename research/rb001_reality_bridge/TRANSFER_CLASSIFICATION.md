# Sim-to-real transfer classification (RB-001 Part 28)

**2026-10-02.**

- **Script:** `receipts_and_transfer.py`.
- **Output:** `TRANSFER_CLASSIFICATION.json`.

## 1. What a class here means

**Every class below is a prediction, or an RB0 observation. None is a
physical validation.** The brief: "Do not call a method validated merely
because its architecture transfers." A producer marked TRANSFERS_DIRECTLY
has transferred in the sense that nothing CSIA calibrated sits between
PX4's output and the evidence. It has not been shown to be useful on a
real vehicle.

The five classes are the brief's:
- TRANSFERS_DIRECTLY;
- TRANSFERS_AFTER_RECALIBRATION;
- REQUIRES_NEW_VALIDITY_CONDITION;
- REQUIRES_NEW_MODEL;
- DOES_NOT_TRANSFER.

## 2. The classification

| producer / mechanism | class | qualification | why | basis |
|---|---|---|---|---|
| `px4:esc.telemetry_response` (2.3) | TRANSFERS_AFTER_RECALIBRATION | REQUIRES_NEW_VALIDITY_CONDITION in forward flight (inflow), and if `THR_MDL_FAC` is wrong | noise, quantization and per-motor offsets are recalibration problems; position-dependent inflow is not | prediction (no real ESC data) |
| `px4:allocator.compensation` (2.3) | REQUIRES_NEW_VALIDITY_CONDITION | steadiness must be redefined (RR-06); payload or mass changes have no calibration answer | the statistic is sound in a symmetric, constant-mass hover; reality breaks the conditions that make it sound | RB0 (gyro at rest) + prediction |
| 2.3 steadiness condition (θ_steady) | DOES_NOT_TRANSFER | as defined: a maximum against an SIH threshold | real boards at rest exceed it | **RB0 observation** |
| `px4:vehicle.rate_transient` | DOES_NOT_TRANSFER as evidence | stays context | a 0.2 s window needs onset accuracy that real timing and noise do not give | 2.3 + prediction |
| `px4:allocator.status` | TRANSFERS_DIRECTLY | — | PX4's own flags; CSIA calibrates nothing | structural |
| `px4:battery.status` | TRANSFERS_DIRECTLY | reach grows with a power module | presence semantics, no threshold | structural |
| `px4:ekf2.estimator_status` (2.2) | TRANSFERS_DIRECTLY on the contract's PX4 schema | DOES_NOT_TRANSFER across PX4 versions until per-version contracts exist (RR-01) | EKF2's own gates | **RB0 observation** (schema) |
| event discovery: telemetry and compensation CUSUMs | TRANSFERS_AFTER_RECALIBRATION | the maneuvering false-event rate also needs maneuver-aware discovery | k and h are SIH's | 2.3 + prediction |
| event discovery: PX4 monitor triggers | TRANSFERS_DIRECTLY | real warnings will add candidate events | PX4's own | structural |
| log completeness | REQUIRES_NEW_VALIDITY_CONDITION | dropout detection transfers (RR-03); the gap rule's reference interval does not (RR-04, RR-05) | real jitter and logging rates | **RB0 observation** + stress |
| frozen v1.1 CUSUM | DOES_NOT_TRANSFER | — | it has no input in a PX4 log | 2.3 |
| maneuver-study B3/B4 (research candidate, not in the product) | REQUIRES_NEW_MODEL | the plant model (g, c, mixing) must be identified on each vehicle from its own nominal flights | it is model-based, and the model is SIH's until identified on hardware | structural |

## 3. Reading it

**Only the four observation rows are evidence about reality.** They are
the steadiness condition, the estimator schema, log completeness and, in
part, the compensation. Each was found by running the unchanged product
on real logs or real timing. The other rows rest on how the producer is
built.

**The two producers that carried 2.3's result both need work before they
mean anything on hardware.**
- **The telemetry producer:** the cheapest test is RB2-1, a motor on a
  thrust stand. It needs no flight and no fault.
- **The compensation:** first a new steadiness definition, then
  recalibration, both on RB3/RB5 nominal data.

**Every row that transfers directly transfers by doing very little.** PX4's
own flags, presence semantics and EKF2's gates pass through unchanged.
That is useful for coverage and for dependency reporting. It does not
tell an engineer anything PX4 has not already said.
