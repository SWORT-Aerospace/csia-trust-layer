# Ambiguity within the model versus failure of the model

Written on 2026-09-28. Source ids `Mnn` are defined in
`research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` §1. The notation
(`H*`, `Cons(E)`, V-joint, V-compound, V-equivalent) is from
`research/csia_model_inadequacy/PROBLEM_DEFINITION.md` §§2–3.

This is the core issue of the brief. The question is whether prior art
already formally separates two cases:

- **Case 1: ambiguity.** `E` is consistent with H2 and with H5. The output is
  AMBIGUOUS(H2, H5).
- **Case 2: model inadequacy.** `E` is inconsistent with every one of
  H1, …, Hn. The output is MODEL_INADEQUATE.

The prior art must also treat them as different conditions **at runtime**.

## 1. The distinction in four formal languages

| language | ambiguity within the model | failure of the model | insufficient evidence |
|---|---|---|---|
| set-valued / logical | `|Cons(E)| ≥ 2` | `Cons(E) = ∅` | no test bears on `H*` |
| belief functions, open world (M07) | mass on a non-singleton subset of the frame | mass on the empty set `m(∅)` | mass on the whole frame `m(Ω)` (ignorance) |
| probabilistic, with model criticism (M18, M19) | posterior spread over several models that fit | every candidate fails a posterior predictive / discrepancy check (M-open) | a flat likelihood |
| distance-based decision (M02) | the sample is close to several known classes: **ambiguity reject** | the sample is far from every known class: **distance reject** | (not treated) |

The belief-function row is the only one of the four that separates all three
conditions **inside one representation**:

- `m(∅)`: outside the frame;
- `m(A)` with `|A| ≥ 2`: ambiguous;
- `m(Ω)`: ignorance.

Under the open-world transferable belief model (TBM), `m(∅)` measures what
lies outside the frame, and `m(Ω)` measures ignorance (M07). No directly
matching work was identified in the searched sources that shows this
three-way reading was **operationalized in a flight system**. The formalism
itself has existed since 1990.

## 2. Where prior art makes the distinction, and whether it does so at runtime

| tradition | year | "ambiguous" is called | "model failed" is called | runtime? | source | level |
|---|---|---|---|---|---|---|
| reject option | 1970 | reject when the top classes are close | (not separated) | yes, per sample | M01 | V0 |
| decision with incomplete class knowledge | 1993 | **ambiguity reject** | **distance reject**: "the number of classes is not the true one" | yes, per sample | M02 | V0 |
| consistency-based diagnosis with behavioural modes | 1989 | several minimal diagnoses | only diagnoses that need the **unknown mode U(x)**, which "has no model" | yes (Sherlock) | M03 | V0 |
| GDE+ | 1989 | several fault-model explanations | with complete fault models, no consistent diagnosis ("physical negation") | yes | M04 | V0 |
| abductive diagnosis | 1991 | several explanations | no explanation exists; also "fails to explain too precise observations" (Cordier, 1998) | yes | M06 | V0 |
| open-world belief functions | 1990 | mass on non-singletons | **mass on ∅** | yes, at the combination step | M07, M08 | V0 |
| structured residuals / fault signature matrix | 1991– | a signature shared by several columns | a signature matching **no** column (unanticipated) | yes | M21 | V0 |
| MMAE | 1999 (M24) | probability spread across elemental filters | **all residuals inconsistent**: residual monitoring; new filters spawned | yes (VISTA F-16) | M24 | V0 |
| model invalidation | 2015–2018 | several fault models not invalidated (I-isolability) | **every model invalidated** (MILP infeasible) | yes | M26 | V0 |
| model criticism | 1980, 1996 | estimation within the model | criticism of the model; posterior predictive p-values | offline, applicable online | M18 | V0 |
| M-closed / M-open | 1994 / 2000 editions | model uncertainty inside the list | the true model is outside the list | conceptual | M19 | V0 |
| model discrepancy | 2001 | parameter uncertainty | a **model inadequacy** term | calibration | M20 | V0 |
| runtime model compliance (ModelPlex) | 2014– | (one model) | **non-compliance with the verified model**, then a provably safe fail-safe | yes | M27 | V0 |
| open-set recognition / open-set FD | 2013– | confusion between known classes | the unknown class (open-space risk) | yes | M14, M15 | V0 |
| conformal prediction | — (not dated in the searched summaries) | a set with several labels | **an empty set** | yes | M11, M12 | V0 |
| subjective logic / evidential DL | 2018– | **dissonance** | used as OOD through **vacuity** (see §5e) | yes | M09 | V0 |
| failure detection (ML) | 2023 | misclassification detection | OoD detection. The paper notes the two have been "largely separated research fields" | benchmark | M17 | V2 |
| receiver autonomous integrity monitoring (RAIM) / ARAIM | 2016 (ARAIM FDE, M35) | a fault detected but **exclusion** impossible | fault modes **outside the monitored threat model**, priced in the integrity allocation rather than detected | yes (detection), design (threat model) | M35 | V0 |
| SOTIF | — (ISO 21448; not dated in the summaries) | (known unsafe) | **unknown unsafe** (area 3) | design time | M36 | V0 |
| digital-twin validation | arXiv 2512.04117 | (fault detection in the asset) | **the twin is no longer representative**, kept separate from fault detection | yes | M39 | V0 |

## 3. Verdict on the key distinction

**Established. Status N0.**

- The separation of Case 1 from Case 2 is formal and runtime in:
  - M02 (1993): ambiguity versus distance reject;
  - M03 (1989): the unknown mode;
  - M07 (1990): the open world;
  - M21, M24 and M26 in fault detection and isolation (FDI), estimation and
    model invalidation.
- The statistical articulation is older still: estimation versus criticism
  (M18, 1980).
- The ML field is still unifying its versions of the two cases; M17 records
  this. That is a gap in ML evaluation practice, not an open problem in
  diagnosis.

The brief says Case 1 and Case 2 "must not be treated as the same condition".
The searched prior art agrees, and has said so for more than three decades.

## 4. The four-state assurance semantics: an established-vocabulary map

The brief warns: "Do not invent new vocabulary for established concepts".
Here are the established names:

| brief's label | consistency-based diagnosis (M03–M06) | D-matrix / IVHM reasoners (M33) | reject rules (M01, M02) | belief functions (M07, M09) | conformal (M11) | FDI / estimation (M21, M24, M26) |
|---|---|---|---|---|---|---|
| KNOWN_UNIQUE | a single minimal diagnosis, with fault modes that **explain** (abductive end) | an unambiguous failure mode, "responsible for all failed tests" | accept | mass concentrated on one singleton | a singleton set | a unique signature match; one model not invalidated |
| KNOWN_AMBIGUOUS | several minimal diagnoses | an **ambiguity group** | **ambiguity reject** | mass on a non-singleton set; dissonance | a multi-label set | a signature shared by several faults; several models not invalidated |
| MODEL_INADEQUATE | no consistent diagnosis without **U(x)** | UNCLEAR at V0 (whether conflicting test outcomes are reported as such) | **distance reject** | **m(∅) > 0** (open world) | an **empty set** | an unmatched signature; **all models invalidated**; NIS / residual inconsistency in every filter |
| INSUFFICIENT_EVIDENCE | no conflicts because no observations | test outcome **unknown**; component state **unknown** | (not treated) | **m(Ω)**; **vacuity** | (not distinguished from the empty set; see §5e) | not detectable / not isolable |

**Recommendation.**

- If CSIA or any later work ever emits these states, it should cite and use
  the established terms: "ambiguity reject / distance reject",
  "no consistent diagnosis (unknown mode)", "mass on the empty set",
  "empty prediction set", "vacuity".
- It should not introduce KNOWN_UNIQUE, KNOWN_AMBIGUOUS, MODEL_INADEQUATE or
  INSUFFICIENT_EVIDENCE as if they were new.
- The brief's labels are acceptable as **internal shorthand**, provided each
  one carries its mapping. Status: **N1** (terminological).

## 5. Where the distinction breaks: known caveats

None of these caveats is new. Together they are the reason the brief's safety
concern is real.

**a. Inadequacy is relative to the searched space `H*`.**

- Enlarging `H*` by combinations (M05) or by an unconstrained unknown mode
  (M03) makes `Cons(E) = ∅` rarer.
- An unconstrained U(x) is consistent with any observation. Diagnoses that
  use it are therefore always available, and are ranked by preference or
  probability rather than being ruled out.
- M37 documents the concrete consequence: a structural fault is "explained" as
  several component faults.

**b. Power.** A MODEL_INADEQUATE condition is detected only where some
available test has power against the out-of-library alternative. Robust FDI
states the trade-off directly: residuals must be insensitive to modelling
error and still sensitive to faults (M23).

**c. Observational equivalence: the V-equivalent case.**

- If the out-of-library cause produces evidence consistent with some `h ∈ H*`,
  no test on that evidence can distinguish them.
- 888T and Lufthansa 1829 (M52, M53) are of this kind, with respect to the
  voter's AOA evidence.
- The remedy is **more and dissimilar evidence**: analytical redundancy from
  the flight dynamics (M44). A better verdict label on the same evidence is
  not a remedy.

**d. Normalization erases Case 2.** Each of the following returns a confident
member of `H*` when `Cons(E) = ∅`:

- Dempster's normalized rule (M08);
- a softmax over known classes (M14, M15);
- MMAE posterior probabilities without residual monitoring (M24);
- "least-bad" estimator selection (M60).

This is **the** mechanism of "confident action on a wrong but best-fitting
modelled fault". The known remedies are:

- the unnormalized rule (M07);
- distance reject (M02);
- residual monitoring (M24);
- runtime compliance monitors with fail-safe (M27).

**e. Conflating inadequacy with insufficient evidence.**

- Evidential deep learning uses high **vacuity**, which is lack of evidence,
  as its OOD signal (M09). That conflates MODEL_INADEQUATE with
  INSUFFICIENT_EVIDENCE.
- Conformal empty sets can also arise from threshold effects in "genuinely
  hard regions" (M11).
- The TBM keeps `m(∅)` and `m(Ω)` apart (M07).
- The conflation is known and discussed in the uncertainty literature (M10,
  M17).
- CSIA has an analogous conflation (§7).

**f. Closed-loop masking.** Feedback control can make a faulted closed loop
behave like a healthy one, which shortens or removes the window in which
inadequacy is observable. Active fault detection counters this by modifying
the controller or injecting inputs (M43).

## 6. The second distinction: joint cross-system inconsistency

**The brief's example:**

- battery → H1;
- propulsion → H2;
- dynamics → neither completely;
- navigation → nominal.

In the notation of PROBLEM_DEFINITION.md §3 this is:

- `Cons(E_bat) = {H1, …}`;
- `Cons(E_prop) = {H2, …}`;
- `Cons(E_dyn)` is partial;
- `Cons(E_nav) = {nominal-compatible}`;
- the intersection is empty.

**Prior art.**

- **Consistency-based diagnosis** computes conflicts over **all**
  observations jointly (M03, M05). A conflict can involve components in
  several subsystems, each consistent with its own local data. Nothing in the
  definition restricts conflicts to one domain.
- **The open-world conjunctive rule** puts the joint contradiction of
  individually plausible sources on `m(∅)` (M07). Zadeh's two-expert example
  (M08) is the two-subsystem case. The failure of **normalized** combination
  there is the documented risk.
- **Multi-domain analytical redundancy relations.** Bond-graph GARRs relate
  electrical, mechanical and hydraulic variables in one relation (M48).
  Violation means that no mode consistent with the relation explains the
  cross-domain data.
- **The aircraft form.** AOA vanes are individually plausible and mutually
  consistent, yet inconsistent with inertial and flight-dynamics estimates.
  Detecting this is claimed in patents (M44).
- **Vehicle-level reasoners** fuse heterogeneous subsystem diagnoses (M34).
  Whether they report "subsystem conclusions jointly inconsistent" as its own
  output is UNCLEAR at V0.

**Verdict.**

- Status: **N0** in content.
- What the V-joint case demands is that the reasoner test the **conjunction**
  of the evidence against each hypothesis, not merely combine per-subsystem
  verdicts.
- That is an implementation property. Consistency-based diagnosis has it by
  construction. A per-symptom reasoner does not (CSIA today; §7).

## 7. CSIA against this map (V4, M62; descriptive only)

| state | what CSIA emits today | established equivalent | observation |
|---|---|---|---|
| KNOWN_UNIQUE | localization SUPPORTED: one survivor, affirmatively confirmed | a single diagnosis that **explains** (abductive end) | consistent with the established meaning |
| KNOWN_AMBIGUOUS | AMBIGUOUS | several minimal diagnoses / an ambiguity group | consistent |
| MODEL_INADEQUATE | UNSUPPORTED when every declared hypothesis is refuted (lines 321–326; the code comment calls it "a finding about the MODEL") | no consistent diagnosis (GDE+); distance reject | **the same token** is also emitted for "one unconfirmed survivor" (line 333), and `attribution.py` uses UNSUPPORTED for a third meaning (lines 11–13). Hypotheses marked `unmodelled` are never eliminated (line 299), so a symptom that declares one cannot reach this state |
| INSUFFICIENT_EVIDENCE | NO_EVIDENCE; unmeasurable predicates reported separately (`None`) | vacuity / `m(Ω)`; unknown test outcomes | consistent in spirit. "One unconfirmed survivor" arguably belongs here, not with MODEL_INADEQUATE |
| V-joint | not detected: `localize_all` localizes each symptom independently (lines 352–358) | CBD conflicts over all observations; `m(∅)` under conjunctive combination | an implementation gap relative to established methods |

These are **engineering observations** about conformance to established
semantics. They are not research findings, and nothing here proposes a
change. They are recorded in
`research/csia_model_inadequacy/USEFULNESS.md` §4.
