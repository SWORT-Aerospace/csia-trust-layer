# FULL-TEXT READING LOG

| # | source | full text obtained | pages/sections read | notes |
|---|---|---|---|---|
| — | *(none)* | — | — | — |

**Full texts read in this stage: 0.**

Not "few". Not "partial". Zero. Every attempt is logged in
`REQUIRED_READING_MANIFEST.md` §0 with the host and the failure code.

---

## What WAS read in full, and why it does not substitute

Item 1 forbids substituting search snippets for full text. It does not forbid
reading *source code*, and source code is the only primary material this stage
could obtain. Read in full:

| artefact | revision | what was read |
|---|---|---|
| `libraries/GCS_MAVLink/GCS_Common.cpp` (ArduPilot) | `01a504b` | `send_raw_imu` (2237-2266), `send_scaled_imu` dispatch (6851-6861), `send_vibration` (3070-3087) |
| `libraries/AP_InertialSensor/AP_InertialSensor.h` (ArduPilot) | `01a504b` | accessor overloads, lines 174-338 |
| `libraries/AP_InertialSensor/AP_InertialSensor.cpp` (ArduPilot) | `01a504b` | `update()` health and selection block, 1975-2010 |
| `modules/mavlink/message_definitions/v1.0/common.xml` | `01a504b` | `VIBRATION` message definition, 6632-6641 |
| `msg/SensorSelection.msg` (PX4) | working tree | whole file |
| `src/modules/sensors/voted_sensors_update.cpp` (PX4) | working tree | publication sites, 57 / 198-276 |
| `src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp` (PX4) | working tree | selection-follow logic, 81-95, 232-234 |
| `csia/aircraft/adapters/ardupilot.py` | `65fa17e` | 1-190 |
| `csia/aircraft/adapters/base.py` | `65fa17e` | 40-80 |

**This establishes what the systems do. It establishes nothing about what the
literature has already published about it.** The two questions are separate,
and only the first was answerable here.

---

## Consequence

The prior-art gate returns `INCONCLUSIVE_MISSING_FULLTEXT`
(`REQUIRED_READING_MANIFEST.md` §2).

The four reduction documents in this package —
`ARP4761_CCA_REDUCTION.md`, `COMMON_INFORMATION_REDUCTION.md`,
`META_DIAGNOSIS_REDUCTION.md`, `DYNAMIC_FAULT_TREE_REDUCTION.md` — therefore
each record a **question and a decision rule**, not a verdict. Where they
describe what a body of work is understood to do, that is general background
knowledge, is labelled as such, and is **not** used to kill or to support the
candidate.
