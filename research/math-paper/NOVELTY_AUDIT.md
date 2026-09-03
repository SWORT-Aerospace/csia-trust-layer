# NOVELTY AUDIT — MATHEMATICAL PAPER

Brief C7. Enforced by `tests/test_math_paper_proofs.py`.

> The paper may be publishable even if individual mathematical ingredients
> are known.

---

## 1. Forbidden phrases

These may not appear in `papers/gate_conditioning/` or in
`research/math-paper/` unless the thing they assert has been **proven and the
prior art checked**. A test greps for them.

| forbidden | why |
|---|---|
| "new information theory" | nothing here is information theory, new or otherwise |
| "first posterior-reweighting theorem" | P1 is self-normalised importance weighting |
| "novel KL bound" | P5a/P5b are exact identities, and the Jensen-gap reading is standard |
| "new Bayesian identity" | as above |
| "we prove for the first time" | no proposition here survives that claim |
| "sharp bound" / "tight bound" applied to P6b | P6b is not shown sharp, only shown to hold with margin |

**P6a may be described as attained**, because the audit measures its worst
slack at `+1.78e−15` — equality to floating-point precision. "Attained on this
instance family" is a measurement; "sharp" would be a claim about all
families.

## 2. Allowed contribution language

| allowed | what backs it |
|---|---|
| "an exact runtime-diagnostic formulation" | the setting in `FORMAL_CORE.md` §1: `w_h` is a designed component of the diagnostic software, not a property of the data-collection process |
| "a connection between hypothesis-dependent validity and posterior distortion" | P2's additive, evidence-independent offset |
| "a structural support interpretation" | C3 and the `LOW(a) △ LOW(b) ∩ ACTIVE` condition, which is **statically checkable from a signature table** |
| "an implemented counterexample" | `research/systems-paper/results/checker_verdicts.json` — the condition holds for 200 consecutive ticks on a deployed layer |
| "a unified characterization" | P1–P6 as one algebraic frame for gating, pinning, MAP robustness and divergence |

## 3. Per-proposition novelty status

| id | statement | novelty | prior art | source |
|---|---|---|---|---|
| P1 | `p_h = q_h w_h / E_q[w]` | **KNOWN** | self-normalised importance weighting | `PRIOR_ART_MATRIX.csv` row 4 |
| P2 | `log(p_a/p_b) = log(q_a/q_b) + log(w_a/w_b)` | **KNOWN** (corollary of P1) | as above | as above |
| P3 | no distinguishing evidence ⇒ pinned to the prior | **KNOWN as algebra.** The *runtime reading* — that this is a statically checkable software property — is the candidate contribution | — | — |
| C2 | constant `w` ⇒ `p = q` | **KNOWN** | coarsening at random, Heitjan & Rubin 1991 | `PRIOR_ART_MATRIX.csv` row 1 |
| C3 | concentration ≠ discriminating support | **KNOWN as algebra**; the diagnostic distinction and its implementation are the candidate contribution | — | — |
| P4 | `Δ > R ⇒ argmax p = argmax q` | **KNOWN** | argmax stability under bounded perturbation | `PRIOR_ART_MATRIX.csv` row 6 |
| P5a | `KL(q‖p)` = Jensen gap of `log w` | **KNOWN** | self-normalised IS identities | row 4 |
| P5b | `KL(p‖q) = E_p[log w] − log E_q[w]` | **KNOWN** | as above | row 4 |
| P6a | `\|Δ log-ratio\| ≤ R`, attained | **KNOWN** (immediate from P2) | — | — |
| P6b | `TV ≤ (w_max − w_min)/(4 E_q[w])` | **KNOWN** (MAD ≤ range/2) | — | — |
| P7 | gated additive score ⇒ `w_h = exp(−Σ_j (1−g_j) ℓ_j(h))` | **KNOWN.** Reparameterisation of a log-linear score; one line | — | — |
| P7b | the pairwise shift is exactly the withheld distinguishing contribution | **KNOWN** (immediate from P7 and P2) | — | — |
| P7c | every distinguishing feature gated ⇒ pinned to the prior | **KNOWN** (corner of P2); it *supersedes* P3 as the statement the implemented case satisfies | — | — |
| P8 | a pinned pair with equal prior mass has `Δ ≤ R`, so P4 cannot certify it | **KNOWN as algebra**, and it is a **negative** result about P4 rather than a contribution | — | — |

**Every mathematical proposition in this paper is labelled KNOWN.** That is
the honest outcome and the brief permits it: *"A KNOWN THEOREM IS
ACCEPTABLE."*

## 4. What the paper is therefore claiming

Not a theorem. **A formulation, a diagnosis, and a measured instance.**

1. Runtime diagnostic layers apply hypothesis-relative applicability, and that
   makes them coarsening mechanisms of their own design.
2. Whether the mechanism is ignorable is decidable from the signature table
   **before the system runs** — it does not require data.
3. A deployed layer fails the condition, for 200 consecutive ticks, and an
   independent checker confirms it 378,000 times out of 378,000.
4. The consequence is that posterior concentration and discriminating support
   are different quantities, and reporting only the first is a defect a
   safety-relevant consumer will act on.

Whether that is enough for a venue is an editorial judgement. The audit's job
is to ensure the paper does not overstate it, and Reviewer 4.1 in
`research/systems-paper/REVIEWER_RED_TEAM.md` records that the objection may
simply stand.

## 5. Unclosed holes

| hole | consequence |
|---|---|
| every prior-art row is `WEB_SEARCH_ONLY` / `CANDIDATE_UNVERIFIED` — egress denies `doi.org`, `dblp.org`, `api.crossref.org` | even the concessions are unverified. A human must confirm Heitjan & Rubin before C2's KNOWN label is safe to print |
| the brief's named "Rukhin bounded-likelihood-ratio" prior art was **not located** | `PRIOR_ART_MATRIX.csv` row 8 is `NOT_FOUND_NEEDS_HUMAN`. No sharpness may be claimed for P6 until it is closed |
| the baseline `q` is a **counterfactual** and, in the measured case, is not evaluable at all | `FORMAL_CORE.md` §1.1. P5 and P6 quantify a distance to a reference point the system never computes. The pinning claim survives because it names only `p` and the prior; the divergence apparatus does not |
| no MAP-stability result exists for the regime the project measures | P8 (`FORMAL_CORE.md` §9a) proves P4 **cannot** apply to a pinned pair with equal prior mass. This is an absence, not a result, and no substitute is claimed |
| the **estimator** literature behind P1 and P5a is named as a phrase, not engaged | `KL(q‖p) = log E_q[w] − E_q[log w]` is the standard self-normalised-IS weight-degeneracy diagnostic, and `R` is a bounded-weight condition of the kind that literature uses to control the estimator. The related-work section should engage it and does not. **It cannot be closed from here**: adding a citation would mean adding an unverified string, which `papers/BIB_VERIFICATION_LEDGER.yaml` exists to prevent. Red team objection 1.3 |

## 6. What red team changed, and what it did not

The math-paper red team pass is `REVIEWER_RED_TEAM_MATH.md`. It found one
defect that would have been fatal in review — the baseline ambiguity above —
and one over-claim in this document's own §4 about `w_a = w_b` holding "by
construction". Both are recorded in place rather than silently repaired.

**Nothing in §3's novelty column changed.** Every row said KNOWN before the
pass and says KNOWN after it. Finding a hole in a paper that claims no
theorems does not create one.
