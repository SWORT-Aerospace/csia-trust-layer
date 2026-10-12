# Preregistration amendment 1 — repairing the instrument

**Dated 2026-09-13. Committed before any seed outside the original
partitions is read.**

Amends `PREREGISTRATION.md` (committed `84576af`). The original hypotheses
H1 to H6 are **preserved unchanged**. Nothing below weakens a falsification
condition; the amendment exists because the instrument cannot currently
answer the question the hypotheses pose.

Base: HEAD `e3c39a1`, clean tree. `a0209cb` and `e3c39a1` are both ancestors.

## 1. What actually failed, stated accurately

The instruction that prompted this amendment described two instrument
failures. One is stale and one is worse than described. Recording that
precisely matters more than accepting the framing.

### 1.1 P3 produced zero certificates in the pilot. IT NO LONGER DOES.

**"P3 produced zero certificates in the pilot."** That statement is true of
the pilot and is **not** true of the committed state. The failure was found
and repaired before the first artifact was written, and it is recorded as
RC-3 in `COUNTEREXAMPLE_LOG.md`. In `results/RCEC_CAMPAIGN.json` P3 reports
`CERTIFIED_IN_MODEL` 50 times out of 50 in all three plant models.

The pilot objective penalised a shortfall against `S_II_min` and the drift
lever arm, and divided energy by 100. `S_II_min` is 36.9 A²·sample, which
nearly every waveform clears, so the deficit term went to zero and the
objective reduced to *use as little energy as possible*. It selected a 2 A
chirp over 2 s, which the certificate refused as `MEASUREMENT_LIMITED` with
a realized lever arm of 0.591 s.

**What was never done, and is done by this amendment**, is the rigorous
classification: was the pilot failure infeasibility, optimizer failure,
prediction/realization mismatch, or a certificate defect? RC-3 asserts a
cause from one observation. A binding-constraint table over the whole
candidate grid, a feasibility argument, and an optimizer comparison against
exhaustive enumeration are required before that assertion is evidence.

**The failing objective was never committed.** `git log -S` over the
campaign file returns nothing. The pilot artifact therefore does not exist
and cannot be recovered. It will be **reconstructed** from the exact
description in RC-3, run deterministically, and labelled
`RECONSTRUCTED_NOT_RECOVERED` in every file it appears in.

### 1.2 The task metric saturates. AT BOTH ENDS, WHICH IS WORSE.

**"The original task metric reached its upper bound and was
non-discriminating."** Confirmed, and understated. Measured on the committed
artifact, separation fraction by target change, one-RC model:

| arm | ΔR 0.005 | 0.010 | 0.020 | 0.040 |
|---|---|---|---|---|
| P1 palindromic | 0.00 | 1.00 | 1.00 | 1.00 |
| P2 compensated | 0.00 | 1.00 | 1.00 | 1.00 |
| P3 shaped | 0.00 | 0.00 | 1.00 | 1.00 |
| P4 feedback | 0.00 | 1.00 | 1.00 | 1.00 |
| P5 random safe | 0.00 | 1.00 | 1.00 | 1.00 |
| P6 mission | 0.00 | 0.00 | 1.00 | 1.00 |
| P7 oracle | 0.00 | 1.00 | 1.00 | 1.00 |

The metric is floored at 0.00 for every arm at the smallest change and
ceilinged at 1.00 for every arm at the two largest. **Exactly one of four
grid points discriminates, and it separates seven arms into two groups.**
Every difference reported between arms in MX-039 rests on that single point.

### 1.3 The active/passive comparison is nuisance-model-dependent.

**"Passive performance changed when effort_drift was removed."** Measured
this session: removing `effort_drift` from the signature moves passive from
5 unresolved to 9 while every active arm stays at 6, reversing the sign of
the active advantage. This is an interaction, not a nuisance to be deleted.

## 2. Why the existing metric cannot answer the comparison

It is binary per (arm, magnitude, seed) and the magnitude grid was chosen
before the discriminating band was known. A binary outcome on a four-point
grid cannot express *how close* an arm came, so two arms that fail by a
factor of two and by a factor of one hundred score identically, and two arms
that succeed with 5% and 95% margin also score identically.

## 3. Changes this amendment permits

1. **A continuous primary outcome.** The signed resolution margin
   `M_R = |ΔR_target| − (|B_total| + U_R)`, reported with its sign, replaces
   the binary fraction as the primary comparison. The binary metric is
   **retained for auditability** and reported beside it.
2. **A difficulty ladder** over the sixteen factors listed in §6 of the
   governing instruction, concentrated near the resolution transition rather
   than spread over a fixed grid.
3. **`effort_drift` as a factorial variable**, present and absent and varied,
   crossed with strategy, plant model and difficulty. It is **not removed**.
4. **New immutable seed partitions**, defined in
   `csia_active_evidence/partitions.py`, manifest SHA-256
   `e872d36fb3a9337704c18290e1b8ec0452d295c416eef0ba58a8b97c5b6f65c2`.

## 4. What remains locked and unchanged

* H1 to H6 and every falsification condition in `PREREGISTRATION.md` §3;
* `c_fraction = 0.5`, `k_sigma = 3.0`;
* the six error terms and the union bound;
* the ten certificate states and their evaluation order;
* the rule that an undeclared term is `UNBOUNDED_TERM` and fails closed;
* the original partitions. `ORIGINAL_LOCKED` has been opened and its results
  are published; it will not be reused to evaluate the repair.

## 5. Seeds

| partition | seeds | use |
|---|---|---|
| `diagnostic` | 11000–11700 | repair work only |
| `amended_calibration` | 12000–12500 | fitting anything that must be fitted |
| `amended_validation` | 13000–13900 | choosing between repaired variants |
| `amended_locked` | 14000–15900 | **SEALED.** Opened once, after freeze |

`partitions.assert_disjoint()` runs at import and refuses to load the package
if any seed appears twice. `partitions.seeds()` raises on a sealed partition
and there is no override argument.

**No locked seed, original or amended, is read during repair.** A test
asserts the diagnostic tooling's seed constants are disjoint from both.

## 6. What would falsify the repaired experiment

Unchanged from the original, plus:

* the continuous margin saturates as the binary metric did, meaning the
  difficulty ladder failed to bracket the transition;
* the margin and the binary metric disagree in rank order without an
  explanation grounded in the error terms;
* a feasible witness exists that P3's search cannot find, and the search is
  not repaired;
* the spectral polarization bound is violated anywhere in the bounded
  calibration grid;
* lag underestimation is shown to be non-conservative and the claim is not
  withdrawn.

## 7. Stop conditions

`INVALID_INSTRUMENT` is reported, and the campaign is not run, if any
condition in §10 of the governing instruction holds. The two most likely
here are exposure of a locked seed during repair, and a spectral bound that
uses a diagnostic outcome rather than the commanded waveform.

## 8. Status

AMENDED AND PREREGISTERED. The repaired campaign has not been run.
