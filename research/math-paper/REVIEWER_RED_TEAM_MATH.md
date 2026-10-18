<!-- publication-guard: research-note -->
# REVIEWER RED TEAM — MATHEMATICAL PAPER

Companion to `research/systems-paper/REVIEWER_RED_TEAM.md`, same discipline.
Four reviewers, eleven objections.
Each objection carries: the claim challenged, the best version of the
criticism, the evidence response, the **remaining weakness** (never omitted),
and the manuscript change it forces.

An objection with no remaining weakness listed has been answered too easily.
Every objection below lists one.

> **The headline outcome is not flattering and is stated first.** This pass
> found a defect that would have been fatal in review: the paper's own §2
> defined its baseline in a way that made Propositions 1, 2, 5 and 6
> **vacuous for the system the paper is about**. It was not a presentational
> slip. It is fixed, the fix is a new proposition and a new section, and the
> paper now says out loud that the earlier reading was wrong.
>
> A second finding is a **negative result about one of the paper's own
> propositions**: the MAP-robustness condition provably cannot fire in the
> regime the project measures. That is now a proposition (P8) with a proof, a
> numeric check, and a Limitations entry.

---

## REVIEWER 1 — Bayesian statistics / methodology

### 1.1 "What is $q$? Under your own definition, $p = q$ and the paper is empty."

**Claim challenged:** everything. P1, P2, P5a, P5b, P6a, P6b, and the framing
of §9 as an *instance* of the framework.

**Best criticism.** §2 said `L_h` is "the likelihood of the **active**
(ungated) evidence". The system in §9 computes an additive score
`log L_h = Σ_j g_j ℓ_j(h)`. If `L_h` already means the gated score, the gate is
*inside* `L_h`; there is nothing left for `w_h` to carry; `w_h ≡ 1`;
`E_q[w] = 1`; `R = 0`; `p = q` identically. Every proposition in the paper is
then true and describes a reweighting by the constant 1. The worked example is
not an instance of the framework, and the framework has no instances at all.

**Evidence response.** **The criticism is correct and was not survivable by
rewording.** Both readings were computed. Reading A returns `w ≡ 1` exactly.
The framework applies under the full-evidence baseline, where

    w_h = exp( − Σ_j (1 − g_j) ℓ_j(h) )

which is hypothesis-dependent whenever a gated feature contributes differently
to two hypotheses. That is now Proposition P7 in `FORMAL_CORE.md` §9a and
Proposition 3 in the manuscript, with proof, and it is verified numerically at
`5.551e−16` (P7), `3.553e−15` (P7b) and `1.776e−15` (P7c).

**Remaining weakness. Two, and the second is serious.**

1. Under the full-evidence baseline, `q` is a **counterfactual**. The system
   does not compute it, and in the measured case it *cannot*: the gate closes
   because the receiver stopped reporting, so the withheld `ℓ_j(h)` has no
   observed value to take. P5 and P6 measure a distance to a reference point
   that is not evaluable.
2. A reviewer may reasonably say the framework is therefore an accounting
   identity rather than a measurement. **We do not have a rebuttal to that.**
   What we have is that the paper's *empirical* claim does not use `q` at all
   — P3 and P7c relate `p` to the prior, both of which the implementation
   holds — so a reviewer who rejects the baseline still owes an answer to the
   200-tick observation.

**Manuscript change. DONE.**
- New §2.1 "What $q$ is measured against, and why it matters", stating
  Reading A and Reading B side by side, and stating in bold that Reading A
  makes the paper vacuous — before a reader can discover it.
- The sentence *"An earlier draft of this paper defined $L_h$ that way and
  presented Section 9 as an instance of the framework; it was not one."*
- New Proposition (gated score) giving `w_h` in closed form and the
  withheld-contribution identity, and Corollary (pinned), recovering the
  pinning result from the gated form.
- New Remark (`r:counterfactual`) conceding weakness 1 in the body, not the
  Limitations list.
- **Abstract rewritten.** It carried the Reading A wording; fixing §2 and
  leaving the abstract would have left the defect in the first paragraph a
  reviewer reads.
- Limitations gains the counterfactual baseline as item 1.

### 1.2 "Every proposition is one line. Where is the paper?"

**Claim challenged:** that the manuscript is a paper rather than a note.

**Best criticism.** P1 is self-normalised importance weighting. P2 is its
logarithm. P5 is Jensen. P6b is "mean absolute deviation ≤ range / 2". P7 is a
reparameterisation. A theory venue will observe that the entire formal core is
a change of variables and that the interesting content is one systems
measurement.

**Evidence response.** Conceded in the manuscript itself, in a table, with
every row labelled KNOWN, and in the abstract's *"We claim no new
mathematics."* The claim is the runtime-diagnostic formulation, the
observation that the ignorability condition is **decidable statically from a
signature table before the system runs**, and the implemented instance.

**Remaining weakness. The objection may simply stand.** `NOVELTY_AUDIT.md` §4
already records this: whether a formulation plus a measured instance is enough
for a venue is an editorial judgement, and the audit's job is to stop the
paper overstating it, not to win the argument. No change can fix this, because
the honest answer is the one already printed.

**Manuscript change. NONE, deliberately.** Adding difficulty to make the
mathematics look harder is the failure mode this whole register exists to
prevent.

### 1.3 "P5a is the importance-sampling weight-degeneracy diagnostic. You cite a phrase, not a literature."

**Claim challenged:** the related-work coverage for P1 and P5.

**Best criticism.** `KL(q‖p) = log E_q[w] − E_q[log w]` is the standard
self-normalised-IS diagnostic, and `R` is a bounded-weight condition of the
kind used in that literature to control the estimator. The manuscript cites
"self-normalised importance weighting" as a phrase in a novelty table and
never engages the estimator literature it belongs to.

**Evidence response.** Partly conceded. The connection is real and the paper
gains nothing by ignoring it. What blocks the fix is not judgement but access:
**every bibliographic route out of this environment is denied** —
`api.crossref.org`, `doi.org` and `dblp.org` all fail at CONNECT — so a
citation added here would be an unverified string, and
`papers/BIB_VERIFICATION_LEDGER.yaml` exists precisely to stop that.

**Remaining weakness. This is an open hole, not a closed objection.** The
related-work section is thinner than it should be on the estimator side, and
we cannot close it from here. A reviewer is entitled to hold it against the
paper.

**Manuscript change. NONE — recorded instead.** Added as a row to
`NOVELTY_AUDIT.md` §5 rather than papered over with a citation nobody checked.
Inventing one to make the section look complete is the specific thing the
project's rules forbid.

---

## REVIEWER 2 — Missing data / coarsening

### 2.1 "C2 is CAR. Fine. Do you show your gate violates it, or only that a gate could?"

**Claim challenged:** the force of §5 and its caveat.

**Best criticism.** Stating that constancy of `w` is the ignorability
condition, and that a multivalued gate need not satisfy it, is a statement
about a hypothetical system. A referee wants the deployed one.

**Evidence response.** The deployed one is now exhibited. By P7,
`w_a/w_b = exp(−S)` with `S = Σ_j (ℓ_j(a) − ℓ_j(b))`, so `w_a ≠ w_b` exactly
when the withheld features distinguish the pair — which is the measured case.
The constancy condition fails, explicitly and computably, rather than
hypothetically.

**Remaining weakness.** Shown for **one pair on one layer**, under the
full-evidence baseline that Objection 1.1 leaves contestable. We do not show
the deployed gate fails the condition for all 28 pairs, and we do not claim
it: the checker reports that 27 of them never collapse.

**Manuscript change. DONE.** The §5 caveat now points at Proposition (gated
score) for the concrete `w`, and the §6 corollary is restated through
`D(a,b)` rather than through `w_a = w_b`, with a remark explaining why the
`w`-level statement is the wrong one to reach for under Reading B.

### 2.2 "Assumption 1 excludes $w_h = 0$, but a hard skip *is* $w_h = 0$."

**Claim challenged:** Assumption (strict positivity), and with it every
logarithm in the paper.

**Best criticism.** If the assumption excludes exactly the operation the
system performs, the paper's proofs do not apply to the paper's example.

**Evidence response.** **The criticism conflates two different zeros, and the
answer is favourable to us.** A closed gate is `g_j = 0`, giving
`w_h = exp(−ℓ_j(h))` — strictly positive and finite for any finite `ℓ_j(h)`.
What Assumption 1 excludes is a zero *likelihood*, `L_h = 0` or a divergent
`ℓ_j(h)`, which is an **exclusion** of a hypothesis rather than a gating of
evidence, and is a different operation with different semantics.
`FORMAL_CORE.md` §11 has said so since the first draft.

**Remaining weakness.** The distinction is stated in the formal core and was
*not* stated in the manuscript, where a reader meets Assumption 1 with the
word "skip" fresh in mind from §1. Being right in a supporting document is not
being clear in the paper.

**Manuscript change. DONE.** A sentence after Assumption 1 distinguishing a
closed gate from an excluded hypothesis.

---

## REVIEWER 3 — Formal methods / diagnosability

### 3.1 "This is structural isolability under a time-varying observation mask. That literature has it."

**Claim challenged:** the static-checkability contribution, and the related
work section.

**Best criticism.** `D(a,b) = (LOW(a) △ LOW(b)) ∩ ACTIVE` is a structural
detectability condition evaluated against a mask. Structural analysis for FDI
computes exactly such conditions, and the DES diagnosability literature covers
state-dependent observation maps. If the general mechanism is theirs, the
paper's contribution is a re-derivation with different notation.

**Evidence response.** The related-work section already cedes the general
mechanism — *"We assert no priority over the general mechanism"* — and names
state-dependent observation maps, intermittent and permanent loss, and sensor
failure. The stated difference is the setting: a continuous-signal Bayesian
layer in which applicability is hypothesis-relative and decided by the
diagnostic system itself, so the condition is a property of its configuration.

**Remaining weakness. We assert a difference of setting; we do not prove
non-subsumption.** Showing that no DES formulation expresses this would be a
real result and we do not have it. Worse, **every reference in that section is
unverified** for the egress reason in 1.3, so the paper's account of what the
prior art says rests on secondary descriptions.

**Manuscript change. NONE.** The concession is already in the text and
strengthening it further would overstate in the other direction.

### 3.2 "378,000 agreements between two implementations of the same definition validates nothing."

**Claim challenged:** the evidential weight of the checker comparison, quoted
in the abstract.

**Best criticism.** The independent checker and the production analysis both
evaluate `(LOW(a) △ LOW(b)) ∩ ACTIVE`. Agreement shows the two implementations
agree. If the signature table is wrong — if `LOW(h)` does not describe what
the features actually do — both are wrong together, 378,000 times, and the
number reads as validation while being a consistency check.

**Evidence response. Conceded in full.** The comparison tests the *reading*,
not the model. What the checker rules out is that the collapse claim is an
artefact of the production analysis pipeline: it imports none of it (a test
runs it in a fresh interpreter and asserts no diagnostic module reaches
`sys.modules`), and its input carries no leader, posterior or support label.
Whether the signature table is a faithful description of the sensors is a
separate question that no amount of agreement can answer.

**Remaining weakness. Nothing in the comparison validates the signature
table**, and the paper's whole structural argument is downstream of it. The
negative control on the current stack (0 collapses in 15,595 ticks) is
evidence that the predicate is not trivially true, which is weaker than
evidence that the table is right.

**Manuscript change. DONE.** §9 states what the agreement does and does not
establish, in the paragraph introducing the checker, rather than leaving a
reader to infer it from the caption.

---

## REVIEWER 4 — ADVERSARIAL / SELF

### 4.1 "Your MAP proposition is decoration. It cannot fire where you need it."

**Claim challenged:** Proposition (MAP robustness), and its presence in the
paper at all.

**Best criticism.** `R` is the spread of the *withheld* log-likelihood, so `R`
is largest exactly when the gate withholds most — the regime the paper is
about. A condition of the form `Δ > R` is therefore least likely to hold
precisely where a reader wants it. Including it without saying so flatters the
paper.

**Evidence response. The criticism is right, and it is sharper than the
reviewer put it — so we proved it.** For a pinned pair `a, b` with equal prior
mass that is the top two under `q`, write `S = Σ_j (ℓ_j(a) − ℓ_j(b))`. By P7,
`log w_a − log w_b = −S`, so `R ≥ |S|`; and `Δ = |log(π_a/π_b) + S| = |S|`.
Hence `Δ ≤ R` **always**, with equality attained. The condition can never
certify a pinned pair. That is P8 in `FORMAL_CORE.md` §9a, with proof, and the
audit measures worst slack `+8.882e−16` over the **2,282** sampled instances
in which such a pair was the top two — equality to floating-point precision,
zero violations.

**Remaining weakness. The equal-prior hypothesis is load-bearing, and the
escape is worse for us, not better.** Since `Δ ≤ |log(π_a/π_b)| + |S|`, the
condition `Δ > R` forces `|log(π_a/π_b)| > R − |S| ≥ 0` — the prior log-odds
must carry the whole excess unaided. It does happen: **1,224** of **20,130**
sampled instances under a lopsided `Dirichlet(0.3)` prior. When it fires, the
certificate was bought with prior mass rather than evidence, which is exactly
the quantity the paper's own §6 says carries no discriminating support.

**Manuscript change. DONE.** A remark after Proposition (MAP robustness)
giving the proof, the measurement and the escape; a row in the verification
table; and Limitations item 2: *"We have no MAP-stability result for the case
the paper is about."*

### 4.2 "Your §4 supporting document claims the skip makes $w_a = w_b$ 'by construction'. It does not."

**Claim challenged:** `FORMAL_CORE.md` §4, and with it the assertion that the
implemented case satisfies P3's hypotheses.

**Best criticism.** The *decision* to skip is hypothesis-blind. The *term*
skipped is not: removing feature `j` removes `ℓ_j(a)` from one score and
`ℓ_j(b)` from the other, and those differ exactly when `j` distinguishes the
pair. Under the full-evidence baseline the implemented case has `L_a ≠ L_b`
**and** `w_a ≠ w_b`, so neither of P3's two hypotheses holds.

**Evidence response. Conceded — this was our own error and it survived
because it is invisible from the conclusion.** The ratio *is* pinned; it is
pinned by the two inequalities cancelling exactly (`w_a/w_b = exp(−S) =
L_b/L_a`), not by both quantities being equal. The correct statement is P7c,
which reaches P3's conclusion from the gate condition instead of from
equalities that do not hold. A test now asserts that **both** P3 hypotheses
fail in the pinned construction, so the claim cannot return.

**Remaining weakness.** P3 stays in the paper as the abstract statement, so a
reader who stops at P3 gets a true proposition whose hypotheses the example
does not satisfy. The manuscript points §9 at the corollary and adds a remark
explaining the substitution, which is mitigation rather than removal.

**Manuscript change. DONE.** §9's bullet cites Corollary (pinned) instead of
Proposition (pinned to prior), with the parenthetical reason; `FORMAL_CORE.md`
§4 replaces the claim with a record of why it was wrong.

### 4.3 "You verify at $n = 4$ symbolically and $n = 5$ numerically and call it verification."

**Claim challenged:** §8 and Table 1.

**Best criticism.** The hand proofs are for general `n`. The symbolic pass is
`n = 4`. The numeric pass is `n = 5`. Nothing checks the general statement,
and the new propositions (gated score, MAP remark) are checked numerically
only.

**Evidence response.** Conceded and already flagged in Limitations item 1 of
the previous draft — "the hand proofs are general; the machine check is not" —
with the table's own caption repeating it.

**Remaining weakness. No general-`n` machine check exists**, and adding one
would require an induction the audit script cannot express.

**Manuscript change. DONE.** Limitations item 3 now names *which* results are
numeric-only, rather than leaving the reader to work it out from the table's
dashes.

### 4.4 "The audit's numbers move when you add an unrelated proposition."

**Claim challenged:** the reproducibility of every count the paper prints.

**Best criticism.** Adding the P7 block to `proof_audit.py` drew from the
shared generator and moved P4's published counts from **2,721 / 6,877** to
2,692 / 7,031. Nothing was wrong with either figure — which is exactly the
problem. A reader rerunning the audit after a later addition finds a number in
the manuscript that no longer reproduces, and cannot tell a stream shift from
an error.

**Evidence response.** Fixed structurally rather than by re-typing the
numbers: each proposition needing randomness beyond the shared instance draws
from its own generator. Restoring stream independence returned P4's counts to
**2,721 / 6,877** exactly, and every other reported deviation to its published
value, which is also the confirmation that the diagnosis was right.

**Remaining weakness.** The counts are still artefacts of one seed and carry
no meaning beyond "sufficient, not necessary". Stability is not significance,
and the manuscript should not be read as claiming otherwise.

**Manuscript change. NONE.** A test — `test_the_P4_counts_the_manuscript_
prints_are_stream_stable` — pins the two published counts, and the comment
above it says what to do if it ever fails: restore independence, or update the
manuscript, `FORMAL_CORE.md` and bindings PB-17/PB-18 together. Never the
artifact alone.

---

## WHAT THIS PASS DID NOT CLOSE

| open item | why it stays open |
|---|---|
| every citation is unverified | egress denies `api.crossref.org`, `doi.org`, `dblp.org`. `papers/BIB_VERIFICATION_LEDGER.yaml` records each one; no marker may be retired from this environment |
| the estimator-literature connection for P1/P5 (1.3) | cannot be cited without verification. Recorded in `NOVELTY_AUDIT.md` §5 |
| non-subsumption by DES / structural FDI (3.1) | asserted as a difference of setting, never proved |
| the signature table itself (3.2) | no amount of checker agreement validates it |
| `q` is counterfactual and unevaluable in the measured case (1.1) | intrinsic to the full-evidence baseline. P5 and P6 inherit it |
| no MAP result for the pinned regime (4.1) | P8 shows there cannot be one of P4's form |

**Nothing in the novelty table changed.** Every proposition was labelled KNOWN
before this pass and is labelled KNOWN after it. Finding holes in a paper that
claims no theorems does not create any.
