# SELECTED DYNAMIC EXAMPLE

Item 17. One source-grounded example in which nominally distinct evidence
channels change their upstream dependency at runtime. Audit only — nothing was
executed.

---

## The example

**ArduPilot `01a504b`. The pair `(vibration.rms, imu1.accel)` as CSIA consumes
them.**

| CSIA channel | MAVLink message | producer instance | citation |
|---|---|---|---|
| `imu0.accel` | `RAW_IMU` / `SCALED_IMU` | accel **0**, hardcoded | `GCS_Common.cpp:2241-2242`, `:6851` |
| `imu1.accel` | `SCALED_IMU2` | accel **1**, hardcoded | `GCS_Common.cpp:6856` |
| `vibration.rms` | `VIBRATION` | accel **`_first_usable_accel`** | `GCS_Common.cpp:3075` → `AP_InertialSensor.h:312` |

`_first_usable_accel` is reassigned inside `AP_InertialSensor::update()` — once
per main-loop iteration — from the runtime health array:

- health cleared for an accel that has accumulated errors:
  `AP_InertialSensor.cpp:1986-1989`
- index reassigned to the first healthy, in-use accel:
  `AP_InertialSensor.cpp:2001-2006`

All three CSIA channels sit in the **same** group, `"imu"`
(`csia/aircraft/adapters/base.py:58-71`), so CSIA treats them as several pieces
of evidence about one subsystem.

## The transition

**N0 — `_first_usable_accel == 0`:** `vibration.rms` ← accel0,
`imu1.accel` ← accel1. Distinct. κ_prov = 2.

**N1 — accel0 unhealthy, `_first_usable_accel == 1`:** `vibration.rms` ← accel1,
`imu1.accel` ← accel1. **Same transducer.** κ_prov = 1.

The pairing with `imu0.accel` swaps the other way at the same instant.

## Nothing announces it

`VIBRATION` (message id 241, `common.xml:6632-6641`) has seven fields —
`time_usec`, `vibration_x/y/z`, `clipping_0/1/2`. No instance field, no device
id, no selection field. A MAVLink consumer cannot tell which accelerometer
produced the sample, nor that the answer changed mid-flight.

## Why this is a weaker example than it looks

Four caveats, all established in this stage. They are here rather than in a
footnote because they are most of the finding.

1. **PX4 already publishes this.** `msg/SensorSelection.msg` carries
   `accel_device_id` and `gyro_device_id` and is published on change
   (`voted_sensors_update.cpp:276`), with downstream modules subscribing
   precisely to follow the switch
   (`VehicleAngularVelocity.cpp:81-82`). The phenomenon is known well enough to
   have a dedicated message in one of the two stacks. What ArduPilot lacks is a
   *field on the wire*, not a concept.

2. **The autopilot knows.** The switch happens because `_accel_healthy[0]` went
   false. `SYS_STATUS` carries aggregate sensor-health bits. CSIA does not
   subscribe to `SYS_STATUS` (`ardupilot.py:77-81`), so *CSIA* is blind — but
   that is a property of CSIA's subscription set, not of the field.

3. **κ_prov changing does not establish that anything diagnostic changed.**
   `MENGER_CLAIM_COUNTEREXAMPLES.md` §1.1 works this exact pair: `vibration.rms`
   is a high-passed magnitude statistic and `imu1.accel` is a low-passed signed
   vector. Even in state N1, with one shared transducer, a step bias at accel1
   moves one and not the other — so the comparison is *not* blind. The
   structural collapse is real; the diagnostic consequence is not demonstrated
   and, for at least one important fault signature, is demonstrably absent.

4. **The example is one pair in one message family.** GNSS, barometer, battery
   and the estimator were not audited.

## What the example does and does not license

**Licensed:** the statement that the evidence-provenance topology of a real
autopilot changes in flight, by a mechanism proved from source, invisibly on
the interface CSIA consumes. Item 16's gate passes; the verdict is not
`STATIC_DEPENDENCE_ONLY`.

**Not licensed:** that this matters diagnostically; that it is novel; that
κ_prov is the right way to detect it; or that a consumer could not know by
other means. Caveats 1-3 each attack one of those.
