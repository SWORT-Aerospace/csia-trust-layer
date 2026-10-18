# Preregistration Amendment 2 — the primary metric is saturated

**Written on calibration evidence only. No validation or final outcome has been
read at the time of writing, and the amendment is committed before any is.**

Amends `PREREGISTRATION.md` and `PREREGISTRATION_AMENDMENT_1.md`. It changes no
hypothesis, no frozen constant, no metric definition, and none of the ten
conditions for opening the seal. It adds one non-deployable arm and it records
a defect in the preregistered primary metric.

## 1. What calibration showed

The calibration partition — 12 seeds, 20 304 rows, 76 896 plant runs — was run
as the rehearsal `PREREGISTRATION_AMENDMENT_1.md` §2 describes. It is a
constants-fixing partition and this is what it fixed.

**The preregistered primary metric is saturated.** Grid resolution area on the
change metric, nominal drift:

| arm | `A_s` (change) |
|---|---|
| P0 passive | 0.000 |
| **every other arm, all thirteen** | **1.000** |

P1, P2, P3, P4, P5, P6, P7a, P7b, P7c, S0, S1, S2 and S3 are indistinguishable.
The metric separates "did you excite at all" from "did you not", and nothing
else.

This is a direct consequence of `COUNTEREXAMPLE_LOG.md` IV-9, now visible at
campaign scale. Under the paired design `e_ΔR = |λ̂ − 1|·Δ` with `λ̂ ≈ 1.001`,
so `|e_ΔR| ≈ 1e-3·Δ`, while `τ_R = 0.5·Δ`. The margin is positive by a factor
of roughly 500 in every cell where any excitation happened at all. It could not
have come out otherwise.

The point metric does discriminate, on the same rows:

| arm | `A_s` (point) | frontier | mean energy |
|---|---|---|---|
| P0 passive | 0.009 | `> 0.04` | 0 A·s |
| P6 mission | 0.051 | `> 0.04` | 48.0 A·s |
| P5 random-safe | 0.694 | 0.010 | 20.4 A·s |
| P7a benchmark | 0.694 | 0.010 | 80.0 A·s |
| P3 shaped | 0.741 | 0.010 | 14.0 A·s |
| P4 feedback | 0.861 | 0.006 | 56.0 A·s |
| **P7b oracle (change loss)** | **0.907** | 0.004 | 45.8 A·s |
| P1 palindromic | 1.000 | 0.002 | 50.9 A·s |
| P2 compensated | 1.000 | 0.002 | 71.3 A·s |

## 2. The consequence for the ceiling, stated carefully

On the point metric, five deployable arms score above P7b. **This is not a
violation of the ceiling invariant and it must not be reported as one.** The
invariant is defined on P7b's *own objective*, and on that objective it holds
exactly: across 432 matched calibration cells, **zero** deployable arms beat
P7b on the change loss. Checked directly, not inferred.

What the calibration data shows is different and worse: **P7b, built to the
letter of the specification, optimises a loss that carries almost no
information, and therefore bounds nothing anybody cares about.** A ceiling on a
saturated metric is a valid ceiling and a useless one.

The task is explicit that if a deployable strategy beats P7b on P7b's exact
objective, the oracle implementation is invalid and the phase stops, and that
the deployable method must not be relabelled super-oracular. Neither applies
here. The oracle is correct; the objective it was given is inadequate.

## 3. What this amendment adds

**One arm: `P7b_point_oracle`.** The same exhaustive hindsight argmin over the
same 72-action space, minimising `AE_R` instead of `|e_ΔR|`.

This is not new capability written to fit an observation. `ceilings.p7b_select`
has taken a `loss` parameter since it was first committed, and
`tools/research/iv_oracle_taxonomy.py` has been running the ceiling invariant
on **both** losses since IV-4 — 216 checks, 108 of them on the point loss, zero
violations. What changes is which of the two appears as a campaign arm.

The arm list goes from 14 to 15. Because the arm list changed, **the validation
run is re-run in full**; a validation campaign that does not match the final
design does not satisfy condition 7.

## 4. What this amendment does not change

`TAU_R_RELATIVE`, `TAU_R_ABSOLUTE`, `COVERAGE_TARGET`, the resolve predicates,
the magnitude grid, `d_max_tested`, the primary interaction statistic `I_s`,
the factor structure, any hypothesis, any falsifier, and none of the ten
conditions in `PREREGISTRATION.md` §6.

In particular **`e_ΔR` and `M_R^out` remain the preregistered primary metric.**
They are not demoted, not replaced, and not quietly dropped. Every table
reports them. What this amendment records is that on this design they are
saturated, which is a result about the metric and belongs in the results rather
than in a redefinition.

The honest reading of H1 through H5, stated now rather than after the fact: on
the primary metric they will be answered by a metric that cannot tell thirteen
arms apart, and any discrimination in the answer comes from the point metric
that §4.1 of the preregistration listed alongside it.

## 5. Provenance

Calibration partition, manifest `b293e30f…01786731`, 12 seeds. The calibration
raw artifact is 11.6 MB and is **not** committed: it fixed one design decision,
recorded here, and its design no longer matches the final one. Its headline
numbers are reproduced in §1 above and the run is reproducible from
`tools/research/iv_campaign.py --partition calibration` at the commit that
carries this document.
