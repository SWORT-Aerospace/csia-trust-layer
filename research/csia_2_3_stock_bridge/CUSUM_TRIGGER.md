# The frozen v1.1 CUSUM as an event trigger (Phase 13)

**2026-10-02.**

- **Script:** `cusum_trigger_study.py`.
- **Output:** `CUSUM_TRIGGER_STUDY.json`.

## 1. Where it has coverage

The frozen CUSUM bank (`csia/v1_1/sequential.py`, Page's one-sided CUSUM,
k = 0.5, h = 500) reads one input: the v1 simulation's per-node physics
chi-square. A PX4 log has no such input.

**On PX4 data it therefore has no coverage at all.**
- The 2.3 event discovery says so in every report (a coverage notice from
  `events.discover`).
- It never treats the CUSUM's silence as "no event".

**Its coverage is the nine frozen v1 scenarios.** This study runs it there
unchanged, through the 2.2 adapter (`adapters/cusum.py`):
- each node's alarm rising edge becomes an `events.Trigger`;
- the PX4 path's clustering rule groups them (`events.cluster`, 3 s gap).

The scenario's fault list is read for scoring only.

## 2. Results

**Covered nodes:** battery, gps, mag, motor_esc, vibration.
**Not covered:** imu0, imu1, baro, each with the bank's own reason.

| scenario | fault (start-end, s) | alarms | events | detection delay | onset-estimate error | false events | clearance |
|---|---|---|---|---|---|---|---|
| clean | none | 0 | 0 | — | — | 0 | — |
| gps_spoof | gps 20-35 | 1 (gps 21.16) | 1 | 1.16 s | -7.96 s | 0 | not before the end of the run |
| gps_dropout | gps 25-33 | 0 | 0 | missed | — | 0 | — |
| imu0_bias_drift | imu0 20-40 | 0 | 0 | missed (imu0 not covered) | — | 0 | — |
| mag_emi | mag 25-33 | 1 | 1 | 0.08 s | +0.04 s | 0 | not before the end |
| power_sag | battery and motor_esc 30-36 | 3 (motor_esc 30.12, battery 30.20, vibration 35.36) | 1 | 0.12 s | -0.12 s | 0 | vibration cleared at 39.64 s; the others not before the end |
| vibration_anomaly | vibration 28-40 | 1 | 1 | 0.08 s | +0.04 s | 0 | not before the end |
| dual_imu_failure | imu0 25-55, imu1 27-55 | 0 | 0 | missed (not covered) | — | 0 | — |
| high_speed_dash | none (maneuver) | 0 | 0 | — | — | 0 | — |

**Totals** over 539.6 simulated seconds:
- 8 fault onsets, 6 alarms, 4 events;
- **0 false events**, including the clean run and the high-speed dash;
- the 5 missed onsets are:
  - 3 on nodes the bank cannot see (imu0, imu1);
  - the GPS dropout;
  - for power_sag, two targets share one onset and count once.

## 3. What this shows about the CUSUM as a trigger

**Detection is fast where it has coverage:**
- 0.08-0.12 s for a step change (mag, vibration, power);
- 1.2 s for a slow GPS spoof ramp.

**Duplicates are absorbed.**
- The power sag raised three node alarms: motor_esc, battery and,
  5 s later, vibration.
- Clustering made one event of them, because they fall within 3 s of each
  other in a chain.
- The 2.2 adapter's lineage already says the three share
  `sensor:motor_esc`, so they are one line of evidence, not three.

**Several producers agree on one event.** That is the multi-producer case
on the v1 path. The event says only "something may have started here".

**Clearance means the statistic dropped below h, not that the fault went
away.**
- With h = 500 most alarms do not clear before the run ends.
- A CUSUM alarm marks the start of an event. It does not mark the end.

**The onset estimate (the last S = 0) is unreliable for a slow drift.**
- For the GPS spoof it lies 8 s before the fault: in control, the
  statistic wanders above zero for long stretches when h is large.
- Detection is scored on the alarm, which came 1.16 s after the onset.
- **The scoring rule was corrected once in this study.** The first run
  matched events on the onset estimate and miscounted this alarm as false.
  The final rule matches on the alarm and reports the onset error apart.

**Dropout is not a shift.** A GPS dropout makes the node's input stale.
The frozen bank's own rule is that absence of evidence is not evidence of
change, so it does not alarm. Freshness is a different monitor.

## 4. Consequence for the product

On PX4 logs, event discovery uses the stock propulsion CUSUMs and PX4's
own monitors (`EVENT_DISCOVERY.md`). The frozen bank stays what it is: a
detector for the v1 simulation, used on its own coverage and never
stretched to data it was not built for.
