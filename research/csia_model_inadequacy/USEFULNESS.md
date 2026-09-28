# Assurance under model incompleteness: usefulness

Written on 2026-09-28. Source ids `Mnn` are defined in
`research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` §1.

**All scores are qualitative.** Every one rests on V0 evidence, except the
fielded-code observation (V4).

- No operator, manufacturer or certification authority was consulted.
- A blank in the "evidence of need" column means nothing was found. It does
  not mean there is no need.
- Scales follow `research/csia_dx/CSIA_DX_USEFULNESS_SCORECARD.md`:

| scale | levels |
|---|---|
| NEED | STRONG / MODERATE / WEAK / NONE_FOUND |
| COVERAGE | HIGH / PARTIAL / LOW |
| GAP | LARGE / SMALL / NONE |

## 1. Is the problem real?

**Yes.** Confident action on a wrong but best-fitting explanation, when
reality lies outside the model, is documented in aviation and space accidents
and serious incidents:

- M52: XL Airways 888T;
- M53: Lufthansa 1829;
- M54: Schiaparelli;
- M50: Qantas 72, at least as an unanticipated input pattern;
- M51: Ariane 501, as a common-mode software failure.

It is also documented formally:

- Zadeh's normalization example (M08);
- closed-world misdiagnosis of structural faults (M37).

Assurance practice already treats model incompleteness as a first-class
concern:

- ARAIM allocates integrity to unmonitored fault modes (M35);
- SOTIF defines an "unknown unsafe" area (M36).

## 2. Would a runtime ambiguous-versus-inadequate output have helped in the documented cases?

| case | inadequacy observable from the deciding logic's own evidence? | what would have exposed it | established? | value of a separated verdict alone |
|---|---|---|---|---|
| 888T (M52) | **no**. The two frozen vanes agreed, so under the single-sensor-fault model the healthy third vane was the outlier (V-equivalent) | AOA versus flight-dynamics analytical redundancy (M44) | yes (patents, M44) | **none without new evidence** |
| Lufthansa 1829 (M53) | the same class (V0 SS) | the same | yes | none without new evidence |
| Schiaparelli (M54) | **yes**. A negative altitude estimate contradicts the vehicle's own state model | a runtime compliance / plausibility check (M27 style) | yes | real, but delivered by a known check. Whether such a check existed is queued (FULLTEXT_VERIFICATION_QUEUE.md Q12) |
| Qantas 72 (M50) | UNCLEAR at V0 | UNCLEAR | UNCLEAR | UNCLEAR |
| Ariane 501 (M51) | both SRIs failed on the same software exception, which is inconsistent with independent random unit failures. Queued (Q11) | common-mode reasoning at design time; the inquiry's recommendations are queued | yes, as design practice | the failure was in the fault response (processor shutdown), not in any missing verdict (V0) |
| structural fault read as multiple component faults (M37) | yes, if structural-fault hypotheses exist | structural or unknown-mode hypotheses (M03, M37) | yes | real; delivered by established MBD extensions |
| fielded estimator selection (M60, M61; V4) | yes, as per-instance combined test ratios (the PX4 selector publishes them, line 890) | not normalizing inadequacy away at selection | the principle, yes (M02, M07, M24) | **a deployment question**: whether vehicle-level logic uses these ratios was not traced (UNCLEAR) |

**Reading.** The useful work in these cases is done by two things:

- **more, dissimilar evidence**: analytical redundancy across physical
  domains;
- **not normalizing inadequacy away**: reject rules, open-world combination,
  residual monitoring and compliance monitors with fail-safe.

Both are established. A new verdict label applied to the same evidence would
not have changed the outcome of the V-equivalent cases.

## 3. Scorecard

| # | problem | evidence of need | existing approaches | NEED | COVERAGE | GAP |
|---|---|---|---|---|---|---|
| 1 | separate ambiguity from inadequacy at runtime | §1 cases; M17 (ML practice) | M02, M03, M07, M11, M21, M24, M26 | MODERATE | HIGH | NONE |
| 2 | detect joint cross-system inconsistency | 888T / Lufthansa 1829 pattern (M52, M53) | M03, M05, M07, M44, M48 | STRONG | HIGH | NONE |
| 3 | compound faults from single-fault components | multiple-fault scenarios in MMAE work (M24) | M05, M24 | MODERATE | HIGH | NONE |
| 4 | conditions no combination of modes explains | M37; El Al 1862 (M47) | M03, M04, M06 | MODERATE | HIGH (in theory) / PARTIAL (in fielded systems: UNCLEAR) | SMALL, deployment only |
| 5 | prevent confident action on a wrong best fit | §1 cases | M27, M24, M01, M02, M16 | STRONG | PARTIAL (fielded selectors, M60 and M61: V4; system level UNCLEAR) | SMALL, deployment only |
| 6 | detect observationally equivalent out-of-library causes | 888T, Lufthansa 1829 | dissimilar redundancy (M44); design-time allocation (M35, M36) | STRONG | PARTIAL, bounded by identifiability | NONE (a limit, not a gap) |
| 7 | calibrated inadequacy outputs | none specific | M11, M12, M13 | WEAK | PARTIAL | SMALL |

## 4. Why CSIA specifically would or would not help (part H)

This section is descriptive of CSIA at commit 503321f (V4, M62). It proposes
nothing and changes nothing.

**What CSIA has that bears on the problem.**

- **Three-valued predicates.** `None` means unmeasurable, so INSUFFICIENT
  evidence is kept apart from refutation. This matches vacuity and `m(Ω)`
  (MI-C3, N0).
- **An all-refuted state.** The code comment names it "a finding about the
  MODEL" (`csia/v2/localization.py` lines 321–326). This is the GDE+ "no
  consistent diagnosis" signal (M04; MI-C15, N0).
- **SupportCertificate.** It records which competitors lack a separating
  witness (`csia_assurance/witness.py` lines 61–71). That is the
  ambiguity-group record in established terms.
- **Cross-domain evidence breadth.** The platform ingests evidence from
  several physical domains. That breadth is what M44-style analytical
  redundancy needs. It is a property of the evidence, not of the reasoning
  method.

**What CSIA lacks, relative to established methods.**

- **No joint consistency.** Each symptom is localized independently
  (`localize_all`, lines 352–358). V-joint is not checked. Consistency-based
  diagnosis, the TBM and GARRs all check it by construction.
- **An overloaded verdict.** UNSUPPORTED covers:
  - "all refuted", which is MODEL_INADEQUATE (line 326);
  - "one unconfirmed survivor", which is closer to insufficient evidence
    (line 333);
  - in `attribution.py`, "implicated without own adverse evidence"
    (lines 11–13).

  The established literature keeps these apart (M02, M07, M09).
- **Elimination only by declared refuters.** An out-of-library cause yields
  the all-refuted state only if a declared refuter happens to fire against
  every modelled hypothesis. Hypotheses marked `unmodelled` are never
  eliminated (line 299), so symptoms that declare one cannot reach the
  all-refuted state at all. Distance reject (M02), NIS and residual tests
  (M24, M25) and model invalidation (M26) do not depend on hand-declared
  refuters.
- **No evidence about out-of-library conditions.** XSYS-001 tested
  separation of **modelled** hypotheses. It is not evidence for or against
  CSIA's handling of out-of-library conditions, and it is not reinterpreted
  here.

**Verdict on H.** CSIA's structure gives **no meaningful advantage** for this
problem. Its relevant mechanism is a consistency-based diagnosis variant
(novelty audit: N0/N1). On the joint case it has less than the established
methods.

**Engineering observations.** These are recorded only. They are not
research, not implemented and not requested.

| id | observation |
|---|---|
| EO-1 | UNSUPPORTED carries three meanings across `localization.py` and `attribution.py` |
| EO-2 | localization does not test whether one hypothesis explains all symptoms jointly |
| EO-3 | if CSIA ever reports these states, it should use the established names mapped in AMBIGUITY_VS_MODEL_INADEQUACY.md §4 rather than new vocabulary |

## 5. Users and product forms

| user | interest | evidence found |
|---|---|---|
| UAV autopilot developers | not normalizing inadequacy away in estimator and failure selection | the V4 code observation only (M60, M61); no demand evidence |
| eVTOL / autonomous aircraft | model-compliance fail-safes; dissimilar redundancy | M27 (patents), M44 (patents) |
| space systems | unknown-anomaly handling in on-board FDIR | M46, M29, M30 |
| certification | handling of unmodelled threats | M35, M36 |

**Product reading.** No product form emerged whose value is not already
delivered by established methods: runtime compliance monitors, analytical
redundancy, open-world combination and reject rules. The practical value lies
in **applying** these methods to fielded autopilots. That is an engineering
and deployment task, not a research contribution.
