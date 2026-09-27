# XSYS-001-A2 — pre-data amendment: correcting the definition of C4

**Status: SPECIFICATION FROZEN BEFORE USE.** This document, the
machine-readable specification
`research/xsys_confirmatory_001/amendment_a2/C4_A2_SPEC.json`, the fresh pilot
matrix and the evaluation code were committed and pushed **before any A2
pilot was flown**. The results are recorded separately after the pilots. This
file is never edited afterwards.

| | |
|---|---|
| chain | XSYS-001 (manifest `868880182a8c242abef9fb5dca2d250f2af9f9f83abbe703979c0eb7b300407b`) → XSYS-001-A1 (manifest `55d72d390059449c01d12b4a9007db155a3add1df6a25f26dd9000142825dd3b`) → XSYS-001-A2 |
| scope | the definition of criterion C4 only |
| unchanged | C1, C2, C3 and C5, the 11-condition design, η set, headings, 25 s spacing, noise-segment assignments, the A1 confirmatory matrix and order, matched pairs, W_RPM, W_CTRL, W_DYN, W_EST status, thresholds, windows, hypotheses, primary endpoint, statistical rule, zero-WRONG, Holm, v2, the PX4 apparatus |
| authorization | `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` §10 |
| confirmatory flights / analysis trials | 0 / 0 |

**One conflict in the instruction, resolved conservatively.** Its title reads
"I approve the corrected C4 and C1". Its body says "DO NOT loosen C1" and
"Do NOT change C1". C1 is therefore **unchanged**: I ≤ 0.001, global lag
search, spans extended back by τ_mem. The A1 proposal to set C1's limit to
0.01 is not adopted.

## 1. Rationale and the A1 failure

A1's C4 required |r| ≤ 0.1 for the Pearson correlation between two
conditions' span signals. The signals were the gyro projection, κ₀, ρ₀, and
the true roll and pitch rates.

- **What failed.** On the A1 design pilots the true pitch rate reached
  r = 0.274, and C4 failed. Every signal the frozen evidence pipeline uses
  stayed at |r| ≤ 0.055.
- **What A1 found afterwards.** A post-hoc, exploratory analysis compared
  spans already known to use independent noise segments. Their true body
  rates exceed |r| = 0.1 in 44–48% of pairs, because a slow physical
  trajectory carries only about 32 independent samples in 20 s.

**Why A1 remains failed.** A1's C4 was defined before its data. Its failure
is historical evidence and is not rewritten. A1's verdict, manifest and
non-executable status are untouched. A2 defines a corrected criterion
**prospectively** and tests it only on **fresh** nominal data. The A1 design
pilots Q2–Q5 were observed before this definition, so they are historical
context only.

**Corrected scientific interpretation.** C4 should not ask whether two
nominal trajectories are nearly uncorrelated. One deterministic aircraft,
controller and hover objective produces correlated slow states even under
independent forcing. C4-A2 instead asks:

> Does the segmented nuisance design introduce cross-condition dependence
> beyond what is naturally observed between independently separated nominal
> spans?

That makes the null an empirical **independent-span reference**, not zero.

## 2. Reference population

- **Data.** Two fresh nominal hovers, R1 and R2: η = 1.00, headings 8.182°
  and 188.182°. They follow the A1 long-hover protocol: arm 10 s, benign
  event at 30 s, end 400 s. So they share the aircraft, controller and
  nominal mission, and they vary the heading as the design does.
- **Spans.** t0 = arm + 20 s + 25 s·k for k = 0…14, giving 30 spans. Each
  span is [t0 − 5, t0 + 15), the 20 s duration of the analysis span. The
  first span matches the conditions' mission phase exactly.
- **Valid pair.** Two spans are a valid pair if both hold:
  - their onsets differ by ≥ 25 s in simulated time (the accepted C2
    spacing), within one hover or across the two;
  - they share no noise draws under the **unchanged C1** (I ≤ 0.001, spans
    extended back by τ_mem = 0.332 s).

  Pairs that fail C1 are excluded and reported.
- **Preprocessing.** Identical to the candidates: the A1 function
  `trajectory_corr` in
  `research/xsys_confirmatory_001/amendment_a1/independence/independence_diagnostics.py`,
  frozen by A1 and imported unchanged.

## 3. C4-A2: exact definition (the one primary rule)

- **Signals.** The five A1 C4 signals: gyro projection on motor 0's loss
  axis, κ₀, ρ₀, true roll rate and true pitch rate.
- **Sample unit.** The candidate flight on the candidate side and the
  reference span on the reference side. Pairwise |r| values are derived
  quantities.
- **Statistic, per signal s.**
  Δ_s = mean |r| over the 28 candidate pairs − mean |r| over the valid
  reference pairs.
- **Uncertainty.** U_s is the one-sided 95% upper bound: the 95th percentile
  of Δ_s* over B = 20000 bootstrap replicates.
  - Each replicate resamples the 8 candidate flights and the reference spans
    with replacement.
  - It averages |r| over pairs of distinct resampled units that form valid
    pairs.
  - The random generator is numpy `default_rng(20260927)`, with one joint
    draw sequence for all signals.
- **Autocorrelation.** No parametric standard error of r is used. The
  reference |r| values come from spans with the same signals, duration,
  preprocessing and autocorrelation, so the comparison is calibrated
  empirically. Dependence between pairs that share a unit is carried by the
  unit bootstrap.
- **Multiple variables.** Intersection–union: C4-A2 passes only if all five
  signals pass. Each test is one-sided at 5%, and the pass decision needs no
  adjustment.
- **Rule.** **C4-A2 PASS iff U_s ≤ 0.10 for every signal.**

  0.10 is A1's own materiality scale. It now applies to the increase over
  the natural independent reference rather than to |r| itself.

## 4. Evidence-signal hard requirement (EV-A2)

The inference operates on the frozen statistics L, D and C. These are
functions of exactly three per-step signals: the gyro projection, κ₀ and ρ₀.
A2 fails if these show meaningful dependence, whatever C4-A2 says. C3 is
also kept unchanged.

**EV-A2 PASS iff, for each of the three evidence signals, both hold:**

- U_s ≤ 0.05, using the same statistic and bootstrap as C4-A2;
- every candidate pair has |r| ≤ 0.20.

Why these limits:

- Natural |r| between independent spans is 0.02–0.04 for these signals, so
  an increase of 0.05 would more than double it.
- 0.20 is about twice the largest evidence-signal |r| (0.117) among 105
  independent A1 reference pairs.

## 5. Fresh replication of the unchanged gates

| gate | on fresh data |
|---|---|
| C1 | unchanged definition and threshold, on all 28 candidate pairs. **Gating** |
| C5 | unchanged definition and thresholds, on all 10 A2 flights. **Gating** |
| C3 | recomputed on each reference hover, band [25, 35] s. **Descriptive only**: C3 is carried from A1 unchanged |
| C2 | a design property: S = 25 s ≥ 20 s + τ_mem. Carried |

**Acceptance.** XSYS-001 may become READY only if all of these hold:

- the carried A1 results C1, C2, C3 and C5 are PASS;
- fresh C1 and fresh C5 are PASS;
- C4-A2 and EV-A2 are PASS;
- every frozen preregistration guard test passes.

Otherwise the verdict is **XSYS_001_REQUIRES_FURTHER_DESIGN_WORK**. No A3 is
created automatically.

## 6. Pilot design and sample size

The design is in `research/xsys_confirmatory_001/amendment_a2/PILOT_MATRIX_A2.csv`,
generated by `research/xsys_confirmatory_001/amendment_a2/generate_pilots_a2.py`:

- **2 reference hovers**, R1 and R2 (above);
- **8 candidate flights**, flown exactly as the A1 25 s segmentation
  schedules a condition: arm = 10 s + 25 s × slot, benign event at arm +
  20 s, end 16 s later.
  - Slots are 0, 1, 2, 3, 5, 7, 9 and 10: adjacent pairs and both extremes.
  - Headings are 180.000, 212.727, 245.455, 278.182, 310.909, 343.636,
    24.545 and 57.273°.
  - These are quarter-steps that are neither confirmatory headings nor A1
    pilot headings.

**Sample size, planned before collection.** The planning used only the A1
long-hover null: 105 independent Q1 span pairs, never the A1 candidates.

| candidate flights | rule passes an exchangeable null | rule passes a true increase equal to the margin |
|---|---|---|
| 8 (with 30 reference spans) | 0.98–1.00 per signal | 0.01–0.03 |
| 6 | 0.82–0.94 per signal | — |
| 4 | the flight bootstrap degenerates | — |

Eight is the smallest adequate number. The same null showed C1's I never
exceeding 0.001 between independent spans (max 0.00059), so gating fresh C1
is not a chance trap.

## 7. Stopping rule

- `research/xsys_confirmatory_001/amendment_a2/fly_pilots_a2.py` flies the
  10 rows in matrix order with the frozen XSYS-001 trial driver.
- It retries each technical failure once, with the identical configuration.
- Nothing is evaluated until all 10 are flown. The evaluation does not stop
  early because a gate passes.
- If any flight cannot be completed, the evaluation is incomplete and the
  verdict is REQUIRES FURTHER DESIGN WORK.
- No flight is added and none is dropped.

## 8. Evaluation code

`research/xsys_confirmatory_001/amendment_a2/analyze_a2.py` is committed with
this specification. Before the commit it was exercised only on synthetic
matrices, never on flight data.
