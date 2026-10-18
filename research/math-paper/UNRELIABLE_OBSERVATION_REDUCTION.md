# REDUCTION ATTEMPT — CSIA GATING → MAXIMUM-LIKELIHOOD DIAGNOSIS UNDER UNRELIABLE OBSERVATIONS

Peer-review hardening campaign, §21. This is a **novelty-killer test**, run
against the paper rather than for it. The question is not "how is CSIA
different?" — that question flatters the paper and can always be answered.
The question is: **can the CSIA setting be written as an instance of an
existing framework, and if so, which of the paper's statements does that
instance already contain?**

Target: Athanasopoulou, E., Li, L. and Hadjicostis, C. N., *Maximum Likelihood
Failure Diagnosis in Finite State Machines Under Unreliable Observations*,
IEEE Transactions on Automatic Control 55(3), 579–593, 2010.
`PRIOR_ART_MATRIX.csv` row status `CANDIDATE_UNVERIFIED`,
verification route `WEB_SEARCH_ONLY`.

> **READING STATUS, STATED FIRST BECAUSE IT BOUNDS EVERY CONCLUSION BELOW.**
> The paper has **not been read**. Every publisher host is blocked from this
> environment (`research/systems-paper/PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json`
> records the same blockage for the log corpus; the bibliography case is in
> `papers/BIB_VERIFICATION_LEDGER.yaml`). What is used below is the
> abstract-level description recorded in `PRIOR_ART_MATRIX.csv` row 3:
> a recursive algorithm choosing the most likely deterministic FSM given an
> observation sequence corrupted by **insertions, deletions and transpositions
> with known probabilities**. Statements about *their* theorems are therefore
> labelled and the verdict is conditioned on them.

---

## 1. What a reduction would have to exhibit

Write CSIA's per-tick object, in the paper's own notation
(`FORMAL_CORE.md` §1, §9a):

| CSIA | |
|---|---|
| hypotheses | `H`, finite, `π_h > 0` |
| per-feature log-likelihood | `ℓ_j(h)` |
| gates | `g_j ∈ [0,1]`, computed from the realised signal, **the same `g_j` for every `h`** |
| produced score | `log L_h^gated = Σ_j g_j ℓ_j(h)` |
| produced output | `p_h ∝ π_h exp(Σ_j g_j ℓ_j(h))` |
| reference point | `q_h ∝ π_h exp(Σ_j ℓ_j(h))`, the ungated **counterfactual** |
| validity factor | `w_h = exp(−Σ_j (1−g_j) ℓ_j(h))` (P7) |

A reduction must supply a map `Φ` from this data to their data — FSM models,
an observation sequence, a corruption law — such that

* **(R1)** their maximum-likelihood decision equals `argmax_h p_h`; and
* **(R2)** their framework *forms* the objects the paper's propositions are
  about, namely the pair `(p, q)` and the quantities
  `log(p_a/p_b) − log(q_a/q_b)`, `KL(q‖p)`, `TV(p,q)`, `R`.

(R1) alone is not subsumption of the paper. (R1) alone is subsumption of the
**decision rule**, which is not what the paper claims. Both are tested.

---

## 2. (R1) — the decision layer. IT REDUCES, and the reduction is trivial

Fix a tick. Take binary gates for the moment (`g_j ∈ {0,1}`) and let
`A = { j : g_j = 1 }` be the surviving feature set.

Map each hypothesis `h` to a model that emits the full feature vector, and take
the corruption law to be the **degenerate deletion channel** that deletes
exactly the complement of `A` with probability one and deletes nothing else.
Their likelihood of the observed sequence marginalises over corruption events
consistent with what was seen; with a degenerate law that sum has one term:

    P(observed | h) = P(delete exactly Aᶜ) · Π_{j∈A} exp(ℓ_j(h))
                    = κ · exp( Σ_j g_j ℓ_j(h) ) ,

with `κ` **free of `h`**, so it cancels in the argmax and in the normalisation.
Therefore `argmax_h P(observed | h) · π_h = argmax_h p_h`.

**(R1) holds.** CSIA's produced output is the posterior of a
deletion-corrupted observation model, at a degenerate setting of the
corruption law. This costs one line and it should be stated in the paper
rather than discovered by a reviewer.

Two riders, both honest:

* **The partial-gate case.** With `g_j ∈ (0,1)` the term is `g_j ℓ_j(h)`,
  which is a *tempered* contribution, not a marginalisation. A deletion channel
  emits or deletes; it does not emit a fractional symbol. So (R1) as written
  covers the binary corner. Whether their framework has a fractional analogue
  is unknown and **unread**. CSIA's gates are in `[0,1]` in general
  (`csia/diagnosis/bayes.py`, `ll[ci] += gate * (...)`), so the reduction is
  established for the binary corner only. This is a limitation of the
  reduction, not a defence of the paper.
* **The deployed layer is not literally this.** The shipped score applies an
  `EPS = 0.02` floor inside the log, exponential smoothing with
  `SMOOTH_ALPHA = 0.06` over ~15 ticks, and an `EVIDENCE_MULT = 1.5`
  tempering before the softmax. The reduction is to the paper's idealised
  additive model, not to the binary. That distinction is already the reason
  `research/PAPER_CROSS_CONSISTENCY.md` forbids calling the deployed output a
  posterior.

## 3. (R2) — the distortion layer. IT DOES NOT REDUCE, and the reason is not flattering either

Their framework ranks models given a corrupted stream. It does not form `q`.
Nothing in a maximum-likelihood decision procedure asks "what would the
posterior have been had the channel been perfect?", because a perfect channel
is not one of the objects being ranked.

**But this is a weak difference, and the paper must not lean on it**, for a
reason recorded in `FORMAL_CORE.md` §1.1: *we cannot form `q` either.* In the
case the systems paper measures, the gate closes because the receiver stopped
reporting, so the withheld `ℓ_j(h)` has no observed value to take. `q` is a
counterfactual reference point in our paper too. The honest statement of the
difference is:

> Their framework does not ask the question. Ours asks it and answers it only
> as an identity in an unobserved quantity.

That is a difference in *what is asked*, not in what either framework can
compute. It supports a framing claim and supports no mathematical claim
whatsoever.

## 4. The conditioning hypothesis that cannot be checked from here

The degenerate channel of §2 has a property their model may or may not permit:
**the deletion pattern is a deterministic function of the realised signal, and
in the case of interest it is caused by the same fault under diagnosis.** A
corruption model with *known probabilities* is normally a model of the
observation apparatus, fixed in advance and independent of the state; here the
"probabilities" are a point mass placed after the fact on what actually
happened, and their location depends on the fault.

Whether their theorems admit such a law — whether their misclassification
bounds hold when the corruption law is state-dependent and degenerate — is
**exactly the hypothesis this environment cannot check**. It requires reading
the paper.

**Two directions, and the conservative one is taken.**

| if their theorems admit it | if they do not |
|---|---|
| the reduction of §2 is a genuine instance, and any claim that CSIA's decision rule needs a new framework is dead | the reduction is a construction outside their stated hypotheses, and their results do not transfer to CSIA either |
| conservative for us: **kill the claim** | convenient for us: a real gap |

Under the standing rule — *if prior art subsumes a claim, kill the claim* —
the paper is written as though the left column holds. **No claim in the paper
may depend on the right column being true.** An audit of the manuscript
against this rule is §6 below.

---

## 5. VERDICT

**`PARTIALLY_SUBSUMES`.**

Precisely:

| layer | verdict | basis |
|---|---|---|
| the decision rule `argmax p` | **SUBSUMED**, conditional on §4 | §2, one line, our own construction |
| the produced output `p` as a posterior over a corrupted observation | **SUBSUMED**, conditional on §4 | §2 |
| the pair `(p, q)` and the distortion identities P2, P5, P6 | **NOT FORMED** in their framework | §3 — and this buys a framing point, not a theorem |
| the *mechanism* — applicability rather than noise | **DIFFERENT ASSUMPTIONS** | their unreliability is a channel with a known error law; CSIA's is a designed gate with no probability attached |
| the static-checkability reading (C3, `D(a,b)`) | **NOT ADDRESSED** in their framework as described | but see the caveat below |

The single verdict word is `PARTIALLY_SUBSUMES` rather than
`DIFFERENT_ASSUMPTIONS`, because `DIFFERENT_ASSUMPTIONS` would be the
self-serving reading: it is true of the mechanism and false of the decision
rule, and the decision rule is the thing a reviewer will test first.

**Caveat on the last row, and it is not small.** "Not addressed in their
framework as described" is a statement about a description, not about a paper.
It may not be printed as a gap. The static-checkability reading is defended in
`NOVELTY_AUDIT.md` §4 on its own terms and does not rest on this row.

## 6. WHAT THIS CHANGES IN THE MANUSCRIPT

| # | required | status |
|---|---|---|
| 1 | The related-work section must not say or imply that CSIA's produced output needs machinery outside the unreliable-observation literature. | **Already compliant.** `PRIOR_ART_MATRIX.csv` row 3 carries `claim_consequence` = "Do NOT claim CSIA handles a case they cannot; claim it is a different mechanism." |
| 2 | The "different mechanism" phrasing must not be read as "their formalism cannot express our decision rule". It can, degenerately. | **Tightened here.** The matrix row is amended to say so. |
| 3 | No claim may depend on their theorems *failing* to cover the state-dependent degenerate channel. | **Compliant.** No proposition in `FORMAL_CORE.md` cites them; every one is proved from A1–A4. |
| 4 | The reduction of §2 should appear in the paper as a remark, because a reviewer who finds it unaided will read its absence as concealment. | **Actioned** — see `papers/gate_conditioning/main.tex`, the remark labelled `r:marginal`. |

## 7. WHAT IT DOES NOT CHANGE

Nothing in `NOVELTY_AUDIT.md` §3. Every proposition was labelled **KNOWN**
before this reduction and is labelled KNOWN after it. A reduction that
confirms known things are known has found nothing new to concede.

The measured instance is untouched: `checker_verdicts.json`, 378,000 verdicts
out of 378,000, is a statement about a deployed layer and no reduction reaches
it.
