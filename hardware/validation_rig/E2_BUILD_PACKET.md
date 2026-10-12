# E2 build packet — real flight-controller hardware, real telemetry boundary

**Written:** 2026-09-06, at the E1 freeze.
**Audience:** whoever buys and wires the bench.
**Predecessor:** `research/physical_validation/E1_FREEZE_MANIFEST.yaml`.
**Once the bench is built:** `docs/FIELD_INTEGRATION_RUNBOOK.md` covers the
SOFTWARE side — connecting CSIA to the autopilot, the preflight that must pass
first, what to expect at each stage with numbers, which tool measures which
part, and six falsifiable hypotheses with their pass/fail criteria.

---

## 0. The objective, and its two hard edges

> **E2 OBJECTIVE: run the SAME frozen CSIA core against real
> flight-controller hardware over a real telemetry boundary.**

**That is the whole tier.** Two things it is deliberately **not**:

* **NOT a physical GNSS fault.** No antenna disconnection, no bus
  interruption, no injected sensor failure. That is **E3**, it needs the
  fault-injection interface board and the inline harness, and mixing it into
  E2 would mean a failed E2 trial could not be distinguished from a working
  fault injector.
* **NOT flight.** **Props are removed for every E2 trial**, without exception.
  The vehicle does not need to move for E2 to answer its question.

**What E2 answers:** does the frozen core, ingesting telemetry produced by real
sensors on real silicon across a real serial link, behave the way it behaves
against a simulator's model of them — same channel semantics, same relation
availability, same tick cadence, same latency envelope?

**What E2 cannot answer:** anything about the *mechanism*. The mechanism needs
a fault, and a working board produces nominal telemetry. **E2 raises the
evidence tier of the plumbing, not of the finding.** Anyone reading an E2
result as evidence about self-occlusion has read it wrong, and §9's
preregistration says so in advance.

---

## 1. Recommended board class, and why it holds constant across both stacks

**Board class: a Pixhawk-standard STM32H743 (or H753) flight controller.**

**Why this class and not a specific product:** the requirement is that **the
same physical board runs both ArduPilot and PX4**, so that an ArduPilot-vs-PX4
difference at E2 is a difference between the two stacks and not between two
pieces of hardware. That property belongs to the *Pixhawk FMU standard*, which
both projects target, and not to any one vendor's board.

| requirement | why E2 needs it |
|---|---|
| **runs both ArduPilot and PX4 from the same board** | the E1 campaigns are two platforms on one simulator. E2 must keep the platform the variable and the hardware the constant, or the comparison is confounded exactly the way FL-017 was |
| **STM32H743/H753** | the class both stacks build current firmware for, and the MCU family the repository's own BOM already selected (`docs/HARDWARE_BOM.md`) |
| **two IMUs** | `redundant_imu` is a relation in the frozen trust graph. **PX4 SIH publishes no `SCALED_IMU2` at all**, which is why PX4's E1 demonstration was narrower (1 of 4 GNSS-gated relations live, not 3 of 4). A dual-IMU board is what lets E2 test whether that narrowness was a property of the *simulator* or of the *platform* |
| **barometer on board** | `altitude_baro` is one of the four GNSS-gated relations, and it was `STARVED_BY_TRANSPORT` on the PX4 passive link at 0.993 Hz against 10 declared |
| **magnetometer** (on board or on the GPS module) | `heading_course` was `DARK_BY_GATE` in E1 on both platforms. E2 should record whether it is dark for the same reason on hardware |
| **a second serial port free for a passive link** | the E1 architecture gives CSIA a **read-only** link separate from the rig's command link. §4 wires that, and it is not optional: it is what makes `NO_COMMAND_PATH_REACHABLE` a physical fact and not a software promise |

**Concrete examples of the class** (illustrative, not an endorsement, and
**not priced** — see §12): Matek H743-SLIM or H743-WING, Holybro Pixhawk 6C,
Holybro Durandal, CubePilot Cube Orange. `docs/HARDWARE_BOM.md` already
selected the Matek H743 line for MCU/IMU representativeness to the target
stack; **that choice is compatible with this packet and there is no reason to
revisit it**, provided the specific board carries two IMUs and a free UART.

**Verify before purchase, because both facts have exceptions:** that the exact
board appears in *both* the ArduPilot firmware list and the PX4 airframe/board
list, and that its published spec names **two** IMUs. Some H743 boards in this
class ship a single IMU.

## 2. Minimum quantity, and what each unit buys

| item | qty | what it buys, specifically |
|---|---|---|
| Flight controller (§1 class) | **1** | the whole tier. One board is enough: E2 compares stacks on one board, not boards against each other |
| GPS + compass module | **1** | `gnss.position`, `gnss.velocity` and `mag.field_ut` from a real receiver. **Needed for E2 even though E2 injects no fault**, because the four GNSS-gated relations must be *live* before anyone can say what a fault would remove |
| Companion computer (SBC, USB/serial + Ethernet) | **1** | hosts `csia-shadow` beside the FC, as a deployment would. Without it every latency figure stays a desktop figure |
| MicroSD cards | **2** | firmware and logs, one spare. A corrupt card mid-campaign turns valid trials into re-runs and ledger entries |
| USB-to-serial adapter (3.3 V TTL) | **1** | the passive CSIA link of §4 |
| Regulated bench supply + wiring loom | **1** | so a trial is a trial and not a wiring variation |

**Nothing above is requested without a purpose in this table.** No thrust
stand, no motors, no ESCs, no airframe, no battery: none of those affect
whether the frozen core reads real telemetry correctly, and all of them belong
to E4/E5 in `PURCHASE_JUSTIFICATION.csv`.

## 3. Power requirements

* **Bench power only.** A regulated supply at the board's documented input
  voltage; a **flight battery is not required for E2 and should not be used**
  — it stores far more energy than a props-off bench test needs.
* The FC is powered from the bench supply through its normal power input; the
  companion computer from its own supply. **Do not** back-power the FC from
  the companion computer's USB while the bench supply is connected.
* **Current headroom:** the FC plus GPS draws little; the companion computer
  dominates. Size the supply from the SBC's published peak, not its idle.
* **Common ground** between the FC and the companion computer is required for
  the serial link in §4. This is the single most common cause of a link that
  enumerates and then produces garbage.

## 4. Exact wiring

Two links, and the separation between them is the point.

```
                    ┌──────────────────────────────┐
   bench supply ───▶│  FLIGHT CONTROLLER (H743)    │
                    │                              │
  GPS+compass ─────▶│ GPS/UART port                │
                    │                              │
                    │ USB  ────────────────────────┼──▶ RIG / GCS
                    │      (command link)          │    (arms, sets params,
                    │                              │     requests streams)
                    │                              │
                    │ TELEM2 (free UART)  ─────────┼──▶ USB-serial adapter
                    └──────────────────────────────┘         │
                                                             ▼
                                           ┌─────────────────────────┐
                                           │  COMPANION COMPUTER     │
                                           │  csia-shadow, READ ONLY │
                                           └─────────────────────────┘
```

**TELEM2 to the USB-serial adapter, four wires:**

| FC TELEM2 | adapter | note |
|---|---|---|
| TX | RX | **crossed.** TX-to-TX is the second most common bring-up failure |
| RX | TX | see §4.1 — this wire is deliberately **left disconnected** |
| GND | GND | **required.** Common ground, per §3 |
| 5 V | — | **do not connect.** Each board has its own supply |

### 4.1 The receive wire is cut on purpose

**Leave the FC's TELEM2 RX pin unconnected.** CSIA's no-command property is
enforced in software by half-closing the socket's write side, and every run
records a live probe of the denial. **At E2 the same property becomes
physical**: with no wire from the companion computer into the FC's receiver,
no software defect on the companion computer can transmit, whatever it
intends.

This costs nothing and is the single strongest safety property available at
this tier. **It also means the CSIA link is passive**, exactly as the E1
campaigns ran it — so the E1 starvation observations (§1's table) transfer as
a question rather than being designed away.

### 4.2 Props

**There are no props at E2.** No motors, no ESCs, nothing that can spin. This
is not a precaution to be relaxed if the bench looks safe: it is a declared
property of every shipped profile, and E2 does not need motion.

## 5. Software to flash, and in what order

Both stacks, one board, **one at a time**, with a full verification pass
between them:

1. **ArduPilot ArduCopter**, current stable for the board.
2. Complete §6 verification and §7 telemetry capture. Record the firmware
   version string the board reports **from the board**, not from the download
   page.
3. **PX4**, current stable for the board.
4. Repeat §6 and §7 in full.

**Pin both.** Record for each: firmware version string as reported over
MAVLink, the git hash if the build reports one, and the exact download or
build provenance. **This is FL-017's lesson made procedural**: the E1 original
trials recorded `autopilot_version: "ardupilot"` — a platform name, not a
build — and that field is now permanently unrecoverable for those trials.

**On the companion computer:** the repository at the E1 freeze commit, the
frozen core untouched, `csia-shadow` in `SHADOW` mode. **The core is not
rebuilt, retuned or reconfigured for hardware.** If it needs changing to run
on hardware, that is itself the E2 finding and it goes in the failure ledger
before any workaround.

## 6. Board verification, before any trial

Each of these produces a number or a string that goes in the trial record.
**A board that fails any of them is not ready, and proceeding anyway produces
trials nobody can interpret.**

| # | check | pass condition |
|---|---|---|
| V1 | board enumerates over USB and reports a firmware version | a version string is captured, not assumed |
| V2 | **both IMUs present and reporting** | `SCALED_IMU` **and** `SCALED_IMU2` (or the PX4 equivalent) arrive. If `imu1` is absent on hardware, that is a **finding** and §9 records it rather than working around it |
| V3 | barometer reporting, and at what rate | measured Hz, against the rate the adapter declares |
| V4 | magnetometer reporting | present or absent, recorded either way |
| V5 | GPS reports a 3D fix | **needs sky view or a window.** A board that never gets a fix cannot make the GNSS-gated relations live, and every E2 trial would be starved for a reason unrelated to CSIA |
| V6 | the passive TELEM2 link carries traffic | messages per second on the companion computer |
| V7 | **command authority denied** | `csia-shadow` reports `NO_COMMAND_PATH_REACHABLE`, and the live transmit probe shows `command_long_send: denied` etc. Now backed by §4.1's cut wire |
| V8 | tick cadence | CSIA ticks at the configured 25 Hz on the companion computer, sustained |
| V9 | **`csia-edge validate --profile <new hardware profile>`** | run *before* the campaign. It reports which diagnostic relations this airframe can feed and which are structurally out. On a single-IMU board that answer already includes 7 of 11 relations out |

## 7. Expected telemetry, and what would be a surprise

From the E1 campaigns, on the same passive-link architecture:

| quantity | ArduPilot SITL (E1) | PX4 SIH (E1) | what E2 should record |
|---|---|---|---|
| ticks in a 30 s run at 25 Hz | 751 | 751 | the same, or the cadence is wrong |
| messages in the same run | ~12 900 | ~13 000 | measured; a large shortfall is transport starvation |
| live discriminating relations, pre-fault | 6 | 2 | **the number to watch.** PX4's 2 was a passive-link property in simulation; hardware is where that is tested |
| `gps_gate_weight_sum`, nominal | 3.0 | 1.0 | if PX4 hardware reads 3.0, the E1 narrowness was the simulator |
| `gnss.position` usable share | ~1.00 | ~1.00 | needs V5's fix |
| `baro.altitude` usable share | ~1.00 | **~0.50** | PX4's starvation is a specific, testable prediction |
| `battery.voltage`, `vibration.rms` usable share | — | ~0.24 | on a bench supply with no motors, expect these to differ from both |
| failsafe level, no fault | NORMAL | NORMAL | **anything else at E2 is a finding**, because nothing is wrong with the vehicle |

**The single most informative E2 result would be a disagreement in the
`live discriminating relations` row.** It would say that E1's PX4
qualification — the one thing this programme repeatedly declined to design
away — was an artifact of the simulator rather than of the link.

## 8. Logs required, per trial

Nothing here is optional; a trial missing any of it is `INCOMPLETE_ARTIFACT`
in the twelve-cause invalid-trial matrix.

* the **CSIA flight log** (`logs/shadow-*/`), full per-tick record;
* the **FC's own onboard log** (`.BIN` / `.ulg`) from the SD card, for the
  same window — the independent record of what the board thought;
* the **trial manifest**, content-hashed, written once;
* the **firmware version string as reported by the board** (§5);
* the **companion computer's** OS, CPU, and repository commit;
* **wall-clock start and end**, and anything else sharing the host;
* the **§6 verification results** for that session, V1 through V9;
* **photographs of the wiring**, once per bench build, so a later
  wiring-variation hypothesis can be checked rather than argued.

## 9. E2 preregistration plan

**Frozen before the first trial, exactly as A2, P1 and their predecessors
were.** The document does not exist yet — it cannot honestly be written until
§6 has been run once on a real board and the achievable rates are known — but
its required contents are fixed now, so that nothing is chosen after seeing
data:

1. **Hypothesis.** The frozen core, ingesting telemetry from real sensors over
   a real serial link, produces the same channel semantics, relation
   availability and tick cadence as against the simulator, within stated
   bounds. **Not a hypothesis about the mechanism.**
2. **Pinned environment**, and this list is longer than E1's by exactly the
   field E1 got wrong: board and revision; firmware version string **as
   reported by the board**; GPS module; the companion computer; CSIA commit;
   frozen core tag; tick rate; **the runtime stale-timeout source** — FL-017 —
   and the link topology of §4.
3. **Arms.** ArduPilot and PX4 on the **same board**, and a **null control**:
   a run in which CSIA is connected and the FC is idle. RULE A applies — a
   control that moves invalidates every arm.
4. **N and stopping rule**, with `planned = valid + invalid + not_attempted`
   balancing or the report raises.
5. **Captured quantities**, named in advance, matching §7's table.
6. **Success is not "it matches".** A hardware/simulator disagreement is a
   **result**, and the preregistration says so before any trial, exactly as
   A2's §6 said success is not "trust must rise".
7. **Validity vocabulary**: the eight states and the twelve-cause matrix,
   unchanged.
8. **What E2 cannot establish**, restated: nothing about a fault, nothing
   about flight, nothing about prevalence.

## 10. Abort conditions

**Stop the session and record it. Do not work around any of these.**

| condition | why it aborts |
|---|---|
| any §6 check fails | trials from an unverified board cannot be interpreted |
| **the FC receives anything from the companion computer** | §4.1's guarantee is broken. Stop, find the wire, start over |
| GPS cannot hold a 3D fix | every GNSS-gated relation is starved for an unrelated reason |
| the board browns out, resets, or the log shows a reboot mid-trial | that trial is `HARDWARE_FAULT`; a second occurrence aborts the session |
| the serial link drops or resyncs mid-trial | `INSTRUMENT_DEAD` for that trial |
| the frozen core would need editing to run | **the strongest abort on this list.** It is the E2 finding. Ledger first, workaround never |
| anything gets warm enough to be uncomfortable to touch | bench safety, before diagnosis |
| a prop, motor or ESC is present on the bench | §4.2. E2 does not need them and they are the only stored-energy hazard here |

## 11. What E2 will and will not license

**Will:** that the frozen core reads real hardware telemetry over a real
boundary and behaves as measured; the latency distribution on
deployment-class hardware; which relations are live on a real board — the
question E1's PX4 qualification leaves open.

**Will not:** anything about the self-occlusion mechanism (needs a fault,
E3); anything about flight (E5); any rate, frequency or prevalence; any
statement about a board other than the one bought.

## 12. Deliberately unpriced

**No price appears in this packet.** Vendor sites are unreachable from the
environment that wrote it — the agent proxy answers **403 at CONNECT** — so
every figure would have been invented. `docs/HARDWARE_BOM.md` carries 2026
planning estimates that say on their face to verify at purchase, and
`PURCHASE_JUSTIFICATION.csv` carries, per line, what it buys and **what it
does not**.

---

## The one decision that is the user's

**Buy the §2 list, or do not start E2.** Every item in it has a named purpose
in this document, and nothing is requested that E2 does not use. The software
side is complete and waiting: the orchestrator, the eight-state validity
vocabulary, the twelve-cause matrix, content-hashed manifests, and a hardware
backend that **refuses to construct** rather than returning plausible values —
because a stub would produce E2 numbers out of nothing, indistinguishable from
measurements downstream.

**Do not begin E2 without the physical hardware.** There is no partial E2.
