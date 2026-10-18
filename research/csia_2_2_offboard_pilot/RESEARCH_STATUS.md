# Research status (Phase 28)

**2026-10-01.**

**Classes:**
- **VALIDATED RESEARCH:** a preregistered or confirmatory result on data
  collected for it, with the claim stated before the data;
- **ENGINEERING:** built and tested against fixed expectations, including
  regression pins on real data. Not a research claim;
- **PRODUCTIZATION:** what makes it usable by someone else: commands,
  reports, manifests, batch;
- **UNVALIDATED RESEARCH:** a claim that some observations support but no
  designed test has confirmed.

## 1. The status of every claim this pilot touches

| claim | class | evidence | what would move it |
|---|---|---|---|
| in PX4 547e2ca SIH, three witnesses (RPM, body-rate response, controller compensation) separate actuator degradation from RPM telemetry corruption | VALIDATED RESEARCH (SITL) | XSYS-001, preregistered; 55/55 pairs at C3, V3 | hardware, other airframes, other autopilot versions |
| Semantic Core 2.1.1 gives the XSYS-001 verdicts and the Phase C answers | ENGINEERING | the 2.1.1 revision; property tests; replay | — |
| 2.2 admissibility refuses out-of-window evidence and so avoids V4's wrong verdict | ENGINEERING | 55/55 A trials at C3, V4 (2.2 phase; re-verified here) | — |
| the lineage-aware count of independent lines equals the ground-truth count | ENGINEERING on one real dependence structure | 121/121 trials (`INDEPENDENCE_AND_CORROBORATION.md`) | a second real structure; an outside source tracing (G8) |
| a report that shows the dependence of refutations and corroborations helps engineers reach better-justified conclusions than the monitors read individually | **UNVALIDATED RESEARCH** | the pilot team's own reading (`ENGINEER_USEFULNESS.md`, `BASELINE_COMPARISON.md`) | `EXTERNAL_USER_TEST_PLAN.md`, run |
| EKF2 innovation claims do not respond to motor thrust loss | UNVALIDATED RESEARCH (exploratory, as XSYS-001 made W_EST) | AUC 0.43-0.55 on 55 A vs 11 NB flights; 0 over-gate outputs | a preregistered test, or acceptance as context only (current) |
| estimator freshness as producing evidence (EM-1); simultaneous aiding failures as a shared-prediction indicator (EM-2) | UNVALIDATED RESEARCH (ideas) | none: EM-1 blocked by the profile's age limit; EM-2 never observed | a successor profile (EM-1); a real multi-aiding failure (EM-2) |
| the PX4 adapter follows the EKF2 selector and stamps lane epochs | ENGINEERING on one real selector log (one lane) and a synthetic switch | S1; E1; WA-2 | a real lane switch (designed, not run) |
| configuration changes in real logs are reported completely | ENGINEERING | every reset increment in S1 against the report (WA-2); 66 flights | — |
| coverage states keep silence and absence distinct from health | ENGINEERING | U6; WA-3; 66 flights | — |
| the Analyzer command, reports, manifests, batch and determinism | PRODUCTIZATION | `ANALYZER_MVP.md`; `SCALE.md`; pinned hashes | external use |
| the product boundary is a SITL/HIL Validator | PRODUCTIZATION decision | `PRODUCT_BOUNDARY.md` | the external test; G1-G4 |

## 2. Reading

**One VALIDATED RESEARCH result underlies the pilot, and it predates it:**
XSYS-001. Everything 2.2 adds on top of it is ENGINEERING or
PRODUCTIZATION.

**The product's central claim is UNVALIDATED RESEARCH.** That claim: the
explanation is more useful and more defensible. The measured parts are
engineering facts:
- the count is right;
- the warning appears;
- the refusal prevents a wrong verdict.

Whether engineers are helped by seeing them is an open question. The
external test is the experiment that answers it.

**Nothing in this pilot is confirmatory.** Every result document carries
NON-CONFIRMATORY. The estimator statements carry EXPLORATORY.
