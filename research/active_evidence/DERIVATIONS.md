# Derivations, and the one that was wrong

Everything here is a local, linear, two-parameter analysis of one relation.
None of it is a theorem, none of it is new, and the prior-art search that
would say what is already known could not be run — see `PRIOR_ART_MATRIX.md`.

## 1. The model

Over a window short enough that open-circuit voltage `E` and internal
resistance `R` are approximately constant,

```
V_k = E - I_k R + eps_k
```

which as a least-squares regression on the design `[1, -I]` has two
parameters. Three separate things stop `R` being recovered, and they fail in
different ways.

## 2. Attenuation, and why a hover cannot be fixed with more data

The regressor is a MEASURED current, carrying noise `sigma_I`. Writing the
true current as `I_true` and the measurement as `I_meas = I_true + u`:

```
cov(-I_meas, V) = R var(I_true) + d cov(t, I_true)
var(I_meas)     = var(I_true) + sigma_I^2
```

so the ordinary least-squares slope converges not on `R` but on

```
lambda = var(I_true) / (var(I_true) + sigma_I^2)        the attenuation
E[R_hat] = lambda * (R + d * cov(t, I) / var(I))
```

At a steady operating point `var(I_true) -> 0`, so `lambda -> 0` and
`R_hat -> 0` **whatever `R` is**. This is a bias and averaging does not
touch it.

It is sharper than "the regressor is rank deficient". A noisy hover has
design rank **2**, not 1: sensor noise makes the columns independent. The
textbook rank test passes and the estimate is confidently wrong.
`tests/test_identifiability.py::test_rank_is_the_wrong_diagnostic_and_the_module_says_so`
asserts exactly that pair of facts.

Measured, at `R = 0.040`: a 5 s hover and a 60 s hover both return an
estimate within 25% of zero, and twelve times the data does not reduce the
error. If it had, the effect would be variance and this section would be
wrong.

## 3. Drift aliasing

With `E(t) = E0 - d t` the fitted slope acquires `d * cov(t, I) / var(I)`.
A probe whose current correlates with time aliases the drift straight into
the resistance. A ramp is the worst case and gets worse the longer it runs:
over windows of 2, 5 and 20 s the predicted estimate rises monotonically and
at 20 s exceeds three times the true `R`.

**A profile symmetric about the window midpoint has `cov(t, I) = 0` exactly**,
at any amplitude and any window, because each sample pairs with its mirror.
Measured at 1e-16 for every probe in the library. §6 records what happened to
that guarantee when it met a closed loop.

## 4. The combined mean, verified

```
E[R_hat] = lambda * (R + d * cov(t, I) / var(I))
```

Checked against Monte Carlo on a generator written inside
`tests/test_identifiability.py`, which imports nothing from the component
simulator. Worst absolute error over 18 shape/window/amplitude combinations
at 4000 trials each:

| quantity | value |
|---|---|
| worst absolute error | 2.1e-05 ohm |
| spread of estimates across the grid | 0.037 to 0.137 ohm |

The spread matters: a formula agreeing with 18 cases that were all near
`R` would prove only that it returns something near `R`. The grid exercises
the bias terms hard enough to move the answer by a factor of three.

## 5. The scatter, and the expression this work falsified

The textbook slope variance is

```
sd(R_hat) = sigma_V / sqrt(sum (I - Ibar)^2)                      [NAIVE]
```

An earlier revision of `identifiability.py` asserted it and its docstring
claimed Monte Carlo agreement within 1.5%. **Writing the Monte Carlo
falsified it.** Over 108 cases in three noise regimes the naive expression
was optimistic by up to **85%**.

It is wrong for two reasons, both consequences of a measured regressor:

* substituting `I_true = I_meas - u` makes the effective residual
  `eps_V - r u`, so the CURRENT noise enters scaled by the slope being
  estimated. Drift aliasing can make that slope an order of magnitude larger
  than `R`, and the term then dominates;
* the denominator is itself random, so `R_hat` is a ratio of random sums
  rather than a linear function of the data.

The replacement is the delta-method expansion of that ratio, carrying the
effective slope `r_det = R + d cov(t,I)/var(I)`, the drift component
orthogonal to the current, and the variance of the denominator:

```
A = N var(I_true),  B = N sigma_I^2,  lambda = A/(A+B),  r = lambda r_det
var_w = max(d^2 var(t) - (d cov(t,I)/var(I))^2 var(I), 0)

Var(R_hat) = [ r_det^2 sigma_I^2 A + sigma_I^2 N var_w
               + sigma_V^2 A + N sigma_I^2 sigma_V^2
               - 2 r (2 r_det sigma_I^2 A)
               + r^2 (4 sigma_I^2 A + 2 N sigma_I^4) ] / (A+B)^2
```

| expression | worst deviation from Monte Carlo, 108 cases |
|---|---|
| naive | 85% (optimistic) |
| delta method | 2.2% |

The direction is what makes it worth the extra terms. The naive form reports
**less** scatter than the estimator has, so a requirement built on it would
authorise a probe that cannot deliver. `test_the_naive_scatter_formula_is_optimistic`
keeps the falsified expression alive and re-measures it on every run.

## 6. Where the symmetry guarantee stops

§3's guarantee is about the COMMANDED profile. The campaign measured what the
plant actually drew:

| probe | realised lever arm | realised drift bias |
|---|---|---|
| triangle_soft | -1.138 s | -0.0052 ohm |
| doublet | -0.943 s | -0.0043 ohm |
| triangle | -0.860 s | -0.0040 ohm |
| step_hold | -0.584 s | -0.0027 ohm |
| burst_2hz | +0.019 s | +0.00009 ohm |
| burst_wide | +0.004 s | +0.00002 ohm |

The commanded lever arm is ~1e-16 for all six. The vehicle is a closed loop
with integral action, its current response lags the command, and a lag turns
a palindrome into something that is not one. `triangle_soft`'s realised bias
is **larger than the smallest change the campaign tried to resolve**.

What survives is narrower and still useful: **a multi-cycle symmetric burst
keeps the property, because the lag averages across cycles; a single
excursion does not.** For every other shape the lever arm must be measured
from the realised current with `ExcitationStats.from_measured`.

## 7. The inversion

Given a change `delta_r` worth resolving, a confidence `k`, a bias budget
fraction `b` and the platform's measured noise, solving the three error
expressions for the excitation statistics gives three necessary conditions:

```
attenuation   var(I) >= sigma_I^2 (r_ref / (b delta_r) - 1)
variance      std(I) sqrt(N) >= k sigma_eff / delta_r,
                 sigma_eff = sqrt(sigma_V^2 + r_ref^2 sigma_I^2)
drift         |cov(t,I)/var(I)| <= b delta_r / d
```

No search, no simulator, no fitting. `bias_fraction` is a declared
engineering budget reported in the requirement, not a tuned value.

The three scalars are guides for a human. `ProbeRequirement.met_by`
evaluates the **full** delta-method scatter rather than the scalar form,
because the scalar form assumes the effective slope equals `r_ref` and drift
aliasing can make it much larger. Where the two disagree the exact one
decides.

## 8. What this excludes

No RC dynamics, no temperature coupling, no cell imbalance, no
state-of-charge curvature within the window, Gaussian additive noise on both
channels, and a first-order expansion that degrades as `sigma_I` approaches
`std(I)` — which is the regime where the attenuation condition already
refuses the probe. `SIMULATOR_VALIDITY_ENVELOPE.md` carries the rest.
