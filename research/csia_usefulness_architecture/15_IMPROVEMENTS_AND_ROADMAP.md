# New directions, prioritisation, labels, roadmap and top five (Phases 19, 20, 47, 48, 49)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`. Scores and labels for all 16 improvements are in
`IMPROVEMENT_SCORES.csv`.

## 1. Phase 19: candidate directions

Each of the brief's candidate areas A-P maps to one improvement; four more
come from the audit.

| brief area | improvement |
|---|---|
| A. evidence-admissibility tracking | I-01 |
| B. evidence provenance | I-09 |
| C. monitor-health monitoring | I-04 |
| D. correlated-evidence handling | I-06 |
| E. explicit evidence conflict | I-07 |
| F. configuration-aware invalidation | I-02 |
| G. method registry / plugin architecture | I-05 |
| H. automatic evidence expiration | inside I-01 (lifecycle) |
| I. evidence dependency graphs | I-09 |
| J. assumption contracts | inside I-01 |
| K. post-flight explanation traces | I-08 |
| L. audit-ready evidence chains | I-08 |
| M. integration with mature active diagnosis | I-13 |
| N. integration with RTA | I-12 |
| O. integration with flight-stack health data | I-02 and I-05 (RA-2) |
| P. learned monitors with strict validity envelopes | I-15 |
| added from the audit | I-03 verdict repair (AF-02, AF-03); I-10 analyzer product surface; I-11 vocabulary mapping (AF-08); I-14 event-bounded validity generalised; I-16 diagnosability accounting (closed-loop package P06) |

**Why some areas are grouped.** H and J live inside I-01. Admissibility
without contracts and lifecycle would be a status field with nothing
deciding it.

## 2. Phase 20: scoring

- **Scale.** Ten columns, each scored 0-5, for a maximum of 50. For the two
  cost columns, 5 means cheap.
- **Prior-art defensibility.** It is 1 for every item. Every improvement
  reuses an established method: DEM conditions, validity intervals, ATMS
  labels, runtime-verification assumptions, W3C PROV. Novelty is one column
  of ten, and it moves no ranking here.

| rank | id | improvement | total /50 | label |
|---|---|---|---|---|
| 1 | I-01 | evidence admissibility layer | 42 | ENGINEERING |
| 1 | I-03 | verdict semantics repair | 42 | ENGINEERING |
| 3 | I-04 | producer health and predicate-error reporting | 41 | ENGINEERING |
| 4 | I-08 | decision trace and audit-ready ledger events | 40 | ENGINEERING |
| 5 | I-05 | producer registry, adapter API, reference adapters | 38 | ENGINEERING |
| 5 | I-10 | configuration-change evidence analyzer | 38 | ENGINEERING |
| 7 | I-02 | configuration-aware targeted invalidation | 37 | ENGINEERING |
| 8 | I-06 | independence policy and source identity | 36 | ENGINEERING |
| 9 | I-07 | explicit disagreement | 35 | ENGINEERING |
| 10 | I-09 | minimal provenance | 34 | ENGINEERING |
| 10 | I-14 | event-bounded validity generalised | 34 | EXPERIMENTAL |
| 12 | I-12 | RTA integration | 33 | ENGINEERING |
| 13 | I-11 | vocabulary mapping | 32 | ENGINEERING |
| 14 | I-13 | active-diagnosis integration | 28 | EXPERIMENTAL |
| 15 | I-16 | diagnosability accounting | 25 | RESEARCH_PENDING_PRIOR_ART |
| 16 | I-15 | learned monitors with validity envelopes | 24 | RESEARCH_PENDING_PRIOR_ART |

## 3. Phase 47: research or engineering

| label | count | items | why |
|---|---|---|---|
| ENGINEERING | 12 | I-01 to I-12 | adapters, metadata, contracts, audit trail, configuration events and verdict naming are established practice. Complexity does not make them research |
| EXPERIMENTAL | 2 | I-13, I-14 | the mechanism is known; whether it pays off here needs a measured experiment (I-14: the first experiment; I-13: an integration trial with an existing planner) |
| RESEARCH_PENDING_PRIOR_ART | 2 | I-15, I-16 | open questions exist, but the closest literature is crowded (closed-loop package: safe active diagnosis, s-FEAST class; S072) and was not read in full |
| RESEARCH | 0 | — | no item has an unresolved technical uncertainty that has also passed a prior-art gate |

## 4. Phase 48: roadmap

**Gate 0 applies throughout.** Owner authorisation of overlay work, or the
freeze lifting, is required first (`13_MIGRATION_AND_VALIDATION.md` §4).

**Owner types** are the kind of person needed, not named individuals:

- core engineer;
- integration engineer (PX4, ArduPilot);
- test engineer;
- research scientist;
- owner.

### Horizon 1: make current CSIA better (0-6 weeks)

These are high-value, low-risk items, all overlays and all shadow-first.

| item | owner type | dependencies | difficulty | value (total) | validation gate |
|---|---|---|---|---|---|
| M0 golden fixtures for v2 and XSYS-001 | test engineer | Gate 0 | LOW | enabler | Gate B |
| I-03 verdict repair (2.1.0 plus 2.0.0 view) | core engineer | M0 | LOW | 42 | L0; 2.0.0 golden parity |
| I-01 admissibility layer in shadow (M1-M2) with minimal context | core engineer | M0 | MEDIUM | 42 | L0-L1; XSYS-001 V4 records non-admissible 55/55 |
| I-04 producer health and predicate errors | core engineer | I-01 | LOW | 41 | L0; injected staleness gives NOT_VALID |
| I-08 decision trace and ledger events | core engineer | I-01, I-03 | LOW | 40 | L0; trace fields vary with input (HF-008 lesson) |
| M3 shadow comparison, L4 XSYS-001 replay | test engineer | I-01, I-03 | MEDIUM | enabler | Gate D (partial) |
| first-experiment preregistration draft | research scientist | the above | MEDIUM | enabler | Gate C |

### Horizon 2: operational CSIA (2-6 months)

These are integrations, SITL and HIL, and the product surface.

| item | owner type | dependencies | difficulty | value (total) | validation gate |
|---|---|---|---|---|---|
| I-05 registry and adapters RA-1 to RA-4 | integration engineer | I-01, I-04 | MEDIUM | 38 | L0-L1; per-adapter conformance |
| I-02 targeted invalidation with PX4 and ArduPilot context | integration engineer | I-01, I-05 | HIGH | 37 | L2 synthetic suite; L3 |
| I-06 independence policy and source identity | core engineer | I-05 | MEDIUM | 36 | L0; self-referential refutation unit cases |
| I-07 disagreement | core engineer | I-03, I-06 | MEDIUM | 35 | L0; shadow comparison shows no lost correct results |
| first experiment run (XSYS-002-ADM) | research scientist, test engineer | Gate C | HIGH | decides I-14 | Gate F |
| lane-switch campaign (second experiment) | integration engineer | I-02 | HIGH | decides I-02's value | L5 |
| I-10 analyzer MVP for SITL, HIL and integration logs | integration engineer | I-01, I-05, I-08 | MEDIUM | 38 | L3 on committed logs |
| C port of the admissibility core; target benchmark | core engineer | I-01 stable | MEDIUM | enabler | Gate E |
| HIL run of the analyzer and the C core (L6) | test engineer | the above; bench authorisation | HIGH | enabler | L6 |
| structured interviews with integration and flight-test engineers | owner | I-10 prototype | LOW | validates the downstream views | recorded interview notes |
| I-12 RTA consumer contract; I-11 vocabulary mapping; I-09 provenance | core engineer | I-03 | LOW-MEDIUM | 32-34 | L0 |

### Horizon 3: advanced assurance (6-18 months)

Only items that pass prior-art and usefulness gates enter this horizon.

| item | owner type | dependencies | difficulty | gate before starting |
|---|---|---|---|---|
| I-14 event-bounded validity generalised to other witnesses | research scientist | first experiment positive | MEDIUM | Gate F result |
| I-13 information-need interface to an existing safe active-diagnosis planner | research scientist, integration engineer | I-03, I-05 | HIGH | integration trial preregistered; full-text reading of S072 |
| I-16 diagnosability accounting | research scientist | I-13 | HIGH | full-text prior-art gate (currently crowded) |
| I-15 learned monitors with validity envelopes | research scientist | I-05 | HIGH | prior-art gate |
| contract import from AADL / EMV2 through FORGE | owner, core engineer | FORGE authorised (S041) | HIGH | owner decision |
| L7 shadow flights | test engineer | L6, hardware gate | HIGH | hardware authorisation |

## 5. Phase 49: the top five

**The selection rule.** Take the five highest totals. Break ties first on
safety value, then on dependency on items outside the top five.

- **The one tie.** At 38, I-05 and I-10 are equal on safety value (3). I-10
  depends on I-05, so I-05 is chosen.
- **I-02 is not in the five.** Its targeted-invalidation value is exactly what
  the second experiment must demonstrate against a global flush. The five
  below already carry the first experiment.

| # | improvement | why now | failure it prevents | existing method reused | implementation complexity | validation plan | expected product value |
|---|---|---|---|---|---|---|---|
| T1 | I-01 evidence admissibility layer | the only wrong attributions in the confirmatory result came from the preregistered negative control, which used evidence outside its conditions (S014); v2 has no such check (AF-01) | FM-01, FM-02, FM-04, FM-08, FM-11, FM-33 | DEM enable conditions (S050); ARINC NCD (S053); RTDB validity intervals (S071); Trust Contract v0.1 (S023); quality alphabet (S024) | MEDIUM: an overlay package, compiled masks, slot table | L0-L2; L4 XSYS-001 replay with the expected V1-V4 results | the core of the analyzer: "this evidence was used outside its conditions" |
| T2 | I-03 verdict semantics repair | a correctness defect in frozen attribution found by probe (S044a); UNSUPPORTED overloaded (S031) | FM-13, FM-20, FM-22 | consistency-based diagnosis vocabulary (S061, S032) | LOW: additive 2.1.0 schema and compatibility view | L0; 2.0.0 golden parity; the probe case gives AMBIGUOUS | operators and consumers can act on the result: collect evidence, fix the model, or name a cause |
| T3 | I-04 producer health and predicate errors | a broken check currently looks like an unmeasurable one (S044b) | FM-15, FM-21, FM-28 | plugin supervision (S007); SYS_STATUS health (S054); assumption-based RV (S067) | LOW | L0; injected input staleness and raising predicates | maintenance view: which monitors are not trustworthy right now |
| T4 | I-08 decision trace and ledger events | the first product surface needs replayable justifications; HF-008 showed a justification can assert what it never checked | FM-16, FM-25, FM-32 | the v2 ledger hash chain (S009); v2 explanation (S010); the SupportCertificate hash fields (S017) | LOW | L0; trace fields vary with input; replay reads recorded decisions | post-flight and integration-test analysis; audit |
| T5 | I-05 registry and reference adapters | proves the architecture carries heterogeneous evidence without rewriting producers; needed for the first experiment (RA-3) and for autopilot context (RA-2) | FM-18, FM-27, FM-29 | the v1.1 CUSUM bank (S021); PX4 EstimatorStatus (S055); v2 domains (S006); ISO 13374 vocabulary (S058) | MEDIUM | per-adapter conformance; wrapped v2 domains give unchanged records | integrators plug in existing monitors instead of waiting for CSIA to re-implement them |

Implementation-ready specifications for these five are in
`16_TOP_FIVE_IMPLEMENTATION_SPEC.md`.
