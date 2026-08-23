# CSIA Latency Path Audit

**Baseline:** commit `944134f` · **Date:** 2026-08-03
**Scope:** the complete path from fault injection to operator-visible output.
**Method:** every timing figure below was produced by executing repository code
in this environment. Nothing is quoted from prior documents.

Companion documents: `docs/audit/CSIA_REPOSITORY_AUDIT.md` (finding F-02),
`docs/validation/METRIC_DEFINITIONS.md` (normative definitions).

---

## 1. The pipeline, stage by stage

| # | Stage | File · symbol | Input | Output | Timing behaviour | State across ticks | Risk / ambiguity |
|---|---|---|---|---|---|---|---|
| 1 | Fault begins | `csia/sensors/faults.py::Fault` | `start`, `duration`, `params` | window annotation | Ground truth. `start` is a *configured* time, not necessarily the first corrupted sample. | none | **Onset ambiguity**: configured start ≠ first corrupted sample ≠ first observable effect. Only the first is currently recorded. |
| 2 | Sensor data changes | `csia/sensors/*.py::sample()` | truth + faults | per-sensor streams @ native rate | Fault applied inside each sensor model, dispatched on `f.kind`. | none (batch) | Fault application is coupled into each sensor (audit F-07); timing/transport faults have no home. |
| 3 | Residual changes | `csia/prediction/comparator.py::PredictionComparator.build` | streams | `TickData`: edge λ + gate, physics λ + gate, hist λ, var-ratio, fresh @ **25 Hz** | Strictly causal backward differences; EW smoothers introduce lag. | EW/Holt smoother state | Smoother lag is real detection lag and is *not* separately attributed. |
| 4 | Trust updates | `csia/trust_engine/engine.py::TrustCore.step` | per-tick scalars | trust, evidence, ρ, sub-scores | Beta recursion with adaptive forgetting ρ ∈ [0.95, 0.998]; memory ≈ 1/(1−ρ) ticks. | `alpha`, `beta`, `trust` | Recovery is gradual by construction — trust re-entry lags posture recovery (see §5). |
| 5 | Analysis threshold crossed | `csia/validation.py::_detection`, `csia/cli.py::_report` | trust series | first t where `trust < 0.85` | **No operational effect.** | none | **This is what was published as "detection latency".** See §3. |
| 6 | Production threshold crossed | `csia/runtime/failsafe.py::FailsafePolicy._conditions` | `TrustState` | condition set | Per sensor class, not 0.85. | none | Conditions read `max(imu0, imu1)` for attitude — a single IMU fault may never qualify (§4). |
| 7 | Dwell satisfied | `failsafe.py::update` | condition set, `t` | dwelled conditions | Condition must persist `dwell_up` (**1.0 s** default; **3.0 s** offline posture). | `_cond_since`, `_issued` | Conditions clearing before dwell produce no alert at all. |
| 8 | Arm gate | `failsafe.py::update` | `t`, `state.armed` | pass/suppress | Suppressed while `t < arm_time` (**10.0 s** default; **20.0 s** offline). `reset_timers()` on disarm. | `_ever_fresh` | A fault inside arm time is invisible; latency must be `None`, never 0. |
| 9 | Failsafe state changes | `failsafe.py::_transition` | target level | `Transition` | Escalation immediate once dwelled; de-escalation needs `dwell_down` (**5.0 s**). | `level`, `transitions`, `_below_since` | Records **both** escalation and recovery — the F-01 miscount. |
| 10 | Alert emitted | `runtime/service.py::_handle` | `Transition` + actions | actuator calls, `state.jsonl` | Same tick as the transition. | actuator logs | Advisory only; no confirmation path back (§6). |
| 11 | Diagnosis produced | `csia/diagnosis/bayes.py::DiagnosisCore.step`, called at `runtime/online.py:632` | comparator features | posterior over 8 causes | **Computed BEFORE the failsafe decision each tick**, but does not gate it. | `_smoothed` (α = 0.06, ≈15-tick window) | Alert and diagnosis can contradict each other with nothing recording it (audit F-06). |
| 12 | Arbitration recommendation | `failsafe.py` `Action(...)` | dwelled condition | named actions | Issued **once per condition**, at the tick the condition dwells. | `_issued`, `_selected_imu` | A second condition dwelling later issues new actions *without* a level change — so recommendation time is not always the alert time. |

---

## 2. Confirmations requested

**Where `trust < 0.85` is measured** — `csia/validation.py:53-64` (`_detection`)
and `csia/cli.py:67-70` (`_report`). Two copies of an unnamed literal.

**Whether `0.85` has any operational effect** — **Two numerically identical
but semantically unrelated literals exist, and this is itself a hazard.**

1. **The analysis threshold** (`validation.py:61`, `cli.py:70`) — the one whose
   crossing was published as "detection latency". **No operational effect:** no
   `FailsafeConfig` field equals it and no condition compares trust against it
   to raise a level.
2. **A guard inside the `imu_isolated` condition** (`failsafe.py:130`):
   `min(T["imu0"], T["imu1"]) < 0.85`. This **is** operational — it suppresses
   IMU-isolation CAUTION while both units remain healthy. It is an un-named
   magic number in the production path (`imu_isolation_gap` is configurable
   beside it; this literal is not).

The two are equal by coincidence. Changing the analysis threshold would not
change behaviour; changing the literal at `failsafe.py:130` would. Both should
be named — the first as `LEGACY_ANALYSIS_THRESHOLD` (done, in
`csia/metrics/latency.py`), the second as a `FailsafeConfig` field (**open**).

**Actual production thresholds** (`FailsafeConfig`, `failsafe.py:58-71`):

| Sensor / class | Field | Value | Level raised |
|---|---|---|---|
| gps | `nav_caution` | 0.75 | CAUTION |
| mag | `heading_caution` | 0.60 | CAUTION |
| vibration | `struct_critical` | 0.60 | CRITICAL |
| battery | `power_critical` | 0.70 | CRITICAL |
| `max(imu0, imu1)` | `att_caution` | 0.82 | CRITICAL |
| `max(imu0, imu1)` | `att_emergency` | 0.70 | EMERGENCY |
| \|imu0 − imu1\| | `imu_isolation_gap` | 0.12 | CAUTION |

**Dwell / arm timing** — `dwell_up` 1.0 s (offline 3.0 s), `dwell_down` 5.0 s
(offline 10.0 s), `arm_time` 10.0 s (offline 20.0 s). Offline values are set in
`cli.py:163-165` for `.ulg` replay.

**Alert suppression** — three independent gates: `state.armed is False`
(immediate hold + `reset_timers()`), `t < arm_time`, and un-dwelled conditions.

**Escalation** — immediate once dwelled; `target = max(level of dwelled
conditions)`.

**Recovery** — requires the lower target to hold for `dwell_down`; emits
`RESUME_NORMAL` only on return to NORMAL.

**Does alert time differ between fault categories?** — Yes, and measurably:
the analysis-to-production threshold distance differs per sensor. See §3.

**Diagnosis before or after the alert?** — Diagnosis is computed **before** the
failsafe decision within the same tick (`online.py:632` → `TrustState` →
`policy.update`), and the reason string embeds the diagnosis callout. But the
alert does **not** require diagnostic agreement, which is how a CRITICAL
structural alert can fire while the posterior says `nominal p=0.72` (F-06).
Measured here: for `vibration`, classification at **0.76 s** *precedes* the
alert at **5.76 s**; for `gps_spoof`, no cause reaches 0.90 at all.

**Does CAUTION→CRITICAL count as a new alert event?** — It is a new **alert
event** (severity increased) but **not** a new **alert episode**. Episode
latency uses the first event; `alert_escalations` records the rest.

**Flapping** — episodes separated by less than `merge_s` (10 s) of recovered
posture merge into one incident, so latency is measured to the first crossing
and the incident counts once.

---

## 3. Measured: the gap that was being published

Sim posture, `generate_flight()` baseline, fault onset t = 20 s, amplitude ×1.0.

| scenario | ① t→trust<0.85 | production thr | ② t→prod thr | ③ t→**alert** | ③−② |
|---|---|---|---|---|---|
| gps_spoof | 2.16 s | 0.75 | 3.36 s | **4.40 s** | 1.04 s |
| mag_emi | 1.52 s | 0.60 | 2.84 s | **3.88 s** | 1.04 s |
| power_sag | 1.36 s | 0.70 | 2.36 s | **3.40 s** | 1.04 s |
| vibration | 2.16 s | 0.60 | 4.72 s | **5.76 s** | 1.04 s |
| imu_bias | 13.00 s | 0.82 | 13.84 s | **never** | — |

Two exact results:

1. **③ − ② = 1.04 s uniformly** = `dwell_up` (1.0 s) + one tick (0.04 s at
   25 Hz). The state machine adds a constant, and the *variable* part of the
   gap is stage ①→② — the distance from the analysis threshold down to the
   sensor's own production threshold, which ranges 1.00 s (power) to 2.56 s
   (vibration).

2. **`imu_bias` never raises an alert.** The published "13.0 s detection" is a
   trust crossing with no operator-visible consequence. `imu0` alone falls, but
   the attitude condition reads `max(imu0, imu1)` and `imu1` stays healthy at
   ≈0.86, above `att_caution` 0.82. This is redundancy working exactly as
   designed — one IMU degraded, the other still trusted, no emergency — but it
   is **not** a detection event, and it must not be reported as one. Diagnosis
   still isolates `imu0` correctly at 15.08 s.

Published detection latencies were therefore optimistic by **1.9×–2.7×** where
an alert exists, and unbounded where none does.

---

## 4. Ambiguity and failure risks

- **Onset is not one timestamp.** Only *configured start* is recorded.
  *First corrupted sample* requires a clean reference run to diff against;
  *first observable effect* requires a per-check detectability model CSIA does
  not have. Reported as `None` rather than estimated.
- **Attitude conditions are aggregate.** `max(imu0, imu1)` means single-IMU
  latency is undefined by construction. Per-source latency and per-condition
  latency are different quantities.
- **Smoother lag is unattributed.** Comparator EW/Holt lag and the diagnosis
  15-tick window are inside every latency number and are not separable today.
- **Actions ≠ alerts.** A recommendation can be issued without a level change
  when a second condition dwells inside an ongoing episode.
- **Batch vs online.** `dashboard/export.py:59` drives the same policy from a
  `_BatchState` shim; the batch path has no `armed` flag, so arm-gating
  behaviour differs from the live path.

---

## 5. Recovery vs trusted re-entry

These are deliberately separate metrics and are **not** simultaneous:

- **Recovery** — posture leaves the degraded state. Requires the condition to
  clear *and* hold for `dwell_down` (5 s / 10 s offline).
- **Trusted re-entry** — the source's own trust returns above the value at
  which it would re-trigger. Because the Beta recursion recovers gradually
  (ρ ≤ 0.998), a source can still be below its production threshold after the
  posture has already returned to NORMAL.

`tests/test_metrics_latency.py::test_trusted_reentry_is_distinct_from_recovery`
pins the distinction.

---

## 6. Applied mitigation

**Unavailable, by architecture.** `LoggingActuator` records; `MavlinkActuator`
transmits; neither returns confirmation that the receiving system applied the
recommendation. `time_to_applied_mitigation_s` is therefore always `None` with
an explicit reason string, never simulated. Closing this requires a
confirmation channel from the autopilot — an integration task, not a metric task.
