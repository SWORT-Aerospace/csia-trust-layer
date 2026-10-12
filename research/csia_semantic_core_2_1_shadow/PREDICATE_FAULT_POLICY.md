# Predicate-fault policy (G-3 / R9B)

**2026-09-30. Parts 10, 11, 12 and 48 of the shadow-validation brief.**
Dataset D is produced by `predicate_fault_study.py`. Results are in
`PREDICATE_FAULT_INJECTION_RESULTS.csv` (per role and policy) and
`PREDICATE_FAULT_RESULTS.json`.

## 1. The question

In 2.1 (C4), a predicate that raises is recorded and evaluates to None. The
localization's evaluation becomes PREDICATE_FAULT. **The verdict rule is
unchanged**, so a verdict may stay SUPPORTED over a faulted predicate. That
is R9B from the semantic audit.

**The question to settle:** did the failed predicate matter to the
conclusion? If it did, the conclusion should not stand as if it had not
failed.

## 2. What a fault can and cannot do, from the rules

This follows from the frozen elimination rule (`csia/v2/localization.py`
lines 282-335), which 2.1 keeps:

- **A hypothesis is rejected only by a refuter that is True.** A None never
  rejects, so a faulted predicate can never remove a hypothesis.
- **A hypothesis is supported only by confirmers that are True.** A None
  never confirms, so a faulted confirmer can only turn a SUPPORTED into
  something weaker.
- **So a fault can create unjustified certainty in exactly one way.** A
  faulted **refuter** of the hypothesis that ends up SUPPORTED would, had it
  evaluated, have been True and rejected it. Everything else a fault does
  widens the answer.
- **Attribution reads records, not predicates.** F2 can only withhold a
  UNIQUE, never grant one, so no predicate fault can create a wrong UNIQUE.
- **`X` and `X_FALSE` fail together**, because both are computed from one
  test (the successor rebuilds the negation from the base). A hypothesis
  confirmed by `X_FALSE` and refuted by `X` is therefore fully neutralised by
  one fault: it becomes unresolved, never supported. The dangerous case needs
  a hypothesis whose confirmer and refuter come from **different** base
  predicates.

**The existing trace is enough to decide "did it matter?".** Each
localization already records its predicate errors, with the ids each fault
made None and the hypotheses they touched (`PredicateError.evaluated_as`,
`.hypotheses`). The symptom table says which ids refute the supported
hypothesis. No new tracing is needed.

## 3. Injection (dataset D)

**What was injected.** On every tick of dataset A, every one of the 26 base
predicates was made to raise, one at a time: 68,640 injections and 90,870
(injection, localization) pairs. Five policies were applied to each single
faulted result.

**How roles were assigned.** Each pair's role comes from the **unfaulted**
result of the same tick. A pair can hold several roles; ALL counts each pair
once.

**Grading.** Ground truth is `ground_truth.py`. Units whose true hypothesis
the scenario does not state are counted but not graded (76,570 of 90,870 are
graded). "wrong" includes the answers that were already wrong without any
fault (3,032 pair-counts, identical in v2.0 and 2.1; see
`WORSE_ANSWER_SEARCH.json`, W2). The columns that measure the policy are
`new wrong`, `fault-created SUPPORTED` and `lost`.

| policy | new wrong | fault-created SUPPORTED | SUPPORTED resting on a failed refuter | correct SUPPORTED lost (of 42,770) | correct UNIQUE lost (of 13,624) | new wrong UNIQUE | ticks with any correct conclusion lost |
|---|---|---|---|---|---|---|---|
| **A** report only (2.1 today) | **168** | **168** | **210** | 6,189 | 330 | 0 | 3,891 |
| **B** dependency-sensitive | **0** | **0** | **0** | 6,231 | 330 | 0 | 3,933 |
| C downgrade on any fault | 0 | 0 | 0 | 7,986 | 1,407 | 0 | 5,246 |
| D invalidate the tick | 0 | 0 | 0 | 14,577 | 1,407 | 0 | 6,634 |
| B+U (B, plus unmeasured refuters) | 0 | 0 | 0 | 6,231 | 330 | 0 | 3,933 |

**By role (policy A unless stated; full table in the CSV):**

| role | pairs | what the fault does |
|---|---|---|
| CONFIRMING | 2,929 | loses correct SUPPORTED (1,645 of 1,687); never creates a wrong one |
| REFUTING_SUPPORTED | 3,501 | the SUPPORTED survives unrefuted: 42 pairs rest on the failed refuter. It was in fact False, so these are correct only by luck. B withholds exactly these 42 |
| REFUTING_REJECTED | 8,501 | **the only role that creates wrong answers: 168**, all described below |
| ALTERNATIVE_DOMAIN | 7,800 | widens only |
| MULTI_HYPOTHESIS | 4,491 | widens only |
| IRRELEVANT | 75,752 | nothing under A, B or C. **Under D, 6,591 correct SUPPORTED are lost that never read the failed predicate.** Policy D costs exactly this global failure |

**Error visibility.** Every fault that was evaluated is visible under every
policy: 15,118 of 15,118 pairs, through the localization's
`predicate_errors` and PREDICATE_FAULT status. A fault in a predicate no
localization evaluates on that tick is invisible, and correctly so: it did
not take part.

**The 168 wrong answers under A, all one mechanism.**

- **Where they are.** MS_A1_SENSOR_DELAY and MS_A2_COMMUNICATION_DELAY,
  POSITION_UNAVAILABLE on POSITION_HOLD and on PRECISION_NAVIGATION,
  42 ticks each.
- **The unfaulted answer is right.** It is UNSUPPORTED with every hypothesis
  rejected: the injected cause (a slow source, a transport delay) is not a
  POSITION_UNAVAILABLE hypothesis.
- **The fault removes one refuter.** Failing `NO_TIMING_SEGMENT_OVER_BUDGET`
  removes the refuter of TIMING/deadline_violation.
  `FUNCTION_TIMING_WITHIN_DEADLINE_FALSE` still confirms that hypothesis, so
  it becomes the only survivor and is SUPPORTED.
- **The SUPPORTED is wrong by definition.** TIMING/deadline_violation means
  "the deadline was missed with no segment over budget", and the injected
  segment is over budget.
- **One faulted predicate therefore turns a correct "no declared hypothesis
  fits" into a confident wrong cause.**

**Grading note.** The ground truth for these units was set to "no declared
hypothesis is true" from the hypothesis definitions, after the mechanism was
found. It is documented in `ground_truth.py`. Before that the units were
ungraded, and the same 168 appear as `fault_created_supported` either way.

## 4. Policy chosen: B, dependency-sensitive, with D only for structural faults

**It is chosen on the measurements, not on conservatism.**
- **B removes every fault-created SUPPORTED** (168 → 0) and every SUPPORTED
  resting on a failed refuter (210 → 0).
- **It costs 42 correct SUPPORTED more than A (0.1 %)** and no correct
  UNIQUE. Those 42 are exactly the ones that rested on the failed predicate.
- **C and D give no additional safety on this data.** C loses 1,797 more
  correct SUPPORTED than A and 1,077 more correct UNIQUE. D loses 8,388 more
  correct SUPPORTED, including 6,591 in localizations that never read the
  failed predicate.
- **B+U costs nothing here, but is not proposed.** It extends B to refuters
  that were merely unmeasured (a C2 None without a fault). In dataset A no
  SUPPORTED localization has an unmeasured refuter (0 of 1,928), so it costs
  nothing. Unmeasured is a different condition from faulted, however, and it
  is the admissibility work's to decide.

**The semantics, for adoption by a governed revision of 2.1.** The reference
implementation is `apply_policy` in `predicate_fault_study.py`; 2.1's
default is not changed here.

| question | rule |
|---|---|
| **When does a verdict stay admissible?** | A localization's verdict stands if no failed predicate is a refuter of a hypothesis it SUPPORTS. Faults in confirmers, in refuters of rejected or unresolved hypotheses, or in predicates it did not read, leave it admissible: they can only have widened it, and the trace shows they occurred. An attribution verdict stands whatever the predicate faults, because attribution reads records and F2 can only withhold |
| **When is it downgraded?** | A SUPPORTED whose hypothesis has a failed refuter becomes WITHHELD_PREDICATE_FAULT. Its survivors are unchanged; it is reported as not established. Downstream it counts as AMBIGUOUS, not as NO_CONSISTENT |
| **When is the tick invalid?** | Only for a structural fault: a failure outside the predicate wrapper (symptom detector, index construction, attribution). In the shadow runner that is `shadow_fault`. A predicate fault never invalidates the tick |
| **How does the trace show it?** | `predicate_errors` (predicate, evaluated ids, subject, error class, touched hypotheses) and `evaluation: PREDICATE_FAULT`, as today. B adds `withheld_because: FAILED_REFUTER_OF_SUPPORTED_HYPOTHESIS`, naming the refuter |
| **How should a consumer read it?** | See below |

**How a downstream consumer should read each state:**
- **PREDICATE_FAULT with the verdict standing:** "the conclusion holds; a
  monitor of the reasoner is broken". Raise the producer or predicate health
  issue; do not discount the conclusion.
- **WITHHELD_PREDICATE_FAULT:** "no conclusion". Treat it as missing
  diagnosis, not as nominal.
- **An invalid tick:** "no CSIA output for this tick".

## 5. Status

**Policy B is selected and validated in shadow on dataset D. It is not
adopted into 2.1.**
- **Adopting it changes decisions**, which needs the owner's approval, as C1
  to C6 did.
- **Until then 2.1 carries policy A**, whose measured weakness is the 168
  above.
- **The promotion review counts this as a revision 2.1 requires.**
