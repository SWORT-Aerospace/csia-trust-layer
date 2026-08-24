# Aircraft integration — companion deployment and the gates before it

**First physical-aircraft version is OBSERVE + LOG + ADVISE only.** No flight
control authority by default, and none available by configuration.

---

## 1. Gates. Do not skip one.

SITL to autonomous flight is five steps, not one.

### Gate 1 — SITL

| requirement | status | evidence |
|---|---|---|
| valid interventions (six-stage chain) | machinery built | `csia/simulation/contract.py` |
| clean nominal runs, no prohibited transitions | v1 baseline: 0 false alarms sim and field | `campaigns/bench.json` |
| deterministic reproduction | replay path is seeded and byte-stable | `csia report` |
| no simulator-stub relation admitted as evidence | **enforced** | `CHANNEL_SEMANTICS.yaml` + `test_esc_stub_never_reaches_the_frozen_core` |

### Gate 2 — hardware bench

Real flight controller, real companion computer, real telemetry transport,
real sensors where practical. **No propulsion.** Purpose: prove the adapter
against hardware rather than a simulator.

The single most important bench task: **re-qualify every channel.** The
committed contract is qualified against *simulators*. Real ESC telemetry is
informative where SITL's is a constant; the row says so and
`SemanticContract.override()` exists for exactly this, and refuses an override
with no stated reason.

### Gate 3 — HIL / restrained integration

Verify under adversity, not under nominal: timing jitter, dropped packets,
autopilot reboot mid-stream, companion reconnect, CPU contention, sensor
startup transients, stale data, corrupted packets. The adapter's `STALE`
handling and the runner's watchdog exist for this gate and have not yet met
real hardware.

### Gate 4 — real aircraft, SHADOW

Zero authority. Collect evidence. See `SHADOW_MODE.md`.

### Gate 5 — advisory

Recommendations visible to an operator. Still no automatic authority.

**Any control-authority integration requires a separate safety work package
and explicit approval.** Nothing in this repository is a step toward it.

---

## 2. Companion computer deployment (mode A, first)

### 2.0 The vehicle must already be streaming. CSIA cannot ask.

**Read this before wiring anything.** It is the first thing that will go wrong
on a real aircraft, and it produces no error message.

A MAVLink autopilot does not stream telemetry unprompted. Someone has to ask —
`REQUEST_DATA_STREAM`, `MAV_CMD_SET_MESSAGE_INTERVAL`, or the flight
controller's own `SR*_` rate parameters.

**CSIA cannot be that someone.** Asking is transmitting, and in SHADOW mode
the transmit surface is denied by construction. `request_data_stream_send`
raises `CommandAuthorityError` like any other command. That is correct
behaviour, not a bug to work around: a monitor that can ask for streams is a
monitor that can send.

Discovered by running the stack against live SITL rather than a fake:

```
ticks: 31   messages: 1
R13: INVALID_MEASUREMENT -- 1 message, 0 usable channels
```

One heartbeat, then silence. Every channel `NOT_RECEIVED`, no error anywhere,
a flight log full of well-formed empty ticks.

**What this means for installation, corrected against ArduPilot source.**

An earlier version of this section said to set `SR2_*` stream-rate parameters
on the companion's port and called it the preferred option. **That instruction
was wrong for ArduCopter 4.8 and would have failed silently.** Measured and
then confirmed in source:

| evidence | result |
|---|---|
| full parameter dump, ArduCopter 4.8 SITL | 1409 parameters; the only `SR*` group is `SRTL_*` (SmartRTL) |
| `SR1_RAW_SENS`, `SR1_EXTRA1` readback | `None` — the names do not resolve |
| `SERIAL1_PROTOCOL` readback, same loop | `2.0` — so the loop works and the link is MAVLink2 |
| `ArduCopter/Parameters.cpp:591` | `GOBJECT(_gcs, "MAV", GCS)` — the group is `MAV`, not `SR` |
| `libraries/GCS_MAVLink/GCS.cpp:43-75` | that group holds only `MAV_SYSID`, `MAV_GCS_SYSID`, `MAV_OPTIONS`, `MAV_TELEM_DELAY`. **No stream rates.** |
| `libraries/GCS_MAVLink/GCS.h:537` | `virtual bool persist_streamrates() const { return false; }` — overridden `true` only by ArduPlane |

**On ArduCopter 4.8 there is no parameter-based way to make a link stream.**
Stream rates are per-link runtime state, not persisted configuration, and they
are established only by a transmit on that link — `REQUEST_DATA_STREAM` or
`MAV_CMD_SET_MESSAGE_INTERVAL`.

A parameter write to a name that does not exist returns no error. That is why
this took four SITL runs to notice: the harness printed "rig set SR1_* stream
rates" while writing eight parameters into the void.

So a strictly-passive monitor on its OWN dedicated link receives only the
unsolicited messages. Measured on `tcp:5762` over 10 s with the vehicle
flying:

```
HEARTBEAT 11, SYS_STATUS 1, GPS_GLOBAL_ORIGIN 1, HOME_POSITION 1, TIMESYNC 1
```

No IMU, no GNSS, no barometer, no battery. Zero usable channels.

**The remaining options, honestly ranked:**

| option | passivity | cost |
|---|---|---|
| **CSIA listens to a stream someone else drives** — a telemetry tee, a MAVProxy `--out` forward, or a shared bus the GCS is already polling | **strict** — CSIA never transmits | needs the GCS/link to stay connected; CSIA's evidence depends on another party |
| a one-time configurator with transmit authority runs on CSIA's link at boot, then exits | broken once | rates do NOT persist (`persist_streamrates()==false`), so it must run every boot, and it puts a transmit path on the vehicle that needs its own safety case |
| ArduPlane | n/a | it overrides `persist_streamrates()` to `true`; this constraint is Copter-specific |

**The first is the only one that preserves strict passivity**, and it is what
a shadow installation should use: CSIA on a tee of an already-driven link, not
on a private link it cannot bring to life.

**This is unresolved for the deployment plan and is a Gate 2 blocker**, not a
detail. It also means R13 has not been measured through the v1.1 stack: four
SITL attempts were all correctly refused by the harness positive control as
`INVALID_MEASUREMENT`, because zero channels reached the core.

### 2.1 Hardware

| item | minimum | notes |
|---|---|---|
| companion computer | quad-core ARM64 or x86-64, 2 GB RAM | Pi 4/5, Jetson Nano, or equivalent |
| storage | 32 GB, industrial-grade SD or eMMC | logs rotate at 64 MB, 20 parts kept |
| link to autopilot | dedicated UART (`TELEM2`) or USB-serial | **do not share the ground-station port** |
| power | supplied independently of flight-critical rails | a companion brownout must not disturb the FC |
| clock | monotonic source; no NTP step during flight | `t_mono` never goes backwards |

Measured CPU headroom: v1 runs 297-356 µs/tick on desktop Python against a
2 ms budget. **That is a desktop number.** Companion-class ARM is expected to
be several times slower and has not been measured. Measure it at Gate 2 before
relying on the margin.

### 2.2 Autopilot side

**Port protocol — this part is parameters and does work:**

```
SERIAL2_PROTOCOL = 2      # MAVLink2
SERIAL2_BAUD     = 921    # 921600
```

**Stream rates are NOT parameters on ArduCopter 4.8.** An earlier version of
this section listed `SR2_RAW_SENS`, `SR2_EXTRA1`, `SR2_EXTRA2`, `SR2_EXTRA3`,
`SR2_POSITION` and `SR2_EXT_STAT`. **Those parameters do not exist** — see 2.0
for the source evidence. Pasting that block sets nothing, reports no error,
and yields a shadow flight with no sensor data.

Rates are established at runtime, per link, by a transmit on that link:

```
MAV_CMD_SET_MESSAGE_INTERVAL   per message id, interval in microseconds
REQUEST_DATA_STREAM            older, per stream group  (deprecated upstream)
```

and they do **not** persist across a reboot on Copter
(`GCS.h:537`, `persist_streamrates() == false`; ArduPlane overrides it to
`true`).

So whoever drives the link must re-establish rates every boot, and it cannot
be CSIA. Use the telemetry-tee arrangement in 2.0.

**What the contract needs on that link**, from
`docs/simulation/CHANNEL_SEMANTICS.yaml`:

| message | rate | feeds |
|---|---|---|
| `RAW_IMU` | 25 Hz | **`imu0` and the magnetometer** |
| `SCALED_IMU2` | 25 Hz | `imu1` |
| `SCALED_PRESSURE` | 10 Hz | `baro` |
| `GPS_RAW_INT` | 5 Hz | `gnss` — raw receiver, deliberately not the fused solution |
| `BATTERY_STATUS` | 10 Hz | `battery` |
| `VIBRATION` | 10 Hz | `vibration` |
| `HEARTBEAT` | 1 Hz | armed state |
| `EKF_STATUS_REPORT` | 5 Hz | autopilot comparison only, never diagnosis |

**`RAW_IMU` is not optional.** ArduPilot publishes inertial instance 0 there.
A live qualification run against ArduCopter 4.8 found `imu0` and the
magnetometer missing entirely because only `SCALED_IMU2` and `SCALED_IMU3`
were arriving — the primary IMU simply was not on the link.

**Verify, do not assume:** `csia-shadow --self-test` reports which channels
actually arrive. Zero usable channels means the link is not being driven.

### 2.3 Process

```ini
# /etc/systemd/system/csia-shadow.service
[Unit]
Description=CSIA Trust Layer (SHADOW)
After=network.target

[Service]
Type=simple
Environment=CSIA_MODE=SHADOW
ExecStart=/opt/csia/.venv/bin/csia-shadow \
  --config /etc/csia/vehicle.yaml --log-dir /var/log/csia
Restart=always
RestartSec=5
WatchdogSec=30
Nice=5
MemoryMax=512M
# CSIA must never be able to starve the flight-critical path, and must
# never be the reason a companion computer stays up.
[Install]
WantedBy=multi-user.target
```

`Restart=always` is safe precisely because CSIA has no authority: restarting
it cannot disturb the aircraft. `MemoryMax` is a hard bound; the adapter keeps
exactly one value per channel, so steady-state memory is flat.

### 2.4 Configuration

`configs/vehicle/*.yaml` — one file per airframe. Its SHA-256 goes into every
flight-log header, so a log can be tied to the configuration that produced it.

---

## 3. Embedded STM32/H7 (mode B, later)

**Not claimed, not scheduled, not measured.**

The native C core (`csia/native/`) is parity-pinned to Python at 1e-12 on the
production graph and benchmarks at 247 ns + 427 ns per tick **on a desktop
host**. The 7-15 µs STM32H743 figure that appears in older documents is an
estimate. The C core is on no execution path; the Python runtime is what runs.

Nothing may claim STM32 execution until it is measured on target hardware.

---

## 4. Pre-flight checklist for the first shadow flight

1. `make qualification` passes on the exact autopilot firmware to be flown.
2. Channel qualification re-run on the real vehicle at Gate 2, with any
   override recorded and reasoned.
3. `assert_no_command_capability` in the flight-log header reads
   `NO_COMMAND_PATH_REACHABLE`.
4. Companion power is independent of flight-critical rails.
5. Telemetry port is dedicated, not shared with a ground station.
6. Log storage has room for the planned duration at 64 MB per part.
7. Vehicle config hash recorded and matches the airframe.
8. Someone who is not the person who set it up has read the header.
