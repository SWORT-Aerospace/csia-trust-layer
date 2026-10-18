# RUNTIME TOPOLOGY SOURCE AUDIT

Items 16, 17, 18, 19. **Source audit only. Nothing was executed.**

Question: is there at least one mechanism, provable from source, by which the
evidence-provenance graph genuinely changes during operation? If topology is
effectively constant, the runtime framing of candidate B dies and the verdict
is `STATIC_DEPENDENCE_ONLY`.

**Answer: yes, in ArduPilot, and it is proved below. But the finding is
narrower than it first appears, and §6 explains why.**

---

## 1. EXTRACTION RULES — FIXED BEFORE THE AUDIT

Item 18 forbids drawing a graph to obtain κ = 1. These rules were written
before any ArduPilot file was opened in this stage.

**A node is:**

| node kind | admitted? |
|---|---|
| a physical transducer instance (accel 0, accel 1, compass 0, GPS 0) | yes |
| a software aggregate that selects among instances (`_first_usable_accel`) | yes — as an *index*, see below |
| a MAVLink message field as emitted | yes |
| a CSIA channel | yes |
| a shared clock, calibration table or power rail | **no** — not admitted in this audit; see §7 limitations |

**An edge `u → w` is admitted only if:** a source line shows the value at `w`
computed from the value at `u`, on a path with no intervening selection that
this audit has not resolved.

**Edge categories (item 19 — no numeric probabilities anywhere):**

| category | meaning |
|---|---|
| `PROVED_FROM_SOURCE` | a cited `file:line` shows the dependency unconditionally |
| `PROVED_FROM_CONFIGURATION` | the dependency holds for a stated parameter value |
| `OBSERVED_RUNTIME` | seen in a log; not used in this audit |
| `INFERRED` | plausible but not shown by a line |
| `UNKNOWN` | not established |

**Only `PROVED_FROM_SOURCE` edges are used in the structural result below.**
No `INFERRED` edge appears in the example.

---

## 2. WHAT CSIA ACTUALLY CONSUMES

`csia/aircraft/adapters/ardupilot.py:77-81` — `HANDLED_TYPES` includes
`RAW_IMU`, `SCALED_IMU`, `SCALED_IMU2`, `SCALED_IMU3`, and `VIBRATION`.

`csia/aircraft/adapters/ardupilot.py:124-126` maps them to CSIA nodes:

```
RAW_IMU     -> imu0
SCALED_IMU  -> imu0
SCALED_IMU2 -> imu1
SCALED_IMU3 -> imu2
```

`csia/aircraft/adapters/ardupilot.py:184-189` maps `VIBRATION` to the channel
`vibration.rms`.

`csia/aircraft/adapters/base.py:58-71` — `GROUP_OF` places
`imu0.accel`, `imu0.gyro`, `imu1.accel`, `imu1.gyro` **and** `vibration.rms`
in the **same group, `"imu"`**.

So CSIA treats these as several pieces of evidence about one subsystem. That
is the pre-condition for the question: are they several pieces, or fewer?

---

## 3. PRODUCER-SIDE PROVENANCE — ARDUPILOT

ArduPilot at `/home/user/ardupilot/ardupilot`, HEAD `01a504b`, which is the
revision the adapter already declares itself verified against
(`csia/aircraft/adapters/ardupilot.py:3`).

### 3.1 `RAW_IMU` — static, instance 0

`libraries/GCS_MAVLink/GCS_Common.cpp:2241-2242`

```cpp
const Vector3f &accel = ins.get_accel(0);
const Vector3f &gyro  = ins.get_gyro(0);
```

Hardcoded literal `0`. `PROVED_FROM_SOURCE`. **No runtime variation.**

### 3.2 `SCALED_IMU` / `SCALED_IMU2` / `SCALED_IMU3` — static, instances 0/1/2

`libraries/GCS_MAVLink/GCS_Common.cpp:6851, 6856, 6861`

```cpp
send_scaled_imu(0, mavlink_msg_scaled_imu_send);
send_scaled_imu(1, mavlink_msg_scaled_imu2_send);
send_scaled_imu(2, mavlink_msg_scaled_imu3_send);
```

Literal instance per message id. `PROVED_FROM_SOURCE`. **No runtime
variation.** (The CSIA adapter already cites these exact lines at
`ardupilot.py:113-114`, independently of this audit.)

### 3.3 `VIBRATION` — **runtime-variable instance**

`libraries/GCS_MAVLink/GCS_Common.cpp:3075`

```cpp
Vector3f vibration = ins.get_vibration_levels();
```

No instance argument. Resolving the overload:

`libraries/AP_InertialSensor/AP_InertialSensor.h:312`

```cpp
Vector3f get_vibration_levels() const { return get_vibration_levels(_first_usable_accel); }
```

So the instance is `_first_usable_accel`. `PROVED_FROM_SOURCE`.

### 3.4 `_first_usable_accel` is reassigned every loop, from health

`libraries/AP_InertialSensor/AP_InertialSensor.cpp:2001-2006`, inside
`AP_InertialSensor::update()` (function opens at line 1926, called once per
main-loop iteration):

```cpp
for (uint8_t i=0; i<INS_MAX_INSTANCES; i++) {
    if (_accel_healthy[i] && _use(i)) {
        _first_usable_accel = i;
        break;
    }
}
```

with `_accel_healthy[i]` cleared a few lines earlier
(`AP_InertialSensor.cpp:1986-1989`) for any accel whose error count has risen
above its startup value while some other accel has none:

```cpp
if (_accel_healthy[i] && _accel_error_count[i] > _accel_startup_error_count[i] && have_zero_accel_error_count) {
    // we prefer not to use a accel that has had errors
    _accel_healthy[i] = false;
}
```

`PROVED_FROM_SOURCE`. **The index changes at runtime, in flight, as a function
of sensor health.** This is not a parameter read at boot.

### 3.5 Nothing on the wire announces the change

`modules/mavlink/message_definitions/v1.0/common.xml:6632-6641` — the
`VIBRATION` message (id 241) has exactly seven fields: `time_usec`,
`vibration_x/y/z`, `clipping_0/1/2`. **There is no instance, device-id or
selection field.**

A MAVLink consumer therefore cannot tell, from `VIBRATION`, which accelerometer
produced it, nor that the answer changed.

---

## 4. THE DYNAMIC EXAMPLE (item 17)

Nodes: `accel0`, `accel1` (transducers); `RAW_IMU`, `SCALED_IMU2`,
`VIBRATION` (wire); `imu0.accel`, `imu1.accel`, `vibration.rms` (CSIA).

**State N0 — nominal, `_first_usable_accel == 0`:**

```
accel0 ──> RAW_IMU     ──> imu0.accel
accel0 ──> VIBRATION   ──> vibration.rms
accel1 ──> SCALED_IMU2 ──> imu1.accel
```

Pair `(vibration.rms, imu1.accel)`: two disjoint paths, from `accel0` and
`accel1`. κ_prov = 2.
Pair `(vibration.rms, imu0.accel)`: both from `accel0`. κ_prov = 1.

**State N1 — after accel0 is marked unhealthy, `_first_usable_accel == 1`:**

```
accel0 ──> RAW_IMU     ──> imu0.accel
accel1 ──> VIBRATION   ──> vibration.rms
accel1 ──> SCALED_IMU2 ──> imu1.accel
```

Pair `(vibration.rms, imu1.accel)`: both from `accel1`. κ_prov = **1**.
Pair `(vibration.rms, imu0.accel)`: now disjoint. κ_prov = **2**.

**The pairing swaps, and no field in the telemetry says so.** Every edge above
is `PROVED_FROM_SOURCE` with a cited line.

Item 16's gate is therefore passed: the evidence-provenance graph genuinely
changes during operation, by a mechanism proved from source, and the change is
invisible on the interface CSIA consumes.

---

## 5. PX4 — THE CONTRAST, AND WHY IT MATTERS

PX4 at `/home/user/px4`.

`msg/SensorSelection.msg`:

```
# Sensor ID's for the voted sensors output on the sensor_combined topic.
# Will be updated on startup of the sensor module and when sensor selection changes
uint64 timestamp
uint32 accel_device_id      # unique device ID for the selected accelerometers
uint32 gyro_device_id       # unique device ID for the selected rate gyros
```

Published on change at `src/modules/sensors/voted_sensors_update.cpp:276`
(`_sensor_selection_pub.publish(_selection);`), advertised at line 57, and
consumed by downstream modules that must follow the switch — e.g.
`src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp:81-82`,
whose own comment reads: *"sensor_selection needed to change the active sensor
if the primary stops updating"*.

**So PX4 has the same phenomenon and already represents it as a first-class
message.** ArduPilot has the phenomenon and does not put it on the wire.

---

## 6. WHAT THIS DOES TO CANDIDATE B — READ BEFORE CELEBRATING

The §5 finding is bad news for the candidate, not good news, and it is
recorded here rather than buried.

1. **The phenomenon is real but already modelled by one of the two platforms.**
   PX4 publishes the selection identity on change. A monitor consuming uORB
   already has the information a provenance graph would reconstruct. What is
   missing in ArduPilot is a *field in a telemetry message*, not a concept.

2. **That reframes the gap as a protocol/telemetry deficiency.** "MAVLink's
   `VIBRATION` does not carry the accelerometer identity that PX4's
   `SensorSelection` does" is an engineering observation about an interface. It
   is a good defect report. It is not obviously a research contribution, and
   item 26 of the frontier brief hard-kills contributions that reduce to an
   implementation-level finding.

3. **The switch is a consequence of a health decision the autopilot already
   made.** `_first_usable_accel` only moves because `_accel_healthy[0]` went
   false. The autopilot knows. `SYS_STATUS` carries aggregate sensor-health
   bits — CSIA does not subscribe to `SYS_STATUS`
   (`ardupilot.py:77-81`), but a general MAVLink consumer could. So the claim
   "nothing downstream can know" is **false in general** and true only for a
   consumer that, like CSIA, does not subscribe to the health message. That is
   a property of CSIA's subscription set, not of the field.

Points 1–3 are the honest reading. The runtime-topology gate passes; the
*significance* gate does not obviously pass.

---

## 7. LIMITATIONS OF THIS AUDIT

- **Only three message families were audited** (`RAW_IMU`, `SCALED_IMU*`,
  `VIBRATION`) plus their CSIA channels. GNSS, barometer, battery and the
  estimator were not audited in this stage.
- **Shared clocks, shared calibration and shared power rails were excluded by
  the extraction rules (§1).** They are real dependencies. Their exclusion
  means the graph under-represents true coupling — see
  `FORMAL_REDUCTION.md` §4 on what that does to the bound direction.
- **Environmental coupling is entirely outside the graph.** Two accelerometers
  on one airframe both respond to the same structural vibration with no
  software edge between them. This is conceded to hostile Reviewer I and is
  the second half of the argument in `MENGER_CLAIM_COUNTEREXAMPLES.md` §3.
- **No execution.** Nothing here was run; no log was replayed; no κ was
  computed by code. Every statement is a citation to a line of source.
