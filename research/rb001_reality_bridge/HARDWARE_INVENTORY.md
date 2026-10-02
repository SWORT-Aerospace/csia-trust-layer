# Hardware inventory and the environment this work ran in (RB-001 Part 7)

**2026-10-02.** The brief's rule: do not assume remembered hardware is
physically available.

## 1. What this session could physically reach

**This work ran in a cloud container.** It has:
- 4 vCPU (Intel Xeon), 15 GB RAM;
- no USB bus (`/sys/bus/usb` absent);
- no serial, I²C, SPI or GPIO device in `/dev`.

**No flight controller, ESC, motor or instrument can be attached to it.**
So:
- ladder rungs RB1-RB6 (sensor bench through flight) cannot be run from
  here by anyone;
- RB0 (offline real data) and SITL can be.

**Network** (the session's egress policy; see `RB0_REAL_LOGS.md`):

| reachable | refused (policy 403) |
|---|---|
| raw.githubusercontent.com, package registries | logs.px4.io (PX4 Flight Review), Zenodo, Figshare, Hugging Face, Kaggle, Google Drive, IEEE DataPort, the RflyMAD site |

## 2. What the repository records about owned hardware

**Read, not guessed:**
- `hardware/inventory/e2m_sensors.yaml` is **empty by design**. The
  owner's decision forbids inventing an inventory from memory or
  photographs.
- `hardware/validation_rig/E2_MINIMUM_BOM.csv` lists a **planned** Pixhawk
  6C (FMUv6C) and its accessories. All are unpriced and none is recorded as
  bought.
- The BOM's one owner-reported item is a Linux desktop ("the user's
  existing OptiPlex").
- `docs/CURRENT_PROGRAM_STATE.md` reads **HARDWARE: NOT CURRENT GATE**. Its
  single exception (E2M) is an unarmed I²C sensor bench, `AUTHORIZED_NOT_RUN`,
  that expressly excludes motors, propellers, ESCs and flight batteries.

**This brief changes one thing:** RB-001 asks for a hardware program. The
inventory below is therefore a **request to the owner**, not a record of
fact.

## 3. Inventory (states per the brief)

**What the states mean:**
- **AVAILABLE:** verified by a recorded physical event.
- **AVAILABLE_BUT_UNVERIFIED:** the owner has reported it, nothing has
  verified it.
- **NEEDS_PURCHASE:** not reported, and required for the minimum
  experiment (`MINIMUM_PHYSICAL_EXPERIMENT.md`).
- **NOT_REQUIRED:** not needed for the minimum experiment.

| item | state | needed for the minimum experiment (RB2) | note |
|---|---|---|---|
| flight controller, PX4-capable (FMUv6C class) | NEEDS_PURCHASE (planned in E2 BOM, not reported bought) | yes: RB3; for RB2 the ESC can be driven by the FC or a signal generator | a multi-IMU board also enables the lane-switch experiment (Part 23) |
| IMUs | come with the FC | RB3 | the planned board class declares 3-4 IMUs |
| ESC with telemetry (bidirectional DShot or serial: RPM, current, voltage, temperature) | NEEDS_PURCHASE | **yes** | E4 item in the BOM; one is enough |
| brushless motor | NEEDS_PURCHASE | **yes** | one |
| propeller | NEEDS_PURCHASE | yes for thrust; **runs start prop-off** | |
| bench power supply, current-limited | NEEDS_PURCHASE (BOM: optional for E2) | **yes**: the safest energy source for RB2 | no flight battery in RB2 |
| battery | NOT_REQUIRED for RB2 | no | a LiPo adds risk the first experiment does not need |
| current sensor (power module or shunt) | NEEDS_PURCHASE | yes: independent current ground truth | |
| voltage sensor | comes with the power module | yes | |
| RPM sensing in the ESC | comes with the ESC | yes: as EVIDENCE | |
| optical tachometer, or an IR reflective sensor with a logic analyzer | NEEDS_PURCHASE | **yes: independent rotor-speed GROUND TRUTH** (Part 10) | low cost |
| oscilloscope | not reported | no: a logic analyzer covers command and tachometer timing | |
| logic analyzer (8-channel, USB) | NEEDS_PURCHASE | yes: command pulses, tachometer pulses, one timebase | low cost |
| multimeter | not reported | yes, for safety checks | |
| load cell / thrust stand | NEEDS_PURCHASE (E4 BOM item) | **yes for Part 12 A** (independent thrust) | a single-axis load-cell stand is enough |
| 3D printer | not reported | no: a commercial stand or clamped plate | |
| mounting hardware, prop guard / enclosure | NEEDS_PURCHASE | **yes: safety** | |
| computer | AVAILABLE_BUT_UNVERIFIED (owner-reported Linux desktop) | yes: runs PX4 tools and CSIA offline | |
| PX4-compatible hardware for HIL | the FC above | RB4 | |

**Nothing has been ordered or recommended for purchase on the strength of
this table alone.** It becomes a purchase list only when the owner confirms
two things:
- which of these they already hold;
- that RB2 (`MINIMUM_PHYSICAL_EXPERIMENT.md`) is the experiment to run.

The low-cost items (tachometer sensor, logic analyzer, current shunt) are
the ones that make the evidence and the ground truth independent.

## 4. What the owner needs to provide

**1. Hardware they actually hold.** One line per item in
`hardware/inventory/`, with the repository's existing states:
- `OWNER_REPORTED_ON_HAND`;
- `VISUALLY_IDENTIFIED`;
- and, for a physical event, `MEASUREMENT_VERIFIED` with its run
  manifest.

**2. Authorization for RB2.** `CURRENT_PROGRAM_STATE.md` currently forbids
motors and ESCs. RB2 needs an owner authorization record like E2M's, scoped
to:
- a restrained single motor;
- prop-off first;
- a current-limited bench supply.

**3. Real flight logs, if they have any.** Their own vehicle's ULogs, or the
RflyMAD real-flight subset, placed under `/home/user/rb001_raw/`. That is
RB0 with real propulsion data, and needs no hardware at all.
