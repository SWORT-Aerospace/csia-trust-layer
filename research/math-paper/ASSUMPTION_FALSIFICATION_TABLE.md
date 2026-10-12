<!-- publication-guard: research-note -->
# Assumption and falsification table — mathematical paper

Brief §23. Each result, the assumption doing the work, what breaks without it,
and the status. This replaces theorem inflation with assumption clarity: every
proposition is KNOWN, so what a reader needs is precision about scope.

| result | key assumption | what breaks if removed | counterexample / status |
|---|---|---|---|
| **P1** `p_h = q_h w_h / E_q[w]` | A1 strict positivity; A2 finiteness | `w_h = 0` makes `log w` undefined and P2/P5/P6a fail. A zero **likelihood** is an *exclusion*, a different operation | `FORMAL_CORE.md` §11; symbolic exact, numeric 4.44e−16 |
| **P2** log-ratio decomposition | as P1 | as P1 | symbolic exact, numeric 1.78e−15 |
| **P3** pinned to the prior | `L_a = L_b` **and** `w_a = w_b` | **both hypotheses are FALSE in the implemented case** under the full-evidence baseline; the conclusion still holds, via P7c, because the two inequalities cancel | superseded by P7c for the implemented case; symbolic exact |
| **P4** `Δ > R ⇒ argmax unchanged` | sufficiency only; **not** necessary | reading it as a characterisation is wrong | 6,877 audited instances where the argmax moved with the condition violated |
| **P5a/P5b** divergence identities | A1, A2, and a **computable `q`** | `q` is counterfactual and, under realized fix loss, **not evaluable at all** — so these quantify a distance to a reference point the system never computes | acknowledged in the manuscript's Limitations, item 1 |
| **P6a** `\|Δ log-ratio\| ≤ R` | A1, A2 | — | **attained**; worst slack +1.78e−15 |
| **P6b** `TV ≤ (w_max−w_min)/(4 E_q[w])` | A1, A2 | — | **attained** — see P6c |
| **P6c** the TV bound is attained | `q = (1/2,1/2)`, two-point `w` | nothing; it is a witness, not a hypothesis | `TV = \|a−b\|/(2(a+b))` **equals** the bound identically on both ordering branches. Symbolic; numeric 5.551e−17. Licenses "cannot be improved as a function of `(w_max, w_min, E_q[w])`" — **not** bare "sharp", and not a priority claim |
| **P7** `w_h = exp(−Σ_j (1−g_j) ℓ_j(h))` | the score is **additive over per-feature terms** | a non-additive score has no such closed form, and the framework loses its concrete instance | numeric 5.551e−16 |
| **P7b** shift = withheld distinguishing contribution | as P7 | as P7 | numeric 3.553e−15 |
| **P7c** all distinguishing features gated ⇒ pinned | as P7, plus `g_j = 0` for **every** `j` with `ℓ_j(a) ≠ ℓ_j(b)` | one ungated distinguishing feature is enough to break the pinning — which is exactly the paper's design rule | numeric 1.776e−15 |
| **P8** `Δ ≤ R` for a pinned pair | pinned pair, **`π_a = π_b`**, and the pair is the **top two under `q`** | drop equal priors and the condition CAN fire — in 1,224 of 20,130 sampled instances under a lopsided prior — but only because the prior log-odds carried the whole excess | 0 violations over 2,282 instances, worst slack +8.882e−16 |
| **C2** constant `w` ⇒ `p = q` | `w` constant **across hypotheses** — not gate randomness, not conditional independence | with a multivalued gate the hypothesis dependence re-enters through `ℓ_j` even when `g_j` is hypothesis-blind | coarsening at random; KNOWN |
| **C3** concentration ≠ discriminating support | `D(a,b) = ∅` | — | the whole point: the conclusion holds *regardless of* `max_h p_h` |

## The two negative results, kept prominent

1. **`q` is counterfactual.** Under realized fix loss the withheld `ℓ_j(h)`
   has no observed value, so `q` is not merely uncomputed but **not
   evaluable**. P1, P2, P4, P5, P6 all inherit this. P3, P7c and C3 do not —
   they relate `p` to the prior, and the implementation holds both.
2. **P8.** There is no MAP-stability result for the regime the project
   measures, and P8 shows there cannot be one of P4's form. When the escape
   fires it is because prior mass, not evidence, supplied the margin — which
   C3 already says carries no discriminating support.
