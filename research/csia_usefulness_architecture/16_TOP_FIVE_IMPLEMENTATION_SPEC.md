# Implementation specifications for the top five, and the repository plan (Phases 51, 52)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

**No code is written in this phase.** Interfaces are given as signatures so
that an implementer has no major decision left open. Every module is an
**overlay**: it lives outside `csia/` and `csia/v2/`, imports their public
types, and changes none of them. That keeps it inside the program freeze
(S029, S045).

## T1: evidence admissibility layer (I-01)

| aspect | specification |
|---|---|
| **module boundary** | `csia_admissibility.envelope`, `.contracts`, `.context`, `.admissibility`, `.lifecycle`. It imports `csia.v2.evidence` (types only). It imports nothing from `csia/runtime`, `csia/v1_1` producers or `research/` |
| **public interface** | `EvidenceEnvelope.wrap(record, producer, contract, acquisition, context, tags, *, derived_from=(), quality=None, uncertainty=None) -> EvidenceEnvelope`; `load_contracts(paths) -> ContractSet` (raises `ContractError`); `ContextState.update(messages, now) -> tuple[Transition, ...]`; `admissible(envelope, context, now) -> Admissibility(status, reasons)`; `SlotTable.admit(envelopes, context, now)`, `.expire(now)`, `.live(status=None)` |
| **data structures** | `EvidenceEnvelope`: frozen dataclass per `EVIDENCE_RECORD_V2_FIELDS.csv`. `CompiledContract`: `requires_mask`, `requires_values`, `dim_mask`, `tag_mask`, `window` (`anchor`, `start_us`, `end_us`, `end_on_dim`), `max_age_us`, `max_skew_us`, `evidence_class`, `exonerating`, `hash`. `ContextState`: 16 fields, `last_change_epoch[16]`, a global epoch counter, per-dimension freshness and stability counters. `SlotTable`: a fixed-capacity array of envelopes, a lifecycle-state array and a free list |
| **state transitions** | lifecycle: CREATED → ADMITTED \| NOT_APPLICABLE \| PRODUCER_NOT_VALID \| UNKNOWN; ADMITTED → STALE \| INVALIDATED \| SUPERSEDED → EXPIRED. One direction only (`03_EVIDENCE_ADMISSIBILITY.md` §4.1) |
| **error handling** | a contract load error (unknown clause, unknown dimension, cycle, missing justification when `exonerating: true`) **aborts start-up**, fail-closed at configuration time. A missing context field at run time gives `UNKNOWN (CONTEXT_UNAVAILABLE)`. `admissible()` never raises: an internal exception gives `UNKNOWN` plus a health event. A full slot table evicts the oldest EXPIRED slot, then the oldest STALE one, and never an ADMITTED one; if nothing can be evicted, a new record is rejected with a ledger event |
| **backward compatibility** | the wrapped `EvidenceRecord` is byte-identical. `as_not_applicable(record)` builds a **new** record with `observation_state=NOT_APPLICABLE` and `applicability=NOT_APPLICABLE` for the frozen reasoning path; the original is kept in the envelope |
| **tests** | a unit test per status and per lifecycle transition; contract-loader negative tests (unknown clause, unknown dimension, cycle); the monotone rule (no ELIGIBLE after invalidation); XSYS-001 V1-V4 replay counts (`13_MIGRATION_AND_VALIDATION.md` §2) |
| **benchmark** | host first: per-envelope `admissible()` and per-tick `expire()` over the Phase C scenario corpus; later, target cycles (Gate E) |
| **migration** | M1 (wrap), M2 (shadow status), M3 (shadow comparison) |
| **rollback** | remove the package; no frozen file was touched |
| **dependencies** | none in the top five. PyYAML (already a dependency) for contract files |

## T2: verdict semantics repair (I-03)

| aspect | specification |
|---|---|
| **module boundary** | `csia_admissibility.verdicts` (`localize_admissible`, `attribution_inventory`), `.state` (schema 2.1.0 builder), `.compat_v2_0` |
| **public interface** | `localize_admissible(spec, records, predicates, envelopes=None) -> AdmissibleLocalization` (the frozen `Localization` plus `status`, `unmeasurable_reasons`, `independence_masked`); `attribution_inventory(records, relations, localizations, relevance) -> Inventory(adverse_components, shared_adverse_dependencies, implicated_without_evidence, unique_compatible: bool)`; `build_state(...) -> dict` (2.1.0); `compat_v2_0(state, frozen_outputs) -> dict` (2.0.0) |
| **data structures** | `Status` enum: SUPPORTED, AMBIGUOUS, INSUFFICIENT_EVIDENCE, NO_CONSISTENT_HYPOTHESIS, EVIDENCE_DISAGREEMENT, NO_EVIDENCE. `RelevanceTable`: for each hypothesis, the relation ids that are declared refuters of its competitors, derived at load from the signature matrix |
| **state transitions** | none; pure functions per tick |
| **error handling** | a predicate exception gives None plus the reason `PREDICATE_ERROR` (reported to T3). A signature matrix without suspect scopes gives a load warning, and independence masking is disabled for that hypothesis, visibly, in the trace |
| **backward compatibility** | `compat_v2_0` must reproduce the frozen 2.0.0 document **byte for byte** on the golden corpus. That includes the frozen attribution behaviour; the relevance fix appears in 2.1.0 only. With all records admissible and no dependent refuters, `localize_admissible` must equal the frozen `localize` on every golden case |
| **tests** | the two UNSUPPORTED senses map to the two new states (the S044c probe); the S044a probe gives `unique_compatible=False`; golden parity; a mapping test (every new state maps to exactly one 2.0.0 verdict) |
| **benchmark** | the added cost over frozen `localize` (independence ANDs) on the Phase C corpus |
| **migration** | M6 |
| **rollback** | stop emitting 2.1.0; 2.0.0 is unaffected |
| **dependencies** | T1 for envelopes (optional: without them every record counts as admissible and independence masking is off) |

## T3: producer health and predicate errors (I-04)

| aspect | specification |
|---|---|
| **module boundary** | `csia_admissibility.health` |
| **public interface** | `ProducerHealth.evaluate(declaration, input_view, context, now) -> Health(state: VALID \| NOT_VALID, reasons)`; `HealthMonitor.record_predicate_error(predicate_id, producer_id)`; `HealthMonitor.snapshot() -> dict` |
| **data structures** | per producer: last input times per channel, deadline counters, predicate-error counters, the last health state, and a transition log (bounded ring buffer) |
| **state transitions** | VALID ↔ NOT_VALID, with hysteresis: K consecutive evaluations to return to VALID. K is declared per producer and defaults to 3, to be measured. Every change is a ledger event |
| **error handling** | health is computed from **independent** signals: input freshness (the MaxAge rule, S021); SYS_STATUS bits (S054); plugin supervisor state (S007); version and calibration against context; the predicate-error count. It is never computed from the producer's own verdict. An exception inside the health evaluation gives NOT_VALID (`NUMERICAL_FAILURE`) |
| **backward compatibility** | `PluginSupervisor` stays as is. Its FAILED and NOT_CONFIGURED states map to NOT_VALID for every producer in that domain |
| **tests** | a stale input gives NOT_VALID within one tick of MaxAge; a raising predicate increments its counter and yields `PREDICATE_ERROR`; hysteresis prevents flapping; NOT_VALID records never reach reasoning |
| **benchmark** | per-producer health cost per tick |
| **migration** | M2 (shadow), M5 (full) |
| **rollback** | remove the module; plugin supervision is unaffected |
| **dependencies** | T1 |

## T4: decision trace and ledger events (I-08)

| aspect | specification |
|---|---|
| **module boundary** | `csia_admissibility.trace`, plus event types registered with the existing ledger (S009) through its public append API. The v2 ledger module is not edited; if it cannot accept new event types without edits, a parallel ledger with the same hash-chain mechanism is used until the freeze lifts |
| **public interface** | `DecisionTrace.build(conclusion, predicate_values, envelopes, admissibility, contracts, context, previous_trace) -> DecisionTrace`; `.to_dict()`; `.hash()`; ledger event types `ADMISSIBILITY_CHANGED`, `CONTEXT_TRANSITION`, `PRODUCER_HEALTH_CHANGED`, `DISAGREEMENT_OPENED` / `CLOSED`, `DECISION_TRACE` |
| **data structures** | trace fields per `12_TARGET_ARCHITECTURE.md` §7 (conclusion, supporting, refuting, inadmissible, assumptions, configuration, delta). Onboard events store hashes and counts; the debug view stores the full lists |
| **state transitions** | none; each trace links to the previous one by hash |
| **error handling** | a trace that cannot be built is an event in its own right, `TRACE_FAILED` with a reason. A decision is never emitted without either a trace or a `TRACE_FAILED` event. Fields are filled only from computed results, with no defaults for freshness or applicability (HF-008) |
| **backward compatibility** | existing ledger events unchanged; replay of old ledgers unaffected |
| **tests** | trace fields change when inputs change (a mutation test against hard-coding); the hash chain detects a removed event; replay **reads** recorded admissibility decisions and reproduces the state (FM-32); a round trip through the audit view |
| **benchmark** | bytes per tick onboard; ledger growth per hour of replay |
| **migration** | M2 (shadow ledger), M6 (with 2.1.0) |
| **rollback** | stop writing the new event types |
| **dependencies** | T1, T2 |

## T5: producer registry and reference adapters (I-05)

| aspect | specification |
|---|---|
| **module boundary** | `csia_admissibility.registry`; `csia_admissibility.producers.{api, cusum, px4_estimator, xsys_witness, v2_domain}` |
| **public interface** | `Registry.load(declarations, contracts, gate_records) -> Registry` (raises `RegistryError`); `Registry.enabled(context) -> tuple[Producer, ...]`; `Registry.validation_status(producer_id) -> Status`; `Producer.evaluate(inputs, context, now)`, `.health(...)`, `.reset(reason)` (`06_PRODUCERS_REGISTRY_AND_ADAPTERS.md` §6) |
| **data structures** | `ProducerDeclaration` per `06_PRODUCERS_REGISTRY_AND_ADAPTERS.md` §1.1; a tag-interning table; a budget table (declared cost per producer) |
| **the adapters** | **RA-1 CUSUM** wraps `csia.v1_1.sequential` unchanged. Semantics `ABSENCE_OF_ALARM`, `exonerating: false`, class `ACCUMULATED_STATISTIC` (reset on invalidation). **RA-2 PX4 estimator** reads `EstimatorStatus` (test ratios, `solution_status_flags`, reset counts, device ids, fault flags; S055) and emits evidence **and** context updates. **RA-3 XSYS witnesses** loads the witness functions by path, read-only, as `csia_assurance` loads its clean-room reference (S017). It emits W_DYN with the event-bounded contract and `compensation_active` as evidence. **RA-4 v2 domain** wraps an existing `AssuranceDomain` unchanged, with contract and tags from a declaration file |
| **state transitions** | registry: LOADED (immutable during a run). Producer: per T3 health |
| **error handling** | declarations are loaded through the exact-key configuration gate (S017): an unknown key fails. A validation status in a declaration is ignored, because the status comes from gate records. A load-time budget overrun is a load error. An adapter that cannot read its input emits UNAVAILABLE with a reason, never NOMINAL |
| **backward compatibility** | RA-4 must reproduce the wrapped plugin's records exactly, and RA-1 the CUSUM bank's alarms exactly |
| **tests** | per-adapter conformance: output equality with the wrapped implementation; declaration negative tests; an import-graph test that nothing imports `csia.runtime.service` (AD-30) or writes to `research/` |
| **benchmark** | per-adapter evaluation cost; registry load time |
| **migration** | M5 |
| **rollback** | remove the adapters; the wrapped implementations are unaffected |
| **dependencies** | T1, T3 |

## Phase 52: repository plan

These paths are **not created** in this phase. They follow the existing
convention of top-level `csia_*` packages outside the frozen core
(`csia_assurance`, `csia_mission`, `csia_supervision`, `csia_evidence`).

```
csia_admissibility/                 (new overlay package)
  __init__.py
  envelope.py      contracts.py     context.py      admissibility.py
  lifecycle.py     invalidation.py  health.py       registry.py
  verdicts.py      disagreement.py  trace.py        state.py
  compat_v2_0.py   views.py
  producers/
    api.py   cusum.py   px4_estimator.py   xsys_witness.py   v2_domain.py
specifications/evidence_contracts/*.yaml             (beside the existing trust contract)
specifications/producer_declarations/*.yaml
schemas/csia_assurance_state_2_1_0.schema.json
tests/test_admissibility_envelope.py, ..._contracts.py, ..._context.py, ..._verdicts.py,
      ..._health.py, ..._trace.py, ..._producers.py, ..._golden_parity.py
tests/golden/admissibility/                           (M0 fixtures)
docs/architecture/EVIDENCE_ADMISSIBILITY.md           (written when implemented)
```

**Why not `csia/evidence/`.** That name already exists and holds the
anytime-valid e-process research (S039). A new sub-package there would
collide in meaning and sit inside `csia/`.

**Files likely to be modified later.**

| file | when | why |
|---|---|---|
| `docs/DOCUMENT_INDEX.md` | each stage | document count and rows |
| `Makefile` | M1 | an `admissibility-check` target in the existing guard style |
| `tests/test_ci_env.py` | only if a dependency is added | none planned: PyYAML is already a dependency |
| `csia/v2/api.py`, `csia/v2/engine.py` and consumers | **M8 only, after the freeze lifts** | switch the default output to 2.1.0 |
| `csia/runtime/*` (v1) | **never** | zero-diff freeze |
