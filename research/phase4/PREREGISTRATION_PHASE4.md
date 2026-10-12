# Phase 4 preregistration — detector performance

**Written and committed before the Phase-4 `locked` partition is opened.**
Detectors, threshold grids, partitions, fault grid, onset set, horizon, every
definition, the matching procedure, the intervals, the stopping rule and the
multiplicity treatment are frozen at this commit and may not change after
locked results are inspected.

**Phase 4 measures detector performance. It measures no consequence.** No
action, no policy, no failsafe level and no vehicle outcome appears in it.
The consequence question was Phases 3, 3.1 and 3.2 and is not reopened.

**Scope: deterministic simulation.** No hardware, no RF, no armed vehicle, no
actuator, no flight, no SITL, no autopilot execution.

---

## 1. Measured starting state

| item | value |
|---|---|
| HEAD | `5208624` plus the Part-A FL-032 work |
| Phase-3.2 preregistration freeze | `e95c616ce9543af5f62fa5f1a5e8f94a7d5e33ae` |
| frozen core | 12 of 12 match `docs/v1/FROZEN_BASELINE.json` |
| Phase-3.2 locked result | sealed, sha256 `2f58a6ae415ecccfdc4a3b4c331d0cab4c42954464eaf155ed23beaa6f20d2c6`, byte-identical |

**No Phase-4 result is pooled with any consequence phase.** Different
partitions, different question, different unit of analysis.

## 2. Detectors

All three run on the **same series**, from the frozen batch pipeline, on the
**`vibration` node**. The node is not a free choice: the CUSUM bank's frozen
in-control statistics cover `gps`, `mag`, `battery`, `motor_esc` and
`vibration` and **explicitly do not cover `imu0` or `imu1`**, which its own
module docstring records as a coverage fact. `vibration` is the one covered
node that is also the subject of the Phase-3.2 primary arm.

| id | detector | statistic | threshold |
|---|---|---|---|
| `CSIA` | trust-persistence | `hist.trust[:, col("vibration")]` | alarm when trust < θ for `DWELL_TICKS` consecutive ticks |
| `CUSUM` | Page's one-sided CUSUM | `csia.v1_1.sequential.CusumBank` on the smoothed pre-transform λ | alarm when S > h |
| `BINST` | instantaneous λ threshold | the same λ, no persistence | alarm when λ > τ |

**CUSUM is not a straw man.** It is the repository's existing implementation,
with `k = 0.5` fixed at its textbook value and its in-control statistics
frozen from the clean arm — `IN_CONTROL["vibration"] = (0.025427388135084314,
0.013755742784080371)`. Only `h` is swept, which is the parameter a CUSUM is
meant to be operated at. `BINST` is the simple baseline and is expected to be
poor; it is included because leaving it out would flatter both others.

`DWELL_TICKS = 25` (1.0 s at 25 Hz), taken from `FailsafeConfig.dwell_up`
rather than chosen.

Gating: a tick with `gate <= GATE_EPS` is **not evidence** and is skipped by
all three detectors, exactly as the frozen runtime skips it.

## 3. Threshold grids, evaluated in full

Declared lists, iterated in declaration order. **Never sorted, pruned,
interpolated or shortened.**

```
CSIA  θ ∈ [0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.40, 0.30, 0.20]
CUSUM h ∈ [5, 10, 25, 50, 100, 200, 300, 500, 750, 1000]
BINST τ = mu0 + m*sigma0,  m ∈ [1, 2, 3, 4, 5, 6, 8, 10]
```

## 4. Non-monotonicity, stated explicitly

**Crossing time is non-monotone in fault rate.** Phase 3.2 measured it on its
locked partition: under the matched control, time to `CAUTION` fell 50.215 →
35.168 → 31.395 → 26.885 s as the IMU fault rate rose 0.03 → 0.12, and then
**rose again to 34.752 s at 0.18**; and the conflict rate went 40, 40, 31,
**0, 0** across the same grid.

Therefore Phase 4:

- evaluates **every** declared grid point and reports every one, including
  non-detections and failures;
- **never** interpolates between grid points;
- **never** sorts or prunes the fault-magnitude grid, and never stops early
  at a "sufficient" magnitude;
- does not fit, assume or report a monotone delay-versus-magnitude curve.

## 5. Partitions

`csia_consequence/phase4_partitions.py`, domain
`csia/detector_performance_phase4/2026-09-20`, disjoint from every earlier
partition including all three consequence phases.

| partition | seeds | use |
|---|---|---|
| `development` | 12 | **threshold tuning and operating-point matching. The only partition thresholds may be chosen on.** |
| `validation` | 16 | a rehearsal of the frozen design |
| `locked` | 40 | sealed; the final curves are evaluated here and nothing is tuned afterwards |

Manifest hash: `bbcaae73c2eee4a579e90723df8d1ea48dcc4e201fb0fd3a2072499d4cdd3174`

## 6. Scenarios

- **Flight**: `hover_circle`, 60.0 s, 25 Hz, 1500 ticks. Seeds vary sensor
  noise only; `generate_flight` is scripted and its seed has no effect, by
  its own docstring.
- **Nominal runs**: one per seed, no fault. These and only these define the
  false-alarm rate.
- **Faulted runs**: `vibration_anomaly` on the `vibration` node, at every
  combination of

```
gain  ∈ [1.5, 2.0, 2.5, 3.0, 4.0]          (Phase 3.2's declared grid)
onset ∈ [20.0, 25.0, 30.0, 35.0] s          duration 20.0 s
```

  **The onset set is enumerated exhaustively, not sampled.** Every seed runs
  every (gain, onset) pair, so delay-by-onset is a complete factorial and not
  a marginal over an unstated distribution.

## 7. Definitions

- **Horizon**: the flight, `[0, 60.0] s`. Alarms are only counted after a
  settling window `SETTLE_S = 10.0 s`, which covers calibration and trust
  convergence and is taken from `FailsafeConfig.arm_time`.
- **False alarm**: the detector is **alarming at any time** in
  `[SETTLE_S, 60.0]` on a **nominal** run. Measured from the first alarm at
  or after `SETTLE_S`, **not** from the first alarm of the run: the CUSUM
  statistic is non-decreasing while a drift persists, so a low `h` crosses
  during the settling window and stays above it for the rest of the flight.
  Counting only the first alarm would score that as clean. Reported as
  **false alarms per horizon** — a run either has one or does not, so the
  rate is per 50 s of flight.
- **Detection**: on a faulted run, the first alarm at `t ≥ onset`.
- **Pre-onset alarm on a faulted run**: an alarm before the onset is a
  **false alarm**, not a detection with negative delay. Both the first alarm
  of the run and the first alarm at or after onset are recorded per
  threshold, and the detection uses the latter. (Found on a development
  probe: CUSUM at `h = 5` fires at 4.92 s on a run whose fault starts at
  30 s.)
- **Persistence latching**: the CSIA detector alarms at the tick its
  run-length condition is met and its counter then resets, so a later
  episode is a separate alarm rather than a continuation.
- **Missed detection**: no alarm in `[onset, 60.0]` on a faulted run.
- **Delay**: `t_alarm − onset`, in seconds, reported only for detections.
  Missed detections are **excluded from delay statistics and reported
  separately as a miss rate**; they are never imputed as the horizon.

## 8. Matched false-alarm operating points

Thresholds are chosen **on `development` only**.

1. For each detector and each threshold in its declared grid, compute the
   false-alarm rate over the development nominal runs.
2. For each target level in `TARGET_FAR = [0.00, 0.05, 0.10]` false alarms per
   horizon, select for each detector the threshold whose development FAR
   is **≤ the target and closest to it**, breaking ties by the more sensitive
   threshold. If no threshold reaches a target, that detector reports
   `NO_THRESHOLD_MEETS_TARGET` at that level and is not compared there.
3. The selected thresholds are then applied unchanged to `locked`, and the
   **locked** FAR is reported alongside the development FAR. A detector
   whose locked FAR exceeds its development FAR is reported as such; the
   operating point is not re-selected.

**A favourable threshold for one detector may not be compared with an
unfavourable threshold for another.** The matching above is the only
comparison permitted, and every full curve is reported so a reader can see
the whole grid rather than the matched points alone.

**Primary comparison: `TARGET_FAR = 0.00`** — the zero-false-alarm operating
point, which is the rule the repository's own CUSUM `h` was selected under.
The other two levels are secondary and carry no verdict.

## 9. Reported per detector and per operating point

False alarms per horizon; average delay; median delay; 90th percentile delay;
99th percentile delay; miss rate; delay by fault magnitude; delay by onset
time; the matched operating-point comparison; confidence intervals; and
computational cost where measured.

**Intervals.** Clopper–Pearson 95 % exact for every rate (false-alarm rate,
miss rate). For delay quantiles, a percentile bootstrap with `B = 2000`
resamples at a fixed declared seed, reported as a 95 % interval; when fewer
than 10 detections exist at an operating point the interval is **not
computed** and the count is reported instead.

**Computational cost** is measured as wall-clock nanoseconds per tick per
detector over the locked campaign, on this container, and is labelled as an
environment-specific figure and not a portable one.

## 10. Stopping rule and multiplicity

Run every declared grid point on every seed, onset and gain, once.
**No interim looks, no extension, no threshold added after a result is seen,
no grid point dropped.**

Every operating point and every grid point is reported. **One primary
comparison** (`TARGET_FAR = 0.00`) carries any verdict; all others are
secondary and **no multiplicity correction is claimed** for them.

## 11. What Phase 4 may not conclude

No hardware validation. No flight validation. No autopilot execution. No
universal prevalence. No airworthiness. No certification. **No claim that the
Phase-3.2 result applies to aircraft that report ESC telemetry** — it is
precisely a statement about one that does not. **No claim about P2's general
safety**; P2 does not appear in Phase 4 at all. **No claim that RAIM proves the CSIA mechanism**; RAIM is a design
analogy and nothing here bears on it.
**No novelty claim** — CUSUM is Page (1954), stated as prior art in the
module Phase 4 imports, and nothing in Phase 4 establishes novelty for
anything else either.

A detector being faster at a matched false-alarm rate is a statement about
these three detectors, on one node, one fault family, one airframe profile,
one trajectory, in simulation.
