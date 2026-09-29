# Missing-evidence audit (Part 8)

CSIA semantic correctness audit, 2026-09-29. Result ids refer to
`semantic_probe_results.json`. Literature ids are defined in `SOURCES.md`.

## 1. Answer

**Current CSIA does turn "I don't know" into "therefore H".** It happens in
two independent places:

1. **Predicates.** Eighteen of the 26 base predicates read a record that
   could not look (UNAVAILABLE), or a shared node nobody reported, as
   healthy (`CURRENT_SEMANTICS_MAP.md` §3). They then refute or confirm on
   that basis.
2. **Attribution.** An alternative that is unobserved, UNAVAILABLE, or whose
   whole producer is down simply stops being a candidate. Any unrelated
   NOMINAL record then licenses UNIQUE.

Both paths are reachable **with the shipped domains**. The v2 domains emit
UNAVAILABLE themselves when a component's telemetry is absent:

- actuation.py:138;
- communication.py:120, 148;
- compute.py:140, 169, 280, 311;
- power.py:193, 311;
- timing.py:143.

The plugin supervisor removes a failed domain's records altogether.

## 2. The criterion

"Missing" is judged by **Kleene's strong three-valued logic** (L05), the
logic SQL uses for NULL:

- **Unknown is neither.** Treating an unknown as True or as False is the
  error.
- **The check** (`k3_check` in the probe). With one record unknown, a
  hypothesis may be **rejected** only if it is rejected under *both*
  completions of that record, NOMINAL and VIOLATED. It may be **confirmed**
  only if it is confirmed under both.
- **Structure is held constant.** The record keeps its declared dependencies,
  so the check tests evidence, not wiring.

A hypothesis that merely *survives* because its own refuter is unknown is
**not** counted as a violation. v2 states that "an unmeasurable predicate
eliminates nothing" (localization.py:26-32), and that choice is respected.
Its reporting gap is SC-21.

## 3. Results

### 3.1 On every shipped final tick (P6)

**Method.** Each record of each of the 44 final ticks is replaced in turn by
its UNAVAILABLE twin, giving 2,465 cases.

| | frozen | shadow |
|---|---|---|
| cases with a violation | **382** | **0** |
| hypotheses rejected on an unknown (UNKNOWN_REFUTES) | **531** | 0 |
| hypotheses confirmed on an unknown (UNKNOWN_CONFIRMS) | 0 | 0 |
| SUPPORTED verdicts resting on either (UNKNOWN_SUPPORTED) | **339** | 0 |
| UNIQUE attributions that stand while the unknown record is a declared alternative of the candidate | **185** | 0 |

NOT_APPLICABLE ("nothing to look at") is judged differently. It should behave
as absence, and is tested against removal on records that carry no
dependencies: 416 cases, 7 frozen differences, 0 in the shadow.

- **All 7 are the same record.** `compute.resource_headroom` NOT_APPLICABLE
  is read as "headroom fine", across all three profiles: CPU_OVERLOAD,
  ESTIMATOR_LATE, MS_A3, MS_C4, MS_D4, PS_LOOP_SATURATED and TS_CPU_OVERLOAD.
- **Effect.** It turns PROCESS_OUTPUT_LATE from "one explanation left,
  unconfirmed" into "every explanation rejected".

### 3.2 Exhaustive small-state enumeration (`SMALL_STATE_ENUMERATION.md`)

| enumeration | configurations with an unknown | frozen: rejects on unknown | frozen: SUPPORTED on unknown | shadow |
|---|---|---|---|---|
| N3 COMMAND_NO_RESPONSE: 6 records, 3,072 configurations | 2,343 | **1,208** | **211** | 0 / 0 |
| N4 OUTPUT_STALE: 6 records, 1,296 configurations | 567 | **486** | **38** | 0 / 0 |
| N6 shared nodes: 4 nodes each absent, NOMINAL, VIOLATED or UNAVAILABLE; 256 configurations | 240 | **224** | **176** | 0 / 0 |

In N6, "unknown" includes a node that is simply **not reported**. Frozen v2
returns SUPPORTED SENSOR/independent_faults in 81 of 256 configurations. The
shadow does so in 1: the configuration where all four shared nodes are
reported NOMINAL.

### 3.3 The shipped domains producing the unknown themselves (E.variants)

| variant | ground truth | frozen before → after | shadow after |
|---|---|---|---|
| V_MIS_1: GNSS link telemetry absent | transport delay | OUTPUT_STALE: SUPPORTED transport_delay → **UNSUPPORTED, every explanation rejected** | unchanged: SUPPORTED transport_delay |
| V_MIS_2: estimator telemetry absent | process stall | OUTPUT_STALE: SUPPORTED process_stall → **SUPPORTED processing_delay** ("the process was running but took too long") | AMBIGUOUS {processing_delay supported, process_stall unresolved} |
| V_MIS_3: CPU resource telemetry absent | CPU saturation | PROCESS_OUTPUT_LATE: SUPPORTED resource_exhaustion → **UNSUPPORTED, all rejected** | UNSUPPORTED, resource_exhaustion **unresolved** |
| V_MIS_4: battery telemetry absent | power path | COMMAND_NO_RESPONSE: supported cause switches **power path → drive_no_current**. Attribution AMBIGUOUS → **UNIQUE ACTUATION/motor_0** | power path unresolved; attribution AMBIGUOUS |

**V_MIS_2 is the clearest case.** The only change is that the process stops
reporting. CSIA then asserts, at its highest localization verdict, a
different cause: one that presupposes the process was alive.

### 3.4 Producer unavailable (E.producer_unavailable)

This uses the plugin wrapper the v2 tests themselves use
(`plugin_runtime.FailingDomain`, mode `raise`).

| case | frozen attribution | shadow attribution |
|---|---|---|
| MS_B2 (true power-path fault), POWER plugin raises | AMBIGUOUS [motor_0, battery] → **UNIQUE ACTUATION/motor_0** | AMBIGUOUS |
| MS_A4, COMPUTE plugin raises | stays AMBIGUOUS | AMBIGUOUS |
| MS_D3, COMMUNICATION plugin raises | the only adverse component disappears → NO_EVIDENCE | NO_EVIDENCE |

**In the MS_B2 case three outputs of one tick disagree:**

- the function graph marks **every function UNKNOWN**, correctly, because
  a required domain failed;
- attribution names the motor as the unique cause of a power-path fault;
- localization correctly keeps POWER/path_unavailable unresolved.

This is because the failed domain's records vanish, and `plugin.status` is
not attributable.

## 4. Part 8 matrix: can each kind of missing state do each thing?

"Yes" cites the case that shows it.

| missing state | support a hypothesis | refute a hypothesis | create UNIQUE | remove AMBIGUOUS | produce UNSUPPORTED |
|---|---|---|---|---|---|
| **missing record**: component never reported | **yes**: R17A (independent_faults SUPPORTED, no shared node reported) | **yes**: R17A (all three shared-node hypotheses) | **yes**: R2 (alternatives unobserved, plus one unrelated NOMINAL) | **yes**: R2 | not observed |
| **UNAVAILABLE record**: could not look | **yes**: R8E (processing_delay SUPPORTED) | **yes**: R8B, R8E, R8G | **yes**: R3, R8G | **yes**: R8G | **yes**: R8B, V_MIS_1, V_MIS_3 |
| **NOT_APPLICABLE record** | no case observed | **yes**: P6 (the 7 `resource_headroom` cases) | no case observed | no case observed | changes its meaning: the same 7 go from "one explanation left, unconfirmed" to "every explanation rejected" |
| **NOT_MEASURABLE**: predicate returns None | by design it never supports; but see the note below | no, by design | indirectly: the survivor of an unmeasured refuter can be SUPPORTED | — | — |
| **predicate absent**: id not in the table | no: `KeyError`, the tick fails (R15A) | no | no | no | no |
| **predicate raises** | **indirectly yes**: R9B turns "all rejected" into SUPPORTED; P5 records 9 new SUPPORTED verdicts on shipped ticks | no | — | **yes**: P5 | **yes**: P5 (some decision changes go to UNSUPPORTED) |
| **producer unavailable**: plugin failed | not observed | not observed | **yes**: MS_B2 with POWER plugin raising | **yes**: the same | not observed |
| **domain absent**: not registered | as for "producer unavailable" but **without** the `plugin.status` record, so only the function graph's `coverage_report` shows it | | | | |

**Note on NOT_MEASURABLE.** A hypothesis whose own refuter could not be
evaluated can still be SUPPORTED, once every competitor is rejected. This is
v2's declared semantics ("eliminates nothing"). It is safe for elimination,
but the output does not tie the unmeasurable refuter to the hypothesis it
would have tested. A reader of SUPPORTED h1 cannot tell that h1 itself was
never checked for refutation (SC-21).

## 5. What is not a defect

These were checked and are correct:

- **`_nominal`** (localization.py:147-155) maps UNAVAILABLE, NOT_APPLICABLE
  and absent to None. All eight single-record state predicates built on it
  are Kleene-consistent.
- **Absent records** give None in every predicate except the shared-node
  group.
- **`worst([])`** is UNAVAILABLE (evidence.py:147-157). The function graph
  treats an empty required domain as UNKNOWN, which outranks INELIGIBLE. The
  function graph does **not** have the missing-evidence defect.
- **XSYS-001** uses its own predicates, which map UNAVAILABLE and
  NOT_APPLICABLE to None (`xsys_v2_adapter._state`). None of the 3,872 sealed
  localization slots contains an UNAVAILABLE record (X.record_states_seen).

## 6. Severity (see `FINDINGS.csv`)

- **SC-03, UNAVAILABLE read as healthy: S3.** It is reachable with shipped
  domains whenever telemetry drops. V_MIS_2 is a wrong SUPPORTED cause.
- **SC-04, unreported shared node read as not adverse: S3.** A wrong
  SUPPORTED "independent faults".
- **Why not S4.** Nothing downstream acts on a v2 localization or attribution
  verdict today (`CURRENT_SEMANTICS_MAP.md` §7). The future risk is S4: a
  consumer that switched a function or a controller on "SUPPORTED
  processing_delay" would be acting on a conclusion drawn from the absence of
  telemetry.
