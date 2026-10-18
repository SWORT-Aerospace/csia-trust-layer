# REDUCTION ATTEMPT — CSIA GATING → COARSENING AT RANDOM

Peer-review hardening campaign, §22. Companion to
`UNRELIABLE_OBSERVATION_REDUCTION.md` (§21) and run under the same rule: the
test is whether an existing framework already contains the setting, not
whether a difference can be found.

Target: Heitjan, D. F. and Rubin, D. B., *Ignorability and Coarse Data*,
Annals of Statistics 19(4), 1991. `PRIOR_ART_MATRIX.csv` status
`CANDIDATE_UNVERIFIED`, route `WEB_SEARCH_ONLY`. Related and closer to the
framing: Speekenbrink & Visser, *State-Dependent Missingness in Hidden Markov
Models*, Psychometrika 2025 (`LOCATED_CORROBORATED_NOT_READ`).

> **READING STATUS.** Neither reference has been read. The characterisation of
> coarsening at random used below is the standard textbook one; it is not
> quoted from the source, and where a conclusion depends on the precise form
> of their condition it is marked `[CAR-DEF]` and may not be printed as a
> statement about their paper.

**This document contains the sharpest finding of the campaign, and it is a
correction to our own text, not to theirs.** §4 identifies a
mischaracterisation of Proposition C2 that has been in `FORMAL_CORE.md`, in
`NOVELTY_AUDIT.md` and in the manuscript since the first draft.

---

## 1. The map

| coarse-data framework | CSIA |
|---|---|
| full data `X` | the complete feature vector — every `ℓ_j(h)`'s argument, gated or not |
| coarsening variable `G` | the gate pattern; here binary, `G = A = { j : g_j = 1 }` |
| coarse observation `Y` | the pair `(A, x_A)`: which features survived, and their values |
| coarsening mechanism | `P(G = A \mid X, ψ)` |
| parameter of interest | the hypothesis `h ∈ H` |

The map is exact and requires no contrivance. **The gate is a coarsening
mechanism.** The manuscript already says so and this document does not
weaken it.

## 2. `p` is the coarse-data posterior. This is one line and it is the thing to worry about

CSIA's diagnosis is naive Bayes over the consistency signature
(`csia/diagnosis/bayes.py`, module docstring and `ll[ci] += gate * (...)`), so
the model asserts conditional independence of the features given `h`. Under
that assertion, for binary gates,

    Π_{j∈A} exp(ℓ_j(h))  =  Π_{j∈A} P(x_j \mid h)  =  P(x_A \mid h) ,

which is the **marginal likelihood of the surviving features** — precisely
what one obtains by integrating the withheld features out. Hence

    p_h  ∝  π_h · P(x_A \mid h) .

**So `p` is the correct Bayesian posterior given the evidence that survived,
provided the coarsening is ignorable.** It is not an approximation of `q`, and
it is not a corrupted `q`. Under CAR it is simply *the right answer to a
smaller question*.

### 2.1 The rejection hook this creates, stated in the reviewer's voice

> "The paper is called *Posterior Distortion*. But the produced quantity is
> the posterior given the observed subset. That is not distortion, it is
> information loss, and Proposition 2 is the statement that a smaller
> likelihood ratio yields a smaller log-odds shift. Reject."

**That objection is correct under CAR**, and the manuscript as drafted did not
pre-empt it. §3 is why it is not correct for the layer the systems paper
measures, and §6 records the remark added to the manuscript to say so.

## 3. Where CAR fails — and it fails for the reason CAR was invented to name

`[CAR-DEF]` Coarsening at random asks that `P(G = A \mid X, ψ)` depend on `X`
only through the coarse observation `(A, x_A)`; the coarsening probability may
not depend on the values that were coarsened away.

For the measured layer it depends on more than that, and the dependence runs
through the fault itself:

* Mechanism A, as recorded in `research/systems-paper/`: the gate closes
  **because the receiver stopped reporting**. The gate-closing event is caused
  by the very fault under diagnosis.
* Therefore `{G = A}` carries information about `h` that is not carried by
  `x_A`. CAR fails. The coarsening is **non-ignorable**.

`[CAR-DEF]` Under non-ignorable coarsening the correct posterior given
everything observed is

    p̃_h  ∝  π_h · P(x_A \mid h) · P(G = A \mid h) ,

and **CSIA's score contains no factor of the third kind.** Verified against
the implementation, not inferred: `step()` in `csia/diagnosis/bayes.py` skips
a gated feature (`if gate <= 1e-9: continue`), accumulates only
`gate * ℓ_j(h)`, and adds a **fixed** log prior (`PRIOR_NOMINAL = 0.86`, the
remainder split evenly). No term anywhere is a function of the gate pattern.

### 3.1 The three-way statement that replaces "distortion"

    q       the ungated counterfactual posterior      — not computable (§1.1)
    p       what CSIA produces                        — correct under CAR
    p̃       correct given the gate pattern too        — CSIA does not compute it

`p ≠ q` is information loss. **`p ≠ p̃` is the defect.** The paper's identities
quantify the first; the second is the reason the first matters operationally,
and the paper should say which is which.

**Scope discipline.** Naming `p̃` is a diagnosis, not a proposal. Nothing in
this campaign adds a gate-pattern term to CSIA, and no such change is
recommended here: estimating `P(G = A \mid h)` would require a model of gate
closure per hypothesis that the system does not have and that this project has
not validated. It is out of scope by the brief and it stays out.

## 4. CORRECTION — Proposition C2 is **not** the coarsening-at-random condition

`FORMAL_CORE.md` §5, `NOVELTY_AUDIT.md` §3 row C2, and the manuscript remark
`this is coarsening at random` all describe C2 as "recognisably the
ignorability condition for a coarsening mechanism". **That is imprecise, and a
reviewer with a missing-data background will catch it.**

| | condition | conclusion it licenses |
|---|---|---|
| CAR `[CAR-DEF]` | the coarsening probability does not depend on what was coarsened away | the mechanism may be dropped from the likelihood; inference proceeds with `P(x_A \mid h)`. **It does not give `p = q`** — information is still lost |
| C2 | `w_h = c` for all `h`: the withheld log-contribution is the same for every hypothesis | `p = q` exactly: **no** information about `h` was lost |

C2 is **strictly stronger and about a different object**. CAR is a condition on
the *mechanism*; C2 is a condition on the *withheld evidence*. Neither implies
the other:

* CAR can hold while `w` varies — a hypothesis-blind gate that nonetheless
  removes discriminating features. Mechanism ignorable, `p ≠ q`.
* `w` can be constant while CAR fails — the withheld features are
  non-discriminating, but the gate pattern is still caused by the fault. Then
  `p = q` and **neither equals `p̃`**.

The second row is not a curiosity. It is the case where a system looks
perfectly healthy by the paper's own criterion and is still wrong.

### 4.1 What the correction costs and what it does not

It costs the sentence, not the proposition. C2 remains **KNOWN** — it is one
line from P1 and always was. No novelty is created by the correction; if
anything it moves the paper further into known territory, because
"the missingness mechanism depends on the latent state" is exactly the
setting Speekenbrink & Visser examine (`PRIOR_ART_MATRIX.csv`, added
2026-09-04, and it narrows the paper).

---

## 5. VERDICT

**`SUBSUMES_FORMALISM`.**

The coarse-data framework contains the CSIA setting entirely: the gate is a
coarsening mechanism, `p` is the coarse-data posterior, and the ignorability
question is CAR's question. Nothing about the *setting* is outside it.

What is outside it, and the claim each supports:

| item | outside the formalism? | claim it supports |
|---|---|---|
| C2 as stated | it is a **different, stronger** condition, not a novel one | none — C2 stays KNOWN |
| the static-checkability reading (`D(a,b)` from the signature table) | not addressed in the framework as described | the paper's stated contribution, defended in `NOVELTY_AUDIT.md` §4 on its own terms |
| the measured instance (378,000/378,000) | a fact about a deployed layer; no formalism reaches it | the paper's empirical content |

`SUBSUMES_FORMALISM` is the harshest of the four available verdicts and it is
the correct one. The paper survives it because the paper does not claim the
formalism.

## 6. WHAT THIS CHANGES IN THE MANUSCRIPT

| # | change | status |
|---|---|---|
| 1 | Add the marginal-likelihood reading of `p` and pre-empt the "this is information loss, not distortion" objection. | **Actioned** — remark `r:marginal` in `papers/gate_conditioning/main.tex`. |
| 2 | Stop calling C2 "the ignorability condition". State the relation as in §4: CAR is the mechanism condition, C2 is the zero-loss condition, and they are different. | **Actioned** — the `r:car` remark is rewritten. |
| 3 | Name the sense in which the measured layer's coarsening is non-ignorable: the gate is caused by the fault, and no term scores the gate pattern. | **Actioned** — same remark, and it is a statement about our implementation, verified against it. |
| 4 | Do not add `P(G \mid h)` to CSIA. | **Held.** Out of scope by the brief; recorded in §3 as a diagnosis only. |

## 7. WHAT IT DOES NOT CHANGE

`NOVELTY_AUDIT.md` §3: every proposition was KNOWN before and is KNOWN after.
`proof_audit.py` is untouched — no proposition's statement changed, only the
prose that relates C2 to the missing-data literature. The frozen evidence is
untouched.
