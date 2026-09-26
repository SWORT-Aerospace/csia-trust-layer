# Latency path analysis — where CSIA's decision time actually goes

**Status labels used throughout:** HISTORICAL/SEALED · CURRENT VALIDATED ·
EXPERIMENTAL · PROPOSED · UNPROVEN. Written under
`docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`. Base commit `e7594e4`.

**The primary research variable is not computation speed.** It is:

> When does sufficient information physically exist to justify the correct
> conclusion?

This builds on `docs/audit/CSIA_LATENCY_PATH_AUDIT.md`, which already maps
the pipeline stage by stage from executed code. It does not repeat that
audit; it adds the definitions, the measurements and the attribution below.

---

## 1. Definitions

### 1.1 The seven timestamps

Each is defined for **one fault in one run**. Each is allowed to be
**undefined**, and an undefined stage is reported as undefined, never as 0 and
never estimated.

| t | name | definition | defined only when |
|---|---|---|---|
| **t0** | fault onset | the instant the injection takes effect in the plant | the injection's effect can be timestamped; the configured start is only a proxy (`OnsetBasis.configured`) |
| **t1** | first physically observable deviation | the first sample at which some observable differs from the same run without the fault by more than that observable's nominal variability | a **twin run** exists: same seed, same profile, no fault (§6, P1) |
| **t2** | first local statistical indication | the first time any single-domain detector (λ threshold, CUSUM) on that observable crosses its **declared** threshold | a local detector is declared for that observable. None is for `imu0`, `imu1` or `baro` (`csia/v1_1/sequential.py` `NO_RESIDUAL`) |
| **t3** | evidence available to CSIA | the first tick at which the deviating evidence is admitted: its channel is fresh **and** its gate is open | the feature is gated and fresh-checked. A gate the fault itself closes makes t3 **never**, which is the self-occlusion case |
| **t4** | competing hypotheses distinguishable | the first time the correct hypothesis is separated from every competitor by the architecture's own rule: for v1, a posterior-margin rule (§6, P4); for v2, a single surviving candidate | the competitors are separable at all. If a gate pins the ratio at the prior, t4 is **never** by construction |
| **t5** | certificate / justified decision | the first time the architecture emits a conclusion **it is entitled to**: v1's alert event; for v2, a localization verdict of `SUPPORTED` (last candidate standing **and** affirmatively confirmed) | the architecture emits one. The EXPERIMENTAL `SupportCertificate` (`csia_assurance/witness.py`) is a separate firewall layer, **not** connected to v2, and is a t5 candidate only for the record type it qualifies |
| **t6** | action eligibility | the first time a downstream runtime-assurance layer could legitimately act | a policy exists. v1's failsafe issues recommended actions; there is no FORGE implementation, so beyond v1's own policy this is **undefined** |

### 1.2 The five latency classes

| class | interval | what it measures |
|---|---|---|
| **DETECTION** | t2 − t1 | how long a local detector takes to notice a deviation that already exists |
| **ISOLATION** | t4 − t1 | how long until the evidence separates the causes |
| **CERTIFICATION** | t5 − t1 | how long until the architecture's own evidence requirements permit the conclusion |
| **ACTION** | t6 − t1 | how long until acting is legitimate |
| **COMPUTATIONAL** | per-tick wall time | processing time only. Measured per tick, not as an interval from onset |

They are measured **from t1, not t0**. Time before the fault is physically
observable is not latency any architecture can remove. It is a property of the
plant and its sensors.

**Not all seven are meaningful for every architecture.** CUSUM has t2 and
nothing after it. v2 localization has t4 and t5 but no internal notion of time
(§5). v1 has t2 only if one of its residuals is read as a local detector.

---

## 2. What is measurable today (CURRENT VALIDATED unless stated)

| t | today | where |
|---|---|---|
| t0 | **configured start only** | `csia/metrics/latency.py` `OnsetBasis`; its `first_corrupted_sample` and `first_observable_effect` fields exist and are **never filled** by any committed caller |
| t1 | **not measured** | needs a twin run; the bench simulator is deterministic in decision timing (§3), so it is feasible there |
| t2 | **only inside one script** | λ and CUSUM crossings are computed in `research/systems-paper/mechanism_b.py`, not in the latency module |
| t3 | **implicit** | only as "trust crosses its production threshold", which conflates admission with accumulation |
| t4 | **partly** | `time_to_classification` (posterior ≥ 0.90) and `time_to_correct_isolation`; no margin-based rule |
| t5 | **v1 only** | `time_to_alert_event`. v2's `SUPPORTED` verdict exists per snapshot but no committed code times it. The EXPERIMENTAL `SupportCertificate` (`csia_assurance/witness.py`) is built only in its own tests (`tests/test_assurance_firewall.py`) and is not imported by `csia/v2/` |
| t6 | **recommendation only** | `time_to_arbitration`; applied mitigation is `UNAVAILABLE` by design (`APPLIED_MITIGATION_UNAVAILABLE`) |
| computational | **per tick** | `TrustState.latency_us`, set at `csia/runtime/online.py:645` |

**The latency module has never been run on a real scenario by committed
code.** `csia/metrics/latency.py::measure` is called only from
`tests/test_metrics_latency.py`, on hand-built fake summaries. The numbers in
the existing audit came from ad hoc execution.

---

## 3. Measured: the decomposition on the catalogue scenarios

**EXPERIMENTAL measurement, not a sealed result.** Existing online runtime,
existing latency module, simulator posture, default configuration. Nothing
was modified.

| scenario : target | trust < production threshold | **alert (t5)** | classified p ≥ 0.90 | **correctly isolated (t4)** | outcome | compute per tick, median |
|---|---|---|---|---|---|---|
| `gps_spoof` : gps | 3.36 s | **4.40 s** | never | never | alert without isolation | ~0.26 ms |
| `power_sag` : battery | 2.72 s | **3.76 s** | 1.12 s | **1.12 s** | correct | ~0.27 ms |
| `power_sag` : motor_esc | no threshold defined | 3.76 s | 1.12 s | never | **incorrect isolation → battery** | ~0.25 ms |
| `mag_emi` : mag | 4.04 s | **5.08 s** | 0.76 s | **0.76 s** | correct | ~0.24 ms |
| `vibration_anomaly` | 5.16 s | **6.20 s** | 0.76 s | **0.76 s** | correct | ~0.24 ms |
| `imu0_bias_drift` : imu0 | 13.84 s | never | 14.40 s | 14.40 s | missed: no alert | ~0.24 ms |

Times are seconds after the configured onset. The decision timings were
**identical across three independent runs**; the compute figures vary run to
run (medians 240–275 µs, p99 367–509 µs, worst single tick 15.2 ms), as
wall-clock measurements do.

**Reproduce** (run from the repository root):

```python
import statistics, sys
sys.path.insert(0, ".")
from csia.metrics.latency import measure, production_threshold
from csia.runtime.plugins import SimulatedFlightSource
from csia.runtime.service import TrustLayerRuntime
from csia.scenarios import SCENARIOS

CASES = [("gps_spoof", 0), ("power_sag", 0), ("power_sag", 1),
         ("mag_emi", 0), ("vibration_anomaly", 0), ("imu0_bias_drift", 0)]
s = lambda x: "never" if x is None else f"{x:.2f}"
for name, i in CASES:
    fault = SCENARIOS[name][1][i]
    run = TrustLayerRuntime(SimulatedFlightSource(name), keep_states=True).run()
    r = measure(run, fault, scenario_id=name)
    thr = production_threshold(fault.target)
    cross = None if thr is None else next(
        (st.t - fault.start for st in run.states
         if st.t >= fault.start and st.trust.get(fault.target, 1.0) < thr),
        None)
    us = sorted(st.latency_us for st in run.states if st.latency_us)
    print(name, fault.target, s(cross), s(r.time_to_alert_event_s),
          s(r.time_to_classification_s), s(r.time_to_correct_isolation_s),
          r.outcome, r.isolated_as, f"{statistics.median(us):.0f}us")
```

---

## 4. Where the time goes

### 4.1 The answer, in one paragraph

**It is not computation.** A tick costs about 0.25 ms against a 40 ms tick
budget and a multi-second decision. The time is spent in three places, all of
them evidence handling:

1. the trust recursion's descent to each sensor's production threshold, about
   2.7–5.2 s;
2. a fixed **1.04 s** policy dwell;
3. structural limits (gating, and the `max(imu0, imu1)` attitude rule) that
   make some stages **never** happen.

And in three of the four isolated cases **the correct cause is known 2.6–5.4 s
before the alert fires.** The alert path, not hypothesis distinguishability,
is the bottleneck.

### 4.2 Against the ten candidate sources

| # | candidate | contributes? | basis |
|---|---|---|---|
| 1 | signal / window accumulation | **yes, small** | residual EW smoothing adds +0.04 to +0.12 s (`research/systems-paper/MECHANISM_B.md` §5, measured) |
| 2 | detector thresholds | **yes** | the per-sensor production threshold sets how far trust must fall: from 0.82 (attitude) and 0.75 (gps) down to 0.60 (magnetometer, vibration) (`csia/runtime/failsafe.py`). The lower the threshold, the longer the descent |
| 3 | evidence persistence | **yes, dominant** | the Beta recursion's memory (ρ up to 0.998, `csia/trust_engine/engine.py`) makes trust fall slowly. Trust crosses its threshold 2.72–5.16 s after onset while the diagnosis has isolated at 0.76–1.12 s (§3) |
| 4 | temporal conditioning | **yes** | `arm_time` (10 s) suppresses early faults outright, and the diagnosis smoother (α = 0.06, ~15 ticks) is inside every classification time (`csia/diagnosis/bayes.py`) |
| 5 | cross-sensor agreement | **structural** | the attitude condition reads `max(imu0, imu1)`, so a single-IMU fault never alerts (`imu0_bias_drift`: never) |
| 6 | hypothesis distinguishability | **not the bottleneck when separable; total when not** | isolation precedes the alert in 3 of 4 cases. For `gps_spoof`, the fault closes its own evidence gate, so t4 is never, by construction (`docs/research/CSIA_ALGORITHM_EXPOSITION.md` §4) |
| 7 | certificate requirements | **yes, exactly 1.04 s** | `dwell_up` 1.0 s plus one tick, uniform across scenarios (§3; the existing audit §3) |
| 8 | scheduling / sample rate | **bounded** | 25 Hz sets a 0.04 s floor on every stage; the slowest channels (gps, battery, vibration) have 0.5 s freshness windows |
| 9 | computation | **negligible** | ~0.25 ms per tick; v2 localization alone 45.8 µs per tick (`engineering/v2/V2_PHASEC_COMPUTE.json`) |
| 10 | combination | **yes** | 3 + 7 + 2 dominate; 1, 4 and 8 are second order; 5 and 6 decide *whether* a stage occurs rather than *when* |

### 4.3 The "~2.5 s" figure, and why §3 does not reproduce it

The figure comes from **HISTORICAL / SEALED** results: Phase 4 claim C27,
trust-persistence median **2.52 s** against CUSUM 0.08 s on the vibration node
(`research/consequence/CLAIMS_AND_ARTIFACTS.md`); and Phase 5 baseline `B0`,
**2.54 s** (`research/phase5/PHASE5_RESULTS.md`). Those are medians over a
locked partition, on a different harness, magnitudes and onsets, at matched
operating points. §3 is one default run per catalogue scenario. **They are
different measurements and must not be compared number to number.** What
carries over is the *mechanism*: Phase 5 attributes about 1.0 s of `B0`'s
delay to `dwell_up`, exactly as §3 measures it.

---

## 5. CUSUM against CSIA — apples to apples?

### 5.1 The detection comparison was fair, and the correction to it was not

The Mechanism B comparison (`research/systems-paper/MECHANISM_B.md`) set the
CUSUM's first crossing against the **raw** trust crossing. That is detector
against detector: neither includes a policy dwell. The committed "correction"
subtracted a 1.0 s dwell from the trust figure that was never in it, and so
favoured the trust path by one second. **Recorded as FL-053; the correction is
proposed in `docs/research/SC09_PROPOSED_CORRECTION.md`; no sealed artifact
was modified.** The CUSUM's lead survives and grows: 5.76 / 2.20 / 2.52 s,
not 4.76 / 1.20 / 1.52 s.

### 5.2 The deeper mismatch: both are detection endpoints

| | CUSUM alarm | trust crossing | CSIA alert | v1 diagnosis |
|---|---|---|---|---|
| timestamp class | t2 | t3-like | t5 | t4 |
| information used | one residual on one node | one node's fused evidence | a node's trust + threshold + dwell | all features, all hypotheses |
| **entitled to conclude** | "this node's residual mean has shifted" | "this node's evidence is inconsistent" | "this condition persisted" | "this cause, over the modelled competitors" |
| names a cause? | **no** | **no** | no (the condition, not the cause) | **yes** |

**Neither published comparison measured isolation.** CUSUM earlier than trust
is a fair **detection** result. It says nothing about which architecture names
the cause sooner, because CUSUM never names one. CUSUM has no residual at all
for `imu0`, `imu1` or `baro`, so "no alarm" there is never "no fault".

### 5.3 Could a sequential detector be a local evidence producer?

Phase 5 already tested a fast path supplying suspicion to CSIA (HISTORICAL /
SEALED, 1,360 locked runs):

- it cut latency about tenfold (0.24 s against 2.54 s);
- false alarms rose (0.100 against 0.000) and threshold robustness failed
  (H5 **killed**);
- it did not reduce action conflicts at all.

The one arm that bought latency without cost, `B5`, added timescales **inside**
the trust series and never read λ directly. The repository's own lesson:
*"the robustness came from the trust recursion, not from the persistence
dwell."*

**Consequence.** A sequential detector may serve as a **t2 producer**, a
timestamp and a *suspicion* record. It must not be wired into CSIA's belief
update without re-running the question Phase 5 answered, and that is not
proposed here.

---

## 6. Proposed post-hoc instrumentation (PROPOSED — not implemented)

**Principle.** Every addition **reads an emitted state stream after the run**.
Nothing is imported by `csia/runtime/` or `csia/v2/`, so no decision can change.
This is the separation the existing latency module already has.

| # | addition | reads | produces | notes |
|---|---|---|---|---|
| P1 | **twin-run onset** | a faulted run and its fault-free twin | fills `OnsetBasis.first_observable_effect`, which gives t1 | feasible on the bench simulator, whose decision timing is deterministic (§3); on SITL, estimated per pair with spread |
| P2 | **local-detector timestamps** | per-node λ from the emitted state; the frozen CUSUM bank run over it | t2 per declared detector, with the detector named | reuses `csia/v1_1/sequential.py` read-only; nodes with no residual report **not defined** |
| P3 | **evidence-admission time** | freshness and gate values per feature | t3 | separates "admitted" from "accumulated", which trust-threshold crossing conflates |
| P4 | **margin-based distinguishability** | the posterior series | t4 as the first tick the correct hypothesis's log-odds over **every** competitor exceeds a **declared** margin, held for a declared window | the margin is declared before use and never fitted to a sealed result; for v2, t4 is the first single-survivor snapshot |
| P5 | **justified-decision time** | v2 localization verdicts, per snapshot | t5 as the first snapshot whose verdict is `SUPPORTED` for the correct cause | read-only use of `csia/v2/localization.py`; semantics unchanged. `SupportCertificate` is not used for v2: it is a separate EXPERIMENTAL layer |
| P6 | **latency-class report** | P1–P5 | the five classes of §1.2, each possibly undefined, never collapsed | one record per fault per run |

**Tests the implementation must ship with:**

1. **Output invariance.** Running the analysis twice on the same run gives
   identical results, and the run's emitted states are byte-identical with
   and without the analysis loaded.
2. **No runtime reach.** No module under `csia/runtime/` or `csia/v2/` imports
   the new code, checked by import inspection, the same technique the hardware
   gate's frozen-core test uses.
3. **Undefined is not zero.** A stage that does not occur is reported as
   undefined; a test plants a run in which the gate never opens and requires
   t3 to be undefined.
4. **Twin pairing.** A mismatched twin (different seed or profile) is
   refused, not diffed.

**What it will not do:** change any threshold, tune the P4 margin against
Phase 4 or Phase 5 results, alter the Beta recursion, or add a stage the
architecture does not naturally have.

---

## 7. What v2 cannot yet tell us about latency (UNPROVEN)

v2's cross-domain localization is **atemporal**. Each snapshot is judged alone,
and its only cross-tick state is the ledger, which records changes and
accumulates no evidence (`csia/v2/ledger.py`). So **isolation latency and
certification latency are undefined for cross-domain reasoning today.** There
is no answer yet to "how long after onset does v2 name the cause". That is
the question the first cross-system experiment is built to start answering
(`docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` §10).
