# Phase-II Problem Definition

**Baseline commit:** `848f556` · **Status:** frozen, `BASELINE_MANIFEST.json`
**This document defines the tested fault trajectory space and the observed joint
miss set. It does not propose a solution.**

---

## 0. The headline, before the detail

The Phase-II brief nominates **F3 (dual-monitor blind region)** as the initial
target "unless repository evidence shows another phenomenon is more
fundamental." Applying the project's own significance threshold to the existing
grid, repository evidence does show exactly that.

| Restricted to operationally significant faults | Cells |
|---|---|
| Total significant cells in the tested grid | 9 of 21 |
| **Jointly blind — neither monitor detects** | **0** |
| **CSIA does not escalate; the estimator carries it alone** | **6** |

**At magnitudes the project itself requires the system to detect, the joint
blind region in the tested grid is empty.** F3 in its safety-relevant form is
not demonstrated by the evidence that motivated it. What *is* demonstrated is
that for two thirds of significant GNSS position faults, escalation depends
entirely on the autopilot's estimator and the independent monitor contributes
nothing.

That is a single-point-of-failure finding, not a blind-region finding, and it
is a restatement of **F2**, not F3.

**This does not close F3.** The grid's slowest ramp is 20 s and the blind wedge
widened monotonically with slew. Section 5 defines the smallest experiment that
decides it.

---

## 1. The significance threshold, and where it comes from

Section 6 of the brief forbids choosing a convenient budget after seeing
results. Two thresholds are needed and both are taken from artifacts that
predate Phase II.

### 1.1 False-alert budget

| | |
|---|---|
| Source | `docs/REQUIREMENTS.md` **R10** |
| Requirement | "Clean nominal flight shall produce zero failsafe transitions" |
| Verified by | `test_failsafe_clean_no_false_alarms`, `campaigns/bench.json` |
| Measured baseline | 50 flights / 0.8 h, 0 events, 0.0/hr, Poisson 95% [0.0, 4.4] |
| **Phase-II budget** | **0 failsafe transitions on clean nominal scenarios** |

Fixed for the duration of Phase II. A candidate that produces any clean-flight
transition fails, regardless of what it gains.

### 1.2 Operational significance threshold

A fault too small to matter cannot constitute a blind spot. Not detecting a
2 m GNSS error is correct behaviour. The threshold is taken from the project's
own reference fault:

```
csia/scenarios.py:27
  "gps_spoof": Fault("gps_spoof", "gps", 20.0, 15.0, {"drift": (3.0, 1.0, 0.0)})
  "GPS spoof 20-35 s: position walks off ~3.2 m/s, Doppler clean"
```

That is the GNSS fault the system claims to detect, and
`docs/REQUIREMENTS.md` records TPR **1.00** (n=25, 95% CI [0.87, 1.00])
against it. Its total displacement is ~3.2 m/s × 15 s ≈ **48 m**.

> **Θ_significant = { θ : total induced position error ≥ 48 m }**

Chosen as *total displacement* rather than rate: a rate threshold is
meaningless for step injections, and an earlier pass of this analysis produced
a nonsense "12.1 m/s" by dividing a 2.4 m step by one GPS sample interval. The
displacement form is unambiguous across every trajectory in the grid.

**This threshold is conservative against our own interest** — it excludes cells
from the blind region and therefore makes the case for invention harder, not
easier.

---

## 2. The tested fault trajectory space

Only parameters the harness actually supports are represented.

```
θ = ( amplitude, slew, duration, onset, context )
```

| Axis | Symbol | Tested values | Units | Notes |
|---|---|---|---|---|
| Amplitude | `a` | 0.5, 2.0, 5.6, 22.3, 55.7, 556.6, 5566.0 | m | log-spaced, below noise floor to far above saturation |
| Slew | `s` | 0 (step), 4, 20 | s to full amplitude | **20 s is the slowest tested** |
| Duration | `d` | 1, 2, 3, 4, 6, 10 | s held, then released | separate sub-grid, amplitude ∈ {55.7, 5566.0} |
| Onset | `t₀` | 30, 45, 60, 75 | s | climb / early / mid / late cruise |
| Context | `c` | climb, cruise, descent | — | one cell each |

**Direction is not a supported axis.** The harness injects on
`SIM_GPS_GLITCH_X` (latitude); a meaningful direction sweep would require
joint X/Y injection and is not implemented. Recorded as a gap, not simulated.

**Not represented, and therefore not claimed:** partial constellation geometry
(the satellite ladder showed `SIM_GPS_NUMSATS` does not affect the fix flag in
either build), carrier-to-noise decay, multipath, spoofing with consistent
Doppler.

---

## 3. The monitors

| Symbol | Monitor | Detection criterion | Source of criterion |
|---|---|---|---|
| `M_ekf` | Autopilot estimator | `EKF_STATUS_REPORT.pos_horiz_variance > 0.8` | ArduPilot's own `FS_EKF_THRESH` default; the variances are normalised innovation test ratios |
| `M_csia,det` | CSIA residual | gps physics component < 0.10 (saturated) | `csia/trust_engine/engine.py` consistency map |
| `M_csia,esc` | CSIA escalation | failsafe level leaves NORMAL | `csia/runtime/failsafe.py` |

**Detection and escalation are recorded separately and never pooled.** The
Phase-I crux was that the CSIA residual saturates at every magnitude while
trust never crosses threshold; a single "detected" column erases it.

Per monitor `M_i` and condition θ the harness records:

```
detected | not_detected
escalated | not_escalated
detection_time      (s from injection)
false_alert         (clean-arm transitions)
```

---

## 4. The observed joint miss set

```
B_baseline = { θ ∈ Θ_tested : all required monitors fail to escalate }
```

Measured, `research/wp_c8/results/response_surface.json`, 21 amplitude × slew
cells:

| Coverage | By detection | By escalation |
|---|---|---|
| both | 12 | 3 |
| estimator only | 0 | 9 |
| CSIA only | 1 | 0 |
| **neither** | **8 (38%)** | **9 (43%)** |

Restricted to `Θ_significant` (≥ 48 m):

| err (m) | slew (s) | rate (m/s) | EKF | CSIA det | CSIA esc |
|---|---|---|---|---|---|
| 58.0 | step | — | yes | yes | **no** |
| 558.9 | step | — | yes | yes | **no** |
| 5568.2 | step | — | yes | yes | **no** |
| 58.0 | 4 | 14.5 | yes | yes | **no** |
| 558.9 | 4 | 139.7 | yes | yes | **no** |
| 5568.2 | 4 | 1392.1 | yes | yes | yes |
| 57.9 | 20 | 2.9 | yes | yes | **no** |
| 556.6 | 20 | 27.8 | yes | yes | yes |
| 5566.0 | 20 | 278.3 | yes | yes | yes |

> **|B_baseline ∩ Θ_significant| = 0** by detection.
> **6 of 9** significant cells are not escalated by CSIA.

---

## 5. What this leaves open, and the experiment that decides it

**The grid is truncated exactly where the interesting behaviour lives.** The
blind wedge widened monotonically with slew — a step is caught above 2 m, a 4 s
ramp is missed to 5.6 m, a 20 s ramp is missed to 22.3 m — and 20 s is the
slowest ramp anyone has run. Extrapolating the wedge is *not* evidence; the
brief forbids inferring boundaries beyond tested evidence.

The single cell that matters most is **57.9 m over 20 s = 2.9 m/s**, just below
the project's own 3.2 m/s reference rate. The estimator caught it. CSIA did
not escalate it.

**Decisive experiment (Phase-II E1):** extend the slew axis to 60, 120 and
240 s at amplitudes 55.7 m and 556.6 m — that is, walk-offs of 0.24 to 9.3 m/s
that all exceed the significance threshold in total displacement.

| Outcome | Consequence |
|---|---|
| Estimator still detects every significant cell | **F3 refuted at significant magnitude.** The joint blind region is confined to errors too small to matter. Phase II redirects to F2. Verdict **D** for F3. |
| Estimator fails on slow significant walk-offs | **F3 confirmed and bounded.** Phase II has a real target and a measured region to close. Verdict **C** if established baselines then fail. |
| CSIA escalates where it did not before | The 20 s result was slew-specific rather than a general escalation defect. |

This is the smallest experiment that distinguishes "curiosity" from "result",
and the brief requires that distinction be reportable either way.

---

## 6. Interpolation policy

Every cell in section 4 is a measured flight. **No boundary between cells is
claimed.** The wedge described in Phase-I prose is a description of measured
corner cells, not a fitted contour. Where a later document draws a continuous
boundary it must be labelled as interpolation with the model stated.

---

## 7. Known limits carried forward, unchanged

- All Phase-I numbers come from **ArduCopter 3.3 SITL (2015)**. Modern
  replication status: `research/phase2/results/modern_replication.json`.
- The 26-log real corpus is **unannotated**, so `F_h` does not exist in it and
  `T_FH` / `T_SOFH` are permanently unmeasurable from it.
- `SIM_WIND_SPD` applies no force in the 3.3 build; the Phase-I campaign varied
  one axis (home site) and was described as varying two.
- Direction is not a tested axis.
