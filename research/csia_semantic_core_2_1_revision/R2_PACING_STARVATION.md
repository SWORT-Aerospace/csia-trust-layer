# R-2: starvation from pacing inputs, not from the closure

**2026-10-01. Revision R-2 of the promotion-candidate brief, with the parts of
Phases 5, 6 and 11 that concern it.**
- **Switch:** `Corrections(pacing_inputs=True)`, part of
  `Corrections.revised()`. Off by default.
- **Code:**
  - `csia_semantic_core/predicates.py` (`pacing_test`, `validate_pacing`, the
    OUTPUT_MISSING hypothesis replacement);
  - `csia_semantic_core/profile_overlay.py` (pacing declarations,
    `pacing_map()`);
  - `csia_semantic_core/profile_validator.py` (PV9);
  - `csia_semantic_core/successor_profiles/aircraft_successor_r2.json`.
- **Tests:** `test_r2_*` in `tests/test_semantic_core_2_1_revision.py`.

## 1. The defect it closes (L17)

**The hypothesis.** OUTPUT_MISSING's COMMUNICATION/input_starvation ("the
process has nothing to work on") was refuted in 2.1.0 by
FUNCTION_LINKS_NOMINAL: every link in the subject's declared closure is up.

**Why that is wrong.** On PX4 the estimator's output is paced by its IMU
alone:
- `EKF2::Run` sets `imu_updated` from `vehicle_imu` (multi-EKF) or
  `sensor_combined` (single EKF) (EKF2.cpp lines 625-702);
- the whole update and every publication are gated by `if (imu_updated)`
  (line 767);
- GNSS is polled inside that branch.

These lines were read in the PX4 source at 547e2ca (V4). So a healthy GNSS
link says nothing about whether the estimator can be starved.

**What it cost.** The shadow study found that every way of declaring the
estimator's GNSS input brought back v2.0's wrong SUPPORTED process_stall when
the IMU died (counterfactual W7). That covered the link (R5b), the source
(R5a, through source.gps's own dependency on the link) and both (R5). G-2 was
therefore blocked.

## 2. The rule

**The profile describes architecture.** A successor-profile declaration names
which existing edge paces an output: `add_pacing_inputs`, and `pacing_mode`:

| mode | meaning |
|---|---|
| ALL | each one is needed; any one stopping stops the output |
| ANY | failover or voting; the output continues while one arrives |

**The predicate describes starvation semantics.** PACING_INPUTS_NOMINAL reads
each declared pacing input's own records in Kleene form:

| an input's records | that input's value |
|---|---|
| any adverse record | False |
| UNAVAILABLE, or no record at all | None (gap PACING_INPUT_NOT_OBSERVED) |
| a C6 conflict on one of its keys | unknown |

The inputs then combine: **ALL** is Kleene AND, **ANY** is Kleene OR.

**Three further rules:**
- **No closure is read.** The subject's other declared dependencies are set
  aside, and listed in the trace as DECLARED_DEPENDENCY_NOT_PACING.
- **No declaration, no answer.** The value is None, with gap
  NO_DECLARED_PACING_INPUT. There is no fallback to links.
- **One hypothesis on one symptom changes.** Only OUTPUT_MISSING's
  input_starvation now reads PACING_INPUTS_NOMINAL(_FALSE).
  POSITION_UNAVAILABLE's function-level COMMUNICATION/starvation still reads
  FUNCTION_LINKS_NOMINAL, because that hypothesis is about the links serving
  a function. A test pins it.

**PV9** (validator, ERROR): a pacing input must already be a declared
dependency of its component, and the mode must be ALL or ANY. A pacing
declaration says which edge paces the output; it may not add an edge. A
malformed declaration is refused when the core is built.

## 3. Successor profile r2

**Composition:**
- **`aircraft_successor_r2.json`** is r1's two declarations, byte for byte
  (G-1 kept separate and unchanged), plus one declaration:
  `COMPUTE/state_estimator`, pacing input `SENSOR/source.imu0`, mode ALL,
  kind DIRECT, with the EKF2 lines as its source.
- **source.imu0 is already a dependency** of state_estimator in the frozen
  profile (`csia/v2/profiles/aircraft.py` line 245), so r2 adds no edge.

**What r2 does not contain:**
- **No GNSS dependency.** R5, R5a and R5b stay rejected, as the brief
  requires ("do not repair G-2 by adding GNSS/profile edges").

**Digests** (r1 is unchanged; empty pacing fields are left out of its
canonical form):
- r1 `c7541cab…`;
- r2 `c834b035…`;
- the pacing declarations as the core sees them `0b48730d…`, recorded in
  every 2.1.1 result.

## 4. The five cases

They are run on PROCESS_STALL's final tick, the shadow study's W7 base, with
2.1.1 and r2:

| case | evidence | result |
|---|---|---|
| A | IMU stale (VIOLATED), GNSS healthy | starvation confirmed (supported), process_stall also confirmed: AMBIGUOUS. IMU UNAVAILABLE: starvation stays open (unresolved) |
| B | GNSS source UNAVAILABLE and GNSS link VIOLATED, IMU healthy | starvation **rejected by PACING_INPUTS_NOMINAL**; SUPPORTED process_stall |
| C | IMU and GNSS both VIOLATED | starvation confirmed; the trace names only imu0 as read |
| D | gnss_serial, source.gps or cpu VIOLATED or UNAVAILABLE | PACING_INPUTS_NOMINAL unchanged (True) |
| E | two pacing inputs, ALL and ANY, 8 combinations | Kleene AND / OR exactly (parametrized test) |

## 5. The rejected repairs cannot return

**Permanent tests:**
- **`test_r2_the_rejected_gnss_repairs_cannot_restore_the_wrong_process_stall`,
  for R5, R5a and R5b on top of r2.** No SUPPORTED process_stall,
  starvation stays confirmed, and no GNSS record is read by the pacing
  predicate.
- **`test_r2_the_closure_predicate_is_gone_from_output_missing_and_only_there`.**
- **`test_r2_gnss_cannot_be_smuggled_in_as_a_pacing_input`.** PV9 refuses
  gnss_serial as a pacing input when it is not a dependency.
- **`test_r2_successor_r2_is_r1_plus_one_pacing_declaration_and_no_gnss_edge`.**
  r1 and r2 are pinned by digest.

**Every variant of the W7 counterfactual** (`BASELINE_LOCK.json`,
`PROFILE_VALIDATION_RESULTS.json`):

| configuration | OUTPUT_MISSING on the estimator when the IMU dies |
|---|---|
| frozen v2.0 | SUPPORTED process_stall (wrong) |
| 2.1.0, any profile without GNSS | AMBIGUOUS, starvation unresolved (for lack of a declared link) |
| 2.1.0 + R5 / R5a / R5b | SUPPORTED process_stall (wrong): blocker B2 |
| **2.1.1 + r2** | AMBIGUOUS, starvation **confirmed** |
| **2.1.1 + r2 + R5 / R5a / R5b** | AMBIGUOUS, starvation confirmed |

## 6. What it restores, and what it costs

**What it restores** (dataset A, `DATASET_A_THREE_WAY.json`):
- **Every unit where 2.1.1 + r2 differs from 2.1.0 + r1** is caused by R-2.
  That is 204 units:
  - 123 OUTPUT_MISSING localizations (MS_A4, MS_D2, PROCESS_STALL) go from
    correct-uncertain to correct-certain SUPPORTED process_stall;
  - 81 attribution ticks (MS_D2 42, PROCESS_STALL 39) get UNIQUE
    COMPUTE/state_estimator back.
- **These are exactly the 204 G-2 units the shadow study blocked.** Each is
  now restored for the right reason: the IMU is healthy, so the estimator was
  not starved.
- **The two ARTIFICIAL abstentions are restored.** PROCESS_STALL (39 of 39
  correct UNIQUE) and MS_D2 (42 of 42) come back. The five other weakened
  scenarios are unchanged (§7).

**On the frozen profile, R-2 changes nothing.** Without a pacing
declaration, 2.1.1 differs from 2.1.0 in 0 units on dataset A. 2.1.0 already
left starvation unresolved for want of a declared link; 2.1.1 leaves it
unresolved for want of a pacing declaration.

## 7. The seven weakened scenarios (Phase 5) and MS_B5 (Phase 6)

**Phase 5: correct UNIQUE ticks** (the shadow study's list, `unique_review.WEAKENED`):

| scenario | v2.0 | 2.1.0 | 2.1.0 + r1 | 2.1.1 base | 2.1.1 + r2 | shadow class | now |
|---|---|---|---|---|---|---|---|
| ACTUATOR_NO_RESPONSE | 34 | 0 | 0 | 0 | 0 | ARTIFICIAL (signature) | unchanged; F2 |
| CLOCK_DRIFT | 39 | 0 | 0 | 0 | 0 | ARTIFICIAL (signature) | unchanged; F2 |
| MS_B3_DRIVE_NO_CURRENT | 42 | 0 | 0 | 0 | 0 | ARTIFICIAL (signature) | unchanged; F2 |
| MS_B4_MECHANICAL | 42 | 0 | 0 | 0 | 0 | NECESSARY | unchanged; F2 |
| STALLED_ACTUATOR | 33 | 0 | 0 | 0 | 0 | NECESSARY | unchanged; F2 |
| PROCESS_STALL | 39 | 0 | 0 | 0 | **39** | ARTIFICIAL (G-2) | **restored, right reason** |
| MS_D2_ESTIMATOR_STALE | 42 | 0 | 0 | 0 | **42** | ARTIFICIAL (G-2) | **restored, right reason** |
| TS_STALLED | 33 | 26 | 26 | 26 | 26 | onset TEMPORARY | unchanged |

**The three remaining ARTIFICIAL abstentions** need signature refuters
(physics that rules out the RPM sensor when there is no current). That is
outside R-1, R-2 and R-3 and was not touched.

**Phase 6: wrong UNIQUE ticks under 2.1.1** in MS_B5_RESPONSE_SENSOR and
MS_TS_B5_RESPONSE_SENSOR: **0** under every one of 13 profile variants. The
variants are:
- no successor; r1; r2;
- r2 plus each of the shadow candidates R1, R2, R3, R4, R5, R5a, R5b, R6 and
  R-BAD;
- r2 plus every candidate together.

## 8. Profile errors that R-2 depends on (Phase 11)

**What was tried.** Pacing declarations mutated on purpose, run over the 30
aircraft scenarios and over W7 (`PROFILE_VALIDATION_RESULTS.json`).

| mutation | dataset A effect against r2 | W7 wrong? | caught by |
|---|---|---|---|
| PM0 the accepted r2 | none | no | — |
| PM1 the GNSS link as pacing input, no edge | none on dataset A | **yes** | **PV9 ERROR** |
| PM2 the GNSS link as pacing input, with the R5b edge | none on dataset A | **yes** | **nothing static**: it is a wrong statement about architecture on an existing edge |
| PM3 the CPU also declared pacing (ALL) | none | no | nothing; it can only widen (starvation confirmed when the CPU is adverse) |
| PM4 no pacing declaration | 204 underconfident (G-2 back) | no | nothing; gap NO_DECLARED_PACING_INPUT in the trace |
| PM5 pacing on a misspelled component | 204 underconfident | no | **PV9 ERROR** |
| PM6 ANY instead of ALL, one input | none | no | — (equivalent) |
| PM7 malformed mode or empty inputs | — | — | **refused when the core is built** |

**Two residual risks, recorded rather than fixed:**
- **A wrong pacing declaration on a real edge (PM2) brings back the wrong
  answer.** The validator cannot know which edge paces an output. That is the
  profile's job, and it is why r2's declaration carries the EKF2 line
  numbers. Review of a pacing declaration should require such a source.
- **An incomplete pacing declaration (WORSE_ANSWER_SEARCH.md, H1).** If a
  real pacing input is left undeclared and it is the one that dies, 2.1.1
  rejects starvation and SUPPORTS process_stall. 2.1.0 + r1 said AMBIGUOUS
  there, for want of any declaration.
  - **When it arises:** only on a platform whose profile omits a pacing
    input. The frozen aircraft has one IMU.
  - **On PX4 with several IMUs:** the semantics that matches production is
    ANY over every IMU. EKF2 in multi-instance mode has one IMU per instance,
    and the selector publishes while any instance runs; single-EKF uses the
    voted IMU with failover.
  - **What a static declaration cannot follow:** a pacing input that changes
    with the configuration (shadow loophole L21). That would need pacing per
    configuration epoch, which is a dependency of R-2 on R-3 this revision
    **does not implement**. Doing it would extend scope, and the brief says
    to stop there.
