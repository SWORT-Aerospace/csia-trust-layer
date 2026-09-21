# Phase 4 results — detector performance

**Evidence level: `DETERMINISTIC_SIMULATION`.** Not SITL, not HIL, not bench
hardware, not flight. No autopilot executed anything. Nothing was armed,
nothing was commanded, nothing flew.

**Phase 4 measures detector performance and nothing else.** No action, no
policy, no failsafe level and no vehicle outcome appears in it. The
consequence question belongs to Phases 3, 3.1 and 3.2 and is **not** reopened
or pooled here — different seed partitions, different question, different unit
of analysis.

| item | value |
|---|---|
| preregistration | `PREREGISTRATION_PHASE4.md`, committed at `aee7fcc` before the locked partition was opened |
| development partition | 12 seeds, 252 runs — thresholds selected here and only here |
| locked partition | 40 seeds, **840 runs**, manifest `bbcaae73c2eee4a579e90723df8d1ea4…` |
| node | `vibration` (the one CUSUM-covered node that is also the Phase-3.2 primary arm) |
| fault | `vibration_anomaly`, gains 1.5–4.0, onsets 20/25/30/35 s, 20 s duration, **exhaustive not sampled** |
| replay | **three** independent locked passes, identical on every measured quantity |
| intake | 0 incomplete seeds, 0 empty declared cells, 0 refusals, on both partitions |

---

## THE HEADLINE, STATED AGAINST THE MECHANISM

**At the matched operating point — zero false alarms observed for all three —
CSIA trust persistence is about thirty times slower than both comparators on
this fault, and all three miss nothing.** This is a **tradeoff** result, not
a superiority result for any of the three.

| detector | threshold | dev FAR (obs.) | locked FAR (obs.) | miss rate | median delay | 95 % CI | p90 | p99 |
|---|---|---|---|---|---|---|---|---|
| **CSIA** trust-persistence | θ = 0.90 | 0.000 | **0.000** | **0.000** | **2.52 s** | [2.52, 2.52] | 2.76 s | 2.76 s |
| **CUSUM** (Page 1954) | h = 200 | 0.000 | **0.000** | **0.000** | **0.08 s** | [0.08, 0.08] | 0.12 s | 0.12 s |
| **BINST** bare threshold | τ = μ₀+10σ₀ | 0.000 | **0.000** | **0.000** | **0.08 s** | [0.08, 0.08] | 0.08 s | 0.08 s |

### Zero **observed** false alarms — and that is not a probability

**Zero false alarms were observed, over a finite horizon, and no claim of
zero false-alarm probability is made or implied.**

The false-alarm *rate* is measured over the **40 nominal runs**, not over all
840: a faulted run cannot contribute a false alarm after its onset. All three
selected thresholds give **0 / 40**, Clopper–Pearson 95 % CI
**[0.0, 0.0881]** — the upper bound is the honest content of a zero numerator.
Separately, all three raised **0 pre-onset alarms on the 800 faulted runs**,
so across the whole locked partition **no false alarm was observed at all**.

The total exposure over which that zero was observed is finite and small:

| source | runs | scored window per run | exposure |
|---|---|---|---|
| nominal runs | 40 | `SETTLE_S` → horizon, 50.0 s | 2 000 s |
| faulted runs, before onset | 800 | `SETTLE_S` → onset (10/15/20/25 s) | 14 000 s |
| **total** | | | **16 000 s ≈ 4.44 h** |

Four and a half hours of simulated flight with no false alarm is consistent
with a per-horizon false-alarm probability anywhere up to ~0.09 for each
detector. **It is not evidence of a zero rate**, and any figure quoted from
this table must carry its interval. Locked detections: 800/800 for all three.

**The matching handed CSIA its best threshold.** Every θ in the declared grid
has a development false-alarm rate of exactly 0.000, so the whole CSIA grid
was eligible at the primary target and the tie-break selected θ = 0.90 — the
*fastest* CSIA operating point on the grid, median 2.52 s against 7.00 s at
θ = 0.40. There is no CSIA threshold in the preregistered grid that would have
done better, and the comparison is not an artefact of an unfavourable choice.

**About 1.0 s of the 2.52 s is structural, not tuning.** `DWELL_TICKS = 25`
at 25 Hz is a one-second persistence requirement taken from
`FailsafeConfig.dwell_up` and not chosen for this study. A persistence
detector cannot alarm faster than its dwell. The remaining ~1.5 s is the
trust recursion falling below θ. Neither comparator has a persistence
requirement at all, so part of what this table measures is *persistence versus
none* — which is the honest reading, and it does not rescue the number.

### The simplest detector is not beaten here either

`BINST` is a bare instantaneous threshold on λ with no memory, included
because leaving it out would flatter both others. At μ₀+10σ₀ it detects every
one of the 800 faulted runs in 0.08 s with zero false alarms. **On this fault
the simplest thing that could work, works.** That is a property of *this
fault* — a large, abrupt, sustained step in exactly the statistic all three
detectors watch — and it is the easy case for an instantaneous threshold.
Phase 4 tested no drift, no incipient, no intermittent and no slow-onset
fault, and nothing here says what happens on one.

## WHERE CSIA IS AHEAD: THRESHOLD ROBUSTNESS, AND NOTHING ELSE MEASURED HERE

**CSIA is slower than both comparators at the matched operating point.** Its
one measured advantage in Phase 4 is that its false-alarm behaviour does not
depend on getting the threshold right.

**CSIA has a false-alarm rate of 0.000 across its entire declared grid**, from
θ = 0.90 down to θ = 0.20. Neither comparator does:

| detector | thresholds in grid | thresholds with locked FAR = 0 |
|---|---|---|
| CSIA | 12 | **12 of 12** |
| CUSUM | 10 | 5 of 10 |
| BINST | 8 | **1 of 8** |

At its *textbook* setting `h = 5`, CUSUM false-alarms on **100 %** of nominal
runs and raises pre-onset alarms on 795 of 800 faulted runs. That is not news
to this repository — `SEQUENTIAL_DETECTOR_SPEC.md` already records h = 5
producing 2681 clean alarm ticks under v1.1, and it is why the deployed `h` is
500. The bare threshold is worse still: seven of its eight grid points
false-alarm on at least half the nominal runs, and only the most extreme
(μ₀+10σ₀) is clean.

So the measured tradeoff is: **CSIA buys insensitivity to threshold
misspecification and pays about 2.4 s of delay for it.**

**No claim is made that threshold robustness compensates for the latency
penalty.** They are different quantities in different units — one is a
property of the grid, the other of the clock — and nothing measured here
converts between them. Whether 2.4 s of additional delay is worth tolerating
a badly chosen threshold is a question about a vehicle, an altitude, a
mission and a failure mode. Phase 4 does not answer it and no arithmetic in
this document should be read as answering it.

**And no claim of universal detector superiority is made, in any direction.**
On this fault, on this node, CSIA is slower than both comparators and the
bare threshold matches CUSUM. That ranking is a statement about one abrupt
sustained step in one statistic. A different fault — drift, incipient,
intermittent, multi-node — could reorder all three, and Phase 4 tested none
of them.

## H4 — **SUPPORTED**, direction stated

> H4: the trust-persistence detector has a measurable delay/false-alarm
> tradeoff against a matched CUSUM comparator.
> **Killed if** no operating point exists at which the two are comparable, or
> the curves are statistically indistinguishable across the whole grid.

Neither kill condition fires. A matched operating point with zero observed
false alarms exists for both, and the curves are not remotely
indistinguishable: 2.52 s against 0.08 s with non-overlapping bootstrap
intervals.

**H4 as written is direction-neutral, and it is supported as a TRADEOFF
result. It is not a CSIA superiority result and must not be cited as one.**
The direction is unfavourable to the mechanism on delay and favourable on
threshold robustness. The preregistration's binding constraint is honoured —
**no claim is made that CUSUM is inferior.** It is not: on this fault it is
thirty times faster at the same observed false-alarm rate, and it is a 1954
method used as the baseline it is.

---

## FULL GRID — LOCKED, ALL 30 DECLARED POINTS

Reported in **declaration order, never sorted**, including every point that
detects nothing. `pre` counts alarms raised on a *faulted* run before its
fault began; those are false alarms, not detections with negative delay.

(The JSON serializes its keys sorted, for stable diffs. The declared order is
the one in `grids`, and it is what the evaluator iterates — a test asserts
that `_thresholds` reads the grid and never sorts it.)

| point | locked FAR | miss rate | mean | median | p90 | p99 | pre-onset | detections |
|---|---|---|---|---|---|---|---|---|
| `CSIA` θ=0.90 | 0.000 | 0.000 | 2.500 | 2.52 | 2.76 | 2.76 | 0 | 800 |
| `CSIA` θ=0.85 | 0.000 | 0.000 | 3.249 | 3.36 | 3.684 | 3.72 | 0 | 800 |
| `CSIA` θ=0.80 | 0.000 | 0.000 | 3.912 | 3.96 | 4.56 | 4.72 | 0 | 800 |
| `CSIA` θ=0.75 | 0.000 | 0.000 | 4.442 | 4.56 | 5.184 | 5.48 | 0 | 800 |
| `CSIA` θ=0.70 | 0.000 | 0.000 | 4.841 | 5.00 | 5.812 | 6.04 | 0 | 800 |
| `CSIA` θ=0.65 | 0.000 | 0.000 | 5.165 | 5.34 | 6.28 | 6.44 | 0 | 800 |
| `CSIA` θ=0.60 | 0.000 | 0.000 | 5.455 | 5.66 | 6.60 | 6.76 | 0 | 800 |
| `CSIA` θ=0.55 | 0.000 | 0.000 | 5.740 | 5.94 | 6.88 | 7.08 | 0 | 800 |
| `CSIA` θ=0.50 | 0.000 | 0.000 | 6.043 | 6.22 | 7.16 | 7.36 | 0 | 800 |
| `CSIA` θ=0.40 | 0.000 | 0.000 | 6.903 | 7.00 | 7.80 | 8.00 | 0 | 800 |
| `CSIA` θ=0.30 | 0.000 | **0.254** | 21.160 | 21.16 | 21.16 | 21.16 | 0 | 597 |
| `CSIA` θ=0.20 | 0.000 | **0.999** | 21.600 | 21.60 | 21.60 | 21.60 | 0 | **1** |
| `CUSUM` h=5 | **1.000** | 0.000 | 0.050 | 0.08 | 0.08 | 0.08 | **795** | 800 |
| `CUSUM` h=10 | **1.000** | 0.000 | 0.056 | 0.08 | 0.08 | 0.08 | 765 | 800 |
| `CUSUM` h=25 | **1.000** | 0.000 | 0.069 | 0.08 | 0.08 | 0.08 | 660 | 800 |
| `CUSUM` h=50 | 0.775 | 0.000 | 0.076 | 0.08 | 0.08 | 0.08 | 355 | 800 |
| `CUSUM` h=100 | 0.075 | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 50 | 800 |
| `CUSUM` h=200 | 0.000 | 0.000 | 0.087 | 0.08 | 0.12 | 0.12 | 0 | 800 |
| `CUSUM` h=300 | 0.000 | 0.000 | 0.088 | 0.08 | 0.12 | 0.12 | 0 | 800 |
| `CUSUM` h=500 | 0.000 | 0.000 | 0.096 | 0.08 | 0.16 | 0.16 | 0 | 800 |
| `CUSUM` h=750 | 0.000 | 0.000 | 0.105 | 0.08 | 0.16 | 0.20 | 0 | 800 |
| `CUSUM` h=1000 | 0.000 | 0.000 | 0.113 | 0.08 | 0.20 | 0.20 | 0 | 800 |
| `BINST` μ₀+1σ₀ | **1.000** | 0.000 | 0.065 | 0.08 | 0.08 | 0.08 | **800** | 800 |
| `BINST` μ₀+2σ₀ | **1.000** | 0.000 | 0.077 | 0.08 | 0.08 | 0.08 | 790 | 800 |
| `BINST` μ₀+3σ₀ | **1.000** | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 710 | 800 |
| `BINST` μ₀+4σ₀ | **1.000** | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 585 | 800 |
| `BINST` μ₀+5σ₀ | 0.875 | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 340 | 800 |
| `BINST` μ₀+6σ₀ | 0.500 | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 165 | 800 |
| `BINST` μ₀+8σ₀ | 0.125 | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 80 | 800 |
| `BINST` μ₀+10σ₀ | 0.000 | 0.000 | 0.080 | 0.08 | 0.08 | 0.08 | 0 | 800 |

`CSIA` θ = 0.20 detected **1 of 800** faulted runs: trust on this node does not
fall that far on this fault. It is reported rather than dropped, because a
grid point that cannot detect is a fact about the detector.

## DELAY BY FAULT MAGNITUDE — AND IT IS NOT MONOTONE

At the primary matched point, medians over 160 locked runs per gain:

| gain | CSIA θ=0.90 | CUSUM h=200 | BINST μ₀+10σ₀ |
|---|---|---|---|
| 1.5 | **2.26 s** | 0.12 s | 0.08 s |
| 2.0 | 2.54 s | 0.08 s | 0.08 s |
| 2.5 | 2.60 s | 0.08 s | 0.08 s |
| 3.0 | 2.60 s | 0.08 s | 0.08 s |
| 4.0 | 2.60 s | 0.08 s | 0.08 s |

**CSIA is fastest on the *weakest* fault**, and its delay rises and then flattens
as the fault gets stronger. The preregistration stated in advance that crossing
time is non-monotone in fault rate and forbade sorting, pruning or
interpolating the grid on a monotonicity assumption; this is that
non-monotonicity showing up in the delay itself. Miss rate is 0.000 at every
gain for all three detectors, so the effect is in the timing and not in
detectability. **No mechanism is asserted for it here** — Phase 4 measured it
and did not explain it.

CUSUM shows the ordinary direction weakly (0.12 s at gain 1.5, 0.08 s above),
and the bare threshold is flat at the tick resolution.

## DELAY BY ONSET TIME

| onset | CSIA θ=0.90 | CUSUM h=200 | BINST μ₀+10σ₀ |
|---|---|---|---|
| 20 s | 2.36 s | 0.08 s | 0.08 s |
| 25 s | 2.52 s | 0.08 s | 0.08 s |
| 30 s | 2.68 s | 0.08 s | 0.08 s |
| 35 s | 2.76 s | 0.08 s | 0.08 s |

CSIA's delay grows monotonically with onset time across the declared set;
the memoryless comparators are flat. Onsets were **exhaustive, not sampled** —
every seed ran every onset — so this is the whole declared set and not a
subsample of it.

## SECONDARY OPERATING POINTS, WHICH CARRY NO VERDICT

`TARGET_FAR = 0.05` selects exactly the same three thresholds as the primary
target, because no threshold has a development FAR strictly between 0 and
0.05 on any detector.

At `TARGET_FAR = 0.10`, the bare threshold moves to μ₀+8σ₀ (development FAR
0.083) and its **locked FAR comes out at 0.125 — higher than the development
FAR it was selected on.** The preregistration says such a point is reported as
such and the operating point is **not re-selected**, and it was not. CSIA and
CUSUM do not move.

## COMPUTATIONAL COST

Wall clock on this container, **environment-specific and not portable**. Each
detector's figure covers its *full declared threshold grid* on one flight —
12 thresholds for CSIA, 10 for CUSUM, 8 for the bare threshold — so the
per-threshold column is the comparable one. The series build (sensor models,
prediction comparator, trust engine) is **shared by all three** and is
reported on its own line rather than charged to any one of them.

Over the 840 locked runs, 1 260 000 ticks:

| component | ns / run | ns / tick | ns / tick / threshold | thresholds |
|---|---|---|---|---|
| **series build (shared)** | 191 536 630 | **127 691.1** | — | — |
| `CSIA` full grid | 2 289 607 | 1 526.4 | **127.2** | 12 |
| `CUSUM` full grid | 1 701 897 | 1 134.6 | **113.5** | 10 |
| `BINST` full grid | 486 755 | 324.5 | **40.6** | 8 |
| total | 196 014 888 | 130 676.6 | — | — |

**The shared series build is about 84× the cost of all three detectors
combined.** On this implementation the choice of detector is not where the
cycles go, and a delay figure of 2.52 s against 0.08 s is not explained by
anything in this table.

Per threshold per tick the three are within a factor of three of each other,
which is a statement about **these implementations** and not about the
algorithms: `CSIA` and `CUSUM` run a Python loop over ticks while `BINST` is
a vectorised NumPy comparison, so the ratios reflect interpreter overhead at
least as much as arithmetic. Phase 5 would port the CUSUM to `float S[N]`
with one add, one max and one compare per node per tick; none of these
numbers predicts what that costs.

---

## MUTATION — 17 EVALUATED, 17 KILLED, 0 SURVIVED

**17 evaluated, 17 killed, 0 survived**, in 811 s. A score
without the conditions that produced it is worthless, so the conditions are
stated first and a test asserts them:

| integrity condition | required | observed |
|---|---|---|
| unmutated baseline passes in the sandbox | exit 0 | **exit 0**, 96 s |
| canary mutant dies | killed | **KILLED** — `test_a_detector_that_cannot_meet_a_target_is_reported_not_dropped` |
| kills attributed to a **test node** | all | **17 of 17** |
| kills attributed to a **bare file** (collection error, missing artifact) | none | **0** |
| invalid mutants (anchor not found) | reported, not scored | **0** |
| timeouts scored as kills | never | **0** — no mutant ran past 100 s against a 3600 s limit |

**This is a fourth, separate runner.** `run_e2m_mutations.py` (38/36/2),
`run_phase31_mutations.py` (11/8/3) and `run_phase32_mutations.py` (12/12/0)
are untouched, so none of the five survivors in the first two can be killed
as a side effect of widening this selection. Verified: all three result files
are byte-identical to their state at `5208624`.

Two tests are **deselected**, and neither deselection is a convenience. A
sha256 manifest guard fails for every mutant because mutating a file changes
its hash — including it manufactures a perfect score, which is exactly what
happened on the first Phase-3.2 attempt (**FL-033**). And a test that pins
this run's own score cannot sit inside the selection that run measures.

### Every mutant

| id | family | target | what it breaks | first failing test node | result |
|---|---|---|---|---|---|
| `4-01` | PREREG | `evaluate4.py` | moves the primary comparison off the zero-false-alarm point | `test_phase4_pipeline.py` ::<br>`test_build_reproduces_the_sealed_result_from_the_committed_…` | **KILLED** |
| `4-02` | PREREG | `evaluate4.py` | admits thresholds whose development FAR exceeds the target | `test_phase4_pipeline.py` ::<br>`test_build_reproduces_the_sealed_result_from_the_committed_…` | **KILLED** |
| `4-03` | PREREG | `evaluate4.py` | selects thresholds on the LOCKED partition instead of development | `test_phase4_pipeline.py` ::<br>`test_build_reproduces_the_sealed_result_from_the_committed_…` | **KILLED** |
| `4-04` | PREREG | `evaluate4.py` | sorts the declared threshold grid | `test_phase4_detectors.py` ::<br>`test_the_grid_is_read_in_declaration_order` | **KILLED** |
| `4-05` | PREREG | `campaign4.py` | prunes the onset grid to a single onset | `test_phase4_pipeline.py` ::<br>`test_the_campaign_runs_every_onset_for_every_gain_on_a_real…` | **KILLED** |
| `4-06` | DEFINITION | `evaluate4.py` | scores a latched detector as clean (the FL-035 false-alarm defect) | `test_phase4_detectors.py` ::<br>`test_a_latched_alarm_from_the_settling_window_is_a_false_alarm` | **KILLED** |
| `4-07` | DEFINITION | `evaluate4.py` | scores a pre-onset alarm as a detection (the FL-035 delay defect) | `test_phase4_detectors.py` ::<br>`test_a_pre_onset_alarm_is_not_a_detection_with_negative_delay` | **KILLED** |
| `4-08` | DEFINITION | `evaluate4.py` | reports every detector as never missing | `test_phase4_detectors.py` ::<br>`test_a_miss_is_reported_and_never_imputed_as_the_horizon` | **KILLED** |
| `4-09` | DEFINITION | `evaluate4.py` | hides pre-onset alarms on faulted runs | `test_phase4_detectors.py` ::<br>`test_a_pre_onset_alarm_is_not_a_detection_with_negative_delay` | **KILLED** |
| `4-10` | STATS | `evaluate4.py` | pins every lower confidence bound at zero | `test_phase4_detectors.py` ::<br>`test_clopper_pearson_matches_the_exact_interval` | **KILLED** |
| `4-11` | STATS | `evaluate4.py` | changes the declared quantile definition | `test_phase4_detectors.py` ::<br>`test_the_quantile_is_the_declared_interpolation[values1-0.5…` | **KILLED** |
| `4-12` | STATS | `evaluate4.py` | computes a bootstrap interval from too few detections | `test_phase4_detectors.py` ::<br>`test_no_interval_is_computed_from_too_few_detections` | **KILLED** |
| `4-13` | STATS | `evaluate4.py` | unpins the bootstrap seed | `test_phase4_pipeline.py` ::<br>`test_build_reproduces_the_sealed_result_from_the_committed_…` | **KILLED** |
| `4-14` | CAMPAIGN | `campaign4.py` | removes the persistence requirement, which IS the CSIA detector | `test_phase4_pipeline.py` ::<br>`test_the_settling_window_and_dwell_come_from_the_frozen_fai…` | **KILLED** |
| `4-15` | CAMPAIGN | `campaign4.py` | counts gated-off ticks as evidence for CSIA | `test_phase4_pipeline.py` ::<br>`test_gated_ticks_are_not_evidence_for_the_csia_detector` | **KILLED** |
| `4-16` | CAMPAIGN | `campaign4.py` | feeds the CUSUM gated-off ticks as live evidence | `test_phase4_pipeline.py` ::<br>`test_gated_ticks_are_not_evidence_for_the_cusum_baseline` | **KILLED** |
| `4-17` | CAMPAIGN | `campaign4.py` | removes the settling window | `test_phase4_pipeline.py` ::<br>`test_the_settling_window_and_dwell_come_from_the_frozen_fai…` | **KILLED** |

### The four kills that landed on the end-to-end test

`test_build_reproduces_the_sealed_result_from_the_committed_runs` is a
genuine behavioural test — it re-derives the sealed result from the committed
runs — but it is also a **catch-all**: it fails for any change to the
evaluator's output, so it does not by itself show that the specific property
is tested. Each of those four mutants was therefore re-applied by hand and
run against its own targeted test alone:

| mutant | targeted test run in isolation | result |
|---|---|---|
| `4-01` | `test_the_primary_target_is_the_zero_false_alarm_point` | FAILED |
| `4-02` | `test_thresholds_selected_on_locked_instead_of_development_change_the_verdict` | FAILED |
| `4-03` | `test_thresholds_selected_on_locked_instead_of_development_change_the_verdict` | FAILED |
| `4-13` | `test_the_bootstrap_is_reproducible_from_the_committed_seed` | FAILED |

All four fail their specific test, so the properties are genuinely covered
and not merely disturbed. `4-03` was additionally verified in both
directions: the cherry-pick canary fails under it and passes unmutated.

**No mutant survived, so there is no survivor to report.** That is stated
plainly rather than dressed up: 17 is a small mutant set aimed at the
scoring rules, the matching rule and the gating, and a clean sweep over 17
hand-written mutants is weaker evidence than a clean sweep over a generated
set would be. The three surviving Phase-3.1 mutants and the two surviving
E2M mutants remain alive and remain reported.

## POST-LOCK ANALYSIS — SEPARATE FROM THE PREREGISTERED VERDICT

**Everything in this section happened after the locked partition was opened.
None of it is part of the preregistered verdict**, which is the matched
comparison at `TARGET_FAR = 0.00` reported above, computed under the
definitions frozen in `PREREGISTRATION_PHASE4.md`.

The preregistration froze the detectors, the grids, the partitions, the fault
and onset sets, the horizon, every definition, the matching procedure, the
intervals, the stopping rule and the multiplicity treatment. `campaign4.py`
and `evaluate4.py` were nonetheless edited after the locked run existed, so
here is the complete list and what each did to the published numbers. A
referee should not have to reconstruct this from a diff.

| change | why | effect on reported numbers |
|---|---|---|
| `validate()` extended to classify incomplete seeds and empty declared cells, and to refuse nominal-with-fault, faulted-without-onset and off-grid runs | the FL-032 lesson: an analysis pipeline that never rejects anything has never been tested | **none.** Both partitions pass clean: 0 incomplete seeds, 0 empty cells, 0 refusals |
| per-detector wall-clock instrumentation in `run_one`, and `environment_specific_fields` declared | the preregistration promised cost *per detector*; the campaign was only recording the shared series build | **none on any measurement.** Verified directly: alarm times, tick counts, `cusum_max`, `trust_min` and `active_ticks` are identical across all 840 runs before and after the instrumentation |
| `bootstrap_ci` sorts its input before resampling (**FL-037**) — **post-lock correction** | it resampled by index, so the interval depended on the order runs sat in the file rather than on the data | **five numbers**, all lower endpoints of p90 bootstrap intervals, all by ≤ 0.001 s. No point estimate, no matched threshold, no rate, no Clopper–Pearson interval and no verdict moved |
| per-detector cost block added to the result document | reporting a preregistered quantity that was being computed but not surfaced | purely additive |

**Nothing in that list is a detector, a threshold, a grid, a definition, the
matching rule or a verdict**, and the preregistration and the seed partitions
were not touched at all — `git diff` on both is empty. The FL-037 row is the
one that changed published values after the locked open, which is the thing
preregistration exists to prevent; it is recorded at full weight rather than
folded into a "minor corrections" sentence.

**The locked campaign was never re-run with changed scoring or changed
thresholds.** The 840 runs behind every number in this document are the ones
produced by the first opening of the locked partition; the only regeneration
was to add the per-detector timing fields, and that was verified inert on
every alarm time, tick count, `cusum_max`, `trust_min` and `active_ticks`
across all 840 runs. Had any correction changed a matched threshold or a
verdict, it would appear here as a **post-lock analysis** alongside the
preregistered result, not in place of it.

## WHAT PHASE 4 ESTABLISHES

1. A matched operating point with **zero observed false alarms** exists for
   all three detectors, and at it **CSIA is ~31× slower than CUSUM and the
   bare threshold** on this fault, with all three missing nothing.
   **H4 is supported as a TRADEOFF result. It is not a CSIA superiority
   result**, and the preregistration's bar on claiming CUSUM inferior stands
   — the measurement would not have supported that claim in any case.
2. **CSIA's observed false-alarm rate is 0/40 at every one of its twelve
   declared thresholds**; CUSUM's at 5 of 10 and the bare threshold's at 1
   of 8. This is the one measured CSIA advantage in Phase 4, and it is
   threshold robustness, not detection performance.
3. CSIA's delay is **non-monotone in fault magnitude** and monotone in onset
   time.
4. Two of CSIA's twelve grid points cannot detect this fault reliably
   (θ = 0.30 misses 25.4 %, θ = 0.20 misses 99.9 %).
5. **Three** independent locked passes agree on every measured quantity —
   all 840 runs, all three detectors, every declared threshold, all three
   alarm times — differing only in the wall-clock fields the campaign
   declares as environment-specific.

## WHAT PHASE 4 DOES NOT ESTABLISH

- **Nothing about hardware, RF, arming, actuators, flight, SITL, HIL,
  airworthiness or certification.** None of it was touched.
- **No autopilot executed anything.**
- **Nothing about consequence.** No action, no policy, no failsafe level, no
  vehicle outcome is in any Phase-4 artifact. Phase 4 is **not pooled** with
  Phase 3, 3.1 or 3.2, whose results stand exactly as recorded.
- **Nothing about the Phase-3.2 result applying to aircraft that report ESC
  telemetry.** Phase 3.2 is precisely a statement about one that does not, and
  Phase 4 does not touch that question.
- **Nothing about P2**, which does not appear in Phase 4 at all, and so
  nothing about its general safety or unsafety.
- **No novelty.** CUSUM is Page (1954), named as prior art in the module
  Phase 4 imports. Nothing here establishes novelty for anything else either.
- **No claim that RAIM proves the CSIA mechanism.** RAIM is a design analogy
  and nothing measured here bears on it.
- **Nothing about other faults.** One node, one fault family, one airframe
  profile, one trajectory, in simulation. No drift, no incipient, no
  intermittent, no multi-node fault was tested, and the case that was tested —
  a large abrupt sustained step — is the easy case for the memoryless
  comparators that won it.
- **No prevalence**, in either autopilot or anywhere else.
- **No zero false-alarm PROBABILITY.** Zero was *observed*, over 16 000 s of
  simulated flight, with a 95 % upper bound of 0.0881 per horizon for each
  detector. A zero count is not a zero rate.
- **No claim that threshold robustness compensates for the latency
  penalty.** Phase 4 measured both and converts between neither.
- **No universal detector superiority**, for CSIA, CUSUM or the bare
  threshold. The ranking here belongs to this fault on this node.

## Provenance

- preregistration `PREREGISTRATION_PHASE4.md`, frozen before the locked
  partition was opened
- `results/PHASE4_RUNS_DEVELOPMENT.json`, `results/PHASE4_RUNS_LOCKED.json`,
  `results/PHASE4_RESULTS_LOCKED.json`, `results/PHASE4_MUTATION_RESULTS.json`
- reproduction: `REPRODUCE4.md`; manifest: `SHA256_MANIFEST4.json`
- **three defects are on the record, and one of them was found late.**
  **FL-035** — two scoring defects found on *development* data before the
  locked partition was opened; the second changed the matched thresholds.
  **FL-036** — the reproduction check was a byte-identity comparison of a
  document that deliberately carries wall-clock timing, so it could never
  pass; the timing field was kept and the check was fixed.
  **FL-037** — the bootstrap resampled by index, so the reported interval
  depended on the order runs sat in the file. **This one was found after the
  locked partition was opened**, by the test that shuffles the committed runs
  and asserts nothing moves. It moved five numbers in the whole document, all
  lower endpoints of p90 intervals, all by ≤ 0.001 s; no point estimate, no
  matched threshold and no verdict changed. It is recorded at full weight
  anyway, because "it turned out not to matter" is a fact about this dataset
  and not about the defect.
