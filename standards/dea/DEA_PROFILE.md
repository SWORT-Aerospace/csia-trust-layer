# Diagnostic Evidence Assurance (DEA) — candidate profile v0.1

**Status: CANDIDATE. Not a standard, not submitted to any body, not endorsed by
one.** This document is a *draft profile* written to be reviewed and attacked.
Every requirement below is a proposal.

**Implementation-neutral by construction.** DEA does not standardise CSIA. A
conforming implementation may share no code, no architecture and no
mathematics with this repository; CSIA appears here only as one reference
implementation among several, and §9 lists a deliberately non-CSIA one.

---

## 1. Scope

DEA applies to a **diagnostic layer**: any component that consumes evidence
about a system and emits statements about that system's health, faults, or the
cause of an observed anomaly.

It says **nothing** about:

* how the diagnostic layer computes anything;
* what mathematics, model, or learning method it uses;
* what its thresholds are, or whether it has any;
* whether it is correct.

It constrains exactly one thing: **what a diagnostic layer is entitled to
assert, given the evidence it actually holds.**

## 2. The core safety property

> **DEA-CORE.** A diagnostic layer shall not assert a unique attribution unless
> it holds active evidence that separates the asserted hypothesis from every
> other hypothesis its own model admits.
>
> A ranking is not a separation. That one hypothesis scores highest is not
> evidence that the others are excluded.

Everything else in this profile is machinery for making DEA-CORE checkable.

### 2.1 Why this property and not the obvious one

The obvious rule — *"when a gate closes, trust shall decrease"* — is
**deliberately NOT in this profile**, and the reason is a measurement.

On both current-stack platforms, across a GNSS fix-loss fault, the gate weight
collapses to zero **and the trust coefficient rises**: ArduPilot 0.9213 →
0.9300, PX4 0.9856 → 0.9875. That is not a bug. Removing an inconsistent
comparison removes a source of disagreement, and a layer that scores agreement
will score higher with less to disagree about.

A standard containing "gate closure shall lower trust" would fail a correct
implementation for doing the arithmetic right, and would be met by
implementations that special-case the rule. The defect in that scenario is not
that trust rose; it is that the layer **kept asserting an attribution after the
evidence supporting it went away.** DEA-CORE names that directly.

## 3. Terminology

Defined here because the words are used inconsistently across the field, and
because the profile is unenforceable if `support` means two things.

| term | definition |
|---|---|
| **evidence item** | a comparison whose outcome is observable, together with the time it was observed |
| **active** | an evidence item is active at time *t* if it was observed within its declared freshness limit and its applicability conditions held |
| **hypothesis** | a candidate explanation the layer's model admits. The set of admitted hypotheses is part of the implementation, not of this profile |
| **separating evidence** | an active evidence item whose observed outcome is what the model predicts for one hypothesis and NOT what it predicts for the other. **Directional**: evidence *against* a hypothesis is not evidence *for* it, and an earlier draft of this row was ambiguous enough that the reference implementation got it backwards. Separation is relative to a declared model, never absolute |
| **support** | hypothesis *h* is supported at *t* if, for every other admitted hypothesis *h'*, at least one active evidence item separates *h* from *h'* |
| **attribution** | a statement naming one hypothesis as the explanation |
| **unassessable** | a state in which the layer holds insufficient active evidence to decide. Distinct from *healthy* and from *faulty* |
| **witness** | the record of which evidence items separated which hypotheses, produced at the moment of an attribution |

### 3.1 Words this profile forbids in a conformance claim

* **"confidence"** — used in the field for at least four different quantities
  (a posterior, a normalised score, a calibration statistic, a subjective
  degree of belief). A conformance claim using it is not checkable.
* **"posterior"**, unless the quantity really is one. An implementation whose
  output departs from a posterior — a floor inside a logarithm, a temperature,
  smoothing, a table-asserted hypothesis set — shall call it something else.
  CSIA calls its own output a **normalised hypothesis weight** for exactly this
  reason, and names its four departures.

## 4. Requirements

Each is stated so that a conformance test can return PASS, FAIL, INAPPLICABLE
or INCONCLUSIVE against it.

### DEA-1 — Declared hypothesis set
The implementation shall declare, in machine-readable form, the set of
hypotheses it admits. *Rationale: separation is relative to this set, so a
layer that will not state it cannot be assessed at all.*

### DEA-2 — Declared evidence model
For each hypothesis, the implementation shall declare which evidence items it
predicts, and how. *Rationale: without this, "separating" has no meaning.*

### DEA-3 — Freshness is explicit
Each evidence item shall carry a declared freshness limit, and the
implementation shall be able to report, for any *t*, whether the item was
active. *Rationale: an implementation that cannot say whether its evidence was
stale cannot be shown to satisfy DEA-CORE.*

### DEA-4 — Applicability is explicit
Where an evidence item is only meaningful under conditions (a speed gate, an
armed state, a flight phase), those conditions shall be declared, and the
implementation shall report whether they held. *Rationale: the failure this
profile exists for is a layer treating an INAPPLICABLE comparison as a passed
one.*

### DEA-5 — Support is computed, not assumed
The implementation shall compute support as defined in §3 and shall not
substitute rank, score, or margin for it.

### DEA-6 — Attribution requires support **(the enforceable form of DEA-CORE)**
The implementation shall not emit an attribution for hypothesis *h* at time *t*
unless *h* is supported at *t*.

### DEA-7 — Unassessable is reportable
The implementation shall be able to emit *unassessable*, and shall do so when
DEA-6 is not met. *Rationale: a layer with no way to say "I do not know" will
say something else.*

### DEA-8 — Witness on attribution
Every attribution shall be accompanied by a witness (§3, and
`schemas/support_witness.schema.json`) naming the competitor hypotheses and,
for each, the active evidence item that separated it. *Rationale: this is what
makes DEA-6 auditable after the fact rather than only at design time.*

### DEA-9 — Absence of evidence is not evidence of health
The implementation shall not emit a health assertion for a function whose
supporting evidence items are all inactive. *Rationale: this is the failure
mode the reference measurement in §2.1 exhibits.*

### DEA-10 — Silence is distinguishable
A consumer of the implementation's output shall be able to distinguish
"assessed and healthy" from "not assessed". *Rationale: DEA-9 is unenforceable
downstream if the wire format collapses them.*

## 5. Conformance verdicts

| verdict | meaning |
|---|---|
| `PASS` | the requirement was tested and held |
| `FAIL` | the requirement was tested and did not hold. **A witness of the failure is required** |
| `INAPPLICABLE` | the requirement does not apply to this implementation, with a stated reason |
| `INCONCLUSIVE` | the test could not be run, or the implementation did not expose what the test needs |

**`INCONCLUSIVE` is not a soft FAIL and not a soft PASS.** A conformance report
that has no `INCONCLUSIVE` verdict is more likely to have collapsed them into
`PASS` than to have tested everything. The runner reports the count separately
and refuses to compute a "conformance percentage" — see §7.

## 6. What conformance does NOT mean

Stated in the profile rather than in a footnote, because every conformance
regime is eventually quoted as if it meant more than it does.

* Conformance is **not correctness**. An implementation whose model is wrong —
  whose declared evidence predictions do not match physics — can conform
  perfectly. DEA constrains the relationship between evidence and assertion,
  not the truth of the model.
* Conformance is **not safety**. DEA is one property. A conforming layer can be
  unsafe for reasons DEA does not address.
* Conformance is **not certification**. No body has adopted this profile.
* Conformance is **relative to a declared model** (§3). An implementation that
  admits two hypotheses conforms more easily than one that admits twenty. The
  conformance certificate therefore records the size of the declared hypothesis
  set, and a reader must not compare certificates across different sets.

## 7. No conformance score

The runner does not compute a percentage, a grade, or a score, and this is a
requirement on the *runner*, not a stylistic choice.

A percentage invites two behaviours that destroy the regime: declaring
requirements INAPPLICABLE to raise the denominator, and shrinking the declared
hypothesis set to make DEA-6 easier. Both raise the number and lower what it
means. The certificate lists every requirement with its verdict and its
witness, and a reader who wants a summary must read them.

## 8. Reference implementations

| reference | role |
|---|---|
| CSIA (this repository) | one conforming implementation. Not the definition |
| `tools/dea/references/good_minimal.py` | a **non-CSIA** conforming implementation sharing no code with CSIA. Exists to prove the profile is not a description of CSIA |
| `tools/dea/references/bad_*.py` | eight deliberately non-conforming implementations, each violating a named requirement. Every one must be REJECTED by the runner |

The eight bad references are the load-bearing part of the test suite. A
conformance runner that passes everything is indistinguishable from one that
tests nothing, and the bad references are how that is measured.

## 9. Relationship to existing work

DEA claims no novelty in fault diagnosis, in consistency-based diagnosis, or in
sequential detection. Diagnosability, distinguishability and the requirement
that a fault be isolable from its alternatives are long-established; DEA's
contribution, if any, is narrow: **stating the entitlement condition as a
runtime obligation on the output, with a witness, so that it can be audited
after the fact.** Whether that is novel is a question for review, and the
prior-art matrix in `research/math-paper/PRIOR_ART_MATRIX.csv` is the current state of that
question. No entry in it has been verified against a publisher record — see
`USER_ACTION_REQUIRED.md` §B.

## 10. Open questions

Recorded because a draft that hides them wastes its reviewers' time.

1. **How is the hypothesis set bounded?** DEA-6 quantifies over "every other
   admitted hypothesis". An implementation with an open-world hypothesis set
   cannot satisfy that literally. CSIA has an `UNKNOWN` hypothesis; whether the
   profile should require one is unresolved.
2. **Partial separation.** DEA-6 is all-or-nothing. A layer separating *h* from
   19 of 20 competitors is currently non-conforming, with no way to express
   "supported against all but one". Whether a graded form is worth the loss of
   crispness is unresolved.
3. **Freshness under variable rate.** DEA-3 assumes a declarable freshness
   limit. For an evidence item whose source publishes at a rate that varies by
   an order of magnitude across platforms — the PX4 vs ArduPilot ESC telemetry
   difference is a real instance — a single limit is either too tight or
   meaningless. Unresolved.
4. **Witness cost.** DEA-8 requires a witness at every attribution. On a small
   embedded target that may be prohibitive. No profile-level allowance is
   currently made, and whether one should exist is unresolved.
