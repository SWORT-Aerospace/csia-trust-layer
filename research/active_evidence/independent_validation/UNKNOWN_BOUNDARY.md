# Unknown-Fault Detectability Boundary

**Development partition. Simulator. Nothing here promotes anything.**
Evidence: `results/UNKNOWN_AND_SENSITIVITY.json`, produced by
`tools/research/iv_unknown_boundary.py`. Four development seeds, 1440 trials.

## 1. The question, and the answer that was not allowed

The prior campaign routed a 0.40 V ringing fault to
`UNKNOWN_OR_MODEL_MISMATCH` and absorbed a 0.10 V one as
`CERTIFIED_IN_MODEL`. The tempting response is to lower a threshold until the
0.10 V case is caught. The task forbids that, and rightly: if the 0.10 V
trajectory lies inside what the model can already explain, no classifier can
separate it, and lowering a threshold would buy the catch with false alarms
somewhere else.

So the question becomes a measurement: **how far is each unknown trajectory
from the modelled observation set?**

## 2. The modelled set and the metric

```
Y_model(u) = ∪_{h ∈ H} Y_h(u, Θ_h, E)
```

`H` is the hypothesis bank: nominal plus a resistance increase at each of the
six magnitudes on the frozen grid. `Θ` is the declared nuisance envelope —
three polarization resistances × three time constants × two drift levels,
matching the certificate's declared polarization envelope. That is 7 × 3 × 3 ×
2 = **126 enumerated members**, so every distance reported is an **upper bound
on the true infimum**: the envelope is sampled, not covered.

The estimator fits an intercept and a slope on `[1, −I]`, so anything in that
two-dimensional subspace is absorbed for free and cannot contribute to
detectability. The distance is therefore measured on the residual after
projecting that subspace out, normalised by the declared voltage sigma and the
window length:

```
δ_unknown = min_{y ∈ Y_model} ‖P⊥(y_unknown − y)‖ / (σ_V √N)
```

in units of **sigmas of per-sample sensor noise**. Fixed before the sweep ran.

## 3. The sweep

Ringing amplitude × frequency (2, 6, 15 Hz) × damping (0.1, 0.4, 1.5) × phase
(0, π/2) × onset (0, 3 s), four seeds. `routed` counts
`UNKNOWN_OR_MODEL_MISMATCH` only.

| ringing amplitude | median δ_unknown | routed to unknown |
|---|---|---|
| 0.00 V (no fault) | **0.445 σ** | 0.000 |
| 0.02 V | 0.523 σ | 0.000 |
| 0.05 V | 0.824 σ | 0.000 |
| 0.08 V | 1.198 σ | 0.000 |
| **0.10 V** | **1.461 σ** | **0.000** |
| 0.15 V | 2.138 σ | 0.000 |
| 0.20 V | 2.824 σ | 0.333 |
| 0.30 V | 4.208 σ | 0.667 |
| **0.40 V** | **5.599 σ** | **0.667** |
| 0.60 V | 8.385 σ | 1.000 |

## 4. The boundary

**δ\* = 3.363 σ.** Above it the routing rate is 0.901 over 426 trials; below
it, **0.000 over 870 trials**. The transition is sharp.

## 5. What this says about the 0.10 V case

The no-fault floor is 0.445 σ — the irreducible distance from a noisy trace to
the nearest enumerated member of a finite grid. The 0.10 V case sits at
1.461 σ, **about one sigma above that floor and less than half the boundary**.

So the prior phase's failure to label 0.10 V as unknown is **structural, not a
classifier defect**. That trajectory is close to something the declared model
can already produce. Catching it would require either a tighter declared
envelope — which would then have to be justified against real hardware nobody
has — or accepting false alarms on trajectories the model genuinely explains.

This is reported as a **detectability boundary for this envelope, this command
and this metric**. It is not a claim about unknown-fault detection in general,
and no such claim is permitted.

## 6. Two harness defects found on the way

**The routing predicate was wrong.** The first version counted
`MODEL_MISMATCH_LIMITED` as "routed to unknown". That is the in-model "my
budget cannot resolve this" answer, and at a 0.010 Ω target it is what a
**no-fault** run returns. The routing rate came out 1.000 at every amplitude
including zero, and the boundary that fell out of it — 0.439 σ, with zero
observations below it — was an artifact of the predicate. Only
`UNKNOWN_OR_MODEL_MISMATCH` counts now.

**The operating point was saturated.** At a 0.010 Ω target this command's union
bound is 0.005161 against an allowed 0.005000, dominated by the polarization
term, so the certificate says "cannot resolve" whatever it is shown. The sweep
uses 0.020 Ω, where the no-fault case certifies — the same operating point the
prior phase's ablation used, and the only one where routing carries
information. Fixed before the boundary was read, and recorded here rather than
left for a reader to infer.

## 7. Limits

126 enumerated members is a coarse sampling of `Θ`; a finer grid can only
reduce `δ_unknown`, so the boundary reported here is, if anything, optimistic.
One command, one plant (Q1), one ringing family. A different unmodelled fault —
one that looks like a resistance change rather than an oscillation — would have
its own boundary and there is no reason to expect it to be this one.
