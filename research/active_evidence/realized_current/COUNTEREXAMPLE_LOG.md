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

---

# Multi-RC pack with hysteresis

## RC-8 — my prediction about the richer pack was wrong

`MODEL_VALIDITY_ENVELOPE.md` predicted that a multi-RC pack with hysteresis
would trip `UNKNOWN_OR_MODEL_MISMATCH` on healthy data because the clean
residual ratio was already 2.17 of a 3.0 tolerance.

**It went the other way.** The clean ratio on the multi-RC pack was 1.84,
LOWER than on the one-RC pack, because the branch parameters happened to be
gentler. A prediction that fails in the safe direction is still a failed
prediction and is recorded as one.

## RC-9 — my first hysteresis test was vacuous

Hysteresis only moves when the current REVERSES SIGN. With a 20 A base
current and an 8 A probe the current never went below 13 A, the hysteresis
state sat at exactly +1.0000 for the entire window, and the term was a
constant the regression absorbed into the intercept. Three of my four
configurations were testing nothing.

Measured `h` range by base current and amplitude:

| base | amplitude | min current | `h` range |
|---|---|---|---|
| 20 A | 8 A | +12.99 A | [+1.0000, +1.0000] |
| 5 A | 15 A | −5.32 A | [+0.8997, +1.0000] |
| 5 A | 15 A, γ=3000 | −5.32 A | [−0.3493, +1.0000] |

## RC-10 — a false alarm on a healthy multi-RC pack

At 22 A and 3 cycles the certificate refused a **healthy** pack as
`UNKNOWN_OR_MODEL_MISMATCH` (residual ratio 3.06) while its estimate was
0.00163 Ω from truth, comfortably inside the bound it would have issued.

The predicted residual counted sensor noise only, while the budget already
declared a polarization branch through `B_dynamic`. **Conflating "a mechanism
nobody declared" with "a declared mechanism I chose a bad probe for"** is the
error.

**Fixed** by adding the declared polarization to the predicted residual in
quadrature. Verified in both directions: every healthy multi-RC case now
certifies with its error inside its bound, and detection of genuine mismatch
improved, catching 0.10 V of ringing where it previously needed 0.20 V.

## RC-11 — A GENUINE FALSE CERTIFICATION, and the term that was missing

A multi-RC pack with M = 0.12 V of hysteresis and fast relaxation produced:

| | |
|---|---|
| state | **`CERTIFIED_IN_MODEL`** |
| estimate | 0.032167 Ω |
| truth | 0.039998 Ω |
| signed error | **−0.007831 Ω** |
| declared bound | 0.001627 Ω |
| error as a multiple of its own bound | **4.81×** |
| residual ratio | 2.39 against a tolerance of 3.0 |

The residual check did not see it, and no tightening of its tolerance would
have. The reason is structural:

> **A nuisance that is correlated with the regressor is absorbed into the
> slope and leaves no residual.**

Hysteresis voltage follows `sign(I)`, which for a reversing probe is nearly
in phase with `I`, so least squares attributes it to resistance and the fit
looks clean. A residual check is blind to exactly the errors that matter most.

**Fixed** by deriving a sixth budget term from the realized current:

```
|B_hysteresis| <= M_max * |cov(sign(I), I)| / var(I)
```

Zero when the current never reverses, which is correct. Verified: declared
truthfully at 0.15 V the case now returns `MODEL_MISMATCH_LIMITED`; a
non-reversing probe earns exactly 0.000000; an undeclared bound returns
`UNBOUNDED_TERM:B_hysteresis` and fails closed.

## RC-12 — the limit that cannot be closed from here

Declaring 0.05 V for a pack that has 0.12 V still yields a certified estimate
wrong by more than its bound. **Nothing inside the certificate detects this,
because the certificate never measures M — it is told M.**

Measured over 400 draws each:

| envelope | draws | certified | false certifications | worst ratio |
|---|---|---|---|---|
| inside declared | 400 | 331 | **0** | 0.43 |
| outside declared | 400 | 290 | **11** | 1.53 |

**The cross-probe check does not rescue it.** A probe that never reverses the
current has a zero hysteresis lever and one that reverses heavily has a large
one, so their estimates should disagree if the declaration were too small.
Measured ratio of disagreement to combined bound, at a declared 0.05 V:

| true M | disagreement | combined bound | ratio | detected |
|---|---|---|---|---|
| 0.05 | 0.00315 | 0.00945 | 0.33 | no |
| 0.08 | 0.00524 | 0.00945 | 0.55 | no |
| 0.12 | 0.00801 | 0.00945 | 0.85 | no |

It never fires, at any over-declaration where the certificate still
certifies, because the same M that creates the disagreement also inflates the
declared bound on the reversing probe. **The two scale together.** Three
different probe pairs were tried and all three behave the same way.

**This is reported as a null result, not omitted.** The hysteresis
declaration must come from cell characterisation. This repository has none,
and this host cannot obtain any.
