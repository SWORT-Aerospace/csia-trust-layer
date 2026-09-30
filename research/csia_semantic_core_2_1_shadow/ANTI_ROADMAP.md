# Anti-roadmap, updated after shadow validation

**2026-09-30. Part 54 of the shadow-validation brief.**

**Where the previous anti-roadmap is.** It is in
`research/csia_usefulness_architecture/11_TARGET_ROLE_AND_NON_GOALS.md` §3.
That document is a previous architecture audit and is **not edited**. This
file re-examines its list against what this phase measured, and adds what
this phase taught. Where the two differ, this one is newer. External methods
are V0 (see `METHOD_REUSE_MAP.md`).

## 1. The brief's list, re-examined

| do not build | still true? | why, with this phase's evidence |
|---|---|---|
| a custom CUSUM | **yes** | the repository already has Page's CUSUM, frozen with v1.1 (`csia/v1_1/sequential.py`), and v2 enforces its constants at ingest. What CSIA lacks is the **contract** around it: lineage, validity and coverage (`CUSUM_INTEGRATION_EXAMPLE.md`), not a better detector |
| a custom active-diagnosis planner | **yes** | CSIA's retained ambiguity set is exactly the input such planners take. MS_B4 and MS_B5 show what a planner would need: a probe that separates a mechanical fault from a lying RPM sensor on the multirotor. CSIA should say that, not plan the probe |
| a custom reachability engine | **yes** | nothing in this phase needed reachability. Capability is downstream of diagnosis |
| a custom RTA | **yes** | CSIA's outputs are the RTA's inputs (`METHOD_REUSE_MAP.md` §3). E1 showed CSIA's own problem is evidence validity, which is upstream of any safety switch |
| a generic IVHM | **yes** | CSIA's value in this phase came from relevance, unknown handling and cross-domain consistency on a declared model. None of that is generic health management |
| a generic dynamic-assurance-case system | **yes** | the boundary is the interface in `METHOD_REUSE_MAP.md` §3. DAC re-evaluates arguments; CSIA supplies evidence states |
| a generic open-set diagnosis | **yes** | 2.1 already reports NO_CONSISTENT_HYPOTHESIS when every declared hypothesis is refuted. The fault study shows the danger is the opposite one: a fault can turn that honest answer into a confident wrong cause (policy A). Fix that before reaching for open-set methods |
| a generic capability planner | **yes** | as in the previous record (G02_ENGINEERING_ONLY) |

## 2. New items from this phase

| do not build | because | evidence |
|---|---|---|
| **profile repairs chosen by how many historical answers they restore** | the one repair that restored everything, R5, restored it through evidence unrelated to the hypothesis it excluded, and brought back v2.0's wrong answer in a counterfactual | `PROFILE_REPAIR_PROPOSAL.md`; `G2_ESTIMATOR_INPUT_AUDIT.md` |
| **confidence counting of any kind** (votes, scores, "N monitors agree") | a count multiplies shared-source evidence (naive over-count 9 in 7 cases) and needs lineage to mean anything. Keep set elimination; add lineage only where corroboration is counted | `DEPENDENCY_METADATA_PREVIEW.md` |
| **a state-conditioned validity layer driven by raw estimated signals** | on XSYS-001 the compensation-state rule lost 64 % of correct identifications, and, when also used as evidence, made 10 wrong. Validity should hang on **reported configuration facts** (epochs, resets, modes). An estimated state is allowed only through a producer that declares its own regime | `XSYS_STATE_CONDITIONED_EXPLORATION.md` |
| **a single fixed validity window** | the fixed-age rule failed both ways in E1 (it dropped a slow valid producer, or kept a latched stale one) | `CONFIGURATION_TRANSITION_STUDY.md` |
| **EKF integrity monitoring** | PX4 EKF2 already publishes test ratios, fault flags, fusion flags, reset counters and lane-switch state (V4). Consume them | `ESTIMATOR_INTEGRATION_EXAMPLE.md` |
| **an isolability algebra of our own** | structural isolability tooling exists. What is missing is running a design-time check against the signature matrix, not new theory | `METHOD_REUSE_MAP.md`; MS_B4 and MS_B5 |
| **a profile compiler or a digital twin** | eight static checks, each motivated by an observed failure, caught 9 of 10 profile mutations. A larger checker has no measured failure to justify it | `PROFILE_VALIDATOR_SPEC.md` |
| **"fixing" the predicate-fault problem by invalidating the tick** | policy D cost 8,388 correct conclusions more than policy B for no safety gain, including 6,591 that never read the failed predicate | `PREDICATE_FAULT_POLICY.md` |
| **an onboard shadow runner** | it costs 12.5× the v2.0 reasoning step on the desktop, mostly hashing and comparison building. It is a ground and SITL tool | `H743_FEASIBILITY.md` |
| **a C port before the evidence adapters exist** | the reasoning core is estimated to be small. What is unknown and probably larger is producing the evidence on the flight controller | `C_RUNTIME_DELTA.md` §4 |
| **FORGE, or any adaptation layer on top of 2.1** | the evidence foundation is not ready: no admissibility, no producer contracts, fault policy B not adopted, G-2 blocked | `PROMOTION_REVIEW.md` |

## 3. What remains worth building

The ranked list, with reasons, is in `NEXT_IMPLEMENTATION_TOP5.md`. Each item
is an **interface or bookkeeping** piece around mature methods, never a
replacement for one.
