# Evidence as a first-class object, admissibility, contracts and lifecycle (Phases 3, 4, 12, 13)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`. Failure modes `FM-nn` are defined in `CSIA_FMEA.csv`.

**The question.** Can CSIA determine whether a piece of evidence is currently
**admissible**? Today it cannot (AF-01 in `01_CURRENT_SYSTEM_AUDIT.md`).

## 1. Phase 3: which candidate fields earn their place

The rule is that a field is kept only if it prevents or helps diagnose a
failure mode in `CSIA_FMEA.csv`.

**The main design choice.** Most "context" fields do **not** belong in each
record:

- facts about the vehicle (controller mode, estimator lane, sensor
  selection, configuration) live **once** in a context state;
- the record points to that state by an **epoch** number;
- assumptions, validity and invalidation conditions live **once** in a
  contract, and the record points to it by `contract_id`.

This keeps each record small (see `08_PERFORMANCE_SAFETY_BOUNDARY.md` §3)
and avoids copying autopilot state into every item.

| candidate field | prevents | decision | where it lives |
|---|---|---|---|
| evidence_id | FM-05, FM-16, FM-25 | **required** | record (deterministic content hash) |
| source | FM-16, FM-29 | **required** (already exists) | record: `EvidenceRecord.source` |
| source_type | FM-18 | derived | registry (from the producer declaration) |
| timestamp | FM-01, FM-12 | **required** (already exists as three timestamps) | record |
| acquisition_window | FM-01, FM-11, FM-12 | **required** | record (start and end, vehicle time) |
| vehicle_configuration | FM-17 | by reference | context (`config_hash`), via `context_epoch` |
| controller_mode | FM-02, FM-11 | by reference | context |
| estimator_mode | FM-10 | by reference | context |
| sensor_configuration | FM-29, FM-09 | by reference | context (selection and device ids) |
| operating_regime | FM-08 | by reference | context (airborne, flight mode); the regime **requirement** is in the contract |
| assumptions | FM-04 | by reference | contract (`requires`) |
| validity_conditions | FM-04, FM-11 | by reference | contract (`valid_while`, `window`) |
| invalidation_conditions | FM-02, FM-10, FM-11 | by reference | contract (`invalidated_by`) |
| uncertainty | FM-07 | optional, only with declared semantics | record; never compared across producers |
| independence_group | FM-05, FM-06, FM-19 | replaced by dependency tags | record (`dependency_tags`) |
| correlation_group | FM-06 | replaced by dependency tags | record; a numeric correlation is **not** proposed (S025) |
| provenance | FM-16, FM-32 | **required, minimal**: producer id and version, input channel ids, `derived_from` | record |
| causal_dependencies | FM-06, FM-19 | merged into dependency tags | record |
| transformation_history | FM-32 | audit only | ledger (debug view) |
| calibration_version | FM-17 | as a dependency tag (`calib:<id>`) | record tag; the calibration fact lives in context |
| model_version | FM-17, FM-27 | as a dependency tag (`model:<id>`) plus the producer version | record |
| expiration / persistence semantics | FM-01, FM-33 | by reference | contract (`persistence` class) |
| quality | FM-01, FM-15 | optional, from the existing quality alphabet (V, I, N, S, X, R; S024) | record |
| evidence_strength | FM-07, FM-28 | **dropped as a number**; replaced by the contract flag `exonerating` (may this producer's NOMINAL rule a hypothesis out?) | contract |
| computational origin | FM-18 | derived | registry |

The resulting record specification is in `EVIDENCE_RECORD_V2_FIELDS.csv` and
`12_TARGET_ARCHITECTURE.md` §3.

## 2. Phase 4: the admissibility check

### 2.1 Established vocabulary, checked first

| source | its states | what it contributes |
|---|---|---|
| ARINC 429 Sign/Status Matrix (S053) | Normal Operation, Functional Test, Failure Warning, **No Computed Data** | a data word can be "not meaningful now" for a reason other than failure. NCD is the closest established counterpart of NOT_APPLICABLE |
| AUTOSAR DEM (S050) and ISO 14229-1 status bits (S051) | enable conditions, storage conditions, "test not completed this operation cycle", test failed, confirmed, aging and healing | a monitor's result counts only when its **enable conditions** held. A result suppressed by a **storage condition** (another active fault explains it) is not stored |
| OBD-II readiness (S052) | enable criteria; ready or not ready | "no fault found" means nothing until the monitor has actually completed under its enable criteria |
| MAVLink SYS_STATUS (S054) | present, enabled, healthy (three separate bitmaps); explicit invalid encodings | presence, enablement and health are different facts |
| real-time database temporal consistency (S071) and age of information (S070) | absolute validity interval; relative consistency; age | staleness and mutual consistency are measurable properties of each datum |
| GNSS integrity (S073) | integrity "not available" | declining to bound is a legitimate output |
| CSIA v2 (S001) | NOMINAL, DEGRADED, VIOLATED, UNAVAILABLE, NOT_APPLICABLE; applicability APPLICABLE, NOT_APPLICABLE, INPUTS_MISSING | the producer-side vocabulary that already exists |
| CSIA quality alphabet (S024) | V, I, N, S, X, R | per-value quality at ingestion |

### 2.2 Proposed statuses

A label is proposed only where it leads to a **different downstream
action**. Each status also carries one or more reason codes.

| status | meaning | downstream action it enables | reasons it carries | established counterpart |
|---|---|---|---|---|
| `ADMISSIBLE` | every enable condition holds, no valid-while condition broken, within window and age, producer healthy | use it | — | ARINC Normal Operation; DEM test completed |
| `NOT_APPLICABLE` | the enable conditions do not hold now (for example, not airborne) | wait for the regime; nothing is wrong | `ENABLE_CONDITION_FALSE` | ARINC NCD; DEM enable condition false; OBD not ready |
| `STALE` | older than its maximum age, or its window has closed | refresh or re-acquire | `MAX_AGE_EXCEEDED`, `WINDOW_CLOSED`, `SUPERSEDED` | RTDB absolute validity interval; AoI |
| `INVALIDATED` | a condition it depended on changed after it was acquired | recompute under the new context | `ASSUMPTION_VIOLATED`, `CONFIGURATION_MISMATCH`, `DEPENDENCY_INVALID` | DEM storage condition; estimator reset semantics (S056) |
| `PRODUCER_NOT_VALID` | the producer or its input is unhealthy | maintenance or producer repair | `INSUFFICIENT_QUALITY`, `PRODUCER_FAILED`, `PREDICATE_ERROR`, `DEADLINE_MISSED` | ARINC Failure Warning; MAVLink health = 0 |
| `UNKNOWN` | admissibility cannot be decided: no contract, or a required context field is unavailable | fix configuration or integration; **fail closed** | `CONTRACT_MISSING`, `CONTEXT_UNAVAILABLE`, `CONTEXT_UNSTABLE` | GNSS integrity not available |

**The brief's candidate labels map as follows:**

- VALID becomes `ADMISSIBLE`.
- INVALID splits by cause into `INVALIDATED` and `PRODUCER_NOT_VALID`.
- ASSUMPTION_VIOLATED, CONFIGURATION_MISMATCH and DEPENDENCY_INVALID become
  **reasons** under `INVALIDATED`.
- INSUFFICIENT_QUALITY becomes a reason under `PRODUCER_NOT_VALID`.
- STALE, NOT_APPLICABLE and UNKNOWN are kept.

They are collapsed because every non-admissible status has the **same**
effect on reasoning: the record is excluded and eliminates nothing. Only the
downstream action differs, and six statuses cover every distinct action
above.

### 2.3 How admissibility meets the existing reasoning

1. **Admissibility runs before any predicate.**
2. **An admissible record passes unchanged** into `csia.v2` localization.
3. **A non-admissible record reaches localization as `NOT_APPLICABLE`.** Its
   predicates therefore return None, which is the existing, validated "not
   measurable" path (S002). The status and reasons are kept alongside it for
   the trace and for the information-need output.
4. **Admissibility never turns a record into NOMINAL or into adverse.** It can
   only remove a record from reasoning. This is the same one-directional
   discipline as the supervision overlay (S028) and the evidence-base layer
   (S043).
5. **Invalidated adverse evidence cannot lift a restriction** (FM-33). A
   function whose last admissible adverse evidence was invalidated goes to
   UNKNOWN, not ELIGIBLE, until new admissible evidence arrives.

### 2.4 XSYS-001 as the worked example

Sealed facts (S014, S015):

- W_DYN separates the causes in T1 = [0, 0.2) s;
- after compensation it reads nominal;
- reading it in T3 = [10, 15) s was wrong in 55/55 trials.

| evidence configuration in XSYS-001 | what the new check would return for W_DYN | effect |
|---|---|---|
| V1: W_DYN in T1 | `ADMISSIBLE` (enable conditions hold; window open; compensation not yet active) | unchanged: resolves at C1 |
| V2: W_CTRL in T3 | `ADMISSIBLE` for W_CTRL | unchanged |
| V3: both in their windows | both `ADMISSIBLE` in their windows | unchanged |
| V4: W_DYN read in T3 (the negative control) | `STALE` (`WINDOW_CLOSED`) under a time-bounded contract; `INVALIDATED` (`ASSUMPTION_VIOLATED: compensation_active`) under an event-bounded contract | the predicate becomes None; the 55 wrong attributions become at worst AMBIGUOUS or INSUFFICIENT_EVIDENCE, and W_CTRL resolves them |

**What this shows.** The check reproduces, as a general mechanism, what
XSYS-001's pipeline did by hand (S013).

**What it does not show.** It does not show that an event-bounded contract
beats a time window. In XSYS-001 the controller was fixed, so a time window
was enough. `14_FIRST_EXPERIMENT.md` is designed to test that.

**Answer to the key engineering question.** Yes. Before evidence can
eliminate or support a hypothesis, CSIA should check whether the conditions
that make it meaningful still hold:

- the only observed wrong attributions in this program's confirmatory result
  came from skipping that check (S014);
- the equivalent check is standard practice in automotive and avionics
  diagnostics (S050-S053).

## 3. Phase 12: explicit assumption contracts

### 3.1 Reuse before invention

Three contract shapes already exist in this repository or in standards:

- **the CSIA Trust Contract v0.1** (S023): per component, covering functions,
  dependencies, validity domain, degradation modes, fault modes, restart
  semantics and authorization;
- **the evidence-semantics channel contract** (S024): accepted and emitted
  states, freshness, retention and sentinel handling;
- **DEM enable and storage conditions** (S050).

The proposed **evidence contract** adds, per producer and relation, only
what those three lack:

- when a result counts (`requires`);
- what invalidates it (`invalidated_by`);
- how long it lives (`window`, `persistence`);
- whether its NOMINAL may exonerate (`exonerating`).

It references the Trust Contract for component dependencies rather than
repeating them.

### 3.2 Example: the XSYS-001 dynamics witness

This is illustrative. XSYS-001 is not hard-coded into the architecture.

```yaml
contract_id: research.xsys.w_dyn
contract_version: 1
producer: research.xsys.w_dyn            # producer id in the registry
relation: xsys.dynamics_T1
validation_status: VALIDATED_SIMULATION  # PX4 SIH only (S014)
evidence_class: TRANSIENT_WITNESS        # see §4
requires:                                # enable conditions (DEM term)
  - context.airborne == true
  - context.attitude_solution_valid == true
  - context.flight_mode in [POSITION, HOLD]
  - symptom.onset_known == true
invalidated_by:                          # any change -> INVALIDATED
  - context.gyro_source                  # IMU selection (device id)
  - context.allocation_epoch             # motor removal or effectiveness update
  - context.controller_config_hash       # gains changed
  - context.compensation_active          # the XSYS-001 lesson, event-bounded
window:
  anchor: symptom.onset
  start_s: 0.0
  end_s: 0.2                             # time bound: a fallback, not the primary
  end_on: context.compensation_active    # whichever comes first
timing:
  max_age_s: 0.2
  max_input_skew_s: 0.02                 # relative consistency (S071)
dependency_tags: [src:gyro_selected, model:rigid_body_nominal, phys:hover_symmetry]
exonerating: true                        # its NOMINAL may refute ACTUATION/<motor>
exonerating_justification: "in T1 a genuine loss produces a body-rate response above theta_dyn (S014 min margin 1.53 theta_dyn)"
```

### 3.3 Rules that keep contracts small and honest

- **Every clause type has one evaluator and one test.** An unknown clause
  makes the whole contract INVALID, never ignored (FM-27; the MX-011
  lesson).
- **Context fields named in a contract must exist** in the context model
  (`04_CONFIGURATION_TRANSITIONS.md` §2). Otherwise the contract fails to
  load.
- **Validation status is set by the registry**, from gate records, never by
  the producer (FM-25; `08_PERFORMANCE_SAFETY_BOUNDARY.md` §5).
- **Contracts compile once, at load, into bitmasks** (§3.4). No parsing
  happens at run time.
- **No temporal logic language** is introduced. Where a requirement needs
  one, FRET and Copilot already exist (S074) and are the route.

### 3.4 Precompilation

At load time each contract becomes:

- **`requires_mask`**: a bitmask over boolean context predicates;
- **`invalidated_by_mask`**: a bitmask over context dimensions;
- **scalars**: window bounds, maximum age and maximum skew;
- **`tag_mask`**: a bitmask over interned dependency tags.

A run-time admissibility check is then a few mask comparisons and two time
subtractions.

## 4. Phase 13: evidence lifecycle

### 4.1 States

```
CREATED --admit--> ADMITTED --(window end | max age)--> STALE --> EXPIRED
   |                  |  \--(invalidated_by dimension changes)--> INVALIDATED --> EXPIRED
   |                  \--(newer record, same producer+relation+subject)--> SUPERSEDED --> EXPIRED
   \--(requires false | producer not valid | unknown)--> held as NOT_APPLICABLE / PRODUCER_NOT_VALID / UNKNOWN
```

- **One direction only.** `INVALIDATED`, `STALE` and `SUPERSEDED` never return
  to `ADMITTED`. A fresh measurement is a **new** record with a new id. This
  keeps the trace honest; it is the same rule as the failure ledger's "a
  rerun gets a new entry".
- **`EXPIRED` means removed** from the working set. The record stays in the
  ledger.

### 4.2 Evidence classes

Different evidence types behave differently, so the class is declared per
contract.

| class | example | persistence | ends by |
|---|---|---|---|
| `TRANSIENT_WITNESS` | W_DYN; an onset response | short, window-bound | window end, or an event such as compensation becoming active |
| `STATE_OBSERVATION` | current innovation test ratio; rail voltage | until the next sample | SUPERSEDED; STALE if no update within `max_age_s` |
| `LATCHED_FINDING` | "motor 2 produced no RPM under command in window W" | until an invalidating transition, or an explicit clear after a healing criterion | invalidation; healing (DEM aging and healing, S050) |
| `CONFIGURATION_FACT` | airframe configuration, calibration version, hardware present | until changed | a context change event |
| `ACCUMULATED_STATISTIC` | CUSUM state; low-pass-filtered test ratio | while its inputs stay admissible and context is unchanged | invalidation **resets** the statistic, as the PX4 selector resets its relative test ratios after a switch (S056) |

### 4.3 Decay is not proposed

Confidence decay would need a number with no calibrated basis. That is the
same objection the v2 record already makes to a confidence field (S001).

Evidence therefore stays admissible at full standing until it expires, is
superseded or is invalidated, and then leaves reasoning completely. The only
graded behaviour is the lifecycle class above.
