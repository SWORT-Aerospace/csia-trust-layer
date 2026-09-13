# Claim Ledger — RCEC Independent Validation

Every claim this phase makes, with the evidence that supports it and the exact
scope outside which it is not claimed. A claim with no executable evidence is
listed as `UNSUPPORTED` and stays that way until it has one.

Status vocabulary: `VERIFIED` (recomputed from a committed artifact by
independent code), `WITHDRAWN` (was claimed, now shown not to be supported),
`OPEN` (preregistered, not yet measured), `UNSUPPORTED` (stated nowhere as a
result).

**Nothing in this ledger promotes anything.** Simulator research, post-freeze,
quarantined.

---

## A. Claims about the prior locked result

| # | claim | status | evidence |
|---|---|---|---|
| A1 | The frozen CSIA core is unchanged: 12/12 files match `docs/v1/FROZEN_BASELINE.json`, digest `b0b011c6…915ba5a8`. | VERIFIED | `test_frozen_core_digest_and_its_derivation` |
| A2 | The prior sealed partition manifest is unchanged: `e872d36f…5c6f65c2`. | VERIFIED | `test_prior_partition_manifest_is_untouched` |
| A3 | The locked artifact holds 8640 rows from partition `amended_locked`. | VERIFIED | `test_locked_artifact_is_the_one_that_was_sealed` |
| A4 | Certificate state counts are 4723 / 1440 / 1320 / 620 / 537, summing to 8640. | VERIFIED | `test_certificate_confusion_counts` |
| A5 | Published one-RC frontiers (P0 never, P1 0.020, P2 0.006, P3 0.010, P4 0.010, P5 0.020, P6 never, old P7 0.040) reproduce **under the predicate `M_R > 0`**. | VERIFIED | `test_published_frontier_reproduces_under_margin_positive` |
| A6 | Under the stricter predicate `CERTIFIED_IN_MODEL and M_R > 0` every frontier is one grid step worse and the old P7 never resolves. | VERIFIED | `test_frontier_is_strictly_worse_when_certification_is_required` |
| A7 | P2 beats P6 on 140/140 and P1 on 240/240 **on the one-RC slice**; campaign-wide 420/420 and 726/726. | VERIFIED | `test_published_paired_wins_are_the_one_rc_slice`, `test_campaign_wide_denominators_are_larger_and_still_unanimous` |
| A8 | P2 costs 45.85341 A·s against P1's 40.74283 A·s; P3 costs 20.37016 A·s. | VERIFIED | `test_energy_cost_of_the_winning_arm` |
| A9 | Clipping yields `CLIPPED_CERTIFICATE_INVALID` and abort yields `ABORTED_INCOMPLETE`. | VERIFIED | `test_execution_and_unknown_fault_ablations` |
| A10 | 0.40 V ringing routes to `UNKNOWN_OR_MODEL_MISMATCH`; 0.10 V is absorbed as `CERTIFIED_IN_MODEL`. | VERIFIED | `test_execution_and_unknown_fault_ablations` |
| A11 | Only lag ratio 1.0 certifies in the locked sweep; a fourfold lag underestimate flips the realized lever sign. | VERIFIED | `test_only_the_exact_lag_certifies_and_underestimate_flips_the_sign` |
| A12 | Elevated drift collapses P2 and P3 to never while P4 holds 0.010 ohm. | VERIFIED | `test_elevated_drift_collapses_p2_and_p3_but_not_p4` |
| A13 | The certificate margin is bit-identical across all three plants in all 2012 comparable cells. | VERIFIED | `test_certificate_margin_is_bit_identical_across_plants` |
| A14 | "Zero false certificates in 8640 runs" demonstrates certificate soundness. | **WITHDRAWN** | IV-1. The check is `CERTIFIED and M_R < 0`; `certify` issues `CERTIFIED` only when `M_R > 0`. Empty by construction. |
| A15 | The locked campaign's false-certificate check scored estimates against plant truth. | **WITHDRAWN** | IV-1. No row in the artifact carries a true resistance. |
| A16 | The polarization bound is exhaustive over 105 enumerated grid points and sampled at 1800 further draws, with a rule-of-three bound `p < 3/1800 ≈ 0.00167` under an IID reading. | VERIFIED | `POLARIZATION_BOUND_SCOPE.md`, unchanged |

## B. Claims this phase intends to test

| # | hypothesis | status |
|---|---|---|
| B1 | H1 independent outcome advantage | OPEN |
| B2 | H2 nominal/robust tradeoff | OPEN |
| B3 | H3 robust selection | OPEN |
| B4 | H4 certificate calibration | OPEN |
| B5 | H5 plant discrimination by the independent evaluator | OPEN |
| B6 | H6 open-set detectability boundary | OPEN |
| B7 | H7 commanded information is insufficient | OPEN |

## B1a. The seven hypotheses, on validation

24 hash-derived validation seeds, 41 472 rows, 117 627 plant runs. These are
**validation** dispositions. The sealed final partition is a confirmatory run
of the same frozen design, and where it disagrees that disagreement is recorded
beside these rather than replacing them.

| # | hypothesis | disposition on validation | evidence |
|---|---|---|---|
| H1 | independent outcome advantage | **SUPPORTED** | P2 beats P6 864/864 matched cells on `AE_R`, P0 863/864, P5 809/864, P1 827/864 |
| H2 | nominal/robust tradeoff | **REJECTED** | P4 is worse than P2 in *both* drift conditions (0.873/0.884 against 1.000/1.000). P2 does not collapse under elevated drift here |
| H3 | robust selection | **REJECTED** | S2 worst-case `A_s` 0.884 against always-P2's 1.000, and the worst `I_s` of any arm at −0.1019. S3 ties S0 by never choosing P4 |
| H4 | certificate calibration | **SUPPORTED** | `CERTIFIED_IN_MODEL` n = 2404, resolved 1.0000 on both metrics, zero false certificates |
| H5 | plant discrimination | **SUPPORTED on the point metric** | median `AE_R` 3.10e-4 / 1.55e-3 / 1.29e-3 Ω for Q0/Q1/Q2, against three identical figures on the change metric |
| H6 | open-set boundary | **SUPPORTED, narrow** | boundary 3.363 σ, routing 0.901 above over 426 trials and 0.000 below over 870. One ringing family |
| H7 | commanded information insufficient | **SUPPORTED by counterexample** | realized lever −0.0276 s from a command lever of zero, 2.8× the declared γ |

| # | preregistered claim | disposition | evidence |
|---|---|---|---|
| C-2gate | requiring both gates reduces false accepted inferences relative to **either** alone | **REJECTED** | `pre=False/post=True` is empty; accept-if-both is identical to accept-if-post, 2404 accepted and 0 wrong. Beats the pre gate alone, not the post gate alone |

## B2. Claims settled on the development partition

These are measured, not preregistered predictions, and they are development
results: the instrument is connected and these are what it read. None is a
final result and none opens the seal.

| # | claim | status | evidence |
|---|---|---|---|
| D1 | The Q plants are numerically independent of the prior simulator: exact ZOH against forward Euler, 4.05% apart on the per-step coefficient at the 0.25 s command lag. | VERIFIED | `PLANT_INDEPENDENCE_AUDIT.md` §1, `test_zoh_step_is_the_exact_solution` |
| D2 | Every declared effect is wired into the observed voltage: removing R1 moves the resistance estimate by 24% of the smallest grid magnitude, R2 by 5.4%, hysteresis by 3.1%, OCV curvature by 2.5%. | VERIFIED | `PLANT_INDEPENDENCE_AUDIT.md` §2 |
| D3 | `M_R^cert` is bit-identical across Q0, Q1 and Q2 in 48 of 48 matched development cells, reproducing IV-4 on independent code. | VERIFIED | `results/PLANT_INDEPENDENCE.json` |
| D4 | The preregistered change error `e_ΔR` is near-identical across plants (4e-6 Ω on all three) because the paired design cancels every plant-common nuisance exactly; what survives is the finite-sample EIV factor λ̂ = 1.0009463544, matching the observed ratio to seven digits. | VERIFIED, DERIVED | IV-9, `test_the_paired_change_error_is_exactly_the_finite_sample_eiv_factor` |
| D5 | The point error `AE_R` does separate the plants: 1.94e-4, 6.57e-4 and 5.06e-4 Ω for Q0, Q1, Q2. | VERIFIED | `results/PLANT_INDEPENDENCE.json` |
| D6 | The P7b ceiling invariant holds: 216 checks against all 72 admissible actions each, 15 552 comparisons, zero violations, on both losses. | VERIFIED | `ORACLE_TAXONOMY.md` §3 |
| D7 | P7a never agrees with the outcome oracle (0.0% of 108 cells), loses by a median factor of 11.0, and spends 2.4× the energy. | VERIFIED | `ORACLE_TAXONOMY.md` §4 |
| D8 | P7a's objective is exactly the classical A-optimal design for resistance: `var(R) = σ_V²/S_II`, and `argmin var(R)`, `argmax S_II` and P7a's selection are the same action. | VERIFIED, DERIVED | `BASELINE_MAPPING.md` §3, `test_the_cramer_rao_variance_of_r_is_sigma_squared_over_s_ii` |
| D9 | Set-membership model invalidation separates the plants at 2.46, 4.90 and 7.31 σ for Q0, Q1, Q2. | VERIFIED | `BASELINE_MAPPING.md` §4 |
| D10 | The unknown-fault detectability boundary is 3.363 σ: routing rate 0.901 above it over 426 trials, 0.000 below it over 870. | VERIFIED | `UNKNOWN_BOUNDARY.md` §4 |
| D11 | The 0.10 V ringing case lies at 1.461 σ, about one σ above the 0.445 σ no-fault floor, so its absorption is structural rather than a classifier defect. | VERIFIED | `UNKNOWN_BOUNDARY.md` §5 |
| D12 | Four sensing parameters have exactly zero effect on the outcome, each for a derived reason: voltage offset absorbed by the intercept, current offset absorbed by the free intercept, voltage noise cancelled by the paired design, timestamps never read by the estimator. | VERIFIED, DERIVED | `SENSITIVITY_AUDIT.md` §3 |
| D13 | Current gain error is the dominant sensitivity, and `e_ΔR ≈ −s·Δ/(1+s)` matches measurement to 2e-6 Ω. | VERIFIED | `test_a_one_percent_gain_error_moves_the_change_estimate_by_about_one_percent` |
| D14 | Proposition A: a palindromic command with zero drift lever and 20050 A² of second moment yields a realized lever of −0.0276 s through an ordinary causal bounded lag, violating a declared γ of 0.01 s. | PROVEN BY COUNTEREXAMPLE | `FORMAL_PROPOSITIONS.md` A |
| D15 | Proposition B: disjoint error sets imply correct change sign, **conditional** on the declared error set containing the true error. | CONDITIONALLY PROVEN | `FORMAL_PROPOSITIONS.md` B |
| D16 | Proposition C: truncation always costs excitation and moves the drift lever non-monotonically and with a sign change, so a full-window certificate bounds a prefix in neither direction. | PROVEN FOR TRUNCATION | `FORMAL_PROPOSITIONS.md` C |
| D17 | A conventional post-execution fit reports a truth-covering interval on a full window and a non-covering one, in identical language, on the same run truncated to 25%. | VERIFIED, single instance | `BASELINE_MAPPING.md` §5 |

## B2a. Findings from building the instrument, validation phase

| # | finding | status | evidence |
|---|---|---|---|
| E1 | The pre-action gate's safety half cannot fail for any admissible action: 34 A worst case against a 56 A limit. | VERIFIED, and it is a defect in the experiment's discriminating power | IV-19, `test_no_admissible_action_can_fail_the_safety_sub_gate` |
| E2 | Zero intersection volume does not imply empty intersection, and the touching case occurs in 48 of 12 960 validation cells (0.37%). | VERIFIED | IV-20, IV-22 |
| E3 | The certificate is sound and conservative: it declined 8655 cells of which 86.4% would have resolved, and 76 unknowns of which 100% would have. | VERIFIED | `RESULTS.md` §3 |
| E4 | The post-action gate's accepted set is strictly contained in the pre-action gate's. | VERIFIED | IV-21 |
| E5 | No selector abstained in 12 960 cells. All three abstention paths are reachable and tested; none was reached. | VERIFIED | `RESULTS.md` §6 |
| E6 | The worst independently scored error among certified cells is P7a on Q1 at Δ = 0.040, `AE_R` 4.506e-3 Ω — still inside τ_R = 0.020. | VERIFIED | `results/WORST_COUNTEREXAMPLE.json` |

## B3. Constructs withdrawn or corrected in this phase

| # | construct | disposition |
|---|---|---|
| W1 | "Zero false certificates in 8640 runs" as evidence of soundness | **WITHDRAWN** — empty by construction (IV-1) |
| W2 | "The locked false-certificate check scored against plant truth" | **WITHDRAWN** — no row carried a true resistance (IV-1) |
| W3 | The label "90% resolution frontier" for a margin-only predicate | **CORRECTED** — both predicates now reported (IV-2) |
| W4 | Paired-win denominators 140 and 240 as campaign-wide | **CORRECTED** — they are the one-RC slice (IV-3) |
| W5 | "Median margin identical to twelve decimal places" | **STRENGTHENED** — bit-identical (IV-4) |
| W6 | `P7_oracle` as an oracle | **WITHDRAWN** — renamed P7a benchmark (IV-15) |
| W7 | My own belief that a prefix of a palindrome carries more drift leverage | **FALSIFIED** by its own test (IV-10) |
| W8 | P7c as "robust" under the change loss | **QUALIFIED** — six different actions in six seeds (IV-11) |
| W9 | My belief that the pre-action gate would add safety screening | **FALSIFIED** — its safety half cannot fail over this action space (IV-19) |
| W10 | The preregistered two-gate combined claim | **REJECTED** — the pre gate is redundant given the post gate in this envelope (IV-21) |
| W11 | H2 and H3, both preregistered by me | **REJECTED on validation** — P4 is worse than P2 in both drift conditions, and the threshold selector built on the prior phase's finding is strictly worse than committing to P2 |
| W12 | "Closest **verified** source" in the supplied related-work draft | **CORRECTED** — the primary text could not be retrieved; seven endpoints refused (`RELATED_WORK.md` §0) |

## C. Claims explicitly not made

| # | claim | status |
|---|---|---|
| C1 | Any of this is a certified safety artifact. | UNSUPPORTED, prohibited |
| C2 | Any of this is airworthy, production-ready, or flight-qualified. | UNSUPPORTED, prohibited |
| C3 | Any of this is novel relative to the active-diagnosis literature. | `BLOCKED_EXTERNAL_ACCESS` — see `EXTERNAL_SOURCE_REQUEST.md` in the prior phase |
| C4 | The simulated pack represents any real battery chemistry or hardware. | UNSUPPORTED, explicitly disclaimed |
| C5 | Results transfer outside the declared model validity envelope. | UNSUPPORTED |
