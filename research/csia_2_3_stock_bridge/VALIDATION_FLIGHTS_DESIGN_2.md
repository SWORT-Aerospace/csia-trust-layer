# Validation flights, second design: the steadiness fix, blind (frozen before flying)

**2026-10-02. Written and committed, with the code it tests, before any of
these flights is flown.**

## 1. Why a second design

**What the first design found.** Its flights (`VALIDATION_FLIGHTS.md`,
`FALSE_POSITIVES.md`) exposed two gaps between the bridge's code and its
own claim register:
- **V5 and V6 (nominal, maneuvering):** every reposition and yaw turn
  raised a transient false `COMMAND_NO_RESPONSE` on motors 0 and 1. The
  compensation claim assumes "near-steady flight in both windows", and the
  code did not check it.
- **V9 (ESC telemetry off):** an offline ESC's zero RPM was read as a
  measured deficit.

**What was fixed, all in this commit:**
- **The steadiness check:** the compensation is UNAVAILABLE
  (NOT_STEADY_FLIGHT) when the largest body rate in its BEFORE or AFTER
  window exceeds theta_steady.
- **The threshold:** theta_steady = 0.0989 rad/s, which is 2 x the
  apparatus hover null maximum (calibration revision 3; no XSYS-001 or
  validation flight sets it).
- **The ESC-offline handling and the power gate at L >= 1.**
- **The summary** now names every symptom raised at any time, not only
  those at the end of the log.

**Why new flights.** V5, V6 and V9 found the gaps, so they cannot test the
fix blind. These three new flights can.

## 2. Rules

The rules of the first design apply unchanged:
- the same build;
- PX4's default logging;
- faults through `SIH_MOT_EFFn` over MAVLink;
- the apparatus MAVLink helper, imported unchanged;
- injection times read for scoring only;
- each run flown once;
- expectations not revised after flying.

**The code under test is this commit.** Nothing in the product changes
between this commit and the scoring.

**The schedule.**
- Repositions via `MAV_CMD_DO_REPOSITION`, every 15 s from 40 s, with
  60 m legs and 180-degree heading changes. This is a different pattern
  from V5 and V6 (10 s, 40 m, 90 degrees).
- Times are seconds from boot; arm at 20 s.

## 3. The runs

| id | purpose | maneuvers | injection | end |
|---|---|---|---|---|
| V11 | nominal, maneuvering, crosswind | repositions at 40, 55, ..., 145 s | none; `SIH_WIND_E` = 3 m/s from boot | 160 s |
| V12 | a loss after maneuvering, in a steady hold | repositions at 40, 55, 70 s, then hold at the origin | `SIH_MOT_EFF3` = 0.6 (motor_2) at 100 s | 130 s |
| V13 | a loss during maneuvering | repositions at 40, 55, ..., 130 s | `SIH_MOT_EFF3` = 0.6 (motor_2) at 77 s, mid-leg | 140 s |

## 4. Expectations, stated before flying

Scored over the whole timeline: "at any time" means at any tick, not only
at the end.

| id | expectation |
|---|---|
| V11 | no symptom at any time. Events may still be discovered: event discovery is unchanged, and every event is counted as a false event. |
| V12 | an event within 2 s of the injection, with motor_2 among its triggers; `COMMAND_NO_RESPONSE` on motor_2 and on no other motor at any time; SENSOR/response_sensor eliminated; ACTUATION/mechanical among the remaining |
| V13 | no symptom on any motor other than motor_2 at any time; for the event at the injection, motor_2's telemetry deficit is reported (DEGRADED) and its compensation is UNAVAILABLE (NOT_STEADY_FLIGHT), because the vehicle is maneuvering in that event's BEFORE window |

**What V13 expects is a miss, stated in advance.** During continuous
maneuvering the product cannot use the compensation, so it cannot confirm
the loss. It must say so: the telemetry deficit as context, and why the
physical check was not possible. It must never blame another motor.
