# CSIA-ACEG Evidence — Formal Specification (shared by T-1 … T-5)

**Scope:** definitions used by every theorem document. Nothing here is a
result; results live in T-N documents with explicit status labels.

## Objects

- **Tick** `t ∈ ℕ` at 25 Hz. **Filtration** `F_t`: everything observed up to
  `t` (residuals, contexts, calibration data). Predictable = `F_{t−1}`-measurable.
- **Residual** `r^{(i)}_t`: output of a declared residual factor with units,
  validity context and nominal model (Layer 3).
- **Context** `c_t ∈ C`: flight-phase/dynamics label, predictable.
- **Null** `H_0^h` for hypothesis `h`: all residuals in `h`'s evidence set
  follow their context-conditioned nominal law.
- **p-variable**: `P(p ≤ u) ≤ u` under the null (super-uniform). *Conditional*
  p-variable: the same bound given `F_{t−1}`.
- **e-variable**: `E[e] ≤ 1` under the null. *Conditional* e-variable:
  `E[e_t | F_{t−1}] ≤ 1`.
- **e-process**: `E_t` with `E_t ≥ 0` and `E[E_τ] ≤ 1` for every stopping
  time τ; sufficient condition: nonnegative supermartingale started at 1.
- **Alert at level α**: first `t` with `E_t ≥ 1/α`. Ville: `P(alert | H_0) ≤ α`.

## Theorem registry

| ID | Claim | Status file |
|---|---|---|
| T-1 | Blockwise anytime false-alert control | `T1_BLOCKWISE_EPROCESS.md` |
| T-2 | Mission-level family error control (e-BH, restarts, α_mission) | open |
| T-3 | Non-double-counting of shared evidence | open |
| T-4 | Identifiability-constrained isolation (ambiguity sets) | open |
| T-5 | Bounded shadow arbitration risk | open |

## Global prohibitions (restated as formal constraints)

1. No product across residual streams sharing latent state (violates
   Lemma 2's scope; measured mean 2.87 > 1).
2. No per-tick temporal product without conditional validity (measured 0.442
   vs bound 0.05 at ρ=0.94).
3. No p-value may be described as `P(sensor healthy)`.
4. No heuristic score (CSIA v1 confidence) may enter an e-process.
5. Every e-process restart conditions on its first post-restart observation
   (T-1 §6 counterexample).
