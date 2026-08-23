# Shared-Power Generalization Audit

**Baseline:** commit `86b19f9` · **Date:** 2026-08-03 · **Slice:** 3C Part 1
**Subject:** why `H_SHARED_POWER_DEGRADATION` generalizes 14/16 on development
parameters but 1/4 on previously held-out combinations.
**Method:** measured. Per-feature degradation `1 − c`, averaged over the window
`[onset+1 s, onset+5 s]`, gate-masked.

---

## 1. Measurement

| depth_v / rpm_loss | phys_battery | temp_battery | phys_motor_esc | accel_motor_current | accel_esc_rpm | **MEAN** | outcome |
|---|---|---|---|---|---|---|---|
| **1.2 / 350** (development) | 1.000 | 0.486 | 0.999 | **0.000** | 0.954 | **0.688** | PASS |
| 1.5 / 500 (held-out) | 1.000 | 0.681 | 1.000 | **0.000** | 0.997 | **0.736** | PASS |
| 0.5 / 620 (held-out) | 0.982 | 0.011 | 1.000 | **0.000** | 1.000 | **0.599** | FAIL (dwell) |
| 0.75 / 200 (held-out) | 0.998 | 0.086 | 0.806 | **0.000** | 0.472 | **0.472** | FAIL |
| 2.1 / 120 (held-out) | 1.000 | 0.913 | 0.368 | **0.000** | 0.000 | **0.456** | FAIL |

`support = mean(1 − c)` over the five `required_evidence` features
(`hypothesis.py::_score`), then multiplied by topology and temporal factors.

---

## 2. Three distinct defects

### D-1 — The arithmetic mean conflates "how many sources" with "how severe"

The scoring function averages over a **flat feature list that spans two
different sources**. Battery-side features (`phys_battery`, `temp_battery`)
and motor-side features (`phys_motor_esc`, `accel_esc_rpm`) degrade by
*different amounts* depending on the injected amplitude ratio. A mean over
both requires them to degrade **together and comparably** — which is true only
near the development ratio 1.2 V : 350 rpm.

This is the primary mechanism. It is not a threshold problem: the *shape* of
the statistic encodes one amplitude relationship.

- **2.1 / 120** — strong battery (1.000, 0.913) but weak motor (0.368, 0.000).
  A real shared-power event with a stiff motor load. Mean collapses to 0.456.
- **0.75 / 200** — moderate both ways. Mean 0.472.

### D-2 — `accel_motor_current` is **0.000 in every case**, including development

The feature never contributes, yet occupies 1/5 of the mean — capping the
achievable score at **0.8** before any topology or temporal factor is applied.

This is not a bug in the feature; it is correct physics being misused. The
`imu0↔motor_esc` edge validates *coherence* between acceleration and motor
current. A power sag reduces both **coherently**, so the edge correctly stays
green. It is a valid consistency check that is **simply not diagnostic for
this fault class**, and listing it as `required_evidence` was the error.

### D-3 — `temp_battery` is the most ratio-sensitive feature

Ranges 0.011 → 0.913 across the same fault class. It tracks the thermal
signature of the sag, which depends strongly on depth and duration. Weighting
it equally with `phys_battery` (which is ≥ 0.98 in **all five** cases, i.e. a
near-perfect battery indicator) discards a reliable signal in favour of a
fragile one.

---

## 3. The specific questions answered

**Why do matching development ratios pass?** Because the mean is maximised
when battery-side and motor-side features degrade to a similar degree, which
happens only near 1.2 V : 350 rpm.

**Why do mismatched ratios stay below activation?** Because a strong effect on
one source cannot compensate for a weak effect on the other under an
arithmetic mean over a mixed-source feature list — and one always-zero feature
removes a further 20% of headroom.

**Why does topology ablation produce no measurable difference?** Because
topology is applied only as a *multiplier derived from contradicting
evidence* (`support *= 0.35 + 0.65 × intact`). In every shared-power scenario
the contradicting features (`redundant_imu`, `phys_gps`, `phys_mag`) remain
healthy, so `intact = 1.0` and the multiplier is **exactly 1.0** — a no-op.
The topology declaration `SHARED_RESOURCES` is never consulted at all: it is
data with no reader. **Topology is currently decorative.**

**Why does confidence rank correctly but fail dwell?** Ranking depends only on
the *relative* ordering of hypotheses, which the mean preserves — battery
evidence alone is enough to put shared-power first. Activation depends on the
*absolute* value crossing 0.60 for 25 consecutive ticks. Cases at 0.456–0.599
rank first but never clear the bar, and 0.599 clears it only intermittently,
failing dwell.

---

## 4. Sensitivity summary per feature

| Feature | Definition | Depth sens. | RPM sens. | Ratio sens. | Uses topology | Duplicate? |
|---|---|---|---|---|---|---|
| `phys_battery` | V vs OCV−IR self-model | High | None | **None** | No | No |
| `temp_battery` | Holt temporal stability | **Very high** | Low | **High** | No | Partial (with phys_battery) |
| `phys_motor_esc` | current ∝ rpm³ self-model | None | High | **High** | No | No |
| `accel_esc_rpm` | imu1↔motor_esc edge | Low | **Very high** | **High** | No | Partial (with phys_motor_esc) |
| `accel_motor_current` | imu0↔motor_esc edge | **None** | **None** | None | No | **Dead for this fault** |

---

## 5. Required redesign (not implemented in this audit)

1. **Per-source normalization first.** Aggregate each source's own indicators
   into one degradation score relative to that source's own expected range,
   then reason over the *set* of degraded sources. This removes the
   cross-source amplitude coupling that is the root cause.
2. **Drop `accel_motor_current`** from `required_evidence` — retain it as
   *contradicting* evidence, where staying green is informative.
3. **Combine per-source scores with a geometric mean**, which requires *both*
   sources to be degraded (unlike an arithmetic mean, where one can
   compensate) without the brutality of `min`.
4. **Make topology load-bearing** by consulting `SHARED_RESOURCES` for
   membership, expected-affected-set derivation, and contradiction when a
   strongly coupled member stays healthy — or delete it as unused.

Threshold changes are explicitly **not** part of the remedy. The defect is the
shape of the statistic.
