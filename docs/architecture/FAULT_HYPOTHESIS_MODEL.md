# Fault Hypothesis Model

**Status:** SHADOW / ADVISORY ONLY · **Slice:** 3B
**Implementation:** `csia/diagnosis/hypothesis.py`, `csia/diagnosis/shadow.py`
**Tests:** `tests/test_hypothesis.py` · **Audit:** `docs/audit/CSIA_CAUSAL_DIAGNOSIS_AUDIT.md`

## 1. Inference semantics — deliberately not a softmax

The legacy diagnoser softmaxes 8 mutually exclusive labels, so
`P(power_fault)` and `P(gps_fault)` compete for one unit of mass. That is
correct for *"which single label"* and wrong for *"which causes are active"*.

**Hypotheses here are scored independently on [0, 1] and are NOT normalized
across the registry.** A root cause and its downstream effects may be
simultaneously true:

```
H_SHARED_POWER_DEGRADATION            (root, ACTIVE)
   ├── battery degraded               (affected source)
   └── motor_esc degraded             (affected source)
```

`sum(confidence) != 1` is an invariant, asserted by
`test_confidences_are_bounded_not_normalized`.

Separate outputs are emitted rather than one winner:

| Output | Meaning |
|---|---|
| `most_probable_root_cause` | Highest-ranked ACTIVE hypothesis, or `None` |
| `active_contributing_causes` | All hypotheses that reached ACTIVE |
| `affected_sources` | Union of affected sets over ACTIVE hypotheses |
| `alternative_hypotheses` | Still-plausible explanations (≥ EMERGING) |
| `residual_unexplained_evidence` | Degradation no supported hypothesis claims |
| `diagnostic_ambiguity` | 1 − (top₁ − top₂) confidence margin |

## 2. Scoring

`support` = mean degradation `(1 − c)` over **valid** required evidence, then:

- **Topology factor** — healthy *contradicting* evidence confirms a localized
  cause; if the relationships that should stay intact are also degraded,
  support is cut.
- **Temporal factor** — onset spread across required evidence:
  ≤ 2 s → 1.0, ≤ 5 s → 0.5, else 0. **A shared cause requires co-onset**
  (`support *= 0.30 + 0.70 × temporal`); a multi-source-independent
  hypothesis is instead favoured by *dispersed* onsets. This is the mechanism
  that stops coincidental faults being promoted to a common cause.
- **Arm time** (10 s) — priors, EW smoothers and gates are still converging;
  nothing is reported before it.
- **Dwell** (25 ticks = 1.0 s) — no single-tick conclusions.

## 3. Bounds (for eventual C implementation)

`MAX_HYPOTHESES = 32`, `MAX_SOURCES_PER_HYPOTHESIS = 8`, static registry, no
runtime hypothesis creation, stable ordering, deterministic tie-break by
registry index. Per-tick cost is O(hypotheses × required evidence).

## 4. UNKNOWN gating

`H_UNKNOWN_CROSS_SENSOR_INCONSISTENCY` activates only when **all** hold:

1. past arm time;
2. **≥ 2 distinct** unexplained relationships — it is *cross-sensor* by
   definition, and one lone degraded relationship is a single-source concern
   the legacy diagnoser already covers;
3. each strongly degraded (`c < 0.50`) and persistent (≥ 1 s);
4. residual ≥ 0.35;
5. no supported hypothesis above 0.45.

Condition 2 exists because of a measured false activation: the scripted
yaw-in-place manoeuvre drives `attitude_gravity_mag` to ≈ 0.37 on **clean**
flight, and without it UNKNOWN reached 0.63 on healthy data.

## 5. Product boundary

`FailsafePolicy` reads the diagnosis posterior only to build a display string
(audit Q10) — no condition, threshold, dwell, level or action depends on it.
The shadow layer therefore *cannot* alter active behaviour. Every hypothesis
carries `SHADOW_ONLY`; every recommendation carries
`active_application_permitted = False`, asserted by test.
