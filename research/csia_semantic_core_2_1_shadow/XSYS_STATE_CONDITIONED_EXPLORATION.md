# XSYS-001: state-conditioned evidence validity

**EXPLORATORY. Not a confirmatory result. XSYS-001's sealed result, its
preregistration and every sealed file are unchanged.**

**2026-09-30. Parts 16 and 50 of the shadow-validation brief.** Script:
`xsys_state_conditioned.py`. Output: `XSYS_STATE_CONDITIONED_RESULTS.json`.

## 1. What was read, and how

- **Inputs:**
  - the committed blind inputs (`stage1_inputs/blind/*.npz`, 121 trials);
  - the frozen calibration from the sealed `STAGE1.json`;
  - the sealed Stage 2 labels (`stage2/RESULTS.json`), used only to grade.
- **Frozen code, imported unchanged.** The feature functions
  (`xsys_features.py`) and the adapter's `localize_subject`
  (`xsys_v2_adapter.py`). The only addition is a set of sliding windows placed
  in the imported module's window table **in memory**, so the frozen
  statistics can be evaluated at more times than the preregistered T1
  (0-0.2 s) and T3 (10-15 s).
- **Check.** Recomputing the preregistered V3 at checkpoint C3 with this code
  reproduces the sealed outcome on 110 of 110 fault trials.

**How the analysis developed (disclosed because it is post hoc).**
- **The first version was wrong and was replaced.** It had one state rule,
  gave compensation as evidence to every rule, and had a logic error in its
  admission rule. The error was found by inspecting individual trials.
- **Two things were added after seeing the first result:**
  - the dynamics-only evidence set, which isolates the validity question;
  - a 1 s state window, which tests whether the failure was only the 0.2 s
    window's noise.
- **Nothing else was tuned.** The numbers below are from the final version.
  With two post-hoc additions, they are hypotheses for a future
  preregistered study, not findings.

## 2. The question

W_DYN, the body-rate response to a rotor's thrust loss, separates a genuine
effectiveness loss from RPM-telemetry corruption early, and misleads late.
Once the controller has compensated, a genuine loss looks dynamically
nominal. The preregistration handled this with a fixed rule: dynamics
evidence is taken only from T1 = [0, 0.2) s.

**Could an observable controller state have said when W_DYN stopped being
admissible, better than the fixed rule?** The state considered here is
allocator compensation, from the frozen compensation witness.

## 3. Results

**Setup.** Motor 0, every 0.1 s from 0.2 s to 15 s after onset. 110 fault
trials × 149 times = 16,390 graded trial-times. Localization uses the frozen
signature.

**Dynamics-only evidence** (RPM symptom plus dynamics), which isolates the
validity rule:

| rule | wrong trial-times | trials ever wrong | correct UNIQUE trial-times |
|---|---|---|---|
| no validity rule | 7,228 | **55** (all genuine-loss trials) | 8,669 |
| fixed time (T1 only, the preregistered rule) | **0** | **0** | **16,390 (all)** |
| state, 0.2 s compensation witness | 0 | 0 | 5,960 |
| state, 1 s compensation witness | 0 | 0 | 5,960 |

**With compensation also given as evidence** (trailing 1 s):

| rule | wrong trial-times | trials ever wrong | correct UNIQUE trial-times |
|---|---|---|---|
| no validity rule | 0 | 0 | 9,107 |
| fixed time | 0 | 0 | 16,335 |
| state, 0.2 s | 30 | **10** (sensor-fault trials) | 16,300 |
| state, 1 s | 30 | **10** (sensor-fault trials) | 16,300 |

**Timing, genuine-loss trials (55):**
- compensation is first detected in the **first** 0.2 s window in all 55;
- the dynamics witness first reads "nominal" (misleading) at **0.4 to
  1.9 s**;
- compensation is detected no later than the dynamics turn misleading in
  **55 of 55**.

**Spurious compensation in trials with no physical loss.**
- **Short window.** The 0.2 s compensation statistic crosses its threshold at
  some time in every sensor-fault trial and every nominal trial.
- **1 s window.** 15 of 55 sensor-fault trials cross it.
- **Why.** The frozen threshold θ_ctrl = 0.0022 was calibrated on the 5 s T3
  window. Over sub-second windows the allocator's normal variation reaches
  it.

## 4. Reading

1. **The state rule is safe for genuine losses, but for the wrong reason.**
   - Compensation is visible from the first window, so the rule never admits
     the dynamics transient of a genuine loss at all.
   - It therefore loses every genuine-loss trial as a dynamics
     identification. Those 55 trials are AMBIGUOUS where the fixed rule is
     right.
   - **The deeper point is what "compensation present" means.** Compensation
     *starting* is not the moment W_DYN stops being informative. Compensation
     *converging* is, and that happens at 0.4-1.9 s.
2. **In trials with no physical loss, the state estimate itself is the
   problem.**
   - A noisy compensation estimate closes validity early.
   - When the same estimate is also evidence, it refutes the true hypothesis:
     10 wrong UNIQUE.
   - **This is loophole L12 in a real system.** The validity condition and the
     discriminating evidence come from one source (the allocator output), so
     they fail together.
3. **The fixed 0.2 s rule worked on this apparatus and was conservative.**
   The dynamics stayed informative until at least 0.4 s in every
   genuine-loss trial. It worked because the onset timing on this apparatus
   is consistent, which says nothing general about 200 ms.

**Answer to the brief's question, for XSYS-001.** No: the observable
compensation state, as the frozen witness measures it, did not identify
W_DYN's validity better than the fixed rule. It revoked the evidence earlier
in every genuine-loss trial, and it kept it no longer in any trial where
keeping it helped.

**Hypothesis for a preregistered study** (not tested here, to avoid adding
further post-hoc variants): a state variable of the form "compensation has
converged" (the compensation statistic within a tolerance of its implied
steady state), with the state producer's own validity regime declared, may
bound W_DYN's validity better than either the fixed rule or "compensation
present".

## 5. What this changes for CSIA

- **A state condition must be treated as evidence with its own validity**,
  not as ground truth. Its producer must declare the regime its estimate is
  valid in (`DEPENDENCY_METADATA_PREVIEW.md`; the evidence-contract fields
  `validity_condition` and `operating_regime`).
- **Validity conditions should prefer discrete, reported configuration
  facts** (epochs, resets, modes) over estimated continuous states. E1 in
  `CONFIGURATION_TRANSITION_STUDY.md` is the contrasting case.
- **A validity condition must not share its source with the evidence it
  gates** unless that dependence is declared, so the reasoner can see it
  (L12).
