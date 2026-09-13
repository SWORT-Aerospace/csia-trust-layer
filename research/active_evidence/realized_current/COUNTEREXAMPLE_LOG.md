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
**under**-estimates.

> **AMENDED 2026-09-13.** This entry originally continued "which
> under-compensates, which is conservative." **That claim is withdrawn.** See
> RC-14.

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

---

# Repair phase, 2026-09-13

## RC-13 — the shipped polarization bound is unsound, by a factor of five

`B_dynamic` shipped as `R1_max / sqrt(1 + (2 pi f_eff tau_min)^2)`. Measured
against direct simulation of the branch it bounds, on the three-cycle
palindromic probe the campaign's headline arms used:

| | |
|---|---|
| committed bound | 0.00155 ohm |
| true worst case over the declared envelope | 0.00797 ohm |

**Understated fivefold, which is the false-certification direction.** Two
independent errors: it used the magnitude of the branch impedance where a
regression sees only its in-phase part, and the entire frequency-domain
argument assumes a steady state the branch never reaches over a window
shorter than its time constant.

A Cauchy-Schwarz transient term was tried: sound for oscillating probes,
**violated in 80 of 1200** (waveform, R1, tau, initial condition)
combinations, because the transform's implicit periodic extension
misrepresents a ramp.

**Replaced by direct evaluation over the declared envelope.** Zero violations
in 1800 draws, tightness 0.57 to 0.90, 40 ms per bound, and it uses only the
waveform.

**This invalidates part of MX-039.** A three-cycle probe now totals 0.01065
against an allowed 0.01000 and does not certify. P1, P2, P4, P5 and P7 all
used it. The arm comparison must be re-run.

## RC-14 — "conservative" withdrawn for lag underestimation

MX-039 said underestimating the loop lag is conservative because it
under-compensates. **Asserted, not shown.** A signed sweep over assumed/true
ratios from 0.25 to 4.0 measured:

* the achieved error is **not monotone** in the lag ratio;
* at a four-fold underestimate the **realized drift lever changes sign**, at
  true lags of 0.10 s and 0.25 s. A sign change puts the bias on the other
  side of the truth, which is not what conservative means.

What survives, as a fact about the grid rather than a property: worst error
under underestimation 0.0196 ohm, under the exact lag 0.0204 ohm, under
overestimation 0.0232 ohm.

## RC-15 — P3's pilot failure classified: optimizer, not infeasibility

RC-3 asserted a cause from one observation. The binding-constraint table over
all 120 grid candidates on the diagnostic partition settles it:

| first binding condition | candidates |
|---|---|
| model mismatch / error budget | 76 |
| **certified** | **24** |
| excitation | 20 |

**The feasible set is not empty.** The cheapest feasible witness is a
palindromic probe, 4 A, 8 s, 6 cycles. The repaired objective finds it. The
reconstructed pilot objective selects a 2 A, 2 s chirp that does not certify.

So the failure was **objective misspecification, a form of optimizer
failure** — not mathematical infeasibility, not prediction/realization
mismatch, and not a certificate defect. RC-3's conclusion was right and its
evidence was one data point; this is the table.

It also confirms RC-3's secondary claim with a count rather than an anecdote:
excitation binds for only 20 of 120 candidates, so `S_II_min` was never the
constraint that mattered.

## RC-16 — the pilot artifact cannot be recovered, only reconstructed

`git log -S` over the campaign file finds no commit containing the failing
objective. The pilot ran from uncommitted working state. Everything about it
in this repository is **`RECONSTRUCTED_NOT_RECOVERED`**, rebuilt from RC-3's
wording and re-run deterministically on the diagnostic partition. It is
labelled that way in `results/RCEC_DIAGNOSTICS.json` and must not be cited as
a recovered original.

## RC-17 — a limit I recorded was measured under the unsound bound

MX-040 recorded that an under-declared hysteresis bound produces certified
estimates wrong by more than their bound, with no internal test able to catch
it. **That was measured with the polarization bound RC-13 shows to be
unsound.** Re-measured with the corrected bound and a six-cycle probe, the
window closes on that case: at 2.4x over-declaration the estimate sits inside
the correctly larger bound, and at 4x the residual check routes it to
`UNKNOWN_OR_MODEL_MISMATCH`.

**This retires one measurement, not the limit.** The 400-draw hunt that
produced "11 false certificates in 290" also ran under the unsound bound and
has to be repeated across the whole envelope before anything stronger is
said.

---

# Amended locked campaign, 2026-09-13 — run once

## RC-18 — P7 is not a ceiling. The oracle claim is falsified.

P7 was declared a non-deployable oracle upper bound. On locked data it has
the **highest realized excitation (21445), the lowest drift lever (0.018) and
the worst detection frontier of every arm (0.040 ohm)**, against 0.006 for
P2.

It maximises the second moment of current, which is not the objective. Its
energy sits at the window fundamental near 0.125 Hz, where the polarization
branch follows it completely.

> **A quantity that upper-bounds excitation does not upper-bound
> resolution.**

The claim is withdrawn. P7 stays in the tables, marked not deployable, as a
measured counterexample to its own description.

## RC-19 — the resolution margin cannot distinguish plant models

Median `M_R` is identical to twelve decimal places across simple, one-RC and
multi-RC in all 2012 comparable cells, and `B_total` takes exactly one value
per cell.

By construction: `M_R` is built from the **declared envelope** and the
**realized current**, and the realized current is set by the control loop,
which the polarization branch barely affects. The margin measures **what the
certificate can bound, not what the plant does.**

The arm comparison under a common envelope stands. **The
simple-versus-one-RC comparison is withdrawn before being reported**, because
this campaign cannot make it.

## RC-20 — the drift interaction is real and its scalar is undefined

At elevated drift, P2 and P3 collapse from 0.006 and 0.010 to **never**,
while P4 holds at 0.010. The best arm at nominal drift is the most fragile.

The preregistered scalar `delta_interaction` came out **not a number**,
because "never" encodes as infinity and the difference of two infinities is
undefined. The interaction is reported as the table. No number is quoted in
its place and the scalar is not redefined after the fact.

## RC-21 — the unknown-fault detector has a floor

Unmodelled ringing at 0.10 V is **certified**, at 0.40 V routed to
`UNKNOWN_OR_MODEL_MISMATCH`. A small unmodelled dynamic is absorbed into the
estimate. The routing works at the top of the range tested and there is a
band below it where it does not.

## RC-22 — a commit went in with a red test

The runner-guard commit was made while
`test_the_locked_runner_does_not_search_or_tune_at_run_time` was failing on a
case-sensitive string assertion, because a shell pipeline masked pytest's
exit status. Caught and fixed in the next commit, before the seal was opened.
Recorded rather than amended away: the guard suite must be green before a
locked partition is touched, and for one commit it was not.
