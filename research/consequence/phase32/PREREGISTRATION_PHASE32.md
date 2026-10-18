# Phase 3.2 — direct preregistered consequence test (H2)

**Written and committed before the Phase-3.2 `locked` partition is opened.**
Scenario family, control, fault grid, telemetry-loss mechanism, seed count,
every definition, the statistical test, the effect-size threshold, the
interval, the stopping rule and the treatment of invalid runs are frozen at
this commit and may not change after locked results are inspected.

**Scope: deterministic simulation.** No hardware, no RF, no armed physical
vehicle, no real actuator, no flight, no SITL execution, no autopilot
execution. Evidence level `MODEL_BASED_ACTION_CONSEQUENCE`.

---

## 1. Measured starting state

| item | value |
|---|---|
| HEAD | `48f7b8d7e21f2a13cb0c7110aa8b929162d2a32c` |
| Phase-3.1 amendment freeze | `7b890ba369d250ac481adb945f835f48a068e4b3` |
| working tree | clean |
| frozen core | 12 of 12 match `docs/v1/FROZEN_BASELINE.json`, 0 mismatches |

### Frozen inputs, hashed

| artifact | sha256 |
|---|---|
| `phase31/PREREGISTRATION_PHASE31.md` | `5d6b75745e66d70cc682598cc07603f4dcb26996de73b786cbd32da4ce6b1934` |
| `phase31/results/PHASE31_RESULTS_LOCKED.json` | `92e47af2d2cb3a31761109a9ed9a302d473ca1103be17cecc9fd0e9b597df946` |
| `phase31/results/PHASE31_TRACES_LOCKED.json` | `e8c2d90d81b16835d48e4ae5c2a35fad54101e751b8d64dda74c50afaf56539e` |
| `phase31/results/PHASE31_MUTATION_RESULTS.json` | `83fb30f2d86ceda6bbed4ab57615764acb741d39e8a218fd42df4baa7e4336ff` |
| `phase3/results/PHASE3_RESULTS_LOCKED.json` | `d1e911ba6d770d5afa5ab542d1fe037be8a538a9a29f0a5589a77551c27dd3e3` |
| `research/bus_provenance/results/E2M_MUTATION_RESULTS.json` | `4f30ff13620dbc7b93025de922ee209526d4323f9492a199b882577843c38e12` |

`FL-025` through `FL-029` are present and unchanged. The eight Phase-2
candidates are unchanged and none is replaced. `SOURCE_INDICATORS` is **not**
repaired; the frozen core is not edited.

## 2. Pooling rule, stated before execution

**Phase-3.2 results are NOT pooled with Phase 3 or Phase 3.1.** Three disjoint
seed partitions, asserted by test. No combined count, rate, p-value, interval
or effect size over more than one campaign may be computed or reported. Where
campaigns are mentioned together they are reported side by side with their
partitions named.

Phase 3's `3/24` versus `1/24` at p = 0.625 and Phase 3.1's `40/40` versus
`0/40` at p = 1.82 × 10⁻¹² both stand exactly as recorded.

## 3. The primary question

> Does fault-dependent loss of diagnostic support produce an operationally
> incorrect or unsupported action when the correct response differs from the
> current policy response?

Tested against **P0 versus ground truth**. P2 is excluded from the primary
test because `FL-029` establishes that its support mapping is invalid: the
LOW-sets it reads from `SOURCE_INDICATORS` omit the per-IMU Doppler edges, so
its `NON_IDENTIFIABLE` verdicts do not mean what the policy takes them to
mean. P2 appears only in a separate table labelled
**`P2_CURRENT_IMPLEMENTATION_EXPLORATORY`**, and no H2 conclusion rests on it.

## 4. Primary arm

**Family:** `structural` — `vibration_anomaly` on the `vibration` node.

**Telemetry-loss mechanism:** the `motor_esc` node emits **no samples at all**
for the whole run. The vehicle is armed from t = 0 and airborne from t = 5.0 s
throughout; **no disarmed-gate logic is used anywhere in Phase 3.2**, as a
condition or as a control. Because `csia/runtime/online.py` computes every
edge as `gate * fresh[a] * fresh[b]` and applies
`P["vibration"] *= float(fresh["motor_esc"])`, the absence makes
`accel_motor_current`, `accel_esc_rpm` and the `phys_vibration` cross-gate
simultaneously unavailable while flying.

**Fault onset and duration:** onset 28.0 s, duration 20.0 s, on a 60.0 s
`hover_circle` flight. Fixed for every grid point.

**Fault-magnitude grid, evaluated in full:**

```
gain ∈ {1.5, 2.0, 2.5, 3.0, 4.0}
```

**Every grid point is run and reported. None is sorted, pruned, dropped or
re-ordered on the basis of expected behaviour.** Phase 3.1 measured crossing
time to be **non-monotone** in fault rate for the IMU family — 0.12 crossed at
26.96 s while 0.18 and 0.25 crossed later — so any procedure that assumed
monotonicity would be unsound here. The grid is a declared list, iterated in
declaration order.

**Confirmatory grid point: `gain = 3.0`**, the value Phase 3.1 used. That
single point carries the H2 verdict. The other four are preregistered
dose-response secondaries, reported in full, with **no** multiplicity
correction claimed and no verdict resting on them.

### Conditions

| id | condition |
|---|---|
| **N** | matched nominal — no fault, ESC telemetry present. Run once per seed per family; it does not depend on the grid point. |
| **EA** | matched fault, **evidence applicable** — ESC telemetry present |
| **EG** | matched fault, **evidence gated** — ESC telemetry absent |

EA is the matched-fault control: identical seed, trajectory, fault family,
onset, duration and magnitude, differing only in whether `motor_esc` reports.

## 5. Secondary arm

**Family:** `imu_isolation` — `imu0` accel-z `bias_drift`, onset 15.0 s,
duration 40.0 s, same conditions, and its own grid evaluated in full:

```
rate ∈ {0.03, 0.05, 0.08, 0.12, 0.18}
```

Secondary. It carries no H2 verdict, and it is the arm from which the
exploratory P2 table is drawn.

## 6. Seeds

`csia_consequence/phase32_partitions.py`, domain
`csia/direct_consequence_test_phase32/2026-09-20`, disjoint from the
phase-one, follow-up (with companions), Phase-2, **Phase-3 and Phase-3.1**
partitions.

| partition | seeds |
|---|---|
| `development` | 12 |
| `validation` | 16 |
| `locked` | **40** (sealed) |

Manifest hash: `b1867fb6a050bb7882209260fc8209d548c3224a5dbb1e57deac991d5aaeca05`

**Eligible seed count for the confirmatory test: 40 paired seeds**, matching
Phase 3.1 so the two are readable side by side without being pooled.

## 7. Definitions, all fixed here

**Action conflict.** The set of response *classes* issued differs from the
correct response's class, using the `RESPONSE_CLASS` map unchanged from the
Phase-3 independent evaluator. Issuing nothing where a response is required
is a conflict. Defined on **issued actions**, not on how long a response label
persists, because the frozen failsafe issues each action exactly once.

**Correct response.** Ground truth from the latent fault, not from any policy:
`vibration_anomaly → PREPARE_LANDING` (class `TERMINATE`);
`imu_bias on imu0 → SELECT_IMU1` (class `ATTRIBUTION_IMU1`);
no fault → `NONE` (class `NO_ACTION`).

**Unsupported confident attribution.** An attributing response issued while
the pair it discriminates is reported not identifiable, measured with the
Phase-3.1 span rule (`ticks / TICK_HZ`).

**Safe state.** Modelled altitude ≤ `SAFE_STATE_ALT_M = 0.5 m`. Unchanged
from Phase 3.

**Escalation.** Correct escalation: the correct response class was issued in a
scenario whose latent truth requires one. False escalation: any actionable
response issued in condition **N**.

## 8. Statistics

**Primary test.** Exact two-sided McNemar on the seed-paired action-conflict
indicator, **EG versus EA, at `gain = 3.0` only**, α = 0.05.

**Effect size.** The paired risk difference `RD = (b − c) / n` over the n
valid paired seeds, where b and c are the discordant counts.

**Effect-size threshold, declared in advance: `MIN_RD = 0.50`.** An RD below
it is reported as observed but is **not** described as a demonstrated
consequence, whatever its p-value. With 40 paired seeds a statistically
significant but small RD would be a real difference of no operational
interest, and saying so afterwards would be a choice made with the numbers in
view.

**Confidence intervals.**
- Per-condition conflict rates: exact Clopper–Pearson 95 %.
- Paired risk difference: the **exact conditional interval** — a
  Clopper–Pearson 95 % interval on `p = b / (b + c)` transformed by
  `RD = (2p − 1)(b + c) / n`. It is conditional on the number of discordant
  pairs, which is stated wherever it is reported; it is not a marginal
  interval and is not presented as one.
- Odds ratio: `b / c`, which is **not finite when c = 0**. In that case no
  point estimate is reported and only the risk difference and its interval
  are.

**Stopping rule.** Run every declared grid point on all 40 locked seeds,
once. No interim looks, no extension, no seed added after any result is seen,
no grid point added or removed.

**Invalid runs.** A run is invalid if the campaign raises, if it produces zero
ticks, or if the trust layer reports `bad_samples > 0`. Invalid runs are
counted, their reason recorded per run, and they are **excluded from the
paired test with the exclusion reported**. A seed with an invalid run in
either arm of a pair is dropped from that pair, and the pair count n is
reduced accordingly. **If more than `MAX_DROPPED_PAIRS = 4` of the 40 pairs
are dropped at the confirmatory grid point, the confirmatory test is reported
as `UNDERPOWERED_BY_EXCLUSIONS` and no H2 verdict is drawn from it.**

## 9. Outcomes recorded

Action-conflict rate; unsupported confident attribution; correct escalation
rate; false escalation rate; time to `CAUTION`; time to `CRITICAL`; time to
`EMERGENCY`; time to modelled safe state; position error; altitude error;
geofence margin; energy margin; fault-window duration; ambiguity duration.

Per the Phase-3.1 declaration, carried forward unchanged: **position error is
meaningful only for the IMU family**; `structural` has a declared drift rate
of 0.0 and its meaningful column is time to safe state; **the energy margin is
meaningful for no family** and is recorded and labelled rather than dropped.

## 10. Independence

`research/consequence/phase32/evaluate32.py` imports the standard library
only. It does not import the CSIA policy implementation, the support
classifier, the consequence model or the campaign. A test asserts this in a
fresh interpreter. It is a second derivation by the same author, not a second
party, and that limit is not softened.

## 11. Kill criteria

**H2 is supported at Phase 3.2** only if, at the confirmatory grid point, the
exact McNemar p < 0.05 **and** the paired risk difference exceeds
`MIN_RD = 0.50` in the direction of more conflicts under EG, **and** the
matched nominal control N shows no false escalation.

**H2 is not supported** if any of those fails, including the case where the
conflict appears in EA as well — which would mean the gating is not what
produces it.

## 12. What Phase 3.2 may not conclude

No hardware, SITL, HIL or flight validation. No autopilot execution. No claim
that P2 is safe or unsafe in general — `FL-029` makes its current mapping
invalid and that is a statement about this implementation. No universal
prevalence: one fault family confirmatory, one secondary, one airframe
profile, one trajectory, one simulator. No certification, no airworthiness,
no novelty. Nothing about the five Phase-2 candidates still outside the frozen
core's exposed interface.
