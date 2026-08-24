# ArduPilot, as it actually is today

**Verified against ArduCopter V4.8.0-dev @ `01a504b`**, built from source,
`./waf configure --board sitl && ./waf copter`.

This document records what a live run measured, not what documentation says.
Every row below was produced by
`python tools/simulation/qualify_platform.py --platform ardupilot`, which
launches the simulator, arms and climbs, and reads the real stream through the
real adapter.

---

## 1. Qualification result: **PASS**

```
positive control:  armed=True  climbed=13.4 m
messages:          131,570 in 45 s
mapped:            106,915
channels:          18/18 agree with the committed contract
observed stubs:    2, both declared
```

| channel | declared | observed | evidence |
|---|---|---|---|
| imu0.accel | INFORMATIVE | INFORMATIVE | range 1.27, sd 0.074, n=131570 |
| imu0.gyro | INFORMATIVE | INFORMATIVE | range 0.016, sd 0.0022 |
| imu1.accel | INFORMATIVE | INFORMATIVE | range 1.27, sd 0.074 |
| imu1.gyro | INFORMATIVE | INFORMATIVE | range 0.016, sd 0.0022 |
| mag.field_ut | INFORMATIVE | INFORMATIVE | range 1.0, sd 0.29 |
| baro.altitude | INFORMATIVE | INFORMATIVE | range 11.6 m, sd 0.69 |
| baro.temp_c | VALIDATED_SEMANTICS | INFORMATIVE | range 0.23 degC — varies, still not admitted (its relation is measured inert) |
| gnss.position | INFORMATIVE | INFORMATIVE | range 12.05 m, sd 0.71 |
| gnss.velocity | INFORMATIVE | INFORMATIVE | range 0.022 m/s |
| gnss.velocity_z | UNAVAILABLE | UNAVAILABLE | never arrives; GPS_RAW_INT has no vertical rate |
| battery.voltage | INFORMATIVE | INFORMATIVE | range 0.053 V under load |
| battery.current | INFORMATIVE | INFORMATIVE | range 5.19 A |
| vibration.rms | INFORMATIVE | INFORMATIVE | range 0.037 m/s^2 |
| vehicle_status.armed | INFORMATIVE | INFORMATIVE | latched, criterion DECODE |
| estimator.variances | INFORMATIVE | INFORMATIVE | logged only, never diagnosed |
| estimator.flight_mode | INFORMATIVE | INFORMATIVE | latched, criterion DECODE |
| **esc.current** | **STUB** | **STUB** | **constant at 3.2 A over 131,548 samples** |
| **esc.rpm** | **STUB** | **STUB** | **constant at 0 over 131,548 samples** |

**The two ESC rows are now confirmed by measurement, not only by source
reading.** 3.2 A is exactly 4 x 0.8 A — the hard-coded per-motor value in
`AP_ESC_Telem_SITL.cpp:72`, summed over four motors, unchanged across an
entire flight including climb. And rpm is identically 0 because
`SIM_Frame.cpp:901` derives it from `vibe_motor`, whose `VIB_MOT_MAX` defaults
to 0 (`SITL.cpp:512`).

---

## 2. Two defects this run found

### 2.1 `RAW_IMU`, not `SCALED_IMU`

The first adapter mapped inertial instance 0 from `SCALED_IMU`. On 4.8 that
message **never arrives**: `imu0.accel`, `imu0.gyro` and `mag.field_ut` were
all missing, while `SCALED_IMU2` and `SCALED_IMU3` arrived 10,030 times each.

ArduPilot publishes instance 0 as `RAW_IMU` on the `RAW_SENSORS` stream
(`GCS_Common.cpp` `send_raw_imu`, which reads `get_accel(0)`, `get_gyro(0)`,
`compass.get_field(0)`). `SCALED_IMU` carries the same instance
(`send_scaled_imu(0, ...)` at `GCS_Common.cpp:6851`) but is not always
enabled.

Scaling is identical across all four messages: `accel * 1000 / GRAVITY_MSS`
(milli-g), `gyro * 1000` (milli-rad/s), mag straight from
`Compass::get_field()` (milligauss).

**Operational consequence:** `SR2_RAW_SENS` is not optional on a companion
deployment. Without it, half the IMU evidence never arrives.

### 2.2 The probe itself was wrong

Run against a **stationary, disarmed** vehicle, the qualification tool
reported nine channels as stubs: battery voltage (no load), GNSS position (not
moving), barometric altitude (on the ground), armed (false), and more.

None of them is a stub. Nothing was happening.

The tool now arms and climbs first, and records `armed` and `climbed_m` as the
evidence that its positive control fired. Without motion the run is
`INVALID_PROBE` and **no channel verdict is issued at all**. See
`docs/simulation/SIMULATION_CONTRACT.md` RULE A.

---

## 3. Parameter renames that break Phase-I scripts

| Phase-I (3.3) | current (4.x) | consequence of using the old name |
|---|---|---|
| `SIM_GPS_GLITCH_X` | `SIM_GPS1_GLITCH_X` | write succeeds at the MAVLink level, injects nothing |
| `SIM_GPS_DISABLE` | `SIM_GPS1_ENABLE` (inverted) | denial never reaches the receiver |
| `SIM_GPS_NUMSATS` | `SIM_GPS1_NUMSATS` | satellite ladder silently flat |

**A write to a nonexistent parameter does not fail.** This is the single most
important reason every scenario carries a `verify` block: COMMAND ISSUED !=
FAULT INJECTED.

---

## 4. Simulator behaviours to know

| behaviour | detail |
|---|---|
| GPS glitch reaches the receiver | `SIM_GPS.cpp:581` `d.latitude += glitch_offsets.x` — good; the fault is upstream of the EKF |
| vibration amplitude | comes from `SIM_ACC*_RND` **together with** `SIM_VIB_MOT_MAX`; setting only the latter injects nothing |
| wind | `SIM_WIND_T` scales by `sqrt(alt/60)`, so a probe at 3.4 m sees almost none |
| both IMUs share dynamics | a SITL imu0/imu1 disagreement is a noise-model artifact, not independent-hardware evidence |
| `gpsDriftNE` monitor | exists (`AP_NavEKF3_VehicleStatus.cpp:58-66`, leaky integrator, 3 m trip) but is gated `&& onGround` — it is a pre-arm check, not an in-flight one |

---

## 5. Message inventory on the streams we request

Mapped: `RAW_IMU`, `SCALED_IMU2`, `SCALED_PRESSURE`, `GPS_RAW_INT`,
`BATTERY_STATUS`, `VIBRATION`, `ESC_TELEMETRY_1_TO_4`, `EKF_STATUS_REPORT`,
`HEARTBEAT`.

Seen and deliberately not consumed (counted in `unmapped_types`, never
silently dropped): `SCALED_IMU3`, `SCALED_PRESSURE2`, `AHRS2`, `ATTITUDE`,
`GLOBAL_POSITION_INT`, `VFR_HUD`, `SYS_STATUS`, `POWER_STATUS`, `MEMINFO`,
`NAV_CONTROLLER_OUTPUT`, `MISSION_CURRENT`.

`GLOBAL_POSITION_INT` is excluded on purpose: it is the **EKF-fused** output,
and the EKF innovation-gates faults out of it, hiding exactly what an
integrity monitor exists to see. `GPS_RAW_INT` is the raw receiver solution
and is what we consume.

---

## 6. Reproducing

```bash
export CSIA_AP_ROOT=/path/to/ardupilot
make sim-ardupilot
```

Writes `research/v1_1/results/qualification_ardupilot.json`, which carries the
positive-control evidence, every channel row, and the verdict.
