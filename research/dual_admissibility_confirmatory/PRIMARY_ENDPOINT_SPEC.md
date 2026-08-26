# Primary endpoint specification

## What was retired, and why

The exploratory headline — *gps_fault posterior improves under the split* — is
**demoted to a secondary result**. On the one real jam recording that
comparison is detector-dominant: the h_acc term with `D` coupled to `A`
recovers +0.138 of leading-cause share and the split adds +0.002. An endpoint
that a stronger detector can move is not measuring the architecture.

## Primary endpoint: mechanism discrimination under matched A

**The quantity.** Over the matched-`A` scored interval, classify each tick into
a frozen mechanism label set and score against the injected mechanism.

```
MECHANISMS = { SENSOR_INVALID, TRANSPORT_UNAVAILABLE, UNRESOLVED }
```

`UNRESOLVED` is a first-class output, not a failure code. An architecture that
cannot tell the two apart should say so rather than guess, and a classifier
forced to choose would convert an honest tie into a coin flip.

**Score.** Per trial, the fraction of scored ticks classified correctly;
reported as the confusion matrix item 10 specifies:

| | predicted SENSOR | predicted TRANSPORT | UNRESOLVED |
|---|---|---|---|
| actual SENSOR | | | |
| actual TRANSPORT | | | |

plus per-arm totals across trials. **No aggregate statistic beyond counts and
proportions is reported**, and no interval or p-value: these are deterministic
simulator scenarios, not samples.

## The classifier

Frozen, per arm, before any confirmatory trial. It is a **decision rule over
runtime-observable state**, not a learned model and not a likelihood term —
which is what keeps detector magnitude out of the primary endpoint entirely.

**Inputs it may read**, and nothing else:

| Input | Available to |
|---|---|
| `A_gps` (the frozen `fresh["gps"]`) | every arm |
| whether a GNSS message arrived within `MSG_FRESH_S` | C1, C2, C0_STRONG |
| the last observed `fix_type` category, as `OBSERVED_VALID` / `OBSERVED_INVALID` | C1, C2 |
| `trust_gps`, `post_gps_fault`, `post_nominal` | C0_STRONG only |

**Inputs it may NOT read, ever:** the test condition, the simulator parameter,
the scenario filename, the injected mechanism label, the trial index, or the
onset time. A test asserts the classifier's call signature admits none of
these.

**The rules, frozen:**

```
C0  (coupled)      if A == 0:  UNRESOLVED
                   else:       (not scored -- outside the interval)

C1  (split)        if A == 0 and a message arrived within MSG_FRESH_S
                        and last fix_type category == OBSERVED_INVALID:
                                SENSOR_INVALID
                   if A == 0 and no message within MSG_FRESH_S:
                                TRANSPORT_UNAVAILABLE
                   otherwise:   UNRESOLVED

C2  (status only)  identical to C1. C2 differs from C1 only in what evidence
                   is admitted into the DIAGNOSIS, not in the classifier.

C0_STRONG          a threshold rule on the continuous residue, with the
                   threshold FITTED ON DEVELOPMENT DATA ONLY and frozen
                   before the confirmatory run. See below.
```

C0's rule is `UNRESOLVED` by construction because under matched `A` the coupled
arm has, by T1, nothing else to read. **That is the point of C0_STRONG.**

## C0_STRONG — the arm that can kill the result

`DESIGN_FEASIBILITY.json` shows the coupled arm is *not* purely coupled: under
matched `A`, `trust_gps` differs between the two mechanisms on 857/857 ticks
and `post_gps_fault` on 181/857, because a propagated invalid sample feeds the
ungated temporal features while a missing message feeds nothing.

So the coupled architecture retains a **leak** — though the same artifact shows
the leak is mostly an onset artefact rather than usable evidence (see the two
corrections below). C0_STRONG is the arm that tries to exploit it anyway,
because "mostly" is not "entirely" and the null deserves its best shot:

```
C0_STRONG:  if A == 0 and trust_gps > theta:   SENSOR_INVALID
            if A == 0 and trust_gps <= theta:  TRANSPORT_UNAVAILABLE
```

**`theta` is ONE value, frozen, applied to every pair.** Fitted on development
traces only, chosen to maximise development-set discrimination, and recorded
numerically in the preregistration before any confirmatory trial.

Two things about this rule are corrections to an earlier draft, and both matter:

* **The discriminant is the RAW trust value, not a delta from a reference.**
  `trust_gps − trust_ref` is provably useless here: trust *freezes* the moment
  `A` closes, because the Beta update is gated on `fresh`
  (`csia/trust_engine/engine.py:146`). The delta is identically zero for both
  mechanisms on every scored tick. Specifying it would have handed the null
  arm a discriminant that cannot work.
* **A per-pair threshold is forbidden.** On a single development pair, trust
  freezes at 0.935936 for sensor-invalid and 0.937249 for transport loss, so a
  threshold between them scores **1.0000** — on a constant inherited from the
  onset transient the scored interval excludes. Across pairs with different
  onsets those frozen values interleave. One cross-pair threshold is the only
  version of this arm that tests anything.

The other continuous fields are at chance on development data
(`post_gps_fault` 0.5047, `post_nominal` 0.5053), so raw trust is the coupled
arm's best available handle and this rule gives it that handle.

Giving the null a threshold tuned on data the split arms never saw is
deliberate: it is the strongest fair version of the null, and the honest way to
ask "was the split needed?".

**If C0_STRONG matches C1/C2 on held-out data, the architectural claim
collapses, and that is the reported result.**

## Second primary endpoint: information retention

Item 12. Over the scored interval, treat the injected mechanism `M ∈ {SENSOR,
TRANSPORT}` as a two-valued variable with equal design frequency (10 trials
each), and the arm's downstream evidence state `E` as a categorical variable.

```
I(M ; E)  computed from the EXACT empirical joint over the scored ticks
```

Because the categories are controlled and discrete and the design frequency is
fixed by construction, the empirical joint is the exact distribution over the
scored population — no estimator is used and no correction is needed. This is
reported as an exact descriptive quantity over the campaign, **not** as an
estimate of a population parameter.

Three values are reported per arm:

| | `E` is |
|---|---|
| `I(M; E_upstream)` | the raw observation category (`OBSERVED_VALID` / `OBSERVED_INVALID` / `NOT_OBSERVED`) |
| `I(M; E_arm)` | the arm's downstream state, discretised to the classifier's input vector |
| `I(M; decision)` | the arm's mechanism output |

`I(M; E_upstream) ≥ I(M; E_arm) ≥ I(M; decision)` is forced by data
processing. **The data-processing inequality is textbook and is not claimed.**
What is measured is *how much* each architecture gives away, not that giving
something away is possible.

## Clean criterion

`CLEAN` trials contain no injected mechanism. The frozen budget:

> **Zero** ticks classified as `SENSOR_INVALID` or `TRANSPORT_UNAVAILABLE`
> across all 10 clean trials, for every arm.

Not a rate — zero. The classifier's `A == 0` precondition means it should never
fire on a clean trial at all, so any firing is a defect rather than a tolerable
false-alarm rate. An arm that fires on clean data is disqualified regardless of
its discrimination score.

## Secondary endpoints, reported but not headline

* `gps_fault` leading-cause share and final posterior (the retired exploratory
  endpoint, kept for continuity with `b21b539`).
* `objective_O` — operational admissibility overlap with raw invalidity.
* Failsafe level trajectory and time to `nav_degraded`, to re-check the
  exploratory finding that the operational recommendation does not differ
  between arms.
* T5's predicted 0.29 s rank-reversal time, measured directly for the first
  time.

## What this endpoint cannot show

It cannot show the split is *worth* adopting. It measures whether mechanism
information survives to the decision point, not whether any operator or
autopilot behaviour would improve as a result. The exploratory package found
the operational recommendation identical across all arms, and nothing in this
design changes that.
