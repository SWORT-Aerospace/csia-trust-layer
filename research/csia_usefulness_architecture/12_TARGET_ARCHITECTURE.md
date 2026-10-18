# Target architecture (Phases 24, 25, 26, 33, 34, 35)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`. **Design only; nothing is implemented.**

The target is written so that another engineer could build it without
inventing major decisions. Where a decision is still open, it is named as
open.

## 1. Principles

These are fixed before the modules.

1. **Overlay, not rewrite.**
   - Everything new lives outside `csia/` and `csia/v2/`, reads their
     outputs, and wraps their types.
   - The frozen `EvidenceRecord`, `localize()`, `attribute()` and
     `FunctionGraph` are called as they are.
   - Existing working code is not renamed.
2. **One direction.** Admissibility, invalidation and health can only
   **remove** evidence from reasoning or **widen** results. They never create
   support (FM-33).
3. **Categorical throughout.** No fused scores (S001, S005).
4. **Declared, compiled, checked.** Producers and contracts are declared in
   data, compiled at load into masks, and rejected at load when inconsistent.
   Nothing is parsed at run time.
5. **Deterministic and replayable.** Wall-clock values are never reasoning
   inputs, as in the v2 plugin runtime (S007). The ledger records decisions so
   that replay reads them.

## 2. Phase 24: modules

| placeholder name | proposed module | reuses | role |
|---|---|---|---|
| EvidenceProducer | `ProducerDeclaration` + `Producer` adapters | `csia.v2.domain.AssuranceDomain` (S006) as the grouping; the v1.1 CUSUM bank (S021); PX4 messages (S055) | produce envelopes; report health (`06_PRODUCERS_REGISTRY_AND_ADAPTERS.md`) |
| EvidenceRecord | `EvidenceEnvelope` | wraps the frozen `csia.v2.evidence.EvidenceRecord` (S001) | §3 and `EVIDENCE_RECORD_V2_FIELDS.csv` |
| EvidenceContract | `EvidenceContract` (compiled) | generalises the CSIA Trust Contract v0.1 (S023) and the evidence-semantics channel contract (S024) | §4 |
| EvidenceRegistry | `Registry` | the v2 `DomainRegistry`; the exact-key configuration gate (S017) as loader | producers, contracts, validation status, tag interning, budget check |
| ContextState / ConfigurationState | `ContextState` (one object; configuration hashes are dimensions of it) | reads PX4 and ArduPilot status (S055-S057) and MAVLink SYS_STATUS (S054) | the 16 dimensions and their change epochs (`04_CONFIGURATION_TRANSITIONS.md` §2) |
| DependencyGraph | `InvalidationIndex` (dimension and tag bitmaps plus the `derived_from` DAG) | FORGE-SEED acyclicity rule (S042) | targeted invalidation |
| EvidenceAdmissibilityEngine | `admissible(envelope, context, now)` | DEM enable-condition semantics (S050) | the six statuses (`03_EVIDENCE_ADMISSIBILITY.md` §2.2) |
| EvidenceLifecycleManager | `SlotTable` | v1.1 MaxAge rule (S021) | lifecycle states and classes |
| ConflictAnalyzer | `DisagreementAnalyzer` | the predicate values `localize()` already computes (S002) | D1 and D2 detection; rule-based explanations (`07_CONFLICT_SEMANTICS.md`) |
| HypothesisEngine | `csia.v2.localization.localize` (frozen) called through `localize_admissible` | the frozen algorithm | §5 |
| AttributionEngine | `csia.v2.attribution.attribute` (frozen) called through `attribution_inventory` | the frozen grouping and common-cause code | §6 |
| AssuranceState | `AssuranceStateBuilder` (schema 2.1.0) | `FunctionGraph` (S008); explanation (S010) | `09_DOWNSTREAM_AND_PRODUCT.md` §2 |
| AuditTrail | the existing ledger plus new event types | `csia.v2.ledger` hash chain (S009) | admissibility, transitions, disagreements, health |
| DownstreamInterface | `views` (onboard, operator, maintenance, audit) plus `compat_v2_0` | `csia.v2.api` 2.0.0 (S005) | §8 |

### 2.1 The tick, in order

```
 1. context.update(messages)                  -> dimension changes -> InvalidationIndex.on_transition(d)
 2. for producer in registry.enabled(context):  (enable conditions checked first; section 4 of 06)
        envelopes += producer.evaluate(inputs, context, now);  health[producer] = producer.health(...)
 3. slot_table.admit(envelopes)                 -> lifecycle CREATED -> ADMITTED or held with status
 4. slot_table.expire(now)                      -> STALE / SUPERSEDED / EXPIRED
 5. admissible_records = [e.record if ADMISSIBLE else as_not_applicable(e.record) for e in live]
 6. localizations = localize_admissible(specs, admissible_records, predicates, envelopes)   (section 5)
 7. disagreements = DisagreementAnalyzer(localizations.values, envelopes)
 8. inventory = attribution_inventory(admissible_records, relations, localizations)         (section 6)
 9. functions = FunctionGraph.evaluate(admissible_records)   + monotone rule (FM-33)
10. state = AssuranceStateBuilder(...); trace = DecisionTrace(...)                           (section 7)
11. ledger.append(transitions, admissibility changes, disagreements, health changes, trace hash)
```

### 2.2 Ownership and dependencies

- **Arrows point one way:** producers → envelopes → slot table → reasoning →
  state → ledger and views.
- **Nothing downstream feeds back** into evidence (FM-24).
- **The context state is read by producers and by admissibility**, and is
  written only by context update.

## 3. Phase 25: the evidence record, next generation

The full field specification is `EVIDENCE_RECORD_V2_FIELDS.csv`: 22 fields,
each with type, meaning, producer responsibility, consumer responsibility,
runtime cost, serialisation, and the failure modes it addresses.

| tier | fields | count |
|---|---|---|
| REQUIRED | the frozen `record`, `evidence_id`, `producer_id`, `producer_version`, `contract_id`, `acquisition_start`, `acquisition_end`, `context_epoch`, `dependency_tags`, `source_binding` | 10 |
| OPTIONAL | `derived_from`, `quality`, `uncertainty` | 3 |
| DERIVED (by CSIA) | `admissibility_status`, `admissibility_reasons`, `lifecycle_state`, `age_s`, `dim_mask` | 5 |
| DEBUG / AUDIT only | `input_channel_ids`, `input_hashes`, `compute_time_us`, `producer_detail` | 4 |

**The one compact-encoding decision: `context_epoch`.** It is a **single
global counter**, not a 16-element vector.

- The context keeps, per dimension, the global epoch at which that dimension
  last changed.
- A record is invalidated iff some dimension in its contract's
  `invalidated_by` changed after the record's epoch.

This keeps the record to 4 bytes of context reference. The check costs one
comparison per dimension named by the contract.

**Why the record is not bigger.** Assumptions, validity and invalidation
conditions, and operating regime are all referenced through `contract_id`.
Vehicle facts are referenced through `context_epoch`. Neither is copied into
each record (`03_EVIDENCE_ADMISSIBILITY.md` §1).

## 4. Phase 26: the evidence contract

### 4.1 Required keys

| key | type | meaning |
|---|---|---|
| `contract_id`, `contract_version` | string, int | identity; the hash is computed at load |
| `producer`, `relation` | string | what the contract governs |
| `validation_status` | enum (set by the registry from gate records, never by the author) | `DECLARED`, `VALIDATED_SIMULATION`, `VALIDATED_SITL`, `VALIDATED_HIL`, `VALIDATED_FLIGHT` |
| `evidence_class` | enum | `TRANSIENT_WITNESS`, `STATE_OBSERVATION`, `LATCHED_FINDING`, `CONFIGURATION_FACT`, `ACCUMULATED_STATISTIC` |
| `requires` | list of clauses | enable conditions. All must hold, or the record is `NOT_APPLICABLE` |
| `invalidated_by` | list of context dimensions, or `ANY` | any change after acquisition makes the record `INVALIDATED` |
| `timing.max_age_s` | number | beyond it, the record is `STALE` |
| `dependency_tags` | list of typed tags | see `05_PROVENANCE_AND_DEPENDENCE.md` §3.2 |
| `exonerating` | bool, plus `exonerating_justification` (required if true) | may this record's NOMINAL refute a hypothesis? |

### 4.2 Optional keys

| key | meaning |
|---|---|
| `window` (`anchor`, `start_s`, `end_s`, `end_on`) | a validity window relative to an anchor event, bounded by time, by an event, or by both (whichever comes first) |
| `timing.max_input_skew_s` | relative-consistency bound across inputs (S071) |
| `timing.update_rate_hz` | expected rate; a missed rate makes the producer `NOT_VALID` (`INPUT_STALE`) |
| `inputs` | per input: channel, required source binding, allowed device ids |
| `trust_contract_ref` | the component Trust Contract v0.1 whose validity domain and dependencies apply (S023) |
| `operating_regime` | a named subset of that Trust Contract's `validity_domain` |

### 4.3 Clause grammar

The grammar is minimal on purpose.

```
clause   := context.<dim> <op> <value>        op in {==, !=, in, <, <=, >, >=}
          | symptom.<field> <op> <value>      (only for windowed witnesses: onset known, subject)
          | producer.<id>.health == VALID      (a dependency on another producer's health)
dims     := the 16 context dimensions in 04_CONFIGURATION_TRANSITIONS.md section 2; anything else is a load error
```

- **Every clause type has one evaluator and one test.** An unknown clause is
  a load error (FM-27).
- **No disjunction across clauses except `in`.** No quantifiers. No temporal
  operators.
- **Temporal requirements that need more** go to FRET and Copilot (S074) as
  separate producers.

**Compilation.** At load, `requires` becomes a mask over boolean context
predicates. `invalidated_by` becomes a dimension mask, and tags become a tag
mask (`03_EVIDENCE_ADMISSIBILITY.md` §3.4).

**The example.** The W_DYN contract is in `03_EVIDENCE_ADMISSIBILITY.md`
§3.2. It is one instance. Nothing in the grammar, the modules or the masks
refers to XSYS-001.

## 5. Phase 33: is v2 localization still the right hypothesis engine?

| question | answer today | smallest change needed |
|---|---|---|
| can it consume admissibility-filtered evidence? | **yes**: a non-admissible record passed as NOT_APPLICABLE makes its predicates None, which eliminates nothing (S002) | none to the algorithm |
| can it distinguish support, refutation, not observed, not applicable and invalid without semantic hacks? | **partly**: support (True in `confirmed_by`) and refutation (True in `refuted_by`) are distinct; the other three all collapse into None | carry a **reason for None** alongside the value (from the envelope's admissibility status, or `PREDICATE_ERROR`, or `NOT_INDEPENDENT`); reported, never used to eliminate |
| can it handle evidence conflict? | **no**: refute wins silently (AF-05) | compute D1 collisions from the `values` map it already builds (`07_CONFLICT_SEMANTICS.md` §2) |
| can it preserve ambiguity? | **yes** | none |
| can it avoid double counting? | **yes for counting** (set elimination is idempotent); **no for common-mode refutation** | per-hypothesis refutation independence: a refuting predicate whose supporting records intersect the hypothesis's suspect tags is None for that hypothesis |
| can it work incrementally? | per tick, stateless, 45.8 µs on a host (S012) | not needed now; dirty-flag recomputation later if profiling requires it |

**Decision: KEEP the algorithm. REFACTOR its surroundings** (AD-02).

The smallest generalisation is a new function, `localize_admissible`, beside
the frozen `localize`. It:

1. evaluates predicates once, as today;
2. masks refuting predicates per hypothesis for independence;
3. applies the unchanged elimination loop;
4. returns the frozen `Localization` plus additive fields:
   - `status` (the split states);
   - `unmeasurable_reasons`;
   - `disagreements`.

The frozen `localize` stays for replay parity, and the two must agree
exactly whenever every record is ADMISSIBLE and no refuter is dependent
(Gate D).

**No replacement formalism is proposed.** A Bayesian or belief-function
engine would re-import scores that v2 excluded. It would need calibration data
that does not exist, and it would not fix any failure mode in the FMEA that
the smaller changes do not fix.

## 6. Phase 34: attribution

| question | answer |
|---|---|
| what does attribution mean today? | group adverse attributable records by component. UNIQUE if exactly one candidate **and** at least one NOMINAL record exists in another domain; AMBIGUOUS otherwise; name a shared adverse dependency as a common-cause alternative; list relation-implicated components without adverse evidence as UNSUPPORTED (S003) |
| is it necessary? | the **inventory** is (which components carry adverse admissible evidence, and which shared dependency is itself adverse). It works even when no symptom specification matches, which localization cannot. Its **verdict** is not necessary |
| does it duplicate localization? | yes, for "what caused it". The two run on the same records every tick (S004) and can disagree, with no rule for which wins |
| do its UNSUPPORTED semantics conflict with localization's? | yes: a third meaning for the same token (S031) |
| should it consume only admissible evidence? | yes |
| should it expose reasons rather than one label? | yes |

**Future relationship.**

- **LOCALIZATION** is the only component that may name a cause: SUPPORTED,
  AMBIGUOUS, INSUFFICIENT_EVIDENCE, NO_CONSISTENT_HYPOTHESIS or
  EVIDENCE_DISAGREEMENT per symptom.
- **ATTRIBUTION becomes an inventory**:
  - `adverse_components`;
  - `shared_adverse_dependencies` (the common-cause alternatives);
  - `implicated_without_evidence`.

  Its UNIQUE survives in the `2.0.0` compatibility view only, and only when:
  - localization is SUPPORTED for a symptom covering that component; or
  - the discriminators are **declared relevant**, meaning each named nominal
    record is a declared refuter of a competing hypothesis in the signature
    matrix.

  This fixes FM-20. The S044a probe case must become AMBIGUOUS.
- **ASSURANCE STATE** combines:
  - function eligibility (`FunctionGraph`, S008, on admissible records with
    the monotone rule);
  - per-symptom localization statuses;
  - the attribution inventory;
  - disagreements;
  - the inadmissible summary;
  - the information need.

## 7. Phase 35: "certificate" is the wrong word

The earlier novelty work found the experimental certificate much weaker than
formal integrity and certification concepts. HF-008 then found it had
asserted properties it never read (S018).

The useful product is a **decision trace**: a justification record. It makes
no claim to be a certificate, and it answers six questions.

| question | trace field | source of the data |
|---|---|---|
| what conclusion was produced? | `conclusion` (status, supported and unresolved hypotheses, function states) | localization; function graph |
| which evidence supported it? | `supporting` (evidence ids per confirming predicate) | predicate values plus envelopes |
| which evidence refuted alternatives? | `refuting` ((hypothesis, predicate, evidence ids) triples; the existing `rejected` pairs extended with ids) | S002 `rejected` |
| which evidence was rejected as invalid? | `inadmissible` ((evidence id, status, reasons)) | admissibility |
| which assumptions were required? | `assumptions` (contract ids and hashes of every used record; the enable conditions satisfied) | contracts |
| which configuration was active? | `configuration` (`config_hash`, `contract_set_hash`, `context_epoch`, software hash) | context; the SupportCertificate's hash fields, reused (S017) |
| what changed since the previous conclusion? | `delta` (evidence ids added, expired, invalidated; statuses changed) | slot-table diff |

**Integrity.** The trace hash enters the existing ledger chain (S009), with
the same stated limit: it detects gaps and reordering, and it is not
tamper-proof.

**What the trace does not do.** It never asserts freshness or applicability
that was not computed. A test must show those fields vary with the input
(the HF-008 lesson).

## 8. Downstream interface

- **Schema.** `assurance_state` 2.1.0 is additive
  (`09_DOWNSTREAM_AND_PRODUCT.md` §2).
- **Compatibility.** A `compat_v2_0` view regenerates the frozen 2.0.0
  document. It must be byte-identical on the golden corpus whenever every
  record is ADMISSIBLE (Gate B).
- **Views.** Four: onboard, operator, maintenance, audit.

## 9. Open decisions

These are named, not guessed.

1. Whether reading estimator status as **context** is permitted under the
   freeze's "estimator domain" prohibition (S029). This is an owner decision.
2. The value of N, the tag width and the derivation depth. These are design
   limits, to be set by profiling the replay corpus (Gate E).
3. Whether `compensation_active` is derived from W_CTRL's κ with its own
   threshold, or from the PX4 allocator's saturation and effectiveness state.
   This is decided by the first experiment's calibration flights.
