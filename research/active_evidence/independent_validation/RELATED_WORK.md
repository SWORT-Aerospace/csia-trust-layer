# Related Work and Novelty Boundary

**Status: research draft. Not paper-ready.**
**Novelty status: `NOVELTY_UNRESOLVED`.**

## 0. A correction to the draft this document is based on

This document develops a draft supplied with the task, which described
Ni et al. as the "closest **verified** source" and its internal results as
placeholders to be replaced once the independent-validation campaign completed.

The placeholders are now replaced with measured values from
`results/CAMPAIGN_VALIDATION.json`. The word *verified* is not carried over.

**I could not retrieve the primary text.** Seven endpoints, once each, all
refused; the record with proxy responses is
`results/EXTERNAL_ACCESS_CHECK.json`. No content hash exists because no content
was retrieved. Everything below about that paper is therefore **as
characterised by the supplied draft and the task brief**, and is marked as
such. Nothing here is a reading, and no sentence in this repository may say the
paper shows, states or establishes anything on the strength of this document.

## 1. The closest named source, as characterised by the supplied draft

> X. Ni, M. Ornik, G. Chou, and S. Coogan, *Safe, Real-Time Active Model
> Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable
> Reachability*, arXiv:2606.19590v1, 17 June 2026,
> DOI `10.48550/arXiv.2606.19590`.

As the draft describes it: a finite collection of uncertain nonlinear
continuous-time models, an output-feedback policy that seeks to satisfy
state-input constraints robustly while making every model pair separable at one
or more sampled times, interval over-approximations of reachable state and
output sets, and a differentiable pairwise overlap objective of the form

```
J(π) = Σ_q min_t Vol( ∩_{m∈q} Y_m(t; π) )
```

with an output-anticipating refinement that retains only ambiguity-relevant
state intervals. Reported evidence, again as characterised: two hardware ground
robots and a simplified nine-state ten-input aircraft simulation with eleven
models; a five-second separating sequence in 45.3 ms on an RTX 4070 laptop
against 301 s for a mixed-integer baseline.

**On that characterisation**, this establishes a substantially stronger
*pre-execution* result than anything in this repository, and RCEC must not
claim that constrained active fault diagnosis, finite-model separation,
output-feedback probe design, set-based diagnosis or safety-aware excitation is
new.

Two qualifications the draft insists on, both of which this phase acted on:

1. the output-anticipating refinement needs a closed-form or efficiently
   over-approximable preimage of the output map, and general set inversion is
   NP-hard;
2. the optimised surrogate is intersection **volume**, and zero volume may
   include a measure-zero intersection rather than strict disjointness.

The second is not a footnote here. `discrimination.py` reports `zero_volume`,
`empty_intersection` and a signed `separation_margin` as three separate fields,
the gate requires the second and not the first, and **the distinction has a
measured frequency: 48 of 12 960 validation cells, 0.37%, were touching rather
than separated** (`COUNTEREXAMPLE_LOG.md` IV-22).

## 2. What this phase measured, with the placeholders filled in

RCEC addresses a different failure surface: a command predicted to be
informative is transformed by the controller, actuator lag, saturation,
authorization clipping, abort logic and telemetry sampling before it becomes
measured current.

That transformation is not hypothetical here. **Proposition A**: a palindromic
command with a drift lever of zero to 1e-9 and 20 050 A² of second moment
yields a realized lever of **−0.0276 s** through an ordinary causal bounded
lag, 2.8× a declared γ of 0.01 s; at six cycles the same lag removes **60%** of
the second moment.

| dimension | Ni et al. (as characterised by the supplied draft) | this phase, measured |
|---|---|---|
| primary object | predicted reachable state/output sets | realized current, voltage, timing, estimator error |
| strongest point | pre-action robust safety and finite-model separation | post-action validity: **2404 certified inferences, 0 wrong** against simulator truth |
| model class | uncertain nonlinear continuous-time | one-output battery family, Q0/Q1/Q2 |
| action design | differentiable output-feedback optimisation | 72-action library plus selectors S0–S3 |
| unknown models | omitted-model experiments not reported | one ringing family, boundary at **3.363 σ**, routing 0.901 above and 0.000 below |
| safety | reachable-set constraints over retained models | interval over-approximation whose **safety half cannot fail** here (IV-19); not a reachability guarantee |
| execution deviation | not isolated as a separate certificate | clipping, abort, staleness explicit and separately tested |
| hardware | ground robots; aircraft simulated | **simulator only** |
| compute | RTX 4070-class GPU | target timing **not established**; host component timings only |
| evaluation independence | not a reported design objective | independent internal implementation; **no external replication** |

## 3. The two-certificate architecture, and its first negative result

The draft proposes a two-stage contract rather than positioning RCEC as a
substitute for reachability. This phase preregistered that claim verbatim and
tested it.

**It is rejected as stated.** Across 12 960 validation cells the
`pre-fails / post-passes` cell is **empty**, so accepting on both gates is
identical to accepting on the post gate alone: 2404 accepted, zero wrong.
Requiring both beats the pre gate alone — 892 false acceptances to zero — and
does not beat the post gate alone.

**Within this envelope the pre-action separation gate is redundant.** That is
one of the two negative outcomes named in advance, and it is the result.

It does not generalise, for two reasons stated wherever the table appears: the
pre-gate's safety half cannot fail over this action space, and the post-action
certificate is unusually strong on a one-output model. A pre-action gate that
could reject on safety, on a plant where it could bite, is a different object.

## 4. Missing evidence, unchanged

Of the eight requirements the draft lists, four are addressed here — the
frozen reduction of the overlap baseline, the touching-set counterexample,
matched-class comparisons, and the surrogate audit — and four are not:
calibrated uncertainty sets from held-out or hardware data; timing on the
intended companion computer; an electronic-load or restrained-powertrain
experiment; and genuinely external reproduction. Owner authorisation forbids
the hardware items outright.

## 5. Defensible novelty boundary

Unchanged from the draft, and now with the measurements behind it.

**Do not claim novelty** for active fault diagnosis, optimal excitation,
Fisher-information design, set-membership diagnosis, output-feedback model
discrimination, reachable-set safety, runtime assurance, or battery-resistance
estimation individually. At least one is demonstrably textbook inside this
phase: P7a's objective **is** the classical A-optimal design for resistance,
`var(R) = σ_V²/S_II`, and `argmin var(R)`, `argmax S_II` and P7a's selection
are the same action (`BASELINE_MAPPING.md` §3).

The potentially differentiating claim is the assurance-level **composition**
across proposal, authorization, physical realization and evidence acceptance.
Whether that composition is novel is **unresolved**, and the first thing
standing in the way is that the closest named source could not be retrieved
from this container.

## 6. Reference

[1] X. Ni, M. Ornik, G. Chou, and S. Coogan, "Safe, Real-Time Active Model
Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable
Reachability," arXiv:2606.19590v1, 17 June 2026,
DOI `10.48550/arXiv.2606.19590`.

**Retrieval status: NOT RETRIEVED.** Bibliographic details are as supplied with
the task and are not confirmed against a retrieved document. See
`results/EXTERNAL_ACCESS_CHECK.json`.
