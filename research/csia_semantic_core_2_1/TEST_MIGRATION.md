# Existing-test migration (Phase H)

**2026-09-30.** The classification of every existing test is in
`TEST_MIGRATION.csv`.

## How the affected tests were found

They were measured, not guessed. `test_migration_probe.py` ran all 362 tests
in the 13 test files that exercise frozen v2 twice, in separate pytest
processes:

1. **As they are.** 0 failures.
2. **With `semantic_2_1_pytest_plugin`.** In that process only, and in
   memory only, the frozen entry points return 2.1 decisions:
   - `localize` and `localize_all`;
   - `attribute`;
   - `AssuranceEngine.evaluate`;
   - the shipped predicate and symptom tables.

The raw outcome of both runs is in `TEST_MIGRATION_PROBE.json`.

**4 tests change outcome under 2.1:**

| test | classification |
|---|---|
| `test_v2_framework.py::test_unique_requires_an_affirmative_exclusion_and_names_it` (T01) | TEST_LOCKS_IN_DEFECT (SC-01) |
| `test_v2_framework.py::test_both_verdicts_report_what_was_ruled_out_the_same_way` (T02) | TEST_LOCKS_IN_DEFECT (SC-01) |
| `test_v2_scenarios.py::test_a_stalled_process_is_attributed_to_the_process` (T03) | TEST_NEEDS_VERSIONED_EXPECTATION (right component; profile gap G-2) |
| `test_csia_semantic_correctness.py::test_record_level_reproductions_still_characterize_frozen_v2` | TEST_CORRECT_2_0_CHARACTERIZATION (it pins frozen v2 by design) |

**TEST_REVEALS_2_1_REGRESSION: none.**

**One earlier probe result was wrong, and the error was in the probe.** A
first run also showed
`test_every_scenario_replays_bit_for_bit[PS_BOTH_PUMPS_DOWN]` failing.
- **The cause.** The plugin cached one 2.1 reasoner per engine keyed by
  `id(engine)`. After garbage collection a pump-skid engine reused an
  aircraft engine's id and received its tables.
- **The fix.** The cache now lives on the engine object, and the test passes
  under 2.1.
- **What it says about 2.1.** Nothing: 2.1 is deterministic (P8).

The audit also listed T04 to T09 (`research/csia_semantic_correctness/EXISTING_TEST_COVERAGE.csv`).
They **pass** under 2.1 and are classified in the CSV:
- T04 as TEST_NEEDS_VERSIONED_EXPECTATION: the value holds, the meaning of
  `unsupported` does not;
- T05 as TEST_MIS_SPECIFIED;
- T06 to T09 as TEST_CORRECT_2_0_CHARACTERIZATION.

## What was done

**No existing test was edited.** Each existing test still asserts 2.0.0
behaviour against frozen v2, where it passes. The 2.1 expectations are
separate, in `tests/test_semantic_core_2_1.py`:
- the twins `test_T01_twin_*` to `test_T05_twin_*`;
- the R-case tests, which replace the characterization test's R section for
  2.1.

The probe itself is not part of the suite. It rebinds frozen functions in its
own process, and that should never happen inside the normal run.
