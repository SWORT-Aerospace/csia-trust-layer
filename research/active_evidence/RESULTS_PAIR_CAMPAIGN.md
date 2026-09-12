# Results — does probing beat not probing?

**Verdict: `ACTIVE_PROBING_NOT_SUPPORTED_ON_THIS_GRID`. E0, simulation only.
No novelty claimed. Not a safety artifact.**

Artifact: `research/active_evidence/results/AEA_PAIR_CAMPAIGN.json`, schema
`csia.active_evidence.pair_campaign/1`.

## 1. What the earlier campaign could not answer

MX-037 tested whether the identifiability model's *prediction* is right and
found no counterexample. It had no baselines, so it could not say whether
active evidence acquisition is worth anything. This campaign supplies five
arms over an eight-hypothesis bank and 28 pairs.

## 2. The headline table

Unresolved hypothesis pairs out of 28, at the low, middle and high end of
each hypothesis's declared magnitude bracket.

| arm | probe | low | mid | high | sum | eligible relations | incremental cost |
|---|---|---|---|---|---|---|---|
| passive | hold | 3 | 1 | 1 | **5** | 10 | 0.00 A·s |
| opportunistic | mission manoeuvre | 5 | 1 | 0 | 6 | 10 | **0.00 A·s** |
| fixed | triangle | 5 | 1 | 0 | 6 | 10 | 3.03 A·s |
| random_safe | burst_2hz | 5 | 1 | 0 | 6 | 10 | 4.50 A·s |
| selected | doublet | 5 | 1 | 0 | 6 | 10 | 2.40 A·s |

**Every active arm is identical in effect.** Same three per-magnitude
numbers, same total, same gates. Their costs span 0.00 to 4.50 amp-seconds.
The purpose-built closed-form selector did not beat a fixed triangle, a
randomly chosen probe, or a manoeuvre the mission was flying anyway.

## 3. The mechanism, exact and measured

`source_impedance` is gated on the load **varying**. `effort_drift` is gated
on the operating point being **stationary**. Every action opens the first and
closes the second:

| arm | relation made eligible | relation made INELIGIBLE |
|---|---|---|
| every active arm | `source_impedance` | `effort_drift` |

That is the finding:

> **A probe is not free information. It is a swap.**

The swap is a net loss over the bracket. Per magnitude, relative to passive:

| magnitude | pairs gained | pairs lost | net |
|---|---|---|---|
| low | 0 | 2 | **−2** |
| mid | 1 | 1 | 0 |
| high | 1 | 0 | +1 |
| **over the bracket** | | | **−1** |

At low magnitudes the probe destroys `nominal|efficiency_loss` and
`pack_impedance|efficiency_loss`, both of which passive resolves through
`effort_drift`. At high magnitude it buys back `nominal|pack_impedance`,
which passive never resolves at any magnitude.

## 4. The anchor claim survives, and it is the one thing that does

| claim | result |
|---|---|
| a steady hover cannot separate nominal from pack impedance rise | **holds at every magnitude in the bracket** |
| that pair is inseparable in principle | **false** — every active arm resolves it at the top of the bracket |

So the physics of MX-036 is confirmed and sharpened: the pair is not
unidentifiable, it is unidentifiable *at a constant load*. What fails is the
claim that a purpose-selected probe is the way to get the load to vary.

## 5. Falsifiers, all four fired

The preregistration named them. Each is now a recorded fact, not a
possibility:

| falsifier | fired |
|---|---|
| a free mission manoeuvre matches the selected probe | **yes** |
| the selected probe does not beat the fixed probe | **yes** |
| the selected probe does not beat a random safe probe | **yes** |
| the selected probe is worse than passive somewhere | **yes** (low magnitude) |

## 6. What held: abstention integrity

A fault outside the bank entirely — thermal path loss on a motor no bank
entry names — was run through the same machinery on every arm.

| arm | outcome | hypotheses still consistent |
|---|---|---|
| passive | ambiguous | nominal, pack_impedance, thermal_path |
| every active arm | ambiguous | + efficiency_loss |

**No arm attributed it to a single cause.** H4 is supported: the machinery
declines to name a cause it has no model for, which is the behaviour that
matters most and the only hypothesis that survived this campaign intact.

## 7. Two instrument defects, both caught before the artifact

**The first pilot reported that a passive hover separated 27 of 28 pairs.**
Six of the twelve residuals have zero-width envelopes in this simulator, so
"the envelopes are disjoint" degenerated into "these two floats differ".
Pairs separated on 1e-17. The work order names this hazard explicitly and the
first run walked into it. Fixed by requiring the gap to exceed a declared
physical scale per residual, each traceable to a declared sensor noise or to
one count of a counter.

**The second pilot found the selected probe was the worst arm of five.** It
closed `effort_drift` without opening `source_impedance`, paying the full
cost of probing for none of the benefit. The cause was two unreconciled
eligibility criteria for the same relation: the error model said the probe
was adequate, and `residuals.source_impedance` refused to run at a realised
0.2438 A against its declared 0.25 A threshold. The selector now reads that
threshold out of the residual by introspection rather than copying it.

Fixing that defect moved the selected arm from 9 unresolved to 6 — which is
still not better than free.

## 8. What this means for CSIA

On this evidence, **CSIA should wait rather than ask.** An ordinary mission
manoeuvre delivers every bit of the separation a purpose-built probe
delivers, at zero incremental energy, and the machinery to choose a probe
earns nothing over choosing one at random.

That is a reason not to build a subsystem, which is worth more than a reason
to build one. It does not retire the identifiability model: the model is what
predicts which manoeuvres carry information, and §4 shows the prediction is
the useful part. What it retires is the selector as a source of value.

## 9. What this cannot establish

One simulator, one platform, one bank of eight hypotheses, three magnitudes,
five seeds, E0. The min-max envelope over five seeds is not a confidence
interval; it understates the spread and is therefore optimistic about
separation. Every arm is measured the same optimistic way so the comparison
is fair, but the absolute counts are not bounds.

The result is specific to a bank in which `effort_drift` is load-bearing. A
platform whose relations do not include a stationarity-gated effort check
would not pay the cost measured here, and the conclusion could reverse.
That is the highest-value next experiment.

## 10. Process honesty

The arm set, the metric and the falsifiers were fixed in the campaign source
before the run that produced the artifact. **They were not committed in a
preregistration document before the first outcome-producing run**, and the
H1–H5 labelling in this file was written after seeing the numbers. It is a
post-hoc labelling of a pre-fixed design, which is weaker than a
preregistration and is recorded as such.
