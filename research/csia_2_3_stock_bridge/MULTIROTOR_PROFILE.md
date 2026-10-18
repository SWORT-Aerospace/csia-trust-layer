# The multirotor quad profile r1 (Phase 10)

**2026-10-02.** **Code:** `csia_evidence_assurance/profiles/multirotor_quad.py`.

## 1. Why a successor profile

**The historical aircraft profile is generic.** The 2.2 pilot ran PX4
logs through it (`csia/v2/profiles/aircraft.py`, with the successor
overlay). It has one actuator, generic rails, and the v1.1 sensor payload.

On an ordinary PX4 log it observed 0 of its 68 profile records. Its
records were not the ones a PX4 log can fill.

**The brief's rule.** The successor is a new, versioned profile. The
historical profile is not modified, and its digest and every report made
with it are unchanged.

## 2. What it declares

| domain | components | dependencies | affected functions |
|---|---|---|---|
| ACTUATION | motor_0 .. motor_3 | POWER/battery, COMPUTE/control_allocator | PROPULSION, AUTONOMOUS_MISSION |
| POWER | battery | — | all |
| COMPUTE | state_estimator | COMPUTE/cpu | STATE_ESTIMATION, AUTONOMOUS_MISSION |
| COMPUTE | control_allocator | COMPUTE/state_estimator, COMPUTE/cpu | PROPULSION, AUTONOMOUS_MISSION |
| COMPUTE | cpu | — | all |

**Functions:**
- **PROPULSION:** the vehicle produces commanded thrust and torque;
- **STATE_ESTIMATION:** it knows its own state;
- **AUTONOMOUS_MISSION:** it can fly a mission without an operator.

**Record catalog: 29 records:**
- 4 motors x 4 actuation relations (`command_path`,
  `electrical_response`, `mechanical_response`, `physical_response`);
- 4 battery relations;
- 2 processes x 4 compute relations;
- CPU headroom.

**The brief's list.** The brief named:
- motor_0-3 (present);
- ESC and telemetry paths: the telemetry claim is context, by SB-1, so it
  has no profile record;
- battery (present);
- IMU, GNSS and magnetometer;
- estimator (present);
- compute (present);
- allocation (present, as COMPUTE/control_allocator);
- navigation output.

**The SENSOR domain is omitted, on purpose.**
- The v2 SENSOR domain needs the v1.1 sensor payload (trust scores per
  source).
- A PX4 log does not contain it, and nothing in the 2.3 bridge produces
  it.
- Declaring sensor components that can only ever be UNAVAILABLE would
  inflate the catalog without adding a decision.
- Navigation integrity stays with the 2.2 estimator producer, as context.
- This is a declared gap, listed in every report's coverage section.

**The motor_0 naming.** CSIA motor_m is PX4 output m, and SIH MotorN is
motor_{N-1}. The rotor geometry comes from the log's `CA_ROTORm_PX/PY`, not
from the profile.

## 3. The gate

The profile passes 2.2's load gate with no finding:
- `Q.gate()` gives ACCEPTED;
- the profile validator's PV1-PV9 apply to the declarations;
- there is no pacing overlay, so PG1 has nothing to check.

The gate runs on every analysis. A refused profile reasons nothing.

**Versioning:**
- name `multirotor-quad`, version `r1`;
- the digest covers the engine builder and the function list;
- the report and the manifest carry all three.

`build_quad_engine(n)` takes a motor count for the Phase 11 scale test
only. The released profile is four motors.

## 4. What the profile still cannot do

**Electrical and command-delivery relations:**
- No stock topic fills `actuation.command_path`: delivery to the ESC is not
  observable.
- In SIH nothing fills `actuation.electrical_response` or
  `actuation.mechanical_response` (no ESC current).
- On those motors, ACTUATION/drive_no_current,
  COMMUNICATION/command_not_delivered and POWER/path_unavailable can never
  be eliminated. The diagnosability section of every report says so.

**Hexa- and octocopters.**
- The scale test shows that the reasoning grows linearly in the motor
  count.
- But the stock statistics normalise by the median motor, and the loss
  axis assumes a planar airframe. Neither was tried beyond a quad.

**Fixed-wing and VTOL** need other profiles.
