# Everything that went wrong, in order

Append-only. Six of my own claims or instruments failed during this campaign
and all six are here. "We fixed it" is a different fact from "it was right".

## RC-1 — the lag fit was biased by a factor of 2.3

`estimate_lag` fitted `-ln(1 - fraction) = t/tau` by least squares and
returned **0.569 s against a plant lag of 0.250 s**. The linearisation
diverges as the response approaches its asymptote, so the noisiest and least
informative samples at the end of the window carried the largest weight.

A compensator built on a `tau` 2.3× too large over-corrects and demands
authority it does not need, and the failure would have been reported as a
failure of the compensation idea rather than of the fit.

**Fixed** by direct residual minimisation over a `tau` grid. Known-answer
check across three plant lags now recovers 0.71 to 0.93 of truth; it
**under**-estimates, which under-compensates, which is conservative.

## RC-2 — the polarization bound made the certificate refuse everything

`B_dynamic` used the worst case `R1_max` outright. With `R1_max` equal to the
target change, **no excitation of any kind could clear the margin**, and the
campaign's own negative control — an 8 A cosine that must certify — refused.

The control was right and the certificate was not broken. The error model was
too crude for waveform design to matter at all.

**Fixed** by deriving the bound from the realized spectrum against a declared
lower bound on `tau1`: `R1_max / sqrt(1 + (2 pi f_eff tau1_min)^2)`. This is
the change that made the campaign's main result possible, and it was forced
by a control rather than noticed by inspection.

## RC-3 — P3 optimised a proxy and chose a probe the certificate rejected

The objective penalised a shortfall against `S_II_min` and the drift lever
arm. `S_II_min` is only 36.9 here, so nearly every waveform cleared it, the
term went to zero, and the objective reduced to "use as little energy as
possible". It selected a 2 A chirp over 2 s, which the certificate refused as
`MEASUREMENT_LIMITED` with a lever arm of 0.591 s. **The arm scored zero
certificates in the pilot.**

The binding constraint was never `S_II_min`; it is the total error budget. A
search that optimises a proxy for the thing it is judged on will find the
corner where the two disagree, and this one did.

**Fixed** by scoring candidates with `rcec.certify` itself. P3 then certifies
at 4.0 A·s against P1's 40.7.

## RC-4 — the feedback arm never ran, for a whole pilot campaign

**The worst one.** `_run_with_feedback` kept a `state` dict that nothing ever
wrote, so `probe.observe` was never called, the accumulator saw **0 samples**,
and P4 produced a realized current **byte-identical to P1** — while being
reported in the results table under its own name with its own row.

Caught by noticing P4's numbers matched P1's exactly and checking
`probe.report()`, which said `samples_seen: 0`.

**Fixed** by adding a causal per-sample `observer` to the plant, which
required moving the measurement chain inside the integration loop. The noise
arrays are still drawn in one block from the same independent streams, so the
restructure is byte-identical and a test asserts it.

## RC-5 — and then the feedback law made things worse

With the plumbing fixed, P4 capped **330 of 401** corrections and left a
realized lever arm of 0.132 s, **four times worse** than the open-loop probe
it was meant to improve. The correction divided the outstanding imbalance by
`0.5 * remaining` and called that a lever, and it consulted a method on the
moment snapshot that does not exist, so it silently took its own fallback
branch every tick.

**Fixed** by deriving the law: a correction `c(t) = -g (t - t_mid)` changes
`S_tI` by `-g sum_{remaining}(t_k - t_mid)^2`, so the cancelling gain is
`g = S_tI_so_far / capacity`. P4 now caps **4** corrections and reaches a
lever arm of −0.022 s against P1's +0.033 s.

## RC-6 — the search grid did not contain the optimum

P3's candidate set offered 2, 3 and 5 cycles. The certificate's own error
decomposition predicts the best probe sits where the polarization bias equals
the noise term, which on this pack is **6 to 12 cycles**. The sweep confirmed
it: 6 cycles resolves 0.005 Ω and 3 cycles does not, at identical energy.

**A search cannot find what its grid excludes.** The grid was widened and a
test now asserts it spans the optimum.

## RC-7 — two of my own tests were wrong, not the code

`test_control_14` asserted that stretching the timebase leaves the lever arm
unchanged; it doubles it. `test_control_16[s_ti_sign]` negated and reversed
the timebase, which leaves it increasing and flips nothing. Both corrected,
with the reasoning in the test body.

## What did NOT go wrong

Zero false certifications in 2000 adversarial draws, and the bound is used
rather than slack: worst case 0.928 of its own limit, median 0.332.
