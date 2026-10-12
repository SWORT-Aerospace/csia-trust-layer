# CSIA mathematical paper — canonical handoff

**For the mathematical-paper writing agent, who has no repository access.**
Self-contained: every proposition, assumption, verification number and
prior-art row is quoted from the artifact that holds it.

| | |
|---|---|
| repository HEAD | `228bebeb14395aebda60d76dbf6a54b292d0e344` |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| evidence freeze | `csia-dual-paper-evidence-freeze` = `eb2577d6830208b26d33facb283aa5be0ddf7c86` |
| tests | 1684 collected, all passing |
| build | `make paper-math` -> **10 pages**, all citations resolved |

---

## 1. Canonical manuscript

| | |
|---|---|
| **canonical source** | `papers/gate_conditioning/main.tex` — the ONLY canonical math manuscript |
| title | **Posterior Distortion from Hypothesis-Dependent Validity Gating in Runtime Diagnosis** |
| page count | **10** |
| bibliography | `papers/gate_conditioning/refs.bib` — 6 entries, **0 verified** |
| proposition ledger | `research/math-paper/FORMAL_CORE.md` §10 (**canonical**) |
| proof audit | `research/math-paper/proof_audit.py` -> `research/math-paper/results/proof_audit.json` |
| novelty audit | `research/math-paper/NOVELTY_AUDIT.md` |
| prior-art matrix | `research/math-paper/PRIOR_ART_MATRIX.csv` |
| artifact map | `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml` |
| red team | `research/math-paper/REVIEWER_RED_TEAM_MATH.md` |

### Superseded / non-canonical — never write from these

| path | status |
|---|---|
| `docs/math/PROOF_STATUS.md` | **A DIFFERENT BODY OF WORK.** It is the claim register for the ANYTIME-VALID e-process results (T-1…T-5, Ville's inequality, six refutations). It does **NOT** govern P1–P8. A reader who assumes it does will look for P3 there, not find it, and conclude something is missing. Nothing is |
| `docs/research/PAPER1_EMPIRICAL_SECTION.md` | belongs to THIS paper despite the "PAPER1" filename. Naming collision, recorded in the artifact map |
| `docs/math/T1_BLOCKWISE_EPROCESS.md`, `T2_MISSION_ERROR_CONTROL.md`, `ANYTIME_VALID_EVIDENCE.md`, `CSIA_EVIDENCE_FORMAL_SPEC.md` | formal sources for the e-process work, not for this manuscript |

### Current abstract (verbatim)

```
A runtime diagnostic layer decides, tick by tick, which of its evidence is
\emph{applicable}. That decision is a coarsening mechanism the system designed
for itself, and whether it may be ignored is a property of the software rather
than of the data. We give the exact algebra. Writing $q$ for the posterior the
system would have obtained from \emph{all} the evidence it could in principle
have scored and $p$ for the posterior it actually produces,
$p_h = q_h w_h / \mathbb{E}_q[w]$, so every pairwise log-posterior ratio
acquires an additive, evidence-independent offset $\log(w_a/w_b)$ that further
data of the same kind cannot argue with. For the additive gated scores runtime
layers compute, $w_h$ is exhibited in closed form and the offset is exactly the
withheld distinguishing contribution. When no active term distinguishes two
hypotheses their ratio is pinned to the prior ratio exactly, for as long as the
gate stays shut, however concentrated the posterior becomes --- a statement
about the produced posterior alone, which does not depend on the choice of
baseline.
We give the ignorability condition, its multivalued caveat, a sufficient
condition for the MAP to be unchanged, and exact divergence identities:
$\mathrm{KL}(q\Vert p)$ is precisely the Jensen gap of $\log w$ under $q$, so
the distortion is zero exactly when the validity factors do not vary across
hypotheses.

\textbf{We claim no new mathematics.} Each result is an instance of something
known --- self-normalised reweighting, coarsening at random, argmax stability
under bounded perturbation --- and the paper says so for each one. What we
offer is the runtime-diagnostic formulation, the observation that the
condition is decidable \emph{statically, from a signature table, before the
system runs}, and a deployed layer that fails it: an independently written
checker that imports none of the production analysis agrees with it on
$378{,}000$ of $378{,}000$ tick-by-pair comparisons and finds one hypothesis
pair pinned to its prior for $200$ consecutive ticks.
```

### Section structure

1. The problem
2. Setting — incl. **2.1 What `q` is measured against, and why it matters**
3. The reweighting identity
4. Pinning, and the condition that causes it — incl. **the gated-score form**
5. Ignorability, and a caveat that is easy to get wrong
6. Concentration is not discriminating support
7. MAP robustness
8. Exact divergences, and bounds
9. Verification
10. An implemented instance
11. What is new, stated plainly
12. Related work
13. Limitations
14. (unnumbered) A separate body of work, not in this paper

---

## 2. Canonical formal model

| symbol | meaning | assumption |
|---|---|---|
| `H = {h_1,…,h_n}` | finite hypothesis set, mutually exclusive | `n < infinity` (A2) |
| `pi_h` | prior on `H` | `pi_h > 0`, sums to 1 |
| `ell_j(h)` | feature `j`'s log-likelihood contribution under `h` | finite |
| `g_j in [0,1]` | the gate on feature `j` | `ACTIVE = {j : g_j > 0}` |
| `L_h` | likelihood of the **FULL** evidence, gated and ungated alike | `L_h > 0` (A1) |
| `w_h` | hypothesis-dependent validity factor: everything gating contributes to `h`'s score that is not in `L_h` | `w_h > 0`, finite (A1) |
| `q_h` | **posterior from the full evidence** — `pi_h L_h / sum_j pi_j L_j` | the BASELINE |
| `p_h` | **posterior actually produced** — `pi_h w_h L_h / sum_j pi_j w_j L_j` | what the system emits |
| `E_q[w]` | `sum_h q_h w_h` | normalizer |
| `R` | `log(w_max / w_min) >= 0` | the **log range** of the validity factors |
| `D(a,b)` | `{j in ACTIVE : ell_j(a) != ell_j(b)}` = `(LOW(a) △ LOW(b)) ∩ ACTIVE` | the **active distinguishing set** |

**A3 (no independence is assumed).** Nothing assumes the gate is independent of
the residual or of the fault. The gate may be an arbitrary function of the same
state the evidence is a function of. **That is the point**: the results are
about what happens *when* the gate depends on the state.

**A4 (`w` is exogenous to the algebra).** The propositions say what follows
*given* `w`; they do not model how `w` arises, except where a structural
condition is stated explicitly.

**A closed gate does not violate A1.** By the gated-score form below, a shut
gate gives `w_h = exp(-ell_j(h))`, strictly positive and finite. What A1
excludes is a zero *likelihood* — the **exclusion** of a hypothesis, a
different operation, out of scope.

---

## 3. THE BASELINE DEFECT, AND WHY IT MATTERED

This is the single most important thing in this handoff.

**The earlier draft defined `L_h` as the likelihood of the ACTIVE (ungated)
evidence.** The system in §10 computes an additive score
`log L_h = sum_j g_j ell_j(h)`. If `L_h` already means the gated score, then:

- the gate is **already inside** `L_h`;
- there is nothing left for `w_h` to carry, so `w_h == 1` identically;
- `E_q[w] = 1`, `R = 0`, and `p = q` identically;
- **P1, P2, P5a, P5b, P6a and P6b are all TRUE and all EMPTY** — they describe
  a reweighting by the constant 1;
- the worked example is not an instance of the framework, and the framework
  has no instances at all.

Both readings were computed. **Reading A returns `w == 1` exactly.**

The framework applies under **Reading B**, the full-evidence baseline. The
manuscript now states both readings side by side in §2.1 and says in bold that
Reading A makes the paper vacuous, *before a reader can discover it*, including
the sentence: *"An earlier draft of this paper defined `L_h` that way and
presented Section 10 as an instance of the framework; it was not one."*

### The derivation of `w_h`

```
log L_h^gated  =  sum_j g_j ell_j(h)
               =  sum_j ell_j(h)  -  sum_j (1 - g_j) ell_j(h)
               =  log L_h         +  log w_h

so             w_h = exp( - sum_j (1 - g_j) ell_j(h) )
```

which is strictly positive and finite for finite `ell`, so A1 holds. `w_h` is
hypothesis-dependent **precisely when some gated feature contributes
differently to two hypotheses** — the ordinary case, not a contrived one.

---

## 4. Proposition table — canonical status

| id | statement | assumptions | proof | runtime-evaluable? | novelty | check |
|---|---|---|---|---|---|---|
| **P1** | `p_h = q_h w_h / E_q[w]` | A1, A2 | one line, normalizers cancel | needs `q` — **no** | **KNOWN** — self-normalised importance weighting | symbolic exact + numeric 4.441e-16 |
| **P2** | `log(p_a/p_b) = log(q_a/q_b) + log(w_a/w_b)` | A1, A2 | logarithm of P1 | needs `q` — **no** | **KNOWN** (corollary of P1) | symbolic exact + numeric 1.776e-15 |
| **P3** | `L_a = L_b` **and** `w_a = w_b` ⇒ `p_a/p_b = pi_a/pi_b` | A1, A2 | apply P2 with a zero offset | **YES** — names only `p` and the prior | **KNOWN as algebra**; the runtime reading is the candidate contribution | symbolic exact + numeric 8.882e-16 |
| **P4** | `Delta > R` ⇒ `argmax p = argmax q` | A1, A2 | margin exceeds perturbation | needs `q` — **no** | **KNOWN** — argmax stability under bounded perturbation | numeric, held in 2,721/2,721 |
| **P5a** | `KL(q‖p) = log E_q[w] - E_q[log w]` (the Jensen gap) | A1, A2 | direct | needs `q` — **no** | **KNOWN** | symbolic exact + numeric 1.332e-15 |
| **P5b** | `KL(p‖q) = E_p[log w] - log E_q[w]` | A1, A2 | direct | needs `q` — **no** | **KNOWN** | symbolic exact + numeric 1.533e-15 |
| **P6a** | `\|log(p_a/p_b) - log(q_a/q_b)\| <= R`, **attained** | A1, A2 | immediate from P2 | needs `q` — **no** | **KNOWN** | 0 violations, max slack +1.776e-15 |
| **P6b** | `TV(p,q) <= (w_max - w_min)/(4 E_q[w])` | A1, A2 | MAD <= range/2 | needs `q` — **no** | **KNOWN**; **no sharpness claimed** | 0 violations, max slack -8.381e-05 |
| **P7** | gated additive score ⇒ `w_h = exp(-sum_j (1-g_j) ell_j(h))` | A1, A2, additive score | reparameterisation | **YES**, given `ell` and `g` | **KNOWN** — log-linear reparameterisation | numeric 5.551e-16 |
| **P7b** | `log(p_a/p_b) - log(q_a/q_b) = -sum_j (1-g_j)(ell_j(a) - ell_j(b))` | as P7 | P7 then P2 | **YES** | **KNOWN** | numeric 3.553e-15 |
| **P7c** | every distinguishing feature gated ⇒ `log(p_a/p_b) = log(pi_a/pi_b)` | as P7 | corner of P7b | **YES** — **THIS IS THE ONE THE SYSTEMS PAPER MEASURES** | **KNOWN** (corner of P2); it **supersedes P3** as the statement the implemented case satisfies | numeric 1.776e-15 |
| **P8** | pinned pair with equal prior mass, top two under `q` ⇒ `Delta <= R`, so **P4 can never certify it** | as P7, plus `pi_a = pi_b` | see §6 | **YES** | **KNOWN as algebra**, and a **NEGATIVE result about P4** | 0 violations over 2,282 instances, max slack +8.882e-16 |
| **C2** | `w_h = c` for all `h` ⇒ `p = q` identically | A1, A2 | `E_q[w] = c` | — | **KNOWN** — coarsening at random (Heitjan & Rubin 1991) | symbolic exact |
| **C3** | `D(a,b) = ∅` ⇒ ratio pinned **regardless of `max_h p_h`** | as P7c | P7c; concentration plays no role | **YES** | **KNOWN as algebra**; the diagnostic distinction is the candidate contribution | via P7c |

### The honest summary

- **REFUTED**: none in this paper. (Six refutations exist in the *e-process*
  register, which is a different body of work.)
- **WITHDRAWN**: none.
- **KNOWN**: **every proposition.** `NOVELTY_AUDIT.md` states *"Every
  mathematical proposition in this paper is labelled KNOWN"*, and a test
  asserts each id appears in that table.
- **SUBSUMED**: P3 by P7c for the implemented case — P3 remains true and
  remains the abstract statement.
- **PROVED, NOVELTY NOT ESTABLISHED**: none claimed as such.
- **POSSIBLE NOVEL CONTRIBUTION** (the only claim the paper makes): the
  runtime-diagnostic **formulation**; the observation that the ignorability
  condition is **decidable statically from a signature table before the system
  runs**; and the implemented instance. Whether that suffices for a venue is
  an editorial judgement the audit deliberately does not try to win.

### Symbolic pass (sympy 1.14.0, n = 4, exact)
- `C2_constant_w_implies_p_equals_q` — exact, verified
- `P1_reweighting_identity` — exact, verified
- `P2_log_ratio_identity` — exact, verified
- `P3_pinned_to_prior` — exact, verified
- `P5a_KL_q_p_is_jensen_gap` — exact, verified
- `P5b_KL_p_q_identity` — exact, verified

P4, P6a, P6b, P7, P7b, P7c and P8 are **numeric only**; the manuscript's
Limitations says which, and there is no general-`n` machine check.

---

## 5. P7 / P7b / P7c — exact statements and verification

**Proposition P7 (gated score).** Let the score be additive over per-feature
terms, `log L_h^gated = sum_j g_j ell_j(h)` with gates `g_j in [0,1]`, and let
`q` be the posterior from the ungated score (`g_j == 1`, Reading B). Then `p`
is the self-normalised reweighting of `q` by
`w_h = exp(-sum_j (1-g_j) ell_j(h))`, P1 applies, and P7b holds for any pair.

*Proof.* `log L_h^gated = sum_j ell_j(h) - sum_j (1-g_j) ell_j(h) = log L_h +
log w_h` with `w_h` as above, strictly positive and finite, so A1 holds. Apply
P1, then P2. ∎

**P7b in words.** The shift is **exactly the withheld distinguishing
contribution**. A fully open gate contributes all of its term, a fully closed
one none, a partial gate in proportion.

**Corollary P7c.** If `g_j = 0` for every `j` with `ell_j(a) != ell_j(b)`, then
`log(p_a/p_b) = log(pi_a/pi_b)`.

*Proof.* By P7b, `log(p_a/p_b) = log(pi_a/pi_b) + sum_j g_j (ell_j(a) -
ell_j(b))`, and every surviving summand has `ell_j(a) = ell_j(b)`. ∎

| proposition | numeric worst deviation | symbolic |
|---|---|---|
| **P7** `P7_gated_score_is_a_reweighting` | **5.5511e-16** | not run |
| **P7b** `P7b_shift_is_the_withheld_contribution` | **3.5527e-15** | not run |
| **P7c** `P7c_pinned_when_all_distinguishing_gated` | **1.7764e-15** | not run |

**VERIFIED against the brief's expected values.** 5.551e-16 -> P7,
3.553e-15 -> P7b, 1.776e-15 -> P7c. The mapping is confirmed; the brief had it
right. Trials: 20,000 instances, 5 hypotheses each, seed 20260903.

### **P7c replaced the old P3 pointer — VERIFIED**

Under Reading B, in the measured case, **both of P3's hypotheses are FALSE**:
skipping feature `j` removes `ell_j(a)` from one score and `ell_j(b)` from the
other, and those differ exactly when `j` distinguishes the pair. So
`L_a != L_b` **and** `w_a != w_b`, and the ratio is pinned anyway, because
`w_a/w_b = exp(-S) = L_b/L_a` with `S = sum_j (ell_j(a) - ell_j(b))`. The two
inequalities cancel exactly.

An earlier version of `FORMAL_CORE.md` §4 claimed CSIA's skip makes
`w_a = w_b` "by construction". **That was wrong and is recorded as wrong.** The
*decision* to skip is hypothesis-blind; the *term* skipped is not. Every
document that pointed at P3 as the statement the systems paper measures was
repointed at P7c (`MECHANISM_A.md`, `PAPER_RELATIONSHIP.md`,
`REVIEWER_RED_TEAM.md`, `CURRENT_STACK_BLOCKERS.md`), and **no number changed**.

A test asserts that both P3 hypotheses fail in the pinned construction, so the
claim cannot return.

---

## 6. P8 — the negative result about P4

**Proposition P8.** Let `a, b` be a pinned pair (every distinguishing feature
gated shut) with `pi_a = pi_b`, and suppose they are the top two under `q`.
Then `Delta <= R`, with equality attained. Consequently **P4 can never certify
a pinned pair.**

*Proof.* Write `S = sum_j (ell_j(a) - ell_j(b))`. Every `j` with
`ell_j(a) != ell_j(b)` has `g_j = 0`, so by P7
`log w_a - log w_b = -sum_j (1-g_j)(ell_j(a) - ell_j(b)) = -S`, giving
`R = log w_max - log w_min >= |log w_a - log w_b| = |S|`. Since `a, b` are the
top two under `q`, `Delta = |log(q_a/q_b)| = |log(pi_a/pi_b) + S| = |S|` using
`pi_a = pi_b`. Hence `Delta = |S| <= R`. Equality holds when the pair attains
the extremes of `w`. ∎

**VERIFIED — every element of the chain confirmed:**

| element | value |
|---|---|
| `Delta = |S|` for equal priors | confirmed algebraically and numerically |
| `R >= |S|` | confirmed |
| therefore `Delta <= R` | confirmed |
| **sampled instances where a pinned equal-prior pair was the top two** | **2,282** |
| **violations beyond 1e-9** | **0** |
| **worst slack `Delta - R`** | **+8.8818e-16** — equality to floating-point precision |

The brief's figures (2,282 instances, 0 violations, ~8.88e-16 slack) are
**correct**.

### The unequal-prior escape — VERIFIED

Dropping `pi_a = pi_b` lets the condition fire, and **that makes P4 look worse,
not better**. Since `Delta <= |log(pi_a/pi_b)| + |S|`, the condition `Delta > R`
forces `|log(pi_a/pi_b)| > R - |S| >= 0`: the prior log-odds must carry the
entire excess unaided.

| element | value |
|---|---|
| draws | 200,000 |
| prior | `Dirichlet(0.3), deliberately lopsided` |
| **pinned pairs that were the top two** | **20,130** |
| **P4 condition fired anyway** | **1,224** |
| fraction | 0.0608 |

The brief's figures (1,224 / 20,130) are **correct**.

**Interpretation, for the manuscript.** When P4's condition fires on a pinned
pair, the certificate was bought with **prior mass, not evidence**. C3 has
already said what such a MAP is worth as discriminating support: nothing. So
the escape does not rescue P4 in the regime the project cares about; it
identifies the escape as diagnostically empty.

**Consequence to state in Limitations.** `R` is the spread of the *withheld*
log-likelihood, so it is **largest** exactly where the gate withholds most —
the regime this paper is about. P4 is informative when the gate withholds
little, which is when the phenomenon is absent. **There is no MAP-stability
result for the pinned regime, and P8 shows there cannot be one of P4's form.**

---

## 7. The counterfactual `q`

| question | answer |
|---|---|
| what `q` represents | the posterior the system **would have obtained from all the evidence it could in principle have scored** — the full-evidence baseline, Reading B |
| when `q` is observable | when every feature is ungated and every `ell_j(h)` has an observed value |
| when `q` is counterfactual | whenever a gate is shut. `q` is generally **not computable at runtime** |
| why fix loss makes it non-evaluable | the gate closes **because the receiver has stopped reporting**, so the withheld `ell_j(h)` has **no observed value to take**. There is nothing to plug in, not merely something the system declines to compute |
| propositions that inherit the limitation | **P1, P2, P4, P5a, P5b, P6a, P6b** — every result that mentions `q` |
| results that do **NOT** require evaluating `q` | **P3, P7c and C3.** They relate `p` to the **prior**, and the implementation holds both. Also P7 and P7b as *definitions* of `w_h` in terms of `g` and `ell` |

**Why this matters for the paper's defence.** A reviewer who rejects Reading B
entirely still owes an answer to §10, where a weight ratio sat at its prior
value for 200 consecutive ticks. What such a reviewer takes away is the
*quantitative apparatus* — P5 and P6 measure a distance to a baseline that
cannot be evaluated — not the empirical claim.

### The manuscript's own limitation paragraph, verbatim

```
\begin{remark}[$q$ is counterfactual, and the main claim does not need it]
\label{r:counterfactual}
Under Reading B the baseline $q$ is generally \emph{not computable at runtime},
and in the case Section~\ref{sec:instance} measures it is not computable at
all: the gate closes because the receiver has stopped reporting, so the
withheld $\ell_j(h)$ has no observed value to take. $q$ is a reference point,
not a quantity we claim to evaluate, and $w_h$ is the exact bookkeeping of what
separates the two --- no more than that.

This matters less than it appears, because \textbf{the paper's empirical claim
does not mention $q$}. Proposition~\ref{p:pin} and Corollary~\ref{c:pinned}
relate $p$ to the \emph{prior}, both of which the system computes. A reader who
rejects Reading B entirely still owes an answer to Section~\ref{sec:instance},
where a posterior ratio sat at its prior value for $200$ consecutive ticks.
What such a reader loses is the quantitative apparatus ---
Propositions~\ref{p:kl} and \ref{p:bounds} measure a distance to a baseline,
and a baseline that cannot be evaluated cannot be measured against.
```

---

## 8. Support definition — no threshold, and the observations that show it

**The canonical structural definition.** `D(a,b) = (LOW(a) △ LOW(b)) ∩ ACTIVE`,
where `LOW(h)` is the feature set hypothesis `h` drives low and `ACTIVE` the
set of features whose gate is open. `D(a,b) = ∅` means no active feature
distinguishes the pair.

**NO weight threshold, and no posterior threshold, is any part of support.**
The implementation confirms it twice:

- `csia/v1_1/eligibility.py` fires `SUPPORT_LOST_FOR_REQUIRED_INFORMATION` on
  `sensitive_hypotheses ∩ non_identifiable_against` **alone**;
- `engineering/v1_1/support/support.py` says why in its own comment:
  *"Spec section 5: identifiable against EVERY other modeled hypothesis. No
  filtering by posterior mass — that would make identifiability depend on the
  score whose support is in question."*

**The false statement is GONE — verified.** The manuscript previously said
support is withheld for *"a leader above 0.999"*. A grep for `leader above
0.999` in `papers/gate_conditioning/main.tex` returns **0 matches**. The
sentence now reads that the rule fires *"at any posterior value, because no
posterior threshold enters the rule at all"* (which the terminology policy will
change from "posterior" to "weight" — see §11).

### The observed range — these are OBSERVATIONS, not thresholds

| | |
|---|---|
| artifact | `engineering/v1_1/SUPPORT_STATE_RESULTS.csv` |
| rows where the structural condition fires | **44** (non-empty `non_identifiable_against`) |
| **minimum leader weight** | **0.969087** -> quoted as 0.9691 |
| **maximum leader weight** | **0.999822** -> quoted as 0.9998 |
| all such rows labelled | `NON_IDENTIFIABLE` |

A rule gated at 0.999 would have **passed most of these 44 ticks**. That is the
observable form of "no threshold": the wide span is the evidence that no gate
is there. Both endpoints are bound as scalars `GS01` and `GS02` in the artifact
map and guarded by `tests/test_support_state_posterior_range.py`.

---

## 9. Prior-art matrix — all 18 rows

**Every row is `WEB_SEARCH_ONLY` for its verification route.** No row has been
confirmed against a publisher record from this environment. **Novelty must not
be inferred from `NOT_FOUND`.**

| topic | status | reference | closest CSIA statement / difference |
|---|---|---|---|
| bounded likelihood ratios | **NOT_FOUND_NEEDS_HUMAN** | Rukhin-type bounded-likelihood-ratio information bound (named in the brief). | P6a/P6b sharpness. — *Unknown.* |
| likelihood reweighting | **CANDIDATE_UNVERIFIED** | Self-normalised importance sampling / importance-weighted variational inference (standard; multiple sources returned, no | P1, P5a, P5b. — *None mathematically. CSIA's w arises from a runtime validity gate rather than from a proposal distribution.* |
| loss of observations | **CANDIDATE_UNVERIFIED** | Carvalho, L. K., Basilio, J. C. and Moreira, M. V. Robust diagnosis of discrete event systems against intermittent loss  | The systems paper's Mechanism A: gating removes the discriminating evidence. — *CSIA's loss is hypothesis-relative applicability decided by the diagnostic layer itself, not channel loss imposed from outside.* |
| maximum-likelihood diagnosis under unreliable observations | **CANDIDATE_UNVERIFIED** | Athanasopoulou, E., Li, L. and Hadjicostis, C. N. Maximum Likelihood Failure Diagnosis in Finite State Machines Under Un | P1/P2: the produced posterior is a reweighting of the active-evidence posterior. — *Their unreliability is a NOISE model over observations with a known error distribution. CSIA's is APPLICABILITY: the observation i* |
| missing data / selection mechanisms | **CANDIDATE_UNVERIFIED** | Gill, R. D., van der Laan, M. J. and Robins, J. M. Coarsening at Random: characterizations, conjectures, counter-example | The multivalued caveat in FORMAL_CORE section 5: conditional independence of the gate does not by it — *CSIA's multivalued gate is a partial weight g in [0,1] applied inside a naive-Bayes sum, which is a specific structure rather than* |
| missing data / selection mechanisms | **NOT_FOUND_NEEDS_HUMAN** | Heitjan, D. F. Ignorability and Coarse Data: some biomedical examples. (follow-on literature; exact entry not establishe | C2 and the multivalued caveat in FORMAL_CORE section 5. — *Not established.* |
| missing data / selection mechanisms | **CANDIDATE_UNVERIFIED** | Heitjan, D. F. and Rubin, D. B. Ignorability and Coarse Data. Annals of Statistics 19(4), 1991. | C2 (exogeneity): w_h constant in h implies p = q. — *CSIA's coarsening mechanism is a DESIGNED component of the diagnostic system rather than a feature of the data collection, and its* |
| partial observations | **CANDIDATE_UNVERIFIED** | Fault diagnosis in discrete event systems modeled by partially observed Petri nets; and the broader partially-observed D | The active set ACTIVE and the structural condition D(a,b) = (LOW(a) sym-diff LOW(b)) intersect ACTIV — *Their observation mask is FIXED. CSIA's ACTIVE set changes tick by tick as gates open and close, and it can change as a function o* |
| posterior sensitivity | **CANDIDATE_UNVERIFIED** | Argmax/argmin stability under bounded perturbation of the objective (margin exceeds twice the perturbation bound implies | P4: Delta > R implies argmax p = argmax q. — *None. P4 is the additive-log-score instance of it.* |
| posterior sensitivity | **CANDIDATE_UNVERIFIED** | Bayesian local robustness / local sensitivity analysis: derivatives of posterior functionals with respect to perturbatio | P5a/P5b (exact KL identities) and P6 (the R and TV bounds). — *This literature measures sensitivity to a perturbation the analyst CHOOSES to explore. CSIA's perturbation is not hypothetical: w * |
| posterior sensitivity | **CANDIDATE_UNVERIFIED** | Kallioinen, N. et al. Detecting and diagnosing prior and likelihood sensitivity with power-scaling. arXiv:2107.14054. | P1: p_h = q_h w_h / E_q[w], self-normalised reweighting. — *Their reweighting is a diagnostic an analyst runs after fitting. CSIA's is what the running system does, and w is fixed by the gat* |
| posterior sensitivity | **NOT_READ_HIGH_PRIORITY** | Likelihood distortion and Bayesian local robustness. arXiv:2405.15141. | The paper's own title phrase, posterior distortion from a likelihood-side factor. — *Not established. It was located by search and has NOT been read.* |
| robust diagnosability | **CANDIDATE_UNVERIFIED** | Active fault diagnosis / active model discrimination (multiple 2021-2026 sources returned). | PART G's disambiguation intervention; and the CSIA bench-vs-aircraft result that instrumentation rat — *CSIA is a monitoring layer that issues no commands, so it cannot perform active diagnosis. Its analogue is instrumentation choice * |
| robust diagnosability | **CANDIDATE_UNVERIFIED** | Matei, I., Piotrowski, W., Perez, A., de Kleer, J., Tierno, J., Mungovan, W. and Turnewitsch, V. System Resilience throu | PART G in full, and the CSIA v2 cross-domain localization layer. — *CSIA carries no digital twin, issues no interventions, and reports non-identifiability rather than resolving it. The named-by-the-* |
| robust diagnosability | **CANDIDATE_UNVERIFIED** | Paoli, A. and Lafortune, S. Safe diagnosability for fault-tolerant supervision of discrete-event systems. Automatica, 20 | PART G's 'evidence-constrained resilience under non-identifiability'. — *CSIA's proposed condition ranges over the hypotheses still SUPPORTED by evidence at runtime rather than over language-level diagno* |
| runtime validity gating | **TOPIC_SEARCHED_NO_CLOSE_MATCH** | Uncertainty in runtime verification: a survey; and symbolic runtime verification for monitoring under uncertainties and  | The whole runtime formulation: a monitor deciding per tick which of its own evidence is applicable. — *RV treats missing or noisy input as uncertainty to be reasoned THROUGH. CSIA's gate treats it as inapplicability and removes the t* |
| sequential monitoring | **KNOWN** | Page, E. S. Continuous inspection schemes. Biometrika 41, 1954. | csia/v1_1/sequential.py CusumBank; Mechanism B's CUSUM crossing times. — *None. CSIA uses the textbook detector with k = 0.5 and h chosen by a zero-clean-alarm rule.* |
| unreliable observations | **CANDIDATE_UNVERIFIED** | Dong, W., Yin, X. and Li, S. Verification of diagnosability for discrete-event systems under state-dependent observation | The general mechanism of fault-state-dependent observation loss. The systems paper asserts NO priori — *CSIA is a measurement of the mechanism in a deployed continuous-signal layer, not a verification result.* |

**Coverage of the ten required topics: 10/10.**
All ten covered.
A test asserts every required topic has at least one row, and that an
unsuccessful search is never recorded as a gap.

### The five the brief asks about

| reference | state | consequence |
|---|---|---|
| **Heitjan & Rubin 1991** (coarsening at random) | `CANDIDATE_UNVERIFIED` | **THE CRITICAL ENTRY.** It is what makes the ignorability proposition (C2) KNOWN rather than a contribution, so the paper's central concession rests on an unverified reference. A companion Heitjan row is `NOT_FOUND_NEEDS_HUMAN` |
| **Athanasopoulou / Li / Hadjicostis 2010** | `CANDIDATE_UNVERIFIED` | closest ML-diagnosis-under-unreliable-observations work. **Their unreliability is a NOISE model with a known error distribution; CSIA's is APPLICABILITY** — the observation is not corrupted, it is correctly and deliberately withheld, by the diagnostic system itself, with no probability attached. Cite as closest work and state the noise-versus-applicability distinction. Do NOT claim CSIA handles a case they cannot |
| **arXiv:2405.15141**, *Likelihood distortion and Bayesian local robustness* | **`NOT_READ_HIGH_PRIORITY`** | **the most important unread reference in the matrix** — the title alone overlaps this paper's subject. Until it is read, no claim of formulation novelty is safe |
| **Rukhin-type bounded-likelihood-ratio bound** | **`NOT_FOUND_NEEDS_HUMAN`** | named by the brief, could not be located. **No sharpness may be claimed for P6b until it is closed.** "Not found" is not "does not exist" |
| **DES / structural FDI nearest work** | `CANDIDATE_UNVERIFIED` across several rows (Dong/Yin/Li, Carvalho, Takai, Paoli & Lafortune, Krysander) | the paper cedes the general mechanism and asserts only a **difference of setting**. It does **not** prove non-subsumption, and cannot from here |

One row is `TOPIC_SEARCHED_NO_CLOSE_MATCH` (runtime validity gating) and one is
`KNOWN` (Page 1954, CUSUM).

---

## 10. Bibliography — 6 entries, 0 verified

**`make bib-guard` fails, correctly.** 15 provenance markers in
`papers/gate_conditioning/refs.bib`.

| key | status | risk |
|---|---|---|
| `heitjan1991car` | UNVERIFIED | **CRITICAL** — THE CRITICAL ENTRY OF THE MATHEMATICAL PAPER. It is what makes Proposition 5 KNOWN rather than a contribution, so the paper's central concession is attached to it. Reconstructed from search results alone: volume, number, pages and |
| `dong2024statedependent` | UNVERIFIED | carried over, confirm only — Carried over from the systems paper's bibliography with its status. |
| `carvalho2012intermittent` | UNVERIFIED | carried over, confirm only — Carried over from the systems paper's bibliography with its status. |
| `carvalho2013permanent` | UNVERIFIED | carried over, confirm only — Carried over from the systems paper's bibliography with its status. |
| `takai2021diagnosability` | UNVERIFIED | **candidate title, not verified** — This copy carries the search-derived candidate title rather than the placeholder, and its own note says so. That makes it MORE informative and NO more verified than the systems paper's copy. |
| `krysander2008sensorplacement` | UNVERIFIED | carried over, confirm only — Carried over from the systems paper's bibliography with its status. |

**`heitjan1991car` is the entry to fix first.** It is what makes the paper's
central concession — that the ignorability condition is coarsening at random
and therefore KNOWN — and it is `RECONSTRUCTED` from search alone.

**`takai2021diagnosability` differs between the two papers' bib files**: this
copy carries a search-derived candidate title, the systems copy carries a
literal `VERIFY` placeholder. Neither is verified. Do not reconcile them by
copying one into the other — that would launder an unverified candidate into a
second location.

Six routes tested from this environment; all six return HTTP 403 at CONNECT.
The last three would have been `rejected_routes` anyway.

---

## 11. Terminology policy — binding

Full policy: `research/PAPER_CROSS_CONSISTENCY.md`.

**For this paper, `q_h` and `p_h` ARE posteriors and "posterior" is
mathematically correct.** Both are, by A1–A2, a prior times a strictly positive
function of the data, normalized. Nothing in the propositions depends on
calibration. **Lines 56–532 need no change.**

**Six uses in §10–§11 describe the DEPLOYED layer**, where "posterior" is not
justified — the deployed output is EPS-floored, EW-smoothed over ~15 ticks,
tempered by 1.5 and softmaxed, so it is a **normalized hypothesis weight**:

| line | current | correct |
|---|---|---|
| 648 | "the posterior ratio equals the prior" | "the weight ratio equals the prior ratio" |
| 665 | "separately from the posterior" | "separately from the normalized hypothesis weight" |
| 667 | "at any posterior value" | "at any weight" |
| 668 | "no posterior threshold enters the rule" | "no weight threshold enters the rule" |
| 669 | "conditioning identifiability on the posterior" | "conditioning identifiability on the weight" |
| 674 | "the leader's posterior ranges from 0.9691 to 0.9998" | "the leader's weight ranges from…" |

**WARNING.** `tests/test_support_state_posterior_range.py` asserts the literal
string `"no posterior threshold enters the rule"` is present, because the
sentence it guards replaced a false claim. Changing line 668 requires updating
that assertion in the same commit. Keep the guard; change the string.

**Collision hazard.** This paper's `w_h` is the **validity factor**. The
systems paper's "normalized hypothesis weight" is the layer's output. Different
objects. Say "validity factor `w_h`" on first use in each section, and never
use the bare word "weight" for it.

**"Confidence" is FORBIDDEN** for either object, except as a disclaimer about
the word.

---

## 12. Red team — objections that remain unresolved

`research/math-paper/REVIEWER_RED_TEAM_MATH.md`, four reviewers, eleven
objections.

| # | objection | state |
|---|---|---|
| 1.1 | "what is `q`? under your own definition `p = q` and the paper is empty" | **the criticism was correct.** Fixed with §2.1, P7 and a rewritten abstract. **Remaining**: `q` is counterfactual and, in the measured case, not evaluable; a reviewer may call the framework an accounting identity, and **we have no rebuttal to that** |
| 1.2 | "every proposition is one line — where is the paper?" | **may simply stand.** Conceded in the manuscript, in a table, with every row KNOWN. No change can fix it because the honest answer is already printed |
| 1.3 | "P5a is the IS weight-degeneracy diagnostic; you cite a phrase, not a literature" | **OPEN HOLE.** The connection is real and the related-work section is thinner than it should be. **BLOCKED** — a citation added here would be an unverified string |
| 2.1 | "do you show your gate violates CAR, or only that a gate could?" | answered via P7. **Remaining**: shown for one pair on one layer, under the contested baseline. 27 of the 28 pairs never collapse |
| 3.1 | "this is structural isolability under a time-varying observation mask" | **we assert a difference of setting; we do not prove non-subsumption.** Every reference in that section is unverified |
| 3.2 | "378,000 agreements between two implementations of the same definition validates nothing" | **conceded in full.** Nothing validates the signature table |
| 4.1 | "your MAP proposition is decoration" | **the criticism was right and sharper than stated — so we proved it (P8)** |
| 4.2 | "`FORMAL_CORE.md` §4 claims the skip makes `w_a = w_b` 'by construction'" | **our own error, conceded.** P7c is the correct statement |
| 4.3 | "you verify at n = 4 symbolically and n = 5 numerically" | **no general-`n` machine check exists** |

## 13. What is BLOCKED, and what the writing agent must not do

| blocked | why |
|---|---|
| bibliography verification | no route from any tested host |
| the estimator-literature connection for P1/P5a | cannot cite without verification |
| non-subsumption by DES / structural FDI | asserted, never proved |
| reading arXiv:2405.15141 | no access |
| closing the Rukhin bounded-likelihood-ratio row | not located |

**Must not**: claim any proposition is new; claim sharpness for P6b; use
"confidence" for a posterior; cite the unlocated bounded-likelihood-ratio
reference; retire a bibliography marker; present `q` as something the system
computes; describe the deployed layer's output as a posterior; or let §10 point
at P3 where P7c is the statement that holds.

