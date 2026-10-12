# The minimal counterexample

Two hypotheses, two features, binary admissibility. Solved in closed form from
the frozen constants; no simulation is involved. Reproduced by
`formal_analysis.py`, which also checks the answer against a real replay.

## The system

Hypotheses `a = gps_fault`, `b = nominal`, with the frozen priors
`pi_a = (1 - 0.86)/7 = 0.02`, `pi_b = 0.86`.

Two features, both in `LOW(a)` and neither in `LOW(b)`:

* `phys_gps` — a **VALUE** feature. Consistency `c_value`, admissibility
  `D_value`.
* `gnss_no_fix_status` — a **STATUS** feature. Consistency `c_status`,
  admissibility `D_status`.

The frozen likelihood gives each feature a pairwise increment

```
delta(c) = log((1 - c + eps) / (c + eps)),    eps = 0.02
delta(0) = +3.931826      maximally inconsistent -> supports a
delta(1) = -3.931826      maximally consistent   -> supports b
```

and the steady-state log posterior ratio under a sustained condition is

```
log P(a)/P(b) = log(pi_a/pi_b) + M * [ D_value delta(c_value)
                                     + D_status delta(c_status) ]
              = -3.761200 + 1.5 * [ ... ]
```

## The fault

A GNSS fault in which the receiver reports no fix. It does three things at
once, and that simultaneity is the whole point:

1. drives `c_value -> 0` (the position is wrong, if you could see it);
2. drives `c_status -> 0` (the receiver says so itself);
3. drives `A_gps -> 0` (the value is no longer operationally admissible).

## The three regimes

| Regime | `c_value` | `D_value` | `c_status` | `D_status` | steady `log P(a)/P(b)` | `P(a)` |
|---|---|---|---|---|---|---|
| healthy | 1 | 1 | 1 | 1 | −15.556 | 0.000000 |
| fault, **coupled** `D = A` | 0 | **0** | 0 | **0** | −3.761 | **0.022727** |
| fault, **split** | 0 | **0** | 0 | **1** | +2.137 | **0.894404** |

Read the middle row carefully. Under coupling, a sustained GNSS fault leaves
the posterior at **exactly the prior**. Not "weakly detected" — the log ratio
is `log(pi_a/pi_b)` with no evidence term at all. The system has returned to
what it believed before it observed anything, while the fault is still
happening.

The split row shows what the status field is worth: `M * delta(0) = 5.898`
nats of log-odds, which turns 0.023 into 0.894.

## It is not an artifact of the reduction

The closed form above uses two hypotheses. The implementation runs eight
through a softmax. Replaying the sustained-invalidity fixture through the real
frozen core gives:

| Arm | predicted (2 hypotheses) | measured (8 hypotheses) | difference |
|---|---|---|---|
| `S1D` — coupled | 0.022727 | **0.022723** | 4 × 10⁻⁶ |
| `S2a` — split | 0.894404 | **0.894386** | 1.8 × 10⁻⁵ |

The other six causes contribute less than 2 × 10⁻⁵ of posterior mass here, so
the two-hypothesis reduction is not a simplification that changes the answer.

## What the counterexample does and does not establish

It establishes that **coupling `D` to `A` can drive a fault hypothesis to
exactly its prior while the fault is active**, and that a status feature
outside the coupled gate recovers it — in this system, with these constants,
in closed form.

It does not establish that this is novel, that the status encoding used is a
good one (it is the strongest the consistency domain permits, and
`CHATGPT_REVIEW_REPORT.md` §13 shows it is actively harmful under intermittent
invalidity), or that any of it generalises past GNSS. `NOVELTY: NOT
ESTABLISHED`.
