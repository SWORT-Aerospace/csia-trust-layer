# CSIA 2.0 and CSIA 2.1: the historical semantics and the successor (Phase L)

**2026-09-30.** Figures come from `SEMANTIC_CORE_2_1_RESULTS.json`, produced
by `semantic_core_2_1_differential.py`, unless another source is named.

## 1. The two versions

| | CSIA 2.0.0 | CSIA 2.1.0 |
|---|---|---|
| status | **historical, frozen**. The default runtime | **corrected successor**. Not the default; recommended for shadow mode only |
| code | `csia/v2` (Phase C freeze `50c5d35`, byte-identical since) | `csia_semantic_core/`, which wraps the frozen `localize()`, `attribute()`, `EvidenceIndex` and predicate table |
| schema | the `SystemAssurance.to_dict()` documents | `csia.semantic_core/2.1.0` (`TickResult.to_dict()`) |
| used by | every recorded Phase C result, XSYS-001, the API, the ledgers | nothing in production; the tests and the research harness here |

**How to move between them:**

- **2.1 in the 2.0.0 schema.** `TickResult.to_v2_0_view()` renders any 2.1
  result that way.
- **Historical evidence under 2.1.** `reason_historical_tick()` evaluates a
  recorded 2.0.0 tick, either a `SystemAssurance` or its `to_dict()`
  document, and does not modify it.
- **Identity.** With every correction switched off (`Corrections.none()`),
  the 2.0.0 view equals frozen v2 exactly on all 2,640 shipped ticks.

## 2. What changed, and why

Each correction answers one confirmed finding of the semantic correctness
audit (`research/csia_semantic_correctness/FINDINGS.csv`).

| | defect in 2.0.0 | 2.1.0 rule | code |
|---|---|---|---|
| **C1** (SC-01) | any NOMINAL record from another domain licensed UNIQUE | UNIQUE also needs every **declared** alternative affirmatively NOMINAL, and a relevant discriminator from another domain. Declared alternatives are the dependency ancestors plus the relation implicates | `attribution.py` |
| **F2** (SC-02) | UNIQUE could contradict the same tick's localization of the candidate | UNIQUE is withheld while that localization keeps another domain's hypothesis | `attribution.py` |
| **C2** (SC-03, SC-04) | 18 predicates read "could not look" as "fine", and an unreported shared node as "not adverse" | strong-Kleene aggregation in exactly those 18 | `predicates.py` |
| **C3** (SC-05) | 5 function predicates and one detector read the whole tick | they read only components declared to serve the subject; if nothing is declared the value is None and the gap is recorded | `predicates.py` |
| **C4** (SC-06, SC-07) | a raising or non-bool predicate was silently "not measurable" | still not measurable for elimination, and **reported**: evaluation status PREDICATE_FAULT with predicate, evaluated id, subject, error class and hypotheses | `predicates.py`, `localization.py` |
| **C6** (SC-12, SC-13) | container order decided between disagreeing records, and an exact duplicate counted twice | duplicates count once; two different records for one key answer neither; the conflict is listed | `index.py` |
| **C5** (SC-09, SC-10, SC-11, SC-20) | UNSUPPORTED and `unsupported` carried several meanings | outcome NO_CONSISTENT_HYPOTHESIS or INSUFFICIENT_EVIDENCE (reason UNCONFIRMED_SURVIVOR or UNMODELLED); `implicated_nominal`, `implicated_unavailable`, `implicated_unobserved`, `implicated_other`; `components_not_observed` | labels only |
| **C7** (SC-16, SC-21) | silent confirm-and-refute; SUPPORTED over refuters that could not look | `confirmed_and_refuted`, `supported_with_unmeasured_refuters` | trace only |

**C1 and F2 only ever turn UNIQUE into AMBIGUOUS.** They never create a
UNIQUE, and they never add, remove or rename a candidate. **Neither C4 nor C6
reinstates or eliminates a hypothesis on its own.** C5 and C7 are verified
behaviour-neutral by the identity check.

**The four outcome states the brief requires**, in the repository's own
vocabulary:

| state | how 2.1 says it |
|---|---|
| no consistent hypothesis remains | outcome `NO_CONSISTENT_HYPOTHESIS` (2.0.0 view: UNSUPPORTED) |
| one hypothesis survives without confirmation | outcome `INSUFFICIENT_EVIDENCE`, reason `UNCONFIRMED_SURVIVOR` or `UNMODELLED` (2.0.0 view: UNSUPPORTED) |
| predicate evaluation failed | evaluation `PREDICATE_FAULT`, with `predicate_errors` |
| evidence unavailable | evaluation `EVIDENCE_UNAVAILABLE`, with `evidence_unavailable` (faulted ids excluded) |

The outcome and the evaluation status are separate fields, so a verdict is
never replaced by a fault.

## 3. What historical results remain valid

**Every recorded result remains a true record of 2.0.0.** No file was edited.

| record | under 2.1 replay |
|---|---|
| **XSYS-001 confirmatory primary** (55/55, LB 0.7616, SUPPORTED) | **unchanged**. All 3,872 sealed slots give identical decisions and identical full 2.0.0 documents; 0 scored-outcome differences; the primary recomputes to the same numbers (§5) |
| XSYS-001 secondary results, A1, A2 | unchanged. Every trial outcome is identical, so every statistic computed from outcomes is identical |
| **Phase C gate headline** (`CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`, qualifying sets A_STALE_OUTPUT and B_ACTUATOR_RESPONSE_BENCH) | **unchanged**, including every qualifying answer. Recomputed with the frozen `decision_gate` |
| Phase C A, B, B-bench and C matched-set rows | unchanged |
| the 2.0.0 compatibility tests | unchanged, and they still pass against frozen v2 |
| Paper I | not affected. It concerns the v1 attribution channel |

## 4. What historical secondary results differ under 2.1 replay

These are secondary results. The details and the per-change justification
are in `PHASE_C_GOVERNANCE_REPORT.md`.

- **Across the 44 scenarios at 60 ticks (2,640 ticks):**
  - 945 ticks change: 664 localization ticks and 362 attribution ticks;
  - 1,275 units change; 0 are unexpected and 0 are more certain;
  - one receipt per changed tick: `PHASE_E_CHANGE_RECEIPTS.jsonl`.
- **In `V2_SCENARIO_RESULTS.json`** (200 ticks, 19 scenarios): 4 of its 10
  recorded UNIQUE final verdicts become AMBIGUOUS:
  - ACTUATOR_NO_RESPONSE, CLOCK_DRIFT and STALLED_ACTUATOR, by F2;
  - PROCESS_STALL, by C3 and F2 together.

  In addition, 23 TS_STALLED ticks change. The review-report table repeats
  this artifact.
- **In `LOCALIZATION_RESULTS.csv`**, 4 D-set rows on COARSE_NAVIGATION change:
  - MS_D1 goes from SUPPORTED to AMBIGUOUS;
  - the MS_D2, MS_D3 and MS_D4 rows are no longer raised.

  `EVIDENCE_SUBSET_RESULTS.csv` changes on the same 4 rows. The D set was
  non-qualifying and stays non-qualifying.
- **Two wrong-cause UNIQUE verdicts are withheld:** MS_B5 and MS_TS_B5,
  whose true cause is the response sensor. Neither is recorded in any Phase C
  artifact. They exist only in replay (proposed ledger entry FL-060 corrects the audit's statement
  that they were recorded).

## 5. What XSYS-001 does under 2.1

| check | result |
|---|---|
| Stage-1 output hash against its seal | match |
| every hash in `CONFIRMATORY_RESULT_MANIFEST.json` (225 files), the manifest against its `.sha256`, and the XSYS-001, A1 and A2 freeze manifests | all valid |
| slots replayed through 2.1 | 3,872 |
| decision differences against the sealed Stage-1 verdicts | **0** |
| full 2.0.0-document differences | **0** |
| scored-outcome differences, against both the sealed verdicts and the recorded RESULTS.json | **0** |
| primary recomputed under 2.1 | 55 of 55 pairs resolved, n_eff 11, LB 0.7615958096191473, 0 WRONG, SUPPORTED |
| predicate faults, duplicates, conflicts | 0, 0, 0 |
| 2.1 outcome labels on the 880 detected slots | SUPPORTED 660, AMBIGUOUS 220 |

XSYS-001 used only `localize()`, with its own predicates. **C2 and C3 do not
apply to those predicates**: they replace only the shipped v2 predicate
objects, by identity. C1 and F2 act on attribution, which XSYS-001 never
called. C4 and C6 found nothing to report. **XSYS HARD GATE: PASS.**

## 6. What remains deferred

| item | why it is not here |
|---|---|
| G5: withholding SUPPORTED over a faulted refuter (R9B) | not approved. The fault is observable, and the verdict rule is 2.0.0's |
| intake validation of malformed records (SC-08); detector and attribution exceptions (P17) | not approved; they still raise as in 2.0.0 |
| profile gaps G-1, G-2, G-3 (SC-18); P16 residual 168 | profile data, an owner decision; exposed, not fixed |
| correlated evidence from distinct detectors (SC-14, P18) | outside scope |
| rail source lookup C8 (SC-15, P20) | not approved |
| multi-fault attribution (SC-17) | a semantics change, not a defect fix |
| full evidence provenance, evidence contracts, configuration-aware invalidation, producer health, producer registry, monitor plugins, broad conflict architecture, FORGE | the architecture work; not authorized |
| the C runtime (`embedded/`) | does not implement 2.1 |

**One minimal local mechanism was needed.** C3 needs the set of components
declared to serve a subject. That set is computed from fields the records
already carry (`affected_functions`, `dependencies`) and nothing more. It is
not a provenance graph and not a producer registry.
