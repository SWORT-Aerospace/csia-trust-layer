# False-value search (Phase 17)

**2026-10-01. NON-CONFIRMATORY.**

**The question:** is each thing the report shows actually worth showing,
or does it only look valuable?

**Classes:**
- **NEW ENGINEERING VALUE:** an answer the monitors read individually and
  2.1.1 alone do not give, and that was right on real data.
- **USEFUL AGGREGATION:** information that exists elsewhere, assembled
  where the engineer needs it.
- **DUPLICATE INFORMATION:** already in another baseline, or in another
  part of the report, adding nothing.
- **MISLEADING:** could lead a careful reader to a wrong conclusion.

**Baselines:** `BASELINE_COMPARISON.md` (A raw log, B producers, C 2.1.1
alone).

## 1. Every element of the report, classified

| # | report element | class | evidence |
|---|---|---|---|
| 1 | the verdict: symptom, outcome, remaining explanations | DUPLICATE INFORMATION | 2.1.1's own. Identical to C on 3,872 XSYS-001 slots, except V4 at C3, where the difference comes from admissibility (row 7) |
| 2 | "eliminated … by \<predicate\>" | DUPLICATE INFORMATION | in 2.1.1's trace |
| 3 | supporting and refuting evidence, with "rests on" sources | USEFUL AGGREGATION | the trace joined with each contract's lineage. Reconstructible by hand from the contracts |
| 4 | "the refuting evidence shares sensor:imu.1310988: it is not independent corroboration" | **NEW ENGINEERING VALUE** | in all 110 A and B trials; matches the code-path source analysis; absent from B and C |
| 5 | adverse evidence as lineage groups and independent lines | **NEW ENGINEERING VALUE** | 121/121 trials equal the ground-truth count; the naive count is wrong by one in 55/55 A trials |
| 6 | which members of a lineage group share each source | USEFUL AGGREGATION | after FV-1 (§2). **Before it: MISLEADING** |
| 7 | refusals with a reason (REGIME_INVALID, STALE, CONFIGURATION_MISMATCH, …) | **NEW ENGINEERING VALUE** | V4: C is wrong in 55/55 A trials; the Analyzer refuses W_DYN's out-of-window output and is AMBIGUOUS and correct in 55/55. A 2.2-phase result, re-verified in Phase 0 |
| 8 | "would discriminate, but could not be evaluated" | USEFUL AGGREGATION | 2.1.1's unavailable predicates, with their meaning (U3) |
| 9 | key moments | USEFUL AGGREGATION | derivable from the per-tick results; nobody would derive them by hand (`ENGINEER_USEFULNESS.md` questions 5, 6) |
| 10 | timeline intervals | USEFUL AGGREGATION | 1,718 ticks in 10 intervals (median flight) |
| 11 | configuration changes in PX4 terms | USEFUL AGGREGATION | decoded from `estimator_status` and the selector; in the log as bitmasks and counters |
| 12 | coverage states, NO_ANOMALY distinct from NOMINAL | USEFUL AGGREGATION | the contract's `nominal_means`. **Before the pilot: MISLEADING**, because CUSUM silence was shown as NOMINAL |
| 13 | profile coverage and the "scope" line | USEFUL AGGREGATION | the profile's records against what the producers emitted. **Before the pilot: MISLEADING by omission (WA-3)** |
| 14 | EKF2 innovation claims NOMINAL in a motor-fault report (U1) | DUPLICATE INFORMATION for this fault class | AUC 0.43-0.55: they cannot see it. Risk FV-2 (open, §3) |
| 15 | attribution "NO_EVIDENCE (NOTHING_ADVERSE)" beside a SUPPORTED localization | DUPLICATE INFORMATION | 2.1.1's attribution. The added note says the localizations are the diagnosis. Risk FV-3 (open, §3) |
| 16 | profile warnings PV2 and PV3 in every aircraft report | DUPLICATE INFORMATION | the same four static warnings in all 66 flight reports; they describe the profile, not the flight |
| 17 | producer health changes | USEFUL AGGREGATION | U4: EKF2 alignment at 2.7 s |
| 18 | predicate faults and "may rest on the failed refuter" | USEFUL AGGREGATION | 2.1.1's predicate-fault trace, surfaced (U8) |
| 19 | the manifest | USEFUL AGGREGATION | hashes and versions in one place; reproduction verified byte for byte |
| 20 | batch index and coverage matrix | USEFUL AGGREGATION | per-flight lines; no fleet statistic is computed |

**Count:**
- NEW ENGINEERING VALUE: 3 (rows 4, 5, 7);
- USEFUL AGGREGATION: 12;
- DUPLICATE INFORMATION: 5;
- MISLEADING now: 0 confirmed. Three were found and fixed (rows 6, 12, 13).

## 2. The MISLEADING elements found and fixed

| id | what a careful reader could conclude | why it was wrong | fix | pinned |
|---|---|---|---|---|
| NOMINAL silence | "CUSUM observed the battery, and it was healthy" | a CUSUM that has not alarmed has not shown health | `nominal_means` NO_ANOMALY in the CUSUM contract (cusum-2) | `test_a_silent_detector_is_no_anomaly_and_an_unseen_source_is_no_coverage` |
| WA-3 | "the motor-degraded flight was clean" | no producer observed the motors | profile coverage and the scope line | `test_wa3_a_verdict_names_the_profile_records_nothing_observed` |
| FV-1 | "W_RPM, W_CTRL and W_DYN all share the motor command and the IMU" | a lineage group is transitive: W_RPM and W_DYN share nothing. The independent-line count (2) was right; the sentence explaining it was not | each shared source now names the members that hold it | `test_fv1_a_lineage_group_names_who_shares_each_source` |

**FV-1, as the report now reads (U1):**

```
linked through shared sources (a group is transitive: two members may share nothing):
  channel:motor_command.motor_0: CONTROL/motor_0 [xsys:w_ctrl], ACTUATION/motor_0 [xsys:w_rpm]
  sensor:imu.1310988: CONTROL/motor_0 [xsys:w_ctrl], NAVIGATION/motor_0 [xsys:w_dyn]
```

## 3. Risks found and not fixed

**FV-2. Uninformative claims printed beside informative ones.**
- **What the report shows:** U1 prints "INNOVATION_POS: NOMINAL 161"
  beside "RPM_DEFICIT: ANOMALY 149".
- **How a reader could misread it:** as "if the motor really lost thrust,
  the navigation filter would have noticed".
- **What the report says:** nothing in favour of that reading.
- **What it does not say:** that these claims cannot see this fault class.
- **Why not fixed:**
  - the fix belongs in the contract: a declared diagnostic role for each
    claim, and the fault classes it is known blind to;
  - that is a contract-schema change, with its own validation.

  Listed in `PRODUCT_GAP_ANALYSIS.md`.

**FV-3. "NOTHING_ADVERSE" beside three adverse outputs.**
- **Where the words come from:** 2.1.1's attribution reason code. It means
  "nothing adverse that cross-domain attribution reads".
- **Mitigation:** the report adds that the localizations are the
  diagnosis.
- **Why the wording stays:** changing it would change 2.1.1's output.
  That is a Semantic Core change, which this pilot does not make.

## 4. What this means for the value claim

**The value that is NEW rests on three elements, all measured on real
data:**
- the shared-source warning under an elimination;
- the independent-line count;
- refusal of invalid evidence.

**Everything else is aggregation.** Aggregation has value; it is not
evidence that CSIA explains better. The three elements are.

**The three fixed MISLEADING elements are a warning about the report
layer.** Each was invisible to the record-level probes. Each was found only
by reading a real report as an engineer would.
