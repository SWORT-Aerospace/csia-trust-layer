# HIL criterion 0 — plan, and what was answered without hardware

Items 16, 17.

## Hardware availability: NO

Checked, not assumed:

```
/dev/ttyUSB*  /dev/ttyACM*  /dev/serial*   -> none
pyserial comports                          -> ['/dev/ttyS0']
```

`/dev/ttyS0` is the container's legacy console device, not a connected flight
controller. **No physical hardware is attached to this environment, so
criterion 0 was NOT executed on hardware and nothing here may be described as
a HIL result.**

## What WAS answered, in SITL

The criterion-0 question is:

> When the GNSS input reports an invalid / no-fix condition, does the
> downstream `GPS_RAW_INT` stream continue to be emitted with `fix_type < 3`,
> or does the invalidity disappear before the interface CSIA observes?

In **ArduPilot SITL @ 01a504b** this is now measured rather than assumed.
`heldout_capture.py` sets `SIM_GPS1_ENABLE = 0` — the simulated receiver stops
producing — and records what reaches the consumer:

| Trial | `GPS_RAW_INT` during the condition | fix types |
|---|---|---|
| `PAIR_01_SENSOR_INVALID` | 301 | `{1: 300, 6: 1}` |
| `PAIR_02_SENSOR_INVALID` | 451 | `{1: 450, 6: 1}` |
| `PAIR_03_SENSOR_INVALID` | 601 | `{1: 600, 6: 1}` |
| `PAIR_0*_TRANSPORT_UNAVAILABLE` | 0, 1, 0 | `{}`, `{6: 1}`, `{}` |

**SITL verdict: PASS.** The autopilot keeps emitting `GPS_RAW_INT` at the
delivered rate with `fix_type = 1` (NO_FIX) throughout. Explicit source
invalidity *is* transported to the consumer interface. The single `fix_type=6`
in each run is the last valid fix in flight when the parameter took effect.

This is a **simulator** result. It makes the question worth asking on
hardware; it does not answer it.

## Physical procedure, for the user to execute

### Hardware

| Item | Requirement |
|---|---|
| Flight controller | Pixhawk-class board (STM32F4/F7/H7), a serial port assignable to GPS. Any board on which ArduPilot @ `01a504b` builds and runs. |
| Firmware | ArduCopter, **the same commit the repository is verified against: `01a504b`**. Record the exact build hash in the log. |
| GNSS source | A host PC or second MCU emitting UBX over UART. A real u-blox receiver may be substituted for LEVEL 2; for criterion 0 the emulator is preferable because the invalidity is programmable. |
| Link to consumer | USB or TELEM to the machine running the CSIA runtime. |
| Bench | Props removed, airframe restrained, bench power. No radio transmission. |

### Wiring

```
host TX  ──►  FC GPS RX
host RX  ◄──  FC GPS TX
GND      ───  GND      (common ground, single point)
FC USB / TELEM  ──►  consumer host
```

### Autopilot parameters

```
SERIALn_PROTOCOL = 5      (GPS)   n = the port used
SERIALn_BAUD     = 230400
GPS_TYPE         = 2      (u-blox)
GPS_AUTO_CONFIG  = 0      so the emulator is not reconfigured mid-test
```

### Protocol

`UBX-NAV-PVT` (class `0x01`, id `0x07`) at **5 Hz**. It carries `iTOW`,
`fixType`, `flags`, `numSV`, `hAcc`, `vAcc`, `sAcc` and the solution, so one
message type drives every field the study reads.

**The emulator must answer ArduPilot's start-up configuration handshake**
(`UBX-CFG-*`, `UBX-MON-VER`) or the driver never accepts the port. Scope this
first; it is the bulk of the work.

### Sequence

Onset only after the FC reports a 3D fix and the GPS driver is stable
(≥ 30 s of `fixType = 3`):

```
  VALID    10 s    fixType = 3, numSV = 12, hAcc = 300 mm
  VALID    10 s    (unchanged -- establishes the baseline)
  INVALID  10 s    fixType = 0, numSV = 0
  INVALID  10 s    (unchanged -- spans well past any timeout)
  VALID    10 s    fixType = 3 restored
```

Repeat three times. Record each repetition separately; do not average.

### Logging

| Stream | Where | What |
|---|---|---|
| Raw serial input | host emulator | every UBX frame with its `write()` timestamp |
| Autopilot GPS state | FC onboard `.bin` | `GPS` and `GPA` messages |
| Downstream interface | consumer host | full MAVLink capture, gzip JSON, `heldout_capture.py` format |

Three clocks — emulator TX, FC `time_usec`, consumer `_t_recv`. **Record all
three; correct none.** A correction would hide the transport jitter the test
exists to characterise.

### Pass / fail

**PASS** — during each INVALID window, the consumer observes `GPS_RAW_INT`
messages continuing at ≥ 90% of the pre-onset delivered rate, with
`fix_type < 3` on ≥ 95% of them.

**FAIL** — the consumer observes no `GPS_RAW_INT` during the INVALID window,
or the messages continue carrying `fix_type >= 3`. Either way the explicit
source invalidity has been destroyed before the interface CSIA observes, and
**`SENSOR_INVALID` is not distinguishable from `TRANSPORT_UNAVAILABLE` on real
hardware** — which would close the GNSS line for physical deployments
regardless of anything measured in simulation.

**AMBIGUOUS** — the delivered rate drops materially but does not stop. Record
it; do not adjudicate. It would mean the distinction survives but degraded,
and the matched-`A` design would need re-deriving against the realised rate.

### What criterion 0 does not establish

It says nothing about whether the split architecture is useful, whether the
operational recommendation changes, or whether any of it generalises past
GNSS. It establishes only that the input the whole question depends on exists
at the interface on real hardware.
