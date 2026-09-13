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

## C. Claims explicitly not made

| # | claim | status |
|---|---|---|
| C1 | Any of this is a certified safety artifact. | UNSUPPORTED, prohibited |
| C2 | Any of this is airworthy, production-ready, or flight-qualified. | UNSUPPORTED, prohibited |
| C3 | Any of this is novel relative to the active-diagnosis literature. | `BLOCKED_EXTERNAL_ACCESS` — see `EXTERNAL_SOURCE_REQUEST.md` in the prior phase |
| C4 | The simulated pack represents any real battery chemistry or hardware. | UNSUPPORTED, explicitly disclaimed |
| C5 | Results transfer outside the declared model validity envelope. | UNSUPPORTED |
