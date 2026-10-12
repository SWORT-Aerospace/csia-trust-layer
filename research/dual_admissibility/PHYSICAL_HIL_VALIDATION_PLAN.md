# Physical / HIL validation plan

**No physical experiment was run.** No hardware was connected, and nothing in
this work package should be read as a hardware result. Everything measured
here is SITL replay or closed-form derivation. This document specifies what
would have to be built to move any of it off the simulator, and it exists
because Reviewer H's objection — "this is simulator-only" — is conceded rather
than answered.

## Why the software result needs hardware at all

Two of the load-bearing facts are properties of a *simulator's* GNSS model, not
of a receiver:

* The duty cycle of `fix_type` under `SIM_GPS1_JAM`. The recording shows 29%
  of observations invalid, arranged in runs of 1–17 messages. A real receiver
  under a real impairment need not do anything like that, and the whole
  split-versus-detector result turns on **sustained** closure duration.
* Whether `h_acc` stays populated and meaningful while `fix_type < 3`. In the
  recording it does not — `h_acc = 0` accompanies every no-fix message — which
  is what makes the status field, not the accuracy field, the one that matters
  under sustained invalidity. A receiver that keeps reporting a degrading
  `h_acc` through loss of lock would change which arm wins.

Neither can be settled by more simulation.

## Architecture

```
  GNSS protocol source            physical flight controller        consumer
  ────────────────────            ─────────────────────────         ────────
  L1: deterministic emulator ──►  ArduPilot on real hardware  ──►  MAVLink ──►  CSIA
      (host, UBX over UART)       (e.g. a Pixhawk-class board)     (USB/TELEM)   research
                                                                                 runtime
  L2: real receiver in a          same                             same          same
      conducted/shielded path
  L3: real receiver, real         same                             same          same
      flight, passive shadow
```

The CSIA side is unchanged from what is committed: `ArduPilotAdapter` →
`OnlineTrustLayer` → `FailsafePolicy`, with `csia/deploy/shadow.py` in its
existing no-command mode. The research arms attach exactly as they do here, by
replacing `layer.diag`.

## LEVEL 1 — deterministic GNSS protocol emulator → physical flight controller

The only level that can produce a *programmed* validity schedule, which is what
the pattern experiment needs.

**Hardware.** A host machine driving the flight controller's GPS UART through a
USB-serial adapter at the port's configured baud (typically 230400 for
u-blox on ArduPilot). The flight controller runs unmodified ArduPilot with
`GPS_TYPE = 2` (u-blox) and the GPS port assigned normally.

**Protocol.** UBX binary, minimally `UBX-NAV-PVT` (class 0x01, id 0x07) at
5 Hz, which carries `fixType`, `numSV`, `hAcc`, `vAcc`, `sAcc` and the
position/velocity solution in one message — so a single message type can drive
every field the study reads. `UBX-NAV-SAT` may be added if per-satellite
metadata is wanted later. The emulator must implement the u-blox configuration
handshake ArduPilot performs at startup (`UBX-CFG-*` / `UBX-MON-VER`) or
ArduPilot will not accept the port; this is the main engineering cost of L1 and
it should be scoped explicitly rather than discovered.

**Message sequence.** Identical in structure to `TEMPORAL_PATTERN_DEFINITIONS`
from the invalidity-masking package, re-expressed in UBX:

| Pattern | `fixType` schedule after onset | purpose |
|---|---|---|
| `P0` | `3` throughout | null control |
| `P1-` | `0` for 0.2 s | below the 0.5 s timeout |
| `P1+` | `0` for 2.0 s | above it |
| `P2` | alternating `0`/`3` per message | high density, short runs |
| `P4` | `0` × 4 then `3` × 6, repeating | sustained bursts with gaps |
| `P5` | `0` from onset to end | sustained — the arm-separating case |
| `T` | **transmit nothing** | transport control |
| `G` | `3` with `hAcc` ramped 0.3 m → 250 m | degraded but valid |

Each pattern runs for at least 40 s post-onset, with onset at least 15 s after
the vehicle reports armed so the core is clear of its `tau > 3` warm-up and the
failsafe's `arm_time = 10.0`.

**Timestamps and synchronisation.** Three clocks exist and all three must be
recorded: the emulator's transmit time, the flight controller's `time_usec`,
and the consumer's receive time. The emulator stamps each UBX frame's intended
transmit time in its own log at the instant of `write()`; the consumer stamps
`_t_recv` exactly as `maer_capture.py` does. Cross-clock offset is estimated
once per run from a `UBX-NAV-PVT` burst at a known cadence and recorded, not
corrected — a correction would hide the very transport jitter L1 is meant to
characterise. **Do not assume the flight controller relays GNSS messages
promptly:** the previously measured PX4 finding that stream rates are a
property of the link, not of the source, applies here and must be measured per
link, per direction.

**Recorded artifacts, per run.** The emulator's transmit log (UBX frames with
transmit timestamps), the raw MAVLink capture at the consumer (gzip JSON, same
format as `research/maer/results/scored/raw/`), the flight controller's
onboard `.bin` log, the CSIA flight log, SHA-256 of each, and the firmware
version and git hash of both ArduPilot and this repository.

**Pass/fail criteria — stated before any run.**

| # | Criterion | Threshold |
|---|---|---|
| 1 | The programmed schedule reaches the consumer | ≥ 99% of intended `fixType` transitions observable in the MAVLink capture, at the intended times ± 1 message period |
| 2 | `S0` reproduces the masking result | on `P2`, `A` open on ≥ 95% of ticks whose most recent observation was invalid |
| 3 | `S1` reproduces the diagnostic loss | on `P5`, final `gps_fault` posterior within 0.01 of the prior 0.02 |
| 4 | The split effect survives on hardware | on `P5`, `S2a` final `gps_fault` ≥ 0.80, and its coupled control `S1Da` ≤ 0.05 |
| 5 | The transport control still separates | on `T`, `S2a` final `gps_fault` ≤ 0.05 while `A` is closed for ≥ 30 s |
| 6 | Clean control | on `P0`, no arm leads with `gps_fault` on any tick |

Criteria 4 and 5 together are the experiment. **If 4 fails, the split does not
survive contact with hardware and that is the result.** If 3 fails, the
motivating tradeoff is a simulator artifact and the whole line closes.

## LEVEL 2 — real receiver under conducted, shielded impairment

Replaces the emulator with a real GNSS receiver fed from a shielded source, so
that `fix_type`, `h_acc` and `numSV` are produced by real receiver firmware
rather than programmed. This is what answers the "does `h_acc` stay meaningful
through loss of lock" question that L1 cannot.

**Conducted only.** GNSS simulator or recorded-RF playback into the receiver's
antenna port through coaxial cable and a calibrated attenuator, inside a
shielded enclosure, with the antenna port terminated. Impairment is applied by
attenuation and by the simulator's own scenario, never by radiating.

Everything else — patterns, artifacts, criteria — as L1, except that the
schedule becomes *requested* rather than *programmed*, so criterion 1 changes
to "the realised `fixType` schedule is recorded and reported", and the pattern
table becomes a set of attenuation profiles whose realised duty cycles are
measured after the fact.

**Regulatory and safety.** No radiated GNSS jamming or spoofing. No transmission
into any uncontrolled environment. Conducted testing inside a shielded
enclosure only, with the enclosure's leakage verified before the first run.
This is a hard constraint, not a preference.

## LEVEL 3 — clean real flight, passive shadow

No impairment at all. A real aircraft, real GNSS, CSIA in the committed
shadow mode with no command authority, flying an ordinary profile.

The purpose is exclusively the **false-alarm** question, which is the one the
software clean control answers least convincingly: on the synthetic and
pre-onset controls no arm ever leads with `gps_fault`, but both controls are
short and one holds the GNSS payload constant. Real flight has real multipath,
real satellite geometry changes, real brief `fix_type` transitions on takeoff
and under structures.

**Criterion.** Over at least 10 flights: no arm leads with `gps_fault` on more
than 0.1% of armed ticks, and no arm raises `nav_degraded` on a flight where
`S0` does not. Any arm that fails this is disqualified regardless of its
fault-detection performance — a monitor that cries wolf on clean flights is
worse than no monitor.

## What would still be missing after all three

* **Non-GNSS generalisation.** `CROSS_SENSOR_CANDIDATE_AUDIT.csv` finds GNSS is
  the only 4/4 candidate in this stack. Levels 1–3 would say nothing about
  whether the split helps anywhere else.
* **A confirmatory design.** Everything in this work package is exploratory
  (item 39). L1 is where a frozen preregistration should first be applied —
  see `DUAL_ADMISSIBILITY_PREREGISTRATION_DRAFT.md` — because it is the only
  level with a programmable independent variable.
