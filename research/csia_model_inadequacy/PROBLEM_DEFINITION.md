# Assurance under model incompleteness: problem definition

Written on 2026-09-28, as part of the model-inadequacy problem validation and
prior-art attack. Source ids `Mnn` are defined in
`research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` §1.

**Status.** This package does two things only: it validates the problem, and
it attacks the prior art.

- No CSIA code, architecture, simulator work, experiment or threshold was
  produced.
- No paper claim is made.
- XSYS-001, amendments A1 and A2, the confirmatory result, its manifests and
  the novelty audit were not modified. They were not reinterpreted either.
- The FAILURE_LEDGER was not appended.

**Context.**

- The CSIA-DX review ended in `CSIA_DX_PIVOT`
  (`research/csia_dx/CSIA_DX_REVIEW.md`). That decision is accepted and is
  not reopened here.
- The method changes with this package: **the unsolved problem comes first,
  and a CSIA solution second**.
- This document states the problem without reference to any CSIA mechanism.
  §6 records CSIA's current behaviour only as a baseline for the final report.

## 1. The question

A diagnostic reasoner holds a hypothesis library `H = {H1, …, Hn}`. It usually
reasons under the closed-world assumption `true state ∈ H`. Bayesian statistics
names this assumption **M-closed** (M19): the true model is in the candidate
list.

Real autonomous systems meet conditions outside any finite library, such as:

- unmodelled faults;
- compound faults;
- structural damage;
- software failures;
- correlated sensor failures;
- degraded physics.

A reasoner that keeps the closed-world assumption can force the evidence onto
the nearest modelled explanation, and then act on it confidently.

The candidate problem asks whether an autonomous system can, **at runtime**,
tell the following conditions apart:

| brief's label | condition |
|---|---|
| A: KNOWN + IDENTIFIABLE | one modelled hypothesis adequately explains the evidence |
| B: KNOWN + AMBIGUOUS | several modelled hypotheses remain consistent with the evidence |
| C: UNKNOWN / MODEL INADEQUATE | no modelled hypothesis adequately explains the evidence |
| (and) INSUFFICIENT EVIDENCE | the evidence does not bear on the hypotheses at all |

**These labels are working names from the brief.** This package does not
adopt them as new terms. `research/csia_model_inadequacy/AMBIGUITY_VS_MODEL_INADEQUACY.md`
§4 maps each one to the established vocabulary that already names it.

## 2. Definitions used by the attack

These definitions make the question precise enough to attack. They are not a
proposal.

Let `E` be the evidence. Let `H*` be the hypothesis space **the reasoner
actually searches**. That can be the single faults of `H`, the combinations up
to size `k`, or those plus an unconstrained "unknown" mode. Let `Cons(E)` be
the members of `H*` that are consistent with `E` under the reasoner's
adequacy test: a logical consistency check, a residual threshold, a
goodness-of-fit test, or a model-invalidation program.

| condition | set-valued form | probabilistic form |
|---|---|---|
| KNOWN_UNIQUE | `Cons(E) = {h}`, and `h` is affirmatively confirmed | one hypothesis passes an adequacy test, and it dominates the others |
| KNOWN_AMBIGUOUS | `|Cons(E)| ≥ 2` | several hypotheses pass; none dominates |
| MODEL_INADEQUATE | `Cons(E) = ∅` | every hypothesis fails its adequacy test (a posterior predictive or model-criticism check, M18) |
| INSUFFICIENT_EVIDENCE | every test that bears on `H*` is unmeasurable or uninformative | the likelihood is flat over `H*` |

Two qualifications follow from the definitions themselves.

- **Inadequacy is relative to `H*` and to the test's power.** "Inadequate
  relative to single faults" is not "inadequate relative to pairs". An
  out-of-library cause is detectable only where some available test has power
  against it.
- **Normalization destroys the MODEL_INADEQUATE condition.** A posterior
  normalized over `H*` always sums to one. The same holds for a softmax over
  known classes and for a selector that picks the least-bad candidate. Any of
  these turns `Cons(E) = ∅` into a confident choice of the best-fitting
  member. This is the mechanism behind the brief's safety concern. It is
  documented in PRIOR_ART_ATTACK.md §7.

## 3. The harder variants in the brief, and one added by this attack

**V-joint: every observation is plausible alone, but the joint story is not.**
Partition the evidence by subsystem into `E = E1 ∪ … ∪ Em`, for example
battery, propulsion, vehicle dynamics and navigation. The case is:

- every `Cons(Ei)` is non-empty;
- the intersection `Cons(E1) ∩ … ∩ Cons(Em)` is empty for the single-hypothesis
  library.

The brief's example has this form:

- battery evidence supports H1;
- propulsion evidence supports H2;
- vehicle dynamics support neither completely;
- navigation is nominal.

**V-compound: reality is a combination.** Reality is `H_motor + H_sensor`, but
the library holds only single faults. Two cases arise:

- **the weak case:** some combination of modelled faults explains `E`;
- **the strong case:** no combination of modelled fault modes explains `E`.

**V-equivalent: out-of-library reality looks like a library hypothesis.** This
variant was added by this attack.

- The true cause is outside `H*`, but `E` is consistent with some `h ∈ H*`.
- No test on `E` can then flag inadequacy. The out-of-library cause and `h`
  are observationally equivalent on the available evidence.

The documented aircraft cases in PRIOR_ART_ATTACK.md §7 (M52, M53) have this
form, **with respect to the voter's own evidence**. Two angle-of-attack vanes
froze at consistent values, so the single-sensor-fault model's best
explanation was "the third, healthy sensor is the faulty one".

## 4. What would make the problem unsolved

For CONTINUE, the attack would have to leave standing a runtime capability
that meets all of the following:

1. it separates KNOWN_AMBIGUOUS from MODEL_INADEQUATE;
2. it detects V-joint;
3. it handles V-compound without letting the combination space absorb the
   MODEL_INADEQUATE condition;
4. it prevents confident action on the best-fitting modelled hypothesis when
   the condition is MODEL_INADEQUATE;
5. the searched prior art does not already provide (1)–(4) in the sense that
   matters for autonomous aerospace.

It would also have to meet the brief's five CONTINUE conditions, which are
assessed in PRIOR_ART_ATTACK.md §9.

## 5. What this package does not do

- It does not design a CSIA solution. The brief says: "Do not design the CSIA
  solution yet."
- It does not treat the XSYS-001 result as evidence about out-of-library
  conditions.
  - XSYS-001 tested separation between **modelled** hypotheses (confirmatory
    result manifest `03f4fbfc…`).
  - It contained no out-of-library condition, so it says nothing about the
    MODEL_INADEQUATE condition.
- It does not coin vocabulary. Where a condition already has an established
  name, that name is used.

## 6. Baseline: what CSIA does today (V4, M62)

This section is descriptive only. It is needed to answer part H of the final
report. It is not a design.

- **Localization verdicts.** `csia/v2/localization.py` returns SUPPORTED,
  AMBIGUOUS, UNSUPPORTED or NO_EVIDENCE for each symptom.
- **When every declared hypothesis is refuted, the verdict is UNSUPPORTED.**
  The code comment at lines 321–326 calls this "a finding about the MODEL".
  This is the `Cons(E) = ∅` condition of §2.
- **The same UNSUPPORTED token also covers a second case.** When exactly one
  hypothesis survives unconfirmed, the verdict is also UNSUPPORTED (line 333).
  The token therefore mixes MODEL_INADEQUATE with "one unconfirmed survivor",
  which is closer to insufficient evidence.
  - `csia/v2/attribution.py` (lines 11–13) uses UNSUPPORTED for a third
    meaning: implicated by a relation, but no adverse evidence of its own.
- **Unmodelled hypotheses keep the all-refuted state from occurring.**
  Hypotheses flagged `unmodelled` are never eliminated (lines 196, 299). A
  symptom with such a hypothesis therefore cannot reach the all-refuted
  state. The condition surfaces as AMBIGUOUS, or as UNSUPPORTED with one
  survivor.
- **Localization runs per symptom.** `localize_all` (lines 352–358) localizes
  each symptom independently. Nothing checks that one hypothesis explains all
  symptoms jointly, so V-joint is not detected today.
- **Elimination needs a declared refuter.** A hypothesis is removed only when
  a predicate declared as its refuter is TRUE. An out-of-library cause
  therefore produces MODEL_INADEQUATE only if the declared refuters happen to
  fire against every modelled hypothesis.
