# Reality receipts (RB-001 Part 27)

**2026-10-02.**

- **Script:** `receipts_and_transfer.py`.
- **Output:** `REALITY_RECEIPTS.json`. This document is a reading of it.

## 1. What counts as a receipt

**A receipt records a difference between SITL and real behaviour that was
actually observed.** In RB-001 "observed" means one of:
- seen in the reachable real logs (`RB0_REAL_LOGS.md`): four real boards,
  none of which flew a propulsion event;
- real-board statistics (jitter, dropouts) applied offline to a SITL log
  (`LOG_COMPLETENESS.md`).

**A threat that is only expected belongs in the reality-gap audit**
(`REALITY_GAP_AUDIT.md`), not here. Vibration, motor heating, ESC
quantization, propeller wear and sag under load are all expected. None has
a receipt, because no real propulsion data reached this session.

## 2. The receipts

Columns follow the brief: assumption, SITL behaviour, physical behaviour,
impact on CSIA, calibration fix?, evidence-definition fix?, model
limitation?, product consequence.

| id | assumption | SITL | physical (observed) | impact on CSIA | calib. fix? | evidence-def. fix? | model limitation | product consequence | status |
|---|---|---|---|---|---|---|---|---|---|
| RR-01 | every PX4 log has PX4 547e2ca's `estimator_status` schema | all 2.2/2.3 logs had it | 6/6 reachable logs lack fields (`accel_device_id`, `hdg_test_ratio`); the stock path **crashed** | no report at all on other PX4 versions | no | no | one contract per PX4 schema version | **fixed narrowly:** a schema mismatch is a coverage notice; the estimator producer is not run; historical outputs reproduce byte for byte | fixed |
| RR-02 | an ordinary PX4 log carries `actuator_motors` and `esc_status` at 547e2ca's rates | present at 10 Hz | absent on all 4 real boards (pre-control-allocation PX4); a newer SITL log has `esc_status` at 4 Hz | no propulsion evidence on older vehicles; 0-1 of 29 profile records observed | no | no | the stock bridge needs PX4 with control allocation and ESC telemetry | reported honestly as coverage notices; the supported PX4 range must be stated | documented |
| RR-03 | logs have no dropouts | 0 in 79 SITL flights | 3 of 4 real logs: 4 (119 ms), 1 (10 ms), 1 (30 ms) | windows over a dropout must be refused | no | no | — | already handled: the gap check flagged 6/6 real dropouts | transfers |
| RR-04 | sample spacing is regular at the default interval | jitter 0-9 ms, gaps 4-16 ms | real jitter 1.4-16 ms at 100 ms, gaps up to 164 ms; applied to the V4 loss log, the default-rate re-decimation makes 302 ms and 605 ms gaps, above the 3-interval rule, and the loss (C = 0.664) is refused | real faults may go unreported on jittery real logs: an honest refusal, but a miss | no | **yes** | — | **specified, not applied:** re-decimate only topics logged faster than their default; measure gaps against the topic's own median interval. Gate: the first real propulsion log | open |
| RR-05 | the logging rate is 547e2ca's default | it is | rates differ by version and by logging profile (CubeOrange's reduced profile: `actuator_outputs` at about 9 Hz); at 2 Hz (stress) every propulsion window is refused | total refusal on slower-logged vehicles | no | **yes** | — | the RR-04 fix | open |
| RR-06 | the peak body rate measures maneuvering only | SIH hover nulls max 0.049 rad/s; θ_steady 0.0989 | real boards at rest: 5 s peaks above 0.0989 rad/s in some windows on all three boards measured; 0.067 rad/s yaw bias on a CubeOrange | the compensation may never be assessable on a real vehicle (NOT_STEADY_FLIGHT everywhere) | partly | **yes** | a maximum is the wrong statistic under noise; remove the window median, or use PX4's bias-corrected rate | redefine and recalibrate on RB3/RB5 data before relying on the compensation outside SITL | open |
| RR-07 | one IMU, one EKF2 lane | SIH: one IMU, one magnetometer | a real CubeOrange logs 3 gyro, 3 accelerometer and 2 magnetometer instances | lane switches and IMU-instance lineage changes happen on hardware | no | no | — | lineage roots must name the selected IMU instance (2.2 already does); the frozen lane-switch design becomes runnable on a multi-IMU board | documented |
| RR-08 | publication time equals acquisition time | `timestamp − timestamp_sample` = 0 | 0.40 ms median, 0.44 ms p99 (CubeOrange, `vehicle_angular_velocity`) | none for IMU-derived evidence (windows 0.2-15 s) | no | no | ESC telemetry latency is unmeasured: `esc_status` has no sample time | keep 2.2 content time for IMU outputs; measure ESC latency at RB2-0 | transfers (IMU); open (ESC) |

## 3. What the receipts say together

**Three of eight are about access, not physics.** RR-01, RR-02 and RR-05
are about which PX4 version and logging profile wrote the log. They are
the first thing a real user hits, and they hit before any noise or
vibration matters.

**One fix was made, under Part 35's rule.** RR-01 was a crash, so the
product could not even say what it had not observed. It was fixed
narrowly, in the one adapter, with a test. Nothing else in the evidence
model changed.

**Two evidence-definition fixes are specified and not applied** (RR-04/05,
RR-06). Part 1 says not to change evidence definitions yet. Neither has
been confirmed on a real propulsion log. Both are written down with the
condition that releases them, so that the fix cannot be chosen after
seeing the data it is tested on.

**The receipt this program most needs is still missing:** real ESC
telemetry against a real thrust measurement (RB2-1, `MINIMUM_PHYSICAL_EXPERIMENT.md`).
Until it exists, the telemetry producer's transfer class is a prediction.
