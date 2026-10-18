# What the model can and cannot decide

## Evidence tier

**E0. Desktop simulation.** The repository's ladder runs E0 to E5 and this
work has not reached E1. Nothing here has run on hardware, on SITL, or on any
real battery.

## Every battery parameter is synthetic

There is no real cell data in this repository and none is obtainable from
this host. `battery_1rc.SYNTHETIC_PACK` is a plausible small-vehicle pack in
consistent SI units and **it is not a measurement of any chemistry**.

> Nothing in this work characterises lithium polymer, NMC, LFP, sodium-ion or
> any other real cell. A claim of "robust operation across real battery
> chemistries" is **not supported and cannot be supported from this host.**

## What the plant does model

A one-RC Thevenin pack with a curved open-circuit characteristic, a
temperature coefficient on `R0`, self-heating, a first-order command-to-current
lag, saturation, and a measurement chain with offset, scale error, transport
delay, quantisation, dropout and independent per-subsystem noise streams.

It deliberately does **not** satisfy the estimator's model, which is the only
reason agreement between them means anything.

## What it does not model

| excluded | why it matters |
|---|---|
| ~~multi-RC / diffusion~~ | **NOW MODELLED** in `battery_multirc.py`, two branches at 1 s and 32 s |
| ~~hysteresis~~ | **NOW MODELLED**, and it found a false certification; see `COUNTEREXAMPLE_LOG.md` RC-11 |
| cell imbalance | modelled only as a scalar `weak_cell_scale`; a real weak cell is not a lumped resistance |
| three or more RC branches, distributed relaxation | still excluded |
| aerodynamic and rotor effects | the current demand here is a scalar, not a vehicle |
| ESC commutation and current-loop dynamics | the loop is one first-order lag |
| flexible structure and vibration coupling | absent |
| bus contention and firmware scheduling | absent |
| correlated common-cause faults | faults are injected one at a time |
| wind, thermal environment | absent |

## SUPERSEDED MEASUREMENT — READ THIS FIRST

> **The hysteresis numbers below were measured with a polarization bound that
> has since been shown UNSOUND** (`COUNTEREXAMPLE_LOG.md` RC-13, understating
> the truth fivefold). Re-measured with the corrected bound and a six-cycle
> probe, the specific window closes: at 2.4x over-declaration the estimate
> sits inside the correctly larger bound, and at 4x the residual check routes
> it to `UNKNOWN_OR_MODEL_MISMATCH`. **This retires one measurement, not the
> limit.** The 400-draw hunt has to be repeated across the whole envelope
> before anything stronger is said.

## THE LIMIT THAT MATTERS MOST, MEASURED

`hysteresis_v_max` is **told** to the certificate and never measured by it.
Declaring 0.05 V for a pack that has 0.12 V produces a certified estimate
wrong by more than its own bound, and nothing inside this framework detects
it:

| envelope | draws | certified | false certifications | worst ratio |
|---|---|---|---|---|
| inside the declaration | 400 | 331 | **0** | 0.43 |
| outside it | 400 | 290 | **11** | 1.53 |

A cross-probe consistency check was implemented and **does not work**: the
same hysteresis that creates the disagreement also inflates the declared
bound on the reversing probe, so the ratio never reaches one. Measured at
0.33, 0.55 and 0.85 for true M of 0.05, 0.08 and 0.12 V against a declared
0.05 V, across three probe pairs.

> **The hysteresis declaration must come from cell characterisation.
> This is the concrete reason "robust operation across real battery
> chemistries" is not supported and cannot be supported from this host.**

## Known thin margins

* the clean residual ratio was 2.17 against a tolerance of 3.0 and the
  prediction above it was that a richer pack would trip the detector on
  healthy data. **That prediction was wrong**: the multi-RC pack came in at
  1.84. What did happen is RC-10, a false alarm at high amplitude and low
  frequency, fixed by putting the declared polarization into the predicted
  residual. The clean ratio is now 2.04;
* **the residual check is structurally blind to any nuisance correlated with
  the current**, because such a nuisance is absorbed into the slope. This is
  not a tolerance that can be tightened. It is why `B_hysteresis` had to be
  derived and declared;
* `tau1_min` is a declared lower bound. If a real pack's polarization is
  faster than declared, `B_dynamic` is under-bounded and the certificate is
  optimistic. This is the single most load-bearing declaration in the budget;
* the separation metric is binary per seed, and only the 0.010 ohm point in
  the swept grid discriminates between arms. Differences in the swept mean
  are therefore driven by one delta.

## What would change the verdict

Hardware, real cell data, and the prior-art reading. None is available from
this host.
