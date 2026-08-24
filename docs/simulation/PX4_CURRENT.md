# PX4, as it actually is today

**Built and running: PX4-Autopilot @ `547e2ca`, `px4_sitl_default`, SIH.**

The vehicle arms, takes off and climbs, and the qualification probe is valid
for the first time. Section 2 has the verdict; section 2.0 records a finding
that was published backwards and has been corrected.

---

## 1. Getting PX4 SITL to run at all

Three things cost time and are worth writing down.

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

**`MAV_CMD_NAV_TAKEOFF` param7 is an AMSL altitude, not a height.** The rig
sent 25.0 while SIH sits at 489.4 m AMSL (`SIH_LOC_H0`), so the commanded
target was 464 m below ground; the navigator clamped it and the vehicle
correctly did nothing. `navigator/takeoff.cpp:193-210` is where that is
decided. Sending `NaN` makes the navigator use `MIS_TAKEOFF_ALT` relative to
the current position, and the airframe then climbs. Six rounds of hypotheses
were spent on this before the PX4 console was read; the console had been going
to `/dev/null`.

---

## 2. Qualification status: **FAIL** — and the probe is valid

```
positive control:  armed=True   climbed=2.69 m   (threshold: >= 1.0 m)
decoder:           csia_px4, 250 message types, vehicle definitions IN USE
                   0 undecodable frames
verdict:           FAIL -- a channel the contract admits as evidence
                   never arrived
```

`MOTION_CONTROL_SATISFIED: true`, `DECODER_COMPLETE: true`, `PROBE_VALID:
true`. Both validity conditions hold, so **every row below is a result**, not
an observation: presence claims and constancy claims alike.

The FAIL is a real contract defect and is described in 2.1. It is not a
simulator failure and not a probe failure.

### 2.0 CORRECTION: the previous "no ESC telemetry on PX4" finding was wrong

The earlier version of this file reported, as a property of PX4 SIH:

> **No ESC telemetry.** `ESC_STATUS` never arrives, so on PX4 the ESC
> channels are `UNAVAILABLE` rather than `STUB_OR_NONINFORMATIVE`.

**PX4 was sending `ESC_STATUS` the entire time**, at about 1 Hz. The frames
arrived, were well-formed, and were counted — as `UNKNOWN_291`, because the
pymavlink installed here carries a reduced `common.xml` (205 messages) with no
message 291. `MAVLink.decode()` returns a `MAVLink_unknown` for any id it does
not know, and the probe binned those with the traffic we deliberately ignore.

The instrument could not read the message and reported the **platform** as not
sending it. This is the same error as calling a channel a stub because the
aircraft never moved: a property of the apparatus written down as a property
of the thing measured. It survived review because "never arrived" and "I
cannot decode this" produce identical evidence at the layer that was looking —
an empty list either way.

Two changes, and the second matters more than the first:

1. **Decode with the vehicle's own definitions.** `csia/simulation/dialect.py`
   generates a dialect from `PX4-Autopilot/src/modules/mavlink/mavlink/
   message_definitions/v1.0` (and ArduPilot's from its own checkout) and
   activates it before the connection is built. PX4: 250 message types,
   **0 undecodable frames**. ArduPilot: 300, unchanged verdict (still `PASS`,
   same numbers).
2. **An undecodable producer can no longer become a claim.** Every surviving
   `UNKNOWN_<id>` is resolved against the vehicle's XML; if the id names a
   message the contract depends on, that channel is marked `UNDECODABLE`
   (never `UNAVAILABLE`), it is given neither agreement nor disagreement, and
   the run's verdict becomes `INSTRUMENT_DEAD`. Regression test:
   `tests/test_dialect_guard.py::test_the_published_px4_defect_is_now_caught`.

What the decoder had been hiding, on this platform alone: `ESC_STATUS` (291),
`ESC_INFO` (290), `EVENT` (410), `CURRENT_EVENT_SEQUENCE` (411),
`CURRENT_MODE` (436), `GNSS_INTEGRITY` (441),
`ESTIMATOR_SENSOR_FUSION_STATUS` (514), `LINK_NODE_STATUS` (8),
`TIME_ESTIMATE_TO_TARGET` (380).

### 2.1 PRESENCE findings — valid

| channel | contract declares | observed | admissible? |
|---|---|---|---|
| **`imu1.accel`** | INFORMATIVE | **never arrived** | **yes** |
| **`imu1.gyro`** | INFORMATIVE | **never arrived** | **yes** |
| **`battery.current`** | INFORMATIVE | **arrived 387× carrying the not-measured sentinel** | **yes** |
| `gnss.velocity_z` | UNAVAILABLE | never arrived | no |

The three bold rows are the FAIL: the contract admits them as diagnostic
evidence and PX4 SIH does not deliver them.

`battery.current` is a **different fact** from the other two and the previous
report gave both the same words. `BATTERY_STATUS` reaches us at ~9.7 Hz with
`current_battery = -1`, the documented "not measured" value. The stream is
implemented; the measurement is absent. That distinction decides whether the
fix is wiring a message or fitting a sensor, so the adapters now count
sentinel rejections **per channel** (`AircraftAdapter.sentinel_counts()`)
instead of keeping one global tally that could not say which channel it meant.

**The contract has NOT been edited.** The probe produces the evidence for
changing a row, never the change; `producer_px4` for `imu1.*` says
`SCALED_IMU2`, and correcting these rows is a decision with an owner.

### 2.2 CONSTANCY findings — now valid verdicts

The airframe climbed 2.69 m, so these are channel verdicts rather than
observations. From `research/v1_1/results/qualification_px4.json`.

| channel | observed | verdict |
|---|---|---|
| imu0.accel | range 3.74 m/s², sd 0.348, n=17153 | INFORMATIVE |
| imu0.gyro | range 1.213 rad/s, sd 0.230, n=17153 | INFORMATIVE |
| mag.field_ut | range 56.5 µT, sd 10.24, n=17153 | INFORMATIVE |
| baro.altitude | range 22.0 m, sd 6.54, n=17158 | INFORMATIVE |
| gnss.position | range 21.7 m, sd 6.53, n=17162 | INFORMATIVE |
| gnss.velocity | range 0.238 m/s, sd 0.042, n=17162 | INFORMATIVE |
| vibration.rms | range 0.0113 m/s², sd 0.0022, n=17139 | INFORMATIVE |
| estimator.variances | range 0.124, sd 0.0188, n=17138 | INFORMATIVE (blocked from use by policy) |
| estimator.flight_mode | latched, decoded, n=16728 | INFORMATIVE (DECODE criterion) |
| vehicle_status.armed | latched armed=1, n=16728 | INFORMATIVE (DECODE criterion) |
| baro.temp_c | range 0.14 °C, sd 0.043, n=17158 | varies, but declared non-informative and not used |
| **`battery.voltage`** | **range 0.689 V, sd 0.229, n=17144** | **INFORMATIVE — the W-5 suspicion is REFUTED** |
| **`esc.rpm`** | **range 5540 RPM, sd 1323, n=17167** | **INFORMATIVE — the contract declares it a stub** |
| `esc.current` | constant at 0 over 17167 samples | STUB_OR_NONINFORMATIVE, as declared |

Two of these change what CSIA can do on PX4.

**`battery.voltage` is not a stub.** It read a constant 15.3 V across 18,920
samples on the static airframe and was recorded as an UNCONFIRMED W-5-pattern
suspicion rather than a finding, precisely because constancy on a vehicle that
never moved describes the trial. Under load it varies by 0.689 V. Marking it
UNCONFIRMED was correct, and recording it as a finding would have been wrong.

**`esc.rpm` is real on PX4 and the contract is wrong about it.** 5,540 RPM of
range with sd 1,323 over 17,167 samples is a live signal, and the contract row
— written against ArduPilot SITL, where `SIM_Frame.cpp:901` derives rpm from
`vibe_motor` with `VIB_MOT_MAX` defaulting to 0 — declares it
`STUB_OR_NONINFORMATIVE`. On ArduPilot that row is correct and was
re-confirmed on the same day (constant at 0 over 116,911 samples). On PX4 it
is not. This is exactly the case the contract header calls out: qualification
is **per platform instance**, never global.

### 2.3 What this means for the `power_thrust` relation

| | ArduPilot SITL | PX4 SIH |
|---|---|---|
| `esc.current` | constant 3.2 A (placeholder) | constant 0 (stub) |
| `esc.rpm` | constant 0 | **varies, 5540 RPM range** |
| `battery.current` | varies, 5.4 A range | not measured (sentinel) |
| `battery.voltage` | varies, 0.053 V range | varies, 0.689 V range |

Neither backend supplies a full set. They fail in **opposite** places, which
is more useful than either alone: a relation that survives both has not been
validated against one simulator's quirks. Nothing here is a reason to admit a
stub — `esc.current` stays blocked on both platforms.

### 2.4 Three findings that still stand

1. **No second IMU.** PX4 SIH does not publish `SCALED_IMU2`, so `imu1` never
   arrives. **CSIA's dual-IMU cross-check relation cannot be evaluated on this
   backend at all** — and dual-IMU is one of the two families v1 handles best.
   A PX4 evaluation on SIH would silently omit it. Now confirmed under motion.
2. **Estimator health is ratios, not variances.** PX4 sends
   `ESTIMATOR_STATUS` with normalised innovation *ratios*; ArduPilot sends
   `EKF_STATUS_REPORT` with *variances*. They are not interchangeable. The
   adapter tags the value with `_source: ESTIMATOR_STATUS(ratios)` so a
   post-flight reader cannot compare one against the other by accident.
3. **PX4 has moved its diagnostics off `STATUSTEXT`.** "Preflight Fail: no
   heading reference" appears in the console log and never on `STATUSTEXT`,
   even with message 253 explicitly requested at 10 Hz. PX4 publishes
   `CURRENT_EVENT_SEQUENCE` (411) and the `EVENT` protocol (410) instead —
   both of which were arriving as undecodable frames. The rig's null control
   now has three outcomes rather than two: text seen / no text but events
   flowing / nothing at all. Only the third means the diagnostic channel is
   dead. This run: 0 STATUSTEXT, **15 event frames**, so the silence on 253
   carries no information about the vehicle. **Rendering `EVENT` payloads as text needs PX4's event metadata and
   is not implemented**; `px4_console.log` is the channel to read.

---

## 3. What remains before PX4 can be qualified

| item | owner | note |
|---|---|---|
| decide the `imu1` rows | contract owner | `producer_px4: SCALED_IMU2` is not what SIH publishes. Either the row becomes UNAVAILABLE for PX4 or the platform gains a second IMU |
| decide the `battery.current` row | contract owner | implemented stream, no sensor. UNAVAILABLE-with-reason, not FIELD_ABSENT |
| decide the `esc.rpm` row per platform | contract owner | INFORMATIVE on PX4, stub on ArduPilot. The contract has no per-platform qualification field today; adding one is a design decision |
| SIH vs Gazebo | engineering | SIH gives dynamics with no dependencies but one IMU; Gazebo publishes more but adds a heavy dependency |
| `Preflight Fail: no heading reference` | engineering | present in the console at boot; the vehicle arms and flies anyway under force-arm. Not diagnosed |
| re-run `make sim-px4` to PASS | engineering | it currently exits **1**, correctly. Until the contract rows are decided it should stay red |

---

## 4. Adapter status

The PX4 adapter is implemented and unit-tested against synthetic messages, and
verified against the live stream for the 14 channels that arrive. It is
deliberately not a copy of the ArduPilot adapter:

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
make sim-px4          # exits 1 today: the verdict is FAIL
```

Writes `research/v1_1/results/qualification_px4.json`, including the `decoder`
block (which dialect ran, how many message types, which frames it could not
read, which channels that blinded) and the positive-control evidence. The
generated dialect lands in `build/mavdialect/` and is regenerated whenever the
vehicle's XML is newer.

A reader asking "is this row a fact about PX4 or a fact about pymavlink?" must
be able to answer it from the result file alone. That question had no answer
in the previous format, which is how a decoder limitation was published as a
platform property.
