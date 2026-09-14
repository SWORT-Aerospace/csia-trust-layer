# Preregistration Amendment 4 — break the paired-design cancellation

**Written and committed before any follow-up seed is drawn.** This amendment
changes what the preregistered primary metric *measures*, which is exactly why
it is an amendment written in advance rather than a reinterpretation written
afterwards.

It does not touch the completed sealed campaign, its artifacts, its numbers or
its verdicts. Those stay as they are.

## 1. The defect being fixed

`COUNTEREXAMPLE_LOG.md` IV-9, confirmed at campaign scale in
`PREREGISTRATION_AMENDMENT_2.md` and again on the sealed partition: the
preregistered change metric is **saturated**. `A_s` on the change metric is
0.933 for every arm except passive. Thirteen arms are indistinguishable.

The cause is a property of the experimental design, not of the methods:

* the fault does not move the current — this loop is driven by command and lag,
  not by terminal voltage;
* the nominal and fault windows of a matched pair share a seed, so they share
  every noise draw;
* therefore `V_fault(t) − V_nominal(t) = −ΔR₀·I_true(t)` **exactly**, verified
  to 1e-12;
* least squares is linear in the response and the regressor is shared, so
  `R̂_fault − R̂_nominal = ΔR₀·λ̂` where `λ̂` is the finite-sample
  errors-in-variables factor, measured at 1.0009463544;
* so `|e_ΔR| ≈ 10⁻³·Δ` while `τ_R = 0.5·Δ`, and the margin is positive by a
  factor of roughly 500 wherever any excitation occurred.

Every plant-common nuisance — OCV curvature, both polarization branches,
hysteresis, self-heating, open-circuit drift and the voltage-noise draw itself
— cancels in the difference.

**No deployment has this property.** No vehicle gets to re-fly the identical
probe, under the identical noise realisation, with and without a fault. The
nominal baseline in any real system comes from a *different window*.

## 2. The change

A new factor, `nominal_source`, with three levels. The existing behaviour is
kept as a level so that the comparison is visible rather than asserted.

| level | nominal window | what it breaks |
|---|---|---|
| `paired_crn` | same action, same seed — **the current design** | nothing; the control |
| `independent_seed` | same action, a hash-derived companion seed | the shared noise draw, and with it the exact cancellation identity |
| `independent_window` | a **fixed reference probe** at a companion seed | the shared noise draw *and* the shared excitation, so plant-common systematic bias no longer cancels either |

`independent_window` is the deployment-faithful one: a baseline measured earlier
with whatever excitation was available then, not a counterfactual re-flight.

The reference probe is `cosine3_10A_8s`, which is P1's fixed waveform. It is
chosen because it is already in the frozen action space, is already the naive
arm's choice, and predates this amendment — not because of anything it scores.

Companion seeds are derived by the same domain-separated SHA-256 construction
as the partitions, in their own namespace, and asserted disjoint from every
partition seed. No seed is hand-picked.

## 3. Hypotheses, preregistered now

`H8 — the saturation is a design artifact.` Under `independent_seed` and
`independent_window`, `A_s` on the change metric is no longer constant across
arms: at least one deployable arm differs from another by more than 0.05.

`H9 — the change metric recovers plant structure.` Under `independent_window`,
median `|e_ΔR|` differs across Q0, Q1 and Q2 by at least a factor of two, where
under `paired_crn` all three are equal to within 5%.

`H10 — ordering is preserved.` The ranking of deployable arms by `A_s` under
`independent_window` on the **change** metric agrees with the ranking under
`paired_crn` on the **point** metric at Spearman ρ ≥ 0.7. If the two disagree,
the point-metric conclusions in `RESULTS.md` are conditional on the metric and
must be reported as such.

**Predeclared falsifiers.** H8 fails if the change metric stays saturated, in
which case the saturation is not a design artifact and the report says so. H9
fails if breaking the cancellation does not recover plant structure. H10 fails
if the orderings disagree, which would weaken this phase's existing headline
rather than strengthen it — and that outcome is accepted in advance.

## 4. Scope, and what is deliberately not run

**Main block only.** Three plants × two drift states × six magnitudes × three
`nominal_source` levels, over a new hash-derived partition.

**Deployable arms and selectors only** — P0–P6 and S0–S3, eleven arms. The
three ceilings are **omitted**, and the reason is honest rather than
convenient: P7b is an exhaustive argmin whose own objective is computed through
the arena's nominal window, so including it would require threading
`nominal_source` through the ceiling machinery as well, tripling an already
expensive search. The question this amendment asks — *is the change metric
saturated by construction* — does not need a ceiling to answer. Regret against
a ceiling is therefore **not** reported for the follow-up, and no follow-up
number may be compared to a sealed-campaign regret figure.

**New partitions**, `csia_independent_validation/followup_partitions.py`, with
their own domain string. Nothing reuses a seed from the completed phase, so no
question of contamination arises in either direction.

**The completed sealed partition is not reopened.** It was opened once, for a
design that is now superseded on one factor, and that result stands as what it
is.

## 5. What this amendment does not change

`TAU_R_RELATIVE`, `TAU_R_ABSOLUTE`, `COVERAGE_TARGET`, the resolve predicates,
the magnitude grid, `d_max_tested`, `I_s`, the action space, the plant
families, the certificate, the evaluator, or any conclusion already committed.

H1 through H7 and the two-gate claim are settled on the sealed partition and
are not revisited. If the follow-up shows the change metric behaving
differently once the cancellation is broken, that is a statement about the
metric and about what a future campaign should use — **not** a retroactive
edit to what this one found.
