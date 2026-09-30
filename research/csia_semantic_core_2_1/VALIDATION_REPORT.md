# Validation of Semantic Core 2.1 (Phases A, C, D, E and F)

**2026-09-30.** Numbers come from `SEMANTIC_CORE_2_1_RESULTS.json` and
`PHASE_A_CHARACTERIZATION_LOCK.json`. Tests are in
`tests/test_semantic_core_2_1.py`.

## Phase A: characterization lock

This was done before any successor code existed, at HEAD `d87834c`.

| check | result |
|---|---|
| `tests/test_csia_semantic_correctness.py` | 12 of 12 pass |
| the audit's R section, re-executed against frozen v2 | identical to the committed result. Canonical SHA-256 `826ac475…3c4ca` both times |
| targeted defects reproduce | R1, R6, R7, R8B, R8E, R8G, R9, R9B, R17: **all 9** |
| frozen reasoning files | `attribution.py`, `localization.py`, `signatures.py` and `evidence.py` are byte-identical to the Phase C freeze `50c5d35`; their hashes are locked |
| audit results file | `semantic_probe_results.json` SHA-256 `aa856577…6a9b0` |

The baseline matched the audit, so implementation went ahead.

## Phase C: property and regression tests

`tests/test_semantic_core_2_1.py` has 50 tests (at this commit) and runs in about 16 s.

**Guards:**
- the frozen files match the lock;
- nothing in `csia/` imports the successor;
- in a fresh interpreter the frozen engine is still the default and never
  loads 2.1;
- 2.1 calls the frozen `localize()` itself.

**Identity:** with every correction off, the 2.0.0 view equals frozen v2 on
**2,640 of 2,640** ticks.

**The Phase A defects under 2.1:**

| case | 2.0.0 | 2.1 |
|---|---|---|
| R1: an unrelated NOMINAL record | UNIQUE | AMBIGUOUS, `DECLARED_ALTERNATIVE_NOT_AFFIRMATIVELY_NOMINAL` |
| R4: control, alternatives NOMINAL | UNIQUE | UNIQUE, with the relevant discriminators named |
| R2, R3, R8G: an alternative that did not look | UNIQUE | AMBIGUOUS |
| R6: disagreeing records | the order decides | the same in both orders; the conflict is listed |
| R7: exact duplicate | a multi-sensor symptom from one source | counts once |
| R8B: link UNAVAILABLE | the true cause is rejected | not rejected; `CHANNEL_LINK_NOMINAL` is in `evidence_unavailable` |
| R8E: process telemetry UNAVAILABLE | SUPPORTED processing_delay | AMBIGUOUS, process_stall kept open |
| R17: unreported shared nodes | SUPPORTED independent_faults | not supported |
| R9, R10: raise or non-bool | silent | `PREDICATE_FAULT`, with predicate, evaluated id, subject, class and hypotheses |
| R9B: a raising refuter | SUPPORTED, silently | SUPPORTED **and** `PREDICATE_FAULT`. The verdict rule is 2.0.0's, because G5 is not approved |
| a missing predicate id | `KeyError` mid-tick | `PredicateTableError` before any tick |

**The audit's properties** (`research/csia_semantic_correctness/SEMANTIC_PROPERTY_MATRIX.csv`):

| property | test | form |
|---|---|---|
| P1, P7 | irrelevant addition; no candidate lost | exhaustive, 1,320 cases, with the audit's definitions |
| P2 | removal of a record outside the declared scope | property-based |
| P3 | container order: reverse plus seeded shuffles; decisions **and** traces | property-based |
| P4, P15 | a duplicate of one record, and of the whole set; decisions and traces | property-based |
| P5 | a fault injected into every one of the 26 predicates on every final tick: reported in every evaluation, and deciding nothing a None return would not | exhaustive |
| P6, P12 | one record UNAVAILABLE: every measured predicate value equals both completions; UNIQUE never stands on an unknown alternative | property-based, 120 examples |
| P8 | deterministic replay | direct |
| P9 | UNIQUE never contradicts its own tick | all 2,640 ticks |
| P10, P11, P13 | trace equals values; outcome never UNSUPPORTED; implicated split is a partition; confirm-and-refute complete | all final ticks |
| P14 | the elimination core is the frozen function | identity |
| P19 | every UNIQUE has every declared alternative NOMINAL, and a cross-domain discriminator | every 5th tick |
| P16, P17, P18, P20 | deferred | pinned, so they cannot grow silently |

**The property tests are not vacuous.** Run with every correction off,
P1, P2, P4 and P6 all fail. Hypothesis is derandomized, has no deadline and
is bounded to 60–120 examples.

## Phase D: small-state enumeration and properties, frozen v2 against 2.1

**Method.** The audit's own probe was re-run with 2.1 in the successor slot:
its `shadow`, `shadow_attribute` and `shadow_predicates` were rebound in
memory. The probe file is unchanged.

**Result.** Sections E, N, P, SH and X are **identical** to the audit's
measurements of its shadow successor. R differs in one field only: 2.1
records `evaluated_as` beside each fault (`AUDIT.R11A_values`).

| measure | frozen v2 | 2.1 | correction | class |
|---|---|---|---|---|
| N2: irrelevant NOMINAL creates UNIQUE | 6 | 0 | C1 | FIXED |
| N2: UNIQUE configurations of 125 | 21 | 4 (each with its declared alternative NOMINAL) | C1 | FIXED |
| N3: unknown record refutes / SUPPORTED on unknown | 1,208 / 211 | 0 / 0 | C2 | FIXED |
| N4: the same | 486 / 38 | 0 / 0 | C2 | FIXED |
| N5: irrelevant evidence changes a POSITION result | 94 | 0 | C3 | FIXED |
| N6: unreported shared node refutes / confirms / supports | 224 / 80 / 176 | 0 / 0 / 0 | C2 | FIXED |
| P1: another subject's localization changes | 142 | 0 | C3 | FIXED |
| P2: irrelevant removal decides / relevance unknown | 6 / 17 | 0 / 0 | C3 | FIXED |
| P4: duplicate changes a decision | 3 | 0 | C6 | FIXED |
| P5: injected faults not visible | 259 | 0 | C4 | FIXED |
| P6: Kleene violations | 382 | 0 | C2 | FIXED |
| P9: UNIQUE contradicting its localization | 281 | 0 | F2 | FIXED |
| P12: inconsistent predicates | 15 | 0 | C2 | FIXED |
| P16: symptom on an ELIGIBLE function | 838 | 168 | C3 | INTENTIONALLY_DEFERRED (profile gap G-3) |
| N1 monotonicity; N2/N3/N4 order and duplicate; N2 UNAVAILABLE creates UNIQUE; P3 corpus; P7 | 0 | 0 | — | NOT_APPLICABLE (no violation in either) |
| P17, P18, P20, R9B verdict | — | — | — | INTENTIONALLY_DEFERRED |

**Totals:** 18 FIXED, 10 NOT_APPLICABLE, 5 INTENTIONALLY_DEFERRED,
**0 STILL_PRESENT**.

## Phase E: historical differential replay (44 scenarios, 2,640 ticks)

| | count |
|---|---|
| ticks changed | 945 |
| localization ticks changed | 664 (audit: 664) |
| attribution ticks changed | 362 (audit, F2 alone: 281; with C3: 362) |
| decision units changed | 1,275 |
| unexpected | **0** |
| more certain | **0** |
| final-tick scenarios changed | 23 |

**How the rule for each change was found.** Each changed unit is attributed
to the correction whose single-switch run reproduces it. Where no single
switch does, the pair C3 and F2 is tested. The result is C3 913, F2 281 and
C3+F2 81, with nothing unattributed.

**Root-cause clusters** (`E.clusters`, one row per cluster):

| units | rule | what changed | assessment |
|---|---|---|---|
| 126 + 63 | C3 | POSITION_UNAVAILABLE no longer raised when only components serving no navigation function raised it (MS_B1, NETWORK_LATENCY); the function graph calls the function ELIGIBLE | consistent with the function graph (a fix) |
| 397 + 84 | C3 | POSITION_UNAVAILABLE on COARSE_NAVIGATION no longer raised; the responsible components serve the sibling navigation functions, and nothing is declared for this one (G-1) | decided by a profile gap |
| 123 | C3 | OUTPUT_MISSING on state_estimator goes from SUPPORTED to AMBIGUOUS: no input link is declared (G-2) | weakened by a profile gap |
| 120 | C3 | POSITION_UNAVAILABLE on COARSE_NAVIGATION goes from SUPPORTED to AMBIGUOUS in MS_D1 and SHARED_RAIL: nothing is declared to serve it (G-1) | weakened by a profile gap |
| 197 | F2 | UNIQUE to AMBIGUOUS; the candidate names the true cause's domain | right UNIQUE weakened |
| 84 | F2 | UNIQUE to AMBIGUOUS in MS_B5 and MS_TS_B5 | **wrong UNIQUE corrected** |
| 81 | C3+F2 | UNIQUE to AMBIGUOUS in PROCESS_STALL and MS_D2, via the G-2 gap | right UNIQUE weakened |

**Receipts.** `PHASE_E_CHANGE_RECEIPTS.jsonl` has one line per changed tick,
945 in all. Each receipt carries:
- scenario and tick;
- old and new localization, old and new attribution;
- the rule;
- the evidence responsible: changed predicate values with their
  out-of-scope records and scope gaps, or the adverse out-of-scope records
  that raised a removed symptom, or the localization disagreement that
  withheld UNIQUE;
- expected yes or no, and the reason;
- `HISTORICAL_RESULT_MODIFIED: NO`.

In the brief's receipt format, the MS_B5 final tick reads:

```
OLD:      UNIQUE ACTUATION/motor_0
NEW:      AMBIGUOUS {ACTUATION/motor_0}; the same tick's localizations
          COMMAND_NO_RESPONSE and HIGH_CURRENT_LOW_RPM on motor_0 still
          retain SENSOR/response_sensor
REASON:   UNIQUE_WITHHELD: SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN
RULE:     F2
EXPECTED: YES
HISTORICAL RESULT MODIFIED: NO
```

**Why the sensor is not added as a candidate.** An attribution candidate is
a component with adverse evidence of its own. F2 withholds UNIQUE; it does
not add, remove or rename candidates. The sensor alternative is therefore
carried as the localization disagreement, not as an invented candidate.

## Phase F: XSYS-001 hard gate

| check | result |
|---|---|
| Stage-1 output against its seal | match (`ccbc10f5…e8e3`) |
| `CONFIRMATORY_RESULT_MANIFEST.json`: 225 file hashes, its own `.sha256`, and the XSYS-001, A1 and A2 freeze manifests | all valid |
| frozen replay against the sealed verdicts | 0 differences over 3,872 slots |
| 2.1 against sealed: decisions / full 2.0.0 documents | **0 / 0** |
| scored outcomes: against the sealed verdicts / against the recorded RESULTS.json | **0 / 0** |
| primary, recomputed with `stage2_score`'s own functions | 55/55, n_eff 11, LB 0.7615958096191473, WRONG 0, **SUPPORTED**; identical to the record |
| predicate faults, duplicates, conflicts | 0 |

**XSYS_HARD_GATE: PASS.** Nothing was written to any XSYS-001 path. The
replay is separate and lives only in `SEMANTIC_CORE_2_1_RESULTS.json`.

## Protected files

22 protected files were hashed before and after the differential run and
were unchanged. They cover:
- the frozen reasoning code;
- the Phase C records and runner;
- the sealed XSYS-001 files and pipeline;
- the audit probe and its results.
