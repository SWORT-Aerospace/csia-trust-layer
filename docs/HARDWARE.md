# CSIA Trust Layer — Hardware Deployment Guide

Deployment reference for running the CSIA runtime (`csia run --source mavlink`)
against real hardware, from the SOW001 baseline to higher-capability builds.

> **Safety boundary, read first.** The runtime ships ADVISORY: it scores,
> diagnoses, and recommends. `MavlinkActuator(enable_commands=True)` — which
> lets it command LAND/RTL — must only be enabled after the full SITL and
> tethered validation sequence below. Nothing in this repository is
> DO-178C/DO-254 qualified; for operations that legally require certified
> software, this stack is a development/evaluation tool.

---

## Tier 1 — SOW001 baseline (validated reference target)

The sensor models and edge library in this package are written against this
exact bill of materials.

| Role | Part | Interface | CSIA node |
|---|---|---|---|
| Flight controller | STM32H743VIT6 (480 MHz M7) | — | (host of raw sensors) |
| IMU A | ICM-42688-P | SPI1, dedicated CS | `imu0` |
| IMU B | ICM-42688-P | SPI2 (separate bus — bus fault independence) | `imu1` |
| Barometer | MS5611 | SPI or I2C, OSR 4096 | `baro` |
| Magnetometer | RM3100 | SPI, mounted ≥ 8 cm from power leads | `mag` |
| GNSS | u-blox M9/M10 class | UART, 10 Hz nav rate | `gps` |
| ESC telemetry | BLHeli32/AM32, 4× | DShot telemetry wire | `motor_esc` |
| Pack monitor | FC ADC or smart battery | — | `battery` |
| Vibration | FC IMU high-rate channel or dedicated accel | — | `vibration` |
| Companion | Raspberry Pi 5 (4 GB+) | UART4/USB ↔ FC TELEM2, 921600 baud | runs `csia` |

### Companion computer setup (Pi 5, Raspberry Pi OS Bookworm 64-bit)

```sh
sudo apt update && sudo apt install -y python3.11-venv git
sudo mkdir -p /opt/csia && sudo chown $USER /opt/csia
cd /opt/csia
git clone <your-repo> . && python3 -m venv .venv
.venv/bin/pip install -e ".[mavlink]"
```

Route MAVLink so the GCS and CSIA both get the stream (mavlink-router):

```ini
# /etc/mavlink-router/main.conf
[UartEndpoint fc]
Device = /dev/ttyAMA4
Baud = 921600

[UdpEndpoint csia]
Mode = Normal
Address = 127.0.0.1
Port = 14551
```

### Required telemetry rates (set once from the GCS or a boot script)

The trust layer needs these minimums; request them with
`MAV_CMD_SET_MESSAGE_INTERVAL` (interval in µs):

| Message | Rate | Feeds |
|---|---|---|
| HIGHRES_IMU | 100 Hz | imu0 |
| SCALED_IMU2 | 100 Hz | imu1 |
| SCALED_PRESSURE | 50 Hz | baro |
| GLOBAL_POSITION_INT | 10 Hz | gps |
| ESC_STATUS | 50 Hz | motor_esc |
| BATTERY_STATUS | 10 Hz | battery |
| VIBRATION | 10 Hz | vibration |

If a rate cannot be met, raise that sensor's `STALE_TIMEOUT_S` — otherwise
the watchdog will (correctly) declare the sensor silent.

### Run it

```sh
/opt/csia/.venv/bin/csia run --source mavlink --conn udp:127.0.0.1:14551 \
    --profile sow001_quad --log /var/log/csia/state.jsonl
```

As a service:

```ini
# /etc/systemd/system/csia.service
[Unit]
Description=CSIA Trust Layer
After=mavlink-router.service

[Service]
ExecStart=/opt/csia/.venv/bin/csia run --source mavlink \
    --conn udp:127.0.0.1:14551 --profile sow001_quad \
    --log /var/log/csia/state.jsonl
Restart=on-failure
User=csia

[Install]
WantedBy=multi-user.target
```

### Commissioning sequence (do not skip steps)

1. **SITL first.** ArduPilot SITL (`sim_vehicle.py -v ArduCopter --out udp:127.0.0.1:14551`);
   confirm all seven sensors go fresh, trust converges > 0.9, no failsafe
   transitions in hover and gentle flight.
2. **σ calibration on the bench.** 60 s powered ground log + 60 s hover log;
   fit each comparator σ so the clean-flight normalized residuals average
   λ ≈ 1 (the repo σ's are the *simulation's* noise budgets — real sensors
   WILL differ; this step is mandatory, `csia report` shows the residual
   health). This is the one thing simulation cannot do for you.
3. **Fault rehearsal, props off.** Unplug the GPS antenna (dropout), wave a
   magnet near the RM3100 (EMI), verify detection + diagnosis + advisory
   actions in the state log.
4. **Tethered flight, advisory only.** Review `state.jsonl` after each
   flight; tune failsafe thresholds via a profile, not code edits.
5. Only then consider `MavlinkActuator(enable_commands=True)`, starting in
   SITL, then tethered.

---

## Tier 2 — hardened navigation build

Adds redundancy on the weakest single points found in Tier 1 practice
(GNSS integrity and heading).

- **RTK GNSS**: u-blox ZED-F9P (+ NTRIP corrections). cm-level position and
  a much tighter σ for the `phys_gps` matched detector → spoof/multipath
  detection sensitivity improves ~10×. New edge opportunity:
  RTK-fix-state ↔ position-noise consistency.
- **Third IMU** (different silicon, e.g. BMI088): converts the dual-IMU
  ambiguity ("which one drifted?") into 2-of-3 voting — extend the edge set
  with `redundant_imu_02`, `redundant_imu_12`; diagnosis then isolates a
  single unit with no motor-edge tiebreak needed.
- **Optical flow + rangefinder** (PMW3901 + TFmini/LW20): gives the
  Velocity edge a GPS-independent partner — the `heading_course` and
  velocity checks stop being gated by GPS health entirely.
- Companion unchanged (Pi 5 has ~250× margin at 25 Hz; even 100 Hz ticks
  with 3 IMUs stays under 5 % of one core).

## Tier 3 — full-capability build (visual heading, higher rates)

- **Compute**: NVIDIA Jetson Orin Nano / Orin NX companion.
- **Visual-inertial odometry** (stereo cam or VOXL2-class module): finally
  populates the paper's Mag-Heading ↔ **Visual-Heading** edge with a real
  sensor (this prototype substitutes GPS course; see trust_graph notes) and
  adds a full GPS-independent position reference.
- **Tick rate 50–100 Hz** with the same architecture; port the per-tick core
  to C++/Rust if you need < 100 µs deterministic ticks on the FC itself
  (the math in `TrustCore`/`DiagnosisCore` is ~200 lines and was written to
  be portable: fixed state, no allocation in steady state).
- **Beyond aircraft**: the runtime is platform-agnostic above the edge
  library. A ground rover, USV, or industrial sensor network deploys the
  same TrustCore/diagnosis/failsafe stack with its own edge module
  (wheel-odometry ↔ IMU, thruster-current ↔ acceleration, redundant
  process sensors ↔ physics model) and its own profile — see the extension
  contract in `csia/profiles.py`.

---

## Failure-mode coverage map (what the current edge set catches)

| Failure | Detected by | Typical response |
|---|---|---|
| GPS spoof / multipath walk | position-derivative ↔ Doppler | CAUTION: inertial hold, inhibit GPS modes |
| GPS silence / no fix | freshness watchdog + valid flag | CAUTION (data absence ≠ fault) |
| IMU bias drift (one unit) | dual-IMU + motor edges | CAUTION: select healthy IMU |
| IMU integrity loss (both) | all IMU edges | **EMERGENCY: stabilize + controlled descent** |
| Mag EMI / hard-iron event | field magnitude + heading edges | CAUTION: gyro heading hold |
| Power sag / pack fault | V–I physics + motor edges | CRITICAL: reduce power, land now |
| Prop/structural damage | vibration ↔ RPM envelope | CRITICAL: land soon |
| Any sensor going silent | staleness watchdog | per-class response above |
