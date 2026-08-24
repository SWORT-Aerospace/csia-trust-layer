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

## 2. Qualification status: **PARTIAL**

**Presence findings stand. No constancy verdict is issued.**

```
positive control:  armed=True   climbed=0.43 m   (threshold: >= 1.0 m)
verdict:           PARTIAL
                   no motion, so constancy is not assessed;
                   PRESENCE findings stand, and a channel the contract
                   admits as evidence never arrived
```

**This was `INVALID_PROBE` until the probe was corrected.** The old gate
voided the entire run when the airframe did not climb, which threw away
findings that do not depend on motion at all: a run that collected 18,900
samples and established that `imu1.*`, `esc.*` and `battery.current` never
arrive on SIH reported none of it.

Two kinds of claim, two different validity conditions:

| claim | example | motion needed? |
|---|---|---|
| **PRESENCE** | "this channel never arrived" | **no** — an unpublished message is unpublished whether or not the vehicle flew |
| **CONSTANCY** | "this channel is a stub" | **yes** — on a static airframe "constant" describes the trial, not the channel |

Presence findings are now always issued; constancy findings stay gated. Under
RULE A an informativeness measurement without motion is still not a
measurement, so **no constancy claim below may be quoted as a PX4 result.**

The vehicle **arms** — that took `COM_ARM_WO_GPS`, the EKF arming thresholds,
the supply/USB circuit breakers, `AUTO.TAKEOFF` entry and force-arm
(`param2=21196`) — but `MAV_CMD_NAV_TAKEOFF` does not produce a climb: 0.43 m,
below the 1.0 m the probe requires.

**PX4 is not qualified.** Getting SIH to climb is the remaining work; see §3.

### 2.1 PRESENCE findings — valid on this run

Motion-independent, so these are results rather than observations. Measured
over ~18,900 samples per channel, PX4-Autopilot @ `547e2ca`, `sihsim_quadx`:

| channel | contract declares | observed | admissible? |
|---|---|---|---|
| **`battery.current`** | INFORMATIVE | **never arrived** | **yes** |
| **`imu1.accel`** | INFORMATIVE | **never arrived** | **yes** |
| **`imu1.gyro`** | INFORMATIVE | **never arrived** | **yes** |
| `esc.current` | STUB_OR_NONINFORMATIVE | never arrived | no |
| `esc.rpm` | STUB_OR_NONINFORMATIVE | never arrived | no |
| `gnss.velocity_z` | UNAVAILABLE | never arrived | no |

The three bold rows are what makes the verdict `PARTIAL` rather than
`INVALID_PROBE`: the contract admits them as evidence and PX4 SIH does not
publish them. That is a contract defect on any trial, flying or not.

**The contract has NOT been edited.** The probe's rule is that it produces the
evidence for changing a row, never the change; `producer_px4` for `imu1.*`
says `SCALED_IMU2` and for `battery.current` says
`BATTERY_STATUS.current_battery`, and correcting those is a decision with an
owner. Recorded here for that decision.

### 2.2 CONSTANCY observations — NOT verdicts

The airframe did not move, so **nothing in this table is a channel verdict**.
Numbers are from the current run (`research/v1_1/results/qualification_px4.json`);
channels that never arrived are in 2.1 and are not repeated here.

| channel | observation |
|---|---|
| imu0.accel | range 1.52 m/s^2, sd 0.200, n=18917 |
| imu0.gyro | range 0.100 rad/s, sd 0.0145, n=18917 |
| mag.field_ut | range 15.6 uT, sd 2.51, n=18907 |
| baro.altitude | range 0.438 m, sd 0.0847, n=18886 |
| gnss.position | range 0.234 m, sd 0.0476, n=18887 |
| gnss.velocity | range 0.195 m/s, sd 0.0329, n=18887 |
| vibration.rms | range 0.0131 m/s^2, sd 0.00221, n=18916 |
| estimator.variances | range 0.179, sd 0.0300, n=18868 — `ESTIMATOR_STATUS` ratios |
| estimator.flight_mode | latched, decoded via main/sub mode, n=18511 |
| vehicle_status.armed | latched armed=1, n=18511 |
| baro.temp_c | constant at 11.82 over 18886 samples — already declared non-informative |
| **battery.voltage** | **constant at 15.3 V over 18920 samples.** The contract marks this channel ADMISSIBLE. This is the W-5 pattern on a second platform and it is **UNCONFIRMED**: constancy on a static airframe describes the trial, not the channel. It becomes a finding only when SIH climbs. |

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
| **make SIH climb** | engineering | arming is solved; `MAV_CMD_NAV_TAKEOFF` yields 0.43 m. Next: check whether SIH needs `MIS_TAKEOFF_ALT`, an offboard setpoint stream, or a mission item rather than a bare takeoff command |
| decide the SIH-vs-Gazebo question | engineering | SIH gives dynamics with no dependencies but publishes fewer messages; Gazebo publishes more but adds a heavy dependency |
| per-platform contract rows | engineering | the ESC rows are ArduPilot-specific and must not be read as PX4 verdicts |
| re-run `make sim-px4` to PASS | engineering | until it does, no PX4 **constancy** result may be quoted. Presence results (2.1) are already valid. |

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
