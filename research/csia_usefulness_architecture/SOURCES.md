# Sources and search log

CSIA usefulness architecture review, 2026-09-29. Every other file in this
package cites sources by the ids defined here (`Snnn`).

## Verification levels

| level | meaning |
|---|---|
| V0 | search summary only |
| V1 | abstract |
| V2 | substantial text |
| V3 | complete text |
| V4 | exact lines read or executed; for external files, with a hash |

**External papers and standards.** Every one is **V0** and carries
REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION. Scholarly and standards hosts were
unreachable from this environment, as recorded in every previous package, and
nothing below goes beyond what the summaries state.

**Repository files.** These were read at V4.

**Fielded code.** PX4 and MAVLink files were fetched from
raw.githubusercontent.com and hashed.

## 1. Repository sources (read in this review)

| id | source | what it establishes here | level |
|---|---|---|---|
| S001 | `csia/v2/evidence.py` | `EvidenceRecord` fields (lines 59-103): categorical `observation_state` required, numerics optional, free-form `provenance` dict, `dependencies` tuple, `attributable` flag; `worst([])` is UNAVAILABLE (lines 147-157) | V4 |
| S002 | `csia/v2/localization.py` | three-valued predicates; a predicate that raises returns None (lines 136-140); verdict rules, with UNSUPPORTED used for "all refuted" and "one unconfirmed survivor" (lines 320-335); per-tick only; exhaustive `minimum_resolving_subsets` (lines 363-416) | V4 |
| S003 | `csia/v2/attribution.py` | UNIQUE when one adverse candidate and any NOMINAL record from another domain exist (lines 169-198); common-cause retention by dependency reachability (lines 138-160); UNSUPPORTED = implicated by a relation without adverse evidence (lines 162-167, 252-259) | V4 |
| S004 | `csia/v2/engine.py` | the engine is stateless between ticks except for the ledger; localization and attribution both run on the same records every tick (lines 122-149) | V4 |
| S005 | `csia/v2/api.py` | schema 2.0.0; no score, no command, no mode; v2 ingests v1.1 one way | V4 |
| S006 | `csia/v2/domain.py` | `Snapshot` and the `AssuranceDomain` plugin contract: required and optional inputs, relations, functions, reason codes; determinism | V4 |
| S007 | `csia/v2/plugin_runtime.py` | plugin states AVAILABLE, DEGRADED, FAILED, NOT_CONFIGURED; a failed plugin emits UNAVAILABLE on every declared function; deadline evidence is opt-in; `configuration_hash` | V4 |
| S008 | `csia/v2/functions.py` | ELIGIBLE, DEGRADED, INELIGIBLE, UNKNOWN; UNKNOWN outranks INELIGIBLE | V4 |
| S009 | `csia/v2/ledger.py` | deterministic hash chain ("not tamper-proof"); events carry domain, component, limiting domain, dependencies, attribution | V4 |
| S010 | `csia/v2/explanation.py` | per-function limiting, possible and cleared domains | V4 |
| S011 | `csia/v2/signatures.py` (measured by import in this review) | 9 symptoms, 30 hypotheses, 52 predicates | V4 |
| S012 | `engineering/v2/V2_COMPUTE.json`, `engineering/v2/V2_PHASEC_COMPUTE.json` | host CPython timings: domains median 747 µs/tick; localization alone 45.8 µs; attribution median 91.6 µs; explanation 87.3 µs; ledger median 14.1 µs; 68 records and 9 symptoms per tick; no target-hardware figure | V4 |
| S013 | `research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py` | XSYS-001 windows were applied **outside** v2: outside its window a witness became NOT_APPLICABLE and its predicate None | V4 |
| S014 | `docs/research/XSYS_001_CONFIRMATORY_RESULT.md` §A, §O | 55/55 resolved; the preregistered negative control read W_DYN in T3 and was wrong in 55/55 | V4 |
| S015 | `docs/research/FIRST_CROSS_SYSTEM_EXPERIMENT.md` (witness table) | W_DYN compares response with the nominal closed-loop envelope; W_CTRL is command-side compensation | V4 |
| S016 | `docs/research/CROSS_SYSTEM_ARCHITECTURE_SEED.md` | recorded gaps: v2 is atemporal; `sequential_state` is never assigned; no v1-to-v2 bridge; producers may report but not update belief (Phase 5 constraint) | V4 |
| S017 | `csia_assurance/firewall.py`, `witness.py`, `config_gate.py` | fail-closed firewall; EXPERIMENTAL SupportCertificate, not wired into v2; exact-key configuration gate outside the core | V4 |
| S018 | `research/physical_validation/FAILURE_LEDGER.yaml` entries HF-001, HF-005, HF-008, HF-014, MX-001, MX-002, MX-011, SR-001, SR-004, SR-005, FL-016 | recorded failures of CSIA's own layers; the individual entries are cited where used | V4 |
| S019 | `docs/FMEA.md` (v0.7) | the existing FMEA of the v1 monitor, F1-F10 | V4 |
| S020 | `docs/embedded/NATIVE_RUNTIME_STATUS.md` | the C core covers the v1 trust step and diagnosis only; host benchmark 247 ns and 427 ns per tick; no STM32H743 build or measurement | V4 |
| S021 | `csia/v1_1/` (`staleness.py`, `sequential.py`, `eligibility.py`, `firewall.py`) | MaxAge-derived stale timeouts; textbook CUSUM bank (Page 1954; k = 0.5, h = 500); REQUIRE_IDENTIFIABLE eligibility; default-deny output firewall | V4 |
| S022 | `csia/runtime/failsafe.py`, `csia/runtime/service.py` | frozen v1 failsafe recommends actions; `MavlinkActuator` can call `set_mode` when opted in | V4 |
| S023 | `csia/contracts/csia_trust_contract_schema_v0.1.json`; `docs/architecture/CSIA_TRUST_CONTRACT.md` | component Trust Contract v0.1: identity, functions, dependencies (rails, timing, bus, estimator, shared software, mounting), validity domain (flight phases, dynamics, temperature, vibration, operating modes), restart semantics, authorization (active action prohibited) | V4 |
| S024 | `research/evidence_semantics/CANONICAL_STATE_MODEL.md`; `EVIDENCE_SEMANTICS_CONTRACT.schema.json` | quality alphabet: V OBSERVED_VALID, I OBSERVED_INVALID, N NOT_OBSERVED, S STALE, X SENTINEL, R RETAINED_AFTER_DISAVOWAL; per-channel contract (accepted states, freshness, retention, sentinel handling) | V4 |
| S025 | `research/effective_evidence_independence/README.md` | runtime sensor topology changes and is invisible on the ArduPilot wire; a provenance-cut metric is **not** independence (shared source can still give diagnostic diversity; distinct sources can share a physical disturbance); PX4 publishes the sensor selection | V4 |
| S026 | `csia_bus_provenance/provenance.py` | value-provenance coordinate REAL, RETAINED, IMPUTED, MISATTRIBUTED | V4 |
| S027 | `csia_mission/capability.py` | capability states SUPPORTED, DEGRADED_SUPPORTED, NOT_SUPPORTED, NOT_EVALUABLE, UNKNOWN; UNKNOWN never promoted | V4 |
| S028 | `csia_supervision/__init__.py` | the overlay may only raise urgency: effective level = max(frozen, overlay) | V4 |
| S029 | `docs/CURRENT_PROGRAM_STATE.md` | engineering frozen at v2 Phase C; next product phase locked until both paper tags exist; future-architecture documentation is allowed; estimator, energy and other domains forbidden; cross-system exception allows adapters that read frozen outputs | V4 |
| S030 | `RESEARCH_STATE.md` | v1 in one paragraph; INVENTION_GATE CLOSED (textbook CUSUM satisfied every hard constraint) | V4 |
| S031 | `research/csia_novelty_audit/CSIA_NOVELTY_VERIFICATION.md` | UNSUPPORTED overloads three situations the literature keeps apart | V4 |
| S032 | `research/csia_model_inadequacy/NOVELTY_CLAIM_MATRIX.csv` (MI-C15) | localization is per symptom; the all-refuted state matches "no consistent diagnosis" | V4 |
| S033 | `research/csia_dx/CSIA_DX_REVIEW.md` | CSIA_DX_PIVOT; the decisive comparison for any diagnosability feature is against active diagnosis | V4 |
| S034 | `research/closed_loop_evidence_gap/TOP_GAPS.md` and `PROBLEM_LANDSCAPE.md` (L063-L068) | CLOSED_LOOP_EVIDENCE_ENGINEERING_ONLY; fielded reset and lane-switch provenance; ArduCopter vibration-compensation clearing; PX4 imbalance filter kept across a sensor switch | V4 |
| S035 | `research/g02_capability_margin/G02_DEEP_AUDIT.md` | G02_ENGINEERING_ONLY: a capability margin belongs in the flight stack | V4 |
| S036 | `research/autonomous_assurance_gap_search/TOP_THREE_GAPS.md` | the earlier gap search (G02, G07 runtime-assurance recovery assumption, G08 navigation integrity) | V4 |
| S037 | `tests/test_v2_framework.py` lines 251-268 | the test encodes UNIQUE as "one adverse candidate plus a NOMINAL record from another domain" | V4 |
| S038 | `engineering/v2/V2_CHATGPT_REVIEW_REPORT.md` §12 | the v2 review describes the UNIQUE discriminator as "a NOMINAL record from another domain" | V4 |
| S039 | `csia/evidence/validity_monitor.py` | VALIDITY_SUPPORTED, UNCERTAIN, VIOLATED; fails closed | V4 |
| S040 | `docs/research/LATENCY_PATH_ANALYSIS.md` | timestamps t0 onward, each allowed to be undefined | V4 |
| S041 | `forge/README_FUTURE.md` | FORGE is documentation only; import SysML v2, AADL, EMV2 and CycloneDX rather than invent a language | V4 |
| S042 | `csia_mission/forge_seed.py` | FORGE-SEED dependency compiler; cycles are compile errors | V4 |
| S043 | `csia_evidence/__init__.py`; `docs/architecture/EVIDENCE_BASE_LAYER.md` | ingestion, intent and corpus records; "nothing in this package promotes anything" | V4 |
| S044 | executed probe of `csia/v2` in this review (read-only; no file written) | (a) one adverse POWER record plus one unrelated NOMINAL COMPUTE record gives **UNIQUE**; without it, AMBIGUOUS. (b) a predicate that raises returns None. (c) "all refuted" and "one unconfirmed survivor" both give UNSUPPORTED | V4 |
| S045 | `engineering/v2/V2_PHASEC_FREEZE.md`; `tests/test_phase_c_freeze.py` | Phase C freezes eight artifact hashes and the recorded commit | V4 |
| S046 | `docs/product/CSIA_READINESS.md` (via `CURRENT_PROGRAM_STATE.md`) | maturity M2, "simulation/research prototype, not flight software" | V4 |

## 2. External sources

| id | source | what it establishes here | level |
|---|---|---|---|
| S050 | AUTOSAR Classic Platform, Specification of Diagnostic Event Manager (R20-11, R22-11) | enable conditions suspend monitoring under stated conditions; storage conditions suppress fault storage (e.g., no signal-timeout faults while a bus fault is active); operation cycles; debouncing; aging and healing; event combination | V0 SC |
| S051 | ISO 14229-1 DTC status byte (via S050 summaries) | "test not completed this operation cycle", "test failed", "confirmed" and related bits | V0 SS |
| S052 | OBD-II readiness monitors | enable criteria (temperature, load, speed, timing) before a test counts; continuous and non-continuous monitors; "ready" = test completed | V0 SC |
| S053 | ARINC 429 Sign/Status Matrix | Normal Operation, Functional Test, Failure Warning, and No Computed Data (missing or not meaningful for a reason other than failure, such as the function being off) | V0 SC |
| S054 | MAVLink `common.xml`, message `SYS_STATUS` (mavlink/mavlink master, sha256 `44a89c43069cc70d1f4cd6956835b1f3f6d4e42a6c8ba4d01c43a8ae7c35e6a6`, lines 5537-5545) | separate `present`, `enabled` and `health` bitmaps per sensor and controller; explicit invalid encodings (`voltage_battery` UINT16_MAX, `current_battery` -1) | V4 |
| S055 | PX4 `msg/EstimatorStatus.msg` (main, sha256 `dfef1210ff72fea4e37edbf493cce441825048eda460992d981813aa2cd113ea`) and `msg/EstimatorStatusFlags.msg` (sha256 `b48af525077636459d2cc9d5a9a249da1129f4e861c0206581d6df8545df075a`) | `timestamp_sample` (line 2); GNSS check flags including SPOOFED and JAMMED (lines 6-19); `control_mode_flags` such as CS_IN_AIR and CS_MAG_FAULT (lines 21-44); `filter_fault_flags` (line 55); low-pass-filtered innovation test ratios (lines 78-84); `solution_status_flags` "valid for flight control use" (line 86); reset counts (lines 100-104); `accel_device_id` and `gyro_device_id` (lines 115-116); health and timeout flags (lines 121-122) | V4 |
| S056 | PX4 `VehicleLocalPosition.msg` and `EKF2Selector.cpp` (hashes in `research/closed_loop_evidence_gap/SEARCH_LOG.md` §2) | reset deltas and counters for every consumer; a lane switch republishes the sensor selection and becomes a reset event | V4 |
| S057 | ArduPilot `AP_NavEKF3.cpp` and `ArduCopter/ekf_check.cpp` (hashes as in S056) | lane-switch reset data; 5 s hold-off between switches; monitor escalation requests a yaw reset, then a lane switch; vibration-compensation clearing | V4 |
| S058 | ISO 13374-1/-2 and MIMOSA OSA-CBM | six blocks: data acquisition, data manipulation, state detection, health assessment, prognostic assessment, advisory generation | V0 SC |
| S059 | Julier and Uhlmann, covariance intersection (1997) | consistent fusion of estimates with unknown correlation, conservatively | V0 SC |
| S060 | Denœux, "Conjunctive and disjunctive combination of belief functions induced by nondistinct bodies of evidence", Artificial Intelligence, 2008 | the cautious rule is idempotent; Dempster's rule assumes distinct (independent) bodies of evidence | V0 SC |
| S061 | de Kleer, assumption-based TMS (1986); de Kleer and Williams, GDE (1987) | each derived datum carries the assumption sets it depends on; conflicts (nogoods) are computed from those labels | V0 SC |
| S062 | Zadeh's criticism of Dempster's rule; conflict measures | normalising away conflict produces confident minority conclusions; measure conflict before combining | V0 SC |
| S063 | Benveniste et al., "Contracts for system design", Foundations and Trends in EDA 12(2-3), 2018; Pacti (ACM TCPS) | assume-guarantee contracts for composition and runtime assumptions | V0 SC |
| S064 | NASA sensor data qualification (Ares I FDDR; SDQS; NTRS 20070001482, 20080033120) | qualify sensor data first so that decisions rest on good data; limit, rate and analytical-redundancy checks | V0 SC |
| S065 | W3C PROV-DM and PROV-O | Entity, Activity, Agent; used, wasGeneratedBy, wasDerivedFrom | V0 SC |
| S066 | avionics redundancy management (mid-value select, cross-channel data link, miscompare monitors) | disagreement between redundant channels is detected and managed, not averaged blindly | V0 SC |
| S067 | Cimatti et al., "Assumption-based runtime verification" (FMSD 2023); "Monitorability under assumptions"; symbolic RV under uncertainties (arXiv 2207.05678) | monitors whose verdicts are conditioned on stated assumptions; the monitor is itself safety-critical | V0 SC |
| S068 | D-matrix / TEAMS dependency modelling; D-matrix diagnostic reasoners | failure-mode × test dependency matrices and reasoners that use them | V0 SC |
| S069 | Fault Diagnosis Toolbox (Frisk, Krysander, Jung); PyPI `faultdiagnosistoolbox` 0.12.5 (metadata read from pypi.org) | structural analysis, isolability and residual code generation; available as a Python package | V4 (PyPI metadata); V0 (capabilities) |
| S070 | Sun, Kadota, Talak and Modiano, "Age of Information" (2019) | AoI = time since the freshest received update was generated | V0 SC |
| S071 | real-time database temporal consistency (Ramamritham, 1993, and later work) | absolute validity interval (age under a bound) and relative consistency (ages of jointly used data within a bound) | V0 SC |
| S072 | s-FEAST (Science Robotics 2024) and arXiv 2606.19590 (see `research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` L008, L009) | safe active fault diagnosis exists; readme read at V4 | V0; V4 (readme) |
| S073 | ARAIM protection levels after exclusion (L040 in the closed-loop package) | integrity after an estimator exclusion is bounded analytically | V0 SC |
| S074 | ModelPlex; NASA FRET, Ogma and Copilot (L035, L037 in the closed-loop package) | action-conditioned runtime monitors; mode-scoped requirements that generate monitors | V0 SC |
| S075 | run time assurance and Simplex (L032 in the closed-loop package) | the safety layer that decides what remains safe | V0 SC |

## 3. Search log for this review

Queries are recorded verbatim. External sources found by the earlier packages
are reused through their ids there rather than searched again.

| # | exact query | kept |
|---|---|---|
| AQ1 | `AUTOSAR DEM enable conditions storage conditions operation cycle monitor status testNotCompletedThisOperationCycle aging healing debouncing` | S050, S051 |
| AQ2 | `OBD-II readiness monitors enable criteria monitor completion conditions diagnostic executive` | S052 |
| AQ3 | `ARINC 429 sign status matrix SSM normal operation no computed data failure warning functional test data validity` | S053 |
| AQ4 | `MAVLink SYS_STATUS onboard_control_sensors_present enabled health bitmask MAV_SYS_STATUS_SENSOR` | S054 (then read at V4) |
| AQ5 | `ISO 13374 OSA-CBM data acquisition data manipulation state detection health assessment prognostics advisory generation architecture` | S058 |
| AQ6 | `covariance intersection Julier Uhlmann unknown correlation data incest decentralized fusion double counting` | S059 |
| AQ7 | `Denoeux cautious conjunctive rule non-distinct bodies of evidence idempotent belief functions dependent evidence` | S060 |
| AQ8 | `assumption-based truth maintenance system de Kleer 1986 labels environments dependencies GDE conflict sets` | S061 |
| AQ9 | `Zadeh paradox Dempster-Shafer high conflict mass on empty set conflict measure evidence disagreement sources unreliable` | S062 |
| AQ10 | `contracts for system design assume-guarantee Benveniste runtime monitoring of assumptions contract-based design cyber-physical` | S063 |
| AQ11 | `NASA sensor data qualification sensor validation before fault diagnosis integrated system health management Ares sensor data validation` | S064 |
| AQ12 | `W3C PROV data model entity activity agent wasDerivedFrom provenance lightweight embedded` | S065 |
| AQ13 | `avionics cross-channel monitoring voting mid-value select sensor disagreement monitor miscompare triplex redundancy management` | S066 |
| AQ14 | `monitoring the monitor runtime verification monitor assumptions trustworthiness of runtime monitors partial observability monitor soundness sampling` | S067 |
| AQ15 | `D-matrix dependency matrix diagnostic reasoner TEAMS failure modes tests IVHM Honeywell diagnostic model fault signature matrix` | S068 |
| AQ16 | `Fault Diagnosis Toolbox Frisk Krysander Jung structural analysis residual generation isolability open source` | S069 |
| AQ17 | `age of information freshness metric status update time-to-live data expiration real-time systems temporal validity interval real-time databases` | S070 |
| AQ18 | `real-time database temporal consistency absolute validity interval relative consistency Ramamritham sensor data freshness` | S071 |
| AQ19 | `PX4 estimator_status_flags innovation test ratio cs_ flags fault flags documentation estimator health reporting uORB` | S055 (then read at V4) |

**Access.** Only raw.githubusercontent.com and pypi.org were reachable. The
V4 fetches were:

- MAVLink `common.xml` (S054);
- PX4 `EstimatorStatus.msg` and `EstimatorStatusFlags.msg` (S055);
- the PyPI JSON for `faultdiagnosistoolbox` (S069).
