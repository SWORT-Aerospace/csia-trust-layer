# Minimal reproductions

CSIA semantic correctness audit, 2026-09-29.

**How these were produced.** Every case was executed against frozen v2 by
`semantic_probe.py`, section R, and the exact inputs and outputs are in
`semantic_probe_results.json` under `R`. Unless a case says otherwise:

- the reasoning configuration is the shipped aircraft one:
  `signatures.SYMPTOMS`, `signatures.PREDICATES` and
  `profiles.aircraft.AIRCRAFT_RELATIONS`;
- records are `EvidenceRecord`s with `attributable=True`;
- the applicability follows the state (APPLICABLE, or INPUTS_MISSING for
  UNAVAILABLE);
- no reason codes and no dependencies are set.

**Columns.** "Shadow" is the proposed successor semantics
(`MINIMAL_CORRECTION_DESIGN.md`), run only to measure it.

## Part 1: can unrelated nominal evidence create UNIQUE? **Yes. Reproduced.**

The earlier audit's description (probe S044a) was correct.

### R1: the smallest case (two records)

| case | records | localization | attribution |
|---|---|---|---|
| R1A | `POWER/rail_5v power.rail_tolerance VIOLATED` | VOLTAGE_RAIL_LOW on rail_5v: AMBIGUOUS {POWER/distribution, POWER/source} | **AMBIGUOUS** [POWER/rail_5v]. why: "single candidate, but no affirmatively nominal evidence from another domain to exclude an alternative" |
| R1B | R1A + `COMPUTE/cpu compute.resource_headroom NOMINAL` | unchanged | **UNIQUE** [POWER/rail_5v]; discriminators = [`COMPUTE/cpu:compute.resource_headroom`]; domains_excluded = [COMPUTE] |

**Why the CPU record is irrelevant, by every structure the code declares:**

- **Dependency graph.** Nothing connects the CPU to the rail.
- **Relations.** No relation spans COMPUTE and POWER.
- **Signature matrix.** COMPUTE is CANNOT_EXPLAIN for VOLTAGE_RAIL_LOW. The
  only hypotheses are POWER/source and POWER/distribution
  (`engineering/v2/CROSS_DOMAIN_SIGNATURE_MATRIX.csv`).

**Hypotheses and predicates.**

- **Attribution** uses no hypotheses and no predicates. Its candidates are
  adverse components.
- **Localization** evaluates SOURCE_WITHIN_TOLERANCE and its negation. Both
  are None; see R12.

**Code path.** `engine.evaluate` → `attribution.attribute` (attribution.py:113).

| line | what happens |
|---|---|
| 117-120 | builds `adverse` = [rail_5v] and `nominal` = [cpu] |
| 169 | one candidate |
| **174-176** | `discriminators` = every NOMINAL record with `r.domain != only.domain`. No relevance condition |
| 187 | the non-empty discriminator list returns UNIQUE |

**Responsible lines:** attribution.py:174-176 and 187.

**Shadow.** AMBIGUOUS, reason `DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL`.
The declared alternatives of rail_5v are POWER/battery and ACTUATION/motor_0,
both implicated by `actuation_power.demand_vs_current`. Neither was observed.

### R2 to R4: the same defect where the relevant alternative is known

The candidate is `SENSOR/source.gps v1_1.source_health VIOLATED`,
`dependencies=(POWER/rail_5v, COMMUNICATION/gnss_serial)`.

| case | added records | attribution | `unsupported` field | shadow |
|---|---|---|---|---|
| R2 | `ACTUATION/motor_0 actuation.command_path NOMINAL` (unrelated) | **UNIQUE**; discriminator = the motor record | [COMMUNICATION/gnss_serial, POWER/rail_5v] | AMBIGUOUS |
| R3 | R2 + `COMMUNICATION/gnss_serial comm.link_state UNAVAILABLE` + `POWER/rail_5v power.rail_tolerance UNAVAILABLE` | **UNIQUE**; discriminator = the motor record | same | AMBIGUOUS |
| R4 (control) | link NOMINAL + rail NOMINAL, and no motor record | UNIQUE; discriminators = the link and the rail | **same list** | UNIQUE |

R3 is the case the brief's question asks about.

- **The facts.** The two components that could explain a GNSS failure could
  not be looked at. The motor is fine.
- **The verdict.** Frozen v2 names the GNSS source as the unique cause.
- **What the output claims.** `domains_excluded` says ACTUATION was "looked at
  and found unsupported". The output nowhere says that the link and the rail
  were not looked at.

R4 shows the rule working as its docstring intends, which is the control.
It also shows that `unsupported` lists the same two components whether they
were never seen (R2), could not be seen (R3) or were seen and fine (R4).
That is SC-11.

### A realistic instance: shipped scenario MS_B5_RESPONSE_SENSOR

In this matched scenario the true fault is the **RPM response sensor**. On
its final tick (`E.B5_contradiction`):

| output | value |
|---|---|
| localization COMMAND_NO_RESPONSE on motor_0 | AMBIGUOUS, supported {ACTUATION/mechanical, SENSOR/response_sensor} |
| localization HIGH_CURRENT_LOW_RPM on motor_0 | AMBIGUOUS, supported {ACTUATION/mechanical}, unresolved {SENSOR/response_sensor} |
| attribution | **UNIQUE ACTUATION/motor_0** |
| `domains_excluded` | [COMMUNICATION, COMPUTE, POWER, **SENSOR**, TIMING] |
| SENSOR discriminators | the eight v1.1 navigation-source records (baro, battery, gps, imu0, imu1, mag, motor_esc, vibration) |

**The contradiction.** In the same output document:

- the localization says the SENSOR explanation cannot be eliminated;
- the attribution says SENSOR was "affirmatively NOMINAL, contributing no
  candidate", because eight unrelated sensor sources were nominal.

The attribution names the working motor as the unique cause of a
sensor fault. The same happens on the test-stand twin
MS_TS_B5_RESPONSE_SENSOR.

**Across all 2,640 ticks of the 44 shipped scenarios** (E.tick_census):

- 889 ticks had exactly one adverse attributable component;
- all 889 were UNIQUE, and 0 were AMBIGUOUS.

**What this means.** In the shipped profiles, UNIQUE is equivalent to "exactly
one adverse component". That is precisely what the module docstring says
UNIQUE is not ("Not 'it is the only one we noticed'").

## Irrelevant evidence changes localization

| case | records | localization |
|---|---|---|
| R16A | v1.1 PRECISION_NAVIGATION eligible (not attributable) + nav_solution end-to-end NOMINAL (`affected_functions` = PRECISION_NAVIGATION) + gnss_serial link NOMINAL + state_estimator deadline NOMINAL | no symptom |
| R16B | R16A + `COMPUTE/logger compute.deadline_met VIOLATED` (`affected_functions` = LOGGING) | POSITION_UNAVAILABLE on PRECISION_NAVIGATION: **SUPPORTED COMPUTE/estimator_stale** |

**Code path.** The late logger adds PRECISION_NAVIGATION to the subjects:

1. `_degraded_position_functions` (signatures.py:488-504) calls
   `_estimator_ok(index, name)`.
2. `_estimator_ok` (324-332) returns False if **any** COMPUTE process is
   adverse.
3. `localize` then confirms COMPUTE/estimator_stale and rejects the other
   three explanations.

**Responsible lines:** signatures.py:324-332 and 488-504.

**Shadow.** No symptom. The logger is not declared to serve
PRECISION_NAVIGATION.

**Engine level** (E.variants, real domains, shipped aircraft profile):

- **V_IRR_1.** A late logger in NOMINAL gives SUPPORTED estimator_stale on
  COARSE_NAVIGATION, POSITION_HOLD and PRECISION_NAVIGATION. All three
  functions stay ELIGIBLE.
- **V_IRR_3.** The telemetry radio going down gives SUPPORTED
  COMMUNICATION/starvation on the same three.
- **MS_B1_COMMAND_LOST** (shipped, unmodified). The ESC CAN bus going down
  gives SUPPORTED COMMUNICATION/starvation on the navigation functions. The
  GNSS link is healthy.

## Part 5: order. **Container order changes conclusions** when two records disagree

| case | records (same set) | localization OUTPUT_STALE on nav_solution |
|---|---|---|
| R6A | …, `clock_consistency NOMINAL`, `clock_consistency VIOLATED` | **UNSUPPORTED** (all five rejected) |
| R6B | …, `clock_consistency VIOLATED`, `clock_consistency NOMINAL` | **SUPPORTED TIMING/clock_inconsistent** |

The other records in both cases:

- nav_solution end-to-end VIOLATED;
- sensor_slow rate NOMINAL;
- transport and processing segments NOMINAL;
- gnss_serial link NOMINAL;
- state_estimator alive and producing NOMINAL.

**Mechanism.**

1. `_clock` → `index.one("timing.clock_consistency", component=channel)`.
2. `EvidenceIndex.one` returns `rows[0]` (localization.py:92-94), which is
   **insertion order**.

**Responsible line:** localization.py:94.

**Temporal vs container order.** Records carry timestamps, but nothing in
localization or attribution reads time. The order that matters here is
container order. It is not temporal order.

**Shadow.** Both orders give UNSUPPORTED with `TIMING/clock_inconsistent`
**unresolved** (INSUFFICIENT_EVIDENCE), and the disagreement is recorded.

**Scope.** Shipped scenarios never emit two records for one
(relation, component). Reversal and five seeded shuffles of every shipped
final tick changed nothing (P3: 0 of 264).

## Part 6: exact duplication

| case | records | effect |
|---|---|---|
| R7A | gps source VIOLATED (depends on rail_5v) + rail_5v VIOLATED | no MULTIPLE_SENSORS_DEGRADED |
| R7B | the **same** gps record twice + rail_5v | **MULTIPLE_SENSORS_DEGRADED appears**: POWER/shared_node supported, SENSOR/independent_faults rejected |
| R7C | rail VIOLATED + the same CPU NOMINAL record twice | attribution verdict unchanged; `discriminators` lists the CPU record **twice** |

**Mechanism.**

- **The symptom.** `_multi_sensor` counts `len(_adverse_sources(index)) >= 2`
  (signatures.py:484-485), and `_shared_adverse_dependency` counts each record
  (218-239). One source recorded twice counts as two sources sharing a node.
- **The trace.** The attribution discriminator list is not de-duplicated
  (attribution.py:174-176).

**In shipped scenarios** (P4):

- duplicating one record changed a decision in 3 of 2,503 cases, and each
  time it was this MULTIPLE_SENSORS_DEGRADED effect;
- 1,612 duplications changed only the trace.

## Part 8: missing evidence used as positive evidence

| case | records | localization |
|---|---|---|
| R8A | transport segment VIOLATED; link **not reported**; rest nominal | **SUPPORTED** COMMUNICATION/transport_delay |
| R8B | the same, link **UNAVAILABLE** | **UNSUPPORTED**: all five rejected, including the true cause, rejected by CHANNEL_LINK_NOMINAL |
| R8C | processing segment VIOLATED; producing process **VIOLATED** (true stall) | SUPPORTED COMPUTE/process_stall |
| R8D | the same; process **not reported** | AMBIGUOUS {processing_delay supported, process_stall unresolved} (correct) |
| R8E | the same; process **UNAVAILABLE** | **SUPPORTED COMPUTE/processing_delay**: process_stall rejected by PRODUCER_PROCESS_HEALTHY |
| R8F | motor: no current (ACT_NO_ELECTRICAL_RESPONSE); battery source VIOLATED; CPU NOMINAL | localization supports POWER/path_unavailable. Attribution AMBIGUOUS [motor_0, battery] |
| R8G | the same, battery **UNAVAILABLE** | localization **rejects** POWER/path_unavailable and supports drive_no_current. Attribution **UNIQUE ACTUATION/motor_0** |

**R8E is the brief's "I don't know, therefore H".**

- **Input.** The process's telemetry is missing.
- **Output.** v2 concludes the process was *running but slow*, and does so
  with SUPPORTED.
- **Mechanism.** `_producer_health` (signatures.py:106-123) counts the
  UNAVAILABLE `process_alive` record as "seen" and "not adverse". It returns
  True.

**Responsible lines:**

- R8E: signatures.py:117-123.
- R8B and R8G: `_any_adverse_id` (64-76), where an UNAVAILABLE row sets
  `seen` and is not adverse, giving False, so "all fine".

**Engine level** (E.variants, where the shipped domains emit the UNAVAILABLE
record themselves when telemetry is absent):

- **V_MIS_2.** MS_A4 (true stall) with the estimator's telemetry absent.
  OUTPUT_STALE moves from SUPPORTED process_stall to **SUPPORTED
  processing_delay**.
- **V_MIS_1.** MS_A2 (true transport delay) with the link telemetry absent.
  SUPPORTED transport_delay becomes UNSUPPORTED, all rejected.
- **V_MIS_4.** MS_B2 (true power path) with the battery telemetry absent.
  The supported cause switches to drive_no_current.

## Shared dependencies nobody reported

**Setup.** Two adverse sources, imu0 and mag, both declare the same four
nodes: POWER/rail_3v3, COMMUNICATION/bus_a, COMPUTE/proc_a, TIMING/clk_a.

| case | node records | MULTIPLE_SENSORS_DEGRADED |
|---|---|---|
| R17A | **none reported** | **SUPPORTED SENSOR/independent_faults**; all three shared-node hypotheses rejected |
| R17B | rail_3v3 VIOLATED | SUPPORTED POWER/shared_node; the unreported link and process are rejected |
| R17C | rail_3v3 **UNAVAILABLE** | **SUPPORTED SENSOR/independent_faults** |

**Mechanism.** `_shared_adverse_dependency` (signatures.py:218-239) finds the
shared nodes from the declared structure. It then keeps only those with
`_any_adverse_id(...) is True` (238), so a node nobody reported counts as
"not adverse". `_covered` is True because the model declares the nodes. The
predicates therefore return False (not shared), and
NO_SHARED_ADVERSE_DEPENDENCY returns True.

The module's own docstring for `_covered` (246-265) warns against exactly this
("turns 'I cannot see' into 'it is not so'"). The warning is applied to
undeclared nodes, but not to declared nodes that were never reported.

**Shadow.** R17A and R17C are AMBIGUOUS with all four unresolved. R17B keeps
POWER/shared_node supported, and leaves the unreported link and process
unresolved.

## Parts 9 and 10: exceptions, return types, malformed records

**Setup.** Synthetic spec: h1 is refuted by Q, h2 is refuted by R, and both
are confirmed by P, which is True.

| Q returns | R | frozen verdict | frozen `unmeasurable` | visible as an error? | shadow |
|---|---|---|---|---|---|
| True | False | SUPPORTED h2 | [] | — | same |
| False | False | AMBIGUOUS | [] | — | same |
| None | False | AMBIGUOUS | [Q] | — | same |
| raises KeyError | False | AMBIGUOUS | **[Q]** | **no** | same verdict; `RAISED:KeyError` recorded |
| raises ZeroDivisionError | False | AMBIGUOUS | **[Q]** | **no** | same verdict; recorded |
| `numpy.True_` | False | **AMBIGUOUS** (should refute h1) | **[]** | **no** | recorded `NON_BOOL:numpy.bool` |
| `1`, `"yes"`, `nan` | False | AMBIGUOUS | **[]** | **no** | recorded as NON_BOOL |
| True | **True** | UNSUPPORTED (all rejected) | [] | — | — |
| None | True | **SUPPORTED h1** | [Q] | — | — |
| raises KeyError | True | **SUPPORTED h1** | [Q] | **no** | — |

The last row (R9B) is a software defect that **creates** a SUPPORTED verdict:

- **Without the fault.** The refuter works and every explanation is ruled
  out.
- **With the fault.** The refuter raises, and the surviving hypothesis is
  named as the cause.
- **What the output shows.** Only that Q was "not measurable".

**Responsible lines:**

- localization.py:139-140 (catch-all);
- localization.py:303 and 310-311 (`is True`, so non-bool returns are
  neither True nor listed as unmeasurable).

**Malformed records.**

| case | input | frozen behaviour |
|---|---|---|
| R11A | `actuation.electrical_response VIOLATED` with `reason_codes=None` | localization: 11 predicates silently "unmeasurable" (the `in None` TypeError is caught). Attribution **raises** `TypeError` |
| R11B | `v1_1.source_health VIOLATED` with `dependencies=None` | attribution **raises** `TypeError: 'NoneType' object is not iterable`. The tick fails |
| R15A | a hypothesis names a predicate id absent from the table | `KeyError` propagates. The tick fails |
| R15B | a symptom detector raises | the exception propagates. The tick fails |

**The same fault behaves in opposite ways by stage.** A malformed record is:

- swallowed as "not measurable" in predicates;
- fatal to the whole tick in attribution and in detectors.

## Part 7: correlated evidence (three detectors on one IMU)

| case | how the three detectors report | attribution | localization |
|---|---|---|---|
| R18A | three relations of one component `SENSOR/source.imu1` | one candidate, UNIQUE (with an unrelated CPU discriminator) | — |
| R18B | three components `imu1.cusum`, `imu1.threshold`, `imu1.kalman`, each declaring `SENSOR/source.imu1` | **three candidates**, AMBIGUOUS, no common cause (the shared IMU has no adverse record) | — |
| R18C | one `v1_1.source_health` reading for source.imu1 | UNIQUE | no multi-sensor symptom |
| R18D | the same reading from three detectors, differing **only in `source`** | UNIQUE | **MULTIPLE_SENSORS_DEGRADED** appears ("two or more sensor-derived sources are adverse"), from one sensor |

**What CSIA can and cannot tell apart.**

- **Detector identity.** `EvidenceRecord.source` is never read by any
  reasoning path: changing only `source` changes no output
  (R18_source_field_read).
- **Shared physical source.** SENSOR is not among the common-cause domains
  (`_COMMON_CAUSE_DOMAINS`, signatures.py:243). Localization can therefore
  never name a shared physical source.
- **Conclusion.** Whether three views of one IMU become one candidate, three
  candidates or a multi-sensor symptom depends only on how the producer names
  its records.

**This limitation is recorded and not corrected here**, as the brief requires
(SC-14).

## Also found

**R12: VOLTAGE_RAIL_LOW can never resolve.**

- **Case.** rail_5v VIOLATED, battery affirmatively NOMINAL. VOLTAGE_RAIL_LOW
  is AMBIGUOUS {distribution, source}. The unmeasurable list is
  [SOURCE_WITHIN_TOLERANCE, SOURCE_WITHIN_TOLERANCE_FALSE].
- **Shipped scenario.** On REGULATOR_FAILURE the power domain's own reason
  code already says `POWER_DISTRIBUTION_SUSPECT`.
- **Responsible lines.** signatures.py:371 queries the source by the subject,
  and the subject is the rail's name (507).

**R14: an unrelated second fault gives AMBIGUOUS between the two.**

- **Case.** R1B plus a VIOLATED telemetry radio gives AMBIGUOUS
  [telemetry_radio, rail_5v].
- **Why.** Attribution treats every adverse component as a competitor for a
  single explanation. It has no way to say "two findings".
- **Severity.** This errs on the conservative side, but it is confusing
  (SC-17).

**R13: static facts.**

- `attribute_unsupported` has **no callers** anywhere in the repository.
- RAIL_WITHIN_TOLERANCE and PRODUCER_DEADLINE_MET are declared but used by
  no hypothesis, in either polarity.
