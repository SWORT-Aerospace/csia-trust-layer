# Failure-ledger recommendations: FL-054 to FL-060

**2026-09-30. Part 31 of the shadow-validation brief.**

**Nothing was appended.**
- **The ledger:** `research/physical_validation/FAILURE_LEDGER.yaml` is
  unchanged. Its SHA-256, `6c7e6cf3…f5b58f`, is pinned by three sealed-phase
  manifests and checked by `tests/test_semantic_core_2_1_shadow.py`.
- **Rule R8** reserves appends to the owner.
- **The entries under review** are held in
  `research/csia_semantic_core_2_1/PROPOSED_LEDGER_ENTRIES.md`. That file is
  not edited either.
- **What this file is:** recommendations with proposed replacement wording.
  The owner decides.

## 1. Recommendations

| entry | recommendation | reason, from the shadow findings |
|---|---|---|
| FL-054 (SC-01, C1) | **APPEND_AS_WRITTEN** | Nothing in shadow contradicts it. C1 changed 0 of 2,640 dataset-A ticks, as the entry says, and none of the 278 weakened UNIQUE ticks was withheld by C1. Every withhold was F2 |
| FL-055 (SC-02, F2) | **REVISE_THEN_APPEND** | Its consequence says 2.1 withholds seven UNIQUE verdicts "that named the right component **without the evidence to call it unique**". The shadow review shows that is true for only two of them |
| FL-056 (SC-03/04, C2) | **APPEND_AS_WRITTEN** | Nothing contradicts it. In dataset A no SUPPORTED localization rests on an unmeasured refuter (0 of 1,928) |
| FL-057 (SC-05, C3) | **REVISE_THEN_APPEND** | Its consequence ("Profile gaps G-1, G-2 and G-3 are exposed rather than fixed") is out of date, and shadow found a latent C3 defect the entry should carry |
| FL-058 (SC-06/07, C4) | **REVISE_THEN_APPEND** | It says the R9B verdict "still stands, now marked PREDICATE_FAULT", which is true. Shadow has now measured the scale, and a policy has been selected |
| FL-059 (SC-12/13, C6) | **APPEND_AS_WRITTEN** | The shadow's probes agree with it:<br>• identical duplication (mutation M5) changes 0 ticks under 2.1 against 313 under v2.0;<br>• replayed records beside the current one make the key unread, with 0 wrong answers. |
| FL-060 (documentation error) | **APPEND_AS_WRITTEN** | Still accurate; nothing in shadow bears on it |

**Where FL-055 is wrong** (see `WEAKENED_UNIQUE_REVIEW.md`):
- **Two are evidence-limited:** MS_B4 and STALLED_ACTUATOR.
- **Five are ARTIFICIAL:** the evidence is present, but the declared model
  (profile or signature) cannot use it.
- **One is TEMPORARY:** TS_STALLED's onset.

## 2. Proposed replacement text

**FL-055, `consequence`:**

> Not resolved. 2.0.0 is frozen and remains the default. The successor withholds both wrong-cause UNIQUE verdicts. It also withholds UNIQUE in seven scenarios whose attribution named the right component (shadow review, research/csia_semantic_core_2_1_shadow/WEAKENED_UNIQUE_REVIEW.md):
> - in two (MS_B4, STALLED_ACTUATOR) the evidence cannot separate the alternatives, and MS_B4 carries evidence identical to MS_B5;
> - in five the declared model cannot use evidence that is present: the G-2 profile gap (PROCESS_STALL, MS_D2), and missing refuters in the signature matrix (ACTUATOR_NO_RESPONSE, MS_B3, CLOCK_DRIFT).
>
> In none of the seven was v2.0's UNIQUE justified by evidence that excluded the retained alternative.

**FL-057, `consequence`:**

> Not resolved in 2.0.0. In shadow validation (research/csia_semantic_core_2_1_shadow/):
> - G-1 is resolved for 2.1 by a versioned successor profile (csia_semantic_core/successor_profiles/aircraft_successor_r1.json; the frozen profile is unchanged).
> - G-2 is blocked. C3 scopes FUNCTION_LINKS_NOMINAL to the subject's transitive dependency closure. So any correct declaration of the estimator's GNSS input (source or link) lets a GNSS link refute input starvation of an IMU-paced estimator, restoring v2.0's wrong reason (counterfactual W7). The starvation refuter needs the subject's pacing inputs, not its closure.
> - G-3 is a function-table question.

**FL-058, `historical_impact`:** append this sentence:

> In shadow (dataset D, 68,640 single-predicate injections), the unchanged verdict rule let one failing predicate create 168 wrong SUPPORTED unit-ticks (TIMING/deadline_violation in MS_A1 and MS_A2, from a correct NO_CONSISTENT), all visible as PREDICATE_FAULT.

**FL-058, `consequence`:**

> Not resolved in 2.0.0. In 2.1.0 the fault is observable, and the verdict rule is unchanged. Governance option G5, as policy B (withhold SUPPORTED when a failed predicate refutes the supported hypothesis), was selected and validated in shadow: 0 fault-created SUPPORTED, at a cost of 42 correct SUPPORTED out of 42,770 (research/csia_semantic_core_2_1_shadow/PREDICATE_FAULT_POLICY.md). Adoption is an owner decision. Intake validation (SC-08) remains deferred.

## 3. Findings the owner may want as new entries

These are **not** drafted as ledger YAML. They are recorded here so the owner
can decide whether each is a ledger event or a design note.

| finding | kind | where |
|---|---|---|
| **L17: C3's closure scope applied to starvation.** A latent 2.1 defect; it becomes an error the moment the profile is completed correctly | OUR_OWN_ERROR in 2.1's C3 design | `G2_ESTIMATOR_INPUT_AUDIT.md` §5 |
| **Stale configuration evidence.** A latched producer after a lane switch gives a SUPPORTED false symptom for the latch's duration, in v2.0 and 2.1 alike | a shared limitation, not a regression | `CONFIGURATION_TRANSITION_STUDY.md` §3 |
| **This phase's own first ground-truth table graded SHARED_RAIL's pre-onset GPS UNIQUE (ticks 0-28) as wrong.** The payload's own GPS fault is the only cause present before tick 29, so it is correct. It was corrected before any report was written. No recorded result, and nothing in the 2.1 package, is affected | a within-phase measurement correction; probably a design note rather than a ledger event | `ground_truth.py` `payload_cause` |
