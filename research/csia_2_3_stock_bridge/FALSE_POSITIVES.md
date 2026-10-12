# False-positive search (Phase 26)

**2026-10-02.**

- **Script:** `false_positive_search.py`.
- **Outputs:**
  - `FALSE_POSITIVE_SEARCH.json`: final code;
  - `FALSE_POSITIVE_SEARCH_r2_as_found.json`: the producers as first
    frozen, which the validation flights exposed.

## 1. What counts as false

Every log went through the product path: configuration B, discovered
events.

- **On a nominal flight,** every event is false. That covers the benign
  onset flights, where an event near the benign heading change is counted
  separately.
- **On a flight with an injected fault,** an event more than 2 s before
  the injection is false.
- **Events more than 2 s after a persistent injection** may be
  consequences, such as a failsafe seconds after a GPS loss. They are
  counted apart and never called false or detected.

**Per false event:**
- its trigger kinds and its duration, up to "cleared";
- whether the analysis RETAINED it (a symptom was raised at any of its
  checkpoints) or DISMISSED it (no symptom).

## 2. Results, final code

| logs | flights | in flight (h) | false events | per flight | per in-flight hour | retained | dismissed |
|---|---|---|---|---|---|---|---|
| XSYS-001 fault flights, before the injection | 55 | 0.522 | 0 | 0 | 0 | 0 | 0 |
| XSYS-001 benign-onset flights | 11 | 0.104 | 0 | 0 | 0 | 0 | 0 |
| validation, nominal maneuvering (V5, V6, V11) | 3 | 0.115 | **33** | 11 | **287** | 0 | 33 |
| validation, injected (V1-V4, V7-V10, V12, V13), before the injection | 10 | 0.187 | 6 (V12, V13: the maneuvers before the loss) | 0.6 | 32 | 0 | 6 |
| **all** | **79** | **0.929** | **39** | 0.49 | 42 | **0** | **39** |

**Later events, after a persistent injection** (8, not counted false):
- V7 and V8: the failsafe 5 s after the GPS loss or battery fault;
- V10: deficit-direction telemetry alarms once the trailing reference
  absorbed the x 10 RPM;
- V13: maneuvers during the loss, with PX4's allocator reporting setpoints
  not achieved.

**By trigger kind,** all 39 false events are `propulsion.compensation_change`.
- **Duration**, up to "cleared" (the trailing reference has absorbed the
  new command split): 1.2-9.4 s, median 4.9 s. One V13 event lasted
  69.8 s, because the loss came during it.
- **Never:**
  - the telemetry CUSUM;
  - PX4's failure detector;
  - a battery warning;
  - the allocator flags on a nominal flight;
  - an EKF2 rejection.

## 3. Hover against maneuvering

**In hover the false-event rate is zero:**
- 66 XSYS-001 flights, 0.63 h in flight;
- none during the benign heading change;
- none in the hold segments of the validation flights.

**Under maneuvering it is about 11 per 2.5-minute flight.**
- Every reposition or yaw turn changes the split of commands between the
  motor pairs.
- The compensation CUSUM reads that split as a change, with thresholds set
  from hover.

## 4. What those events did, as first frozen and now

**As first frozen (`FALSE_POSITIVE_SEARCH_r2_as_found.json`): all 22
maneuver events in V5 and V6 were RETAINED.**
- Each event's AFTER window [t0 + 10, t0 + 15] s overlapped the next
  maneuver.
- The compensation reported a loss on the yaw pair, motors 0 and 1, and
  2.1.1 raised `COMMAND_NO_RESPONSE` on both.
- The symptom was withdrawn 5 s later, when the evidence left its
  validity window.
- The end-of-log result, "no symptom", did not show it.

That was a wrong answer: a healthy motor blamed, repeatedly, on a nominal
flight.

**Now: all 39 are DISMISSED, with 0 symptoms at any time.**
- The compensation claim checks its register assumption, near-steady
  flight in both windows. Above theta_steady (2 x the apparatus hover
  null of the peak body rate) it is UNAVAILABLE (NOT_STEADY_FLIGHT).
- The summary now names any symptom raised during the flight, so a
  transient wrong answer can no longer hide behind the final tick.
- The fix was tested blind on V11-V13, flown after it was committed.

## 5. What remains

**The event list is noisy under maneuvering:** 287 false events per
in-flight hour of nominal maneuvering flight. Each one is dismissed, and
the report says so. But an engineer reading a normal flight's report must
page through them.

**What would reduce it:**
- discovery that reads the commanded setpoints (`trajectory_setpoint`,
  `vehicle_attitude_setpoint`), so that a commanded change in the command
  split is not a candidate event;
- or null data from maneuvering flights, calibrated by the same rule.

Neither was built here. Neither may be tuned on these validation flights,
which are now development data.

**The rate is SIH's.** Hardware adds vibration, gusts and ESC noise.
Hover-only nulls from SIH say nothing about a real vehicle's false-event
rate.
