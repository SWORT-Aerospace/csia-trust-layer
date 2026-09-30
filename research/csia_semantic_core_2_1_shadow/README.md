# CSIA Semantic Core 2.1: shadow validation

**2026-09-30.**
- **Decision: SEMANTIC_2_1_REQUIRES_REVISION** (`PROMOTION_REVIEW.md`).
- **2.1 stays in shadow with zero control authority.** Frozen CSIA v2.0
  remains the authoritative default.

**The brief's question was whether 2.1 is actually a better semantic
baseline.** The answer has two parts:
- **On every dimension measured it is not worse than v2.0**, and it
  corrects what the audit found.
- **Before it can be a baseline for new work it needs three revisions**:
  predicate-fault policy B; starvation scoped to pacing inputs; and
  configuration-epoch invalidation. One promotion criterion (12, realistic
  configuration transitions) fails without them.

## Findings in one table

| topic | result | document |
|---|---|---|
| differences in dataset A | 1,275 units in 945 of 2,640 ticks: 273 correctness fixes, 197 conservative withholds, 805 profile gaps, **0 possible regressions** | `SHADOW_VALIDATION_REPORT.md`, `SHADOW_DIFFERENCES.csv` |
| G-1 (COARSE_NAVIGATION) | **resolved** by successor profile r1 (estimator and nav_solution serve it; PX4 EKF2 feeds every position consumer). 601 units restored, nothing incorrect added | `G1_COARSE_NAVIGATION_AUDIT.md` |
| G-2 (estimator inputs) | **explicitly blocked**. Every GNSS-input declaration brings back v2.0's wrong reason, because the starvation predicate reads the closure (L17) | `G2_ESTIMATOR_INPUT_AUDIT.md` |
| profile repairs | R2 and R3 accepted; R1, R5, R5b and R-BAD (the over-connection control) rejected; R4, R5a and R6 deferred | `PROFILE_REPAIR_PROPOSAL.md`, `PROFILE_COUNTERFACTUAL_RESULTS.md` |
| seven weakened UNIQUE | all F2; v2.0 right for the wrong reason in all; 2 NECESSARY, 5 ARTIFICIAL, 0 REGRESSION | `WEAKENED_UNIQUE_REVIEW.md` |
| wrong UNIQUE (MS_B5, MS_TS_B5) | stay corrected under every profile variant; 24 pinned tests | `WRONG_UNIQUE_REGRESSION.md` |
| predicate faults | 2.1 today (policy A) lets one fault create 168 wrong SUPPORTED; **policy B selected**: 0, at 0.1 % cost | `PREDICATE_FAULT_POLICY.md`, `PREDICATE_FAULT_INJECTION_RESULTS.csv` |
| configuration transition E1 | without validity management, 9 ticks of SUPPORTED false symptom after a lane switch (as in v2.0); the epoch rule gives 0 | `CONFIGURATION_TRANSITION_STUDY.md` |
| XSYS-001, time rule against state rule (exploratory) | the compensation-state rule was never better than the fixed 0.2 s rule: it lost 64 % of correct answers, and made 10 wrong when also used as evidence | `XSYS_STATE_CONDITIONED_EXPLORATION.md` |
| static profile validator | 8 rules, each from an observed failure; 9 of 10 profile mutations caught; real warnings in all three shipped profiles | `PROFILE_VALIDATOR_SPEC.md` |
| correlated evidence | lineage disjointness removes every false corroboration and keeps the real one | `DEPENDENCY_METADATA_PREVIEW.md` |
| runtime | desktop: 2.1 2.6-3.0× v2.0; shadow 12.5× (ground only) | `SHADOW_VALIDATION_REPORT.md` §7 |
| H743 | C port plausible at 25-200 Hz **as an estimate**; nothing measured on target; the C runtime has no v2 at all | `C_RUNTIME_DELTA.md`, `H743_FEASIBILITY.md` |
| XSYS-001 / Phase C | unchanged: 3,872 / 3,872 slots; primary 55/55; headline and answers identical | `PROMOTION_REVIEW.md` |

## Contents

**Reports:**
- `SHADOW_VALIDATION_REPORT.md`
- `PROMOTION_REVIEW.md`
- `G1_COARSE_NAVIGATION_AUDIT.md`
- `G2_ESTIMATOR_INPUT_AUDIT.md`
- `PROFILE_REPAIR_PROPOSAL.md`
- `PROFILE_COUNTERFACTUAL_RESULTS.md`
- `WEAKENED_UNIQUE_REVIEW.md`
- `WRONG_UNIQUE_REGRESSION.md`
- `PREDICATE_FAULT_POLICY.md`
- `CONFIGURATION_TRANSITION_STUDY.md`
- `XSYS_STATE_CONDITIONED_EXPLORATION.md`
- `PROFILE_VALIDATOR_SPEC.md`
- `DEPENDENCY_METADATA_PREVIEW.md`
- `CUSUM_INTEGRATION_EXAMPLE.md`
- `ESTIMATOR_INTEGRATION_EXAMPLE.md`
- `C_RUNTIME_DELTA.md`
- `H743_FEASIBILITY.md`
- `PRODUCT_UTILITY.md`
- `METHOD_REUSE_MAP.md`
- `NEXT_IMPLEMENTATION_TOP5.md`
- `ANTI_ROADMAP.md`
- `FULLTEXT_VERIFICATION_QUEUE.md`
- `FAILURE_LEDGER_RECOMMENDATIONS.md`

**Tables:**
- `SHADOW_DIFFERENCES.csv`
- `PREDICATE_FAULT_INJECTION_RESULTS.csv`
- `LOOPHOLE_REGISTER.csv` (23 loopholes)

**Harnesses** (each writes only its own output next to it):

| script | output | part |
|---|---|---|
| `verify_state.py` | `STATE_VERIFICATION.json` | 1 |
| `shadow_validation.py` | `SHADOW_RESULTS.json`, `SHADOW_DIFFERENCES.csv`, `SHADOW_LOG.jsonl` | 2, 3, 7 (datasets A and B) |
| `dataset_c_enumeration.py` | `DATASET_C_RESULTS.json` | dataset C |
| `unique_review.py` | `UNIQUE_REVIEW.json` | 8, 9, 46 |
| `predicate_fault_study.py` | `PREDICATE_FAULT_INJECTION_RESULTS.csv`, `PREDICATE_FAULT_RESULTS.json` | 10-12 (dataset D) |
| `transition_study.py`, run from `TRANSITION_DESIGN.json` (frozen) | `TRANSITION_RESULTS.json` | 13-17, 49 (dataset E) |
| `xsys_state_conditioned.py` | `XSYS_STATE_CONDITIONED_RESULTS.json` | 50, exploratory |
| `adversarial_profiles.py` | `ADVERSARIAL_PROFILE_RESULTS.json` | 23 |
| `worse_answer_search.py` | `WORSE_ANSWER_SEARCH.json` | 22 |
| `imu_dependency_preview.py` | `IMU_DEPENDENCY_PREVIEW.json` | 29, 38 |
| `shadow_runtime.py` | `SHADOW_RUNTIME.json` | 26, 28 |

**Inputs to the harnesses:**
- `ground_truth.py`: scenario truth, from the scenarios' own descriptions;
- `profile_candidates.json`: every candidate declaration, with its source,
  written before it was run.

**Code added outside this directory:**
- `csia_semantic_core/shadow.py`: the shadow runner;
- `csia_semantic_core/profile_overlay.py`: versioned successor-profile
  overlays;
- `csia_semantic_core/successor_profiles/aircraft_successor_r1.json`: the
  accepted successor profile, digest `c7541cab…`;
- `csia_semantic_core/profile_validator.py`: the static validator;
- `tests/test_semantic_core_2_1_shadow.py`: the permanent regression tests.

**None of it changes 2.1's default semantics.**

## What was not touched

**No file under these was modified:**
- frozen CSIA v2.0 (`csia/v2`);
- the Phase C results;
- XSYS-001, its A1 and A2 amendments, and its confirmatory result;
- any sealed manifest;
- the semantic, architecture and novelty audits;
- the 2.1 package.

**Governance was kept:**
- **The seven held failure-ledger entries were not appended**
  (recommendations in `FAILURE_LEDGER_RECOMMENDATIONS.md`).
- **No FORGE work was done**, no admissibility architecture was built, and
  nothing was ported to C.

## Reproduce

From the repository root, with `.venv`:

```
.venv/bin/python research/csia_semantic_core_2_1_shadow/verify_state.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/shadow_validation.py        # ~10 min
.venv/bin/python research/csia_semantic_core_2_1_shadow/unique_review.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/predicate_fault_study.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/transition_study.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/xsys_state_conditioned.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/adversarial_profiles.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/worse_answer_search.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/imu_dependency_preview.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/dataset_c_enumeration.py
.venv/bin/python research/csia_semantic_core_2_1_shadow/shadow_runtime.py          # timings vary by machine
.venv/bin/python -m pytest -q tests/test_semantic_core_2_1_shadow.py
```
