# PX4, as it actually is today

**Built and running: PX4-Autopilot @ `547e2ca`, `px4_sitl_default`.**

Live MAVLink stream verified through the CSIA PX4 adapter. Qualification
status and the exact blocker are in section 2 — read that before quoting any
PX4 number.

---

## 1. Getting PX4 SITL to run at all

Two things cost time and are worth writing down.

**Build dependencies are Python packages, not apt packages.** A bare
`make px4_sitl_default` fails at CMake configure with
`please install using "pip3 install kconfiglib"`. The set needed:

```bash
pip install kconfiglib jinja2 pyros-genmsg empy==3.3.4 packaging \
            jsonschema future lxml pyserial toml numpy
```

**`PX4_SIM_MODEL=none_iris` does not produce a running vehicle.** With no
simulator attached, `simulator_mavlink` blocks on TCP 4560 waiting for one and
the rest of the system never boots — **no heartbeat ever appears**, on any
port. We waited 90 s twice before reading the source.

The answer is **SIH — Simulation In Hardware**: PX4's own rigid-body model,
running inside the PX4 process. No Gazebo, no jMAVSim, no Java, no external
frontend.

```bash
PX4_SYS_AUTOSTART=10040 PX4_SIM_MODEL=sihsim_quadx \
  ./build/px4_sitl_default/bin/px4 -d \
  -s build/px4_sitl_default/etc/init.d-posix/rcS \
     build/px4_sitl_default/etc
```

Heartbeat then appears on `udp:127.0.0.1:14550` within a few seconds, with
real dynamics behind it.

---

## 2. Qualification status: **INVALID_PROBE**

**No PX4 channel verdict is issued.**

```
positive control:  armed=True   climbed=0.4 m   (threshold: >= 1.0 m)
verdict:           INVALID_PROBE
```

The vehicle **arms** — that took `COM_ARM_WO_GPS`, the EKF arming thresholds,
the supply/USB circuit breakers, `AUTO.TAKEOFF` entry and force-arm
(`param2=21196`) — but `MAV_CMD_NAV_TAKEOFF` does not produce a climb: 0.4 m,
below the 1.0 m the probe requires.

Under RULE A an informativeness measurement without motion is not a weak
measurement, it is not a measurement. The tool therefore reports
`INVALID_PROBE` and withholds every channel verdict rather than reporting
constancy as evidence. **PX4 is not qualified, and nothing here may be quoted
as a PX4 result.**

This is the contract working, not a tooling failure. It is also the honest
status: **PX4 is not qualified.**

### What the live stream did show

These are observations from a booted SIH vehicle that did not climb, recorded for
integration purposes and **not** as qualification verdicts:

| channel | arrived? | observation |
|---|---|---|
| imu0.accel | yes | range 0.80 m/s^2, sd 0.121, n=14198 |
| imu0.gyro | yes | range 0.075 rad/s, sd 0.0122 |
| mag.field_ut | yes | range 15.7 uT, sd 2.74 |
| baro.altitude | yes | range 0.58 m, sd 0.089 |
| gnss.position | yes | range 0.27 m |
| gnss.velocity | yes | range 0.20 m/s |
| vibration.rms | yes | range 0.012 m/s^2 |
| estimator.variances | yes | range 0.152 — `ESTIMATOR_STATUS` ratios |
| estimator.flight_mode | yes | decoded via main/sub mode |
| vehicle_status.armed | yes | latched; arms on the current sequence, but the climb does not follow |
| battery.voltage | yes | constant 16.2 V (unloaded, stationary) |
| **imu1.accel / imu1.gyro** | **no** | `SCALED_IMU2` is not published |
| **esc.current / esc.rpm** | **no** | `ESC_STATUS` is not published |
| **battery.current** | **no** | not populated in SIH |

### Three findings that matter for CSIA on PX4

1. **No second IMU.** PX4 SIH does not publish `SCALED_IMU2`, so `imu1` never
   arrives. **CSIA's dual-IMU cross-check relation cannot be evaluated on this
   backend at all** — and dual-IMU is one of the two families v1 handles best.
   A PX4 evaluation on SIH would silently omit it.
2. **No ESC telemetry.** `ESC_STATUS` never arrives, so on PX4 the ESC
   channels are `UNAVAILABLE` rather than `STUB_OR_NONINFORMATIVE`. Different
   reason, same outcome: `power_thrust` stays dark. The contract rows are
   written against ArduPilot and are *inaccurate for PX4* — a row that says
   CONSTANT_STUB should say UNAVAILABLE here. Recorded, not silently
   generalised.
3. **Estimator health is ratios, not variances.** PX4 sends
   `ESTIMATOR_STATUS` with normalised innovation *ratios*; ArduPilot sends
   `EKF_STATUS_REPORT` with *variances*. They are not interchangeable. The
   adapter tags the value with `_source: ESTIMATOR_STATUS(ratios)` so a
   post-flight reader cannot compare one against the other by accident.

---

## 3. What remains before PX4 can be qualified

| item | owner | note |
|---|---|---|
| **make SIH climb** | engineering | arming is solved; `MAV_CMD_NAV_TAKEOFF` yields 0.4 m. Next: check whether SIH needs `MIS_TAKEOFF_ALT`, an offboard setpoint stream, or a mission item rather than a bare takeoff command |
| decide the SIH-vs-Gazebo question | engineering | SIH gives dynamics with no dependencies but publishes fewer messages; Gazebo publishes more but adds a heavy dependency |
| per-platform contract rows | engineering | the ESC rows are ArduPilot-specific and must not be read as PX4 verdicts |
| re-run `make sim-px4` to PASS | engineering | until it does, **no PX4 result may be quoted** |

---

## 4. Adapter status

The PX4 adapter itself is implemented and unit-tested against synthetic
messages, and verified against the live stream for the 13 channels that
arrive. It is deliberately not a copy of the ArduPilot adapter:

| difference | why it matters |
|---|---|
| `HIGHRES_IMU` is SI | applying ArduPilot's milli-scaling is a silent 1000x error |
| mag is gauss (x100 -> uT) | ArduPilot's is milligauss (x0.1 -> uT) |
| `fields_updated` bitmask | a field whose bit is clear is a repeat, not a new measurement |
| mode in main/sub bytes | not a flat enum like ArduCopter's `custom_mode` |

The two adapters share no scaling code, on purpose.

---

## 5. Reproducing

```bash
export CSIA_PX4_ROOT=/path/to/PX4-Autopilot
make sim-px4
```

Writes `research/v1_1/results/qualification_px4.json`, including
`PROBE_VALID` and the positive-control evidence.
