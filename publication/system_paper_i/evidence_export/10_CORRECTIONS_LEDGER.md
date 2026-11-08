# 10 — Corrections ledger, paper-eligible

Fourteen corrections that change what a sentence may say. Each row points at
the repository record. **The full internal ledgers are in
`docs/audit/`**; this is the compact version a paper can carry.

**Every one of these is a strength, not an embarrassment.** Several were found
by the project's own instruments against the project's own claims, and the
paper should say so.

Full ledgers:
`docs/audit/WP_A2_CORRECTION_PACKAGE.md` ·
`docs/audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md` ·
`docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md` ·
`docs/audit/VERSION_BOUNDARY.md` ·
`docs/audit/WP_A2_CLAIM_PROVENANCE_MATRIX.csv` ·
`docs/audit/WP_C1_CERTIFICATE.md` through `docs/audit/WP_C8_REPORT.md`

---

| # | OLD_CLAIM | FINAL_STATUS | REASON | ARTIFACT | COMMIT |
|---|---|---|---|---|---|
| 1 | reciprocal weighting is used in the fusion | **NOT_LOCATED_IN_SOURCE** | no reciprocal-weighting term exists in `csia/trust_engine/engine.py`; the fusion is a fixed weighted mean over available sub-scores, renormalised. The claim has no source basis | `csia/trust_engine/engine.py` `EngineConfig` | see `15_REPOSITORY_STATE.json` `artifact_last_touched` |
| 2 | unrestricted irreparability of `gps_fault` | **WITHDRAWN** | irreparability would follow from `U_h ⊆ C_h`, and `U_h` is only definable relative to `(M, S, R)`. The containment that does hold is `E_h ⊆ C_h` | `docs/audit/WP_C7_REPORT.md` §284; `research/wp_c6/results/` | WP-C6/C7 |
| 3 | super-additive interaction between channel losses | **REFUTED** | the first version of the test reported 1784 super-additive configurations and was wrong; the corrected enumeration reports sub-additivity | `docs/audit/WP_C1_CERTIFICATE.md` §87; `research/wp_c1/results/certificate.json` key `subadditivity` | WP-C1 |
| 4 | a general coarsening argument covering both mechanisms | **RETRACTED / NARROWED** | `κ` is agnostic to *why* a feature is unobservable, but results turning on the cause apply only to endogenous coarsening. The real-log section measures the exogenous mechanism only | `docs/research/PAPER1_EMPIRICAL_SECTION.md` §N.1 | — |
| 5 | GNSS faults self-occlude | **NARROWED** | arm A is a GNSS fault that preserves the fix; its gate never closes and the diagnosis names `gps_fault` in 1.44 s. Final wording: **self-occlusion observed for tested fix-loss faults** | `research/wp_c4/results/self_occlusion.json` `results.A_spoof_only` | WP-C4 |
| 6 | satellite loss drives the gate closure | **CORRECTED** | WP-C7's satellite ladder showed the satellite count contributes nothing; the closure came from byte loss. The arm was renamed `degraded` to `link_loss` | `research/wp_c7/results/campaign_expanded.json`; rename in `research/wp_c8/four_quantity_metrics.py` `ARM_PARAMS` | WP-C7 |
| 7 | the campaign varied two axes (home site and wind) | **CORRECTED** | `SIM_WIND_SPD` applies no force in the ArduCopter 3.3 build. The campaign varied one axis | `docs/audit/WP_C7_REPORT.md`; `research/wp_c7/results/variance_investigation.json` | WP-C7 |
| 8 | a single false-healthy quantity `T_FH` | **REFUTED AND SPLIT** | it measured an *unsupported* healthy verdict, not a *false* one. Without ground truth a healthy verdict with no applicable evidence may be right by accident. Split into `T_NA`, `T_UH`, `T_FH`, `T_SOFH` | `research/wp_c8/results/four_quantity_metrics.json` key `why_the_old_single_quantity_was_wrong` | WP-C8 |
| 9 | the first escalation derivation | **SUPERSEDED** | the mass-invariance argument assumed constant `ρ`. The corrected closed form matches the shipping code with `max_abs_error_vs_equation_1 = 0.0` | `research/wp_c8/results/escalation_algebra.json` | WP-C8 |
| 10 | the crossing occurs at tick 100 | **CORRECTED to 94** | the detector scanned the *sampled* trace, and 94 was not in the sample. Corrected to scan every tick | `escalation_algebra.json` `verification_against_shipping_trustcore.note_on_crossing` | WP-C8 |
| 11 | threshold provenance for the failsafe thresholds | **PERMANENTLY INDETERMINATE** | the only thing that could close it is pre-import design notes or history, which do not exist in this repository | `docs/audit/WP_A2_REPORT.md` §271; `docs/audit/WP_A2_THRESHOLD_PROVENANCE.md` | WP-A2 |
| 12 | "5 of 11 edges are inert" | **REFUTED** | measured: 6 of 11 vary with state, 5 are constant, and exactly one (`temp_bias_drift`) is genuinely inert in both directions | `reports/wp_a2/e1_inert_gates.json` | `cb0ef62` |
| 13 | gate-closure ceiling κ = 0.286 | **SUPERSEDED by κ = 0.143** | 0.286 is the **pre-promotion** value. After the WP-C3 promotion of `attitude_gravity_mag` into `imu0_bias_drift` the ceiling is 0.143. 15 occurrences of the stale value were found and tracked | `docs/audit/VERSION_BOUNDARY.md` §38-39; `docs/audit/WP_C5_REPORT.md` §138-144; `research/wp_c3/results/effective_signature.json` | WP-C3 promotion `081cca3` |
| 14 | real-log alert rate 4.52/h, then 3.02/h | **CORRECTED to 3.859/h, 95% CI [0.467, 13.939]** | 4.52/h over-counted transitions by 1.50x; 3.02/h used the raw denominator including `arm_time`, during which no alert can be raised. 21.8% of recorded duration (520.0 s over 26 logs) lies inside it | `datasets/reports/exposure_v2.json`; `docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md` D-02; `docs/audit/CSIA_REPOSITORY_AUDIT.md` §120 | dataset audit |

---

## The two that most change the paper

**#8, the four-quantity split.** The paper cannot report "false healthy" as a
single number. It must report four, and the glitch arm is the case that forces
it: substantial `T_FH` with `T_SOFH = 0`. See `06`.

**#13, κ 0.286 to 0.143.** `docs/audit/VERSION_BOUNDARY.md` records this as
**flagged, not yet edited** in `docs/research/PAPER1_EMPIRICAL_SECTION.md`.
That is a live editing action, not a resolved one. The argument is unchanged
(the ceiling still sits far below the corpus's 1.000) but the number must be
updated before submission.

---

## Preserved, not deleted

The superseded derivation in #9, the wrong crossing tick in #10, the 1784
super-additive configurations in #3 and the stale κ in #13 all remain in the
repository as history. Nothing in this ledger licenses removing them.
