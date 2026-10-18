# R-1: dependency-sensitive predicate-fault policy B

**2026-10-01. Revision R-1 of the promotion-candidate brief, and its Phase 3.**
- **Switch:** `Corrections(fault_policy_b=True)`, part of `Corrections.revised()`.
  It is off by default, so `Corrections()` is still 2.1.0.
- **Code:** `csia_semantic_core/localization.py` (`fault_impact`, `_impact`,
  `localize_2_1`).
- **Tests:** `tests/test_semantic_core_2_1_revision.py`, the `test_r1_*`
  tests and `test_p5_prime_*`.

## 1. The rule

**The question asked of every failure:** could the failed predicate have
changed this conclusion?

**Where it is asked.** Per localization, for each failed predicate id and each
hypothesis that names it (as confirmer or refuter). The answer is one
`fault_impact` entry.

| role | the hypothesis is | dependency | action |
|---|---|---|---|
| REFUTER | rejected by another refuter that was measured True | NOT_MATERIAL | none |
| REFUTER | the SUPPORTED one | MATERIAL: had it been True it would have rejected it | SUPPORTED_WITHHELD |
| REFUTER | a survivor of a result that is not SUPPORTED | MATERIAL: its survival may rest on the fault | none (nothing was established) |
| CONFIRMER | rejected | NOT_MATERIAL | none |
| CONFIRMER | supported, and another confirmer is True (any-of) | NOT_MATERIAL | none |
| CONFIRMER | supported only through it | MATERIAL | SUPPORTED_WITHHELD |
| CONFIRMER | unresolved | MATERIAL: it may be why nothing confirmed it | none |
| either | unmodelled | NOT_MATERIAL: no predicate ever decides it | none |

**A withheld SUPPORTED:**
- gets the outcome **WITHHELD_PREDICATE_FAULT**, with reason
  FAILED_REFUTER_OF_SUPPORTED_HYPOTHESIS (or FAILED_CONFIRMER_…);
- keeps its survivors, unchanged;
- reads AMBIGUOUS in the 2.0 view, so a downstream consumer treats it as "no
  conclusion", never as NO_CONSISTENT;
- carries `withheld_because`, naming the predicate, the evaluated id, the
  hypothesis and the role.

**Unchanged:**
- **A localization that did not read the failed predicate** is untouched: the
  failure cannot have changed its conclusion.
- **The failure stays visible** in `predicate_errors` and in
  `evaluation: PREDICATE_FAULT`, exactly as in 2.1.0.
- **Attribution is never changed** by this rule. It reads records, not
  predicates, and the survivors F2 reads are unchanged.

**Why the confirmer rows rarely act.** Under the frozen elimination rule, a
None never confirms. So a SUPPORTED that needed the failed confirmer cannot
exist. Those rows are there so the trace answers "did it matter?" for every
failure, not because they withhold anything on the data.

**What is not here.** A tick is never invalidated by a predicate fault. A
structural fault (detector, index or attribution) still raises out of
`reason()` and becomes `shadow_fault` in the shadow runner, as before (L23).
B+U (withholding over a merely UNMEASURED refuter) is not adopted: the shadow
study priced it at zero on dataset A and left it to the admissibility work.

## 2. The six cases the brief asked for

Each case is a permanent test on a synthetic table, with real-tick versions
where the data has the case.

| case | test | result |
|---|---|---|
| refuter of the supported hypothesis | `test_r1_a_failed_refuter_of_the_supported_hypothesis_withholds_it`; `…_material_refuter_failure_never_creates_a_supported` | WITHHELD; 2.1.0 (policy A) leaves SUPPORTED |
| confirmer | `…_a_failed_confirmer_never_preserves_certainty_that_needed_it`; `…_another_true_confirmer_covers_is_not_material` | never SUPPORTED through a failed confirmer; covered confirmer NOT_MATERIAL |
| irrelevant | `…_an_irrelevant_failure_leaves_an_unrelated_conclusion_alone_and_visible` | the other symptom's SUPPORTED stands, with no fault on it; the failing symptom shows its fault |
| alternative domain | `…_alternative_domain_failure_on_a_rejected_hypothesis_is_not_material`; `…_alternative_domain_refuter_failure_only_widens` | NOT_MATERIAL when the hypothesis is rejected anyway; otherwise it only widens |
| shared by two hypotheses | `…_a_predicate_shared_by_two_hypotheses_gets_one_entry_per_hypothesis` | one entry per hypothesis, judged separately |
| several at once | `…_multiple_simultaneous_failures_are_each_judged_and_all_visible` | each judged; only the material one withholds; all visible |

**The four required properties:**
- **An irrelevant failure does not destroy unrelated conclusions:** 0 of
  75,752 IRRELEVANT pairs in dataset D lost anything.
- **A material refuter failure does not create a SUPPORTED:** 168 → 0.
- **A material confirmer failure does not preserve certainty:** no SUPPORTED
  rests on a failed confirmer.
- **Failures stay visible:** 15,118 of 15,118 evaluated faults.

## 3. Phase 3: the 68,640-injection replay

`fault_replay.py` reuses the shadow study's injection, roles and grading
(`predicate_fault_study.py`) by import. **PRE** must reproduce the shadow
result exactly, and does (`BASELINE_LOCK.json`, B1).

| configuration | injections | new wrong | fault-created SUPPORTED | correct SUPPORTED lost | correct UNIQUE lost | ticks with any conclusion lost | withheld | faults visible |
|---|---|---|---|---|---|---|---|---|
| 2.1.0, policy A (as committed) | 68,640 | **168** | **168** | 6,189 of 42,770 | 330 of 13,624 | 3,891 | 0 | 15,118 / 15,118 |
| reference policy B (post hoc) | 68,640 | 0 | 0 | 6,231 | 330 | 3,933 | 210 | 15,118 / 15,118 |
| reference policy C | 68,640 | 0 | 0 | 7,986 | 1,407 | 5,246 | 2,105 | 15,118 / 15,118 |
| reference policy D | 68,640 | 0 | 0 | 14,577 | 1,407 | 6,634 | 27,647 invalid | 15,118 / 15,118 |
| **2.1.1, R-1 only (implemented)** | 68,640 | **0** | **0** | **6,231** | **330** | **3,933** | **210** | **15,118 / 15,118** |
| 2.1.1 all revisions + r2, the 26 shared predicates | 68,640 | 0 | 0 | 8,377 of 59,410 | 330 of 15,730 | 4,056 | 294 | 17,400 / 17,400 |
| 2.1.1 all revisions + r2, PACING_INPUTS_NOMINAL failed | 2,640 | 0 | 0 | 123 of 2,285 | 81 of 605 | 123 | 0 | 123 / 123 |

**How to read it:**
- **The implemented policy equals the reference policy B, count for count.**
  The reference is the post-hoc `apply_policy("B")` the shadow study
  validated.
- **Every withhold is traced to a material refuter:** 210 of 210 carry a
  SUPPORTED_WITHHELD entry, and 0 were withheld without one.
- **By role:**
  - IRRELEVANT: 0 lost;
  - REFUTING_REJECTED: the 168, now withheld;
  - REFUTING_SUPPORTED: the 42 SUPPORTED that were right only because the
    failed refuter happened to be False, now withheld.
  The other 6,189 of the 6,231 are exactly policy A's losses: a failed
  confirmer or refuter widens the answer under any policy.
- **Under all revisions with r2 there are more pairs and more correct
  SUPPORTED.** That is because r1/r2 restore the COARSE_NAVIGATION
  localizations and R-2 restores process_stall. 0 fault-created SUPPORTED
  either way.
- **A fault in the new pacing predicate** turns the restored SUPPORTED
  process_stall back into AMBIGUOUS (starvation unresolved). It never creates
  a wrong answer.

## 4. The property P5 and its replacement P5'

**What the 2.1 suite's P5 asserts:**
- (a) a fault is reported wherever the predicate is evaluated;
- (b) a fault decides exactly what a None return decides.

**Why (b) cannot hold.** R-1 is, by definition, the rule that a FAULTED
refuter of the supported hypothesis withholds it, while a merely UNMEASURED
one does not. So under 2.1.1 the P5 test fails on (b).
- **This is the approved decision change itself, not a weakening.** It is
  what the owner adopted R-1 to do.
- **It is replaced by P5':**
  - (a) is unchanged;
  - (b') a fault never decides anything MORE certain than None. Every
    difference is a SUPPORTED withheld as WITHHELD_PREDICATE_FAULT with the
    same survivors, and attribution is identical.

**P5' over P5's own injection** (every base predicate raising on the final
tick of every shipped scenario, `property_rerun.p5_prime`):

| measure | result |
|---|---|
| injections | 1,144 |
| faults reported where evaluated | 376 of 376 |
| localizations identical to a None return | 2,335 |
| differences that are only a withheld SUPPORTED (each naming the fault) | 5 |
| differences that are more certain than None | **0** |
| attribution differences | **0** |

P5' is pinned in `tests/test_semantic_core_2_1_revision.py`.
