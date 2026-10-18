# NUMERIC EQUIVALENCE SPEC — Phase 4.5 §§24–26

The Tier-B tolerance for the Python ↔ embedded C/C++ comparison.

> **Written before any C exists.** There is no C source in this repository —
> a test asserts `embedded/` contains no `.c`, `.h`, `.cpp` or `.hpp`. Nothing
> below was derived from, calibrated against, or adjusted after a measured
> port error, because there is no port error to have seen.
>
> **§25 is binding: this tolerance is never widened after seeing C.** If a
> port exceeds it, the port is wrong until proven otherwise, and if the
> reference turns out to be wrong instead, that is a v1.1 defect with its own
> commit and its own remeasurement — not a relaxed bound.

---

## 1. THE ARITHMETIC MODEL

| | |
|---|---|
| reference | CPython / NumPy, IEEE-754 **binary64** |
| port | assumed IEEE-754 **binary32** on the target |
| unit roundoff | `u = 2⁻²⁴ = 5.9605e-8` |
| tick rate | 25 Hz |
| longest run | 1500 ticks (60 s) |

Every bound below is derived from `u`, the recurrence, and the run length.
Where a rigorous bound is impractical the spec says so and states a
conservative engineering tolerance with its reasoning, as §25 permits.

## 2. THE FIVE QUANTITIES, DERIVED

### 2.1 Trust — a decaying accumulator

    alpha <- rho*alpha + E          beta <- rho*beta + (1 - E)
    trust  = alpha / (alpha + beta)

A first-order IIR with forgetting factor `rho ≤ rho_max = 0.998` does **not**
accumulate error without bound: a per-step relative rounding of `u` reaches a
steady state of `u / (1 - rho)`.

    u / (1 - 0.998) = 2.980e-5      relative

`trust ∈ [0, 1]`, and the division contributes one further `u`. So the
absolute error in `trust` is bounded by ≈ **3.0e-5**.

    DECLARED   trust        1e-4 absolute      (3.4x headroom)
    DECLARED   alpha, beta  1e-4 relative      (same recursion)

### 2.2 Diagnosis smoothing — a decaying accumulator with a small α

    smoothed <- (1 - a)*smoothed + a*ll,    a = SMOOTH_ALPHA = 0.06

Steady-state relative error `u / a = 9.93e-7`. The log-likelihood magnitude is
bounded by the feature count and the floor: 21 features × `|log(EPS)| =
|log 0.02| = 3.91` gives `|ll| ≤ 82`. So

    9.93e-7 x 82 = 8.15e-5           absolute

    DECLARED   smoothed  1e-3 absolute        (12x headroom)

`score = log_prior + EVIDENCE_MULT * smoothed` scales this by 1.5 → 1.22e-4,
inside the same declared bound.

### 2.3 Posterior — softmax of the score

The softmax Jacobian has spectral norm ≤ ½, so a score perturbation `δ` moves
any probability by at most `δ/2`:

    0.5 x 1.5 x 8.15e-5 = 6.11e-5    absolute

    DECLARED   posterior  1e-3 absolute        (16x headroom)

In practice the posterior saturates near 1.0 on most fault ticks, where the
softmax derivative is far smaller than the bound — so this is loose by
construction, deliberately.

### 2.4 CUSUM `S` — **the worst case in the set**

    z = (lam - mu0) / sigma0
    S <- max(0, S + z - k)

`S` has **no forgetting factor**. Error accumulates additively and the clamp
at zero is the only thing that resets it, so this is the one quantity whose
bound grows with run length. Two terms:

| term | source | bound |
|---|---|---|
| standardisation | `3u` relative on each `z`, and `Σ\|z\| ≈ h + N·k` at the alarm | `3u(500 + 1500·0.5)` = **2.24e-4** |
| accumulation | one rounding of `S` per step, `\|S\| ≤ h` | `N·u·h = 1500 · 5.96e-8 · 500` = **4.47e-2** |

    total <= 4.49e-2                 absolute

The `Σ|z|` term is small because of a self-limiting property worth stating: a
large `|z|` reaches `h` in few steps and a small `|z|` takes many, so the
product is pinned near `h` either way.

    DECLARED   CUSUM S  0.5 absolute          (11x headroom, 0.1% of h)

### 2.5 Summary — the frozen Tier-B tolerance

| quantity | derived bound | **DECLARED** | headroom |
|---|---:|---:|---:|
| `trust[node]` | 3.0e-5 abs | **1e-4 abs** | 3.4× |
| `alpha`, `beta` | 3.0e-5 rel | **1e-4 rel** | 3.4× |
| `diagnosis.smoothed`, `score` | 1.22e-4 abs | **1e-3 abs** | 8.2× |
| `diagnosis.posterior` | 6.1e-5 abs | **1e-3 abs** | 16× |
| `sequential.S[node]` | 4.49e-2 abs | **0.5 abs** | 11× |

Headroom is deliberate and bounded: enough that a correct port is not failed
by an implementation detail (a different but valid summation order, a fused
multiply-add, a `logf` differing in the last ulp), not so much that a real
defect hides inside it. Nothing here was chosen to accommodate a number
anyone has measured.

## 3. THE COMPARISON RULE

- **Tier A is exact.** Any difference on any tick of any case fails the port.
  A tier-A difference is never resolved by relaxing tier A.
- **Tier B is compared per tick against the table above.** The **maximum**
  deviation over all cases is reported, never the mean — a mean hides exactly
  the excursion that matters.
- **Tier C is not compared.** Event ids, content hashes, configuration and
  software hashes hash the *implementation*, not the behaviour.

## 4. WHY A NUMERIC BOUND IS NOT THE REAL QUESTION — §26

A numeric difference only matters if it can change a **discrete** state.
`DECISION_MARGIN_AUDIT.csv` computes, for every golden tick, the distance from
each numeric quantity to the boundary that would change a decision:

| boundary | source |
|---|---|
| `nav_caution` 0.75 | `FailsafeConfig`, gps trust |
| `heading_caution` 0.60 | mag trust |
| `att_caution` 0.82 / `att_emergency` 0.70 | `max(imu0, imu1)` |
| `power_critical` 0.70 | battery trust |
| `struct_critical` 0.60 | vibration trust |
| CUSUM `h` = 500 | `S` per covered node |
| eligibility thresholds | the same inherited trust thresholds |
| diagnosis ranking | leader-to-runner-up score margin |

A tick is flagged **`NUMERICALLY_NEAR_BOUNDARY`** when the declared tolerance
for the relevant quantity is at least the distance to its boundary — that is,
when a conforming port could legitimately land on the other side.

**Those ticks are where Phase 5 has to look.** They are not failures and they
are not excused: they are the finite, enumerated set of places where an
exact-tier disagreement could arise from arithmetic alone rather than from a
logic error, and knowing them in advance is the difference between debugging a
port and arguing about one.

## 5. WHAT THIS SPEC DOES NOT COVER

- **Fixed-point.** Binary32 is assumed. A fixed-point port needs its own
  derivation; nothing here transfers.
- **Fused multiply-add and reassociation.** Assumed to be absorbed by the
  headroom, not separately bounded. A target that reassociates aggressively
  could exceed a bound that a strictly-ordered one meets.
- **`exp` and `log` accuracy.** Assumed correctly-rounded to within 1 ulp.
  A libm worse than that invalidates §2.2 and §2.3.
- **Non-determinism.** Threading, SIMD reductions and `-ffast-math` are out of
  scope and must not be enabled: they break the assumption that the port is
  computing the same function at all.
- **The reference's own error.** Bounds are Python-binary64 against
  target-binary32. The binary64 reference is treated as exact, which it is not
  — its own error is ~2⁻⁵³ and is negligible at these tolerances, but it is an
  assumption rather than a proof.
