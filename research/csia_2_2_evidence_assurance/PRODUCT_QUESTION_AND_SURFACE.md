# The minimum product question and the product surface (Phases 1 and 2)

**2026-10-01.**

## 1. The question an engineer brings (Phase 1)

| question | where the answer is | from |
|---|---|---|
| What appears abnormal? | `state.abnormal`: the symptoms 2.1.1 detected, and the adverse admitted evidence | 2.1.1 localization; admissibility |
| Which explanations remain possible? | per localization: `candidates` (supported and unresolved hypotheses); `attribution.candidates` | 2.1.1 |
| Which were eliminated, and by what? | per localization: `eliminated` (hypothesis and predicate) and `refuting_evidence` (the evidence ids that predicate read) | 2.1.1 trace |
| Which evidence was used? | `evidence.used`; per localization `supporting_evidence` | admissibility; 2.1.1 trace |
| Which evidence was rejected, and why? | `evidence.rejected`: status and every failing check | admissibility |
| Did a monitor itself fail? | `producers.by_producer`: health, faults, admitted and rejected counts; `coverage_gaps` | health; admissibility |
| Did a configuration change invalidate evidence? | `configuration`: epochs, transition events, and what R-3 did not admit | R-3 |
| Are apparently independent monitors actually dependent? | `corroboration`: per component and overall, lineage groups and independent lines | lineage |
| Did a predicate fail? | per localization: `predicate_faults` and `fault_impact` | 2.1.1 R-1 |
| Can the profile be trusted? | `profile`: gate status; `profile_warnings` | profile gate |

**Every answer is something 2.1.1 or admissibility already computes.** The
Analyzer computes nothing about the vehicle itself.

## 2. The product surface (Phase 2)

**The CSIA Flight Assurance Analyzer is offboard only:**
- SITL, HIL and flight test;
- post-flight analysis;
- integration debugging.

It has no flight-control authority, and nothing in `csia/` imports it
(`test_nothing_in_csia_imports_2_2_and_2_2_never_attributes_unsupported`).

**Inputs:**

| input | how |
|---|---|
| PX4 ULog | `python -m csia_evidence_assurance ulog FILE`: `estimator_status`, `estimator_selector_status`, initial parameters |
| CSIA evidence | the frozen v2 domain plugins (`scenario NAME`) |
| estimator status | the PX4 estimator adapter |
| monitor outputs | the frozen CUSUM (`cusum NAME`); the XSYS-001 witnesses (`xsys ID`) |
| profile | the successor profile r2, gated; or a research specification (NOT_APPLICABLE) |
| configuration transitions | the epoch context from the estimator adapter, or the integration's own (E1) |

**Outputs** (`report.json`, byte-stable; `report.txt` for an engineer):

| output | field |
|---|---|
| event timeline | `timeline`: intervals of unchanged state, each with what changed |
| assurance events | the timeline's change list |
| candidate causes | per localization `candidates`; `attribution` |
| UNIQUE / AMBIGUOUS / no consistent hypothesis | `state.headline`, localization outcomes, attribution verdict |
| evidence used and rejected, with reasons | `evidence` |
| producer health | `producers` |
| configuration changes | `configuration` |
| profile warnings | `profile_warnings` |
| decision trace | `reason_trace`, per localization `why` |

**No GUI.**
