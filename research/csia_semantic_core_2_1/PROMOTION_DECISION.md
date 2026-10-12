# Promotion decision: Semantic Core 2.1

**2026-09-30.** Each criterion below is the brief's own wording, checked
against evidence in this package.

## The fifteen criteria

| # | criterion | met? | evidence |
|---|---|---|---|
| 1 | all approved C1/C2/C3/C4/C6/F2 corrections are implemented | **yes** | `csia_semantic_core/`. Each correction alone reproduces the audit's measured effect on all 2,640 shipped ticks, and so does the full set: 0 decision or trace mismatches against the shadow instrument |
| 2 | C5/C7 remain behavior-neutral or are withheld | **yes** | with the decision corrections off, the 2.0.0 view equals frozen v2 on 2,640 of 2,640 ticks. C5 and C7 exist only as additional 2.1 fields |
| 3 | all new semantic regression tests pass | **yes** | `tests/test_semantic_core_2_1.py`: 50 of 50 at this commit |
| 4 | property/metamorphic tests pass except explicitly deferred properties | **yes** | P1–P15 and P19 pass. P16, P17, P18 and P20 are deferred and pinned. The tests fail when the corrections are switched off, so they are not vacuous |
| 5 | small-state enumeration shows the targeted violations eliminated | **yes** | Phase D: 18 FIXED, 0 STILL_PRESENT, 5 INTENTIONALLY_DEFERRED, 10 NOT_APPLICABLE |
| 6 | all historical changes are accounted for | **yes** | 945 changed ticks, 1,275 units: 0 unexpected, 0 more certain, 0 unattributed. 945 receipts. Every recorded Phase C artifact is compared at its own tick count. The audit's misstatement is corrected (proposed ledger entry FL-060) |
| 7 | XSYS-001 remains unchanged in primary result | **yes** | 3,872 slots: 0 decision and 0 outcome differences. Primary 55/55, LB 0.7616, SUPPORTED. Every sealed manifest hash is valid |
| 8 | Phase C headline gate remains intact or any change is escalated | **yes, intact** | `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`, with the same qualifying sets and answers, recomputed with the frozen gate function |
| 9 | no unexplained new UNIQUE attribution is introduced | **yes** | 0 UNIQUE created on 2,640 ticks. C1 and F2 can only withhold UNIQUE |
| 10 | predicate errors are observable | **yes** | P5: 259 of 259 injected-fault evaluations reported. R9, R10 and R9B give `PREDICATE_FAULT` with predicate, id, subject, class and context |
| 11 | unknown evidence no longer acts as healthy evidence in corrected paths | **yes** | P6 382 → 0; P12 15 → 0; N3, N4 and N6 unknown-based rejections and confirmations → 0 |
| 12 | duplicate/order defects are eliminated | **yes** | R6 is order-independent, with the conflict listed. R7 counts once. P4 3 → 0. P3 holds for decisions and traces |
| 13 | runtime cost remains bounded and acceptable | **yes, with a stated caveat** | linear in record count; no unbounded search; 0 bytes retained across 2,640 ticks. About 0.3 ms more per tick on desktop CPython (3–4x frozen). **Not** an embedded measurement, and the C runtime does not implement 2.1 |
| 14 | frozen v2 remains reproducible | **yes** | the four reasoning files are byte-identical to the Phase A lock and the Phase C freeze. Every recorded Phase C artifact regenerates exactly from frozen v2. The 2.0.0 tests are unchanged and passing |
| 15 | historical manifests remain valid | **yes** | `tests/test_phase_c_freeze.py` passes. The XSYS-001 result manifest (225 files, its seal, and the A1/A2 chain) is valid. 22 protected files are unchanged by the run. The failure ledger is byte-identical to the hash the Phase 3.2, 4 and 5 manifests pin: the proposed entries are held aside rather than appended (R8) |

## What a reader must weigh beside the tick marks

1. **2.1 changes more results than it corrects.**
   - Corrections: 2 wrong-cause UNIQUE verdicts, and 189 units of a false
     navigation symptom.
   - Decided by missing profile declarations (G-1, G-2): 481 units, and 243
     more weakened.
   - Right answers weakened: 7 attribution scenarios.

   This is the approved rule working as designed on profiles that do not
   declare what serves COARSE_NAVIGATION or what feeds the estimator. It is
   not a defect of 2.1, but it is the main thing shadow mode will show
   (`PHASE_C_GOVERNANCE_REPORT.md` §3).
2. **R9B still gives SUPPORTED over a faulted refuter.** It is now marked
   `PREDICATE_FAULT`. Withholding the verdict is option G5, which was not
   approved.
3. **Deferred, and not solved quietly:**
   - correlated detectors (SC-14);
   - rail source lookup (C8);
   - multi-fault attribution;
   - intake validation;
   - profile data;
   - the provenance, contract and registry architecture.

## Decision

**SEMANTIC_2_1_READY_FOR_SHADOW**

**What this token means.** The implementation is accepted for shadow-mode
validation against the current default, under `SHADOW_MODE_PLAN.md`. That
plan is prepared and **not executed**.

**What it does not mean:**
- frozen v2 is not deleted or deprecated;
- 2.1 is not the default;
- FORGE, or anything else, may not act on 2.1;
- the profiles are not corrected.
