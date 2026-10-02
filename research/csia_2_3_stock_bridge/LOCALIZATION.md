# Four-motor localization (Phase 17)

**2026-10-02.** **Data:**
- validation flights V1-V4 (`VALIDATION_FLIGHTS_DESIGN.md`, committed
  before flying; results in `VALIDATION_RESULTS.json`; reports in
  `research/csia_2_3_stock_bridge/reports/`, V1-V4);
- the XSYS-001 replay (`UNKNOWN_ONSET.md`).

## 1. Why new flights were needed

**Every XSYS-001 fault is on SIH Motor1** (CSIA motor_0), and so is every
apparatus sweep fault. Nothing showed that the product can tell motor 1
from motor 3.

**The validation flights:**
- put the same loss (SIH_MOT_EFFn = 0.6 at 50 s from boot) on each motor
  in turn;
- use PX4's default logging, so these are ordinary logs;
- were each flown once;
- were each analysed with the command line alone (no onset, label or
  sidecar).

## 2. Results

| run | injected | event (onset error) | first trigger | motors in the event | 2.1.1 result | compensation C (1/eta - 1 = 0.667) | telemetry deficit L (1 - eta = 0.4) |
|---|---|---|---|---|---|---|---|
| V4 | motor_0 | 1 (-0.088 s) | telemetry, motor 0 | 0, 1 | `COMMAND_NO_RESPONSE|motor_0` | 0.6631 | 0.3991 |
| V1 | motor_1 | 1 (-0.136 s) | telemetry, motor 1 | 0, 1 | `COMMAND_NO_RESPONSE|motor_1` | 0.6617 | 0.3991 |
| V2 | motor_2 | 1 (-0.056 s) | telemetry, motor 2 | 2 | `COMMAND_NO_RESPONSE|motor_2` | 0.6634 | 0.3986 |
| V3 | motor_3 | 1 (-0.156 s) | telemetry, motor 3 | 2, 3 | `COMMAND_NO_RESPONSE|motor_3` | 0.6620 | 0.3977 |

**In every run:**
- exactly one symptom, on the injected motor, and on no other;
- SENSOR/response_sensor eliminated by the compensation;
- AMBIGUOUS among drive_no_current, mechanical, command_not_delivered and
  path_unavailable;
- attribution not justified.

All four met their stated expectation.

**Together with XSYS-001** (motor_0, 55/55 at eta 0.55-0.95), every motor
of the quad has now been localized at least once, on ordinary logs.

**After maneuvering (V12, second design, blind).** The loss on motor_2 came
during a hold after three maneuvers. It was localized the same way:
- C = 0.664, L = 0.399;
- no other motor at any time.

**During continuous maneuvering (V13)** it was not confirmed:
NOT_STEADY_FLIGHT, a stated and honest miss (`VALIDATION_FLIGHTS.md`).

## 3. The secondary motor, and why it is not localized

**Three of four events also contain a compensation trigger on a second
motor:**
- V4 (motor_0 lost): motor 1;
- V1 (motor_1 lost): motor 0;
- V3 (motor_3 lost): motor 2.

**Why that motor.** In PX4's quad X, motors 0 and 1 spin one way and 2 and
3 the other. When one motor loses thrust, the loop asks a little more of
the motor that shares its spin direction, to hold yaw torque. In V1,
motor 0's compensation rose 0.048 in the first second.

**Why no symptom.** The rise is transient. At the AFTER checkpoint motor
0's compensation is -0.0033, which is NOT_APPLICABLE: no local deficit and
no sustained rise. 2.1.1 therefore raises nothing on it.

**What the report shows.** It lists the second motor among the event's
triggers ("on motor(s) 0, 1") and names only the injected one in the
symptom. A trigger is a reason to look, not a finding.

## 4. Subsystem ambiguity is the right answer

**What the localization does and does not say.**
- It is to a motor's propulsion chain, never to a part of it.
- On a stock SIH log, the floor of never-eliminable explanations is
  {drive_no_current, command_not_delivered, path_unavailable}
  (`REPORT_PRODUCT.md`).
- Mechanical stays, because no ESC current is available to test the stall.

**Why that is correct.**
- The brief accepts subsystem ambiguity.
- The product reports exactly this ambiguity, with the records that would
  resolve it: ESC current, a measured battery current. For delivery to the
  ESC, nothing in a stock log can resolve it.

## 5. Limits

- **One loss level per motor (0.6), one flight each, in a hover.**
  Sensitivity per motor is not established beyond XSYS-001's motor_0 sweep.
- **Simultaneous losses on two motors were not flown.** The scale test
  (`SCALE.md`) shows that the reasoning handles k symptoms independently,
  but the statistics normalise by the median motor. With two of four
  motors deviating, the median moves, and the per-motor change is then
  understated. That is untested on flight data.
- **Maneuvering degrades event discovery** (`FALSE_POSITIVES.md`).
- **A loss during continuous maneuvering is not localized at all (V13).**
  The compensation is not assessable there.
