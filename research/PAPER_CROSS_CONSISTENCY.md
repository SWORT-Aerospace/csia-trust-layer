# Cross-paper consistency

Binding for both manuscripts. Where the two papers use the same word, this file
gives one definition. Where they quote the same number, it gives one artifact.
Where they conflict, it resolves the conflict or marks it BLOCKED.

Audited at HEAD `228bebeb14395aebda60d76dbf6a54b292d0e344`,
evidence freeze `csia-dual-paper-evidence-freeze` = `eb2577d6…`.

---

## A. Terminology policy

### The decision, and why

The deployed CSIA diagnosis computes, per tick, in `csia/diagnosis/bayes.py`:

```
ll[c]     = Σ_j  g_j · ℓ_j(c)              ℓ_j(c) = log(c_j + EPS) or log(1 − c_j + EPS)
smoothed  = (1 − α)·smoothed + α·ll        α = SMOOTH_ALPHA = 0.06, ≈15 ticks
score[c]  = log π_c + EVIDENCE_MULT · smoothed[c]      EVIDENCE_MULT = 1.5
p[c]      = softmax(score)[c]
```

Four departures from a Bayes posterior, **any one of which is sufficient**:

1. `EPS = 0.02` is a floor inside the logarithm, not a density. At `c = 1` the
   agreeing term is `log(1.02) > 0`. The pair is not a likelihood.
2. The evidence term is an **exponential moving average** of per-tick scores.
   A Bayes update over `T` ticks *sums* log-likelihoods; an EWMA *averages*
   them and discounts history. The result is not the posterior of any stated
   generative model over the tick sequence.
3. `EVIDENCE_MULT = 1.5` tempers the evidence — a power posterior, valid only
   against a likelihood `L^1.5` that is not the model's likelihood.
4. Normalization is a softmax over eight causes asserted exhaustive by the
   signature table, not by a probability model of the world.

**Conclusion.** For the deployed output, "posterior" is not formally
justified. For the mathematical paper's `q_h` and `p_h` it is: both are, by the
paper's own Assumptions 1–2, a prior times a strictly positive function of the
data, normalized. That is a posterior, and nothing in the propositions depends
on calibration.

### The canonical table

| concept | math-paper term | systems-paper term | implementation field | allowed shorthand | forbidden | reason |
|---|---|---|---|---|---|---|
| formal baseline object | **posterior** `q_h` | (do not use) | — | `q` | — | prior × likelihood, normalized. A posterior by construction |
| formal produced object | **posterior** `p_h` | (do not use) | — | `p` | — | as above, with the validity factor |
| deployed diagnosis output | **normalized hypothesis weight** when §9 speaks about the layer | **normalized hypothesis weight** | `DiagnosisResult.posterior` (field name; **do not quote it as a term**) | "weight", "the weights" | **posterior**, **probability**, **confidence** | the four departures above |
| validity factor | **`w_h`** | (do not use) | — | — | "weight" unqualified | **COLLISION HAZARD, see below** |
| per-feature contribution | `ℓ_j(h)` | "feature log-score" | `ll[ci] +=` term | — | "likelihood" for the EPS-floored form | not a density |
| gate | `g_j ∈ [0,1]` | "gate", "validity gate" | `gate` in `features` | — | — | — |
| trust coefficient | (not used) | **trust coefficient** | `TrustState.trust` | "trust" | "probability of health" | Beta-recursion state, uncalibrated |
| structural separability | `D(a,b) ≠ ∅` | **discriminating support** | `discriminating_terms` | — | — | — |
| its absence | `D(a,b) = ∅` | **support lost / non-identifiable** | `NON_IDENTIFIABLE` | — | "low confidence" | it is not a confidence statement |
| pair-level indistinguishability | pinned to the prior | **ambiguity** `AMBIGUOUS` | `ambiguity` | — | — | structural, never a posterior margin |

### The collision hazard, stated explicitly

The systems paper's **"normalized hypothesis weight"** and the mathematical
paper's **`w_h`** are *different objects*:

- systems `weight` = the normalized output over hypotheses, sums to 1;
- math `w_h` = the per-hypothesis **validity factor**, strictly positive, does
  not sum to anything.

**Neither paper may use the bare word "weight" for the other's object.** The
mathematical paper says "validity factor $w_h$" on first use in each section;
the systems paper says "normalized hypothesis weight" in full on first use per
section and "the weights" thereafter.

### Required replacements — SYSTEMS PAPER (2)

The manuscript **already states the policy correctly** at line 251:
*"We call the output a normalized hypothesis weight, not a posterior"*, with
the three reasons. Two later lines contradict it.

| file | line | current wording | correct wording | action |
|---|---|---|---|---|
| `papers/csia_systems/main.tex` | 1405 | "The diagnosis posterior is a tempered softmax over exponentially smoothed pseudo-log-likelihoods." | "The diagnosis output is a normalized hypothesis weight: a tempered softmax over exponentially smoothed feature log-scores." | writing agent |
| `papers/csia_systems/main.tex` | 1408 | "We deliberately do not call the posterior a \emph{confidence}" | "We deliberately call it neither a posterior nor a \emph{confidence}" | writing agent |

Also, non-manuscript: `research/systems-paper/CLAIMS.csv` row **SC-20** reads
*"The posterior is not confidence: a leader at high posterior…"*. Same
substitution. It is a ledger row, not prose, so it may be updated in the same
commit as the manuscript or left with a note; it must not be left silently
inconsistent.

### Required replacements — MATHEMATICAL PAPER (6)

Lines 56–532 use "posterior" for the **formal** `q_h`/`p_h`. **All correct; do
not change them.** Six uses in §9–§10 describe the **deployed layer**:

| file | line | context | correct wording |
|---|---|---|---|
| `papers/gate_conditioning/main.tex` | 648 | "Corollary~\ref{c:pinned} says the posterior ratio equals the prior" | "…the weight ratio equals the prior ratio" |
| same | 665 | "reports a support state separately from the posterior" | "…separately from the normalized hypothesis weight" |
| same | 667 | "at any posterior value" | "at any weight" |
| same | 668 | "no posterior threshold enters the rule" | "no weight threshold enters the rule" |
| same | 669 | "conditioning identifiability on the posterior" | "conditioning identifiability on the weight" |
| same | 674 | "the leader's posterior ranges from 0.9691 to 0.9998" | "the leader's weight ranges from…" |

**Note for the math-paper agent.** `tests/test_support_state_posterior_range.py`
asserts the literal string `"no posterior threshold enters the rule"` is
present. Changing line 668 requires updating that assertion in the same commit.
The test exists because the sentence it guards replaced a false claim; keep the
guard, change the string.

### "Confidence"

**FORBIDDEN in both papers, for both objects.** Already enforced: a test greps
the systems manuscript. Each paper currently contains exactly one occurrence,
and in both it is a *disclaimer* ("we do not call it a confidence"), which is
the permitted use/mention form.

---

## B. Mathematical object versus deployed implementation

| | mathematical paper | deployed CSIA |
|---|---|---|
| object | `q_h`, `p_h` — posteriors | normalized hypothesis weights |
| evidence | a likelihood `L_h` | EPS-floored feature log-scores, EW-smoothed, tempered |
| gate | `g_j ∈ [0,1]`, abstract | `gate` in the feature dict; a skip when 0 |
| baseline | the **full-evidence** posterior (Reading B) | **not computed, and under fix loss not computable** |
| what transfers | the *structural* results: pinning, `D(a,b)`, static checkability | all of it |
| what does **not** transfer | the divergence results (P5, P6) quantify a distance to a baseline the layer never evaluates | — |

The mathematical paper's §9 must therefore be read as: *the layer instantiates
the gate structure, and the structural propositions apply to it; the
quantitative divergence propositions describe a reference point the layer does
not compute.* Both papers already say this; neither may soften it.

---

## C. Shared mechanism terminology

| mechanism | canonical name | both papers must use |
|---|---|---|
| the fault removes the observable that would name it | **diagnostic self-occlusion** | yes |
| the pair whose separating feature is gated shut | **`(nominal, gps_fault)`**, "the target pair" | yes |
| the separating feature | **`phys_gps`**, the GNSS internal-physics consistency check | yes |
| the gate that closes it | **`gvalid`**, closes when the receiver reports no valid fix | yes |
| the condition | **`D(a,b) = (LOW(a) △ LOW(b)) ∩ ACTIVE = ∅`** | yes |
| the design rule | *a feature intended to discriminate `h` must not be gated by a gate that `h` closes* | yes |

The formal proposition the implemented case satisfies is **P7c**, not P3. P3 is
the abstract statement; its literal hypotheses (`L_a = L_b` **and**
`w_a = w_b`) are both **false** in the measured case under the full-evidence
baseline, and the ratio is pinned because the two inequalities cancel exactly.
Every document that pointed at P3 was repointed at P7c; the systems paper's
`MECHANISM_A.md` records the correction.

---

## D. Shared numbers — one artifact each

| number | meaning | canonical artifact | pointer |
|---|---|---|---|
| **378,000 / 378,000** | checker-vs-production tick-by-pair agreements | `research/systems-paper/results/checker_agreement.json` | `/totals/{agree,real_disagreements}` |
| **200 ticks** | collapse window under injected fix loss (8.0 s at 25 Hz) | `research/systems-paper/results/checker_verdicts.json` | per-scenario groups |
| **76 ticks** | startup collapse present in every scenario including clean | same | same |
| **28 pairs**, 1 collapsing | unordered hypothesis pairs over 8 causes | same | `/hypotheses` |
| **15,595 ticks / 20 trials / 0 collapses** | current-stack negative control | `research/systems-paper/results/current_stack_structural.json` | `/ticks`, `/trials`, `/pair_not_distinguishable_ticks` |
| **0.9691 – 0.9998** | leader weight range at ticks where the support rule fires | `engineering/v1_1/SUPPORT_STATE_RESULTS.csv` | min/max of `posterior` over rows with non-empty `non_identifiable_against` |
| **118.82** | banked-agreement term `S_0(T_0 − T*)` | `research/wp_c8/results/escalation_algebra.json` | `/what_dominates_N_star/mass_term_S0_times_T0_minus_Tstar` |
| **93.31 ticks** | predicted escalation boundary `N*` | same | `/ticks_required_N_star` |

**The CSV column is named `posterior`.** That is an implementation field name,
not a term of art. Quote the number, not the column name; see §A.

---

## E. Citation overlap

Six keys appear in both `refs.bib` files:
`dong2024statedependent`, `carvalho2012intermittent`, `carvalho2013permanent`,
`takai2021diagnosability`, `krysander2008sensorplacement`, and (systems only)
`heitjan1991car` in the mathematical paper.

**All six are UNVERIFIED in both.** `takai2021diagnosability` differs between
the two files: the systems copy carries a literal `VERIFY` placeholder title,
the gate-conditioning copy carries a search-derived candidate title. Neither is
verified; the two files must not be reconciled by copying one into the other,
because that would launder an unverified candidate into a second location.

---

## F. Systems paper → mathematical paper

The systems paper may cite **P7c** and **C3** as the closed-form account of
what it measures. It may **not** claim the mathematics is novel; every
proposition is labelled KNOWN.

## G. Mathematical paper → systems paper

The mathematical paper may cite the measurement as an implemented instance:
the 378,000 agreements, the 200-tick window, the 15,595-tick negative control.
It must state what the agreement does **not** establish — the signature table
is not validated by any amount of checker agreement — which §9 already does.

Neither paper is load-bearing for the other. Delete the systems paper and the
mathematics still holds, minus its worked instance; delete the mathematical
paper and the measurements still stand, minus their closed-form explanation.

---

## Unresolved / BLOCKED

| # | conflict | state |
|---|---|---|
| 1 | bibliography verification, both papers | **BLOCKED** — six routes tested, all 403 |
| 2 | the estimator literature behind P1/P5a is named as a phrase, not engaged | **BLOCKED** — cannot cite without verification |
| 3 | non-subsumption by DES / structural FDI | **OPEN** — asserted as a difference of setting, never proved |
| 4 | 49 unmapped prose literals in the systems manuscript | **OPEN** — listed in the systems handoff; the writing agent decides which need binding |
| 5 | the eight terminology substitutions in §A | **RESOLVED HERE, NOT YET APPLIED** — policy is explicit; the writing agents apply it |
