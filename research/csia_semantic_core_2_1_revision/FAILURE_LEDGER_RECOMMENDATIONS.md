# Failure-ledger recommendations after the revision (Phase 18)

**2026-10-01.**

**Nothing was appended:**
- **The ledger.** `research/physical_validation/FAILURE_LEDGER.yaml` is
  unchanged. Its SHA-256 `6c7e6cf3…f5b58f` is pinned by three sealed-phase
  manifests and checked by `verify_baseline.py --final` and by the test
  suites.
- **Rule R8** of `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` reserves
  appends to the owner.
- **The entries under review stay where they are held:** FL-054 to FL-060 in
  `research/csia_semantic_core_2_1/PROPOSED_LEDGER_ENTRIES.md`, and the
  Mechanism B entry (proposed FL-053). Neither file is edited.
- **The shadow study's recommendations are not edited either**
  (`research/csia_semantic_core_2_1_shadow/FAILURE_LEDGER_RECOMMENDATIONS.md`).
  This file supersedes them only where the revision changed a fact.

**Owner approval is required for every append below.**

## 1. FL-054 to FL-060, updated

| entry | shadow recommendation | **now** | what changed |
|---|---|---|---|
| FL-054 (SC-01, C1) | APPEND_AS_WRITTEN | **APPEND_AS_WRITTEN** | nothing: C1 still withholds none of the weakened UNIQUE |
| FL-055 (SC-02, F2) | REVISE_THEN_APPEND | **REVISE_THEN_APPEND, with newer wording** | two of the five ARTIFICIAL abstentions (PROCESS_STALL, MS_D2) are restored in 2.1.1 by R-2 |
| FL-056 (SC-03/04, C2) | APPEND_AS_WRITTEN | **APPEND_AS_WRITTEN** | nothing |
| FL-057 (SC-05, C3) | REVISE_THEN_APPEND | **REVISE_THEN_APPEND, with newer wording** | G-2 is no longer blocked: R-2 and successor r2 resolve it with no GNSS edge; L17 is corrected |
| FL-058 (SC-06/07, C4) | REVISE_THEN_APPEND | **REVISE_THEN_APPEND, with newer wording** | policy B is adopted as R-1 in 2.1.1: 168 → 0 fault-created SUPPORTED |
| FL-059 (SC-12/13, C6) | APPEND_AS_WRITTEN | **APPEND_AS_WRITTEN** | nothing; the revision adds 0 order or duplicate dependence (2,700 ticks probed) |
| FL-060 (documentation error) | APPEND_AS_WRITTEN | **APPEND_AS_WRITTEN** | nothing |

**Proposed replacement text.** It replaces the shadow study's proposals for
the same fields.

**FL-055, `consequence`:**

> Not resolved in 2.0.0, which is frozen and remains the default. The successor withholds both wrong-cause UNIQUE verdicts. It also withheld UNIQUE in seven scenarios whose attribution named the right component (research/csia_semantic_core_2_1_shadow/WEAKENED_UNIQUE_REVIEW.md):
> - in two (MS_B4, STALLED_ACTUATOR) the evidence cannot separate the alternatives, and MS_B4 carries evidence identical to MS_B5;
> - in two (PROCESS_STALL, MS_D2) the cause was the G-2 profile gap, and 2.1.1 with successor profile r2 restores the UNIQUE for the right reason;
> - in three (ACTUATOR_NO_RESPONSE, MS_B3, CLOCK_DRIFT) the signature matrix lacks a refuter.
>
> In none of the seven was v2.0's UNIQUE justified by evidence that excluded the retained alternative.

**FL-057, `consequence`:**

> Not resolved in 2.0.0. In the successor:
> - G-1 is resolved by versioned successor profiles r1 and r2 (the frozen profile is unchanged).
> - G-2 is resolved in 2.1.1. R-2 decides the estimator's input starvation from its declared pacing input (successor profile r2: source.imu0, an existing dependency), never from the dependency closure, so no GNSS edge is needed and none was added. It restores 204 shadow units for the right reason, with 0 new wrong answers.
> - The latent defect shadow found (C3's closure applied to starvation, L17) is corrected by the same change.
> - G-3 remains a function-table question.
>
> research/csia_semantic_core_2_1_revision/R2_PACING_STARVATION.md.

**FL-058, `historical_impact`:** append this sentence, replacing the shadow
study's proposed one:

> In shadow (dataset D, 68,640 single-predicate injections), the unchanged verdict rule let one failing predicate create 168 wrong SUPPORTED unit-ticks (TIMING/deadline_violation in MS_A1 and MS_A2, from a correct NO_CONSISTENT), all visible as PREDICATE_FAULT. Under 2.1.1 with R-1 the same injections create 0.

**FL-058, `consequence`:**

> Not resolved in 2.0.0. In 2.1.0 the fault is observable and the verdict rule is unchanged. In 2.1.1, R-1 (policy B, owner-approved) withholds a SUPPORTED whenever a failed predicate could have changed it, as WITHHELD_PREDICATE_FAULT with the survivors kept. Measured: 0 fault-created SUPPORTED; 42 SUPPORTED that rested on a failed refuter withheld; no unrelated conclusion lost; every fault visible (research/csia_semantic_core_2_1_revision/R1_FAULT_POLICY_B.md). Intake validation (SC-08) remains deferred.

## 2. New entries, drafted and not appended

**Numbering.** These are numbered on the assumption that proposed FL-053 to
FL-060 are promoted first. Renumber otherwise.

**What they are.** Both are this program's own findings, of the ledger's
`OUR_OWN_ERROR` and `SYSTEMIC_FINDING` kinds, which is why they are drafted at
all.

**Parse check.** The block parses as YAML (checked by
`tests/test_semantic_core_2_1_revision.py`).

```yaml
  - id: FL-061
    date: 2026-10-01
    phase: CSIA Semantic Core 2.1 promotion-candidate revision (R-2)
    kind: OUR_OWN_ERROR
    what_happened: >-
      C3 in Semantic Core 2.1.0 scoped FUNCTION_LINKS_NOMINAL to the subject's
      transitive dependency closure, and OUTPUT_MISSING's
      COMMUNICATION/input_starvation was refuted by it. On PX4 the estimator's
      output is paced by its IMU alone (EKF2::Run gates every update and
      publication on imu_updated), so a healthy GNSS link cannot show the
      estimator was not starved. The defect was latent: with the frozen
      profile no link is in the estimator's closure, and 2.1.0 left
      starvation unresolved. Any correct completion of the profile (the GNSS
      source, its link, or both: R5a, R5b, R5) made 2.1.0 refute starvation
      with the link and SUPPORT the wrong COMPUTE/process_stall when the IMU
      died (shadow counterfactual W7, loophole L17).
    affected_version: >-
      csia_semantic_core 2.1.0 (C3), commit 245dcb6. Not frozen v2.0, whose
      unscoped predicate gives the same wrong answer for a different reason.
    found_by: >-
      The 2.1 shadow validation, research/csia_semantic_core_2_1_shadow/
      G2_ESTIMATOR_INPUT_AUDIT.md, counterfactual W7.
    successor_correction: >-
      R-2 in csia_semantic_core 2.1.1 (switch pacing_inputs): starvation on
      OUTPUT_MISSING reads PACING_INPUTS_NOMINAL over the subject's declared
      pacing inputs (ALL or ANY, Kleene), never the closure; no declaration
      gives no answer. Successor profile r2 declares source.imu0 as the
      estimator's pacing input; PV9 refuses a pacing input that is not a
      declared dependency.
    historical_impact: >-
      None on any recorded result: no shipped or historical run used a
      profile with the GNSS declarations. In 2.1.1 with r2 the 204 shadow G-2
      units are restored for the right reason, with 0 new wrong answers.
    xsys_impact: none. XSYS-001's 3,872 slots are unchanged under 2.1.1.
    verdict: RECORDED
    consequence: >-
      Corrected in the 2.1.1 successor, which is not the runtime default.
      R-2 is only as good as the pacing declaration: a wrong or incomplete
      one can bring a wrong answer back (research/csia_semantic_core_2_1_revision/
      WORSE_ANSWER_SEARCH.md section 2.2).
    artifact: >-
      csia_semantic_core/predicates.py; csia_semantic_core/successor_profiles/
      aircraft_successor_r2.json; tests/test_semantic_core_2_1_revision.py;
      research/csia_semantic_core_2_1_revision/R2_PACING_STARVATION.md

  - id: FL-062
    date: 2026-10-01
    phase: CSIA Semantic Core 2.1 promotion-candidate revision (R-3)
    kind: SYSTEMIC_FINDING
    what_happened: >-
      Neither frozen v2.0 nor Semantic Core 2.1.0 had any notion of the
      configuration a piece of evidence was generated under. In the frozen
      transition design E1 (an estimator lane switch after an IMU failure,
      with a producer that latches its last lane's deadline misses), both
      SUPPORTED a false POSITION_UNAVAILABLE (COMPUTE/estimator_stale) on two
      navigation functions for 9 ticks after the switch, from evidence that
      described the lane no longer in use.
    affected_version: >-
      CSIA v2 reasoning semantics 2.0.0 (frozen) and csia_semantic_core
      2.1.0.
    found_by: >-
      The 2.1 shadow validation's configuration-transition experiment E1
      (design frozen at e0fc81a before its runner existed),
      research/csia_semantic_core_2_1_shadow/CONFIGURATION_TRANSITION_STUDY.md.
    successor_correction: >-
      R-3 in csia_semantic_core 2.1.1 (switch config_epoch): a record stamped
      with a configuration epoch is admitted only at the context's epoch;
      stale, ahead, unknown or malformed epochs are dropped when superseded
      or made UNAVAILABLE with their content cleared, and traced.
    historical_impact: >-
      None on recorded results: E1 is a shadow experiment, non-confirmatory.
      Replayed exactly under 2.1.1: 0 stale ticks and 0 valid records lost.
    xsys_impact: none. XSYS-001's records carry no epoch; unchanged.
    verdict: RECORDED
    consequence: >-
      Corrected in the 2.1.1 successor under an integration contract: the
      context must be supplied each tick, keyed on a monotonic counter, with
      a composite epoch across producer restarts. Fourteen adversarial
      variants show each broken clause reproduces at most the 2.1.0 behaviour
      (research/csia_semantic_core_2_1_revision/R3_CONFIGURATION_EPOCH.md).
    artifact: >-
      csia_semantic_core/admission.py; tests/test_semantic_core_2_1_revision.py;
      research/csia_semantic_core_2_1_revision/R3_CONFIGURATION_EPOCH.md
```

## 3. Not drafted as entries (design notes)

**Recorded here so the owner can disagree:**

| finding | why it is not drafted as a ledger entry |
|---|---|
| P5's decision clause superseded by R-1 | it is the approved decision change itself, not a failure. The replacement P5' holds and is pinned (`R1_FAULT_POLICY_B.md` §4) |
| two harness errors in this phase (the epoch-variant accounting; the order probe comparing presentation lists) | caught and corrected before any number was reported, and disclosed in `REVISION_REPORT.md` §10. The shadow study treated its own within-phase correction the same way |
| the fail-closed admission that can hide a symptom when the context is missing or a stamp is malformed | a property of the rule under a broken contract, measured and documented (`WORSE_ANSWER_SEARCH.md` §2.1); no recorded result is affected |
| pacing that does not follow the configuration (L21) | a scope boundary the revision stopped at, as the brief requires; it is a dependency, not an error |
