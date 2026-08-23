# T-1 — Blockwise Anytime False-Alert Control

**Status:** see per-claim labels below. Summary: Lemmas 1–2 **PROVED**;
Theorem T-1 **PROVED GIVEN A3**, with A3 itself **EMPIRICAL ONLY** for mixing
residuals; the LR variant **PROVED** under correct null specification.
**Implementation:** `csia/evidence/eprocess.py`
**Falsification:** `tools/simulate_anytime_validity.py` →
`experiments/results/anytime_validity_v1.json` · **Tests:** `tests/test_anytime_validity.py`

Simulation cannot prove any statement here. Its role is falsification, and it
has already discharged that role twice: it exposed the naive per-tick
construction (measured 0.442 crossing against a 0.05 bound) and **a bug in this
slice's own LR implementation** (first-step conditioning against the wrong
variance → 0.196; fixed by conditioning on the first observation → 0.0088).

---

## 1. Setting

- **A1 (Filtration).** `F_t = σ(all residual samples, context labels, and
  calibration data up to tick t)`. All weights and block boundaries are
  `F`-predictable.
- **A2 (Null).** `H_0`: the monitored residual stream follows its
  context-conditioned nominal law. For the analysis model this is a
  stationary Gaussian AR(1) with parameter ρ and unit marginal variance;
  ρ ≈ 0.94 corresponds to CSIA's EW-smoothed residuals (`SMOOTH_ALPHA=0.06`).
- **Blocks.** Fixed length `L`; block `j` covers ticks `(j−1)L+1 … jL`.
  `G_j = F_{jL}` is the block filtration. Block statistic: the block mean;
  block p-value `p_j` from the exact null distribution of that mean
  (`ar1_block_mean_p`).
- **Calibrator.** `e = κ p^{κ−1}`, `κ ∈ (0,1)`, clamped at `p_min`.
- **Process.** `E_j = Π_{i≤j} e_i`, held constant between block boundaries.

## 2. Lemma 1 (calibrator admissibility + clamp conservativeness) — **PROVED**

For any super-uniform `p` (`P(p ≤ u) ≤ u`): `∫₀¹ κ u^{κ−1} du = 1`, so
`E[κ p^{κ−1}] ≤ 1` (Vovk–Wang p-to-e calibration). Clamping replaces `p` by
`max(p, p_min)`; the calibrator is decreasing, so the clamped value is
dominated by the exact one and remains an e-value. Conservative, never
anti-conservative. ∎

## 3. Lemma 2 (predictable convex combination) — **PROVED**

If each `e^{(i)}_j` satisfies `E[e^{(i)}_j | G_{j−1}] ≤ 1` and weights
`π_{i,j} ≥ 0`, `Σ_i π_{i,j} ≤ 1` are `G_{j−1}`-measurable, then
`E[Σ_i π_{i,j} e^{(i)}_j | G_{j−1}] ≤ 1` by linearity. **No independence
across residuals is needed.** The corresponding product across residuals is
NOT an e-value (measured: mean 2.87 on duplicated residuals). ∎

## 4. Assumption A3 (block conditional super-uniformity) — **EMPIRICAL ONLY**

`P(p_j ≤ u | G_{j−1}) ≤ u` for all `u ∈ [0,1]`, for every `j`.

This is the load-bearing assumption and it is **not a theorem** for mixing
processes at finite `L`: consecutive AR(1) block means retain correlation
≈ `ρ^L`-order terms. What is measurable is how fast the violation of the
final bound decays in `L` — see §7.

## 5. Theorem T-1 — **PROVED GIVEN A3**

Under A1–A2 and A3, `E_j` is a nonnegative supermartingale with `E[E_0]=1`:
`E[E_j | G_{j−1}] = E_{j−1} · E[e_j | G_{j−1}] ≤ E_{j−1}` by Lemma 1 applied
conditionally. Ville's inequality then gives, for any `α ∈ (0,1)`:

    P( ∃ j : E_j ≥ 1/α ) ≤ α.

Holding `E` constant between block boundaries cannot raise the running
maximum, so the bound holds at tick resolution. ∎ (Standard; the content of
T-1 is entirely in whether A3 holds.)

## 6. Corollary (likelihood-ratio variant) — **PROVED under correct null**

With `e_t = q₁(x_t|x_{t−1}) / q₀(x_t|x_{t−1})` and `q₀` the TRUE conditional
null law, `E[e_t | F_{t−1}] = ∫ q₁ = 1` identically, so the product is a
martingale and the Ville bound is exact — no blocks, no mixing assumption.
Validity is exactly as strong as the null specification;
misspecification voids it (measured: 0.447 when AR(1) ρ=0.94 data is scored
against an iid null).

**Counterexample discovered by the suite (initial-state handling):** scoring
the first stationary observation (marginal variance 1) against the
conditional density `N(0, 1−ρ²)` produces one enormous invalid factor —
measured 0.196 crossing. Conditioning the process on `x₀` removes it
(0.0088). This failure mode matters operationally: **every restart of an
e-process re-encounters it**, so restart semantics must condition on the
post-restart first observation. Recorded for T-2.

## 7. Measured falsification matrix (α = 0.05, threshold 20, T = 3000)

Selection (seed base 0, 2000 paths) — used ONLY to choose `L`:

| ρ | L=1 | L=5 | L=25 | L=50 | L=100 | L=200 | L=400 |
|---|---|---|---|---|---|---|---|
| 0.50 | **0.152** | 0.053 | 0.033 | 0.025 | 0.027 | — | — |
| 0.94 | **0.460** | **0.295** | **0.107** | 0.057 | 0.036 | — | — |
| 0.99 | **0.539** | **0.456** | **0.301** | **0.218** | **0.113** | 0.054 | 0.014 |

Selected: **L = 50** (smallest valid across the declared domain ρ ≤ 0.94).

Evaluation (seed base 1000, 4000 paths — never used for selection):

| Cell | Crossing | Verdict |
|---|---|---|
| naive per-tick, iid | 0.0248 | ok |
| **naive per-tick, AR(1) ρ=0.94** | **0.4420** | **VIOLATES (known-invalid control)** |
| naive, t₃ iid (heavy tails, correct marginal p) | 0.0257 | ok |
| naive, calibration reuse (iid, n_cal=200) | 0.0107 | no violation detected at this configuration |
| blockwise L=50, ρ=0.50 / 0.94 | 0.0248 / 0.0498 | ok |
| **blockwise L=50, ρ=0.99** | **0.2080** | **VIOLATES — domain boundary counterexample** |
| blockwise L=50, regime-switching, context-conditioned p | 0.0475 | ok |
| **blockwise L=50, regime-switching, context IGNORED** | **0.7850** | **VIOLATES — context conditioning is not optional** |
| LR, correct AR(1) null | 0.0088 | ok (exact martingale) |
| **LR, misspecified (iid assumed)** | **0.4467** | **VIOLATES** |

Power (not a validity claim): blockwise L=50 at ρ=0.94 detects a 1σ mean
shift with rate 1.0 at median 400 ticks (16 s at 25 Hz); a 0.5σ shift at rate
0.689, median 1050 ticks. **This is the price of validity: the block length
that restores the bound also sets the latency floor.**

## 8. Honest limitations

1. A3 is unproved for mixing processes; validity at L=50/ρ≤0.94 is
   empirical. A proof route (φ-mixing block coupling bounds) is future work.
2. The declared dependence domain must be enforced at runtime: if measured
   residual autocorrelation exceeds the domain (ρ→0.99 regime), the process
   must widen L or refuse authorization — never silently continue.
3. Calibration-reuse showed no violation *at this configuration*; that is
   not a general license, and fresh-per-block calibration remains the safe
   default when data allows.
4. Restart/recovery accounting is NOT covered by T-1 (goes to T-2), except
   for the initial-state rule in §6.
5. All of this concerns ONE residual stream per hypothesis. Multiplicity
   across hypotheses is T-2 (e-BH pre-registered).
