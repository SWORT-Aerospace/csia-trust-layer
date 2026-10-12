# Censoring-Aware Comparison Metrics

**Research only. Post-freeze. Quarantined.**
Implementation: `csia_independent_validation/evaluator.py`. Tests:
`tests/test_iv_evaluator.py`.

## 1. The failure being replaced

The prior phase preregistered a drift-interaction scalar and computed it from
the detection frontier. The frontier encodes "this method never resolved
anywhere on the grid" as `float("inf")`, and the interaction is a difference of
differences, so the moment any arm never resolved the statistic became `NaN`.

That failure is preserved in the ledger as `A14`-adjacent evidence and in
`RESULTS_LOCKED.md`. It is not repaired retroactively.

The underlying mistake is treating an unresolved case as an infinitely large
magnitude. It is not: it is a **right-censored observation**. All that is known
is that the frontier lies above the largest magnitude tested.

## 2. Three metrics, all reported, one declared primary

### Grid resolution area `A_s` — primary input

For the frozen magnitude grid `D = {0.002, 0.004, 0.006, 0.010, 0.020, 0.040}`:

```
A_s = (1/|D|) Σ_j P_s(resolve | d_j)
```

A mean of probabilities. Always in `[0, 1]`, always finite, defined whether a
method resolves everywhere or nowhere. A method that never resolves scores
exactly `0`, which is a number and not a symbol.

### Finite drift interaction `I_s` — **the preregistered primary statistic**

```
I_s = (A_{s,drift} − A_{P0,drift}) − (A_{s,no drift} − A_{P0,no drift})
```

Difference in differences against the passive baseline, in units of resolution
probability. Bounded in `[−2, 2]`.

`drift_interaction` **raises** on any argument that is not a probability in
`[0, 1]`, including `inf` and `NaN`. That is deliberate and it is the direct
fix: the previous statistic failed silently, produced `NaN`, and was discovered
only when somebody read the output. This one refuses the input that caused it.

### Censored frontier — reported, never arithmetic

`censored_frontier` returns the smallest magnitude reaching the 90% target when
one exists, and otherwise the **string** `"> 0.04"`. Returning a string rather
than a float is not a presentation choice; it makes the value impossible to
feed into arithmetic by accident, which is how the old statistic died.

### Paired margin difference — also reported

Median or trimmed-mean paired differences in `M_R^out` across matched cells.
This is the metric with the most resolution when both arms resolve, and the
least meaning when one of them never does, so it is reported beside `A_s`
rather than instead of it.

## 3. The predicate is always stated with the number

`A_s` is computed under `RESOLVE_PREDICATE = M_R^out > 0`, strictly. Ties go
against the claim.

This is not pedantry. The prior phase's headline frontier table was computed
under `M_R^cert > 0` with no certificate requirement, and was read — including
by the follow-on task that commissioned this work — as a statement about what
each probe could certify. Under the stricter predicate every frontier is a grid
step worse and one arm vanishes (`COUNTEREXAMPLE_LOG.md` IV-2). The number
without the predicate is not a result.

## 4. A caveat this phase discovered about its own primary metric

`A_s` inherits whatever `resolved` means, and `resolved` is `M_R^out > 0`,
which rests on `e_ΔR`. `COUNTEREXAMPLE_LOG.md` IV-9 shows that under the paired
design `e_ΔR` reduces to `|λ̂ − 1|·Δ`, a finite-sample noise term that is
almost independent of the plant and, within a seed, independent of the
magnitude too.

So `A_s` on the change metric is a well-behaved, finite, censoring-aware
summary of a quantity that carries less information about the action than one
would assume. `A_s` is therefore computed and reported on **both** the change
metric and the point metric `AE_R`, and any comparison of actions leans on the
second. The metric machinery is correct; what it is fed matters more.

## 5. What is frozen

`D`, `d_max_tested = 0.040`, `COVERAGE_TARGET = 0.90`, the resolve predicate,
and `I_s` as primary. All were fixed in §2 of the preregistration before any
outcome-producing run, and none may be changed now that outcomes exist. If one
of them turns out to be badly chosen, the result is reported under the frozen
choice with the problem stated.
