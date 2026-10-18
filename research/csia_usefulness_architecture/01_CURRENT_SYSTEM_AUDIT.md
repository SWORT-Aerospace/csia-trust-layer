# Phase 1: current system audit

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`. Design and audit only: nothing in the repository was changed to
produce this file.

## 0. What "CSIA" is today

There are three layers. They are not bridged (S016).

| layer | where | state | role |
|---|---|---|---|
| **v1 / v1.1** | `csia/` (frozen, zero diff; S029) | temporal, Bayesian, cross-**sensor** | Beta trust recursion over 8 sensor nodes and 11 relations; gated naive-Bayes diagnosis over 8 causes; failsafe advisory policy; v1.1 adds function eligibility, a CUSUM bank, MaxAge-derived stale timeouts and an output firewall (S021, S022, S030) |
| **v2 Phase C** | `csia/v2/` (frozen artifacts; S045) | atemporal, structural, cross-**domain** | domain plugins emit categorical `EvidenceRecord`s; a function graph; set-elimination localization over 9 symptoms, 30 hypotheses and 52 predicates; structural attribution; ledger; API schema 2.0.0 (S001-S011) |
| **peripheral research layers** | `csia_assurance`, `csia_mission`, `csia_supervision`, `csia_evidence`, `csia_bus_provenance`, `csia_hybrid`, `csia_physical`, `csia_active_evidence` and others | outside the frozen core; each additive | experimental support certificate and firewall; capability assurance; data-loss overlay; evidence-base records; bus provenance; the Phase 5 fast path; physical ingestion; active evidence (S017, S025-S028, S043) |

**XSYS-001 ran through v2 localization via an adapter** that applied the
temporal windows itself (S013). v2 has no notion of an evidence window.

## 1. Pipeline graph

```
RAW OBSERVATIONS
  Snapshot.signals[domain][component][signal]         (host-supplied)       S006
  v1.1 payload, schema 1.1.0, parsed one-way           (NAVIGATION domain)   S005
  v1 path: ULog/MAVLink adapters -> samples with MaxAge freshness            S021
        |
        v
EVIDENCE GENERATION
  v2 AssuranceDomain plugins (POWER, ACTUATION, NAVIGATION, COMPUTE,
    COMMUNICATION, TIMING) -> EvidenceRecord (categorical state)             S001, S006
  v1 TrustCore (Beta recursion) + v1.1 CUSUM bank                            S021, S030
  research witnesses (XSYS W_RPM, W_DYN, W_CTRL) computed outside the core   S013, S015
        |
        v
EVIDENCE CONDITIONING                           <- the thinnest stage
  PluginSupervisor: FAILED/NOT_CONFIGURED plugin -> UNAVAILABLE records      S007
  Applicability enum on each record (APPLICABLE / NOT_APPLICABLE /
    INPUTS_MISSING), set by the producer                                     S001
  v1.1 gating and stale timeouts (v1 path only)                              S021
  XSYS windows: applied by the experiment pipeline, not by CSIA              S013
  NO admissibility check, NO context, NO expiry, NO invalidation in v2       S004
        |
        v
LOCALIZATION   localize_all(): per symptom, three-valued set elimination     S002, S011
ATTRIBUTION    attribute(): UNIQUE / AMBIGUOUS / UNSUPPORTED / NO_EVIDENCE   S003
FUNCTIONS      FunctionGraph: ELIGIBLE / DEGRADED / INELIGIBLE / UNKNOWN     S008
        |
        v
RESULT / "CERTIFICATE"
  v2 API document 2.0.0 + explanation (limiting / possible / cleared)        S005, S010
  v2 ledger (hash chain)                                                     S009
  separate, NOT wired to v2: assurance firewall + EXPERIMENTAL
    SupportCertificate; mission capability states; supervision overlay       S017, S027, S028
        |
        v
DOWNSTREAM CONSUMERS
  v2: a document; no command, no mode, no score                              S005
  v1: failsafe advisory; opt-in MavlinkActuator.set_mode (frozen code)       S022
  v1.1 output firewall: default-deny for writes                              S021
```

## 2. Stage-by-stage assessment

### 2.1 Raw observations

| aspect | finding |
|---|---|
| current implementation | the host builds a `Snapshot` of nested signals (S006); v1 adapters decode ULog and MAVLink |
| validated behaviour | v1.1 MaxAge stale timeouts derived from declared rates (S021); v2 ingests v1.1 through the strict parser (S005) |
| unvalidated assumptions | that a signal's name identifies its physical source. It does not: ArduPilot's `VIBRATION` follows whichever accelerometer is first usable, with no instance field on the wire (S025) |
| known failure modes | absent values collapsing into usable values (sentinels, retained values, imputed zeros; S024, S026); misattributed sources (S026) |
| technical debt | three separate state vocabularies for "is this value real" (S024 quality alphabet, S026 provenance coordinate, v1 `valid` flag) |
| duplicated functionality | freshness is derived in v1.1 (MaxAge) and again, differently, in the replay path (HF-014 in S018) |
| missing abstraction | **source identity** bound to a physical device (PX4 already publishes `accel_device_id` and `gyro_device_id`; S055) |
| coupling | v2 NAVIGATION is coupled to the v1.1 payload schema (by design, one-way) |
| computational cost | JSON Schema validation dominated ingest (22 ms per tick uncached, 0.67 ms cached, 9.2 µs typed; S012) |
| test coverage | v2 ingest is covered by `tests/test_v2_internal_interface.py` (15 test functions); freshness replay has recorded instrument defects (HF-014, HF-017 in S018) |

### 2.2 Evidence generation

| aspect | finding |
|---|---|
| current implementation | six v2 domain plugins; v1 trust core; v1.1 CUSUM; research witnesses outside the core |
| validated behaviour | v2 Phase C verdict `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL` on synthetic and matched scenarios; XSYS-001 witnesses in simulation (S014) |
| unvalidated assumptions | that a producer's NOMINAL is an affirmative exoneration. W_DYN's NOMINAL after compensation was a false exoneration in 55/55 trials (S014) |
| known failure modes | an evidence producer whose meaning depends on the controller's state (S014, S034); CUSUM absence-of-alarm is not proof of health |
| technical debt | `EvidenceRecord.sequential_state` is never assigned (S016); v1's temporal evidence has no route into v2 (S016) |
| duplicated functionality | two diagnosis engines: v1 Bayes over 8 causes and v2 set elimination over 30 hypotheses, never reconciled |
| missing abstraction | a **per-producer declaration** (what it assumes, when it is valid, what it depends on). Plugins declare inputs, relations and functions, not validity (S006) |
| coupling | research witnesses live in `research/`, so a validated witness has no production home |
| computational cost | domains median 747 µs per tick on a host (S012) |
| test coverage | `tests/test_v2_domains.py` 34 test functions; `tests/test_v2_scenarios.py` 27 |

### 2.3 Evidence conditioning

| aspect | finding |
|---|---|
| current implementation | plugin supervision (S007); the producer-set `applicability` flag (S001) |
| validated behaviour | a crashing plugin produces UNAVAILABLE, not silence (S007); "not measurable" eliminates nothing (S002) |
| unvalidated assumptions | that the producer knows when its own evidence stops meaning anything. XSYS-001 needed the experimenter to impose the window (S013) |
| known failure modes | **timeless evidence** (S014); stale evidence; evidence surviving an estimator or configuration change (S034); a predicate exception silently becoming "not measurable" (S044b) |
| technical debt | `provenance` is a free-form dict; `dependencies` is a free-form tuple (S001) |
| duplicated functionality | a validity monitor for the e-process research (S039), the mission capability "fresh and applicable" check (S027), the supervision data-loss rule (S028) and plugin supervision (S007) each re-implement part of "may this evidence be used now" |
| missing abstraction | **admissibility**: a single check, before reasoning, of whether the conditions that make a record meaningful still hold |
| coupling | none, because the stage barely exists |
| computational cost | negligible today |
| test coverage | plugin supervision is covered in `tests/test_v2_framework.py`; admissibility has no tests because it does not exist |

### 2.4 Localization

| aspect | finding |
|---|---|
| current implementation | deterministic set elimination per symptom and per subject (S002) |
| validated behaviour | Phase C matched scenarios; XSYS-001 55/55 resolved at C3 with 0 WRONG (S014); an independent checker agreed 378,000/378,000 for the related Mechanism A account (S030) |
| unvalidated assumptions | that refuting evidence does not depend on the component it exonerates; that all refuters are independent of each other |
| known failure modes | UNSUPPORTED means both "all refuted" and "one unconfirmed survivor" (S031, S044c); a raising predicate is indistinguishable from an unmeasurable one (S044b); a hypothesis that is both confirmed and refuted is rejected silently, because refute wins (S002 lines 302-307) |
| technical debt | per-symptom only, with no joint check across symptoms (S032) |
| duplicated functionality | attribution answers "what caused it" again, by a different rule (S003, S004) |
| missing abstraction | the **reason** a predicate is None (not observed, not applicable, inadmissible, error) |
| coupling | predicates read `EvidenceIndex` directly; the matrix is Python data (S011) |
| computational cost | 45.8 µs per tick on a host, 9 symptoms (S012) |
| test coverage | `tests/test_v2_localization.py` 30 test functions |

### 2.5 Attribution

| aspect | finding |
|---|---|
| current implementation | groups adverse attributable records by component; UNIQUE if one candidate and any NOMINAL record exists in another domain; common cause by dependency reachability (S003) |
| validated behaviour | common-cause retention (rail scenario E) in Phase C; tests pin the behaviour (S037) |
| unvalidated assumptions | that any nominal record elsewhere excludes the alternatives. **It does not**: an unrelated nominal COMPUTE record turned AMBIGUOUS into UNIQUE (S044a). The module docstring promises more ("every other domain that would have shown adverse evidence… is affirmatively NOMINAL"); the code and its test implement "any NOMINAL record from another domain" (S003, S037, S038) |
| known failure modes | UNIQUE licensed by irrelevant evidence; a third meaning of UNSUPPORTED (S031) |
| technical debt | the docstring and the implemented rule disagree |
| duplicated functionality | localization (S004) |
| missing abstraction | the relevance of a discriminator to the competing hypothesis |
| coupling | uses the free-form `dependencies` tuple for common-cause reachability |
| computational cost | median 91.6 µs per tick on a host (S012) |
| test coverage | `tests/test_v2_framework.py` 31 test functions, which encode the weak rule (S037) |

### 2.6 Function graph

| aspect | finding |
|---|---|
| current implementation | per-function required, supporting and no-degradation domains; limiting domain; one-of-N redundancy groups (S008) |
| validated behaviour | Phase C; UNKNOWN outranks INELIGIBLE, so "cannot tell" is never acted on as "available" (S008) |
| unvalidated assumptions | that the worst observation state of a domain is the right input; no admissibility filter in between |
| known failure modes | an alarm and the capability report disagreeing, in the peripheral mission layer (SR-005 in S018) |
| technical debt | the mission capability layer (S027) re-states function availability with a different state set |
| missing abstraction | none essential |
| computational cost | included in the domain and engine timings |
| test coverage | covered in the v2 framework and scenario tests |

### 2.7 Result, justification and "certificate"

| aspect | finding |
|---|---|
| current implementation | v2 API document with the full evidence list; explanation with limiting, possible and cleared domains; ledger hash chain (S005, S009, S010); a separate EXPERIMENTAL SupportCertificate built from a firewall verdict (S017) |
| validated behaviour | deterministic replay and byte-identical documents; hash-chain gap detection (S009) |
| unvalidated assumptions | that a certificate's freshness and applicability fields were checked. HF-008: they were hard-coded (S018) |
| known failure modes | a near-zero gate weight licensing SUPPORTED_UNIQUE (HF-001 in S018); a certificate asserting properties it never read (HF-008) |
| technical debt | "certificate" names something much weaker than formal integrity or certification concepts (novelty audits) |
| duplicated functionality | three justification formats: the v2 Localization dict, the v2 explanation, and the SupportCertificate |
| missing abstraction | a **decision trace** listing which evidence was rejected as inadmissible and why |
| computational cost | explanation 87.3 µs; ledger 14.1 µs median; API build and serialisation about 1-3 ms per tick on a host (S012) |
| test coverage | `tests/test_v2_api_ledger.py` 22; `tests/test_assurance_firewall.py` 21; metamorphic 11; vectors 5 |

### 2.8 Downstream consumers

| aspect | finding |
|---|---|
| current implementation | v2 produces a document and commands nothing (S005); v1 failsafe advisories, with an opt-in `MavlinkActuator.set_mode` in frozen code (S022); the v1.1 output firewall denies writes by default (S021) |
| validated behaviour | advisory by default; transport-level and operation-level write denial |
| unvalidated assumptions | that consumers can use a full evidence dump; no consumer-specific view exists |
| known failure modes | an alarm that reaches nothing (SR-004, SR-005 in S018) |
| missing abstraction | an "information need" output: what evidence would resolve the ambiguity, and what is blocking it |
| coupling | v2 and v1 outputs are independent documents |

## 3. Cross-cutting findings

| id | finding | evidence |
|---|---|---|
| AF-01 | **v2 has no evidence validity beyond the current tick.** Temporal validity in XSYS-001 was imposed by the experiment pipeline; the core would have used the dynamics witness at any time | S004, S013, S014 |
| AF-02 | **UNSUPPORTED is overloaded** across localization (two meanings) and attribution (a third) | S002, S003, S031, S044c |
| AF-03 | **attribution UNIQUE can be licensed by an unrelated nominal record.** The docstring promises relevance; the code and its test do not require it | S003, S037, S038, S044a |
| AF-04 | **a raising predicate is silently "not measurable".** Safe for elimination, but the fault in the predicate is never reported | S002, S044b |
| AF-05 | **confirm-and-refute on one hypothesis is resolved silently** in favour of refutation, with no disagreement record | S002 lines 302-315 |
| AF-06 | **no context or configuration model** in v2; plugin configuration hashes exist but records do not carry the configuration they were produced under | S001, S007 |
| AF-07 | **no dependency discipline for refutation**: nothing stops evidence derived from a component from exonerating that component | S001, S002 |
| AF-08 | **at least ten state vocabularies** for overlapping questions: v2 observation states, applicability, localization verdicts, attribution verdicts, function states, plugin states, firewall verdicts, mission capability states, evidence-quality alphabet, provenance coordinate, e-process validity | S001-S008, S017, S024, S026, S027, S039 |
| AF-09 | **validated pieces exist but are not connected**: plugin supervision, the quality alphabet, the Trust Contract schema, the ledger and the explanation are all reusable, and none performs admissibility | S007, S009, S010, S023, S024 |
| AF-10 | **no native v2**: the C core covers v1 only, and no target measurement exists | S020 |
| AF-11 | **an actuation path exists in frozen v1**, opt-in and advisory by default, which conflicts with the target safety boundary | S022 |

AF-03 and AF-04 are defects in frozen v2 behaviour, found by this review.
Under the freeze they are recorded here and in `02_CSIA_FMEA.md`, not fixed.
The failure ledger was not appended; whether to add an entry is left to the
owner.
