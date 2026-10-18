# Mechanism A, ArduPilot — trust measurement completion (CAMPAIGN A2)

**Committed BEFORE the first trial of this campaign.** `git log` on this file
against the results commit is the audit trail.

**This is NOT an amendment to Campaign A1.** A1 is sealed
(`campaigns/physical_validation/mechanism_a_repeat_ap/_CAMPAIGN_A1.yaml`), its
preregistration is unchanged, its manifests are immutable, and nothing here
edits, reruns into, or regenerates any part of it. A2 is a **separate campaign
with a separate identifier**, and the two are reported separately (§9).

**Nothing in the frozen v1 core is modified.** `FROZEN_PATHS` are read, run and
replayed, never edited.

---

## 1. Why this campaign exists

Campaign A1 ran 20 FAULT + 20 CONTROL and captured every preregistered quantity
**except one**: the trust coefficient. `tools/deploy/shadow_sitl_check.py`
writes a per-tick trust series only when given `--trust-trace`, and the A1
runner did not pass it (FL-014).

A1's trust trajectory is therefore **`NOT_CAPTURED`** — which is not `FAIL`,
not `ZERO`, and not `UNCHANGED`. The instrument was never switched on, and
there is no data in A1's logs to re-read at any confidence.

**A2's scope is exactly that omission and nothing else.** It is deliberately
not an improved experiment; every design choice below is "same as A1" unless
capturing trust required otherwise.

## 2. What is held identical to A1

| held identical | value |
|---|---|
| frozen CSIA core | `csia-v1.0-research-final`, verified by recorded hashes |
| ArduPilot build | `ArduCopter V4.8.0-dev @ 01a504b472259602e13df4cf07df7c0cdbb35993`, the same rebuilt binary A1 used |
| intervention | `SIM_GPS1_ENABLE = 0`, sent on the rig link at t+12.0 s |
| intervention confirmation | parameter **readback**, not write-success |
| control semantics | identical flight, fix preserved, **no parameter written** |
| downstream confirmation | `gnss.position` MISSING with `NO_3D_FIX` |
| validity criteria | the eight-state vocabulary, `tools/csia_experiment/validity.py` |
| trial structure | 20 FAULT + 20 CONTROL, **interleaved** FAULT-first |
| run length / rate | 30 s, `--speedup 5`, tick 25 Hz |
| flight profile | `--fly`: arm, climb, hold |
| nuisance policy | latency **recorded, not adjudicated** (§7) |

**The one deliberate difference:** `--trust-trace` is enabled. It writes an
additional file per flight and changes no diagnostic path — the frozen core is
byte-identical and the tracer only reads state the engine already computed.

## 3. Sample size and stopping rule — frozen here

* **20 valid FAULT, 20 valid CONTROL.**
* The campaign **stops at 40 attempted trials**. It does not stop early because
  a pattern appeared, and it does not continue past 40 because one did not.
* **No backfilling.** If trials are invalid they are recorded and the
  denominator stays 40; `planned = valid + invalid + not_attempted` must
  balance or the report raises rather than printing.
* **No resource limitation is declared.** A1 completed 40 trials in ~30 minutes
  on this host, so 40 is affordable and is not being reduced.

## 4. Trust fields captured — named from the writer, not from memory

Read out of `csia/deploy/shadow.py:_trace_states`, which is what will produce
them. One row per **engine step** (not per tick — the flight log keeps only the
last step of each tick and cannot reconstruct a recursion).

| field | what it is |
|---|---|
| `trust` | per-node trust coefficient. **`trust["gps"]` is the campaign's primary quantity** |
| `evidence` | per-node evidence value `e(k)` |
| `components` | per-node `w_nbr`/`w_phys`/`w_temp`/`w_stat` contributions, `None` where inapplicable |
| `fresh` | per-node freshness boolean |
| `S` | per-node Beta mass `α+β` — the quantity `S_0` is settled from |
| `armed` | arming state |
| `edges` | `altitude_baro`, `velocity_gps_doppler_0`, `velocity_gps_doppler_1`, `heading_course`, each as `[consistency, gate_weight]` |
| `policy` | failsafe conditions, dwell timers and level, on the last step of each tick |
| header `engine_config` | `w_*`, `rho_min`, `rho_max`, `alpha0`, `beta0`, `tick_hz`, `field_mode`, **read from the engine that produced the run** |

**Nothing is rounded** in the trace: the writer emits shortest-round-trip repr
deliberately, so a reconstruction tolerance of 1e-6 is not eaten by storage.

### 4.1 Raw first, derived second

**The full raw trace is archived before any reduction.** A committed
deterministic extractor then derives the four windows in §5. Reducing to
snapshots before preserving the series is forbidden: it would make every later
question about the trajectory unanswerable.

## 5. Windows — fixed before any trace is seen

Relative to the injection command at **t = 12.0 s** (`t` in the trace is the
engine's own clock; the extractor anchors on the first traced step).

| window | span | purpose |
|---|---|---|
| `PRE` | [10.0, 12.0) | settled pre-fault state |
| `AT` | [12.0, 13.0) | the second containing the downstream effect |
| `POST` | [14.0, 20.0) | settled post-fault state |
| `LATE` | [20.0, end] | drift check |

Each window's value is the **median over the window**, at the **trial** level.

**These windows are fixed now and will not be moved after seeing a trace.** A
window chosen to make a difference appear is not a measurement.

## 6. The trust result, defined before it is seen

### Primary questions

* **A.** Does GPS trust *increase* across confirmed fix-loss trials under the
  frozen implementation?
* **B.** What is the distribution of `T_post − T_pre` across valid FAULT trials?
* **C.** What is the corresponding distribution across valid CONTROL trials?
* **D.** Does the original n=1 result (0.9213 → 0.9300, Δ = +0.0087) fall inside
  the repeated FAULT distribution?

### Reporting rule

**Success is NOT defined as "trust must rise."**

The n=1 observation is that trust rises. If the repeat contradicts it, **the
contradiction is the result** and it is reported as such — the paper claim
changes, not the experiment. The preregistered output is the distribution and
its comparison to n=1, whichever way it falls.

### Statistics

Report **N, median, min, max and IQR at the trial level**. Ticks are **not**
independent replicates and are never counted as such.

**No p-values and no confidence intervals.** These are runs of a deterministic
simulator differing in seed and timing jitter; they are not draws from a
population, and an interval computed over them would describe the simulator's
jitter while reading as a statement about vehicles.

## 7. Nuisance policy — identical to A1

Tick latency is **recorded and NOT a validity criterion**. The host is shared
with other work in this container, and the driver's own host-noise control
measured a *higher* median for constant work than the real tick. `timing_budget`
is deliberately absent from every trial record, leaving the timing predicate
**undecidable** rather than false.

**No latency or timing claim may be made from this campaign.**

## 8. Exclusion criteria

A trial is excluded from the trust analysis only if it is not `VALID` under
`tools/csia_experiment/validity.py`. In particular:

| condition | verdict |
|---|---|
| injection readback not confirmed (FAULT arm) | `INVALID_SCENARIO` — an unproven intervention, **not** a detector miss |
| a parameter was written on a CONTROL flight | `INSTRUMENT_DEAD` — RULE A: **no arm may be read**, campaign-wide |
| no usable telemetry | `HARDWARE_FAULT` |
| trace file missing or unparseable | `INVALID_SCENARIO`, recorded with the reason |
| tick latency over budget | **not an exclusion** (§7) |

## 9. Relationship to A1 and to the original n=1

Reported **separately**, in `ARDUPILOT_REPEAT_RECONCILIATION.md`.

**Trials are not pooled.** A1 and A2 differ in an instrumentation flag, and
while that flag does not touch a diagnostic path, "it should not matter" is an
assumption and pooling would bury it. Where the two campaigns measure the same
quantity, agreement is *evidence about the instrument* and is reported as such.

## 10. What A2 cannot establish

Fixed here so it cannot be softened later:

* **Still E1.** Repeating a simulation produces simulator runs, not evidence
  about hardware. The evidence tier does not move.
* **ArduPilot only.** PX4 is a separate campaign with its own preregistration.
* **No timing claim** (§7).
* **No frequency claim about deployed systems.** 20 runs of one pinned build on
  one flight profile.
* **Nothing about the signature table.** No amount of repetition tests whether
  a relation behaves as its `LOW(h)` entry says.
