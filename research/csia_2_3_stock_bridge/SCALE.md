# Scale: 1 against 4 motors, and a search for combinatorial growth (Phase 11)

**2026-10-02.**

- **Script:** `scale_test.py`.
- **Output:** `SCALE_2_3.json` (30 repetitions per configuration, one
  process, 4-core machine, nothing else running).

## 1. Method

**One real event:** XS1A1-C00-A-E055 (motor_0 at eta = 0.55), through the
stock producers at its three checkpoints. For a profile of N motors
(`build_quad_engine(N)`; the released profile is N = 4):
- motor j's outputs are motor_0's real outputs, renamed, for the first k
  motors (adverse);
- the rest get motor_1's real outputs, renamed (healthy as recorded).

The battery outputs are kept. Every envelope is a real producer output;
only the component name changes.

**Measured on the AFTER tick, with a fresh Analyzer per configuration:**
- symptoms raised;
- hypotheses examined;
- candidates left per symptom (ambiguity);
- 2.1.1's own count of predicate evaluations;
- the step's wall time;
- peak Python allocation;
- the size of its machine form;
- the diagnosability probe's time and size.

**Configurations:** N = 1 and 4 are the brief's comparison. N = 2, 6, 8,
12, 16 with k up to N are the search for growth.

## 2. 1 against 4 motors

| N | k | profile records | symptoms | hypotheses examined | predicate evaluations | candidates left | step (median ms) | peak alloc (KB) | result (bytes) | diagnosability probe (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 17 | 0 | 0 | 0 | — | 0.38 | 17.6 | 3,372 | 5.1 |
| 1 | 1 | 17 | 1 | 5 | 11 | 4 | 0.68 | 29.3 | 8,796 | 5.1 |
| 4 | 0 | 29 | 0 | 0 | 0 | — | 0.75 | 33.2 | 5,679 | 67.3 |
| 4 | 1 | 29 | 1 | 5 | 11 | 4 | 1.04 | 42.0 | 11,103 | 60.5 |
| 4 | 4 | 29 | 4 | 20 | 44 | 4 each | 1.84 | 75.5 | 29,134 | 67.4 |

## 3. The search for growth

| N | k = N: symptoms | hypotheses | predicates | step (median ms) | peak alloc (KB) | result (bytes) | probe (ms) |
|---|---|---|---|---|---|---|---|
| 2 | 2 | 10 | 22 | 0.99 | 39.9 | 16,379 | 15.7 |
| 4 | 4 | 20 | 44 | 1.84 | 75.5 | 29,134 | 67.4 |
| 6 | 6 | 30 | 66 | 2.22 | 105.9 | 41,888 | 150.7 |
| 8 | 8 | 40 | 88 | 2.95 | 145.4 | 54,642 | 305.0 |
| 12 | 12 | 60 | 132 | 4.72 | 219.4 | 80,247 | 897.2 |
| 16 | 16 | 80 | 176 | 7.01 | 313.3 | 105,935 | 1,934.5 |

**The reasoning is linear in the motor count.**
- Each symptom brings 5 hypotheses and 11 predicate evaluations, at every
  N.
- Ambiguity stays at 4 candidates per symptom, whatever else fails.
- 2.1.1 localises per (symptom, subject). It never forms sets of
  subjects, so k simultaneous failures cost k times one: there is no 2^k.
- Memory and the result size grow linearly.
- **Step time** grows from 0.4 ms to 7 ms over N = 1-16.

**One component grows faster: the diagnosability probe**, from 5 ms at
N = 1 to 67 ms at N = 4 and 1.9 s at N = 16. That is roughly N^2.7.
- For every raisable symptom (one per motor) and every hypothesis, it
  tries each catalog record (4N + 13) as the missing one.
- Each try rebuilds a probe index over the observable records (about N).
- It is polynomial, not combinatorial. It runs once per analysis, offline.
- At the released N = 4 it costs 67 ms.

An octocopter profile (N = 8, 0.3 s) is fine. A 16-rotor profile would want
the probe memoised per relation. That is not needed now.

**Timing noise.** The largest single step (31-33 ms at N = 4 and 16, k = N)
is a garbage-collection pause, not reasoning; medians are stable. The
first version of this test ran beside a SITL flight and showed a similar
outlier. It was re-run here alone.

## 4. What scale does not show

**Cloned outputs.** Larger N is built from one real event's outputs. A
real hexa- or octocopter's statistics (median normalisation, the loss axis)
were not exercised.

**Simultaneous real losses** on two motors move the median the statistics
normalise by. The reasoning scales; whether the statistics still separate
the motors was not tested (`LOCALIZATION.md`).

**Whole-flight cost** is dominated by reading the log, not by reasoning:
- about 2 s per 18-37 MB validation log (`ORDINARY_ULOG.md`);
- the 2.2 pilot's 66-flight batch took 3 min 6 s on the estimator path.
