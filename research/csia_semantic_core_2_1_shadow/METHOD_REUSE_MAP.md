# Method reuse map, imported concepts, and CSIA's job

**2026-09-30. Parts 18, 19, 20, 34 and 35 of the shadow-validation brief.**

**The purpose is reuse, not novelty.** The question throughout is: which
mature method should CSIA consume instead of re-implementing?

**Source level.** Every external work named here is **V0**: recalled or
summarised, not read in full in this phase. Those whose content would change
a decision are queued in `FULLTEXT_VERIFICATION_QUEUE.md`. Repository
evidence is cited where it exists (V4).

## 1. Capability map (Part 34)

**Cost classes** (per update, per monitored signal):
- **O(1):** constant;
- **O(n):** linear in the signals;
- **O(state³):** filter-sized;
- **offline:** design time only.

"→ EvidenceRecord" means: domain / component : relation, observation state,
lineage.

### Fast change detection

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| CUSUM (Page 1954; Lorden 1971) | quickest detection of a mean shift | textbook; in the repository (`csia/v1_1/sequential.py`) | O(1) | the existing frozen bank, as a producer | tuning theory, alternatives to it | "a shift occurred on node X" | a known in-control model; independent samples | SENSOR/<node> : `seq.mean_shift`; VIOLATED on alarm; lineage {node, smoothing model} |
| GLR (Willsky and Jones 1976) | detection with an unknown change magnitude or time | textbook | O(window) | as a producer where the magnitude matters | — | onset-time estimate | a parametric change model | as CUSUM, plus an onset time in `sequential_state` |
| SPRT (Wald 1945) | sequential test between two hypotheses | textbook | O(1) | for two-hypothesis producer tests | — | accept/reject with error bounds | i.i.d. under each hypothesis | a claim record; state from the decision |
| change-point detection (Basseville and Nikiforov 1993) | general framework | textbook | varies | as a framework for producer design | — | — | — | — |

### Model / state consistency

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| Kalman innovation monitoring and NIS (Mehra and Peschon 1971; Bar-Shalom et al.) | measurement/model disagreement | flight-proven; **in PX4 EKF2** (`estimator_status` test ratios, V4) | O(state³), already paid | EKF2's test ratios and flags (`ESTIMATOR_INTEGRATION_EXAMPLE.md`) | any second EKF integrity layer | "source X disagrees with the prediction" | Gaussian innovations; a correct model | COMPUTE/state_estimator : `estimator.innovation.<src>`; lineage {src, imu, model} |
| residual generation and observer-based FDI (Gertler; Chen and Patton) | fault-sensitive residuals | mature | O(state²) | per-subsystem residual producers | generic observer design | residual-exceeds-threshold claims | a linear or linearised model | as the innovation row |

### Structural diagnosis

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| structural isolability, MSO sets (Krysander, Frisk, Blanke et al.) | which faults a sensor set **can** separate | mature, with tools | offline | **as a design-time check of the signature matrix and the profile**: it would have flagged, before any run, that MS_B4 and MS_B5 cannot be separated on the multirotor | an in-house isolability algebra | "these hypotheses are not isolable with these observables" | a structural model | not a runtime record; a validator finding (a later PV rule) |
| analytical redundancy relations; fault signature matrices | residual-to-fault mapping | mature | offline | CSIA's signature matrix **is** a fault signature matrix, and should be read and reviewed as one | — | — | — | — |
| consistency-based diagnosis (Reiter 1987; de Kleer and Williams) | minimal diagnoses from conflicts | mature | worst case exponential | the vocabulary: 2.1's elimination is single-fault consistency checking | minimal-hitting-set engines onboard | — | a correct system description | — |

### Partial information

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| Kleene strong three-valued logic | reasoning with "unknown" | textbook | O(1) | **already used** (C2) | — | — | monotonicity | the observation state already carries UNAVAILABLE |
| partial interpretations; Belnap's four values | unknown against conflicting | textbook | O(1) | C6's "conflict read by nobody" is the four-valued "both" collapsed to unknown | — | — | — | — |

### Dependent evidence

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| covariance intersection (Julier and Uhlmann 1997); conservative fusion | fusing estimates with an unknown correlation | mature | O(state³) | only if CSIA ever fuses **numbers**. Today it does not | probabilistic fusion inside CSIA | — | consistent estimates | — |
| track-to-track correlation (Bar-Shalom and Campo 1986); double counting | shared-source correlation | mature | — | the lesson: record lineage, do not assume independence | — | — | — | the `source_lineage` field (`DEPENDENCY_METADATA_PREVIEW.md`) |
| common-cause / beta-factor models (reliability engineering) | shared-cause failure | mature | offline | the dependency graph CSIA already has (C1, common cause) | — | — | — | `dependencies` |

### Runtime assurance

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| Simplex / RTA (Sha 2001; later RTA work) | switch to a verified safe controller | mature; flight demonstrations | O(1) switching | **as a consumer** of CSIA outputs | **any RTA inside CSIA** | — | a verified safe controller and switching logic | — |
| runtime verification (Leucker and Schallhart 2009) | checking traces against temporal properties | mature; tools exist | O(n) | a monitor as a producer of property-violation evidence | a temporal-logic engine | "property P violated" | a trace model | <domain>/<component> : `rv.<property>` |
| assume-guarantee contracts (Benveniste et al. 2018) | component interfaces | mature theory | offline | **the evidence contract** (validity, regime, claim) | a contract algebra | — | — | contract fields on the producer |
| dynamic assurance cases (Denney, Pai and Habli 2015) | runtime re-evaluation of safety arguments | research-to-practice | varies | **as a consumer** (§3) | a DAC framework | — | a structured argument | — |

### Active information acquisition

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| active diagnosis / auxiliary signal design (Campbell and Nikoukhah) | injecting inputs to separate hypotheses | mature theory | offline to online | a consumer of CSIA's retained ambiguity. CSIA says *which* hypotheses remain; a planner decides whether to probe | a probing planner | — | a model per hypothesis | — |
| safe active model discrimination | the same, under safety constraints | research | heavy | as above | as above | — | — | — |
| "s-FEAST-class" belief-space planning | named in the brief | **not identified in this phase (V0, name only)** | — | — | — | — | — | — |

### Capability / safety

| method | what it solves | maturity | cost | reuse | do not re-implement | gives CSIA | assumptions | → EvidenceRecord |
|---|---|---|---|---|---|---|---|---|
| reachability (Mitchell, Bayen and Tomlin 2005) | the states reachable under a disturbance | mature, heavy | offline / heavy | a consumer, or an offline envelope | a reachability engine | — | a model and bounds | — |
| control barrier functions (Ames et al.) | safety filtering | mature | O(QP) | a consumer | a CBF layer | — | a model | — |
| attainable moment sets (Durham 1993); degraded envelopes | what is controllable after a failure | mature | offline / O(n) | a consumer of CSIA's localized actuator hypothesis | — | — | an effectiveness model | — |

## 2. Imported concepts (Part 18)

| concept | source (V0) | what CSIA reuses | what is not claimed | why it helps |
|---|---|---|---|---|
| three-valued logic | Kleene | UNKNOWN never decides a hypothesis (C2) | nothing beyond Kleene | stops "could not look" from becoming "fine" |
| structural isolability | Krysander, Frisk; Blanke et al. | design-time "can these hypotheses be separated at all?" | no new isolability theory | explains MS_B4 and MS_B5 (NECESSARY abstention) before any run |
| fault signature matrices | FDI practice | reading the symptom table as one | — | its missing refuters are the ARTIFICIAL abstentions |
| estimator integrity monitoring | Kalman/NIS; PX4 EKF2 | consuming test ratios, resets and lane switches | no EKF monitoring of its own | configuration epochs come from EKF2 itself |
| mode-dependent residuals; closed-loop FDD | FDD literature | validity conditioned on regime and configuration | no claim that state-conditioned validity is better; XSYS shows where it is worse | the transition study's framing |
| runtime contracts | assume-guarantee work | the minimum evidence contract | no contract theory | stale, duplicate and incompatible producers |
| runtime verification | RV literature | producers of property evidence | — | — |
| fault accommodation | FTC literature | nothing internal: CSIA is upstream of accommodation | — | the RTA boundary |
| dynamic assurance | DAC literature | the interface only | not a DAC framework | §3 |

## 3. Boundaries (Parts 19 and 20)

**CSIA provides evidence-level and hypothesis-level assurance:**
- which evidence is admissible;
- which hypotheses it supports, refutes or leaves open;
- what is ambiguous, and why;
- which producers are faulted;
- a reason trace.

**Dynamic assurance and RTA own system-level safety:**
- whether the vehicle's current operation is justified, and at what risk;
- which controller, mode or envelope to use.

| CSIA provides to RTA / DAC | RTA / DAC decides |
|---|---|
| diagnostic state per subject (SUPPORTED / AMBIGUOUS / NO_CONSISTENT / INSUFFICIENT / WITHHELD) | whether a manoeuvre is safe |
| the retained hypotheses (the ambiguity set) | which contingency to take |
| evidence validity: admissible or stale, with the epoch | whether to trust a subsystem for control |
| producer faults and profile gaps | whether the argument's premises still hold |
| the reason trace | what to tell the operator |

**Two rules keep the layers apart:**
- **CSIA never issues a command, a mode change or a risk number.** v2's API
  already has "no score, no command, no mode" (`csia/v2/api.py`, V4).
- **RTA never re-reasons CSIA's evidence.** It consumes CSIA's states and
  applies its own policy.

## 4. What job CSIA should own (Part 35)

**The job, stated narrowly:** **an evidence-qualification and
hypothesis-bookkeeping layer between heterogeneous monitors and downstream
assurance.** It takes claims from mature producers (detectors, estimators,
runtime verifiers), each with a declared contract, and decides four things:
- **admissibility:** is each claim currently valid, independent and
  compatible?
- **relevance:** which declared hypotheses, across domains, does it bear on?
- **consistency:** what remains, what is confirmed, what is contradictory, and
  what cannot be separated with the observables available?
- **accountability:** a trace that says which evidence, gap or fault decided
  the outcome.

**Is that the right role? Largely yes, with one correction.** This phase's
measurements support it:
- **Every place 2.1 was better than v2.0 was one of those four things.**
  Relevance (C1, C3), unknown handling (C2), producer faults (C4), duplicates
  (C6) and cross-stage consistency (F2).
- **Every loss traced to the declared model, not to missing detection.**

**The correction.** "Cross-domain consistency" is only as good as the profile
and the signature matrix. So the job must include **validating its own
configuration** (the profile validator, structural isolability at design
time). Otherwise CSIA becomes a confident amplifier of profile errors, as the
M2 mutation shows.

**What CSIA should not own:**
- detection (producers do it);
- estimation (EKF2 does it);
- safety decisions (RTA does them);
- probing (active-diagnosis planners do it);
- capability envelopes (reachability does it).
