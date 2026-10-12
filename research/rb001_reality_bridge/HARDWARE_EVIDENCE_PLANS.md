# Event discovery, timing, lineage, common causes and producer health on hardware (RB-001 Parts 16-21)

**2026-10-02.** What can be said now from RB0 and SITL, and the plan for
each part on the bench (`MINIMUM_PHYSICAL_EXPERIMENT.md`). Nothing physical
was run.

## Part 16: event discovery under real noise

**Measured so far:**
- the 2.3 SITL numbers: 0 events per hour in hover, 287 per hour under
  maneuvering, all dismissed with the final code;
- on the reachable real logs (RB0), 0 events. The trigger topics
  (`actuator_motors`, `esc_status`) are absent from those PX4 versions, so
  that 0 is not a measurement of noise.

**Plan, on the frozen nominal corpus of RB2-1, RB3 and RB5,** per producer:
- events per hour;
- event duration;
- the producer that triggered;
- repeatability across identical runs;
- how many events became symptoms, and how many became attributions.

Against the budget in `FALSE_ALARM_BUDGET.md`.

**No tuning until that corpus is frozen.** Then, recalibrate CUSUM k and h
by 2.3's rule on calibration runs only.

## Part 17: sensor timing

**Measured on real boards (RB0, `RB0_REAL_LOGS.json`):**

| quantity | real boards | SITL (2.3 logs) |
|---|---|---|
| IMU-class topic interval jitter (std) | 0.2-0.7 ms at 4 ms (CubeOrange: 4.3 ms with its sparse logging profile) | 0 |
| actuator_outputs jitter (std) | 1.4-16 ms at 100 ms | about 5 ms |
| largest gap inside a topic | 65-164 ms | 4-8 ms |
| publish minus sample time (vehicle_angular_velocity) | 0.4 ms median, 0.44 ms p99 (CubeOrange) | 0 |
| logger dropouts | 3 of 4 real logs, 10-119 ms | 0 in 79 flights |

**Are 2.2's content-time semantics still right?**
- **For IMU-derived evidence, yes.** Publication time is within half a
  millisecond of acquisition, against windows of 0.2-15 s.
- **For ESC telemetry, unknown.** `esc_status` carries no sample time, and
  its real latency (DShot telemetry frame or serial round-robin) was not
  measurable here.
- **Bench plan (RB2-0):**
  - the FC toggles a GPIO when it sends a command step;
  - the logic analyzer records the GPIO and the tachometer pulses;
  - the ULog records the command and the reported RPM;
  - the latency distribution is reported RPM time minus tachometer time.
- **If it exceeds a few hundred ms,** ESC outputs need content time =
  publication minus measured latency (`REALITY_GAP_AUDIT.json`, CONTENT
  TIME row).

**Clock alignment** between the FC and external instruments: one shared
step (the GPIO), recorded in both, sets the offset. Drift is measured
across a 5-minute run.

## Part 18: log completeness

Done offline, on 2.3 logs and real-board timing (`LOG_COMPLETENESS.md`).
Missing samples never became healthy evidence, but two weaknesses showed:
- the default-rate re-decimation interacts badly with real jitter;
- the gap rule is relative to 547e2ca's intervals, not the log's own.

Both are receipts, not yet fixes.

## Part 19: lineage rebuilt on the actual hardware

**The rule.** Independence is a physical fact about shared parts, never
inferred from topic names. For the planned FMUv6C board, a DShot telemetry
ESC and a power module:

| output | physical sources | shares with |
|---|---|---|
| ESC RPM | the ESC MCU's commutation timing, per motor | ESC current and temperature (same MCU); the motor |
| ESC current | the ESC's current sense, same MCU | ESC RPM |
| bus current and voltage | the power module | independent of the ESC MCU; shares the power rail with every ESC |
| motor command | the FC's mixer output | every closed-loop statistic (compensation, B3/B4) |
| compensation C | motor commands, driven by the rate loop, driven by the IMU through EKF2 | B3/B4 (same commands and IMU); rate transient D (same IMU) |
| B3/B4 residual | torque setpoint (rate loop), angular-rate derivative (IMU), commands | compensation (same IMU and loop); **one IMU feeds both**: same as 2.2's finding that the elimination rested twice on one IMU |
| rate transient D | IMU | compensation, B3/B4 |
| EKF2 innovations | IMU plus GNSS, magnetometer, barometer | the IMU, with everything above |
| thrust (bench) | load cell | **independent**: its own ADC, its own supply |
| tachometer (bench) | optical sensor | **independent** |

**On a multi-IMU board,** `vehicle_angular_velocity` comes from the
selected IMU. The lineage root must name the selected instance
(`sensor:imu.<device id>`, as the 2.2 adapter already does). After a lane
switch the root changes, which is a configuration epoch.

## Part 20: minimal common-cause map

Only dependencies relevant to the tested evidence:

| common cause | affects | what a fault there looks like |
|---|---|---|
| sensor package: IMU (selected instance) | C, B3/B4, D, EKF2 | correlated anomalies on several outputs: one line of evidence, not several |
| power domain: battery or bench supply rail | all ESCs, all motors, bus current | a common change on every motor: the median normalisation cancels it; POWER/path_unavailable remains a hypothesis |
| ESC MCU (per motor) | that motor's RPM, current, temperature | RPM and current agree with each other but not with thrust: the telemetry path, or the ESC drive |
| compute node: the FC | commands, setpoints, every logged topic, every timestamp | log gaps, timing anomalies, a scheduler stall: producer health, not vehicle faults |
| communication bus: DShot line per ESC | command delivery and telemetry return for that ESC | COMMUNICATION/command_not_delivered and telemetry loss together |
| clock / timebase: the FC clock | every ULog timestamp | drift only matters against external instruments |
| physical component: motor and propeller | RPM, current, thrust, vibration | all of them consistent: a genuine loss |
| calibration source: ESC pole count, power-module scale, CA_ROTOR geometry, THR_MDL_FAC | RPM scale, current scale, loss axes, thrust model | a common scale error cancels in ratios; a per-ESC error does not |

## Part 21: producer health on hardware

| state | physical way to produce it safely | expected CSIA behaviour |
|---|---|---|
| healthy | nominal run | outputs admitted |
| unavailable | ESC telemetry wire unplugged before power-up | ESC_TELEMETRY_OFFLINE / UNAVAILABLE; no motor symptom (2.3 V9 behaviour) |
| stale | telemetry rate reduced (ESC setting) or logger profile reduced | outputs over gaps producer-UNAVAILABLE (and the LOG_COMPLETENESS receipts apply) |
| malformed | offline only: truncate or corrupt a copy of the ULog | a parse failure is a report, not a crash (RR-01 showed the product crashing on schema differences until fixed) |
| configuration mismatch | a parameter change between runs (e.g. pole count, CA_ROTOR geometry) | a configuration epoch in the timeline; evidence from before and after not mixed |

**The rule held everywhere it was tested** (2.3 synthetic tests, RB-001
stress tests): **producer failure is never a vehicle fault.** The bench
confirms it on hardware.
