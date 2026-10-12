# Evidence producers: registry, reuse, monitor health, method selection, API and reference adapters (Phases 8, 9, 11, 14, 31, 32)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

## 1. Phase 8: the producer abstraction

**Start from what exists.** A v2 `AssuranceDomain` plugin already declares
(S006):

- required and optional inputs;
- relations;
- affected functions;
- reason codes.

It is supervised for crashes, configuration and deadlines (S007).

**What is missing.** It declares nothing about **validity**, and the unit is a
whole domain rather than an individual evidence source.

**Decision.** Keep `AssuranceDomain` as the grouping and execution boundary.
Add a finer **producer declaration** for each evidence source inside or beside
a domain. A domain can host several producers. An external method (CUSUM,
PX4 estimator status, a structural residual) becomes a producer through a
thin adapter.

### 1.1 What every producer declares

| declaration | type | why (FM ids from `CSIA_FMEA.csv`) |
|---|---|---|
| `producer_id`, `version` | string, semver | FM-16, FM-17 |
| `inputs` | list of (channel id, source binding: `FIXED_DEVICE` \| `SELECTED_DEVICE` \| `UNKNOWN`) | FM-29 |
| `output` | relation ids, and the mapping from native output to `ObservationState` | FM-07, FM-28 |
| `nominal_semantics` | `AFFIRMATIVE` (a check that would have fired) \| `ABSENCE_OF_ALARM` | FM-28 |
| `contracts` | contract ids, one per relation | FM-04, FM-08 |
| `dependency_tags` | typed tags (see `05_PROVENANCE_AND_DEPENDENCE.md` §3.2) | FM-06, FM-19 |
| `update_rate_hz`, `latency_s` | numbers, declared and checked | FM-12, FM-15 |
| `uncertainty_semantics` | `NONE` \| `CALIBRATED_INTERVAL` \| `UNCALIBRATED_SCORE` | FM-07 |
| `validation_status` | set by the **registry** from gate records (§5) | FM-18, FM-25 |
| `failure_behaviour` | what it emits when it cannot evaluate: always `UNAVAILABLE` with a reason, never NOMINAL | FM-15, FM-21 |

**No common probability is required.** A producer that has a calibrated
number may report it with declared semantics. CSIA never compares numbers
across producers.

## 2. Phase 9: build versus reuse

| capability | mature method or implementation | decision | note |
|---|---|---|---|
| fast change detection | CUSUM (Page 1954), GLR, SPRT | **reuse**: the v1.1 CUSUM bank already implements Page's CUSUM (S021); wrap it as a producer | INVENTION_GATE CLOSED: textbook CUSUM met every hard constraint (S030) |
| slow drift | the same CUSUM bank; ArduPilot already has a cumulative GPS drift monitor (S030) | **reuse**, do not build a dual-timescale variant from scratch | replaces the planned bespoke remedy for R16 |
| state consistency | estimator innovation tests (PX4 test ratios, S055; Kalman-filter integrity, S073) | **wrap** the autopilot's own ratios and flags | CSIA does not re-implement the estimator |
| sensor data qualification | limit, rate and analytical-redundancy checks (S064); the v1.1 stale timeouts (S021); the quality alphabet (S024) | **reuse** the existing ingestion checks | |
| structural isolability (design time) | Fault Diagnosis Toolbox (S069); D-matrix analysis (S068) | **reuse offline** to check a signature matrix | `minimum_resolving_subsets` (S002) stays for predicate-level questions |
| active evidence acquisition and safe probing | s-FEAST-class safe active diagnosis (S072) | **integrate, do not build** | CSIA supplies the information need (§4); the planner decides |
| runtime safety | run time assurance and Simplex (S075) | **delegate** | non-goal |
| capability margin | flight-stack performance tools (S035) | **delegate** | G02 decision |
| navigation integrity | ARAIM and Kalman-filter integrity (S073) | **delegate**; consume the integrity status as evidence | |
| requirement monitors | FRET, Ogma and Copilot (S074) | **reuse** for temporal-logic monitors | no new logic language |
| provenance export | W3C PROV (S065) | **reuse** as an export format | |
| component dependency declarations | CSIA Trust Contract v0.1 (S023); AADL and EMV2 via FORGE later (S041) | **reuse** | |

## 3. Phase 11: monitoring the monitors

**What exists.** `PluginSupervisor` (S007) handles, **per domain**:

- a plugin that fails;
- a plugin that is not configured;
- a plugin that misses its deadline (opt-in).

The e-process research has a validity monitor that fails closed (S039).

**What is missing.** Per-producer health, and reporting of predicate errors,
which today become silent "not measurable" (S044b).

**Producer health state.** One per producer:

- `VALID`;
- `NOT_VALID`, with one of these reasons:
  - `INPUT_MISSING`;
  - `INPUT_STALE`;
  - `CALIBRATION_INVALID`;
  - `REGIME_UNSUPPORTED`;
  - `DEADLINE_MISSED`;
  - `MODEL_VERSION_MISMATCH`;
  - `ASSUMPTION_VIOLATED`;
  - `NUMERICAL_FAILURE`;
  - `PREDICATE_ERROR`;
  - `CALIBRATION_EXPIRED`.

**Rules.**

1. **A NOT_VALID producer's records are `PRODUCER_NOT_VALID`.** They never
   reach reasoning as NOMINAL or adverse.
2. **The health of a producer is decided from independent signals**, not
   from its own output. Those signals are:
   - input freshness (the v1.1 MaxAge rule, S021);
   - MAVLink SYS_STATUS health bits (S054);
   - the plugin supervisor (S007);
   - predicate-error counts;
   - deadline accounting;
   - version and calibration matching against the context.

   This follows assumption-based runtime verification: a verdict is only as
   good as the assumptions it is conditioned on (S067).
3. **Health changes are ledger events**, as plugin status changes are today
   (S007).
4. **A predicate that raises is caught as now, but also counted.** It
   produces `PREDICATE_ERROR` on its producer and an unmeasurable reason, so
   the defect is visible (fixes FM-21 without changing the fail-safe
   direction).

## 4. Phase 14: which producers to run

This is an engineering optimisation. No novelty is claimed.

1. **Enable conditions decide first.** A producer whose contract's `requires`
   is false is not evaluated at all. This is exactly DEM enable conditions and
   OBD non-continuous monitors (S050, S052), and it is most of the saving.
2. **A static schedule by budget.** Each producer declares its cost. The
   registry checks at load that the worst-case sum of enabled producers fits
   the tick budget. It rejects configurations that do not fit, rather than
   dropping producers at run time.
3. **The information need drives optional producers.** When localization
   leaves a symptom AMBIGUOUS, it lists the predicates that would separate the
   survivors. The minimum resolving subset (S002) is already computed. The
   registry may then enable an optional producer that serves one of them, if
   its cost fits.

   **Exciting the vehicle to obtain such evidence is not CSIA's decision.** It
   is published as an information need for an active-diagnosis planner (S072)
   or an operator.
4. **Every producer runs on replay.** Post-flight, cost matters less, so every
   producer runs, subject to its enable conditions.

## 5. Validation status

Validation status is assigned by the registry, never by the producer.

| status | granted by |
|---|---|
| `DECLARED` | a declaration and contract that load |
| `VALIDATED_SIMULATION` | a preregistered simulation result (e.g., XSYS-001 for W_DYN and W_CTRL under PX4 SIH, S014) |
| `VALIDATED_SITL` / `VALIDATED_HIL` / `VALIDATED_FLIGHT` | the corresponding gate record (`13_MIGRATION_AND_VALIDATION.md`) |

A consumer can require a minimum validation status per function. For example,
a function might admit only `VALIDATED_SITL` or better.

## 6. Phase 31: the adapter API

Interface specification only. No implementation.

```
ProducerDeclaration        # static; loaded and checked at start-up (section 1.1)
Producer.evaluate(inputs: InputView, context: ContextView, now: VehicleTime)
    -> tuple[EvidenceEnvelope, ...]      # zero or more; never raises out
Producer.health(context: ContextView, now: VehicleTime) -> ProducerHealth
Producer.reset(reason: ResetReason)      # called on invalidation of its accumulation
```

- **`InputView`** exposes only the declared inputs, each with its value,
  quality (S024), timestamps and source identity.
- **`ContextView`** exposes only the context dimensions the producer's
  contracts name.
- **Why narrow views.** They make undeclared dependencies impossible rather
  than merely forbidden. This is the same design as v1.1's `Observation`,
  which cannot see ground truth (S021).
- **What an envelope wraps.** Each envelope wraps an unchanged
  `csia.v2.evidence.EvidenceRecord` plus the fields in
  `EVIDENCE_RECORD_V2_FIELDS.csv`.
- **Wrapping.** An adapter for an external method maps its native output to
  `ObservationState` under its declared `nominal_semantics`. A CUSUM with no
  alarm is `NOMINAL` with `ABSENCE_OF_ALARM`, and its contract sets
  `exonerating: false` unless a detection-coverage argument is attached
  (FM-28).

## 7. Phase 32: the reference adapters

Exactly four, to prove heterogeneity. None is implemented in this phase.

| # | adapter | wraps | what it proves | why it was chosen |
|---|---|---|---|---|
| RA-1 | **CUSUM** | `csia/v1_1/sequential.py` bank, unchanged (S021) | a textbook detector with `ABSENCE_OF_ALARM` semantics and an `ACCUMULATED_STATISTIC` lifecycle that resets on invalidation | already validated as the best-performing baseline (S030); exercises FM-28 and reset |
| RA-2 | **PX4 estimator status** | `EstimatorStatus`: test ratios, `solution_status_flags`, reset counts, device ids, fault flags (S055) | external autopilot evidence **and** context in one message; source identity from device ids | fielded, V4-read, and it supplies the context dimensions invalidation needs |
| RA-3 | **physical witnesses W_DYN / W_CTRL** | the XSYS-001 witness computations, from research code, read-only (S013, S015) | a `TRANSIENT_WITNESS` with an event-bounded contract; `compensation_active` produced as evidence | the only witnesses with a preregistered result; the XSYS-001 lesson |
| RA-4 | **a v2 domain, wrapped** | an existing plugin such as POWER, unchanged (S006) | legacy producers need no rewrite: their records get envelopes, contracts and tags from a declaration file | proves backward compatibility |

**Not chosen.**

- **ArduPilot health.** Useful, but it duplicates RA-2's role, and parts of its
  topology are invisible on the wire (S025).
- **Reachability and learned detectors.** Their validity envelopes are
  research questions, not adapter questions.
