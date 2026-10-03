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

HELDOUT_RESULTS_SECTION
