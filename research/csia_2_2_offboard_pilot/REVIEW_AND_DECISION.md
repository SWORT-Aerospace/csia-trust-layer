# CSIA 2.2 offboard pilot: review and decision

**2026-10-01. NON-CONFIRMATORY.**

## 1. Decision

**`CSIA_2_2_PILOT_VALUE_DEMONSTRATED_NARROW`**

**On the one real event that several real monitors observe, the Analyzer
gives a more defensible explanation than the monitors read individually.**
The event is motor thrust loss in XSYS-001, PX4 547e2ca SITL, 121 trials.
The Analyzer's explanation is better in three measured ways:
1. **Independent evidence:** it counts the adverse evidence as 2
   independent lines, not 3 monitors. This is right in 121/121 trials.
2. **Dependent refuters:** the exclusion of the telemetry hypothesis rests
   twice on one IMU. The Analyzer shows this in 110/110 fault trials.
3. **Invalid evidence:** it refuses an output used outside its validated
   window. Without that refusal, 2.1.1 alone is wrong in 55/55 trials.

**The value is narrow:**
- one event class and one dependence structure;
- research producers with a known onset;
- SITL;
- no outside engineer has read a report.

**On a stock PX4 log, the Analyzer has nothing to diagnose with.** It
observes 0 of 68 profile records, and now says so.

**The product boundary is the SITL/HIL Validator** (`PRODUCT_BOUNDARY.md`).

**Unchanged:**
- **CSIA 2.2 remains OFFBOARD, OBSERVATIONAL, ZERO CONTROL AUTHORITY.**
- This decision is **not** authorization for onboard authority, FORGE or
  autonomous recovery.

**The tokens are this package's own.** The brief as received ends inside
Phase 29 ("If none: say:"), with no deliverables list or decision tokens.
This package follows the conventions of the previous briefs.

**Alternatives considered:**

| token | why not |
|---|---|
| `CSIA_2_2_PILOT_READY_FOR_EXTERNAL_PRODUCT` | on an operator's own stock log it observes nothing it can diagnose (G1-G4); no outside user has tested it |
| `CSIA_2_2_PILOT_NO_VALUE_OVER_MONITORS` | contradicted by the three measured elements above |
| `CSIA_2_2_PILOT_SEMANTIC_CORE_DEFECT_STOP` | no 2.1.1 defect found (§4) |
| `CSIA_2_2_PILOT_GOVERNANCE_BLOCK` | every governance check passes (§3) |

## 2. The primary question, answered

> When multiple real monitors observe the same real vehicle event, does
> CSIA 2.2 produce a more useful and more defensible engineering
> explanation than the monitors provide individually?

**Yes, narrowly.** `PRODUCT_QUESTION.md` gives the answer and its limits.

| | the monitors individually | the Analyzer |
|---|---|---|
| verdict (V3) | W_RPM alone cannot separate a motor fault from a telemetry fault (adverse in 55/55 of each) | 55/55 A, 55/55 B, 11/11 N correct (the same as 2.1.1) |
| corroboration | 3 monitors agree | 2 independent lines, the shared sources named; equal to ground truth in 121/121 |
| elimination | not visible | rests on one IMU, said in every fault report |
| invalid window (V4) | the out-of-window output looks valid | refused; AMBIGUOUS and correct in 55/55, where 2.1.1 alone is wrong in 55/55 |
| estimator | innovations NOMINAL, uninformative (AUC 0.43-0.55) | context only; shown, never counted |

**Aggregation was not counted as value.** `FALSE_VALUE_SEARCH.md`
classifies every report element:
- 3 NEW ENGINEERING VALUE;
- 12 USEFUL AGGREGATION;
- 5 DUPLICATE INFORMATION;
- 0 MISLEADING now. Three elements were MISLEADING when the pilot began
  (rows 6, 12, 13 there), and all three were fixed.

## 3. Baseline and governance

| check | result | evidence |
|---|---|---|
| 2.2 locked before the pilot: 4fb191e, c197abd; core identity; tests; XSYS 3,872 slots; Phase C; replays; validator; contracts | yes | `PILOT_BASELINE.json` (`PILOT_BASELINE_LOCKED`) |
| re-verified at the end | yes | `PILOT_FINAL_STATE.json` (`PILOT_FINAL_STATE_OK`) |
| Semantic Core 2.1.1 | unchanged (`semantic_core_changed_since_2_1_1`: none) | same |
| frozen v2.0, Phase C, XSYS-001, A1, A2, sealed manifests | unchanged; XSYS hard gate PASS, 0 differences on 3,872 slots; primary 55/55, lower bound 0.7616 | same |
| the previous 2.2 package and its replay results | unchanged (`previous_2_2_package_changed`: none) | same |
| 2.2 replays re-run with the pilot code | equal: v2 corpus (44 scenarios, 0 decision differences), XSYS (110 expected V4 differences, 0 elsewhere), E1, receipts | same |
| failure ledger | SHA pinned and matching; nothing appended | same |
| raw flight logs | not committed; inputs identified by SHA-256 | manifests |

## 4. Semantic-core defects

**None found.** The stop rule was not triggered.
- **Where the findings were:** of the three wrong-answer findings, two
  were in 2.2's adapters (WA-1, WA-2) and one in its report (WA-3).
  FV-1 was in the report.
- **Where they were fixed:** every fix is outside `csia_semantic_core/`.
- **What stays as 2.1.1's output:** FV-3 ("NOTHING_ADVERSE" wording) is
  documented, not changed. Changing it would be a semantic-core change.

## 5. What the pilot changed in 2.2 (analyzer 2.2.1, report schema 3)

| change | why | pinned by |
|---|---|---|
| IMU lineage root `sensor:imu.<device>` (WA-1) | a gyro and an accelerometer monitor of one chip counted as independent | `test_wa1_one_imu_chip_is_one_root` |
| provisional estimator context before the first selection (WA-2) | resets before the selector's first message were missing | `test_wa2_every_real_reset_is_reported_even_before_the_first_selection` |
| profile coverage and the scope of a verdict (WA-3) | "no symptom" printed for motor-degraded flights with no motor observer | `test_wa3_a_verdict_names_the_profile_records_nothing_observed` |
| lineage groups name who shares each source (FV-1) | the group sentence implied every member shared every source | `test_fv1_a_lineage_group_names_who_shares_each_source` |
| `nominal_means`; CUSUM contract cusum-2 (NO_ANOMALY) | a silent detector was shown as NOMINAL | `test_a_silent_detector_is_no_anomaly_and_an_unseen_source_is_no_coverage` |
| key moments; every refuter; shared-refuter warning; would-discriminate; PX4-term configuration changes | the engineer's WHEN and WHY questions | `test_key_moments_answer_when` and others |
| `analyze`, `analyze-many`, manifest, coverage matrix | Phases 12, 13, 22, 23 | `test_analyze_and_analyze_many_commands`, `test_manifest_is_reproducible_and_path_free` |
| determinism pins | Phase 20 | `test_report_bytes_do_not_depend_on_process_or_directory`, `test_pinned_reports_regenerate_byte_for_byte` |

## 6. Phases

| phase | deliverable | status |
|---|---|---|
| 0 lock | `PILOT_BASELINE.json`, `PILOT_FINAL_STATE.json` | done |
| 1 product question | `PRODUCT_QUESTION.md` | done |
| 2-3 event matrix, existing data | `MULTI_PRODUCER_EVENT_MATRIX.md` | done: one real multi-producer event class |
| 4 full-campaign estimator replay | `CAMPAIGN_REPLAY.md` §1, `CAMPAIGN_XSYS.json` | done: 66 flights, 121 trials |
| 5 estimator claim mapping | `ESTIMATOR_CLAIM_MAPPING.md` | done: context only |
| 6-8 real case, independence, corroboration | `INDEPENDENCE_AND_CORROBORATION.md` | done |
| 9 coverage states | `COVERAGE.md` §1 | done |
| 10 real transitions | `CAMPAIGN_REPLAY.md` §2, `SITL_SELECTOR_RUN.md` | done: resets, aiding changes, a real magnetometer loss; no lane switch exists in the data |
| 11 multi-lane gap | `SITL_SELECTOR_RUN_DESIGN.md`, `SITL_SELECTOR_RUN.md`, `LANE_SWITCH_EXPERIMENT_DESIGN.md` | **the lane switch was not run.** Stock SIH has one IMU and one magnetometer, so a lane switch needs a simulator change: **stopped at design**, as the brief requires. Run S1 (`SENS_IMU_MODE=0`, magnetometer failed at 75 s) was run instead, on unmodified PX4 |
| 12-14 analyze, manifest, timeline | `ANALYZER_MVP.md` | done |
| 15 usefulness questions | `ENGINEER_USEFULNESS.md` | done: 16 questions |
| 16 baselines | `BASELINE_COMPARISON.md` | done |
| 17 false value | `FALSE_VALUE_SEARCH.md` | done |
| 18 wrong answers | `WRONG_ANSWER_SEARCH.md` | done: WA-1, WA-2, WA-3 fixed |
| 19 cross-flight consistency | `CAMPAIGN_REPLAY.md` §3 | done |
| 20 determinism | `ANALYZER_MVP.md` §4, `SCALE.md` §3, `REPORT_HASHES.json` | done |
| 21 scale | `SCALE.md` | done: 66 logs, 3 min 6 s |
| 22 analyze-many | `batch/` | done |
| 23 coverage matrix | `COVERAGE.md` §2-3 | done |
| 24 gap analysis | `PRODUCT_GAP_ANALYSIS.md` | done |
| 25 product boundary | `PRODUCT_BOUNDARY.md` | done: B |
| 26 external user test | `EXTERNAL_USER_TEST_PLAN.md` | plan only, by design |
| 27 onboard readiness | `ONBOARD_READINESS_AUDIT.md` | audit only; nothing ported |
| 28 research status | `RESEARCH_STATUS.md` | done |
| 29 novelty discipline | `NOVELTY_DISCIPLINE.md` | done: no new technical question identified; the brief is truncated here |

## 7. Limitations

1. **One real multi-producer event class,** with one dependence structure
   repeated 55 times.
2. **The lineage ground truth** was traced by the team that wrote the
   lineage.
3. **The witnesses come from sealed stage-1 features** at two checkpoints,
   with a known onset.
4. **One PX4 version, SITL.** In SIH, RPM telemetry and rotor state are
   one variable.
5. **No real lane switch** has been analysed.
6. **The usefulness judgements are the team's own.**

## 8. Recommended next steps

| # | step | why first |
|---|---|---|
| 1 | run `EXTERNAL_USER_TEST_PLAN.md` on the nine cases | the central claim is UNVALIDATED RESEARCH until outside engineers use it |
| 2 | an outside, blind trace of the four producers' sources (G8) | the corroboration result's ground truth |
| 3 | one continuous producer from stock topics, with a contract and calibration (G1), and an onset detector (G2) | the condition for any value on a user's own log |
| 4 | a four-motor successor profile through the gate (G3) | the aircraft profile has one motor |
| 5 | with owner approval, the frozen 3-IMU SIH lane-switch experiment | the last untested configuration path on real data |
