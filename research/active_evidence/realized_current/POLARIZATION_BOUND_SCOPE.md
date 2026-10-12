# Polarization bound — exact scope of the claim

**Documentation only. No waveform, threshold, objective, seed, plant range,
comparison metric or acceptance gate is altered by this file.**

The earlier wording ("sound over the declared envelope", "zero violations in
1800 draws") conflated two different objects. They are separated here.

## 1. What the bound computes: an exhaustive maximum over a finite grid

`polarization.bound` returns the maximum of `|cov(V1, I)/var(I)|` over a
**finite, exhaustively enumerated grid** of 105 points:

| axis | points | values |
|---|---|---|
| `R1` | 5 | 0.004, 0.008, 0.012, 0.016, 0.020 ohm, linear |
| `tau` | 7 | 1.00, 1.85, 3.42, 6.33, 11.70, 21.63, 40.00 s, geometric |
| `V1(0)` | 3 | 0, `+R1·max|I|`, `−R1·max|I|` |

For those 105 model instances the statement is exact and complete:

> **Bounded over the declared discrete model grid.**

Every point is evaluated. Nothing is sampled, estimated or extrapolated
within that grid, and the branch integration is the same arithmetic the
plant uses.

## 2. What the validation tests: a sample from a continuum

The true `R1`, `tau` and initial condition are **continuous**, and the grid
above has gaps between its nodes. `polarization.validate` therefore draws
from the continuous envelope — `R1` uniform, `tau` log-uniform, `V1(0)`
uniform — and checks whether the grid maximum still covers them.

Across nine waveform families, 1800 such draws:

> **Zero observed bound violations in 1,800 preregistered simulator
> evaluations.**

**This is not a proof of soundness on the continuum.** Under an
independent-and-identically-distributed interpretation of those draws, the
one-sided 95% rule-of-three upper bound on the violation rate is

```
p_violation < 3 / 1800 ≈ 0.00167
```

**That is not a formal guarantee.** It is an upper confidence limit under an
assumption about the draws, and it says nothing about adversarially chosen
parameters, about correlations between draws, or about any waveform family
not among the nine tested. A bound that holds at 105 enumerated points and
at 1800 sampled points may still fail at a point between them.

## 3. Outside the evaluated envelope

When the declared envelope does not contain the true parameters, or when no
envelope is declared at all, the certificate **fails closed**:

| condition | state |
|---|---|
| no envelope declared | `MODEL_MISMATCH_LIMITED`, reason `UNBOUNDED_TERM:B_dynamic` |
| envelope declared, budget exceeded and dominated by `B_dynamic` | `MODEL_MISMATCH_LIMITED` |
| the fit residual exceeds what the declared channels and envelope predict | `UNKNOWN_OR_MODEL_MISMATCH` |

There is no path by which an undeclared or out-of-envelope term becomes a
finite number, and `tests/test_rcec.py::test_control_15_missing_configuration_is_not_defaulted`
asserts it for every budget field.

**The certificate is told the envelope and never measures it.** That is the
same load-bearing declaration recorded for hysteresis, and it is the reason
"robust operation across real battery chemistries" is not supported.

## 4. What may be said, and what may not

| may be said | may not be said |
|---|---|
| bounded over the declared discrete model grid | sound, proven or guaranteed on the continuum |
| zero observed violations in 1,800 preregistered evaluations | zero violations, full stop |
| `p_violation < 0.00167` under an IID interpretation | the violation rate is below 0.00167 |
| fails closed outside the evaluated envelope | covers parameters outside the envelope |
