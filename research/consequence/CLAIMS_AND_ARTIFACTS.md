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

## Hypotheses

| | status | why |
|---|---|---|
| H1 | **consistent at `SOURCE_ANALYSIS`, not tested** | H1 also requires that no independent freshness path forces an equivalent warning. That clause is established from source structure only, which is not a test of it. |
| H2 | **untouched** | needs phase 3 |
| H3 | **untouched** | needs phase 3 |
| H4 | **untouched** | needs phase 4, at matched false-alarm operating points |
| H5 | **not killed** | twelve paths classified; H5 predicts nothing, so classification is the whole test |
| H6 | **not killed** | both mechanisms reproduce, fresh-interpreter import check clean |

**No hypothesis in this phase has been tested above `SOURCE_ANALYSIS` except
H6, and H6's test is about code, not about aircraft.**

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
