# WP-A2 Part B — Threshold Provenance

**Question:** were CSIA's detection thresholds calibrated using the same
synthetic injections they are then evaluated against?

**Verdict: `INDETERMINATE` — permanently, and for a structural reason.**

Two components of the question *are* determinable, and both resolve to
`NOT_DISJOINT`. The third cannot be answered from this repository and no
future work inside it can change that.

---

## 1. Why the verdict is permanent, not pending

`csia/prediction/comparator.py` — which holds every σ literal and every gate
constant — has **exactly one commit in its entire history**:

```
$ git log --oneline --follow -- csia/prediction/comparator.py
f2786f6 CSIA Trust Layer v0.6.0 — cross-sensor trust runtime, failsafe, …
```

The same is true of `tests/scenarios/test_fault_scenarios.py` and of every
individual σ literal probed with `git log -S`. Nothing was tuned *inside*
version control.

That is not evidence of no tuning. `f2786f6` is the **root commit** of the
repository (`git rev-list --max-parents=0`), a single squashed import of 56
files that already contains the sensor models, the comparator, the scenario
catalog, the fault harness, and `data/real_logs_report.json` — the whole
system and its evidence, arriving at once on 2026-07-12.

**All pre-v0.6.0 development history is absent from this repository.** Whether
the σ values were fit against these same injections before the import is not
recorded anywhere a reader can reach.

> **This verdict cannot be closed by any work in this repository.** It is not
> an open action item, a TODO, or a gap awaiting a future measurement. Closing
> it requires evidence that does not exist here: original design notes
> deriving each σ from sensor physics, component datasheets supporting the
> declared noise classes, or the pre-import git history if it survives on
> another machine. Absent one of those, `INDETERMINATE` is the final answer
> and should be reported as such to any reviewer who asks.

---

## 2. Component 1 — test-assertion thresholds: `NOT_DISJOINT`

Unambiguous, and stated in the source itself.
`tests/scenarios/test_fault_scenarios.py:22-27`:

```python
# scenario -> expectations. Measured performance (2026-07, seeds fixed):
#   gps_spoof:  min 0.59, detect 2.2 s, P=0.89
#   imu0_bias:  min 0.77, detect 13.0 s (slow ramp), P=0.99, imu1 min 0.86
#   mag_emi:    min 0.28, detect 1.5 s, P=1.00
#   power_sag:  min 0.40, detect 1.6 s, P=1.00
#   vibration:  min 0.17, detect 2.6 s, P=1.00
CASES = {
    "gps_spoof": dict(target="gps", cause="gps_fault", drop_below=0.72,
                      detect_within=5.0, p_cause=0.75, …),
```

The bounds are placed below the measured values **from those same seeded
runs**. The module docstring states the intent plainly: *"fixed thresholds set
below measured performance (so regressions fail loudly)."*

This is correct regression-test design and should not be changed. Its
consequence for external claims is the point:

> These 8 tests cannot fail for insufficient detection *capability*. They can
> only fail for *regression*. Passing them is therefore not independent
> evidence that CSIA detects faults — it is evidence that CSIA still behaves
> as it behaved in July 2026.

WP-A2 E4 re-measured every value and reproduced the in-source comment exactly
(gps_spoof 2.16 s / min 0.5905 / P 0.8934 against the comment's 2.2 / 0.59 /
0.89), confirming both the provenance and the arithmetic. It also quantified
how much degradation would pass silently:

| Scenario | latency measured → asserted | slack | min-trust measured → asserted | slack |
|---|---|---|---|---|
| gps_spoof | 2.16 s → < 5.0 s | **+2.84 s** | 0.5905 → < 0.72 | +0.129 |
| imu0_bias_drift | 13.0 s → < 16.0 s | **+3.00 s** | 0.7657 → < 0.85 | +0.084 |
| mag_emi | 1.48 s → < 4.0 s | **+2.52 s** | 0.2764 → < 0.50 | +0.224 |
| power_sag | 1.60 s → < 4.0 s | **+2.40 s** | 0.3991 → < 0.60 | +0.201 |
| vibration_anomaly | 2.56 s → < 5.0 s | **+2.44 s** | 0.1658 → < 0.45 | +0.284 |

Detection could take roughly **twice as long** in every scenario and still
pass. The min-trust bounds are tighter, `imu0_bias_drift` tightest at +0.084.

---

## 3. Component 2 — `field_mode` on the real corpus: `NOT_DISJOINT`

Already established by the Slice-3A provenance audit (D-03) and not disputed
here:

- All 26 logs influenced thresholds. **`field_mode` exists because of them.**
- All 26 influenced architecture.
- Eligible for held-out evaluation: **0 of 26. Held-out exposure 0.000 h.**

The README states it directly: the field-mode machinery was *"all of it forced
into existence by real logs."* The corpus is a training set, and the
false-alarm number computed on it is a training-set number.

---

## 4. Component 3 — system σ, gates and failsafe levels: `INDETERMINATE`

What can be said in favour of physical derivation, without upgrading the
verdict:

- The sensor models declare datasheet-class noise, not fitted values:
  `ACCEL_NOISE_SIGMA = 70e-6 * G * sqrt(50.0)` (ICM-42688-P noise density over
  a 50 Hz bandwidth), `NOISE_UT = 0.03  # RM3100 class`,
  `PRESSURE_NOISE_HPA = 0.012  # ~10 cm altitude RMS at high OSR`.
- Comparator σ values are commented as physical budgets rather than fits —
  e.g. the `attitude_gravity_mag` σ *"budgets ~2-3 deg of complementary-filter
  attitude error leaking into the tilt compensation, on top of mag noise."*
- The σ magnitudes are consistent with budgets rather than tight fits:
  `redundant_imu` σ = 0.09 m/s² sits roughly 13× above the white-noise floor
  of the differenced IMU pair (≈6.9e-3 m/s² per axis), leaving room for bias
  and misalignment.

**None of this is proof.** A σ can be described as a physical budget in a
comment and still have been nudged until the scenarios passed. Consistency
with derivation is not derivation. The verdict stands at `INDETERMINATE`.

There is one structural argument worth recording on the other side: the σ
values were authored *before* the repository existed and have never been
touched since, across 48 commits and a test suite that grew from 39 to 448.
Iterative tuning-to-the-test usually leaves fingerprints — repeated small
edits to constants alongside changing expected values. **No such fingerprints
exist here.** But the window in which they would have been left is precisely
the window the repository does not cover.

---

## 5. What this means for external claims

The synthetic caveat is necessary but **not sufficient**. Any claim resting on
the five scripted scenarios must carry two caveats, not one:

1. **Synthetic.** The faults are injected into simulated sensor streams from
   fixed seeds. No real fault data is involved.
2. **Regression-bounded.** The assertions are bounds derived from these same
   runs. Passing indicates no regression, not detection capability.

And any claim resting on the 26-log corpus must carry a third:

3. **Training set.** All 26 logs shaped the tolerances they are evaluated
   against. Held-out exposure is 0.000 h.

Whether the *system* thresholds share that circularity is unknown and
unknowable from here. A reviewer is entitled to ask; the honest answer is that
the repository's history begins after the constants were fixed, and that
answering it requires external evidence.
