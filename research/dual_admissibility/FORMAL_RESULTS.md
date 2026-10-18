# Formal results

Derived from the frozen constants in `csia/diagnosis/bayes.py` and
`csia/trust_engine/engine.py`, then checked against measured replays by
`formal_analysis.py`. Numbers in `results/FORMAL_RESULTS.json`.

Every statement carries a status. None is `PROVED — POSSIBLE NOVEL
CONTRIBUTION`: these are elementary consequences of a naive-Bayes log-likelihood
with a multiplicative gate, and no search was done for prior art.

## Model

```
X_j(t)   numerical measurement / state
V_j(t)   source-reported validity
P_j(t)   provenance state
A_j(t)   operational admissibility        in {0,1}
D_j(t)   diagnostic evidential admissibility  in {0,1}

coupled architecture   D_j = A_j
split architecture     D_j may differ from A_j
```

The implementation, verbatim (`csia/diagnosis/bayes.py:102-131`):

```
ell_{j,h}(t) = log(1 - c_j + eps)   if j in LOW(h)
               log(c_j + eps)       otherwise
ll_h(t)      = sum_j D_j(t) ell_{j,h}(t)
S_h(t)       = (1 - alpha) S_h(t-1) + alpha ll_h(t)
score_h      = log pi_h + M S_h
posterior    = softmax(score)
```

with `eps = 0.02`, `alpha = 0.06`, `M = 1.5`, `pi_nominal = 0.86`, seven fault
hypotheses at `0.02` each.

Define the per-feature discriminating increment

```
delta(c) = log((1 - c + eps)/(c + eps))
```

decreasing in `c`, zero at `c = 1/2`, `delta(0) = +3.931826`,
`delta(1) = -3.931826`.

---

## T1 — evidence deletion

**Statement.** For hypotheses `a`, `b`, the pairwise separation is

```
Delta_ab(t) = sum_{j in LOW(a) Δ LOW(b)}  s_j D_j(t) delta(c_j(t))
```

where `Δ` is symmetric difference and `s_j = +1` if `j in LOW(a)`, `-1`
otherwise. Every feature in **both** `LOW` sets, or in **neither**, contributes
exactly zero. Consequently, if `D_j(t) = 0` for every `j` in the symmetric
difference, `Delta_ab(t) = 0` and the tick carries no information
distinguishing `a` from `b`.

**Proof.** `ell_{j,a} - ell_{j,b}` is `log(1-c+eps) - log(c+eps) = delta(c)`
when `j` is in `LOW(a)` only, its negation when in `LOW(b)` only, and `0`
otherwise because both terms are then the same expression. Multiply by `D_j`
and sum. ∎

**Status: PROVED — NOVELTY NOT ESTABLISHED.**

---

## T2 — self-masking faults

**Statement.** Call a fault `F` *self-masking* for the pair `(a,b)` under
coupling if

1. `F` drives `A_k -> 0` for a set of relations `K`, and
2. `LOW(a) Δ LOW(b) ⊆ K`.

Then under `D = A`, `Delta_ab(t) = 0` for every tick `F` is active: **the
hypothesis the fault supports is unidentifiable from its alternative exactly
while the fault is happening.** Condition (2) is necessary as well as
sufficient for `Delta_ab` to vanish identically.

**Instance in this system, by construction.** `a = gps_fault`,
`b = nominal`. `LOW(gps_fault) = ["phys_gps"]`, `LOW(nominal) = []`, so the
symmetric difference is `{phys_gps}`, whose gate is
`gvalid * 1[tau > 3] * fresh["gps"]` — and `fresh["gps"]` **is** `A_gps`
(`SOURCE_VALIDITY_ROLE_AUDIT.md`). A GNSS fault that makes the receiver report
no fix satisfies (1) and (2) simultaneously.

**Status: PROVED — NOVELTY NOT ESTABLISHED.**

---

## T3 — what the split can and cannot restore

**Statement.** Splitting `D` from `A` restores identifiability for `(a,b)`
during `F` **if and only if** there exists an observable `j'` with
`j' in LOW(a) Δ LOW(b)` and `D_{j'} > 0` while `F` is active.

Necessity matters as much as sufficiency: with no such `j'`, every term of
`Delta_ab` is zero regardless of how `D` is gated. **No gating policy can
manufacture evidence that was never observed.**

**Corollary — a falsifiable prediction.** If the fault removes the *source*
rather than the *value* — transport loss, a dead receiver, a severed link — no
such `j'` exists and the split provably cannot help.

**Test.** The transport control. `T_TRANSPORT_STARVED` and `P5_PERMANENT`
produce **identical** operational state (A closed for 34.0 s in both) and
opposite diagnoses:

| Condition | `S2a` final `gps_fault` | leading cause |
|---|---|---|
| `P5_PERMANENT` — receiver reports no fix | **0.894386** | `gps_fault` |
| `T_TRANSPORT_STARVED` — healthy receiver, no messages | **0.022723** | `nominal` |

`0.022723` is the coupled steady state from T4 — that is, exactly the prior.
The prediction holds.

**Status: PROVED — NOVELTY NOT ESTABLISHED (corollary EMPIRICALLY CONFIRMED,
N = 1 fixture pair).**

---

## T4 — steady-state posterior

**Statement.** Under a sustained condition the smoother converges, so

```
log P(a)/P(b)  ->  log(pi_a/pi_b) + M delta(c)
```

With `D = 0` the second term vanishes and the ratio returns to the **prior**
ratio: the diagnosis reverts to nominal no matter how severe the fault.

**Numbers.**

| | |
|---|---|
| `log(pi_a/pi_b)` | −3.761200 |
| `delta(0)` | +3.931826 |
| coupled, sustained: `log P(a)/P(b)` | −3.761200 → `P(a) = 0.022727` |
| split, sustained: `log P(a)/P(b)` | +2.136539 → `P(a) = 0.894404` |

**Validation against the implementation** (`P5_PERMANENT`, full eight-cause
softmax, real frozen core):

| Arm | predicted | measured | difference |
|---|---|---|---|
| `S1D` coupled | 0.022727 | 0.022723 | 4 × 10⁻⁶ |
| `S2a` split | 0.894404 | 0.894386 | 1.8 × 10⁻⁵ |

**Status: PROVED — NOVELTY NOT ESTABLISHED. Numerically validated.**

---

## T5 — time to rank reversal

**Statement.** After `D` is gated off, `S_a - S_b` decays as `(1-alpha)^n`
toward zero, so the rank reverses once
`M Delta_0 (1-alpha)^n < -log(pi_a/pi_b)`, giving

```
n = log(threshold / Delta_0) / log(1 - alpha),   threshold = -log(pi_a/pi_b)/M
```

**Numbers.** `threshold = 2.507467`, and from a saturated
`Delta_0 = delta(0) = 3.931826`, `n = 7.29` ticks ≈ **0.29 s** at 25 Hz.

So the coupled architecture forgets a saturated GNSS fault in under a third of
a second of gate closure. That is the quantitative reason `S1` loses on the
real recording: 27.7% of its post-onset ticks have the gate closed, and each
closed run erodes the accumulated evidence far faster than the open runs
rebuild it.

**Status: PROVED — NOVELTY NOT ESTABLISHED.** The reversal *time* was not
measured directly against the replay; only the steady states were. Recorded as
an unvalidated consequence of validated premises.

---

## Information loss

`results/INFORMATION_LOSS_ANALYSIS.json`. The upstream alphabet is
`{OBSERVED_VALID, OBSERVED_INVALID, NOT_OBSERVED}`; two worlds are specified
exactly — a failed receiver `(0.05, 0.90, 0.05)` and a failed link
`(0.05, 0.05, 0.90)`.

| Mapping | downstream classes | `D_KL` downstream | loss | states collapsed |
|---|---|---|---|---|
| `phi_S0` drop-invalid | `{V}, {I,N}` | 0.000000 | **2.456816** | 1 |
| `phi_S1` coupled | `{V}, {I,N}` | 0.000000 | **2.456816** | 1 |
| `phi_S2` split | `{V}, {I}, {N}` | 2.456816 | **0.000000** | 0 |

Upstream `D_KL = 2.456816` nats. Under `phi_S0` and `phi_S1` it is **entirely**
destroyed: the two worlds become the same distribution downstream, so no
downstream procedure whatsoever can tell a failed receiver from a failed link.

These are **exact** numbers for the stated hypothetical distributions, chosen
so the two worlds differ only in which collapsed symbol dominates. They are not
estimates from data; one recording cannot support a KL estimate and none is
offered. The data-processing inequality is textbook and nothing here claims it,
or this application of it, is novel.

## Semantic collapse count

A descriptive implementation metric, not a standardised one: **how many
semantically distinct upstream states are merged downstream.** Measured by
automatic search (`results/COUNTEREXAMPLE_SEARCH_RESULTS.json`) over words in
`{V, I, N}` driven through the real implementation:

| Arm | shortest pair of distinct raw words with identical downstream state |
|---|---|
| `S0` | `('I', 'N')` — **length 1** |
| `S1` | `('VV', 'IV')` — length 2 |
| `S2c2` | `('III', 'INI')` — length 3 |

The minimum distinguishing word length rises 1 → 2 → 3. `S0`'s witness is the
cheapest possible one: a single message reporting no fix is downstream-identical
to no message at all.
