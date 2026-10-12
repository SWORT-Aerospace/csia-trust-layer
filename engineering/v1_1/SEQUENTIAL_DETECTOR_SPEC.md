# SEQUENTIAL DETECTOR SPEC — Phase 3B

§§23–24. **Known prior art. No algorithmic novelty is claimed** — this is
Page's 1954 CUSUM, applied as an engineering baseline.

**Status: the §23 constant gate is PASSED and the Phase 3B arm comparison
(T0–T4) is COMPLETE.** §§1–4 below are the frozen definition and the
verification that licensed it; §5 records the outcome.

---

## 1. THE DEFINITION, FROZEN

Recovered from the historical artifacts, not re-invented:
`research/phase2/p1_offline_baselines.py` and
`research/phase2/results/baseline_comparison.json`.

    z_t = (lam_t − mu0) / sigma0        standardised PRE-TRANSFORM residual
    S_t = max(0, S_{t−1} + z_t − k)     one-sided CUSUM
    alarm when S_t > h

    k = 0.5      textbook, set by design
    h = 500      selected by rule, see §2

`lam` is the **pre-transform smoothed chi-square** the layer already computes
(`td.physics[n] = (lam, gate)`), not the consistency. §24 is explicit that the
rejected invented form `z = max(0, 1−c) · 10` must never be used, and it is
not. The historical file also records *why* the pre-transform quantity is the
right one: the consistency `exp(−0.5·max(0, lam−1))` floors every sub-unity
chi-square to exactly 1.0, which gave `sigma0 = 0` for gps, mag and battery on
the clean arm and made the detector unable to alarm anywhere but gps.

**Gating.** A gated-out or stale sample is not evidence and does not enter the
statistic. This mirrors what production does to the same quantity
(`online.py:613`) and is the one place the v1.1 construction had to be stated
explicitly rather than inherited.

## 2. WHERE h = 500 COMES FROM — AND WHY IT IS NOT TUNED

The textbook pair is `k = 0.5, h = 5.0`, for a one-sigma shift at an
in-control ARL of ~465 samples. **That pair failed here, and the historical
record keeps the failure**: the layer ticks at ~25 Hz, so a 100 s flight is
~2500 samples and `h = 5.0` predicts about five false alarms per flight.
Measured: 4 alarms on the clean nominal arm. Retained as a committed negative
result rather than quietly replaced.

The corrected rule:

> take the **smallest h from a fixed grid** for which the **clean nominal arm
> produces zero alarms**, evaluated **only on the clean arm, never on a fault
> outcome**.

Grid: 5, 10, 20, 50, 100, 200, 500, 1000. First value satisfying it: **500**.

This is constraint satisfaction on the in-control arm, not tuning against
detection performance. No fault outcome was consulted at any point.

## 3. THE §23 VERIFICATION — RESULT

§23 permits reuse **only if** the constants are still semantically valid under
v1.1 residual construction. Verified by
`engineering/v1_1/ablation/b4_verify.py`; full record in
`B4_CONSTANT_VERIFICATION.json`.

mu0/sigma0 re-derived from the v1.1 clean arm, then the historical selection
rule re-applied:

| h | clean-arm alarm ticks | zero? |
|---:|---:|---|
| 5 | 2681 | no |
| 10 | 2067 | no |
| 20 | 1343 | no |
| 50 | 503 | no |
| 100 | 274 | no |
| 200 | 132 | no |
| **500** | **0** | **yes** |
| 1000 | 0 | yes |

**Smallest h with zero clean alarms under v1.1: 500.** Identical to the
historical selection. The textbook `h = 5.0` fails again, harder.

    VERDICT: REUSABLE

So `k = 0.5, h = 500` may be carried into Phase 3B unchanged. Had the rule
selected a different h, §23 forbids silent reuse and the constants would have
been re-derived and relabelled.

## 4. THE COVERAGE LIMITATION — FOUND BY THE VERIFICATION, AND IT MATTERS

In-control statistics exist for **five** nodes: `gps`, `mag`, `battery`,
`motor_esc`, `vibration`. `baro` is excluded (`sigma0` degenerate on the clean
arm). **There is no per-IMU physics chi-square in this construction, so B4
cannot see `imu0` or `imu1` at all.**

Response at `h = 500` across the fault arms:

| scenario | node | first alarm | fault onset | latency |
|---|---|---:|---:|---:|
| `gps_spoof` | gps | 21.16 s | 20.0 s | **1.16 s** |
| `mag_emi` | mag | 25.08 s | 25.0 s | **0.08 s** |
| `power_sag` | motor_esc | 30.12 s | 30.0 s | **0.12 s** |
| `power_sag` | battery | 30.20 s | 30.0 s | **0.20 s** |
| `vibration_anomaly` | vibration | 28.08 s | 28.0 s | **0.08 s** |
| `gps_dropout` | — | **no alarm** | — | correct: a dropout is absence, gated out, and absence is not evidence |
| `imu0_bias_drift` | — | **no alarm** | — | **B4 is blind to IMU faults** |
| `dual_imu_failure` | — | **no alarm** | — | **B4 is blind to IMU faults** |

This shapes the architecture question and must not be glossed. The sequential
detector is fast where it applies — sub-100 ms on three of five mechanisms —
and **structurally cannot address the IMU faults**, which are precisely the
scenarios where Phase 3A found the trust arm doing its escalation work
(`dual_imu_failure` was one of only two scenarios where GRAPH and FLAT
differed at all).

So "replace trust with the standard method" is **not** an option this evidence
supports. A combined arm is the only one that could cover both, which is what
Phase 3B is for.

## 5. PHASE 3B OUTCOME

§25's five arms were run over §26's mechanism matrix. Full data in
`PHASE3B_ARCHITECTURE_RESULTS.csv` and `PHASE3B_PAIRED_DIFFERENCES.csv`;
decision in `ARCHITECTURE_DECISION.md`.

**Sequential is KEPT.** `T3 − T0` improves five of nine mechanisms and
regresses none:

| mechanism | trust-flat | flat+sequential | Δ |
|---|---:|---:|---:|
| `GNSS_RAMP_SLOW` | 32.48 s | **24.40 s** | **−8.08 s** |
| `VIBRATION_ANOMALY` | 34.16 s | **28.08 s** | **−6.08 s** |
| `MAG_DEGRADED` | 30.04 s | **25.08 s** | **−4.96 s** |
| `POWER_SAG` | 33.72 s | **30.12 s** | **−3.60 s** |
| `GNSS_RAMP_FAST` | 24.36 s | **21.16 s** | **−3.20 s** |

with **zero alarms on the clean arm**, reproducing the historical
zero-clean-alarm condition at `h = 500`.

**It does not replace trust**, for the reason §4 predicted: it is
right-censored on `GNSS_FIX_LOSS` and `DUAL_IMU_FAILURE`, which trust covers
at 26.00 s and 34.12 s.

Right-censored no-responses are kept right-censored throughout and never
converted into a latency; a test enforces it.
