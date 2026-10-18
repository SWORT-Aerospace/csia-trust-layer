# Plant Independence Audit

**Development partition only. Nothing here is a result.** This is the evidence
that the instrument is connected, produced by
`tools/research/iv_plant_independence.py` and stored in
`results/PLANT_INDEPENDENCE.json`. Eight development seeds, six magnitudes,
three plants, 144 paired runs.

Every parameter is synthetic. No chemistry is claimed and no hardware
representativeness is implied.

## 1. Numerical independence from the prior simulator

The prior simulator integrates the polarization state and the command lag with
explicit forward Euler. These plants use the exact zero-order-hold step. They
are different numerical methods, and the disagreement is largest exactly where
this experiment lives — the command-to-current lag:

| time constant | forward-Euler step coefficient | exact ZOH coefficient | difference |
|---|---|---|---|
| 0.25 s (command lag) | 0.080000 | 0.076884 | **+4.05%** |
| 1.20 s (Q2 fast branch) | 0.016667 | 0.016529 | +0.84% |
| 13.5 s (slow branch) | 0.001481 | 0.001480 | +0.07% |
| 40 s (envelope edge) | 0.000500 | 0.000500 | +0.03% |

The exact step is pinned against closed form to 1e-12 over 200 steps at five
`(τ, dt)` combinations, and the forward-Euler coefficient is *measured* in the
same test rather than recalled
(`tests/test_iv_plants.py::test_zoh_step_is_the_exact_solution`,
`::test_forward_euler_would_fail_this_same_check`). The RK4 thermal integrator
is pinned against its own closed form to 1e-9 over 500 steps.

These plants therefore do not reproduce the realized current waveform of the
prior simulator, and they are not supposed to. A certificate that only works
against the integrator it was developed on is not a certificate.

## 2. Is every declared effect actually wired into the observation?

Falsifier 7 of the preregistration: *the richer plant does not change any
outcome because it is not actually connected to the generated voltage.*

Each effect is removed from the plant and the change is measured two ways: at
the terminal voltage, against one sigma of sensor noise; and at the
least-squares resistance estimate, against the smallest magnitude on the frozen
grid (0.002 ohm). The second is the comparison that decides whether an effect
can change a verdict.

| effect removed | peak voltage shift | vs σ_V = 0.020 V | shift in R̂ | vs smallest grid magnitude |
|---|---|---|---|---|
| R1 on Q1 | 0.1322 V | 6.6× | 4.80e-4 Ω | 24.0% |
| R1 on Q2 | 0.1322 V | 6.6× | — | — |
| R2 on Q2 | 0.1364 V | 6.8× | 1.07e-4 Ω | 5.4% |
| hysteresis on Q2 | 0.0169 V | 0.85× | 6.29e-5 Ω | 3.1% |
| OCV curvature on Q1 | 0.2431 V | 12.2× | 5.01e-5 Ω | 2.5% |

Every effect is connected. Hysteresis is the weakest: its peak voltage
signature sits *below* one sigma of per-sample sensor noise, and it moves the
resistance estimate by 3.1% of the smallest fault on the grid. That is a real
effect and a small one, and this table is the honest statement of its size
rather than a pass mark against a threshold chosen to produce one.

The earlier version of this plant had hysteresis a thousand times slower, at
which point removing it moved the voltage by 4.7e-5 V and it was a constant
offset wearing a dynamic effect's name. See `COUNTEREXAMPLE_LOG.md` IV-8.

## 3. Does the outcome metric see the plant when the certificate margin cannot?

Across 48 cells matched on magnitude and seed, with all three plants present:

| quantity | identical across all three plants |
|---|---|
| certificate margin `M_R^cert` | **48 of 48** |
| independent change error `e_ΔR` | 1 of 48 |

`M_R^cert` is bit-identical across plants on this independently written plant
family, exactly as it was on the prior one. That reproduces `COUNTEREXAMPLE_LOG.md`
IV-4 on fresh code and settles it: the certificate margin is plant-independent
by construction, not by coincidence.

The independent evaluator is not. But the *size* of the difference depends
sharply on which independent metric is used:

| plant | median `\|e_ΔR\|` | median `AE_R` | resolved fraction |
|---|---|---|---|
| Q0 zero-RC | 4e-6 Ω | **1.94e-4 Ω** | 1.000 |
| Q1 one-RC | 4e-6 Ω | **6.57e-4 Ω** | 1.000 |
| Q2 richer mismatch | 4e-6 Ω | **5.06e-4 Ω** | 1.000 |

The point error separates the plants by a factor of 3.4. The paired change
error does not separate them at all, and the reason is a derivation rather
than a measurement: on a matched pair under common random numbers the fault
does not move the current, so `V_fault − V_nominal = −ΔR₀·I_true` exactly and
every plant-common nuisance cancels in the difference. What is left is the
finite-sample errors-in-variables factor on the shared regressor, measured at
λ̂ = 1.0009463544 and matching the observed ratio to seven digits. Full
derivation and evidence: `COUNTEREXAMPLE_LOG.md` IV-9.

**Consequence for the phase.** `e_ΔR` and `M_R^out` stay primary, as
preregistered and as the task defines them. But H5 — plant discrimination — is
tested on `AE_R`, which was preregistered in §4.1 and does not enjoy the
cancellation. Any sentence of the form "the richer plant changed nothing" must
name the metric, because for `e_ΔR` that is a theorem about the paired design
and not a finding about the plant.

## 4. Stream discipline

Seven named streams: `plant`, `voltage_sensor`, `current_sensor`,
`controller`, `environment`, `telemetry`, `unknown_fault`. Each is a separate
generator spawned from one seed, and every block is drawn unconditionally
before the integration loop, so a branch that does not fire cannot shift a
stream belonging to another subsystem.

Pinned by test: injecting 0.40 V of unknown ringing leaves `i_meas`
bit-identical; enabling timestamp jitter leaves the dropout mask
bit-identical; changing `R₀` leaves the commanded current bit-identical; the
same seed reproduces a run bit for bit. The jitter case is not hypothetical —
the first draft of this module drew that block conditionally and did shift the
dropout mask (`COUNTEREXAMPLE_LOG.md` IV-7).

## 5. What this audit does not establish

That the plants resemble any real battery. They do not, and nothing in this
repository could show that they did. It also does not establish that the
plant family is *rich enough*: Q2 contains one dynamic effect the deployable
estimator has no term for, which satisfies the requirement and is not the same
as covering the space of things a real pack can do.
