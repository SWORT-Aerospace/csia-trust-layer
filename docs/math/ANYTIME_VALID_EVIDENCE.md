# Anytime-Valid Evidence — Critique of the Proposed Construction

**Slice:** ACEG first response · **Status of verdict:** CONDITIONALLY VALID
**Simulation:** `docs/math/proofs/eprocess_null_simulation.py` (4000 paths × 2000 steps)

---

## 1. The proposed construction

```
e_t      = κ · p_t^(κ−1),          0 < κ < 1
m_{h,t}  = Σ_e π_{h,e,t} · e_{e,t}
E_{h,t}  = Π_{s≤t} m_{h,s}
```

## 2. Formal setting (stated, as required)

- **Filtration** `F_t = σ(all sensor samples, comparator residuals, context
  labels and calibration data available up to and including tick t)`.
- **Null** `H_0^h`: the sources named by hypothesis *h* are behaving according
  to their context-conditioned nominal model — i.e. every residual assigned to
  *h* is exchangeable with its calibration set within its declared context.
- **Required of each per-time e-value**: `E[m_{h,t} | F_{t−1}] ≤ 1` under
  `H_0^h`. **Conditional**, not marginal. This is the load-bearing condition.
- **Required of weights**: `π_{h,e,t}` must be `F_{t−1}`-measurable
  (predictable) and satisfy `Σ_e π_{h,e,t} ≤ 1`.

## 3. Component-by-component verdict

### 3.1 The calibrator `κ p^(κ−1)` — **VALID (PROVED, standard)**

A p-to-e calibrator must satisfy `∫₀¹ f(p) dp ≤ 1` (Vovk & Wang 2021).

`∫₀¹ κ p^(κ−1) dp = [p^κ]₀¹ = 1` exactly, for every κ > 0. Admissible.

> Numerical caution, not a mathematical one: for κ < 1 the integrand diverges
> as p → 0, so naive quadrature overestimates (measured 1.354 at κ = 0.2 by
> trapezoid). The **implementation** must clamp `p ≥ p_min` and document the
> resulting conservatism; the mathematics is exact.

### 3.2 Convex combination across residuals — **VALID under arbitrary dependence**

By linearity of expectation, if each `e_e` is an e-value and `π` is predictable
with `Σπ ≤ 1`, then `E[Σ π e] ≤ 1` **regardless of dependence between
residuals**. Measured on maximally dependent residuals (`e₂ = e₁`):

| statistic | mean | required |
|---|---|---|
| `e` | 0.9989 | ≤ 1 ✅ |
| `(e₁+e₂)/2` (sum) | 0.9989 | ≤ 1 ✅ |
| `e₁·e₂` (product) | **2.8677** | ≤ 1 ❌ |

**The construction is right to SUM across residuals and would be badly wrong to
multiply across them.** CSIA's residuals are heavily dependent by design (they
share one truth state), so this choice is essential, not incidental.

### 3.3 Product over time — **INVALID AS APPLIED TO CSIA**

`E_t = Π m_s` is a non-negative supermartingale, and Ville's inequality
`P(∃t: E_t ≥ 1/α) ≤ α` holds, **only if** each `m_s` is a *conditional*
e-value given `F_{s−1}`.

Split-conformal p-values are **marginally** super-uniform but not
conditionally so when (a) one fixed calibration set is reused at every tick,
and (b) residuals are autocorrelated.

**CSIA is squarely in the failure regime.** Its diagnosis evidence is
exponentially smoothed with `SMOOTH_ALPHA = 0.06` (≈15-tick memory), giving
lag-1 autocorrelation ρ ≈ 0.94.

Simulation, 4000 paths × 2000 steps, κ = 0.5, threshold 1/α = 20 (α = 0.05),
p-values **exactly marginally Uniform(0,1)** in both arms:

| null process | P(ever E ≥ 20) | Ville bound |
|---|---|---|
| i.i.d. uniform (conditionally valid) | **0.0230** | 0.0500 ✅ |
| AR(1) ρ = 0.94, marginally uniform | **0.4540** | 0.0500 ❌ |

**A 9× violation of the claimed false-alert bound.** Applying the proposed
construction to CSIA residuals as they exist today would advertise 5% and
deliver ~45%.

Simulation cannot prove the theorem; it *did* falsify the naive
implementation, which is exactly its role here.

## 4. Verdict

**CONDITIONALLY VALID.** The calibrator and the cross-residual combination are
correct and standard. The temporal product is valid **only** under conditional
super-uniformity, which CSIA's smoothed residuals violate.

## 5. Required repairs (ranked)

1. **Decorrelated blocking (recommended first).** Emit one e-value per block
   of length exceeding the residual decorrelation time (for ρ = 0.94, ~50
   ticks ≈ 2 s), using a block-level statistic. Restores approximate
   conditional validity at the cost of latency — a trade that must be measured,
   not assumed.
2. **Conditional calibration.** Recompute nonconformity against a calibration
   set conditioned on context *and* on the recent residual state, so
   `p_t | F_{t−1}` is super-uniform by construction.
3. **Direct e-values without p-values.** Build a likelihood-ratio /
   universal-inference e-value against a parametric context-conditioned null,
   bypassing conformal calibration and its exchangeability requirement.
4. **Reduce smoothing in the evidence path.** The 15-tick EW window exists for
   the *heuristic* diagnoser. The evidence channel could consume less-smoothed
   residuals, trading variance for validity.

Options 1 and 3 are the two that can carry a theorem. Option 2 is hard to
verify. Option 4 changes v1 behaviour and is out of scope while v1 is frozen.

## 6. Multiplicity

With several hypotheses monitored simultaneously, per-hypothesis control does
not give family-level control. **e-BH** (Wang & Ramdas 2022) provides FDR
control from e-values **under arbitrary dependence**, which suits a hypothesis
set that shares residuals. This is the correct tool and is pre-registered here
before any implementation.

## 7. Restarts, recovery, nonstationarity

Not yet addressed and **must not be hand-waved**: an e-process that has
accumulated evidence does not reset when a fault clears. Candidate treatments
(to be evaluated, not assumed): resetting on a declared context change with a
spent-alpha ledger; running parallel processes per context; or a decaying
e-process with an explicit validity statement. Each changes the guarantee and
each needs its own proof.
