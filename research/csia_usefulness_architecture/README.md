# CSIA usefulness architecture review

**Status: DESIGN AND AUDIT ONLY.** 2026-09-29.

- **Nothing implemented.** No CSIA code was changed. No experiment was run.
  No sealed artifact, preregistration, manifest, failure-ledger entry or
  earlier audit was modified.
- **Governance.** The work is documentation of future architecture, which
  `docs/CURRENT_PROGRAM_STATE.md` allows while engineering is frozen at v2
  Phase C. Implementing any of it needs Gate 0
  (`13_MIGRATION_AND_VALIDATION.md` §4).
- **Objective.** Make the current CSIA as useful, reliable, modular and
  evidence-aware as possible. **Usefulness over novelty; reuse over
  reimplementation.**

## The answer in one paragraph

CSIA's pipeline is missing one stage. It never checks whether a piece of
evidence is still **admissible**: whether the conditions that made it
meaningful still hold. It uses whatever it is handed for the current tick.

The only wrong attributions in the program's confirmatory result are the
55/55 of XSYS-001's preregistered negative control. That control deliberately
read the dynamics witness outside its validity window. In the valid
configurations it was the experiment pipeline, not CSIA, that imposed the
windows.

The recommended target is:

- an **overlay** around the frozen v2 core that adds evidence contracts, an
  admissibility check, a minimal context model, lifecycle and targeted
  invalidation;
- **reusing** automotive and avionics diagnostic practice (DEM enable and
  storage conditions, ARINC 429 No Computed Data) and autopilot-published
  status (PX4 reset counters and device ids);
- **repairing** two verdict defects in frozen v2: UNSUPPORTED is overloaded,
  and attribution UNIQUE can be licensed by an unrelated record, which this
  review demonstrated by probe;
- **keeping** set elimination, the function graph and the ledger.

The first product surface is **off-board**: a configuration-change evidence
analyzer for SITL, HIL and integration-test logs. Onboard comes only after
the HIL and flight levels.

## Files, by phase

| phase(s) | file |
|---|---|
| 1 current system audit | `01_CURRENT_SYSTEM_AUDIT.md` |
| 2 failure modes of CSIA itself | `02_CSIA_FMEA.md`, `CSIA_FMEA.csv` (33 failure modes) |
| 3 evidence as a first-class object; 4 admissibility; 12 assumption contracts; 13 lifecycle | `03_EVIDENCE_ADMISSIBILITY.md` |
| 5 configuration transitions; 27 context model; 28 invalidation engine | `04_CONFIGURATION_TRANSITIONS.md`, `TRANSITION_MATRIX.csv` (28 transitions) |
| 6 provenance graph; 7 correlated evidence; 29 double-counting policy | `05_PROVENANCE_AND_DEPENDENCE.md` |
| 8 monitor registry; 9 build vs reuse; 11 monitor the monitors; 14 method selection; 31 producer API; 32 reference adapters | `06_PRODUCERS_REGISTRY_AND_ADAPTERS.md` |
| 10 conflict; 30 conflict semantics and verdict migration | `07_CONFLICT_SEMANTICS.md` |
| 15 performance; 16 safety boundary; 37 FORGE boundary; 45 performance budget; 46 security and robustness | `08_PERFORMANCE_SAFETY_BOUNDARY.md` |
| 17 downstream output; 18 use cases; 36 assurance state; 38 product value | `09_DOWNSTREAM_AND_PRODUCT.md` |
| 21 keep / replace / add / remove | `10_KEEP_REPLACE_TABLE.md`, `ARCHITECTURE_DECISIONS.csv` (34 mechanisms) |
| 22 target role; 23 non-goals; 50 what not to build | `11_TARGET_ROLE_AND_NON_GOALS.md` |
| 24 target architecture; 25 EvidenceRecord v2; 26 evidence contract; 33 hypothesis engine; 34 attribution; 35 certificate vs trace | `12_TARGET_ARCHITECTURE.md`, `EVIDENCE_RECORD_V2_FIELDS.csv` (22 fields) |
| 39 migration; 40 backward compatibility; 41 validation ladder; 53 decision gates | `13_MIGRATION_AND_VALIDATION.md` |
| 42 first experiment; 43 baselines; 44 success metrics | `14_FIRST_EXPERIMENT.md` |
| 19 new directions; 20 prioritisation; 47 research vs engineering; 48 roadmap; 49 top five | `15_IMPROVEMENTS_AND_ROADMAP.md`, `IMPROVEMENT_SCORES.csv` (16 improvements) |
| 51 implementation specification; 52 repository plan | `16_TOP_FIVE_IMPLEMENTATION_SPEC.md` |
| 54 final architecture review | `17_ARCHITECTURE_RED_TEAM.md` |
| sources and search log | `SOURCES.md` |

## Output choices made because the brief was cut off

The brief arrived in two parts. The second ended in the middle of Phase 54,
at "Can this run on H743-class hardware". It therefore did not state:

- an output folder;
- a file list;
- a decision format;
- a final-report format.

The following choices were made and can be changed cheaply.

1. **One folder, `research/csia_usefulness_architecture/`.** This follows the
   repository's convention for multi-file research packages. Future
   architecture is also allowed under `docs/`. If the owner prefers
   `docs/architecture/`, the move is mechanical.
2. **Files grouped by related phases, not one file per phase.** Every phase
   is mapped in the table above. The phases' own tables are CSVs where they
   are large.
3. **No decision token was invented.** The package ends with a
   recommendation rather than a verdict keyword.
4. **The Phase 54 questions received are all answered.** Six further
   red-team questions are added and marked as added.
5. **A guard test for honesty checks** (`tests/test_csia_usefulness_architecture.py`),
   as for every earlier package.

## Key numbers

| item | value |
|---|---|
| mechanisms assessed (Phase 21) | 34: 10 KEEP, 6 REFACTOR, 9 GENERALIZE, 7 ADD, 1 REPLACE_WITH_EXISTING_METHOD, 1 DEPRECATE, 0 REMOVE |
| CSIA failure modes | 33 (FM-01 to FM-18 from the brief; FM-19 to FM-33 found in the audit) |
| evidence-record fields | 22: 10 required, 3 optional, 5 derived, 4 audit-only |
| improvements scored | 16: 12 ENGINEERING, 2 EXPERIMENTAL, 2 RESEARCH_PENDING_PRIOR_ART, 0 RESEARCH |
| top five | I-01 admissibility layer (42/50); I-03 verdict repair (42); I-04 producer health (41); I-08 decision trace (40); I-05 registry and adapters (38) |
| first product surface | configuration-change evidence analyzer (surfaces C and F, 31/40 each) |
| first experiment | XSYS-002-ADM: compensation onset with rate-loop gains varied, against a fixed window, an oracle per-gain window, and a command-conditioned plant residual |
| frozen-code findings | 1 correctness defect (attribution UNIQUE licensed by an unrelated nominal record, S044a) and 1 reporting gap (a predicate error is reported as not measurable, fail-safe but invisible, S044b). Recorded in this package, not fixed, because of the freeze |

**Recommendation:** proceed to Gate A review of this package. Implementation
is not authorised by this document.
