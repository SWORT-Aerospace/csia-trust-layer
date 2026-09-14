# The paired design, broken on purpose

**GENERATED** by `tools/research/iv_followup_report.py` from
`results/FOLLOWUP_DEVELOPMENT.json`. Edit the
script, not this file.

Preregistered in PREREGISTRATION.md + PREREGISTRATION_AMENDMENT_4.md. Amendment 4 was
written and committed before the first follow-up seed was drawn;
Amendment 5 records that one of its three hypotheses turned out
unfalsifiable and adds the version that is not. This campaign does
not touch the sealed phase-one result, which stands as it is.

## What ran

| field | value |
|---|---|
| partition | `development`, 8 seeds |
| partition manifest | `b6af853781b62631dde39c5b0c83a623a3c3c458d7936d10ac2ccb8218702515` |
| phase-one manifest (untouched) | `b293e30f30a767c13b29d1abfa9ac4c3bdc49580f3224d037252513801786731` |
| arms | 11 deployable (`P0_passive`, `P1_palindromic`, `P2_compensated`, `P3_shaped`, `P4_feedback`, `P5_random_safe`, `P6_mission`, `S0_always_P2`, `S1_always_P4`, `S2_threshold`, `S3_minimax`) |
| arms omitted | `P7a_benchmark`, `P7b_oracle`, `P7b_point_oracle`, `P7c_robust` |
| reference probe | `cosine3_10A_8s` |
| rows | 9504 |
| plant runs | 10176 |
| wall clock | 898 s |

Simulator only. Synthetic pack, no chemistry, no hardware representativeness. Not a certified safety artifact. Nothing here promotes anything, and nothing here edits the sealed campaign.

**Regret.** not computed. Amendment 4 section 4: the ceilings are omitted from this campaign, so no regret figure exists here and none may be borrowed from the sealed one.

## The factor moves one thing

`AE_R` scores the fault window alone and never reads the baseline, so
the three levels must agree on it exactly. If they did not, the factor
would be contaminating something it was not supposed to touch and
every verdict below would be void.

* matched groups compared: **3168**
* worst `AE_R` spread across levels: **0.0000e+00**
* identical everywhere: **yes**

## Resolution with nothing injected

`P0_passive` emits no probe, so its resistance estimate is a fit to
noise. Under `paired_crn` both windows are the same draw, the
difference is exactly zero, and `|e_ΔR| = Δ` never clears
`τ_R = 0.5Δ`. Under `independent_seed` the draws differ, the
difference is a random quantity, and it lands inside the tolerance
often enough to score.

| nominal source | zero-energy rows | scored resolved | rate | of those, certified |
|---|---|---|---|---|
| `paired_crn` | 288 | 0 | 0.0000 | 0 |
| `independent_seed` | 288 | 22 | 0.0764 | 0 |
| `independent_window` | 288 | 0 | 0.0000 | 0 |

The outcome metric can score a resolution where no probe was injected at all; the certificate refuses every one of them, which is why none of these rows is a false certificate.

## The cancellation, level by level

| nominal source | rows | median &#124;e_ΔR&#124; | resolved (change) | false certs (change) | false certs (point) |
|---|---|---|---|---|---|
| `paired_crn` | 3168 | 3.5386e-06 | 0.9091 | 0 | 0 |
| `independent_seed` | 3168 | 2.3140e-04 | 0.8867 | 0 | 0 |
| `independent_window` | 3168 | 5.1242e-04 | 0.7645 | 0 | 0 |

The deployment-faithful level is **144.8×** the
paired control on median |e_ΔR|. The paired figure is not a
measurement of the estimator; it is the residual of an identity
that holds because the two windows share a noise draw.

## H8 — the saturation is a design artifact

> under independent_seed and independent_window, A_s on the change metric is no longer constant across arms: at least one deployable arm differs from another by more than 0.05

**Verdict: SUPPORTED.**

Predeclared falsifier: the change metric stays saturated, in which case the saturation is not a design artifact.

| nominal source | A_s spread across all arms | exceeds 0.05 |
|---|---|---|
| `paired_crn` — **the control** | 1.0000 | yes |
| `independent_seed` | 0.9236 | yes |
| `independent_window` | 1.0000 | yes |

**Vacuity: VACUOUS_IN_ENVELOPE.** P0_passive injects no energy, so it resolves nowhere and scores A_s = 0 at every level including the control. The spread between it and any excited arm is ~1.0 by construction, so this statistic cannot come out any other way and its verdict above carries no information.

The control passes the test, so the verdict above carries
no information. It is printed rather than deleted: a
preregistered statistic that came out useless is evidence
about the preregistration, and removing it is how a phase
stops being falsifiable.

### H8′ — PREREGISTRATION_AMENDMENT_5.md

> restricted to arms with non-zero mean injected energy, A_s on the change metric is constant across arms under paired_crn (spread <= 0.05) and is not constant under independent_seed and independent_window (spread > 0.05)

**Verdict: SUPPORTED.**

Excluded: `P0_passive`, because mean energy_as == 0 over this campaign's rows. The remaining
10 arms all inject a probe.

| nominal source | A_s spread, excited arms | flat (≤ 0.05) |
|---|---|---|
| `paired_crn` — **the control** | 0.0000 | yes |
| `independent_seed` | 0.2604 | no |
| `independent_window` | 0.9340 | no |

Control is flat: **yes**. Unlike
H8, this is part of the claim: H8′ fails if the control is not
flat.

Predeclared falsifier: the paired_crn control is not flat over the excited arms, in which case phase one's diagnosis of its own saturation was incomplete; or either broken level stays flat, in which case breaking the pairing did not break the saturation.

Per-arm `A_s` on the change metric, all arms:

| arm | excited | `paired_crn` | `independent_seed` | `independent_window` |
|---|---|---|---|---|
| `P0_passive` | **no** | 0.0000 | 0.0764 | 0.0000 |
| `P1_palindromic` | yes | 1.0000 | 1.0000 | 1.0000 |
| `P2_compensated` | yes | 1.0000 | 1.0000 | 1.0000 |
| `P3_shaped` | yes | 1.0000 | 0.9792 | 0.7986 |
| `P4_feedback` | yes | 1.0000 | 1.0000 | 0.9306 |
| `P5_random_safe` | yes | 1.0000 | 0.9583 | 0.7153 |
| `P6_mission` | yes | 1.0000 | 0.7396 | 0.0660 |
| `S0_always_P2` | yes | 1.0000 | 1.0000 | 1.0000 |
| `S1_always_P4` | yes | 1.0000 | 1.0000 | 0.9306 |
| `S2_threshold` | yes | 1.0000 | 1.0000 | 0.9688 |
| `S3_minimax` | yes | 1.0000 | 1.0000 | 1.0000 |

## H9 — the change metric recovers plant structure

> under independent_window, median |e_dR| differs across Q0, Q1 and Q2 by at least a factor of two, where under paired_crn all three are equal to within 5%

**Verdict: SUPPORTED.**

Predeclared falsifier: breaking the cancellation does not recover plant structure.

| nominal source | Q0 | Q1 | Q2 | max/min |
|---|---|---|---|---|
| `paired_crn` | 3.5386e-06 | 3.5386e-06 | 3.5386e-06 | 1.00 |
| `independent_seed` | 2.3165e-04 | 2.3089e-04 | 2.3124e-04 | 1.00 |
| `independent_window` | 3.0455e-04 | 1.0050e-03 | 9.0919e-04 | 3.30 |

Control precondition (paired plants agree to within 5%): **yes**.

## H10 — ordering is preserved

> the ranking of deployable arms by A_s under independent_window on the change metric agrees with the ranking under paired_crn on the point metric at Spearman rho >= 0.7

**Verdict: SUPPORTED.**

Predeclared falsifier: the orderings disagree.

Spearman ρ = **0.9859** against a floor of 0.7.

| arm | A_s change, `independent_window` | A_s point, `paired_crn` |
|---|---|---|
| `P0_passive` | 0.0000 | 0.0000 |
| `P1_palindromic` | 1.0000 | 0.9965 |
| `P2_compensated` | 1.0000 | 1.0000 |
| `P3_shaped` | 0.7986 | 0.7569 |
| `P4_feedback` | 0.9306 | 0.8819 |
| `P5_random_safe` | 0.7153 | 0.6806 |
| `P6_mission` | 0.0660 | 0.0660 |
| `S0_always_P2` | 1.0000 | 1.0000 |
| `S1_always_P4` | 0.9306 | 0.8819 |
| `S2_threshold` | 0.9688 | 0.9444 |
| `S3_minimax` | 1.0000 | 1.0000 |

If rejected: the point-metric conclusions in RESULTS.md are conditional on the metric and must be reported as such.

## What this does not establish

* Nothing here is a novelty claim. The construction being measured is
  an experimental-design property, and finding it is not a
  contribution to anybody's literature.
* Nothing here revises a phase-one conclusion. H1–H7 and the two-gate
  claim were settled on the sealed partition and are not reopened.
* No regret, no ceiling, no comparison to a sealed-campaign regret
  figure. The ceilings did not run.
* Simulator only. Synthetic pack, no chemistry, no hardware
  representativeness, no certified safety artifact, no promotion.

