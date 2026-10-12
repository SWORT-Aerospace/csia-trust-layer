# R-3: configuration-epoch admission

**2026-10-01. Revision R-3 of the promotion-candidate brief, and Phases 7
and 8.**
- **Switch:** `Corrections(config_epoch=True)`, part of
  `Corrections.revised()`. Off by default.
- **Code:** `csia_semantic_core/admission.py`; `SemanticCore21.reason(records,
  epochs=...)`; `ShadowRunner.evaluate(snapshot, epochs=...)`.
- **Tests:** `test_r3_*` in `tests/test_semantic_core_2_1_revision.py`.

## 1. Scope

**This is the smallest piece of admissibility.** Evidence generated under one
configuration is not admitted once the configuration it depends on has
changed. Unrelated evidence is never touched.

**Not built:**
- an age or freshness rule;
- producer contracts or a producer registry;
- a provenance graph.

The brief excludes all three, and none was needed.

**Three quantities:**

| quantity | where it lives |
|---|---|
| the producer or source's epoch | the key named in the record's stamp |
| the evidence's generation epoch | `provenance["config_epoch"] = {key: epoch}` on the record, written by the producer |
| the current context epoch | `EpochContext(current={key: epoch}, events={key: description})`, given to `reason()` each tick by the integration |

**An epoch is** a non-negative int, or a tuple of them for a composite such as
(boot count, counter). A record without a stamp depends on no configuration.
A sensor's own health record, for instance, describes the sensor, not the
estimator lane that reads it.

## 2. Alignment with PX4

The PX4 source at 547e2ca was read at these lines (V4). The rule reads
counters that PX4 already publishes. It does not re-derive the estimator's
logic, and it does not decide when a lane switch should happen.

| configuration | PX4 field | type | where it changes |
|---|---|---|---|
| estimator lane | `estimator_selector_status.instance_changed_count` | uint32 | `EKF2Selector::SelectInstance`, `_instance_changed_count++` (EKF2Selector.cpp line 132) |
| IMU in use | `sensor_selection.accel_device_id`, `gyro_device_id` | uint32 | published in the same function on every instance change (lines 115-118) |
| estimator state resets | `vehicle_local_position.xy_reset_counter`, `z_reset_counter`, `vxy_reset_counter`, `vz_reset_counter`, `heading_reset_counter` | **uint8** | on each reset |

**Use a monotonic counter as the key, not the lane id.** A switch back to an
earlier lane then does not re-admit that lane's old evidence (§5, SWITCH_BACK
against SWITCH_BACK_LANE_ID).

## 3. The rule

**A stamped record is admitted iff every key it names is in the context with
an EQUAL epoch.** Order only names the reason:

| condition | reason | effect |
|---|---|---|
| record epoch < current | STALE_CONFIGURATION_EPOCH | not admitted |
| record epoch > current | EPOCH_AHEAD_OF_CONTEXT | not admitted, and **every** record of that key is held back this tick (CONTEXT_BEHIND_PRODUCER): the context has evidently missed a transition, so its "current" is not trusted |
| key not in the context | UNKNOWN_EPOCH_KEY | not admitted |
| unparseable stamp | MALFORMED_EPOCH | not admitted |
| context value not an epoch | MALFORMED_CONTEXT_EPOCH | not admitted |
| composite epochs of different length | EPOCH_FORM_MISMATCH | not admitted |

**What happens to a record that is not admitted:**
- **Superseded:** if an admitted record answers the same (relation,
  component), it is dropped. Keeping it would only make C6 read neither.
- **Otherwise it becomes UNAVAILABLE** ("could not look").
  - **Kept:** its identity and declared structure.
  - **Cleared:** its content, that is, reason codes, values, timestamps,
    sequential state and detail.
  - **Why clear the content:** a detector that reads reason codes cannot see
    the stale content. `test_r3_inadmissible_content_is_invisible_to_reason_code_detectors`
    pins this with a stale TIMING_DEADLINE_MISSED record.

**The trace.** `TickResult.admission` (and `to_dict()["evidence_handling"]["config_epoch_admission"]`)
lists every record not admitted, with:
- the record id;
- its producer (`source`);
- the key;
- the evidence epoch and the current epoch;
- the reason and the action;
- the transition event, when the context gave one.

It also lists the context epochs, malformed context keys, and keys whose
context is behind.

## 4. Tests 1-7

| # | case | test | result |
|---|---|---|---|
| 1 | same epoch | `test_r3_1_same_epoch_is_admitted_unchanged` | admitted, byte-identical |
| 2 | dependent evidence after N+1 | `test_r3_2_…` | UNAVAILABLE, content cleared, traced with producer, epochs and event |
| 3 | unrelated evidence | `test_r3_3_…` | unstamped and other-key records untouched |
| 4 | new evidence | `test_r3_4_…` | the N+1 record admitted; the old one of its key dropped as superseded |
| 5 | multiple transitions | `test_r3_5_…` | every older epoch not admitted |
| 6 | replayed old epoch | `test_r3_6_…` | not admitted, duplicated or not |
| 7 | transition with no dependency | `test_r3_7_…` | nothing invalidated |

**Adversarial unit tests** cover:
- switching back to an earlier lane;
- rapid switching;
- evidence ahead of the context;
- nine malformed stamps;
- malformed or missing context;
- a producer restart (composite epoch);
- counter rollover;
- an unrelated producer's transition.

**Two more pins:** a 2.1.0 core ignores epochs entirely, and the frozen E1
design replays with no stale tick.

## 5. Phase 7: E1 replayed exactly

**The design.** E1 is the shadow study's frozen TRANSITION_DESIGN.json
(commit e0fc81a). `transition_study.load_design()` refuses any other SHA-256.

**The mapping to the implemented rule** (`transition_replay.py`, written
down before the run and not changed after it):
- every record the design gives an estimator epoch is stamped with
  `ekf2.selector.instance_changed_count`;
- the context is the lane counter, 0 then 1, with the event named from tick
  25.

| configuration | stale POSITION_UNAVAILABLE ticks | missed | stale record-ticks admitted | valid record-ticks not admitted | CORRECT_UNIQUE / CORRECT_AMBIGUOUS | recovery tick |
|---|---|---|---|---|---|---|
| frozen v2.0 | **9** (25-33) | 0 | 9 | 0 | 26 / 14 | 34 |
| 2.1.0 | **9** (25-33) | 0 | 9 | 0 | 26 / 14 | 34 |
| **2.1.1 (implemented rule)** | **0** | 0 | **0** | **0** | 35 / 5 | **25** |
| 2.1.1 + successor r2 | 0 | 0 | 0 | 0 | 35 / 5 | 25 |
| 2.1.1 given stamped records but **no context** | 0 | **5** | 0 | **111** | 40 / 0 | 25 |

**How to read it:**
- **The implemented rule reproduces the design's own epoch policy
  (B_STATE_EPOCH) exactly**, on every metric. On ticks 25-33 the trace shows
  the latched lane-0 deadline record as STALE_CONFIGURATION_EPOCH, epoch [0]
  against current [1], MADE_UNAVAILABLE.
- **Without a context the rule fails closed.** No stale evidence is admitted,
  but 111 valid record-ticks are withheld. A real POSITION_UNAVAILABLE on
  ticks 20-24 is then not raised, because the estimator's degradation is the
  only evidence for it and it is no longer admitted. This is reported, not
  hidden: every withheld record is in the tick's admission report with
  reason UNKNOWN_EPOCH_KEY. It does mean **the integration must supply the
  context**. A deployment should treat UNKNOWN_EPOCH_KEY as a configuration
  error.

## 6. Phase 8: fourteen adversarial variants

**What each variant does.** It perturbs the frozen E1 stream one way. Each
record carries a TRUE configuration identity, independent of its stamp, and
a record is valid iff that identity is the one in force
(`epoch_adversarial.py`).

| variant | stale admitted | valid withheld | stale symptom ticks | missed symptom ticks | reading |
|---|---|---|---|---|---|
| BASE | 0 | 0 | 0 | 0 | as E1 |
| RAPID_SWITCHING (4 switches) | 0 | 0 | 0 | 0 | |
| SWITCH_BACK (0→1→0, counter) | 0 | 0 | 0 | 0 | the counter keeps lane 0's old evidence out |
| SWITCH_BACK_LANE_ID (rejected design) | **4** | 0 | **4** | 0 | why the key must be a counter, not the lane id |
| EARLY_NEW_EPOCH (lane-1 record before the event) | 0 | 2 | 0 | **1** | fail-closed: the key is held back for one tick |
| LATE_OLD_EPOCH (lane-0 record arrives late) | 0 | 0 | 0 | 0 | dropped as superseded |
| DUPLICATE_OLD | 0 | 0 | 0 | 0 | |
| MISSING_TRANSITION (lane-1 records reveal it) | 0 | 61 | 0 | 0 | fail-closed: nothing stale, the estimator's current records withheld |
| MISSING_TRANSITION_SILENT (nothing reveals it) | **9** | 26 | **9** | 0 | **undetectable**: a transition no record and no context reports cannot be seen; the same as 2.1.0 (9) |
| MALFORMED_EPOCH | 0 | 51 | 0 | **5** | fail-closed |
| RESTART_COUNTER_ONLY | **6** | 0 | **6** | 0 | a restarted counter re-matches old evidence |
| RESTART_COMPOSITE (boot, counter) | 0 | 0 | 0 | 0 | the composite epoch fixes it |
| ROLLOVER_UINT8 (255 → 0) | 0 | 9 | 0 | 0 | the old 255 looks "ahead", so the key is held back while it persists |
| UNRELATED_TRANSITION (gyro id) | 0 | 0 | 0 | 0 | |

**The rule's integration contract.** These follow from the table:
1. **Supply the context every tick.** UNKNOWN_EPOCH_KEY fails closed, and can
   hide a symptom.
2. **Key on a monotonic counter**, not on a lane or instance id.
3. **Use a composite epoch (boot or session, counter) when a producer can
   restart.**
4. **Unwrap narrow counters** (the uint8 reset counters) into a monotonic
   value in the adapter, or accept a few ticks of withheld evidence after a
   wrap. The 32-bit `instance_changed_count` does not need this in practice.
5. **A transition reported by nobody cannot be detected.** The context must
   come from the configuration owner (the selector's status), not be inferred
   from the evidence.

**Against 2.1.0:**
- **Better in eight variants:** 2.1.0 has 9 stale ticks in every variant;
  2.1.1 has none in BASE, RAPID_SWITCHING, SWITCH_BACK, LATE_OLD_EPOCH,
  DUPLICATE_OLD, MISSING_TRANSITION, RESTART_COMPOSITE and
  UNRELATED_TRANSITION.
- **Never worse in stale ticks.** In the contract violations it is
  fail-closed (fewer stale, more withheld) or equal (the silent transition).

## 7. Interactions checked (Phase 12)

| interaction | result |
|---|---|
| R-1 and R-3 together | every base predicate failed on every E1 tick, with epochs: 1,620 injections, 0 wrong SUPPORTED, 0 wrong UNIQUE, 0 stale symptom ticks |
| profile overlays and R-3 | both successor overlays keep every epoch stamp |
| order and duplicates | reversing or duplicating E1's records changes no decision |
