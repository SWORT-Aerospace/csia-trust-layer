# Event discovery in PRIME-1 (Phases 6-12)

**2026-10-03. EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY.** Every number
below comes from PX4 software-in-the-loop flights (SIH quadrotor, PX4
547e2ca). None is a real-flight rate.

**Boundary:** offboard, after the flight. An event only says that a channel
changed enough to analyse; it is never a conclusion.

## 1. What the successor front end does (`events.discover_prime1`)

| trigger | semantics in the reason trace | rule |
|---|---|---|
| `propulsion.rpm_deficit` | RPM_DEFICIT_EVENT | one-sided CUSUM on d = ref - q (q = reported over expected rotor speed, cross-rotor normalised). Counts only while the channel's own trailing reference is within [1/2, 2] |
| `propulsion.rpm_excess` | RPM_EXCESS_EVENT | a **separate** one-sided CUSUM on d = q - ref, same k and h (the 2.3 calibration on the deficit statistic). Same reference condition |
| `propulsion.compensation_change` | COMPENSATION_CHANGE_EVENT | the 2.3 compensation CUSUM; an alarm counts only if the claim's own BEFORE and AFTER windows are steady (peak body rate <= theta_steady) and the heading changed by at most 15 degrees between them |
| `px4.esc_offline` | ESC_OFFLINE_EVENT | an ESC's bit in `esc_online_flags` clears |
| `px4.*` | PX4's own monitors | warnings, failsafes, failure detector, allocator, estimator. An identical condition re-raised within 60 s opens no new event |

**Not an absolute value.** The deficit and excess arms are two statistics with
two names. A test (`test_the_two_arms_are_separate_one_sided_cusums_not_an_absolute_value`)
pins that a shortfall never opens the excess arm, and the reverse.

**What it ignores, by design (Phase 7):**
- PX4 `[failure_injection_manager]` messages: test-harness records, counted in
  `inputs.event_discovery.test_harness_messages_ignored`, never a trigger;
- SIH parameters, truth labels, sidecar files and known onsets: discovery
  reads none of them.

A permanent test analyses the same flight with and without an injected
message and SIH parameter change and requires identical events, symptoms and
attribution (`test_an_injection_message_or_sih_parameter_changes_nothing_in_the_product`).

## 2. Telemetry matrix design (Phase 8)

Fifteen perturbations of one healthy motor's reported RPM, applied offline to
real SITL flights. The expected outcome of each was written into
`telemetry_matrix.py` before any run.

| kind | expected event | expected telemetry state | why |
|---|---|---|---|
| x0.1, x0.5, x0.78, x0.95 | RPM_DEFICIT | DEGRADED | shortfall |
| x1.05, x1.2, x2, x10 | RPM_EXCESS | DEGRADED | excess (D-PRIME-2) |
| step down 500 rpm / step up 500 rpm | DEFICIT / EXCESS | DEGRADED | a step is a change |
| zero while offline | ESC_OFFLINE | UNAVAILABLE | PX4 says the ESC is offline: no measurement |
| static offset +1000 rpm from take-off | none required | — | no change to detect: a **blind spot** of any change detector |
| drift 0.5 per cent of value per second | none required | — | slower than the trailing reference: a **blind spot** |
| dropout 10 s | none required | — | a gap is not a measurement |
| stuck value | none required | — | visible only if the command moves |
| **every kind** | — | — | **no motor symptom** (the motor is healthy) |

**Development result** (`TELEMETRY_MATRIX_DEV.json`, in-sample flights CAL1
hover and V5 maneuvering):
- prime1: 30 of 30 as expected;
- 2.3: 8 of 30 by trigger name. By behaviour, 20 of 30: it has no excess arm
  and no offline semantics;
- no motor symptom in either release.

## 3. False-positive control design (Phase 9)

| condition | where it occurs in the held-out set |
|---|---|
| hover | HN1 (150 s), HN8 (before 70 s) |
| maneuvering | HN2, HN3, HN4, HN5, HN7, HN8 |
| wind | HN2 (N 3 m/s), HN3 (E 4), HN5 (N 2), HN7 (E 2), HN8 (N 5) |
| startup, arming, ESC spin-up | every flight (arm at 20 s, take-off to 10 m) |
| shutdown, disarming, ESC spin-down | every flight (forced disarm in flight at the end) |
| configuration transition | HN6 (magnetometer off at 90 s; EKF2 heading aiding changes) |
| logging jitter | every nominal flight again with microsecond-grid timestamp jitter (std 20 per cent of each topic's logging interval) |

**Measured per in-flight hour:** candidate events, false events, false
telemetry events, false symptoms, wrong attribution.

## 4. The comparison (Phases 10-12)

Frozen before any held-out flight (`HELDOUT_PREREGISTRATION.md`,
`HELDOUT_FREEZE.json`: 22 file hashes). `heldout_eval.py` refuses to run if
any frozen file changed or if results already exist, so it ran once.

**Why prospectively generated SITL:**
- no reachable real log has a propulsion event or a maneuvering multirotor
  flight (the network policy refuses every public real-log host);
- every untouched simulation log had already been used in development.

**Priority order (the brief's):** no wrong attribution, then no false
symptoms, then recall, then burden.

## 5. Results (`HELDOUT_RESULTS.json`, run once)

**Verdict:** **PROMOTE**. **EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY.**
The successor front end stays the commercial default of `assure`. Every
criterion held:

| criterion | requirement | prime1 | holds |
|---|---|---|---|
| S1 safety | no false symptom, no wrong motor, no wrong UNIQUE (blinded and jittered) | none of the three, in either copy | yes |
| S2 recall | every held-out fault found, at least as many as 2.3 | 6 of 6 (2.3: 5 of 6) | yes |
| S3 burden | <= 6 false events per nominal hour (blinded and jittered), at most half of 2.3's | 3.35 and 3.35 (2.3: 308.4) | yes |
| S4 onset | median absolute onset error <= 0.5 s | 0.010 s | yes |
| S5 telemetry matrix | every held-out case as expected | 30 of 30 (HN1 hover, HN4 maneuvering) | yes |
| S6 no simulation leak | raw and blinded copies give identical events, symptoms, attribution | 14 of 14 flights | yes |

### 5.1 Per flight (blinded copies)

| flight | condition | in-flight min | 2.3 events | prime1 events | prime1 symptoms |
|---|---|---|---|---|---|
| HN1 | hover | 2.13 | 0 | 0 | none |
| HN2 | maneuvering, wind N 3 | 2.30 | 16 | 0 | none |
| HN3 | maneuvering, altitude changes, wind E 4 | 1.97 | 9 | 0 | none |
| HN4 | long legs, heading reversals | 2.30 | 15 | 0 | none |
| HN5 | yaw-only spins, wind N 2 | 2.30 | 13 | 0 | none |
| HN6 | configuration transition (magnetometer off) | 2.30 | 13 | 1 | none |
| HN7 | mixed, wind E 2 | 2.30 | 15 | 0 | none |
| HN8 | hover then maneuvers, wind N 5 | 2.30 | 11 | 0 | none |
| HF1 | loss in hover | 1.80 | 1 | 1 | COMMAND_NO_RESPONSE on motor_1 (AMBIGUOUS) |
| HF2 | loss in a hold | 2.13 | 10 | 1 | COMMAND_NO_RESPONSE on motor_2 (AMBIGUOUS) |
| HF3 | loss mid-maneuver | 2.30 | 13 | 1 | none (found, not confirmed) |
| HF4 | loss mid-maneuver in wind | 2.30 | 16 | 1 | none (found, not confirmed) |
| HT1 | RPM excess on a healthy motor | 2.30 | 13 (excess missed) | 1 (RPM_EXCESS_EVENT) | none |
| HT2 | ESC telemetry offline | 1.80 | 1 | 1 (ESC_OFFLINE_EVENT) | none |

**The one nominal event** (HN6, 90.03 s) is PX4's own error
`MAG #0 failed: TIMEOUT`, 0.3 s after the magnetometer was switched off. It
is a true sensor-loss warning, not a propulsion false alarm. The
preregistration counts every event in a nominal flight, so it is counted.
**Propulsion events on nominal flights: 0.**

### 5.2 The Phase 9 measures

| measure (per in-flight hour) | prime1 | 2.3 |
|---|---|---|
| candidate events, all flights (0.509 h) | 13.76 | 286.95 |
| false events, nominal flights (0.298 h) | 3.35 (1 event: PX4's magnetometer timeout) | 308.43 |
| false events, nominal flights with timestamp jitter | 3.35 (the same event) | not run (preregistered for prime1 only) |
| false telemetry events, nominal flights | 0 | 0 |
| extra events inside fault flights | 0 | 49 |
| false symptoms, all flights | 0 | 0 |
| wrong attribution (wrong motor or wrong UNIQUE), all flights | 0 | 0 |
| median onset error | 0.010 s | 0.012 s |

**Onset errors (prime1):** -0.012, -0.020, -0.008, +0.008, 0.000, -0.096 s.
An event's time is its first triggering sample on the logging grid; the
truth time is the injection message's log time (read from the raw log, for
scoring only). Every difference is under 0.1 s.

### 5.3 What the numbers do not show

- **Statistical power is small.** 0.298 nominal hours: one event in that
  time has a 95 per cent upper bound near 16 per hour; zero events would
  have had 10.1.
- **SITL noise is far below real.** SIH has almost no vibration or sensor
  noise; real nominal flights will open more telemetry events and refuse
  more compensation evidence. The thresholds were calibrated on SITL only.
- **Maneuvering losses are found, not confirmed.** HF3 and HF4 opened an
  RPM_DEFICIT_EVENT at onset, but no symptom: the physical-response witness
  needs steady flight. That is the product's stated limitation, not a miss.
- **One airframe, one PX4 version.**

## 6. Commercial target and status

| target | status |
|---|---|
| no wrong attribution | met in simulation (0 in 0.509 h) |
| no false symptoms | met in simulation (0) |
| every injected propulsion and telemetry fault opens an event at onset | met in simulation (6 of 6, median 0.010 s) |
| alert burden an engineer will read (<= 6 per nominal flight hour) | met in simulation (3.35 per hour, and 0 propulsion events) |
| the same on real nominal flights | **not measured**: needs a pilot customer's nominal logs |

**Statement for every use of these numbers:** EVENT DISCOVERY PROMOTION IS
SIMULATION-ONLY.
