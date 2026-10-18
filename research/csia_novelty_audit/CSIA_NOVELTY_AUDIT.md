# CSIA novelty and prior-art audit (pre-result)

| | |
|---|---|
| date | 2026-09-27 |
| status | **PRE-RESULT**: written while the XSYS-001 confirmatory campaign was running, and logically independent of its outcome |
| scope | what, if anything, is novel about CSIA, judged against the public literature and patents |
| package | this file; `CSIA_PRIOR_ART_MATRIX.csv`; `CSIA_CLOSEST_SYSTEMS.md`; `CSIA_TERMINOLOGY_CROSSWALK.md`; `XSYS_001_NOVELTY_AUDIT.md`; `CSIA_NOVELTY_RED_TEAM.md`; `CSIA_CANDIDATE_CONTRIBUTIONS.md`; `BIBLIOGRAPHY.md`; `NOVELTY_SEARCH_LOG.md`, all in `research/csia_novelty_audit/` |
| modifies | **nothing**. No CSIA code, no XSYS-001, A1 or A2 artifact, no PX4 file, manifest, threshold or hypothesis |

## 0. Independence and evidence limits

**Independence.** The inputs were:

- the public literature;
- CSIA's pre-confirmatory documents: the architecture, the frozen XSYS-001
  preregistration and its amendments, and the repository's earlier novelty
  audits.

No confirmatory log, stage output, completion record or result was opened.
The campaign's own watchers were removed before the audit began, so nothing
would prompt campaign actions during it.

Every conclusion here reads the same whether XSYS-001's primary result is
SUPPORTED or NOT SUPPORTED. The result may be integrated only in a later,
separately labelled update.

**Evidence limits.**

- **Access.** The environment's egress policy blocked every full-text route:
  scholarly APIs, DOI resolution, arXiv, NTRS, IEEE, ScienceDirect and patent
  databases. Only a web-search tool worked.
- **Consequence.** No source was read in full, and every characterization
  rests on search summaries. That can only **understate** prior art.
  Section 1 of `research/csia_novelty_audit/BIBLIOGRAPHY.md` records the rules.
- **Absence claims.** They take the form "No directly matching prior work was
  identified in the searched literature". The search scope is in
  `research/csia_novelty_audit/NOVELTY_SEARCH_LOG.md`: about 110 queries,
  covering all fifty required domains, a separate patent screen, and a list
  of gaps not searched.
- **Patents.** This is a technical screen, not legal advice. No claim was read.

**Status vocabulary** (as required):

| status | meaning |
|---|---|
| KNOWN | established; directly anticipated |
| LIKELY_KNOWN | almost certainly established; anticipation seen in part |
| CLOSE_PRIOR_ART | a close antecedent exists; a narrow difference may remain |
| POSSIBLY_DISTINCT | a difference may exist but is unproven |
| APPARENTLY_NOVEL | no antecedent found in the searched literature; weak evidence |
| UNSUPPORTED_NOVELTY_CLAIM | claimed, or implied, without support |

"NOVEL" is never used as a definitive status.

## 1. The answer, in one paragraph

**Almost everything CSIA does has a named antecedent, most of them decades
old.**

- **Old.** Cross-sensor and cross-domain analytical redundancy, 1970s–1990s.
  Consistency-based elimination with candidate sets, 1987. Transient-versus-
  steady-state fault signatures, 1999. Sensor-versus-actuator fault
  discrimination through the vehicle's dynamics, from a 1987 patent and 1998–99
  multiple-model work. Ambiguity groups, from testability standards. Controller
  compensation as fault evidence, in a fielded open-source autopilot.
  Three-valued verdicts. Evidence-bounded authorization, from GNSS integrity.
- **Recent.** Temporal monitoring feeding diagnosis on UAS, from 2014.
- **What survives** is narrow, and none of it is an algorithm or an
  architecture:
  1. An **experimental instance**: a physical rotor-effectiveness loss against
     RPM-telemetry corruption matched by construction, separated only by
     time-windowed dynamics and compensation evidence, with ambiguity
     permitted.
  2. An **evaluation methodology** not seen in the searched FDI literature:
     preregistered, label-blinded, and with zero wrong attributions required
     in the primary rule.
  3. A **configuration** of known verdict logic, chosen for assurance use.
     Temporal validity is expressed as applicability, and survival alone is
     not confirmation.

All three are held at LOW or LOW-MEDIUM confidence.

## 2. The seven levels, evaluated independently

| level | question | status | confidence | decisive prior art |
|---|---|---|---|---|
| **L1** component techniques | CUSUM, GLR, residuals, parity space, observers, MMAE/IMM, Bayesian networks, fault trees, runtime monitors | **KNOWN** | HIGH | B02, B03, B04, B05, B10, B11, B12, B13, B35, B70 |
| **L2** cross-sensor reasoning | multiple sensors validate or isolate sensor faults | **KNOWN** | HIGH | B04, B05, B22, B87, B90, B95 |
| **L3** cross-subsystem / cross-domain diagnosis | evidence from other subsystems discriminates causes | **KNOWN** | HIGH | B58 (1992), B46, B47, B59, B60, P03, P12 |
| **L4** temporally conditioned cross-system evidence | the value of an evidence channel depends on the fault phase (onset, transient, compensation, steady state) | **CLOSE_PRIOR_ART** | MEDIUM | B37 (1999), B38, B40, B67; B56 for the fielded latch. The difference left is representational: out-of-window evidence is *inapplicable*, never negative (C6) |
| **L5** assurance semantics | UNIQUE / AMBIGUOUS / UNSUPPORTED / NO_EVIDENCE / CONFLICT, and refusing unsupported root-cause claims | **CLOSE_PRIOR_ART** | MEDIUM | B28 and B29 (all minimal diagnoses), B31 (the consistency-plus-abduction spectrum), B70 (the inconclusive verdict), B87 (integrity not available), B71 (FDI correctness), B89 (SEVA status). CSIA v2 defines no CONFLICT verdict (evidence conflict surfaces as UNSUPPORTED), and the name would collide with the established DX term |
| **L6** certification / action semantics | evidence sufficiency governing what may be done | **CLOSE_PRIOR_ART** as a principle; **UNSUPPORTED_NOVELTY_CLAIM** as a CSIA capability | MEDIUM / HIGH | B87 (protection level against alert limit), B84 ConSerts, B77 safe diagnosability, B79–B82 RTA, B66 Livingstone. CSIA issues no command (C19) |
| **L7** the full architecture | fast local evidence, temporal reasoning, structural cross-domain reasoning, hypothesis discrimination, explicit ambiguity, evidence sufficiency and bounded adaptation, together | **POSSIBLY_DISTINCT** | LOW | nearest: B67/B68 (R2U2), B59 (VIPR), B66 (Livingstone), B37/B39 (TRANSCEND/QED), B76, B69. No emergent property shown. The "bounded adaptation" element does not exist in CSIA |

**Reading L4–L7.** Each level up adds one more known ingredient. What climbs
is the specificity of the combination, not the novelty of any part. L7's
POSSIBLY_DISTINCT rests on **not having seen** a system combining every
element in the summaries. It does not rest on having shown that the
combination does anything its parts cannot.

## 3. Claim-by-claim summary

The full matrix is `research/csia_novelty_audit/CSIA_PRIOR_ART_MATRIX.csv`,
with 20 atomic claims and all required columns. C1–C12 are the brief's claims.
C13–C20 are the additional claims the repository implies.

| id | claim (short) | status | confidence |
|---|---|---|---|
| C1 | cross-sensor evidence isolates sensor faults | KNOWN | HIGH |
| C2 | cross-domain evidence distinguishes causes local evidence cannot | KNOWN | HIGH |
| C3 | vehicle dynamics as independent witness | KNOWN | HIGH |
| C4 | controller compensation as diagnostic evidence | KNOWN | MEDIUM-HIGH |
| C5 | evidence usefulness changes through onset and compensation | KNOWN | HIGH |
| C6 | explicit conditioning of evidence on temporal validity | CLOSE_PRIOR_ART | MEDIUM |
| C7 | structural elimination plus temporal accumulation | KNOWN (and CSIA does less of it than the prior art) | HIGH |
| C8 | preserve ambiguity | KNOWN | HIGH |
| C9 | separate detection, isolation, certification and authorization | LIKELY_KNOWN | MEDIUM |
| C10 | adaptation bounded by the strongest justified conclusion | CLOSE_PRIOR_ART | MEDIUM |
| C11 | the aircraft as an evidence graph | KNOWN | HIGH |
| C12 | the combined architecture is distinct | POSSIBLY_DISTINCT | LOW |
| C13 | three-valued evidence; absence of evidence is not health | KNOWN | HIGH |
| C14 | concentration is not support; statically decidable separability | LIKELY_KNOWN (defers to `research/math-paper/NOVELTY_AUDIT.md`) | MEDIUM |
| C15 | diagnostic self-occlusion | CLOSE_PRIOR_ART | MEDIUM |
| C16 | gated negative evidence | CLOSE_PRIOR_ART | MEDIUM-LOW |
| C17 | matched-set, preregistered, blinded, zero-WRONG validation methodology | APPARENTLY_NOVEL | LOW |
| C18 | the XSYS-001 question as an experimental instance | POSSIBLY_DISTINCT | LOW-MEDIUM |
| C19 | CSIA provides bounded runtime assurance | UNSUPPORTED_NOVELTY_CLAIM | HIGH |
| C20 | a support certificate of separating evidence | LIKELY_KNOWN | MEDIUM |

## 4. The hardest question

> Could a knowledgeable reviewer reasonably say: "This is just Integrated
> Vehicle Health Management / model-based FDI with different terminology"?

### 4.1 The strongest argument FOR the criticism

1. **The evidence layer is analytical redundancy.** Every witness is a
   residual against a model or baseline, thresholded (B04, B05, B06; red team
   R1).
2. **The decision layer is consistency-based diagnosis.** It uses conflict-
   driven set elimination over a fault signature matrix (B08, B28, B29, B40).
   The FDI and DX formulations were shown equivalent under conditions in 2004
   (B27).
3. **The verdict lattice is covered.**
   - AMBIGUOUS is the minimal-diagnosis set (B28) or an ambiguity group (B62,
     B64).
   - UNSUPPORTED is "no consistent diagnosis" (B28, B102).
   - Inconclusive verdicts are standard in runtime verification (B70).
   - Requiring confirmation beyond survival is the abductive end of
     Console & Torasso's spectrum (B31).
4. **Temporal validity is TRANSCEND's insight.** Evidence is read by fault
   phase, transient then steady state (B37). Event-based orderings (B38) and
   timed signature matrices (B40) extend it. CSIA's v2 is **less** temporal
   than this prior art (C7).
5. **Cross-subsystem reasoning is IVHM's definition.**
   - The 777 central maintenance function traced cascaded LRU faults to a
     power bus in 1992 (B58).
   - VIPR reasons over supplier monitors at aircraft level and reports ranked
     ambiguity groups (B59, B60).
   - R2U2 combines temporal-logic observers with model-based and Bayesian
     diagnosis on UAS (B67, B68).
6. **The XSYS-001 signals are established.**
   - Sensor-versus-actuator discrimination through the vehicle's response:
     P01 (1987), B43 (1998), B44 (1999), B46 (2003), and P03 (engine response
     separating actuator-sensor drift from actuator hardware failure).
   - Compensation as evidence: B55, fielded in ArduPilot.
7. **Evidence-bounded authorization is RAIM** (B87), plus ConSerts (B84) and
   runtime assurance (B79–B81). CSIA does not even implement authorization
   (C19).
8. **There is no new algorithm.** The repository's own mathematical audit
   labels every proposition KNOWN.

### 4.2 The strongest evidence-based argument AGAINST it

1. **The refusal rule.** In CSIA a hypothesis is never reported as the cause
   unless every alternative is refuted **and** it is affirmatively confirmed,
   by evidence admissible in its own time window. The IVHM reasoners seen in
   summary (VIPR, P06) *rank* ambiguity groups and aggregate belief. MMAE, IMM
   and Bayesian-network isolators report the most probable hypothesis. Against
   probabilistic isolation, the rule is a real difference in output
   semantics, but it is **not** a difference from consistency-based diagnosis
   (B28, B31).
2. **Out-of-window evidence is inapplicable, not negative.** No searched
   summary showed this representation. It is weakly distinct and plausibly
   present in hybrid or mode-dependent diagnosis (B41, B42), which was not
   read.
3. **The matched-set construction.** Case B replays case A's ratio, so the
   local channel carries no discriminating information by design. Every
   resolution must come from other domains. No searched source used such a
   construction for an FDI evaluation.
4. **The evaluation standard.** A preregistered, label-blinded protocol, with
   zero wrong attributions required in the primary decision, was not seen in
   the searched FDI, PHM or UAV literature. The conceptual antecedents are
   B71 (formal correctness) and B72 (guaranteed no false alarm).

### 4.3 Which properties would have to hold for the criticism to fail

The criticism **stands on present evidence**. It would fail only if one of
the following were established:

| # | property | test | exists now? |
|---|---|---|---|
| H1 | **Output-semantic superiority on a matched set.** Established isolators (MMAE/IMM, a hybrid dynamic Bayesian network, a TRANSCEND/QED signature matcher, a set-valued observer) produce WRONG or unjustified UNIQUE outputs where CSIA returns AMBIGUOUS, at comparable pair resolution | a head-to-head baseline on the XSYS-001 matched set, scored with the same taxonomy | **no**. XSYS-001 compares only internal variants V0–V4 |
| H2 | **A soundness property with proof.** Under stated model-validity, noise-bound and window assumptions, UNIQUE ⇒ the true cause; unseparated causes ⇒ AMBIGUOUS. It must go beyond B71 (discrete synthesis) and B72 (bounded linear) | a formal statement and proof | **no** |
| H3 | **A representational difference in the temporal model** that the hybrid / mode-dependent-ARR literature lacks | full reading of B37, B41, B42 and B69 | **not checked** |
| H4 | **The closest reasoners lack refusal semantics.** VIPR and R2U2 would name a cause under the matched symptom | full reading of B59 and B68, or running them | **not checked** |

Without H1 or H2, the fair verdict is that **the reviewer's criticism is
substantially correct at the algorithmic and architectural levels**. It is
answerable only at the level of experimental instance and evaluation
methodology, and there only modestly.

## 5. Novelty versus validation novelty

The six kinds are assessed separately in
`research/csia_novelty_audit/CSIA_CANDIDATE_CONTRIBUTIONS.md` §1.

| kind | status |
|---|---|
| algorithmic | KNOWN |
| architectural | POSSIBLY_DISTINCT (LOW) |
| assurance-semantic | CLOSE_PRIOR_ART |
| experimental | POSSIBLY_DISTINCT (LOW-MEDIUM) |
| validation-methodology | APPARENTLY_NOVEL (LOW) |
| product / engineering | KNOWN |

The underlying techniques are known. The strongest remaining candidates are
experimental and methodological. They are not algorithmic or architectural.

## 6. Publication positioning

**An empirical and methodological study of an established diagnostic
formulation.** It is consistency-based diagnosis over time-windowed
analytical-redundancy evidence, applied to a deliberately matched multirotor
actuator-versus-telemetry case, under a preregistered, label-blinded,
zero-wrong-attribution protocol. It must cite:

- Reiter, and Console & Torasso;
- TRANSCEND and QED;
- R2U2 and VIPR;
- the IMM/MMAE sensor-versus-actuator literature, P01 and P03;
- RAIM;
- ArduPilot.

**Not** a new algorithm. **Not** a new architecture. **Not** new assurance
semantics. The details, and the ranking of candidate labels, are in
`research/csia_novelty_audit/CSIA_CANDIDATE_CONTRIBUTIONS.md` §2.

## 7. The novelty boundary

> The potentially distinct contribution is **not**:
>
> - cross-sensor or cross-domain analytical redundancy;
> - consistency-based candidate elimination;
> - ambiguity groups;
> - temporal fault signatures;
> - vehicle dynamics or controller compensation as fault evidence;
> - sensor-versus-actuator fault discrimination;
> - three-valued verdicts;
> - runtime assurance.
>
> These are established.
>
> It **is** the formulation and preregistered, label-blinded evaluation of a
> **zero-wrong-attribution verdict rule**. The rule issues a unique cause only
> when every alternative is refuted by analytical-redundancy evidence
> admissible in its own physically justified time window, and otherwise
> returns AMBIGUOUS, UNSUPPORTED or NO_EVIDENCE.
>
> The conditions (D): a matched pair whose local symptom is identical by
> construction, meaning physical rotor-effectiveness loss against RPM-telemetry
> corruption replaying the same ratio, on a closed-loop multirotor simulation
> (PX4 SIH), with the nuisance condition as the independent unit.
>
> The semantics (E): out-of-window or ungated evidence is inapplicable, never
> negative, and survival without affirmative confirmation is never reported
> as a cause.

Even this statement fails if a professional search finds any of:

- a matched sensor-corruption versus physical-fault evaluation (the ProDiMES
  benchmark and the EPOS patent family are the suspects);
- a registered or blinded FDI evaluation;
- the temporal-applicability representation in the hybrid-diagnosis
  literature.

**In that case the literature supports no novelty statement beyond "a careful
application", and this audit says so in advance.**

---

## 8. Final report

### A. The strongest established prior art against CSIA novelty

1. **Mosterman & Biswas, TRANSCEND (B37, 1999).** It reads evidence by fault
   phase and refines candidate sets from transient signatures toward
   steady-state analysis. This covers C5 and C7, and most of C6.
2. **Reiter (B28) and de Kleer & Williams (B29), 1987**, with **Console &
   Torasso (B31), 1991**. They give candidate-set diagnosis and the
   consistency-plus-abduction spectrum behind CSIA's verdict rule (C8, L5).
3. **The sensor-versus-actuator discrimination lineage.** US 4,641,517 (P01,
   1987); Zhang & Li IMM (B43, 1998); Maybeck MMAE (B44, 1999); Kobayashi &
   Simon (B46, 2003); and the EPOS engine patents (P03–P05). P03 states that
   the plant's response distinguishes an actuator-sensor fault from an
   actuator hardware fault (C3, XSYS question 2).
4. **R2U2 (B67, B68).** On-board UAS health management combining temporal-logic
   observers with model-based and Bayesian diagnosis across sensor, software
   and hardware (C7, C12).
5. **VIPR (B59, B60) and the Boeing 777 central maintenance function
   (B58).** Aircraft-level cross-subsystem root-cause reasoning with
   ambiguity groups (C2, C8, C11).
6. **ArduPilot thrust-loss detection (B55).** Controller compensation, as
   motor saturation, used as propulsion-failure evidence in a fielded
   autopilot (C4).
7. **RAIM / ARAIM (B87).** Evidence sufficiency bound to operational
   authorization (C9, C10).

### B. The strongest apparently distinct CSIA contribution

The **validation methodology**, applied as a whole to an FDI question
(C17, APPARENTLY_NOVEL):

- a matched-by-construction counterfactual for the local channel;
- preregistration with frozen manifests;
- two-stage label-blinded scoring;
- zero wrong attributions in the primary decision;
- the nuisance condition as the unit of the bound.

The closely related **experimental instance** (C18, POSSIBLY_DISTINCT) comes
next. Neither is algorithmic or architectural.

### C. Claims CSIA should stop calling novel

1. Cross-sensor or cross-domain validation (C1, C2).
2. "Physical consequence as an independent witness" (C3).
3. Controller compensation as diagnostic evidence (C4).
4. "Evidence value changes through the transient" (C5).
5. Ambiguity preservation (C8).
6. The evidence graph (C11).
7. Three-valued evidence / "absence of evidence is not health" (C13).
8. Temporal evidence accumulation (C7). CSIA's v2 is atemporal.
9. Any "bounded runtime assurance" capability (C19). None exists.
10. Any "new algorithm" or "new architecture" wording.

### D. Claims that remain potentially novel

| claim | status | confidence |
|---|---|---|
| C17 validation methodology | APPARENTLY_NOVEL | LOW |
| C18 XSYS-001 experimental instance | POSSIBLY_DISTINCT | LOW-MEDIUM |
| C12 full combination | POSSIBLY_DISTINCT | LOW |
| C6 temporal validity as applicability | CLOSE_PRIOR_ART | MEDIUM |
| C9 a named certification stage for root-cause attribution | LIKELY_KNOWN | MEDIUM |

### E. Confidence levels

| judgement | confidence |
|---|---|
| L1–L3 (and C1–C5, C7, C8, C11, C13) KNOWN | HIGH |
| L4 / L5 / L6 (C6, C9, C10, C15, C16) close prior art | MEDIUM (MEDIUM-LOW for C16) |
| L7 / C12 possibly distinct | LOW |
| C18 possibly distinct | LOW-MEDIUM |
| C17 apparently novel | LOW |
| C19 unsupported | HIGH |

All confidences are capped by snippet-level access (§0).

### F. Exact literature gaps remaining

1. Full texts of B59 (VIPR), B68 (R2U2 SHM), B69 (RV + MBD in LOLA), B37, B38,
   B41, B42, B71.
2. Full claims of P03–P05 (EPOS), P06 (RTX), P07 and P08.
3. SAE IVHM standards: ARP6803, AIR6900, JA6268.
4. HUMS credit guidance: FAA AC 29-2C, MG-15.
5. ARP4754A / ARP4761.
6. The ProDiMES benchmark, PHM data-challenge rules and NASA DASHlink
   benchmarks.
7. DShot / CAN ESC-telemetry fault-injection and spoofing literature.
8. Registered reports in robotics and PHM.
9. Mode-dependent ARRs and possible conflicts in hybrid systems.
10. ArduPilot and PX4 detector source code.
11. SPRT-specific literature, CN patents and non-English literature.

### G. Best defensible paper positioning

**An empirical and methodological study of an established formulation**
(§6). Lead with the matched-set design and the preregistered zero-WRONG
protocol. Present the verdict rule as a stated configuration of
consistency-based diagnosis with abductive confirmation. Cite the full
antecedent list. Make no algorithmic or architectural claim.

A novelty claim beyond this requires H1 (a head-to-head baseline on the
matched set) or H2 (a soundness theorem), neither of which exists.

### H. Strongest patent / prior-art concern

This is a technical concern only; no legal conclusion is drawn.

1. **The EPOS family (P03–P05).** The summaries describe distinguishing an
   actuator-sensor fault from an actuator hardware fault by the plant's
   response. That is the XSYS-001 idea on a different plant and channel.
   Assignee not shown.
2. **US 11,061,390 (P06, RTX; Volponi, Tang, Lee).** It resolves ambiguity
   groups with evidence from a diagnosis matrix.
3. **US 12,134,484 (P07).** Structural-temporal fault-propagation-graph
   diagnosis for aircraft.
4. **US 12,087,171 (P08).** A run-time assurance module for dynamic contexts.
5. **US 12,397,908 (P09, Amazon).** Commanded against measured RPM, then
   mitigation.

The 1987 patent (P01) is prior art for the discrimination idea generally.
Freedom to operate and patentability were not assessed.

### I. Next literature searches required

In priority order:

1. Full-text read of B59, B68, B69.
2. P03–P05 and P06 claims.
3. B37, B41, B42 for the temporal-applicability representation.
4. The ProDiMES and PHM benchmark rules, for any matched sensor-bias versus
   component-fault design.
5. ESC / DShot telemetry fault-injection literature.
6. SAE IVHM standards and HUMS credit guidance, for certification semantics.
7. The registered-reports literature in robotics and PHM.
8. B71 against the zero-WRONG criterion.
9. ArduPilot and PX4 detector source.

Each is listed with its reason in
`research/csia_novelty_audit/NOVELTY_SEARCH_LOG.md` §6–§7.

### J. Is a deeper human patent and literature review warranted?

**Yes.** There are three reasons:

1. **Access.** Every full-text route was blocked. The judgements are
   snippet-level, and snippet-level evidence can only understate prior art.
2. **Patents.** At least five patents (P03–P09) sit close to the XSYS-001
   idea or to CSIA's ambiguity and assurance semantics. Only a professional
   search with claim reading can assess them.
3. **The fate of the surviving candidates.** Every surviving candidate (C17,
   C18, C12) rests on the **absence** of something in search summaries. A
   librarian-assisted search of PHM, DX and SAFEPROCESS proceedings, and of
   engine-diagnostics benchmarks, would settle them in either direction.

Until that review is done, no CSIA document or manuscript should use a
priority claim ("first", "novel", "new architecture") for any row of the
matrix.

---

This audit changes nothing in CSIA, XSYS-001, A1, A2, PX4, any manifest,
threshold or hypothesis, and it makes no recommendation based on any
confirmatory outcome.
