# Phase 5 preregistration — the hybrid detector study

**Written and committed before the Phase-5 `validation` or `locked`
partitions are opened.** Detectors, baselines, threshold grids, partitions,
fault grids, onset sets, horizon, every definition, the matching procedure,
the intervals, the minimum effect sizes, the dominance criterion, the
stopping rule and the multiplicity treatment are frozen at this commit and
may not change after any locked result is inspected.

**The goal is not to make CSIA appear superior to CUSUM.** Phase 4 measured
CSIA to be roughly 31× slower than CUSUM at a matched observed false-alarm
operating point, and that result stands, is not reopened, and is not pooled
with anything here. The question this phase asks is a different one.

> **Can a fast detector provide timely suspicion while CSIA determines
> whether the evidence supports attribution and what vehicle capability
> remains justified?**

**Scope: deterministic simulation.** No hardware, no RF, no armed vehicle, no
actuator, no HIL, no SITL, no flight, no autopilot execution. The fast path
emits a suspicion, the support layer emits a typed state, the capability
layer emits a record, and a **model** consumes them. A vehicle never does.

---

## 1. Measured starting state

| item | value |
|---|---|
| HEAD at preregistration | `cd08191805cadf602404b3431d65a70376a0b54e` |
| frozen core | 12 of 12 match `docs/v1/FROZEN_BASELINE.json`, digest `b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8` |
| Phase-4 locked runs | sealed, sha256 `c8f3f94b7eefb1e005ac6fd86c3e624f47d083ef18fc48b766351210cdda57f7` |
| Phase-4 locked result | sealed, sha256 `6fff064168090336ec64e453c5f03d3bdc6402752f859f047b974768e2926812` |
| Phase-3.2 locked result | sealed, sha256 `2f58a6ae415ecccfdc4a3b4c331d0cab4c42954464eaf155ed23beaa6f20d2c6` |
| Phase-5 partition manifest | `4659a6a1fed28716b87a319acb01a013b796b3236fcce5dcb6868113423a2a84` |

**Nothing in Phase 5 is pooled with Phase 3, 3.1, 3.2 or 4.** Different seed
partitions, asserted disjoint by test, different question, different unit of
analysis.

## 2. Partitions

| partition | seeds | what it is for |
|---|---|---|
| `development` | 12 | scenario construction, debugging, and **all** tuning — thresholds, detector parameters, policy rules |
| `validation` | 16 | one dress rehearsal of the frozen design, read **once**, after this document is committed |
| `locked` | 40 | opened **once**, after validation, never tuned against |

`locked` raises `PermissionError` unless the call site spells out that it is
opening it. Every threshold, gain, dwell, reset rule and policy constant is
selected on `development` and on nothing else. A parameter chosen on
`development` and evaluated on `development` is not a measurement, which is
why `validation` exists.

**One validation read is permitted.** If validation shows a candidate failing
its hypothesis, the candidate is **still carried to locked and reported as
failing**. Candidates are not dropped, added or retuned after this document
is committed.

## 3. Scenario space — identical for every baseline

Every baseline reads **the same series**: the same measurements, the same
fault trajectories, the same onset times, the same seeds, the same horizon.
One series is built per scenario and all seven baselines are read off it, so
no baseline can differ because it saw different data.

| axis | declared values |
|---|---|
| node | `vibration` |
| horizon | `[0, 60] s`, tick 25 Hz, settling window `SETTLE_S = 10.0 s` from `FailsafeConfig.arm_time` |
| condition | `EA` — ESC telemetry present · `EG` — ESC telemetry absent (the Phase-3.2 physically consistent in-flight gating condition) |
| fault shape | `ABRUPT` — one `vibration_anomaly` · `GRADUAL` — a five-stage staircase ramp of `vibration_anomaly` windows at rising gain |
| gain grid | `[1.5, 2.5, 4.0]` |
| onset grid | `[20.0, 30.0]` |
| fault duration | 20.0 s total |
| nominal | one per condition, per seed |

**26 scenarios per seed** = 2 nominal + 2 conditions × 2 shapes × 3 gains × 2
onsets. Locked: 40 × 26 = **1040 runs**.

**The gradual shape is built from the frozen fault API and nothing else.** It
stacks five `vibration_anomaly` windows of 4 s each at gains
`g × [0.40, 0.55, 0.70, 0.85, 1.00]`, which ramps the same statistic on the
same node. Using a different node for the gradual arm would confound fault
shape with node, so it is not done.

### Two frozen pipelines, over one generated flight

Each scenario generates **one** flight from its seed and fault list, and that
one flight feeds two frozen pipelines:

| pipeline | what it provides | used by |
|---|---|---|
| batch — `PredictionComparator` + `TrustEngine` | the pre-transform λ, its gate, and the trust series | every detector: `B0`, `B1`, `B2`, the fast path, `B5` |
| streaming — `OnlineTrustLayer` | `TrustState` per tick: edge gates, freshness, armed flag, posterior | the support layer, the frozen `FailsafePolicy`, and every consequence metric |

Both are in the frozen core and neither is modified. The λ CUSUM needs is not
exposed on the streaming path and the `TrustState` the support layer needs is
not produced by the batch path, which is why both are run rather than one
being made to serve both. **The fault trajectory, the seed and the horizon
are identical across the two**, so no baseline sees a different fault from
any other.

### What counts as "the alarm", per baseline

Latency is meaningless unless this is fixed in advance:

| baseline | the alarm is |
|---|---|
| `B0` | trust below θ for `DWELL_TICKS` consecutive active ticks |
| `B1` | CUSUM statistic above `h` |
| `B2` | λ above τ |
| `B3`, `B4`, `B6` | the fast path's first `PROVISIONAL_DEGRADATION` — **not** `SUSPECTED_CHANGE`, which is a one-tick excursion and would flatter the hybrid |
| `B5` | the earliest of the three accumulators, with the winning scale recorded |

### `B1` and `B2` have no attribution and no consequence output

CUSUM and a bare threshold emit a crossing. They do not attribute, they
produce no support state, and they drive no policy. Their evidence and
consequence metrics are therefore reported as **`N/A`** and never as zeros: a
zero would read as "no action conflicts", which is a claim about a policy
neither of them has.

Grids are iterated in **declaration order** and are never sorted, pruned or
interpolated. **Crossing time is not monotone in fault rate** — Phase 3.1
measured a conflict rate of 40, 40, 31, 0, 0 across a rising gain grid and
Phase 4 measured CSIA fastest at the *weakest* gain — so no grid point may be
skipped on a monotonicity assumption and every declared point is reported,
including points that detect nothing.

## 4. Baselines — measured separately before anything is combined

| id | baseline | what it is |
|---|---|---|
| `B0` | **current CSIA** | the frozen trust-persistence detector, exactly as Phase 4 ran it |
| `B1` | **CUSUM** | the repository's own `CusumBank`, `k = 0.5` fixed, `h` swept |
| `B2` | **bare threshold** | instantaneous λ > τ, no persistence |
| `B3` | **fast + current CSIA** | fast detector emits suspicion only; CSIA evaluates evidence validity, support and attribution with the **current** `SOURCE_INDICATORS` |
| `B4` | **fast + corrected support map** | as `B3`, with the FL-029 correction implemented **outside** the frozen core |
| `B5` | **multi-timescale CSIA** | fast, medium and slow accumulators, additive |
| `B6` | **full staged hybrid** | fast provisional detection → CSIA support analysis → capability output |

**No changes are combined before the individual ablations are measured.**
`B6` is reported only alongside `B3`, `B4` and `B5`, and any `B6` improvement
that is not present in the ablation that introduces it is reported as
unexplained.

## 5. Threshold grids, evaluated in full

| detector | grid | n |
|---|---|---|
| `B0` CSIA | θ = `[0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50, 0.40]` | 9 |
| `B1` CUSUM | h = `[50, 100, 200, 300, 500, 750, 1000]` | 7 |
| `B2` bare | τ = μ₀ + m·σ₀, m = `[4, 5, 6, 8, 10, 12]` | 6 |
| fast path | h_fast = `[10, 25, 50, 100, 200]` | 5 |

`μ₀, σ₀` are the frozen `IN_CONTROL["vibration"]` values and are not
re-estimated. The fast path's grid is swept on `development` and **one**
h_fast is frozen for `validation` and `locked`.

## 6. The fast path — what it may and may not say

The fast detector emits exactly one of:

```
NO_CHANGE
SUSPECTED_CHANGE
PROVISIONAL_DEGRADATION
```

It may **not** claim a specific fault identity, sensor attribution, safe
landing authority or actuator authority. Enforced by module structure, not
by convention: its return type carries no field in which any of those could
be expressed, and a test asserts the vocabulary is closed.

Every emission carries: timestamp, detector id, statistic value, threshold,
evidence source, freshness, provenance, detector state, and whether the alert
is provisional or confirmed.

## 7. The CSIA support output

The support layer exposes: active evidence, withdrawn evidence, gated
evidence, stale evidence, contradictory evidence, the hypothesis set, the
support status, the attribution status and provenance.

Support states are exactly:

```
IDENTIFIABLE
AMBIGUOUS
NON_IDENTIFIABLE
```

**A high confidence score without active support is never represented as a
supported fault attribution.** That is the invariant this layer exists to
enforce, and it is asserted by test rather than by prose.

The support classifier is a separate module from the fast detector and from
the capability layer, and imports neither.

## 8. The experimental FL-029 correction — shadow only

`csia/diagnosis/causal.py:50-59` maps each source to its indicator features.
For the two IMUs it lists:

```
"imu0": ("redundant_imu", "accel_motor_current"),
"imu1": ("redundant_imu", "accel_esc_rpm"),
```

It **omits** `velocity_gps_doppler_0` and `velocity_gps_doppler_1`, which the
frozen core declares at `csia/trust_graph/graph.py:42` and `:44`, keys
separately at `csia/runtime/online.py:207-208`, and **computes as live
evidence** at `csia/runtime/online.py:527-537`. So the trust engine isolates
on evidence the attribution model does not know it has. That is FL-029.

The corrected map adds, each with the source reference above:

| source | added indicator | declared at | computed at |
|---|---|---|---|
| `imu0` | `velocity_gps_doppler_0` | `graph.py:42` | `online.py:527-537` |
| `imu1` | `velocity_gps_doppler_1` | `graph.py:44` | `online.py:527-537` |

**This adds no new sensing and no new computation.** Both edges are already
computed every tick by the frozen core and then ignored by the attribution
map. The evidence budget of `B4` is therefore identical to `B3`'s, and the
report must say so rather than claiming an efficiency that is really a
bookkeeping fix.

Requirements, all asserted by test:

- the frozen core is unchanged — 12 of 12 digests still match;
- the current mapping remains available and is what `B3` uses;
- the corrected mapping is `B4` and lives outside the frozen core;
- every added indicator has a source reference;
- **every support claim corresponds to an actually active evidence edge** —
  a support claim resting on an edge whose gate is shut is a defect, not a
  result;
- no Phase-5 result is presented as a production-core result.

The comparison measures, for `B3` against `B4`: false refusals, unsupported
confident outputs, action conflicts, correct attribution, ambiguity, and
resolution coverage.

## 8a. The hybrid decision rule — and how it differs from P2

Phase 3.1 measured P2, the support-aware policy, producing **40 false
refusals and preventing 0 incorrect actionable decisions**: when the pair its
attribution discriminates was not identifiable, it withdrew to `ABSTAIN`. An
abstention is a refusal to give a wrong answer, and it is also a refusal to
give any answer.

The hybrid's rule is deliberately different, and it is fixed here:

1. Start from the frozen `FailsafePolicy` output (`p0_decide`), unmodified.
2. If the fast path reports `PROVISIONAL_DEGRADATION` and the frozen policy
   would issue nothing, issue **`CAUTION_GENERIC`** — a provisional,
   non-attributing response. This is the latency mechanism: act generically
   early, attribute later.
3. If the frozen policy issues an **attributing** response and the support
   layer does not report the discriminated pair `SUPPORTED`, **downgrade to
   `CAUTION_GENERIC` rather than to `ABSTAIN`.** The hybrid never refuses; it
   falls back to an action that asserts no attribution.
4. If support is `SUPPORTED`, the attributing response stands unchanged.

Step 3 is the whole H3 mechanism. A false refusal under P2 becomes a generic
caution under the hybrid, so the false-refusal rate should fall — and step 2
is the only place the hybrid may *add* an action, so that is where any
increase in false escalation would have to come from. Both are measured.

**The hybrid holds no actuator authority.** It names a response; a model
consumes it. No vehicle does.

## 9. Hypotheses

### H1 — Hybrid latency

> A fast-detector-plus-CSIA architecture has lower detection latency than
> current CSIA at matched observed false-alarm operating points.

**Supported if** at the primary matched operating point the candidate's
median detection delay is **at least 0.50 s lower** than `B0`'s *and* their
95 % bootstrap intervals do not overlap.
**Killed if** the candidate's median delay is not lower, or the difference is
below 0.50 s, or the intervals overlap.

### H2 — Assurance preservation

> The hybrid does not increase unsupported confident attribution, incorrect
> actionable decisions, action conflicts, or false escalation, relative to
> current CSIA.

A non-inferiority claim, so it gets a margin: **δ = 0.05** on each of the
four rates. **Supported if** for all four, the upper bound of the exact 95 %
interval on (candidate − `B0`) is **≤ 0.05**.
**Killed if** any of the four exceeds that margin.

### H3 — Support-map correction

> An experimental correction for FL-029 reduces false refusals without
> increasing unsupported confident outputs or action conflicts.

**Supported if** `B4`'s false-refusal rate is at least **0.20 lower** than
`B3`'s with exact two-sided McNemar `p < 0.05`, **and** unsupported confident
outputs and action conflicts are non-inferior at δ = 0.05.
**Killed if** the reduction is smaller, or not significant, or either
guard rate exceeds its margin.

### H4 — Multi-timescale detection

> A fast and slow evidence accumulator improves abrupt-fault latency without
> materially worsening gradual-fault detection.

**Supported if** median delay on `ABRUPT` falls by **≥ 0.50 s** and median
delay on `GRADUAL` rises by **≤ 0.50 s**, with the miss rate on `GRADUAL`
non-inferior at δ = 0.05.
**Killed if** abrupt latency does not improve by the margin, or gradual
latency worsens by more than it, or gradual misses rise past the margin.

### H5 — Threshold robustness

> The hybrid retains or improves the observed threshold robustness seen in
> Phase 4.

Measured as the **fraction of declared thresholds with observed
false-alarm rate 0 on the locked partition**. Phase 4 measured `B0` at 12/12
on its grid. **Supported if** the candidate's fraction is ≥ `B0`'s fraction
on this phase's grid.
**Killed if** it is lower.

### H6 — No dominance

> If no candidate dominates current CSIA on the declared system-level
> metrics, report `NO_HYBRID_DOMINANCE`.

**This is a real permitted outcome and not a failure of the study.** Tuning
stops when the declared grids are exhausted. There is no second round.

## 10. Matched operating points

Selected on `development` only, applied unchanged to `validation` and
`locked`.

1. For each detector and each threshold in its declared grid, compute the
   observed false-alarm rate over the development nominal runs.
2. For each target in `TARGET_FAR = [0.00, 0.05]`, select the threshold whose
   development rate is **≤ the target and closest to it**, ties broken by the
   more sensitive threshold. If none reaches a target the detector reports
   `NO_THRESHOLD_MEETS_TARGET` and is not compared there.
3. Apply unchanged to `locked` and report the locked rate alongside. A
   detector whose locked rate exceeds its development rate is **reported as
   such and not re-selected**.

**Primary comparison: `TARGET_FAR = 0.00`.** The second level is secondary
and carries no verdict. **A favourable threshold for one detector is never
compared with an unfavourable one for another**, and the full grid is
reported alongside the matched points.

Where the data permit, the comparison is also made at **matched observed miss
rate** and at **matched action-conflict rate**; where they do not, that is
reported rather than approximated.

## 11. Definitions

- **False alarm**: the detector is alarming at any time in
  `[SETTLE_S, 60.0]` on a **nominal** run, measured from the first alarm at
  or after `SETTLE_S` — not from the first alarm of the run, because a
  non-decreasing statistic crosses during settling and stays above
  (**FL-035**).
- **Detection**: on a faulted run, the first alarm at `t ≥ onset`. An alarm
  before onset on a faulted run is a **false alarm**, not a detection with
  negative delay (**FL-035**).
- **Delay**: `t_alarm − onset`, reported only for detections. Misses are
  **excluded from delay statistics and reported separately**, never imputed
  as the horizon.
- **False refusal**: a scenario in which the correct attribution was
  available and the policy declined to issue it because support was withdrawn.
- **Unsupported confident output**: a confident attribution issued while the
  evidence that separates it from its alternative is not active.
- **Action conflict**: the response class issued differs from the response
  class the model says was required.
- **Observed false-alarm rate**: a **finite-horizon count**, reported with
  its exact Clopper–Pearson interval. A zero count is **not** a zero
  probability and may never be reported as one.

## 12. Statistics

Exact and standard-library only. Clopper–Pearson 95 % for every rate; exact
two-sided McNemar for paired binary outcomes; exact conditional interval for
the paired risk difference, labelled conditional; fixed-seed percentile
bootstrap for delay quantiles, `B = 2000`, seed `20260921`, **input sorted
before resampling** (**FL-037**); no interval computed from fewer than 10
detections, the count reported instead.

## 13. Metrics reported

**Detector**: observed false alarms per nominal run; pre-onset alarms;
median, p90 and p99 delay; miss rate; delay by fault magnitude; delay by
onset; threshold robustness; finite-horizon intervals.

**Evidence**: supported-attribution rate; ambiguity rate; non-identifiable
rate; false-refusal rate; unsupported confident-output rate; correct and
incorrect attribution rate; evidence-loss latency; recovery latency.

**Operational consequence**: action-conflict rate; false escalation; missed
escalation; time to modeled safe state; position error; altitude error;
geofence margin; energy margin; capability-restriction duration.

**Implementation**: per-detector computation cost; total per-tick cost;
memory use; deterministic replay; behaviour under missing, stale, delayed
and correlated inputs.

Every consequence metric is **model-based** and carries the
`MODEL_BASED_ACTION_CONSEQUENCE` label. The model is
`csia_consequence/consequence_model.py` with its constants, and it is not a
vehicle.

## 14. Primary dominance criterion

A candidate may be called **dominant** only if, on `locked`, it:

1. has lower or equal median latency than `B0`;
2. has no worse observed false-alarm performance;
3. does not increase unsupported confident outputs;
4. does not increase action conflicts;
5. improves or preserves time to modeled safe state;
6. uses the same evidence budget, or clearly reports the added evidence.

Non-inferiority on 2, 3 and 4 uses the same δ = 0.05 margin as H2. If a
candidate improves only one metric, **that specific improvement is reported
and nothing more**.

Permitted verdicts, exactly:

```
HYBRID_DOMINATES_ON_DECLARED_SYSTEM_METRICS
HYBRID_IMPROVES_LATENCY_ONLY
HYBRID_IMPROVES_SUPPORT_ONLY
HYBRID_IMPROVES_ACTIONABILITY_ONLY
NO_HYBRID_DOMINANCE
INCONCLUSIVE
```

## 15. Stopping rule and multiplicity

Run every declared grid point on every seed, condition, shape, gain and
onset, **once**. No interim looks at `locked`, no extension, no threshold
added after a result is seen, no grid point dropped, no second tuning round.

Every operating point and every grid point is reported. **One primary
comparison** (`TARGET_FAR = 0.00`, `B6` against `B0`) carries any verdict;
all others are secondary and **no multiplicity correction is claimed** for
them.

## 16. What Phase 5 may not conclude

- No hardware, RF, HIL, SITL, flight, airworthiness or certification.
- No autopilot execution.
- **No claim that CSIA currently outperforms CUSUM.** Phase 4 measured the
  opposite on latency and that result stands.
- No universal detector superiority, in any direction.
- **No zero false-alarm probability.** Zero observed over a finite horizon is
  a count with an interval.
- No claim about P2's general safety or unsafety; FL-029 invalidated its
  support mapping and P2 remains exploratory.
- No universal prevalence.
- No novelty, unless independently established. CUSUM is Page (1954).
- No claim that the corrected support map is a production fix. It is a
  shadow module, and the production core is unchanged.
- No claim that threshold robustness compensates for a latency penalty.
