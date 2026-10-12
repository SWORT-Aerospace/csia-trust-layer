# Sensing and Telemetry Sensitivity Audit

**Development partition. Simulator.** Evidence:
`results/UNKNOWN_AND_SENSITIVITY.json`. Eight development seeds, finite
differences on one matched pair per seed at a 0.020 Ω target.

## 1. The question

Sensing defects barely moved the prior phase's margin. That is either genuine
insensitivity or another disconnected instrument, and the task is explicit that
a zero is only acceptable when the cancellation is derived and its conditions
stated.

Both answers turned up. One defect was disconnected. Four are exactly zero for
reasons that can be written down. The rest move the outcome.

## 2. The numbers

`J_q^out = ∂M_R^out/∂q`, `J_q^cert = ∂M_R^cert/∂q`, median over seeds.

| parameter | step | `J_q^out` | `J_q^cert` | reaches the outcome |
|---|---|---|---|---|
| `scale_i` | 0.010 | **−1.92e-2** | +5.95e-4 | yes |
| `delay_v_s` | 0.020 s | −2.99e-3 | 0 | yes |
| `quantum_v` | 0.010 V | −1.52e-3 | 0 | yes |
| `delay_i_s` | 0.020 s | −7.68e-4 | −1.58e-3 | yes |
| `sigma_i` | 0.050 A | −7.32e-5 | −1.17e-4 | yes |
| `dropout` | 0.100 | −2.25e-5 | −9.43e-4 | yes |
| `quantum_i` | 0.050 A | −2.13e-5 | −1.04e-5 | yes |
| `antialias_tau_s` | 0.020 s | −1.22e-5 | −1.03e-3 | yes |
| `sample_phase` | 0.500 | +3.60e-7 | +1.09e-4 | yes |
| `bias_i` | 0.500 A | **0** | 0 | **no — derived** |
| `bias_v` | 0.020 V | **0** | 0 | **no — derived** |
| `sigma_v` | 0.010 V | **0** | 0 | **no — derived** |
| `timestamp_jitter_s` | 0.002 s | **0** | −5.06e-5 | **no — derived** |

Current gain error is the dominant sensitivity by an order of magnitude, which
is what one expects: it multiplies the regressor and therefore attenuates the
slope directly. A 1% gain error produces `e_ΔR ≈ −s·Δ/(1+s)`, and the measured
value matches that prediction to 2e-6 Ω across three seeds.

## 3. The four exact zeros, derived

Each is zero to floating point, not merely small, and each has a test that
states the derivation and then measures it.

**`bias_v` — a constant voltage offset is absorbed by the intercept.**
The model is `V = E − R·I`. Adding `b` to every voltage sample maps `E → E + b`
and leaves `R` untouched. Exactly zero, unconditionally.

**`bias_i` — a constant current offset leaves the slope alone.**
Adding `b` to every current sample shifts the regressor by a constant. Least
squares fits a free intercept, so the *centred* regressor is unchanged, and the
offset lands entirely in `E − R·b`. Exactly zero, and the condition is that the
intercept is free — an estimator with a fixed `E` would not enjoy this.

**`sigma_v` — voltage noise cancels in the paired difference.**
Both members of a matched pair draw the same noise sequence (common random
numbers) and least squares is linear in the response, so the noise contributes
identically to both estimates and vanishes from their difference. This is
`COUNTEREXAMPLE_LOG.md` IV-9 seen from the sensing side. **The condition is the
paired design**: on a single window, voltage noise very much does move the
estimate.

**`timestamp_jitter_s` — the estimator never reads time.**
`R̂` regresses voltage on current. There is no `t` in that fit, so perturbing
the reported timestamps cannot reach it. Exactly zero, unconditionally.

## 4. The contrast that makes those derivations honest

The certificate *does* read time, and the audit shows it plainly:

| jitter | certificate |
|---|---|
| 0 | `CERTIFIED_IN_MODEL`, margin 0.00433755 |
| 0.002 s | `CERTIFIED_IN_MODEL`, margin 0.00433930 |
| 0.010 s | **`INVALID_INSTRUMENT`**, `TIMEBASE_NOT_STRICTLY_INCREASING`, no margin |

At 10 ms the sampled timebase stops being monotone and the certificate refuses
to produce a number at all. That is the right behaviour, and it is the reason
`J_q^out = 0` for jitter is a statement about the estimator rather than an
alibi for the instrument.

Similarly `J_q^cert = 0` for `sigma_v`, `bias_v`, `quantum_v` and `delay_v_s`:
the certificate's margin is built from the **declared** sensing envelope, not
the realized one. Perturbing the plant's actual voltage channel without
updating the declared budget cannot move it. That is by design, and it is also
a limitation worth stating plainly — the certificate is only as good as the
declaration it is handed.

## 5. The disconnected instrument, found and fixed

`dropout` measured **exactly zero** in the first version of this audit. The
harness passed the full measured arrays to the estimator, so samples the
telemetry layer had marked invalid were still being fitted: a 20% dropout
changed nothing because nothing was actually dropped.

It now uses `Observation.kept()`, and dropout registers on both the outcome
(−2.25e-5) and the certificate (−9.43e-4). A regression test asserts that
fitting all samples and fitting only the delivered ones give different answers.

This is precisely the failure mode §11 of the task warned about: "sensing
defects remain absent because the evaluator forgot them" is a preregistered
falsifier, and for one parameter it was true until it was fixed.

## 6. What the audit does not establish

These are single-parameter derivatives at one operating point, one command, one
plant and one target magnitude. They do not bound interactions between defects,
and a combination that individually moves the margin by 1e-5 each could still
matter together. Nothing here is a claim about real sensor hardware.
