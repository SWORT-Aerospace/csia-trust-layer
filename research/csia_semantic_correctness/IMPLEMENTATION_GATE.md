# Implementation gate (Parts 21 and 22)

CSIA semantic correctness audit, 2026-09-29.

## 1. The question

Current CSIA can become more certain for the wrong reasons. Does it?
**Yes.** It does so in five independent ways, each rated S3
(`FINDINGS.csv`):

| finding | defect |
|---|---|
| SC-01 | UNIQUE licensed by an irrelevant NOMINAL record |
| SC-02 | UNIQUE that contradicts the same tick's localization. Includes a wrong UNIQUE on two shipped matched scenarios whose true cause is the response sensor |
| SC-03 | "could not look" read as "fine" by predicates. Includes a wrong SUPPORTED cause at engine level when estimator telemetry drops |
| SC-04 | a shared node nobody reported read as "not adverse". "Independent faults" becomes SUPPORTED |
| SC-05 | unrelated components creating symptoms and SUPPORTED causes on navigation functions, including in shipped scenario MS_B1 |

**Tally.** Of 20 semantic properties tested, frozen v2 fails 15.

**Why S3 and not S4.** Nothing downstream acts on these verdicts today:

- the API issues no command;
- FORGE production code is forbidden;
- XSYS-001 used only `localize()` with its own predicates.

The future downstream risk is S4 for SC-01 to SC-05.

## 2. The options

| option | rejected or chosen | reason |
|---|---|---|
| the semantics are clean and need no fix | rejected | 15 of 20 properties fail; five S3 findings are reproduced at record level and at engine level |
| a fix is required, but it need not precede the architecture | rejected | Part 21 puts correctness first. Two reasons it should also come first in practice: the architecture's adapter layer would route more producers through predicates that read UNAVAILABLE as healthy, and would create the same-key conflicts that make order matter |
| a fix is required before the architecture, with no governance question | rejected, **narrowly** | the fix *is* required before the architecture. But two of its parts change fundamental v2 semantics and reinterpret sealed historical records (section 3), which Part 22 reserves for governance |
| governance review | **chosen** | see below |

## 3. Why governance review, and not a plain go-ahead

Part 22 requires governance review if any proposed fix changes one of four
things. Here is what the minimal correction set does to each:

| trigger | does the minimal correction trigger it? | evidence |
|---|---|---|
| XSYS-001 primary result | **no**. Every correction is NO EFFECT or CHANGES INTERNAL TRACE ONLY; 3,872 of 3,872 sealed slots replay identically, with 0 decision or outcome differences under the shadow successor | `XSYS_001_COMPATIBILITY.md` |
| sealed historical interpretation | **yes, for F2 and C3** | F2 turns 7 recorded UNIQUE final verdicts into AMBIGUOUS. They are in `V2_SCENARIO_RESULTS.json` and the review-report tables, and include two where the recorded UNIQUE names the wrong cause. C3 changes the D-set rows of `LOCALIZATION_RESULTS.csv`. The Phase C gate headline (two qualifying sets) is **not** changed |
| major public claim | **no**. Paper I concerns the v1 attribution channel, not v2 attribution | `papers/csia_systems/main.tex`; `PAPER_I_SCOPE_GUARD.md` |
| fundamental v2 semantics | **yes, for C1 and F2** | they replace the definition of UNIQUE in `CROSS_DOMAIN_RELATION_SPEC.md` §2 ("a NOMINAL record from a different domain"). C2 also changes what the shipped predicates return under missing telemetry, though no recorded result depends on it |

**Decision:** SEMANTICS_REQUIRES_GOVERNANCE_REVIEW

**What this decision means.** The correction is required, and it outranks the
architecture. The governance question is **how** it is introduced relative to
the frozen record, not **whether** it is needed.

## 4. What governance needs to decide

| # | decision | recommendation | what depends on it |
|---|---|---|---|
| G1 | authorize a **post-freeze successor** (schema 2.1.0, overlay package, 2.0.0 compatibility view kept as the default), or wait for the freeze to lift | authorize the successor overlay. It touches no frozen file, and the shadow shows it reproduces 2.0.0 exactly when switched off | everything below |
| G2 | C1 with no declared alternative: AMBIGUOUS, or allow "vacuous UNIQUE" | AMBIGUOUS. No shipped tick is affected | C1 |
| G3 | accept that the successor disagrees with 7 recorded UNIQUE verdicts. Record the disagreement in a **new** erratum-style note beside the Phase C record; the record itself stays unedited | accept. Two of the seven are wrong causes; five are right answers without the evidence to call them unique | F2 |
| G4 | C3 (strict scoping) or C3′ (scope only where the profile declares serving components); and whether to correct profile gaps G-1, G-2 and G-3 (SC-18) as data | C3, plus the profile corrections. C3′ keeps the defect for undeclared subjects | C3 |
| G5 | whether a predicate error on a refuter of the supported hypothesis withholds SUPPORTED; and whether the successor's intake validates tuple fields | yes to both, as a second step after C4 | C4 extensions |
| G6 | FAILURE_LEDGER entries for SC-01 to SC-05 | the owner decides; **this package appends nothing** | — |
| G7 | whether the characterization tests and successor test twins join the suite | yes, labelled as characterization (`METAMORPHIC_TEST_PLAN.md` §2) | — |

## 5. Sequencing once governance has decided

| step | contents | condition |
|---|---|---|
| 1 | the successor overlay with **C1, C2, C4, C6** (correctness) and **C5, C7** (explainability). These change **no** recorded result: 0 of 2,640 shipped ticks for C1, C2, C4 and C6 | G1, G2 |
| 2 | **F2** and **C3** | G3, G4 |
| 3 | the architecture package's top five, starting with admissibility. C2 and C6 are its kernel | step 1 in place |

Deferred:

- C8 (rail source lookup, S1);
- correlated evidence (SC-14);
- multi-fault attribution (SC-17).

**Until step 1 exists, the broader architecture should not start.** Documents
and analysis remain permitted.
