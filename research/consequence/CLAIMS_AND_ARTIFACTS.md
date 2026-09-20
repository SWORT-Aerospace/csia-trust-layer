# Phase 8 — what may be said, and the artifact that backs it

One row per claim. If a claim is not in this table, this phase does not
support it. If a row has no artifact, the claim is not made.

**The evidence ladder, unchanged from the preregistration:**
`SOURCE_ANALYSIS` · `DETERMINISTIC_SIMULATION` · `REPLAY` · `SITL` · `HIL` ·
`BENCH_HARDWARE` · `FLIGHT`. **Nothing in this phase reaches above
`DETERMINISTIC_SIMULATION`.**

---

## Claims this phase supports

| # | claim | level | artifact |
|---|---|---|---|
| C1 | Eighteen evidence terms in `csia/runtime/online.py` carry a gate expression, recorded verbatim | `SOURCE_ANALYSIS` | `results/GATE_INVENTORY.json` |
| C2 | Seven of them close while their data is fresh and no independent freshness path reacts; an eighth, `hist_vr_withdrawal`, is a boundary case counted separately | `SOURCE_ANALYSIS` | `results/GATE_INVENTORY.json`, `PHASE2_GATE_FINDINGS.md` |
| C3 | A second derivation that imports no CSIA module reaches the same set | `SOURCE_ANALYSIS` | `results/INDEPENDENT_GATE_EVALUATION.json`, `independent_gate_evaluator.py` |
| C4 | A structural support classifier distinguishes `IDENTIFIABLE` / `AMBIGUOUS` / `NON_IDENTIFIABLE` from active evidence alone, never from a normalized number | `DETERMINISTIC_SIMULATION` | `csia_consequence/support.py`, `tests/test_consequence_support.py` |
| C5 | Twelve hand-read paths in PX4 `547e2caa` and ArduPilot `01a504b4` show the same structure, in one subsystem family | `SOURCE_ANALYSIS` | `CROSSARCH_AUDIT.md`, `results/CROSSARCH_AUDIT.json` |
| C6 | ArduPilot states the feedback-loss mechanism in its own source comment | `SOURCE_ANALYSIS` | `results/CROSSARCH_AUDIT.json`, finding `AP-COMMENT` |
| C7 | A standard-library reimplementation reproduces both mechanisms without importing CSIA, by a different derivation | `DETERMINISTIC_SIMULATION` | `CSIA_LITE.md`, `results/CSIA_LITE_DEMO.json` |
| C8 | Occlusion changes the support state only where the closing relation is the sole separator of two candidates | `DETERMINISTIC_SIMULATION` | `results/CSIA_LITE_DEMO.json`, `redundancy_note` |
| C9 | For `accel_motor_current` and `accel_esc_rpm` on this airframe, the occlusion window has **zero** overlap with airborne flight: 0.00 s of fault-window occlusion over 48 locked scenarios | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase3/results/PHASE3_RESULTS_LOCKED.json` |
| C10 | Conditions B and C for those gates give identical first-response times and position errors to three decimal places | `MODEL_BASED_ACTION_CONSEQUENCE` | same |
| C11 | For `heading_course`, the gate is shut for 3.992 s of a 4.0 s fault in a physically consistent regime, and the fault is still detected in 21 of 24 seeds | `MODEL_BASED_ACTION_CONSEQUENCE` | same |
| C12 | The seed-paired gate-shut versus gate-open difference is 3/24 vs 1/24, exact McNemar p = 0.625, not distinguishable from chance at α = 0.05 | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `paired_tests` |
| C13 | P0, P1 and P2 are identical on all 216 locked scenarios | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `policy_table` |
| C14 | The campaign replays byte-identically (two full locked runs) | measured | `phase3/REPRODUCE.md`, `SHA256_MANIFEST.json` |
| C15 | An actionable consequence **is** reachable under the current model, in a physically consistent configuration and with no disarmed-gate scenario | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase31/results/PHASE31_RESULTS_LOCKED.json` |
| C16 | `structural/EG` gives 40/40 action conflicts against 0/40 in its matched control, exact McNemar p = 1.82 × 10⁻¹² | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `tests` |
| C17 | A confident attribution is issued while its separating evidence is entirely gated off in 40/360 scenarios, CI [0.0806, 0.1482] — and is correct in all 40 | `MODEL_BASED_ACTION_CONSEQUENCE` | same |
| C18 | P2's activation precondition is reachable: 40/40 eligible, CI [0.911903, 1.0] | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `actionability_precondition` |
| C19 | P2 produced 40 false refusals, prevented 0 incorrect actionable decisions, and doubled action conflicts 40 → 80 | `MODEL_BASED_ACTION_CONSEQUENCE` | same, `by_policy` |
| C20 | `SOURCE_INDICATORS` omits the per-IMU doppler edges from the IMU indicator sets | `SOURCE_ANALYSIS` | `phase31/PHASE31_RESULTS.md`, FL-029 |
| C21 | Stronger-than-`CAUTION` transitions are reachable: `CRITICAL` by two routes, `EMERGENCY` by one | `MODEL_BASED_ACTION_CONSEQUENCE` | `phase31/PREREGISTRATION_PHASE31.md` §4 |

## Hypotheses

| | status | why |
|---|---|---|
| H1 | **consistent at `SOURCE_ANALYSIS`, not tested** | H1 also requires that no independent freshness path forces an equivalent warning. That clause is established from source structure only, which is not a test of it. |
| H2 | **NOT SUPPORTED** | 28 conflicts; 24 in a physically inconsistent control and excluded; the remaining 4 are not separated from their matched control (p = 0.625). Rejection criteria (a) and (d). |
| H3 | **NOT SUPPORTED**, and in Phase 3.1 **rejected in the harmful direction** | Phase 3: P0 made 0 incorrect actionable decisions and P2 was inert — the absence of a test. Phase 3.1, separate partition, no pooling: P2 fired in 40/40 eligible scenarios, produced 40 false refusals, prevented 0, and doubled action conflicts. |
| A1 (Phase 3.1) | **SUPPORTED** | the actionability precondition is reachable; P2 activated in 40/40 eligible scenarios |
| A2 (Phase 3.1) | **false-refusal direction** | 40 false refusals, 0 prevented incorrect actionable decisions |
| H4 | **untouched** | needs phase 4, at matched false-alarm operating points |
| H5 | **not killed** | twelve paths classified; H5 predicts nothing, so classification is the whole test |
| H6 | **not killed** | both mechanisms reproduce, fresh-interpreter import check clean |

**H2 and H3 were tested at `MODEL_BASED_ACTION_CONSEQUENCE` and both were
rejected.** H1 and H5 remain at `SOURCE_ANALYSIS`; H6's test is about code,
not about aircraft. H4 is untouched and needs Phase 4.

## Claims this phase does NOT support, listed so they cannot be borrowed

- **Prevalence.** Twelve hand-picked paths are not a sample, and every one of
  them classified `STRUCTURALLY_PRESENT` *because* they were picked as
  candidates.
- **Universality.** Forbidden by the preregistration at any number of audited
  paths.
- **Novelty.** C6 is a counterexample to it, in one of the audited projects'
  own words.
- **That an autopilot executed anything.** No autopilot path ran. No SITL ran.
  `RUNTIME_REPRODUCED` and `RUNTIME_NOT_REPRODUCED` appear nowhere in the
  results.
- **That CUSUM is inferior**, or superior, or comparable. Phase 4 has not run,
  and the preregistration forbids the comparison except at matched false-alarm
  operating points over a preregistered threshold grid.
- **That the occlusion is harmless in general.** Phase 3 tested 3 of 8
  candidates, one airframe profile, one trajectory family, two fault families.
- **That the support-aware policy is safe or unsafe.** Phase 3.1 shows it
  withdrew a correct attribution in 40/40 activations; that is a capability
  cost, not a hazard, and no safety conclusion follows in either direction.
- **That freshness logic covers the occlusion.** P1 never fired in either
  phase; that is untested, not confirmed.
- **That H2 is supported.** Phase 3.1 did not preregister H2, and its pooling
  rule forbids combining it with Phase 3. What Phase 3.1 shows is that the
  precondition H2 needs is reachable — an input to a preregistered retest.
- **That abstention is a solved safety problem.** `AMBIGUOUS` is a report that
  a question cannot be answered. Reporting it is not the same as handling it,
  and the tradeoff curve phase 3 would produce does not exist yet.
- **That RAIM proves the mechanism.** RAIM may be cited as a design analogy for
  availability/integrity reporting. It is not evidence, and RAIM and CSIA are
  not claimed to solve the same problem.
- **Anything about hardware, RF, arming, flight, airworthiness or
  certification.** The E2M hardware campaign remains `AUTHORIZED_NOT_RUN` and
  this phase did not touch it.
- **An independent party's replication.** CSIA-Lite is independent of the code
  and not of the author, and `CSIA_LITE.md` says so before it reports anything.

## Corrections this phase made to itself

| what | where |
|---|---|
| Phase 6 was recorded `BLOCKED_BY_SOURCE_ACCESS` on a `find` that searched the repository and concluded about the environment. Both source trees were present. | `PHASE_STATUS.md`, `CROSSARCH_AUDIT.md` |
| The independent gate evaluator disagreed with the hand inventory on four terms and missed the `P[...]` family entirely. The parse defects were fixed **after** the disagreement was seen, which weakens the independence and is recorded as such. | `PHASE2_GATE_FINDINGS.md` |
| The first CSIA-Lite demonstration showed no occlusion, because the two airspeed hypotheses were also separated by a second feature. | `CSIA_LITE.md`, `csia_lite/demo.py` |
| A mutation run reported 24/24 killed. Every kill was a collection error caused by a module the sandbox never received, so the score was meaningless. A baseline check now refuses to report unless the unmutated selection passes. | `tools/mutation/run_e2m_mutations.py` |
| `decode()` accepted a frame with one bit flipped in the CRC field, because `int(x, 16)` is case-insensitive. Found by a property test that had been failing about one run in three. | `csia_e2m/protocol.py`, `tests/test_e2m_properties.py` |

## What is still missing

Phases 3 and 4. `PHASE_STATUS.md` says what each needs and why a thin version
of either would be worse than none.
