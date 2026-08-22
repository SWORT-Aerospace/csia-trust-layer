# Measurement spec: `q_gvalid` conditioned on hypothesis

**Purpose.** Convert every structural result in WP-C1 through WP-C5 into a risk
statement. The quantity is

```
q_gvalid | h  =  P( gvalid closed at a tick | hypothesis h is the true state )
```

and the one that matters is the ratio

```
R  =  q_gvalid | gps_fault   /   q_gvalid | nominal
```

This is the **single most important missing number in the programme**. It is
currently unmeasurable, and this document makes it executable the day data
lands.

**Status of the externally supplied figure.** A ratio of roughly 45:1
(P(Z=0 | GNSS_DEG) ≈ 0.90 against P(Z=0 | nominal) ≈ 0.02) has been quoted to
this programme. **It does not exist anywhere in this repository** — no emission
table, no closure-probability model, no measured rate. It is used in no
computation and must not be cited as ours. This measurement is what would
replace it with something we own.

---

## 1. Required telemetry, and what is plumbed today

`csia/runtime/ulog_source.py:165-188` reads `vehicle_gps_position` and uses
**only** latitude, longitude, altitude, NED velocity, and `fix_type >= 3` as
the validity predicate.

| Field | Needed for | Plumbed today? |
|---|---|---|
| `fix_type` | **the gate itself** — `gvalid` is `fix_type >= 3` | **YES** |
| timestamp | per-tick alignment | **YES** |
| `satellites_used` | discriminating denial from geometry loss | **NO** |
| `noise_per_ms` | carrier-to-noise proxy; jamming signature | **NO** |
| `jamming_indicator` | direct jamming flag where the receiver reports it | **NO** |
| `hdop` / `vdop` | geometry degradation without fix loss | **NO** |
| `vehicle_status.arming_state` | excluding pre-arm from the denominator | **YES** (`:217-225`) |

**Critical scoping consequence.** `fix_type` alone is enough to measure
`q_gvalid` itself, because the gate is a function of `fix_type` and nothing
else. The unplumbed fields are needed for the *labelling* problem in §2, not
for the gate trace. **The estimator is therefore runnable on today's ingestion
path if and only if the hypothesis label can be established another way.**

---

## 2. The labelling problem, stated before the estimator

`q_gvalid | h` conditions on the true hypothesis. The corpus is
**unannotated**: no log carries a ground-truth health label
(`docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md`, D-01). So the conditioning
variable does not exist in the data as it stands.

Three ways to obtain it, in decreasing order of strength:

| # | Source of the label | Strength | Cost |
|---|---|---|---|
| L1 | **Controlled injection.** Fly or SITL-fly with a GNSS jammer or simulator-injected denial at known times. The label is the injection schedule. | **Strongest.** True `h` known exactly. | Range time or a SITL campaign |
| L2 | **Independent annotation** of re-acquired logs by an operator using `satellites_used`, `noise_per_ms` and flight-mode history — which requires plumbing those fields first. | Medium. The annotation is a judgement, and it uses signals correlated with the gate. | Field plumbing + annotator time |
| L3 | **Unconditional `q_gvalid` only.** Measure P(gvalid closed) over the corpus with no conditioning. | **Weak, and it does not answer the question.** It bounds nothing about `R`. | Free today |

**L3 is not a substitute and must not be reported as one.** It would give a
marginal rate that mixes both hypotheses in unknown proportion. Report it, if
at all, as a descriptive corpus statistic and never as `q_gvalid | h`.

**Recommendation: L1.** It is the only route that gives a defensible label, and
it also gives the fault magnitudes and onset times needed to make the estimate
interpretable.

---

## 3. Estimator

**Unit of observation:** a tick, at the layer's 25 Hz cadence.

**Independence unit: the flight, not the tick.** Gate closure is strongly
autocorrelated within a flight — a denial event closes the gate for a
contiguous block of hundreds of ticks. Treating ticks as independent would
understate the interval by roughly the square root of the block length and is
the single most likely way to get this wrong.

Estimate per flight $j$ in condition $h$:

```
p_hj = (ticks with gvalid closed) / (monitored ticks)
```

where *monitored* excludes the arm window, consistent with the exposure
convention already used for the alert rate (`csia/metrics/exposure.py`).

Then aggregate across flights:

```
q_gvalid | h  =  mean_j ( p_hj )
```

with the flight as the resampling unit.

**Interval method: bootstrap over flights**, 10 000 resamples, BCa. Not a
binomial interval on tick counts, for the autocorrelation reason above. For
the ratio $R$, bootstrap the two arms jointly and report the percentile
interval of the ratio directly rather than dividing two intervals.

**Pre-registration.** Fix the arm window, the tick cadence, the monitored
definition, the resample count and the interval method **before** looking at
any outcome. This programme has already restated one published rate three
times; that will not be repeated here.

---

## 4. Cell counts first, inference second

**No inferential quantity may be computed until this table is produced and
reviewed.**

| Condition | Flights | Monitored ticks | Ticks with `gvalid` closed | Flights with ≥1 closure |
|---|---|---|---|---|
| `gps_fault` (injected) | | | | |
| `nominal` (clean) | | | | |

**Stopping rules, set in advance:**

- **Fewer than 5 flights in either arm:** report cell counts only. No point
  estimate, no interval.
- **Zero closures in the `nominal` arm:** the ratio is unbounded above. Report
  a one-sided lower bound on `R` and say plainly that the upper end is
  undetermined.
- **Zero closures in the `gps_fault` arm:** this is the outcome that would
  most change the programme. See §5.
- **All closures concentrated in one or two flights:** report the per-flight
  distribution, not just the mean. A ratio driven by one flight is a
  case study.

---

## 5. What each outcome would mean

| Outcome | Consequence for the structural results already in hand |
|---|---|
| **R large** (say ≥ 10) | The self-occlusion measurement is characteristic, not a corner case. `IRE = 0.037` becomes a live risk rather than a structural fact, and the GPS integrity relation (`gps_cn0_stats`, WP-C2) becomes a priority rather than an option. Nothing already reported changes; everything already reported gains weight. |
| **R near 1** | Real GNSS faults mostly leave the fix valid. **Arm A becomes the typical case and arm B a corner case.** The structural results all still hold — they are statements about what can happen — but their operational priority drops sharply, and the GPS integrity work should be reprioritised. This is the outcome that would most change the conclusions. |
| **R small** (< 1) | The gate closes *more* in healthy flight than under fault. Surprising, would suggest the fix-validity predicate is dominated by environment rather than by fault, and would call the `closes(gps_fault, gvalid) = TRUE` attribution in WP-C3 into question. **`S_eff` would need recomputing** and the reported gap could shrink to zero. |
| **`gvalid` never closes in either arm** | The gate is inert in practice, joining `speed_gate` and `temp_bias_scale`. The design-time and effective partitions coincide operationally, and the paper's central measurement would be a property of the simulator's denial model rather than of flight. **This would be the strongest refutation available** and is why the measurement must be run before the paper is submitted rather than after. |

Note the asymmetry: **three of the four outcomes weaken or complicate the
programme's current position, and one strengthens it.** That is the correct
shape for a measurement worth running.

---

## 6. Commands

**Today, on a network-permitted host, to get the corpus:**

```sh
python tools/fetch_real_logs.py --no-run      # 26 logs by UUID
python tools/build_dataset_manifest.py        # hash, dedup, classify
```

**Then, once L1 injection data exists** (the estimator itself does not yet
exist and is scoped, not written):

```sh
PYTHONPATH=. python research/wp_c5/measure_q_gvalid.py \
    --logs data/real_logs/'*.ulg' \
    --injection-schedule data/injection/schedule.json \
    --arm-time 20.0 --tick-hz 25 \
    --bootstrap 10000 --method bca \
    --out reports/wp_c5/q_gvalid.json
```

**Prerequisite work, in order:**

1. Plumb `satellites_used`, `noise_per_ms`, `jamming_indicator`, `hdop`,
   `vdop` in `ulog_source.py` (needed for L2, and for `gps_cn0_stats` later).
2. Run the L1 injection campaign, or accept L2 with its weaker label.
3. Write `research/wp_c5/measure_q_gvalid.py` against this spec.
4. Produce the §4 cell-count table and review it.
5. Only then compute `R`.

---

## 7. What this measurement still would not settle

- **Frequency is not severity.** A high `R` says the gate closes under fault;
  it does not say how often GNSS faults occur.
- **The simulator's denial model** invalidates the fix flag outright. Real
  degradation includes partial constellation loss and gradual carrier-to-noise
  decay that may leave `fix_type >= 3` set. L1 with a real jammer would capture
  this; SITL injection would not.
- **It says nothing about the other three gates.** `armed_gate` and
  `gps_warmup` are closed by nothing, and `speed_gate` has three undetermined
  cells that do not affect any partition. Those remain as they are.
