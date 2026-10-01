# Baseline comparison (Phase 16)

**2026-10-01. NON-CONFIRMATORY.**

**Rule:** no numeric gain is claimed beyond what was counted. Where a
baseline was not run, the cell says what that baseline contains, not what
it would score.

## 1. The four baselines

| | what the engineer has | run in this pilot? |
|---|---|---|
| **A. raw flight log** | the ULog, plotted (e.g. PX4 Flight Review or pyulog) | not as a user study; its contents were checked topic by topic |
| **B. individual producers** | each monitor's output, read on its own: W_RPM, W_DYN, W_CTRL, EKF2 status, CUSUM | yes: the outputs are the campaign's |
| **C. 2.1.1 without Evidence Assurance** | the Semantic Core fed the producers' records directly, with its trace; no contracts, admissibility, lineage, coverage or report | yes: the 2.2 replay's 2.1.1 arm (`REPLAY_2_2_RESULTS.json`), re-verified in Phase 0 |
| **D. the 2.2 Analyzer** | `report.txt`, `report.json`, `manifest.json` | yes |

## 2. What was measured on the real multi-producer case

**Data:** XSYS-001, 121 trials, PX4 547e2ca SITL.

| measure | A | B | C | D |
|---|---|---|---|---|
| verdict at C3, V3 (A, B, N trials) | not run | W_RPM alone is adverse in 55/55 A **and** 55/55 B trials: it cannot separate a motor fault from a telemetry fault | 55/55, 55/55, 11/11 correct | 55/55, 55/55, 11/11 correct (the same) |
| verdict at C3 with W_DYN read outside its validated window (V4) | — | an engineer reading W_DYN's T3 output sees "no response" | **A trials: WRONG 55/55** (SENSOR/response_sensor) | **A trials: AMBIGUOUS, correct, 55/55**; W_DYN refused as REGIME_INVALID; the two discriminators named |
| adverse evidence counted as corroboration (A trials) | — | 3 monitors agree (naive count 3; ground truth 2): wrong by one in 55/55 | no count | 2 independent lines in 1 lineage group: right in 121/121 |
| the elimination of the alternative rests on one IMU | — | not visible | not visible | stated in every A and B report |
| a flight log alone, motor degraded (55 flights) | RPM, motor commands and body rates are all in the log; an engineer who knows where to look can see the deficit | EKF2 innovations NOMINAL: not informative (AUC 0.43-0.55) | — | "no symptom", with "observed 0 of 68 profile records" (after WA-3); **no diagnosis** |

**Notes on these results:**
- The V4 result is the 2.2 phase's, not new in this pilot. It is the only
  case where C and D give different verdicts on real data.
- The counting result is this pilot's (`INDEPENDENCE_AND_CORROBORATION.md`).
- **On a flight log alone, D is worse than A for diagnosis.** It has one
  producer, and that producer is blind to this fault class. A has every
  topic.

## 3. The engineer's questions, by baseline

**Questions:** from `ENGINEER_USEFULNESS.md`.

**Key:**
- **YES:** answered without further work;
- **PARTIAL:** answerable with expert effort or only in part;
- **NO:** not available from that baseline.

| # | question | A raw log | B producers | C 2.1.1 alone | D Analyzer |
|---|---|---|---|---|---|
| 1 | what went wrong, where | PARTIAL (expert reading; no fault class) | PARTIAL (motor 0 flagged; W_RPM cannot separate A from B) | YES | YES |
| 2 | why the alternatives fell | NO | NO | YES (trace) | YES, with the evidence and its sources |
| 3 | how much independent evidence | NO | NO (counts 3 where there are 2) | NO | YES |
| 4 | is the ruling-out independent | NO | NO | NO | YES |
| 5 | when it started, who saw it first | PARTIAL (plots) | PARTIAL (each monitor's own time) | PARTIAL (per-tick states) | YES |
| 6 | when certainty came and went | NO | NO | PARTIAL (diff the ticks) | YES |
| 7 | what evidence was refused, and why | NO | NO | NO (V4: wrong 55/55) | YES |
| 8 | what would resolve an ambiguity | NO | NO | PARTIAL (unavailable predicates in the trace) | YES |
| 9 | what was not observed | PARTIAL (the engineer knows the logged topics) | NO (silence looks like health) | NO | YES (after WA-3) |
| 10 | configuration changes and their effect | PARTIAL (raw bitmasks and counters) | NO | PARTIAL (epochs, if supplied) | YES |
| 11 | were the monitors healthy | PARTIAL | PARTIAL (if a monitor reports its own status) | NO | YES |
| 12 | is the estimator relevant to this fault | PARTIAL | PARTIAL | NO | PARTIAL |
| 13 | can it be reproduced | PARTIAL (the log's hash) | NO | PARTIAL | PARTIAL (no library versions) |
| 14 | is this flight like the others | NO | NO | NO | PARTIAL (batch index) |
| 15 | how bad is it | **YES** | **YES** (the statistics) | PARTIAL (in the records, no report) | **NO** |
| 16 | what to do | NO | NO | NO | NO (by design) |

**Tally:**

| | A | B | C | D |
|---|---|---|---|---|
| YES | 1 | 1 | 2 | 11 |
| PARTIAL | 7 | 4 | 6 | 3 |
| NO | 8 | 11 | 8 | 2 |

**These tallies are the pilot team's own reading.** They are a map of
where each baseline has the information, not a usefulness score. The
external test (`EXTERNAL_USER_TEST_PLAN.md`) is what would measure
usefulness.

## 4. What the comparison says

1. **Against B (the monitors read individually),** D adds three things,
   each measured on real data:
   - the right count of independent evidence (121/121, where the naive
     count is wrong in 55/55 A trials);
   - the visibility of a shared source under the elimination;
   - the refusal of out-of-window evidence (V4).
2. **Against C (2.1.1 alone),** the verdicts are identical except V4, where
   C is wrong in 55/55 A trials and D is not. Everything else D adds is
   explanation: sources, independence, refusals, key moments, scope.
3. **Against A (the raw log),** D adds the reasoning and loses the
   magnitudes. On a stock flight log with no witnesses, D adds no
   diagnosis at all.
4. **The value is conditional on producers.** With three real monitors, D
   is the most useful of the four. With one monitor blind to the fault, it
   is the least useful for diagnosis, and it now says so.
