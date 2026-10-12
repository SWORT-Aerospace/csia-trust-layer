# SUPPORT-STATE SPECIFICATION — v1.1 Phase 2

**Written before implementation** (§6). Every definition below is structural.
There is no tuned threshold anywhere in this document, and §5 forbids adding
one.

The principle Phase 2 exists to enforce:

> **A HIGH POSTERIOR IS NOT THE SAME AS STRONG EVIDENCE.**

---

## 1. WHAT THE FROZEN CORE ACTUALLY COMPUTES

From `csia/diagnosis/bayes.py` (frozen; read, not modified). Per tick, for
each hypothesis *h*:

    ll[h]        = Σ_j  gate_j · ( log(1 − c_j + EPS)   if j ∈ LOW[h]
                                   log(c_j + EPS)       otherwise )

    smoothed[h]  = (1 − α)·smoothed_prev[h] + α·ll[h]        α = SMOOTH_ALPHA

    score[h]     = log_prior[h] + EVIDENCE_MULT · smoothed[h]

    posterior    = softmax(score)

with `EPS = 0.02`, `SMOOTH_ALPHA = 0.06`, `EVIDENCE_MULT = 1.5`,
`PRIOR_NOMINAL = 0.86` and the remaining mass split evenly over the other
eight hypotheses.

**Every constant is imported from the frozen module, never copied**, so the
analysis cannot silently drift from production.

## 2. THE TERM CONTRIBUTION

    contribution_j[h] = gate_j · ( lo_j  if j ∈ LOW[h] else hi_j )

    lo_j = log(1 − c_j + EPS)      hi_j = log(c_j + EPS)

This is the exact per-feature summand of `ll[h]`. Summing over *j* reproduces
`ll[h]` identically — asserted by test, not assumed.

## 3. ACTIVE

> Term *j* is **ACTIVE** at tick *k* iff `gate_j[k] > 0`.

Gate zero is not weak evidence; it is *no* evidence. The frozen core skips it
(`if gate <= 1e-9: continue`), and so does this analysis, using the same
threshold value taken from the same source.

The gate is where the sensor's availability enters. In the runtime,
`csia/runtime/online.py:610-618` multiplies each edge gate by the freshness of
**both** endpoint sensors and each physics gate by its own sensor's freshness.
So a sensor that is absent, stale or withheld by Phase 1's canonical ingestion
drives its features' gates to zero, and they stop being evidence — which is
the correct behaviour and the mechanism this whole phase measures.

## 4. DISCRIMINATING — THE STRUCTURAL DEFINITION

> Term *j* is **DISCRIMINATING for the ordered pair (a, b)** iff
>
>     |contribution_j[a] − contribution_j[b]| > τ_num
>
> where τ_num is a **numerical** tolerance for float comparison, not a
> decision threshold.

Expanding, `δ_j(a,b) = gate_j · (t_j[a] − t_j[b])`, which is non-zero exactly
when **all three** hold:

1. `gate_j > 0` — the term is active;
2. `j ∈ LOW[a]  XOR  j ∈ LOW[b]` — the hypotheses disagree about this feature;
3. `lo_j ≠ hi_j`, i.e. `c_j ≠ 0.5` — the feature's value is not exactly the
   point at which "expected low" and "expected high" score identically.

Condition 2 is pure structure, fixed by the `CAUSES` table. Condition 1 is
runtime availability. Condition 3 is a measure-zero coincidence in floating
point and is checked rather than assumed.

**A term contributing identically to both hypotheses does not count**, exactly
as §4 requires. This is the whole content of the definition: it asks *does
discriminating evidence exist*, never *how much evidence feels like enough*.

**τ_num is declared before use: `1e-12`.** It exists because these are
64-bit floats, not because a quantity of evidence is being judged. Any value
in `[1e-15, 1e-9]` gives identical results on every scenario in the matrix,
and that insensitivity is asserted by test.

## 5. IDENTIFIABILITY

> Leader `h*` is **CURRENTLY IDENTIFIABLE against competitor `h_j`** iff at
> least one currently active term is discriminating for `(h*, h_j)`.
>
> `h*` is **CURRENTLY IDENTIFIABLE** iff it is identifiable against **every**
> other modeled hypothesis.

If some `h_j` exists for which every active term contributes identically to
`h*` and `h_j`, then `h*` and `h_j` are **NON-IDENTIFIABLE under the currently
active evidence** — the posterior may still separate them, but only because of
the prior and of smoothed history, not because of anything the system can
currently observe.

**"Relevant competitor" is defined as every other modeled hypothesis**, with
no filtering by posterior mass. Filtering by posterior would make
identifiability depend on the very score whose support is in question, which
is circular. The per-pair detail is reported so a reader can see exactly which
pairs collapse rather than only the aggregate.

Per §7: **this is an implementation-level structural test over the active
feature set. It is not a general theorem and is not called one.**

## 6. PRIOR SENSITIVITY

Computed by scoring the same evidence twice, changing only the prior:

- `P_CONFIGURED` — `log_prior` as the frozen core builds it;
- `P_NEUTRAL` — uniform prior over the same hypothesis set.

Identical smoothed evidence, identical `EVIDENCE_MULT`, identical active
relations. Only the prior term differs.

> `prior_sensitive` is **true** iff `argmax` differs between the two.

Since `softmax` is monotone and the neutral prior adds the same constant to
every hypothesis, this is equivalent to comparing `argmax(smoothed)` against
`argmax(log_prior + EVIDENCE_MULT·smoothed)` — no probability
re-interpretation is introduced.

**This is diagnostic metadata only. It never modifies the production
posterior**, and a test asserts that running the analysis leaves the
production diagnosis bit-identical.

Note the size of the effect this is detecting: `log(0.86 / 0.0175) ≈ 3.895`,
so with `EVIDENCE_MULT = 1.5` the evidence must move the smoothed
log-likelihood difference by ≈ 2.60 before it overturns the nominal prior.
That is a substantial prior, and whether it is deciding the winner is exactly
what a reader needs to know.

## 7. AMBIGUITY

> **UNIQUE** — the leader is identifiable against every modeled competitor.
> **AMBIGUOUS** — at least one competitor is non-identifiable from the leader
> under currently active evidence.

Per §10, ambiguity is **not** defined from posterior margin. The margin is
reported separately, as `score_margin`, and never enters the definition.

## 8. THE OUTPUT SHAPE — STRUCTURED, NOT AN OVERLOADED ENUM

§6 offers five candidate labels and says not to keep all five unless each has
a non-overlapping operational meaning, and that a structured output may be
cleaner. **It is**, and here is the reason rather than a preference:
`PRIOR_SENSITIVE` and `NON_IDENTIFIABLE` are not mutually exclusive — a leader
can be both, and forcing one label would discard information a reader needs.

The canonical output is therefore three independent booleans plus detail:

```
support:
  evidence_available:      bool     # any active term at all
  leader_identifiable:     bool     # discriminating evidence vs EVERY competitor
  prior_sensitive:         bool     # leader changes under a uniform prior
  non_identifiable_against: [h, ...] # exactly which competitors collapse
  active_terms:            int
  discriminating_terms:    {h_j: int}
```

A single convenience label is derived from those booleans by a total function
with **no** additional information and **no** threshold:

| `evidence_available` | `leader_identifiable` | `prior_sensitive` | `support_state` |
|---|---|---|---|
| false | — | — | `NO_APPLICABLE_EVIDENCE` |
| true | false | — | `NON_IDENTIFIABLE` |
| true | true | true | `PRIOR_SENSITIVE` |
| true | true | false | `EVIDENCE_BACKED` |

`PARTIALLY_IDENTIFIABLE` from §6's candidate list is **not implemented**: it
would need a cut-off on *how many* competitors may collapse, which is the
tuned threshold §5 forbids. The `non_identifiable_against` list carries the
same information exactly and without a cut-off.

## 9. UNKNOWN / UNMODELED

**Not specified here.** §11 forbids implementing it to complete a feature
list. The audit is in `UNKNOWN_MODEL_ADEQUACY_AUDIT.md` and its conclusion is
recorded there, not pre-empted here.

## 10. WHAT THIS SPEC DOES NOT DO

- It does not change the production posterior, the frozen core, or any
  threshold.
- It does not claim the structural test is complete: two hypotheses with
  identical `LOW` sets would be non-identifiable under *every* evidence
  configuration, which is a design-time property, not a runtime one. The
  analysis reports it the same way, and the distinction is noted in the
  results rather than hidden.
- It does not interpret `contribution_j` as a probability. It is a summand of
  a log-likelihood in a naive-Bayes score, and the frozen core's own docstring
  is careful about that; so is this.
