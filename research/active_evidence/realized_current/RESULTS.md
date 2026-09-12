# Results — Realized-Current Excitation Certificate

**Verdict: `SUPPORTED_WITH_NARROW_SCOPE`, and one genuine false
certification was found and closed. E0, simulation only, synthetic
pack. Post-freeze, research-only, quarantined. No novelty claimed.**

Artifact: `results/RCEC_CAMPAIGN.json`, schema
`csia.active_evidence.rcec_campaign/1`.

## 1. The strongest defensible result

> At constant amplitude and constant energy (40.7 A·s), moving a probe's
> energy from 0.41 Hz to 0.77 Hz reduced the smallest resolvable pack
> resistance change from **0.020 Ω to 0.005 Ω**, a factor of four, and the
> certificate's own error decomposition predicted the optimum without
> running the sweep.

## 2. The mechanism, and it is a trade

| cycles in 8 s | `f_eff` | `B_dynamic` | `k·SE` | total | resolves 0.005 Ω |
|---|---|---|---|---|---|
| 1 | 0.17 Hz | 0.00366 | 0.00057 | 0.00471 | no |
| 2 | 0.29 Hz | 0.00219 | 0.00060 | 0.00326 | no |
| 3 | 0.41 Hz | 0.00156 | 0.00064 | 0.00268 | no |
| **6** | **0.77 Hz** | **0.00083** | **0.00083** | **0.00214** | **yes** |
| 9 | 1.14 Hz | 0.00056 | 0.00107 | 0.00214 | yes |
| 12 | 1.51 Hz | 0.00042 | 0.00133 | 0.00230 | yes |
| 18 | 2.28 Hz | 0.00028 | 0.00190 | 0.00283 | no |
| 24 | 3.04 Hz | 0.00021 | 0.00246 | 0.00347 | no |

Too slow and the polarization bound dominates, because an RC branch follows
a slow probe and its impedance lands in the fitted slope. Too fast and the
loop lag and current-channel delay attenuate the realized excitation, so the
noise term dominates. **The optimum is where the two are equal**, and at 6
cycles they are equal to two significant figures.

## 3. The arm comparison, at the preregistered settings

| model / arm | realized `S_II` | lever arm | energy | swept separation | certificate |
|---|---|---|---|---|---|
| P0 passive | 1 | — | 0.00 | 0.00 | insufficient excitation, 50/50 |
| P1 palindromic | 9095 | +0.033 s | 40.74 | 0.75 | certified 50/50 |
| P2 compensated | 11585 | −0.028 s | 45.85 | 0.75 | certified 50/50 |
| P3 shaped | 286 | +0.009 s | **4.00** | 0.50 | certified 50/50 |
| P4 feedback | 10168 | **−0.022 s** | 40.74 | 0.75 | certified 50/50 |
| P5 random safe | 6863 | +0.038 s | 35.39 | 0.75 | certified 50/50 |
| P6 mission | 2993 | −0.641 s | **0.00** | 0.50 | certified 50/50 |
| P7 oracle (**not executable**) | 21458 | +0.018 s | 64.00 | 0.75 | certified 50/50 |

Simple and one-RC plants give the same separation verdicts; the estimates
differ (most for P6, by 0.0064 Ω), but the binary separation test is too
coarse to show it.

## 4. Hypotheses

| | verdict |
|---|---|
| H1 command/realization gap | **supported** — P6's realized lever arm is −0.641 s |
| H2 compensable gap | **supported on mechanism, rejected on outcome** |
| H3 diagnostic value | **supported over passive, not over the naive palindrome** |
| H4 conservative certification | **supported** — 0 false certifications in 2000 adversarial draws |
| H5 open-set integrity | **supported** — 10/10 unknown at the largest unmodelled fault |
| H6 mission comparison | **probing beats waiting here**, 0.75 against 0.50 |

**H2 is the interesting one.** P4 does exactly what it claims: it cuts the
realized lever arm from +0.033 s to −0.022 s and raises `S_II` by 12%. The
separation does not move, because `B_drift` is only 9% of P1's total error
while `B_dynamic` is 59%. **The compensation improves a term that is not
binding.** Each arm is limited by a different term: P1 and P4 by
polarization, P6 by drift aliasing (0.00511 of a 0.00971 total, at 97% of
its budget), P3 by noise because it spends a tenth of the energy.

## 5. Certificate integrity

| check | result |
|---|---|
| adversarial draws over RC values, lag, bias, scale, delay, quantisation, dropout and drift | 2000 |
| certified | 1921 |
| **false certifications** | **0** |
| worst |error| as a fraction of the run's own bound | 0.928 |
| median | 0.332 |

The bound is used, not slack: the worst case consumes 93% of it. A bound
never approached would be safe and uninformative.

| control | result |
|---|---|
| large voltage step at constant current | not certified (−0.80 V moved, insufficient excitation) |
| unmodelled ringing at 0.40 V | unknown / model mismatch, 10/10 |
| clipped action | `CLIPPED_CERTIFICATE_INVALID` |
| aborted action | `ABORTED_INCOMPLETE` |
| undeclared `r1_max`, `tau1_min_s` or `scale_error_max` | `MODEL_MISMATCH_LIMITED` naming the unbounded term |

## 6. What was falsified during the work

Six things, all mine, listed in full in `COUNTEREXAMPLE_LOG.md`. The two that
changed a reported number:

* **P4 never ran.** The feedback arm's plumbing kept a state dict nothing
  ever wrote, so the accumulator saw zero samples and the arm was a
  byte-identical copy of P1, reported under its own name for a whole pilot.
* **The P3 search grid did not contain the optimum.** It offered 2, 3 and 5
  cycles; the optimum is 6 to 12. A search cannot find what its grid excludes.

## 7. The multi-RC pack with hysteresis

Added after the first campaign, as the experiment predicted to break the
certificate. It did, in a way I did not predict.

**The prediction failed.** A richer pack was expected to trip the open-set
detector on healthy data. It did not: the clean residual ratio came in at
1.84 against the one-RC pack's 2.17.

**A genuine false certification was found instead.** A pack with 0.12 V of
voltage hysteresis returned `CERTIFIED_IN_MODEL` with an estimate **4.81
times its own declared bound** from the truth, and the residual check sat at
2.39 of a 3.0 tolerance. The cause is structural: hysteresis voltage follows
`sign(I)`, which is nearly in phase with the current, so least squares
attributes it to resistance and the fit looks clean.

> A nuisance correlated with the regressor is absorbed into the slope and
> leaves no residual. A residual check is blind to exactly the errors that
> matter most.

**A sixth budget term closes it**, derived from the realized current:
`|B_hysteresis| <= M_max |cov(sign(I), I)| / var(I)`, which is exactly zero
when the current never reverses.

| envelope | draws | certified | false certifications | worst ratio |
|---|---|---|---|---|
| inside the declared bound | 400 | 331 | **0** | 0.43 |
| outside it | 400 | 290 | 11 | 1.53 |

**And the limit that remains.** The certificate is told `M`, never measures
it. An under-declared bound produces confident wrong answers and no test
here detects it. A cross-probe consistency check was built and **does not
work**: measured disagreement-to-bound ratios of 0.33, 0.55 and 0.85 across
three probe pairs, never reaching one, because the same hysteresis that
creates the disagreement also inflates the bound on the reversing probe.

This is reported as a null result. It is also the concrete reason the first
item below is not supported.

## 8. What this does not establish

Fixed in the preregistration before the run, and unchanged:

1. **robust operation across real battery chemistries** — every pack
   parameter is synthetic; there is no cell data here and none obtainable;
2. **reliable behaviour on hardware** — E0;
3. **novelty** — scholarly access denied by organization policy, rechecked;
4. **production integration** — forbidden by the owner authorization;
5. **any formal safety guarantee** — Monte Carlo is not a proof.

The clean-data residual ratio is 2.17 against a tolerance of 3.0, so the
open-set detector has thin headroom on this pack already. `tau1_min` is the
single most load-bearing declaration in the budget: if a real pack's
polarization is faster than declared, `B_dynamic` is under-bounded and the
certificate is optimistic.
