# Physical / HIL validation plan

Item 28. Supersedes `research/dual_admissibility/PHYSICAL_HIL_VALIDATION_PLAN.md`,
which was written around a sustained-closure sweep. The target is now the
**matched-A mechanism pair**, because that is the experiment the confirmatory
design is built on.

**No hardware was connected. Nothing here has been run.** This is a build
specification.

## Why hardware is needed for this specific question

Two facts the simulator cannot settle, and both bear directly on the primary
endpoint:

* **Does a real receiver keep talking while it has no fix?** The whole
  `SENSOR_INVALID` mechanism assumes messages continue to arrive carrying
  `fix_type < 3`. A receiver that goes quiet instead would collapse
  `SENSOR_INVALID` into `TRANSPORT_UNAVAILABLE` at the wire, and T3 says no
  architecture could then separate them. ArduPilot's SITL GNSS model is not
  evidence about receiver firmware.
* **Does the transport actually starve the way the simulator does?** The
  earlier PX4 finding — that delivered stream rates are a property of the link
  rather than the source — means "no message" at the consumer may have several
  distinct causes on real hardware, only some of which are a link failure.

## Architecture

```
  L1  UBX emulator (host) ──UART──► ArduPilot on real FC ──MAVLink──► frozen runtime
  L2  real GNSS receiver, conducted/shielded impairment ──► same ──► same
  L3  real receiver, real flight, passive shadow ──────────► same ──► same
```

CSIA side unchanged from the committed stack: `ArduPilotAdapter` →
`OnlineTrustLayer` → `FailsafePolicy`, `csia/deploy/shadow.py` in its existing
no-command mode. The arms attach as they do in simulation, by replacing
`layer.diag`.

## LEVEL 1 — deterministic UBX emulator → physical flight controller

The only level with a programmable independent variable, and therefore the
only one a frozen preregistration can apply to.

**Hardware.** Host PC; USB-serial adapter (FTDI or CP210x) to the flight
controller's GPS UART; a Pixhawk-class board running unmodified ArduPilot;
USB or TELEM link from the board to the consumer host. Bench power, propellers
removed, airframe restrained. No radio transmission of any kind.

**Wiring.** Host TX → FC GPS RX, host RX → FC GPS TX, common ground. Serial
port configured `SERIALn_PROTOCOL = 5` (GPS), `SERIALn_BAUD = 230400`,
`GPS_TYPE = 2` (u-blox). The emulator must implement the `UBX-CFG-*` /
`UBX-MON-VER` configuration handshake ArduPilot performs at startup or the
port is never accepted — **this is the main engineering cost of L1 and it
should be scoped before anything else.**

**Protocol and rates.** `UBX-NAV-PVT` (class 0x01, id 0x07) at **5 Hz**,
carrying `fixType`, `numSV`, `hAcc`, `vAcc`, `sAcc` and the solution. One
message type drives every field the study reads. Consumer-side MAVLink rates
requested exactly as `research/maer/maer_capture.py` does, and **measured per
link and per direction rather than assumed.**

### The two mechanisms, on hardware

| | `C_SENSOR` | `C_TRANSPORT` |
|---|---|---|
| Emulator behaviour | keeps sending `UBX-NAV-PVT` at 5 Hz with `fixType = 0` | **stops sending entirely** |
| What the FC sees | a receiver reporting no fix | a dead GPS port |
| What the consumer sees | `GPS_RAW_INT` with `fix_type < 3`, or nothing — **to be measured** | no `GPS_RAW_INT` |

The row that matters is the last one. **ArduPilot may or may not forward
`GPS_RAW_INT` while `fixType = 0`.** If it does not, `C_SENSOR` is
indistinguishable from `C_TRANSPORT` at the consumer *on real hardware*, and
the entire GNSS line of work is invalidated for physical deployments regardless
of what the simulator shows. **Establishing this is the first L1 experiment and
it should be run before the rest of L1 is built.**

### Matched A on hardware

The scored interval rule from `MECHANISM_MATCHING_SPEC.md` transfers unchanged:

```
[ onset + tau + margin , end_of_condition - tau - margin ],  tau = 0.5 s, margin = 0.2 s
```

with the same admissibility gate: **equal `A_trace_sha256` between the paired
mechanisms over the scored interval, zero mismatched ticks.** Real timing
jitter makes this harder than in replay, so a larger margin may be needed —
if so it is preregistered from a pilot run before scoring, not adjusted after.

### Timestamps

Three clocks, all recorded, none corrected: emulator transmit time (stamped at
`write()`), the FC's `time_usec`, and the consumer's `_t_recv`. Cross-clock
offset estimated once per run from a known-cadence burst and **recorded, not
applied** — correcting it would hide the transport jitter L1 exists to
characterise.

### Artifacts per run

Emulator TX log (UBX frames + transmit timestamps); consumer MAVLink capture
(gzip JSON, `maer_capture.py` format); the FC's onboard `.bin`; the CSIA
flight log; SHA-256 of each; ArduPilot firmware version and git hash; this
repository's commit.

### Pass/fail, stated before any run

| # | Criterion | Threshold |
|---|---|---|
| 0 | **Precondition.** `GPS_RAW_INT` with `fix_type < 3` is observable at the consumer while the emulator sends `fixType = 0` | ≥ 95% of intended messages observed. **If this fails, stop: the mechanisms are not separable on hardware and the confirmatory question is moot.** |
| 1 | The programmed schedule reaches the consumer | ≥ 99% of intended `fixType` transitions, at the intended times ± 1 message period |
| 2 | Matched A | zero mismatched ticks in the scored interval, per pair |
| 3 | `C0` cannot discriminate | mechanism classification correct on ≤ 5% of scored ticks; `UNRESOLVED` on ≥ 95% |
| 4 | `C2` (status only) can | correct on ≥ 90% of scored ticks, both mechanisms |
| 5 | `C0_STRONG` cannot | correct on ≤ 60% of scored ticks. **If it exceeds this, the split was unnecessary and that is the result.** |
| 6 | Clean | zero mechanism classifications across all clean runs, every arm |

Criteria 4 and 5 together are the experiment. Criterion 0 gates everything.

## LEVEL 2 — real receiver, conducted and shielded

Replaces the emulator with a real GNSS receiver fed from a shielded source, so
`fixType`, `numSV` and `hAcc` come from receiver firmware. This is what
actually answers "does a real receiver keep talking while it has no fix".

**Conducted only.** GNSS simulator or recorded-RF playback into the antenna
port via coaxial cable and a calibrated attenuator, inside a shielded
enclosure, antenna port terminated, enclosure leakage verified before the
first run. Impairment applied by attenuation and by the simulator's scenario.

`C_TRANSPORT` is produced by interrupting the **serial link**, not the RF —
that keeps the two mechanisms mechanistically distinct rather than both
becoming signal loss.

Schedules become *requested* rather than programmed, so criterion 1 becomes
"the realised schedule is recorded and reported" and the matched-A gate does
the work of admitting pairs.

**No radiated GNSS interference at any point.**

## LEVEL 3 — clean real flight, passive shadow

No impairment. Real aircraft, real GNSS, CSIA in committed shadow mode with no
command authority.

Purpose is exclusively **false alarms**, which the software controls answer
least well: both clean fixtures are short and one holds the GNSS payload
constant. Real flight has multipath, changing geometry, and brief genuine
`fix_type` transitions on takeoff and near structures.

**Criterion.** Over ≥ 10 flights: zero mechanism classifications on any armed
tick, every arm. An arm that fires on a clean flight is disqualified whatever
its discrimination score — a monitor that cries wolf is worse than none.

## What remains missing after all three

* Non-GNSS generalisation. `BATTERY_SOURCE_AUDIT.md` explains why battery
  would test a different defect, and no other family has the ingredients.
* Whether any of it changes an *operational* outcome. The exploratory work
  found the failsafe recommendation identical across every arm, and none of
  L1–L3 is designed to change that.
