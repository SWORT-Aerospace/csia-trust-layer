# Terminology crosswalk: CSIA terms and established terms

This crosswalk is part of the pre-result novelty audit (2026-09-27). Source
ids are listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.

**Why this file exists.** New vocabulary is not new science. Every CSIA term
below is mapped to the established term or terms a reviewer from FDI, the DX
community, IVHM, runtime verification, navigation integrity or safety
assurance would use. **CSIA papers should use the established term first and
give the CSIA name second, if at all.**

The "residual difference" column records what, if anything, the CSIA term
carries that the established term does not. Blank or "none" means the term is
a synonym.

## Evidence and relations

| CSIA term | established terms | where established | residual difference |
|---|---|---|---|
| cross-sensor validation, cross-sensor evidence | analytical redundancy; parity relations; sensor validation; plausibility check; residual generation | B04, B05, B06, B22, B90 | none |
| cross-system / cross-domain validation or evidence | analytical redundancy relations spanning subsystems; vehicle-level reasoning; cascaded-fault screening; multi-domain / integrated diagnosis | B09, B58, B59, B60 | none |
| evidence witness; physical witness; "physical consequence as an independent witness" | analytical redundancy relation; virtual sensor; consistency relation; control invariant; physical invariant; model-based residual | B05, B06, B92, B93 | none as a concept |
| `EvidenceRecord` (a verdict plus optional numbers) | residual with evaluation; symptom; test outcome; observation with status | B07, B63 | a packaging choice |
| three-valued predicate (True / False / not measurable) | Kleene three-valued logic; inconclusive verdict (LTL3); "no computed data" status; SEVA measurement status BLIND | B70, B89, `research/evidence_semantics/PRIOR_ART_MATRIX.md` | none |
| "absence of evidence is not health" | no-exoneration assumption; fail-safe default; stale data is not valid data | B30, `research/evidence_semantics/PRIOR_ART_MATRIX.md` | none |
| witness gate (a "nominal" witness only if the symptom predicts a detectable response) | exoneration conditioned on fault models (physical negation); detectability condition; test power | B30, B09 | a specific quantitative rule (2× threshold), not a concept |
| Dynamic Trust Graph; Trust Coefficient | sensor validity index; reliability weighting; consistency-based sensor trust; reputation | B22, B95, B96 | the Beta-recursion form is one implementation choice |
| W_DYN (early dynamics) | actuator-effectiveness / loss-of-effectiveness evidence from body rates; dynamic residual | B44, B48, B54 | none |
| W_CTRL (controller compensation) | control effort / manipulated-variable monitoring; motor-output saturation; closed-loop fault masking handled with controller-internal variables | B55, B99, B17 | none |
| W_RPM (local symptom) | ESC telemetry residual; commanded-versus-measured speed | B56, P09 | none |

## Time

| CSIA term | established terms | where established | residual difference |
|---|---|---|---|
| temporally valid evidence; temporal validity | transient versus steady-state analysis; activation window; mode- or context-dependent ARR; temporal model-based diagnosis | B32, B37, B40 | CSIA encodes it as a per-evidence **applicability** value (outside its window the predicate is None). See matrix C6 (CLOSE_PRIOR_ART) |
| "changing evidentiary value through a fault transient" | fault signature evolution; transient signatures; relative measurement orderings; progressive monitoring | B37, B38, B40 | none |
| T1 / T2 / T3 regions | transient window / settling / steady-state window | B37 | none |
| checkpoint C1 / C3 | decision epoch; evaluation instant | — | none |
| temporal evidence accumulation | sequential diagnosis; recursive hypothesis testing; dynamic Bayesian network; CUSUM / SPRT | B10, B11, B35 | CSIA's v2 has **less** of this than the prior art: two checkpoints (matrix C7) |

## Verdicts and ambiguity

| CSIA term | established terms | where established | residual difference |
|---|---|---|---|
| localization | fault isolation; diagnosis; candidate generation | B07, B28, B29 | none |
| hypothesis elimination; set elimination | consistency-based diagnosis; conflict-driven candidate generation; model invalidation | B28, B29, B72 | none |
| signature matrix | fault signature matrix; incidence matrix; D-matrix; coding set | B08, B40, B62 | three-valued entries, known in D-matrix practice (the "unknown" outcome) |
| AMBIGUOUS | ambiguity group; multiple minimal diagnoses; non-isolable fault set; set-valued diagnosis | B28, B62, B64, B72 | none |
| structural ambiguity; "Set B floor of two" | structural non-isolability; isolability class; fault isolation matrix entry | B09, B23, B25 | none |
| SUPPORTED / UNIQUE | isolated fault; single-fault diagnosis; unique minimal diagnosis **plus** abductive confirmation | B28, B31 | the requirement that survival alone is not enough is the consistency-plus-abduction combination described in B31. It is a stated rule, not a new logic |
| UNSUPPORTED (evidence eliminates every hypothesis) | no consistent diagnosis; model incompleteness; unmodelled or unknown fault; open-set | B28, B102 | none |
| NO_EVIDENCE (no symptom) | no detection; nominal | B07 | none |
| CONFLICT (named in the research direction; **not a verdict CSIA v2 defines**, since `csia/v2/attribution.py` has UNIQUE, AMBIGUOUS, UNSUPPORTED and NO_EVIDENCE only) | conflict set (in the DX sense, a different meaning); inconsistent evidence | B29 | **term collision**: in the DX community a "conflict" is a set of assumptions that cannot all hold. Evidence conflict in v2 surfaces as UNSUPPORTED. Any future verdict of this name must be defined against the DX meaning |
| WRONG (primary endpoint) | misdiagnosis; false isolation; incorrect diagnosis; violation of FDI correctness | B64, B71 | none |
| zero-WRONG requirement | FDI correctness requirement; guaranteed isolation / no false alarm under bounded uncertainty | B71, B72 | an **empirical** acceptance criterion rather than a synthesis property; see matrix C17 |
| common-cause retention | cascaded-fault screening; common-mode fault; root-cause consolidation | B58, P12 | none |
| resolving power; pair resolution rate | isolability; diagnostic resolution; isolation rate | B25, B64 | the "pair" is XSYS-001's design unit, not a new metric |

## Assurance and action

| CSIA term | established terms | where established | residual difference |
|---|---|---|---|
| certificate; `SupportCertificate` | distinguishing measurement; D-matrix row; diagnostic outcome record; integrity certificate | B29, B62, B63 | runtime packaging of the separating evidence (matrix C20, LIKELY_KNOWN) |
| certification (as a runtime step); certification latency | integrity availability; exclusion; time to isolation; time to alert | B87, B07 | naming a "certification" stage for root-cause attribution was not seen elsewhere; weak evidence (matrix C9) |
| evidence sufficiency | assurance claim point; confidence argument; sufficiency and appropriateness of evidence; integrity risk | B86, B87 | none as a concept |
| function eligibility; "which functions are still justified" | capability assessment; functional availability; degraded-mode management; conditional safety certificate | B84, `docs/mission/NOVELTY_CLASSIFICATION.md` | none as a concept |
| "the layer issues no command" | monitor-only (advisory) function; separation of monitoring from recovery | B81 | a design constraint, not a contribution |
| bounded runtime assurance; action constrained by justified state | runtime assurance; Simplex; safety filter; protection level against alert limit; safe diagnosability | B79, B80, B81, B87, B77 | **not implemented in CSIA** (matrix C19, UNSUPPORTED_NOVELTY_CLAIM) |
| hypothesis-dependent validity gating; self-occlusion | state-dependent observation; loss of observations; closed-loop fault masking; action-induced evidence loss | B103, B104, B105, B99, B56 | a measured instance on a deployed layer (matrix C15) |

## Experimental design

| CSIA term | established terms | where established | residual difference |
|---|---|---|---|
| matched set; case B | a counterfactual or adversarial test case; a mimicking or stealthy fault; attack emulation | B94, B115 | the "identical local symptom by construction" replay was not found in the searched FDI literature (matrix C17, C18) |
| nuisance condition as independent unit | cluster / block as experimental unit | standard statistics | none |
| two-stage blinded analysis; preregistration; freeze manifest | blinded outcome assessment; registered report; preregistration | standard in clinical and psychological research | applying these in FDI evaluation was not seen in the searched literature (weak evidence) |
| operational validity (apparatus checks) | manipulation checks; data-quality exclusion | standard experimental methodology | none |

## Terms to stop using without a gloss

1. **"cross-system assurance"** without saying analytical redundancy across
   subsystems.
2. **"witness"** without saying residual / analytical redundancy relation. In
   DES diagnosability, "witness" also means a counterexample trace, which is a
   collision.
3. **"certificate"**. It suggests a formal proof object; the CSIA artifact is
   a record of which discriminating evidence was active.
4. **"conflict"** as a verdict name. It collides with the DX meaning.
5. **"temporal validity"** without citing TRANSCEND (B37) and the
   temporal-diagnosis literature (B32).
