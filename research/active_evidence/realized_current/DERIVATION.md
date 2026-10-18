# Derivations for the Realized-Current Excitation Certificate

Nothing here is a theorem and nothing here is claimed to be new. The
prior-art search could not be run; see `EXTERNAL_SOURCE_REQUEST.md`.

## 1. The estimator and what it is blind to

Over a window short enough that open-circuit voltage and resistance are
approximately constant,

```
V_k = E_k - R I_k + eps_V,k        measured current  Itilde_k = I_k + eta_I,k
```

regressed on `[1, -I]`. Define, **on the measured channel**,

```
S_II = sum (I_k - Ibar)^2          S_tI = sum (t_k - tbar)(I_k - Ibar)
```

`S_II` on the measured channel is inflated: `E[S_II_meas] = S_II_true + N
sigma_I^2`. The excitation condition is checked against the deconvolved
value, and `deconvolved_s_ii` returns `None` rather than a small positive
number when the remainder does not clear `k * sigma_I^2 * sqrt(2N)`, the
sampling error of the estimate itself. Sensor noise is not excitation.

## 2. The five bias terms

| term | form | bounded by |
|---|---|---|
| `B_drift` | `d * S_tI / S_II` | declared `d_max`, realized lever arm |
| `B_EIV` | `(1 - lambda) R`, `lambda = var_true/var_meas` | measured |
| `B_dynamic` | polarization seen by the regression | `R1_max / sqrt(1 + (2 pi f_eff tau1_min)^2)` |
| `B_mismatch` | current-channel scale error `s` | `R |s| / (1 - |s|)` |
| `B_sampling` | transport delay and quantisation | measured autocorrelation at the declared lag, plus `q^2/12` as extra regressor noise |

```
B_total = |B_drift| + |B_EIV| + |B_dynamic| + |B_mismatch| + |B_sampling|
```

**A union bound, not a root-sum-square.** The terms are not independent:
drift, polarization and a scale error all act on the same regression through
the same samples, and quadrature would assume a cancellation nobody has
shown. If `r1_max`, `tau1_min_s` or `scale_error_max` is undeclared the
corresponding term is `UNBOUNDED_TERM` and the state is
`MODEL_MISMATCH_LIMITED`. There is no path by which an unbounded term
becomes a zero.

## 3. `B_dynamic` — SUPERSEDED. See §3a.

> **The closed form described in this section was measured to be UNSOUND on
> 2026-09-13 and has been replaced.** It is retained here because it is what
> MX-039 and MX-040 were computed with, and removing it would make those
> artifacts unreproducible. Read §3a before relying on anything below.

The first version used `R1_max` outright. With `R1_max` equal to the target
change, **no excitation of any kind could clear the margin**, and the
campaign's own negative control refused. The certificate was not broken; the
error model was too crude for waveform design to matter at all.

A first-order polarization branch has impedance magnitude
`|Z1(f)| = R1 / sqrt(1 + (2 pi f tau1)^2)`, so a probe whose energy sits well
above `1/(2 pi tau1)` sees almost none of it. The bound therefore uses the
**realized current's power-weighted mean frequency** against a declared
**lower** bound on `tau1`. Lower is the conservative direction: a faster
polarization branch follows the probe more closely and contributes more.

Measured on the synthetic pack, whose true `tau1 = R1 C1 = 13.5 s`, against a
declared `tau1_min = 5 s`:

| probe | realized `f_eff` | `B_dynamic` |
|---|---|---|
| 8 A cosine, 3 cycles in 8 s | 0.408 Hz | 0.00155 ohm |
| mission manoeuvre, 0.1 Hz | 0.200 Hz | 0.00314 ohm |
| passive hover | — | condition never reached |

This is the one place where a better waveform earns a smaller error, and it
is why waveform design is worth doing at all.

## 3a. `B_dynamic`, corrected: the branch is evaluated, not approximated

The closed form in §3 understates the truth. Measured against direct
simulation of the branch it bounds, on a three-cycle palindromic probe over
an eight-second window with `R1` in [0.004, 0.020] and `tau` in [1, 40]:

| | |
|---|---|
| committed closed-form bound | 0.00155 ohm |
| true worst case | 0.00797 ohm |

**A factor of five, in the false-certification direction.** Two errors:

* `Re[Z1] = R1/(1 + (w tau)^2)`, not `R1/sqrt(1 + (w tau)^2)`. A regression
  attributes the IN-PHASE part of the branch voltage to resistance, not its
  magnitude;
* the whole frequency-domain argument assumes **steady state**. Over a window
  shorter than the branch's time constant it never reaches it, and the
  initial-condition transient dominates. On a 1.2 A/s ramp over 8 s with
  `tau = 13.5 s` the true apparent resistance is 0.0176 ohm, **larger than
  `R1` itself**, which no steady-state formula produces.

A Cauchy-Schwarz transient term was tried and is sound for oscillating probes
and violated for low-variance ones: 80 violations in 1200 combinations.

**No closed form is needed.** The branch is linear with one scalar state, so
`polarization.bound` integrates it over the declared envelope of `R1`, `tau`
and initial condition and takes the worst case. It uses **only the waveform**
— no fault label, no hypothesis, no outcome — and the signature has no
argument through which one could be passed.

Measured: **bounded over the declared discrete model grid** of 105 instances,
and **zero observed bound violations in 1,800 preregistered simulator
evaluations** sampled from the continuous envelope. Under an IID
interpretation the rule-of-three upper limit is `p < 3/1800 ≈ 0.00167`, which
is **not a formal guarantee**. Tightness 0.57 to 0.90, about 40 ms per bound.
Scope: `POLARIZATION_BOUND_SCOPE.md`. It
discriminates by a factor of 336 between a six-cycle palindromic probe and a
slow ramp.

**Consequence for the published arms.** Under the corrected bound a
three-cycle palindromic probe no longer certifies: total error 0.01065
against an allowed 0.01000. That is the probe P1, P2, P4, P5 and P7 all used
in MX-039, so **that arm comparison was computed on an unsound bound and
cannot stand as reported.**

## 4. The resolution rule

```
|B_total| + k * SE(Rhat)  <  c * |target change|,   c < 1 declared
```

Set separation is primary. `SE` enters as one term inside a declared margin
and never as a p-value: flight ticks are dependent, the action is adaptively
chosen, and optional stopping is where casual p-value logic fails.

## 5. The residual check, and why an error budget is not enough

A budget bounds the terms a model knows about. It says nothing about a
mechanism the model has no term for. `certify` therefore compares its own
fit residual against what the declared channel noise predicts,

```
expected residual RMS = sqrt(sigma_V^2 + R_ref^2 sigma_I^2)
```

and returns `UNKNOWN_OR_MODEL_MISMATCH` when the realized residual exceeds it
by more than the declared tolerance. Measured ratios on the synthetic pack:

| case | residual ratio | state |
|---|---|---|
| clean | 2.17 | certified |
| unmodelled ringing 0.05 V | 2.59 | certified |
| unmodelled ringing 0.20 V | 5.65 | unknown / model mismatch |
| open-circuit drift 0.02 V/s | 4.31 | unknown / model mismatch |
| genuine `R0` rise of 0.040 | 2.18 | certified |

The clean ratio is 2.17 rather than 1.0 because the polarization branch and
the curved open-circuit characteristic add structure the estimator has no
term for. **The margin to the tolerance of 3.0 is thin and that is a real
limitation**, recorded in `MODEL_VALIDITY_ENVELOPE.md`.

## 6. Command symmetry versus realized symmetry

A palindromic command has `S_tI = 0` in command space by construction. The
loop lags, and a lag breaks a palindrome. Measured previously as realized
lever arms up to -1.138 s against a commanded 1e-16 (AE-F5).

The lead compensator `u = w + tau dw/dt` inverts a first-order lag. Two
things stop it being free: differentiation amplifies noise and can demand
more authority than the vehicle has, and the inverse is only as good as
`tau`. The fitted `tau` recovers a known plant value within 7 to 29 percent and
under-estimates. **That is not the same as conservative**, and the word has
been withdrawn: a signed sweep measured the achieved error to be
non-monotone in the lag ratio, and at a four-fold underestimate the realized
drift lever changes sign at true lags of 0.10 s and 0.25 s. On the swept grid
the worst error under underestimation (0.0196 ohm) was not larger than under
the exact lag (0.0204 ohm), and overestimation was worse (0.0232 ohm). That
is a fact about the grid, not a property.

## 7. Units

`S_tI / S_II` has units of seconds. Scaling the current by ten scales `S_tI`
once and `S_II` twice, so the lever arm falls by ten; stretching the timebase
by two doubles it. Both are asserted in `tests/test_rcec.py`.
