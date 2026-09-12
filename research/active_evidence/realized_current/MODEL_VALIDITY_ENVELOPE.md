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
| multi-RC / diffusion | a real pack has more than one time constant; `B_dynamic` bounds one |
| hysteresis | open-circuit voltage depends on charge history, not only on state of charge |
| cell imbalance | a weak cell in series does not behave like a lumped resistance |
| aerodynamic and rotor effects | the current demand here is a scalar, not a vehicle |
| ESC commutation and current-loop dynamics | the loop is one first-order lag |
| flexible structure and vibration coupling | absent |
| bus contention and firmware scheduling | absent |
| correlated common-cause faults | faults are injected one at a time |
| wind, thermal environment | absent |

## Known thin margins

* **the clean residual ratio is 2.17 against a tolerance of 3.0.** The
  polarization branch and the curved open-circuit characteristic already
  consume most of the headroom the open-set detector has. A pack with more
  structure would trip `UNKNOWN_OR_MODEL_MISMATCH` on clean data, and the
  detector would have to be re-derived rather than re-tuned;
* `tau1_min` is a declared lower bound. If a real pack's polarization is
  faster than declared, `B_dynamic` is under-bounded and the certificate is
  optimistic. This is the single most load-bearing declaration in the budget;
* the separation metric is binary per seed, and only the 0.010 ohm point in
  the swept grid discriminates between arms. Differences in the swept mean
  are therefore driven by one delta.

## What would change the verdict

Hardware, real cell data, and the prior-art reading. None is available from
this host.
