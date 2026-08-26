# Formal audit: T1–T5 restated, with assumptions and their counterexamples

The exploratory package reported T1–T5 as `PROVED — NOVELTY NOT ESTABLISHED`.
This document restates each self-contained, makes every assumption explicit,
gives the implementation correspondence, and — the part the exploratory version
omitted — **states what fails when each assumption is removed**.

Prior-art status is assigned separately from proof status, per item 4. A proof
licenses nothing about novelty.

## Common definitions

Let `H` be a finite hypothesis set, `J` a finite feature index set.

* `c_j(t) ∈ [0,1]` — the consistency of feature `j` at tick `t`.
* `D_j(t) ∈ {0,1}` — diagnostic evidential admissibility of `j`.
* `A_j(t) ∈ {0,1}` — operational admissibility.
* `LOW(h) ⊆ J` — the features cause `h` drives low.

The frozen implementation (`csia/diagnosis/bayes.py:102-131`):

```
ell_{j,h}(t) = log(1 - c_j(t) + eps)   if j ∈ LOW(h)
               log(c_j(t) + eps)       otherwise
ll_h(t)      = Σ_j D_j(t) · ell_{j,h}(t)
S_h(t)       = (1-α)·S_h(t-1) + α·ll_h(t)
score_h(t)   = log π_h + M·S_h(t)
posterior    = softmax(score)
```

`eps = 0.02`, `α = 0.06`, `M = 1.5`, `π_nominal = 0.86`, seven fault
hypotheses at `0.02`.

Define `δ(c) = log((1-c+eps)/(c+eps))`, strictly decreasing on `[0,1]`,
`δ(0) = +3.931826`, `δ(1/2) = 0`, `δ(1) = −3.931826`.

**Standing assumptions**, used by every proposition below:

* **(A1)** The gate enters the log-likelihood *multiplicatively and linearly*,
  as above.
* **(A2)** `D_j ∈ {0,1}`. The implementation permits any non-negative weight;
  every arm in this work uses `{0,1}`.
* **(A3)** Features are combined by summation — a naive-Bayes form with no
  interaction terms.
* **(A4)** `LOW(h)` is fixed and known.

---

## T1 — Evidence deletion

**Proposition.** For any `a, b ∈ H`,

```
Δ_ab(t) := ll_a(t) − ll_b(t) = Σ_{j ∈ LOW(a) Δ LOW(b)} s_j · D_j(t) · δ(c_j(t))
```

where `Δ` is symmetric difference and `s_j = +1` if `j ∈ LOW(a)`, `−1` if
`j ∈ LOW(b)`. Hence if `D_j(t) = 0` for all `j ∈ LOW(a) Δ LOW(b)`, then
`Δ_ab(t) = 0`.

**Proof.** For `j ∈ LOW(a) ∩ LOW(b)` and for `j ∉ LOW(a) ∪ LOW(b)`, the two
terms `ell_{j,a}` and `ell_{j,b}` are the same expression, so their difference
is 0. For `j ∈ LOW(a) \ LOW(b)`:
`ell_{j,a} − ell_{j,b} = log(1−c+eps) − log(c+eps) = δ(c_j)`. Symmetrically for
`j ∈ LOW(b) \ LOW(a)` the difference is `−δ(c_j)`. Multiply by `D_j` and sum
over `J`. ∎

**Implementation correspondence.** `bayes.py:104-121`: the loop skips any
feature with `gate <= 1e-9`, and otherwise adds `gate * (lo if fname in low
else hi)`. `gate` is `D_j`.

**Remove (A1) — a non-linear gate.** If the gate entered as, say,
`ell^{D_j}`, then `D_j = 0` would give `ell^0 = 1` — a constant contribution
rather than no contribution — and the difference would not vanish. The
proposition is specific to a multiplicative-linear gate.

**Remove (A3) — feature interactions.** With a term `g(c_j, c_k)` spanning a
gated and an ungated feature, gating `j` off need not remove its influence.
`Δ_ab` could remain non-zero even with `D_j = 0` for every discriminating `j`.

**Status: PROVED — KNOWN/SUBSUMED.** This is elementary algebra on a
log-likelihood ratio, and the general statement (an observation that is not
made cannot contribute to a likelihood ratio) is standard.

---

## T2 — Self-masking faults

**Definition.** A fault `F` is *self-masking* for `(a,b)` under coupling if

1. `F ⟹ A_k(t) = 0` for all `k` in some set `K`, while `F` is active;
2. `LOW(a) Δ LOW(b) ⊆ K`.

**Proposition.** Under `D = A`, `F` self-masking for `(a,b)` implies
`Δ_ab(t) = 0` for every tick `F` is active. Condition (2) is also *necessary*
for `Δ_ab` to vanish identically for all consistency assignments.

**Proof.** Sufficiency is T1 with `D_j = A_j = 0` on `LOW(a) Δ LOW(b) ⊆ K`.
Necessity: suppose `∃ j* ∈ (LOW(a) Δ LOW(b)) \ K`. Then `D_{j*} = A_{j*}` is
not forced to 0 by `F`, and choosing `c_{j*} ≠ 1/2` gives
`δ(c_{j*}) ≠ 0`, so `Δ_ab ≠ 0` for that assignment. ∎

**Note on the necessity direction.** It is *for all consistency assignments*.
For a particular assignment, `Δ_ab` may vanish by cancellation between two
discriminating features with opposite signs. The proposition does not claim
otherwise.

**Implementation correspondence.** `a = gps_fault`, `b = nominal`.
`CAUSES["gps_fault"] = ["phys_gps"]` (`bayes.py:47`), `LOW(nominal) = []`, so
`LOW(a) Δ LOW(b) = {phys_gps}`. The gate of `phys_gps` is
`gvalid · 1[τ>3] · fresh["gps"]` (`online.py:573, 613`), and `fresh["gps"]` is
`A_gps` (`failsafe.py:100, 145`). A GNSS fault making the receiver report no
fix satisfies (1) with `K ⊇ {phys_gps}` and hence (2).

**Remove (A4) — a richer hypothesis map.** If `gps_fault` had a second
supporting feature outside `K`, (2) would fail and the fault would not be
self-masking. **The singleton feature set is what makes this system
vulnerable, not the coupling alone.** That is worth stating plainly: a
diagnostic architecture with redundant support for each hypothesis is less
exposed to this defect regardless of whether `D` is split from `A`.

**Status: PROVED — KNOWN/SUBSUMED.** The containment condition is a
restatement of "the fault removed the only observation that could witness it",
which is the classical diagnosability-under-partial-observation question.

---

## T3 — What the split can and cannot restore

**Proposition.** Under a fault `F`, splitting `D` from `A` yields
`Δ_ab(t) ≠ 0` for some tick during `F` **iff** there exists `j' ∈ LOW(a) Δ
LOW(b)` that is observable during `F` with `D_{j'}(t) > 0` and
`c_{j'}(t) ≠ 1/2`.

**Proof.** Immediate from T1: `Δ_ab` is a sum over `LOW(a) Δ LOW(b)` of terms
`s_j D_j δ(c_j)`. If no term has both `D_j > 0` and `δ(c_j) ≠ 0`, the sum is 0
regardless of how `D` is gated. Conversely a single such term with no
cancelling partner makes the sum non-zero. ∎

**Corollary (the transport prediction).** If `F` removes the *source* — no
message arrives — then no `j'` derived from that source is observable, so no
gating policy can restore `Δ_ab`. **The split provably cannot help against
transport loss.**

**Implementation correspondence and test.** `T_TRANSPORT_STARVED` and
`P5_PERMANENT` were measured with identical `A` (closed 34.0 s in both). Under
the split, final `gps_fault` was 0.894386 for sensor-invalid and 0.022723 —
exactly the prior — for transport loss. The corollary holds. *(Development
data; this is where the corollary came from, not confirmation of it.)*

**Remove (A2) — fractional `D`.** With `D_j ∈ [0,1]`, "restores" becomes a
matter of degree and the iff becomes `D_{j'} > 0`, which is what is stated. No
change.

**Status: PROVED — KNOWN/SUBSUMED.** "You cannot infer from an observation you
did not make" is not a contribution.

---

## T4 — Steady-state posterior

**Proposition.** Under a sustained condition in which every `c_j` is constant,
`S_h → ll_h`, so for any pair

```
log P(a)/P(b) → log(π_a/π_b) + M · Σ_j s_j D_j δ(c_j)
```

With `D_j = 0` on the discriminating set, the second term vanishes and the log
posterior ratio returns to the **prior** ratio.

**Proof.** `S_h(t) = (1-α)S_h(t-1) + α·ll_h` is a contraction with fixed point
`ll_h` for `α ∈ (0,1]`; the softmax over two hypotheses is monotone in the
score difference. ∎

**Numbers.** `log(π_gps_fault/π_nominal) = −3.761200`; `δ(0) = +3.931826`;
coupled steady `P(fault) = 0.022727`; split steady `P(fault) = 0.894404`.

**Implementation correspondence, measured.** Full eight-cause softmax on the
real frozen core, sustained invalidity: coupled 0.022723 (|Δ| = 4 × 10⁻⁶),
split 0.894386 (|Δ| = 1.8 × 10⁻⁵).

**Remove "sustained".** For an alternating condition the smoother does not
converge and the steady-state expression does not apply. This is exactly why
the exploratory package found the split's value depends on *sustained* closure
duration rather than closed fraction — T4 only bites when the smoother has time
to converge.

**Status: PROVED — KNOWN/SUBSUMED.** Convergence of an exponential smoother to
its input, composed with a softmax.

---

## T5 — Time to rank reversal

**Proposition.** If `D` is gated off at `t_0` when the smoothed difference is
`Δ_0`, the rank of `(a,b)` reverses after

```
n = log(θ / Δ_0) / log(1-α),      θ = −log(π_a/π_b) / M
```

ticks, provided `Δ_0 > θ > 0`.

**Numbers.** `θ = 2.507467`; from a saturated `Δ_0 = δ(0) = 3.931826`,
`n = 7.29` ticks ≈ **0.29 s** at 25 Hz.

**Implementation correspondence: NOT MEASURED.** The exploratory package
validated the steady states, not the transient. This proposition is a
consequence of validated premises whose own prediction has never been checked
against a replay.

**Remove "gated off at `t_0` and stays off".** For intermittent gating the
decay is interrupted and `n` is not the reversal time; the process becomes a
random walk in `S` driven by the duty cycle. **T5 as stated applies only to a
single sustained closure.**

**Status: PROVED — KNOWN/SUBSUMED, and UNVALIDATED.** Flagged in the
preregistration as the one derived quantity a confirmatory campaign could
cheaply test and has not.

---

## Summary

| | Proof | Prior-art status | Implementation correspondence |
|---|---|---|---|
| T1 | valid | KNOWN/SUBSUMED | verified |
| T2 | valid, necessity qualified | KNOWN/SUBSUMED | verified |
| T3 | valid | KNOWN/SUBSUMED | corollary measured on dev data |
| T4 | valid | KNOWN/SUBSUMED | measured to 1.8 × 10⁻⁵ |
| T5 | valid | KNOWN/SUBSUMED | **never measured** |

**No proposition is assigned `PROVED — POSSIBLE NOVEL CONTRIBUTION`.** The
exploratory package's `PROVED — NOVELTY NOT ESTABLISHED` labels are hereby
downgraded to `KNOWN/SUBSUMED` on the strength of the prior-art search
(`PRIOR_ART_MATRIX.md`): observation-mask and partition formulations of
diagnosability already cover T1–T3, and T4–T5 are elementary properties of the
smoother.

The two things that remain the exploratory work's own are **not theorems**:
that this implementation couples `A` and `D` in one variable, and the measured
size of what that costs.
