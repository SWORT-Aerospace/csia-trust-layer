# CSIA Semantic Core 2.1: promotion-candidate revision (2.1.1)

**2026-10-01.**
- **Decision: SEMANTIC_2_1_READY_AS_BASELINE** (`PROMOTION_REVIEW.md`).
  2.1.1 is ready to be the preferred semantic baseline for new CSIA work, on
  three stated conditions.
- **Frozen v2.0 remains the authoritative runtime default.** 2.1 has zero
  control authority, and the code default stays 2.1.0.

**What was done.** The owner accepted the shadow validation's
SEMANTIC_2_1_REQUIRES_REVISION and approved exactly three revisions. They are
implemented as separately versioned switches (semantics 2.1.1), and the whole
promotion evidence was re-run.

## Findings in one table

| topic | result | document |
|---|---|---|
| starting state (Phase 0) | locked before any code; 50/50 and 51/51 tests; blockers B1 (168), B2 (W7) and B3 (9 stale ticks) reproduced exactly | `REVISION_REPORT.md` §2, `BASELINE_LOCK.json` |
| R-1 fault policy B | 168 → **0** fault-created SUPPORTED on 68,640 injections; equal to the reference policy B; 0 unrelated conclusions lost; every fault visible | `R1_FAULT_POLICY_B.md` |
| R-2 starvation from pacing inputs | G-2 **resolved with no GNSS edge**: 204 units restored for the right reason; W7 stays AMBIGUOUS with starvation confirmed, even with R5/R5a/R5b; cases A-E as required | `R2_PACING_STARVATION.md` |
| R-3 configuration epoch | E1 replayed exactly: 9 stale ticks → **0**, 0 valid records lost; 14 adversarial variants; an integration contract with five clauses | `R3_CONFIGURATION_EPOCH.md` |
| tests and properties (Phase 1) | 75 new tests; under 2.1.1 every property holds except P5's decision clause, superseded by R-1 by definition; replacement P5' holds | `REVISION_REPORT.md` §3 |
| enumeration (Phase 2) | section D identical; 0 new violations; R9B fixed | `REVISION_REPORT.md` §4 |
| dataset A against v2.0 (Phase 4) | 470 differing units: 273 correctness fixes, 197 conservative withholds, **0 profile gaps** (805 before), 0 regressions, 0 UNKNOWN | `REVISION_REPORT.md` §5 |
| weakened UNIQUE (Phase 5) | PROCESS_STALL and MS_D2 restored; 2 NECESSARY and 3 ARTIFICIAL (signature) remain | `R2_PACING_STARVATION.md` §7 |
| MS_B5 / MS_TS_B5 (Phase 6) | 0 wrong UNIQUE under 13 variants | same |
| XSYS-001, Phase C (Phases 9, 10) | unchanged under 2.1.1: 3,872 slots, 55/55, lower bound 0.7616; headline and six answers | `REVISION_REPORT.md` §6 |
| profiles (Phase 11) | validator: 0 errors on shipped profiles; PV9 added; 0 overconfident under the ten shadow mutations; a wrong pacing declaration on a real edge is not statically detectable (L24) | `R2_PACING_STARVATION.md` §8 |
| worse-answer search (Phase 12) | no wrong UNIQUE, wrong SUPPORTED, eliminated true hypothesis, hidden fault or order dependence; the worse answers found all need a broken precondition | `WORSE_ANSWER_SEARCH.md` |
| decision quality (Phase 13) | against v2.0: same correct SUPPORTED (2,285), wrong UNIQUE 87 → 3, false symptoms 189 → 0 | `REVISION_REPORT.md` §7 |
| trace (Phase 14) | answers all five questions on every measured case | `REVISION_REPORT.md` §8 |
| runtime (Phase 15) | 1.13× 2.1.0 (desktop median, trace off); linear; no retained state | `REVISION_REPORT.md` §9 |
| H743 and C (Phases 16, 17) | estimate moves from about 30-400 to about 30-500 µs per tick and about 13-15 KB RAM: not material; nothing measured on target; nothing ported | `H743_UPDATE.md`, `C_RUNTIME_DELTA_UPDATE.md` |
| ledger (Phase 18) | nothing appended; FL-054 to FL-060 recommendations updated; FL-061 and FL-062 drafted | `FAILURE_LEDGER_RECOMMENDATIONS.md` |

## Contents

**Reports:**
- `PROMOTION_REVIEW.md`
- `REVISION_REPORT.md`
- `R1_FAULT_POLICY_B.md`
- `R2_PACING_STARVATION.md`
- `R3_CONFIGURATION_EPOCH.md`
- `WORSE_ANSWER_SEARCH.md`
- `H743_UPDATE.md`
- `C_RUNTIME_DELTA_UPDATE.md`
- `FAILURE_LEDGER_RECOMMENDATIONS.md`

**Tables:**
- `REVISION_DIFFERENCES.csv`: every unit where 2.1.1 differs from 2.1.0;
- `FAULT_REPLAY_RESULTS.csv`;
- `LOOPHOLE_REGISTER_UPDATE.csv`: L1-L23 after the revision, plus L24-L26.

**Harnesses** (each writes only its own output next to it, and reuses the
shadow package by import):

| script | output | phase |
|---|---|---|
| `verify_baseline.py` (`--final` at the end) | `BASELINE_LOCK.json`, `FINAL_STATE_CHECK.json` | 0 |
| `property_rerun.py` (with `revised_defaults_pytest_plugin.py`) | `PROPERTY_RERUN.json` | 1 |
| `enumeration_three_way.py` | `ENUMERATION_THREE_WAY.json` | 2 |
| `fault_replay.py` | `FAULT_REPLAY_RESULTS.json`, `.csv` | 3 |
| `dataset_a_three_way.py` | `DATASET_A_THREE_WAY.json`, `REVISION_DIFFERENCES.csv` | 4, 5, 6, 13 |
| `transition_replay.py` | `TRANSITION_REPLAY_RESULTS.json` | 7 |
| `epoch_adversarial.py` | `EPOCH_ADVERSARIAL_RESULTS.json` | 8 |
| `governance_gates.py` | `GOVERNANCE_GATES.json` | 9, 10 |
| `profile_validation.py` | `PROFILE_VALIDATION_RESULTS.json` | 11 |
| `worse_answer_revision.py` | `WORSE_ANSWER_REVISION.json` | 12 |
| `trace_validation.py` | `TRACE_VALIDATION.json` | 14 |
| `runtime_revision.py` | `RUNTIME_REVISION.json` | 15 |
| `revision_common.py` | — | shared paths and pins |

**Code changed outside this directory:**
- `csia_semantic_core/`:
  - `admission.py` (new);
  - `core.py`, `localization.py`, `predicates.py`, `index.py`,
    `profile_overlay.py`, `profile_validator.py`, `shadow.py`,
    `__init__.py`;
  - `successor_profiles/aircraft_successor_r2.json` (new).
- `tests/test_semantic_core_2_1_revision.py`: 75 tests.

**With every revision switch off, 2.1.0 is unchanged:** the 50 and 51
existing tests pass as before.

## What was not touched

**No file under these was modified:**
- frozen CSIA v2.0 (`csia/v2`);
- the Phase C results;
- XSYS-001, its A1 and A2 amendments, and its confirmatory result;
- any sealed manifest;
- the semantic audit, the 2.1 package, the shadow-validation package and the
  novelty and research audits.

`FINAL_STATE_CHECK.json` verifies them all at the end of the phase.

**Governance kept:**
- **Nothing was appended to the failure ledger.**
- **Nothing outside the three revisions was built:**
  - no producer registry or contracts;
  - no admissibility engine or provenance graph;
  - no fusion, CUSUM or EKF2 adapter, or profile compiler;
  - no FORGE, RTA or active diagnosis;
  - no C port, and nothing toward 2.2.
- **One dependency was found and stopped at, not built:** pacing per
  configuration epoch.

**The brief arrived truncated part-way through Phase 18.** Phases 0-18 were
done as written. The package, the review and the tokens follow the
shadow-validation brief's structure (`PROMOTION_REVIEW.md`, final note).

## Reproduce

From the repository root, with `.venv`:

```
.venv/bin/python research/csia_semantic_core_2_1_revision/verify_baseline.py
.venv/bin/python research/csia_semantic_core_2_1_revision/property_rerun.py
.venv/bin/python research/csia_semantic_core_2_1_revision/enumeration_three_way.py   # ~5 min
.venv/bin/python research/csia_semantic_core_2_1_revision/fault_replay.py            # ~4 min
.venv/bin/python research/csia_semantic_core_2_1_revision/dataset_a_three_way.py
.venv/bin/python research/csia_semantic_core_2_1_revision/transition_replay.py
.venv/bin/python research/csia_semantic_core_2_1_revision/epoch_adversarial.py
.venv/bin/python research/csia_semantic_core_2_1_revision/governance_gates.py
.venv/bin/python research/csia_semantic_core_2_1_revision/profile_validation.py
.venv/bin/python research/csia_semantic_core_2_1_revision/worse_answer_revision.py
.venv/bin/python research/csia_semantic_core_2_1_revision/trace_validation.py
.venv/bin/python research/csia_semantic_core_2_1_revision/runtime_revision.py       # timings vary by machine
.venv/bin/python research/csia_semantic_core_2_1_revision/verify_baseline.py --final
.venv/bin/python -m pytest -q tests/test_semantic_core_2_1_revision.py
```
