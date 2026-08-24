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

ArduPilot, on the dedicated telemetry port:

```
SERIAL2_PROTOCOL = 2      # MAVLink2
SERIAL2_BAUD     = 921    # 921600
SR2_RAW_SENS     = 25     # RAW_IMU, SCALED_IMU2, SCALED_PRESSURE
SR2_EXTRA1       = 10     # ATTITUDE, VIBRATION
SR2_EXTRA2       = 10     # VFR_HUD
SR2_EXTRA3       = 5      # BATTERY_STATUS, EKF_STATUS_REPORT
SR2_POSITION     = 10     # GLOBAL_POSITION_INT
SR2_EXT_STAT     = 10     # GPS_RAW_INT, SYS_STATUS
```

**`SR2_RAW_SENS` is not optional.** ArduPilot publishes inertial instance 0 as
`RAW_IMU` on that stream. A live qualification run against ArduCopter 4.8
found `imu0` and the magnetometer missing entirely because only `SCALED_IMU2`
and `SCALED_IMU3` were arriving.

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
