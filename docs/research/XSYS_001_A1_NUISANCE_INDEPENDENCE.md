# XSYS-001-A1 — pre-data amendment: independence of the nuisance conditions

**Status: FROZEN — NOT ACCEPTED FOR EXECUTION.** This is a formal pre-data
amendment of `docs/research/XSYS_001_PREREGISTRATION.md`.

- It changes only the nuisance-generation mechanism.
- It was frozen before any confirmatory flight and before any confirmatory
  outcome existed.
- Its own acceptance rule was frozen before it was applied. That rule
  failed one criterion (C4, §7), so the amended executor refuses to fly.
- A further amendment is required before any confirmatory run.

| | |
|---|---|
| amends | XSYS-001, manifest `research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json`, SHA-256 `868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b` (unchanged) |
| amendment manifest | `research/xsys_confirmatory_001/amendment_a1/FREEZE_MANIFEST_A1.json`. Its SHA-256 is in `research/xsys_confirmatory_001/amendment_a1/FREEZE_MANIFEST_A1.sha256` and `tests/test_xsys_001_a1_amendment.py`; this file is one of the files it hashes |
| machine-readable | `research/xsys_confirmatory_001/amendment_a1/A1_CONFIG.json` |
| diagnostics frozen before use | `research/xsys_confirmatory_001/amendment_a1/independence/DIAGNOSTIC_SPEC.json`, committed and pushed as `d47f339` before any new pilot flew |
| authorization | `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` §9: nominal-only pilots and this amendment; no confirmatory flight |
| confirmatory flights / analysis trials | **0 / 0** |

## 1. Why, when, what

**Why.** XSYS-001 made the nuisance condition its independent statistical
unit. It stated that this independence was "by design, not verified", and
its analysis spans overlapped in simulated time. This amendment
investigated the assumption. It is **false** for the XSYS-001 design (§3).

**When.** On 2026-09-27, after the XSYS-001 freeze (`3c83931`) and before
any confirmatory flight or outcome. The steps, in order:

1. source trace;
2. diagnostic spec committed (`d47f339`);
3. existing-data analysis;
4. nominal-only pilots Q1 to Q5;
5. design check;
6. this freeze.

**What changed** (nuisance generation only):

| item | XSYS-001 | XSYS-001-A1 |
|---|---|---|
| condition | (heading_j, onset_j) | (heading_j, noise segment slot_j) |
| arm time | 10 s for every flight | 10 s + 25 s × slot_j (a pre-arm dwell on the ground) |
| onset | 30.0 + 0.5 × rank_j s (20–25 s after arm) | arm_j + 20 s for every flight (the apparatus timeline) |
| analysis spans | overlap in simulated time | disjoint segments of the one noise stream, at least 25 s apart |
| heading | 360 j / 11° | **unchanged** |
| seed / realization id | none | none exists in PX4 SIH; the realization identifier is the noise segment `SEG00`–`SEG10` |
| matrix | `prereg/FLIGHT_MATRIX.csv`, `prereg/ANALYSIS_MATRIX.csv` | `amendment_a1/FLIGHT_MATRIX_A1.csv`, `amendment_a1/ANALYSIS_MATRIX_A1.csv` (ids `XS1A1-…`) |
| order | seed `XSYS-001/2026-09-26` | new seed `XSYS-001-A1/2026-09-27` |
| entry points | `execution/run_confirmatory.py`, stage 0 and stage 2 | amended copies that change only the matrix paths, the manifest chain and an acceptance gate (§8) |

**What did not change.** Each item below is the XSYS-001 frozen file,
byte-identical. `tests/test_xsys_001_a1_amendment.py` asserts each one.

- the hypotheses H_PRIMARY and H1–H6;
- the η levels 0.95, 0.85, 0.75, 0.65, 0.55, with the nominal 1.00;
- the evidence definitions W_RPM, W_DYN and W_CTRL; W_EST stays exploratory;
- the thresholds and gates;
- the windows T0–T3;
- the matched-pair (case B) construction;
- the primary endpoint;
- the one-sided 95% cluster-conservative lower-bound rule;
- the zero-WRONG requirement;
- the one Holm family of eight, with gatekeeping;
- the attribution semantics and taxonomy;
- the CSIA v2 implementation;
- the manipulation checks and exclusion logic. Only mechanically necessary
  schedule fields changed: the arm time and noise segment in the matrix;
- the PX4 source, SIH patch, logger configuration and trial driver;
- the number of conditions, 11.

## 2. Part 1 — where the stochastic variation comes from (SOURCE, PX4 `547e2ca`)

| question | answer |
|---|---|
| 1. origin of the noise state | One process-global glibc `rand()` stream (single state, lock-protected), consumed by `generate_wgn()` (Marsaglia polar method with rejection) in several modules. **SIH task thread:** accelerometer and gyro noise every 4 ms step (gyro σ = 0.01 rad/s, `sih.cpp:734-740`), plus ranging-beacon noise every 500 ms. **`hp_default` work-queue thread:** `sensor_baro_sim` at 20 Hz, `sensor_mag_sim` at 50 Hz, `sensor_gps_sim` at 8 Hz |
| 2. explicit seed | yes, a hard-coded constant: `srand(1234)` in `Sih::Sih()` (`sih.cpp:61`) and again in `SensorBaroSim::SensorBaroSim()` (`SensorBaroSim.cpp:46`) |
| 3. controllable | **no.** No parameter, launch argument or environment variable reaches it. Changing it means changing PX4, which was not done |
| 4. same sequence across processes | **yes.** Every process starts from 1234 |
| 5. thread interleaving | **yes.** Lockstep fixes simulated time but not the order of `rand()` calls between the SIH thread and the work-queue thread within a step. The second `srand(1234)` also resets the stream at a boot moment that depends on scheduling |
| 6. heading alters the noise | **no.** Heading changes the initial yaw; the additive noise draws do not depend on state |
| 7. onset time | shifting the onset moves the analysis windows to a **different segment of the same stream**. Overlapping windows in simulated time read the same draws |
| 8. independent processes | **not in any defensible sense.** Separate launches replay the one stream aligned to simulated time. They differ only by per-step interleaving and small offsets (§3) |

The three things the request distinguishes are, here:

- **different trajectory:** a different heading;
- **different segment of one stochastic stream:** a different simulated time;
- **different stochastic realization:** available only as an uncontrolled
  by-product of thread interleaving, never by design.

## 3. Part 2 — dependence in the XSYS-001 design (existing data only)

**Data.** 67 existing nominal logs (`research/xsys_confirmatory_001/amendment_a1/independence/EXISTING_DATA_DEPENDENCE.json`):

- 32 nominal-equivalence flights;
- 27 sweep flights, used only before their onset;
- the 8-flight nuisance pilot.

No fault data were used after onset, and no individual 250 Hz sample was
treated as independent.

**Measurement.** The gyro noise residual r = `sensor_combined.gyro_rad` −
true body rate is PX4's trapezoidal IMU integral of two consecutive SIH draws.

- It has standard deviation 0.0072 rad/s and lag-1 autocorrelation 0.51.
- Identical draws differ by about 1e-6 rad/s. Independent draws coincide
  within 3e-4 rad/s on all three axes with probability 1.4e-5.

| diagnostic | result |
|---|---|
| **E. families** (zero lag, 25–30 s) | 8 bit-identical families among 67 logs (sizes 34, 11, 10, 6, 3, 1, 1, 1). **38%** of identically configured pairs are bit-identical; **75%** of the pilot pairs are, across different headings. Same-family pairs stay identical through 30–44 s (median 0.9989) |
| **A/D. noise identity of every pair** (best lag within ±0.16 s) | **all 2211 pairs** share ≥ 10% of their draws; 95% share ≥ 50%; the median is **92%**. Best lags are 0 (1345 pairs), ±1 step (800) or ±30–31 steps (66). Launches are near-replays aligned to simulated time, not independent realizations |
| **D. XSYS-001 design emulated** (two same-family launches as two conditions with onsets 0.5–5 s apart) | the spans share **75–97%** of their draws (DX1 I = 0.748–0.975). Criterion C1 (≤ 0.001) fails by three orders of magnitude |
| **B. W_DYN null** at the XSYS-001 onset separations (one stream) | D_T1 correlation 0.19 at 0.5 s, and −0.19 to 0.10 up to 5 s |
| **C. W_CTRL null** at the same separations | C_T3 correlation 0.45 at 0.5 s and 0.24 at 2.5 s. L_T3 correlation 0.90 at 0.5 s and 0.53 at 2.5 s (the T3 windows overlap) |
| **D. trajectory**, same noise at different headings (pilot) | true roll-rate correlation −0.20 to 0.51; D_T1 series correlation −0.38 to 0.50. Same heading: 0.99. Heading changes the trajectory without making the noise independent |

**Conclusion for XSYS-001.** Its 11 conditions would read largely the same
noise draws in overlapping spans. The nuisance condition **cannot** be
treated as an independent unit in the XSYS-001 design.

An earlier XSYS-001 statement is refined, not contradicted. XSYS-001 §4.3
reported that different headings shared 2–100% of their pre-arm
**accelerometer** samples. The gyro residual, the signal W_DYN uses, is
shared far more: 60–100% for every pilot pair.

## 4. Part 3 — diagnostics frozen before use

`research/xsys_confirmatory_001/amendment_a1/independence/DIAGNOSTIC_SPEC.json`
was committed (`d47f339`) before any new pilot and before any of these
diagnostics was computed. It defines six diagnostics:

| id | diagnostic |
|---|---|
| DX1 | noise-draw identity, global over every lag |
| DX5 | family membership |
| DX2/DX3 | lag correlation of the frozen statistics L_T1, D_T1, L_T3, C_T3 on every motor |
| DX6 | memory of the per-step signals the statistics are built from |
| DX4 | trajectory correlation |
| C5 | threshold validity |

**Separation rule.** S_min = 20 s + τ_mem, rounded up to a multiple of 5 s.

**Acceptance.** The design is accepted only if all of C1–C5 hold.

## 5. Parts 4–8 — explicit seeding, onset overlap, heading, pilots, design

**Explicit seeding.** None is supported (§2). PX4 was not patched. The
preference order therefore leads to option 3, sufficiently separated
stochastic windows with heading variation. Option 2 (independent process
realizations) is refuted by §3.

**The mechanism.** A pre-arm dwell places each condition's analysis span on
its own segment of the stream. The flight timeline relative to arming is
the same for every condition as in the apparatus: arm, take off, onset 20 s
later, end 16 s after onset. So the thresholds' calibration conditions,
the simulated battery and the hover duration are identical.

This was preferred over shifting the onset within one flight, which would
change the hover time and battery state at onset between conditions.

**Pilots** (nominal only: η = 1.00, no fault, no corruption, no CSIA; ids
`A1P-…`; archived in `research/xsys_confirmatory_001/amendment_a1/pilot_logs/`
with `SHA256SUMS`). Every pilot heading is a half-step between confirmatory
headings, so no confirmatory condition tuple was flown.

| pilot | schedule | purpose |
|---|---|---|
| Q1 `A1P-Q1-LONGHOVER-H016` | heading 16.364°, arm 10 s, end 400 s | memory, statistic lag correlation, long-hover threshold validity |
| Q2 `A1P-Q2-DESIGN-SLOT00` | 49.091°, arm 10 s, onset 30 s | a design condition, slot 0 |
| Q3 `A1P-Q3-DESIGN-SLOT01` | 81.818°, arm 35 s, onset 55 s | slot 1: adjacent, the minimum separation |
| Q4 `A1P-Q4-DESIGN-SLOT02` | 114.545°, arm 60 s, onset 80 s | slot 2 |
| Q5 `A1P-Q5-DESIGN-SLOT10` | 147.273°, arm 260 s, onset 280 s | the longest dwell |

**Memory and required spacing** (`research/xsys_confirmatory_001/amendment_a1/independence/MEMORY.json`;
Q1 hover 22–400 s; 1789 pseudo-onsets):

- τ_mem = **0.332 s** (gyro). ρ memory is 0.08 s and κ memory 0.02 s.
- So S_min = 20.33 s and **S = 25 s**.
- At the statistic level, the correlations fall to the ±0.1 estimation
  noise beyond the 20 s window-overlap distance.
- C_T3 is −0.55 at 15 s, where one onset's T0 is the other's T3, then 0.12
  at 20 s and 0.03 at 25 s.

**Final heading set:** unchanged, 360 j / 11°.

**Final onset schedule:** onset_j = 30 s + 25 s × slot_j, with arm_j = onset_j − 20 s:

| condition | C00 | C01 | C02 | C03 | C04 | C05 | C06 | C07 | C08 | C09 | C10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| heading ° | 0.000 | 32.727 | 65.455 | 98.182 | 130.909 | 163.636 | 196.364 | 229.091 | 261.818 | 294.545 | 327.273 |
| noise segment | SEG05 | SEG07 | SEG10 | SEG02 | SEG04 | SEG09 | SEG00 | SEG08 | SEG01 | SEG06 | SEG03 |
| arm s | 135 | 185 | 260 | 60 | 110 | 235 | 10 | 210 | 35 | 160 | 85 |
| onset s | 155 | 205 | 280 | 80 | 130 | 255 | 30 | 230 | 55 | 180 | 105 |

**Seed mapping.** None exists: PX4 offers no seed. The realization
identifier is the segment `SEGnn`.

## 6. Part 9 — number of conditions and power

`research/xsys_confirmatory_001/amendment_a1/POWER_A1.json` reruns the frozen
calculation with the frozen functions. It reproduces
`research/xsys_confirmatory_001/prereg/POWER.json` exactly, so **N stays 11**.

The frozen requirement assumes two things:

- conditions are independent;
- pairs within a condition are fully correlated.

The amendment exists to make the first assumption true. Nothing was
re-tuned to keep 11.

The same file shows why independence matters. Under between-condition
correlation ρ_b, the frozen rule's false-positive rate at a true rate of
0.5 is:

| ρ_b | 0 | 0.05 | 0.10 | 0.20 |
|---|---|---|---|---|
| false-positive rate | 0.033 | 0.070 | 0.109 | 0.175 |

## 7. Result of the frozen acceptance rule

From `research/xsys_confirmatory_001/amendment_a1/independence/DESIGN_CHECK.json`:

| criterion | result | detail |
|---|---|---|
| C1 no shared draws | **pass** | max I = 0.00079 over the 6 design pairs, at unrelated lags. Same-simulated-time spans of Q1 replay the design spans at 0.60–0.999 (the family effect) |
| C2 separation ≥ 20 s + τ_mem | **pass** | realized onset separations 25.0 s and more; required 20.33 s |
| C3 statistics uncorrelated at S | **pass** | worst band mean ρ = −0.075 |
| C4 trajectories uncorrelated | **FAIL** | every evidence signal \|r\| ≤ 0.055 (gyro projection, κ₀, ρ₀). But the **true pitch rate** gives 0.274 (Q2–Q4), 0.171 (Q4–Q5) and −0.110 (Q3–Q5), against the frozen limit of 0.1 |
| C5 threshold validity | **pass** | every null statistic is below its frozen threshold in all five pilots, including the 250 s dwell and the 390 s hover; heading error ≤ 0.65° |

**Decision (frozen rule): XSYS_001_REQUIRES_FURTHER_DESIGN_WORK.**

### POST-HOC / EXPLORATORY (does not change the decision)

`research/xsys_confirmatory_001/amendment_a1/independence/C4_POSTHOC_EXPLORATORY.json`
was written after C4 failed. It asks whether |r| ≤ 0.1 is attainable at all.

**Reference.** 105 pairs of disjoint 20 s spans of Q1, independent by the
same construction the design uses. Between these spans:

- the true roll and pitch rates exceed |r| = 0.1 in **44–48%** of pairs;
- their 95th percentile is **0.27–0.28**, so the design pairs sit inside
  that distribution;
- the true rates carry only about 32 independent samples in 20 s;
- even the gyro projection exceeds 0.1 in 6% of independent pairs.

**Reading.** The C4 limit was mis-specified: it ignored the autocorrelation
of slow signals. The data give no sign of shared state. Similarly, C1's
limit of 0.001 lies close to the chance level of its global-lag maximum:
spans that share no draws gave 0.0004–0.0008. The failure is still reported
as a failure.
Fixing a failed acceptance criterion after seeing it is a decision for the
program owner, not for the analyst who wrote it.

## 8. What the freeze does, and the next step

**What the freeze does.**

- XSYS-001 stays frozen and byte-identical.
- Its nuisance design is **superseded and must not be flown**: its
  conditions share noise.
- XSYS-001-A1 is frozen as the record of this investigation and of the
  candidate design. Its manifest binds the XSYS-001 manifest by SHA-256 and
  lists every XSYS-001 frozen file with the same hash.

**The amended entry points.**

- `research/xsys_confirmatory_001/amendment_a1/execution_a1/run_confirmatory_a1.py`
  reads the A1 matrix and order and verifies both manifests. It verifies
  and lists with `--dry-run`, but **refuses to fly while `DESIGN_CHECK.json`
  says not accepted**, which is its frozen state.
- The stage 0 and stage 2 wrappers in
  `research/xsys_confirmatory_001/amendment_a1/pipeline_a1/` run the frozen
  stage code byte-identical. They only redirect its manifest check to the
  A1 matrices.
- Stage 1 needs no wrapper: it runs frozen with the A1 manifest.
- `tests/test_xsys_001_a1_amendment.py` fails if any campaign or trial
  record ever carries the XSYS-001 or the A1 manifest.

**Proposed next step (for owner review; NOT adopted here).** A further
amendment would:

1. pre-register a corrected C4 that compares design-pair correlations with
   an independent-span reference null (for example, not above that null's
   99th percentile per signal), and set C1's limit at 0.01. That is still
   more than 100× below the smallest replay seen (0.12), and well above its
   chance maximum;
2. fly **fresh** nominal design pilots at new half-step headings;
3. if they are accepted, unlock execution of this unchanged A1 matrix under
   its own manifest.

It would change no scientific element of XSYS-001.

**Also preregistered here for any accepted successor.**
`research/xsys_confirmatory_001/amendment_a1/independence/audit_campaign_a1.py`
re-checks C1 on the campaign's own NB flights. It is outcome-blind and
report-only.

## 9. Validation after the freeze

`research/xsys_confirmatory_001/amendment_a1/post_freeze_check_a1.py`
performs the 20 checks the request lists. It writes
`research/xsys_confirmatory_001/amendment_a1/POST_FREEZE_CHECK_A1.json`,
which is outside the freeze.

## 10. Limitations

- The dwell design's independence rests on disjoint segments of one
  pseudo-random stream plus measured short memory. It is not a new seed.
- The segment alignment to simulated time was observed to vary by up to
  31 steps (0.124 s) between launches. That is far below the 25 s spacing.
- Only five nominal pilots were flown. C4's failure means the design is
  not yet accepted by its own rule.
- Flights now last up to 296 s, so the campaign takes about 3 hours and
  its logs are larger.
