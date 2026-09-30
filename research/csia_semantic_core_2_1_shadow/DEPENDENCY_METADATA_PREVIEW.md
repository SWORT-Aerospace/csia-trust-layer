# Correlated evidence, dependency metadata, monitor health and the evidence contract

**2026-09-30. Parts 29, 37, 38, 41 and 42 of the shadow-validation brief.
SYNTHETIC AND SHADOW ONLY.** Script: `imu_dependency_preview.py`. Output:
`IMU_DEPENDENCY_PREVIEW.json`.

**Nothing here is implemented in 2.1.** This is a design input for the next
architecture phase.

## 1. Three monitors on one IMU: how 2.1 represents them today

| monitor | what it is | as a 2.1 evidence record | real source lineage |
|---|---|---|---|
| A | threshold detector on IMU1 rate | SENSOR/imu1 `monitor.rate_threshold` | {imu1} |
| B | CUSUM on IMU1 rate | SENSOR/imu1 `monitor.cusum_mean_shift` | {imu1} |
| C | estimator innovation (IMU1-driven prediction against GNSS) | COMPUTE/state_estimator `monitor.innovation`, optionally `depends_on SENSOR/imu1` | {imu1, gps, model:ekf} |
| D (control) | threshold detector on IMU2 | SENSOR/imu2 `monitor.rate_threshold` | {imu2} |

**2.1 never counts confirmations.**
- **Attribution** works on components. A and B are two records of one
  component, so they are one candidate.
- **Localization** works on predicates. A confirmer is either True or not,
  whatever number of records made it so.

So 2.1 cannot multiply confidence the way naive vote counting does.

**What it can do is treat shared-source evidence as cross-domain
corroboration.** C1's independence notion is "a discriminator from another
domain". C is COMPUTE and A and B are SENSOR, yet C descends from IMU1. With
C's dependency on IMU1 undeclared, 2.1 has no way to know that.

## 2. The experiment

The count column says how many independent confirmations each policy gives
an alarm pattern:

- **Naive:** one per alarming record.
- **2.1's cross-domain notion:** distinct domains among the alarms, a proxy
  for what C1 would treat as corroborating.
- **Minimal dependency-aware policy:** collapse records with the same producer
  and claim, then take the largest set of alarms whose source lineages are
  pairwise disjoint.
- **Dependency-aware plus validity:** as the previous row, after dropping
  content older than the producer's validity.

| case | truly independent | naive | 2.1 domains | dependency-aware | dep-aware + validity | 2.1 attribution (C's dependency declared / undeclared) |
|---|---|---|---|---|---|---|
| 1 all three agree | 1 | 3 | 2 | 1 | 1 | AMBIGUOUS {estimator, imu1} / same |
| 2 A and B agree, C nominal | 1 | 2 | 1 | 1 | 1 | AMBIGUOUS {imu1} / same |
| 3 IMU1 biased | 1 | 3 | 2 | 1 | 1 | AMBIGUOUS {estimator, imu1} / same |
| 4 estimator model wrong (C alone) | 1 | 1 | 1 | 1 | 1 | **UNIQUE estimator** / AMBIGUOUS |
| 5 A republished under a new identity | 1 | 4 | 2 | 1 | 1 | AMBIGUOUS / same |
| 6 B's output latched, anomaly over | 0 | 1 | 1 | 1 | **0** | AMBIGUOUS {imu1} / same |
| 7 control: two independent IMUs agree | 2 | 2 | **1** | 2 | 2 | AMBIGUOUS {imu1, imu2} / same |

| policy | over-count (sum) | false corroboration (count ≥ 2, truth < 2) | lost corroboration (truth ≥ 2, count < 2) |
|---|---|---|---|
| naive | 9 | 4 | 0 |
| 2.1 domains | 4 | 3 | **1** |
| dependency-aware | 1 | 0 | 0 |
| dependency-aware + validity | 0 | 0 | 0 |

**The answer to Part 38's question: yes.**
- **It prevents false multiplication without losing independent evidence.**
  The minimal dependency-aware policy removes every false corroboration and
  keeps the genuine one in case 7. 2.1's domain notion both over-counts
  (cases 1, 3, 5) and under-counts (case 7: two independent IMUs are one
  domain).
- **Staleness is a separate problem.** Case 6 needs validity, not dependency.
- **Declaring C's dependency is what makes the model-error case (4)
  attributable.** With IMU1 as a declared alternative that is affirmatively
  nominal, 2.1 names the estimator UNIQUE. Without it, it cannot.

**Limits.** Seven constructed cases with truth fixed by construction show the
mechanism. They do not measure how often it happens.

## 3. The minimum dependency model (Part 37)

**Which field prevents which failure:**

| field | prevents | needed now? |
|---|---|---|
| `producer_id` + `claim` | duplicated outputs counted as independent (case 5; L8) | **yes** |
| `source_lineage`: the set of root sources (sensors, and models by id) | false independence between monitors of one sensor (cases 1, 3; L1, L12) | **yes** |
| `model_id` inside the lineage | shared-model failure (L2); model error against sensor error (case 4) | **yes**, as a lineage element, not a separate mechanism |
| `content_time` + a validity declaration (§5) | stale outputs counted as current (case 6; L4) | **yes** |
| `calibration_id` | shared calibration (L3) | later: fold into the lineage when a real calibration source exists |
| `power_domain`, `compute_node` | common-cause loss of monitors | **no**: already expressed by `dependencies` in 2.1's profile |
| `timebase` | incomparable timestamps (L7) | later, with the admissibility layer |
| `parent_evidence_ids` | derived evidence counted with its inputs | **no**: `attributable=False` already covers roll-ups in v2 |
| `transformation_id`, `independence_group` | — | **no**: lineage disjointness gives independence directly; a hand-assigned group is a second, error-prone source of the same fact |

**The minimum is four fields:** `producer_id`, `claim`, `source_lineage` and
`content_time`. Only `source_lineage` needs new reasoning, a disjointness test
over small sets, and that is **only for counting corroboration**.

## 4. Minimum producer health (Part 41)

A producer's diagnostic result and its own health are two separate fields.
A result of NOMINAL from a FAULTED producer is not nominal evidence about the
aircraft.

| producer health | meaning | how CSIA must read the producer's result |
|---|---|---|
| OK | operating within its declared regime and rate | as evidence |
| DEGRADED | operating, outside a declared quality bound (reduced rate, reduced input set) | as evidence, with the degradation in the trace; not usable as a sole discriminator |
| UNAVAILABLE | not producing | no evidence; the claim is UNKNOWN, never NOMINAL |
| FAULTED | producing, but its self-check failed | no evidence; UNKNOWN, and the fault is itself evidence about the producer's host |
| UNKNOWN | health not reported | as UNAVAILABLE for any claim that would exclude a hypothesis |

**Terminology** (V0): these follow the "available / degraded / unavailable"
usage of health-management and diagnostic-event practice. The one rule that
matters is that `UNAVAILABLE`, `FAULTED` and `UNKNOWN` never become
affirmative NOMINAL. That is C2's rule for missing evidence, extended to the
producer.

## 5. Minimum evidence contract (Part 42)

Each field is kept only if it would have prevented a loophole ranked P0 or P1
in `LOOPHOLE_REGISTER.csv`.

| field | prevents | example (the CUSUM of `CUSUM_INTEGRATION_EXAMPLE.md`) |
|---|---|---|
| `producer_id`, `producer_version` | L9 version drift; L8 duplication | `cusum@imu1` v1.2 |
| `claim` | a result read with a meaning it does not have (L6) | "mean shift of IMU1 z-rate beyond k·σ" |
| `supports` / `refutes`: the hypotheses the claim bears on | CSIA inventing a relevance the producer did not state | refutes `SENSOR/imu1_nominal`; supports nothing about actuators |
| `source_lineage` | L1, L2, L12 | {imu1} |
| `operating_regime` | L11 conditioning error | "hover and cruise, rates < 2 rad/s" |
| `validity`: `max_content_age` and/or `invalidating_events` | L4 stale configuration; L8 replay | age 0.5 s; invalidated by an IMU re-selection or an estimator reset |
| `update_rate` | slow-but-valid read as stale (E1) | 250 Hz |
| `health` (§4) | L14 malformed producer; a faulted producer read as nominal | OK |
| `profile_compatibility`: the profile digest(s) it was declared against | L5, L9 | `c7541cab…` |

**Not in the minimum:** latency distributions, confidence numbers, and free
text.
