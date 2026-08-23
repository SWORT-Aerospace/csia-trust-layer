# CSIA Causal-Diagnosis Audit

**Baseline:** commit `9d50671` · **Date:** 2026-08-03 · **Slice:** 3B Part 1
**Subject:** `csia/diagnosis/bayes.py`, its consumers, and its native counterpart.
**Method:** read from source and executed. No inference.

---

## 1. The twelve questions, answered precisely

### Q1 — Why can the current model represent only one source?

`CAUSES` (`bayes.py:44-56`) is a **flat dict of 8 mutually exclusive labels**,
and each label conflates *source* with *mechanism*: `imu0_bias_drift` encodes
both "imu0" and "bias drift". The output is a categorical posterior over those
8 labels. There is no field anywhere for an affected-source **set**, so a
multi-source explanation has nowhere to be written even if the evidence
supported it.

### Q2 — Does the posterior assume mutual exclusivity?

**Yes, structurally.** `bayes.py:112-113` (online) and `:153-154` (batch):

```python
post = np.exp(score); post /= post.sum()
```

A softmax forces Σ P = 1. `P(power_fault)` and `P(gps_fault)` are in direct
competition: evidence for one mathematically suppresses the other. This is
correct for "which single label", and wrong for "which causes are active".

### Q3 — Can more than one cause be true simultaneously?

**No.** Not representable. Two genuinely concurrent faults split probability
mass and can leave *both* below any confidence threshold — the system reports
uncertainty when it should report two findings.

### Q4 — Is a source treated as identical to a cause?

**Effectively yes.** `CAUSE_TO_SOURCE` (`metrics/latency.py`) is a 1:1 map
built precisely because the label *is* the source. `nominal` and
`unexpected_maneuver` map to `None` and are the only exceptions.

### Q5 — Can one cause affect several sensors?

**In the evidence, yes; in the output, no.** `power_fault` already lists five
features spanning `battery`, `motor_esc` and the IMU-motor edges
(`bayes.py:51-52`). The likelihood model is genuinely multi-sensor. The
*result* still collapses to one label with no affected-source list.

### Q6 — Can one sensor participate in several hypotheses?

**Yes, in features.** `accel_motor_current` appears in both
`imu0_bias_drift` and `power_fault`. The feature layer is already a
many-to-many structure; only the output is 1-of-K.

### Q7 — Can it represent a healthy sensor corrupted by an external cause?

**No.** There is no distinction between *"this sensor is broken"* and *"this
sensor's readings are being corrupted by something else"*. Both produce the
same single label, and the operational consequence differs completely:
one warrants replacing a unit, the other warrants investigating a shared rail.

### Q8 — Can it distinguish estimator failure from raw-sensor failure?

**No.** There is no estimator node in the trust graph (8 nodes, all physical
sensors) and no estimator hypothesis. See §3.

### Q9 — Can it represent uncertainty without picking a winner?

**No.** Softmax always yields an argmax. `nominal` absorbs mass under weak
evidence, so "healthy" and "I don't know" are the same output. There is no
`UNKNOWN` state distinguishable from `NONE`.

### Q10 — What does active failsafe logic consume? ⭐

**Nothing.** `FailsafePolicy._conditions` (`failsafe.py:108-109`) calls
`state.top_causes(1)[0]` **only** to build the human-readable `diag` string
embedded in reason text. No condition, threshold, dwell, level or action
depends on the posterior — verified by reading every use of `diag` in
`failsafe.py` (lines 115, 125, 134, 149, 157, 164, 170: all f-string
interpolation).

**This is the single most important finding for slice 3B.** The diagnosis
layer can be extended arbitrarily without any possibility of changing active
failsafe behavior. The product boundary is enforced by the existing
architecture, not merely by discipline.

### Q11 — What exists in Python but not native C?

`csia_diag_step` (`csia_core.c:133`) implements the same math with
`CSIA_MAX_CAUSES = 32`, parity-tested. It takes a **flat `low[nc][nf]`
matrix** — a 1-of-K structure with no notion of affected-source sets, shared
resources, or hierarchy. **Any hypothesis layer added in this slice is
Python-only** and must be declared so.

### Q12 — Which existing relationships support a legitimate common-cause demo?

Verified from the topology (11 edges) and the scenario catalog:

| Candidate | Verdict |
|---|---|
| **Shared power** | **AVAILABLE NOW.** `power_sag` already injects **two** faults from **one** physical cause — `Fault("power_sag","battery",30,6)` **and** `Fault("power_sag","motor_esc",30,6)` — and edges `motor_esc↔battery`, `baro↔battery`, `motor_esc↔vibration` connect the affected set. |
| Independent multi-fault contrast | **AVAILABLE NOW.** `dual_imu_failure` injects imu0 @25 s and imu1 @27 s with *opposite* signs — two independent faults at similar times, the exact confusable case. |
| Estimator divergence | **NOT AVAILABLE.** No estimator node, no innovations, no estimator health topic in the graph. Simulation-only architecture at best. |
| Shared clock / bus | **NOT AVAILABLE.** No timing or transport faults exist (ontology is 6 value-domain kinds). |
| Shared environment | Partially — `mag_emi` is single-source; no multi-sensor environmental fault exists. |
| **Dual-GNSS common mode** | **MUST NOT BE BUILT.** The graph contains **one** GPS node. Fabricating a second would be inventing an architecture. |

---

## 2. Smallest compatible extension

The audit's conclusion, per the instruction not to change code until it is
identified:

1. **Add a parallel hypothesis layer**, consuming the *same* comparator
   features. Do not modify `DiagnosisCore`, `CausalDiagnosis`, `CAUSES`,
   priors, smoothing constants, or the softmax — every existing number stays
   bit-identical.
2. **Do not normalize across hypotheses.** Score each independently so a root
   cause and its downstream effects can be simultaneously true (§3 of
   `FAULT_HYPOTHESIS_MODEL.md`).
3. **Emit shadow output only.** `FailsafePolicy` already ignores the
   posterior, so no guard is needed to prevent active use — but the
   authorization field makes the intent explicit and testable.
4. **First scenario: shared power**, because it exists in the repository
   today and requires no new fault mechanism.

## 3. Estimator hypotheses — availability

| Required datum | Present? |
|---|---|
| Raw sensor measurements | Yes |
| Estimator outputs | **No** — the complementary attitude filter in `prediction/attitude.py` is CSIA-internal, not a vehicle estimator |
| Estimated state / innovations | **No** |
| Estimator health indicators | **No** |

`H_ESTIMATOR_DIVERGENCE` can therefore be defined and tested **in simulation
only**, with real-log validation recorded as **unavailable**. It must not be
described as operationally validated.

## 4. Fixed-size assumptions to preserve

`CSIA_MAX_CAUSES = 32`; feature count bounded by 11 edges + 8 physics + 4
temporal = 23; per-tick cost is O(causes × features). Any hypothesis layer
intended for eventual C implementation must declare a fixed maximum
hypothesis count and maximum sources per hypothesis, with no runtime
allocation.
