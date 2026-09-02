# GOLDEN TRACE PLAN — Phase 4 §37

The plan for proving a future C/C++ port equivalent to the Python reference.

> **Nothing is implemented here, and no numerical value is frozen.** §37 is
> explicit: golden-trace numbers are not frozen until the Phase 4 default
> architecture and API are final. This document fixes **which cases, which
> fields, and which comparison rule** — the parts that can be decided now
> without pre-committing to numbers that a later fix would invalidate.
>
> **There is no C code in this repository.** G6 is `NOT_STARTED`.

---

## 1. THE CASES — ELEVEN

Nine from the Phase 3B mechanism matrix, plus the two ingest-layer sentinel
cases, which exercise a different layer and would otherwise be unported and
untested.

| # | case | source | why it is in the set |
|---|---|---|---|
| 1 | `clean` | scenario | the in-control control; must produce no transition and no CUSUM alarm |
| 2 | `GNSS_RAMP_SLOW` | `gps_spoof`, slow drift | the only case where the sequential channel responds and the diagnosis never attributes |
| 3 | `GNSS_RAMP_FAST` | `gps_spoof` | trust and sequential both respond; ordering matters |
| 4 | `GNSS_FIX_LOSS` | `gps_dropout` | **the support case.** High posterior, zero discriminating evidence |
| 5 | `IMU0_BIAS_DRIFT` | `imu0_bias_drift` | correct non-escalation; redundancy working |
| 6 | `DUAL_IMU_FAILURE` | `dual_imu_failure` | the only case where trust modes differ (0.28 s) |
| 7 | `MAG_DEGRADED` | `mag_emi` | sub-100 ms CUSUM response |
| 8 | `POWER_SAG` | `power_sag` | three sequential nodes alarm together |
| 9 | `VIBRATION_ANOMALY` | `vibration_anomaly` | largest sequential gain |
| 10 | `BATTERY_SENTINEL` | Phase 1 fixture | `current_battery = -1` after a real reading — R1 supersession |
| 11 | `MAG_SENTINEL` | Phase 1 fixture | all-zero magnetometer triple |

Cases 10 and 11 are **ingest-layer** and have no scenario in the catalogue;
they run from the Phase 1 defect fixtures
(`engineering/v1_1/KNOWN_DEFECTS_POST_FIX.json`) and exercise R1–R5 rather
than the trust update.

## 2. WHAT MUST BE COMPARED

Three tiers, because they cannot share a tolerance.

### Tier A — EXACT. Any difference is a failure.

Discrete state. There is no such thing as an off-by-a-little failsafe level.

| field | |
|---|---|
| `assurance.level` | per tick |
| `function_eligibility[*].state` | per tick, all five functions |
| `function_eligibility[*].reason_codes` | per tick, as a **set** |
| `diagnosis.leader` | per tick |
| `diagnosis.ambiguity`, `identifiable`, `support_state` | per tick |
| `diagnosis.non_identifiable_against` | per tick, as a set |
| `sequential.alarming` | per tick, as a set |
| `evidence.fresh`, `missing_reason` | per tick |
| `evidence.active_relations` / `suppressed_relations` / `suppression_reasons` | per tick |
| ledger `event_type`, `subject`, `previous_state`, `new_state`, `reason_codes` | per event |
| ledger event **count and order** | per case |

### Tier B — NUMERIC, tolerance to be declared at Phase 5 start.

| field | note |
|---|---|
| `trust.nodes[*]` | float32 on target vs float64 in Python is the dominant term |
| `diagnosis.posterior`, `score_margin` | softmax over a smoothed log-likelihood; accumulates |
| `sequential.S[*]` | a running sum, so error accumulates monotonically — the worst case in the set |

**The tolerance is not declared here and must not be guessed.** It has to come
from a stated arithmetic argument (float32 epsilon, accumulation length, the
smoothing time constants) plus a measured distribution, not from whatever the
first port happens to produce. Declaring it after seeing the port's error is
the failure mode this whole programme has been avoiding.

### Tier C — NOT COMPARED.

`event_id`, `content_sha256`, `previous_event_hash`, `configuration_hash`,
`software_sha`, wall-clock timings. These hash the **implementation**, not the
behaviour; a port must reproduce the event *sequence*, not the Python build's
hashes.

## 3. THE COMPARISON RULE

> A tier-A difference on **any** tick of **any** case fails the port. Tier B
> is compared per tick against the declared tolerance, and the **maximum**
> deviation over all cases is reported, never the mean.

A mean hides exactly the excursion that matters. If a port is within tolerance
on 99.9% of ticks and outside it on the tick where `DUAL_IMU_FAILURE` crosses
`att_caution`, it has failed.

**A tier-A difference is never resolved by relaxing tier A.**

## 4. WHAT MUST BE FIXED BEFORE THE TRACES ARE FROZEN

1. **The §30 review of the propagation removal.** The default is `FLAT_V1_1`
   and the frozen engine still contains the legacy line. If the review changes
   the decision, every trace changes.
2. **The staleness rule.** `STALENESS_LAYER_AUDIT.md` proposes a canonical
   per-platform timeout and does **not** adopt it. Adopting it changes
   admissibility on every tick, so freezing traces first would waste them.
3. **The output schema.** It is at 1.1.0 and validated on 13 500 payloads, but
   it has never met a real consumer.

Until those are settled, freezing numbers would freeze the wrong ones.

## 5. WHAT THE PORT MUST CARRY — the state, from the freeze

    float alpha[8], beta[8], trust[8];     trust recursion       (32 floats)
    float S[5];                            CUSUM, k=0.5 h=500     (5 floats)
    float smoothed[8];                     diagnosis smoothing    (8 floats)

Removing neighbour propagation deletes the **inter-node read** of `trust[]`
inside the neighbour weight. `trust[]` itself is still computed and still
reported, so the struct does not shrink.

In-control statistics (`mu0`, `sigma0` for five nodes) are **constants**, not
runtime estimates. A port that re-estimated them from live data would not be
the same algorithm.

## 6. WHAT PHASE 5 IS NOT ALLOWED TO DO

- **Re-tune.** `k = 0.5` and `h = 500` come with a stated selection rule and a
  committed negative result (the textbook `h = 5.0` produced 2681 clean alarm
  ticks). A port that changed them would be a different detector.
- **Fix a disagreement by changing the reference.** If the C and the Python
  disagree, the C is wrong until proven otherwise, and if the Python turns out
  to be wrong, that is a v1.1 defect with its own commit and its own
  remeasurement — not a silent alignment.
- **Claim a timing figure the Python reference cannot support.** Python
  measured **90 µs/tick core** and **541 µs/tick reporting** on a
  general-purpose host (`PHASE4_COMPUTE.json`). Neither is an embedded
  figure, and the reporting number in particular must never appear in an
  embedded-core claim (§29).

## 7. FORMAT, WHEN THE TIME COMES

One JSON Lines file per case: the `csia_output_v1_1` payload per tick, plus a
sidecar of the ledger events. The payload already carries `input_trace_hash`,
so a golden trace names the input that produced it and cannot be silently
paired with a different one.
