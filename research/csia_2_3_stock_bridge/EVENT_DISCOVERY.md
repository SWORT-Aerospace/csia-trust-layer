# Automatic event discovery and clustering (Phases 12 and 14)

**2026-10-02.** **Code:** `csia_evidence_assurance/events.py`, with the
statistics in `stock_stats.py`.

## 1. The question it answers

**What an event means.**
- An event says: SOMETHING WORTH ANALYSING MAY HAVE STARTED HERE.
- It never says "this motor failed".

**What happens next.** A discovered event only sets the time t0 that the
stock producers compare against: their windows before and after t0. The
diagnosis stays with:
- the producers, against their contracts;
- admissibility;
- Semantic Core 2.1.1.

**Why not a universal detector.** A universal anomaly detector would put
an unexplained judgement in front of the explained ones. So event
discovery uses only:
- mature change detection;
- PX4's own monitors.

## 2. Triggers

| kind | method | source | reference |
|---|---|---|---|
| `propulsion.telemetry_change` (per motor) | one-sided CUSUM on the telemetry response q_m, in physical units, against a trailing median reference over [t - 10, t - 2] s | `esc_status`, `actuator_motors` | Page (1954) |
| `propulsion.compensation_change` (per motor) | the same on the compensation ratio kappa_m | `actuator_motors` | Page (1954) |
| `px4.failure_detector` | rising edge of any `fd_*` flag | `failure_detector_status` | PX4 |
| `px4.battery_warning` | rising edge of warning >= LOW | `battery_status` | PX4 |
| `px4.allocation_not_achieved` | setpoint not achieved, or a motor saturated, held >= 0.5 s | `control_allocator_status` | PX4 |
| `px4.estimator_rejection` | a test ratio above 1.0 held >= 1 s, or a filter fault flag | `estimator_status` | PX4 EKF2 |
| `px4.failsafe` | rising edge of `vehicle_status.failsafe` | `vehicle_status` | PX4 commander |
| `px4.log_message` | a WARNING or worse logged in flight | the ULog message log | PX4 |

**The CUSUM's parameters** (k, h) come from the stock calibration
(apparatus nominal flights only):
- telemetry: k = 0.039, h = 0.118;
- compensation: k = 0.040, h = 0.120.

**The onset estimate** is the last sample with S = 0 before the alarm, the
usual CUSUM change-point estimate.

**Not triggers, deliberately:**
- **In-flight parameter changes:** they are not read at all. In SITL they
  are how faults are injected, so reading them would hand the onset to the
  analysis.
- **EKF2 resets and aiding changes:** they happen around every take-off
  (64 of 66 XSYS-001 flights). As triggers, every take-off would be an
  incident. They stay configuration context in the timeline.
- **The frozen v1.1 CUSUM:** it has no input in a PX4 log. Every report
  says so (`CUSUM_TRIGGER.md` studies it on its own coverage).

**Every trigger must be in flight:** armed and not landed.

## 3. Clustering (Phase 14)

**The rule.** Triggers are sorted by onset. A trigger joins the open
cluster if its onset is within 3.0 s of the cluster's latest onset;
otherwise it opens a new one.

**The event's times:**
- **t0** is the earliest onset in the cluster;
- **first alarm** is the earliest alarm;
- **"cleared"** is the time every CUSUM in the cluster returned to zero.
  The trailing reference absorbs the new level within about 10 s, so it
  means "the change is complete". It does not mean "the fault went away".

**Why so simple.** Each event keeps all its triggers, so the report can
show which detectors fired, on which motor, with what magnitude, in what
order. Nothing is learned and nothing is weighted.

**What clustering does in practice:**
- **A motor loss** fires the compensation and telemetry CUSUMs on the
  motor, within 0.1-0.3 s of each other: one event.
- **The other motors' compensation can move a little** as the loop
  redistributes thrust (V1: motor 0's compensation rose 0.048 while motor
  1 lost 40 %). It joins the same event as a secondary trigger. The event
  lists every motor that triggered. Localization is left to the producers
  and 2.1.1, which named motor 1 alone.
- **The frozen CUSUM on the v1 power sag** raised three node alarms within
  5 s: one event (`CUSUM_TRIGGER.md`).

## 4. Results, and where it fails

| data | result |
|---|---|
| XSYS-001, 121 cases (`UNKNOWN_ONSET.md`) | 110/110 injections found, exactly one event each; 0 events on 11 benign-onset flights; onset error -0.096 to +0.140 s |
| validation flights (`VALIDATION_FLIGHTS.md`) | per run, against expectations stated before flying |
| false events (`FALSE_POSITIVES.md`) | none in hover; **many under maneuvering** |

**The weakness.** The thresholds were set from hover. A reposition or yaw
turn changes the motor command split. The compensation CUSUM reads that as
a change, and so it fires at every maneuver:
- 11 events in each of the nominal maneuvering flights V5, V6 and V11;
- 3-7 maneuver events around the losses in V12 and V13.

**What the events led to, first time round.** With the producers as
frozen, these events did not stay harmless. Each event's AFTER window
overlapped the next maneuver, so the compensation claim reported a loss on
the yaw pair, motors 0 and 1. That raised a transient false
`COMMAND_NO_RESPONSE` 11 times in V5 and 11 times in V6
(`FALSE_POSITIVE_SEARCH_r2_as_found.json`).

**The fix.** The claim's register assumption, "near-steady flight in both
windows", is now checked (NOT_STEADY_FLIGHT; `STOCK_PRODUCERS.md`). In the
blind flights (V11-V13), the maneuver events raised no symptom.

**What remains.** The event list stays noisy: an engineer reads eleven
"something may have started here" entries for a normal flight.

**What reducing it needs, not done here:**
- maneuver-aware discovery, reading the commanded setpoints, so that a
  commanded change is not a candidate event;
- or null data from maneuvering flights, calibrated by the same rule.

Neither may be tuned on the validation flights.
