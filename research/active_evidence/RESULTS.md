# Results — active evidence acquisition

**Status: E0, desktop simulation. No novelty claimed. Not a safety artifact.**

Artifact: `research/active_evidence/results/ACTIVE_EVIDENCE_CAMPAIGN.json`,
schema `csia.active_evidence.campaign/1`.
Preregistered before the run: `PREREGISTRATION.md`.

## 1. The headline

The prediction, fixed in advance: *a probe meeting all three closed-form
conditions resolves `delta_r`; a probe failing any one does not.* A single
false positive would falsify it.

| cell class | count |
|---|---|
| met the requirement and resolved | 20 |
| failed the requirement and did not resolve | 7 |
| **false positive — met and did not resolve** | **0** |
| false negative — failed and resolved anyway | 1 |

**Verdict: `NO_COUNTEREXAMPLE_IN_THIS_GRID`.** That sentence is exactly what
it says. 28 cells, 4 deltas, 7 probes, 5 seeds, one simulator. It is not a
statement about any other grid and it is not a statement about hardware.

## 2. The measurement that decides whether the campaign means anything

The null arm, `hold`, commands nothing. Under a 0.040 ohm rise:

| quantity | value |
|---|---|
| terminal voltage shift | **-0.959 V** |
| change in the fitted resistance | **8.6e-12 ohm** |

The fault is present, unmistakable, and roughly 24 A x 0.040 ohm as arithmetic
requires. The estimator cannot see it at all, because there is no current
variation to regress against.

That pair of numbers is the whole argument for active evidence in one line:
**the information is not missing from the vehicle, it is missing from the
excitation.** It also discharges both halves of the preregistration's Rule A
— the null arm resolves nothing, and it is not vacuous.

## 3. The noise model was measured, not read

Reading `simulate.SIGMA` would have handed the derivation the plant's own
parameters and made every agreement a tautology. Successive differencing on
the held-out reference seed recovered:

| channel | measured | plant's true value |
|---|---|---|
| voltage sigma | 0.02005 V | 0.020 V |
| current sigma | 0.07864 A | 0.080 A |
| open-circuit drift | 0.004598 V/s | not a declared constant |

## 4. Closed-loop realisation: two findings the derivation did not predict

Measured per probe against its commanded profile:

| probe | realised / predicted std(I) | commanded lever arm | realised lever arm |
|---|---|---|---|
| triangle_soft | 1.76 | -1.2e-15 s | -1.138 s |
| doublet | 1.59 | +2.2e-16 s | -0.943 s |
| step_hold | 1.48 | -5.9e-17 s | -0.584 s |
| triangle | 1.46 | +8.4e-16 s | -0.860 s |
| burst_2hz | 1.46 | -1.8e-16 s | **+0.019 s** |
| burst_wide | 1.46 | -6.5e-16 s | **+0.004 s** |

**First:** the loop amplifies the excitation by 1.46x to 1.76x, because
holding a commanded velocity against integral action costs more current
excursion than the static gain predicts. The requirement is computed from the
command and therefore understates every probe. This is why the one false
negative exists, and it is the conservative direction.

**Second, and it corrects a claim this work made about itself:** the symmetry
guarantee is about the COMMAND. The loop lags, and a lag breaks a palindrome.
Four of six probes lose the property, with realised drift biases up to
0.0052 ohm — larger than the smallest change in the grid. Only the two
multi-cycle bursts keep it, because the lag averages across cycles.

The campaign's cell verdicts could not have caught this: they score a
differential comparison and a common bias cancels. It was found by measuring
the realisation separately, which was possible only because the design rule
had been stated sharply enough to be checkable.

## 5. The false negative, and why it is not a counterexample

`triangle` at `delta_r` = 0.005 fails the variance condition and separates
anyway, at a gap-to-scatter ratio of 4.16 against a threshold of 3. The
preregistration fixed in advance that false negatives do not falsify the
claim: they show the requirement is conservative, which is the safe
direction. §4 gives the mechanism.

Stable across seed counts — scatter 0.00119, 0.00134, 0.00129 at 5, 20 and
40 seeds — so it is a property, not sampling noise.

## 6. Two errors in the derivation, caught by writing the test

| what | measured |
|---|---|
| the mean formula, over 18 Monte Carlo cases | worst error **2.1e-05 ohm** |
| the textbook slope variance | optimistic by up to **85%** |
| the delta-method replacement | within **2.2%** |
| the deconvolution accepting a pure-noise hover, before the fix | **45% to 48%** of windows |

The variance error mattered more than its size: it under-reports scatter, so
a requirement built on it authorises probes that cannot deliver. The
falsified expression is kept in the module and re-measured on every test run.

Full narrative in `FAILURE_AND_COUNTEREXAMPLE_LOG.md`.

## 7. What did not happen

* no frozen path was read, imported or edited;
* no threshold, gate, weight, prior, signature, hypothesis semantic,
  smoothing, freshness semantic, failsafe semantic or support semantic was
  changed anywhere in CSIA;
* no number in either paper moved, and no row in any claim table changed;
* nothing here was tuned to make a result come out. The two configuration
  numbers that exist — `k_sigma` = 3.0 and `bias_fraction` = 0.25 — were
  fixed in the preregistration and never swept;
* nothing was promoted. The package writes no trust value, no capability
  state and no support verdict;
* no novelty was claimed.

## 8. What would have to happen next

Hardware, and the prior-art reading. Neither is available from this host.
