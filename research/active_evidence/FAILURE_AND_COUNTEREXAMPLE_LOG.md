# Everything that went wrong, in the order it went wrong

Append-only. Nothing here is removed once the mistake is fixed; "we fixed it"
is a different fact from "it was right".

## AE-F1 — the module asserted a Monte Carlo result that had never been run

`csia_active_evidence/identifiability.py` was written with a docstring
stating *"Measured agreement: mean within 7e-5 of prediction across 12
shape/window combinations, and sd within 1.5%."* **The test that would have
measured it did not exist.** The numbers came from an exploratory script run
in a scratch directory and never committed, which is precisely the failure
`docs/CURRENT_PROGRAM_STATE.md` §6 exists to prevent: *no result may live
only inside a chat transcript*.

**Found by:** writing `tests/test_identifiability.py` in order to make the
docstring true.
**Verdict:** the mean claim survived and improved (2.1e-05, better than the
7e-5 asserted). **The scatter claim was false** — see AE-F2.
**Fixed:** the docstring now quotes only what the committed test measures.

## AE-F2 — the textbook slope variance is optimistic by up to 85%

The module used `sd(R_hat) = sigma_V / sqrt(sum (I - Ibar)^2)`, the standard
expression, and claimed 1.5% agreement. Monte Carlo over 108 cases in three
noise regimes measured up to **85% optimism**.

**Why it matters more than an accuracy figure:** the error is in the
dangerous direction. A requirement inverted from an over-confident scatter
authorises a probe that cannot deliver, and the caller runs it.

**Cause:** the regressor is measured, so (a) the current noise reaches the
residual scaled by the slope being estimated, and (b) the estimate is a ratio
of random sums, not a linear function of the data.
**Fixed:** delta-method expansion, worst deviation 2.2% over the same 108
cases. The falsified expression is **kept** as `naive_estimate_sd` and
re-measured every run by
`test_the_naive_scatter_formula_is_optimistic`, so the correction cannot
silently regress.

## AE-F3 — the deconvolution accepted a steady hover about half the time

`ExcitationStats.from_measured` subtracts the channel noise power from the
measured variance and originally refused only when the remainder was
non-positive. A sample variance is itself an estimate: under pure noise the
remainder is positive roughly half the time. Measured, over 20 000 draws:

| N | fraction of pure-noise windows with a positive remainder |
|---|---|
| 100 | 0.452 |
| 500 | 0.473 |
| 1000 | 0.479 |

So a steady hover — the exact case the module exists to refuse — would have
been accepted as excited on about half of all windows, and reported a lever
arm computed from noise.

**Found by:** `test_a_window_with_no_excitation_above_the_noise_is_refused`
failing on the first run.
**Fixed:** the excess must clear `k_sigma` times the sampling standard
deviation of the variance estimate, `sigma_I^2 sqrt(2/N)`. That is
chi-squared arithmetic, not a tuned threshold.

## AE-F4 — a sine probe does not have a zero drift lever arm

A test asserted that a sine probe is not drift-dominated. It is: 20 s of
0.5 Hz leaves `cov(t,I)/var(I) = -0.0795 s`, small but larger than the
3-sigma scatter of a strong probe, so drift remains the largest single term.
Raising the amplitude divides the lever arm by the amplitude; it never
reaches zero.

**The test was wrong, not the code.** Correcting it produced the design rule
the probe library is built on: a profile symmetric about the window midpoint
has `cov(t, I) = 0` **exactly**, measured at 1e-16, at any amplitude and any
window.

## AE-F5 — and that rule is about the command, not the current

`probes.py` claimed the symmetric design *"removes the one error term whose
magnitude depends on a quantity that is never known precisely"*. The campaign
measured the realised current in the plant:

| probe | commanded lever arm | realised lever arm | realised drift bias |
|---|---|---|---|
| triangle_soft | -1.2e-15 s | -1.138 s | -0.0052 ohm |
| doublet | +2.2e-16 s | -0.943 s | -0.0043 ohm |
| triangle | +8.4e-16 s | -0.860 s | -0.0040 ohm |
| step_hold | -5.9e-17 s | -0.584 s | -0.0027 ohm |
| burst_2hz | -1.8e-16 s | +0.019 s | +0.00009 ohm |
| burst_wide | -6.5e-16 s | +0.004 s | +0.00002 ohm |

The closed loop lags the command and a lag breaks the palindrome.
`triangle_soft`'s realised bias exceeds the smallest change the campaign
tried to resolve.

**Why the campaign's own cell verdicts could not have caught it:** the
campaign scores a differential comparison, the same probe on two packs, and a
bias common to both cancels. It was caught by measuring the realisation
separately and comparing it against the prediction — an extra measurement
that existed only because the design rule was stated sharply enough to be
checkable.

**Fixed:** the docstring now states the narrower rule that survives — a
multi-cycle symmetric burst keeps the property, a single excursion does not —
and both the correction and this table are pinned by
`test_the_realisation_finding_is_recorded_and_not_softened`.

## AE-F6 — an invented constant, optimistic by a factor of 3.6

`CURRENT_PER_AMP_OF_VZ` was set to **9.0** A per m/s as a "planning default",
which is a polite way of saying it was made up so there would be something to
compute with. The campaign measured **2.519** on the reference platform.

Every excitation statistic derived from the guess overstated the probe's
power by 3.6x, which is the direction that authorises probes that cannot
work.
**Fixed:** the constant is the measured value, and
`test_the_amps_per_volt_constant_is_the_measured_one` couples it to the
campaign artifact so it cannot drift back into a guess.

## AE-F7 — one false negative, reported

`triangle` at `delta_r = 0.005` fails the variance condition and resolves
anyway (gap-to-scatter 4.16 against a threshold of 3). The requirement is
**conservative** there, which is the safe direction and does not falsify the
prediction — the preregistration fixed that reading in advance.

The cause is measurable: the closed loop amplifies the realised excitation by
1.46x to 1.76x over the open-loop linear prediction, because holding a
commanded velocity against integral action costs more current excursion than
the static gain predicts. The requirement is computed from the commanded
profile and therefore understates the probe.

Stable across seed counts: scatter 0.00119, 0.00134 and 0.00129 at 5, 20 and
40 seeds. It is a real property, not sampling noise.

## AE-F8 — the prior-art search could not be run

All four scholarly endpoints (`arxiv.org`, `api.semanticscholar.org`,
`api.crossref.org`, `api.openalex.org`) returned HTTP 000; the proxy reports
`connect_rejected` — *gateway answered 403 to CONNECT*. This is the same
denial already recorded as publication blockers 1, 3 and 4 in
`docs/CURRENT_PROGRAM_STATE.md`.

**Consequence, and it is not negotiable:** the search is `INCOMPLETE` and
**no novelty, priority or originality claim may be made for any part of this
work**. `PRIOR_ART_MATRIX.md` carries the refusals verbatim and the reading
list that has not been done, including the one reference the repository
already knows is closest: Matei et al., ACM TCPS 8(1) 2024,
DOI 10.1145/3631612, which `forge/PRIOR_ART_REQUIRED.md` records as covering
*"interventions to disambiguate uncertain diagnosis"*.

## AE-F9 — a governance conflict, not a defect, recorded anyway

`docs/CURRENT_PROGRAM_STATE.md` §1 lists **energy domain** among the
FORBIDDEN work areas while the dual-paper freeze holds, and states that it
governs where documents disagree. Pack internal resistance is the energy
domain.

The work proceeded on the program owner's explicit instruction. It touches no
frozen path, changes no frozen behaviour, adds nothing to `csia/`, and makes
no paper, product or readiness claim. `PREREGISTRATION.md` §0 records the
conflict and the narrowing; this entry records that it was recorded rather
than routed around.
