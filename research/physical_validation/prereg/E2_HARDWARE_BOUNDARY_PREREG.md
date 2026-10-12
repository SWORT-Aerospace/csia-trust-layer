# E2 — frozen core against a real flight controller (CAMPAIGN E2)

**TEMPLATE, NOT A COMMITTED PREREGISTRATION.**

Every field marked `[FILL: …]` is blank because it cannot honestly be written
before a board exists on the bench. Everything else is fixed **now**, before
any hardware is purchased, so that no design decision can be made after seeing
a measurement.

**This file becomes a preregistration when — and only when — the following are
all true:**

1. Hardware from `hardware/validation_rig/E2_MINIMUM_BOM.csv` is physically
   present.
2. `hardware/validation_rig/E2_BUILD_PACKET.md` §6 board verification has been
   run once and **passed**, so the achievable rates in §5 below are measured
   rather than guessed.
3. Every `[FILL: …]` is replaced with an observed value.
4. It is committed, and the commit hash recorded, **before the first trial**.

Until then, `E2_STATUS` is **NOT_RUN** and nothing in this file is evidence of
anything.

**Nothing in the frozen v1 core is modified.** If E2 cannot run without editing
it, that is the finding — see §11.

---

## 1. Scope, and the two hard edges

E2 asks exactly one question:

> Does the frozen CSIA core, ingesting telemetry from **real sensors on real
> flight-controller silicon** across a **real external serial boundary**,
> produce the same channel semantics, relation availability and tick cadence
> as it does against a simulator — within the bounds stated in §6?

**It is not a hypothesis about the mechanism.** No fault is injected. Nothing
here can speak to self-occlusion, to trust trajectories under fault, or to
FL-016.

**The two edges, restated from the build packet because they are the reason
this tier exists at all:**

- **REAL HARDWARE.** A flight controller running real autopilot firmware on its
  own MCU, reading its own sensors. Simulation-on-hardware is a *secondary*
  mode (§4), never the primary evidence.
- **REAL BOUNDARY.** CSIA reads a serial link with its **receive wire
  physically absent** (build packet §4.1). `NO_COMMAND_PATH_REACHABLE` becomes
  a property of the wiring, not a promise made by software.

## 2. Environment, pinned

This table is **longer than E1's by exactly the field E1 got wrong.** FL-017
was a "repeat" that varied a configuration nobody had pinned; the runtime
stale-timeout source is therefore pinned here explicitly.

| item | value |
|---|---|
| board model and revision | `[FILL: as silkscreened, including hardware revision]` |
| board serial / unique id | `[FILL: from the FC's own reported UID]` |
| board class (selected pre-purchase) | Pixhawk FMUv6C — see `hardware/validation_rig/E2_BOARD_SELECTION.md` |
| ArduPilot firmware version **as the board reports it** | `[FILL: AUTOPILOT_VERSION message, not the download page]` |
| ArduPilot git hash **as the board reports it** | `[FILL:]` |
| PX4 firmware version **as the board reports it** | `[FILL:]` |
| PX4 git hash **as the board reports it** | `[FILL:]` |
| GNSS module model and firmware | `[FILL:]` |
| companion computer | `[FILL: the OptiPlex — model, CPU, RAM]` |
| companion OS, **detected not assumed** | `[FILL: /etc/os-release PRETTY_NAME]` |
| companion kernel | `[FILL: uname -r]` |
| CSIA commit | `[FILL:]` |
| frozen core tag | `csia-v1.0-research-final` |
| tick rate | 25.0 Hz |
| **runtime stale-timeout source** | `[FILL: the exact call and its resolved values — FL-017]` |
| link topology | build packet §4, with TELEM2 RX **not connected** |
| serial baud | `[FILL:]` |
| requested stream rates | `[FILL: as set, and as achieved — they differ]` |

**Why "as the board reports it" appears four times:** both original Mechanism-A
logs recorded a platform *name* rather than a *build*
(`ARDUPILOT_REPEAT_RECONCILIATION.md` §4.6). That omission cost a reconciliation
pass. A version string typed from a download page is not an observation.

## 3. Arms

| arm | n | what it is |
|---|---|---|
| `AP_HW` | `[FILL:]` | ArduPilot on the board, CSIA reading TELEM2 |
| `PX4_HW` | `[FILL:]` | PX4 on the **same board**, CSIA reading TELEM2 |
| `NULL` | `[FILL:]` | CSIA connected, **FC idle and disarmed**, no operator interaction |

**One board, flashed sequentially** — `E2_BOARD_SELECTION.md` §2. Two boards
would add unit-to-unit sensor variation to an experiment designed to have one
variable.

**RULE A APPLIES WITHOUT EXCEPTION.** The `NULL` arm is a control. If it moves —
if channel semantics, relation availability or cadence differ across `NULL`
trials in a way the other arms are being asked to distinguish — **every arm is
invalidated**, and the session is recorded as invalid rather than reinterpreted.

**COMMAND ISSUED ≠ FAULT INJECTED**, and E2 injects neither. Any operator action
during a trial other than starting and stopping it makes that trial
`PROTOCOL_VIOLATION`.

## 4. Execution modes, and which one is evidence

| mode | status | note |
|---|---|---|
| **PRIMARY** — real sensors, board on the bench, GNSS with a fix | **the evidence** | |
| SECONDARY — PX4 SIH running on the board's own MCU | supporting only | separates "property of the simulator" from "property of the platform" |

**The secondary mode is not available on both stacks.** The board survey found
**no board** supporting simulation-on-hardware on ArduPilot *and* PX4
(`E2_BOARD_SURVEY.json`, `both_support_simulation_on_hardware` false for all 15
intersection rows). A symmetric design across the two stacks in this mode does
not exist and is not to be improvised.

## 5. N, stopping rule, and the arithmetic that must balance

- **Planned n per arm:** `[FILL: after §6 verification establishes trial duration]`
- **Trial duration:** `[FILL:]`
- **Stopping rule:** run the planned n. **Do not stop early because a result
  looks clean, and do not extend because it does not.**

    planned = valid + invalid + not_attempted

**The report raises if this does not balance.** The eight-state validity
vocabulary and the twelve invalid-trial causes are unchanged from A1/A2/P1 —
see `tools/csia_experiment/` — and are not re-derived here.

## 6. Captured quantities, named in advance

Matching build packet §7. Nothing is added to this list after the first trial.

| quantity | why |
|---|---|
| per-channel presence, rate and freshness | the core question |
| which trust-graph relations are LIVE | E1's PX4 qualification (1 of 4 GNSS-gated relations) leaves this open on real hardware |
| tick cadence and achieved rate vs requested | requested and achieved differ; both are recorded |
| CSIA tick latency distribution | **recorded, NOT adjudicated** — same discipline as E1 |
| the FC's own onboard log | the independent record against CSIA's |
| GNSS fix type and satellite count, per tick | a starved relation and a blind relation look alike |
| `NO_COMMAND_PATH_REACHABLE` evidence | per trial, from the wiring |
| board temperature if the FC reports it | bench safety and drift |

### 6.1 Declared equivalence bounds

**Fixed here, before any measurement.** `docs/SEMANTIC_PORTABILITY_CONTRACT.md`
already separates the four levels; E2 inherits them rather than inventing new
ones.

| level | requirement for E2 |
|---|---|
| 1 — decision | **EXACT.** No tolerance |
| 2 — structural support | **EXACT** |
| 3 — numerical | not asserted across hardware/simulator; a difference here is **reported, not failed** |
| 4 — timing | **bounds, not equivalence.** No timing claim transfers from the OptiPlex to any other compute |

## 7. Success is not "it matches"

**A hardware/simulator disagreement is a RESULT.** It is written down, kept, and
reported at whichever of the four levels it appears — exactly as A2's §6 said
success is not "trust must rise", and exactly as FL-016 was kept when a repeated
campaign took a claim away.

There is no outcome of E2 that counts as a failure of E2. There are outcomes
that count as failures of an *expectation*, and those are the useful ones.

## 8. Raw evidence before reduction

Raw traces are archived and hashed **before any extractor runs**, as
`research/physical_validation/results/a2_traces_raw/` and `p1_traces_raw/`
already are. `tools/evidence_guard.py` `protected_write` refuses to overwrite
committed evidence without `--regenerate` (FL-013), and that stands for E2.

## 9. Abort conditions

Build packet §10, unchanged and not restated here so the two cannot drift.

**The strongest one, repeated because it is the one that will be tempting:**
*if the frozen core would need editing to run against the hardware, that is the
E2 finding.* Ledger first. Workaround never.

## 10. Analysis, fixed in advance

1. Per-arm tables of every §6 quantity. **Arms are never pooled.**
2. Hardware vs simulator compared at each of the four contract levels
   separately.
3. The `NULL` arm is examined **first**. If it moved, analysis stops there.
4. Relation availability on real hardware is reported per stack, per relation,
   with the same 1-of-4 qualification language E1 used for PX4 — no
   generalisation across stacks, no pooling.
5. Latency is reported and **not adjudicated**.

## 11. What E2 cannot establish

**Restated as a limit, not as future work.**

- **Nothing about a fault.** No fault is injected. That is E3.
- **Nothing about flight.** No props are on the bench (build packet §4.2). That
  is E5.
- **Nothing about prevalence, rate, frequency or exposure.** One board, a fixed
  n, under the tested conditions.
- **Nothing about any other board.** The result is about the unit purchased.
- **No airworthiness statement of any kind.**

Permitted wording: **"repeated under the tested conditions"**. Not permitted:
"always", "general", "population probability", "prevalence".

## 12. Status

    E2_STATUS: NOT_RUN
    reason:    no flight-controller hardware is present
    blocking:  hardware/validation_rig/E2_MINIMUM_BOM.csv, the REQUIRED rows

This line is the only thing in this file that any downstream document may cite
today.
