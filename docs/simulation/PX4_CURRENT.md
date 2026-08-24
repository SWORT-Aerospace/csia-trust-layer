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

## 2. Qualification status: **PASS**, with five declared platform narrowings

```
positive control:  armed=True   climbed=2.72 m   (threshold: >= 1.0 m)
decoder:           csia_px4, 250 message types, vehicle definitions IN USE
                   0 undecodable frames
heading:           HEADING_REFERENCE_VALID, source MAGNETOMETER,
                   aligned at 2.384 s -- 8.4 s BEFORE the vehicle armed;
                   yaw vs SIH ground truth mean |err| 0.237 deg,
                   max 1.076 deg over 13,872 samples
platform rows:     5 in force (section 2.5)
verdict:           PASS
```

Four validity flags, all true: `MOTION_CONTROL_SATISFIED`,
`DECODER_COMPLETE`, `HEADING_VERIFIED`, and their conjunction `PROBE_VALID`.
They are separate because there are four different ways a run can be invalid
and collapsing them loses which one happened.

**This PASS is reached by narrowing, and the narrowing is on the face of the
result.** Five contract rows are declared UNAVAILABLE or non-admissible *for
PX4 specifically*, each carrying the measurement that justifies it. Section
2.5 lists all five. A reader who disagrees with any of them can see exactly
what was excluded and on what evidence — which is the whole difference
between "the platform genuinely does not provide it" and "we stopped
checking".

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
| **`battery.current`** | INFORMATIVE | **arrived 390× carrying the not-measured sentinel** | **yes** |
| `gnss.velocity_z` | UNAVAILABLE | never arrived | no |

All three were the FAIL until 2026-08-24. They are now **declared platform
rows** (section 2.5): the contract records, per platform and with the
measurement attached, that PX4 SIH does not provide them. The channels are
still absent, still reported, and still excluded from evidence — what changed
is that PX4 no longer fails qualification for a property of the airframe.

`battery.current` is a **different fact** from the other two and the previous
report gave both the same words. `BATTERY_STATUS` reaches us at ~9.7 Hz with
`current_battery = -1`, the documented "not measured" value. The stream is
implemented; the measurement is absent. That distinction decides whether the
fix is wiring a message or fitting a sensor, so the adapters now count
sentinel rejections **per channel** (`AircraftAdapter.sentinel_counts()`)
instead of keeping one global tally that could not say which channel it meant.

### 2.4b The sample counts above were wrong by up to 445x

Every `n` in section 2.2 used to be a **message** count, not a sample count.
The probe reads the adapter's whole channel store after every message, so a
1 Hz channel was recorded once per arriving message of any type. `esc.rpm`
was reported with **n=17,346** when ESC_STATUS had arrived **39** times.

Two consequences, and the second is worse. The reported evidence base was
inflated by one to two orders of magnitude — and it was quoted in a committed
contract row. And `sd` was **dwell-weighted**: each value counted once per
message that happened to arrive while it was current, so a slow channel's
spread was weighted by how long each value sat in the store rather than by how
often it was measured.

Fixed by sampling only when the store's receive stamp changes. **No verdict
moved** — range is over the same set of values and the stub test is
`spread <= EPS` — and every count now matches its declared producer rate:
`imu0` 1,947 over 40 s (~49 Hz, HIGHRES_IMU at 50), `baro`/`battery` 390
(~10 Hz), `esc` 39 (~1 Hz), `HEARTBEAT`-derived channels 38 (~1 Hz).

That last figure is why `esc.rpm` stays refused on a second, independent
ground: 39 samples from one 2.7 m hop is a thin base for promoting a contract
row, quite apart from the missing source read.

### 2.4c Two declared publish rates were wrong, and freshness inherited it

With honest sample counts, the probe could finally compare the contract's
declared producer rate against the measured one. Two rows were wrong:

| channel | declared | measured | why |
|---|---|---|---|
| `esc.current` / `esc.rpm` | 10 Hz | **0.97 Hz** | the 10 was carried over from the ArduPilot row; PX4 publishes `ESC_STATUS` at ~1 Hz |
| `mag.field_ut` | 50 Hz | **13.9 Hz** | `HIGHRES_IMU` does arrive at ~49 Hz, but PX4's `fields_updated` bitmask marks the mag fields fresh only about every fourth message |

The magnetometer one is not an adapter bug — honouring `fields_updated` is
**correct**, because a field whose bit is clear is a repeat and not a
measurement. The row simply has to state the effective channel rate rather
than the message rate.

**This decided staleness.** `MaxAge` is documented as "the declared producer
rate with a 5x margin", but it was a hand-written table that could not express
a per-platform rate, so PX4 inherited ArduPilot's 0.50 s limit for a 1.03 s
publish period. Verified with a controlled clock: at age 0.60 s the PX4 ESC
channel returns `STALE`. On a real PX4 deployment those channels would have
read stale for about half of every publish period — invisible today only
because they are blocked for other reasons, and waiting to bite whoever
promotes the row.

Fixed at the root: `MaxAge` is now **derived from the contract per platform**
(`5 / declared_rate_hz`), so the rule is applied rather than restated. PX4 ESC
gets 5.0 s, ArduPilot ESC keeps 0.50 s, PX4 mag gets 0.357 s. The hand table
is only a fallback for channels with no declared rate.

The probe now measures the rate on every run and reports any channel where
declared and measured differ by more than 2x. It is gated on the **effective**
speedup, not the requested one — see 2.4d.

### 2.4d `--speedup` was accepted by the PX4 launcher and never used

`launch_px4(workdir, speedup)` took the argument and ignored it. PX4 SIH runs
lockstep at 1.0x whatever is asked; the console says so on every run invoked
with `--speedup 10`.

On its own that is a silently ignored flag. Downstream it was worse: the new
rate-drift check gates on "is this run real time?", read that from the
**requested** speedup, and therefore skipped itself on every default PX4 run —
a guard that guarded nothing, and it printed `rate drift NOT assessed:
speedup 10` on the very first run that used it.

`HONOURS_SPEEDUP` and `effective_speedup()` now say what each platform
actually does, the launcher prints a note when it cannot honour a request,
and the result file records requested and effective side by side.

### 2.5 The five platform rows, and the rule that keeps them honest

Qualification is per platform instance — `CHANNEL_SEMANTICS.yaml` has said so
since it was written, and these measurements forced the mechanism. A row may
now carry `platform_qualification: {px4: {...}}`, and the adapter for that
platform is built from the narrowed contract.

| channel | base | PX4 row | why |
|---|---|---|---|
| `imu1.accel` | INFORMATIVE | **UNAVAILABLE** | SIH models one IMU; `SCALED_IMU2` is never published |
| `imu1.gyro` | INFORMATIVE | **UNAVAILABLE** | same |
| `battery.current` | INFORMATIVE | **UNAVAILABLE** | `BATTERY_STATUS` arrives at ~9.7 Hz with the `-1` not-measured sentinel; no current sensor is modelled |
| `esc.current` | STUB (ArduPilot fake 0.8 A) | **STUB**, different reason | PX4 publishes 0, not a liveness placeholder. Same verdict, and the base row's `AP_ESC_Telem_SITL.cpp` citation does not apply here |
| `esc.rpm` | STUB (ArduPilot `VIB_MOT_MAX=0`) | **AVAILABLE_UNVALIDATED** | it varies over 5,447 RPM on PX4 — the base row is wrong here. Still **not admissible**: see below |

**A platform row can only narrow.** The effective admissibility is the AND of
the base row and the platform row, enforced in `ChannelContract`, and a row
that tries to make an inadmissible channel admissible raises. Without that
rule this mechanism would be the easiest imaginable way to re-admit a stub:
write a platform row and W-5 disappears. Every platform row must also carry a
`reason`, an `evidence` path that exists, and the `measured` numbers, and
`tests/test_platform_contract.py` holds all of it.

**`esc.rpm` is the case worth dwelling on.** It moves on PX4 — 5,447 RPM of
range, sd 1,317, n=17,346 — and it is still refused. INFORMATIVE requires
`VALIDATED_SEMANTICS` **and** demonstrated variation, and nobody has read the
PX4 source for this field's units, indexing or scaling. Variation alone is not
semantics. Admitting it because it moves would be W-5's mistake with the sign
reversed. The row records what promoting it would take: read
`src/modules/mavlink/streams/ESC_STATUS.hpp` and the `esc_status` uORB
definition. A source read, not another flight.

Every narrowing in force is printed on every run and written into
`platform_contract_rows` in the result file. A narrowing nobody sees is a
narrowing nobody reviews.

### 2.6 "Preflight Fail: no heading reference" — traced, and it is a transient

PX4 prints this on every boot. Taking it at face value would have been wrong;
so would ignoring it. If the simulation genuinely had no heading source, every
magnetometer, GNSS-course, attitude and cross-sensor result on this backend
would be contaminated and nothing in the report would show it.

`estimatorCheck.cpp:648-670` is the exact source. The condition is:

```cpp
!context.isArmed()
&& (hrt_absolute_time() - estimator_status_flags.timestamp < 5_s)
&& !estimator_status_flags.cs_yaw_align
&& lpos.xy_global
```

So the line says one thing: **at that instant the EKF had not declared yaw
alignment.** It does not say a heading source is missing, broken or disabled.
Separating "not yet" from "not at all" needs the time series, and PX4 writes
one. From the run's own ulog:

| question | answer | from |
|---|---|---|
| when did yaw align? | **2.384 s**, and it never regressed over the remaining 53.5 s | `estimator_status_flags.cs_yaw_align` |
| what aligned it? | **the magnetometer** — `cs_mag` and `cs_mag_heading_consistent` turn true at the *same* timestamp | same topic |
| any other source? | no: `cs_gnss_yaw`, `cs_ev_yaw`, `cs_yaw_manual` never true | same topic |
| was the mag healthy? | `cs_mag_fault` never, `cs_mag_field_disturbed` never | same topic |
| was it actually fused? | **99.87 %** of samples fused after alignment, **0.0 %** innovations rejected | `estimator_aid_src_mag` |
| was the heading *correct*? | **mean \|err\| 0.237°, max 1.076°** over 13,872 samples | `vehicle_attitude` vs `vehicle_attitude_groundtruth` |

The last row is the one that settles it. Alignment is a claim the estimator
makes about itself; an estimator can be confidently wrong. SIH publishes
ground-truth attitude, so the estimate can be checked against it, and the
heading is right to within a degree for the whole flight.

`cs_mag_hdg` → `cs_mag_3d` at 17.0 s, together with `cs_mag_aligned_in_flight`
at 16.96 s: the normal PX4 progression from heading-only fusion on the ground
to full 3-axis fusion after in-flight alignment. The airframe setup confirms
the sensor is enabled by design — `10040_sihsim_quadx` sets
`SENS_EN_MAGSIM 1`, and boot assigns `CAL_MAG0_ID`/`CAL_MAG1_ID` at priority
50.

**The observation window is entirely inside the aligned period, and that is
now measured rather than asserted.** `vehicle_status.arming_state` puts arming
at **10.816 s**, so yaw aligned **8.4 s before the vehicle armed** and nothing
in section 2.2 was measured without a heading reference. If alignment ever
happens *after* arming, the verdict is `HEADING_REFERENCE_LATE` and the
heading-dependent channels are voided — a verdict that was declared in the
module and, until it was wired to the arming time, could never actually be
issued.

This is now an automatic check, not a one-off investigation.
`csia/simulation/ulog_check.py` runs on every PX4 qualification, records the
whole trace in `estimator_provenance`, and sets `HEADING_VERIFIED`. If yaw
alignment never happens or is lost mid-run, `mag.field_ut`, `gnss.velocity`
and `estimator.variances` are marked `UNVERIFIED_HEADING` — not graded, not
reported as agreeing — and the verdict becomes `INSTRUMENT_DEAD`. A run that
could not check reports `UNVERIFIABLE` and says so loudly, because "we could
not check" and "it was fine" must never read the same.

### 2.2 CONSTANCY findings — now valid verdicts

The airframe climbed 2.72 m, so these are channel verdicts rather than
observations. From `research/v1_1/results/qualification_px4.json`.

| channel | observed | verdict |
|---|---|---|
| imu0.accel | range 3.84 m/s², sd 0.348, n=1947 | INFORMATIVE |
| imu0.gyro | range 1.199 rad/s, sd 0.227, n=1947 | INFORMATIVE |
| mag.field_ut | range 57.9 µT, sd 10.21, n=556 | INFORMATIVE (heading reference verified — 2.6) |
| baro.altitude | range 22.1 m, sd 6.53, n=390 | INFORMATIVE |
| gnss.position | range 21.8 m, sd 6.51, n=195 | INFORMATIVE |
| gnss.velocity | range 0.300 m/s, sd 0.048, n=195 | INFORMATIVE |
| vibration.rms | range 0.0118 m/s², sd 0.0023, n=390 | INFORMATIVE |
| estimator.variances | range 0.157, sd 0.0302, n=195 | INFORMATIVE (blocked from use by policy) |
| estimator.flight_mode | latched, decoded, n=38 | INFORMATIVE (DECODE criterion) |
| vehicle_status.armed | latched armed=1, n=38 | INFORMATIVE (DECODE criterion) |
| baro.temp_c | range 0.14 °C, sd 0.043, n=390 | varies, but declared non-informative and not used |
| **`battery.voltage`** | **range 0.689 V, sd 0.229, n=390** | **INFORMATIVE — the W-5 suspicion is REFUTED** |
| **`esc.rpm`** | **range 5545 RPM, sd 1320, n=39** | **INFORMATIVE — see 2.5; declared AVAILABLE_UNVALIDATED on PX4 and still refused** |
| `esc.current` | constant at 0 over 39 samples | STUB_OR_NONINFORMATIVE, as declared |

Two of these change what CSIA can do on PX4.

**`battery.voltage` is not a stub.** It read a constant 15.3 V across 18,920
samples on the static airframe and was recorded as an UNCONFIRMED W-5-pattern
suspicion rather than a finding, precisely because constancy on a vehicle that
never moved describes the trial. Under load it varies by 0.689 V. Marking it
UNCONFIRMED was correct, and recording it as a finding would have been wrong.

**`esc.rpm` is real on PX4 and the base contract is wrong about it.** 5,545
RPM of range with sd 1,320 over **39** samples is a live signal, and the contract row
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
| `esc.rpm` | constant 0 | **varies, 5545 RPM range** |
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
