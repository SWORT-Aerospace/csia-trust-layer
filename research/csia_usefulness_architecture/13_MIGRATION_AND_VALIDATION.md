# Migration, backward compatibility, validation ladder and decision gates (Phases 39, 40, 41, 53)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

**Rule.** Current validated behaviour is preserved at every step. Nothing is
rewritten all at once. Every stage has a rollback that deletes only what the
stage added.

## 1. Phase 39: migration sequence

| stage | code touched | behavioural change | tests | rollback | success criterion |
|---|---|---|---|---|---|
| **M0** freeze the baseline | new golden fixtures only; no production code | none | golden-hash tests over: every v2 Phase C and matched scenario (2.0.0 documents); XSYS-001 stage-1 derived inputs through the existing adapter for V1-V4 | delete the fixtures | goldens regenerate byte-identical twice, on two runs |
| **M1** envelope, registry, contracts | a new overlay package (`16_TOP_FIVE_IMPLEMENTATION_SPEC.md` §6); nothing in `csia/` | none: records are wrapped, not used | envelope round-trip; contract loader rejects unknown clauses and unknown dimensions; one declaration per existing domain plus the XSYS witnesses | remove the package | every existing record wrapped with a loadable contract; zero change to any 2.0.0 document |
| **M2** admissibility in shadow | overlay only; a separate shadow ledger | none: status computed and logged, not used | a unit test per status; XSYS-001 replay | remove the shadow step | V1-V3 witness records ADMISSIBLE in 110/110 symptomatic trials; the V4 negative-control records non-admissible in 55/55 |
| **M3** shadow comparison | overlay: `localize_admissible` beside the frozen `localize` | none: a divergence report only | parity harness | remove the harness | zero divergences whenever all records are admissible and every refuter is independent; every other divergence explained case by case |
| **M4** context and invalidation (shadow) | overlay: `ContextState`, `InvalidationIndex`, log readers for PX4 and ArduPilot status | none | synthetic transition suite (Level 2); SITL log replay | remove the modules | synthetic suite passes; invalidations match truth-labelled transitions; no invalidation storm on nominal logs |
| **M5** producer adapters and health | overlay: RA-1 to RA-4 (`06_PRODUCERS_REGISTRY_AND_ADAPTERS.md` §7) | none in 2.0.0 | per-adapter conformance tests; injected input staleness gives NOT_VALID | remove the adapters | each adapter's records carry contracts and tags; health events on every injected fault |
| **M6** verdict split, disagreement, attribution relevance | overlay: schema 2.1.0 builder; `compat_v2_0` view | **new 2.1.0 document only**; 2.0.0 unchanged | 2.0.0 byte-identical on goldens; unit tests for each new state; the S044a probe gives AMBIGUOUS in 2.1.0 | stop emitting 2.1.0 | 2.0.0 golden parity; every new state reachable by a unit case |
| **M7** first experiment and selectable path | overlay; a configuration flag, off by default | only when the flag is on | preregistered first experiment (`14_FIRST_EXPERIMENT.md`); Level 5 campaign | flag off | Gate F passes |
| **M8** default path | `csia/v2` consumers switched to 2.1.0, **only after the freeze lifts**; import-graph tests enforce the deprecations (AD-30) | 2.1.0 becomes the default; the legacy path is kept for replay | the full suite; goldens; ladder L0-L5 results attached | switch the default back; the legacy path is still present | Gates A-F all passed and recorded; owner sign-off |

**Where the freeze bites.**

- **M0-M7** are overlays that read frozen outputs. As research work, they fit
  the existing cross-system exception (S029).
- **M8** requires the engineering freeze to lift, which needs both paper
  submission-candidate tags (S029).

## 2. Phase 40: backward compatibility and replay

Historical evidence is never altered. The replay plan:

| asset | where it lives | how it is replayed | expected result | allowed? |
|---|---|---|---|---|
| v1 tests | `tests/` (v1 frozen-core suite) | unchanged; the new layers do not import the v1 runtime | all pass, zero diff to v1 (the existing `tests/test_v1_frozen.py` guard) | yes |
| v2 tests | `tests/test_v2_*.py` | unchanged, plus the parity harness | all pass; parity as in M3 | yes |
| sealed campaign fixtures | the sealed campaign and manifest directories | **read-only**: hash-verify before and after every replay | unchanged hashes | yes, read-only |
| XSYS-001 apparatus data (calibration, pilots) | `research/xsys_confirmatory_001/` | read the committed derived outputs through the existing pipeline; never re-extract raw logs into the sealed directories | identical derived values | yes, read-only |
| XSYS-001 confirmatory derived inputs | the sealed stage-1 evidence under the result manifest (S014) | a compatibility adapter builds envelopes, with RA-3 contracts, from the sealed stage-1 values and writes only to a new output directory | V1: 55/55 resolved at C1; V2: 55/55 at C3; V3: 55/55; **V4 legacy path: 55/55 WRONG, reproduced; V4 admissibility path: 0 WRONG, with the 55 cases AMBIGUOUS because W_DYN is non-admissible and only the shared RPM symptom remains** | yes, read-only |

**The compatibility adapter's rule.** It reads sealed files by path and hash,
writes elsewhere, and fails if any sealed hash changes. This is the same
discipline as the existing freeze guards (S045).

## 3. Phase 41: validation ladder

| level | content | exit criterion |
|---|---|---|
| **L0** unit | every envelope field, contract clause evaluator, admissibility status, lifecycle transition, invalidation rule, disagreement rule, verdict state and view | each state reachable; each rule has a positive and a negative test; no clause without an evaluator (FM-27) |
| **L1** contract and admissibility | load-time checks (unknown clause or dimension fails; cycles fail; the budget check); every existing domain and witness has a contract | 100 % of existing producers declared; loader negative tests pass |
| **L2** synthetic transitions | generated sequences for each row of `TRANSITION_MATRIX.csv` observable in logs: lane switch, reset, sensor selection, allocation change, compensation onset, mode change, flapping context | the invalidated set equals the expected set exactly; no invalidation outside it; no storm without `CONTEXT_UNSTABLE`; the monotone rule holds (no ELIGIBLE after invalidation) |
| **L3** historical replay | v2 Phase C and matched scenarios; Phase II ArduPilot 4.8 logs where committed | 2.0.0 byte parity; admissibility decisions stable across two replays |
| **L4** XSYS-001 shadow replay | §2 above | the expected V1-V4 results exactly |
| **L5** SITL configuration-change campaign | the first experiment, then a lane-switch campaign | preregistered criteria (`14_FIRST_EXPERIMENT.md` §5) |
| **L6** HIL | the analyzer on HIL logs; the onboard C admissibility core on target, for Gate E | measured budget inside the target ranges (`08_PERFORMANCE_SAFETY_BOUNDARY.md` §3); parity with the Python reference |
| **L7** real flight | shadow mode only; logs analysed post-flight; no action path | no divergence between onboard and post-flight traces; a disagreement and invalidation report for every flight |

**No level is skipped.** A failure at a level is recorded in the program's
negative-results practice and the design is changed. The level is not
re-scoped.

## 4. Phase 53: decision gates

| gate | passes when | evidence required |
|---|---|---|
| **Gate 0** (precondition) | the owner authorises implementation of the overlay under the cross-system exception, or the freeze lifts | a written owner decision, as for the existing exceptions (S029) |
| **Gate A** architecture review accepted | this package reviewed; the open decisions in `12_TARGET_ARCHITECTURE.md` §9 answered | review record |
| **Gate B** compatibility and replay plan accepted | §2 accepted; M0 goldens committed | golden fixtures plus hashes |
| **Gate C** first experiment preregistered | `14_FIRST_EXPERIMENT.md` turned into a frozen preregistration with manifest, before any flight | a preregistration commit that precedes the data |
| **Gate D** shadow-mode replay passes | L3 and L4 exit criteria met | parity and divergence reports |
| **Gate E** runtime budget passes | L6 target measurements inside the stated ranges, or ranges revised with the measurement recorded | a target benchmark report |
| **Gate F** SITL configuration-transition experiment passes | the preregistered success criteria of the first experiment met; the lane-switch campaign not worse than baseline | the result document plus manifest |

**Only after Gates 0 and A-F**, and the freeze lift, does the architecture
become the default CSIA path (M8).
