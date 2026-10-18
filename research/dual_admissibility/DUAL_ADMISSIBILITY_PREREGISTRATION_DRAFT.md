# Dual-channel admissibility — preregistration DRAFT

**DRAFT. NOT FROZEN. NOT RUN.** Nothing in the exploratory package may be
described as confirming anything specified here, because everything here was
written after seeing those results (item 39). This document exists so that a
future confirmatory campaign has a prediction to lose.

## What is being confirmed

One claim, and deliberately not the one the exploratory work is best at:

> **P1.** The diagnostic benefit of decoupling `D` from `A` is governed by the
> longest **sustained** interval for which `A` is closed, and is negligible
> when that interval is shorter than the frozen diagnosis smoother's time
> constant.

Exploratory support: four points from one fixture family (`P2` 0.2 s → 0.000;
`P4` 0.8 s → 0.000; `P1+` 1.0 s → +0.021; `P5` 34.0 s → +0.961), plus T5's
derived constant of 7.29 ticks ≈ 0.29 s. That is not enough to call a
relationship, which is exactly why it is the thing to preregister.

## Frozen prediction

Let `L` be the longest consecutive A-closed interval in a trial, and

```
G(L) = D_top_share(split arm) - D_top_share(its matched coupled control)
```

using the per-term matched pairs already implemented (`S2a`/`S1Da`,
`S2b2`/`S1Db`, `S2c2`/`S1D`).

**Predicted, before any confirmatory trial is run:**

| # | Prediction | Threshold |
|---|---|---|
| P1a | `G(L) <= 0.02` for every trial with `L <= 0.29 s` | the T5 constant |
| P1b | `G(L) >= 0.50` for every trial with `L >= 5.0 s` | |
| P1c | `G(L)` is non-decreasing in `L` when trials are binned by `L` into the six bins below | Spearman rho over bin medians `>= 0.9` |
| P2 | Transport control: `G(L) <= 0.02` for every transport-starved trial regardless of `L` | T3 necessity |
| P3 | Clean control: no arm leads with `gps_fault` on any tick of any clean trial | |

**P1a and P2 are the ones that can kill it.** If the split pays off at short
closures, the mechanism story in T5 is wrong. If it pays off under transport
starvation, the status feature is firing on absence and the whole
value/status separation is unsound.

## Design

**Independent variable.** `L`, the sustained A-closed duration, swept over six
bins: `0.1, 0.25, 0.5, 1.0, 2.0, 8.0 s`. Ten trials per bin with the onset time
randomised over a 10 s window so trials are not byte-identical replays.

**Conditions.** Per bin: `SENSOR_INVALID` (receiver reports no fix) and
`TRANSPORT_MISSING` (no message). Plus one clean condition, ten trials.
Total 6 × 2 × 10 + 10 = **130 trials**.

**Arms.** The six already implemented and hashed: `S0`, `S1`, `S1Da`, `S1Db`,
`S1D`, `S2a`, `S2b2`, `S2c2`. Arms `S2b`/`S2c` (the pre-N3 h_acc freshness
rule) are **excluded**: that rule is a known defect and carrying it into a
confirmatory campaign would preregister a bug.

**Data that may be used.** Traces **not** used to design S2. Specifically **not**
`NON_SCORED_TEST_FIXTURE_M1`, and **not** any fixture built on its non-GNSS
carrier. New captures are required. The exploratory fixtures are burnt.

**Primary endpoint.** `G(L)` as defined above, on `D_top_share`.
**Secondary.** Final `gps_fault` posterior; time to `gps_fault` lead;
`objective_O`; failsafe level trajectory.

**Matching.** Every arm consumes the identical decoded message list per trial,
hashed before any arm runs, exactly as `THREE_ARM_IMPLEMENTATION_AUDIT.json`
does now.

## Stopping rules

* **Stop** if the S0/S1 tradeoff does not reproduce on the new traces. The
  motivating effect must exist in the new data before anything is measured on
  top of it.
* **Stop** if any clean trial produces a `gps_fault` lead under any arm. That
  is a false alarm and it disqualifies the arm regardless of the rest.
* **Do not** add, remove or re-tune any evidence term after the first
  confirmatory trial. The h_acc transform, the binary status encoding, the
  0.5 s freshness window and the hypothesis-map extension are frozen as
  implemented at this commit; their hashes are in
  `results/THREE_ARM_IMPLEMENTATION_AUDIT.json`.

## What a confirmatory pass would and would not license

**Would:** stating P1 as an empirical regime boundary for this architecture,
with the T5 mechanism as its explanation.

**Would not:** any claim about operational benefit (the exploratory work found
none — §8 of the review report), any claim beyond GNSS (no other family has the
ingredients), any hardware claim, or any novelty claim. Those need,
respectively: an operational endpoint that actually differs between arms; a
second modality with an explicit invalid state; the HIL plan; and a literature
search.

## Known weaknesses of this design, stated in advance

* It confirms the **conditional** result, not the architecture. Even a clean
  pass leaves the verdict at "the split helps under sustained closure", which
  is a narrower claim than the work package set out to test.
* The binary status encoding is carried forward unchanged despite being
  harmful under intermittent invalidity (N1). That is deliberate — changing it
  now would be tuning — but it means `S2a` will look bad in the short-`L` bins
  for a reason unrelated to P1.
* `L` is manipulated, but invalidity **density** co-varies with it in any
  natural schedule. The design separates them only by including `P2`-style
  high-density/short-`L` trials in the 0.1 and 0.25 s bins; whether that is
  enough separation should be checked before freezing.
