# CSIA Trust Layer — Engineering Design Review (v0.7)

Internal design review written to a funded-Phase-II / prime-contractor bar.
Its purpose is to be adversarial: to list what a senior aerospace systems
engineer would reject, so the team fixes it before an evaluator finds it.
Findings are tracked as GitHub issues (linked inline).

## Overall assessment

**Score: 38/100** on a scale calibrated to defense-prime / top-startup
review (a typical solo Phase-I submission scores 20–30; fundable ≥55;
internal design-review pass ≥75). CSIA is a competently executed *advisory
prototype* with unusually honest documentation and above-median validation
instincts (real-log replay, live SITL fault injection, causality tests),
built on mathematically ad hoc foundations and statistically thin evidence.
The gap to "fundable" is 6–10 focused weeks.

## Critical weaknesses

- **C1 — headline numbers historically came from two configurations.**
  Detection was measured with `field_mode` OFF; false-alarm rate with it ON.
  *Status: ADDRESSED* — `csia bench` / `csia mc` now measure both from one
  frozen config. This exposed a real gap (below).
- **C2 — circular tuning.** The public-log false-alarm rate was tuned and
  reported on the same 26 flights (train/test contamination; Poisson 95% CI
  ≈ [1, 13]/hr). *Status: infrastructure built (`csia mc`, Wilson/Poisson
  CIs); held-out campaign OPEN — issue #2.*
- **C3 — fusion lacks a probabilistic derivation.** A Beta-Bernoulli
  recursion is fed a weighted arithmetic mean of four heterogeneous scores
  with hand-chosen weights; the χ²→exp mapping and tempering constants are
  fudge factors. *OPEN — issue #5 (factor-graph reformulation).*
- **C4 — trust propagation is unanalyzed feedback.** Neighbor evidence is
  weighted by neighbor trust, which depends recursively on evidence. No
  fixed-point / bistability / oscillation analysis. *OPEN — issue #4.*
- **C5 — diagnosis is a hand-authored table.** Naive Bayes, correlated
  features, single-fault assumption. *OPEN — issue #10 (per-cause detectors).*
- **C6 — no systems-engineering artifacts.** *Status: ADDRESSED for
  requirements + FMEA (docs/REQUIREMENTS.md, docs/FMEA.md); ICD still lives
  in docstrings — OPEN.*
- **C7 — attitude estimator below the bar.** Euler complementary filter,
  gyro-only yaw, custom z-up frame; three edges inherit its unmodeled error.
  *OPEN — issue #3 (ESKF + NED).*

## Measured baseline (single frozen config — the honest number)

Monte Carlo, 150 runs, `field_mode=True` (`campaigns/monte_carlo.json`):

| fault class | n | TPR | 95% CI | latency p50 / p95 |
|---|---|---|---|---|
| gps_spoof | 25 | 1.00 | [0.87, 1.00] | 3.0 / 7.9 s |
| mag_emi | 25 | 1.00 | [0.87, 1.00] | 1.9 / 2.5 s |
| power_sag | 18 | 1.00 | [0.82, 1.00] | 1.7 / 2.5 s |
| vibration | 23 | 1.00 | [0.86, 1.00] | 2.0 / 2.5 s |
| **imu_bias (slow)** | 9 | **0.00** | [0.00, 0.30] | — |
| clean | 50 flt / 0.8 h | 0 alarms | 0.0/hr, Poisson [0.0, 4.4] | — |

**Known blind spot:** the field-mode adaptive normalizer (τ≈90 s) absorbs
ramps slower than its time constant, so slow IMU bias is undetected. This is
measured, disclosed (FMEA F3, requirement R16 WITHDRAWN), and tracked as the
top-priority fix (issue #1: dual-timescale CUSUM on pre-normalization
residuals against a frozen commissioning reference).

## Priority backlog (tracked as issues)

1. #1 slow-drift detector (CUSUM) — unblocks the imu_bias claim.
2. #2 held-out real-data campaign (200+ fresh logs, frozen params).
3. Scale Monte Carlo to 1000+ runs for tighter CIs.
4. #3 ESKF + NED frame.
5. #4 trust-propagation stability study.
6. #5 factor-graph fusion; #10 per-cause diagnosis.
7. #6 sensor timing model; #7 security (MAVLink signing); #8 EdgeSpec
   plugin interface; #9 native-core integration + on-target WCET.

## What is genuinely strong (keep)

Causality proof (batch == online replay), native C core pinned to the Python
reference at 1e-12, raw-sensor (GPS_RAW_INT) monitoring that catches faults
the EKF hides, disclosed-limitation culture, reproducible campaign tooling.
These are above the Phase-I median and are the real asset.
