# PROVISIONAL GRAPH MODEL

Items 5, 18, 19. The terminology correction, the graph definition, and the
extraction discipline that keeps the graph from being drawn to order.

---

## 1. TERMINOLOGY CORRECTION (item 5)

The frontier report used **"effective independence"**. That name asserts a
relationship to failure independence and statistical independence that has not
been established, and — per `MENGER_CLAIM_COUNTEREXAMPLES.md` — is false in
both directions.

From this stage onward, in every artifact:

| retired | adopted |
|---|---|
| effective independence | **structural evidence diversity**, or **provenance cut cardinality** |
| κ | **κ_prov** |
| "zero power" | **zero fault sensitivity** / **structurally indistinguishable** |

**Neither adopted name is claimed to be standard.** Both are provisional labels
for a quantity defined in this package and nowhere else so far as this stage
could check.

---

## 2. DEFINITION

> **κ_prov(t, v)** = the minimum source-separating vertex cut, in the
> provenance DAG G_t, between the sensing frontier F and the evidence set
> E_v(t) supporting verdict *v*.

Equivalently, by Menger's theorem, the maximum number of internally
vertex-disjoint paths from F to E_v(t).

**The cut set is drawn from V \ E_v(t) and MAY include frontier vertices.**
This differs from the frontier report, which restricted cuts to
V \ (E_v ∪ F); under that restriction a graph whose frontier nodes feed the
evidence set directly admits no finite cut at all, and the quantity is
undefined in exactly the case of interest. The correction is recorded rather
than applied silently.

**κ_prov is a graph quantity and nothing else.** It is not statistical
independence, not mutual information, not effective sample size, not
reliability, and not test power. See `INDEPENDENCE_TAXONOMY.md`.

---

## 3. NODE RULES (item 18 — fixed before any audit)

| admitted as a node | |
|---|---|
| physical transducer instance | yes (accel 0, accel 1, compass 0, GPS 0) |
| software transform with its own state | yes (estimator lane, filter) |
| selection index that chooses among instances | yes, as an index node |
| wire message field as emitted | yes |
| consumer channel | yes |
| shared clock | **excluded in this stage** |
| shared calibration procedure | **excluded in this stage** |
| shared power rail | **excluded in this stage** |
| physical environment / airframe | **excluded in this stage** |

The four exclusions are real dependencies. Excluding them is a limitation, not
a claim that they do not matter; `MENGER_CLAIM_COUNTEREXAMPLES.md` §3 shows
that the last of them alone is sufficient to defeat the metric.

## 4. EDGE RULES

An edge `u → w` is admitted only where a cited `file:line` shows the value at
*w* computed from the value at *u*, with any intervening selection resolved.

**Edge categories (item 19 — no numeric probabilities anywhere):**

`PROVED_FROM_SOURCE` · `PROVED_FROM_CONFIGURATION` · `OBSERVED_RUNTIME` ·
`INFERRED` · `UNKNOWN`

**Only `PROVED_FROM_SOURCE` may carry a structural result.** The audit in
`RUNTIME_TOPOLOGY_SOURCE_AUDIT.md` uses no other category.

## 5. BOUND DIRECTION

Worked out in `FORMAL_REDUCTION.md` §4, and it corrects the frontier report:

- omitted edges → κ_prov **under**-estimates (creates false deficits);
- aliased nodes → κ_prov **over**-estimates (hides real deficits);
- **neither bound holds in general.**

Any use of κ_prov must state which assumption it relies on, per verdict.

## 6. WHAT THIS MODEL CANNOT DO

Stated here so no later stage can assume otherwise:

1. It cannot certify residual invariance (counterexample A).
2. It cannot see coupling outside the software graph (counterexample B).
3. It has no fault set, so it cannot express diagnostic diversity, which is
   only defined relative to the hypotheses being discriminated.
4. It is not bounded in a known direction (§5).

Points 1–4 are why the scientific verdict of this stage is
`PROVENANCE_METRIC_INSUFFICIENT`.
