# Closest Prior-Art Baselines

**Novelty status: `BLOCKED_EXTERNAL_ACCESS`.** Nothing in this document
supports a novelty claim in either direction.

## 1. The access check, reproducibly

Run this session, once, from this container:

| endpoint | result |
|---|---|
| `https://api.crossref.org/works?query=active+fault+diagnosis+input+design&rows=1` | `curl (56) CONNECT tunnel failed, response 403` |
| `https://arxiv.org/abs/1903.00000` | `curl (56) CONNECT tunnel failed, response 403` |
| `https://doi.org/10.1016/j.automatica.2015.01.001` | `curl (56) CONNECT tunnel failed, response 403` |

The egress proxy denies CONNECT to scholarly endpoints as a matter of
organisation policy. Per the work order, structurally denied endpoints were not
retried for hours. No full text is reachable and none is stored in this
repository. The outstanding request list is
`research/active_evidence/realized_current/EXTERNAL_SOURCE_REQUEST.md`, which
names ten sources and what each one blocks; it remains accurate and is not
edited here.

## 2. What these baselines are, and are not

They are **textbook reconstructions**: each is written from the defining
equation of a standard objective, implemented over the same 72-action space
every other strategy uses, and labelled
`TEXTBOOK_RECONSTRUCTION_NOT_A_PAPER_REPRODUCTION` in code.

They are **not** reproductions of any specific paper's method. Reconstructing a
named author's formulation from memory and then reporting a comparison against
it would misrepresent their work and inflate this one. Where a formulation
could not be reconstructed honestly, it is left unimplemented and recorded as a
gap.

| baseline | implemented | what it computes |
|---|---|---|
| persistent excitation | yes | `λ_min` of the order-`n` regressor covariance |
| Fisher-information input design | yes | `J`, `det J`, `λ_min(J)`, `var(R)` from the CRB |
| finite-model active discrimination | yes | max-min normalised separation between hypothesis outputs |
| set-membership volume reduction | yes | exact area of the bounded-noise `(E, R)` polytope, by vertex enumeration |
| conventional post-execution validation | yes | OLS with textbook standard error and interval, **no staleness semantics** |
| constrained robust / tube-MPC active diagnosis | **no** | see §6 |

## 3. The most useful thing this comparison found

**P7a is the classical A-optimal design for the resistance parameter.**

Inverting the 2×2 Fisher matrix for `(E, R)` under `V = E − R·I + η` gives
`var(R) = σ_V²/S_II` exactly. Minimising the Cramér–Rao variance of `R` is
therefore *identically* maximising the centred second moment of current, which
is P7a's objective. Measured, not assumed: over the 72-action space,
`argmin var(R)`, `argmax S_II` and P7a's selection are all
`doublet_10A_8s`.

And P7a loses to the hindsight oracle by a median factor of **11** while
spending 2.4× the energy (`ORACLE_TAXONOMY.md` §4).

So the prior phase's "the oracle was not an oracle" is a sharper statement than
it looked: the object that failed is the textbook optimal design, and it failed
because the model it is optimal *for* is not the plant. That is a statement
about model mismatch, not about optimal-design theory, and it is the honest
framing of the whole result.

Two other classical criteria pick different actions on the same space —
`det J` (which weights the intercept too) selects `cosine1_10A_12s`, and the
order-4 persistent-excitation level selects `doublet_14A_4s`. None of the three
agrees with the outcome oracle.

## 4. Set-membership invalidation separates the plants

The bounded-noise feasible set for `(E, R)` is empty when no two-parameter
model can explain the data within the assumed bound. Bisecting on that bound
gives a model-invalidation threshold per plant, with `σ_V = 0.020 V`:

| plant | invalidation threshold | in sigmas |
|---|---|---|
| Q0 zero-RC | 0.0493 V | 2.46 σ |
| Q1 one-RC | 0.0981 V | 4.90 σ |
| Q2 richer mismatch | 0.1462 V | 7.31 σ |

A classical baseline from the 1980s separates Q0, Q1 and Q2 cleanly, on the
same data where the RCEC's own margin is **bit-identical across all three**.
That is independent corroboration of H5 from outside this project's machinery,
and it is also a caution: the discrimination the certificate cannot do is not
hard, it is simply not what the certificate computes.

## 5. What the conventional fit misses

`classical_fit` is OLS with a textbook standard error and a 95% interval, and
it has no concept of staleness — it never asks whether the window it was given
is the window that was planned.

On a full 8 s execution with a true 0.060 Ω resistance it returns an interval
that covers the truth. On the **same run truncated to 25%** it returns an
interval that does **not** cover the truth, in the same confidence language,
with no indication that anything is different. The RCEC routes that case to
`ABORTED_INCOMPLETE` and refuses.

That contrast is the clearest statement available here of what the staleness
semantics buy, and it is a single instance rather than a rate — one seed, one
truncation fraction — so it is reported as an illustration, not a measurement
of how often it matters.

## 6. The baseline that is deliberately missing

`constrained_robust_tube_mpc_active_diagnosis`. A tube-MPC formulation needs a
receding-horizon optimiser over a disturbance-invariant tube, which is a
substantially different experimental object from a selection rule over a fixed
action space. Reconstructing one from memory and presenting it as the closest
prior art would misrepresent both it and this comparison. It is left
unimplemented, recorded in `baselines.NOT_IMPLEMENTED` with this reason
attached in code, and it is a known gap in the comparison.

## 7. What would change the novelty status

Reading the sources listed in `EXTERNAL_SOURCE_REQUEST.md`, and running a
claim-element comparison against the exact claim language. Until then the
status is `BLOCKED_EXTERNAL_ACCESS` and **no novelty may be inferred from a
failed search.**
