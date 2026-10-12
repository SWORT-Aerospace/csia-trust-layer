# E2 — confirmatory replication of the three modern joint-miss cells

**STATUS: FROZEN, NOT EXECUTED.** Everything below is fixed before the first
flight. Nothing in this document may be chosen, widened, narrowed or
re-weighted after outcomes are seen. E2 does not block P0.5 and does not gate
the established-method challenge.

**Frozen at:** the commit that introduces this file.
**Depends on:** E1 (`results/e1_modern.json`), P0.5
(`INFORMATION_CONTRACT_POWER_THRUST.md`).

---

## 1. Hypothesis

> Slow, operationally significant GNSS position slews can produce a
> reproducible regime on modern ArduPilot in which **both** the native
> estimator and CSIA fail to escalate.

E1 observed this in three cells (`a55.7_s60`, `a55.7_s120`, `a55.7_s240`), one
flight each. Three flights at a single amplitude are not a characterised
regime. E2 asks only whether the effect **reproduces under independent
variation**. It does not map a boundary, and it does not search.

---

## 2. What E2 is explicitly not

- **Not an enlargement of E1.** The E1 grid is untouched and its numbers stand
  as reported.
- **Not a search.** No adaptive selection, no cell chosen after seeing an
  outcome, no interpolation between cells.
- **Not a rescue.** If E2 refutes the effect, E1's `SURVIVES_BOUNDED` verdict
  is downgraded and the negative result is committed.

---

## 3. Design

Smallest defensible design carrying independent repeats and a variation that
is verified to reach the simulator.

**Fixed factors** (unchanged from E1, so the comparison is like for like):

| factor | value |
|---|---|
| amplitude | 55.7 m |
| injection start | t = 60 s |
| post-injection window | 30 s |
| target | ArduCopter V4.8.0-dev @ `01a504b` |
| detection criteria | EKF `pos_horiz_variance` > 0.8; CSIA escalation naming GPS |
| significance threshold | 48 m |
| validity contract | V1-V6, corrected instrument, plus `instrument_control()` |
| ESC telemetry | **suppressed at ingestion** (see §6) |

**Varied factors**, all three levels flown for every combination:

| factor | levels | why this factor |
|---|---|---|
| slew | 60, 120, 240 s | the three E1 joint-miss cells, unchanged |
| **repeat seed** | 3 independent SITL instances per cell | E1 flew one flight per cell; rule 3 says these are not replicates. This makes them replicates. |
| **glitch axis** | X (north) and Y (east) | E1 varied only X. Direction has never been a tested axis in this programme. |

**Cells:** 3 slews × 2 axes × 3 repeats = **18 flights**, plus **6 nominal
arms** (one per slew × axis) for the R10 budget, the excursion control and the
instrument null control. **24 flights total.**

**Verification that the variation reaches the simulator.** The Y axis is
driven by `SIM_GPS1_GLTCH_Y`. Before any E2 cell counts, a smoke arm must
confirm that parameter exists on this build and that setting it moves
`sep(GPS_RAW_INT, SIMSTATE)` in the east direction. If it does not,
**the axis factor is dropped and E2 runs 9 flights on slew and repeat alone**
— a documented reduction, decided by an interface check, not by an outcome.

---

## 4. Replication success and failure, defined now

Let *k* be the number of the **9 X-axis cells** (3 slews × 3 repeats) that are
`TRIAL_VALID` and categorise as `JOINT_MISS`.

| outcome | criterion | verdict |
|---|---|---|
| **REPLICATED** | k ≥ 7 of 9 | the regime reproduces; F3 stays `SURVIVES_BOUNDED` and the bound widens to "reproducible across independent repeats at 55.7 m" |
| **PARTIALLY_REPLICATED** | 3 ≤ k ≤ 6 | the effect is real but not reliable; F3 stays `SURVIVES_BOUNDED` with the observed rate reported as the bound, and no stronger statement is made |
| **NOT_REPLICATED** | k ≤ 2 | E1's three cells are not a regime. F3 is downgraded to `SINGLE_OBSERVATION_NOT_REPRODUCED` and the negative result is committed |
| **INVALID** | fewer than 7 of 9 trials pass V1-V6 | no verdict; the rig is repaired and E2 re-run in full, with the failed run preserved |

The Y-axis cells are **reported separately and do not enter k.** They test
whether the effect is axis-specific. Folding them into the same count would
let a second factor rescue or sink the primary question.

Thresholds chosen before execution on this reasoning: 7/9 is the smallest
majority that cannot be produced by a single slew level behaving differently
(each slew contributes 3), and 2/9 is the largest count consistent with the
effect being confined to one slew's repeats.

---

## 5. What is reported regardless of outcome

Per cell: injected offset, true airframe excursion, excess over the
matched-window nominal control, EKF variance, CSIA GPS escalation, coverage
category, and the full V1-V6 record. Negative and invalid cells are retained
in the artifact, never dropped.

The four-way F4 decomposition is reported for E2 **separately** from E1. E1's
numbers (BOTH 1, AUTOPILOT_ONLY 4, CSIA_ONLY 0, JOINT_MISS 3) are not merged
with E2's, pooled, or restated as a combined figure.

---

## 6. Rig configuration, declared before execution

E2 flies with `ESC_TELEMETRY_1_TO_4` suppressed at ingestion, which restores
the legacy information architecture and is required for the R10 budget to be
meaningful (P0.5 §7; `results/r10_attribution.json` arm B: 0 transitions,
`trust_battery` 0.997).

This is a **rig control, not a CSIA change.** It is declared here, before the
first E2 flight, and the unsuppressed R10 breach on the unmodified modern rig
remains a committed finding.

---

## 7. Stopping rule

E2 runs its 24 flights once. There is no re-run on an unfavourable outcome, no
additional cell, and no post-hoc exclusion except by the V1-V6 contract as
written. If the rig fails mid-campaign, the whole campaign is re-run and the
failed run is preserved alongside.
