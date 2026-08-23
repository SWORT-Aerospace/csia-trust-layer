# Proof Status Register

Labels: **PROVED** (assumption-conditional proofs written out) ·
**PROVISIONAL** (argued, not proved) · **EMPIRICAL ONLY** (measured, no proof)
· **REFUTED** (counterexample) · **OPEN**.

| Claim | Status | Evidence |
|---|---|---|
| Calibrator `κp^{κ−1}` is an e-value for super-uniform p; clamp is conservative | **PROVED** | T-1 Lemma 1 |
| Predictable convex combination across dependent residuals is an e-value | **PROVED** | T-1 Lemma 2 |
| Product ACROSS dependent residuals is an e-value | **REFUTED** | measured mean 2.87 (duplicated residuals) |
| Naive per-tick temporal product under CSIA-like smoothing (ρ≈0.94) | **REFUTED** | measured 0.442 vs 0.05 bound |
| T-1 blockwise product, GIVEN block conditional super-uniformity (A3) | **PROVED given A3** | T-1 §5 |
| A3 itself at L=50 for ρ≤0.94 | **EMPIRICAL ONLY** | eval cells 0.0248/0.0498; ρ=0.99 counterexample 0.208 |
| LR e-process under correct conditional null | **PROVED** | T-1 §6; measured 0.0088 |
| LR e-process under misspecified null | **REFUTED** | measured 0.4467 |
| Context-ignorant calibration under regime switching | **REFUTED** | measured 0.7850 |
| Restart validity without first-observation conditioning | **REFUTED** | measured 0.196 (the suite's own bug find) |
| T-2 mission-level error control | **OPEN** | e-BH + α-spending pre-registered |
| T-3 non-double-counting formalization | **OPEN** | Lemma 2 is the base; ownership policy unformalized |
| T-4 identifiability-constrained isolation | **OPEN** | v1 `classify_isolation` + 3E audit are inputs |
| T-5 bounded shadow arbitration | **OPEN** | — |
