# HIL stage and the EKF2 lane switch (RB-001 Parts 22-23)

**2026-10-02.** No HIL run was possible: there is no flight controller
reachable from this environment (`HARDWARE_INVENTORY.md`). This document
says what HIL and real hardware can and cannot provide, and what was
measured on real data.

## 1. HIL (Part 22)

**What PX4 HIL gives.** In PX4 HIL the real flight controller runs the
real firmware, scheduler and logger, while a simulator on the desktop
supplies the sensor data over MAVLink. It exercises:

| what the brief wants HIL for | does HIL give it? |
|---|---|
| real timing (scheduler, logger, USB/MAVLink latency) | **yes**: the real board's scheduler and logger. Sensor timing is the link's, not an IMU's. |
| sensor noise | only the simulator's model, plus link jitter; not real sensor noise |
| configuration transitions | **yes**: parameter changes on the real firmware |
| multiple sensor instances | **depends on the simulator's HIL sensor stream**: in HIL the board's own IMUs are replaced by the simulated ones; whether several instances are delivered has to be checked on the chosen board and firmware, not assumed |
| maneuvering | yes, at no hardware risk |

**The plan.** With the planned FMUv6C board:
1. Run the 2.3 validation schedule (V1-V13 equivalents) and the RB-001
   maneuver set in HIL.
2. Compare event rates, timing and every statistic with the SITL runs of
   the same schedule.

**What it isolates.** Differences come from the board's scheduler and
logger, not from physics: it is the timing half of the reality gap.
**Order:** after RB2-0 or in parallel with it, since it needs no motor.

## 2. The EKF2 lane switch (Part 23)

**The pilot's frozen design** (`LANE_SWITCH_EXPERIMENT_DESIGN.md`, 2.2
pilot) needs three IMUs, so that the selector names the faulty one. A 20
deg/s gyro bias step on one of them gives a fault declared about 2.4 s
after onset. Stock SIH has one IMU, so the design was not run: it needs a
simulator change.

**Real boards have the instances.**
- The real CubeOrange log in the pyulog corpus (RB0) carries
  `sensor_gyro` and `sensor_accel` instances 0-2, `vehicle_imu` 0-2 and
  two magnetometers. That is the hardware the selector needs.
- The planned FMUv6C class declares 3-4 IMUs (E2 board survey).
- **So the lane switch does not need a simulator change on real
  hardware.** It needs a way to make one real IMU inconsistent, safely.

**How to cause it on a bench, without damage, in order of preference:**
1. **PX4's own failure injection for a gyro** (`MAV_CMD_INJECT_FAILURE`,
   gyro unit), if the board's sensor pipeline implements it on hardware.
   That has to be checked on the board, not assumed: some injections are
   implemented only in the simulator models.
2. **A per-instance calibration offset** written to one IMU's
   gyro-calibration parameters between runs. It is reversible, but it is a
   parameter change, a configuration epoch, not an in-flight fault.
3. **Physical rotation of the board** while armed on the bench. This makes
   every IMU agree, so it is the wrong experiment.

**The frozen design's parts that remain valid:**
- the selector arithmetic (3 IMUs, 20 deg/s, about 2.4 s);
- the expected EKF2 epochs (`ekf2.selector.instance_changed_count`);
- the 2.2 analysis path.

**What changes:** the bias source (the simulator parameter becomes a
real-hardware injection or an offset), and the vehicle stays disarmed or
restrained.

**Blocker in this environment:** no board. **Blocker in general:** none
found, once a multi-IMU board is on the bench and the injection route is
verified on it.

**No fake multi-lane evidence was created.** No SITL log was edited to look
like a lane switch, and none is called hardware validation.
