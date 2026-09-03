# FORMAL CORE — POSTERIOR DISTORTION FROM HYPOTHESIS-DEPENDENT VALIDITY GATING

Paper: *Posterior Distortion from Hypothesis-Dependent Validity Gating in
Runtime Diagnosis.*

Brief C1–C5, C8. Verification: `research/math-paper/proof_audit.py` →
`results/proof_audit.json`. Prior art: `PRIOR_ART_MATRIX.csv`. Novelty
language: `NOVELTY_AUDIT.md`.

> **NO NEW MATHEMATICS IS CLAIMED HERE.** P1–P3 are one line of algebra each.
> P4 is a standard perturbation-of-argmax bound. P5–P6 follow from Jensen and
> from the range of a bounded random variable. C2 is, as far as the search in
> `PRIOR_ART_MATRIX.csv` can tell, an instance of **coarsening at random**
> (Heitjan & Rubin 1991). What the paper may claim is the runtime-diagnostic
> formulation, the structural-support reading, and the implemented system
> consequence. Those claims are audited in `NOVELTY_AUDIT.md`.

---

## 1. Setting and assumptions, stated exactly

A finite hypothesis set `H = {h_1, …, h_n}`, `n ≥ 2`, mutually exclusive and
exhaustive by construction of the diagnostic model.

| symbol | meaning | assumption |
|---|---|---|
| `π_h` | prior on `H` | `π_h > 0` for every `h`; `Σ_h π_h = 1` |
| `L_h` | likelihood of the **active** (ungated) evidence under `h` | `L_h > 0` |
| `w_h` | the hypothesis-dependent validity factor: everything the gating contributes to `h`'s score that is not in `L_h` | `w_h > 0`, finite |
| `q_h` | the posterior from active evidence alone | `q_h = π_h L_h / Σ_j π_j L_j` |
| `p_h` | the posterior actually produced | `p_h = π_h w_h L_h / Σ_j π_j w_j L_j` |

**A1 (strict positivity).** `π_h, L_h, w_h ∈ (0, ∞)` for all `h`. Needed for
every logarithm below. A zero likelihood or a zero validity factor is an
*exclusion*, which is a different operation and is out of scope here.

**A2 (finiteness).** `|H| = n < ∞`.

**A3 (no independence assumption is made).** In particular **nothing here
assumes the gate and the residual are independent**, and no such assumption is
used in any proof. The gate may be an arbitrary function of the same state the
evidence is a function of. That is the whole point: the results are about what
happens *when* the gate depends on the state, not about a benign case.

**A4 (`w` is exogenous to the algebra).** `w_h` is whatever the implementation
makes it. The propositions say what follows *given* `w`; they do not model how
`w` arises. C2 is the one place where a structural condition on `w` is
assumed, and it is stated there.

Notation: `E_q[w] = Σ_h q_h w_h`, `w_max = max_h w_h`, `w_min = min_h w_h`,
and `R = log(w_max / w_min) ≥ 0` is the **log range** of the validity factors.

---

## 2. P1 — the reweighting identity

**Proposition P1.** Under A1–A2, for every `h`:

    p_h = q_h · w_h / E_q[w].

*Proof.* Write `Z_q = Σ_j π_j L_j` and `Z_p = Σ_j π_j w_j L_j`, both finite and
positive by A1–A2. Then

    q_h w_h / E_q[w]
      = (π_h L_h / Z_q) · w_h / ( Σ_j (π_j L_j / Z_q) w_j )
      = (π_h L_h w_h / Z_q) · Z_q / Σ_j π_j L_j w_j
      = π_h w_h L_h / Z_p
      = p_h.                                                            ∎

The normalising constants cancel; that cancellation is the whole content.
`p` is the **self-normalised reweighting** of `q` by `w`.

*Verified:* symbolically for `n = 4` (`simplify(p_h − q_h w_h / E_q[w]) == 0`
for every `h`), and numerically over 20 000 random instances, worst absolute
deviation **4.441 × 10⁻¹⁶**.

---

## 3. P2 — the log-ratio decomposition

**Proposition P2.** Under A1–A2, for any pair `a, b ∈ H`:

    log(p_a / p_b) = log(q_a / q_b) + log(w_a / w_b).

*Proof.* By P1, `p_a/p_b = (q_a w_a / E_q[w]) / (q_b w_b / E_q[w])
= (q_a/q_b)(w_a/w_b)`; `E_q[w]` cancels. Take logs, valid by A1. ∎

**This is the paper's central object.** The gating contributes an **additive,
evidence-independent** shift to every pairwise log-posterior ratio. It does not
scale the evidence, does not interact with it, and does not vanish as evidence
accumulates. `log(w_a/w_b)` is a constant offset that the data cannot argue
with.

*Verified:* symbolically; numerically, worst deviation **1.776 × 10⁻¹⁵**.

---

## 4. P3 — pinning to the prior

This is the proposition the systems paper measures.

**Proposition P3.** Under A1–A2, if `L_a = L_b` **and** `w_a = w_b`, then

    p_a / p_b = π_a / π_b

exactly, for every value of the observed evidence.

*Proof.* `q_a/q_b = (π_a L_a)/(π_b L_b) = π_a/π_b` since `L_a = L_b`. By P2,
`log(p_a/p_b) = log(π_a/π_b) + log(w_a/w_b) = log(π_a/π_b)` since
`w_a = w_b`. ∎

**Why both hypotheses hold in the implemented system.** In CSIA the gate is a
**skip**: a gated feature is removed from the sum for *every* hypothesis
identically, so `w_a = w_b` by construction — the implementation's gating is
*not* hypothesis-dependent at the level of the multiplicative factor. What
*is* hypothesis-dependent is which surviving features can separate a given
pair. `L_a = L_b` holds exactly when every remaining feature contributes the
same log-likelihood to `a` and to `b`, which for the naive-Bayes signature
model is exactly the condition

    ( LOW(a) △ LOW(b) ) ∩ ACTIVE = ∅

where `LOW(h)` is the feature set hypothesis `h` drives low and `△` is
symmetric difference. `research/systems-paper/independent_checker.py`
evaluates that condition directly, and
`research/systems-paper/results/checker_agreement.json` records that it agrees
with the production analysis on **378 000 of 378 000** tick-by-pair
comparisons.

**What P3 does and does not prove.** It proves that the *pairwise* posterior
ratio equals the prior ratio and is therefore **unmovable by further evidence
of this kind**. It does **not** prove that the system cannot detect the fault
by some other route: CSIA's failsafe still escalates through an independent
freshness disjunct. The claim is about *attribution*, not about detection, and
the manuscript states that separation explicitly.

*Verified:* symbolically (with `L_b := L_a`, `w_b := w_a`, `simplify(p_a/p_b −
π_a/π_b) == 0`); numerically, worst deviation **8.882 × 10⁻¹⁶**.

---

## 5. C2 — exogeneity, and the multivalued caveat

**Proposition C2 (binary/constant case).** If `w_h = c` for all `h` and some
constant `c > 0`, then `p = q` identically.

*Proof.* Immediate from P1: `E_q[w] = c` and `p_h = q_h c / c = q_h`. ∎

*Verified symbolically* (`simplify(p_h|_{w≡w_0} − q_h) == 0` for every `h`).

**The exact assumption.** The result requires `w` **constant across
hypotheses**, not merely "the gate is random" or "the gate is independent of
the fault". A gate that is stochastic but whose realised factor differs
between hypotheses gives `p ≠ q`, and P2 says by exactly how much.

**The multivalued caveat, stated rather than glossed.** With a **binary** gate
(`g ∈ {0,1}`) applied uniformly, the surviving-evidence factorisation gives a
single `w` shared by all hypotheses and C2 applies. With a **multivalued or
partial** gate (`g ∈ [0,1]`, as CSIA's per-feature gates in fact are), the
per-feature contribution is `g · ℓ_h(feature)`, and the hypothesis-dependence
re-enters through `ℓ_h` even when `g` itself is hypothesis-blind. Constancy of
`w` then requires the stronger condition that the *gate-weighted* likelihood
difference vanish, which is exactly P3's condition, not an independence
statement. **Conditional independence of the gate from the fault does not by
itself deliver `p = q` in the multivalued case, and the paper must not say it
does.**

**Prior art, and it is close.** This is recognisably the ignorability
condition of **coarsening at random** (Heitjan & Rubin, *Ignorability and
Coarse Data*, Annals of Statistics 19(4), 1991 — see `PRIOR_ART_MATRIX.csv`,
status `CANDIDATE_UNVERIFIED`). The paper must cite it and label C2 **KNOWN**.
What is not obviously in that literature is the *runtime* reading: that the
coarsening mechanism here is a designed component of the diagnostic system
itself, whose non-ignorability is a **software property that can be checked
statically from the signature table**. That reading, not the condition, is the
candidate contribution.

---

## 6. C3 — posterior concentration is not discriminating support

Define, for a pair `a, b`, the **active distinguishing-term set**

    D(a, b) = { j ∈ ACTIVE : ℓ_j(a) ≠ ℓ_j(b) }

where `ℓ_j(h)` is feature `j`'s log-likelihood contribution under `h`.

**Proposition C3.** If `D(a, b) = ∅` then `L_a = L_b`, hence by P3 (given
`w_a = w_b`)

    log(p_a / p_b) = log(π_a / π_b)

**regardless of how concentrated `p` is.** In particular `p_a` may be
arbitrarily close to 1 — driven entirely by the prior and by likelihood terms
that do not distinguish `a` from `b` — while the evidence contains nothing
that separates them.

*Proof.* `log L_a − log L_b = Σ_{j ∈ ACTIVE} (ℓ_j(a) − ℓ_j(b)) = 0` when every
summand vanishes. Apply P3. Concentration of `p` is a statement about
`max_h p_h`, which is a function of *all* hypotheses' scores and of the prior;
nothing constrains it to reflect the `a`–`b` separation. ∎

**Be precise about what this does not prove.**

- It does **not** prove `a` and `b` are indistinguishable *in principle*. It
  proves they are indistinguishable *through the modelled terms currently
  active*. Another sensor, another relation, or an ungated version of the same
  relation may separate them, and CSIA's own bench-versus-aircraft result
  (Phase C set B) is a worked example of exactly that.
- It does **not** prove the system is unsafe or blind. Detection through an
  independent route is unaffected.
- It does **not** license calling the posterior "wrong". The posterior is the
  correct output of the model it is computed from. The finding is that the
  model's *support* and the model's *concentration* are different quantities
  and the implementation reports only the second.

**Terminology.** The manuscript must not call the posterior "confidence".
`p_a = 0.9998` with `D(a, b) = ∅` is a number that carries no information
about `a` versus `b`, and the word "confidence" invites a reader to think it
does.

---

## 7. P4 — MAP robustness

Let `Δ = log q_(1) − log q_(2)`, the log margin between the top two
hypotheses under `q`, and `R = log(w_max/w_min)`.

**Proposition P4 (sufficient condition).** If `Δ > R` then
`argmax_h p_h = argmax_h q_h`.

*Proof.* By P1, `log p_h = log q_h + log w_h − log E_q[w]`. The last term is
common to all `h`, so ranking under `p` is ranking of `log q_h + log w_h`. For
the `q`-argmax `a` and any other `b`,

    (log q_a + log w_a) − (log q_b + log w_b)
      = (log q_a − log q_b) + (log w_a − log w_b)
      ≥ Δ − R > 0,

using `log q_a − log q_b ≥ Δ` and `log w_a − log w_b ≥ −R`. ∎

**Sufficient, not necessary, and the audit says so out loud.** Over 20 000
random instances the condition held in **2 721**; in every one of those the
argmax agreed. In **6 877** instances the argmax moved *while the condition
did not hold* — which is permitted and is reported precisely so the bound is
not read as a characterisation.

**Tightness.** The `R` bound in P6a below is attained: the audit's worst slack
is `+1.776 × 10⁻¹⁵`, i.e. equality to floating-point precision.

**Prior art.** A margin-exceeds-perturbation argument for argmax stability is
standard. Label **KNOWN** unless a search establishes otherwise; see
`PRIOR_ART_MATRIX.csv`.

---

## 8. P5 — exact divergence identities

**Proposition P5a.** `KL(q ‖ p) = log E_q[w] − E_q[log w]`.

*Proof.* `KL(q‖p) = Σ_h q_h log(q_h/p_h) = Σ_h q_h log(E_q[w]/w_h)
= log E_q[w] − E_q[log w]`, using P1. ∎

**This is exactly the Jensen gap of `log w` under `q`.** It is `≥ 0` by
Jensen, and `= 0` iff `w` is `q`-almost-surely constant — which is C2. So:

> **The gating distorts the posterior exactly to the extent that the validity
> factors vary across hypotheses, and by exactly the Jensen gap.**

**Proposition P5b.** `KL(p ‖ q) = E_p[log w] − log E_q[w]`.

*Proof.* `Σ_h p_h log(p_h/q_h) = Σ_h p_h log(w_h/E_q[w])`, by P1. ∎

*Verified:* both symbolically and numerically (worst deviations
`1.332 × 10⁻¹⁵` and `1.533 × 10⁻¹⁵`).

**Prior art.** These are the standard self-normalised importance-weighting
identities. Label **KNOWN**.

---

## 9. P6 — bounds

**Proposition P6a.** For every pair `a, b`:

    | log(p_a/p_b) − log(q_a/q_b) | ≤ R.

*Proof.* By P2 the left side is `|log w_a − log w_b|`, which is at most
`log w_max − log w_min = R`. ∎ **Tight**, attained when `{a,b}` are the
argmax and argmin of `w`.

**Proposition P6b.** `TV(p, q) ≤ (w_max − w_min) / (4 E_q[w])`.

*Proof.* `TV(p,q) = ½ Σ_h |p_h − q_h| = ½ Σ_h q_h |w_h/E_q[w] − 1|
= E_q|w − E_q[w]| / (2 E_q[w])`. For a random variable supported on
`[w_min, w_max]`, the mean absolute deviation about its mean is at most
`(w_max − w_min)/2`. Substituting gives the claim. ∎

*Verified numerically:* 0 violations in 20 000 instances; worst slack
`−8.381 × 10⁻⁵`, so the bound is close to tight on this instance family but
not attained.

**On sharpness, and what is NOT claimed.** No claim is made that P6a or P6b is
the sharpest available bound, and no new information-theoretic inequality is
claimed. The MAD-bounded-support step is elementary. A search for a specific
"Rukhin bounded-likelihood-ratio" result the brief names did **not** return a
confirmable reference (see `PRIOR_ART_MATRIX.csv`, row `PA-08`, status
`NOT_FOUND_NEEDS_HUMAN`); the manuscript must not cite it until a human has
located it, and must not claim sharpness in its absence.

---

## 10. Verification summary

`research/math-paper/results/proof_audit.json`, regenerated by
`python research/math-paper/proof_audit.py`.

| proposition | symbolic (sympy, n=4) | numeric (20 000 instances) |
|---|---|---|
| P1 reweighting identity | exact | 4.441e−16 |
| P2 log-ratio decomposition | exact | 1.776e−15 |
| P3 pinned to prior | exact | 8.882e−16 |
| C2 constant `w` ⇒ `p = q` | exact | — |
| P5a KL(q‖p) = Jensen gap | exact | 1.332e−15 |
| P5b KL(p‖q) identity | exact | 1.533e−15 |
| P6a `R` bound | — | 0 violations, max slack +1.78e−15 (tight) |
| P6b TV bound | — | 0 violations, max slack −8.38e−05 |
| P4 sufficient condition | — | held in 2721/2721 instances where Δ > R |

The numeric pass is the one CI re-runs (`tests/test_math_paper_proofs.py`);
sympy is not a declared project dependency and adding one to CI so a research
script can run would be the wrong trade. A reader reproducing the exact
algebra runs `pip install sympy` and re-runs the script.

## 11. Counterexamples to weakened assumptions (C8)

| weakened | what breaks | witness |
|---|---|---|
| drop A1, allow `w_h = 0` | `log w_h` undefined; P2, P5, P6a all fail. `w_h = 0` is an *exclusion*, a different operation | any instance with a zero factor |
| drop A1, allow `L_h = 0` | `q_h = 0`, `log(q_a/q_b)` undefined | as above |
| replace C2's "constant `w`" with "gate independent of the fault" | `p ≠ q` in the multivalued case | §5's caveat; the per-feature `g·ℓ_h` factorisation |
| read P4's condition as necessary | false | 6 877 audited instances where the argmax moved with `Δ ≤ R` |
| read P3 as "the fault is undetectable" | false | CSIA's failsafe reaches CAUTION through the freshness disjunct in exactly the window where P3 holds |
| read concentration as support | false | C3; and the measured `p_nominal → 1` with `D(nominal, gps_fault) = ∅` |
