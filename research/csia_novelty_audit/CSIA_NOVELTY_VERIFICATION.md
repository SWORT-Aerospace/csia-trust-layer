# CSIA novelty verification: stage 2 (PRE-RESULT)

This is the second-stage verification layer of the CSIA novelty audit. It was
written on 2026-09-27 and 2026-09-28. It does **not** replace the broad audit
in `research/csia_novelty_audit/CSIA_NOVELTY_AUDIT.md`, which stays as
written. Source ids are listed in
`research/csia_novelty_audit/BIBLIOGRAPHY.md`: stage-1 ids B01–B116 and
P01–P23; stage-2 ids B117–B147, P24 and P25.

## Independence from the running campaign

The XSYS-001 confirmatory campaign was running while this layer was written.
This layer draws on:

- the frozen preregistration, `docs/research/XSYS_001_PREREGISTRATION.md`;
- the two amendments, `docs/research/XSYS_001_A1_NUISANCE_INDEPENDENCE.md`
  and `docs/research/XSYS_001_A2_C4_CORRECTION.md`;
- the CSIA source code;
- the public literature, open-source autopilot code and patents.

**No confirmatory log, stage output, completion record or result was opened,
and none is referred to.** Every judgement below would read the same whether
XSYS-001's primary hypothesis is supported or not. Where a judgement depends on
that outcome, it is written conditionally, in final-report item 14 and in
`research/csia_novelty_audit/CSIA_PUBLICATION_CLAIM_BOUNDARY.md`.

## Rules this layer follows

1. **A snippet is not a paper.** Every source carries a verification level
   (V0–V4; defined in `BIBLIOGRAPHY.md` §"Stage 2 additions"). A source that
   could not be read is marked REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION.
2. **Unreadable means UNCLEAR, not NO.** A NO appears only where:
   - a source was read at V4 and the feature is absent from the inspected
     code; or
   - the source's subject is positively described and excludes the feature
     (for example, RAIM has no actuators).
3. **No bare use of the word for newness.** Statuses are N0–N4 (§17), with
   stated confidence.
4. **Absence of a match is reported as** "no directly matching work was
   identified in the searched sources". It is never reported as absence of
   prior art.
5. **No legal conclusion.** The patent material is technical triage only.

## 1. Access and verification

The environment's egress policy was retested in stage 2 (log §S2.1). Only
`raw.githubusercontent.com` answers. Every scholarly, patent and publisher
host is blocked, including:

- open-access MDPI;
- PubMed Central;
- the USPTO PDF host, retested on 2026-09-27;
- `github.io`.

What that allowed:

| level | sources | what was read |
|---|---|---|
| **V4** | B130 (ArduPilot), B131 (PX4 at `547e2ca`) | the complete relevant functions, with line numbers: `check_for_failed_motor`, `thrust_loss_check`, `yaw_imbalance_check`, `escCheck.cpp` L310–330, the failure detector, and two documentation pages |
| V2 | B132 (R2U2 tool), B133 (CPS_Invariant artifact), B134 (Fault Diagnosis Toolbox) | repository READMEs. The papers these tools accompany stay V0 |
| V1 | none | no abstract page was reachable |
| V0 | every paper and every patent | search-engine titles and summaries. For the EPOS patents, a short search-rendered excerpt of the patent text (S2Q35) |

**Consequence.** No fine-grained distinction in this layer rests on V3/V4
evidence, except where the V4 autopilot sources close off a claim. **N4 is
therefore unavailable for every element.**

## 2. Step 1: the top threats

Twenty-five sources, or source groups, were selected. Each was chosen because
it overlaps materially with one or more of the brief's areas A–L, not because
it is well known. They are the columns of
`research/csia_novelty_audit/CSIA_CLOSEST_PRIOR_ART_CLAIM_CHART.csv`.

| id | source | level | areas | why it threatens the remaining candidate |
|---|---|---|---|---|
| T01 | ArduPilot thrust-loss, yaw-imbalance and failed-motor logic (B130) | **V4** | B, D, H, J, K | fielded code uses the controller's per-motor demand, and its yaw integrator, as root-cause evidence. It conjoins that with a physical consequence (descent) and context validity gates, then triggers a bounded response |
| T02 | PX4 ESC motor-failure check, failure detector, latch (B131) | **V4** | C, E, J, K | an explicit statement that evidence read after the protective action would falsely exonerate the motor; the conclusion is latched for that reason |
| T03 | TRANSCEND (B37) | V0 | E, F, I | transient signatures refine a candidate set; transient analysis gives way to steady-state analysis |
| T04 | Qualitative event-based diagnosis and QED (B38, B39) | V0 | E, F, I | measurement orderings plus possible conflicts |
| T05 | Mode-sequence ARRs (B119) | V0 | E, F, G, I | ARR validity is scoped to a mode; sequences of modes resolve non-discernibility |
| T06 | Timed fault-signature matrices (B40) | V0 | E, F, I | occurrence-order and occurrence-time signatures |
| T07 | Reiter; de Kleer & Williams (B28, B29) | V0 | F, G | consistency-based elimination, minimal diagnosis sets, measurement selection, multiple faults |
| T08 | Console & Torasso (B31) | V0 | F, G, H | abductive coverage in addition to consistency: the antecedent of "survival is not support" |
| T09 | Alavi, Izadi-Zamanabadi, Hayes (B117) | V0 | C, D, E | closed-loop actuator-versus-sensor FDI. A sensor fault is masked after a short time; controller-demanded signals reveal it |
| T10 | Cascade electro-hydraulic propagation (B118) | V0 | C, D, E, L | feedback removes the steady-state effect of actuator faults but not of feedback-sensor faults; used for isolation |
| T11 | EPOS engine patents (P03, P04, P05; P25) | V0 | A, B, C, L | the actuator-sensor fault and the actuator-hardware fault share a local symptom (minor-loop tracking error), and the engine response separates them |
| T12 | US 4,641,517 (P01) | V0 | C | sensor versus common actuator, decided against a model-synthesized position (1987) |
| T13 | IMM / MMAE (B43, B44) | V0 | B, C, J | sensor versus actuator failures in flight control, decided from the aircraft dynamics; compensation follows |
| T14 | Quadrotor actuator and sensor FDD (B123, B124) | V0 | B, C, L | multirotor loss of effectiveness versus IMU sensor faults, including flight tests |
| T15 | Kobayashi & Simon (B46, B47) | V0 | A, B, C | engine sensor versus actuator/component faults, from a filter bank |
| T16 | R2U2 (B67, B68; tool B132) | V0 / V2 | A, E, I, K | UAS health management: temporal-logic observers plus Bayesian diagnosis over sensor and software |
| T17 | VIPR / VLRS (B59, B60) | V0 | A, G, K | a vehicle-level reasoner; ambiguity groups; temporal latching |
| T18 | US 11,061,390 (P06) | V0 | G, H | ambiguity groups ranked by supporting evidence |
| T19 | US 12,134,484 (P07) | V0 | A, I, K | structural-temporal analysis of fault propagation graphs on aircraft |
| T20 | US 9,725,187 (P24) | V0 | H, J, K | a health score from risk, confidence and benefit, gating reconfiguration |
| T21 | Nikiforov; Lai (B122, B121) | V0 | H | detection–isolation under a probability-of-false-isolation constraint |
| T22 | RAIM / ARAIM (B87) | V0 | G, H, J | protection level against alert limit; an operation authorized only when integrity is sufficient |
| T23 | Stojcsics et al. (B120) | V0 | H, J | an FDI component, a separate assurance monitor and contingency management |
| T24 | Choi et al. control invariants (B92; B133) | V0 / V2 | B, D | physical response must follow controller output (attack detection) |
| T25 | Matei et al. (B76) | V0 | A, G, J | model-based diagnosis with active disambiguation and reconfiguration |

Area coverage:

| area | threats |
|---|---|
| A | T11, T15, T16, T17, T19, T25 |
| B | T01, T11, T13, T14, T15, T24 |
| C | T02, T09, T10, T11, T12, T13, T14, T15 |
| D | T01, T09, T10, T24 |
| E | T02, T03, T04, T05, T06, T09, T10, T16 |
| F | T03, T04, T05, T06, T07, T08 |
| G | T05, T07, T08, T17, T18, T22, T25 |
| H | T01, T08, T18, T20, T21, T22, T23 |
| I | T03, T04, T05, T06, T16, T19 |
| J | T01, T02, T13, T20, T22, T23, T25 |
| K | T01, T02, T16, T17, T19, T20 |
| L | T10, T11, T14 |

Patents included: P01, P03–P05 (with P25), P06, P07 and P24. Sources that
bear on the question but are not columns are used in the text: B30, B32,
B62, B70, B89, B99, B127–B129, B135–B139, B141–B147, P15.

## 3. Step 2: the frozen feature vector

The brief's 25 features were adopted unchanged. Two were added because they
are needed to score what the broad audit left standing:

- **F26** supports matrix C17, the evaluation practice;
- **F27** supports the XSYS-001 H3(b) negative control.

The list was fixed in the working notes before any cell of the claim chart was
filled. It was not changed afterwards.

| id | feature | scored YES when the source… |
|---|---|---|
| F01 | LOCAL_FAULT_DETECTION | detects a fault from one component's own signal |
| F02 | CROSS_SENSOR_REASONING | uses a relation among two or more sensors |
| F03 | CROSS_SUBSYSTEM_REASONING | lets evidence from one subsystem change the reading of another's symptom |
| F04 | PHYSICS_BASED_RELATIONSHIPS | uses explicit physical or dynamic model relations |
| F05 | PHYSICAL_CONSEQUENCE_AS_WITNESS | uses the plant's physical response as evidence about a component hypothesis |
| F06 | ACTUATOR_VS_SENSOR_FAULT_DISCRIMINATION | separates an actuator fault from a sensor fault, including the actuator's own feedback or telemetry |
| F07 | CONTROLLER_RESPONSE_AS_EVIDENCE | uses the controller's compensatory output (effort, integrator, command imbalance) as the evidential statistic. A control input used only as a known model input does not count |
| F08 | TEMPORAL_FAULT_SIGNATURES | uses order, timing or transient shape |
| F09 | EXPLICIT_TEMPORAL_EVIDENCE_VALIDITY | gives an evidence channel an explicit phase, mode or window outside which it is not used |
| F10 | STRUCTURAL_HYPOTHESIS_ELIMINATION | eliminates hypotheses by refutation rather than by scoring |
| F11 | CANDIDATE_SET_OUTPUT | can output a set of candidates |
| F12 | EXPLICIT_AMBIGUITY_PRESERVATION | makes unresolved ambiguity a first-class output |
| F13 | EVIDENCE_SUFFICIENCY | names a cause only when an explicit sufficiency condition holds |
| F14 | DETECTION_VS_ISOLATION_SEPARATION | keeps detection and isolation as distinct stages or criteria |
| F15 | ISOLATION_VS_CERTIFICATION_SEPARATION | produces a separate record or statement of whether the isolation is justified |
| F16 | CERTIFICATION_VS_ACTION_SEPARATION | separates the justifying layer from the acting layer |
| F17 | CROSS_DOMAIN_EVIDENCE_GRAPH | relates heterogeneous evidence to hypotheses in a graph or matrix |
| F18 | MULTIPLE_EVIDENCE_TIMESCALES | uses evidence gathered on deliberately different timescales |
| F19 | BOUNDED_RUNTIME_ACTION_AUTHORITY | uses the diagnostic or integrity state to bound what may be done at run time |
| F20 | ACTIVE_EVIDENCE_ACQUISITION | acts (measures, excites, manoeuvres) to obtain discriminating evidence |
| F21 | MULTI_FAULT_REASONING | handles simultaneous faults |
| F22 | EXPLICIT_WRONG_ATTRIBUTION_AVOIDANCE | states an explicit criterion or constraint against wrong isolation |
| F23 | MATCHED_LOCAL_SYMPTOM_EXPERIMENT | evaluates competing causes constructed to show the same local symptom |
| F24 | PHYSICAL_VS_TELEMETRY_MATCHED_SET | does so specifically for physical actuator degradation versus actuator telemetry corruption |
| F25 | TEMPORAL_PLUS_STRUCTURAL_INTEGRATION | uses temporal evidence inside structural or consistency-based elimination |
| F26 | PREREGISTERED_BLINDED_EVALUATION | freezes decision rules before data, and blinds outcome labels during scoring |
| F27 | EXPLICIT_WINDOW_MISUSE_NEGATIVE_CONTROL | includes a control that uses evidence outside its validity window, to show the misuse causes wrong attribution |

## 4. Steps 3 and 4: scoring and the claim chart

The chart is `research/csia_novelty_audit/CSIA_CLOSEST_PRIOR_ART_CLAIM_CHART.csv`:

- 27 rows, one per feature;
- 26 status columns: CSIA, then T01–T25.

Each cell begins with YES, PARTIAL, NO or UNCLEAR, followed by a short
evidence reference. The verification level is given inside the reference.
The chart has no numeric score.

Two annotations need explaining:

- **(bk)** marks a cell that rests on well-documented background knowledge
  not verified in this session. It is used only to **credit** prior art,
  never to score NO. Where background knowledge would have denied a feature
  (for example, "Reiter's formulation is atemporal"), the cell is UNCLEAR.
- **NO (method nature)** or **NO (scope)** is used only where the search
  summary positively describes the source's method or subject, and that
  description excludes the feature. Examples: IMM is a probability-weighted
  model bank; RAIM has no actuators.

**The CSIA column is scored conservatively.** Several CSIA features exist only
in the XSYS-001 adapter, not in the CSIA v2 engine. The engine is atemporal:
`csia/v2/localization.py` says "Nothing here reads time order". The cells say
so. F19 and F20 are NO. F04, F08, F13, F15, F21 and F25 are PARTIAL.

**How to read the chart.**

- **Features where at least two threats score YES:** every feature except F09,
  F18, F23, F24, F26 and F27. Each YES rests either on V4 code or on a V0
  summary that states the feature directly. That covers every CSIA feature
  outside the six listed.
- **F09** has a single YES: B119, and only at mode scope. Seven threats are
  PARTIAL on it, including both V4 autopilot sources (§8).
- **F18.** No threat scores YES. Several show different timescales without
  designing for them. At V0 this is weak ground, not a distinction.
- **F23, F24, F26 and F27** are evaluation features. For every V0 source they
  are UNCLEAR, because no evaluation section was read. **UNCLEAR is not NO.**
  These rows are where a V3 reading is most needed; see
  `CSIA_FULLTEXT_VERIFICATION_QUEUE.md`.
- **F24.** Five threats are PARTIAL: T09, T10, T11, T12 and T14. They have the
  actuator-versus-own-sensor pair, but not a matched-by-construction set. The
  EPOS excerpt (T11) states that both faults share the same local symptom.

## 5. Step 5: the combination search

Queries S2Q1–S2Q41 are in the search log, §S2.3–§S2.4, together with a
mapping of every example query in the brief. The target was **any single
source that contains the conjunction** CSIA's remaining candidate needs:

> F05 physical witness + F06 actuator versus actuator-telemetry + F07
> compensation witness + F09 per-evidence phase validity + F12 retained
> ambiguity + F24 matched set.

**No directly matching work was identified in the searched sources.** The
nearest partial conjunctions are listed below. All are V0 unless marked.

| source | has | lacks, as far as V0 shows |
|---|---|---|
| EPOS family (P03–P05, P25) | F05, F06, a shared local symptom, a physical-response discriminator; the direction of feedback drift against the request as a loop-behaviour cue | F09 phase windows, F07 as effort, F12, a multirotor, a matched-by-construction evaluation |
| B118 | F06 actuator versus feedback sensor, isolated through how feedback redistributes the fault's steady-state effect (F07-adjacent) | F09, transient-phase evidence (not shown), F12, F24 matching |
| B117 | F06, F07 (controller-demanded signals), closed-loop temporal masking (F09-adjacent) | multirotor, F12, matching; SISO |
| ArduPilot (**V4**) | F05, F07, context validity (F09-partial), sufficiency by conjunction and persistence (F13-partial), a bounded response | F06, F10–F12, telemetry, any evaluation |
| TRANSCEND / QED | F08, F10, F11, F25, transient-then-steady (F09-partial) | F06/F24 as defined, F07 |
| B119 | F09 (mode scope), F10, F12, F25 | F06, F07, F24 |
| B142 | per-residual **validity region** used inside consistency-based diagnosis (F09 over operating region) | time windows, F06, F07 |
| VIPR / R2U2 | F03, F11, F12, F17, temporal latching or observers | F06/F24, F07, per-evidence phase validity (not shown) |

The combination-search finding is recorded in the table above. Every
**pairwise** combination inside the target conjunction appears somewhere in
the searched material. The full conjunction was not found. Section 15 asks
whether the full conjunction is a contribution.

## 6. Step 6: XSYS-001 exact prior art

This has its own file, `research/csia_novelty_audit/XSYS_001_EXACT_PRIOR_ART.md`.

**Headline.** The underlying diagnostic question is **CLOSE_PRIOR_ART**:

- EPOS: shared local symptom, physical-response discriminator;
- B118: actuator versus feedback-sensor faults through closed-loop propagation;
- B117: controller-demanded signals against closed-loop masking.

The exact matched-set formulation is **POSSIBLY_DISTINCT**:

- multirotor;
- RPM telemetry corrupted to replay the observed ratio of a physical
  effectiveness loss;
- a transient dynamics witness plus a post-compensation allocator witness,
  each valid only in its window;
- an elimination rule that may answer AMBIGUOUS;
- zero-WRONG.

It is not APPARENTLY_DISTINCT_PENDING_VERIFICATION, for two reasons. The
closest sources are unread at V0 and could contain the missing parts. The
security literature constructs matched corruptions by design (B147).

## 7. Step 7: controller compensation as diagnostic evidence

**What counts.** The controller's own compensatory behaviour is the
evidential statistic for a root-cause hypothesis. That behaviour can be
effort, integrator state, or per-actuator command imbalance. Each of the
following was separated from that:

| not the same thing | example | why it is not compensation-as-witness |
|---|---|---|
| accommodating a known fault | EPOS "fault accommodation" (P03); Maybeck's command redistribution (B44) | the action follows the diagnosis; the action is not evidence |
| reconfiguring after detection | P24; B19 | same |
| control allocation | B20; B21 (allocation with unknown-input observers) | the allocator distributes effort. In B21 the evidence is an observer residual |
| residual generation | IMM/MMAE (B43, B44); control-objective residuals (B145) | the control input enters a model as a known input. B145 is the closest of these, and is V0 |
| tracking error | EPOS minor-loop error; ArduPilot attitude error | the error, not the controller's compensatory output. ArduPilot uses attitude error < 30° only as a validity gate |

**Finding: compensation as evidence about actuator effectiveness is KNOWN.**
The closest source is ArduPilot, and it was read at **V4** (B130):

- **`AP_MotorsMatrix.cpp::check_for_failed_motor`.**
  - It low-pass filters each motor's thrust demand, `alpha = dt/(dt+0.5)`
    (L417).
  - It computes `thrust_balance = rpyt_high * number_motors / rpyt_sum`
    (L444).
  - It declares a motor failure when `thrust_balance >= 1.5` on frames with
    at least six motors (L450).
  - It names the lost motor as **the motor with the highest filtered
    demand** (L413, L436).
  - This is the controller's allocation imbalance used as root-cause
    evidence.
- **`crash_check.cpp::yaw_imbalance_check`.**
  - It reads the filtered yaw-rate integrator against a fraction of IMAX
    (L214–229).
  - The code comment gives the root causes it evidences: "could be due to
    badly calibrated ESC or misaligned motors" (L183).
  - The wiki calls it "a measure of how hard the vehicle is working to yaw"
    (wiki L31).
- **`crash_check.cpp::thrust_loss_check`.**
  - It conjoins controller demand at its limit ("throttle over 90% or
    throttle saturation", L133) with a **physical consequence**: descending,
    `vel_d > 0` (L145–151).
  - It adds validity gates: requested lean < 15° (L125–131), throttle ≥ 0.25
    "to prevent checks triggering from thrust limitations caused by low
    commanded throttle" (L139–143), and attitude error < 30° (L153–158).
  - It then waits 1 s of persistence (L164) before "Potential Thrust Loss"
    and a bounded response, `set_thrust_boost(true)` (L170–172).

**XSYS-001's compensation statistic is the same kind of statistic.**
- W_CTRL is κ_m = c_alloc,m / mean of the other motors' commands, measured in
  T3 against a T0 baseline (prereg §7.2).
- ArduPilot's `thrust_balance` is max demand / mean demand over all motors.
- The two are the same family of statistic: a per-motor command relative to
  the fleet mean.

**Where the use differs.**
- ArduPilot uses the statistic to decide **that** a motor lost thrust and
  **which** motor.
- XSYS-001 uses it to decide **whether** a local RPM deficit is physical or a
  telemetry artefact. Compensation present confirms physical loss. Compensation
  absent, when the RPM-implied loss would have produced a response at least
  twice the threshold, affirms "nominal" and refutes the physical cause.
- No inspected ArduPilot function reads RPM telemetry.
- The discrimination use is **CLOSE_PRIOR_ART**, all at V0:
  - B117: controller-demanded signals reveal a sensor fault the loop masks;
  - B118: feedback removes the steady-state effect of actuator faults but not
    of feedback-sensor faults;
  - EPOS: the direction of feedback drift against the request.
- The multirotor RPM-telemetry instance was not found in the searched
  sources.

**Structural note that weakens the XSYS-001 case rather than strengthening
it.**
- In PX4, RPM telemetry is not a feedback signal for the attitude loop.
- A corrupted RPM channel therefore leaves the controller untouched, and "no
  compensation" follows by construction.
- That makes the allocator a virtual sensor of rotor effectiveness, checked
  against the RPM channel.
- That is analytical redundancy (B05). It is a simpler structure than B117 and
  B118, where the faulty sensor sits inside the loop.

**Survives?** Not as an independent contribution: **N0**. It survives only as
one of the two witnesses inside the narrow pairing, MNC-1 (§14).

## 8. Step 8: temporal validity

The brief's four sub-questions:

| sub-question | status | closest evidence |
|---|---|---|
| (a) E1 (body-rate dynamics along the loss axis) is informative in the transient T1 | **KNOWN** | TRANSCEND transient signatures (B37, V0); multirotor loss-of-effectiveness from body rates (B48, B54, B125, V0); ArduPilot requires the physical consequence (descent) (B130, **V4**) |
| (b) E2 (compensation) becomes informative in T2/T3 | **KNOWN** | ArduPilot filtered demand and yaw integrator (B130, **V4**); steady-state propagation through feedback (B118, V0) |
| (c) E1 must not be used after its physical validity ends | **CLOSE_PRIOR_ART** | ArduPilot's yaw check is **suspended, and its filter reset, while thrust boost is active**: "thrust loss is triggered, yaw issues are expected" (crash_check.cpp L196–199, **V4**). That is an explicit phase-conditioned invalidation of an evidence channel. Also: ARR validity scoped to a hybrid mode (B119, V0); a residual used only inside its validity region (B142, V0; operating region, not time); progressive monitoring from transient to steady state (B37, V0); three-valued "inconclusive" / BLIND status (B70, B89) |
| (d) using E1 outside its regime causes wrong attribution | **CLOSE_PRIOR_ART** | PX4 states the mechanism in code: "Only set, never clear mid-air: stopping the motor in response could make it appear healthy again" (escCheck.cpp L318, L323; docs L91–92, **V4**). Evidence read after the regime has changed would **falsely exonerate** the failed motor, so the conclusion is latched. Also: closed-loop masking of sensor faults after a short time (B117, V0); masking and compensation lower diagnosability (B129, V0) |

**What CSIA adds, precisely.**

1. **The representation.** Each XSYS-001 witness has one window. Outside it,
   the predicate is **None**, recorded as NOT_APPLICABLE and "never False"
   (prereg §7.3). Set elimination then treats it as eliminating nothing.
   - Per-mode ARR validity (B119), validity regions (B142) and three-valued
     verdicts (B70, B89) cover this.
   - Residual difference: the validity is indexed by the **fault's own
     phase**, set by onset and compensation, rather than by a hybrid mode or
     an operating region.
   - **N1.** The difference is one of indexing, not of kind.
2. **The detectability gate.** A witness may say "nominal" only when the
   RPM-implied loss predicts a response of at least 2× its threshold
   (prereg §7.3). This is exoneration conditioned on the fault model: GDE+
   physical negation (B30) and sensitivity-conditioned FDI (B138). **N1**; a
   specific quantitative rule.
3. **The negative control.** V4_INVALID_WINDOW reads the dynamics witness in
   T3 and **predicts** WRONG on case A (H3(b)).
   - The phenomenon is documented (PX4, V4).
   - Ablations that remove components are routine (S2Q40).
   - A preregistered control built to measure the wrong-attribution rate that
     out-of-window use causes was not found in the searched sources.
   - **N2** as part of MNC-2; a small element.
4. **Architectural honesty.** CSIA v2 is atemporal. The windows live in the
   XSYS-001 adapter. "Temporal evidence validity" is **not** an architectural
   property of CSIA today.

**Survives?** Only in the narrow instance form, inside MNC-1: **N2**. As a
general representation, **N1**. The broad claim "different evidence channels
are valid at different phases of a fault" is **dead**: TRANSCEND, B119,
ArduPilot and PX4.

## 9. Step 9: ambiguity

**The mapping.**

| CSIA verdict | definition in code | established counterpart | difference |
|---|---|---|---|
| UNIQUE / SUPPORTED | one survivor **and** affirmatively confirmed (`localization.py`, `attribution.py`) | a single minimal diagnosis (B28) that also **covers** the observations, the abductive end of the spectrum (B31); fault-model exoneration (B30) | none in kind; a stated conjunction of two known criteria |
| AMBIGUOUS | several survivors, or a confirmed survivor alongside unresolved ones | multiple minimal diagnoses (B28, B29); ambiguity group (B62; VLRS, S2Q24); ranked ambiguity groups (P06) | none |
| UNSUPPORTED | (i) every hypothesis refuted; (ii) exactly one **unconfirmed** survivor; (iii) implicated by a cross-domain relation without its own adverse evidence (`attribution.py`) | (i) no consistent diagnosis under the fault models, meaning model incompleteness (B28, B30); (ii) a case consistency-based diagnosis would name and abductive diagnosis would not (B31); an INSUFFICIENT_EVIDENCE verdict (B137); integrity "not available" (B87) | **one verdict overloads situations the literature keeps apart.** A reviewer will read this as a weakness, not a contribution |
| NO_EVIDENCE | no symptom | no detection | none |

**Material difference?** No. "The system can say AMBIGUOUS" is candidate-set
diagnosis. "Survival is not support" is the consistency–abduction spectrum
(B31). An explicit insufficient-evidence verdict exists in other diagnosis
domains (B137, 2026) and in navigation integrity (B87). The three-valued
predicate is Kleene/LTL3 logic and the SEVA measurement status (B70, B89).

**Survives?** **No: N0** for ambiguity preservation. **N1** for the verdict
taxonomy, which is terminology plus a stated rule. Stop describing
AMBIGUOUS/UNSUPPORTED as a CSIA contribution.

## 10. Step 10: evidence sufficiency and certification

**What CSIA has.** `csia_assurance/witness.py` defines an
`EXPERIMENTAL_SUPPORT_CERTIFICATE` with these fields:

- a target hypothesis;
- for each competitor: the active discriminator ids, evidence source ids, an
  `applicability_state` and a `freshness_state`;
- `competitors_without_witness`;
- `complete`, true iff every modelled competitor has at least one witness;
- configuration, software and evidence hashes;
- a semantics version, the hypothesis set, the evidence topology and
  `valid_until`.

The module docstring says it is **not** a certified safety artifact.
**The certificate is not produced on the v2 localization path that XSYS-001
uses.**

**Comparison.**

| family | what it guarantees | relation to the CSIA certificate |
|---|---|---|
| diagnosability (B36, B101) | offline: faults are distinguishable in principle | CSIA's runtime check is the online counterpart |
| distinguishing tests / D-matrix / testability (B62, B63, B64) | which tests separate which fault pairs | "every competitor has an active discriminator" is **pairwise distinguishability evaluated on the tests that actually fired** |
| consistency-based + abductive diagnosis (B28, B31) | the named diagnosis is the unique minimal consistent one and covers the observations | the same condition in logical form |
| sequential detection–isolation (B121, B122, B135) | a **bounded probability of false isolation** | strictly stronger: CSIA has no error probability |
| RAIM / ARAIM (B87) | a protection level against an alert limit, within an integrity-risk budget; otherwise "not available" | strictly stronger, and it already binds integrity to operation |
| set-membership FDI (B72, B111) | guaranteed isolation under bounded uncertainty | stronger: CSIA's thresholds carry no uncertainty bound |
| certified decisions / conformal RTA (B136, B139) | probabilistic certificates on actions or deadlines | stronger in the guarantee; different in object |
| assurance cases, ConSerts (B85, B86, B84) | a structured argument; conditional certificates | CSIA records evidence and does not argue |

**Distinct or only terminology?** **Mostly terminology plus engineering
packaging: N1.** The assertion rule is the standard isolation condition. What
CSIA adds is a machine-readable provenance record with explicit staleness
conditions: the hashes, hypothesis set, topology, semantics version and
horizon. That is an implementation detail, not a new assurance semantics, and
it carries **less** assurance than RAIM or false-isolation bounds.

**Survives?** **No** as a scientific contribution: N1. Stop calling it
"certification" without the qualifier the code already carries
("EXPERIMENTAL").

## 11. Step 11: action authority

**Classification: UNSUPPORTED.**

- CSIA issues no command. `csia/v2/functions.py` computes function eligibility
  only.
- The bounded-authority layer (FORGE) is not implemented.
- XSYS-001 does not test it.

The concept of mapping diagnostic, health or integrity state to allowed
authority, degraded mode, reconfiguration, continuation or abort is **KNOWN**:

- RAIM/ARAIM: an operation is not authorized when the protection level
  exceeds the alert limit (B87);
- Simplex and runtime assurance (B79, B80, B81);
- US 9,725,187: a health score from risk, confidence and benefit, compared
  with a threshold before reconfiguration (P24, V0);
- ConSerts (B84);
- automated contingency management (B97);
- assurance monitor plus contingency management (B120);
- US 12,087,171 (P08);
- fielded autopilots (**V4**):
  - ArduPilot's thrust boost, triggered by a diagnosis;
  - PX4's failsafe framework.

A later CSIA authority layer would have to be positioned against these. No
difference can be credited today: there is no implementation.

## 12. Step 12: patents

This has its own file, `research/csia_novelty_audit/CSIA_PATENT_PRIOR_ART_SCREEN.md`.
Ten patents are covered. The strongest technical threat to the XSYS-001
**question** is the EPOS family (P03–P05, P25). The strongest to the
action-authority **vision** is P24.

## 13. Step 13: the IVHM challenge

### The argument, as a reviewer who knows the literature would make it

> CSIA is a vehicle health-management reasoner with its parts renamed.
>
> - Its "domain plugins" are subsystem monitors, as in VIPR (B59).
> - Its three-valued `EvidenceRecord` is a monitor output with a "no computed
>   data" status (B63, B89).
> - Its "signature matrix" is a D-matrix (B62) or fault-signature matrix
>   (B08).
> - Its "set elimination" is consistency-based diagnosis (B28). The
>   "affirmative confirmation" is the abductive half of Console and Torasso's
>   spectrum (B31) and GDE+ exoneration (B30).
> - AMBIGUOUS is an ambiguity group (VLRS; P06).
> - Its UNSUPPORTED merges two situations the diagnosis community keeps apart.
> - "Cross-domain" reasoning is what vehicle-level reasoners have done since
>   the Boeing 777 central maintenance function (B58, P12).
> - "Temporal validity" is TRANSCEND's transient-to-steady-state progression
>   (B37), mode-scoped ARRs (B119), and gating logic that ArduPilot and PX4
>   ship today (B130, B131). And CSIA's own engine is atemporal: the windows
>   are a script in one experiment.
> - The "compensation witness" is ArduPilot's `thrust_balance` statistic,
>   running on thousands of vehicles (B130).
> - The "actuator versus telemetry" discrimination is spelled out in an engine
>   patent family: the minor-loop error is the shared symptom and the engine
>   response separates the causes (P03–P05). A 1987 patent (P01) and decades
>   of IMM/MMAE work (B43, B44) precede it.
> - The "certificate" is a distinguishing-test record, without the risk
>   quantification of RAIM (B87) or the false-isolation bound of Nikiforov
>   (B122).
> - "Bounded action authority" does not exist in the code.
>
> What remains is one simulation experiment on a simplified PX4 model, with
> one motor and one fault direction, and a multiplicative telemetry replay.
> Its methodology, preregistration and blinding, is standard in other
> sciences. Nothing here is a contribution to DX, SAFEPROCESS or PHM.

### Answer, claim by claim

| CSIA claim | does the criticism hold? | what, if anything, survives |
|---|---|---|
| heterogeneous cross-domain evidence (A) | **holds** | nothing |
| physical consequence as witness (B) | **holds** | nothing |
| actuator versus telemetry discrimination (C) | **holds** for the idea (EPOS, P01, B43/B44, B118) | the multirotor RPM-telemetry instance only (§6) |
| compensation as evidence (D) | **holds** (ArduPilot, V4) | its use as one of a windowed pair (MNC-1) |
| evidence validity by fault phase (E) | **holds** for the principle (B37, B119, ArduPilot/PX4 V4) | phase-indexed applicability of each witness, inside MNC-1 (N1 alone) |
| structural elimination (F) | **holds** | nothing |
| retained ambiguity (G) | **holds**; the UNSUPPORTED overloading is a fair criticism | nothing |
| sufficiency before attribution (H) | **holds**; CSIA's version is weaker than B87 and B122 | nothing |
| temporal + structural (I) | **holds** (B37, B39, B119, P07) | nothing, and CSIA v2 is atemporal |
| bounded authority (J) | **holds**; not implemented | nothing |
| IVHM architecture (K) | **holds** | nothing |
| the XSYS-001 matched-set experiment (L) | **partly holds**: the question is CLOSE_PRIOR_ART; the method is standard elsewhere | the specific matched-by-construction design with an invalid-window control, zero-WRONG and cluster-unit inference (MNC-2, N2) |

**Verdict on the challenge.** The criticism **survives** for every
architectural claim. Only two narrow distinctions survive (§14): an
experimental instance and an evaluation design. Neither is an architecture.

## 14. Step 14: minimum novel core by subtraction

The full subtraction is in `research/csia_novelty_audit/CSIA_MINIMUM_NOVEL_CORE.md`.
The remainder is:

- **MNC-1 (N2, LOW confidence, pending P0 verification).** For a closed-loop
  multirotor, physical rotor-effectiveness loss is separated from RPM-telemetry
  corruption that presents the same local RPM deficit. The separation pairs two
  witnesses whose informativeness the controller itself creates and destroys:
  - a body-rate witness along the rotor's loss axis, valid only in the
    transient T1;
  - an allocator-ratio witness, valid only after compensation (T3).

  Each witness is inapplicable (None), not negative, outside its window. Each
  may affirm "nominal" only if a genuine loss would have produced at least
  twice its threshold. The witnesses are combined by elimination, which names a
  cause only if the other is refuted and it is confirmed, and otherwise returns
  AMBIGUOUS.
- **MNC-2 (N2, LOW confidence).** The validation design for that pairing:
  - case B built to replay case A's observed RPM ratio, so the local symptom
    is identical by construction;
  - a preregistered invalid-window negative control;
  - frozen rules and two-stage label-blinded scoring;
  - zero-WRONG inside the primary decision;
  - the nuisance condition as the independent unit.

Everything else is removed.

## 15. Step 15: combination tests

| test | MNC-1 | full CSIA combination |
|---|---|---|
| solves a specific technical problem? | **yes, narrowly.** Local motor-failure logic cannot tell a failed motor from a telemetry defect: PX4's ESC check cannot (V4), and field reports show telemetry defects triggering it (B140, B146) | no specific problem is stated beyond "cross-system assurance" |
| requires a non-obvious interaction? | **not shown.** Closed-loop masking (B117, B118, B99), transient-then-steady analysis (B37) and compensation statistics (B130) are all known. A skilled FDI engineer could assemble the pair. Whether that is obvious is a judgement this audit does not make | no |
| produces a capability absent from the parts? | **not shown.** H3(a) tests only that combining windows "loses nothing": PRR(V3) ≥ max(PRR(V1), PRR(V2)). Each witness alone may already resolve the pair at its own checkpoint. The pair's added value is coverage at both checkpoints and robustness, not a new capability | no |
| introduces new assurance semantics? | **no.** Three-valued applicability and fault-model exoneration are known (B70, B89, B30, B138) | no; the certificate is N1 (§10) |
| introduces a new formal relationship? | **no.** The relation (the controller moves discriminating information from the plant-state channel to the effort channel as it compensates) is the known closed-loop masking relation (B117, B118, B129) | no |
| produces a new testable prediction? | **yes, narrowly.** On a matched set: reading the dynamics witness in its window yields no WRONG; reading it in T3 yields WRONG on case A (H3(b), H3(c)). The prediction follows from the known masking relation plus the apparatus data (prereg §3, finding 3), so it is a test of an instance rather than of a new law | no |

**Conclusion.** The full CSIA combination fails every test except, arguably,
the first. MNC-1 passes two tests narrowly: specific problem and testable
prediction. It fails the three that would make a combination a scientific
contribution in its own right: interaction, emergent capability and formal
relation. That is the profile of **a possibly distinct combination (N2)**,
not of a strong candidate.

## 16. Step 16: formalizing the candidate, iterated

**Draft 0** (the brief's example):

> "A diagnostic architecture in which heterogeneous evidence is assigned
> phase-dependent validity and used to eliminate cross-domain failure
> hypotheses, while retaining unresolved candidate sets when the available
> evidence does not separate all modeled causes."

| phrase | known? | closest |
|---|---|---|
| heterogeneous evidence | KNOWN | B59, B67, B68 |
| assigned phase-dependent validity | CLOSE_PRIOR_ART | B119 (mode), B142 (region), B37, B130/B131 (**V4**) |
| used to eliminate … failure hypotheses | KNOWN | B28, B29 |
| cross-domain | KNOWN | B58, B60 |
| retaining unresolved candidate sets | KNOWN | B28, B62, P06 |

**Result: N1.** Every clause has close prior art. TRANSCEND/QED plus hybrid
ARR diagnosis already do this in general. Draft 0 must not be used.

**Draft 1** (narrowed to the interaction):

> "For a closed-loop actuated vehicle, a discrimination between physical
> actuator-effectiveness loss and actuator-telemetry corruption that uses a
> physical-dynamics witness valid only before compensation completes and a
> controller-compensation witness valid only after, each inapplicable outside
> its window, combined by elimination that names a cause only when the rival
> is refuted and the cause confirmed."

Weak words:

- "closed-loop actuated vehicle" is too broad. EPOS (engines) and B118
  (electro-hydraulic) are closed-loop actuated plants.
- "actuator-telemetry corruption" versus "actuator-sensor fault" is close to
  terminological. The only real difference is that the corrupted channel is
  **outside the control loop**, which makes the problem easier, not harder
  (§7).
- "names a cause only when…" is known (B31).

**Result: N1–N2.**

**Draft 2** (final wording; every word checked against the frozen
preregistration):

> For a multirotor under closed-loop attitude control, where rotor *m*'s RPM
> telemetry is a monitoring channel and not a control feedback: let case A be
> a drop of rotor *m*'s thrust effectiveness to η < 1 at t0, and case B be
> nominal flight with rotor *m*'s RPM telemetry scaled to replay case A's
> observed RPM ratio.
>
> Define two witnesses:
>
> - **W_DYN**: the mean body-rate deviation, from its T0 baseline, along the
>   roll/pitch direction a thrust loss at rotor *m* produces, over
>   T1 = [t0, t0 + 0.2 s).
> - **W_CTRL**: the mean, over T3 = [t0 + 10 s, t0 + 15 s), of rotor *m*'s
>   allocator command divided by the mean of the others, minus its T0 value.
>
> Each witness takes True / False / None. It is None outside its window. It
> may affirm "nominal" only when the RPM-implied loss predicts a value of at
> least twice its threshold.
>
> A set-elimination rule names case A or case B only when the other is
> refuted by a witness and the named one is confirmed; otherwise it returns
> AMBIGUOUS.
>
> **Claimed only as a testable design:** on PX4 SIH, this rule separates
> matched pairs without naming a wrong cause, and reading W_DYN in T3 instead
> makes it name the wrong cause for case A.

**Which parts are known?** Every component. Section 7 covers W_CTRL, §8 the
windows and the gate, §9 the elimination rule, and §6 the pair. What was not
found in the searched sources is this exact conjunction, for this pair, with
this validation (§5). Every word is defensible because the sentence claims a
**design and a prediction**, not a mechanism or a result. **Status: N2.**

## 17. Step 17: status levels

| element | status | confidence | basis |
|---|---|---|---|
| cross-sensor validation, analytical redundancy | **N0** | high | B04–B06 |
| cross-domain evidence graph / signature matrix | **N0** | high | B08, B58–B62 |
| physical consequence as witness | **N0** | high | B44, B92, B130 (**V4**) |
| actuator-versus-sensor discrimination (general) | **N0** | high | P01, B43, B44, B46 |
| controller compensation as evidence | **N0** | high | B130 (**V4**) |
| compensation discriminating an actuator from its own sensor | **N1** | medium | B117, B118, EPOS (V0) |
| temporal fault signatures; transient then steady | **N0** | high | B37, B38, B40 |
| per-witness phase validity (representation) | **N1** | medium | B119, B142, B70, B89, B130/B131 (**V4**) |
| out-of-regime evidence causing wrong attribution (phenomenon) | **N1** | medium | B131 (**V4**), B117 |
| structural elimination, candidate sets, AMBIGUOUS | **N0** | high | B28, B29, B62 |
| "survival is not support" verdict rule; UNSUPPORTED | **N1** | medium | B31, B137 |
| support certificate | **N1** | medium | B62, B87, B122 |
| temporal + structural integration | **N0** | high | B37, B39, B119, P07 |
| bounded runtime action authority | **UNSUPPORTED** (concept N0) | high | not implemented; B87, B79–B81, P24 |
| full CSIA architecture as a combination | **N1** | medium | §13 |
| **MNC-1** windowed paired witnesses, physical versus RPM telemetry, multirotor | **N2** | **LOW** | §§5–8, 16; pending the P0 queue |
| **MNC-2** matched-by-construction validation with an invalid-window control | **N2** | **LOW** | §§4, 6; analogues B147, B65, B71, B122 |

**No element is N3.** Two came closest. The multirotor RPM-telemetry instance
has close analogues on other plants (EPOS, B118). The matched-by-construction
replay has a close analogue in constructed physically consistent corruption
(B147). **No element is N4**, because no closest source was read at V3/V4
apart from the autopilot code, and that code kills claims rather than
supporting them.

## 18. Steps 18–20: boundary, IP map, queue

- `research/csia_novelty_audit/CSIA_PUBLICATION_CLAIM_BOUNDARY.md`
- `research/csia_novelty_audit/CSIA_IP_CANDIDATE_MAP.md`
- `research/csia_novelty_audit/CSIA_FULLTEXT_VERIFICATION_QUEUE.md`

## 21. Step 21: search limitations did not become distinctions

Four checks keep search limitations from being read as distinctions:

- Every cell that could not be verified is UNCLEAR, with the missing material
  named.
- No status in §17 is higher than what the searched material permits.
- Three elements that looked apparently distinct at snippet level were
  **downgraded** after follow-up searches:
  - the matched replay, because of B147;
  - the "temporal validity" representation, because of B142 and the V4
    autopilot code;
  - compensation-as-witness, because of the V4 ArduPilot code.
- Where nothing matching was found, the text says "no directly matching work
  was identified in the searched sources".

## Final report

1. **Strongest prior-art threat.** Two, for different reasons.
   - Against the XSYS-001 **question**: the EPOS patent family (P03–P05, P25),
     V0. Its rendered text states that an actuator-sensor fault and an
     actuator-hardware fault share the minor-loop tracking error, and that the
     engine response distinguishes them.
   - Against CSIA's **mechanisms**: ArduPilot (B130), verified at **V4**. It
     uses the controller's per-motor demand imbalance and yaw integrator as
     root-cause evidence, conjoined with a physical consequence and context
     validity gates, followed by a bounded response. The XSYS-001 compensation
     statistic belongs to the same family as its `thrust_balance`.
2. **Dead broad claims.**
   - cross-system or cross-domain assurance as such;
   - physical consequences as witnesses;
   - actuator-versus-sensor discrimination;
   - controller compensation as evidence;
   - "evidence valid at different fault phases" as a principle;
   - structural elimination;
   - ambiguity preservation and the AMBIGUOUS/UNSUPPORTED/NO_EVIDENCE taxonomy
     as a contribution;
   - evidence sufficiency and "certification" as a contribution;
   - temporal-plus-structural diagnosis;
   - bounded action authority (not implemented);
   - "CSIA is a new architecture".
3. **Minimum core that survives.**
   - MNC-1: the windowed pairing of a transient dynamics witness and a
     post-compensation allocator witness, each inapplicable outside its window
     and detectability-gated, combined by ambiguity-preserving elimination.
     It separates physical rotor-effectiveness loss from matched RPM-telemetry
     corruption on a multirotor.
   - MNC-2: its matched-by-construction validation design.
4. **Status.**
   - MNC-1: **N2**, LOW confidence, pending P0 full text.
   - MNC-2: **N2**, LOW confidence.
   - Every other element: N0 or N1 (table in §17). Action authority is
     UNSUPPORTED.
5. **Strongest threat to XSYS-001 experimental novelty.**
   - The EPOS family: the same question on a jet engine, V0.
   - B118: actuator versus feedback-sensor isolation through closed-loop
     propagation, V0.
   - Three unread multirotor sources could hold the instance itself:
     B123/B124, B125, and the unattributed INDI source that splits actuator
     dynamics from effectiveness using RPM.
6. **Does controller compensation as diagnostic evidence survive?** **No: N0.**
   ArduPilot (V4) is the closest source. It survives only as one half of
   MNC-1. Its use to separate an actuator from its own sensor is N1 (B117,
   B118, EPOS).
7. **Does temporal evidence validity survive?** **Not as a principle.**
   - The principle is dead (B37, B119, B130/B131 at V4).
   - The representation is N1: per-witness applicability indexed by fault
     phase.
   - It survives only inside MNC-1 (N2).
   - CSIA v2 itself is atemporal.
8. **Does ambiguity preservation survive?** **No: N0.** The taxonomy is N1,
   and UNSUPPORTED is overloaded.
9. **Does evidence sufficiency / certification survive?** **No: N1.** It is
   terminology plus a provenance record, weaker than RAIM and false-isolation
   bounds, and absent from the XSYS-001 path.
10. **Does the full CSIA combination survive?** **No: N1.** No emergent
    capability, interaction or formal relation is shown (§15).
11. **Strongest patent threat.**
    - EPOS family (P03–P05, P25; assignee shown as United Technologies /
      Raytheon Technologies, now RTX) for the XSYS-001 idea.
    - US 9,725,187 (P24; Boeing) for the action-authority vision.
    - All claims unread; technical triage only.
12. **The 20-source queue.** See `CSIA_FULLTEXT_VERIFICATION_QUEUE.md`.
    - **P0:** B118; EPOS family text and claims; B117; B119; B37;
      B38/B39; B123/B124; the INDI RPM-split source; B68; B59/B60.
    - **P1:** P07; P24; B126; B121/B122; B71; B31; P06.
    - **P2:** B125; B40; B69.
13. **Best defensible paper contribution today.** A carefully scoped
    experimental-design paper, or the design section of a paper, making these
    points:
    - Physical rotor-effectiveness loss and matched RPM-telemetry corruption
      form a hard pair for local motor-failure logic.
    - A preregistered, label-blinded, zero-WRONG test is specified for whether
      a transient dynamics witness and a post-compensation allocator witness,
      each used only in its window, separate them without naming a wrong cause.
    - The design is positioned explicitly against EPOS, B117, B118, TRANSCEND,
      B119 and ArduPilot/PX4, as an application and evaluation of known
      principles, not a new diagnostic principle.
14. **Stronger contribution available conditionally if XSYS-001 supports its
    primary hypothesis.** Scoped to simulation (PX4 SIH), one motor, one fault
    direction, one airframe and an internal comparison: evidence that the
    windowed pairing resolved matched physical-versus-telemetry pairs with a
    cluster lower bound above 0.5 and no wrong attribution. If H3(b) is also
    supported, evidence that out-of-window use of the dynamics witness produced
    wrong attribution in the same setting. The status stays **N2**. A result
    strengthens evidence for the instance; it does not change what is known in
    the literature.
15. **Stop using immediately:**
    - "novel" or "first" without qualification;
    - "cross-system assurance" without the gloss "analytical redundancy
      across subsystems";
    - "certificate" or "certification" without "experimental" and without
      saying it is weaker than RAIM-style integrity;
    - "temporal evidence validity" as a CSIA architectural property (v2 is
      atemporal);
    - "controller compensation as a new witness";
    - "CSIA distinguishes sensor from actuator faults" as a contribution;
    - AMBIGUOUS/UNSUPPORTED as a contribution;
    - any action-authority or FORGE claim;
    - Draft 0 of §16.
16. **Exact remaining uncertainty from blocked full-text access.**
    - Every paper and patent is V0.
    - The ten P0 sources could each move MNC-1 from N2 to N1. The critical
      unknowns:
      - whether the B118 or EPOS descriptions use **transient-phase**
        evidence or **controller effort** as a witness;
      - whether B123/B124/B125, or the INDI source, treat **RPM-sensor
        faults** against loss of effectiveness;
      - whether TRANSCEND, QED or B119 mark evidence **inapplicable**, rather
        than merely unused, after compensation;
      - whether VIPR or R2U2 SHM report windowed witnesses with ambiguity
        groups for actuator-versus-sensor pairs.
    - No evaluation section of any V0 source was read. F23, F24, F26 and F27
      are therefore UNCLEAR for every published source. MNC-2's status rests
      on search-level absence plus the B147 analogue.
    - The ArduPilot fetch has no commit hash; the raw host serves `master`.
    - No patent claim was read. The priority dates of P03–P07 and P24 are
      unconfirmed.

**Verdict:** `CSIA_NOVELTY_REDUCED_TO_NARROW_COMBINATION`
