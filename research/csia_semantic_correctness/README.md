# CSIA semantic correctness audit

**Status: AUDIT, TEST DESIGN AND CORRECTION DESIGN ONLY.** 2026-09-29.

- **Frozen v2 is untouched.** No production CSIA code changed. The audited
  reasoning files are byte-identical to the Phase C freeze commit `50c5d35`.
- **Nothing sealed was modified.** That covers XSYS-001 files, A1, A2,
  manifests, hashes, earlier packages and FAILURE_LEDGER entries.
- **What was added.** Research documents, one research-only probe script with
  its results, and one guard test for this package.

## The answer

**Can current CSIA become more certain for the wrong reasons? Yes.**

**What the probe found.** `semantic_probe.py` executes frozen v2 on:

- minimal records;
- all 44 shipped scenarios (2,640 ticks);
- 10,113 exhaustively enumerated configurations;
- all 3,872 sealed XSYS-001 localization slots.

It found five independent S3 defects:

| | defect | minimal reproduction |
|---|---|---|
| SC-01 | **attribution UNIQUE is licensed by any NOMINAL record from another domain, relevant or not** | one VIOLATED rail gives AMBIGUOUS; adding one NOMINAL CPU record gives UNIQUE (R1). In every shipped scenario, a single adverse component was UNIQUE on 889 of 889 ticks |
| SC-02 | **UNIQUE contradicts the same tick's localization** (281 of 889 UNIQUE ticks) | shipped MS_B5_RESPONSE_SENSOR: true cause the RPM sensor; attribution UNIQUE ACTUATION/motor_0 with SENSOR "affirmatively excluded" by eight unrelated navigation sources |
| SC-03 | **"could not look" is read as "fine"** by 18 of 26 predicates (the four shared-node predicates among them are SC-04) | estimator telemetry missing during a true process stall gives **SUPPORTED processing_delay** ("running but slow") |
| SC-04 | **a declared shared node nobody reported is read as "not adverse"** | two sources sharing four unreported nodes give **SUPPORTED independent_faults** |
| SC-05 | **five predicates and one detector ignore their subject** | a late logger process gives SUPPORTED "estimator stale" on navigation functions the function graph calls ELIGIBLE |

**Also confirmed:**

| | finding | severity |
|---|---|---|
| SC-06 | a raising predicate is silently "not measurable". In 19 of 26 predicates the fault changes decisions, and in 9 cases it creates SUPPORTED | S2 |
| SC-12 | container order decides the answer when two records disagree | S2 |
| SC-13 | an exact duplicate adverse source record creates a multi-sensor symptom | S2 |
| SC-09, SC-10, SC-11, SC-20 | UNSUPPORTED and the `unsupported` field each carry two or three meanings, and the attribution verdict UNSUPPORTED is unreachable | S1 and S0 |

**Nothing downstream acts on these verdicts today, so no finding is S4.**

**XSYS-001 is unaffected.** It used only `localize()` with its own predicates,
which already treat missing evidence correctly. The replay reproduces every
sealed slot. No proposed correction changes any XSYS-001 decision or
outcome.

## Files, by the brief's parts

| part | file |
|---|---|
| 1 exact reproduction | `MINIMAL_REPRODUCTIONS.md` |
| 2 relevance; 3 irrelevant-evidence invariance; 4 removal; 7 correlated evidence | `ATTRIBUTION_RELEVANCE_AUDIT.md` |
| 5 order; 6 duplication | `MINIMAL_REPRODUCTIONS.md` (R6, R7), `SEMANTIC_PROPERTY_MATRIX.csv` (P3, P4) |
| 8 missing evidence | `MISSING_EVIDENCE_AUDIT.md` |
| 9 exception semantics | `EXCEPTION_SEMANTICS_AUDIT.md` |
| 10 UNSUPPORTED semantics | `UNSUPPORTED_TRUTH_TABLE.csv` |
| 11 localization versus attribution | `LOCALIZATION_ATTRIBUTION_MATRIX.csv` |
| 12 monotonicity; 13 metamorphic suite; 15 property-based strategy | `METAMORPHIC_TEST_PLAN.md`, `SEMANTIC_PROPERTY_MATRIX.csv` |
| 14 exhaustive small-state enumeration | `SMALL_STATE_ENUMERATION.md` |
| 16 XSYS-001 compatibility | `XSYS_001_COMPATIBILITY.md` |
| 17 existing test coverage | `EXISTING_TEST_COVERAGE.csv` |
| 18 severity | `FINDINGS.csv` |
| 19 minimal correction; 21 priority | `MINIMAL_CORRECTION_DESIGN.md` |
| 20 do not implement | this README; `MINIMAL_CORRECTION_DESIGN.md` §4 |
| 22 implementation gate | `IMPLEMENTATION_GATE.md` |
| the code-level map every file refers to | `CURRENT_SEMANTICS_MAP.md` |
| literature and search log | `SOURCES.md` |
| executable evidence | `semantic_probe.py`, `semantic_probe_results.json` |

**Two files beyond the 16 deliverables.** `CURRENT_SEMANTICS_MAP.md` is
deliverable 2. The extras are:

- `SOURCES.md`, the repository's convention for literature;
- the probe script and its output, which are the evidence.

## Reproducing

```
.venv/bin/python research/csia_semantic_correctness/semantic_probe.py
```

**What it does.**

- **Runtime.** About three minutes in CPython.
- **Output.** It writes `semantic_probe_results.json`. Output is
  deterministic: fixed seed, sorted iteration, no clock.
- **What it touches.** It only imports frozen v2 and reads sealed XSYS-001
  files. It writes nothing else.

**The SHADOW section is a measuring instrument for the proposed successor,
not the correction.** With every fix switched off it reproduces frozen v2 on
all 2,640 shipped ticks, with 0 mismatches. `tests/test_csia_semantic_correctness.py`:

- re-executes the record-level reproductions;
- checks that they still match the committed results, which pins current
  frozen behaviour as characterization;
- checks the package's own consistency.

## Key numbers

| item | value |
|---|---|
| semantic properties tested | **20** |
| failed by frozen v2 | **15**. Passed: candidate preservation, deterministic replay, trace consistency, monotone information, idempotence of attribution decisions |
| failed by the shadow successor | 4. One profile-data gap, one deferred record validation, correlation (deferred) and C8 (deferred) |
| findings | 21: **5 × S3**, 5 × S2, 9 × S1, 2 × S0 |
| highest severity confirmed | **S3**. Current impact is advisory; future downstream risk is S4 |
| shipped scenarios / ticks exercised | 44 / 2,640 |
| XSYS-001 sealed slots replayed identically | 3,872 / 3,872; 0 decision or outcome differences under any proposed fix |
| minimal correction | C1 relevance-gated discriminator; F2 localization-agreement gate; C2 Kleene aggregation; C3 subject scoping; C4 error transparency; C5 labels; C6 idempotence and same-key conflict; C7 trace entries |
| correction effect on shipped ticks | C1, C2, C4 and C6 change **0 of 2,640**. F2 changes 281 attribution ticks; C3 changes 664 localization ticks |

**Decision:** SEMANTICS_REQUIRES_GOVERNANCE_REVIEW

**What the decision means.**

- **The corrections are required, and they outrank the broader architecture.**
- **Why governance.** Two of them (F2, C3) disagree with recorded v2 Phase C
  results. Two (C1, F2) replace the v2 spec's definition of UNIQUE. Neither
  change touches XSYS-001.

The owner decisions are listed in `IMPLEMENTATION_GATE.md` §4. No correction
has been implemented.
