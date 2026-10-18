# The product question (Phase 1)

**2026-10-01.**

## 1. The question

> When multiple real monitors observe the same real vehicle event, does
> CSIA 2.2 produce a more useful and more defensible engineering
> explanation than the monitors provide individually?

**Two conditions, both required:**
- **more useful:** it answers questions the engineer has, which the
  monitors do not answer;
- **more defensible:** what it adds is right, against a ground truth
  independent of CSIA.

**What does not count:**
- **Aggregation alone.** Putting four monitors' outputs on one page, in
  time order, is convenient. Any dashboard does it. It is not evidence that
  the explanation is better.
- **Novelty.** The question is usefulness.

## 2. The test applied

| step | where |
|---|---|
| find every real event that two or more wrapped producers observe | `MULTI_PRODUCER_EVENT_MATRIX.md`: one, motor thrust loss in XSYS-001 (55 trials, with 55 telemetry-fault and 11 nominal counterparts) |
| trace each producer to its raw sources, independently of 2.2's lineage | `INDEPENDENCE_AND_CORROBORATION.md` §1 |
| compare the monitors read individually, 2.1.1 alone and the Analyzer, against the ground truth | `BASELINE_COMPARISON.md`, `INDEPENDENCE_AND_CORROBORATION.md` §2 |
| classify every report element as new value, aggregation, duplicate or misleading | `FALSE_VALUE_SEARCH.md` |
| look for wrong answers | `WRONG_ANSWER_SEARCH.md` |

## 3. The answer

**Yes, on the one real case available, and narrowly.**

**Three elements are more defensible than the monitors read individually.**
Each is right on real data, against an independently traced ground truth:

| element | the monitors individually | the Analyzer | ground truth |
|---|---|---|---|
| how many independent lines of adverse evidence | 3 monitors agree | 2 lines, 1 lineage group, with the shared sources named | 2, in 121/121 trials |
| does the elimination of the alternative rest on independent evidence | not visible | "the refuting evidence shares sensor:imu.1310988" | true in 110/110 fault trials |
| is every output used inside its validated window | not checked | W_DYN's out-of-window output refused | without the refusal, 2.1.1 is wrong in 55/55 A trials (V4) |

**Everything else is aggregation:**
- the key moments;
- configuration changes in PX4 terms;
- coverage;
- the manifest.

It is useful and correctly done, but it is not the answer to the question.

**It is narrow because:**
1. there is one real multi-producer event class, with one dependence
   structure, repeated;
2. the producers come from a research campaign: sealed features and a
   known onset;
3. it is SITL, one PX4 version;
4. the verdict itself is unchanged under the valid variant. 2.1.1 with the
   frozen specification already reached it. The gain is in the
   explanation, plus the refusal under V4;
5. no engineer outside the team has read a report.

**On a stock PX4 log, the answer is no.** The Analyzer has one producer,
EKF2, whose claims cannot see the fault class. The report now says so
(WA-3). See `PRODUCT_BOUNDARY.md` for what that means for the product.
