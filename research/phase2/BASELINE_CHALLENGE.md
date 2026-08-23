# Phase-II Baseline Challenge — B0 through B4

**Purpose:** establish whether the measured gap can be closed by an established
method before any CSIA-v2 mechanism is designed. Section 7 of the brief gates
invention on this challenge showing a meaningful residual gap.

**None of these modify production code.** Each is a research-only path or a
feature flag, evaluated on the same flights so comparisons are paired.

---

## The gap actually being challenged

Per `PROBLEM_DEFINITION.md`, the safety-relevant gap in the tested grid is
**not** F3. At operationally significant magnitudes the joint blind region is
empty; what exists is:

> **6 of 9 significant GNSS position faults are detected by the autopilot
> estimator and not escalated by CSIA.** For those, the independent monitor
> contributes nothing to the escalation decision.

The challenge below therefore targets **escalation of significant faults under
the R10 zero-false-alert budget**, and Phase-II E1 runs in parallel to
determine whether a genuine joint blind region exists at slower slews.

---

## B0 — Native autopilot behaviour

**What:** no CSIA in the decision path. Record only the estimator's own
detection and the autopilot's own failsafe response.

**Why it is a real baseline, not a strawman:** the estimator detected **9 of 9**
significant cells. If native behaviour already covers the safety-relevant
region, CSIA's contribution to *escalation* on this fault class is
questionable, and that is a finding worth having.

**Implementation:** already measured — `ekf.detects` in
`research/wp_c8/results/response_surface.json`. No new code.

**Kill condition for the whole programme:** if B0 covers everything B1–B4 cover,
at equal or lower cost, the honest verdict is **A** and CSIA-v2 is abandoned
for this fault class.

---

## B1 — CSIA v1, frozen

**What:** the shipped layer at `848f556`, unmodified.

**Known result:** escalates 3 of 21 grid cells, 3 of 9 significant cells.
Escalation is duration-limited with boundary `N* + dwell ≈ 118` ticks
(`research/wp_c8/results/escalation_algebra.json`).

**Implementation:** already measured. No new code.

---

## B2 — Simple residual threshold

**What:** the minimum plausible additional logic. Alarm when the GPS physics
residual stays saturated for `k` consecutive ticks, bypassing the trust
recursion entirely. One integer parameter.

**Why this baseline:** the Phase-I algebra shows the residual detector *already
fires* at every magnitude — the loss is entirely in the accumulation stage. A
direct read of the residual is the most obvious way to recover that, and if it
works, no invention is justified.

**No learned models. No new sensor inputs.**

**Expected failure mode:** clean-flight residual excursions produce transitions,
violating the R10 zero budget. That is precisely what the trust recursion's
smoothing exists to prevent, so B2 is the experiment that prices that smoothing.

**Parameter:** `k` searched on the development partition only.

---

## B3 — Duration-aware accumulation correction

**What:** the obvious repair to the known accumulation defect. The Phase-I
algebra identifies the exact term:

```
N* = ln( M(T*-e_f) / (S_0(T_0-T*) + M(T*-e_f)) ) / ln(rho)

with  S_0(T_0-T*) = 125     (banked mass, dominant)
      M(T*-e_f)   =   1.0   (evidence margin)
```

The delay is set by `S_0 = 1/(1-rho_max) = 500`, the concentration cap. B3 caps
the accumulated mass at `S_max < 500` and re-measures.

**This is deliberately kept separate from F1.** It addresses escalation
(F2/the significant-cell gap) and does nothing for applicability loss.
Conflating them was a Phase-I error the four-quantity decomposition exposed.

**Why it must be tried before inventing:** if a single existing constant closes
the gap inside the false-alert budget, a new mechanism is unjustified and the
verdict is **B**.

**Expected failure mode:** lowering `S_max` shortens the memory that suppresses
clean-flight noise, so the R10 budget is the binding constraint. The question
is whether a value exists that satisfies both.

---

## B4 — Classical model-based FDI baseline

**What:** a **CUSUM change detector on the GPS position-vs-inertial innovation
sequence**, with drift parameter and decision interval set by design rather
than tuned to the outcome.

**Why this one, specifically:**

- The measured phenomenon is a *small persistent shift in a residual sequence*
  — 2.9 m/s walk-off, residual saturated but escalation absent. That is the
  textbook change-detection problem, and CUSUM is the standard sequential test
  for a shift of unknown onset in a residual stream (Page 1954; standard in
  model-based FDI, e.g. Gustafsson, *Adaptive Filtering and Change Detection*).
- It is the natural comparator because it is **explicitly duration-aware by
  construction** — it accumulates evidence rather than thresholding an
  instantaneous value — which is exactly the property B1 lacks.
- **The repository already names it.** `docs/REQUIREMENTS.md` R16 records the
  slow-IMU-bias blind spot with the tracked remedy "issue #1
  (dual-timescale CUSUM)". Choosing CUSUM is therefore not an outside import;
  it is the project's own already-identified method, applied to a second
  phenomenon it was never tried on.

**Not chosen weakly:** the comparison uses a properly parameterised CUSUM with
the drift set from the clean-flight residual distribution measured on the
nominal arm, not a hand-picked constant.

**If B4 closes the gap inside the budget, the verdict is A** — an established
method solves the problem, and the CSIA-v2 invention is abandoned. That is an
explicitly acceptable and useful outcome.

---

## What is deliberately excluded at this stage

| Excluded | Reason |
|---|---|
| Any neural / GNN / transformer method | Section 8: not until simpler baselines fail *and* there is a measurable reason such a model is necessary. No such reason exists yet. |
| New sensor inputs (`satellites_used`, `noise_per_ms`, DOP) | These address **F1**, not the escalation gap. Mixing them in would confound the comparison. Tracked separately. |
| Threshold retuning presented as a method | Section 14. B2/B3 parameters are searched on a development partition and reported as parameters, not as inventions. |

---

## Evaluation

All candidates are scored by `CANDIDATE_REGISTRY.yaml`'s fixed contract, on
identical flights, with the development / protected partition split declared
before any search. The R10 budget (zero clean-flight transitions) is a hard
constraint, not a weighted term.
