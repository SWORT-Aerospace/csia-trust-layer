# Preregistration Amendment 1 — the experimental design, fixed before it is run

**Written and committed before any validation or final seed is opened.**
Amends `PREREGISTRATION.md` for this phase. It does **not** change any
hypothesis, any frozen constant, any metric definition, or the conditions for
opening the sealed partition. It fixes the factor structure, which §14 of the
task left to the experimenter, and it records two things learned on the
development partition that change how results must be read.

## 1. Why a reduced design rather than a full factorial

§14 lists eleven factors. Crossing all of them at full depth is not affordable
here, and the reason is specific rather than general: the **P7b ceiling is an
exhaustive argmin over all 72 admissible actions**, so every cell in which P7b
appears costs 72 plant runs rather than one. A full crossing of plant × drift ×
lag error × magnitude × seed with P7b present would be roughly two orders of
magnitude more plant integrations than the container can run.

§14 explicitly contemplates analytic pruning and a deterministic search on the
development partition. This amendment is that pruning, written down before the
outcomes exist rather than chosen afterwards.

## 2. The design

### Main block — full factorial, all arms

| factor | levels |
|---|---|
| plant | Q0, Q1, Q2 |
| drift | nominal (0 V/s), elevated (2e-3 V/s) |
| magnitude `ΔR` | 0.002, 0.004, 0.006, 0.010, 0.020, 0.040 Ω |
| arm | P0–P6, P7a, P7b, P7c, S0–S3 (14) |
| seed | the whole partition |

Lag estimate equal to the true lag. Matched duration and matched energy class
are recorded per row so that both the like-for-like comparison and the
unequal-energy Pareto analysis can be made from the same data.

### Ablation blocks — not crossed with the main block

Each varies one thing against the main block's nominal configuration, over the
same seeds, on the deployable arms and selectors only. P7b is omitted from the
ablations, and where a ceiling is needed for context the main-block value at
the matching cell is quoted and labelled as such.

1. **Lag-estimation error.** The estimate handed to the strategies is 0.5×,
   1.0× and 2.0× the plant's true lag. The plant is unchanged; only what the
   selector believes moves. This is the factor the prior phase found
   non-monotone, so all three are reported and none is called conservative.
2. **Unknown ringing**, at amplitudes below, near and above the measured
   3.363 σ boundary: 0.05 V (0.82 σ), 0.20 V (2.82 σ) and 0.60 V (8.39 σ).
3. **Sensing defects**: current gain error, current noise, current
   quantisation, current delay, voltage quantisation, voltage delay.
4. **Telemetry defects**: dropout, timestamp jitter, sample phase.
5. **Execution**: full, clipped, aborted at 25% of the window.

### Partitions

Development is already open and everything above was fixed on it. The runner
completes at full scale on **validation** before the sealed **final** partition
is considered, and the sealed partition opens only if every condition in §6 of
the preregistration holds.

## 3. What was learned on development that changes how results read

**3.1 The primary change metric cancels the plant.** `COUNTEREXAMPLE_LOG.md`
IV-9: on a matched pair under common random numbers the fault does not move the
current, so `V_fault − V_nominal = −ΔR₀·I_true` exactly and every plant-common
nuisance cancels. `e_ΔR` reduces to `|λ̂ − 1|·Δ`, a finite-sample
errors-in-variables term.

`e_ΔR` and `M_R^out` **remain primary**, because that is what §5 of the task
defines and §2 of the preregistration froze. Nothing is re-chosen. But:

* H5, plant discrimination, is evaluated on `AE_R`, which was preregistered in
  §4.1 and does not cancel;
* `A_s` and the frontier are reported on **both** metrics, always with the
  predicate stated;
* any statement about *which action is better* leans on `AE_R`, because under
  the change metric such a statement is largely a statement about one noise
  draw (`COUNTEREXAMPLE_LOG.md` IV-11).

**3.2 The certificate saturates below 0.020 Ω on this command.** At a 0.010 Ω
target the union bound is 0.005161 against an allowed 0.005000, dominated by
the polarization term, so nothing certifies at any magnitude. Certificate
calibration (H4) is therefore reported **per target**, and rows where the
budget is infeasible before any data arrives are labelled as such rather than
counted as certification failures.

## 4. What this amendment does not do

It does not change `TAU_R_RELATIVE`, `TAU_R_ABSOLUTE`, `COVERAGE_TARGET`, the
resolve predicate, the magnitude grid, `d_max_tested`, the primary interaction
statistic `I_s`, any hypothesis, any falsifier, or any of the ten conditions for
opening the seal. It adds no metric that did not already exist in §4 of the
preregistration.

It also does not touch the prior phase's frozen artifacts, the frozen CSIA
core, production defaults, deployed authority or failsafe behaviour, and it
authorises no hardware of any kind.
