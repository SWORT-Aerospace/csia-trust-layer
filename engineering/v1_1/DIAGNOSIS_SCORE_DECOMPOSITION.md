# DIAGNOSIS SCORE DECOMPOSITION — Phase 2A

§2. The frozen `DiagnosisCore` audited, not redesigned. Every statement below
is checked by `tests/test_v1_1_support.py`, not asserted in prose.

`csia/diagnosis` is **FROZEN**. Nothing in Phase 2 modifies it. The analysis
**imports** its constants rather than copying them, so the decomposition
cannot drift from production.

---

## 1. WHAT THE CORE COMPUTES

From `csia/diagnosis/bayes.py`. Per tick, per hypothesis *h*:

```
ll[h]       = Σ_j  gate_j · ( log(1 − c_j + EPS)   if j ∈ LOW[h]
                              log(c_j + EPS)       otherwise )

smoothed[h] = (1 − α)·smoothed_prev[h] + α·ll[h]

score[h]    = log_prior[h] + EVIDENCE_MULT · smoothed[h]

posterior   = softmax(score)
```

| constant | value | source |
|---|---|---|
| `EPS` | 0.02 | `bayes.py:37` |
| `SMOOTH_ALPHA` (α) | 0.06 | `bayes.py:38` — ~15-tick accumulation |
| `EVIDENCE_MULT` | 1.5 | `bayes.py:39` |
| `PRIOR_NOMINAL` | 0.86 | `bayes.py:40` |
| gate cut-off | 1e-9 | `bayes.py:110` (`if gate <= 1e-9: continue`) |

Eight hypotheses: `nominal`, `gps_fault`, `imu0_bias_drift`,
`imu1_bias_drift`, `mag_interference`, `power_fault`, `vibration_anomaly`,
`unexpected_maneuver`. Prior: 0.86 on `nominal`, 0.02 on each of the other
seven.

Twenty-one features on the standard scenario: comparator edges, `phys_*`
physics checks, and four `temp_*` temporal-stability scores.

## 2. THE DECOMPOSITION, AND ITS EXACTNESS

```
contribution_j[h] = gate_j · ( lo_j  if j ∈ LOW[h] else hi_j )
lo_j = log(1 − c_j + EPS)      hi_j = log(c_j + EPS)
```

Two obligations, both discharged by test:

**`Σ_j contribution_j[h] = ll[h]` — exactly**, with `atol=0, rtol=0`.
(`test_the_per_term_contributions_sum_to_the_core_log_likelihood`)

**The reconstructed posterior equals production.** Measured over all nine
catalogue scenarios, 1500 ticks each:

    max |reconstructed − production|  =  9.437e-16

That is one to four ULP, from summation order (the core sums over
hypotheses inside a feature loop; the decomposition sums a `(K, J, H)` array
over `J`). It is **not** bit-identical, and the report says so rather than
rounding the claim up.
(`test_the_decomposition_reconstructs_the_production_posterior`)

## 3. THE PAIRWISE DECOMPOSITION (§3)

```
Δ_prior(a,b)    = log_prior[a] − log_prior[b]
Δ_evidence(a,b) = EVIDENCE_MULT · (smoothed[a] − smoothed[b])
Δ_total(a,b)    = Δ_prior + Δ_evidence  =  score[a] − score[b]
```

`Δ_total` reproduces the score ranking by construction, since `softmax` is
strictly monotone. **This is a score decomposition, not a probability
interpretation** — §3's instruction, and the frozen core's own docstring is
equally careful about it.

One number worth having in front of you:

    Δ_prior(nominal, any fault) = log(0.86 / 0.02) = 3.761

so with `EVIDENCE_MULT = 1.5` the evidence must move the smoothed
log-likelihood difference by **2.507** before it overturns the nominal prior.
Whether it has is exactly what `prior_sensitive` reports.

## 4. TERM-LEVEL DISCRIMINATION (§4)

```
δ_j(a,b) = contribution_j[a] − contribution_j[b] = gate_j · (t_j[a] − t_j[b])
```

Non-zero exactly when all three hold:

1. `gate_j > 0` — active;
2. `j ∈ LOW[a] XOR j ∈ LOW[b]` — the hypotheses disagree about the feature;
3. `c_j ≠ 0.5` — not at the likelihood's indifference point.

Condition 2 is fixed by the `CAUSES` table. Condition 1 is runtime
availability. **A term contributing identically to both does not count.**

### The consequence that drives the whole phase

`CAUSES["nominal"] = []` and `CAUSES["gps_fault"] = ["phys_gps"]`, so their
symmetric difference is exactly `{phys_gps}` — asserted by test, not read off
by eye. `phys_gps` is therefore the **only** term that can ever discriminate
those two hypotheses.

`csia/runtime/online.py:613` multiplies every physics gate by its sensor's
freshness:

```python
P = {n: (lam, gate * float(fresh[n])) for n, (lam, gate) in P.items()}
```

So when the GNSS fix goes, `fresh["gps"]` is false, `phys_gps` leaves the
active set, and `nominal` vs `gps_fault` has **no discriminating evidence at
all** — while the posterior, driven by smoothed history and a 0.86 prior,
stays near 1.0.

That is not a bug in the core. It is the core being asked a question its
current evidence cannot answer, and v1 had no way to say so. Phase 2 gives it
one.

## 5. WHAT THE DECOMPOSITION DOES NOT CLAIM

- It is not a new inference method. It is the existing score, written out
  term by term.
- `contribution_j[h]` is a summand of a naive-Bayes log-likelihood. It is not
  a probability, an information quantity, or a causal effect.
- The instantaneous decomposition (§4) and the smoothed score (§1) are
  different objects and are kept apart. "Active evidence" always means the
  instantaneous, gated feature set; the score always means the smoothed one.
  Conflating them would let historical evidence masquerade as current
  support, which is the exact failure Phase 2 exists to expose.
