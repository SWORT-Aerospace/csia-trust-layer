# Exposure Precision Plan

**Implementation:** `csia/metrics/exposure.py` · **Tests:** `tests/test_datasets.py`

What CSIA's real-flight exposure currently supports, and exactly how much more
is needed for each strength of claim.

## Current position

| Quantity | Value |
|---|---|
| Raw log duration | 0.6627 h |
| **Monitored exposure** (post-`arm_time`) | **0.5183 h** |
| Unmonitored (inside arm window) | 0.1444 h (21.8%) |
| Verified-healthy exposure | **0.000 h** |
| Unannotated exposure | 0.5183 h |
| Held-out / blind exposure | **0.000 h** |
| Alert episodes | 2 |
| Rate | **3.86/h**, 95% CI **[0.47, 13.94]** |
| Uncertainty | **~30-fold** |

The interval spans a factor of thirty. Any statement of the form "CSIA has a
false-alarm rate of X" is unsupported at this exposure regardless of X.

## Projected precision

Exact Poisson (Garwood) intervals; zero-event rows use the rule-of-three bound.

| Exposure | 0 events → 95% upper bound | 1 event → 95% CI | 2 events → 95% CI |
|---|---|---|---|
| **0.52 h (now)** | 5.78 /h | 0.05 – 10.75 | **0.47 – 13.94** |
| 10 h | **0.30 /h** | 0.003 – 0.56 | 0.02 – 0.72 |
| 25 h | 0.12 /h | 0.001 – 0.22 | 0.01 – 0.29 |
| 50 h | 0.06 /h | 0.001 – 0.11 | 0.005 – 0.14 |
| 100 h | 0.03 /h | 0.000 – 0.06 | 0.002 – 0.07 |

## Zero-event exposure required for a target bound

| Target upper bound | Zero-event hours required |
|---|---|
| < 1 /h | **3.0 h** |
| < 0.5 /h | **6.0 h** |
| < 0.1 /h | **30.0 h** |
| < 0.05 /h | 60.0 h |
| < 0.01 /h | 300 h |

## What 10 hours would and would not establish

**Ten hours is not automatically sufficient.** It is a precision target, not a
sufficiency threshold, and what it buys depends entirely on the event count.

**Would establish, with 0 events in 10 unique monitored hours:**
- The rate is below **0.30/h** at 95% confidence.
- A ~19× improvement in bound tightness over today.
- If — and only if — those hours are *held out*, a first defensible
  false-alert characterisation.

**Would NOT establish:**
- **A zero false-alarm rate.** Zero observations never demonstrate zero; the
  rule-of-three bound is the strongest available statement.
- **Anything about healthy flight**, unless the logs are annotated. Ten
  unannotated hours yield a bound on the *unannotated* rate. Health is a
  property of the flight, not of CSIA's silence during it.
- **Fitness for a commercial reliability claim.** Operators care about rates
  near 0.1/h or lower; that needs ~30 h zero-event.
- **Generalisation.** Ten hours from one airframe in one environment bounds
  the rate *for that configuration*. Corpus diversity is currently unmeasured
  (no firmware, airframe, or vehicle metadata exists).
- **Superiority over PX4/ArduPilot.** Comparing two rates needs adequate
  counts in *both* arms; `compare_rates_approx()` refuses when either is zero.

## Recommended targets

| Milestone | Exposure | Enables |
|---|---|---|
| M1 — preliminary characterisation | 3 h held-out, 0 events | bound < 1/h; internal use |
| M2 — first external claim | 10 h held-out, 0 events | bound < 0.30/h |
| M3 — commercial reliability claim | 30 h held-out, 0 events | bound < 0.10/h |
| M4 — baseline comparison | 30 h+ with events in both arms | rate-ratio significance |

All exposure figures are **monitored** hours (post-`arm_time`) of **unique,
non-duplicate, held-out** logs. Raw log duration overstates usable exposure by
~22% at the current short-flight distribution.
